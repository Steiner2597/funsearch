# FunSearch Experiment Report

## Run Summary
- **Run ID:** funsearch_orlib_large_20260225_185132
- **Date:** 2026-02-25 20:12:00
- **Task:** bin_packing
- **Dataset:** N/A

## Key Performance Indicators
| Metric | Value | Note |
|--------|-------|------|
| Best Score | 0.0 | Higher = better (negated bins) |
| Unique Rate | 83.96% | |
| Generations to Best | 0 | |
| Final Diversity | 14 | |

## Evolution Analysis
- **Starting Best Score:** 0.0
- **Ending Best Score:** 0.0
- **Improvement:** 0.0000

## Per-Island Performance
| Island ID | Best Score | Avg Score | Count |
|-----------|------------|-----------|-------|
| 0 | 0.0000 | -4.2000 | 5 |
| 1 | 0.0000 | -383.6667 | 3 |
| 2 | 0.0000 | -470.0000 | 6 |

## Deduplication Statistics
- **Total Candidates Attempted:** 480
- **Duplicates Skipped:** 77
- **Deduplication Efficiency:** 16.04%

## Configuration
```yaml
artifact_dir: artifacts
batch_timeout_s: 30.0
evaluator:
  capacity: 100
  seed: 42
  size: large
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
max_generations: 8
num_islands: 3
population_size: 20
refiner_provider_id: main_provider
resume_from: null
run_id: funsearch_orlib_large_20260225_185132
sandbox_memory_limit_mb: 256
sandbox_timeout_s: 5.0
save_interval: 5
seed: 42
task_name: bin_packing
top_k_for_full_eval: 5
variant: null

```
