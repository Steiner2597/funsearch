"""
SQLite-backed candidate repository and query interface.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TypeAlias, cast

from .database import connect, initialize_database


ConfigInput: TypeAlias = Mapping[str, object] | str | None
EvaluationPayload: TypeAlias = Mapping[str, object]

_SECRET_TOKENS = ("api_key", "apikey", "token", "secret")


@dataclass
class Candidate:
    id: str
    run_id: str
    code: str
    code_hash: str
    parent_id: str | None
    generation: int
    model_id: str
    signature: str | None = None
    status: str = "pending"
    created_at: str | None = None
    score: float | None = None
    fidelity: str | None = None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Candidate":
        row_dict = cast(dict[str, object], dict(row))
        return cls(
            id=_require_str(row_dict["id"], "id"),
            run_id=_require_str(row_dict["run_id"], "run_id"),
            code=_require_str(row_dict["code"], "code"),
            code_hash=_require_str(row_dict["code_hash"], "code_hash"),
            parent_id=_optional_str(row_dict.get("parent_id")),
            generation=_require_int(row_dict["generation"], "generation"),
            model_id=_require_str(row_dict["model_id"], "model_id"),
            signature=_optional_str(row_dict.get("signature")),
            status=_optional_str(row_dict.get("status")) or "pending",
            created_at=_optional_str(row_dict.get("created_at")),
            score=_optional_float(row_dict.get("score")),
            fidelity=_optional_str(row_dict.get("fidelity")),
        )


@dataclass
class EvaluationResult:
    candidate_id: str
    fidelity: str
    score: float | None = None
    runtime_ms: float | None = None
    error_type: str | None = None
    metadata: dict[str, object] | None = None


def _require_str(value: object, field: str) -> str:
    if isinstance(value, str):
        return value
    if value is None:
        raise ValueError(f"{field} is required")
    return str(value)


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)


def _require_int(value: object, field: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be an int")
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        return int(value)
    if value is None:
        raise ValueError(f"{field} is required")
    raise ValueError(f"{field} must be an int")


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, int):
        return float(value)
    if isinstance(value, float):
        return value
    if isinstance(value, str):
        return float(value)
    raise ValueError("value must be a float")


def _optional_mapping(value: object) -> dict[str, object] | None:
    if value is None:
        return None
    if isinstance(value, Mapping):
        typed_value = cast(Mapping[str, object], value)
        sanitized: dict[str, object] = {}
        for key, item in typed_value.items():
            if isinstance(key, str):
                sanitized[key] = item
        return sanitized
    raise TypeError("metadata must be a mapping")


def normalize_code(code: str) -> str:
    """Normalize code by stripping whitespace and sorting top-level imports."""
    if not code:
        return ""
    lines = [line.strip() for line in code.strip().splitlines()]
    lines = [line for line in lines if line]
    if not lines:
        return ""
    preamble: list[str] = []
    import_lines: list[str] = []
    rest: list[str] = []
    in_import_block = True
    for line in lines:
        if in_import_block:
            if line.startswith("#"):
                preamble.append(line)
                continue
            if line.startswith("import ") or line.startswith("from "):
                import_lines.append(line)
                continue
            in_import_block = False
        rest.append(line)
    normalized_lines = preamble + sorted(import_lines) + rest
    return "\n".join(normalized_lines)


def code_hash(code: str) -> str:
    """Return SHA256 hash for normalized code."""
    normalized = normalize_code(code)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _looks_like_secret(key: str) -> bool:
    lowered = key.lower()
    return any(token in lowered for token in _SECRET_TOKENS)


def _sanitize_mapping(mapping: Mapping[str, object]) -> dict[str, object]:
    sanitized: dict[str, object] = {}
    for key, value in mapping.items():
        if not _looks_like_secret(key):
            sanitized[key] = value
    return sanitized


def _redact_string_config(config: str) -> str:
    redacted = config
    for token in _SECRET_TOKENS:
        pattern = re.compile(rf'("{token}"\s*:\s*)"[^"]*"', re.IGNORECASE)
        redacted = pattern.sub(r"\1\"<redacted>\"", redacted)
    if redacted == config and any(token in config.lower() for token in _SECRET_TOKENS):
        return "<redacted>"
    return redacted


def _sanitize_config(config: ConfigInput) -> Mapping[str, object] | str:
    if config is None:
        return {}
    if isinstance(config, str):
        return _redact_string_config(config)
    return _sanitize_mapping(config)


def _prepare_config_json(config: ConfigInput) -> str:
    sanitized = _sanitize_config(config)
    if isinstance(sanitized, str):
        return sanitized
    return json.dumps(sanitized, sort_keys=True, default=str)


class CandidateStore:
    def __init__(
        self,
        run_id: str,
        config: ConfigInput,
        seed: int,
        base_dir: str | Path = "artifacts",
        db_path: str | None = None,
    ) -> None:
        self.run_id: str = run_id
        self.db_path: str = (
            str(Path(base_dir) / run_id / "candidates.db") if db_path is None else db_path
        )
        initialize_database(self.db_path)
        self._ensure_run(config=config, seed=seed)

    def _ensure_run(self, config: ConfigInput, seed: int) -> None:
        config_json = _prepare_config_json(config)
        with connect(self.db_path) as connection:
            _ = connection.execute(
                "INSERT OR IGNORE INTO runs (run_id, config_json, seed) VALUES (?, ?, ?)",
                (self.run_id, config_json, seed),
            )
            connection.commit()

    def save_candidate(self, candidate: Candidate) -> bool:
        if candidate.run_id and candidate.run_id != self.run_id:
            raise ValueError("Candidate run_id does not match store run_id")
        candidate.run_id = self.run_id
        candidate.code_hash = code_hash(candidate.code)
        status = candidate.status or "pending"
        with connect(self.db_path) as connection:
            try:
                _ = connection.execute(
                    """
                    INSERT INTO candidates (
                        id, run_id, code, code_hash, parent_id,
                        generation, model_id, signature, status
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        candidate.id,
                        candidate.run_id,
                        candidate.code,
                        candidate.code_hash,
                        candidate.parent_id,
                        candidate.generation,
                        candidate.model_id,
                        candidate.signature,
                        status,
                    ),
                )
                connection.commit()
                return True
            except sqlite3.IntegrityError:
                return False

    def update_candidate_status(self, candidate_id: str, status: str) -> None:
        """Update the status of a candidate."""
        with connect(self.db_path) as connection:
            connection.execute(
                "UPDATE candidates SET status = ? WHERE id = ?",
                (status, candidate_id),
            )
            connection.commit()

    def record_evaluation(self, eval_result: EvaluationResult | EvaluationPayload) -> None:
        if isinstance(eval_result, EvaluationResult):
            candidate_id = eval_result.candidate_id
            fidelity = eval_result.fidelity
            score = eval_result.score
            runtime_ms = eval_result.runtime_ms
            error_type = eval_result.error_type
            metadata = eval_result.metadata
        else:
            candidate_id = _require_str(eval_result.get("candidate_id"), "candidate_id")
            fidelity = _require_str(eval_result.get("fidelity"), "fidelity")
            score = _optional_float(eval_result.get("score"))
            runtime_ms = _optional_float(eval_result.get("runtime_ms"))
            error_type = _optional_str(eval_result.get("error_type"))
            metadata = _optional_mapping(eval_result.get("metadata"))
        metadata_json = json.dumps(metadata) if metadata is not None else None
        with connect(self.db_path) as connection:
            _ = connection.execute(
                """
                INSERT INTO evaluations (
                    candidate_id, fidelity, score, runtime_ms, error_type, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (candidate_id, fidelity, score, runtime_ms, error_type, metadata_json),
            )
            connection.commit()

    def get_top_k(self, run_id: str, fidelity: str, k: int) -> list[Candidate]:
        with connect(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT c.*, MAX(e.score) AS score, e.fidelity AS fidelity
                FROM candidates c
                JOIN evaluations e ON e.candidate_id = c.id
                WHERE c.run_id = ? AND e.fidelity = ? AND e.score IS NOT NULL
                GROUP BY c.id
                ORDER BY score DESC
                LIMIT ?
                """,
                (run_id, fidelity, k),
            ).fetchall()
        return [Candidate.from_row(cast(sqlite3.Row, row)) for row in rows]

    def get_generation_stats(self, run_id: str, generation: int) -> dict[str, float | int | None]:
        with connect(self.db_path) as connection:
            total_row = cast(
                sqlite3.Row | None,
                connection.execute(
                    "SELECT COUNT(*) AS count FROM candidates WHERE run_id = ? AND generation = ?",
                    (run_id, generation),
                ).fetchone(),
            )
            total = (
                _require_int(cast(object, total_row[0]), "total") if total_row is not None else 0
            )
            evaluated_row = cast(
                sqlite3.Row | None,
                connection.execute(
                    """
                    SELECT COUNT(DISTINCT e.candidate_id)
                    FROM evaluations e
                    JOIN candidates c ON c.id = e.candidate_id
                    WHERE c.run_id = ? AND c.generation = ?
                    """,
                    (run_id, generation),
                ).fetchone(),
            )
            evaluated = (
                _require_int(cast(object, evaluated_row[0]), "evaluated")
                if evaluated_row is not None
                else 0
            )
            scores_row = cast(
                sqlite3.Row | None,
                connection.execute(
                    """
                    SELECT AVG(e.score), MAX(e.score), MIN(e.score)
                    FROM evaluations e
                    JOIN candidates c ON c.id = e.candidate_id
                    WHERE c.run_id = ? AND c.generation = ? AND e.score IS NOT NULL
                    """,
                    (run_id, generation),
                ).fetchone(),
            )
            if scores_row is None:
                avg_score = best_score = worst_score = None
            else:
                avg_score = _optional_float(cast(object, scores_row[0]))
                best_score = _optional_float(cast(object, scores_row[1]))
                worst_score = _optional_float(cast(object, scores_row[2]))
        return {
            "total": total,
            "evaluated": evaluated,
            "avg_score": avg_score,
            "best_score": best_score,
            "worst_score": worst_score,
        }

    def get_best_candidate(self, run_id: str) -> Candidate | None:
        with connect(self.db_path) as connection:
            row = cast(
                sqlite3.Row | None,
                connection.execute(
                    """
                    SELECT c.*, MAX(e.score) AS score, e.fidelity AS fidelity
                    FROM candidates c
                    JOIN evaluations e ON e.candidate_id = c.id
                    WHERE c.run_id = ? AND e.score IS NOT NULL
                    GROUP BY c.id
                    ORDER BY score DESC
                    LIMIT 1
                    """,
                    (run_id,),
                ).fetchone(),
            )
        if row is None:
            return None
        return Candidate.from_row(row)

    def count_by_status(self, run_id: str, generation: int) -> dict[str, int]:
        with connect(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT status, COUNT(*) AS count
                FROM candidates
                WHERE run_id = ? AND generation = ?
                GROUP BY status
                """,
                (run_id, generation),
            ).fetchall()
        counts: dict[str, int] = {}
        for row in rows:
            typed_row = cast(sqlite3.Row, row)
            status = _require_str(cast(object, typed_row["status"]), "status")
            count = _require_int(cast(object, typed_row["count"]), "count")
            counts[status] = count
        return counts
