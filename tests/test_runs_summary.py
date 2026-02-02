"""Tests for runs summary generation."""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path

import pytest
import yaml

from experiments.summary import RunsSummarizer


class TestRunsSummarizer:
    def test_init_creates_summarizer(self, tmp_path: Path) -> None:
        """Test that RunsSummarizer can be initialized with artifacts root."""
        summarizer = RunsSummarizer(tmp_path)
        
        assert summarizer.artifacts_root == tmp_path
    
    def test_scan_runs_empty_directory(self, tmp_path: Path) -> None:
        """Test scanning an empty artifacts directory."""
        summarizer = RunsSummarizer(tmp_path)
        runs = summarizer.scan_runs()
        
        assert runs == []
    
    def test_scan_runs_with_complete_run(self, tmp_path: Path) -> None:
        """Test scanning a directory with a complete run."""
        # Create a sample run directory
        run_dir = tmp_path / "funsearch_orlib_small_20260201_144522"
        run_dir.mkdir()
        
        # Create config.yaml
        config = {
            "run_id": "funsearch_orlib_small_20260201_144522",
            "seed": 42,
            "max_generations": 10,
            "task_name": "bin_packing",
            "evaluator": {"type": "orlib", "size": "small"},
        }
        with open(run_dir / "config.yaml", "w") as f:
            yaml.dump(config, f)
        
        # Create metrics.jsonl
        metrics = [
            {
                "generation": 0,
                "timestamp": "2026-02-01T05:15:16.658254+00:00",
                "overall": {"count": 8, "best_score": 59.2, "avg_score": 53.225},
                "dedup_skipped": 0,
                "dedup_skipped_total": 0,
            },
            {
                "generation": 1,
                "timestamp": "2026-02-01T05:20:30.123456+00:00",
                "overall": {"count": 12, "best_score": 62.5, "avg_score": 55.3},
                "dedup_skipped": 2,
                "dedup_skipped_total": 2,
            },
        ]
        with open(run_dir / "metrics.jsonl", "w") as f:
            for metric in metrics:
                f.write(json.dumps(metric) + "\n")
        
        summarizer = RunsSummarizer(tmp_path)
        runs = summarizer.scan_runs()
        
        assert len(runs) == 1
        run = runs[0]
        assert run["run_id"] == "funsearch_orlib_small_20260201_144522"
        assert run["dataset"] == "orlib"
        assert run["task"] == "bin_packing"
        assert run["generations_completed"] == 2
        assert run["best_score"] == 62.5
        assert run["avg_score_final"] == 55.3
        assert run["total_candidates"] == 20  # 8 + 12
        assert run["dedup_skipped_total"] == 2
        assert run["timestamp_start"] == "2026-02-01T05:15:16.658254+00:00"
        assert run["timestamp_end"] == "2026-02-01T05:20:30.123456+00:00"
        assert "config_hash" in run
    
    def test_scan_runs_sorts_by_timestamp_newest_first(self, tmp_path: Path) -> None:
        """Test that runs are sorted by timestamp, newest first."""
        # Create two runs with different timestamps
        for run_id, timestamp in [
            ("funsearch_test_20260201_120000", "2026-02-01T12:00:00.000000+00:00"),
            ("funsearch_test_20260201_140000", "2026-02-01T14:00:00.000000+00:00"),
        ]:
            run_dir = tmp_path / run_id
            run_dir.mkdir()
            
            config = {
                "run_id": run_id,
                "seed": 42,
                "max_generations": 5,
                "task_name": "bin_packing",
            }
            with open(run_dir / "config.yaml", "w") as f:
                yaml.dump(config, f)
            
            metrics = [
                {
                    "generation": 0,
                    "timestamp": timestamp,
                    "overall": {"count": 5, "best_score": 50.0, "avg_score": 45.0},
                    "dedup_skipped": 0,
                    "dedup_skipped_total": 0,
                }
            ]
            with open(run_dir / "metrics.jsonl", "w") as f:
                for metric in metrics:
                    f.write(json.dumps(metric) + "\n")
        
        summarizer = RunsSummarizer(tmp_path)
        runs = summarizer.scan_runs()
        
        assert len(runs) == 2
        assert runs[0]["run_id"] == "funsearch_test_20260201_140000"  # Newer first
        assert runs[1]["run_id"] == "funsearch_test_20260201_120000"
    
    def test_scan_runs_handles_corrupted_run(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        """Test that corrupted runs are skipped with a warning."""
        # Create a corrupted run (missing config)
        bad_run_dir = tmp_path / "funsearch_bad_run"
        bad_run_dir.mkdir()
        
        # Create a good run
        good_run_dir = tmp_path / "funsearch_good_run"
        good_run_dir.mkdir()
        
        config = {
            "run_id": "funsearch_good_run",
            "seed": 42,
            "max_generations": 5,
            "task_name": "bin_packing",
        }
        with open(good_run_dir / "config.yaml", "w") as f:
            yaml.dump(config, f)
        
        metrics = [
            {
                "generation": 0,
                "timestamp": "2026-02-01T12:00:00.000000+00:00",
                "overall": {"count": 5, "best_score": 50.0, "avg_score": 45.0},
                "dedup_skipped": 0,
                "dedup_skipped_total": 0,
            }
        ]
        with open(good_run_dir / "metrics.jsonl", "w") as f:
            for metric in metrics:
                f.write(json.dumps(metric) + "\n")
        
        with caplog.at_level(logging.WARNING, logger="experiments.summary"):
            summarizer = RunsSummarizer(tmp_path)
            runs = summarizer.scan_runs()
        
        assert len(runs) == 1
        assert runs[0]["run_id"] == "funsearch_good_run"
        
        assert any("funsearch_bad_run" in record.message for record in caplog.records)
    
    def test_export_csv(self, tmp_path: Path) -> None:
        """Test exporting runs to CSV format."""
        # Create a sample run
        run_dir = tmp_path / "artifacts" / "funsearch_test_run"
        run_dir.mkdir(parents=True)
        
        config = {
            "run_id": "funsearch_test_run",
            "seed": 42,
            "max_generations": 5,
            "task_name": "bin_packing",
        }
        with open(run_dir / "config.yaml", "w") as f:
            yaml.dump(config, f)
        
        metrics = [
            {
                "generation": 0,
                "timestamp": "2026-02-01T12:00:00.000000+00:00",
                "overall": {"count": 10, "best_score": 60.0, "avg_score": 50.0},
                "dedup_skipped": 1,
                "dedup_skipped_total": 1,
            }
        ]
        with open(run_dir / "metrics.jsonl", "w") as f:
            for metric in metrics:
                f.write(json.dumps(metric) + "\n")
        
        summarizer = RunsSummarizer(tmp_path / "artifacts")
        output_path = tmp_path / "runs_summary.csv"
        summarizer.export_csv(output_path)
        
        assert output_path.exists()
        
        # Read and verify CSV content
        with open(output_path, "r") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        assert len(rows) == 1
        row = rows[0]
        assert row["run_id"] == "funsearch_test_run"
        assert row["task"] == "bin_packing"
        assert row["generations_completed"] == "1"
        assert float(row["best_score"]) == 60.0
        assert float(row["avg_score_final"]) == 50.0
        assert int(row["total_candidates"]) == 10
        assert int(row["dedup_skipped_total"]) == 1
    
    def test_export_json(self, tmp_path: Path) -> None:
        """Test exporting runs to JSON format."""
        # Create a sample run
        run_dir = tmp_path / "artifacts" / "funsearch_test_run"
        run_dir.mkdir(parents=True)
        
        config = {
            "run_id": "funsearch_test_run",
            "seed": 42,
            "max_generations": 5,
            "task_name": "bin_packing",
        }
        with open(run_dir / "config.yaml", "w") as f:
            yaml.dump(config, f)
        
        metrics = [
            {
                "generation": 0,
                "timestamp": "2026-02-01T12:00:00.000000+00:00",
                "overall": {"count": 10, "best_score": 60.0, "avg_score": 50.0},
                "dedup_skipped": 1,
                "dedup_skipped_total": 1,
            }
        ]
        with open(run_dir / "metrics.jsonl", "w") as f:
            for metric in metrics:
                f.write(json.dumps(metric) + "\n")
        
        summarizer = RunsSummarizer(tmp_path / "artifacts")
        output_path = tmp_path / "runs_summary.json"
        summarizer.export_json(output_path)
        
        assert output_path.exists()
        
        # Read and verify JSON content
        with open(output_path, "r") as f:
            data = json.load(f)
        
        assert len(data) == 1
        run = data[0]
        assert run["run_id"] == "funsearch_test_run"
        assert run["task"] == "bin_packing"
        assert run["generations_completed"] == 1
        assert run["best_score"] == 60.0
        assert run["avg_score_final"] == 50.0
        assert run["total_candidates"] == 10
        assert run["dedup_skipped_total"] == 1
    
    def test_unique_rate_calculation(self, tmp_path: Path) -> None:
        """Test that unique rate is calculated correctly."""
        run_dir = tmp_path / "funsearch_test_unique"
        run_dir.mkdir()
        
        config = {
            "run_id": "funsearch_test_unique",
            "seed": 42,
            "max_generations": 2,
            "task_name": "bin_packing",
        }
        with open(run_dir / "config.yaml", "w") as f:
            yaml.dump(config, f)
        
        # Total candidates = 20, dedup_skipped = 5, so unique = 15, rate = 75%
        metrics = [
            {
                "generation": 0,
                "timestamp": "2026-02-01T12:00:00.000000+00:00",
                "overall": {"count": 10, "best_score": 60.0, "avg_score": 50.0},
                "dedup_skipped": 2,
                "dedup_skipped_total": 2,
            },
            {
                "generation": 1,
                "timestamp": "2026-02-01T12:05:00.000000+00:00",
                "overall": {"count": 10, "best_score": 65.0, "avg_score": 55.0},
                "dedup_skipped": 3,
                "dedup_skipped_total": 5,
            },
        ]
        with open(run_dir / "metrics.jsonl", "w") as f:
            for metric in metrics:
                f.write(json.dumps(metric) + "\n")
        
        summarizer = RunsSummarizer(tmp_path)
        runs = summarizer.scan_runs()
        
        assert len(runs) == 1
        run = runs[0]
        assert run["total_candidates"] == 20
        assert run["dedup_skipped_total"] == 5
        assert run["unique_rate"] == 0.75  # 15 / 20
