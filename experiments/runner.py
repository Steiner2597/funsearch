"""Experiment runner orchestrating all components."""

from __future__ import annotations

import re
import signal
import time
from typing import Any

from tqdm import tqdm

from funsearch_core.deduplication import FunctionalDeduplicator, create_binpacking_probe_runner
from funsearch_core.diversity import DiversityMaintainer, SignatureCalculator
from funsearch_core.loop import FunSearchLoop
from funsearch_core.schemas import LLMProviderConfig
from funsearch_core.selection import TournamentSelection
from llm.base import BaseLLMProvider, LLMResponse
from llm.prompts import PromptTemplate, get_prompt_template
from llm.providers import create_provider
from store.repository import CandidateStore
from sandbox.executor import SandboxExecutor, ExecutionResult, BatchExecutionResult

from experiments.artifacts import ArtifactManager
from experiments.config import ExperimentConfig


# Global sandbox executor (shared for efficiency)
_sandbox_executor: SandboxExecutor | None = None
_sandbox_memory_limit: int = 256


def get_sandbox_executor(memory_limit_mb: int = 256) -> SandboxExecutor:
    """Get or create the global sandbox executor."""
    global _sandbox_executor, _sandbox_memory_limit
    if _sandbox_executor is None or _sandbox_memory_limit != memory_limit_mb:
        _sandbox_executor = SandboxExecutor(memory_limit_mb=memory_limit_mb)
        _sandbox_memory_limit = memory_limit_mb
    return _sandbox_executor


class LLMProviderAdapter:
    """Adapts BaseLLMProvider to FunSearchLoop's LLMProvider protocol."""
    
    def __init__(self, provider: BaseLLMProvider, prompt_template: PromptTemplate):
        self.provider = provider
        self.prompt_template = prompt_template
        self.provider_id = provider.provider_id
    
    def generate(self, *, temperature: float, seed: int | None = None) -> str:
        """Generate a fresh candidate."""
        prompt = self.prompt_template.generate_fresh_candidate()
        if seed is not None:
            prompt = f"{prompt}\n\n# Seed: {seed}"
        try:
            response = self.provider.generate(prompt, temperature, max_tokens=2048)
            self._record_metrics(response)
            return self._extract_code(response.text)
        except Exception as e:
            self.provider._metrics["calls"] += 1
            self.provider._metrics["errors"] += 1
            raise
    
    def mutate(self, *, parent_code: str, temperature: float, seed: int | None = None) -> str:
        """Mutate an existing candidate."""
        prompt = self.prompt_template.mutate_candidate(parent_code)
        if seed is not None:
            prompt = f"{prompt}\n\n# Seed: {seed}"
        try:
            response = self.provider.generate(prompt, temperature, max_tokens=2048)
            self._record_metrics(response)
            return self._extract_code(response.text)
        except Exception as e:
            self.provider._metrics["calls"] += 1
            self.provider._metrics["errors"] += 1
            raise
    
    def _record_metrics(self, response: LLMResponse) -> None:
        """Record metrics from an LLM response."""
        self.provider._metrics["calls"] += 1
        self.provider._metrics["total_latency_ms"] += response.latency_ms
        
        if "input_tokens" in response.usage:
            self.provider._metrics["total_input_tokens"] += response.usage["input_tokens"]
        if "output_tokens" in response.usage:
            self.provider._metrics["total_output_tokens"] += response.usage["output_tokens"]
        
        cache_hit = response.raw_response.get("cache_hit", False)
        if cache_hit:
            self.provider._metrics["cache_hits"] += 1
        else:
            self.provider._metrics["cache_misses"] += 1
    
    def get_metrics(self) -> dict[str, Any]:
        """Get current metrics."""
        return self.provider.get_metrics()
    
    def reset_metrics(self) -> None:
        """Reset metrics for a new generation."""
        self.provider.reset_metrics()
    
    def _extract_code(self, text: str) -> str:
        """Extract Python code from markdown code blocks."""
        pattern = r"```(?:python)?\s*\n(.*?)\n```"
        matches = re.findall(pattern, text, re.DOTALL)
        if matches:
            return matches[0].strip()
        return text.strip()


class SandboxCandidate:
    """Wraps code string to provide score_bin method via sandbox execution.
    
    This is the SAFE version that executes code in an isolated subprocess
    with resource limits and import restrictions.
    """
    
    # Timeout for individual score_bin calls (seconds)
    CALL_TIMEOUT = 2
    
    def __init__(self, code: str, use_sandbox: bool = True):
        self.code = code
        self._use_sandbox = use_sandbox
        self._namespace: dict[str, Any] = {}
        self._validated = False
        
        # Validate code syntax upfront
        try:
            compile(code, "<candidate>", "exec")
        except SyntaxError as e:
            raise ValueError(f"Syntax error in code: {e}") from e
        
        if not use_sandbox:
            # Fast path: direct execution (for debugging/demo mode)
            try:
                exec(code, self._namespace)
                if "score_bin" not in self._namespace:
                    raise ValueError("Code must define score_bin function")
                self._validated = True
            except Exception as e:
                raise ValueError(f"Failed to execute code: {e}") from e
    
    def score_bin(self, item_size: int, remaining_capacity: int, bin_index: int, step: int) -> float:
        """Call the score_bin function - via sandbox or direct execution."""
        if self._use_sandbox:
            return self._sandbox_call(item_size, remaining_capacity, bin_index, step)
        else:
            return self._direct_call(item_size, remaining_capacity, bin_index, step)
    
    def _sandbox_call(self, item_size: int, remaining_capacity: int, bin_index: int, step: int) -> float:
        """Execute score_bin in isolated sandbox subprocess."""
        executor = get_sandbox_executor()
        instance_data = {
            "item_size": item_size,
            "remaining_capacity": remaining_capacity,
            "bin_index": bin_index,
            "step": step,
        }
        result = executor.execute(self.code, instance_data, timeout_seconds=self.CALL_TIMEOUT)
        
        if not result.success:
            raise RuntimeError(f"Sandbox execution failed: {result.error}")
        if result.result is None:
            raise RuntimeError("Sandbox returned no result")
        
        return float(result.result)
    
    def _direct_call(self, item_size: int, remaining_capacity: int, bin_index: int, step: int) -> float:
        """Direct execution without sandbox (fast but unsafe)."""
        if not self._validated:
            raise RuntimeError("Code not validated for direct execution")
        func = self._namespace["score_bin"]
        return float(func(item_size, remaining_capacity, bin_index, step))


# Alias for backward compatibility
ExecutableCandidate = SandboxCandidate


class SandboxBinPackingEvaluator:
    """Bin packing evaluator that runs code in sandbox using batch mode.
    
    This evaluator runs the entire pack_with_heuristic logic inside the sandbox,
    which is much faster than per-call subprocess creation.
    """
    
    def __init__(
        self,
        capacity: int = 100,
        seed: int = 42,
        cheap_instances: int = 4,
        full_instances: int = 10,
        memory_limit_mb: int = 256,
        batch_timeout_s: float = 30.0,
    ):
        self.capacity = capacity
        self.seed = seed
        self.cheap_instances = cheap_instances
        self.full_instances = full_instances
        self.batch_timeout = batch_timeout_s
        self._executor = get_sandbox_executor(memory_limit_mb)
    
    def _generate_instances(
        self,
        n_instances: int,
        min_items: int,
        max_items: int,
        seed_offset: int,
    ) -> list[dict[str, Any]]:
        """Generate bin packing instances."""
        import random
        rng = random.Random(self.seed + seed_offset)
        instances = []
        for _ in range(n_instances):
            n_items = rng.randint(min_items, max_items)
            instance_seed = rng.randint(0, 2_147_483_647)
            inst_rng = random.Random(instance_seed)
            items = sorted([inst_rng.randint(1, self.capacity) for _ in range(n_items)], reverse=True)
            instances.append({"items": items, "capacity": self.capacity})
        return instances
    
    def _evaluate_batch(self, code: str, instances: list[dict[str, Any]]) -> dict[str, Any]:
        """Evaluate code on instances using sandbox batch mode."""
        from evaluator.bin_packing import first_fit_decreasing
        
        result = self._executor.execute_batch(
            code=code,
            instances=instances,
            capacity=self.capacity,
            timeout_seconds=int(self.batch_timeout),
        )
        
        if not result.success or result.results is None:
            return {
                "score": None,
                "runtime_ms": result.runtime_ms,
                "error_type": "SandboxError",
                "metadata": {"error_message": result.error or "Unknown error"},
            }
        
        
        baseline_bins = []
        for inst in instances:
            baseline_bins.append(first_fit_decreasing(inst["items"], inst["capacity"]))
        
        instance_bins = result.results
        
        # 计算分数：使用平均箱子数（越少越好）
        # 主评分使用 -avg_bins，与非沙箱评估保持一致
        total_saved = sum(b - c for b, c in zip(baseline_bins, instance_bins))
        avg_bins = sum(instance_bins) / len(instance_bins)
        avg_baseline = sum(baseline_bins) / len(baseline_bins)
        score = -avg_bins
        
        return {
            "score": score,
            "runtime_ms": result.runtime_ms,
            "metadata": {
                "n_instances": len(instance_bins),
                "instance_bins": instance_bins,
                "avg_bins": avg_bins,
                "baseline_score": total_saved,
                "baseline_bins": baseline_bins,
                "avg_baseline": avg_baseline,
                "total_saved": total_saved,
            },
        }
    
    def cheap_eval(self, candidate: Any) -> Any:
        """Cheap evaluation on small instances."""
        instances = self._generate_instances(
            n_instances=self.cheap_instances,
            min_items=20,
            max_items=50,
            seed_offset=0,
        )
        return self._evaluate_batch(candidate.code, instances)
    
    def full_eval(self, candidate: Any) -> Any:
        """Full evaluation on more instances."""
        instances = self._generate_instances(
            n_instances=self.full_instances,
            min_items=50,
            max_items=100,
            seed_offset=10_000,
        )
        return self._evaluate_batch(candidate.code, instances)


class SandboxBenchmarkEvaluator:
    """Benchmark evaluator that runs code in sandbox using batch mode."""
    
    def __init__(
        self,
        dataset: Any,
        seed: int = 42,
        cheap_sample_size: int = 5,
        memory_limit_mb: int = 256,
        batch_timeout_s: float = 60.0,
    ):
        self.dataset = dataset
        self.seed = seed
        self.cheap_sample_size = min(cheap_sample_size, len(dataset))
        self.batch_timeout = batch_timeout_s
        self._executor = get_sandbox_executor(memory_limit_mb)
        self._rng = __import__("random").Random(seed)
    
    def _dataset_to_instances(self, dataset_instances: list[Any]) -> list[dict[str, Any]]:
        """Convert dataset instances to sandbox format."""
        return [
            {"items": sorted(inst.items, reverse=True), "capacity": inst.capacity}
            for inst in dataset_instances
        ]
    
    def _evaluate_batch(self, code: str, instances: list[dict[str, Any]]) -> dict[str, Any]:
        """Evaluate code on instances using sandbox batch mode."""
        from evaluator.bin_packing import first_fit_decreasing
        
        result = self._executor.execute_batch(
            code=code,
            instances=instances,
            capacity=100,  # Default, overridden per-instance
            timeout_seconds=int(self.batch_timeout),
        )
        
        if not result.success or result.results is None:
            return {
                "score": None,
                "runtime_ms": result.runtime_ms,
                "error_type": "SandboxError",
                "metadata": {"error_message": result.error or "Unknown error"},
            }
        
        
        baseline_bins = []
        for inst in instances:
            baseline_bins.append(first_fit_decreasing(inst["items"], inst["capacity"]))
        
        instance_bins = result.results
        
        # 计算分数：使用平均箱子数（越少越好）
        # 主评分使用 -avg_bins，与非沙箱评估保持一致
        total_saved = sum(b - c for b, c in zip(baseline_bins, instance_bins))
        avg_bins = sum(instance_bins) / len(instance_bins)
        avg_baseline = sum(baseline_bins) / len(baseline_bins)
        score = -avg_bins
        
        return {
            "score": score,
            "runtime_ms": result.runtime_ms,
            "metadata": {
                "n_instances": len(instance_bins),
                "instance_bins": instance_bins,
                "avg_bins": avg_bins,
                "baseline_score": total_saved,
                "baseline_bins": baseline_bins,
                "avg_baseline": avg_baseline,
                "total_saved": total_saved,
            },
        }
    
    def cheap_eval(self, candidate: Any) -> Any:
        """Cheap evaluation on sample of instances."""
        sample_indices = self._rng.sample(range(len(self.dataset)), self.cheap_sample_size)
        sample_instances = [self.dataset[i] for i in sample_indices]
        instances = self._dataset_to_instances(sample_instances)
        return self._evaluate_batch(candidate.code, instances)
    
    def full_eval(self, candidate: Any) -> Any:
        """Full evaluation on all instances."""
        instances = self._dataset_to_instances(list(self.dataset))
        return self._evaluate_batch(candidate.code, instances)


class EvaluatorAdapter:
    """Adapts evaluator to work with funsearch_core.Candidate.
    
    Args:
        base_evaluator: The underlying evaluator (RandomEvaluator or BenchmarkEvaluator)
        use_sandbox: If True, use sandboxed execution (default). If False, use direct exec.
    """
    
    def __init__(self, base_evaluator: Any, use_sandbox: bool = True):
        self.base_evaluator = base_evaluator
        self.use_sandbox = use_sandbox
    
    def cheap_eval(self, candidate: Any) -> Any:
        """Cheap evaluation - wraps candidate code for execution."""
        try:
            executable = SandboxCandidate(candidate.code, use_sandbox=self.use_sandbox)
            return self.base_evaluator.cheap_eval(executable)
        except Exception as e:
            return {
                "score": None,
                "runtime_ms": 0.0,
                "error_type": type(e).__name__,
                "metadata": {"error_message": str(e)}
            }
    
    def full_eval(self, candidate: Any) -> Any:
        """Full evaluation - wraps candidate code for execution."""
        try:
            executable = SandboxCandidate(candidate.code, use_sandbox=self.use_sandbox)
            return self.base_evaluator.full_eval(executable)
        except Exception as e:
            return {
                "score": None,
                "runtime_ms": 0.0,
                "error_type": type(e).__name__,
                "metadata": {"error_message": str(e)}
            }


class RobustCandidateStore:
    """Wrapper around CandidateStore that handles FK errors gracefully."""
    
    def __init__(self, store: CandidateStore):
        self.store = store
        self._saved_candidates: set[str] = set()
    
    def save_candidate(self, candidate: Any) -> bool:
        """Save candidate and track which ones were saved."""
        result = self.store.save_candidate(candidate)
        if result:
            self._saved_candidates.add(candidate.id)
        return result
    
    def record_evaluation(self, eval_data: dict[str, Any]) -> None:
        """Record evaluation only if candidate was saved."""
        candidate_id = eval_data.get("candidate_id")
        if candidate_id not in self._saved_candidates:
            return
        
        try:
            self.store.record_evaluation(eval_data)
        except Exception:
            pass
    
    def __getattr__(self, name: str) -> Any:
        """Delegate all other methods to the wrapped store."""
        return getattr(self.store, name)


class ExperimentRunner:
    """Coordinates all components for a complete experiment run."""
    
    def __init__(self, config: ExperimentConfig):
        self.config = config
        self.variant = getattr(config, "variant", "both")
        self.artifacts: ArtifactManager | None = None
        self.interrupted = False
        
        self._setup_signal_handlers()
    
    def _setup_signal_handlers(self) -> None:
        """Setup graceful shutdown on Ctrl+C."""
        def signal_handler(signum: int, frame: Any) -> None:
            print("\n⚠️  Interrupt received. Saving progress and shutting down gracefully...")
            self.interrupted = True
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    def run(self) -> dict[str, Any]:
        """Run the complete experiment.
        
        Returns:
            Summary dictionary with run statistics
        """
        variants_to_run = []
        if self.variant == "both":
            variants_to_run = ["A", "B"]
        elif self.variant in ["A", "B"]:
            variants_to_run = [self.variant]
        else:
            variants_to_run = [None]
        
        if len(variants_to_run) == 1 and variants_to_run[0] is None:
            return self._run_single_variant(None)
        
        summaries = {}
        for variant in variants_to_run:
            if variant:
                print(f"\n{'='*60}")
                print(f"  Running Variant {variant}")
                print('='*60 + "\n")
            
            summary = self._run_single_variant(variant)
            summaries[f"variant_{variant}"] = summary
        
        return summaries
    
    def _run_single_variant(self, variant: str | None) -> dict[str, Any]:
        """Run experiment for a single variant.
        
        Args:
            variant: "A", "B", or None for no variant
            
        Returns:
            Summary dictionary with run statistics
        """
        try:
            self.artifacts = ArtifactManager(self.config, variant=variant)
            self.artifacts.snapshot_config()
            
            if variant:
                print(f"📁 Artifacts for Variant {variant}: {self.artifacts.run_dir}")
            else:
                print(f"🚀 Starting experiment: {self.config.run_id}")
            
            print(f"   Max generations: {self.config.max_generations}")
            print(f"   Population size: {self.config.population_size}")
            print(f"   Islands: {self.config.num_islands}")
            print(f"   Task: {self.config.task_name}")
            print()
            
            providers = self._initialize_providers()
            evaluator = self._initialize_evaluator()
            store = self._initialize_store()
            loop = self._initialize_loop(providers, evaluator, store)
            
            self._run_loop(loop)
            
            summary = self._finalize_run(loop)
            
            return summary
            
        except Exception as e:
            print(f"\n❌ Experiment failed: {e}")
            raise
    
    def _initialize_providers(self) -> dict[str, LLMProviderAdapter]:
        """Initialize LLM providers from config."""
        providers: dict[str, LLMProviderAdapter] = {}
        from llm.prompts import VariantType
        variant: VariantType | None = None
        if self.config.variant == "A":
            variant = "A"
        elif self.config.variant == "B":
            variant = "B"
        prompt_template = get_prompt_template(variant)
        
        for provider_config in self.config.llm_providers:
            llm_config = LLMProviderConfig.from_dict(provider_config)
            base_provider = create_provider(llm_config)
            
            adapter = LLMProviderAdapter(base_provider, prompt_template)
            providers[llm_config.provider_id] = adapter
        
        return providers
    
    def _initialize_evaluator(self) -> Any:
        """Initialize task evaluator from config."""
        task_name = self.config.task_name.lower()
        
        # 检查是否启用沙箱（默认启用，demo 模式下可禁用以提高速度）
        use_sandbox = self.config.evaluator.get("use_sandbox", True)
        if use_sandbox:
            print(f"   🔒 Sandbox: ENABLED (safe batch execution)")
        else:
            print(f"   ⚠️  Sandbox: DISABLED (fast but unsafe)")
        
        if task_name == "bin_packing":
            capacity = self.config.evaluator.get("capacity", 100)
            seed = self.config.evaluator.get("seed", self.config.seed)
            eval_type = self.config.evaluator.get("type", "random")
            eval_size = self.config.evaluator.get("size", "small")
            
            if use_sandbox:
                # 使用沙箱批量评估器 (快速且安全)
                if eval_type == "orlib":
                    from evaluator.datasets import load_orlib_small, load_orlib_large
                    
                    if eval_size == "large":
                        dataset = load_orlib_large()
                        print(f"   📊 Using OR-Library LARGE dataset ({len(dataset)} instances)")
                    else:
                        dataset = load_orlib_small()
                        print(f"   📊 Using OR-Library SMALL dataset ({len(dataset)} instances)")
                    
                    return SandboxBenchmarkEvaluator(
                        dataset=dataset,
                        seed=seed,
                        memory_limit_mb=self.config.sandbox_memory_limit_mb,
                        batch_timeout_s=self.config.batch_timeout_s,
                    )
                else:
                    if eval_size == "large":
                        print(f"   📊 Using RANDOM LARGE instances (20 instances, 100-200 items)")
                    else:
                        print(f"   📊 Using RANDOM SMALL instances (default)")
                    
                    return SandboxBinPackingEvaluator(
                        capacity=capacity,
                        seed=seed,
                        memory_limit_mb=self.config.sandbox_memory_limit_mb,
                        batch_timeout_s=self.config.batch_timeout_s,
                    )
            else:
                # 使用直接执行评估器 (快速但不安全)
                from evaluator.bin_packing import BinPackingEvaluator, BenchmarkEvaluator
                
                if eval_type == "orlib":
                    from evaluator.datasets import load_orlib_small, load_orlib_large
                    
                    if eval_size == "large":
                        dataset = load_orlib_large()
                        print(f"   📊 Using OR-Library LARGE dataset ({len(dataset)} instances)")
                    else:
                        dataset = load_orlib_small()
                        print(f"   📊 Using OR-Library SMALL dataset ({len(dataset)} instances)")
                    
                    base_evaluator = BenchmarkEvaluator(dataset=dataset, seed=seed)
                else:
                    if eval_size == "large":
                        print(f"   📊 Using RANDOM LARGE instances (20 instances, 100-200 items)")
                    else:
                        print(f"   📊 Using RANDOM SMALL instances (default)")
                    
                    base_evaluator = BinPackingEvaluator(capacity=capacity, seed=seed)
                
                return EvaluatorAdapter(base_evaluator, use_sandbox=False)
        
        raise ValueError(f"Unknown task: {self.config.task_name}")
    
    def _initialize_store(self) -> RobustCandidateStore:
        """Initialize candidate store with database."""
        base_store = CandidateStore(
            run_id=self.config.run_id,
            config=self.config.to_dict(),
            seed=self.config.seed,
            db_path=str(self.artifacts.candidates_db_path),
        )
        return RobustCandidateStore(base_store)
    
    def _initialize_loop(
        self,
        providers: dict[str, LLMProviderAdapter],
        evaluator: Any,
        store: Any,
    ) -> FunSearchLoop:
        """Initialize FunSearch loop with all components."""
        generator = providers[self.config.generator_provider_id]
        refiner = providers[self.config.refiner_provider_id]
        
        # 使用专门的探针运行器 - 快速测试代码行为而非完整评估
        # 记录评分决策过程（不只是装箱结果），提高区分度
        eval_type = self.config.evaluator.get("type", "random")
        default_probe_items = 20 if eval_type == "orlib" else 8
        probe_num_items = self.config.evaluator.get("probe_num_items", default_probe_items)
        probe_runner = create_binpacking_probe_runner(capacity=100, num_items=probe_num_items)
        
        signature_calculator = SignatureCalculator(probe_runner=probe_runner)
        selection_strategy = TournamentSelection(tournament_size=3)
        default_min_distance = 0.05 if eval_type == "orlib" else 0.1
        min_distance = self.config.evaluator.get("diversity_min_distance", default_min_distance)
        diversity_maintainer = DiversityMaintainer(min_distance=min_distance)
        
        # 创新点1: 功能级去重 (两阶段)
        # Stage 1: 代码规范化哈希 - 快速过滤文本相同的代码
        # Stage 2: 行为签名 - 检测功能等价的不同代码
        # Variant B uses more probe seeds for stronger diversity filtering
        probe_count = 5 if self.config.variant == "B" else 3
        deduplicator = FunctionalDeduplicator(
            probe_runner=probe_runner,
            probe_seeds=list(range(probe_count)),
            cache_size_limit=10000,
            use_code_hash=True,
        )
        
        if self.config.variant == "B":
            print("   🎨 Variant B: Novelty prompting + enhanced diversity")
        
        return FunSearchLoop(
            config=self.config,
            generator=generator,
            refiner=refiner,
            evaluator=evaluator,
            signature_calculator=signature_calculator,
            selection_strategy=selection_strategy,
            diversity_maintainer=diversity_maintainer,
            deduplicator=deduplicator,  # 启用功能级去重
            store=store,
        )
    
    def _run_loop(self, loop: FunSearchLoop) -> None:
        """Run the main evolution loop with periodic saves."""
        best_ever: float | None = None
        
        print("\n" + "=" * 50)
        print("  FunSearch Evolution Started")
        print("=" * 50 + "\n")
        
        # 使用 tqdm 进度条
        pbar = tqdm(
            range(self.config.max_generations),
            desc="🧬 Evolution",
            unit="gen",
            ncols=100,
            bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]"
        )
        
        for gen in pbar:
            if self.interrupted:
                pbar.close()
                print(f"\n⚠️  Stopping at generation {gen}")
                break
            
            stats = loop.run_generation()
            
            # 提取统计信息
            overall = stats.get("overall", {})
            best_score = overall.get("best_score")
            avg_score = overall.get("avg_score")
            count = overall.get("count", 0)
            
            # 跟踪历史最佳
            new_best = False
            if best_score is not None:
                if best_ever is None or best_score > best_ever:
                    best_ever = best_score
                    new_best = True
            
            # 更新进度条后缀
            best_str = f"{best_score:.2f}" if best_score is not None else "N/A"
            avg_str = f"{avg_score:.2f}" if avg_score is not None else "N/A"
            best_ever_str = f"{best_ever:.2f}" if best_ever is not None else "N/A"
            
            postfix = {
                "Best": best_str,
                "Avg": avg_str,
                "Valid": count,
                "🏆Best Ever": best_ever_str
            }
            pbar.set_postfix(postfix)
            
            # 如果有新最佳，额外打印提示
            if new_best:
                tqdm.write(f"  🔥 NEW BEST! Score: {best_score:.4f}")
            
            self.artifacts.save_generation_metrics(gen, stats)
            
            if (gen + 1) % self.config.save_interval == 0:
                tqdm.write(f"   💾 Checkpoint saved at generation {gen + 1}")
        
        if not self.interrupted:
            print(f"\n" + "=" * 50)
            print(f"  Completed {self.config.max_generations} generations")
            if best_ever:
                print(f"  Best Score: {best_ever:.4f}")
            print("=" * 50)
    
    def _print_generation_stats(self, gen: int, stats: dict[str, Any]) -> None:
        """Print generation statistics."""
        overall = stats.get("overall", {})
        best_score = overall.get("best_score")
        avg_score = overall.get("avg_score")
        count = overall.get("count", 0)
        
        best_str = f"{best_score:.4f}" if best_score is not None else "N/A"
        avg_str = f"{avg_score:.4f}" if avg_score is not None else "N/A"
        
        print(f"Gen {gen:3d} | Best: {best_str} | Avg: {avg_str} | Count: {count}")
    
    def _save_checkpoint(self, loop: FunSearchLoop) -> None:
        """Save checkpoint (already handled by store, just log)."""
        print(f"   💾 Checkpoint saved")
    
    def _finalize_run(self, loop: FunSearchLoop) -> dict[str, Any]:
        """Finalize run and export best candidate."""
        best_candidate = None
        best_score = float("-inf")
        
        for island in loop.islands.islands:
            for candidate in island.population.candidates:
                if candidate.score is not None and candidate.score > best_score:
                    best_score = candidate.score
                    best_candidate = candidate
        
        if best_candidate is not None:
            self.artifacts.export_best_candidate(best_candidate)
            print(f"\n🏆 Best candidate (score: {best_score:.4f}) exported to:")
            print(f"   {self.artifacts.best_candidate_path}")
        else:
            print("\n⚠️  No valid candidates found")
        
        # 生成可视化图表
        self._generate_plots()
        
        # 生成实验报告
        self._generate_report()
        
        summary = self.artifacts.get_summary()
        
        print(f"\n📊 Run Summary:")
        print(f"   Run ID: {summary['run_id']}")
        print(f"   Status: {summary['status']}")
        print(f"   Generations: {summary['generations_completed']}/{summary['max_generations']}")
        print(f"   Best Score: {summary.get('best_score', 'N/A')}")
        print(f"   Artifacts: {self.artifacts.run_dir}")
        
        return summary
    
    def _generate_plots(self) -> None:
        """Generate visualization plots from metrics."""
        if not self.artifacts:
            return
            
        try:
            from experiments.plotting import PlotGenerator, MATPLOTLIB_AVAILABLE
            
            if not MATPLOTLIB_AVAILABLE:
                print("   ⚠️  matplotlib not available, skipping plots")
                return
            
            metrics = self.artifacts.load_metrics()
            if len(metrics) < 2:
                print("   ⚠️  Not enough data for plots (need at least 2 generations)")
                return
            
            plotter = PlotGenerator()
            
            evolution_path = self.artifacts.plots_dir / "evolution_curve.png"
            plotter.plot_evolution_curve(metrics, evolution_path)
            
            dashboard_path = self.artifacts.plots_dir / "dashboard.png"
            plotter.plot_dashboard(metrics, dashboard_path)
            
            islands_path = self.artifacts.plots_dir / "islands_evolution.png"
            plotter.plot_per_island_evolution(metrics, islands_path)
            
            # 生成失败分布饼图 (如果有失败数据)
            if any("failures" in m for m in metrics):
                failure_path = self.artifacts.plots_dir / "failure_distribution.png"
                plotter.plot_failure_distribution(metrics, failure_path)
            
            print(f"\n📈 Plots generated in: {self.artifacts.plots_dir}")
            
        except Exception as e:
            print(f"   ⚠️  Failed to generate plots: {e}")

    def _generate_report(self) -> None:
        """Generate Markdown and HTML reports."""
        if not self.artifacts:
            return
            
        try:
            from experiments.report import ReportGenerator
            
            generator = ReportGenerator(
                metrics_path=self.artifacts.metrics_path,
                plots_dir=self.artifacts.plots_dir,
                config=self.config.to_dict()
            )
            
            md_path = self.artifacts.run_dir / "report.md"
            html_path = self.artifacts.run_dir / "report.html"
            
            generator.generate_markdown(md_path)
            generator.generate_html(html_path)
            
            print(f"📄 Reports generated in: {self.artifacts.run_dir}")
            
        except Exception as e:
            print(f"   ⚠️  Failed to generate reports: {e}")
