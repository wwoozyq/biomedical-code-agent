"""
多智能体协调器
"""

from typing import Dict, Any, List, Optional
import time
import threading
from concurrent.futures import ThreadPoolExecutor

from .communication import MessageBus, Message, MessageType, CommunicationProtocol
from .specialized_agents import (
    DataAnalystAgent, ModelingAgent, SQLExpertAgent, QualityAssuranceAgent
)
from .collaboration_patterns import (
    SequentialPattern, ParallelPattern, HierarchicalPattern, AdaptivePattern
)


class MultiAgentCoordinator:
    """多智能体协调器 - 管理和协调多个专门化智能体"""
    
    def __init__(self, coordination_strategy: str = "adaptive"):
        self.message_bus = MessageBus()
        self.agents = {}
        self.collaboration_patterns = {}
        self.coordination_strategy = coordination_strategy
        self.execution_history = []
        self.active_tasks = {}
        
        # 初始化协作模式
        self._initialize_collaboration_patterns()
        
        # 初始化专门化智能体
        self._initialize_agents()
        
        print(f"🤖 多智能体协调器初始化完成")
        print(f"📊 协调策略: {coordination_strategy}")
        print(f"👥 可用智能体: {list(self.agents.keys())}")
    
    def _initialize_collaboration_patterns(self):
        """初始化协作模式"""
        self.collaboration_patterns = {
            "sequential": SequentialPattern(self.message_bus),
            "parallel": ParallelPattern(self.message_bus),
            "adaptive": AdaptivePattern(self.message_bus)
        }
    
    def _initialize_agents(self):
        """初始化专门化智能体"""
        try:
            # 创建专门化智能体
            self.agents = {
                "data_analyst": DataAnalystAgent(self.message_bus),
                "modeling_expert": ModelingAgent(self.message_bus),
                "sql_expert": SQLExpertAgent(self.message_bus),
                "qa_expert": QualityAssuranceAgent(self.message_bus)
            }
            
            # 为分层模式设置协调者
            if "data_analyst" in self.agents:
                self.collaboration_patterns["hierarchical"] = HierarchicalPattern(
                    self.message_bus, self.agents["data_analyst"]
                )
            
            print(f"✅ 成功初始化 {len(self.agents)} 个专门化智能体")
            
        except Exception as e:
            print(f"❌ 初始化智能体失败: {e}")
            self.agents = {}
    
    def solve_task(self, task_description: str, task_data: Dict[str, Any], 
                   collaboration_mode: str = None) -> Dict[str, Any]:
        """使用多智能体协作解决任务"""
        print(f"\n🚀 开始多智能体协作任务")
        print(f"📋 任务描述: {task_description}")
        print(f"🔧 协作模式: {collaboration_mode or self.coordination_strategy}")
        
        start_time = time.time()
        task_id = f"task_{int(start_time)}"
        
        try:
            # 选择协作模式
            pattern = self._select_collaboration_pattern(
                collaboration_mode or self.coordination_strategy,
                task_description, 
                task_data
            )
            
            # 选择参与的智能体
            participating_agents = self._select_agents(task_description, task_data)
            
            if not participating_agents:
                return {
                    "success": False,
                    "error": "No suitable agents found for the task",
                    "task_id": task_id
                }
            
            print(f"👥 参与智能体: {[agent.agent_id for agent in participating_agents]}")
            
            # 执行协作任务
            self.active_tasks[task_id] = {
                "description": task_description,
                "start_time": start_time,
                "status": "running"
            }
            
            collaboration_result = pattern.execute(
                task_description, task_data, participating_agents
            )
            
            # 执行质量保证
            qa_result = self._perform_quality_assurance(
                task_description, task_data, collaboration_result
            )
            
            end_time = time.time()
            execution_time = end_time - start_time
            
            # 生成最终结果
            final_result = {
                "success": True,
                "task_id": task_id,
                "collaboration_mode": pattern.name,
                "participating_agents": [agent.agent_id for agent in participating_agents],
                "collaboration_result": collaboration_result,
                "qa_result": qa_result,
                "execution_time": execution_time,
                "timestamp": time.time()
            }
            
            # 更新任务状态
            self.active_tasks[task_id]["status"] = "completed"
            self.active_tasks[task_id]["result"] = final_result
            
            # 记录执行历史
            self.execution_history.append(final_result)
            
            print(f"🎉 多智能体协作任务完成 (耗时: {execution_time:.2f}秒)")
            return final_result
            
        except Exception as e:
            error_result = {
                "success": False,
                "task_id": task_id,
                "error": str(e),
                "execution_time": time.time() - start_time,
                "timestamp": time.time()
            }
            
            self.active_tasks[task_id]["status"] = "failed"
            self.active_tasks[task_id]["error"] = str(e)
            
            print(f"❌ 多智能体协作任务失败: {e}")
            return error_result
    
    def _select_collaboration_pattern(self, mode: str, task_description: str, 
                                    task_data: Dict[str, Any]):
        """选择协作模式"""
        if mode in self.collaboration_patterns:
            return self.collaboration_patterns[mode]
        else:
            print(f"⚠️ 未知协作模式 {mode}，使用自适应模式")
            return self.collaboration_patterns["adaptive"]
    
    def _select_agents(self, task_description: str, task_data: Dict[str, Any]) -> List:
        """选择参与任务的智能体"""
        participating_agents = []
        
        for agent_id, agent in self.agents.items():
            try:
                if agent.can_handle_task(task_description, task_data):
                    participating_agents.append(agent)
                    print(f"✅ {agent_id} 可以处理此任务")
                else:
                    print(f"⚠️ {agent_id} 无法处理此任务")
            except Exception as e:
                print(f"❌ 检查 {agent_id} 能力时出错: {e}")
        
        return participating_agents
    
    def _perform_quality_assurance(self, task_description: str, task_data: Dict[str, Any],
                                 collaboration_result: Dict[str, Any]) -> Dict[str, Any]:
        """执行质量保证"""
        if "qa_expert" not in self.agents:
            return {"status": "skipped", "reason": "QA agent not available"}
        
        try:
            print(f"🔍 执行质量保证检查")
            
            qa_agent = self.agents["qa_expert"]
            
            # 准备QA任务数据
            qa_task_data = task_data.copy()
            qa_task_data["collaboration_result"] = collaboration_result
            
            qa_result = qa_agent.execute_task(
                f"质量保证检查: {task_description}", qa_task_data
            )
            
            print(f"✅ 质量保证检查完成")
            return qa_result
            
        except Exception as e:
            print(f"❌ 质量保证检查失败: {e}")
            return {"status": "failed", "error": str(e)}
    
    def get_agent_status(self) -> Dict[str, Any]:
        """获取所有智能体状态"""
        status = {}
        
        for agent_id, agent in self.agents.items():
            try:
                status[agent_id] = {
                    "specialization": agent.specialization,
                    "capabilities": agent.capabilities,
                    "current_status": agent.status,
                    "current_task": agent.current_task,
                    "collaboration_history_count": len(agent.collaboration_history)
                }
            except Exception as e:
                status[agent_id] = {"error": str(e)}
        
        return status
    
    def get_collaboration_statistics(self) -> Dict[str, Any]:
        """获取协作统计信息"""
        if not self.execution_history:
            return {"message": "No collaboration history"}
        
        stats = {
            "total_tasks": len(self.execution_history),
            "successful_tasks": sum(1 for task in self.execution_history if task.get("success")),
            "collaboration_modes": {},
            "agent_participation": {},
            "average_execution_time": 0,
            "message_bus_stats": self.message_bus.get_statistics()
        }
        
        total_time = 0
        
        for task in self.execution_history:
            # 统计协作模式
            mode = task.get("collaboration_mode", "unknown")
            stats["collaboration_modes"][mode] = stats["collaboration_modes"].get(mode, 0) + 1
            
            # 统计智能体参与度
            for agent_id in task.get("participating_agents", []):
                stats["agent_participation"][agent_id] = stats["agent_participation"].get(agent_id, 0) + 1
            
            # 累计执行时间
            total_time += task.get("execution_time", 0)
        
        stats["average_execution_time"] = total_time / len(self.execution_history)
        stats["success_rate"] = stats["successful_tasks"] / stats["total_tasks"]
        
        return stats
    
    def add_custom_agent(self, agent_id: str, agent_instance) -> bool:
        """添加自定义智能体"""
        try:
            if agent_id in self.agents:
                print(f"⚠️ 智能体 {agent_id} 已存在，将被替换")
            
            self.agents[agent_id] = agent_instance
            print(f"✅ 成功添加自定义智能体: {agent_id}")
            return True
            
        except Exception as e:
            print(f"❌ 添加自定义智能体失败: {e}")
            return False
    
    def remove_agent(self, agent_id: str) -> bool:
        """移除智能体"""
        try:
            if agent_id in self.agents:
                # 从消息总线注销
                self.message_bus.unregister_agent(agent_id)
                
                # 从智能体列表移除
                del self.agents[agent_id]
                
                print(f"✅ 成功移除智能体: {agent_id}")
                return True
            else:
                print(f"⚠️ 智能体 {agent_id} 不存在")
                return False
                
        except Exception as e:
            print(f"❌ 移除智能体失败: {e}")
            return False
    
    def shutdown(self):
        """关闭协调器"""
        try:
            # 注销所有智能体
            for agent_id in list(self.agents.keys()):
                self.message_bus.unregister_agent(agent_id)
            
            # 清空智能体列表
            self.agents.clear()
            
            # 清空活跃任务
            self.active_tasks.clear()
            
            print(f"🔌 多智能体协调器已关闭")
            
        except Exception as e:
            print(f"❌ 关闭协调器失败: {e}")
    
    def get_execution_summary(self) -> Dict[str, Any]:
        """获取执行摘要"""
        return {
            "coordinator_info": {
                "strategy": self.coordination_strategy,
                "available_agents": list(self.agents.keys()),
                "available_patterns": list(self.collaboration_patterns.keys())
            },
            "execution_stats": self.get_collaboration_statistics(),
            "agent_status": self.get_agent_status(),
            "active_tasks": len(self.active_tasks),
            "message_bus_active_agents": len(self.message_bus.get_active_agents())
        }