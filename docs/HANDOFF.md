# FunSearch Bin Packing Handoff (2026-02-25)

## 背景与近期试验

所有实验（含 random 与 orlib）都出现“评分不改进、始终为负数”的问题，从未优于基线。
近期两次 OR-Library 大规模实验（orlib/large）只是最明显的案例。
- 试验 A (8 代, 20*3): funsearch_orlib_large_20260225_185132
- 试验 B (6 代, 15*3): funsearch_orlib_large_20260225_214331

现象:
- 所有实验 Best Score 从第 0 代开始即停滞, 无进一步提升。
- 所有实验分数始终为负数, 从未优于 FFD 基线。
- 实际有效种群数很小, 每岛 count 仅 2-3 (远小于 population_size)。

## 已定位的关键问题

1. 评分信号曾不一致 (已修复)
   - 沙箱评估器原先使用 "相对 FFD 的节省量" 作为 score, 与非沙箱的 "-avg_bins" 不一致。
   - 已修复: 沙箱评估器改为 score = -avg_bins, baseline_score 保留节省量。

2. 有效候选池过小, 搜索空间被过度收缩
   - 多样性阈值 + 功能级去重使大量候选被过滤。
   - 导致每代每岛实际可进化候选只有 2-3 个。

## 已做的改动 (代码)

1. 评分一致性修复
   - 文件: experiments/runner.py
   - 修改: SandboxBinPackingEvaluator/SandboxBenchmarkEvaluator 的 score 使用 -avg_bins

2. 多样性与 probe 调参入口
   - 文件: experiments/runner.py
   - 新增 evaluator 配置:
     - diversity_min_distance (默认 orlib: 0.05, random: 0.1)
     - probe_num_items (默认 orlib: 20, random: 8)

## 仍可能存在的问题 (原因假设)

1. 多样性过滤仍过强
   - 即便放宽到 0.05, 对 orlib/large 仍可能过于严格。
   - probe 的行为签名可能过于稳定, 导致不同代码得到相同签名。

2. Probe 分布与 OR-Library 分布差距大
   - probe 使用随机混合分布, 但 OR-Library 包含 u500/u1000 和 t249/t501 结构。
   - probe 可能未覆盖真实数据特性, 导致多样性判断不准确。

3. 候选生成多样性不足
   - LLM temperature=1.0 可能仍偏收敛。
   - 需要更高温度或引入多样化 prompt/variant。

4. 评分基线过强或目标函数难以超越
   - FFD 对 random/orlib 的表现可能已接近最佳, 导致 score 永远为负。
   - 即使评分改为 -avg_bins, 若 baseline 足够强也会出现“持续负值”。

5. 评估成本高导致每代候选减少
   - orlib/large full_eval 很重, 可能导致候选减少或被超时筛掉。

## 建议的改进方向

优先级 1: 扩大有效候选池
- 将 diversity_min_distance 降到 0.03 或更低。
- 将 probe_num_items 提升到 25-40, 增加区分度。
- 临时关闭 DiversityMaintainer 做对照试验。

优先级 2: 让 probe 更贴近数据分布
- 在 probe_runner 中增加固定 OR-Library 结构样本。
- 例如混合 u500/t249 的分布, 或从 data/orlib 抽样。

优先级 3: 增强候选多样性
- 提高 temperature (如 1.2-1.5)。
- 引入 variant B (Novelty prompting + enhanced diversity)。

优先级 4: 调整基线与目标函数
- 引入多基线对比 (FFD + BF) 或改为相对最优/下界的归一化评分。
- 将 score 定义为 -(avg_bins - lower_bound) 以提升可优化信号。

优先级 5: 降低评估成本
- 减少 full_eval 的 top_k 或缩小 full_eval 频率。
- 在 orlib/large 下先做 small 或 subset 试验快速验证。

## 推荐下一次试验配置

建议用 orlib/large 但放宽过滤, 同时改进评分信号:

- evaluator:
   type: orlib
   size: large
   diversity_min_distance: 0.03
   probe_num_items: 25
- (可选) 评分改为相对下界: score = -(avg_bins - lower_bound)
- 其余保持不变

运行命令:
python run.py --dataset orlib --size large --generations 6 --population 15 --islands 3 --yes

## 参考文件

- 最新试验报告: artifacts/funsearch_orlib_large_20260225_214331/report.md
- 历史试验报告: artifacts/funsearch_orlib_large_20260225_185132/report.md
- 评分修复与配置入口: experiments/runner.py
- 多样性逻辑: funsearch_core/diversity.py
- probe 逻辑: funsearch_core/deduplication.py
