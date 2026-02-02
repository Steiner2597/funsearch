from typing import Callable, cast

import pytest

from evaluator.bin_packing import (
    BinPackingEvaluator,
    FirstFitCandidate,
    generate_instances,
    pack_with_heuristic,
)
from evaluator.heuristics import best_fit_score_bin


def test_generate_instances_deterministic():
    instances_a = generate_instances(seed=123, n_items=15, capacity=100)
    instances_b = generate_instances(seed=123, n_items=15, capacity=100)
    assert instances_a == instances_b


def test_first_fit_candidate_consistent_score():
    evaluator = BinPackingEvaluator(seed=7)
    candidate = FirstFitCandidate()
    result_a = evaluator.cheap_eval(candidate)
    result_b = evaluator.cheap_eval(candidate)
    assert result_a.score == result_b.score
    assert result_a.baseline_score == result_b.baseline_score


def test_invalid_candidate_detected():
    def bad_score_bin(
        _item_size: int,
        _remaining_capacity: int,
        _bin_index: int,
        _step: int,
    ) -> float:
        value: object = object()
        return cast(float, value)

    bad_score_func: Callable[[int, int, int, int], float] = bad_score_bin

    with pytest.raises(ValueError):
        _ = pack_with_heuristic([40, 40], 100, bad_score_func)


def test_best_fit_heuristic_runs():
    bins_used = pack_with_heuristic([60, 40, 40, 20], 100, best_fit_score_bin)
    assert isinstance(bins_used, int)


def test_cheap_eval_uses_fewer_instances_than_full():
    evaluator = BinPackingEvaluator(seed=5)
    candidate = FirstFitCandidate()
    cheap = evaluator.cheap_eval(candidate)
    full = evaluator.full_eval(candidate)
    assert 3 <= cheap.n_instances <= 5
    assert full.n_instances == 10
    assert cheap.n_instances < full.n_instances


def test_score_negation_fewer_bins_is_higher_score():
    def greedy_score_bin(item_size: int, remaining_capacity: int, bin_index: int, step: int) -> float:
        if remaining_capacity < item_size:
            return float("-inf")
        return -remaining_capacity
    
    def wasteful_score_bin(item_size: int, remaining_capacity: int, bin_index: int, step: int) -> float:
        if remaining_capacity < item_size:
            return float("-inf")
        return remaining_capacity
    
    items = [40, 40, 40, 30, 30, 30, 20, 20]
    capacity = 100
    
    greedy_bins = pack_with_heuristic(items, capacity, greedy_score_bin)
    wasteful_bins = pack_with_heuristic(items, capacity, wasteful_score_bin)
    
    # Fewer bins is better
    assert greedy_bins <= wasteful_bins


def test_baseline_score_calculated():
    """Test that baseline_score represents bins saved vs FFD."""
    evaluator = BinPackingEvaluator(seed=99)
    candidate = FirstFitCandidate()
    result = evaluator.cheap_eval(candidate)
    
    assert result.baseline_score is not None
    assert result.baseline_bins is not None
    # FFD candidate vs FFD baseline = 0 saved
    expected_saved = sum(b - c for b, c in zip(result.baseline_bins, result.instance_bins))
    assert result.baseline_score == expected_saved
