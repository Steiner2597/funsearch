# Usage Guide (使用指南)

本文档提供 FunSearch-Lite 的详细使用说明，包括安装、配置、运行实验和结果分析。

## 目录

1. [安装](#1-安装)
2. [快速开始](#2-快速开始)
3. [配置详解](#3-配置详解)
4. [运行实验](#4-运行实验)
5. [结果分析](#5-结果分析)
6. [标准数据集](#6-标准数据集)
7. [高级用法](#7-高级用法)
8. [故障排除](#8-故障排除)

---

## 1. 安装

### 1.1 系统要求

- **Python**: 3.10 或更高
- **操作系统**: Linux, macOS, Windows
- **内存**: 至少 2GB RAM
- **磁盘**: 至少 500MB 可用空间

### 1.2 克隆项目

```bash
# 假设项目已在当前目录
cd /path/to/funsearch
```

### 1.3 创建虚拟环境 (推荐)

```bash
# 使用 venv
python -m venv venv
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate   # Windows

# 或使用 conda
conda create -n funsearch python=3.10
conda activate funsearch
```

### 1.4 安装依赖

```bash
# 方式 1: 使用 pip (可编辑模式)
pip install -e .

# 方式 2: 手动安装依赖
pip install pydantic pyyaml typer matplotlib openai tqdm
```

### 1.5 验证安装

```bash
# 运行测试套件
python -m pytest tests/ -v

# 检查 CLI
python -m experiments.cli --help
```

预期输出:
```
48 passed, 1 skipped  # openai 包未安装时跳过 1 个测试
```

---

## 2. 快速开始

### 2.1 运行演示实验 (FakeProvider)

无需 API key，使用内置的 FakeProvider:

```bash
python -m experiments.cli run configs/binpacking.yaml
```

预期输出:
```
🚀 Starting experiment: binpacking_demo_001
   Max generations: 20
   Population size: 50
   Islands: 3
   Task: bin_packing

==================================================
  FunSearch Evolution Started
==================================================

🧬 Evolution:  10%|████                          | 5/50 [00:32<04:52]
  🔥 NEW BEST! Score: 42.5000

==================================================
  Completed 50 generations
  Best Score: 42.5000
==================================================
```

### 2.2 使用 DeepSeek API (推荐)

DeepSeek 提供性价比很高的 API 服务:

**方式一：使用启动脚本 (推荐)**

```bash
# 创建 .env 文件 (只需一次，API Key 会自动加载)
echo "DEEPSEEK_API_KEY=sk-xxx" > .env

# 启动实验
python run.py                        # 默认配置
python run.py -d orlib -s large      # OR-Library 大型数据集
python run.py -g 3 -p 3 -y           # 快速测试 (~5分钟)
python run.py --help                 # 查看所有选项
```

**方式二：手动设置环境变量**

```bash
# Linux/macOS:
export DEEPSEEK_API_KEY="sk-..."

# Windows PowerShell:
$env:DEEPSEEK_API_KEY = "sk-..."

# 运行实验
python -m experiments.cli run configs/binpacking_deepseek.yaml
```

### 2.3 使用 OpenAI API

```bash
# 设置环境变量
export OPENAI_API_KEY="sk-..."

# 修改配置文件使用 OpenAI
cp configs/binpacking.yaml configs/my_experiment.yaml
# 编辑 my_experiment.yaml, 将 provider_type 改为 "openai"

# 运行实验
python -m experiments.cli run configs/my_experiment.yaml
```

### 2.4 查看结果

```bash
# 列出所有实验
python -m experiments.cli list-runs

# 导出最佳候选
python -m experiments.cli export-best binpacking_deepseek_002

# 查看导出的代码
cat artifacts/binpacking_deepseek_002/best_candidate.py

# 查看可视化
ls artifacts/binpacking_deepseek_002/plots/
```

---

## 3. 配置详解

### 3.1 配置文件结构

配置文件使用 YAML 格式，位于 `configs/` 目录。

**DeepSeek 配置示例** (`configs/binpacking_deepseek.yaml`):

```yaml
# ============== 实验标识 ==============
run_id: "binpacking_deepseek_002"
seed: 42

# ============== 搜索参数 ==============
max_generations: 50
population_size: 15
num_islands: 3
top_k_for_full_eval: 5

# ============== 问题定义 ==============
task_name: "bin_packing"

evaluator:
  # 数据集类型: "random" (随机生成) 或 "orlib" (OR-Library)
  type: "random"
  # 实例大小: "small" 或 "large"
  size: "small"
  capacity: 100
  seed: 42

# ============== LLM 提供者 ==============
llm_providers:
  - provider_id: "deepseek_generator"
    provider_type: "deepseek"
    model_name: "deepseek-chat"
    base_url: "https://api.deepseek.com"
    max_retries: 3
    timeout_seconds: 60
    temperature: 1.0
    max_tokens: 2000

generator_provider_id: "deepseek_generator"
refiner_provider_id: "deepseek_generator"

# ============== 输出配置 ==============
artifact_dir: "artifacts"
save_interval: 5
```

### 3.2 数据集选项

| 配置 | 命令行 | 说明 |
|------|--------|------|
| `type: "random"` + `size: "small"` | `python run.py` | 5-10个物品，快速测试 |
| `type: "random"` + `size: "large"` | `python run.py -s large` | 50-100个物品，更真实 |
| `type: "orlib"` + `size: "small"` | `python run.py -d orlib` | OR-Library binpack1-4 (80实例) |
| `type: "orlib"` + `size: "large"` | `python run.py -d orlib -s large` | OR-Library binpack5-8 (80实例) |

### 3.3 关键参数说明

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `run_id` | string | (必需) | 实验唯一标识，用作工件目录名 |
| `seed` | int | (推荐) | 随机种子，确保可重现性 |
| `max_generations` | int | 20 | 运行的代数 |
| `population_size` | int | 50 | 每代生成的候选数量 |
| `num_islands` | int | 3 | 多岛模型的岛屿数 (1 = 单岛) |
| `top_k_for_full_eval` | int | 10 | 仅对最优 K 个候选执行完整评估 |
| `task_name` | string | "bin_packing" | 任务名称 (必须匹配评估器) |
| `evaluator.type` | string | "random" | 数据集类型: "random" 或 "orlib" |
| `evaluator.size` | string | "small" | 实例大小: "small" 或 "large" |
| `generator_provider_id` | string | (必需) | 生成器 LLM ID |
| `refiner_provider_id` | string | (可选) | 精炼器 LLM ID (可与生成器相同) |

### 3.4 配置多个 LLM 提供者 (多模型协作)

```yaml
llm_providers:
  # 廉价生成器 (用于批量生成)
  - provider_id: "cheap_gen"
    provider_type: "openai"
    model_name: "gpt-3.5-turbo"
    temperature: 0.8
    max_retries: 3
  
  # 强大精炼器 (用于优化 Top-K)
  - provider_id: "strong_refine"
    provider_type: "openai"
    model_name: "gpt-4"
    temperature: 0.3
    max_retries: 5

# 分配不同模型给不同阶段
generator_provider_id: "cheap_gen"
refiner_provider_id: "strong_refine"
```

### 3.4 调整搜索强度

**快速测试 (5分钟)**:
```yaml
max_generations: 10
population_size: 20
top_k_for_full_eval: 5
```

**标准搜索 (30分钟)**:
```yaml
max_generations: 50
population_size: 50
top_k_for_full_eval: 10
```

**深度搜索 (2小时)**:
```yaml
max_generations: 200
population_size: 100
top_k_for_full_eval: 20
```

---

## 4. 运行实验

### 4.1 命令行界面

FunSearch-Lite 提供 4 个主要命令:

```bash
python3 -m experiments.cli [COMMAND] [OPTIONS]
```

#### 命令 1: `run` - 运行实验

```bash
python3 -m experiments.cli run <config_file>
```

**示例**:
```bash
python3 -m experiments.cli run configs/binpacking.yaml
```

**选项**:
- 暂无额外选项 (所有配置通过 YAML 文件指定)

#### 命令 2: `list-runs` - 列出所有实验

```bash
python3 -m experiments.cli list-runs
```

**输出示例**:
```
Run ID                   | Status    | Generations | Best Score
-------------------------|-----------|-------------|------------
binpacking_demo_001      | completed | 20          | -10.5
my_experiment_002        | completed | 50          | -9.2
test_run_003             | incomplete| 15          | -12.1
```

#### 命令 3: `export-best` - 导出最佳候选

```bash
python3 -m experiments.cli export-best <run_id>
```

**示例**:
```bash
python3 -m experiments.cli export-best binpacking_demo_001
```

**输出**:
```
Best candidate exported to: artifacts/binpacking_demo_001/best_candidate.py
Score: -10.5
```

**导出文件内容** (`best_candidate.py`):
```python
"""
Best candidate from run: binpacking_demo_001
Score: -10.5
Generated at: 2024-01-15 10:45:00
"""

def score_bin(item_size: int, remaining_capacity: int, bin_index: int, step: int) -> float:
    """LLM 生成的启发式函数"""
    # ... 自动生成的代码 ...
    return score
```

#### 命令 4: `resume` - 恢复中断的实验

```bash
python3 -m experiments.cli resume <run_id>
```

**用途**: 从最后保存的检查点恢复实验 (需要在配置中设置 `save_interval`)

### 4.2 工件目录结构

每次运行会在 `artifacts/<run_id>/` 创建以下文件:

```
artifacts/binpacking_demo_001/
├── config.yaml              # 配置快照 (实验的完整配置)
├── candidates.db            # SQLite 数据库 (所有候选)
├── llm_cache.db             # LLM 响应缓存 (降低重复成本)
├── metrics.jsonl            # 每代指标 (JSONL 格式, 逐行追加)
├── metrics.csv              # 指标 CSV 版本 (便于分析)
├── best_candidate.py        # 导出的最佳候选代码
└── plots/
    ├── evolution.png        # 进化曲线图
    └── failures.png         # 失败分布饼图
```

### 4.3 实时监控

实验运行时，可以在另一个终端实时监控:

```bash
# 实时查看指标
tail -f artifacts/binpacking_demo_001/metrics.jsonl

# 查询当前最佳分数
sqlite3 artifacts/binpacking_demo_001/candidates.db \
  "SELECT MAX(score) FROM candidates WHERE score IS NOT NULL;"

# 统计有效候选数
sqlite3 artifacts/binpacking_demo_001/candidates.db \
  "SELECT COUNT(*) FROM candidates WHERE score IS NOT NULL;"
```

---

## 5. 结果分析

### 5.1 查看指标文件

**JSONL 格式** (每代一行):
```bash
cat artifacts/binpacking_demo_001/metrics.jsonl | jq .
```

**示例输出**:
```json
{
  "generation": 0,
  "best_score": -15.2,
  "avg_score": -18.7,
  "top_k_avg_score": -16.1,
  "num_candidates": 50,
  "num_valid": 45,
  "failure_counts": {"syntax": 3, "timeout": 2},
  "timestamp": "2024-01-15T10:30:00"
}
```

**CSV 格式** (便于 Excel/Pandas):
```bash
cat artifacts/binpacking_demo_001/metrics.csv | head
```

### 5.2 分析可视化图表

#### 进化曲线 (`plots/evolution.png`)

显示 4 条曲线:
1. **Best Score** (蓝色): 每代最佳分数
2. **Avg Score** (橙色): 每代平均分数
3. **Top-K Avg** (绿色): Top-K 候选平均分数
4. **Valid Candidates** (红色): 有效候选数量

**健康搜索的特征**:
- Best Score 持续上升 (越来越接近 0)
- Avg Score 跟随上升
- Valid Candidates 保持稳定或增加

**问题信号**:
- Best Score 长时间停滞 → 可能陷入局部最优
- Avg Score 远低于 Best Score → 大部分候选质量差
- Valid Candidates 快速下降 → LLM 生成失败率高

#### 失败分布 (`plots/failures.png`)

饼图显示各类失败的占比:
- **Syntax Error**: 语法错误 → Prompt 需要更明确的格式要求
- **Import Blocked**: 导入被阻止 → LLM 尝试使用不安全的模块
- **Runtime Error**: 运行时错误 → 逻辑错误或边界条件未处理
- **Timeout**: 超时 → 生成的代码效率低

### 5.3 分析 SQLite 数据库

#### 查询最佳候选

```sql
-- 查询历史最佳
SELECT id, score, generation, provider_id 
FROM candidates 
WHERE score IS NOT NULL 
ORDER BY score DESC 
LIMIT 10;

-- 查询特定代数的候选
SELECT id, score 
FROM candidates 
WHERE generation = 10 
ORDER BY score DESC;

-- 统计每代有效候选数
SELECT generation, COUNT(*) as count 
FROM candidates 
WHERE score IS NOT NULL 
GROUP BY generation;
```

#### 查询失败统计

```sql
-- 统计失败类型
SELECT 
  json_extract(metadata, '$.failure_type') as failure_type,
  COUNT(*) as count
FROM candidates
WHERE score IS NULL
GROUP BY failure_type;
```

### 5.4 比较不同实验

```bash
# 对比两个实验的最佳分数
sqlite3 artifacts/exp1/candidates.db "SELECT MAX(score) as exp1_best FROM candidates;" &
sqlite3 artifacts/exp2/candidates.db "SELECT MAX(score) as exp2_best FROM candidates;"

# 合并多个实验的指标
cat artifacts/exp1/metrics.csv > comparison.csv
tail -n +2 artifacts/exp2/metrics.csv >> comparison.csv
tail -n +2 artifacts/exp3/metrics.csv >> comparison.csv
```

---

## 6. 高级用法

### 6.1 自定义问题

要添加新问题 (如 TSP 旅行商问题):

**步骤 1**: 实现评估器

```python
# evaluator/tsp.py
from evaluator.base import BaseEvaluator, EvalResult, Candidate

class TSPEvaluator(BaseEvaluator):
    def __init__(self, num_cities: int, seed: int):
        self.num_cities = num_cities
        self.seed = seed
    
    def cheap_eval(self, candidate: Candidate) -> EvalResult:
        # 小规模评估 (10 个城市)
        score = self._evaluate_on_instances(candidate, n=10)
        return EvalResult(score=score, metadata={"fidelity": "cheap"})
    
    def full_eval(self, candidate: Candidate) -> EvalResult:
        # 完整评估 (50 个城市)
        score = self._evaluate_on_instances(candidate, n=50)
        return EvalResult(score=score, metadata={"fidelity": "full"})
```

**步骤 2**: 注册评估器

```python
# experiments/runner.py
from evaluator.tsp import TSPEvaluator

def _create_evaluator(config: RunConfig) -> BaseEvaluator:
    if config.task_name == "bin_packing":
        return BinPackingEvaluator(...)
    elif config.task_name == "tsp":
        return TSPEvaluator(...)
    else:
        raise ValueError(f"Unknown task: {config.task_name}")
```

**步骤 3**: 创建配置

```yaml
# configs/tsp.yaml
run_id: "tsp_experiment_001"
task_name: "tsp"
evaluator:
  num_cities: 50
  seed: 42
# ... 其他配置 ...
```

### 6.2 自定义 LLM 提供者

实现 `BaseLLMProvider` 接口:

```python
# llm/custom_provider.py
from llm.base import BaseLLMProvider

class CustomProvider(BaseLLMProvider):
    def __init__(self, provider_id: str, api_key: str, model_name: str):
        self.provider_id = provider_id
        self.api_key = api_key
        self.model_name = model_name
    
    def generate(self, *, temperature: float, seed: int | None = None) -> str:
        # 调用自定义 API
        response = my_api_call(...)
        return response.code
    
    def mutate(self, *, parent_code: str, temperature: float, seed: int | None = None) -> str:
        # 变异逻辑
        pass
    
    def refine(self, *, candidate_code: str, temperature: float, seed: int | None = None) -> str:
        # 精炼逻辑
        pass
```

### 6.3 批量运行实验

```bash
#!/bin/bash
# run_experiments.sh

for seed in 42 43 44 45 46; do
  # 创建配置副本
  cp configs/binpacking.yaml configs/temp_${seed}.yaml
  
  # 修改 run_id 和 seed
  sed -i "s/run_id: .*/run_id: \"binpacking_seed_${seed}\"/" configs/temp_${seed}.yaml
  sed -i "s/seed: .*/seed: ${seed}/" configs/temp_${seed}.yaml
  
  # 运行实验
  python -m experiments.cli run configs/temp_${seed}.yaml
  
  # 清理临时配置
  rm configs/temp_${seed}.yaml
done

echo "All experiments complete!"
```

### 6.4 Python API (直接调用)

```python
from experiments.runner import ExperimentRunner
from experiments.config import load_config

# 加载配置
config = load_config("configs/binpacking.yaml")

# 运行实验
runner = ExperimentRunner()
result = runner.run(config)

# 访问结果
print(f"Best score: {result.best_candidate.score}")
print(f"Best code:\n{result.best_candidate.code}")
```

### 6.5 使用 OR-Library 标准数据集

FunSearch-Lite 内置支持 OR-Library 装箱问题标准测试集，便于与学术文献对比。

#### 命令行使用

```bash
# 使用 OR-Library 小型数据集 (binpack1-4, 80个实例)
python run.py -d orlib

# 使用 OR-Library 大型数据集 (binpack5-8, 80个实例)
python run.py -d orlib -s large

# 快速测试 OR-Library
python run.py -d orlib -g 3 -p 3 -y
```

#### 编程方式加载

```python
from evaluator.datasets import (
    load_orlib_dataset,
    load_orlib_small,
    load_orlib_large,
    generate_weibull_dataset,
)

# 加载小型实例 (80 个，用于快速测试)
# 包含 binpack1, binpack2, binpack5, binpack6
small = load_orlib_small()
print(f"Loaded {len(small)} small instances")

# 加载大型实例 (80 个，用于完整评估)
# 包含 binpack3, binpack4, binpack7, binpack8
large = load_orlib_large()
print(f"Loaded {len(large)} large instances")

# 加载全部实例 (160 个)
all_data = load_orlib_dataset()
```

#### 查看实例详情

```python
for inst in small[:5]:
    print(f"{inst.name}: {inst.num_items} items, capacity={inst.capacity}, best_known={inst.best_known}")
```

输出示例:
```
u120_00: 120 items, capacity=150, best_known=48
u120_01: 120 items, capacity=150, best_known=49
...
```

#### 按类型筛选实例

```python
# 获取 Uniform 分布实例 (u*)
uniform = small.get_uniform_instances()

# 获取 Triplet 实例 (t*)
triplet = small.get_triplet_instances()

# 按物品数量筛选
medium = all_data.filter_by_size(min_items=100, max_items=300)
```

#### 使用 BenchmarkEvaluator

```python
from evaluator.bin_packing import BenchmarkEvaluator
from evaluator.datasets import load_orlib_small

# 创建基准评估器
dataset = load_orlib_small()
evaluator = BenchmarkEvaluator(dataset)

# 评估候选
result = evaluator.evaluate(candidate)
print(f"Score: {result.score}")
print(f"Matching best known: {result.metadata['num_matching_best']}/{len(dataset)}")
```

#### 生成自定义实例

```python
# 生成 Weibull 分布的实例 (更具挑战性)
weibull_dataset = generate_weibull_dataset(
    num_instances=50,
    num_items=200,
    capacity=100,
    seed=42
)
```

---

## 8. 故障排除

### 8.1 常见问题

#### 问题 1: `ModuleNotFoundError: No module named 'openai'`

**原因**: 使用 OpenAI/DeepSeek provider 但未安装 openai 包

**解决方案**:
```bash
pip install openai
# 或使用 FakeProvider (修改配置文件 provider_type: "fake")
```

#### 问题 2: `api_key client option must be set`

**原因**: 未设置 API 密钥环境变量

**解决方案**:
```bash
# DeepSeek
export DEEPSEEK_API_KEY="sk-..."  # Linux/macOS
$env:DEEPSEEK_API_KEY = "sk-..."  # Windows PowerShell

# OpenAI
export OPENAI_API_KEY="sk-..."
```

#### 问题 3: 所有候选都失败 (num_valid = 0)

**原因**: 
- Prompt 不清晰导致 LLM 生成无效代码
- 沙箱限制过严
- 超时时间过短

**解决方案**:
```bash
# 检查失败类型
sqlite3 artifacts/<run_id>/candidates.db \
  "SELECT json_extract(metadata, '$.error_message') FROM candidates LIMIT 10;"

# 根据错误类型调整:
# - 语法错误 → 优化 Prompt
# - 超时 → 增加 timeout_seconds
# - 导入被阻止 → 检查是否需要添加安全模块
```

#### 问题 4: Best Score 停滞不前

**原因**: 陷入局部最优

**解决方案**:
- 增加种群多样性: `population_size: 100`
- 增加岛屿数量: `num_islands: 5`
- 调整温度: `temperature: 1.0` (更高 = 更探索性)
- 使用更强大的模型

#### 问题 5: Windows 上资源限制不生效

**原因**: Windows 不支持 `resource.setrlimit()`

**解决方案**: 这是预期行为，沙箱会优雅降级。仅超时限制有效。

### 8.2 调试模式

启用详细日志:

```python
# 在 runner.py 顶部添加
import logging
logging.basicConfig(level=logging.DEBUG)
```

### 8.3 性能优化

**如果实验运行太慢**:

1. **减少评估成本**:
   ```yaml
   top_k_for_full_eval: 5  # 减少完整评估数量
   ```

2. **减少候选数量**:
   ```yaml
   population_size: 15  # 减少每代候选数
   ```

3. **使用 LLM 缓存**:
   - 缓存自动启用，重复实验时会命中缓存

4. **预计时间估算**:
   - 实验运行时会显示 tqdm 进度条和预计总时间
   - 总时间 ≈ max_generations × num_islands × population_size × 平均API响应时间

---

## 附录

### A. 配置文件模板

#### FakeProvider 模板 (测试用)

```yaml
# configs/template_fake.yaml
run_id: "my_experiment_001"
seed: 42
max_generations: 20
population_size: 50
num_islands: 3
top_k_for_full_eval: 10

task_name: "bin_packing"
evaluator:
  capacity: 100
  seed: 42

llm_providers:
  - provider_id: "fake_gen"
    provider_type: "fake"
    model_name: "fake-model"
    max_retries: 3
    timeout_seconds: 30

generator_provider_id: "fake_gen"
refiner_provider_id: "fake_gen"

artifact_dir: "artifacts"
save_interval: 5
```

#### DeepSeek 模板 (推荐)

```yaml
# configs/template_deepseek.yaml
run_id: "my_experiment_001"
seed: 42
max_generations: 50
population_size: 15
num_islands: 3
top_k_for_full_eval: 5

task_name: "bin_packing"
evaluator:
  capacity: 100
  seed: 42

llm_providers:
  - provider_id: "deepseek_gen"
    provider_type: "deepseek"
    model_name: "deepseek-chat"
    base_url: "https://api.deepseek.com"
    max_retries: 3
    timeout_seconds: 60
    temperature: 1.0
    max_tokens: 2000

generator_provider_id: "deepseek_gen"
refiner_provider_id: "deepseek_gen"

artifact_dir: "artifacts"
save_interval: 5
```

#### OpenAI 模板

```yaml
# configs/template_openai.yaml
run_id: "my_experiment_001"
seed: 42
max_generations: 50
population_size: 30
num_islands: 3
top_k_for_full_eval: 10

task_name: "bin_packing"
evaluator:
  capacity: 100
  seed: 42

llm_providers:
  - provider_id: "openai_gen"
    provider_type: "openai"
    model_name: "gpt-3.5-turbo"
    temperature: 0.8
    max_tokens: 2000
    max_retries: 3
    timeout_seconds: 30

generator_provider_id: "openai_gen"
refiner_provider_id: "openai_gen"

artifact_dir: "artifacts"
save_interval: 10
```

### B. 有用的脚本

**导出所有实验的最佳分数**:
```bash
#!/bin/bash
echo "Run ID,Best Score"
for dir in artifacts/*/; do
  run_id=$(basename $dir)
  best_score=$(sqlite3 "${dir}candidates.db" "SELECT MAX(score) FROM candidates;")
  echo "${run_id},${best_score}"
done > all_results.csv
```

**清理失败的实验**:
```bash
#!/bin/bash
for dir in artifacts/*/; do
  if [ ! -f "${dir}best_candidate.py" ]; then
    echo "Removing incomplete run: $(basename $dir)"
    rm -rf "$dir"
  fi
done
```

### C. 支持的 LLM 提供者

| 提供者 | provider_type | 环境变量 | 说明 |
|--------|---------------|----------|------|
| DeepSeek | `deepseek` | `DEEPSEEK_API_KEY` | 推荐，性价比高，需要设置 base_url |
| OpenAI | `openai` | `OPENAI_API_KEY` | GPT-3.5/GPT-4 |
| FakeProvider | `fake` | 无需 | 测试用，确定性输出 |

---

## 下一步

- 阅读 [ARCHITECTURE.md](ARCHITECTURE.md) 了解系统设计
- 阅读 [INNOVATION_POINTS.md](INNOVATION_POINTS.md) 了解三个创新点
- 阅读 [SANDBOX_LIMITATIONS.md](SANDBOX_LIMITATIONS.md) 了解安全限制
- 查看 `tests/` 目录了解测试用例
- 运行你的第一个实验！

如有问题，请检查:
1. 是否正确安装依赖 (`pip install -e .`)
2. 是否通过测试 (`pytest tests/ -v`)
3. 是否正确配置 YAML 文件
4. 是否设置了环境变量 (DEEPSEEK_API_KEY 或 OPENAI_API_KEY)
