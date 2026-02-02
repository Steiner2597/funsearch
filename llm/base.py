"""Base LLM provider interfaces and response schema."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from typing import cast


def _coerce_mapping(value: object) -> dict[str, object]:
    if isinstance(value, Mapping):
        typed_value = cast(Mapping[str, object], value)
        return {str(key): item for key, item in typed_value.items()}
    return {}


def _coerce_usage(value: object) -> dict[str, int]:
    if not isinstance(value, Mapping):
        return {}
    usage: dict[str, int] = {}
    typed_value = cast(Mapping[str, object], value)
    for key, item in typed_value.items():
        if isinstance(item, bool):
            usage[key] = int(item)
        elif isinstance(item, (int, float)):
            usage[key] = int(item)
        elif isinstance(item, str):
            try:
                usage[key] = int(float(item))
            except ValueError:
                continue
    return usage


def _coerce_float(value: object, default: float = 0.0) -> float:
    if value is None:
        return default
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return default
    return default


@dataclass(frozen=True)
class LLMResponse:
    text: str
    usage: dict[str, int]
    latency_ms: float
    raw_response: dict[str, object]
    model_id: str

    def to_dict(self) -> dict[str, object]:
        return {
            "text": self.text,
            "usage": dict(self.usage),
            "latency_ms": self.latency_ms,
            "raw_response": dict(self.raw_response),
            "model_id": self.model_id,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "LLMResponse":
        usage = _coerce_usage(payload.get("usage"))
        raw_response = _coerce_mapping(payload.get("raw_response"))
        latency_ms = _coerce_float(payload.get("latency_ms", 0.0))
        return cls(
            text=str(payload.get("text", "")),
            usage=usage,
            latency_ms=latency_ms,
            raw_response=raw_response,
            model_id=str(payload.get("model_id", "")),
        )


class BaseLLMProvider(ABC):
    """Abstract interface for LLM providers."""

    provider_id: str
    model_name: str

    def __init__(self, provider_id: str, model_name: str) -> None:
        self.provider_id = provider_id
        self.model_name = model_name
        self._metrics = {
            "calls": 0,
            "total_latency_ms": 0.0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "errors": 0,
        }

    @abstractmethod
    def generate(self, prompt: str, temperature: float, max_tokens: int) -> LLMResponse:
        """Generate a completion for the prompt."""

    @abstractmethod
    def get_provider_info(self) -> dict[str, object]:
        """Return metadata about the provider/model."""
    
    def get_metrics(self) -> dict[str, object]:
        """Get current metrics."""
        metrics: dict[str, object] = dict(self._metrics)
        if metrics["calls"] > 0:
            metrics["avg_latency_ms"] = float(self._metrics["total_latency_ms"]) / int(metrics["calls"])
        else:
            metrics["avg_latency_ms"] = 0.0
        return metrics
    
    def reset_metrics(self) -> None:
        """Reset metrics."""
        self._metrics = {
            "calls": 0,
            "total_latency_ms": 0.0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "errors": 0,
        }
