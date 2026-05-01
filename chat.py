"""
BioCode Agent - 对话界面
启动: streamlit run chat.py
"""
import streamlit as st
import os, sys, time, json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

st.set_page_config(page_title="BioCode Agent", page_icon="🧬", layout="wide", initial_sidebar_state="expanded")


# ── 自定义样式 ──
st.markdown("""
<style>
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #1a1f2e 0%, #0e1117 100%);
    border-right: 1px solid #2d3748;
}
[data-testid="stChatMessage"] {
    border: 1px solid #2d3748;
    border-radius: 12px;
    padding: 16px;
    margin-bottom: 12px;
}
.stButton > button { border-radius: 8px; font-weight: 600; }
.metric-card {
    background: linear-gradient(135deg, #1e2433 0%, #252d3d 100%);
    border: 1px solid #2d3748;
    border-radius: 12px;
    padding: 16px 20px;
    text-align: center;
}
.metric-value { font-size: 28px; font-weight: 700; color: #818cf8; }
.metric-label { font-size: 12px; color: #94a3b8; margin-top: 4px; }
footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ── session state ──
for key, default in [("messages", []), ("agent_ready", False), ("llm_client", None),
                      ("data_dir", ""), ("total_tasks", 0), ("total_success", 0)]:
    if key not in st.session_state:
        st.session_state[key] = default

# ── 侧边栏 ──
with st.sidebar:
    st.markdown("## 🧬 BioCode Agent")
    st.caption("面向生物医学数据科学的推理编码智能体")
    st.markdown("---")
    api_key = st.text_input("🔑 API Key", type="password", value=os.environ.get("DASHSCOPE_API_KEY", ""))
    model = st.selectbox("🤖 模型", ["deepseek-v3.2", "qwen3.5-27b", "qwen-turbo-latest", "qwen3-max", "qwen-plus", "qwen-turbo"])
    max_iter = st.slider("🔄 最大迭代步数", 1, 15, 8)
    st.markdown("---")
    st.markdown("##### 📁 数据目录")
    data_dir = st.text_input("路径", value="../biodsbench_data/mnm_washu_2016", label_visibility="collapsed")
    st.session_state.data_dir = data_dir
    dp = Path(data_dir)
    if dp.exists():
        for f in dp.glob("*"):
            if f.is_file():
                st.caption("📄 %s (%.0f KB)" % (f.name, f.stat().st_size / 1024))
    else:
        st.warning("目录不存在")
    st.markdown("---")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("🔌 连接", use_container_width=True, type="primary"):
            if not api_key:
                st.error("请输入 API Key")
            else:
                try:
                    from src.llm.client import LLMClient
                    st.session_state.llm_client = LLMClient(api_key=api_key, model=model)
                    st.session_state.agent_ready = True
                    st.success("✅ " + model)
                except Exception as e:
                    st.error("失败: %s" % e)
    with c2:
        if st.button("🗑️ 清空", use_container_width=True):
            st.session_state.messages = []
            st.session_state.total_tasks = 0
            st.session_state.total_success = 0
            st.rerun()
    if st.session_state.agent_ready:
        st.success("🟢 已连接")
    else:
        st.info("🔴 未连接")
    if st.session_state.total_tasks > 0:
        st.markdown("---")
        rate = st.session_state.total_success / st.session_state.total_tasks * 100
        st.caption("📊 任务: %d | 成功: %d | %.0f%%" % (st.session_state.total_tasks, st.session_state.total_success, rate))


# ── 渲染结果 ──
def render_result(result):
    success = result.get("success", False)
    total_steps = result.get("total_steps", 0)
    exec_time = result.get("execution_time", 0)
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown('<div class="metric-card"><div class="metric-value">%s</div><div class="metric-label">%s</div></div>' % (
            "✅" if success else "❌", "任务完成" if success else "任务失败"), unsafe_allow_html=True)
    with c2:
        st.markdown('<div class="metric-card"><div class="metric-value">%d</div><div class="metric-label">推理步骤</div></div>' % total_steps, unsafe_allow_html=True)
    with c3:
        st.markdown('<div class="metric-card"><div class="metric-value">%.1fs</div><div class="metric-label">执行耗时</div></div>' % exec_time, unsafe_allow_html=True)
    st.markdown("")
    for step in result.get("execution_trace", []):
        step_num = step.get("step_id", 0) + 1
        step_ok = step.get("success", False)
        icon = "✅" if step_ok else "❌"
        is_last = step_num == total_steps
        with st.expander("Step %d %s" % (step_num, icon), expanded=is_last):
            thought = step.get("thought", "")
            if thought:
                st.markdown("💭 " + thought)
            code = step.get("code", "")
            if code:
                st.code(code, language="python")
            stdout = step.get("stdout", "")
            if stdout:
                st.text(stdout[:3000])
            error = step.get("error", "")
            if error:
                st.error(error[:2000])

# ── 主界面 ──
st.markdown("# 🧬 BioCode Agent")
st.caption("输入数据分析问题，Agent 自动编写代码、执行、验证")

if not st.session_state.messages:
    st.markdown("##### 💡 试试这些问题：")
    examples = ["How many patients are with TP53 mutations?", "统计各基因突变频率 top 5", "分析不同治疗组的生存曲线差异"]
    cols = st.columns(len(examples))
    for i, (col, ex) in enumerate(zip(cols, examples)):
        with col:
            if st.button(ex, key="ex_%d" % i, use_container_width=True):
                st.session_state.messages.append({"role": "user", "content": ex})
                st.rerun()

for msg in st.session_state.messages:
    with st.chat_message(msg["role"], avatar="🧑‍💻" if msg["role"] == "user" else "🤖"):
        if msg["role"] == "user":
            st.markdown(msg["content"])
        elif "result_data" in msg:
            render_result(msg["result_data"])
        else:
            st.markdown(msg["content"])

def run_agent(query):
    from src.agent.react_agent import ReActAgent
    agent = ReActAgent(llm_client=st.session_state.llm_client, max_iterations=max_iter,
                       sandbox_dir="./sandbox", data_dir=st.session_state.data_dir, verbose=False)
    task_data = {"task_type": "data_analysis", "data_sources": [], "test_cases": ""}
    dp = Path(st.session_state.data_dir)
    if dp.exists():
        task_data["available_files"] = [f.name for f in dp.iterdir() if f.is_file()]
        task_data["data_dir"] = str(dp.resolve())
    return agent.solve_task(query, task_data)

if prompt := st.chat_input("描述你的数据分析任务..."):
    if not st.session_state.agent_ready:
        st.warning("请先在左侧点击「连接」")
    else:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user", avatar="🧑‍💻"):
            st.markdown(prompt)
        with st.chat_message("assistant", avatar="🤖"):
            with st.spinner("🤖 Agent 正在推理中..."):
                try:
                    result = run_agent(prompt)
                    render_result(result)
                    st.session_state.messages.append({"role": "assistant", "content": "", "result_data": result})
                    st.session_state.total_tasks += 1
                    if result.get("success"):
                        st.session_state.total_success += 1
                except Exception as e:
                    st.error("执行出错: %s" % e)
                    st.session_state.messages.append({"role": "assistant", "content": "执行出错: %s" % e})
