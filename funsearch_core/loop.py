from __future__ import annotations

import itertools
import random
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol, TYPE_CHECKING, Literal, cast

from tqdm import tqdm

from .deduplication import FunctionalDeduplicator


def _format_time(seconds: float) -> str:
    """Format seconds into human readable string."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins}m {secs}s"
    else:
        hours = int(seconds // 3600)
        mins = int((seconds % 3600) // 60)
        return f"{hours}h {mins}m"


class GlobalProgressTracker:
    """Track overall experiment progress and estimate total time."""
    
    def __init__(self, max_generations: int, num_islands: int, population_size: int):
        self.max_generations = max_generations
        self.num_islands = num_islands
        self.population_size = population_size
        self.total_candidates = max_generations * num_islands * population_size
        
        self.candidates_completed = 0
        self.start_time: float | None = None
        self.candidate_times: list[float] = []
        self._last_candidate_start: float | None = None
    
    def start(self) -> None:
        self.start_time = time.time()
    
    def candidate_start(self) -> None:
        self._last_candidate_start = time.time()
    
    def candidate_done(self) -> None:
        self.candidates_completed += 1
        if self._last_candidate_start is not None:
            elapsed = time.time() - self._last_candidate_start
            self.candidate_times.append(elapsed)
            # 只保留最近 100 个用于平均
            if len(self.candidate_times) > 100:
                self.candidate_times = self.candidate_times[-100:]
    
    def get_estimate_str(self) -> str:
        """Get estimated total time string."""
        if not self.candidate_times or self.start_time is None:
            return "Estimating..."
        
        avg_time = sum(self.candidate_times) / len(self.candidate_times)
        remaining_candidates = self.total_candidates - self.candidates_completed
        remaining_time = avg_time * remaining_candidates
        
        elapsed = time.time() - self.start_time
        total_estimate = elapsed + remaining_time
        
        return (
            f"Progress: {self.candidates_completed}/{self.total_candidates} candidates | "
            f"Avg: {avg_time:.1f}s/cand | "
            f"ETA: {_format_time(remaining_time)} | "
            f"Total: ~{_format_time(total_estimate)}"
        )
from .diversity import DiversityMaintainer, SignatureCalculator
from .islands import IslandManager
from .population import Population
from .schemas import Candidate, RunConfig
from .selection import SelectionStrategy

if TYPE_CHECKING:
    from store.repository import CandidateStore


class LLMProvider(Protocol):
    provider_id: str

    def generate(self, *, temperature: float, seed: int | None = None) -> str:
        ...

    def mutate(self, *, parent_code: str, temperature: float, seed: int | None = None) -> str:
        ...
    
    def get_metrics(self) -> dict[str, object]:
        ...
    
    def reset_metrics(self) -> None:
        ...


class Evaluator(Protocol):
    def cheap_eval(self, candidate: Candidate) -> object:
        ...

    def full_eval(self, candidate: Candidate) -> object:
        ...


@dataclass(frozen=True)
class EvaluationOutcome:
    candidate_id: str
    fidelity: Literal["cheap", "full"]
    score: float | None
    runtime_ms: float | None
    error_type: str | None
    metadata: dict[str, object]


def _score_key(candidate: Candidate) -> float:
    return candidate.score if candidate.score is not None else float("-inf")


def _coerce_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _coerce_str(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)


class FunSearchLoop:
    """Main evolutionary loop orchestrating generation, evaluation, and selection.
    
    Manages islands with separate populations, handles LLM-based candidate generation
    and mutation, applies multi-fidelity evaluation (cheap then full on top-k),
    and tracks statistics per generation. Supports deduplication and diversity.
    """
    
    def __init__(
        self,
        config: RunConfig,
        generator: LLMProvider,
        refiner: LLMProvider,
        evaluator: Evaluator,
        signature_calculator: SignatureCalculator,
        selection_strategy: SelectionStrategy,
        diversity_maintainer: DiversityMaintainer | None = None,
        deduplicator: FunctionalDeduplicator | None = None,
        store: CandidateStore | None = None,
        island_manager: IslandManager | None = None,
        island_parameters: list[dict[str, object]] | None = None,
        rng: random.Random | None = None,
        fresh_fraction: float = 0.1,
        default_temperature: float = 1.0,
        migration_interval: int = 0,
        migration_size: int = 1,
    ) -> None:
        if fresh_fraction < 0 or fresh_fraction > 1:
            raise ValueError("fresh_fraction must be between 0 and 1")
        self.config: RunConfig = config
        self.generator: LLMProvider = generator
        self.refiner: LLMProvider = refiner
        self.evaluator: Evaluator = evaluator
        self.signature_calculator: SignatureCalculator = signature_calculator
        self.selection_strategy: SelectionStrategy = selection_strategy
        self.diversity_maintainer: DiversityMaintainer | None = diversity_maintainer
        self.deduplicator: FunctionalDeduplicator | None = deduplicator
        self.store: CandidateStore | None = store
        self.fresh_fraction: float = fresh_fraction
        self.default_temperature: float = default_temperature
        self.migration_interval: int = migration_interval
        self.migration_size: int = migration_size
        self.rng: random.Random = rng or random.Random(config.seed)
        self._candidate_counter: itertools.count[int] = itertools.count()
        self.generation: int = 0
        self.stats_history: list[dict[str, object]] = []
        self._dedup_skipped: int = 0  # Track skipped duplicates

        if island_manager is not None:
            self.islands: IslandManager = island_manager
        else:
            def _factory() -> Population:
                return Population(
                    max_size=config.population_size,
                    diversity_maintainer=self.diversity_maintainer,
                )

            self.islands = IslandManager(
                num_islands=config.num_islands,
                population_factory=_factory,
                island_parameters=island_parameters,
            )

    def run(self) -> list[dict[str, object]]:
        remaining = max(self.config.max_generations - self.generation, 0)
        return self.run_generations(remaining)

    def run_generations(self, num_generations: int) -> list[dict[str, object]]:
        if num_generations < 0:
            raise ValueError("num_generations must be non-negative")
        stats: list[dict[str, object]] = []
        for _ in range(num_generations):
            stats.append(self.run_generation())
        return stats

    def run_generation(self) -> dict[str, object]:
        generation_index = self.generation
        gen_dedup_skipped = 0
        
        if hasattr(self.generator, 'reset_metrics'):
            self.generator.reset_metrics()
        if hasattr(self.refiner, 'reset_metrics'):
            self.refiner.reset_metrics()
        
        # 创建或更新全局进度跟踪器
        if not hasattr(self, '_global_tracker'):
            self._global_tracker = GlobalProgressTracker(
                self.config.max_generations,
                len(self.islands.islands),
                self.config.population_size
            )
            self._global_tracker.start()
        
        # 显示全局进度信息
        tqdm.write(f"\n📊 {self._global_tracker.get_estimate_str()}")
        
        # 显示岛屿处理进度
        island_pbar = tqdm(
            enumerate(self.islands.islands),
            total=len(self.islands.islands),
            desc=f"  Gen {generation_index+1} Islands",
            leave=False,
            ncols=80,
            bar_format="{desc}: {n_fmt}/{total_fmt} |{bar}| {elapsed}<{remaining}"
        )
        
        for island_index, island in island_pbar:
            island_pbar.set_description(f"  Gen {generation_index+1} Island {island_index+1}")
            new_candidates = self._generate_candidates_for_island(
                island_index=island_index,
                population=island.population,
            )
            
            # Sample-efficient: Skip evaluation for functionally duplicate candidates
            if self.deduplicator:
                unique_candidates = []
                for candidate in new_candidates:
                    is_dup, _ = self.deduplicator.is_duplicate(candidate.code)
                    if is_dup:
                        # Mark as duplicate, skip evaluation
                        candidate.eval_metadata["skipped_duplicate"] = True
                        candidate.score = None
                        gen_dedup_skipped += 1
                    else:
                        unique_candidates.append(candidate)
                candidates_to_eval = unique_candidates
            else:
                candidates_to_eval = new_candidates
            
            # Only evaluate non-duplicate candidates
            _ = self._evaluate_candidates(candidates_to_eval, fidelity="cheap")
            top_candidates = self._select_top_k(
                candidates_to_eval,
                self.config.top_k_for_full_eval,
            )
            _ = self._evaluate_candidates(top_candidates, fidelity="full")
            
            # Add all candidates to population (including duplicates for tracking)
            for candidate in new_candidates:
                _ = island.population.add_candidate(candidate)

        if self.migration_interval > 0 and (generation_index + 1) % self.migration_interval == 0:
            _ = self.islands.migrate(self.migration_size)

        self._dedup_skipped += gen_dedup_skipped
        stats = self._collect_stats(generation_index)
        
        stats["dedup"]["skipped"] = gen_dedup_skipped
        stats["dedup"]["skipped_total"] = self._dedup_skipped
        
        if hasattr(self.generator, 'get_metrics') and hasattr(self.refiner, 'get_metrics'):
            generator_metrics = self.generator.get_metrics()
            refiner_metrics = self.refiner.get_metrics()
            
            llm_metrics = {
                "calls": generator_metrics["calls"] + refiner_metrics["calls"],
                "total_latency_ms": generator_metrics["total_latency_ms"] + refiner_metrics["total_latency_ms"],
                "total_input_tokens": generator_metrics["total_input_tokens"] + refiner_metrics["total_input_tokens"],
                "total_output_tokens": generator_metrics["total_output_tokens"] + refiner_metrics["total_output_tokens"],
                "cache_hits": generator_metrics["cache_hits"] + refiner_metrics["cache_hits"],
                "cache_misses": generator_metrics["cache_misses"] + refiner_metrics["cache_misses"],
                "errors": generator_metrics["errors"] + refiner_metrics["errors"],
            }
            
            if llm_metrics["calls"] > 0:
                llm_metrics["avg_latency_ms"] = llm_metrics["total_latency_ms"] / llm_metrics["calls"]
                stats["timing"]["llm_s"] = llm_metrics["total_latency_ms"] / 1000.0
            else:
                llm_metrics["avg_latency_ms"] = 0.0
                stats["timing"]["llm_s"] = 0.0
            
            stats["llm"] = llm_metrics
        
        self.stats_history.append(stats)
        self.generation += 1
        return stats

    def _generate_candidates_for_island(
        self,
        island_index: int,
        population: Population,
    ) -> list[Candidate]:
        num_candidates = self.config.population_size
        fresh_count = self._compute_fresh_count(num_candidates)
        temperature = self._get_temperature(island_index)
        candidates: list[Candidate] = []
        
        # 候选生成进度条
        cand_pbar = tqdm(
            range(num_candidates),
            desc=f"    Candidates",
            leave=False,
            ncols=80,
            bar_format="{desc}: {n_fmt}/{total_fmt} |{bar}| {elapsed}<{remaining}"
        )
        
        for idx in cand_pbar:
            # 记录候选开始时间
            if hasattr(self, '_global_tracker'):
                self._global_tracker.candidate_start()
            
            if idx < fresh_count or not population.candidates:
                code = self.generator.generate(
                    temperature=temperature,
                    seed=self._next_seed(),
                )
                parent_id = None
                model_id = getattr(self.generator, "provider_id", "generator")
            else:
                parent = self.selection_strategy.select(population.candidates)
                code = self.refiner.mutate(
                    parent_code=parent.code,
                    temperature=temperature,
                    seed=self._next_seed(),
                )
                parent_id = parent.id
                model_id = getattr(self.refiner, "provider_id", "refiner")

            signature_result = self.signature_calculator.calculate(code)
            candidate = Candidate(
                id=self._next_candidate_id(),
                code=code,
                score=None,
                signature=signature_result.signature,
                parent_id=parent_id,
                generation=self.generation,
                runtime_ms=None,
                error_type=None,
                model_id=model_id,
                eval_metadata={"signature_vector": signature_result.vector},
            )
            self._store_candidate(candidate)
            candidates.append(candidate)
            
            # 更新全局进度
            if hasattr(self, '_global_tracker'):
                self._global_tracker.candidate_done()
        
        return candidates

    def _evaluate_candidates(
        self,
        candidates: Sequence[Candidate],
        fidelity: Literal["cheap", "full"],
    ) -> list[EvaluationOutcome]:
        outcomes: list[EvaluationOutcome] = []
        for candidate in candidates:
            if fidelity == "cheap":
                result = self.evaluator.cheap_eval(candidate)
            else:
                result = self.evaluator.full_eval(candidate)
            outcome = self._normalize_eval_result(candidate.id, fidelity, result)
            self._apply_evaluation(candidate, outcome)
            self._record_evaluation(outcome)
            outcomes.append(outcome)
        return outcomes

    def _normalize_eval_result(
        self,
        candidate_id: str,
        fidelity: Literal["cheap", "full"],
        result: object,
    ) -> EvaluationOutcome:
        if isinstance(result, Mapping):
            typed_result: dict[str, object] = dict(cast(Mapping[str, object], result))
            score = _coerce_float(typed_result.get("score"))
            runtime_ms = _coerce_float(typed_result.get("runtime_ms"))
            error_type = _coerce_str(typed_result.get("error_type"))
            raw_details = typed_result.get("metadata")
            details_map = (
                dict(cast(Mapping[str, object], raw_details))
                if isinstance(raw_details, Mapping)
                else {}
            )
            return EvaluationOutcome(
                candidate_id,
                fidelity,
                score,
                runtime_ms,
                error_type,
                details_map,
            )

        score = _coerce_float(getattr(result, "score", None))
        runtime_ms = _coerce_float(getattr(result, "runtime_ms", None))
        error_type = _coerce_str(getattr(result, "error_type", None))
        details_attr = getattr(result, "metadata", None)
        if isinstance(details_attr, Mapping):
            details_obj = dict(cast(Mapping[str, object], details_attr))
        else:
            details_obj = {}
            for key in ("n_instances", "instance_bins", "baseline_score", "baseline_bins"):
                if hasattr(result, key):
                    details_obj[key] = getattr(result, key)
        return EvaluationOutcome(
            candidate_id,
            fidelity,
            score,
            runtime_ms,
            error_type,
            details_obj,
        )

    def _apply_evaluation(self, candidate: Candidate, outcome: EvaluationOutcome) -> None:
        if outcome.score is not None:
            candidate.score = outcome.score
        candidate.runtime_ms = outcome.runtime_ms
        candidate.error_type = outcome.error_type
        candidate.eval_metadata[f"{outcome.fidelity}_metadata"] = outcome.metadata
        if outcome.score is not None:
            candidate.eval_metadata[f"{outcome.fidelity}_score"] = outcome.score
        
        # Update candidate status in database
        if self.store is not None and outcome.fidelity == "full":
            status = "evaluated" if outcome.score is not None else "failed"
            self.store.update_candidate_status(candidate.id, status)

    def _record_evaluation(self, outcome: EvaluationOutcome) -> None:
        if self.store is None:
            return
        self.store.record_evaluation(
            {
                "candidate_id": outcome.candidate_id,
                "fidelity": outcome.fidelity,
                "score": outcome.score,
                "runtime_ms": outcome.runtime_ms,
                "error_type": outcome.error_type,
                "metadata": outcome.metadata,
            }
        )

    def _store_candidate(self, candidate: Candidate) -> None:
        if self.store is None:
            return
        from store.repository import Candidate as StoreCandidate

        store_candidate = StoreCandidate(
            id=candidate.id,
            run_id=self.config.run_id,
            code=candidate.code,
            code_hash="",
            parent_id=candidate.parent_id,
            generation=candidate.generation,
            model_id=candidate.model_id,
            signature=candidate.signature,
            status="pending",
        )
        _ = self.store.save_candidate(store_candidate)

    def _select_top_k(self, candidates: Sequence[Candidate], k: int) -> list[Candidate]:
        if k <= 0:
            return []
        ordered = sorted(candidates, key=_score_key, reverse=True)
        return ordered[: min(k, len(ordered))]

    def _collect_stats(self, generation_index: int) -> dict[str, object]:
        from datetime import datetime, timezone
        
        island_stats: dict[int, dict[str, float | int | None]] = {}
        overall_scores: list[float] = []
        overall_count = 0
        failure_counts: dict[str, int] = {}
        
        for idx, island in enumerate(self.islands.islands):
            stats = island.population.get_generation_stats()
            island_stats[idx] = stats
            overall_count += len(island.population)
            
            for candidate in island.population.candidates:
                if candidate.score is not None:
                    overall_scores.append(candidate.score)
                
                if hasattr(candidate, 'error_type') and candidate.error_type:
                    error_type = candidate.error_type
                    failure_counts[error_type] = failure_counts.get(error_type, 0) + 1
        
        overall = {
            "count": overall_count,
            "best_score": max(overall_scores) if overall_scores else None,
            "avg_score": sum(overall_scores) / len(overall_scores) if overall_scores else None,
        }
        
        return {
            "generation": generation_index,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "islands": island_stats,
            "overall": overall,
            "variant": None,
            "dedup": {
                "skipped": 0,
                "skipped_total": 0,
            },
            "timing": {},
            "failures": failure_counts,
        }

    def _compute_fresh_count(self, num_candidates: int) -> int:
        if num_candidates <= 0:
            return 0
        if self.fresh_fraction == 0:
            return 0
        fresh_count = int(round(num_candidates * self.fresh_fraction))
        if fresh_count <= 0:
            fresh_count = 1
        return min(fresh_count, num_candidates)

    def _get_temperature(self, island_index: int) -> float:
        params: dict[str, object] = self.islands.get_parameters(island_index)
        temperature = params.get("temperature", self.default_temperature)
        coerced = _coerce_float(temperature)
        return coerced if coerced is not None else self.default_temperature

    def _next_candidate_id(self) -> str:
        return f"cand-{next(self._candidate_counter)}"

    def _next_seed(self) -> int:
        return self.rng.randint(0, 2_147_483_647)
