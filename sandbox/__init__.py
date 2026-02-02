"""
Sandbox Module

Safe execution environment for untrusted LLM-generated code.

This module provides:
- Subprocess-based code execution
- Timeout enforcement
- Memory and CPU limits (platform-dependent)
- Import restrictions and allowlisting
- Best-effort security (documented limitations)

WARNING: This sandbox is NOT cryptographically secure. It provides best-effort
isolation suitable for a research/course project, not production use.
"""

__version__ = "0.1.0"
