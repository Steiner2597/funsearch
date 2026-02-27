from __future__ import annotations

import hashlib
import random
from pathlib import Path

from funsearch_core.diversity import DiversityMaintainer, SignatureCalculator
from funsearch_core.loop import FunSearchLoop
from funsearch_core.population import Population
from funsearch_core.schemas import Candidate, RunConfig
from funsearch_core.selection import TournamentSelection
from store.repository import CandidateStore


def _make_candidate(candidate_id: str, score: float | None, signature: str) -> Candidate:
    return Candidate(
        id=candidate_id,
        code="def score_bin(item_size, remaining_capacity, bin_index, step):\n    return 1.0",
        score=score,
        signature=signature,
        parent_id=None,
        generation=0,
        runtime_ms=None,
        error_type=None,
        model_id="model-x",
        eval_metadata={},
    )


def _probe_runner(code: str, seed: int) -> float:
    digest = hashlib.sha256(f"{seed}:{code}".encode("utf-8")).hexdigest()
    return float(int(digest[:8], 16) % 100)


class FakeProvider:
    def __init__(self, provider_id: str) -> None:
        self.provider_id: str = provider_id
        self.counter: int = 0

    def generate(self, *, temperature: float, seed: int | None = None) -> str:
        _ = (temperature, seed)
        self.counter += 1
        return (
            "def score_bin(item_size, remaining_capacity, bin_index, step):\n"
            f"    return {self.counter}.0\n"
        )

    def mutate(self, *, parent_code: str, temperature: float, seed: int | None = None) -> str:
        _ = (temperature, seed)
        self.counter += 1
        return parent_code + f"\n# mutation {self.counter}\n"


class FakeEvaluator:
    def __init__(self) -> None:
        self.cheap_calls: list[str] = []
        self.full_calls: list[str] = []

    def cheap_eval(self, candidate: Candidate) -> dict[str, object]:
        self.cheap_calls.append(candidate.id)
        score = float(int(candidate.id.rsplit("-", 1)[-1]))
        return {"score": score, "runtime_ms": 1.0, "metadata": {"phase": "cheap"}}

    def full_eval(self, candidate: Candidate) -> dict[str, object]:
        self.full_calls.append(candidate.id)
        score = float(int(candidate.id.rsplit("-", 1)[-1])) + 0.5
        return {"score": score, "runtime_ms": 2.0, "metadata": {"phase": "full"}}


def test_population_top_k() -> None:
    population = Population(max_size=5)
    assert population.add_candidate(_make_candidate("cand-1", 1.0, "sig-1")) is True
    assert population.add_candidate(_make_candidate("cand-2", 2.0, "sig-2")) is True
    assert population.add_candidate(_make_candidate("cand-3", 3.0, "sig-3")) is True

    top_two = population.get_top_k(2)
    assert [candidate.id for candidate in top_two] == ["cand-3", "cand-2"]


def test_population_rejects_duplicate_signature() -> None:
    population = Population(max_size=3)
    assert population.add_candidate(_make_candidate("cand-a", 1.0, "sig-dup")) is True
    assert population.add_candidate(_make_candidate("cand-b", 2.0, "sig-dup")) is False


def test_multifidelity_routes_top_k_only() -> None:
    config = RunConfig(
        run_id="run-multi",
        seed=1,
        max_generations=1,
        population_size=10,
        num_islands=1,
        top_k_for_full_eval=3,
        generator_provider_id="gen",
        refiner_provider_id="ref",
        task_name="test",
    )
    generator = FakeProvider("gen")
    refiner = FakeProvider("ref")
    evaluator = FakeEvaluator()
    signature_calculator = SignatureCalculator(_probe_runner)
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
    )

    _ = loop.run_generations(1)

    assert len(evaluator.cheap_calls) == 10
    assert len(evaluator.full_calls) == 3
    assert sorted(evaluator.full_calls) == ["cand-7", "cand-8", "cand-9"]


def test_funsearch_loop_runs_generations_and_stores(tmp_path: Path) -> None:
    config = RunConfig(
        run_id="run-int",
        seed=5,
        max_generations=3,
        population_size=6,
        num_islands=1,
        top_k_for_full_eval=2,
        generator_provider_id="gen",
        refiner_provider_id="ref",
        task_name="test",
    )
    store = CandidateStore(
        run_id=config.run_id,
        config=config.to_dict(),
        seed=config.seed,
        base_dir=tmp_path,
    )
    generator = FakeProvider("gen")
    refiner = FakeProvider("ref")
    evaluator = FakeEvaluator()
    signature_calculator = SignatureCalculator(_probe_runner)
    selection = TournamentSelection(tournament_size=2, rng=random.Random(1))
    diversity = DiversityMaintainer(min_distance=0.0)

    loop = FunSearchLoop(
        config=config,
        generator=generator,
        refiner=refiner,
        evaluator=evaluator,
        signature_calculator=signature_calculator,
        selection_strategy=selection,
        diversity_maintainer=diversity,
        store=store,
        rng=random.Random(1),
    )

    _ = loop.run_generations(3)

    assert loop.generation == 3
    assert len(loop.stats_history) == 3
    assert all("islands" in stats for stats in loop.stats_history)
    stats = store.get_generation_stats(config.run_id, 0)
    total = stats["total"]
    assert isinstance(total, int)
    assert total > 0


def test_funsearch_loop_emits_funnel_and_timing_metrics() -> None:
    config = RunConfig(
        run_id="run-p2-metrics",
        seed=11,
        max_generations=1,
        population_size=8,
        num_islands=1,
        top_k_for_full_eval=2,
        generator_provider_id="gen",
        refiner_provider_id="ref",
        task_name="test",
    )
    generator = FakeProvider("gen")
    refiner = FakeProvider("ref")
    evaluator = FakeEvaluator()
    signature_calculator = SignatureCalculator(_probe_runner)
    selection = TournamentSelection(tournament_size=2, rng=random.Random(11))
    diversity = DiversityMaintainer(min_distance=0.0)

    loop = FunSearchLoop(
        config=config,
        generator=generator,
        refiner=refiner,
        evaluator=evaluator,
        signature_calculator=signature_calculator,
        selection_strategy=selection,
        diversity_maintainer=diversity,
        rng=random.Random(11),
    )

    stats = loop.run_generation()

    assert "funnel" in stats
    funnel = stats["funnel"]
    assert isinstance(funnel, dict)
    assert funnel["generated"] == config.population_size
    assert funnel["after_dedup"] == funnel["generated"] - funnel["dedup_rejected"]
    assert 0.0 <= stats["effective_candidate_rate"] <= 1.0

    timing = stats["timing"]
    assert "eval_ms_total" in timing
    assert "eval_s_total" in timing
    assert "avg_eval_ms_per_outcome" in timing
    assert isinstance(timing["eval_ms_total"], float)
    assert timing["eval_ms_total"] >= 0.0
