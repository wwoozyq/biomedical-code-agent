"""
技能库预热脚本

从已有的成功实验结果中提取技能，填充技能库。
这样技能库在正式评测时不再有冷启动劣势。

用法:
    python3 warmup_skill_library.py \
        --source-dir benchmark_output_30_turbo \
        --target-dir benchmark_output_30_turbo_skill_warm \
        --model qwen-turbo
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.llm.client import LLMClient
from src.agent.skill_library import SkillLibrary


def main():
    parser = argparse.ArgumentParser(description="技能库预热")
    parser.add_argument("--source-dir", required=True, help="已有实验结果目录（提取成功任务的代码）")
    parser.add_argument("--target-dir", required=True, help="目标实验目录（技能库将存放在此）")
    parser.add_argument("--model", default="qwen-turbo", help="用于提取技能的模型")
    parser.add_argument("--api-key", default=None)
    args = parser.parse_args()

    api_key = args.api_key or os.environ.get("DASHSCOPE_API_KEY", "")
    if not api_key:
        print("❌ 请设置 DASHSCOPE_API_KEY")
        sys.exit(1)

    llm = LLMClient(api_key=api_key, model=args.model)

    # 创建目标目录和技能库
    target = Path(args.target_dir)
    target.mkdir(parents=True, exist_ok=True)
    skill_dir = target / "skill_library"
    lib = SkillLibrary(library_dir=str(skill_dir))

    # 扫描源目录中的成功任务
    source = Path(args.source_dir)
    success_tasks = []
    for f in sorted(source.glob("task_*.json")):
        data = json.loads(f.read_text(encoding="utf-8"))
        if data.get("passed", False):
            success_tasks.append(data)

    print(f"📂 源目录: {source} ({len(success_tasks)} 道成功任务)")
    print(f"🛠️ 目标技能库: {skill_dir}")
    print()

    # 从每道成功任务中提取技能
    extracted = 0
    for i, task in enumerate(success_tasks):
        qid = task.get("unique_question_id", "unknown")
        query = task.get("query", "")
        analysis_types = task.get("analysis_types", "")

        # 找最后一个成功步骤的代码
        final_code = ""
        for step in reversed(task.get("execution_trace", [])):
            if step.get("success") and step.get("code"):
                final_code = step["code"]
                break

        if not final_code or len(final_code.strip()) < 50:
            print(f"  [{i+1}/{len(success_tasks)}] {qid} — 跳过（代码太短）")
            continue

        print(f"  [{i+1}/{len(success_tasks)}] {qid} — 提取中...", end=" ")
        skill = lib.extract_skill(
            llm_client=llm,
            code=final_code,
            query=query,
            task_id=qid,
            analysis_types=analysis_types,
        )
        if skill:
            extracted += 1
            print(f"✅ {skill.name} (调用链: {len(skill.call_chain)})")
        else:
            print("❌ 提取失败")

    print(f"\n🎉 预热完成: 从 {len(success_tasks)} 道成功任务中提取了 {extracted} 个技能")
    print(f"   技能库路径: {skill_dir}")
    stats = lib.get_stats()
    print(f"   技能总数: {stats['total_skills']}")


if __name__ == "__main__":
    main()
