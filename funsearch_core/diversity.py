from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Callable

from .schemas import Candidate


@dataclass(frozen=True)
class SignatureResult:
    signature: str
    vector: list[float]


class SignatureCalculator:
    def __init__(
        self,
        probe_runner: Callable[[str, int], object],
        probe_seeds: Sequence[int] | None = None,
    ) -> None:
        self._probe_runner: Callable[[str, int], object] = probe_runner
        self._probe_seeds: list[int] = (
            list(probe_seeds) if probe_seeds is not None else [0, 1, 2, 3, 4]
        )

    def calculate(self, candidate_or_code: Candidate | str) -> SignatureResult:
        code = candidate_or_code.code if isinstance(candidate_or_code, Candidate) else candidate_or_code
        vector: list[float] = []
        for seed in self._probe_seeds:
            value = self._probe_runner(code, seed)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError("Probe runner must return numeric values")
            vector.append(float(value))
        signature = self._hash_vector(vector)
        return SignatureResult(signature=signature, vector=vector)

    @staticmethod
    def _hash_vector(vector: Sequence[float]) -> str:
        payload = json.dumps(vector, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _default_signature_extractor(candidate: Candidate) -> Sequence[float] | None:
    value = candidate.eval_metadata.get("signature_vector")
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        converted: list[float] = []
        for item in value:
            if isinstance(item, bool):
                converted.append(float(item))
            elif isinstance(item, (int, float)):
                converted.append(float(item))
            elif isinstance(item, str):
                try:
                    converted.append(float(item))
                except ValueError:
                    return None
            else:
                return None
        return converted
    return None


class DiversityMaintainer:
    def __init__(
        self,
        min_distance: float = 0.1,
        metric: str = "cosine",
        signature_extractor: Callable[[Candidate], Sequence[float] | None] | None = None,
    ) -> None:
        if min_distance < 0:
            raise ValueError("min_distance must be non-negative")
        if metric not in ("cosine", "hamming"):
            raise ValueError("metric must be 'cosine' or 'hamming'")
        self.min_distance: float = min_distance
        self.metric: str = metric
        self._signature_extractor: Callable[[Candidate], Sequence[float] | None] = (
            signature_extractor or _default_signature_extractor
        )

    def is_diverse(self, candidate: Candidate, existing: Iterable[Candidate]) -> bool:
        existing_list = list(existing)
        if not existing_list:
            return True
        for other in existing_list:
            if candidate.signature == other.signature:
                return False
        candidate_vector = self._signature_extractor(candidate)
        for other in existing_list:
            other_vector = self._signature_extractor(other)
            if candidate_vector is None or other_vector is None:
                continue
            distance = self._distance(candidate_vector, other_vector)
            if distance < self.min_distance:
                return False
        return True

    def _distance(self, vector_a: Sequence[float], vector_b: Sequence[float]) -> float:
        if self.metric == "hamming":
            return _hamming_distance(vector_a, vector_b)
        return _cosine_distance(vector_a, vector_b)


def _cosine_distance(vector_a: Sequence[float], vector_b: Sequence[float]) -> float:
    if not vector_a or not vector_b:
        return 1.0
    if len(vector_a) != len(vector_b):
        return 1.0
    dot = sum(a * b for a, b in zip(vector_a, vector_b))
    norm_a = math.sqrt(sum(a * a for a in vector_a))
    norm_b = math.sqrt(sum(b * b for b in vector_b))
    if norm_a == 0 or norm_b == 0:
        return 0.0 if list(vector_a) == list(vector_b) else 1.0
    similarity = dot / (norm_a * norm_b)
    similarity = max(-1.0, min(1.0, similarity))
    return 1.0 - similarity


def _hamming_distance(vector_a: Sequence[float], vector_b: Sequence[float]) -> float:
    max_len = max(len(vector_a), len(vector_b))
    if max_len == 0:
        return 0.0
    mismatches = 0
    for idx in range(max_len):
        value_a = vector_a[idx] if idx < len(vector_a) else None
        value_b = vector_b[idx] if idx < len(vector_b) else None
        if value_a != value_b:
            mismatches += 1
    return mismatches / max_len
