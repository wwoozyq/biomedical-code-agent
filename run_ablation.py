#!/usr/bin/env python3
"""
消融实验脚本 — 四组对照实验，互不污染

实验组：
  A: 纯模型 baseline（无经验池、无技能库）
  B: 模型 + 经验池（空启动，边做边学）
  C: 模型 + 技能库（空启动，边做边学）
  D: 模型 + 经验池 + 技能库（空启动，边做边学）

每组使用独立的输出目录，经验池和技能库互不影响。

用法：
  # 跑全部 4 组（108 题）
  python run_ablation.py

  # 只跑指定组
  python run_ablation.py --groups A B

  # 只跑前 30 题（快速验证）
  python run_ablation.py --max-tasks 30

  # 指定模型
  python run_ablation.py --model deepseek-v3.2 --base-url https://api.deepseek.com/v1
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from dotenv import load_dotenv

# 自动加载 .env 文件中的 API Key
load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.llm.client import LLMClient
from src.tasks.benchmark_runner import BenchmarkRunner


# ── 实验配置 ──

EXPERIMENT_GROUPS = {
    "A0": {
        "name": "Zero-shot (一次性生成)",
        "enable_experience": False,
        "enable_reflection": False,
        "enable_skills": False,
        "zero_shot": True,
    },
    "A": {
        "name": "Baseline (ReAct 纯模型)",
        "enable_experience": False,
        "enable_reflection": False,
        "enable_skills": False,
        "enable_attribution": False,
        "zero_shot": False,
    },
    "AT": {
        "name": "ReAct + 归因子智能体",
        "enable_experience": False,
        "enable_reflection": False,
        "enable_skills": False,
        "enable_attribution": True,
        "zero_shot": False,
    },
    "B": {
        "name": "ReAct + 经验池",
        "enable_experience": True,
        "enable_reflection": True,
        "enable_skills": False,
        "enable_attribution": False,
        "zero_shot": False,
    },
    "C": {
        "name": "ReAct + 技能库",
        "enable_experience": False,
        "enable_reflection": False,
        "enable_skills": True,
        "enable_attribution": False,
        "zero_shot": False,
    },
    "D": {
        "name": "ReAct + 经验池 + 技能库",
        "enable_experience": True,
        "enable_reflection": True,
        "enable_skills": True,
        "enable_attribution": False,
        "zero_shot": False,
    },
    "F": {
        "name": "Full System (ReAct + 归因 + 经验池 + 技能库)",
        "enable_experience": True,
        "enable_reflection": True,
        "enable_skills": True,
        "enable_attribution": True,
        "zero_shot": False,
    },
}


def parse_args():
    parser = argparse.ArgumentParser(description="消融实验")
    parser.add_argument(
        "--groups", nargs="+", default=["A0", "A", "AT", "B", "C", "D", "F"],
        choices=["A0", "A", "AT", "B", "C", "D", "F"],
        help="要运行的实验组 (默认全部)",
    )
    parser.add_argument("--max-tasks", type=int, default=None, help="最多跑多少题 (默认全部)")
    parser.add_argument("--max-iterations", type=int, default=8, help="每题最大迭代步数")
    parser.add_argument("--model", type=str, default="deepseek-v3.2", help="模型名称")
    parser.add_argument(
        "--base-url", type=str,
        default="https://dashscope.aliyuncs.com/compatible-mode/v1",
        help="API base URL",
    )
    parser.add_argument("--api-key-env", type=str, default="DASHSCOPE_API_KEY", help="API Key 环境变量名")
    parser.add_argument("--data-root", type=str, default="../biodsbench_data", help="BioDSBench 数据目录")
    parser.add_argument("--output-root", type=str, default="./ablation_output", help="输出根目录")
    parser.add_argument("--verbose", action="store_true", default=True)
    parser.add_argument("--resume", action="store_true", help="断点续跑，跳过已完成的题目")
    return parser.parse_args()


def run_single_group(
    group_id: str,
    group_config: dict,
    llm_client: LLMClient,
    args,
) -> dict:
    """运行单组实验"""
    # 每组独立的输出目录
    output_dir = Path(args.output_root) / f"group_{group_id}"
    output_dir.mkdir(parents=True, exist_ok=True)

    # 断点续跑模式：不清理旧数据
    if not args.resume:
        # 清理旧的经验池和技能库（确保空启动）
        pool_file = output_dir / "experience_pool.json"
        skill_dir = output_dir / "skill_library"
        if pool_file.exists():
            pool_file.unlink()
        if skill_dir.exists():
            import shutil
            shutil.rmtree(skill_dir)

    print(f"\n{'='*70}")
    print(f"  实验组 {group_id}: {group_config['name']}")
    print(f"  经验池: {'✅' if group_config['enable_experience'] else '❌'}")
    print(f"  技能库: {'✅' if group_config['enable_skills'] else '❌'}")
    print(f"  归因子: {'✅' if group_config.get('enable_attribution') else '❌'}")
    print(f"  输出目录: {output_dir}")
    print(f"{'='*70}")

    runner = BenchmarkRunner(
        llm_client=llm_client,
        data_root=args.data_root,
        output_dir=str(output_dir),
        max_iterations=args.max_iterations,
        verbose=args.verbose,
        enable_experience=group_config["enable_experience"],
        enable_reflection=group_config["enable_reflection"],
        enable_skills=group_config["enable_skills"],
        enable_attribution=group_config.get("enable_attribution", False),
        use_sandbox=False,
    )

    # 找出已完成的题目索引（必须在 runner 创建之后）
    completed_indices = set()
    if args.resume:
        all_tasks_for_lookup = runner.loader.load_all_tasks()
        for f in output_dir.glob("task_*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                qid = data.get("unique_question_id", "")
                idx = data.get("task_index")
                if idx is not None:
                    completed_indices.add(idx)
                elif qid:
                    for i, t in enumerate(all_tasks_for_lookup):
                        if t.get("unique_question_ids") == qid:
                            completed_indices.add(i)
                            break
            except Exception:
                pass
        if completed_indices:
            print(f"  📌 断点续跑：已完成 {len(completed_indices)} 题，跳过")

    # 确定要跑的题目范围
    all_tasks = runner.loader.load_all_tasks()
    total = len(all_tasks)
    if args.max_tasks:
        total = min(total, args.max_tasks)

    # 过滤掉已完成的题目
    task_indices = [i for i in range(total) if i not in completed_indices]

    # Zero-shot 模式：一次性生成代码，不做 ReAct 循环
    if group_config.get("zero_shot", False):
        start_time = time.time()
        result = _run_zero_shot_batch(runner, llm_client, total, output_dir, args.verbose, completed_indices)
        elapsed = time.time() - start_time
        result["group_id"] = group_id
        result["group_name"] = group_config["name"]
        result["total_time"] = elapsed
        return result

    start_time = time.time()
    if task_indices:
        result = runner.run_batch(task_indices=task_indices)
    else:
        print("  ✅ 所有题目已完成，无需重跑")
        # 从已有文件汇总结果
        result = _load_existing_results(output_dir, total)
    elapsed = time.time() - start_time

    result["group_id"] = group_id
    result["group_name"] = group_config["name"]
    result["total_time"] = elapsed

    return result


ZERO_SHOT_PROMPT = """\
你是一个生物医学数据科学编码专家。请根据任务描述，一次性写出完整的 Python 代码来解决问题。
不要分步骤，直接给出完整的、可执行的代码。用 print() 输出关键结果。

## 任务
{query}

## 可用数据文件
{tables}

## 数据表 Schema
{table_schemas}

## 验证条件（你的代码必须让以下断言全部通过）
```python
{test_cases}
```

请直接输出完整代码，用 ```python ``` 包裹。不要解释，不要分步。
"""


def _run_zero_shot_batch(runner, llm_client, total, output_dir, verbose, skip_indices=None):
    """Zero-shot 模式：每题只调一次 LLM，生成完整代码，执行一次"""
    import io, sys, traceback, re

    if skip_indices is None:
        skip_indices = set()

    results = []

    # 先加载已有结果
    for idx in sorted(skip_indices):
        f = list(output_dir.glob(f"task_*.json"))
        for fpath in f:
            try:
                data = json.loads(fpath.read_text(encoding="utf-8"))
                if data.get("task_index") == idx:
                    results.append(data)
                    break
            except Exception:
                pass

    for idx in range(total):
        if idx in skip_indices:
            continue
        raw_task = runner.loader.load_task_by_index(idx)
        prepared = runner.loader.prepare_task(raw_task)
        qid = prepared["unique_question_id"]
        query = prepared["query"]
        test_cases_str = prepared.get("test_cases", "")

        print(f"\n{'#'*60}")
        print(f"  [Zero-shot] 任务 {idx+1}/{total} (index={idx})")
        print(f"{'#'*60}")

        start_time = time.time()

        # 构建 prompt
        prompt = ZERO_SHOT_PROMPT.format(
            query=query,
            tables=json.dumps(prepared.get("tables", []), ensure_ascii=False),
            table_schemas=prepared.get("table_schemas", ""),
            test_cases=test_cases_str,
        )

        try:
            # 一次性调用 LLM
            reply = llm_client.chat([
                {"role": "user", "content": prompt},
            ])

            # 提取代码
            code_match = re.search(r"```(?:python)?\s*\n(.*?)```", reply, re.DOTALL)
            code = code_match.group(1).strip() if code_match else ""

            if verbose:
                print(f"📝 生成代码: {len(code)} 字符")

            # 执行一次
            namespace = {}
            old_stdout = sys.stdout
            sys.stdout = captured = io.StringIO()
            try:
                exec(code, namespace)
                stdout_text = captured.getvalue()
                exec_success = True
                exec_error = None
            except Exception:
                stdout_text = captured.getvalue()
                exec_error = traceback.format_exc()
                exec_success = False
            finally:
                sys.stdout = old_stdout

            # 验证 test_cases
            passed = False
            test_details = ""
            if exec_success and test_cases_str:
                assertions = [
                    line.strip() for line in test_cases_str.strip().split("\n")
                    if line.strip() and line.strip().startswith("assert")
                ]
                failed = []
                for i, assertion in enumerate(assertions):
                    try:
                        exec(assertion, namespace)
                    except AssertionError:
                        failed.append(f"断言 {i+1} 失败: {assertion}")
                    except Exception as e:
                        failed.append(f"断言 {i+1} 异常: {assertion} ({type(e).__name__}: {e})")
                if failed:
                    test_details = "; ".join(failed)
                else:
                    passed = True
                    test_details = f"全部 {len(assertions)} 条断言通过"
            elif not exec_success:
                test_details = f"执行失败: {exec_error[:200] if exec_error else 'unknown'}"

        except Exception as e:
            passed = False
            code = ""
            exec_error = str(e)
            test_details = f"LLM 调用失败: {e}"

        elapsed = time.time() - start_time
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"\n{status}  [{qid}]  steps=1  time={elapsed:.1f}s")
        if not passed:
            print(f"  验证详情: {test_details[:200]}")

        result = {
            "task_index": idx,
            "unique_question_id": qid,
            "query": query[:200],
            "analysis_types": prepared.get("analysis_types", ""),
            "passed": passed,
            "test_details": test_details,
            "agent_success": passed,
            "total_steps": 1,
            "execution_time": elapsed,
            "execution_trace": [{"step_id": 0, "code": code[:500], "success": passed}],
        }
        results.append(result)

        # 保存单题结果
        log_file = output_dir / f"task_{qid}.json"
        with open(log_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2, default=str)

    # 汇总
    total_tasks = len(results)
    passed_count = sum(1 for r in results if r["passed"])
    times = [r["execution_time"] for r in results]
    summary = {
        "total_tasks": total_tasks,
        "passed": passed_count,
        "failed": total_tasks - passed_count,
        "pass_rate": round(passed_count / total_tasks, 4) if total_tasks > 0 else 0,
        "avg_execution_time": round(sum(times) / total_tasks, 2) if total_tasks > 0 else 0,
        "avg_steps": 1.0,
        "total_time": round(sum(times), 2),
    }

    # 打印汇总
    print(f"\n{'='*60}")
    print(f"📊 Zero-shot Benchmark 汇总")
    print(f"  通过率: {summary['pass_rate']*100:.1f}% ({passed_count}/{total_tasks})")
    print(f"  平均耗时: {summary['avg_execution_time']}s")
    print(f"{'='*60}")

    # 保存
    output_file = output_dir / "benchmark_results.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "details": results}, f, ensure_ascii=False, indent=2, default=str)

    return {"summary": summary, "details": results}


def _load_existing_results(output_dir, total):
    """从已有的 json 文件加载结果"""
    results = []
    for fpath in sorted(output_dir.glob("task_*.json")):
        try:
            data = json.loads(fpath.read_text(encoding="utf-8"))
            results.append(data)
        except Exception:
            pass

    total_tasks = len(results)
    passed_count = sum(1 for r in results if r.get("passed", False))
    times = [r.get("execution_time", 0) for r in results]
    steps = [r.get("total_steps", 0) for r in results]
    summary = {
        "total_tasks": total_tasks,
        "passed": passed_count,
        "failed": total_tasks - passed_count,
        "pass_rate": round(passed_count / total_tasks, 4) if total_tasks > 0 else 0,
        "avg_execution_time": round(sum(times) / total_tasks, 2) if total_tasks > 0 else 0,
        "avg_steps": round(sum(steps) / total_tasks, 2) if total_tasks > 0 else 0,
        "total_time": round(sum(times), 2),
    }
    return {"summary": summary, "details": results}


def print_comparison(all_results: dict):
    """打印四组对比结果"""
    print("\n" + "=" * 70)
    print("📊 消融实验对比结果")
    print("=" * 70)
    print(f"{'组别':<6} {'配置':<25} {'通过率':>8} {'通过/总数':>10} {'平均步数':>8} {'平均耗时':>8}")
    print("-" * 70)

    for gid in ["A0", "A", "B", "C", "D"]:
        if gid not in all_results:
            continue
        r = all_results[gid]
        s = r["summary"]
        name = r["group_name"]
        rate = f"{s['pass_rate']*100:.1f}%"
        ratio = f"{s['passed']}/{s['total_tasks']}"
        steps = f"{s['avg_steps']:.1f}"
        time_s = f"{s['avg_execution_time']:.1f}s"
        print(f"  {gid:<4} {name:<25} {rate:>8} {ratio:>10} {steps:>8} {time_s:>8}")

    print("=" * 70)

    # 计算各模块贡献
    if "A0" in all_results and "A" in all_results:
        a0_rate = all_results["A0"]["summary"]["pass_rate"]
        a_rate = all_results["A"]["summary"]["pass_rate"]
        print(f"  ReAct 循环 相对 zero-shot 提升: {(a_rate - a0_rate)*100:+.1f}%")

    if "A" in all_results:
        base = all_results["A"]["summary"]["pass_rate"]
        for gid, label in [("B", "经验池"), ("C", "技能库"), ("D", "经验池+技能库")]:
            if gid in all_results:
                rate = all_results[gid]["summary"]["pass_rate"]
                delta = (rate - base) * 100
                print(f"  {label} 相对 ReAct baseline 提升: {delta:+.1f}%")

    # 步数对比
    if "A" in all_results and "D" in all_results:
        base_steps = all_results["A"]["summary"]["avg_steps"]
        full_steps = all_results["D"]["summary"]["avg_steps"]
        if base_steps > 0:
            delta_pct = (full_steps - base_steps) / base_steps * 100
            print(f"  完整系统 vs baseline 平均步数变化: {delta_pct:+.1f}%")

    print("=" * 70)


def main():
    args = parse_args()

    # 初始化 LLM client
    api_key = os.environ.get(args.api_key_env, "")
    if not api_key:
        print(f"❌ 请设置环境变量 {args.api_key_env}")
        sys.exit(1)

    llm = LLMClient(
        api_key=api_key,
        base_url=args.base_url,
        model=args.model,
        temperature=0.0,
        max_tokens=4096,
    )

    print(f"🧪 消融实验开始")
    print(f"   模型: {args.model}")
    print(f"   实验组: {args.groups}")
    print(f"   最大题数: {args.max_tasks or '全部'}")

    all_results = {}

    for gid in args.groups:
        config = EXPERIMENT_GROUPS[gid]
        try:
            result = run_single_group(gid, config, llm, args)
            all_results[gid] = result
        except Exception as e:
            print(f"💥 实验组 {gid} 失败: {e}")
            import traceback
            traceback.print_exc()

    # 保存汇总结果
    output_root = Path(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    summary_file = output_root / "ablation_summary.json"
    summary_data = {}
    for gid, r in all_results.items():
        summary_data[gid] = {
            "group_name": r["group_name"],
            "summary": r["summary"],
            "total_time": r.get("total_time", 0),
        }
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary_data, f, ensure_ascii=False, indent=2)

    # 打印对比
    print_comparison(all_results)
    print(f"\n📁 详细结果已保存到 {output_root}")


if __name__ == "__main__":
    main()
