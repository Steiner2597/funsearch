# FunSearch 项目改进清单

> 更新时间：2026-02-26

---

## 1. 优先级 P0（必须先做）

### P0-1 修复 Variant 链路大小写不一致

**问题**

- CLI 将 variant 写成小写（`a/b/both`），但 runner 中逻辑按大写（`A/B`）判断，导致 Variant B 可能未按预期生效。

**改动项**

- 统一 variant 规范（建议全小写：`a/b/both`）。
- 在 `ExperimentRunner` 内统一做一次标准化，避免调用方差异。

**验收标准**

- `--variant b` 时，能够稳定触发 Novelty prompt + 增强探针种子数量。
- 产物目录、配置快照和日志能正确标识 Variant。

---

### P0-2 增加“可关闭多样性过滤”开关

**问题**

- 文档建议“临时关闭 DiversityMaintainer 做对照试验”，但代码没有可配置开关。

**改动项**

- 在 `evaluator` 或顶层配置增加 `enable_diversity: true/false`。
- 当关闭时，不实例化 `DiversityMaintainer`，仅保留 signature 去重。

**验收标准**

- 同一配置仅切换 `enable_diversity` 后，可观察有效种群数明显变化。
- 生成报告中可记录该开关状态。

---

### P0-3 将关键调参暴露到 run.py

**问题**

- 快速启动脚本 `run.py` 仍把温度固定为 `1.0`，也不支持 probe/diversity/variant 关键参数。

**改动项**

- 为 `run.py` 增加参数：
  - `--temperature`
  - `--variant`
  - `--diversity-min-distance`
  - `--probe-num-items`
  - `--top-k-full-eval`（可选）
- 写入临时配置文件并保留到 artifacts 快照。

**验收标准**

- 命令行传入值可在生成的 `config.yaml` 中准确反映。
- 不再需要手工改 YAML 才能做核心对照实验。

---

### P0 已做的改动（代码）

- ✅ 已实现 P0-1（Variant 链路一致化）
  - `ExperimentRunner` 新增 variant 归一化逻辑，统一支持 `a/b/both/none`。
  - 单变体运行时将配置中的 variant 与当前分支运行值保持一致。
  - 改动位置：
    - `experiments/runner.py` -> `ExperimentRunner.__init__`
    - `experiments/runner.py` -> `ExperimentRunner._normalize_variant`
    - `experiments/runner.py` -> `ExperimentRunner.run`
    - `experiments/runner.py` -> `ExperimentRunner._run_single_variant`
    - `experiments/runner.py` -> `ExperimentRunner._initialize_providers`
    - `experiments/runner.py` -> `ExperimentRunner._initialize_loop`

- ✅ 已实现 P0-2（可关闭多样性过滤）
  - 新增 `evaluator.enable_diversity` 开关。
  - 关闭时不实例化 `DiversityMaintainer`，保留去重流程。
  - 改动位置：
    - `experiments/runner.py` -> `ExperimentRunner._coerce_bool`
    - `experiments/runner.py` -> `ExperimentRunner._initialize_loop`

- ✅ 已实现 P0-3（run.py 暴露关键参数）
  - 新增参数：`--temperature`、`--variant`、`--diversity-min-distance`、`--probe-num-items`、`--top-k-full-eval`、`--disable-diversity`。
  - 临时配置写入 `variant`、`top_k_for_full_eval`、`evaluator.enable_diversity` 及相关调参项。
  - 改动位置：
    - `run.py` -> `create_temp_config`
    - `run.py` -> `print_config`
    - `run.py` -> `main`（argparse 参数定义）
    - `run.py` -> `main`（实验完成状态判定）

- ✅ 配套回归测试已新增
  - 新增测试覆盖：小写 variant 生效、`variant=both` 分支展开、diversity 开关行为。
  - 改动位置：
    - `tests/test_runner_p0.py` -> `test_runner_accepts_lowercase_variant_b_for_prompt_and_dedup`
    - `tests/test_runner_p0.py` -> `test_runner_disables_diversity_when_configured`
    - `tests/test_runner_p0.py` -> `test_runner_expands_lowercase_both_variants`

---

## 2. 优先级 P1（核心效果提升）

### P1-1 OR-Library 感知 Probe

**问题**

- 当前 probe 仍是随机混合分布，和 OR-Library 的典型结构（u/t 类）有分布偏差。

**改动项**

- 在 `create_binpacking_probe_runner` 增加 `mode`：`random` / `orlib`。
- `orlib` 模式可采用：
  - 固定结构模板（近似 u/t 分布）；或
  - 从 `data/orlib` 抽样构建 probe items。

**验收标准**

- 在相同代数下，`orlib` probe 的候选区分度提升（重复率下降或有效候选数上升）。

---

### P1-2 增加可选评分模式（增强优化信号）

**问题**

- 单一 `-avg_bins` 在强基线场景下，可能长期“全负值且不易分辨增益”。

**改动项**

- 增加 `score_mode`：
  - `raw_bins`：`-avg_bins`（当前默认）
  - `gap_to_lb`：`-(avg_bins - lower_bound_avg)`
- 下界 `lower_bound` 先采用 `ceil(sum(items) / capacity)`。

**验收标准**

- 两种评分模式可通过配置切换。
- 报告中能显示对应的 score 定义和关键中间量（如 `lower_bound_avg`）。

---

### P1-3 降低 full_eval 成本并加快反馈

**问题**

- OR-Library large 的 full_eval 计算重，影响每代迭代效率。

**改动项**

- 增加 `full_eval_every_n_generations`（例如每 2~3 代做一次 full_eval）。
- 增加 `orlib_subset`（先在 small/subset 快速验证再上 large）。

**验收标准**

- 单次实验总耗时下降。
- 早期代数能更快获得趋势反馈，不显著损失最终排名能力。

---

### P1 已做的改动（代码）

- ✅ 已实现 P1-1（OR-Library 感知 Probe）
  - `create_binpacking_probe_runner` 支持 `mode=random/orlib` 和 `orlib_item_pool`。
  - `runner` 会在 orlib 场景优先使用 `probe_mode=orlib`，并从数据集抽样构建 probe 池。
  - 改动位置：
    - `funsearch_core/deduplication.py` -> `create_binpacking_probe_runner`
    - `experiments/runner.py` -> `ExperimentRunner._initialize_loop`
    - `tests/test_deduplication.py` -> `test_orlib_probe_mode_works_with_item_pool`

- ✅ 已实现 P1-2（评分模式 `raw_bins/gap_to_lb`）
  - 新增 `score_mode` 配置并接入 sandbox 与非 sandbox 评估器。
  - 新增 `avg_lower_bound`、`score_mode` 指标写入 metadata。
  - 改动位置：
    - `experiments/runner.py` -> `_normalize_score_mode` / `_compute_score`
    - `experiments/runner.py` -> `SandboxBinPackingEvaluator` / `SandboxBenchmarkEvaluator`
    - `evaluator/bin_packing.py` -> `BinPackingEvaluator` / `BenchmarkEvaluator`
    - `tests/test_runner_p1.py` -> `test_runner_p1_passes_score_mode_and_full_eval_cadence`

- ✅ 已实现 P1-3（降低 full_eval 成本）
  - 新增 `full_eval_every_n_generations`，支持按代数间隔执行 full_eval。
  - 新增 `orlib_subset`，支持 OR-Library 子集评估加速。
  - 改动位置：
    - `funsearch_core/loop.py` -> `FunSearchLoop.__init__` / `run_generation`
    - `experiments/runner.py` -> `ExperimentRunner._subset_orlib_dataset`
    - `experiments/runner.py` -> `ExperimentRunner._initialize_evaluator` / `_initialize_loop`
    - `tests/test_runner_p1.py` -> `test_funsearch_loop_full_eval_cadence`

- ✅ `run.py` 已补齐 P1 参数入口
  - 新增参数：`--probe-mode`、`--score-mode`、`--full-eval-every`、`--orlib-subset`。
  - 改动位置：
    - `run.py` -> `create_temp_config`
    - `run.py` -> `print_config`
    - `run.py` -> `main`（argparse 参数定义）

---

## 3. 优先级 P2（工程稳定性与可观测性）

### P2-1 观测指标补齐

**新增指标建议**

- 每代“有效候选率”：`(通过 dedup + diversity + cheap_eval 的数量) / 生成数量`
- 过滤原因拆分：`dedup_skipped`、`diversity_rejected`、`eval_failed`
- 全流程吞吐：每代总评估时长、平均每 candidate 耗时

**验收标准**

- 报告和 metrics 中可直接看到“为何种群缩小”。

---

### P2-2 测试补齐

**新增测试建议**

- variant 大小写链路（CLI -> Config -> Runner -> Prompt Template）
- `enable_diversity` 开关行为
- `probe mode` 切换行为
- `score_mode` 切换结果合法性

**验收标准**

- 相关测试通过，且不会破坏现有回归测试。

---

### P2-3 文档一致性修复

**问题**

- 部分文档描述与当前实现不一致（例如去重描述口径）。

**改动项**

- 更新 `docs/METRICS.md`、`docs/RUNNING_EXPERIMENTS.md`，同步最新字段和行为。

**验收标准**

- 文档参数、命令、指标与代码一致，可直接复现实验。

---

### P2 已做的改动（代码）

- ✅ 已实现 P2-1（观测指标补齐）
  - generation 统计新增 candidate funnel、有效候选率与评估耗时指标。
  - 报告新增 `Candidate Flow Funnel` 小节，直接展示瓶颈位置。
  - 改动位置：
    - `funsearch_core/loop.py` -> `FunSearchLoop.run_generation`
    - `experiments/report.py` -> `ReportGenerator.generate_markdown`

- ✅ 已实现 P2-2（测试补齐）
  - 新增 loop 指标测试，验证 `funnel` / `effective_candidate_rate` / `timing` 字段。
  - 报告生成测试新增 funnel 小节断言。
  - 改动位置：
    - `tests/test_funsearch_core.py` -> `test_funsearch_loop_emits_funnel_and_timing_metrics`
    - `tests/test_report_generation.py` -> `test_report_generator_markdown`

- ✅ 已实现 P2-3（文档一致性）
  - 同步更新 `docs/METRICS.md` 到当前 `metrics.jsonl` 实际 schema。
  - 同步更新 `docs/RUNNING_EXPERIMENTS.md`，补齐 P1/P2 参数与判读口径。
  - 改动位置：
    - `docs/METRICS.md`
    - `docs/RUNNING_EXPERIMENTS.md`

---

## 4. 建议实验矩阵（最小可行）

- 数据集：`orlib/large`
- 代数：`6`
- 种群：`15`
- 岛屿：`3`
- 对照维度：
  1. `enable_diversity`: on/off
  2. `temperature`: 1.0 / 1.3
  3. `probe_num_items`: 20 / 30

共 8 组；每组至少 2 次不同 seed 重复。

**主看板指标**

- Best Score 改进量（终点 - 起点）
- 首次改进代数（generation to first improvement）
- 有效候选率
- 运行总时长

---

## 5. 补充问题（未解决）

### S2. 候选行为特征计算重复开销

**问题**

- 候选在进入评估前可能经历两套行为计算（signature 与 dedup probe 分别执行），导致预算浪费并降低单位时间有效探索量。

**改动项**

- 复用同一份行为向量/签名结果，避免重复 probe。
- 在指标中新增 `probe_calls_per_candidate` 监控重复计算是否被消除。

**验收标准**

- 在相同实验配置下，平均每代可评估候选数上升或代耗时下降。

---

### S3. 运行状态判定口径（剩余收尾）

**问题**

- 目前已支持多变体汇总完成判定，但 CLI 仍未显式输出每个变体（`variant_a` / `variant_b`）的独立完成状态，排查时可见性不足。

**改动项**

- 保留现有“总体完成”判定逻辑。
- 增加逐变体状态输出（`variant_a`、`variant_b`）与最终汇总状态。

**验收标准**

- `--variant both` 运行后，CLI 能准确展示 `variant_a/variant_b` 各自完成情况。

---

### 已解决归档

- ✅ S1. A/B 变体链路一致性风险（已在 P0-1 落地）
- ✅ S4. 缺少过滤链路归因指标（已在 P2-1 落地）

---
