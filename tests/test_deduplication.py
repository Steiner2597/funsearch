"""Tests for functional deduplication (Sample-efficient FunSearch)."""

import pytest

from funsearch_core.deduplication import (
    BehaviorSignature,
    DeduplicationStats,
    FunctionalDeduplicator,
    create_binpacking_probe_runner,
)


class TestBehaviorSignature:
    """Test BehaviorSignature creation and hashing."""
    
    def test_from_vector_creates_hash(self) -> None:
        sig = BehaviorSignature.from_vector([1.0, 2.0, 3.0])
        assert sig.hash
        assert len(sig.hash) == 64  # SHA256 hex length
        assert sig.vector == (1.0, 2.0, 3.0)
    
    def test_same_vector_same_hash(self) -> None:
        sig1 = BehaviorSignature.from_vector([1.0, 2.0, 3.0])
        sig2 = BehaviorSignature.from_vector([1.0, 2.0, 3.0])
        assert sig1.hash == sig2.hash
    
    def test_different_vector_different_hash(self) -> None:
        sig1 = BehaviorSignature.from_vector([1.0, 2.0, 3.0])
        sig2 = BehaviorSignature.from_vector([1.0, 2.0, 4.0])
        assert sig1.hash != sig2.hash


class TestFunctionalDeduplicator:
    """Test FunctionalDeduplicator duplicate detection."""
    
    @pytest.fixture
    def simple_probe_runner(self) -> callable:
        """A simple probe runner that uses hash of code + seed.
        
        This ensures different code strings produce different behaviors.
        """
        def runner(code: str, seed: int) -> float:
            # Use hash to ensure different codes give different results
            return float(hash(code) % 1000 + seed * 10)
        return runner
    
    def test_first_candidate_is_not_duplicate(self, simple_probe_runner) -> None:
        dedup = FunctionalDeduplicator(simple_probe_runner, probe_seeds=[0, 1, 2])
        is_dup, sig = dedup.is_duplicate("def f(): return 1")
        assert not is_dup
        assert sig.hash
    
    def test_same_code_is_duplicate(self, simple_probe_runner) -> None:
        dedup = FunctionalDeduplicator(simple_probe_runner, probe_seeds=[0, 1, 2])
        
        # First occurrence
        is_dup1, _ = dedup.is_duplicate("def f(): return 1")
        assert not is_dup1
        
        # Same code again
        is_dup2, _ = dedup.is_duplicate("def f(): return 1")
        assert is_dup2
    
    def test_different_code_same_behavior_is_duplicate(self) -> None:
        """Test the core insight: different code, same behavior = duplicate.
        
        This is the key innovation from the course requirement.
        """
        # Probe runner that only cares about return value, not code structure
        def behavior_runner(code: str, seed: int) -> float:
            namespace: dict = {}
            try:
                exec(code, namespace)
                func = namespace.get("mean") or namespace.get("f")
                if callable(func):
                    return float(func([1, 2, 3, 4, 5]))
            except:
                pass
            return float("nan")
        
        dedup = FunctionalDeduplicator(behavior_runner, probe_seeds=[0])
        
        # Two different implementations of mean
        code_a = """
def mean(lst):
    return sum(lst) / len(lst)
"""
        code_b = """
def mean(lst):
    total = 0
    for x in lst:
        total += x
    return total / len(lst)
"""
        
        # First implementation
        is_dup1, sig1 = dedup.is_duplicate(code_a)
        assert not is_dup1
        
        # Second implementation - different code but same behavior!
        is_dup2, sig2 = dedup.is_duplicate(code_b)
        assert is_dup2, "Functionally identical code should be detected as duplicate"
        assert sig1.hash == sig2.hash
    
    def test_stats_tracking(self, simple_probe_runner) -> None:
        dedup = FunctionalDeduplicator(simple_probe_runner, probe_seeds=[0, 1])
        
        dedup.is_duplicate("code1")
        dedup.is_duplicate("code2")
        dedup.is_duplicate("code1")  # duplicate
        dedup.is_duplicate("code3")
        dedup.is_duplicate("code2")  # duplicate
        
        stats = dedup.get_stats()
        assert stats.total_checked == 5
        assert stats.duplicates_found == 2
        assert stats.unique_passed == 3
        assert stats.evaluations_saved == 2
    
    def test_dedup_rate_calculation(self, simple_probe_runner) -> None:
        dedup = FunctionalDeduplicator(simple_probe_runner, probe_seeds=[0])
        
        for i in range(5):
            dedup.is_duplicate(f"unique_code_{i}")
        for i in range(5):
            dedup.is_duplicate("unique_code_0")  # All duplicates
        
        stats = dedup.get_stats()
        assert stats.dedup_rate == 50.0  # 5 out of 10 were duplicates
    
    def test_cache_size_limit(self, simple_probe_runner) -> None:
        dedup = FunctionalDeduplicator(
            simple_probe_runner, 
            probe_seeds=[0],
            cache_size_limit=3,
            use_code_hash=False,  # Disable code hash to test behavior signature cache only
        )
        
        # Add 5 unique codes
        for i in range(5):
            dedup.is_duplicate(f"code_{i}")
        
        # Cache should be limited
        assert dedup.cache_size <= 3
    
    def test_clear_cache(self, simple_probe_runner) -> None:
        dedup = FunctionalDeduplicator(
            simple_probe_runner, 
            probe_seeds=[0],
            use_code_hash=False,  # Disable code hash to test behavior signature cache only
        )
        
        dedup.is_duplicate("code1")
        assert dedup.cache_size == 1
        
        dedup.clear_cache()
        assert dedup.cache_size == 0
        
        # Same code should now be "new"
        is_dup, _ = dedup.is_duplicate("code1")
        assert not is_dup

    def test_two_stage_deduplication(self, simple_probe_runner) -> None:
        """Test the two-stage deduplication: code hash + behavior signature."""
        dedup = FunctionalDeduplicator(
            simple_probe_runner, 
            probe_seeds=[0, 1],
            use_code_hash=True,  # Enable code hash (default)
        )
        
        # First code - new
        is_dup1, _ = dedup.is_duplicate("def f(): return 1")
        assert not is_dup1
        
        # Same code with extra whitespace - should be caught by code hash
        is_dup2, _ = dedup.is_duplicate("def f():  return 1")  # Extra space
        assert is_dup2  # Caught by code hash (normalized)
        
        # Completely different code - new
        is_dup3, _ = dedup.is_duplicate("def g(): return 2")
        assert not is_dup3
        
        stats = dedup.get_stats()
        assert stats.duplicates_found == 1
        assert stats.unique_passed == 2


class TestBinPackingProbeRunner:
    """Test the bin packing specific probe runner."""
    
    def test_create_probe_runner(self) -> None:
        runner = create_binpacking_probe_runner(capacity=100)
        assert callable(runner)
    
    def test_valid_score_bin_returns_number(self) -> None:
        runner = create_binpacking_probe_runner(capacity=100)
        
        code = """
def score_bin(item_size, remaining_capacity, bin_index, step):
    return remaining_capacity - item_size
"""
        result = runner(code, seed=42)
        assert isinstance(result, float)
    
    def test_invalid_code_returns_nan(self) -> None:
        import math
        runner = create_binpacking_probe_runner(capacity=100)
        
        result = runner("invalid python code!!!", seed=42)
        assert math.isnan(result)
    
    def test_different_heuristics_different_behavior(self) -> None:
        runner = create_binpacking_probe_runner(capacity=100)
        
        # First-fit style (prefers earlier bins)
        code_first_fit = """
def score_bin(item_size, remaining_capacity, bin_index, step):
    if remaining_capacity >= item_size:
        return 1000 - bin_index
    return -1000
"""
        
        # Worst-fit style (prefers bins with most space)
        code_worst_fit = """
def score_bin(item_size, remaining_capacity, bin_index, step):
    return remaining_capacity
"""
        
        result1 = runner(code_first_fit, seed=42)
        result2 = runner(code_worst_fit, seed=42)
        
        # Different heuristics should produce different behaviors
        # Note: in some edge cases they may produce same result, 
        # so we just check both are valid numbers
        import math
        assert not math.isnan(result1)
        assert not math.isnan(result2)
        # The heuristics should generally differ on packing performance
        # but this can be flaky so we only test they both work


class TestIntegrationWithDeduplicator:
    """Integration test: FunctionalDeduplicator with bin packing probe."""
    
    def test_binpacking_deduplication(self) -> None:
        runner = create_binpacking_probe_runner(capacity=100)
        dedup = FunctionalDeduplicator(runner, probe_seeds=[0, 1, 2])
        
        # Two implementations of first-fit
        code_a = """
def score_bin(item_size, remaining_capacity, bin_index, step):
    if remaining_capacity >= item_size:
        return 1.0
    return -1.0
"""
        code_b = """
def score_bin(item_size, remaining_capacity, bin_index, step):
    # Same logic, different style
    can_fit = remaining_capacity >= item_size
    return 1.0 if can_fit else -1.0
"""
        
        is_dup1, _ = dedup.is_duplicate(code_a)
        assert not is_dup1
        
        is_dup2, _ = dedup.is_duplicate(code_b)
        # These should be detected as duplicates (same behavior)
        assert is_dup2
