"""LLM provider implementations."""

from __future__ import annotations

import hashlib
import importlib
import os
import time
from collections.abc import Mapping, Sequence
from typing import Protocol, cast

from funsearch_core.schemas import LLMProviderConfig

from .base import BaseLLMProvider, LLMResponse
from .retry import RetryPolicy


class _ChatCompletions(Protocol):
    def create(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> object: ...


class _Chat(Protocol):
    completions: _ChatCompletions


class _OpenAIClient(Protocol):
    chat: _Chat


def _load_openai_client(
    api_key: str | None,
    base_url: str | None,
    timeout_seconds: int,
) -> _OpenAIClient:
    try:
        module = importlib.import_module("openai")
    except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency at runtime
        raise ImportError("openai is required to use OpenAIProvider") from exc
    openai_client = getattr(module, "OpenAI", None)
    if openai_client is None:
        raise ImportError("openai.OpenAI client is unavailable")
    return cast(
        _OpenAIClient,
        openai_client(api_key=api_key, base_url=base_url, timeout=timeout_seconds),
    )


def _extract_usage(raw_usage: object) -> dict[str, int]:
    if raw_usage is None:
        return {}
    model_dump = getattr(raw_usage, "model_dump", None)
    if callable(model_dump):
        raw_usage = model_dump()
    if isinstance(raw_usage, Mapping):
        typed_usage = cast(Mapping[str, object], raw_usage)
        usage: dict[str, int] = {}
        for key, value in typed_usage.items():
            if isinstance(value, bool):
                usage[key] = int(value)
            elif isinstance(value, (int, float)):
                usage[key] = int(value)
            elif isinstance(value, str):
                try:
                    usage[key] = int(float(value))
                except ValueError:
                    continue
        return usage
    return {}


def _response_to_dict(response: object) -> dict[str, object]:
    if response is None:
        return {}
    model_dump = getattr(response, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump()
        if isinstance(dumped, Mapping):
            return dict(cast(Mapping[str, object], dumped))
    if isinstance(response, Mapping):
        return dict(cast(Mapping[str, object], response))
    return {"repr": repr(response)}


def _extract_text(response: object) -> str:
    if response is None:
        return ""
    choices = cast(Sequence[object] | None, getattr(response, "choices", None))
    if not choices:
        return ""
    choice = choices[0]
    message = cast(object, getattr(choice, "message", None))
    content = cast(object | None, getattr(message, "content", None)) if message is not None else None
    if content is not None:
        return str(content)
    text_value = cast(object | None, getattr(choice, "text", None))
    if text_value is not None:
        return str(text_value)
    return ""


class OpenAIProvider(BaseLLMProvider):
    """OpenAI-compatible provider (OpenAI, DeepSeek, etc.)."""

    provider_type: str
    _client: _OpenAIClient
    _base_url: str | None
    _timeout_seconds: int
    _retry_policy: RetryPolicy | None

    def __init__(
        self,
        provider_id: str,
        model_name: str,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout_seconds: int = 30,
        retry_policy: RetryPolicy | None = None,
        provider_type: str = "openai",
    ) -> None:
        super().__init__(provider_id=provider_id, model_name=model_name)
        self.provider_type = provider_type
        # 根据 provider_type 选择合适的环境变量
        if api_key:
            api_key_value = api_key
        elif provider_type == "deepseek":
            api_key_value = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
        else:
            api_key_value = os.getenv("OPENAI_API_KEY")
        self._client = _load_openai_client(api_key_value, base_url, timeout_seconds)
        self._base_url = base_url
        self._timeout_seconds = timeout_seconds
        self._retry_policy = retry_policy

    def generate(  # pyright: ignore[reportImplicitOverride]
        self, prompt: str, temperature: float, max_tokens: int
    ) -> LLMResponse:
        def _call() -> object:
            return self._client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
            )

        start = time.perf_counter()
        if self._retry_policy is None:
            response = _call()
        else:
            response = self._retry_policy.execute(_call)
        latency_ms = (time.perf_counter() - start) * 1000

        text = _extract_text(response)
        usage = _extract_usage(getattr(response, "usage", None))
        raw_response = _response_to_dict(response)
        model_id = str(getattr(response, "model", None) or self.model_name)
        return LLMResponse(
            text=text,
            usage=usage,
            latency_ms=latency_ms,
            raw_response=raw_response,
            model_id=model_id,
        )

    def get_provider_info(self) -> dict[str, object]:  # pyright: ignore[reportImplicitOverride]
        return {
            "provider_id": self.provider_id,
            "provider_type": self.provider_type,
            "model_name": self.model_name,
            "base_url": self._base_url,
            "timeout_seconds": self._timeout_seconds,
        }


class FakeProvider(BaseLLMProvider):
    """Deterministic fake provider for offline tests."""

    call_count: int

    def __init__(self, provider_id: str, model_name: str = "fake-model") -> None:
        super().__init__(provider_id=provider_id, model_name=model_name)
        self.call_count = 0

    def generate(  # pyright: ignore[reportImplicitOverride]
        self, prompt: str, temperature: float, max_tokens: int
    ) -> LLMResponse:
        self.call_count += 1
        prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        bias = int(prompt_hash[:8], 16) % 10
        text = (
            "```python\n"
            "def score_bin(item_size, remaining_capacity, bin_index, step) -> float:\n"
            f"    return float(remaining_capacity) - {bias}\n"
            "```"
        )
        usage = {
            "prompt_tokens": len(prompt.split()),
            "completion_tokens": len(text.split()),
            "total_tokens": len(prompt.split()) + len(text.split()),
        }
        return LLMResponse(
            text=text,
            usage=usage,
            latency_ms=0.0,
            raw_response={
                "fake": True,
                "prompt_hash": prompt_hash,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
            model_id=self.model_name,
        )

    def get_provider_info(self) -> dict[str, object]:  # pyright: ignore[reportImplicitOverride]
        return {
            "provider_id": self.provider_id,
            "provider_type": "fake",
            "model_name": self.model_name,
            "max_context": None,
        }


def create_provider(
    config: LLMProviderConfig,
    retry_policy: RetryPolicy | None = None,
) -> BaseLLMProvider:
    provider_type = config.provider_type.lower()
    if provider_type in {"openai", "deepseek", "glm"}:
        policy = retry_policy or RetryPolicy(max_retries=config.max_retries)
        return OpenAIProvider(
            provider_id=config.provider_id,
            model_name=config.model_name,
            api_key=config.api_key,
            base_url=config.base_url,
            timeout_seconds=config.timeout_seconds,
            retry_policy=policy,
            provider_type=provider_type,
        )
    if provider_type == "fake":
        return FakeProvider(provider_id=config.provider_id, model_name=config.model_name)
    raise ValueError(f"Unsupported provider type: {config.provider_type}")
