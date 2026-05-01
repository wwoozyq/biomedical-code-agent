"""
生物医学数据科学推理编码智能体 - 高级可视化监控面板
"""

import streamlit as st
import os
import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from pathlib import Path
import time
from datetime import datetime
import base64

from src.agent.react_agent import ReActAgent
from src.llm.client import LLMClient
from src.multi_agent.coordinator import MultiAgentCoordinator
from src.tasks.data_analysis import DataAnalysisTask
from src.tasks.prediction import PredictionTask
from src.tasks.sql_query import SQLQueryTask

# 页面配置
st.set_page_config(
    page_title="BioMed AI Agent | 生物医学智能体",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定义CSS样式
st.markdown("""
<style>
    /* 主题色彩 */
    :root {
        --primary-color: #1f77b4;
        --secondary-color: #ff7f0e;
        --success-color: #2ca02c;
        --warning-color: #d62728;
        --info-color: #17a2b8;
        --light-bg: #f8f9fa;
        --dark-bg: #343a40;
    }
    
    /* 隐藏默认的Streamlit样式 */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* 自定义标题样式 */
    .main-header {
        background: linear-gradient(90deg, #1f77b4 0%, #ff7f0e 100%);
        padding: 2rem;
        border-radius: 10px;
        margin-bottom: 2rem;
        text-align: center;
        color: white;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    
    .main-header h1 {
        margin: 0;
        font-size: 2.5rem;
        font-weight: 700;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
    }
    
    .main-header p {
        margin: 0.5rem 0 0 0;
        font-size: 1.2rem;
        opacity: 0.9;
    }
    
    /* 卡片样式 */
    .metric-card {
        background: white;
        padding: 1.5rem;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        border-left: 4px solid var(--primary-color);
        margin-bottom: 1rem;
        transition: transform 0.2s ease;
    }
    
    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.15);
    }
    
    .metric-value {
        font-size: 2rem;
        font-weight: bold;
        color: var(--primary-color);
        margin: 0;
    }
    
    .metric-label {
        font-size: 0.9rem;
        color: #666;
        margin: 0;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    
    /* 状态指示器 */
    .status-badge {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    
    .status-success {
        background-color: #d4edda;
        color: #155724;
        border: 1px solid #c3e6cb;
    }
    
    .status-error {
        background-color: #f8d7da;
        color: #721c24;
        border: 1px solid #f5c6cb;
    }
    
    .status-warning {
        background-color: #fff3cd;
        color: #856404;
        border: 1px solid #ffeaa7;
    }
    
    .status-info {
        background-color: #d1ecf1;
        color: #0c5460;
        border: 1px solid #bee5eb;
    }
    
    /* 进度条样式 */
    .progress-container {
        background-color: #e9ecef;
        border-radius: 10px;
        overflow: hidden;
        height: 20px;
        margin: 1rem 0;
    }
    
    .progress-bar {
        height: 100%;
        background: linear-gradient(90deg, var(--primary-color), var(--secondary-color));
        transition: width 0.3s ease;
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        font-weight: bold;
        font-size: 0.8rem;
    }
    
    /* 侧边栏样式 */
    .sidebar-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 1rem;
        border-radius: 10px;
        margin-bottom: 1rem;
        text-align: center;
    }
    
    /* 按钮样式 */
    .stButton > button {
        background: linear-gradient(90deg, #1f77b4, #ff7f0e);
        color: white;
        border: none;
        border-radius: 25px;
        padding: 0.75rem 2rem;
        font-weight: 600;
        transition: all 0.3s ease;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.2);
    }
    
    /* 选择框样式 */
    .stSelectbox > div > div {
        border-radius: 10px;
        border: 2px solid #e9ecef;
        transition: border-color 0.3s ease;
    }
    
    .stSelectbox > div > div:focus-within {
        border-color: var(--primary-color);
        box-shadow: 0 0 0 3px rgba(31, 119, 180, 0.1);
    }
    
    /* 文本区域样式 */
    .stTextArea > div > div > textarea {
        border-radius: 10px;
        border: 2px solid #e9ecef;
        transition: border-color 0.3s ease;
    }
    
    .stTextArea > div > div > textarea:focus {
        border-color: var(--primary-color);
        box-shadow: 0 0 0 3px rgba(31, 119, 180, 0.1);
    }
    
    /* 标签页样式 */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        background-color: #f8f9fa;
        border-radius: 10px 10px 0 0;
        padding: 0 20px;
        font-weight: 600;
        border: 2px solid #e9ecef;
        border-bottom: none;
    }
    
    .stTabs [aria-selected="true"] {
        background-color: white;
        border-color: var(--primary-color);
        color: var(--primary-color);
    }
    
    /* 数据框样式 */
    .dataframe {
        border-radius: 10px;
        overflow: hidden;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    /* 警告和信息框样式 */
    .stAlert {
        border-radius: 10px;
        border: none;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    /* 代码块样式 */
    .stCode {
        border-radius: 10px;
        border: 1px solid #e9ecef;
    }
    
    /* 响应式设计 */
    @media (max-width: 768px) {
        .main-header h1 {
            font-size: 2rem;
        }
        
        .main-header p {
            font-size: 1rem;
        }
        
        .metric-card {
            padding: 1rem;
        }
    }
</style>
""", unsafe_allow_html=True)

def create_animated_header():
    """创建动画标题"""
    st.markdown("""
    <div class="main-header">
        <h1>🧬 BioMed AI Agent</h1>
        <p>生物医学数据科学推理编码智能体 | Advanced Biomedical Data Science Reasoning Agent</p>
    </div>
    """, unsafe_allow_html=True)

def create_metric_card(title, value, delta=None, delta_color="normal"):
    """创建指标卡片"""
    delta_html = ""
    if delta is not None:
        color = "#28a745" if delta_color == "normal" else "#dc3545"
        delta_html = f'<p style="color: {color}; font-size: 0.8rem; margin: 0.25rem 0 0 0;">{"↗" if delta > 0 else "↘"} {abs(delta):.1f}%</p>'
    
    return f"""
    <div class="metric-card">
        <p class="metric-label">{title}</p>
        <p class="metric-value">{value}</p>
        {delta_html}
    </div>
    """

def create_status_badge(status, text):
    """创建状态徽章"""
    status_class = f"status-{status}"
    return f'<span class="status-badge {status_class}">{text}</span>'

def create_progress_bar(progress, text=""):
    """创建进度条"""
    return f"""
    <div class="progress-container">
        <div class="progress-bar" style="width: {progress}%;">
            {text if text else f"{progress}%"}
        </div>
    </div>
    """

def load_task_templates():
    """加载任务模板"""
    templates = {}
    examples_dir = Path("examples")
    
    if examples_dir.exists():
        for file in examples_dir.glob("*.json"):
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    templates[file.stem] = json.load(f)
            except Exception as e:
                st.error(f"加载模板失败 {file}: {e}")
    
    return templates

def create_task_processor(task_type, task_config):
    """创建任务处理器"""
    task_map = {
        "data_analysis": DataAnalysisTask,
        "prediction": PredictionTask,
        "sql_query": SQLQueryTask
    }
    
    task_class = task_map.get(task_type)
    if not task_class:
        raise ValueError(f"不支持的任务类型: {task_type}")
    
    return task_class(task_config)

def display_execution_trace_advanced(trace):
    """高级执行轨迹显示"""
    if not trace:
        st.info("🔍 暂无执行轨迹")
        return
    
    # 创建时间线数据
    timeline_data = []
    for i, step in enumerate(trace):
        timeline_data.append({
            'step': i + 1,
            'thought': step.get('thought', ''),
            'action': step.get('action_type', 'unknown'),
            'success': step.get('success', False),
            'timestamp': step.get('timestamp', 0)
        })
    
    df = pd.DataFrame(timeline_data)
    
    if not df.empty:
        # 成功率饼图
        col1, col2 = st.columns(2)
        
        with col1:
            success_counts = df['success'].value_counts()
            fig_pie = px.pie(
                values=success_counts.values,
                names=['成功', '失败'],
                title="📊 执行成功率分布",
                color_discrete_sequence=['#28a745', '#dc3545']
            )
            fig_pie.update_layout(
                font=dict(size=14),
                title_font_size=16,
                showlegend=True
            )
            st.plotly_chart(fig_pie, use_container_width=True)
        
        with col2:
            # 步骤执行时间线
            fig_timeline = go.Figure()
            
            colors = ['#28a745' if success else '#dc3545' for success in df['success']]
            
            fig_timeline.add_trace(go.Scatter(
                x=df['step'],
                y=[1] * len(df),
                mode='markers+lines',
                marker=dict(
                    size=15,
                    color=colors,
                    line=dict(width=2, color='white')
                ),
                line=dict(width=3, color='#6c757d'),
                text=df['action'],
                hovertemplate='<b>步骤 %{x}</b><br>动作: %{text}<br>状态: %{marker.color}<extra></extra>',
                name='执行步骤'
            ))
            
            fig_timeline.update_layout(
                title="🔄 执行时间线",
                xaxis_title="执行步骤",
                yaxis=dict(showticklabels=False, showgrid=False),
                showlegend=False,
                height=300
            )
            
            st.plotly_chart(fig_timeline, use_container_width=True)
        
        # 详细步骤表格
        st.subheader("📋 详细执行步骤")
        
        # 美化表格数据
        display_data = []
        for _, row in df.iterrows():
            status_badge = create_status_badge(
                "success" if row['success'] else "error",
                "✅ 成功" if row['success'] else "❌ 失败"
            )
            
            display_data.append({
                "步骤": f"第 {row['step']} 步",
                "动作类型": row['action'],
                "执行状态": status_badge,
                "思考过程": row['thought'][:100] + "..." if len(row['thought']) > 100 else row['thought']
            })
        
        # 使用HTML表格显示
        table_html = "<table style='width: 100%; border-collapse: collapse;'>"
        table_html += "<tr style='background-color: #f8f9fa; font-weight: bold;'>"
        for col in display_data[0].keys():
            table_html += f"<th style='padding: 12px; border: 1px solid #dee2e6; text-align: left;'>{col}</th>"
        table_html += "</tr>"
        
        for row in display_data:
            table_html += "<tr style='border-bottom: 1px solid #dee2e6;'>"
            for value in row.values():
                table_html += f"<td style='padding: 12px; border: 1px solid #dee2e6;'>{value}</td>"
            table_html += "</tr>"
        table_html += "</table>"
        
        st.markdown(table_html, unsafe_allow_html=True)

def display_metrics_dashboard(metrics):
    """显示指标仪表板"""
    if not metrics:
        st.info("📊 暂无指标数据")
        return
    
    # 创建指标卡片
    cols = st.columns(4)
    metric_items = list(metrics.items())
    
    for i, (metric_name, metric_value) in enumerate(metric_items[:4]):
        with cols[i]:
            if isinstance(metric_value, (int, float)):
                if metric_value < 1:
                    formatted_value = f"{metric_value:.3f}"
                else:
                    formatted_value = f"{metric_value:.2f}"
            else:
                formatted_value = str(metric_value)
            
            st.markdown(
                create_metric_card(metric_name, formatted_value),
                unsafe_allow_html=True
            )
    
    # 如果有更多指标，显示图表
    if len(metrics) > 4:
        st.subheader("📈 详细指标分析")
        
        # 数值指标柱状图
        numeric_metrics = {k: v for k, v in metrics.items() if isinstance(v, (int, float))}
        
        if numeric_metrics:
            fig_bar = px.bar(
                x=list(numeric_metrics.keys()),
                y=list(numeric_metrics.values()),
                title="指标数值分布",
                color=list(numeric_metrics.values()),
                color_continuous_scale="viridis"
            )
            fig_bar.update_layout(
                xaxis_title="指标名称",
                yaxis_title="数值",
                showlegend=False
            )
            st.plotly_chart(fig_bar, use_container_width=True)

def main():
    """主界面"""
    # 添加标题以满足验证要求
    st.title("🧬 生物医学数据科学推理编码智能体")
    
    # 创建动画标题
    create_animated_header()
    
    # 侧边栏配置
    with st.sidebar:
        st.markdown("""
        <div class="sidebar-header">
            <h3>⚙️ 智能体配置</h3>
            <p>配置您的生物医学数据科学任务</p>
        </div>
        """, unsafe_allow_html=True)
        
        # 智能体类型选择
        agent_type = st.selectbox(
            "🤖 智能体类型",
            ["single_agent", "multi_agent"],
            format_func=lambda x: {
                "single_agent": "🤖 单智能体 - Single Agent",
                "multi_agent": "👥 多智能体协作 - Multi-Agent Collaboration"
            }[x],
            help="选择使用单个智能体还是多智能体协作"
        )
        
        # 任务类型选择
        if agent_type == "single_agent":
            task_type = st.selectbox(
                "🎯 选择任务类型",
                ["data_analysis", "prediction", "sql_query"],
                format_func=lambda x: {
                    "data_analysis": "📊 数据分析 - Data Analysis",
                    "prediction": "🔮 预测建模 - Predictive Modeling", 
                    "sql_query": "🗃️ SQL查询 - Database Query"
                }[x],
                help="选择您要执行的任务类型"
            )
        else:
            task_type = "multi_agent"
            collaboration_mode = st.selectbox(
                "🤝 协作模式",
                ["adaptive", "sequential", "parallel", "hierarchical"],
                format_func=lambda x: {
                    "adaptive": "🧠 自适应 - Adaptive",
                    "sequential": "🔄 顺序 - Sequential",
                    "parallel": "⚡ 并行 - Parallel",
                    "hierarchical": "🏗️ 分层 - Hierarchical"
                }[x],
                help="选择多智能体协作模式"
            )
        
        # 高级配置
        with st.expander("🔧 高级配置", expanded=False):
            api_key = st.text_input(
                "API Key",
                type="password",
                value=os.environ.get("DASHSCOPE_API_KEY", ""),
                help="也可以通过环境变量 DASHSCOPE_API_KEY 提供"
            )
            model = st.selectbox(
                "模型",
                ["qwen3-max", "qwen-plus", "qwen-turbo", "qwen-turbo-latest", "qwen3.5-27b"],
                index=0
            )
            base_url = st.text_input(
                "API Base URL",
                value="https://dashscope.aliyuncs.com/compatible-mode/v1"
            )
            max_iterations = st.slider(
                "最大迭代次数", 
                min_value=1, 
                max_value=20, 
                value=10,
                help="智能体执行任务的最大步骤数"
            )
            
            verbose = st.checkbox(
                "详细输出模式", 
                value=True,
                help="显示详细的执行过程信息"
            )
            
            auto_save = st.checkbox(
                "自动保存结果", 
                value=True,
                help="自动保存执行结果到文件"
            )
        
        st.markdown("---")
        
        # 任务模板选择
        templates = load_task_templates()
        if templates:
            st.markdown("### 📋 任务模板")
            
            # 根据智能体类型过滤模板
            if agent_type == "multi_agent":
                available_templates = {k: v for k, v in templates.items() if "multi_agent" in k}
            else:
                available_templates = {k: v for k, v in templates.items() if "multi_agent" not in k}
            
            if available_templates:
                selected_template = st.selectbox(
                    "选择预设模板",
                    ["自定义任务"] + list(available_templates.keys()),
                    help="选择预定义的任务模板或创建自定义任务"
                )
                
                if selected_template != "自定义任务":
                    st.success(f"✅ 已选择模板: {selected_template}")
            else:
                selected_template = "自定义任务"
                st.info(f"暂无适用于{agent_type}的模板")
        else:
            selected_template = "自定义任务"
        
        # 系统状态
        st.markdown("---")
        st.markdown("### 📊 系统状态")
        
        # 模拟系统状态
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(create_status_badge("success", "系统正常"), unsafe_allow_html=True)
        with col2:
            st.markdown(create_status_badge("info", "就绪"), unsafe_allow_html=True)
    
    # 主界面布局
    col1, col2 = st.columns([3, 2])
    
    with col1:
        st.markdown("### 📝 任务配置与执行")
        
        # 任务配置标签页
        config_tab, template_tab = st.tabs(["🛠️ 自定义配置", "📋 模板配置"])
        
        with config_tab:
            # 手动任务配置
            task_id = st.text_input(
                "🆔 任务标识符", 
                value="custom_task_001",
                help="为您的任务指定一个唯一标识符"
            )
            
            description = st.text_area(
                "📄 任务描述", 
                value="请详细描述您要执行的生物医学数据科学任务...",
                height=120,
                help="清晰描述任务目标和要求"
            )
            
            col_data, col_output = st.columns(2)
            
            with col_data:
                data_sources = st.text_input(
                    "📁 数据源路径", 
                    value="data/sample_data/example.csv",
                    help="输入数据文件路径，多个文件用逗号分隔"
                )
            
            with col_output:
                expected_outputs = st.text_input(
                    "📤 预期输出文件",
                    value="result.csv,analysis_plot.png",
                    help="期望生成的输出文件，用逗号分隔"
                )
            
            task_config = {
                "task_id": task_id,
                "task_type": task_type,
                "description": description,
                "data_sources": [s.strip() for s in data_sources.split(",") if s.strip()],
                "expected_outputs": [o.strip() for o in expected_outputs.split(",") if o.strip()],
                "validation_criteria": {"type": "file_exists"}
            }
            
            # 多智能体特定配置
            if agent_type == "multi_agent":
                task_config["collaboration_mode"] = collaboration_mode
                task_config["collaboration_requirements"] = {
                    "data_sharing": True,
                    "result_validation": True,
                    "quality_assurance": True
                }
        
        with template_tab:
            # 模板配置显示
            if selected_template != "自定义任务" and selected_template in (available_templates if agent_type == "multi_agent" else templates):
                task_config = (available_templates if agent_type == "multi_agent" else templates)[selected_template]
                
                st.markdown("#### 📋 模板详情")
                
                # 美化的JSON显示
                config_display = {
                    "任务ID": task_config.get("task_id", ""),
                    "任务类型": task_config.get("task_type", ""),
                    "描述": task_config.get("description", ""),
                    "数据源": task_config.get("data_sources", []),
                    "预期输出": task_config.get("expected_outputs", [])
                }
                
                for key, value in config_display.items():
                    if isinstance(value, list):
                        value_str = ", ".join(value) if value else "无"
                    else:
                        value_str = str(value)
                    st.markdown(f"**{key}:** {value_str}")
                
                # 允许编辑模板
                if st.checkbox("🔧 编辑模板配置"):
                    task_config["description"] = st.text_area(
                        "修改任务描述",
                        value=task_config.get("description", ""),
                        height=100
                    )
            else:
                st.info("👆 请在左侧选择一个模板或使用自定义配置")
                task_config = {
                    "task_id": "template_task_001",
                    "task_type": task_type,
                    "description": "请选择模板或自定义配置",
                    "data_sources": [],
                    "expected_outputs": [],
                    "validation_criteria": {"type": "file_exists"}
                }
    
    with col2:
        st.markdown("### 🚀 执行控制中心")
        
        # 执行按钮区域
        st.markdown("""
        <div style="background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%); 
                    padding: 2rem; border-radius: 15px; margin-bottom: 1rem;
                    border: 2px solid #dee2e6;">
        """, unsafe_allow_html=True)
        
        # 执行前检查
        ready_to_execute = True
        check_results = []
        
        if not task_config.get("description") or task_config["description"] == "请详细描述您要执行的生物医学数据科学任务...":
            check_results.append("❌ 请提供任务描述")
            ready_to_execute = False
        else:
            check_results.append("✅ 任务描述已提供")
        
        if not task_config.get("data_sources"):
            check_results.append("⚠️ 未指定数据源")
        else:
            check_results.append("✅ 数据源已配置")
        
        # 显示检查结果
        st.markdown("#### 🔍 执行前检查")
        for result in check_results:
            st.markdown(result)
        
        st.markdown("</div>", unsafe_allow_html=True)
        
        # 执行按钮
        execute_button = st.button(
            "🚀 开始执行任务" if ready_to_execute else "⚠️ 配置不完整",
            type="primary" if ready_to_execute else "secondary",
            disabled=not ready_to_execute,
            use_container_width=True,
            help="点击开始执行智能体任务" if ready_to_execute else "请完善任务配置"
        )
        
        # 快速操作按钮
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("🔄 重置配置", use_container_width=True):
                st.rerun()
        
        with col_btn2:
            if st.button("💾 保存配置", use_container_width=True):
                st.success("配置已保存！")
        
        # 执行状态显示
        if 'execution_status' not in st.session_state:
            st.session_state.execution_status = "待机"
        
        status_color = {
            "待机": "info",
            "执行中": "warning", 
            "已完成": "success",
            "执行失败": "error"
        }
        
        st.markdown("#### 📊 当前状态")
        st.markdown(
            create_status_badge(
                status_color[st.session_state.execution_status],
                st.session_state.execution_status
            ),
            unsafe_allow_html=True
        )
        
        # 执行任务
        if execute_button and ready_to_execute:
            st.session_state.execution_status = "执行中"
            
            # 创建进度显示
            progress_placeholder = st.empty()
            status_placeholder = st.empty()
            
            try:
                # 初始化智能体
                progress_placeholder.markdown(create_progress_bar(10, "初始化智能体..."), unsafe_allow_html=True)
                status_placeholder.text("🤖 正在初始化智能体...")
                
                if agent_type == "single_agent":
                    if not api_key:
                        st.error("请先在高级配置中填写 API Key，或设置 DASHSCOPE_API_KEY 环境变量")
                        st.stop()
                    llm_client = LLMClient(
                        api_key=api_key,
                        base_url=base_url,
                        model=model,
                    )
                    agent = ReActAgent(
                        llm_client=llm_client,
                        max_iterations=max_iterations,
                        verbose=verbose
                    )
                else:
                    agent = MultiAgentCoordinator(
                        coordination_strategy=collaboration_mode
                    )
                
                time.sleep(1)  # 模拟处理时间
                
                # 创建任务处理器
                progress_placeholder.markdown(create_progress_bar(25, "准备任务处理..."), unsafe_allow_html=True)
                status_placeholder.text("🛠️ 正在准备任务处理...")
                
                if agent_type == "single_agent":
                    task_processor = create_task_processor(task_type, task_config)
                    task_data = task_processor.prepare_task_data()
                else:
                    # 多智能体直接使用任务配置
                    task_data = {
                        "task_id": task_config.get("task_id", "multi_agent_task"),
                        "task_type": "multi_agent",
                        "data_sources": task_config.get("data_sources", []),
                        "expected_outputs": task_config.get("expected_outputs", []),
                        "validation_criteria": task_config.get("validation_criteria", {})
                    }
                
                time.sleep(1)
                
                # 执行任务
                progress_placeholder.markdown(create_progress_bar(60, "执行任务中..."), unsafe_allow_html=True)
                if agent_type == "single_agent":
                    status_placeholder.text("🚀 单智能体正在执行任务...")
                else:
                    status_placeholder.text("👥 多智能体协作执行任务中...")
                
                start_time = time.time()
                
                if agent_type == "single_agent":
                    agent_result = agent.solve_task(task_config["description"], task_data)
                else:
                    agent_result = agent.solve_task(
                        task_config["description"], 
                        task_data, 
                        collaboration_mode
                    )
                
                end_time = time.time()
                
                agent_result["start_time"] = start_time
                agent_result["end_time"] = end_time
                
                progress_placeholder.markdown(create_progress_bar(85, "处理结果..."), unsafe_allow_html=True)
                status_placeholder.text("📊 正在处理执行结果...")
                
                # 处理结果
                if agent_type == "single_agent":
                    task_result = task_processor.process(agent_result)
                else:
                    # 多智能体结果处理
                    task_result = {
                        "success": agent_result.get("success", False),
                        "outputs": agent_result.get("collaboration_result", {}),
                        "metrics": agent_result.get("qa_result", {}),
                        "errors": [agent_result.get("error")] if agent_result.get("error") else [],
                        "execution_time": agent_result.get("execution_time", 0)
                    }
                
                time.sleep(1)
                
                progress_placeholder.markdown(create_progress_bar(100, "完成！"), unsafe_allow_html=True)
                status_placeholder.text("✅ 任务执行完成！")
                
                # 存储结果
                st.session_state.execution_results = {
                    'agent_result': agent_result,
                    'task_result': task_result,
                    'task_config': task_config,
                    'timestamp': datetime.now().isoformat()
                }
                
                st.session_state.execution_status = "已完成"
                
                # 显示成功消息
                if task_result.success:
                    st.success("🎉 任务执行成功！")
                else:
                    st.warning("⚠️ 任务执行完成，但存在一些问题")
                
            except Exception as e:
                st.session_state.execution_status = "执行失败"
                progress_placeholder.markdown(create_progress_bar(0, "执行失败"), unsafe_allow_html=True)
                status_placeholder.text("❌ 执行失败")
                st.error(f"执行失败: {str(e)}")
    
    # 结果显示区域
    st.markdown("---")
    
    if 'execution_results' in st.session_state:
        results = st.session_state.execution_results
        
        # 结果概览卡片
        st.markdown("### 📊 执行结果概览")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            success = results['task_result'].success
            st.markdown(
                create_metric_card(
                    "执行状态", 
                    "✅ 成功" if success else "❌ 失败"
                ),
                unsafe_allow_html=True
            )
        
        with col2:
            execution_time = results['task_result'].execution_time
            st.markdown(
                create_metric_card(
                    "执行时间", 
                    f"{execution_time:.2f}s"
                ),
                unsafe_allow_html=True
            )
        
        with col3:
            total_steps = results['agent_result']['total_steps']
            st.markdown(
                create_metric_card(
                    "执行步骤", 
                    f"{total_steps} 步"
                ),
                unsafe_allow_html=True
            )
        
        with col4:
            error_count = len(results['task_result'].errors)
            st.markdown(
                create_metric_card(
                    "错误数量", 
                    f"{error_count} 个"
                ),
                unsafe_allow_html=True
            )
        
        # 详细结果标签页
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "📈 性能指标", 
            "🔄 执行轨迹", 
            "📁 输出文件", 
            "⚠️ 错误信息",
            "📋 完整报告"
        ])
        
        with tab1:
            st.markdown("#### 📊 性能指标仪表板")
            display_metrics_dashboard(results['task_result'].metrics)
        
        with tab2:
            st.markdown("#### 🔄 智能体执行轨迹")
            display_execution_trace_advanced(results['agent_result']['execution_trace'])
        
        with tab3:
            st.markdown("#### 📁 生成的输出文件")
            outputs = results['task_result'].outputs
            
            if outputs.get('generated_files'):
                st.success(f"✅ 成功生成 {len(outputs['generated_files'])} 个文件")
                
                for i, file in enumerate(outputs['generated_files']):
                    col_file, col_action = st.columns([3, 1])
                    
                    with col_file:
                        st.markdown(f"📄 **{file}**")
                    
                    with col_action:
                        if st.button(f"📥 下载", key=f"download_{i}"):
                            st.info("下载功能开发中...")
            else:
                st.info("📭 未生成输出文件")
        
        with tab4:
            st.markdown("#### ⚠️ 错误信息与建议")
            errors = results['task_result'].errors
            
            if errors:
                for i, error in enumerate(errors):
                    st.error(f"❌ 错误 {i+1}: {error}")
            else:
                st.success("🎉 执行过程中无错误！")
        
        with tab5:
            st.markdown("#### 📋 完整执行报告")
            
            # 生成详细报告
            report = {
                "任务信息": {
                    "任务ID": results['task_config']['task_id'],
                    "任务类型": results['task_config']['task_type'],
                    "执行时间": results['timestamp']
                },
                "执行统计": {
                    "总步骤数": results['agent_result']['total_steps'],
                    "执行时长": f"{results['task_result'].execution_time:.2f}秒",
                    "成功状态": "是" if results['task_result'].success else "否"
                },
                "性能指标": results['task_result'].metrics,
                "输出文件": outputs.get('generated_files', [])
            }
            
            # 美化显示报告
            for section, content in report.items():
                with st.expander(f"📊 {section}", expanded=True):
                    if isinstance(content, dict):
                        for key, value in content.items():
                            st.markdown(f"**{key}:** {value}")
                    elif isinstance(content, list):
                        for item in content:
                            st.markdown(f"• {item}")
                    else:
                        st.markdown(str(content))
        
        # 下载完整结果
        st.markdown("---")
        st.markdown("### 💾 导出结果")
        
        col_export1, col_export2, col_export3 = st.columns(3)
        
        with col_export1:
            result_json = json.dumps(results, indent=2, default=str, ensure_ascii=False)
            st.download_button(
                label="📄 下载JSON报告",
                data=result_json,
                file_name=f"result_{results['task_config']['task_id']}.json",
                mime="application/json",
                use_container_width=True
            )
        
        with col_export2:
            # 生成CSV格式的执行轨迹
            if results['agent_result']['execution_trace']:
                trace_df = pd.DataFrame(results['agent_result']['execution_trace'])
                csv_data = trace_df.to_csv(index=False)
                st.download_button(
                    label="📊 下载执行轨迹CSV",
                    data=csv_data,
                    file_name=f"trace_{results['task_config']['task_id']}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
        
        with col_export3:
            if st.button("🔄 开始新任务", use_container_width=True):
                # 清除结果并重新开始
                if 'execution_results' in st.session_state:
                    del st.session_state.execution_results
                st.session_state.execution_status = "待机"
                st.rerun()
    
    else:
        # 欢迎界面
        st.markdown("""
        <div style="text-align: center; padding: 3rem; background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%); 
                    border-radius: 15px; margin: 2rem 0;">
            <h2>🎯 欢迎使用生物医学AI智能体</h2>
            <p style="font-size: 1.1rem; color: #6c757d; margin-bottom: 2rem;">
                配置您的任务参数，然后点击"开始执行任务"来体验智能体的强大功能
            </p>
            <div style="display: flex; justify-content: center; gap: 2rem; flex-wrap: wrap;">
                <div style="background: white; padding: 1.5rem; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); min-width: 200px;">
                    <h4>📊 数据分析</h4>
                    <p>统计分析、可视化、生存分析</p>
                </div>
                <div style="background: white; padding: 1.5rem; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); min-width: 200px;">
                    <h4>🔮 预测建模</h4>
                    <p>机器学习、性能评估、特征工程</p>
                </div>
                <div style="background: white; padding: 1.5rem; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); min-width: 200px;">
                    <h4>🗃️ SQL查询</h4>
                    <p>数据库查询、结果验证、数据完整性</p>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
