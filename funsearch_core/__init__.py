"""
FunSearch Core Module

Core search loop, islands, selection/mutation/promotion logic for evolutionary search.

This module implements the main FunSearch evolutionary algorithm:
- Population management across multiple islands
- Selection strategies (tournament, rank-based)
- Mutation operators (LLM-guided)
- Promotion and diversity maintenance
- Functional deduplication (Sample-efficient FunSearch)
"""

__version__ = "0.1.0"

from .deduplication import (
    BehaviorSignature,
    DeduplicationStats,
    FunctionalDeduplicator,
    create_binpacking_probe_runner,
)

__all__ = [
    "BehaviorSignature",
    "DeduplicationStats",
    "FunctionalDeduplicator",
    "create_binpacking_probe_runner",
]
