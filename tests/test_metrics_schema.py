"""Tests for extended metrics schema structure."""

import pytest


def test_extended_metrics_schema_structure():
    from funsearch_core.loop import FunSearchLoop
    from funsearch_core.schemas import RunConfig
    from funsearch_core.selection import TournamentSelection
    from evaluator.bin_packing import BinPackingEvaluator
    from llm.providers import FakeProvider
    import random
    
    config = RunConfig(
        run_id="test_schema",
        max_generations=1,
        population_size=2,
        num_islands=1,
        seed=42,
        top_k_for_full_eval=1,
        generator_provider_id="fake",
        refiner_provider_id="fake",
        task_name="test",
    )
    
    evaluator = BinPackingEvaluator(seed=42)
    generator = FakeProvider(provider_id="fake")
    refiner = FakeProvider(provider_id="fake")
    
    loop = FunSearchLoop(
        config=config,
        generator=generator,
        refiner=refiner,
        evaluator=evaluator,
        signature_calculator=evaluator,
        selection_strategy=TournamentSelection(tournament_size=2),
        rng=random.Random(42),
    )
    
    stats = loop._collect_stats(generation_index=0)
    
    assert "generation" in stats
    assert "islands" in stats
    assert "overall" in stats
    
    assert "variant" in stats
    assert stats["variant"] in ["A", "B", None]
    
    assert "dedup" in stats
    dedup = stats["dedup"]
    assert isinstance(dedup, dict)
    assert "skipped" in dedup
    assert "skipped_total" in dedup
    assert isinstance(dedup["skipped"], int)
    assert isinstance(dedup["skipped_total"], int)
    if "breakdown" in dedup:
        assert isinstance(dedup["breakdown"], dict)
    
    assert "timing" in stats
    timing = stats["timing"]
    assert isinstance(timing, dict)
    for field in ["generation_s", "llm_s", "eval_s"]:
        if field in timing:
            assert isinstance(timing[field], (int, float)) or timing[field] is None
    
    assert "failures" in stats
    failures = stats["failures"]
    assert isinstance(failures, dict)
    for failure_type, count in failures.items():
        assert isinstance(failure_type, str)
        assert isinstance(count, int)


def test_backward_compatibility_with_old_metrics():
    """Test that old metrics format can still be loaded.
    
    This ensures we don't break existing metrics files that don't have
    the new fields (variant, dedup object, timing, failures).
    """
    from experiments.artifacts import ArtifactManager
    from experiments.config import ExperimentConfig
    import tempfile
    import json
    from pathlib import Path
    
    # Create temporary directory for test artifacts
    with tempfile.TemporaryDirectory() as tmpdir:
        config = ExperimentConfig(
            run_id="test_backward_compat",
            seed=42,
            max_generations=1,
            population_size=2,
            num_islands=1,
            top_k_for_full_eval=1,
            generator_provider_id="fake",
            refiner_provider_id="fake",
            task_name="test",
            artifact_dir=tmpdir,
        )
        
        artifact_manager = ArtifactManager(config)
        
        # Write old-format metric (without new fields)
        old_metric = {
            "generation": 0,
            "timestamp": "2024-01-01T00:00:00Z",
            "islands": {0: {"count": 10, "best_score": -5.0}},
            "overall": {"count": 10, "best_score": -5.0, "avg_score": -7.0},
        }
        
        with open(artifact_manager.metrics_path, "w") as f:
            f.write(json.dumps(old_metric) + "\n")
        
        # Should be able to load old format
        metrics = artifact_manager.load_metrics()
        assert len(metrics) == 1
        assert metrics[0]["generation"] == 0
        assert "overall" in metrics[0]


def test_save_generation_metrics_with_extended_schema():
    """Test that save_generation_metrics() handles extended schema correctly."""
    from experiments.artifacts import ArtifactManager
    from experiments.config import ExperimentConfig
    import tempfile
    import json
    
    with tempfile.TemporaryDirectory() as tmpdir:
        config = ExperimentConfig(
            run_id="test_extended_save",
            seed=42,
            max_generations=1,
            population_size=2,
            num_islands=1,
            top_k_for_full_eval=1,
            generator_provider_id="fake",
            refiner_provider_id="fake",
            task_name="test",
            artifact_dir=tmpdir,
        )
        
        artifact_manager = ArtifactManager(config)
        
        # Save extended metrics
        extended_stats = {
            "islands": {0: {"count": 10, "best_score": -5.0}},
            "overall": {"count": 10, "best_score": -5.0, "avg_score": -7.0},
            "variant": "A",
            "dedup": {"skipped": 3, "skipped_total": 15, "breakdown": {"functional_duplicate": 3}},
            "timing": {"generation_s": 12.5, "llm_s": 8.2, "eval_s": 4.3},
            "failures": {"syntax_error": 2, "timeout": 1},
        }
        
        artifact_manager.save_generation_metrics(generation=0, stats=extended_stats)
        
        # Load and verify
        metrics = artifact_manager.load_metrics()
        assert len(metrics) == 1
        
        saved = metrics[0]
        assert saved["generation"] == 0
        assert "timestamp" in saved
        assert saved["variant"] == "A"
        assert saved["dedup"]["skipped"] == 3
        assert saved["dedup"]["skipped_total"] == 15
        assert saved["timing"]["generation_s"] == 12.5
        assert saved["failures"]["syntax_error"] == 2
