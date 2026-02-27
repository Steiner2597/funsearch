import pytest
from pathlib import Path
import json
import yaml
from experiments.report import ReportGenerator

@pytest.fixture
def mock_experiment_data(tmp_path):
    metrics_path = tmp_path / "metrics.jsonl"
    plots_dir = tmp_path / "plots"
    plots_dir.mkdir()
    config_path = tmp_path / "config.yaml"

    # Create mock metrics
    metrics = [
        {
            "generation": 0,
            "timestamp": "2026-02-01T10:00:00",
            "islands": {
                "0": {"count": 10, "best_score": 10.0, "avg_score": 8.0},
                "1": {"count": 10, "best_score": 12.0, "avg_score": 9.0}
            },
            "overall": {"count": 20, "best_score": 12.0, "avg_score": 8.5},
            "dedup_skipped": 5,
            "dedup_skipped_total": 5
        },
        {
            "generation": 1,
            "timestamp": "2026-02-01T10:05:00",
            "islands": {
                "0": {"count": 20, "best_score": 15.0, "avg_score": 11.0},
                "1": {"count": 20, "best_score": 14.0, "avg_score": 10.0}
            },
            "overall": {"count": 40, "best_score": 15.0, "avg_score": 10.5},
            "dedup_skipped": 10,
            "dedup_skipped_total": 15,
            "funnel": {
                "generated": 20,
                "dedup_rejected": 4,
                "after_dedup": 16,
                "diversity_rejected": 2,
                "cheap_eval_failed": 1,
                "cheap_eval_passed": 15,
                "full_eval_attempted": 3,
                "full_eval_failed": 0,
                "full_eval_passed": 3,
                "effective_candidate_rate": 0.75
            }
        }
    ]
    with open(metrics_path, "w") as f:
        for m in metrics:
            f.write(json.dumps(m) + "\n")

    # Create mock config
    config = {
        "run_id": "test_run_001",
        "task": "bin_packing",
        "dataset": "orlib_small",
        "llm": {"model": "gpt-3.5-turbo"}
    }
    with open(config_path, "w") as f:
        yaml.dump(config, f)

    # Create a mock plot
    import matplotlib.pyplot as plt
    import numpy as np
    plt.figure()
    plt.plot(np.random.rand(10))
    plt.savefig(plots_dir / "evolution_curve.png")
    plt.close()

    return metrics_path, plots_dir, config

def test_report_generator_markdown(mock_experiment_data, tmp_path):
    metrics_path, plots_dir, config = mock_experiment_data
    report_path = tmp_path / "report.md"
    
    generator = ReportGenerator(metrics_path, plots_dir, config)
    generator.generate_markdown(report_path)
    
    assert report_path.exists()
    content = report_path.read_text()
    assert "# FunSearch Experiment Report" in content
    assert "## Run Summary" in content
    assert "test_run_001" in content
    assert "## Key Performance Indicators" in content
    assert "## Evolution Analysis" in content
    assert "## Per-Island Performance" in content
    assert "## Deduplication Statistics" in content
    assert "## Candidate Flow Funnel" in content
    assert "## Configuration" in content

def test_report_generator_html(mock_experiment_data, tmp_path):
    metrics_path, plots_dir, config = mock_experiment_data
    report_path = tmp_path / "report.html"
    
    generator = ReportGenerator(metrics_path, plots_dir, config)
    generator.generate_html(report_path)
    
    assert report_path.exists()
    content = report_path.read_text()
    assert "<!DOCTYPE html>" in content
    assert "FunSearch Experiment Report" in content
    assert "data:image/png;base64," in content
