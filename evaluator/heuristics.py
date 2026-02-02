"""Baseline bin scoring heuristics."""

from __future__ import annotations


def first_fit_score_bin(
    _item_size: int,
    remaining_capacity: int,
    _bin_index: int,
    _step: int,
) -> float:
    """First-fit style: prefer largest remaining space."""

    return float(remaining_capacity)


def best_fit_score_bin(
    item_size: int,
    remaining_capacity: int,
    _bin_index: int,
    _step: int,
) -> float:
    """Best-fit style: prefer smallest waste after placing."""

    remaining_after = remaining_capacity - item_size
    return float(-remaining_after)
