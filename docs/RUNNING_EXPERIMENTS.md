# Running & Comparing Experiments

本文档给出当前项目可复现的运行方式，以及 P1/P2 相关参数的建议用法。

## 1) 快速启动（推荐）

使用 `run.py`：

```bash
python run.py --demo
python run.py --dataset orlib --size large --generations 6 --population 15 --islands 3
```

### 常用参数

- 基础：`--dataset` `--size` `--generations` `--population` `--islands` `--seed`
- LLM/探索：`--temperature` `--variant`
- 去重/多样性：`--probe-num-items` `--probe-mode` `--diversity-min-distance` `--disable-diversity`
- 多保真评估：`--top-k-full-eval` `--full-eval-every` `--orlib-subset`
- 评分：`--score-mode raw_bins|gap_to_lb`
- 运行模式：`--demo`（FakeProvider，不消耗 API）

> 运行后会在 `artifacts/<run_id>/` 产出 `config.yaml`、`metrics.jsonl`、`report.md`、`report.html` 等文件。

## 2) 直接 CLI 运行

```bash
python -m experiments.cli run configs/binpacking_deepseek.yaml --variant b
```

可选值：`--variant a|b|both`（大小写不敏感）。

## 3) 报告与对比

生成报告：

```bash
python -m experiments.cli report <run_id>
```

对比多个 run：

```bash
python -m experiments.cli compare run_id_1 run_id_2 --artifact-dir artifacts --output-dir .
```

## 4) 最小对照实验建议

建议一次只改 1 个变量，避免结论混淆：

1. `enable_diversity`: on/off（通过 `--disable-diversity` 反转）
2. `temperature`: 1.0 vs 1.3
3. `probe_mode`: `random` vs `orlib`
4. `score_mode`: `raw_bins` vs `gap_to_lb`

每组建议至少 2 个不同 `seed` 重复。

## 5) 结果判读（P2）

优先看 `report.md` 的 `Candidate Flow Funnel`：

- `generated -> dedup_rejected`：同质化是否严重
- `after_dedup -> cheap_eval_passed`：候选可执行性/有效性
- `effective_candidate_rate`：本代有效候选产出效率
- `timing.eval_ms_total`：单代评估耗时

若 `effective_candidate_rate` 长期偏低，可按顺序尝试：

1. 提高 `temperature`
2. 切换 `variant`（如 `b`）
3. 调整 `probe_mode` 与 `probe_num_items`
4. 降低 `diversity_min_distance`（并做对照）
