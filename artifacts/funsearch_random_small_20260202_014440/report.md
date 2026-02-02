# FunSearch Experiment Report

## Run Summary
- **Run ID:** funsearch_random_small_20260202_014440
- **Date:** 2026-02-02 01:44:48
- **Task:** bin_packing
- **Dataset:** N/A

## Key Performance Indicators
| Metric | Value | Note |
|--------|-------|------|
| Best Score | -1.0 | Higher = better (negated bins) |
| Unique Rate | 11.11% | |
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
| 1 | N/A | N/A | 1 |
| 2 | N/A | N/A | 1 |

## Deduplication Statistics
- **Total Candidates Attempted:** 90
- **Duplicates Skipped:** 80
- **Deduplication Efficiency:** 88.89%

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
max_generations: 2
num_islands: 3
population_size: 15
refiner_provider_id: main_provider
resume_from: null
run_id: funsearch_random_small_20260202_014440
sandbox_memory_limit_mb: 256
sandbox_timeout_s: 5.0
save_interval: 5
seed: 42
task_name: bin_packing
top_k_for_full_eval: 5
variant: null

```
