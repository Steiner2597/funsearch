"""Run comparison functionality for experiment artifacts."""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


class RunComparator:
    
    def __init__(self, artifacts_root: Path):
        self.artifacts_root = Path(artifacts_root)
    
    def compare(self, run_ids: list[str]) -> dict[str, Any]:
        runs = []
        warnings = []
        
        for run_id in run_ids:
            run_dir = self.artifacts_root / run_id
            
            if not run_dir.exists():
                warning_msg = f"Run directory not found: {run_id}"
                logger.warning(warning_msg)
                warnings.append(warning_msg)
                continue
            
            try:
                run_data = self._load_run_data(run_dir, run_id)
                if run_data:
                    runs.append(run_data)
            except Exception as e:
                warning_msg = f"Failed to load run {run_id}: {e}"
                logger.warning(warning_msg)
                warnings.append(warning_msg)
        
        comparison = {"runs": runs}
        
        if warnings:
            comparison["warnings"] = warnings
        
        if runs:
            best_score_winner = max(runs, key=lambda r: r["best_score"])
            comparison["best_score_winner"] = best_score_winner["run_id"]
            
            comparison["config_differences"] = self._compute_config_differences(runs)
        
        return comparison
    
    def _load_run_data(self, run_dir: Path, run_id: str) -> dict[str, Any] | None:
        config_path = run_dir / "config.yaml"
        metrics_path = run_dir / "metrics.jsonl"
        
        if not config_path.exists():
            logger.warning(f"Config not found for {run_id}")
            return None
        
        if not metrics_path.exists():
            logger.warning(f"Metrics not found for {run_id}")
            return None
        
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
        
        metrics = []
        with open(metrics_path, "r") as f:
            for line in f:
                if line.strip():
                    metrics.append(json.loads(line))
        
        if not metrics:
            return None
        
        best_score = max(
            m.get("overall", {}).get("best_score", float("-inf")) for m in metrics
        )
        
        time_to_best = 0
        for idx, m in enumerate(metrics, 1):
            if m.get("overall", {}).get("best_score") == best_score:
                time_to_best = idx
                break
        
        total_candidates = sum(
            m.get("overall", {}).get("count", 0) for m in metrics
        )
        
        last_metric = metrics[-1]
        if "dedup" in last_metric and isinstance(last_metric["dedup"], dict):
            dedup_skipped_total = last_metric["dedup"].get("skipped_total", 0)
        else:
            dedup_skipped_total = last_metric.get("dedup_skipped_total", 0)
        
        unique_candidates = total_candidates - dedup_skipped_total
        unique_rate = unique_candidates / total_candidates if total_candidates > 0 else 0.0
        
        final_diversity = unique_rate
        
        return {
            "run_id": run_id,
            "best_score": best_score,
            "unique_rate": unique_rate,
            "time_to_best": time_to_best,
            "final_diversity": final_diversity,
            "generations_completed": len(metrics),
            "config": config,
        }
    
    def _compute_config_differences(self, runs: list[dict[str, Any]]) -> dict[str, list[Any]]:
        if not runs:
            return {}
        
        all_keys = set()
        for run in runs:
            all_keys.update(run["config"].keys())
        
        differences = {}
        
        for key in all_keys:
            values = [run["config"].get(key) for run in runs]
            
            if len(set(str(v) for v in values)) > 1:
                differences[key] = values
        
        return differences
    
    def export_markdown(self, comparison: dict[str, Any], output_path: Path) -> None:
        runs = comparison.get("runs", [])
        
        lines = ["# Run Comparison Report", ""]
        
        if not runs:
            lines.append("No runs to compare.")
            Path(output_path).write_text("\n".join(lines), encoding="utf-8")
            return
        
        lines.append("## Summary")
        lines.append("")
        lines.append("| Run ID | Best Score | Unique Rate | Time to Best | Generations | Final Diversity |")
        lines.append("|--------|------------|-------------|--------------|-------------|-----------------|")
        
        best_score_winner = comparison.get("best_score_winner")
        
        for run in runs:
            winner_marker = " 🏆" if run["run_id"] == best_score_winner else ""
            lines.append(
                f"| {run['run_id']}{winner_marker} | {run['best_score']:.2f} | "
                f"{run['unique_rate']:.2%} | {run['time_to_best']} | "
                f"{run['generations_completed']} | {run['final_diversity']:.2%} |"
            )
        
        lines.append("")
        
        config_diffs = comparison.get("config_differences", {})
        if config_diffs:
            lines.append("## Config Differences")
            lines.append("")
            lines.append("| Parameter | " + " | ".join(r["run_id"] for r in runs) + " |")
            lines.append("|" + "---|" * (len(runs) + 1))
            
            for key, values in config_diffs.items():
                values_str = " | ".join(str(v) for v in values)
                lines.append(f"| {key} | {values_str} |")
            
            lines.append("")
        
        warnings = comparison.get("warnings", [])
        if warnings:
            lines.append("## Warnings")
            lines.append("")
            for warning in warnings:
                lines.append(f"- {warning}")
            lines.append("")
        
        Path(output_path).write_text("\n".join(lines), encoding="utf-8")
    
    def export_csv(self, comparison: dict[str, Any], output_path: Path) -> None:
        runs = comparison.get("runs", [])
        
        if not runs:
            return
        
        fieldnames = [
            "run_id",
            "best_score",
            "unique_rate",
            "time_to_best",
            "final_diversity",
            "generations_completed",
        ]
        
        with open(output_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for run in runs:
                row = {key: run[key] for key in fieldnames}
                writer.writerow(row)
