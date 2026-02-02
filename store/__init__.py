"""
Store Module

Candidate storage and persistence layer.

This module provides:
- SQLite-backed storage for candidates, evaluations, and runs
- Deduplication via code hashing
- Query interface for Top-K selection
- Run artifact management
- Metrics export
"""

__version__ = "0.1.0"
