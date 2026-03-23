"""
🧬 生物医学数据科学智能体 - 对话界面
启动: streamlit run chat.py
"""
import streamlit as st
import os
import sys
import time
import json
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

st.set_page_config(page_title="Bio Agent Chat", page_icon="🧬", layout="wide")

# ── 初始化 session state ──

if "messages" not in st.session_state:
    st.session_state.messages = []

if "agent_ready" not in st.session_state:
    st.session_state.agent_ready = False

if "llm_client" not in st.session_state:
    st.session_state.llm_client = None

if "data_dir" not in st.session_state:
    st.session_state.data_dir = ""


# ── 侧边栏配置 ──

with st.sidebar:
    st.markdown("## ⚙️ 智能体配置")

    api_key = st.text_input(
        "DashScope API Key",
        type="password",
        value=os.environ.get("DASHSCOPE_API_KEY", ""),
    )
    model = st.selectbox("模型", ["qwen3-max", "qwen-plus", "qwen-turbo"])
    max_iter = st.slider("最大迭代次数", 1, 15, 8)

    st.markdown("---")
    st.markdown("### 📁 数据目录")
    data_dir = st.text_input(
        "Agent 可访问的数据目录",
        value="./data/sample_data",
        help="Agent 执行代码时会在这个目录下读取数据文件",
    )
    st.session_state.data_dir = data_dir

    # 显示数据目录下的文件
    data_path = Path(data_dir)
    if data_path.exists():
        files = list(data_path.glob("*"))
        if files:
            st.markdown("**可用数据文件:**")
            for f in files:
                if f.is_file():
                    size_kb = f.stat().st_size / 1024
                    st.text(f"  📄 {f.name} ({size_kb:.0f} KB)")
        else:
            st.info("目录为空")
    else:
        st.warning("目录不存在")

    st.markdown("---")

    # 初始化按钮
    if st.button("🔌 连接智能体", use_container_width=True, type="primary"):
        if not api_key:
            st.error("请输入 API Key")
        else:
            try:
                from src.llm.client import LLMClient

                st.session_state.llm_client = LLMClient(
                    api_key=api_key, model=model
                )
                st.session_state.agent_ready = True
                st.success(f"已连接 {model}")
            except Exception as e:
                st.error(f"连接失败: {e}")

    if st.session_state.agent_ready:
        st.markdown("🟢 智能体已就绪")
    else:
        st.markdown("🔴 未连接")

    st.markdown("---")
    if st.button("🗑️ 清空对话", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

    st.markdown("---")
    st.caption("💡 使用提示:")
    st.caption("1. 先点击「连接智能体」")
    st.caption("2. 在下方输入框描述你的分析任务")
    st.caption("3. Agent 会自动写代码并执行")
    st.caption("4. 你可以追问或要求修改")


# ── 工具函数 ──

def _render_agent_result(result: dict):
    """渲染 Agent 执行结果"""
    success = result.get("success", False)
    total_steps = result.get("total_steps", 0)
    exec_time = result.get("execution_time", 0)

    # 状态概览
    status = "✅ 任务完成" if success else "❌ 任务未完成"
    st.markdown(f"**{status}** — {total_steps} 步, 耗时 {exec_time:.1f}s")

    # 执行轨迹
    trace = result.get("execution_trace", [])
    for step in trace:
        step_num = step.get("step_id", 0) + 1
        step_ok = step.get("success", False)
        icon = "✅" if step_ok else "❌"

        with st.expander(f"Step {step_num} {icon}", expanded=(step_num == len(trace))):
            # Thought
            thought = step.get("thought", "")
            if thought:
                st.markdown(f"💭 **思考:** {thought}")

            # Code
            code = step.get("code", "")
            if code:
                st.code(code, language="python")

            # Output
            stdout = step.get("stdout", "")
            if stdout:
                st.markdown("**输出:**")
                st.code(stdout[:3000], language=None)

            # Error
            error = step.get("error", "")
            if error:
                st.error(error[:2000])




# ── 主界面 ──

st.title("🧬 生物医学数据科学智能体")
st.caption("输入你的数据分析问题，Agent 会自动编写代码并执行")

# 显示历史消息
for msg in st.session_state.messages:
    with st.chat_message(msg["role"], avatar="🧑‍💻" if msg["role"] == "user" else "🤖"):
        if msg["role"] == "user":
            st.markdown(msg["content"])
        else:
            if "result_data" in msg:
                _render_agent_result(msg["result_data"])
            else:
                st.markdown(msg["content"])


def _run_agent(user_query: str) -> dict:
    """调用 ReActAgent 执行任务"""
    from src.agent.react_agent import ReActAgent

    agent = ReActAgent(
        llm_client=st.session_state.llm_client,
        max_iterations=max_iter,
        sandbox_dir="./sandbox",
        data_dir=st.session_state.data_dir,
        verbose=False,
    )

    task_data = {
        "task_type": "data_analysis",
        "data_sources": [],
        "test_cases": "",
    }

    # 如果数据目录存在，列出文件供 Agent 参考
    dp = Path(st.session_state.data_dir)
    if dp.exists():
        available_files = [f.name for f in dp.iterdir() if f.is_file()]
        task_data["available_files"] = available_files
        task_data["data_dir"] = str(dp.resolve())

    result = agent.solve_task(user_query, task_data)
    return result


# ── 对话输入 ──

if prompt := st.chat_input("描述你的数据分析任务，例如：分析 survival_data.csv 中不同治疗组的生存曲线差异"):
    if not st.session_state.agent_ready:
        st.warning("请先在左侧点击「连接智能体」")
    else:
        # 显示用户消息
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user", avatar="🧑‍💻"):
            st.markdown(prompt)

        # 调用 Agent
        with st.chat_message("assistant", avatar="🤖"):
            with st.spinner("🤖 Agent 正在思考和执行中..."):
                try:
                    result = _run_agent(prompt)
                    _render_agent_result(result)
                    st.session_state.messages.append(
                        {"role": "assistant", "content": "", "result_data": result}
                    )
                except Exception as e:
                    error_msg = f"执行出错: {e}"
                    st.error(error_msg)
                    st.session_state.messages.append(
                        {"role": "assistant", "content": error_msg}
                    )
