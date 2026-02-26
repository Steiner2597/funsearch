# FunSearch 项目改进清单

> 更新时间：2026-02-26

---

## 1. 优先级 P0（必须先做）

## P0-1 修复 Variant 链路大小写不一致

**问题**

- CLI 将 variant 写成小写（`a/b/both`），但 runner 中逻辑按大写（`A/B`）判断，导致 Variant B 可能未按预期生效。

**改动项**

- 统一 variant 规范（建议全小写：`a/b/both`）。
- 在 `ExperimentRunner` 内统一做一次标准化，避免调用方差异。

**验收标准**

- `--variant b` 时，能够稳定触发 Novelty prompt + 增强探针种子数量。
- 产物目录、配置快照和日志能正确标识 Variant。

---

## P0-2 增加“可关闭多样性过滤”开关

**问题**

- 文档建议“临时关闭 DiversityMaintainer 做对照试验”，但代码没有可配置开关。

**改动项**

- 在 `evaluator` 或顶层配置增加 `enable_diversity: true/false`。
- 当关闭时，不实例化 `DiversityMaintainer`，仅保留 signature 去重。

**验收标准**

- 同一配置仅切换 `enable_diversity` 后，可观察有效种群数明显变化。
- 生成报告中可记录该开关状态。

---

## P0-3 将关键调参暴露到 run.py

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

## 2. 优先级 P1（核心效果提升）

## P1-1 OR-Library 感知 Probe

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

## P1-2 增加可选评分模式（增强优化信号）

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

## P1-3 降低 full_eval 成本并加快反馈

**问题**

- OR-Library large 的 full_eval 计算重，影响每代迭代效率。

**改动项**

- 增加 `full_eval_every_n_generations`（例如每 2~3 代做一次 full_eval）。
- 增加 `orlib_subset`（先在 small/subset 快速验证再上 large）。

**验收标准**

- 单次实验总耗时下降。
- 早期代数能更快获得趋势反馈，不显著损失最终排名能力。

---

## 3. 优先级 P2（工程稳定性与可观测性）

## P2-1 观测指标补齐

**新增指标建议**

- 每代“有效候选率”：`(通过 dedup + diversity + cheap_eval 的数量) / 生成数量`
- 过滤原因拆分：`dedup_skipped`、`diversity_rejected`、`eval_failed`
- 全流程吞吐：每代总评估时长、平均每 candidate 耗时

**验收标准**

- 报告和 metrics 中可直接看到“为何种群缩小”。

---

## P2-2 测试补齐

**新增测试建议**

- variant 大小写链路（CLI -> Config -> Runner -> Prompt Template）
- `enable_diversity` 开关行为
- `probe mode` 切换行为
- `score_mode` 切换结果合法性

**验收标准**

- 相关测试通过，且不会破坏现有回归测试。

---

## P2-3 文档一致性修复

**问题**

- 部分文档描述与当前实现不一致（例如去重描述口径）。

**改动项**

- 更新 `docs/METRICS.md`、`docs/RUNNING_EXPERIMENTS.md`，同步最新字段和行为。

**验收标准**

- 文档参数、命令、指标与代码一致，可直接复现实验。

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

## 5. 补充问题

## S1. A/B 变体链路一致性风险

**问题**

- `CLI` 侧使用小写 variant（`a/b/both`），而部分执行逻辑使用大写分支判断，存在“配置已传入但策略未真正生效”的风险。

**改动项**

- 统一全链路 variant 枚举与大小写规范（建议统一小写）。
- 在 `runner` 初始化时做一次标准化并打印生效值。

**验收标准**

- `--variant b` 时，Prompt 模板、probe seed 数量、产物命名三者一致切换。

---

## S2. 候选行为特征计算重复开销

**问题**

- 候选在进入评估前可能经历两套行为计算（signature 与 dedup probe 分别执行），导致预算浪费并降低单位时间有效探索量。

**改动项**

- 复用同一份行为向量/签名结果，避免重复 probe。
- 在指标中新增 `probe_calls_per_candidate` 监控重复计算是否被消除。

**验收标准**

- 在相同实验配置下，平均每代可评估候选数上升或代耗时下降。

---

## S3. 运行状态判定口径风险（CLI 展示层）

**问题**

- 当返回值为多变体汇总结构时，CLI 仍按单 run 的 `status` 读取，可能出现展示状态与真实完成状态不一致。

**改动项**

- 区分单变体与多变体返回结构，分别做完成判定。
- 输出每个变体独立状态与总体状态。

**验收标准**

- `--variant both` 运行后，CLI 能准确展示 `variant_a/variant_b` 各自完成情况。

---

## S4. 缺少过滤链路归因指标

**问题**

- 当前难以直接量化“去重拒绝 / 多样性拒绝 / 评估失败”各自占比，排障和调参效率受限。

**改动项**

- 增加每代过滤归因计数：`dedup_rejected`、`diversity_rejected`、`cheap_eval_failed`。
- 在报告中新增“候选流转漏斗”视图（生成→通过去重→通过多样性→cheap成功→full成功）。

**验收标准**

- 任意一次实验结束后，可直接从报告中定位瓶颈阶段。

---
