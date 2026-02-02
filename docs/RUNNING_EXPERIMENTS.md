# Running & Comparing Experiments

This guide explains how to execute experiments using FunSearch-Lite and how to perform A/B testing to compare different strategies.

## Execution Methods

### 1. The `run.py` Wrapper (Recommended)
The `run.py` script provides a user-friendly interface for common experiment setups. It automatically handles `.env` loading and generates a temporary configuration.

```bash
# Basic run with default settings
python run.py

# Run on OR-Library large instances for 100 generations
python run.py --dataset orlib --size large --generations 100

# Demo mode (uses FakeProvider, no API key needed)
python run.py --demo
```

### 2. Direct CLI Usage
For full control, use the `experiments.cli` module with a YAML configuration file.

```bash
python -m experiments.cli run configs/binpacking_deepseek.yaml
```

## A/B Testing

FunSearch-Lite supports A/B testing via the `--variant` flag in the CLI. This allows you to run different versions of the algorithm (e.g., different prompts, selection strategies, or model configurations) and compare their performance.

### Running Variants
You can specify a variant name when running an experiment:

```bash
# Run variant A
python -m experiments.cli run configs/binpacking.yaml --variant a

# Run variant B
python -m experiments.cli run configs/binpacking.yaml --variant b
```

The system will append the variant name to the `run_id` and store results in separate artifact directories:
- `artifacts/binpacking_demo_001_variant_a/`
- `artifacts/binpacking_demo_001_variant_b/`

### Comparing Results
After running both variants, you can compare their evolution curves:

1.  **Visual Comparison**: Open the `plots/evolution.png` files from both artifact directories side-by-side.
2.  **Metric Comparison**: Use the `metrics.csv` files to perform statistical analysis (e.g., comparing the final best scores or the rate of convergence).
3.  **Code Comparison**: Use `export-best` to see if the variants discovered different types of heuristic logic.

## Resuming Experiments

If an experiment is interrupted, you can resume it from the last saved checkpoint (if `save_interval` was configured):

```bash
python -m experiments.cli resume <run_id>
```

*Note: Resume functionality is currently a placeholder and will be fully implemented in future versions.*

## Best Practices

1.  **Use Seeds**: Always specify a `seed` in your configuration to ensure reproducibility.
2.  **Start Small**: Run a quick test with `--generations 5 --population 10` before committing to a long-running experiment.
3.  **Monitor Real-time**: Use `tail -f artifacts/<run_id>/metrics.jsonl` to watch the progress.
4.  **Check Failures**: If the `n_failed` count is high, inspect the `candidates.db` to understand why the LLM is generating invalid code.
