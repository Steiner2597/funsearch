"""Base evaluator interfaces and shared types."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Protocol, Any
from collections.abc import Sequence


class Candidate(Protocol):
    """Candidate interface for bin packing heuristics.
    
    Note: Scores are NEGATED for evolution (fewer bins = higher score).
    The evaluator returns -avg_bins so evolutionary maximization works correctly.
    """

    def score_bin(
        self,
        item_size: int,
        remaining_capacity: int,
        bin_index: int,
        step: int,
    ) -> float:
        """Return a numeric score for selecting a bin."""
        ...


@dataclass(frozen=True)
class EvalResult:
    """Evaluation result for a candidate across instances."""

    score: float
    n_instances: int
    instance_bins: Sequence[int]
    baseline_score: float | None = None
    baseline_bins: Sequence[int] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseEvaluator(ABC):
    """Base class for multi-fidelity evaluators.

    Evaluations must be deterministic given the same seed.
    """

    def __init__(self, seed: int) -> None:
        self.seed: int = seed

    @abstractmethod
    def cheap_eval(self, candidate: Candidate) -> EvalResult:
        """Cheap evaluation on a small set of instances."""

    @abstractmethod
    def full_eval(self, candidate: Candidate) -> EvalResult:
        """Full evaluation on a larger set of instances."""
