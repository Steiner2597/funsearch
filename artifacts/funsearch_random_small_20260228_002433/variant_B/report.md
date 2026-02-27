# FunSearch Experiment Report

## Run Summary
- **Run ID:** funsearch_random_small_20260228_002433
- **Date:** 2026-02-28 00:24:38
- **Task:** bin_packing
- **Dataset:** N/A

## Key Performance Indicators
| Metric | Value | Note |
|--------|-------|------|
| Best Score | -0.5 | Higher = better (negated bins) |
| Unique Rate | 5.56% | |
| Generations to Best | 0 | |
| Final Diversity | 30 | |

## Evolution Analysis
- **Starting Best Score:** -0.5
- **Ending Best Score:** -0.5
- **Improvement:** 0.0000

## Per-Island Performance
| Island ID | Best Score | Avg Score | Count |
|-----------|------------|-----------|-------|
| 0 | -0.5000 | -0.5000 | 10 |
| 1 | -0.5000 | -0.5000 | 10 |
| 2 | N/A | N/A | 10 |

## Deduplication Statistics
- **Total Candidates Attempted:** 180
- **Duplicates Skipped:** 170
- **Deduplication Efficiency:** 94.44%

## Configuration
```yaml
artifact_dir: artifacts
batch_timeout_s: 30.0
evaluator:
  capacity: 100
  enable_diversity: false
  full_eval_every_n_generations: 2
  probe_mode: random
  score_mode: gap_to_lb
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
max_generations: 6
num_islands: 3
population_size: 10
refiner_provider_id: main_provider
resume_from: null
run_id: funsearch_random_small_20260228_002433
sandbox_memory_limit_mb: 256
sandbox_timeout_s: 5.0
save_interval: 5
seed: 42
task_name: bin_packing
top_k_for_full_eval: 3
variant: b

```
