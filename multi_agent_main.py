"""
多智能体协作主程序
"""

import argparse
import json
import sys
from pathlib import Path
import time

from src.multi_agent.coordinator import MultiAgentCoordinator
from src.utils.logger import setup_logger
from src.utils.helpers import load_config, save_results


def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="生物医学数据科学多智能体协作系统"
    )
    
    parser.add_argument(
        "--task-file",
        type=str,
        required=True,
        help="任务配置文件路径"
    )
    
    parser.add_argument(
        "--collaboration-mode",
        type=str,
        choices=["sequential", "parallel", "hierarchical", "adaptive"],
        default="adaptive",
        help="协作模式"
    )
    
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./multi_agent_output",
        help="输出目录路径"
    )
    
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="详细输出模式"
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


def main():
    """主函数"""
    # 解析参数
    args = parse_arguments()
    
    # 设置日志
    logger = setup_logger(verbose=args.verbose)
    logger.info("=" * 70)
    logger.info("🤖 生物医学数据科学多智能体协作系统")
    logger.info("=" * 70)
    
    # 创建输出目录
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 加载任务
    logger.info(f"📋 加载任务文件: {args.task_file}")
    task_config = load_task_file(args.task_file)
    
    # 初始化多智能体协调器
    logger.info(f"🤖 初始化多智能体协调器 (协作模式: {args.collaboration_mode})")
    coordinator = MultiAgentCoordinator(coordination_strategy=args.collaboration_mode)
    
    try:
        # 显示智能体状态
        agent_status = coordinator.get_agent_status()
        logger.info(f"👥 可用智能体数量: {len(agent_status)}")
        for agent_id, status in agent_status.items():
            logger.info(f"  - {agent_id}: {status.get('specialization', 'Unknown')}")
        
        # 执行任务
        task_description = task_config.get("description", "")
        task_data = {
            "task_id": task_config.get("task_id", "multi_agent_task"),
            "task_type": task_config.get("task_type", "multi_agent"),
            "data_sources": task_config.get("data_sources", []),
            "expected_outputs": task_config.get("expected_outputs", []),
            "validation_criteria": task_config.get("validation_criteria", {})
        }
        
        logger.info(f"🚀 开始执行多智能体协作任务")
        logger.info(f"📝 任务描述: {task_description}")
        
        start_time = time.time()
        result = coordinator.solve_task(
            task_description, 
            task_data, 
            args.collaboration_mode
        )
        end_time = time.time()
        
        # 输出结果
        logger.info("=" * 70)
        logger.info("📊 多智能体协作任务完成")
        logger.info("=" * 70)
        
        success = result.get("success", False)
        execution_time = result.get("execution_time", end_time - start_time)
        
        logger.info(f"✅ 执行状态: {'成功' if success else '失败'}")
        logger.info(f"⏱️ 执行时间: {execution_time:.2f}秒")
        logger.info(f"🤝 协作模式: {result.get('collaboration_mode', 'Unknown')}")
        logger.info(f"👥 参与智能体: {', '.join(result.get('participating_agents', []))}")
        
        if not success:
            logger.error(f"❌ 错误信息: {result.get('error', 'Unknown error')}")
        
        # 显示协作统计
        collaboration_result = result.get("collaboration_result", {})
        if collaboration_result:
            total_agents = collaboration_result.get("total_agents", 0)
            successful_agents = collaboration_result.get("successful_agents", 0)
            logger.info(f"📈 智能体成功率: {successful_agents}/{total_agents}")
        
        # 显示质量保证结果
        qa_result = result.get("qa_result", {})
        if qa_result and qa_result.get("success"):
            quality_score = qa_result.get("quality_score", 0)
            logger.info(f"🔍 质量评分: {quality_score:.2f}")
        
        # 保存结果
        result_file = output_dir / f"{task_config.get('task_id', 'multi_agent_task')}_result.json"
        save_results(result_file, {
            "task_config": task_config,
            "multi_agent_result": result,
            "execution_summary": coordinator.get_execution_summary()
        })
        logger.info(f"💾 结果已保存到: {result_file}")
        
        # 保存协作统计
        stats_file = output_dir / f"{task_config.get('task_id', 'multi_agent_task')}_stats.json"
        collaboration_stats = coordinator.get_collaboration_statistics()
        save_results(stats_file, collaboration_stats)
        logger.info(f"📊 协作统计已保存到: {stats_file}")
        
        # 显示详细统计信息
        if args.verbose and collaboration_stats:
            logger.info("\n📈 详细协作统计:")
            logger.info(f"  总任务数: {collaboration_stats.get('total_tasks', 0)}")
            logger.info(f"  成功率: {collaboration_stats.get('success_rate', 0):.2%}")
            logger.info(f"  平均执行时间: {collaboration_stats.get('average_execution_time', 0):.2f}秒")
            
            agent_participation = collaboration_stats.get('agent_participation', {})
            if agent_participation:
                logger.info("  智能体参与度:")
                for agent_id, count in agent_participation.items():
                    logger.info(f"    - {agent_id}: {count} 次")
        
        return 0 if success else 1
        
    except Exception as e:
        logger.error(f"❌ 执行过程中发生错误: {e}")
        return 1
        
    finally:
        # 关闭协调器
        coordinator.shutdown()
        logger.info("🔌 多智能体协调器已关闭")


if __name__ == "__main__":
    sys.exit(main())