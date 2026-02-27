from __future__ import annotations

from llm.prompts import NoveltyPromptTemplate

from experiments.config import ExperimentConfig
from experiments.runner import ExperimentRunner


def _base_config(variant: str | None = None, enable_diversity: bool = True) -> ExperimentConfig:
    payload: dict[str, object] = {
        "run_id": "p0_runner_test",
        "seed": 42,
        "max_generations": 1,
        "population_size": 2,
        "num_islands": 1,
        "top_k_for_full_eval": 1,
        "task_name": "bin_packing",
        "generator_provider_id": "fake_provider",
        "refiner_provider_id": "fake_provider",
        "llm_providers": [
            {
                "provider_id": "fake_provider",
                "provider_type": "fake",
                "model_name": "fake-model",
            }
        ],
        "evaluator": {
            "type": "random",
            "size": "small",
            "capacity": 100,
            "seed": 42,
            "enable_diversity": enable_diversity,
        },
    }
    if variant is not None:
        payload["variant"] = variant
    return ExperimentConfig.from_dict(payload)


def test_runner_accepts_lowercase_variant_b_for_prompt_and_dedup() -> None:
    config = _base_config(variant="b")
    runner = ExperimentRunner(config)

    providers = runner._initialize_providers()
    adapter = providers[config.generator_provider_id]
    assert isinstance(adapter.prompt_template, NoveltyPromptTemplate)

    loop = runner._initialize_loop(providers, evaluator=object(), store=None)
    assert loop.deduplicator is not None
    assert loop.deduplicator._probe_seeds == [0, 1, 2, 3, 4]


def test_runner_disables_diversity_when_configured() -> None:
    config = _base_config(variant="none", enable_diversity=False)
    runner = ExperimentRunner(config)

    providers = runner._initialize_providers()
    loop = runner._initialize_loop(providers, evaluator=object(), store=None)

    assert loop.diversity_maintainer is None


def test_runner_expands_lowercase_both_variants(monkeypatch) -> None:
    config = _base_config(variant="both")
    runner = ExperimentRunner(config)

    calls: list[str | None] = []

    def _fake_run_single_variant(variant: str | None):
        calls.append(variant)
        return {"status": "completed", "run_id": "p0_runner_test"}

    monkeypatch.setattr(runner, "_run_single_variant", _fake_run_single_variant)

    summary = runner.run()

    assert calls == ["A", "B"]
    assert "variant_A" in summary
    assert "variant_B" in summary
