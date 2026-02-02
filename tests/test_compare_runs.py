"""Tests for run comparison functionality."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from experiments.compare import RunComparator


@pytest.fixture
def temp_artifacts(tmp_path: Path) -> Path:
    """Create a temporary artifacts directory with test runs."""
    artifacts_root = tmp_path / "artifacts"
    artifacts_root.mkdir()
    
    # Create run 1: best_score=10, unique_rate=0.8
    run1_dir = artifacts_root / "run_20240101_120000_abc123"
    run1_dir.mkdir()
    
    config1 = {
        "run_id": "run_20240101_120000_abc123",
        "max_generations": 10,
        "population_size": 50,
        "num_islands": 2,
        "task_name": "binpacking",
        "evaluator": {"type": "orlib", "subset": "small"},
    }
    with open(run1_dir / "config.yaml", "w") as f:
        yaml.dump(config1, f)
    
    metrics1 = [
        {"timestamp": "2024-01-01T12:00:00", "overall": {"best_score": 5, "avg_score": 3, "count": 10}, "dedup": {"skipped_total": 2}},
        {"timestamp": "2024-01-01T12:05:00", "overall": {"best_score": 8, "avg_score": 5, "count": 15}, "dedup": {"skipped_total": 3}},
        {"timestamp": "2024-01-01T12:10:00", "overall": {"best_score": 10, "avg_score": 6, "count": 20}, "dedup": {"skipped_total": 4}},
    ]
    with open(run1_dir / "metrics.jsonl", "w") as f:
        for m in metrics1:
            f.write(json.dumps(m) + "\n")
    
    # Create run 2: best_score=12, unique_rate=0.9
    run2_dir = artifacts_root / "run_20240102_140000_def456"
    run2_dir.mkdir()
    
    config2 = {
        "run_id": "run_20240102_140000_def456",
        "max_generations": 15,
        "population_size": 50,
        "num_islands": 3,
        "task_name": "binpacking",
        "evaluator": {"type": "orlib", "subset": "large"},
    }
    with open(run2_dir / "config.yaml", "w") as f:
        yaml.dump(config2, f)
    
    metrics2 = [
        {"timestamp": "2024-01-02T14:00:00", "overall": {"best_score": 6, "avg_score": 4, "count": 10}, "dedup": {"skipped_total": 1}},
        {"timestamp": "2024-01-02T14:10:00", "overall": {"best_score": 12, "avg_score": 8, "count": 15}, "dedup": {"skipped_total": 1}},
    ]
    with open(run2_dir / "metrics.jsonl", "w") as f:
        for m in metrics2:
            f.write(json.dumps(m) + "\n")
    
    return artifacts_root


def test_comparator_initialization(temp_artifacts: Path) -> None:
    """Test RunComparator initialization."""
    comparator = RunComparator(temp_artifacts)
    assert comparator.artifacts_root == temp_artifacts


def test_compare_two_runs(temp_artifacts: Path) -> None:
    """Test comparing two runs."""
    comparator = RunComparator(temp_artifacts)
    
    run_ids = ["run_20240101_120000_abc123", "run_20240102_140000_def456"]
    comparison = comparator.compare(run_ids)
    
    assert "runs" in comparison
    assert len(comparison["runs"]) == 2
    
    # Check run 1 data
    run1 = comparison["runs"][0]
    assert run1["run_id"] == "run_20240101_120000_abc123"
    assert run1["best_score"] == 10
    assert run1["generations_completed"] == 3
    assert 0.9 <= run1["unique_rate"] <= 0.92
    
    # Check run 2 data
    run2 = comparison["runs"][1]
    assert run2["run_id"] == "run_20240102_140000_def456"
    assert run2["best_score"] == 12
    assert run2["generations_completed"] == 2
    assert run2["unique_rate"] >= 0.9
    
    # Check winner marking
    assert comparison["best_score_winner"] == "run_20240102_140000_def456"


def test_compare_with_missing_run(temp_artifacts: Path) -> None:
    """Test comparing with a non-existent run ID."""
    comparator = RunComparator(temp_artifacts)
    
    run_ids = ["run_20240101_120000_abc123", "nonexistent_run"]
    comparison = comparator.compare(run_ids)
    
    # Should only include the valid run
    assert len(comparison["runs"]) == 1
    assert comparison["runs"][0]["run_id"] == "run_20240101_120000_abc123"
    
    # Should have warnings
    assert "warnings" in comparison
    assert any("nonexistent_run" in w for w in comparison["warnings"])


def test_compare_time_to_best(temp_artifacts: Path) -> None:
    """Test time-to-best calculation."""
    comparator = RunComparator(temp_artifacts)
    
    run_ids = ["run_20240101_120000_abc123", "run_20240102_140000_def456"]
    comparison = comparator.compare(run_ids)
    
    # Run 1 reaches best score at generation 3
    run1 = comparison["runs"][0]
    assert run1["time_to_best"] == 3
    
    # Run 2 reaches best score at generation 2
    run2 = comparison["runs"][1]
    assert run2["time_to_best"] == 2


def test_export_markdown(temp_artifacts: Path, tmp_path: Path) -> None:
    """Test exporting comparison to Markdown."""
    comparator = RunComparator(temp_artifacts)
    
    run_ids = ["run_20240101_120000_abc123", "run_20240102_140000_def456"]
    comparison = comparator.compare(run_ids)
    
    output_path = tmp_path / "compare.md"
    comparator.export_markdown(comparison, output_path)
    
    assert output_path.exists()
    
    content = output_path.read_text(encoding="utf-8")
    assert "# Run Comparison Report" in content
    assert "run_20240101_120000_abc123" in content
    assert "run_20240102_140000_def456" in content
    assert "Best Score" in content
    assert "Unique Rate" in content
    assert "Winner" in content or "🏆" in content


def test_export_csv(temp_artifacts: Path, tmp_path: Path) -> None:
    """Test exporting comparison to CSV."""
    comparator = RunComparator(temp_artifacts)
    
    run_ids = ["run_20240101_120000_abc123", "run_20240102_140000_def456"]
    comparison = comparator.compare(run_ids)
    
    output_path = tmp_path / "compare.csv"
    comparator.export_csv(comparison, output_path)
    
    assert output_path.exists()
    
    content = output_path.read_text()
    assert "run_id" in content
    assert "best_score" in content
    assert "unique_rate" in content
    assert "run_20240101_120000_abc123" in content
    assert "run_20240102_140000_def456" in content


def test_config_differences_highlighted(temp_artifacts: Path) -> None:
    """Test that config differences are highlighted in comparison."""
    comparator = RunComparator(temp_artifacts)
    
    run_ids = ["run_20240101_120000_abc123", "run_20240102_140000_def456"]
    comparison = comparator.compare(run_ids)
    
    assert "config_differences" in comparison
    
    diffs = comparison["config_differences"]
    assert "max_generations" in diffs
    assert diffs["max_generations"] == [10, 15]
    
    assert "num_islands" in diffs
    assert diffs["num_islands"] == [2, 3]


def test_final_diversity(temp_artifacts: Path) -> None:
    """Test final diversity metric calculation."""
    comparator = RunComparator(temp_artifacts)
    
    run_ids = ["run_20240101_120000_abc123", "run_20240102_140000_def456"]
    comparison = comparator.compare(run_ids)
    
    # Both runs should have final_diversity calculated
    for run in comparison["runs"]:
        assert "final_diversity" in run
        assert 0.0 <= run["final_diversity"] <= 1.0
