# FunSearch Experiment Report

## Run Summary
- **Run ID:** funsearch_random_small_20260202_024429
- **Date:** 2026-02-02 03:10:13
- **Task:** bin_packing
- **Dataset:** N/A

## Key Performance Indicators
| Metric | Value | Note |
|--------|-------|------|
| Best Score | 0.0 | Higher = better (negated bins) |
| Unique Rate | 72.00% | |
| Generations to Best | 0 | |
| Final Diversity | 3 | |

## Evolution Analysis
- **Starting Best Score:** 0.0
- **Ending Best Score:** 0.0
- **Improvement:** 0.0000

## Per-Island Performance
| Island ID | Best Score | Avg Score | Count |
|-----------|------------|-----------|-------|
| 0 | 0.0000 | 0.0000 | 1 |
| 1 | 0.0000 | 0.0000 | 1 |
| 2 | 0.0000 | 0.0000 | 1 |

## Deduplication Statistics
- **Total Candidates Attempted:** 150
- **Duplicates Skipped:** 42
- **Deduplication Efficiency:** 28.00%

## Configuration
```yaml
artifact_dir: artifacts
batch_timeout_s: 30.0
evaluator:
  capacity: 100
  seed: 42
  size: small
  type: random
  use_sandbox: true
generator_provider_id: main_provider
llm_providers:
- base_url: https://api.deepseek.com
  max_retries: 3
  max_tokens: 2000
  model_name: deepseek-chat
  provider_id: main_provider
  provider_type: deepseek
  temperature: 1.0
  timeout_seconds: 60
max_generations: 5
num_islands: 3
population_size: 10
refiner_provider_id: main_provider
resume_from: null
run_id: funsearch_random_small_20260202_024429
sandbox_memory_limit_mb: 256
sandbox_timeout_s: 5.0
save_interval: 5
seed: 42
task_name: bin_packing
top_k_for_full_eval: 5
variant: null

```
