"""Runs summary table generator for experiment artifacts."""

from __future__ import annotations

import csv
import hashlib
import json
import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


class RunsSummarizer:
    """Scans artifacts directory and generates summary tables."""
    
    def __init__(self, artifacts_root: Path):
        """Initialize summarizer with artifacts root directory.
        
        Args:
            artifacts_root: Path to artifacts directory containing run folders
        """
        self.artifacts_root = Path(artifacts_root)
    
    def scan_runs(self) -> list[dict[str, Any]]:
        """Scan artifacts directory and collect metadata from all runs.
        
        Returns:
            List of run summaries, sorted by timestamp (newest first)
        """
        runs = []
        
        if not self.artifacts_root.exists():
            return runs
        
        for run_dir in self.artifacts_root.iterdir():
            if not run_dir.is_dir():
                continue
            
            try:
                run_summary = self._process_run(run_dir)
                if run_summary:
                    runs.append(run_summary)
            except Exception as e:
                logger.warning(f"Failed to process run {run_dir.name}: {e}")
        
        runs.sort(key=lambda r: r["timestamp_start"], reverse=True)
        
        return runs
    
    def _process_run(self, run_dir: Path) -> dict[str, Any] | None:
        """Process a single run directory and extract summary.
        
        Args:
            run_dir: Path to run directory
            
        Returns:
            Run summary dict or None if invalid
        """
        config_path = run_dir / "config.yaml"
        metrics_path = run_dir / "metrics.jsonl"
        
        if not config_path.exists():
            logger.warning(f"Skipping {run_dir.name}: config.yaml not found")
            return None
        
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
        
        metrics = []
        if metrics_path.exists():
            with open(metrics_path, "r") as f:
                for line in f:
                    if line.strip():
                        metrics.append(json.loads(line))
        
        if not metrics:
            logger.warning(f"Skipping {run_dir.name}: no metrics found")
            return None
        
        first_metric = metrics[0]
        last_metric = metrics[-1]
        
        total_candidates = sum(
            m.get("overall", {}).get("count", 0) for m in metrics
        )
        
        if "dedup" in last_metric and isinstance(last_metric["dedup"], dict):
            dedup_skipped_total = last_metric["dedup"].get("skipped_total", 0)
        else:
            dedup_skipped_total = last_metric.get("dedup_skipped_total", 0)
        
        unique_candidates = total_candidates - dedup_skipped_total
        unique_rate = unique_candidates / total_candidates if total_candidates > 0 else 0.0
        
        best_score = max(
            m.get("overall", {}).get("best_score", float("-inf")) for m in metrics
        )
        
        avg_score_final = last_metric.get("overall", {}).get("avg_score", 0.0)
        
        dataset = self._extract_dataset(config)
        
        config_hash = self._compute_config_hash(config)
        
        return {
            "run_id": config["run_id"],
            "timestamp_start": first_metric["timestamp"],
            "timestamp_end": last_metric["timestamp"],
            "dataset": dataset,
            "task": config.get("task_name", "unknown"),
            "generations_completed": len(metrics),
            "best_score": best_score,
            "avg_score_final": avg_score_final,
            "unique_rate": unique_rate,
            "total_candidates": total_candidates,
            "dedup_skipped_total": dedup_skipped_total,
            "config_hash": config_hash,
        }
    
    def _extract_dataset(self, config: dict[str, Any]) -> str:
        """Extract dataset name from config.
        
        Args:
            config: Configuration dictionary
            
        Returns:
            Dataset name string
        """
        evaluator = config.get("evaluator", {})
        if isinstance(evaluator, dict):
            dataset_type = evaluator.get("type", "unknown")
            return dataset_type
        return "unknown"
    
    def _compute_config_hash(self, config: dict[str, Any]) -> str:
        """Compute hash of relevant config fields for grouping similar runs.
        
        Args:
            config: Configuration dictionary
            
        Returns:
            8-character hex hash string
        """
        relevant_fields = {
            "max_generations": config.get("max_generations"),
            "population_size": config.get("population_size"),
            "num_islands": config.get("num_islands"),
            "top_k_for_full_eval": config.get("top_k_for_full_eval"),
            "task_name": config.get("task_name"),
            "evaluator": config.get("evaluator"),
        }
        
        hash_input = json.dumps(relevant_fields, sort_keys=True).encode()
        return hashlib.sha256(hash_input).hexdigest()[:8]
    
    def export_csv(self, output_path: Path) -> None:
        """Export runs summary to CSV file.
        
        Args:
            output_path: Path to output CSV file
        """
        runs = self.scan_runs()
        
        if not runs:
            return
        
        fieldnames = [
            "run_id",
            "timestamp_start",
            "timestamp_end",
            "dataset",
            "task",
            "generations_completed",
            "best_score",
            "avg_score_final",
            "unique_rate",
            "total_candidates",
            "dedup_skipped_total",
            "config_hash",
        ]
        
        with open(output_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(runs)
    
    def export_json(self, output_path: Path) -> None:
        """Export runs summary to JSON file.
        
        Args:
            output_path: Path to output JSON file
        """
        runs = self.scan_runs()
        
        with open(output_path, "w") as f:
            json.dump(runs, f, indent=2)
