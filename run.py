#!/usr/bin/env python3
"""
FunSearch 快速启动脚本 (跨平台)

使用方法:
  python run.py                          # 使用默认配置
  python run.py --dataset orlib          # 使用 OR-Library 数据集
  python run.py --size large             # 使用大型实例
  python run.py --generations 100        # 运行100代
  python run.py --demo                   # 演示模式 (无需API Key)
  python run.py --help                   # 显示帮助
"""

import argparse
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path


def load_env_file():
    """自动加载 .env 文件中的环境变量"""
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if key and value and key not in os.environ:
                        os.environ[key] = value


# 启动时自动加载 .env
load_env_file()


def create_temp_config(args) -> Path:
    """创建临时配置文件"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_id = args.run_id or f"funsearch_{args.dataset}_{args.size}_{timestamp}"
    
    provider_type = "fake" if args.demo else "deepseek"
    model_name = "fake-model" if args.demo else "deepseek-chat"
    base_url = "" if args.demo else 'base_url: "https://api.deepseek.com"'
    
    # Demo 模式禁用沙箱以提高速度，正式运行启用沙箱以确保安全
    use_sandbox = "false" if args.demo else "true"
    
    config_content = f"""run_id: "{run_id}"
seed: 42
max_generations: {args.generations}
population_size: {args.population}
num_islands: {args.islands}
top_k_for_full_eval: 5

task_name: "bin_packing"

evaluator:
  type: "{args.dataset}"
  size: "{args.size}"
  capacity: 100
  seed: 42
  use_sandbox: {use_sandbox}

llm_providers:
  - provider_id: "main_provider"
    provider_type: "{provider_type}"
    model_name: "{model_name}"
    {base_url}
    max_retries: 3
    timeout_seconds: 60
    temperature: 1.0
    max_tokens: 2000

generator_provider_id: "main_provider"
refiner_provider_id: "main_provider"

artifact_dir: "artifacts"
save_interval: 5
"""
    
    config_path = Path("configs") / "temp_run.yaml"
    config_path.parent.mkdir(exist_ok=True)
    config_path.write_text(config_content, encoding="utf-8")
    
    return config_path, run_id


def print_banner():
    """打印启动横幅"""
    print()
    print("╔══════════════════════════════════════════════════════════════════╗")
    print("║          🧬 FunSearch - LLM-Guided Evolutionary Search 🧬        ║")
    print("╚══════════════════════════════════════════════════════════════════╝")
    print()


def print_config(args, run_id):
    """打印配置信息"""
    print("📋 实验配置:")
    print(f"   Run ID:      {run_id}")
    print(f"   数据集:      {args.dataset} ({args.size})")
    print(f"   代数:        {args.generations}")
    print(f"   种群大小:    {args.population}")
    print(f"   岛屿数:      {args.islands}")
    
    if args.demo:
        print("   模式:        演示 (FakeProvider)")
    else:
        print("   模式:        DeepSeek API")
    print()


def estimate_time(args):
    """估算运行时间"""
    total_candidates = args.generations * args.islands * args.population
    avg_time_per_candidate = 0.1 if args.demo else 11  # 秒
    estimated_seconds = total_candidates * avg_time_per_candidate
    
    hours = int(estimated_seconds // 3600)
    minutes = int((estimated_seconds % 3600) // 60)
    
    print(f"⏱️  预计时间: {hours}小时 {minutes}分钟 (约 {total_candidates} 个候选)")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="FunSearch 快速启动脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  python run.py                              # 默认配置
  python run.py --demo                       # 演示模式 (无需API)
  python run.py --dataset orlib --size large # OR-Library 大型数据集
  python run.py --generations 100 --population 30

预计时间:
  - random/small: ~3-4小时 (50代)
  - random/large: ~5-6小时 (50代)
  - orlib/small:  ~4-5小时 (50代)
  - orlib/large:  ~6-8小时 (50代)
"""
    )
    
    parser.add_argument(
        "--dataset", "-d",
        choices=["random", "orlib"],
        default="random",
        help="数据集类型: random (随机生成) 或 orlib (OR-Library)"
    )
    parser.add_argument(
        "--size", "-s",
        choices=["small", "large"],
        default="small",
        help="实例大小: small 或 large"
    )
    parser.add_argument(
        "--generations", "-g",
        type=int,
        default=50,
        help="最大进化代数 (默认: 50)"
    )
    parser.add_argument(
        "--population", "-p",
        type=int,
        default=15,
        help="每代候选数量 (默认: 15)"
    )
    parser.add_argument(
        "--islands", "-i",
        type=int,
        default=3,
        help="岛屿数量 (默认: 3)"
    )
    parser.add_argument(
        "--run-id", "-r",
        type=str,
        default="",
        help="运行标识 (默认: 自动生成)"
    )
    parser.add_argument(
        "--api-key", "-k",
        type=str,
        default="",
        help="DeepSeek API Key (也可用环境变量 DEEPSEEK_API_KEY)"
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="使用 FakeProvider 演示模式 (无需 API Key)"
    )
    parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="跳过确认直接开始"
    )
    
    args = parser.parse_args()
    
    print_banner()
    
    # 检查 API Key
    if not args.demo:
        if args.api_key:
            os.environ["DEEPSEEK_API_KEY"] = args.api_key
        
        if not os.environ.get("DEEPSEEK_API_KEY"):
            print("❌ 错误: 未设置 DEEPSEEK_API_KEY")
            print("   请使用以下方式之一:")
            print("   1. python run.py --api-key 'sk-xxx'")
            print("   2. export DEEPSEEK_API_KEY='sk-xxx'  (Linux/Mac)")
            print("   3. $env:DEEPSEEK_API_KEY='sk-xxx'    (PowerShell)")
            print("   4. python run.py --demo              (演示模式)")
            sys.exit(1)
    
    # 创建配置文件
    config_path, run_id = create_temp_config(args)
    
    # 显示配置
    print_config(args, run_id)
    estimate_time(args)
    
    # 确认
    if not args.yes:
        try:
            response = input("按 Enter 开始实验，或输入 'q' 取消: ")
            if response.lower() == 'q':
                print("已取消")
                sys.exit(0)
        except KeyboardInterrupt:
            print("\n已取消")
            sys.exit(0)
    
    print("🚀 启动实验...")
    print()
    
    # 运行实验
    from experiments.config import load_config
    from experiments.runner import ExperimentRunner
    
    try:
        config = load_config(str(config_path))
        runner = ExperimentRunner(config)
        summary = runner.run()
        
        if summary.get("status") == "completed":
            print("\n✅ 实验成功完成!")
        else:
            print("\n⚠️  实验未完成")
    except Exception as e:
        print(f"\n❌ 实验出错: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    print()
    print(f"✅ 实验完成! 结果保存在: artifacts/{run_id}/")


if __name__ == "__main__":
    main()
