#!/bin/bash
# ============================================================
# 消融实验自动化脚本 — 三组实验各跑 30 题（支持断点续跑）
#
# 实验组:
#   1. qwen3-max  + 经验池 + 反思  → benchmark_output_30/
#   2. qwen-turbo + 经验池 + 反思  → benchmark_output_30_turbo/
#   3. qwen-turbo + 无经验池/反思  → benchmark_output_30_turbo_no_exp/
#
# 用法:
#   chmod +x run_ablation_30.sh
#   export DASHSCOPE_API_KEY='你的key'
#   ./run_ablation_30.sh           # 跑全部（自动跳过已完成的题）
#   ./run_ablation_30.sh --only 2  # 只跑第 2 组
#   ./run_ablation_30.sh --only 3  # 只跑第 3 组
#   ./run_ablation_30.sh --report  # 只生成报告，不跑实验
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 检查 API Key
if [ -z "$DASHSCOPE_API_KEY" ]; then
    echo "❌ 请先设置 DASHSCOPE_API_KEY:"
    echo "   export DASHSCOPE_API_KEY='你的key'"
    exit 1
fi

# 解析参数
ONLY_GROUP=""
REPORT_ONLY=false
for arg in "$@"; do
    case $arg in
        --only)   shift ;;
        --report) REPORT_ONLY=true ;;
        1|2|3)    ONLY_GROUP="$arg" ;;
    esac
done

# ── Step 1: 选题（复用已有的） ──
SELECTED_FILE="selected_30.txt"
if [ ! -f "$SELECTED_FILE" ]; then
    echo "📊 正在分层抽样选择 30 道题..."
    python3 select_tasks.py --count 30 --output "$SELECTED_FILE"
fi

ALL_INDICES=$(cat "$SELECTED_FILE")
echo "📋 全部任务索引: $ALL_INDICES"
echo ""

# ── 断点续跑：过滤掉已完成的题 ──
filter_done() {
    local OUTPUT_DIR=$1
    local ALL=$2
    local TODO=""

    IFS=',' read -ra INDICES <<< "$ALL"
    for idx in "${INDICES[@]}"; do
        # 查找该索引对应的 question_id，检查输出文件是否存在
        # 简单策略：如果 output_dir 下已有该索引对应的结果文件就跳过
        local FOUND=false
        if [ -d "$OUTPUT_DIR" ]; then
            # 用 python 快速查找
            FOUND=$(python3 -c "
import json, sys
from pathlib import Path
from src.tasks.biodsbench_loader import BioDSBenchLoader
loader = BioDSBenchLoader('../biodsbench_data')
tasks = loader.load_all_tasks()
t = tasks[$idx]
qid = t.get('unique_question_ids', '')
result_file = Path('$OUTPUT_DIR') / f'task_{qid}.json'
print('yes' if result_file.exists() else 'no')
" 2>/dev/null)
        fi

        if [ "$FOUND" != "yes" ]; then
            if [ -z "$TODO" ]; then
                TODO="$idx"
            else
                TODO="$TODO,$idx"
            fi
        fi
    done
    echo "$TODO"
}

run_experiment() {
    local GROUP_NUM=$1
    local MODEL=$2
    local OUTPUT_DIR=$3
    local EXTRA_FLAGS=$4

    # 过滤已完成的
    local TODO
    TODO=$(filter_done "$OUTPUT_DIR" "$ALL_INDICES")

    if [ -z "$TODO" ]; then
        echo "✅ 实验组 $GROUP_NUM 已全部完成，跳过"
        echo ""
        return 0
    fi

    local DONE_COUNT=$(echo "$ALL_INDICES" | tr ',' '\n' | wc -l | tr -d ' ')
    local TODO_COUNT=$(echo "$TODO" | tr ',' '\n' | wc -l | tr -d ' ')
    local SKIP_COUNT=$((DONE_COUNT - TODO_COUNT))

    echo "============================================================"
    echo "🧪 实验组 $GROUP_NUM: model=$MODEL"
    echo "   输出: $OUTPUT_DIR"
    echo "   总计: $DONE_COUNT 题, 已完成: $SKIP_COUNT, 待跑: $TODO_COUNT"
    echo "============================================================"

    python3 run_benchmark.py \
        --task-indices "$TODO" \
        --model "$MODEL" \
        --output-dir "$OUTPUT_DIR" \
        --max-iter 8 \
        $EXTRA_FLAGS

    local EXIT_CODE=$?
    if [ $EXIT_CODE -ne 0 ]; then
        echo "⚠️  实验组 $GROUP_NUM 异常退出 (code=$EXIT_CODE)，已完成的结果已保存"
        echo "   重新运行脚本即可从断点继续"
    else
        echo "✅ 实验组 $GROUP_NUM 完成"
    fi
    echo ""
    return $EXIT_CODE
}

# ── Step 2: 运行实验 ──
if [ "$REPORT_ONLY" = false ]; then
    if [ -z "$ONLY_GROUP" ] || [ "$ONLY_GROUP" = "1" ]; then
        run_experiment 1 "qwen3-max" "./benchmark_output_30" ""
    fi

    if [ -z "$ONLY_GROUP" ] || [ "$ONLY_GROUP" = "2" ]; then
        run_experiment 2 "qwen-turbo" "./benchmark_output_30_turbo" ""
    fi

    if [ -z "$ONLY_GROUP" ] || [ "$ONLY_GROUP" = "3" ]; then
        run_experiment 3 "qwen-turbo" "./benchmark_output_30_turbo_no_exp" "--no-experience --no-reflection"
    fi
fi

# ── Step 3: 生成对比报告 ──
echo "============================================================"
echo "📊 生成消融实验对比报告..."
echo "============================================================"

python3 ablation_analysis.py \
    --dirs "benchmark_output_30,benchmark_output_30_turbo,benchmark_output_30_turbo_no_exp" \
    --names "qwen3-max (full),qwen-turbo + exp,qwen-turbo (baseline)" \
    --output ablation_report_30.md

echo ""
echo "🎉 完成！报告: ablation_report_30.md"
