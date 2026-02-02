"""Artifact management for experiment runs."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from funsearch_core.schemas import Candidate
from experiments.config import ExperimentConfig


class ArtifactManager:
    """Manages experiment artifacts: configs, databases, metrics, and exports."""
    
    def __init__(self, config: ExperimentConfig, variant: str | None = None):
        self.config = config
        self.variant = variant
        
        base_run_dir = Path(config.artifact_dir) / config.run_id
        
        if variant:
            self.run_dir = base_run_dir / f"variant_{variant}"
        else:
            self.run_dir = base_run_dir
        
        self.plots_dir = self.run_dir / "plots"
        
        self._create_directory_structure()
    
    def _create_directory_structure(self) -> None:
        """Create artifact directory structure for the run."""
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.plots_dir.mkdir(exist_ok=True)
    
    @property
    def config_path(self) -> Path:
        return self.run_dir / "config.yaml"
    
    @property
    def candidates_db_path(self) -> Path:
        return self.run_dir / "candidates.db"
    
    @property
    def llm_cache_db_path(self) -> Path:
        return self.run_dir / "llm_cache.db"
    
    @property
    def metrics_path(self) -> Path:
        return self.run_dir / "metrics.jsonl"
    
    @property
    def best_candidate_path(self) -> Path:
        return self.run_dir / "best_candidate.py"
    
    def snapshot_config(self) -> None:
        """Save a snapshot of the configuration for reproducibility."""
        from experiments.config import save_config
        save_config(self.config, self.config_path)
    
    def save_generation_metrics(self, generation: int, stats: dict[str, Any]) -> None:
        metrics_entry = {
            "generation": stats.get("generation", generation),
            "timestamp": stats.get("timestamp", datetime.now(timezone.utc).isoformat()),
            **{k: v for k, v in stats.items() if k not in ["generation", "timestamp"]}
        }
        
        with open(self.metrics_path, "a") as f:
            f.write(json.dumps(metrics_entry) + "\n")
    
    def export_best_candidate(self, candidate: Candidate) -> None:
        """Export the best candidate as a standalone Python file.
        
        Args:
            candidate: Best candidate to export
        """
        header = f'''"""Best candidate from run: {self.config.run_id}

Generated at: {datetime.now(timezone.utc).isoformat()}
Score: {candidate.score}
Generation: {candidate.generation}
Model: {candidate.model_id}
"""

'''
        
        content = header + candidate.code
        
        with open(self.best_candidate_path, "w") as f:
            f.write(content)
    
    def load_metrics(self) -> list[dict[str, Any]]:
        """Load all generation metrics from JSONL file.
        
        Returns:
            List of metric dictionaries, one per generation
        """
        if not self.metrics_path.exists():
            return []
        
        metrics = []
        with open(self.metrics_path, "r") as f:
            for line in f:
                if line.strip():
                    metrics.append(json.loads(line))
        
        return metrics
    
    def get_summary(self) -> dict[str, Any]:
        """Get a summary of the experiment run.
        
        Returns:
            Dictionary with run statistics
        """
        metrics = self.load_metrics()
        
        if not metrics:
            return {
                "run_id": self.config.run_id,
                "status": "no_data",
                "generations_completed": 0
            }
        
        last_gen = metrics[-1]
        
        # 支持两种格式: 旧格式 (best_score) 和新格式 (overall.best_score)
        best_scores = []
        for m in metrics:
            if "overall" in m and "best_score" in m["overall"]:
                best_scores.append(m["overall"]["best_score"])
            elif "best_score" in m:
                best_scores.append(m["best_score"])
        
        best_score = max(best_scores) if best_scores else float("-inf")
        
        return {
            "run_id": self.config.run_id,
            "status": "completed" if len(metrics) >= self.config.max_generations else "in_progress",
            "generations_completed": len(metrics),
            "max_generations": self.config.max_generations,
            "best_score": best_score,
            "last_generation": last_gen.get("generation"),
            "last_timestamp": last_gen.get("timestamp"),
            "has_best_candidate": self.best_candidate_path.exists()
        }
