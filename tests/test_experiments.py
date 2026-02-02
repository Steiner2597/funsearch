"""Tests for experiment configuration, artifacts, and CLI."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
import yaml

from experiments.artifacts import ArtifactManager
from experiments.config import ExperimentConfig, load_config, save_config
from funsearch_core.schemas import Candidate


class TestExperimentConfig:
    def test_load_config_from_yaml(self, tmp_path: Path) -> None:
        config_path = tmp_path / "test_config.yaml"
        config_data = {
            "run_id": "test_run_001",
            "seed": 42,
            "max_generations": 10,
            "population_size": 20,
            "num_islands": 2,
            "top_k_for_full_eval": 5,
            "task_name": "bin_packing",
            "generator_provider_id": "fake_gen",
            "refiner_provider_id": "fake_ref",
            "evaluator": {"capacity": 100, "seed": 42},
            "llm_providers": [
                {
                    "provider_id": "fake_gen",
                    "provider_type": "fake",
                    "model_name": "fake-model",
                }
            ],
            "artifact_dir": "artifacts",
            "save_interval": 5,
        }
        
        with open(config_path, "w") as f:
            yaml.dump(config_data, f)
        
        config = load_config(config_path)
        
        assert config.run_id == "test_run_001"
        assert config.seed == 42
        assert config.max_generations == 10
        assert config.population_size == 20
        assert config.num_islands == 2
        assert config.task_name == "bin_packing"
        assert config.evaluator["capacity"] == 100
        assert len(config.llm_providers) == 1
        assert config.artifact_dir == "artifacts"
        assert config.save_interval == 5
    
    def test_load_config_missing_file(self) -> None:
        with pytest.raises(FileNotFoundError):
            load_config("nonexistent.yaml")
    
    def test_save_config(self, tmp_path: Path) -> None:
        config = ExperimentConfig(
            run_id="test_save",
            seed=123,
            max_generations=5,
            population_size=10,
            num_islands=1,
            top_k_for_full_eval=3,
            task_name="bin_packing",
            generator_provider_id="gen",
            refiner_provider_id="ref",
        )
        
        config_path = tmp_path / "saved_config.yaml"
        save_config(config, config_path)
        
        assert config_path.exists()
        
        loaded = load_config(config_path)
        assert loaded.run_id == "test_save"
        assert loaded.seed == 123


class TestArtifactManager:
    def test_directory_creation(self, tmp_path: Path) -> None:
        config = ExperimentConfig(
            run_id="test_artifacts",
            seed=42,
            max_generations=10,
            population_size=20,
            num_islands=2,
            top_k_for_full_eval=5,
            task_name="bin_packing",
            generator_provider_id="gen",
            refiner_provider_id="ref",
            artifact_dir=str(tmp_path),
        )
        
        manager = ArtifactManager(config)
        
        assert manager.run_dir.exists()
        assert manager.plots_dir.exists()
        assert manager.run_dir == tmp_path / "test_artifacts"
    
    def test_snapshot_config(self, tmp_path: Path) -> None:
        config = ExperimentConfig(
            run_id="test_snapshot",
            seed=42,
            max_generations=10,
            population_size=20,
            num_islands=2,
            top_k_for_full_eval=5,
            task_name="bin_packing",
            generator_provider_id="gen",
            refiner_provider_id="ref",
            artifact_dir=str(tmp_path),
        )
        
        manager = ArtifactManager(config)
        manager.snapshot_config()
        
        assert manager.config_path.exists()
        
        loaded = load_config(manager.config_path)
        assert loaded.run_id == "test_snapshot"
    
    def test_save_generation_metrics(self, tmp_path: Path) -> None:
        config = ExperimentConfig(
            run_id="test_metrics",
            seed=42,
            max_generations=10,
            population_size=20,
            num_islands=2,
            top_k_for_full_eval=5,
            task_name="bin_packing",
            generator_provider_id="gen",
            refiner_provider_id="ref",
            artifact_dir=str(tmp_path),
        )
        
        manager = ArtifactManager(config)
        
        manager.save_generation_metrics(0, {"best_score": 10.5, "avg_score": 8.2})
        manager.save_generation_metrics(1, {"best_score": 12.3, "avg_score": 9.1})
        
        assert manager.metrics_path.exists()
        
        metrics = manager.load_metrics()
        assert len(metrics) == 2
        assert metrics[0]["generation"] == 0
        assert metrics[0]["best_score"] == 10.5
        assert metrics[1]["generation"] == 1
        assert metrics[1]["best_score"] == 12.3
    
    def test_export_best_candidate(self, tmp_path: Path) -> None:
        config = ExperimentConfig(
            run_id="test_export",
            seed=42,
            max_generations=10,
            population_size=20,
            num_islands=2,
            top_k_for_full_eval=5,
            task_name="bin_packing",
            generator_provider_id="gen",
            refiner_provider_id="ref",
            artifact_dir=str(tmp_path),
        )
        
        manager = ArtifactManager(config)
        
        candidate = Candidate(
            id="cand-1",
            code="def score_bin(item_size, remaining_capacity, bin_index, step) -> float:\n    return float(remaining_capacity)",
            score=15.5,
            signature="abc123",
            generation=5,
            model_id="fake-model",
            eval_metadata={},
        )
        
        manager.export_best_candidate(candidate)
        
        assert manager.best_candidate_path.exists()
        
        with open(manager.best_candidate_path, "r") as f:
            content = f.read()
        
        assert "test_export" in content
        assert "15.5" in content
        assert "def score_bin" in content
    
    def test_get_summary(self, tmp_path: Path) -> None:
        config = ExperimentConfig(
            run_id="test_summary",
            seed=42,
            max_generations=10,
            population_size=20,
            num_islands=2,
            top_k_for_full_eval=5,
            task_name="bin_packing",
            generator_provider_id="gen",
            refiner_provider_id="ref",
            artifact_dir=str(tmp_path),
        )
        
        manager = ArtifactManager(config)
        
        summary = manager.get_summary()
        assert summary["run_id"] == "test_summary"
        assert summary["status"] == "no_data"
        assert summary["generations_completed"] == 0
        
        manager.save_generation_metrics(0, {"best_score": 10.0})
        manager.save_generation_metrics(1, {"best_score": 12.0})
        
        summary = manager.get_summary()
        assert summary["status"] == "in_progress"
        assert summary["generations_completed"] == 2
        assert summary["best_score"] == 12.0


class TestIntegration:
    def test_end_to_end_experiment(self, tmp_path: Path) -> None:
        """Integration test: run 2 generations end-to-end with FakeProvider."""
        config_path = tmp_path / "integration_config.yaml"
        config_data = {
            "run_id": "integration_test",
            "seed": 42,
            "max_generations": 2,
            "population_size": 5,
            "num_islands": 1,
            "top_k_for_full_eval": 2,
            "task_name": "bin_packing",
            "generator_provider_id": "fake_gen",
            "refiner_provider_id": "fake_gen",
            "evaluator": {"capacity": 100, "seed": 42},
            "llm_providers": [
                {
                    "provider_id": "fake_gen",
                    "provider_type": "fake",
                    "model_name": "fake-model",
                }
            ],
            "artifact_dir": str(tmp_path / "artifacts"),
            "save_interval": 1,
        }
        
        with open(config_path, "w") as f:
            yaml.dump(config_data, f)
        
        config = load_config(config_path)
        
        from experiments.runner import ExperimentRunner
        
        runner = ExperimentRunner(config)
        summary = runner.run()
        
        assert summary["run_id"] == "integration_test"
        assert summary["generations_completed"] >= 2
        assert summary["status"] in ["completed", "in_progress"]
        
        artifacts_dir = tmp_path / "artifacts" / "integration_test"
        assert artifacts_dir.exists()
        assert (artifacts_dir / "config.yaml").exists()
        assert (artifacts_dir / "metrics.jsonl").exists()
        assert (artifacts_dir / "candidates.db").exists()
