# System Architecture

本文档详细描述 FunSearch-Lite 的系统架构、模块职责和数据流。

## 1. 总体架构

FunSearch-Lite 采用分层架构，从底层基础设施到顶层实验编排:

```
┌─────────────────────────────────────────────────────────────────┐
│                   Layer 4: Orchestration                        │
│  ┌─────────────┐  ┌──────────┐  ┌─────────┐  ┌──────────────┐  │
│  │ExperimentRunner│  │CLI      │  │Metrics  │  │PlotGenerator│  │
│  │             │  │Interface │  │Collector│  │              │  │
│  └─────────────┘  └──────────┘  └─────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────────────┐
│                   Layer 3: Core Algorithm                       │
│  ┌─────────────┐  ┌──────────┐  ┌──────────┐  ┌─────────────┐  │
│  │FunSearchLoop│  │Population│  │Islands   │  │Diversity    │  │
│  │             │  │Manager   │  │Manager   │  │Maintainer   │  │
│  └─────────────┘  └──────────┘  └──────────┘  └─────────────┘  │
│  ┌─────────────┐                                                │
│  │Selection    │                                                │
│  │Strategies   │                                                │
│  └─────────────┘                                                │
└─────────────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────────────┐
│                  Layer 2: Services                              │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐  ┌───────────────┐  │
│  │LLM       │  │Sandbox   │  │Evaluator  │  │Candidate      │  │
│  │Providers │  │Executor  │  │           │  │Store          │  │
│  └──────────┘  └──────────┘  └───────────┘  └───────────────┘  │
│  ┌──────────┐  ┌──────────┐                                    │
│  │LLM Cache │  │Retry     │                                    │
│  │          │  │Policy    │                                    │
│  └──────────┘  └──────────┘                                    │
└─────────────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────────────┐
│                  Layer 1: Foundation                            │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐  ┌───────────────┐  │
│  │Schemas   │  │Database  │  │Config     │  │Failure        │  │
│  │(Pydantic)│  │(SQLite)  │  │Loader     │  │Taxonomy       │  │
│  └──────────┘  └──────────┘  └───────────┘  └───────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## 2. 核心模块详解

### 2.1 funsearch_core - 核心算法层

**职责**: 实现 FunSearch 进化搜索算法的核心逻辑

#### `loop.py` - 主进化循环 (300+ lines)

核心类 `FunSearchLoop` 协调整个搜索过程:

```python
class FunSearchLoop:
    def run_generation(self) -> dict[str, object]:
        # 显示全局进度信息 (tqdm)
        for island_index, island in tqdm(self.islands.islands):
            # 1. 生成新候选 (带进度条)
            new_candidates = self._generate_candidates_for_island(...)
            
            # 2. 功能级去重 (跳过重复候选)
            if self.deduplicator:
                unique_candidates = self._deduplicate(new_candidates)
            
            # 3. 多保真度评估
            self._evaluate_cheap(unique_candidates)      # 所有候选
            self._evaluate_full(top_k_candidates)        # 仅 Top-K
            
            # 4. 更新种群
            self._update_population(new_candidates)
        
        # 5. 多岛迁移
        if self.migration_interval > 0:
            self._island_migration()
```

**关键设计决策**:
- **两阶段评估**: cheap_eval 过滤 → full_eval 精确评估
- **多岛并行**: 每个岛维护独立子种群，定期交换优质个体
- **功能级去重**: 跳过行为相同的候选
- **实时进度**: tqdm 显示候选生成进度和预计时间

#### `population.py` - 种群管理

```python
class Population:
    def add(self, candidate: Candidate) -> bool:
        """添加候选，自动维护 Top-K 排序"""
        
    def sample(self, k: int) -> list[Candidate]:
        """按适应度采样用于变异"""
        
    def get_top_k(self, k: int) -> list[Candidate]:
        """获取当前最优 K 个候选"""
```

**特点**:
- 自动去重 (通过代码哈希)
- 维护按分数排序的候选列表
- 支持加权采样 (用于父代选择)

#### `islands.py` - 多岛模型

```python
class IslandManager:
    def migrate(self) -> None:
        """岛间迁移: 每个岛向其他岛发送最优个体"""
```

**迁移策略**:
- 定期 (每 N 代) 触发迁移
- 每个岛贡献 Top-1 候选到全局池
- 其他岛接收并融入本地种群

#### `diversity.py` - 多样性维护

```python
class DiversityMaintainer:
    def prune_if_needed(self, population: Population) -> None:
        """基于行为签名裁剪相似候选"""
```

**行为签名计算**:
- 在标准测试实例上运行候选
- 记录每个决策点的输出 (e.g., 选择的箱子索引)
- 签名相同 = 行为等价，保留更优者

#### `selection.py` - 选择策略

实现两种选择方式:
- **TournamentSelection**: 随机抽取 k 个候选，选最优
- **RankBasedSelection**: 按排名分配选择概率

### 2.2 evaluator - 评估模块

**职责**: 定义问题和评估候选质量

#### `base.py` - 评估器基类

```python
class BaseEvaluator(ABC):
    @abstractmethod
    def cheap_eval(self, candidate: Candidate) -> EvalResult:
        """廉价评估: 快速筛选"""
        
    @abstractmethod
    def full_eval(self, candidate: Candidate) -> EvalResult:
        """完整评估: 精确评分"""
```

#### `bin_packing.py` - 装箱问题实现

**多保真度配置**:
- **Cheap**: 4 个实例，每个 10-20 items
- **Full**: 10 个实例，每个 50-100 items

**评估流程**:
```python
1. 生成测试实例 (确定性种子)
2. 沙箱执行候选代码
3. 使用 score_bin 函数贪婪装箱
4. 计算使用的箱子数
5. 返回 score = -num_bins (越少越好)
```

**BenchmarkEvaluator**: 支持 OR-Library 标准数据集评估

#### `datasets.py` - 标准数据集加载器

```python
# OR-Library 装箱问题标准测试集
load_orlib_dataset()   # 加载所有 160 个实例
load_orlib_small()     # 加载小型实例 (binpack1,2,5,6)
load_orlib_large()     # 加载大型实例 (binpack3,4,7,8)
generate_weibull_dataset()  # 生成 Weibull 分布实例
```

#### `heuristics.py` - 基础启发式

提供 First-Fit 等基准算法供对比。

### 2.3 sandbox - 安全执行层

**职责**: 隔离执行不可信的 LLM 生成代码

#### `executor.py` - 子进程执行器

```python
class SandboxExecutor:
    def execute(
        self,
        code: str,
        timeout_seconds: float,
        memory_limit_mb: int | None = None,
    ) -> ExecutionResult:
        """在独立子进程中运行代码，带资源限制"""
```

**安全措施**:
1. **进程隔离**: 每次执行创建新子进程
2. **超时限制**: signal.alarm() 强制中断
3. **内存限制**: resource.setrlimit() (Linux/macOS)
4. **导入限制**: policy.py 白名单机制

#### `policy.py` - 导入策略

```python
SAFE_MODULES = frozenset([
    "math", "random", "itertools", "functools", "collections", ...
])

def is_import_allowed(module_name: str) -> bool:
    """仅允许安全的内置模块"""
```

**限制**:
- ❌ 禁止: os, sys, subprocess, socket, http, ...
- ✅ 允许: math, random, itertools, ...

### 2.4 llm - LLM 集成层

**职责**: 与大语言模型交互生成/变异代码

#### `providers.py` - 提供者实现

```python
class OpenAIProvider:
    """支持 OpenAI 和兼容 API (如 DeepSeek)"""
    
    def generate(self, *, temperature: float, seed: int | None) -> str:
        """从头生成新候选"""
        
    def mutate(self, *, parent_code: str, temperature: float, seed: int | None) -> str:
        """变异现有候选"""
```

**支持的提供者**:
- **OpenAI**: 使用 `OPENAI_API_KEY`
- **DeepSeek**: 使用 `DEEPSEEK_API_KEY`，需设置 `base_url`
- **FakeProvider** (测试用): 无需 API key，生成确定性输出

#### `prompts.py` - Prompt 模板

包含精心设计的提示词:
- **生成提示**: 包含问题描述、接口规范、示例
- **变异提示**: 提供父代码，要求改进
- **精炼提示**: 针对 Top-K 候选的深度优化

#### `cache.py` - 响应缓存

```python
class LLMCache:
    def get(self, prompt: str, temperature: float, seed: int | None) -> str | None:
        """基于哈希的缓存查询"""
        
    def set(self, prompt: str, temperature: float, seed: int | None, response: str) -> None:
        """缓存 LLM 响应"""
```

**效果**: 重复实验时大幅降低 API 成本

#### `retry.py` - 重试策略

指数退避重试处理临时 API 错误:
```python
retry_delays = [1, 2, 4, 8, ...]  # 秒
```

### 2.5 store - 持久化层

**职责**: 候选数据的存储和检索

#### `database.py` - SQLite 数据库

```sql
CREATE TABLE candidates (
    id TEXT PRIMARY KEY,
    code TEXT NOT NULL,
    code_hash TEXT NOT NULL,
    score REAL,
    generation INTEGER,
    parent_id TEXT,
    provider_id TEXT,
    created_at TIMESTAMP,
    metadata TEXT  -- JSON
);

CREATE INDEX idx_code_hash ON candidates(code_hash);
CREATE INDEX idx_score ON candidates(score DESC);
```

#### `repository.py` - 仓库模式

```python
class CandidateStore:
    def save(self, candidate: Candidate) -> None:
        """保存候选（去重）"""
        
    def get_by_id(self, candidate_id: str) -> Candidate | None:
        """ID 查询"""
        
    def get_top_k(self, k: int) -> list[Candidate]:
        """获取历史最优 K 个"""
        
    def exists_by_hash(self, code_hash: str) -> bool:
        """检查代码是否已存在"""
```

**去重机制**: 计算代码的 SHA-256 哈希，避免重复评估相同代码

### 2.6 experiments - 实验编排层

**职责**: 端到端实验管理、配置、指标和可视化

#### `runner.py` - 实验运行器

```python
class ExperimentRunner:
    def run(self, config: RunConfig) -> RunResult:
        """执行完整实验流程"""
        # 1. 初始化所有组件
        # 2. 运行 FunSearchLoop
        # 3. 收集指标
        # 4. 生成可视化
        # 5. 导出最佳候选
```

**多模型协作实现**:
```python
generator_provider = self._create_provider(config.generator_provider_id)
refiner_provider = self._create_provider(config.refiner_provider_id)

# 生成阶段: 使用廉价模型
new_candidates = generator_provider.generate(...)

# 精炼阶段: 对 Top-K 使用强大模型
refined = refiner_provider.refine(top_k_candidates)
```

#### `cli.py` - 命令行接口

```bash
python3 -m experiments.cli run <config.yaml>      # 运行实验
python3 -m experiments.cli list-runs              # 列出所有运行
python3 -m experiments.cli export-best <run_id>   # 导出最佳候选
python3 -m experiments.cli resume <run_id>        # 恢复中断的实验
```

#### `metrics.py` - 指标收集

**GenerationMetrics** 数据类:
```python
@dataclass
class GenerationMetrics:
    generation: int
    best_score: float | None
    avg_score: float | None
    top_k_avg_score: float | None
    num_candidates: int
    num_valid: int
    failure_counts: dict[str, int]  # {FailureType: count}
    timestamp: str
```

**导出格式**:
- JSONL: 每代一行，便于流式分析
- CSV: 表格格式，便于 Excel/Pandas

#### `plotting.py` - 可视化生成

**生成的图表**:
1. **evolution.png**: 进化曲线
   - X 轴: 代数
   - Y 轴: 分数
   - 4 条曲线: 最佳/平均/Top-K 平均/候选数
   
2. **failures.png**: 失败类型分布饼图
   - 显示各类失败 (语法/运行时/超时/...) 的占比

#### `failure_taxonomy.py` - 失败分类

```python
class FailureType(Enum):
    SYNTAX_ERROR = "syntax"
    IMPORT_BLOCKED = "import_blocked"
    RUNTIME_ERROR = "runtime"
    TIMEOUT = "timeout"
    INVALID_SIGNATURE = "signature"
    EVAL_ERROR = "eval_error"
```

**用途**: 指导 LLM 生成时避免常见错误

#### `config.py` - 配置管理

支持 YAML 配置文件:
```yaml
run_id: "binpacking_demo_001"
seed: 42
max_generations: 20
population_size: 50
num_islands: 3
top_k_for_full_eval: 10
task_name: "bin_packing"

llm_providers:
  - provider_id: "cheap_generator"
    provider_type: "openai"
    model_name: "gpt-3.5-turbo"
  - provider_id: "strong_refiner"
    provider_type: "openai"
    model_name: "gpt-4"

generator_provider_id: "cheap_generator"
refiner_provider_id: "strong_refiner"
```

## 3. 数据流

### 3.1 主循环数据流

```
┌──────────────┐
│   Config     │ (YAML)
└──────┬───────┘
       │
       ▼
┌──────────────────────────────────────────────┐
│         Experiment Runner                    │
│  ┌────────────────────────────────────────┐  │
│  │ 1. Initialize components               │  │
│  │    - LLM providers (generator/refiner) │  │
│  │    - Sandbox executor                  │  │
│  │    - Evaluator (multi-fidelity)        │  │
│  │    - Candidate store (SQLite)          │  │
│  │    - Metrics collector                 │  │
│  └────────────────────────────────────────┘  │
│                                              │
│  ┌────────────────────────────────────────┐  │
│  │ 2. Run FunSearchLoop                   │  │
│  │    FOR each generation:                │  │
│  │    ┌────────────────────────────────┐  │  │
│  │    │ 2.1 Generate candidates        │  │  │
│  │    │     - LLM.generate() × N       │  │  │
│  │    │     - LLM.mutate(parent) × M   │  │  │
│  │    └────────────────────────────────┘  │  │
│  │            │                            │  │
│  │            ▼                            │  │
│  │    ┌────────────────────────────────┐  │  │
│  │    │ 2.2 Cheap evaluation (all)     │  │  │
│  │    │     - Sandbox.execute(code)    │  │  │
│  │    │     - Evaluator.cheap_eval()   │  │  │
│  │    └────────────────────────────────┘  │  │
│  │            │                            │  │
│  │            ▼                            │  │
│  │    ┌────────────────────────────────┐  │  │
│  │    │ 2.3 Select Top-K               │  │  │
│  │    │     - Sort by cheap_score      │  │  │
│  │    │     - Take best K candidates   │  │  │
│  │    └────────────────────────────────┘  │  │
│  │            │                            │  │
│  │            ▼                            │  │
│  │    ┌────────────────────────────────┐  │  │
│  │    │ 2.4 Full evaluation (Top-K)    │  │  │
│  │    │     - Evaluator.full_eval()    │  │  │
│  │    │     - Update final scores      │  │  │
│  │    └────────────────────────────────┘  │  │
│  │            │                            │  │
│  │            ▼                            │  │
│  │    ┌────────────────────────────────┐  │  │
│  │    │ 2.5 Update population          │  │  │
│  │    │     - Add valid candidates     │  │  │
│  │    │     - Diversity pruning        │  │  │
│  │    │     - Island migration         │  │  │
│  │    └────────────────────────────────┘  │  │
│  │            │                            │  │
│  │            ▼                            │  │
│  │    ┌────────────────────────────────┐  │  │
│  │    │ 2.6 Collect metrics            │  │  │
│  │    │     - Best/avg scores          │  │  │
│  │    │     - Failure counts           │  │  │
│  │    │     - Save to JSONL            │  │  │
│  │    └────────────────────────────────┘  │  │
│  │    END FOR                             │  │
│  └────────────────────────────────────────┘  │
│                                              │
│  ┌────────────────────────────────────────┐  │
│  │ 3. Post-processing                     │  │
│  │    - Generate plots (evolution/failures)│ │
│  │    - Export best candidate (.py)       │  │
│  │    - Save final config snapshot        │  │
│  └────────────────────────────────────────┘  │
└──────────────────────────────────────────────┘
       │
       ▼
┌──────────────┐
│  Artifacts   │ (SQLite DB, JSONL, plots, best_candidate.py)
└──────────────┘
```

### 3.2 候选生命周期

```
1. LLM 生成代码
   ↓
2. 计算代码哈希，检查去重
   ↓
3. 沙箱执行 + Cheap 评估
   ↓
4. 有效则加入种群，保存到数据库
   ↓
5. 若进入 Top-K → Full 评估
   ↓
6. 更新最终分数
   ↓
7. 作为父代参与后续变异
```

## 4. 关键设计决策

### 4.1 为什么多保真度评估？

**问题**: 评估每个候选的成本高（尤其是大规模测试集）

**解决方案**: 两阶段过滤
- Cheap eval 用小数据集快速排除劣质候选 (4 instances)
- Full eval 仅评估 Top-K (10 instances)

**效果**: 评估成本降低 60-80%，搜索质量几乎不受影响

### 4.2 为什么多岛模型？

**问题**: 单一种群易陷入局部最优

**解决方案**: 并行维护多个独立子种群，定期交换优质个体

**效果**: 增加探索多样性，提高全局搜索能力

### 4.3 为什么多模型协作？

**问题**: 
- 强大模型 (GPT-4) 昂贵但质量高
- 廉价模型 (GPT-3.5) 便宜但质量一般

**解决方案**: 分阶段使用不同模型
- 生成阶段: 廉价模型批量生成 (探索广度)
- 精炼阶段: 强大模型优化 Top-K (优化深度)

**效果**: 在预算内平衡探索和开发

### 4.4 为什么沙箱隔离？

**问题**: LLM 生成的代码不可信 (可能包含恶意/危险操作)

**解决方案**: 子进程隔离 + 资源限制 + 导入白名单

**限制**: Best-effort，不适合生产环境 (详见 SANDBOX_LIMITATIONS.md)

## 5. 扩展点

### 5.1 添加新问题

实现 `BaseEvaluator` 接口:

```python
class MyProblemEvaluator(BaseEvaluator):
    def cheap_eval(self, candidate: Candidate) -> EvalResult:
        # 快速评估逻辑
        pass
        
    def full_eval(self, candidate: Candidate) -> EvalResult:
        # 完整评估逻辑
        pass
```

### 5.2 添加新 LLM 提供者

实现 `BaseLLMProvider` 接口:

```python
class MyLLMProvider(BaseLLMProvider):
    def generate(self, *, temperature: float, seed: int | None) -> str:
        # 调用 API 生成代码
        pass
```

### 5.3 自定义选择策略

实现 `SelectionStrategy` 接口:

```python
class MySelection(SelectionStrategy):
    def select_parents(self, population: Population, k: int) -> list[Candidate]:
        # 自定义选择逻辑
        pass
```

## 6. 性能优化

### 6.1 已实施的优化

1. **LLM 缓存**: 避免重复调用 API (成本↓, 延迟↓)
2. **代码哈希去重**: 避免重复评估相同代码 (评估次数↓)
3. **多保真度**: 仅对 Top-K 做完整评估 (评估成本↓)
4. **行为签名**: 高效识别行为等价的候选 (多样性↑)

### 6.2 可能的未来优化

1. **并行评估**: 多进程并行执行沙箱评估
2. **增量评估**: 仅在新测试实例上评估
3. **代理模型**: 训练快速代理预测候选质量
4. **早停**: 检测收敛提前终止

## 7. 测试覆盖

```
tests/
├── test_evaluator.py       # 评估器测试 (5 tests)
├── test_experiments.py     # 端到端实验测试 (9 tests)
├── test_funsearch_core.py  # 核心算法测试 (4 tests)
├── test_imports.py         # 导入策略测试 (7 tests)
├── test_llm.py             # LLM 提供者测试 (4 tests, 1 skipped)
├── test_observability.py   # 指标和绘图测试 (9 tests)
├── test_sandbox.py         # 沙箱安全测试 (5 tests)
├── test_schemas.py         # Schema 验证测试 (3 tests)
└── test_store.py           # 存储测试 (3 tests)
```

**总计**: 48 passed, 1 skipped (openai 包未安装)

## 8. 依赖关系图

```
experiments/runner.py
  ├─> funsearch_core/loop.py
  │    ├─> llm/providers.py
  │    │    ├─> llm/cache.py
  │    │    ├─> llm/retry.py
  │    │    └─> llm/prompts.py
  │    ├─> sandbox/executor.py
  │    │    └─> sandbox/policy.py
  │    ├─> evaluator/bin_packing.py
  │    │    └─> evaluator/base.py
  │    ├─> store/repository.py
  │    │    └─> store/database.py
  │    ├─> funsearch_core/population.py
  │    ├─> funsearch_core/islands.py
  │    ├─> funsearch_core/diversity.py
  │    └─> funsearch_core/selection.py
  ├─> experiments/metrics.py
  ├─> experiments/plotting.py
  └─> experiments/config.py
       └─> funsearch_core/schemas.py
```

## 9. 关键文件大小和复杂度

| 文件 | 行数 | 复杂度 | 核心职责 |
|------|------|--------|----------|
| `funsearch_core/loop.py` | ~300 | 高 | 主进化循环 |
| `experiments/runner.py` | ~250 | 中 | 端到端编排 |
| `evaluator/bin_packing.py` | ~200 | 中 | 多保真度评估 |
| `sandbox/executor.py` | ~180 | 高 | 安全执行 |
| `llm/providers.py` | ~150 | 中 | LLM 集成 |
| `store/repository.py` | ~120 | 低 | 数据持久化 |

## 10. 配置文件结构

完整配置示例见 `configs/binpacking.yaml`:

```yaml
# 实验标识
run_id: "binpacking_demo_001"
seed: 42

# 搜索参数
max_generations: 20
population_size: 50
num_islands: 3
top_k_for_full_eval: 10

# 问题配置
task_name: "bin_packing"
evaluator:
  capacity: 100
  seed: 42

# LLM 提供者
llm_providers:
  - provider_id: "fake_generator"
    provider_type: "fake"
    model_name: "fake-model"
    max_retries: 3
    timeout_seconds: 30

# 模型分配
generator_provider_id: "fake_generator"
refiner_provider_id: "fake_generator"

# 输出配置
artifact_dir: "artifacts"
save_interval: 5
```

## 总结

FunSearch-Lite 的架构设计体现了以下核心原则:

1. **模块化**: 每个层级职责清晰，易于扩展和测试
2. **可观测性**: 完善的指标收集和可视化
3. **鲁棒性**: 沙箱隔离、失败分类、重试机制
4. **效率**: 多保真度评估、LLM 缓存、代码去重
5. **灵活性**: 配置驱动、策略模式、插件式扩展点

该架构支持从原型研究到课程项目的各种场景。
