"""
任务基类定义
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass


@dataclass
class TaskResult:
    """任务执行结果"""
    success: bool
    outputs: Dict[str, Any]
    metrics: Dict[str, float]
    errors: List[str]
    execution_time: float


class BaseTask(ABC):
    """任务基类"""
    
    def __init__(self, task_config: Dict[str, Any]):
        self.task_config = task_config
        self.task_id = task_config.get("task_id", "")
        self.description = task_config.get("description", "")
        self.data_sources = task_config.get("data_sources", [])
        self.expected_outputs = task_config.get("expected_outputs", [])
        self.validation_criteria = task_config.get("validation_criteria", {})
    
    @abstractmethod
    def process(self, agent_result: Dict[str, Any]) -> TaskResult:
        """处理任务结果"""
        pass
    
    @abstractmethod
    def validate(self, outputs: Dict[str, Any]) -> bool:
        """验证任务输出"""
        pass
    
    @abstractmethod
    def get_metrics(self, outputs: Dict[str, Any]) -> Dict[str, float]:
        """计算任务指标"""
        pass
    
    def prepare_task_data(self) -> Dict[str, Any]:
        """准备任务数据"""
        return {
            "task_id": self.task_id,
            "task_type": self.__class__.__name__.replace("Task", "").lower(),
            "description": self.description,
            "data_sources": self.data_sources,
            "expected_outputs": self.expected_outputs,
            "validation_criteria": self.validation_criteria
        }