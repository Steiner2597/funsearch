"""Tests for variant subfolder structure in artifacts."""

import tempfile
from pathlib import Path

import pytest

from experiments.artifacts import ArtifactManager
from experiments.config import ExperimentConfig
from funsearch_core.schemas import Candidate


def _minimal_config(artifact_dir: str, variant: str = "both") -> dict:
    return {
        "run_id": "test_run",
        "artifact_dir": artifact_dir,
        "variant": variant,
        "seed": 42,
        "max_generations": 10,
        "population_size": 20,
        "num_islands": 2,
        "top_k_for_full_eval": 5,
        "generator_provider_id": "test_gen",
        "refiner_provider_id": "test_ref",
        "task_name": "test_task",
    }


def test_variant_a_creates_subfolder():
    """Test that variant='A' creates variant_A subfolder."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = ExperimentConfig.from_dict(_minimal_config(tmpdir, "A"))
        
        artifacts = ArtifactManager(config, variant="A")
        
        # Check that variant_A subfolder is created
        variant_dir = Path(tmpdir) / "test_run" / "variant_A"
        assert variant_dir.exists()
        assert variant_dir.is_dir()
        
        # Check that paths point to variant subfolder
        assert "variant_A" in str(artifacts.config_path)
        assert "variant_A" in str(artifacts.candidates_db_path)
        assert "variant_A" in str(artifacts.metrics_path)
        assert "variant_A" in str(artifacts.best_candidate_path)
        assert "variant_A" in str(artifacts.plots_dir)


def test_variant_b_creates_subfolder():
    """Test that variant='B' creates variant_B subfolder."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = ExperimentConfig.from_dict(_minimal_config(tmpdir, "B"))
        
        artifacts = ArtifactManager(config, variant="B")
        
        # Check that variant_B subfolder is created
        variant_dir = Path(tmpdir) / "test_run" / "variant_B"
        assert variant_dir.exists()
        assert variant_dir.is_dir()
        
        # Check that paths point to variant subfolder
        assert "variant_B" in str(artifacts.config_path)
        assert "variant_B" in str(artifacts.candidates_db_path)


def test_no_variant_preserves_backward_compat():
    """Test that no variant parameter preserves current structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = ExperimentConfig.from_dict(_minimal_config(tmpdir))
        
        artifacts = ArtifactManager(config)
        
        # Check that no variant subfolder is created
        run_dir = Path(tmpdir) / "test_run"
        assert run_dir.exists()
        
        # Check that paths point directly to run_dir (no variant subfolder)
        assert str(artifacts.config_path) == str(run_dir / "config.yaml")
        assert str(artifacts.candidates_db_path) == str(run_dir / "candidates.db")
        assert "variant_A" not in str(artifacts.config_path)
        assert "variant_B" not in str(artifacts.config_path)


def test_variant_artifacts_are_independent():
    """Test that variant A and B artifacts don't interfere."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = ExperimentConfig.from_dict(_minimal_config(tmpdir))
        
        # Create variant A artifacts
        artifacts_a = ArtifactManager(config, variant="A")
        artifacts_a.snapshot_config()
        
        # Create variant B artifacts
        artifacts_b = ArtifactManager(config, variant="B")
        artifacts_b.snapshot_config()
        
        # Check that both config files exist in separate folders
        assert artifacts_a.config_path.exists()
        assert artifacts_b.config_path.exists()
        assert artifacts_a.config_path != artifacts_b.config_path
        
        # Check folder structure
        run_dir = Path(tmpdir) / "test_run"
        assert (run_dir / "variant_A").exists()
        assert (run_dir / "variant_B").exists()
        assert (run_dir / "variant_A" / "config.yaml").exists()
        assert (run_dir / "variant_B" / "config.yaml").exists()


def test_variant_save_generation_metrics():
    """Test that metrics are saved to variant-specific paths."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = ExperimentConfig.from_dict(_minimal_config(tmpdir))
        
        artifacts_a = ArtifactManager(config, variant="A")
        artifacts_b = ArtifactManager(config, variant="B")
        
        # Save metrics for each variant
        artifacts_a.save_generation_metrics(0, {"best_score": 10.0})
        artifacts_b.save_generation_metrics(0, {"best_score": 20.0})
        
        # Load metrics and verify they're separate
        metrics_a = artifacts_a.load_metrics()
        metrics_b = artifacts_b.load_metrics()
        
        assert len(metrics_a) == 1
        assert len(metrics_b) == 1
        assert metrics_a[0]["best_score"] == 10.0
        assert metrics_b[0]["best_score"] == 20.0


def test_variant_export_best_candidate():
    """Test that best candidates are exported to variant-specific paths."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = ExperimentConfig.from_dict(_minimal_config(tmpdir))
        
        artifacts_a = ArtifactManager(config, variant="A")
        artifacts_b = ArtifactManager(config, variant="B")
        
        # Create dummy candidates
        candidate_a = Candidate(
            id="cand_a",
            code="def score_bin(): return 1.0",
            score=10.0,
            signature="sig_a",
            generation=0,
            parent_id=None,
            model_id="test",
            eval_metadata={},
        )
        candidate_b = Candidate(
            id="cand_b",
            code="def score_bin(): return 2.0",
            score=20.0,
            signature="sig_b",
            generation=0,
            parent_id=None,
            model_id="test",
            eval_metadata={},
        )
        
        # Export best candidates
        artifacts_a.export_best_candidate(candidate_a)
        artifacts_b.export_best_candidate(candidate_b)
        
        # Check files exist in correct locations
        assert artifacts_a.best_candidate_path.exists()
        assert artifacts_b.best_candidate_path.exists()
        
        # Verify content is different
        content_a = artifacts_a.best_candidate_path.read_text()
        content_b = artifacts_b.best_candidate_path.read_text()
        
        assert "return 1.0" in content_a
        assert "return 2.0" in content_b
