# FunSearch Experiment Report

## Run Summary
- **Run ID:** funsearch_random_small_20260202_024032
- **Date:** 2026-02-02 02:40:37
- **Task:** bin_packing
- **Dataset:** N/A

## Key Performance Indicators
| Metric | Value | Note |
|--------|-------|------|
| Best Score | -1.0 | Higher = better (negated bins) |
| Unique Rate | 88.89% | |
| Generations to Best | 0 | |
| Final Diversity | 3 | |

## Evolution Analysis
- **Starting Best Score:** -1.0
- **Ending Best Score:** -1.0
- **Improvement:** 0.0000

## Per-Island Performance
| Island ID | Best Score | Avg Score | Count |
|-----------|------------|-----------|-------|
| 0 | -1.0000 | -1.0000 | 1 |
| 1 | -1.0000 | -1.0000 | 1 |
| 2 | N/A | N/A | 1 |

## Deduplication Statistics
- **Total Candidates Attempted:** 9
- **Duplicates Skipped:** 1
- **Deduplication Efficiency:** 11.11%

## Configuration
```yaml
artifact_dir: artifacts
batch_timeout_s: 30.0
evaluator:
  capacity: 100
  seed: 42
  size: small
  type: random
  use_sandbox: false
generator_provider_id: main_provider
llm_providers:
- max_retries: 3
  max_tokens: 2000
  model_name: fake-model
  provider_id: main_provider
  provider_type: fake
  temperature: 1.0
  timeout_seconds: 60
max_generations: 1
num_islands: 3
population_size: 3
refiner_provider_id: main_provider
resume_from: null
run_id: funsearch_random_small_20260202_024032
sandbox_memory_limit_mb: 256
sandbox_timeout_s: 5.0
save_interval: 5
seed: 42
task_name: bin_packing
top_k_for_full_eval: 5
variant: null

```
