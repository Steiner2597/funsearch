"""
Child process protocol for sandbox execution.
"""

from __future__ import annotations

import builtins
import json
import math
import sys
import time
from typing import Callable, cast

from sandbox import policy

CHILD_TEMPLATE = """
from sandbox.protocol import child_main
child_main()
""".strip()

# Batch evaluation template for bin packing
BATCH_CHILD_TEMPLATE = """
from sandbox.protocol import batch_child_main
batch_child_main()
""".strip()


def _load_payload() -> dict[str, object]:
    raw = sys.stdin.read()
    if not raw:
        return {}
    try:
        return cast(dict[str, object], json.loads(raw))
    except json.JSONDecodeError:
        return {}


def _format_error(exc: BaseException) -> str:
    return f"{exc.__class__.__name__}: {exc}"


def child_main() -> None:
    """Entry point for the sandbox child process (single call mode)."""
    start = time.perf_counter()
    payload = _load_payload()
    code_value = payload.get("code", "")
    code = str(code_value)
    instance_data = cast(dict[str, object], payload.get("instance_data", {}))
    allowed_modules = cast(list[str], payload.get("allowed_modules", list(policy.ALLOWED_MODULES)))

    response: dict[str, object]
    try:
        exec_fn = builtins.exec
        _ = policy.install_import_guard(
            allowed_modules=allowed_modules,
            blocked_modules=policy.BLOCKED_MODULES,
        )
        policy.disable_blocked_builtins(policy.BLOCKED_MODULES)

        namespace: dict[str, object] = {}
        exec_fn(code, namespace, namespace)
        func = namespace.get("score_bin")
        if not callable(func):
            raise RuntimeError("score_bin function not defined")

        score_bin = cast(Callable[[object, object, object, object], object], func)
        result = score_bin(
            instance_data.get("item_size"),
            instance_data.get("remaining_capacity"),
            instance_data.get("bin_index"),
            instance_data.get("step"),
        )
        response = {
            "success": True,
            "result": result,
            "error": None,
        }
    except BaseException as exc:  # noqa: BLE001 - capture all child errors
        response = {
            "success": False,
            "result": None,
            "error": _format_error(exc),
        }

    runtime_ms = (time.perf_counter() - start) * 1000
    response["runtime_ms"] = runtime_ms
    _ = sys.stdout.write(json.dumps(response))


def _pack_with_heuristic_internal(
    items: list[int],
    capacity: int,
    score_bin_func: Callable[[int, int, int, int], float],
) -> int:
    """Pack items greedily using a candidate scoring function.
    
    This is a copy of the logic from evaluator.bin_packing to run inside sandbox.
    """

    class Bin:
        def __init__(self, cap: int) -> None:
            self.remaining = cap
            self.items: list[int] = []
        
        def add(self, item_size: int) -> None:
            self.items.append(item_size)
            self.remaining -= item_size

    bins: list[Bin] = []
    for step, item_size in enumerate(items):
        best_bin: int | None = None
        best_score = float('-inf')
        for i, bin_info in enumerate(bins):
            if bin_info.remaining >= item_size:
                try:
                    score = float(score_bin_func(item_size, bin_info.remaining, i, step))
                    if not math.isfinite(score):
                        continue
                except Exception:
                    continue
                if score > best_score:
                    best_score = score
                    best_bin = i

        if best_bin is not None:
            bins[best_bin].add(item_size)
        else:
            new_bin = Bin(capacity)
            new_bin.add(item_size)
            bins.append(new_bin)

    return len(bins)


def batch_child_main() -> None:
    """Entry point for batch bin packing evaluation in sandbox.
    
    This runs the entire bin packing evaluation inside the sandbox,
    avoiding per-call subprocess overhead.
    """
    start = time.perf_counter()
    payload = _load_payload()
    code_value = payload.get("code", "")
    code = str(code_value)
    instances = cast(list[dict[str, object]], payload.get("instances", []))
    capacity = int(payload.get("capacity", 100))
    allowed_modules = cast(list[str], payload.get("allowed_modules", list(policy.ALLOWED_MODULES)))

    response: dict[str, object]
    try:
        exec_fn = builtins.exec
        _ = policy.install_import_guard(
            allowed_modules=allowed_modules,
            blocked_modules=policy.BLOCKED_MODULES,
        )
        policy.disable_blocked_builtins(policy.BLOCKED_MODULES)

        namespace: dict[str, object] = {}
        exec_fn(code, namespace, namespace)
        func = namespace.get("score_bin")
        if not callable(func):
            raise RuntimeError("score_bin function not defined")

        score_bin = cast(Callable[[int, int, int, int], float], func)
        
        # Evaluate on all instances
        results: list[int] = []
        for inst in instances:
            items = cast(list[int], inst.get("items", []))
            inst_capacity = int(inst.get("capacity", capacity))
            num_bins = _pack_with_heuristic_internal(items, inst_capacity, score_bin)
            results.append(num_bins)
        
        response = {
            "success": True,
            "results": results,
            "error": None,
        }
    except BaseException as exc:  # noqa: BLE001 - capture all child errors
        response = {
            "success": False,
            "results": None,
            "error": _format_error(exc),
        }

    runtime_ms = (time.perf_counter() - start) * 1000
    response["runtime_ms"] = runtime_ms
    _ = sys.stdout.write(json.dumps(response))


if __name__ == "__main__":
    child_main()
