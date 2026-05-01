"""
BioDSBench 运行入口
用法:
    # 运行单个任务（按索引）
    python run_benchmark.py --task-index 0

    # 运行一批任务
    python run_benchmark.py --start 0 --end 10

    # 运行全部 108 道题
    python run_benchmark.py --all

    # 指定模型
    python run_benchmark.py --task-index 0 --model qwen-plus
"""

import argparse
import os
import sys

# 确保项目根目录在 path 中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.llm.client import LLMClient
from src.tasks.benchmark_runner import BenchmarkRunner


def main():
    parser = argparse.ArgumentParser(description="BioDSBench 运行器")
    parser.add_argument("--task-index", type=int, default=None, help="运行单个任务（0-based 索引）")
    parser.add_argument("--task-indices", type=str, default=None, help="运行多个任务，逗号分隔，如 1,9,12,19")
    parser.add_argument("--task-id", type=str, default=None, help="按 unique_question_id 运行")
    parser.add_argument("--start", type=int, default=0, help="批量运行起始索引")
    parser.add_argument("--end", type=int, default=None, help="批量运行结束索引")
    parser.add_argument("--all", action="store_true", help="运行全部任务")
    parser.add_argument("--model", type=str, default="qwen3-max", help="模型名称")
    parser.add_argument("--no-experience", action="store_true", help="禁用经验复用池")
    parser.add_argument("--no-reflection", action="store_true", help="禁用反思机制")
    parser.add_argument("--api-key", type=str, default=None, help="API Key（也可设置 DASHSCOPE_API_KEY 环境变量）")
    parser.add_argument("--max-iter", type=int, default=8, help="每个任务最大迭代次数")
    parser.add_argument("--data-root", type=str, default="../biodsbench_data", help="BioDSBench 数据目录")
    parser.add_argument("--output-dir", type=str, default="./benchmark_output", help="输出目录")
    parser.add_argument("--quiet", action="store_true", help="减少输出")
    parser.add_argument("--sandbox", action="store_true", help="启用安全沙箱（子进程隔离执行代码）")
    parser.add_argument("--use-skills", action="store_true", help="启用技能库（AST 调用链检索 + 技能提取）")
    parser.add_argument("--attribution", action="store_true", help="启用归因子智能体")
    args = parser.parse_args()

    # 初始化 LLM
    api_key = args.api_key or os.environ.get("DASHSCOPE_API_KEY", "")
    if not api_key:
        print("❌ 请设置 API Key:")
        print("   export DASHSCOPE_API_KEY='你的key'")
        print("   或使用 --api-key 参数")
        sys.exit(1)

    llm = LLMClient(api_key=api_key, model=args.model)
    runner = BenchmarkRunner(
        llm_client=llm,
        data_root=args.data_root,
        output_dir=args.output_dir,
        max_iterations=args.max_iter,
        verbose=not args.quiet,
        enable_experience=not args.no_experience,
        enable_reflection=not args.no_reflection,
        use_sandbox=args.sandbox,
        enable_skills=args.use_skills,
        enable_attribution=args.attribution,
    )

    if args.task_index is not None:
        runner.run_single_task(args.task_index)
    elif args.task_indices is not None:
        indices = [int(x.strip()) for x in args.task_indices.split(",")]
        runner.run_batch(task_indices=indices)
    elif args.task_id is not None:
        runner.run_task_by_id(args.task_id)
    elif args.all:
        runner.run_batch()
    else:
        runner.run_batch(start=args.start, end=args.end)


if __name__ == "__main__":
    main()
