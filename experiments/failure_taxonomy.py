"""Failure classification and analysis."""

from enum import Enum


class FailureType(str, Enum):
    TIMEOUT = "timeout"
    IMPORT_BLOCKED = "import_blocked"
    RUNTIME_ERROR = "runtime_error"
    SYNTAX_ERROR = "syntax_error"
    INVALID_OUTPUT = "invalid_output"
    OVERFLOW = "overflow"
    OTHER = "other"


class FailureAnalyzer:
    def __init__(self):
        self.failures: dict[FailureType, int] = {ft: 0 for ft in FailureType}
    
    def classify_error(self, error_msg: str) -> FailureType:
        error_lower = error_msg.lower()
        
        if 'timeout' in error_lower or 'timed out' in error_lower:
            return FailureType.TIMEOUT
        elif 'import' in error_lower and ('blocked' in error_lower or 'not allowed' in error_lower):
            return FailureType.IMPORT_BLOCKED
        elif 'syntaxerror' in error_lower or 'invalid syntax' in error_lower:
            return FailureType.SYNTAX_ERROR
        elif 'overflow' in error_lower:
            return FailureType.OVERFLOW
        elif 'invalid output' in error_lower or 'must return' in error_lower:
            return FailureType.INVALID_OUTPUT
        elif any(err in error_lower for err in ['error', 'exception', 'failed']):
            return FailureType.RUNTIME_ERROR
        else:
            return FailureType.OTHER
    
    def record_failure(self, error_msg: str) -> None:
        failure_type = self.classify_error(error_msg)
        self.failures[failure_type] += 1
    
    def get_failure_stats(self) -> dict[FailureType, int]:
        return dict(self.failures)
    
    def get_top_failures(self, n: int = 5) -> list[tuple[str, int]]:
        sorted_failures = sorted(
            self.failures.items(),
            key=lambda x: x[1],
            reverse=True
        )
        return [(ft.value, count) for ft, count in sorted_failures[:n]]
