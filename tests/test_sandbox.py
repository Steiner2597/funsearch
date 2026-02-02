import math

from sandbox.executor import SandboxExecutor


def _instance_data():
    return {
        "item_size": 3,
        "remaining_capacity": 10,
        "bin_index": 1,
        "step": 5,
    }


def test_infinite_loop_times_out():
    executor = SandboxExecutor()
    code = """
def score_bin(item_size, remaining_capacity, bin_index, step):
    while True:
        pass
"""
    result = executor.execute(code, _instance_data(), timeout_seconds=1)
    assert result.timed_out is True
    assert result.success is False


def test_import_socket_fails():
    executor = SandboxExecutor()
    code = """
import socket

def score_bin(item_size, remaining_capacity, bin_index, step):
    return 1.0
"""
    result = executor.execute(code, _instance_data(), timeout_seconds=2)
    assert result.success is False
    assert result.error
    assert "Import" in result.error or "allowlist" in result.error or "blocked" in result.error


def test_open_fails():
    executor = SandboxExecutor()
    code = """
def score_bin(item_size, remaining_capacity, bin_index, step):
    open('x', 'w')
    return 1.0
"""
    result = executor.execute(code, _instance_data(), timeout_seconds=2)
    assert result.success is False
    assert result.error
    assert "Blocked" in result.error or "policy" in result.error


def test_valid_heuristic_returns_numeric_score():
    executor = SandboxExecutor()
    code = """
import math

def score_bin(item_size, remaining_capacity, bin_index, step):
    return float(item_size) / (remaining_capacity + 1) + math.sqrt(bin_index + step)
"""
    result = executor.execute(code, _instance_data(), timeout_seconds=2)
    assert result.success is True
    assert isinstance(result.result, float)
    assert math.isfinite(result.result)


def test_syntax_error_is_caught():
    executor = SandboxExecutor()
    code = """
def score_bin(item_size, remaining_capacity, bin_index, step)
    return 1.0
"""
    result = executor.execute(code, _instance_data(), timeout_seconds=2)
    assert result.success is False
    assert result.error
    assert "SyntaxError" in result.error
