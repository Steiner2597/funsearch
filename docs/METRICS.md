# Metrics Schema & Explanation

本文档描述当前 `artifacts/<run_id>/metrics.jsonl` 的真实字段口径（以 `funsearch_core.loop.FunSearchLoop` 输出为准）。

## 每代记录（Generation Record）

`metrics.jsonl` 每一行都是一个 generation 的 JSON 对象，核心结构如下：

| 字段 | 类型 | 说明 |
|---|---|---|
| `generation` | `int` | 代数（从 0 开始） |
| `timestamp` | `str` | UTC ISO 时间戳 |
| `islands` | `dict` | 各岛统计，键为岛索引 |
| `overall` | `dict` | 全局统计（count / best_score / avg_score） |
| `variant` | `str \| null` | 变体标记（当前可能为空） |
| `dedup` | `dict` | 去重统计（见下） |
| `dedup_skipped` | `int` | 当代 dedup 跳过数量（兼容字段） |
| `dedup_skipped_total` | `int` | 截止当代累计 dedup 跳过（兼容字段） |
| `funnel` | `dict` | 候选流量漏斗（P2 新增） |
| `effective_candidate_rate` | `float` | 有效候选率（P2 新增） |
| `timing` | `dict` | 评估与 LLM 耗时统计 |
| `failures` | `dict[str,int]` | 错误类型计数 |
| `llm` | `dict` | LLM 调用指标（若 provider 支持） |

## 关键子结构

### `dedup`

- `skipped`: 本代被功能去重过滤的候选数
- `skipped_total`: 累计被功能去重过滤的候选数

### `funnel`（P2）

- `generated`: 本代生成候选总数
- `dedup_rejected`: 被功能去重拒绝数量
- `after_dedup`: 去重后进入评估链路数量
- `diversity_rejected`: 被多样性维护拒绝入种群数量
- `cheap_eval_failed` / `cheap_eval_passed`: cheap 评估失败/成功
- `full_eval_attempted`: 进入 full 评估数量
- `full_eval_failed` / `full_eval_passed`: full 评估失败/成功
- `effective_candidate_rate`: `cheap_eval_passed / generated`

### `timing`

- `eval_ms_total`: 本代评估总耗时（ms）
- `eval_s_total`: 本代评估总耗时（s）
- `avg_eval_ms_per_outcome`: 平均每个评估 outcome 耗时（ms）
- `llm_s`: LLM 总耗时（s，仅 provider 提供指标时）

## 解读建议

- `funnel.generated` 高但 `effective_candidate_rate` 低：提示生成质量或执行稳定性问题。
- `dedup_rejected` 高：可能同质化严重，可尝试调高 `temperature`、切换 prompt 变体。
- `diversity_rejected` 高：说明种群相似度过高，可降低 `diversity_min_distance` 做对照。
- `eval_ms_total` 升高明显：优先检查 `full_eval_every_n_generations`、`orlib_subset` 设置。

## 示例

```json
{
  "generation": 2,
  "overall": {"count": 45, "best_score": -16.2, "avg_score": -18.4},
  "dedup": {"skipped": 8, "skipped_total": 21},
  "funnel": {
    "generated": 15,
    "dedup_rejected": 8,
    "after_dedup": 7,
    "diversity_rejected": 2,
    "cheap_eval_failed": 1,
    "cheap_eval_passed": 6,
    "full_eval_attempted": 3,
    "full_eval_failed": 0,
    "full_eval_passed": 3,
    "effective_candidate_rate": 0.4
  },
  "effective_candidate_rate": 0.4,
  "timing": {"eval_ms_total": 1420.5, "eval_s_total": 1.4205, "avg_eval_ms_per_outcome": 157.8}
}
```
