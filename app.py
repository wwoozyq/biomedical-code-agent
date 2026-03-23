"""
BioDSBench Agent 可视化监控面板
启动: streamlit run app.py
"""
import streamlit as st
import json
import os
import sys
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

st.set_page_config(page_title="BioDSBench Agent", page_icon="🧬", layout="wide")

# ──────────────────────────────────────────────
# 工具函数
# ──────────────────────────────────────────────

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_ROOT = os.path.join(BASE_DIR, "..", "biodsbench_data")

OUTPUT_DIRS = {
    "qwen3-max": "benchmark_output",
    "qwen-turbo (无经验池)": "benchmark_output_turbo_no_exp",
    "qwen-turbo (有经验池)": "benchmark_output_turbo",
}


def load_tasks():
    """加载全部 108 道 BioDSBench 任务"""
    tasks_file = os.path.join(DATA_ROOT, "python_tasks_with_class.jsonl")
    if not os.path.exists(tasks_file):
        return []
    tasks = []
    with open(tasks_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                tasks.append(json.loads(line))
    return tasks


def load_results(output_dir):
    """加载某个实验组的全部结果"""
    results = {}
    full_path = os.path.join(BASE_DIR, output_dir)
    if not os.path.exists(full_path):
        return results
    for f in os.listdir(full_path):
        if f.startswith("task_") and f.endswith(".json"):
            with open(os.path.join(full_path, f), "r", encoding="utf-8") as fh:
                r = json.load(fh)
                qid = r.get("unique_question_id", "")
                results[qid] = r
    return results


def load_experience_pool(pool_dir="benchmark_output"):
    """加载经验池"""
    pool_path = os.path.join(BASE_DIR, pool_dir, "experience_pool.json")
    if os.path.exists(pool_path):
        with open(pool_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def compute_group_stats(results):
    """计算一个实验组的汇总统计"""
    if not results:
        return {"total": 0, "passed": 0, "pass_rate": 0, "avg_steps": 0, "avg_time": 0}
    total = len(results)
    passed = sum(1 for r in results.values() if r.get("passed"))
    times = [r.get("execution_time", 0) for r in results.values()]
    steps = [r.get("total_steps", 0) for r in results.values()]
    return {
        "total": total,
        "passed": passed,
        "pass_rate": round(passed / total * 100, 1) if total else 0,
        "avg_steps": round(sum(steps) / total, 1) if total else 0,
        "avg_time": round(sum(times) / total, 1) if total else 0,
    }


# ──────────────────────────────────────────────
# 侧边栏导航
# ──────────────────────────────────────────────

page = st.sidebar.radio(
    "📑 导航",
    ["📊 实验对比面板", "🔍 任务浏览器", "🧠 经验池", "⚡ 运行任务"],
    index=0,
)

# ══════════════════════════════════════════════
# Page 1: 实验对比面板
# ══════════════════════════════════════════════

if page == "📊 实验对比面板":
    st.title("🧬 BioDSBench Agent 实验对比面板")
    st.caption("三组实验结果对比：qwen3-max vs qwen-turbo (无经验池) vs qwen-turbo (有经验池)")

    # 加载三组结果
    all_group_results = {}
    all_group_stats = {}
    for name, dirname in OUTPUT_DIRS.items():
        res = load_results(dirname)
        all_group_results[name] = res
        all_group_stats[name] = compute_group_stats(res)

    # ── 顶部指标卡片 ──
    st.subheader("汇总指标")
    cols = st.columns(3)
    for i, (name, stats) in enumerate(all_group_stats.items()):
        with cols[i]:
            st.metric(f"🏷️ {name}", f"{stats['pass_rate']}%", f"{stats['passed']}/{stats['total']} 通过")
            st.metric("平均步骤", f"{stats['avg_steps']} 步")
            st.metric("平均耗时", f"{stats['avg_time']}s")

    st.divider()

    # ── 通过率对比柱状图 ──
    st.subheader("通过率对比")
    bar_df = pd.DataFrame([
        {"实验组": name, "通过率 (%)": stats["pass_rate"]}
        for name, stats in all_group_stats.items()
    ])
    fig_rate = px.bar(
        bar_df, x="实验组", y="通过率 (%)", color="实验组",
        text="通过率 (%)", color_discrete_sequence=["#2ecc71", "#e74c3c", "#3498db"],
    )
    fig_rate.update_layout(showlegend=False, yaxis_range=[0, 105])
    fig_rate.update_traces(textposition="outside")
    st.plotly_chart(fig_rate, use_container_width=True)

    # ── 平均步骤 & 耗时对比 ──
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("平均步骤对比")
        steps_df = pd.DataFrame([
            {"实验组": name, "平均步骤": stats["avg_steps"]}
            for name, stats in all_group_stats.items()
        ])
        fig_steps = px.bar(
            steps_df, x="实验组", y="平均步骤", color="实验组",
            text="平均步骤", color_discrete_sequence=["#2ecc71", "#e74c3c", "#3498db"],
        )
        fig_steps.update_layout(showlegend=False)
        fig_steps.update_traces(textposition="outside")
        st.plotly_chart(fig_steps, use_container_width=True)

    with col2:
        st.subheader("平均耗时对比")
        time_df = pd.DataFrame([
            {"实验组": name, "平均耗时 (s)": stats["avg_time"]}
            for name, stats in all_group_stats.items()
        ])
        fig_time = px.bar(
            time_df, x="实验组", y="平均耗时 (s)", color="实验组",
            text="平均耗时 (s)", color_discrete_sequence=["#2ecc71", "#e74c3c", "#3498db"],
        )
        fig_time.update_layout(showlegend=False)
        fig_time.update_traces(textposition="outside")
        st.plotly_chart(fig_time, use_container_width=True)

    st.divider()

    # ── 逐任务对比表 ──
    st.subheader("逐任务对比")
    # 收集所有 task_id
    all_qids = set()
    for res in all_group_results.values():
        all_qids.update(res.keys())
    all_qids = sorted(all_qids)

    rows = []
    for qid in all_qids:
        row = {"任务 ID": qid}
        for name in OUTPUT_DIRS:
            r = all_group_results[name].get(qid)
            if r:
                row[f"{name} 结果"] = "✅" if r.get("passed") else "❌"
                row[f"{name} 步骤"] = r.get("total_steps", "-")
                row[f"{name} 耗时"] = f"{r.get('execution_time', 0):.1f}s"
            else:
                row[f"{name} 结果"] = "—"
                row[f"{name} 步骤"] = "—"
                row[f"{name} 耗时"] = "—"
        rows.append(row)

    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("暂无实验结果。请先运行 benchmark。")

    # ── 经验池效果分析 ──
    st.divider()
    st.subheader("🧠 经验池效果分析")
    turbo_no = all_group_results.get("qwen-turbo (无经验池)", {})
    turbo_yes = all_group_results.get("qwen-turbo (有经验池)", {})
    common_qids = set(turbo_no.keys()) & set(turbo_yes.keys())

    rescued = []  # 无经验池失败，有经验池成功
    degraded = []  # 无经验池成功，有经验池失败
    for qid in common_qids:
        no_pass = turbo_no[qid].get("passed", False)
        yes_pass = turbo_yes[qid].get("passed", False)
        if not no_pass and yes_pass:
            rescued.append(qid)
        elif no_pass and not yes_pass:
            degraded.append(qid)

    c1, c2 = st.columns(2)
    with c1:
        st.metric("🆙 经验池挽救的任务", len(rescued))
        if rescued:
            for qid in rescued:
                st.success(f"  {qid}")
    with c2:
        st.metric("⬇️ 经验池导致退化的任务", len(degraded))
        if degraded:
            for qid in degraded:
                st.error(f"  {qid}")


# ══════════════════════════════════════════════
# Page 2: 任务浏览器
# ══════════════════════════════════════════════

elif page == "🔍 任务浏览器":
    st.title("🔍 BioDSBench 任务浏览器")

    tasks = load_tasks()
    if not tasks:
        st.warning("未找到 python_tasks_with_class.jsonl，请确认 biodsbench_data 目录。")
        st.stop()

    st.caption(f"共 {len(tasks)} 道任务")

    # 选择实验组
    group_name = st.selectbox("选择实验组查看执行结果", list(OUTPUT_DIRS.keys()))
    results = load_results(OUTPUT_DIRS[group_name])

    # 任务索引选择
    task_idx = st.number_input("任务索引", min_value=0, max_value=len(tasks) - 1, value=0, step=1)
    task = tasks[task_idx]

    qid = task.get("unique_question_ids", "")
    st.subheader(f"任务 #{task_idx}: {qid}")

    # 基本信息
    col1, col2 = st.columns([2, 1])
    with col1:
        st.markdown("**查询 (Query):**")
        st.code(task.get("queries", ""), language=None)

        st.markdown("**验证条件 (Test Cases):**")
        st.code(task.get("test_cases", "无"), language="python")

    with col2:
        st.markdown("**分析类型:**")
        st.write(task.get("analysis_types", ""))

        st.markdown("**数据表:**")
        tables = task.get("tables", "[]")
        if isinstance(tables, str):
            tables = json.loads(tables)
        for t in tables:
            st.text(os.path.basename(t))

        st.markdown("**CoT 提示:**")
        cot = task.get("cot_instructions", "")
        if cot:
            st.text(cot[:300])
        else:
            st.text("无")

    # 执行结果
    st.divider()
    result = results.get(qid)
    if result:
        passed = result.get("passed", False)
        st.subheader(f"执行结果 ({'✅ 通过' if passed else '❌ 失败'})")

        m1, m2, m3 = st.columns(3)
        m1.metric("步骤数", result.get("total_steps", 0))
        m2.metric("耗时", f"{result.get('execution_time', 0):.1f}s")
        m3.metric("验证", "通过" if passed else "失败")

        st.markdown("**验证详情:**")
        st.text(result.get("test_details", ""))

        # 执行轨迹
        trace = result.get("execution_trace", [])
        if trace:
            st.subheader("执行轨迹")
            for step in trace:
                step_num = step.get("step_id", 0) + 1
                success = step.get("success", False)
                icon = "✅" if success else "❌"
                with st.expander(f"Step {step_num} {icon}", expanded=(len(trace) == 1)):
                    st.markdown("**Thought:**")
                    st.write(step.get("thought", ""))

                    st.markdown("**Code:**")
                    st.code(step.get("code", ""), language="python")

                    if step.get("stdout"):
                        st.markdown("**Output:**")
                        st.code(step["stdout"][:2000], language=None)

                    if step.get("error"):
                        st.markdown("**Error:**")
                        st.error(step["error"][:2000])
    else:
        st.info(f"该实验组暂无此任务 ({qid}) 的执行结果。")


# ══════════════════════════════════════════════
# Page 3: 经验池
# ══════════════════════════════════════════════

elif page == "🧠 经验池":
    st.title("🧠 经验复用池 & 反思记录")

    # 选择经验池来源
    pool_source = st.selectbox("经验池来源", ["benchmark_output", "benchmark_output_turbo"])
    pool = load_experience_pool(pool_source)

    if not pool:
        st.info("该目录下暂无经验池数据。")
        st.stop()

    # 统计
    total = len(pool)
    success_count = sum(1 for e in pool if e.get("success"))
    fail_count = total - success_count

    c1, c2, c3 = st.columns(3)
    c1.metric("总经验数", total)
    c2.metric("成功经验", success_count)
    c3.metric("失败经验", fail_count)

    st.divider()

    # 筛选
    filter_success = st.radio("筛选", ["全部", "仅成功", "仅失败"], horizontal=True)
    search_kw = st.text_input("关键词搜索 (任务描述)")

    filtered = pool
    if filter_success == "仅成功":
        filtered = [e for e in filtered if e.get("success")]
    elif filter_success == "仅失败":
        filtered = [e for e in filtered if not e.get("success")]

    if search_kw:
        kw_lower = search_kw.lower()
        filtered = [e for e in filtered if kw_lower in e.get("query", "").lower()]

    st.caption(f"显示 {len(filtered)} / {total} 条经验")

    for i, exp in enumerate(filtered):
        task_id = exp.get("task_id", "?")
        success = exp.get("success", False)
        icon = "✅" if success else "❌"
        steps = exp.get("steps_used", 0)

        with st.expander(f"{icon} {task_id} — {exp.get('query', '')[:80]}... ({steps} 步)"):
            st.markdown("**任务描述:**")
            st.write(exp.get("query", ""))

            st.markdown("**分析类型:**")
            st.write(exp.get("analysis_types", ""))

            st.markdown("**反思总结:**")
            reflection = exp.get("reflection", "")
            if reflection:
                st.info(reflection)
            else:
                st.text("无反思记录")

            st.markdown("**关键模式:**")
            patterns = exp.get("key_patterns", [])
            if patterns:
                for p in patterns:
                    st.markdown(f"- `{p}`")
            else:
                st.text("无")

            st.markdown("**最终代码:**")
            st.code(exp.get("final_code", ""), language="python")


# ══════════════════════════════════════════════
# Page 4: 运行任务
# ══════════════════════════════════════════════

elif page == "⚡ 运行任务":
    st.title("⚡ 交互式任务运行")
    st.caption("选择任务和模型，实时运行并查看结果")

    tasks = load_tasks()
    if not tasks:
        st.warning("未找到任务文件。")
        st.stop()

    # 配置区
    col1, col2 = st.columns(2)
    with col1:
        task_idx = st.number_input("任务索引", min_value=0, max_value=len(tasks) - 1, value=0, step=1)
        model = st.selectbox("模型", ["qwen3-max", "qwen-turbo", "qwen-plus"])
        max_iter = st.slider("最大迭代次数", 1, 15, 8)

    with col2:
        api_key = st.text_input("DashScope API Key", type="password",
                                value=os.environ.get("DASHSCOPE_API_KEY", ""))
        enable_exp = st.checkbox("启用经验池", value=True)
        enable_ref = st.checkbox("启用反思机制", value=True)
        output_dir = st.text_input("输出目录", value="./benchmark_output")

    # 预览任务
    task = tasks[task_idx]
    qid = task.get("unique_question_ids", "")
    st.divider()
    st.subheader(f"任务预览: #{task_idx} ({qid})")
    st.code(task.get("queries", "")[:500], language=None)
    st.markdown(f"**分析类型:** {task.get('analysis_types', '')}")

    # 运行按钮
    st.divider()
    if st.button("🚀 运行任务", type="primary", use_container_width=True):
        if not api_key:
            st.error("请输入 DashScope API Key")
            st.stop()

        with st.spinner(f"正在运行任务 #{task_idx} ({qid})..."):
            try:
                from src.llm.client import LLMClient
                from src.tasks.benchmark_runner import BenchmarkRunner

                llm = LLMClient(api_key=api_key, model=model)
                runner = BenchmarkRunner(
                    llm_client=llm,
                    data_root=os.path.join(BASE_DIR, "..", "biodsbench_data"),
                    output_dir=output_dir,
                    max_iterations=max_iter,
                    verbose=False,
                    enable_experience=enable_exp,
                    enable_reflection=enable_ref,
                )
                result = runner.run_single_task(task_idx)

                # 显示结果
                passed = result.get("passed", False)
                st.subheader(f"结果: {'✅ 通过' if passed else '❌ 失败'}")

                m1, m2, m3 = st.columns(3)
                m1.metric("步骤数", result.get("total_steps", 0))
                m2.metric("耗时", f"{result.get('execution_time', 0):.1f}s")
                m3.metric("验证", result.get("test_details", ""))

                # 执行轨迹
                trace = result.get("execution_trace", [])
                if trace:
                    st.subheader("执行轨迹")
                    for step in trace:
                        step_num = step.get("step_id", 0) + 1
                        success = step.get("success", False)
                        icon = "✅" if success else "❌"
                        with st.expander(f"Step {step_num} {icon}"):
                            st.markdown("**Thought:**")
                            st.write(step.get("thought", ""))
                            st.markdown("**Code:**")
                            st.code(step.get("code", ""), language="python")
                            if step.get("stdout"):
                                st.markdown("**Output:**")
                                st.code(step["stdout"][:2000], language=None)
                            if step.get("error"):
                                st.error(step["error"][:2000])

                st.success("结果已保存到 " + output_dir)

            except Exception as e:
                st.error(f"运行出错: {e}")
                import traceback
                st.code(traceback.format_exc(), language=None)

# ── 侧边栏底部信息 ──
st.sidebar.divider()
st.sidebar.caption("BioDSBench Agent v2.0")
st.sidebar.caption("ReAct + 经验池 + 反思机制")
