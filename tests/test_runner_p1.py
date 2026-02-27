from __future__ import annotations

import random

from experiments.config import ExperimentConfig
from experiments.runner import ExperimentRunner
from funsearch_core.diversity import DiversityMaintainer, SignatureCalculator
from funsearch_core.loop import FunSearchLoop
from funsearch_core.schemas import RunConfig
from funsearch_core.selection import TournamentSelection


class _FakeProvider:
    def __init__(self, provider_id: str) -> None:
        self.provider_id = provider_id

    def generate(self, *, temperature: float, seed: int | None = None) -> str:
        _ = (temperature, seed)
        return "def score_bin(item_size, remaining_capacity, bin_index, step):\n    return 1.0\n"

    def mutate(self, *, parent_code: str, temperature: float, seed: int | None = None) -> str:
        _ = (temperature, seed)
        return parent_code


class _FakeEvaluator:
    def __init__(self) -> None:
        self.cheap_calls = 0
        self.full_calls = 0

    def cheap_eval(self, candidate):
        self.cheap_calls += 1
        return {"score": 1.0, "runtime_ms": 1.0, "metadata": {}}

    def full_eval(self, candidate):
        self.full_calls += 1
        return {"score": 1.5, "runtime_ms": 2.0, "metadata": {}}


def _runner_config() -> ExperimentConfig:
    return ExperimentConfig.from_dict(
        {
            "run_id": "p1_runner_test",
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
                "use_sandbox": False,
                "score_mode": "gap_to_lb",
                "full_eval_every_n_generations": 3,
                "probe_mode": "orlib",
            },
        }
    )


def test_runner_p1_passes_score_mode_and_full_eval_cadence() -> None:
    config = _runner_config()
    runner = ExperimentRunner(config)

    evaluator = runner._initialize_evaluator()
    assert evaluator.base_evaluator.score_mode == "gap_to_lb"

    providers = runner._initialize_providers()
    loop = runner._initialize_loop(providers, evaluator=evaluator, store=None)
    assert loop.full_eval_every_n_generations == 3


def test_funsearch_loop_full_eval_cadence() -> None:
    config = RunConfig(
        run_id="p1_loop_test",
        seed=1,
        max_generations=2,
        population_size=4,
        num_islands=1,
        top_k_for_full_eval=2,
        generator_provider_id="gen",
        refiner_provider_id="ref",
        task_name="test",
    )
    generator = _FakeProvider("gen")
    refiner = _FakeProvider("ref")
    evaluator = _FakeEvaluator()
    signature_calculator = SignatureCalculator(lambda code, seed: float(seed + len(code)))
    selection = TournamentSelection(tournament_size=2, rng=random.Random(0))
    diversity = DiversityMaintainer(min_distance=0.0)

    loop = FunSearchLoop(
        config=config,
        generator=generator,
        refiner=refiner,
        evaluator=evaluator,
        signature_calculator=signature_calculator,
        selection_strategy=selection,
        diversity_maintainer=diversity,
        rng=random.Random(0),
        full_eval_every_n_generations=2,
    )

    loop.run_generations(2)

    assert evaluator.cheap_calls == 8
    assert evaluator.full_calls == 2
