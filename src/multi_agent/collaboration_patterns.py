"""
多智能体协作模式
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from .communication import MessageBus, Message, MessageType, CommunicationProtocol
from .specialized_agents import BaseSpecializedAgent


class CollaborationPattern(ABC):
    """协作模式基类"""
    
    def __init__(self, name: str, message_bus: MessageBus):
        self.name = name
        self.message_bus = message_bus
        self.participants = []
        self.execution_log = []
    
    @abstractmethod
    def execute(self, task_description: str, task_data: Dict[str, Any], 
                agents: List[BaseSpecializedAgent]) -> Dict[str, Any]:
        """执行协作模式"""
        pass
    
    def log_execution(self, step: str, details: Dict[str, Any]):
        """记录执行日志"""
        self.execution_log.append({
            "step": step,
            "details": details,
            "timestamp": time.time()
        })


class SequentialPattern(CollaborationPattern):
    """顺序协作模式 - 智能体按顺序执行任务"""
    
    def __init__(self, message_bus: MessageBus):
        super().__init__("Sequential", message_bus)
    
    def execute(self, task_description: str, task_data: Dict[str, Any], 
                agents: List[BaseSpecializedAgent]) -> Dict[str, Any]:
        """顺序执行任务"""
        print(f"🔄 开始顺序协作模式执行")
        
        results = {}
        current_data = task_data.copy()
        
        for i, agent in enumerate(agents):
            print(f"📋 步骤 {i+1}: {agent.agent_id} 开始执行")
            
            # 检查智能体是否能处理任务
            if not agent.can_handle_task(task_description, current_data):
                print(f"⚠️ {agent.agent_id} 无法处理当前任务，跳过")
                continue
            
            try:
                # 执行任务
                start_time = time.time()
                agent_result = agent.execute_task(task_description, current_data)
                execution_time = time.time() - start_time
                
                # 记录结果
                results[agent.agent_id] = {
                    "result": agent_result,
                    "execution_time": execution_time,
                    "step_order": i + 1
                }
                
                # 更新数据供下一个智能体使用
                if agent_result.get("success"):
                    # 将结果添加到数据中供后续智能体使用
                    current_data[f"{agent.agent_id}_result"] = agent_result
                
                self.log_execution(f"agent_{agent.agent_id}_completed", {
                    "success": agent_result.get("success", False),
                    "execution_time": execution_time
                })
                
                print(f"✅ {agent.agent_id} 完成执行")
                
            except Exception as e:
                error_msg = f"❌ {agent.agent_id} 执行失败: {e}"
                print(error_msg)
                results[agent.agent_id] = {
                    "result": {"error": str(e)},
                    "execution_time": 0,
                    "step_order": i + 1
                }
                
                self.log_execution(f"agent_{agent.agent_id}_failed", {"error": str(e)})
        
        # 生成最终结果
        final_result = {
            "collaboration_pattern": self.name,
            "total_agents": len(agents),
            "successful_agents": sum(1 for r in results.values() if r["result"].get("success")),
            "agent_results": results,
            "execution_log": self.execution_log,
            "total_execution_time": sum(r["execution_time"] for r in results.values())
        }
        
        print(f"🎉 顺序协作模式执行完成")
        return final_result


class ParallelPattern(CollaborationPattern):
    """并行协作模式 - 智能体并行执行任务"""
    
    def __init__(self, message_bus: MessageBus, max_workers: int = 4):
        super().__init__("Parallel", message_bus)
        self.max_workers = max_workers
    
    def execute(self, task_description: str, task_data: Dict[str, Any], 
                agents: List[BaseSpecializedAgent]) -> Dict[str, Any]:
        """并行执行任务"""
        print(f"⚡ 开始并行协作模式执行 (最大并发: {self.max_workers})")
        
        results = {}
        
        # 筛选能处理任务的智能体
        capable_agents = [agent for agent in agents 
                         if agent.can_handle_task(task_description, task_data)]
        
        if not capable_agents:
            return {
                "collaboration_pattern": self.name,
                "error": "No agents capable of handling the task"
            }
        
        # 并行执行
        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(capable_agents))) as executor:
            # 提交任务
            future_to_agent = {
                executor.submit(self._execute_agent_task, agent, task_description, task_data): agent
                for agent in capable_agents
            }
            
            # 收集结果
            for future in as_completed(future_to_agent):
                agent = future_to_agent[future]
                try:
                    agent_result, execution_time = future.result()
                    results[agent.agent_id] = {
                        "result": agent_result,
                        "execution_time": execution_time
                    }
                    
                    self.log_execution(f"agent_{agent.agent_id}_completed", {
                        "success": agent_result.get("success", False),
                        "execution_time": execution_time
                    })
                    
                    print(f"✅ {agent.agent_id} 并行执行完成")
                    
                except Exception as e:
                    error_msg = f"❌ {agent.agent_id} 并行执行失败: {e}"
                    print(error_msg)
                    results[agent.agent_id] = {
                        "result": {"error": str(e)},
                        "execution_time": 0
                    }
                    
                    self.log_execution(f"agent_{agent.agent_id}_failed", {"error": str(e)})
        
        # 生成最终结果
        final_result = {
            "collaboration_pattern": self.name,
            "total_agents": len(capable_agents),
            "successful_agents": sum(1 for r in results.values() if r["result"].get("success")),
            "agent_results": results,
            "execution_log": self.execution_log,
            "max_execution_time": max((r["execution_time"] for r in results.values()), default=0)
        }
        
        print(f"🎉 并行协作模式执行完成")
        return final_result
    
    def _execute_agent_task(self, agent: BaseSpecializedAgent, task_description: str, 
                           task_data: Dict[str, Any]) -> tuple:
        """执行单个智能体任务"""
        start_time = time.time()
        result = agent.execute_task(task_description, task_data)
        execution_time = time.time() - start_time
        return result, execution_time


class HierarchicalPattern(CollaborationPattern):
    """分层协作模式 - 主智能体协调子智能体"""
    
    def __init__(self, message_bus: MessageBus, coordinator_agent: BaseSpecializedAgent):
        super().__init__("Hierarchical", message_bus)
        self.coordinator = coordinator_agent
    
    def execute(self, task_description: str, task_data: Dict[str, Any], 
                agents: List[BaseSpecializedAgent]) -> Dict[str, Any]:
        """分层执行任务"""
        print(f"🏗️ 开始分层协作模式执行 (协调者: {self.coordinator.agent_id})")
        
        results = {}
        
        # 第一阶段：协调者分析任务并制定计划
        print(f"📋 阶段1: {self.coordinator.agent_id} 分析任务")
        
        try:
            coordinator_result = self.coordinator.execute_task(task_description, task_data)
            results["coordinator"] = {
                "result": coordinator_result,
                "role": "coordinator"
            }
            
            self.log_execution("coordinator_analysis", {
                "success": coordinator_result.get("success", False)
            })
            
        except Exception as e:
            print(f"❌ 协调者执行失败: {e}")
            return {
                "collaboration_pattern": self.name,
                "error": f"Coordinator failed: {e}"
            }
        
        # 第二阶段：根据协调者的结果，分配任务给其他智能体
        print(f"📋 阶段2: 分配任务给专门智能体")
        
        subordinate_agents = [agent for agent in agents if agent != self.coordinator]
        
        for agent in subordinate_agents:
            if agent.can_handle_task(task_description, task_data):
                print(f"🔄 分配任务给 {agent.agent_id}")
                
                try:
                    # 将协调者的结果作为上下文传递
                    enhanced_task_data = task_data.copy()
                    enhanced_task_data["coordinator_context"] = coordinator_result
                    
                    start_time = time.time()
                    agent_result = agent.execute_task(task_description, enhanced_task_data)
                    execution_time = time.time() - start_time
                    
                    results[agent.agent_id] = {
                        "result": agent_result,
                        "execution_time": execution_time,
                        "role": "subordinate"
                    }
                    
                    self.log_execution(f"subordinate_{agent.agent_id}_completed", {
                        "success": agent_result.get("success", False),
                        "execution_time": execution_time
                    })
                    
                    print(f"✅ {agent.agent_id} 完成分配任务")
                    
                except Exception as e:
                    error_msg = f"❌ {agent.agent_id} 执行失败: {e}"
                    print(error_msg)
                    results[agent.agent_id] = {
                        "result": {"error": str(e)},
                        "execution_time": 0,
                        "role": "subordinate"
                    }
                    
                    self.log_execution(f"subordinate_{agent.agent_id}_failed", {"error": str(e)})
        
        # 第三阶段：协调者整合结果
        print(f"📋 阶段3: {self.coordinator.agent_id} 整合结果")
        
        try:
            # 收集所有子智能体的结果
            subordinate_results = {k: v for k, v in results.items() 
                                 if k != "coordinator" and v.get("role") == "subordinate"}
            
            # 请求协调者整合结果
            integration_task_data = task_data.copy()
            integration_task_data["subordinate_results"] = subordinate_results
            
            integration_result = self._request_integration(integration_task_data)
            results["integration"] = {
                "result": integration_result,
                "role": "integration"
            }
            
            self.log_execution("result_integration", {
                "success": integration_result.get("success", False)
            })
            
        except Exception as e:
            print(f"⚠️ 结果整合失败: {e}")
            results["integration"] = {
                "result": {"error": str(e)},
                "role": "integration"
            }
        
        # 生成最终结果
        final_result = {
            "collaboration_pattern": self.name,
            "coordinator": self.coordinator.agent_id,
            "total_agents": len(agents),
            "successful_agents": sum(1 for r in results.values() 
                                   if r["result"].get("success")),
            "agent_results": results,
            "execution_log": self.execution_log,
            "total_execution_time": sum(r.get("execution_time", 0) for r in results.values())
        }
        
        print(f"🎉 分层协作模式执行完成")
        return final_result
    
    def _request_integration(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """请求协调者整合结果"""
        # 简化的整合逻辑
        subordinate_results = task_data.get("subordinate_results", {})
        
        successful_results = {k: v for k, v in subordinate_results.items() 
                            if v["result"].get("success")}
        
        return {
            "success": True,
            "integrated_results": successful_results,
            "summary": f"Successfully integrated {len(successful_results)} results"
        }


class AdaptivePattern(CollaborationPattern):
    """自适应协作模式 - 根据任务动态选择协作方式"""
    
    def __init__(self, message_bus: MessageBus):
        super().__init__("Adaptive", message_bus)
        self.sequential_pattern = SequentialPattern(message_bus)
        self.parallel_pattern = ParallelPattern(message_bus)
    
    def execute(self, task_description: str, task_data: Dict[str, Any], 
                agents: List[BaseSpecializedAgent]) -> Dict[str, Any]:
        """自适应执行任务"""
        print(f"🧠 开始自适应协作模式执行")
        
        # 分析任务特征
        task_complexity = self._analyze_task_complexity(task_description, task_data)
        capable_agents = [agent for agent in agents 
                         if agent.can_handle_task(task_description, task_data)]
        
        # 选择最适合的协作模式
        if task_complexity["requires_sequential"] or len(capable_agents) <= 2:
            print("📋 选择顺序协作模式")
            pattern = self.sequential_pattern
        else:
            print("⚡ 选择并行协作模式")
            pattern = self.parallel_pattern
        
        # 执行选定的模式
        result = pattern.execute(task_description, task_data, agents)
        result["selected_pattern"] = pattern.name
        result["task_complexity"] = task_complexity
        
        return result
    
    def _analyze_task_complexity(self, task_description: str, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """分析任务复杂度"""
        complexity = {
            "requires_sequential": False,
            "data_dependency": False,
            "computational_intensive": False
        }
        
        # 简化的复杂度分析
        if any(keyword in task_description.lower() for keyword in ["依赖", "顺序", "sequential", "pipeline"]):
            complexity["requires_sequential"] = True
        
        if len(task_data.get("data_sources", [])) > 1:
            complexity["data_dependency"] = True
        
        if any(keyword in task_description.lower() for keyword in ["建模", "训练", "modeling", "training"]):
            complexity["computational_intensive"] = True
        
        return complexity