"""Functional deduplication for Sample-efficient FunSearch.

This module implements duplicate code-checking at the functionality level,
as described in the course requirement for "Sample-efficient FunSearch":

> "Instead of assessing blindly all programs/codes created by an LLM, 
>  can we design a duplicate code-checking mechanism to avoid FunSearch 
>  evaluating a code that has been previously evaluated?"

Key insight: Two codes that look different may have identical behavior.
We detect this by computing a "behavior signature" - the outputs of the
code on a set of probe instances.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .schemas import Candidate


@dataclass(frozen=True)
class BehaviorSignature:
    """Represents the functional behavior of a candidate.
    
    Two candidates with the same signature are functionally equivalent,
    even if their source code looks completely different.
    """
    hash: str
    vector: tuple[float, ...]
    
    @staticmethod
    def from_vector(vector: Sequence[float]) -> "BehaviorSignature":
        """Create a signature from a behavior vector."""
        tuple_vector = tuple(vector)
        payload = json.dumps(tuple_vector, separators=(",", ":"))
        hash_value = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        return BehaviorSignature(hash=hash_value, vector=tuple_vector)


@dataclass
class DeduplicationStats:
    """Statistics about deduplication effectiveness."""
    total_checked: int = 0
    duplicates_found: int = 0
    unique_passed: int = 0
    evaluations_saved: int = 0
    
    @property
    def dedup_rate(self) -> float:
        """Percentage of candidates identified as duplicates."""
        if self.total_checked == 0:
            return 0.0
        return self.duplicates_found / self.total_checked * 100


def _normalize_code(code: str) -> str:
    """Normalize code for comparison by removing comments and extra whitespace.
    
    This provides a fast first-pass check before expensive behavior testing.
    """
    import re
    # Remove single-line comments
    code = re.sub(r'#.*$', '', code, flags=re.MULTILINE)
    # Remove docstrings (triple-quoted strings)
    code = re.sub(r'""".*?"""', '', code, flags=re.DOTALL)
    code = re.sub(r"'''.*?'''", '', code, flags=re.DOTALL)
    # Normalize whitespace: collapse multiple spaces/newlines
    code = re.sub(r'\s+', ' ', code)
    # Strip leading/trailing whitespace
    return code.strip()


def _code_hash(code: str) -> str:
    """Compute hash of normalized code."""
    normalized = _normalize_code(code)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


class FunctionalDeduplicator:
    """Detects functionally duplicate candidates to avoid redundant evaluation.
    
    This implements the "Sample-efficient FunSearch" enhancement from the course:
    
    Two-stage deduplication:
    1. Code normalization hash: Fast check for textually similar code
    2. Behavior signature: Deep check for functionally equivalent code
    
    Example of functionally identical code (from course):
    ```python
    # Code A
    def mean(lst):
        return sum(lst) / len(lst)
    
    # Code B  
    def mean(lst):
        total = 0
        for x in lst:
            total += x
        return total / len(lst)
    ```
    Both produce the same output for any input -> same signature -> duplicate.
    """
    
    def __init__(
        self,
        probe_runner: Callable[[str, int], float],
        probe_seeds: Sequence[int] | None = None,
        cache_size_limit: int = 10000,
        use_code_hash: bool = True,  # Enable code normalization hash
    ) -> None:
        """Initialize the deduplicator.
        
        Args:
            probe_runner: Function that runs candidate code on a probe instance.
                          Takes (code: str, seed: int) -> score: float
            probe_seeds: Seeds for probe instances. More seeds = more accurate
                         but slower duplicate detection.
            cache_size_limit: Maximum number of signatures to cache.
            use_code_hash: Whether to use code normalization hash as first pass.
        """
        self._probe_runner = probe_runner
        self._probe_seeds = list(probe_seeds) if probe_seeds else [0, 1, 2, 3, 4]
        self._cache_size_limit = cache_size_limit
        self._use_code_hash = use_code_hash
        
        # Cache of evaluated behavior signatures
        self._signature_cache: set[str] = set()
        
        # Cache of code hashes (fast first-pass check)
        self._code_hash_cache: set[str] = set()
        
        # Stats tracking
        self._stats = DeduplicationStats()
    
    def compute_signature(self, code: str) -> BehaviorSignature:
        """Compute the behavior signature of a candidate's code.
        
        The signature is computed by running the code on multiple probe
        instances and recording the outputs. This captures the functional
        behavior regardless of code structure.
        """
        vector: list[float] = []
        for seed in self._probe_seeds:
            try:
                result = self._probe_runner(code, seed)
                vector.append(float(result))
            except Exception:
                # If code fails on probe, use a sentinel value
                vector.append(float("nan"))
        
        return BehaviorSignature.from_vector(vector)
    
    def is_duplicate(self, code: str) -> tuple[bool, BehaviorSignature]:
        """Check if a candidate's code is functionally duplicate.
        
        Two-stage deduplication:
        1. Fast check: normalized code hash (catches textually similar code)
        2. Deep check: behavior signature (catches functionally equivalent code)
        
        Returns:
            (is_duplicate, signature): Whether the code is a duplicate,
                                       and its computed signature.
        """
        self._stats.total_checked += 1
        
        # Stage 1: Fast code hash check
        if self._use_code_hash:
            code_h = _code_hash(code)
            if code_h in self._code_hash_cache:
                # Definitely a duplicate (same normalized code)
                self._stats.duplicates_found += 1
                self._stats.evaluations_saved += 1
                # Return a dummy signature for code duplicates
                return True, BehaviorSignature.from_vector([float("nan")])
            # Add to code hash cache
            self._code_hash_cache.add(code_h)
        
        # Stage 2: Behavior signature check (more expensive but catches functional duplicates)
        signature = self.compute_signature(code)
        
        if signature.hash in self._signature_cache:
            self._stats.duplicates_found += 1
            self._stats.evaluations_saved += 1
            return True, signature
        
        # New unique behavior - add to cache
        self._add_to_cache(signature.hash)
        self._stats.unique_passed += 1
        return False, signature
    
    def is_duplicate_candidate(self, candidate: "Candidate") -> tuple[bool, BehaviorSignature]:
        """Check if a Candidate object is functionally duplicate."""
        return self.is_duplicate(candidate.code)
    
    def register_signature(self, signature: BehaviorSignature) -> None:
        """Manually register a signature as evaluated."""
        self._add_to_cache(signature.hash)
    
    def _add_to_cache(self, signature_hash: str) -> None:
        """Add a signature to the cache with LRU-style eviction."""
        if len(self._signature_cache) >= self._cache_size_limit:
            # Simple eviction: remove a random element
            # (In production, use OrderedDict for true LRU)
            self._signature_cache.pop()
        self._signature_cache.add(signature_hash)
    
    def get_stats(self) -> DeduplicationStats:
        """Get deduplication statistics."""
        return self._stats
    
    def reset_stats(self) -> None:
        """Reset statistics counters."""
        self._stats = DeduplicationStats()
    
    def clear_cache(self) -> None:
        """Clear the signature cache and code hash cache."""
        self._signature_cache.clear()
        self._code_hash_cache.clear()
    
    @property
    def cache_size(self) -> int:
        """Current number of cached signatures (behavior signatures only)."""
        return len(self._signature_cache)


def create_binpacking_probe_runner(
    capacity: int = 100,
    num_items: int = 15,
) -> Callable[[str, int], float]:
    """Create a probe runner for bin packing candidates.
    
    The probe runner executes candidate code on small test instances
    to determine its behavior signature. Key insight: we record the
    SCORING DECISIONS, not just the final packing result. This way,
    different heuristics that happen to produce the same packing
    will still have different signatures.
    """
    import random
    
    def probe_runner(code: str, seed: int) -> float:
        """Run candidate code on a probe instance and return behavior fingerprint.
        
        We capture the scoring behavior, not just bin selection. This provides
        much better discrimination between different heuristics.
        """
        # Generate a deterministic instance with varied item sizes
        rng = random.Random(seed)
        
        # Use different distributions based on seed
        if seed % 3 == 0:
            items = [rng.randint(10, capacity - 10) for _ in range(num_items)]
        elif seed % 3 == 1:
            items = [rng.randint(1, capacity // 3) for _ in range(num_items)]
        else:
            items = [rng.choice([rng.randint(5, 25), rng.randint(40, 80)]) 
                     for _ in range(num_items)]
        
        # Create the score_bin function from code
        namespace: dict[str, object] = {"math": __import__("math")}
        try:
            exec(code, namespace)
            score_bin = namespace.get("score_bin")
            if not callable(score_bin):
                return float("nan")
        except Exception:
            return float("nan")
        
        # Simulate packing and capture SCORING BEHAVIOR (not just bin choice)
        # This is the key insight: different heuristics produce different scores
        behavior_fingerprint = 0.0
        bins_remaining = [capacity]
        
        for step, item_size in enumerate(items):
            scores_for_step: list[float] = []
            best_bin = -1
            best_score = float("-inf")
            
            # Collect scores for ALL valid bins (this captures the scoring logic)
            for i, remaining in enumerate(bins_remaining):
                if remaining >= item_size:
                    try:
                        score = float(score_bin(item_size, remaining, i, step))
                        scores_for_step.append(score)
                        if score > best_score:
                            best_score = score
                            best_bin = i
                    except Exception:
                        scores_for_step.append(float("nan"))
            
            # Add to fingerprint: score values themselves (not just which bin)
            # This distinguishes heuristics that score differently even if they
            # choose the same bin
            for idx, s in enumerate(scores_for_step):
                if s == s:  # not NaN
                    # Weight by position and step to create unique fingerprint
                    behavior_fingerprint += s * (0.1 ** (idx % 5)) * (1.0 + step * 0.01)
            
            # Pack into best bin or create new one
            if best_bin >= 0 and bins_remaining[best_bin] >= item_size:
                bins_remaining[best_bin] -= item_size
            else:
                bins_remaining.append(capacity - item_size)
                best_bin = len(bins_remaining) - 1
            
            # Also include bin choice in fingerprint
            behavior_fingerprint += best_bin * 100 + step
        
        # Include final bin count (scaled to not dominate)
        behavior_fingerprint += len(bins_remaining) * 10000
        
        return behavior_fingerprint
    
    return probe_runner
