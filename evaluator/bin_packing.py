"""Bin packing evaluator with multi-fidelity evaluation.

Supports both:
- Random instance generation (for cheap/fast evaluation)
- OR-Library benchmark instances (for standardized evaluation)
"""

from __future__ import annotations

import math
import numbers
import random
from dataclasses import dataclass
from typing import Callable, TypeAlias, TYPE_CHECKING

from .base import BaseEvaluator, Candidate, EvalResult
from .heuristics import first_fit_score_bin

if TYPE_CHECKING:
    from .datasets import BinPackingDataset, BinPackingInstance as DatasetInstance

BinPackingInstance: TypeAlias = list[int]

DEFAULT_CAPACITY = 100
CHEAP_INSTANCE_COUNT = 4
FULL_INSTANCE_COUNT = 10
MAX_SEED = 2_147_483_647


@dataclass
class Bin:
    capacity: int
    remaining: int
    items: list[int]

    def __init__(self, capacity: int) -> None:
        self.capacity = capacity
        self.remaining = capacity
        self.items = []

    def add(self, item_size: int) -> None:
        if item_size > self.remaining:
            raise ValueError("Item does not fit in bin")
        self.items.append(item_size)
        self.remaining -= item_size


def generate_instances(seed: int, n_items: int, capacity: int) -> list[BinPackingInstance]:
    """Generate deterministic bin packing instances.

    Returns a list of instances; each instance is a list of item sizes.
    """

    rng = random.Random(seed)
    items = [rng.randint(1, capacity) for _ in range(n_items)]
    return [items]


def _validated_score(score: object) -> float:
    if isinstance(score, bool) or not isinstance(score, numbers.Real):
        raise ValueError("score_bin must return a numeric score")
    score_value = float(score)
    if not math.isfinite(score_value):
        raise ValueError("score_bin must return a finite score")
    return score_value


def pack_with_heuristic(
    items: list[int],
    capacity: int,
    score_bin_func: Callable[[int, int, int, int], float],
) -> int:
    """Pack items greedily using a candidate scoring function."""

    bins: list[Bin] = []
    for step, item_size in enumerate(items):
        best_bin: int | None = None
        best_score = -math.inf
        for i, bin_info in enumerate(bins):
            if bin_info.remaining >= item_size:
                score = _validated_score(
                    score_bin_func(item_size, bin_info.remaining, i, step)
                )
                if score > best_score:
                    best_score = score
                    best_bin = i

        if best_bin is not None:
            bins[best_bin].add(item_size)
        else:
            new_bin = Bin(capacity)
            new_bin.add(item_size)
            bins.append(new_bin)

    return len(bins)


def first_fit_decreasing(items: list[int], capacity: int) -> int:
    """First-fit decreasing baseline packing."""

    bins: list[Bin] = []
    for item_size in sorted(items, reverse=True):
        placed = False
        for bin_info in bins:
            if bin_info.remaining >= item_size:
                bin_info.add(item_size)
                placed = True
                break
        if not placed:
            new_bin = Bin(capacity)
            new_bin.add(item_size)
            bins.append(new_bin)

    return len(bins)


class BinPackingEvaluator(BaseEvaluator):
    """Multi-fidelity evaluator for bin packing candidates."""

    def __init__(self, seed: int, capacity: int = DEFAULT_CAPACITY) -> None:
        super().__init__(seed)
        self.capacity: int = capacity

    def cheap_eval(self, candidate: Candidate) -> EvalResult:  # pyright: ignore[reportImplicitOverride]
        return self._evaluate(
            candidate=candidate,
            n_instances=CHEAP_INSTANCE_COUNT,
            min_items=10,
            max_items=20,
            seed_offset=0,
        )

    def full_eval(self, candidate: Candidate) -> EvalResult:  # pyright: ignore[reportImplicitOverride]
        return self._evaluate(
            candidate=candidate,
            n_instances=FULL_INSTANCE_COUNT,
            min_items=50,
            max_items=100,
            seed_offset=10_000,
        )

    def _evaluate(
        self,
        candidate: Candidate,
        n_instances: int,
        min_items: int,
        max_items: int,
        seed_offset: int,
    ) -> EvalResult:
        rng = random.Random(self.seed + seed_offset)
        instances: list[BinPackingInstance] = []
        for _ in range(n_instances):
            n_items = rng.randint(min_items, max_items)
            instance_seed = rng.randint(0, MAX_SEED)
            instances.extend(generate_instances(instance_seed, n_items, self.capacity))

        instance_bins: list[int] = []
        baseline_bins: list[int] = []
        for items in instances:
            ordered_items = sorted(items, reverse=True)
            instance_bins.append(
                pack_with_heuristic(ordered_items, self.capacity, candidate.score_bin)
            )
            baseline_bins.append(first_fit_decreasing(ordered_items, self.capacity))

        # Calculate score: bins saved relative to FFD baseline (positive = better)
        avg_bins = sum(instance_bins) / len(instance_bins)
        avg_baseline = sum(baseline_bins) / len(baseline_bins)
        total_saved = sum(b - c for b, c in zip(baseline_bins, instance_bins))
        return EvalResult(
            score=total_saved,  # Positive = better than FFD baseline
            n_instances=len(instance_bins),
            instance_bins=instance_bins,
            baseline_score=total_saved,  # Same as score for consistency
            baseline_bins=baseline_bins,
            metadata={
                "n_instances": len(instance_bins),
                "avg_bins": avg_bins,
                "avg_baseline": avg_baseline,
            },
        )


class BenchmarkEvaluator(BaseEvaluator):
    """Evaluator using OR-Library or other standard benchmark datasets.
    
    This evaluator uses standardized benchmark instances for fair comparison
    with published results in the literature.
    
    Example:
        >>> from evaluator.datasets import load_orlib_small
        >>> dataset = load_orlib_small()
        >>> evaluator = BenchmarkEvaluator(dataset)
        >>> result = evaluator.full_eval(candidate)
        >>> print(f"Score: {result.score}, vs Best Known: {result.metadata['best_known_avg']}")
    """
    
    def __init__(
        self, 
        dataset: "BinPackingDataset",
        cheap_sample_size: int = 5,
        seed: int = 42,
    ) -> None:
        """Initialize with a benchmark dataset.
        
        Args:
            dataset: A BinPackingDataset containing benchmark instances.
            cheap_sample_size: Number of instances to use for cheap_eval.
            seed: Random seed for sampling instances in cheap_eval.
        """
        super().__init__(seed)
        self.dataset = dataset
        self.cheap_sample_size = min(cheap_sample_size, len(dataset))
        self._rng = random.Random(seed)
    
    def cheap_eval(self, candidate: Candidate) -> EvalResult:
        """Evaluate on a small random sample of instances."""
        sample_indices = self._rng.sample(
            range(len(self.dataset)), 
            self.cheap_sample_size
        )
        sample_instances = [self.dataset[i] for i in sample_indices]
        return self._evaluate_instances(candidate, sample_instances)
    
    def full_eval(self, candidate: Candidate) -> EvalResult:
        """Evaluate on all instances in the dataset."""
        return self._evaluate_instances(candidate, list(self.dataset))
    
    def _evaluate_instances(
        self, 
        candidate: Candidate, 
        instances: list["DatasetInstance"],
    ) -> EvalResult:
        """Evaluate candidate on a list of benchmark instances."""
        candidate_bins: list[int] = []
        baseline_bins: list[int] = []
        best_known_bins: list[int] = []
        instance_details: list[dict] = []
        
        for inst in instances:
            # Sort items in decreasing order (standard for online bin packing)
            ordered_items = sorted(inst.items, reverse=True)
            
            # Evaluate with candidate heuristic
            cand_result = pack_with_heuristic(
                ordered_items, inst.capacity, candidate.score_bin
            )
            candidate_bins.append(cand_result)
            
            # Evaluate with FFD baseline
            ffd_result = first_fit_decreasing(ordered_items, inst.capacity)
            baseline_bins.append(ffd_result)
            
            # Record best known
            best_known_bins.append(inst.best_known)
            
            # Details for analysis
            instance_details.append({
                "name": inst.name,
                "num_items": inst.num_items,
                "capacity": inst.capacity,
                "candidate_bins": cand_result,
                "ffd_bins": ffd_result,
                "best_known": inst.best_known,
                "gap_to_best": cand_result - inst.best_known,
            })
        
        # Compute scores: bins saved relative to FFD baseline (positive = better)
        avg_bins = sum(candidate_bins) / len(candidate_bins)
        avg_baseline = sum(baseline_bins) / len(baseline_bins)
        avg_best_known = sum(best_known_bins) / len(best_known_bins)
        
        # Gap metrics
        total_gap = sum(c - b for c, b in zip(candidate_bins, best_known_bins))
        total_saved = sum(b - c for b, c in zip(baseline_bins, candidate_bins))
        instances_matching_best = sum(
            1 for c, b in zip(candidate_bins, best_known_bins) if c == b
        )
        
        return EvalResult(
            score=total_saved,  # Positive = better than FFD baseline
            n_instances=len(instances),
            instance_bins=candidate_bins,
            baseline_score=total_saved,  # Same as score for consistency
            baseline_bins=baseline_bins,
            metadata={
                "n_instances": len(instances),
                "dataset_name": self.dataset.name,
                "avg_bins": avg_bins,
                "avg_baseline": avg_baseline,
                "best_known_avg": avg_best_known,
                "total_gap_to_best": total_gap,
                "instances_matching_best": instances_matching_best,
                "instance_details": instance_details,
            },
        )


class FirstFitCandidate:
    """Baseline candidate using first-fit style scoring."""

    def score_bin(
        self,
        item_size: int,
        remaining_capacity: int,
        bin_index: int,
        step: int,
    ) -> float:
        return first_fit_score_bin(item_size, remaining_capacity, bin_index, step)
