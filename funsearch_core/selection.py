from __future__ import annotations

import random
import sys
from abc import ABC, abstractmethod
from collections.abc import Sequence

# Python 3.12+ has override in typing, earlier versions need typing_extensions
if sys.version_info >= (3, 12):
    from typing import override
else:
    try:
        from typing_extensions import override
    except ImportError:
        # Fallback: no-op decorator for older Python without typing_extensions
        def override(func):  # type: ignore[no-redef]
            return func

from .schemas import Candidate


def _score_key(candidate: Candidate) -> float:
    return candidate.score if candidate.score is not None else float("-inf")


class SelectionStrategy(ABC):
    @abstractmethod
    def select(self, candidates: Sequence[Candidate]) -> Candidate:
        raise NotImplementedError


class TournamentSelection(SelectionStrategy):
    def __init__(self, tournament_size: int, rng: random.Random | None = None) -> None:
        if tournament_size <= 0:
            raise ValueError("tournament_size must be positive")
        self.tournament_size: int = tournament_size
        self._rng: random.Random = rng or random.Random()

    @override
    def select(self, candidates: Sequence[Candidate]) -> Candidate:
        if not candidates:
            raise ValueError("candidates must be non-empty")
        sample_size = min(self.tournament_size, len(candidates))
        if sample_size == 1:
            return self._rng.choice(list(candidates))
        sampled = self._rng.sample(list(candidates), sample_size)
        return max(sampled, key=_score_key)


class RankBasedSelection(SelectionStrategy):
    def __init__(self, rng: random.Random | None = None) -> None:
        self._rng: random.Random = rng or random.Random()

    @override
    def select(self, candidates: Sequence[Candidate]) -> Candidate:
        if not candidates:
            raise ValueError("candidates must be non-empty")
        ordered = sorted(candidates, key=_score_key, reverse=True)
        weights = [len(ordered) - idx for idx in range(len(ordered))]
        return self._rng.choices(ordered, weights=weights, k=1)[0]
