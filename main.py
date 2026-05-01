"""
生物医学数据科学推理编码智能体 - 主程序
"""

import argparse
import json
import os
import sys
from pathlib import Path
import time

from src.agent.react_agent import ReActAgent
from src.llm.client import LLMClient
from src.tasks.data_analysis import DataAnalysisTask
from src.tasks.prediction import PredictionTask
from src.tasks.sql_query import SQLQueryTask
from src.utils.logger import setup_logger, log_execution_trace
from src.utils.helpers import load_config, save_results


def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="生物医学数据科学推理编码智能体"
    )
    
    parser.add_argument(
        "--task-type",
        type=str,
        choices=["data_analysis", "prediction", "sql_query"],
        required=True,
        help="任务类型"
    )
    
    parser.add_argument(
        "--input-file",
        type=str,
        required=True,
        help="输入任务文件路径"
    )
    
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./output",
        help="输出目录路径"
    )
    
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=10,
        help="最大迭代次数"
    )
    
    parser.add_argument(
        "--config",
        type=str,
        default="config/agent_config.yaml",
        help="配置文件路径"
    )
    
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="详细输出模式"
    )
    
    parser.add_argument(
        "--sandbox-dir",
        type=str,
        default="./sandbox",
        help="沙箱目录路径"
    )
    
    parser.add_argument(
        "--data-dir",
        type=str,
        default="./data",
        help="数据目录路径"
    )

    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="LLM 模型名称，默认读取配置文件"
    )

    parser.add_argument(
        "--base-url",
        type=str,
        default=None,
        help="OpenAI 兼容 API base URL，默认读取配置文件"
    )

    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="API Key，也可通过 DASHSCOPE_API_KEY 环境变量提供"
    )
    
    return parser.parse_args()


def load_task_file(file_path: str) -> dict:
    """加载任务文件"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"错误: 任务文件不存在: {file_path}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"错误: 任务文件格式错误: {e}")
        sys.exit(1)


def create_task_processor(task_type: str, task_config: dict):
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


def main():
    """主函数"""
    # 解析参数
    args = parse_arguments()
    config = load_config(args.config)
    
    # 设置日志
    logger = setup_logger(verbose=args.verbose)
    logger.info("=" * 60)
    logger.info("生物医学数据科学推理编码智能体")
    logger.info("=" * 60)
    
    # 创建输出目录
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 加载任务
    logger.info(f"加载任务文件: {args.input_file}")
    task_config = load_task_file(args.input_file)
    
    # 创建任务处理器
    logger.info(f"任务类型: {args.task_type}")
    task_processor = create_task_processor(args.task_type, task_config)
    
    # 创建智能体
    logger.info(f"初始化智能体 (最大迭代次数: {args.max_iterations})")
    llm_config = config.get("llm", {}) if isinstance(config, dict) else {}
    api_key = args.api_key or os.environ.get("DASHSCOPE_API_KEY", "")
    if not api_key:
        logger.error("缺少 API Key，请设置 DASHSCOPE_API_KEY 或使用 --api-key")
        return 1

    llm_client = LLMClient(
        api_key=api_key,
        base_url=args.base_url or llm_config.get("base_url", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        model=args.model or llm_config.get("model", "qwen-plus"),
        temperature=llm_config.get("temperature", 0.0),
        max_tokens=llm_config.get("max_tokens", 4096),
    )
    agent = ReActAgent(
        llm_client=llm_client,
        max_iterations=args.max_iterations,
        sandbox_dir=args.sandbox_dir,
        data_dir=args.data_dir,
        verbose=args.verbose
    )
    
    # 准备任务数据
    task_data = task_processor.prepare_task_data()
    task_description = task_config.get("description", "")
    
    # 执行任务
    logger.info(f"开始执行任务: {task_config.get('task_id', 'unknown')}")
    logger.info(f"任务描述: {task_description}")
    
    start_time = time.time()
    agent_result = agent.solve_task(task_description, task_data)
    end_time = time.time()
    
    agent_result["start_time"] = start_time
    agent_result["end_time"] = end_time
    
    # 处理任务结果
    logger.info("处理任务结果...")
    task_result = task_processor.process(agent_result)
    
    # 输出结果
    logger.info("=" * 60)
    logger.info("任务执行完成")
    logger.info("=" * 60)
    logger.info(f"成功: {task_result.success}")
    logger.info(f"执行时间: {task_result.execution_time:.2f}秒")
    logger.info(f"总步骤数: {agent_result['total_steps']}")
    
    if task_result.errors:
        logger.warning(f"错误数量: {len(task_result.errors)}")
        for error in task_result.errors:
            logger.warning(f"  - {error}")
    
    logger.info("\n指标:")
    for metric_name, metric_value in task_result.metrics.items():
        logger.info(f"  {metric_name}: {metric_value}")
    
    # 保存结果
    result_file = output_dir / f"{task_config.get('task_id', 'task')}_result.json"
    save_results(result_file, {
        "task_config": task_config,
        "agent_result": agent_result,
        "task_result": {
            "success": task_result.success,
            "outputs": task_result.outputs,
            "metrics": task_result.metrics,
            "errors": task_result.errors,
            "execution_time": task_result.execution_time
        }
    })
    logger.info(f"\n结果已保存到: {result_file}")
    
    # 保存执行轨迹
    trace_file = output_dir / f"{task_config.get('task_id', 'task')}_trace.json"
    log_execution_trace(trace_file, agent_result["execution_trace"])
    logger.info(f"执行轨迹已保存到: {trace_file}")
    
    # 返回状态码
    return 0 if task_result.success else 1


if __name__ == "__main__":
    sys.exit(main())
