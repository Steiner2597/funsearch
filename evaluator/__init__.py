"""
Evaluator Module

Task definitions and evaluation functions.

This module provides:
- Abstract evaluator interface
- Bin packing problem implementation
- Multi-fidelity evaluation (cheap_eval, full_eval)
- Deterministic instance generation
- Score computation and validation
- OR-Library and Weibull benchmark dataset loaders
"""

__version__ = "0.1.0"

from .datasets import (
    BinPackingInstance,
    BinPackingDataset,
    load_orlib_dataset,
    load_orlib_small,
    load_orlib_large,
    generate_weibull_dataset,
    generate_weibull_instance,
    dataset_summary,
    ORLIB_FILES,
)

__all__ = [
    "BinPackingInstance",
    "BinPackingDataset",
    "load_orlib_dataset",
    "load_orlib_small",
    "load_orlib_large",
    "generate_weibull_dataset",
    "generate_weibull_instance",
    "dataset_summary",
    "ORLIB_FILES",
]
