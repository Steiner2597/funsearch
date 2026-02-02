"""Experiment configuration with YAML support."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import Field

from funsearch_core.schemas import RunConfig


class ExperimentConfig(RunConfig):
    """Extended configuration for full experiments with artifact management."""
    
    # Evaluator configuration (task-specific)
    evaluator: dict[str, Any] = Field(default_factory=dict)
    
    # LLM provider configurations
    llm_providers: list[dict[str, Any]] = Field(default_factory=list)
    
    # Artifact management
    artifact_dir: str = "artifacts"
    save_interval: int = 5  # Save every N generations
    
    # A/B variant selection
    variant: str | None = None
    
    # Optional resume support
    resume_from: str | None = None
    
    sandbox_memory_limit_mb: int = 256
    sandbox_timeout_s: float = 5.0
    batch_timeout_s: float = 30.0


def load_config(yaml_path: str | Path) -> ExperimentConfig:
    """Load experiment configuration from YAML file.
    
    Args:
        yaml_path: Path to YAML configuration file
        
    Returns:
        ExperimentConfig instance
        
    Raises:
        FileNotFoundError: If YAML file doesn't exist
        ValueError: If YAML is invalid or missing required fields
    """
    yaml_path = Path(yaml_path)
    
    if not yaml_path.exists():
        raise FileNotFoundError(f"Config file not found: {yaml_path}")
    
    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    
    if not data:
        raise ValueError(f"Empty or invalid YAML file: {yaml_path}")
    
    try:
        return ExperimentConfig.from_dict(data)
    except Exception as e:
        raise ValueError(f"Invalid configuration in {yaml_path}: {e}") from e


def save_config(config: ExperimentConfig, yaml_path: str | Path) -> None:
    """Save experiment configuration to YAML file for reproducibility.
    
    Args:
        config: ExperimentConfig to save
        yaml_path: Path where to save YAML file
    """
    yaml_path = Path(yaml_path)
    yaml_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Convert to dict and save as YAML
    data = config.to_dict()
    
    with open(yaml_path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False, indent=2)
