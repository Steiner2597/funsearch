"""SQLite-backed cache for LLM responses."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from pathlib import Path
from typing import cast

from .base import BaseLLMProvider, LLMResponse


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS llm_cache (
  cache_key TEXT PRIMARY KEY,
  provider_id TEXT NOT NULL,
  model_name TEXT NOT NULL,
  temperature REAL NOT NULL,
  max_tokens INTEGER NOT NULL,
  response_json TEXT NOT NULL,
  created_at REAL NOT NULL,
  expires_at REAL
);
"""


def _initialize_database(db_path: str) -> None:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(path))
    try:
        _ = connection.executescript(SCHEMA_SQL)
        connection.commit()
    finally:
        connection.close()


def _connect(db_path: str) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def _make_cache_key(
    provider_id: str,
    model_name: str,
    prompt: str,
    temperature: float,
    max_tokens: int,
) -> str:
    payload = json.dumps(
        {
            "provider_id": provider_id,
            "model_name": model_name,
            "prompt": prompt,
            "temperature": float(temperature),
            "max_tokens": int(max_tokens),
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _serialize_response(response: LLMResponse) -> str:
    payload = response.to_dict()
    return json.dumps(payload, sort_keys=True, default=str)


def _deserialize_response(payload: str) -> LLMResponse:
    data = cast(object, json.loads(payload))
    if not isinstance(data, dict):
        raise ValueError("Invalid cached response payload")
    return LLMResponse.from_dict(cast(dict[str, object], data))


def _coerce_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


class LLMCache:
    """Cache LLM responses keyed by provider/model/prompt/settings."""

    run_id: str
    db_path: str
    ttl_seconds: float | None

    def __init__(
        self,
        run_id: str,
        base_dir: str | Path = "artifacts",
        db_path: str | None = None,
        ttl_seconds: float | None = None,
    ) -> None:
        self.run_id = run_id
        self.db_path = (
            str(Path(base_dir) / run_id / "llm_cache.db") if db_path is None else db_path
        )
        self.ttl_seconds = ttl_seconds
        _initialize_database(self.db_path)

    def get(
        self,
        provider_id: str,
        model_name: str,
        prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> LLMResponse | None:
        cache_key = _make_cache_key(provider_id, model_name, prompt, temperature, max_tokens)
        with _connect(self.db_path) as connection:
            row = cast(
                sqlite3.Row | None,
                connection.execute(
                "SELECT response_json, expires_at FROM llm_cache WHERE cache_key = ?",
                (cache_key,),
                ).fetchone(),
            )
            if row is None:
                return None
            expires_at_value = cast(object, row["expires_at"])
            expires_at = _coerce_float(expires_at_value)
            if expires_at is not None and expires_at < time.time():
                _ = connection.execute(
                    "DELETE FROM llm_cache WHERE cache_key = ?",
                    (cache_key,),
                )
                connection.commit()
                return None
            payload = cast(str, row["response_json"])
            return _deserialize_response(payload)

    def set(
        self,
        provider_id: str,
        model_name: str,
        prompt: str,
        temperature: float,
        max_tokens: int,
        response: LLMResponse,
    ) -> None:
        cache_key = _make_cache_key(provider_id, model_name, prompt, temperature, max_tokens)
        expires_at = time.time() + self.ttl_seconds if self.ttl_seconds else None
        payload = _serialize_response(response)
        with _connect(self.db_path) as connection:
            _ = connection.execute(
                """
                INSERT OR REPLACE INTO llm_cache (
                    cache_key, provider_id, model_name, temperature, max_tokens,
                    response_json, created_at, expires_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    cache_key,
                    provider_id,
                    model_name,
                    float(temperature),
                    int(max_tokens),
                    payload,
                    time.time(),
                    expires_at,
                ),
            )
            connection.commit()

    def get_or_generate(
        self,
        provider: BaseLLMProvider,
        prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> LLMResponse:
        cached = self.get(
            provider_id=provider.provider_id,
            model_name=provider.model_name,
            prompt=prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if cached is not None:
            return cached
        response = provider.generate(prompt, temperature, max_tokens)
        self.set(
            provider_id=provider.provider_id,
            model_name=provider.model_name,
            prompt=prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            response=response,
        )
        return response
