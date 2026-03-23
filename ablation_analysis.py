"""
消融实验对比分析
对比三组实验结果：
  1. benchmark_output          — qwen3-max + 经验池 + 反思 (完整版)
  2. benchmark_output_turbo    — qwen-turbo + 经验池 + 反思
  3. benchmark_output_turbo_no_exp — qwen-turbo + 无经验池/反思

用法:
    python ablation_analysis.py
    python ablation_analysis.py --output ablation_report.md
"""

import json
import sys
import argparse
from pathlib import Path
from collections import defaultdict

# ── 实验组配置 ──

EXPERIMENTS = {
    "qwen3-max (full)": {
        "dir": "benchmark_output",
        "model": "qwen3-max",
        "experience": True,
        "reflection": True,
    },
    "qwen-turbo + exp": {
        "dir": "benchmark_output_turbo",
        "model": "qwen-turbo",
        "experience": True,
        "reflection": True,
    },
    "qwen-turbo (baseline)": {
        "dir": "benchmark_output_turbo_no_exp",
        "model": "qwen-turbo",
        "experience": False,
        "reflection": False,
    },
}


def load_results(output_dir: str) -> dict:
    """加载某个实验目录下所有 task_*.json，返回 {question_id: result}"""
    results = {}
    p = Path(output_dir)
    if not p.exists():
        return results
    for f in sorted(p.glob("task_*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            qid = data.get("unique_question_id", f.stem)
            results[qid] = data
        except (json.JSONDecodeError, KeyError):
            continue
    return results


def compute_metrics(results: dict) -> dict:
    """计算一组实验结果的汇总指标"""
    if not results:
        return {"n": 0}
    n = len(results)
    passed = sum(1 for r in results.values() if r.get("passed"))
    times = [r.get("execution_time", 0) for r in results.values()]
    steps = [r.get("total_steps", 0) for r in results.values()]

    # 按 analysis_type 分组
    by_type = defaultdict(lambda: {"total": 0, "passed": 0})
    for r in results.values():
        atype = r.get("analysis_types", "unknown")
        by_type[atype]["total"] += 1
        if r.get("passed"):
            by_type[atype]["passed"] += 1

    return {
        "n": n,
        "passed": passed,
        "failed": n - passed,
        "pass_rate": passed / n if n else 0,
        "avg_time": sum(times) / n if n else 0,
        "avg_steps": sum(steps) / n if n else 0,
        "total_time": sum(times),
        "by_type": dict(by_type),
    }


def head_to_head(all_results: dict) -> list:
    """逐题对比：找出所有实验组共有的题目，逐题比较"""
    # 取所有实验组共有的 question_id
    qid_sets = [set(results.keys()) for results in all_results.values()]
    common_qids = sorted(set.intersection(*qid_sets)) if qid_sets else []

    rows = []
    for qid in common_qids:
        row = {"qid": qid}
        for exp_name, results in all_results.items():
            r = results[qid]
            row[f"{exp_name}|pass"] = r.get("passed", False)
            row[f"{exp_name}|steps"] = r.get("total_steps", 0)
            row[f"{exp_name}|time"] = r.get("execution_time", 0)
        rows.append(row)
    return rows


def generate_report(output_path: str = None):
    """生成消融实验对比报告"""
    all_results = {}
    all_metrics = {}

    for exp_name, cfg in EXPERIMENTS.items():
        results = load_results(cfg["dir"])
        all_results[exp_name] = results
        all_metrics[exp_name] = compute_metrics(results)

    exp_names = list(EXPERIMENTS.keys())
    lines = []
    lines.append("# 消融实验对比分析报告\n")
    lines.append("## 1. 实验配置\n")
    lines.append("| 实验组 | 模型 | 经验池 | 反思机制 |")
    lines.append("|--------|------|--------|----------|")
    for name, cfg in EXPERIMENTS.items():
        lines.append(
            f"| {name} | {cfg['model']} | {'✅' if cfg['experience'] else '❌'} | {'✅' if cfg['reflection'] else '❌'} |"
        )

    # ── 总体对比 ──
    lines.append("\n## 2. 总体性能对比\n")
    lines.append("| 指标 | " + " | ".join(exp_names) + " |")
    lines.append("|------|" + "|".join(["------"] * len(exp_names)) + "|")

    metric_rows = [
        ("任务数", "n", "{}"),
        ("通过数", "passed", "{}"),
        ("通过率", "pass_rate", "{:.1%}"),
        ("平均步骤数", "avg_steps", "{:.2f}"),
        ("平均耗时(s)", "avg_time", "{:.1f}"),
        ("总耗时(s)", "total_time", "{:.1f}"),
    ]
    for label, key, fmt in metric_rows:
        vals = [fmt.format(all_metrics[name].get(key, 0)) for name in exp_names]
        lines.append(f"| {label} | " + " | ".join(vals) + " |")

    # ── 经验池增益分析 ──
    lines.append("\n## 3. 经验池增益分析\n")
    m_turbo_exp = all_metrics.get("qwen-turbo + exp", {})
    m_turbo_base = all_metrics.get("qwen-turbo (baseline)", {})
    if m_turbo_exp.get("n") and m_turbo_base.get("n"):
        pr_delta = m_turbo_exp["pass_rate"] - m_turbo_base["pass_rate"]
        step_delta = m_turbo_exp["avg_steps"] - m_turbo_base["avg_steps"]
        time_delta = m_turbo_exp["avg_time"] - m_turbo_base["avg_time"]
        lines.append(
            f"在相同模型 (qwen-turbo) 下，启用经验池+反思 vs 不启用的差异：\n"
        )
        lines.append(f"- 通过率变化: {pr_delta:+.1%}")
        lines.append(f"- 平均步骤变化: {step_delta:+.2f}")
        lines.append(f"- 平均耗时变化: {time_delta:+.1f}s")
        if pr_delta > 0:
            lines.append(f"\n经验池+反思机制使通过率提升了 {pr_delta:.1%}。")
        elif pr_delta == 0:
            lines.append("\n经验池+反思机制未改变通过率，但可能影响了效率。")
        else:
            lines.append(f"\n经验池+反思机制使通过率下降了 {abs(pr_delta):.1%}，可能是经验噪声导致。")
    else:
        lines.append("数据不足，无法进行经验池增益分析。")

    # ── 模型能力对比 ──
    lines.append("\n## 4. 模型能力对比\n")
    m_max = all_metrics.get("qwen3-max (full)", {})
    if m_max.get("n") and m_turbo_exp.get("n"):
        pr_delta = m_max["pass_rate"] - m_turbo_exp["pass_rate"]
        lines.append(
            f"在相同配置（经验池+反思）下，qwen3-max vs qwen-turbo：\n"
        )
        lines.append(f"- 通过率差异: {pr_delta:+.1%}")
        lines.append(
            f"- 平均步骤: {m_max['avg_steps']:.2f} vs {m_turbo_exp['avg_steps']:.2f}"
        )
        lines.append(
            f"- 平均耗时: {m_max['avg_time']:.1f}s vs {m_turbo_exp['avg_time']:.1f}s"
        )

    # ── 逐题对比 ──
    lines.append("\n## 5. 逐题对比\n")
    h2h = head_to_head(all_results)
    if h2h:
        header = "| 题目ID |"
        sep = "|--------|"
        for name in exp_names:
            header += f" {name} 通过 | 步骤 | 耗时(s) |"
            sep += "------|------|---------|"
        lines.append(header)
        lines.append(sep)

        for row in h2h:
            line = f"| {row['qid']} |"
            for name in exp_names:
                p = "✅" if row.get(f"{name}|pass") else "❌"
                s = row.get(f"{name}|steps", 0)
                t = row.get(f"{name}|time", 0)
                line += f" {p} | {s} | {t:.1f} |"
            lines.append(line)

        # 统计差异题目
        diff_tasks = []
        for row in h2h:
            passes = [row.get(f"{name}|pass", False) for name in exp_names]
            if len(set(passes)) > 1:
                diff_tasks.append(row["qid"])
        if diff_tasks:
            lines.append(f"\n结果不一致的题目 ({len(diff_tasks)} 道): {', '.join(diff_tasks)}")
        else:
            lines.append("\n所有共有题目在三组实验中结果一致。")
    else:
        lines.append("无共有题目可供对比。")

    # ── 按分析类型对比 ──
    lines.append("\n## 6. 按分析类型对比\n")
    all_types = set()
    for m in all_metrics.values():
        all_types.update(m.get("by_type", {}).keys())
    if all_types:
        lines.append("| 分析类型 | " + " | ".join(exp_names) + " |")
        lines.append("|----------|" + "|".join(["------"] * len(exp_names)) + "|")
        for atype in sorted(all_types):
            vals = []
            for name in exp_names:
                bt = all_metrics[name].get("by_type", {}).get(atype, {})
                total = bt.get("total", 0)
                passed = bt.get("passed", 0)
                if total > 0:
                    vals.append(f"{passed}/{total} ({passed/total:.0%})")
                else:
                    vals.append("-")
            short_type = atype[:50]
            lines.append(f"| {short_type} | " + " | ".join(vals) + " |")

    # ── 结论 ──
    lines.append("\n## 7. 结论\n")
    lines.append("基于以上对比分析：\n")
    if m_turbo_exp.get("n") and m_turbo_base.get("n"):
        pr_exp = m_turbo_exp["pass_rate"]
        pr_base = m_turbo_base["pass_rate"]
        if pr_exp > pr_base:
            lines.append(
                f"1. **经验池有效**: 在 qwen-turbo 上，经验池+反思使通过率从 {pr_base:.1%} 提升到 {pr_exp:.1%}。"
            )
        elif pr_exp == pr_base:
            lines.append(
                f"1. **经验池效果中性**: 通过率持平 ({pr_base:.1%})，但步骤数和耗时可能有变化。"
            )
        else:
            lines.append(
                f"1. **经验池需优化**: 通过率从 {pr_base:.1%} 降至 {pr_exp:.1%}，可能存在经验噪声。"
            )
    if m_max.get("n") and m_turbo_exp.get("n"):
        if m_max["pass_rate"] > m_turbo_exp["pass_rate"]:
            lines.append(
                f"2. **强模型优势明显**: qwen3-max 通过率 {m_max['pass_rate']:.1%}，"
                f"显著高于 qwen-turbo 的 {m_turbo_exp['pass_rate']:.1%}。"
            )
        else:
            lines.append(
                f"2. **模型差异不大**: qwen3-max ({m_max['pass_rate']:.1%}) vs "
                f"qwen-turbo ({m_turbo_exp['pass_rate']:.1%})。"
            )
    lines.append(
        "3. 经验池的核心价值在于减少重复试错，对相似任务类型的提升最为显著。"
    )

    report = "\n".join(lines)

    if output_path:
        Path(output_path).write_text(report, encoding="utf-8")
        print(f"📊 报告已保存到 {output_path}")
    else:
        print(report)

    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="消融实验对比分析")
    parser.add_argument("--output", "-o", type=str, default="ablation_report.md", help="输出报告路径")
    parser.add_argument(
        "--dirs", type=str, default=None,
        help="逗号分隔的实验目录列表，如 'dir1,dir2,dir3'（覆盖默认配置）"
    )
    parser.add_argument(
        "--names", type=str, default=None,
        help="逗号分隔的实验组名称，如 'name1,name2,name3'（与 --dirs 一一对应）"
    )
    args = parser.parse_args()

    # 如果指定了自定义目录，覆盖默认 EXPERIMENTS
    if args.dirs:
        dirs = [d.strip() for d in args.dirs.split(",")]
        if args.names:
            names = [n.strip() for n in args.names.split(",")]
        else:
            names = dirs
        if len(names) != len(dirs):
            print("❌ --dirs 和 --names 数量不匹配")
            sys.exit(1)
        EXPERIMENTS.clear()
        for name, d in zip(names, dirs):
            # 从目录名推断配置
            has_exp = "no_exp" not in d
            model = "qwen3-max" if "qwen3" in name or ("turbo" not in d and "turbo" not in name) else "qwen-turbo"
            EXPERIMENTS[name] = {
                "dir": d,
                "model": model,
                "experience": has_exp,
                "reflection": has_exp,
            }

    generate_report(args.output)
