# FunSearch Experiment Report

## Run Summary
- **Run ID:** funsearch_orlib_small_20260201_224833
- **Date:** 2026-02-02 01:18:50
- **Task:** bin_packing
- **Dataset:** N/A

## Key Performance Indicators
| Metric | Value | Note |
|--------|-------|------|
| Best Score | -43.8 | Higher = better (negated bins) |
| Unique Rate | 73.17% | |
| Generations to Best | 8 | |
| Final Diversity | 13 | |

## Evolution Analysis
- **Starting Best Score:** -54.85
- **Ending Best Score:** -43.8
- **Improvement:** 11.0500

## Per-Island Performance
| Island ID | Best Score | Avg Score | Count |
|-----------|------------|-----------|-------|
| 0 | -43.8000 | -70.7500 | 8 |
| 1 | -54.8500 | -58.7583 | 3 |
| 2 | -54.8625 | -62.0312 | 2 |

## Deduplication Statistics
- **Total Candidates Attempted:** 600
- **Duplicates Skipped:** 161
- **Deduplication Efficiency:** 26.83%

## Configuration
```yaml
artifact_dir: artifacts
batch_timeout_s: 30.0
evaluator:
  capacity: 100
  seed: 42
  size: small
  type: orlib
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
max_generations: 20
num_islands: 3
population_size: 10
refiner_provider_id: main_provider
resume_from: null
run_id: funsearch_orlib_small_20260201_224833
sandbox_memory_limit_mb: 256
sandbox_timeout_s: 5.0
save_interval: 5
seed: 42
task_name: bin_packing
top_k_for_full_eval: 5
variant: null

```
