"""Retry policy with exponential backoff for LLM calls."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")

_AUTH_ERROR_NAMES = {
    "AuthenticationError",
    "PermissionDeniedError",
}

_INVALID_CONFIG_NAMES = {
    "BadRequestError",
    "UnprocessableEntityError",
}

_RETRYABLE_NAMES = {
    "RateLimitError",
    "APITimeoutError",
    "APIConnectionError",
    "InternalServerError",
    "ServiceUnavailableError",
}


def _exception_name(exc: BaseException) -> str:
    return exc.__class__.__name__


class RetryPolicy:
    """Simple exponential backoff retry helper."""

    max_retries: int
    sleep_fn: Callable[[float], None]

    def __init__(
        self,
        max_retries: int = 3,
        sleep_fn: Callable[[float], None] | None = None,
    ) -> None:
        self.max_retries = max_retries
        self.sleep_fn = sleep_fn or time.sleep

    def backoff_seconds(self, attempt_index: int) -> int:
        value = 1 << attempt_index
        return value if value <= 8 else 8

    def execute(self, operation: Callable[[], T]) -> T:
        retries = 0
        while True:
            try:
                return operation()
            except Exception as exc:  # noqa: BLE001
                if self._should_fail_fast(exc):
                    raise
                if not self._is_retryable(exc) or retries >= self.max_retries:
                    raise
                delay = self.backoff_seconds(retries)
                retries += 1
                self.sleep_fn(delay)

    def _should_fail_fast(self, exc: Exception) -> bool:
        if isinstance(exc, ValueError):
            return True
        name = _exception_name(exc)
        if name in _AUTH_ERROR_NAMES:
            return True
        if name in _INVALID_CONFIG_NAMES:
            return True
        return False

    def _is_retryable(self, exc: Exception) -> bool:
        if isinstance(exc, (TimeoutError, ConnectionError)):
            return True
        name = _exception_name(exc)
        if name in _RETRYABLE_NAMES:
            return True
        if name == "APIStatusError":
            status_code = _coerce_status_code(getattr(exc, "status_code", None))
            if status_code is None:
                response = getattr(exc, "response", None)
                status_code = _coerce_status_code(getattr(response, "status_code", None))
            if status_code is None:
                return False
            return status_code >= 500 or status_code == 429
        return False


def _coerce_status_code(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(float(value))
        except ValueError:
            return None
    return None
