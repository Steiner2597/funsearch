"""
Subprocess-based sandbox executor for untrusted code.
"""

from __future__ import annotations

import json
import os
import sys
import time
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from sandbox import policy
from sandbox import protocol


@dataclass
class ExecutionResult:
    success: bool
    result: float | None
    error: str | None
    runtime_ms: float
    timed_out: bool = False


class SandboxExecutor:
    """
    Execute untrusted code in a subprocess with best-effort limits.

    On Unix platforms, CPU and memory limits are enforced via resource.setrlimit.
    On Windows, these limits degrade gracefully and only wall-clock timeout applies.
    """

    DEFAULT_MEMORY_LIMIT_MB: int = 256

    def __init__(self, memory_limit_mb: int | None = None) -> None:
        self.memory_limit_mb: int = memory_limit_mb or self.DEFAULT_MEMORY_LIMIT_MB

    def execute(
        self,
        code: str,
        instance_data: Mapping[str, float | int | None],
        timeout_seconds: int,
    ) -> ExecutionResult:
        payload = {
            "code": code,
            "instance_data": dict(instance_data),
            "allowed_modules": policy.ALLOWED_MODULES,
        }

        env = os.environ.copy()
        project_root = str(Path(__file__).resolve().parents[1])
        existing_pythonpath = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = (
            f"{project_root}{os.pathsep}{existing_pythonpath}"
            if existing_pythonpath
            else project_root
        )

        start = time.perf_counter()
        try:
            completed = subprocess.run(
                [sys.executable, "-c", protocol.CHILD_TEMPLATE],
                input=json.dumps(payload),
                text=True,
                capture_output=True,
                timeout=timeout_seconds,
                env=env,
                preexec_fn=self._limit_resources(timeout_seconds) if os.name != "nt" else None,
            )
        except subprocess.TimeoutExpired:
            runtime_ms = (time.perf_counter() - start) * 1000
            return ExecutionResult(
                success=False,
                result=None,
                error=f"Timeout after {timeout_seconds}s",
                runtime_ms=runtime_ms,
                timed_out=True,
            )

        runtime_ms = (time.perf_counter() - start) * 1000
        if not completed.stdout:
            error = completed.stderr.strip() or "Empty response from sandbox"
            return ExecutionResult(False, None, error, runtime_ms)

        try:
            loaded = cast(object, json.loads(completed.stdout))
        except json.JSONDecodeError as exc:
            error = f"Invalid JSON from sandbox: {exc}"
            return ExecutionResult(False, None, error, runtime_ms)

        if not isinstance(loaded, dict):
            return ExecutionResult(False, None, "Invalid response type from sandbox", runtime_ms)
        data = cast(dict[str, object], loaded)

        success = bool(data.get("success"))
        result_value = data.get("result")
        error_value = data.get("error")
        runtime_value = data.get("runtime_ms")
        error = str(error_value) if error_value is not None else None
        if isinstance(runtime_value, (int, float, str)):
            try:
                runtime_ms = float(runtime_value)
            except (TypeError, ValueError):
                runtime_ms = float(runtime_ms)

        if success:
            if not isinstance(result_value, (int, float, str)):
                return ExecutionResult(
                    False,
                    None,
                    "Result is not numeric",
                    runtime_ms,
                )
            try:
                result = float(result_value)
            except (TypeError, ValueError):
                return ExecutionResult(
                    False,
                    None,
                    "Result is not numeric",
                    runtime_ms,
                )
        else:
            result = None

        return ExecutionResult(success, result, error, runtime_ms)

    def execute_batch(
        self,
        code: str,
        instances: list[dict[str, object]],
        capacity: int,
        timeout_seconds: int,
    ) -> "BatchExecutionResult":
        """Execute bin packing evaluation on multiple instances in a single subprocess.
        
        This is much faster than calling execute() for each score_bin call,
        as the entire evaluation runs in one subprocess.
        
        Args:
            code: Python code defining score_bin function
            instances: List of {"items": [...], "capacity": int} dicts
            capacity: Default capacity if not specified per instance
            timeout_seconds: Maximum execution time
            
        Returns:
            BatchExecutionResult with list of bin counts or error
        """
        payload = {
            "code": code,
            "instances": instances,
            "capacity": capacity,
            "allowed_modules": policy.ALLOWED_MODULES,
        }

        env = os.environ.copy()
        project_root = str(Path(__file__).resolve().parents[1])
        existing_pythonpath = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = (
            f"{project_root}{os.pathsep}{existing_pythonpath}"
            if existing_pythonpath
            else project_root
        )

        start = time.perf_counter()
        try:
            completed = subprocess.run(
                [sys.executable, "-c", protocol.BATCH_CHILD_TEMPLATE],
                input=json.dumps(payload),
                text=True,
                capture_output=True,
                timeout=timeout_seconds,
                env=env,
                preexec_fn=self._limit_resources(timeout_seconds) if os.name != "nt" else None,
            )
        except subprocess.TimeoutExpired:
            runtime_ms = (time.perf_counter() - start) * 1000
            return BatchExecutionResult(
                success=False,
                results=None,
                error=f"Timeout after {timeout_seconds}s",
                runtime_ms=runtime_ms,
                timed_out=True,
            )

        runtime_ms = (time.perf_counter() - start) * 1000
        if not completed.stdout:
            error = completed.stderr.strip() or "Empty response from sandbox"
            return BatchExecutionResult(False, None, error, runtime_ms)

        try:
            loaded = cast(object, json.loads(completed.stdout))
        except json.JSONDecodeError as exc:
            error = f"Invalid JSON from sandbox: {exc}"
            return BatchExecutionResult(False, None, error, runtime_ms)

        if not isinstance(loaded, dict):
            return BatchExecutionResult(False, None, "Invalid response type from sandbox", runtime_ms)
        data = cast(dict[str, object], loaded)

        success = bool(data.get("success"))
        results_value = data.get("results")
        error_value = data.get("error")
        runtime_value = data.get("runtime_ms")
        error = str(error_value) if error_value is not None else None
        if isinstance(runtime_value, (int, float, str)):
            try:
                runtime_ms = float(runtime_value)
            except (TypeError, ValueError):
                pass

        if success and isinstance(results_value, list):
            results = [int(r) for r in results_value]
        else:
            results = None

        return BatchExecutionResult(success, results, error, runtime_ms)

    def _limit_resources(self, timeout_seconds: int):
        """Return a preexec_fn to enforce resource limits on Unix."""
        def _apply_limits():
            try:
                import resource
            except ImportError:
                return
            cpu_seconds = max(1, int(timeout_seconds) + 1)
            memory_bytes = int(self.memory_limit_mb * 1024 * 1024)
            resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds + 1))
            if hasattr(resource, "RLIMIT_AS"):
                resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
            elif hasattr(resource, "RLIMIT_DATA"):
                resource.setrlimit(resource.RLIMIT_DATA, (memory_bytes, memory_bytes))

        return _apply_limits


@dataclass
class BatchExecutionResult:
    """Result of batch bin packing evaluation in sandbox."""
    success: bool
    results: list[int] | None  # Number of bins for each instance
    error: str | None
    runtime_ms: float
    timed_out: bool = False
