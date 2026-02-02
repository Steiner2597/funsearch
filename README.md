# FunSearch-Lite

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Tests Passing](https://img.shields.io/badge/tests-passing-brightgreen.svg)](tests/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**FunSearch-Lite** is an evolutionary search system guided by Large Language Models (LLMs) for automated discovery and optimization of algorithmic heuristics. This project is a streamlined implementation of Google DeepMind's [FunSearch](https://deepmind.google/discover/blog/funsearch-making-new-discoveries-in-mathematical-sciences-using-large-language-models/), specifically designed for AI course projects and research prototyping.

**FunSearch-Lite** 是一个基于大语言模型(LLM)的进化搜索系统，用于自动发现和优化算法启发式函数。本项目是对 Google DeepMind [FunSearch](https://deepmind.google/discover/blog/funsearch-making-new-discoveries-in-mathematical-sciences-using-large-language-models/) 论文的精简实现，专为 AI 课程项目设计。

---

## 🚀 Key Innovations | 核心特性

### 1. Multi-Fidelity Evaluation | 多保真度评估
- **Cheap Eval**: Rapidly filter all candidates using a small set of test instances.
- **Full Eval**: Precisely evaluate only the Top-K candidates using the complete benchmark.
- **Impact**: Significantly reduces evaluation costs while maintaining search quality.

### 2. Multi-Model Collaboration | 多模型协作
- **Generator Model**: Use cost-effective models (e.g., DeepSeek-Chat, GPT-3.5) for bulk candidate generation.
- **Refiner Model**: Use powerful models (e.g., GPT-4) to optimize Top-K candidates.
- **Impact**: Balances search breadth with optimization depth.

### 3. Standard Benchmark Support | 标准基准支持
- **OR-Library**: Built-in support for OR-Library Bin Packing instances (Falkenauer u* and t*).
- **Comparability**: Directly compare results with academic literature.

### 4. Search Trajectory Observability | 搜索可观测性
- **Real-time Progress**: `tqdm` integration showing generation progress and ETA.
- **Metric Tracking**: Best/average scores per generation and failure taxonomy.
- **Visualization**: Automated generation of evolution curves and failure distribution charts.

### 5. Sandbox Safe Execution | 沙箱安全执行
- **Process Isolation**: LLM-generated code runs in isolated sub-processes.
- **Resource Limits**: Timeout protection and import whitelisting (math, random, etc.).
- **Impact**: Prevents accidental or malicious code from compromising the host system.

---

## 🛠️ Quick Start | 快速开始

### Installation | 安装

```bash
# Install in editable mode
pip install -e .

# Or install dependencies manually
pip install pydantic pyyaml typer matplotlib openai tqdm
```

### Run Experiments | 运行实验

**Recommended: Using the `run.py` wrapper**

```bash
# 1. Set up API Key (once)
echo "DEEPSEEK_API_KEY=sk-xxx" > .env

# 2. Launch with one command
python run.py                     # Default (Random dataset)
python run.py -d orlib             # Use OR-Library dataset
python run.py -d orlib -s large    # OR-Library large instances
python run.py --demo               # Demo mode (No API Key required)
python run.py -g 3 -p 3 -y         # Quick test (~5 mins)
```

**Advanced: Using the CLI**

```bash
# Run with specific config and A/B variant
python -m experiments.cli run configs/binpacking_deepseek.yaml --variant a
```

---

## 🏗️ System Architecture | 系统架构

```text
┌─────────────────────────────────────────────────────────────┐
│                     Experiment Runner                       │
│  (Config / Artifacts / Metrics / Plotting / Progress)       │
└──────────────────┬──────────────────────────────────────────┘
                   │
          ┌────────▼─────────┐
          │  FunSearchLoop   │  ← Main Evolution Loop (tqdm)
          │  + GlobalProgress│
          └────────┬─────────┘
                   │
     ┌─────────────┼─────────────┐
     │             │             │
┌────▼─────┐  ┌───▼────┐  ┌────▼─────┐
│   LLM    │  │ Sandbox│  │Evaluator │
│Providers │  │Executor│  │(Multi-   │
│(DeepSeek/│  │(Safety)│  │Fidelity) │
│ OpenAI)  │  └────────┘  └──────────┘
└──────────┘      │             │
     │            │       ┌─────▼─────┐
┌────▼─────┐      └──────►│ Candidate │
│LLM Cache │              │   Store     │
│(Cost Red)│              └─────┬─────┘
└──────────┘                    │
                          ┌─────▼─────┐
                          │ OR-Library│
                          │ Datasets  │
                          └───────────┘
```

---

## 📂 Project Structure | 项目结构

```text
funsearch/
├── run.py                   # Unified entry point (Recommended)
├── funsearch_core/          # Core evolutionary algorithm
│   ├── loop.py              # Main loop with tqdm progress
│   ├── population.py        # Population management
│   └── deduplication.py     # Functional deduplication (AST-based)
├── evaluator/               # Problem-specific evaluation
│   ├── bin_packing.py       # Bin Packing implementation
│   └── datasets.py          # OR-Library loader
├── llm/                     # LLM integration layer
│   ├── providers.py         # Multi-provider support (DeepSeek/OpenAI)
│   └── cache.py             # SQLite-based response caching
├── sandbox/                 # Secure execution environment
│   ├── executor.py          # Subprocess isolation
│   └── policy.py            # Resource & import limits
├── experiments/             # Experiment orchestration
│   ├── cli.py               # Typer-based CLI
│   ├── metrics.py           # KPI collection
│   └── plotting.py          # Matplotlib visualizations
├── artifacts/               # Experiment outputs (Auto-generated)
├── configs/                 # YAML configuration files
└── docs/                    # Detailed documentation
```

---

## 📊 A/B Testing & Metrics | 实验与指标

### A/B Testing
Use the `--variant` flag to compare different strategies (e.g., different prompts or selection logic):
```bash
python -m experiments.cli run configs/binpacking.yaml --variant a
python -m experiments.cli run configs/binpacking.yaml --variant b
```

### Report Generation
Generate comprehensive reports after runs complete:
```bash
python -m experiments.cli report artifacts/run_20250131_120000
python -m experiments.cli report artifacts/run_20250131_120000 --format html
```

Output includes:
- `report.md`: Markdown summary with key metrics and evolution analysis
- `report.html`: Self-contained HTML with embedded charts

See [docs/READING_REPORTS.md](docs/READING_REPORTS.md) for interpretation guidance.

### Run Comparison
Compare two runs (e.g., A/B variants):
```bash
python -m experiments.cli compare artifacts/run_A artifacts/run_B
python -m experiments.cli compare artifacts/run_A artifacts/run_B --output comparison.md
```

### Key Performance Indicators (KPIs)
- **Best Score**: The highest fitness achieved in the population.
- **Pass Rate**: Percentage of LLM-generated candidates that pass syntax and runtime checks.
- **Diversity Index**: Measure of functional uniqueness in the population.
- **Evaluation Efficiency**: Ratio of cheap vs. full evaluations.

---

## 📦 Output Artifacts | 实验产出

Each run generates a dedicated folder in `artifacts/`:
- `config.yaml`: Snapshot of the experiment configuration.
- `candidates.db`: SQLite database containing all generated programs and scores.
- `metrics.jsonl`: Time-series data of all KPIs.
- `best_candidate.py`: The best performing heuristic function found.
- `plots/`: Evolution curves and failure distribution charts.

---

## 📈 Performance Benchmarks | 性能基准

| Dataset | Instances | Best Known | FunSearch-Lite | Gap | Time |
|---------|-----------|------------|----------------|-----|------|
| OR-Lib Small | 80 | 3921 (Total) | 3945 | +0.6% | 4h |
| OR-Lib Large | 80 | 12450 (Total) | 12580 | +1.0% | 8h |
| Random Small | 100 | N/A | -12.4 (Avg) | N/A | 1h |

*Note: Benchmarks are placeholders and vary based on LLM model and search budget.*

---

## 🤝 Contributing | 贡献指南

1. **Add New Tasks**: Implement `BaseEvaluator` in `evaluator/`.
2. **Improve LLM Prompts**: Modify templates in `llm/prompts.py`.
3. **Optimize Search**: Experiment with new selection or mutation strategies in `funsearch_core/`.

---

## 🎓 Academic Context | 学术背景

This project was developed as part of the AI Course at [Your University]. It demonstrates:
1. **Program Synthesis**: Using LLMs to write executable code.
2. **Evolutionary Computation**: Population-based search and diversity maintenance.
3. **System Observability**: Building transparent AI search processes.

**Attribution**: Based on the methodology described in *Romera-Paredes, B. et al. "Mathematical discoveries from program search with large language models." Nature (2023).*

---

## 📜 License

MIT License. See [LICENSE](LICENSE) for details.
