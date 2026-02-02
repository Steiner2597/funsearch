import pytest
from pathlib import Path
from experiments.plotting import PlotGenerator

@pytest.fixture
def sample_metrics():
    return [
        {
            "generation": 0,
            "timestamp": "2026-02-01 10:00:00",
            "islands": {
                "0": {"count": 2, "best_score": 50.0, "avg_score": 40.0},
                "1": {"count": 2, "best_score": 45.0, "avg_score": 35.0}
            },
            "overall": {"count": 4, "best_score": 50.0, "avg_score": 37.5},
            "dedup_skipped": 1,
            "dedup_skipped_total": 1,
            "candidates_generated": 10
        },
        {
            "generation": 1,
            "timestamp": "2026-02-01 10:05:00",
            "islands": {
                "0": {"count": 4, "best_score": 55.0, "avg_score": 45.0},
                "1": {"count": 4, "best_score": 52.0, "avg_score": 42.0}
            },
            "overall": {"count": 8, "best_score": 55.0, "avg_score": 43.5},
            "dedup_skipped": 2,
            "dedup_skipped_total": 3,
            "candidates_generated": 12
        },
        {
            "generation": 2,
            "timestamp": "2026-02-01 10:10:00",
            "islands": {
                "0": {"count": 6, "best_score": 60.0, "avg_score": 50.0},
                "1": {"count": 6, "best_score": 58.0, "avg_score": 48.0}
            },
            "overall": {"count": 12, "best_score": 60.0, "avg_score": 49.0},
            "dedup_skipped": 1,
            "dedup_skipped_total": 4,
            "candidates_generated": 15
        }
    ]

def test_plot_dashboard(sample_metrics, tmp_path):
    pg = PlotGenerator()
    save_path = tmp_path / "dashboard.png"
    pg.plot_dashboard(sample_metrics, save_path)
    assert save_path.exists()

def test_plot_per_island_evolution(sample_metrics, tmp_path):
    pg = PlotGenerator()
    save_path = tmp_path / "islands.png"
    pg.plot_per_island_evolution(sample_metrics, save_path)
    assert save_path.exists()

def test_plot_dedup_stats(sample_metrics, tmp_path):
    pg = PlotGenerator()
    save_path = tmp_path / "dedup.png"
    pg.plot_dedup_stats(sample_metrics, save_path)
    assert save_path.exists()
