"""
分层抽样选题 — 从 108 道 BioDSBench 题目中按分析类型均匀抽取 N 道

策略：
1. 按 analysis_types 分组
2. 每组按比例分配名额（至少 1 道）
3. 组内随机抽取
4. 输出逗号分隔的任务索引

用法:
    python select_tasks.py --count 30 --output selected_30.txt
    python select_tasks.py --count 30 --seed 42
"""

import argparse
import json
import random
import sys
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent))
from src.tasks.biodsbench_loader import BioDSBenchLoader


def stratified_sample(tasks: list, n: int, seed: int = 42) -> list:
    """按 analysis_types 分层抽样"""
    random.seed(seed)

    # 按类型分组
    groups = defaultdict(list)
    for i, t in enumerate(tasks):
        atype = t.get("analysis_types", "unknown")
        groups[atype].append(i)

    # 按比例分配名额（每组至少 1 道）
    total = len(tasks)
    allocation = {}
    remaining = n

    for atype, indices in groups.items():
        quota = max(1, round(len(indices) / total * n))
        quota = min(quota, len(indices))  # 不超过组内总数
        allocation[atype] = quota
        remaining -= quota

    # 如果分配超了，从最大组减
    while remaining < 0:
        largest = max(allocation, key=lambda k: allocation[k])
        if allocation[largest] > 1:
            allocation[largest] -= 1
            remaining += 1
        else:
            break

    # 如果还有余额，分给最大组
    while remaining > 0:
        for atype in sorted(groups, key=lambda k: len(groups[k]), reverse=True):
            if allocation[atype] < len(groups[atype]) and remaining > 0:
                allocation[atype] += 1
                remaining -= 1

    # 组内随机抽取
    selected = []
    for atype, quota in allocation.items():
        indices = groups[atype]
        sampled = random.sample(indices, min(quota, len(indices)))
        selected.extend(sampled)

    selected.sort()
    return selected


def main():
    parser = argparse.ArgumentParser(description="分层抽样选题")
    parser.add_argument("--count", "-n", type=int, default=30, help="抽取题数")
    parser.add_argument("--seed", type=int, default=42, help="随机种子")
    parser.add_argument("--output", "-o", type=str, default=None, help="输出文件")
    parser.add_argument("--data-root", type=str, default="../biodsbench_data")
    args = parser.parse_args()

    loader = BioDSBenchLoader(args.data_root)
    tasks = loader.load_all_tasks()

    selected = stratified_sample(tasks, args.count, args.seed)
    indices_str = ",".join(str(i) for i in selected)

    # 打印选题详情
    print(f"📊 从 {len(tasks)} 道题中分层抽样 {len(selected)} 道:\n")

    type_count = defaultdict(int)
    for idx in selected:
        atype = tasks[idx].get("analysis_types", "unknown")
        type_count[atype] += 1

    for atype, count in sorted(type_count.items(), key=lambda x: -x[1]):
        short = atype[:60]
        print(f"  {short}: {count} 道")

    print(f"\n任务索引: {indices_str}")

    if args.output:
        Path(args.output).write_text(indices_str, encoding="utf-8")
        print(f"已保存到: {args.output}")


if __name__ == "__main__":
    main()
