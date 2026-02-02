from __future__ import annotations

from .diversity import DiversityMaintainer
from .schemas import Candidate


def _score_key(candidate: Candidate) -> float:
    return candidate.score if candidate.score is not None else float("-inf")


class Population:
    """Fixed-size population with diversity maintenance and deduplication.
    
    Candidates are sorted by score (descending). When size exceeds max_size,
    lowest-scoring candidates are removed. Duplicate signatures are rejected.
    """
    
    def __init__(self, max_size: int, diversity_maintainer: DiversityMaintainer | None = None) -> None:
        if max_size <= 0:
            raise ValueError("max_size must be positive")
        self.max_size: int = max_size
        self._candidates: list[Candidate] = []
        self._signature_clusters: dict[str, list[Candidate]] = {}
        self._diversity_maintainer: DiversityMaintainer | None = diversity_maintainer

    def __len__(self) -> int:
        return len(self._candidates)

    @property
    def candidates(self) -> tuple[Candidate, ...]:
        return tuple(self._candidates)

    def add_candidate(self, candidate: Candidate) -> bool:
        if candidate.signature in self._signature_clusters:
            return False
        if self._diversity_maintainer is not None:
            if not self._diversity_maintainer.is_diverse(candidate, self._candidates):
                return False
        self._candidates.append(candidate)
        self._signature_clusters.setdefault(candidate.signature, []).append(candidate)
        self._trim_to_size()
        return True

    def get_top_k(self, k: int) -> list[Candidate]:
        if k <= 0:
            return []
        ordered = sorted(self._candidates, key=_score_key, reverse=True)
        return ordered[:k]

    def get_generation_stats(self) -> dict[str, float | int | None]:
        scores = [candidate.score for candidate in self._candidates if candidate.score is not None]
        count = len(self._candidates)
        best_score = max(scores) if scores else None
        avg_score = sum(scores) / len(scores) if scores else None
        return {"count": count, "best_score": best_score, "avg_score": avg_score}

    def _trim_to_size(self) -> None:
        if len(self._candidates) <= self.max_size:
            return
        ordered = sorted(self._candidates, key=_score_key, reverse=True)
        self._candidates = ordered[: self.max_size]
        self._rebuild_clusters()

    def _rebuild_clusters(self) -> None:
        self._signature_clusters = {}
        for candidate in self._candidates:
            self._signature_clusters.setdefault(candidate.signature, []).append(candidate)
