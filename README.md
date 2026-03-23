# 🧬 面向生物医学数据科学的推理编码智能体

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

基于 ReAct 范式的生物医学数据科学编码智能体，支持经验复用、多智能体协作和 Web 可视化监控。在 BioDSBench 数据集上，qwen3-max 模型达到 90.0% 的任务通过率。

## 特性

- **ReAct 智能体**：Thought → Action → Observation 闭环，持久化命名空间，主动验证 + 渐进式提示
- **反思与经验复用池**：任务结束后 LLM 结构化反思，提取代码模式存入 JSON，新任务检索相似经验做 few-shot 注入（+10% 通过率）
- **安全沙箱**：子进程隔离执行，超时控制，危险操作拦截
- **多智能体协作**：数据分析 / 建模 / SQL / QA 四类专门化智能体，支持顺序、并行、分层、自适应四种协作模式
- **Web 界面**：基于 Streamlit 的实时监控面板

## 快速开始

### 1. 克隆与安装

```bash
git clone https://github.com/wwoozyq/biomedical-code-agent.git
cd biomedical-code-agent

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. 配置 API Key

本项目使用阿里通义千问（DashScope）API：

```bash
export DASHSCOPE_API_KEY="your-api-key-here"
```

> 支持模型：`qwen3-max`（旗舰）、`qwen-turbo`（轻量），可在 `config/agent_config.yaml` 中修改。
> API Key 申请：https://dashscope.console.aliyun.com/

### 3. 准备 BioDSBench 数据集

数据集来源于论文 *"Making Large Language Models Reliable Data Science Programming Copilots for Biomedical Research"*（Nature Biomedical Engineering, 2026）。

**下载方式：**

数据集基于 cBioPortal 公开临床与基因组数据构建。预处理后的数据文件需放置在项目同级目录：

```
your-workspace/
├── biomedical-code-agent/    # 本项目
└── biodsbench_data/          # BioDSBench 数据集
    ├── README.md
    ├── breast_alpelisib_2020/
    │   ├── data_clinical_patient.csv
    │   ├── data_clinical_sample.csv
    │   ├── data_cna.csv
    │   └── data_mutations.csv
    ├── crc_nigerian_2020/
    └── ...（共 10+ 个 study 目录）
```

每个 study 目录包含 `data_clinical_patient.csv`、`data_clinical_sample.csv`，部分包含 `data_cna.csv`（拷贝数变异）和 `data_mutations.csv`（突变数据）。

如果你有课程提供的数据包，直接解压到上述路径即可。也可以从 [cBioPortal](https://www.cbioportal.org/) 手动下载对应 study 的数据。

### 4. 运行

```bash
# 单智能体演示（使用 sample_data）
python3 demo.py

# 多智能体协作演示
python3 demo_multi_agent.py

# 启动 Web 界面（浏览器访问 http://localhost:8501）
python3 run_web_interface.py

# 交互式问答
streamlit run chat.py
```

## 使用方法

### 单智能体模式

```bash
python3 main.py --task-type data_analysis --input-file examples/data_analysis_task.json --verbose
python3 main.py --task-type prediction --input-file examples/prediction_task.json --verbose
python3 main.py --task-type sql_query --input-file examples/sql_query_task.json --verbose
```

### 多智能体协作模式

```bash
python3 multi_agent_main.py --task-file examples/multi_agent_comprehensive_task.json --collaboration-mode adaptive --verbose
python3 multi_agent_main.py --task-file examples/multi_agent_parallel_task.json --collaboration-mode parallel --verbose
```

### Benchmark 评测

```bash
# 运行全部 108 道 BioDSBench 任务
python3 run_benchmark.py --model qwen3-max --use-experience

# 指定任务范围
python3 run_benchmark.py --model qwen-turbo --start 0 --end 30

# 启用安全沙箱
python3 run_benchmark.py --model qwen-turbo --sandbox
```

### 消融实验（30 题）

```bash
# 设置 API Key
export DASHSCOPE_API_KEY="your-key"

# 运行三组消融实验（支持断点续跑）
chmod +x run_ablation_30.sh
./run_ablation_30.sh

# 只跑某一组（1=qwen3-max, 2=turbo+exp, 3=turbo baseline）
./run_ablation_30.sh --only 2

# 只生成报告（实验已跑完时）
./run_ablation_30.sh --report
```

实验结果输出到 `benchmark_output_30*/` 目录，对比报告生成为 `ablation_report_30.md`。

## 实验结果

### BioDSBench 30 题消融实验

| 实验组 | 模型 | 经验池 | 通过率 | 平均步骤 | 平均耗时 |
|--------|------|--------|--------|---------|---------|
| qwen3-max (full) | qwen3-max | ✅ | **90.0%** | 3.20 | 66.9s |
| qwen-turbo + exp | qwen-turbo | ✅ | 66.7% | 5.17 | 31.1s |
| qwen-turbo (baseline) | qwen-turbo | ❌ | 56.7% | 5.40 | 27.2s |

经验池 + 反思机制在 qwen-turbo 上带来 +10% 的通过率提升。

## 项目结构

```
biomedical-code-agent/
├── main.py                     # 单智能体入口
├── multi_agent_main.py         # 多智能体入口
├── run_benchmark.py            # Benchmark 评测
├── run_ablation_30.sh          # 消融实验自动化脚本
├── ablation_analysis.py        # 消融实验分析
├── select_tasks.py             # 分层抽样选题
├── chat.py                     # Streamlit 交互式问答
├── app.py / run_web_interface.py  # Web 监控面板
├── demo.py / demo_multi_agent.py  # 演示脚本
├── config/agent_config.yaml    # 智能体配置
├── requirements.txt            # 依赖清单
├── src/
│   ├── agent/
│   │   ├── react_agent.py      # ReAct 智能体核心
│   │   ├── action_space.py     # 动作空间定义
│   │   ├── sandbox.py          # 安全沙箱
│   │   └── experience_pool.py  # 经验复用池 + 反思引擎
│   ├── multi_agent/
│   │   ├── coordinator.py      # 多智能体协调器
│   │   ├── specialized_agents.py  # 专门化智能体
│   │   ├── collaboration_patterns.py  # 协作模式
│   │   └── communication.py    # 消息总线
│   ├── tasks/
│   │   ├── biodsbench_loader.py  # BioDSBench 数据加载
│   │   ├── benchmark_runner.py   # 评测运行器
│   │   ├── data_analysis.py / prediction.py / sql_query.py
│   │   └── base_task.py
│   ├── llm/client.py           # LLM 客户端（DashScope API）
│   └── utils/
├── data/sample_data/           # 示例数据（随仓库提供）
├── examples/                   # 示例任务 JSON
├── 报告/                       # 实验报告 LaTeX 源文件
│   ├── thesis.tex              # 主文件（xelatex 编译）
│   ├── bibfile.bib             # 参考文献
│   └── body/chapter1-5.tex     # 各章节
└── logs/                       # 运行日志
```

## 配置说明

`config/agent_config.yaml` 主要配置项：

```yaml
agent:
  max_iterations: 10    # 最大迭代步数
  timeout: 300          # 单任务超时(秒)
  verbose: true         # 详细输出

execution:
  sandbox_enabled: true # 启用安全沙箱
  auto_save: true       # 自动保存结果
```

## 许可证

MIT License - 详见 [LICENSE](LICENSE)

## 致谢

- [ReAct](https://arxiv.org/abs/2210.03629) - 推理与行动协同范式
- [BioDSBench](https://www.nature.com/articles/s41551-024-01291-x) - 生物医学数据科学基准测试集
- [MedAgentGym](https://arxiv.org/abs/2503.21691) - 医学推理智能体训练框架
- [阿里通义千问](https://dashscope.console.aliyun.com/) - LLM API 服务
