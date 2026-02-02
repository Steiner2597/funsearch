from __future__ import annotations

from datetime import datetime, timezone
from collections.abc import Mapping
from typing import Literal, TypeVar

from pydantic import BaseModel, Field, field_validator


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


TBaseSchema = TypeVar("TBaseSchema", bound="BaseSchema")


class BaseSchema(BaseModel):
    def to_json(self) -> str:
        return self.model_dump_json()

    def to_dict(self) -> dict[str, object]:
        return self.model_dump()

    @classmethod
    def from_json(cls: type[TBaseSchema], data: str) -> TBaseSchema:
        return cls.model_validate_json(data)

    @classmethod
    def from_dict(cls: type[TBaseSchema], data: Mapping[str, object]) -> TBaseSchema:
        return cls.model_validate(data)


class Candidate(BaseSchema):
    id: str
    code: str
    score: float | None = None
    signature: str
    parent_id: str | None = None
    generation: int = Field(ge=0)
    runtime_ms: float | None = None
    error_type: str | None = None
    model_id: str
    eval_metadata: dict[str, object]
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("created_at")
    @classmethod
    def created_at_utc(cls, value: datetime) -> datetime:
        return _ensure_utc(value)


class RunConfig(BaseSchema):
    run_id: str
    seed: int
    max_generations: int
    population_size: int
    num_islands: int
    top_k_for_full_eval: int
    generator_provider_id: str
    refiner_provider_id: str
    task_name: str


class LLMProviderConfig(BaseSchema):
    provider_id: str
    provider_type: str
    base_url: str | None = None
    model_name: str
    api_key: str | None = None
    max_retries: int = 3
    timeout_seconds: int = 30


class EvalResult(BaseSchema):
    candidate_id: str
    fidelity: Literal["cheap", "full"]
    score: float
    runtime_ms: float
    error_type: str | None = None
    metadata: dict[str, object]
