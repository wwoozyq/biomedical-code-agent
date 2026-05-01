#!/usr/bin/env python3
"""
针对 Descriptive Statistics 类型题目做消融实验
支持强弱模型对比 + 经验池效果验证
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.llm.client import LLMClient
from src.tasks.benchmark_runner import BenchmarkRunner

# Descriptive Statistics 的 27 题索引
DS_INDICES = [0, 1, 9, 10, 11, 19, 20, 28, 33, 36, 37, 49, 50, 51, 55, 57, 68, 69, 70, 71, 77, 88, 92, 93, 96, 97, 98]


def run_group(group_label, llm, data_root, output_dir, indices, enable_experience, enable_reflection):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 清理旧数据（确保空启动）
    pool_file = output_dir / "experience_pool.json"
    if pool_file.exists():
        pool_file.unlink()

    print(f"\n{'='*60}")
    print(f"  {group_label}")
    print(f"  经验池: {'✅' if enable_experience else '❌'} | 题目数: {len(indices)}")
    print(f"  输出: {output_dir}")
    print(f"{'='*60}")

    runner = BenchmarkRunner(
        llm_client=llm,
        data_root=data_root,
        output_dir=str(output_dir),
        max_iterations=8,
        verbose=True,
        enable_experience=enable_experience,
        enable_reflection=enable_reflection,
        enable_skills=False,
        use_sandbox=False,
    )

    result = runner.run_batch(task_indices=indices)
    return result


def main():
    parser = argparse.ArgumentParser(description="同类型题目消融实验")
    parser.add_argument("--max-tasks", type=int, default=None, help="最多跑多少题（默认全部 27 题）")
    parser.add_argument("--models", nargs="+", default=["deepseek-v3.2", "qwen-turbo"],
                        help="要测试的模型列表")
    parser.add_argument("--groups", nargs="+", default=["A", "B"], choices=["A", "B"],
                        help="A=ReAct, B=ReAct+经验池")
    parser.add_argument("--base-url", type=str,
                        default="https://dashscope.aliyuncs.com/compatible-mode/v1")
    parser.add_argument("--data-root", type=str, default="../biodsbench_data")
    parser.add_argument("--output-root", type=str, default="./ablation_output")
    args = parser.parse_args()

    api_key = os.environ.get("DASHSCOPE_API_KEY", "")
    if not api_key:
        print("❌ 请设置 DASHSCOPE_API_KEY")
        sys.exit(1)

    indices = DS_INDICES[:args.max_tasks] if args.max_tasks else DS_INDICES

    print(f"🧪 Descriptive Statistics 同类型消融实验")
    print(f"   题目数: {len(indices)}")
    print(f"   模型: {args.models}")
    print(f"   实验组: {args.groups}")

    all_results = {}

    for model_name in args.models:
        print(f"\n\n{'#'*60}")
        print(f"  模型: {model_name}")
        print(f"{'#'*60}")

        llm = LLMClient(api_key=api_key, base_url=args.base_url, model=model_name)

        for gid in args.groups:
            enable_exp = (gid == "B")
            enable_ref = (gid == "B")
            label_config = "ReAct" if gid == "A" else "ReAct+经验池"
            label = f"{model_name} | {label_config}"
            out_dir = Path(args.output_root) / f"ds_{model_name}_{gid}"

            try:
                result = run_group(label, llm, args.data_root, str(out_dir), indices, enable_exp, enable_ref)
                key = f"{model_name}_{gid}"
                all_results[key] = {
                    "model": model_name,
                    "group": gid,
                    "config": label_config,
                    "summary": result["summary"],
                }
            except Exception as e:
                print(f"💥 {label} 失败: {e}")
                import traceback
                traceback.print_exc()

    # 打印对比结果
    print(f"\n\n{'='*70}")
    print("📊 同类型题目消融实验对比")
    print(f"{'='*70}")
    print(f"  {'模型':<20} {'配置':<15} {'通过率':>8} {'通过/总数':>10} {'平均步数':>8}")
    print("-" * 70)

    for model_name in args.models:
        for gid in ["A", "B"]:
            key = f"{model_name}_{gid}"
            if key not in all_results:
                continue
            r = all_results[key]
            s = r["summary"]
            rate = f"{s['pass_rate']*100:.1f}%"
            ratio = f"{s['passed']}/{s['total_tasks']}"
            steps = f"{s['avg_steps']:.1f}"
            print(f"  {model_name:<20} {r['config']:<15} {rate:>8} {ratio:>10} {steps:>8}")

        # 计算经验池提升
        key_a = f"{model_name}_A"
        key_b = f"{model_name}_B"
        if key_a in all_results and key_b in all_results:
            a_rate = all_results[key_a]["summary"]["pass_rate"]
            b_rate = all_results[key_b]["summary"]["pass_rate"]
            delta = (b_rate - a_rate) * 100
            a_steps = all_results[key_a]["summary"]["avg_steps"]
            b_steps = all_results[key_b]["summary"]["avg_steps"]
            print(f"  {'':20} {'经验池提升':<15} {delta:>+7.1f}%")
            if a_steps > 0:
                step_delta = (b_steps - a_steps) / a_steps * 100
                print(f"  {'':20} {'步数变化':<15} {step_delta:>+7.1f}%")
        print()

    print(f"{'='*70}")

    # 保存汇总
    summary_file = Path(args.output_root) / "ds_ablation_summary.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"📁 汇总已保存到 {summary_file}")


if __name__ == "__main__":
    main()
