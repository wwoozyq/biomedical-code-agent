"""
ReAct 智能体核心实现
"""

from typing import Dict, Any, List, Optional, Tuple
import json
import time
from dataclasses import dataclass
from enum import Enum

from .action_space import ActionSpace, ActionType


class AgentState(Enum):
    """智能体状态"""
    THINKING = "thinking"
    ACTING = "acting"
    OBSERVING = "observing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Step:
    """单步执行记录"""
    step_id: int
    thought: str
    action_type: Optional[ActionType]
    action_params: Optional[Dict[str, Any]]
    observation: Optional[Dict[str, Any]]
    timestamp: float
    state: AgentState


class ReActAgent:
    """基于 ReAct 范式的推理编码智能体"""
    
    def __init__(self, 
                 max_iterations: int = 10,
                 sandbox_dir: str = "./sandbox",
                 data_dir: str = "./data",
                 verbose: bool = True):
        self.max_iterations = max_iterations
        self.verbose = verbose
        self.action_space = ActionSpace(sandbox_dir, data_dir)
        
        # 执行状态
        self.current_step = 0
        self.execution_trace = []
        self.task_context = {}
        self.state = AgentState.THINKING
        
    def solve_task(self, task_description: str, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """解决给定任务"""
        self.task_context = {
            "description": task_description,
            "data": task_data,
            "start_time": time.time()
        }
        
        if self.verbose:
            print(f"开始执行任务: {task_description}")
            print(f"最大迭代次数: {self.max_iterations}")
        
        # 重置状态
        self.current_step = 0
        self.execution_trace = []
        self.state = AgentState.THINKING
        
        # 主执行循环
        while (self.current_step < self.max_iterations and 
               self.state not in [AgentState.COMPLETED, AgentState.FAILED]):
            
            try:
                # 思考阶段
                thought = self._generate_thought()
                
                # 行动阶段
                action_type, action_params = self._plan_action(thought)
                
                # 执行动作并观察结果
                observation = self._execute_and_observe(action_type, action_params)
                
                # 记录步骤
                step = Step(
                    step_id=self.current_step,
                    thought=thought,
                    action_type=action_type,
                    action_params=action_params,
                    observation=observation,
                    timestamp=time.time(),
                    state=self.state
                )
                self.execution_trace.append(step)
                
                if self.verbose:
                    self._print_step(step)
                
                # 检查是否完成任务
                if self._check_completion(observation):
                    self.state = AgentState.COMPLETED
                    break
                
                self.current_step += 1
                
            except Exception as e:
                error_step = Step(
                    step_id=self.current_step,
                    thought=f"执行出错: {str(e)}",
                    action_type=None,
                    action_params=None,
                    observation={"error": str(e)},
                    timestamp=time.time(),
                    state=AgentState.FAILED
                )
                self.execution_trace.append(error_step)
                self.state = AgentState.FAILED
                break
        
        # 生成最终结果
        return self._generate_final_result()
    
    def _generate_thought(self) -> str:
        """生成当前步骤的思考"""
        if self.current_step == 0:
            return f"分析任务: {self.task_context['description']}。需要首先了解数据结构和任务要求。"
        
        # 基于历史执行情况生成思考
        last_observation = self.execution_trace[-1].observation if self.execution_trace else {}
        
        if last_observation.get("success", False):
            return "上一步执行成功，继续下一步操作。"
        else:
            error_info = last_observation.get("error", "")
            return f"上一步执行失败: {error_info}。需要调试并修正问题。"
    
    def _plan_action(self, thought: str) -> Tuple[ActionType, Dict[str, Any]]:
        """基于思考规划下一步动作"""
        
        # 简化的动作规划逻辑
        if self.current_step == 0:
            # 第一步通常是了解数据
            data_sources = self.task_context["data"].get("data_sources", [])
            if data_sources:
                return ActionType.REQUEST_INFO, {
                    "data_source": data_sources[0],
                    "query_type": "describe"
                }
        
        # 检查上一步是否有错误
        if self.execution_trace and not self.execution_trace[-1].observation.get("success", True):
            error_info = self.execution_trace[-1].observation.get("error", "")
            return ActionType.DEBUGGING, {
                "error_info": error_info,
                "error_type": "runtime"
            }
        
        # 根据任务类型规划动作
        task_type = self.task_context["data"].get("task_type", "")
        
        if "analysis" in task_type.lower():
            return self._plan_analysis_action()
        elif "prediction" in task_type.lower():
            return self._plan_prediction_action()
        elif "sql" in task_type.lower():
            return self._plan_sql_action()
        else:
            # 默认执行代码
            return ActionType.CODE_EXECUTION, {
                "code": self._generate_default_code(),
                "language": "python"
            }
    
    def _plan_analysis_action(self) -> Tuple[ActionType, Dict[str, Any]]:
        """规划数据分析动作"""
        # 简化的分析流程
        if self.current_step <= 2:
            # 数据探索和清洗
            code = """
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

# 加载数据
data_file = 'data/sample_data/survival_data.csv'  # 根据实际情况调整
try:
    df = pd.read_csv(data_file)
    print("数据加载成功")
    print(f"数据形状: {df.shape}")
    print(f"列名: {df.columns.tolist()}")
    print("\\n数据预览:")
    print(df.head())
    print("\\n数据描述:")
    print(df.describe())
except Exception as e:
    print(f"数据加载失败: {e}")
"""
        else:
            # 分析和可视化
            code = """
# 数据分析和可视化
try:
    # 基础统计分析
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    if len(numeric_cols) > 0:
        correlation_matrix = df[numeric_cols].corr()
        
        # 绘制相关性热图
        plt.figure(figsize=(10, 8))
        sns.heatmap(correlation_matrix, annot=True, cmap='coolwarm', center=0)
        plt.title('特征相关性矩阵')
        plt.tight_layout()
        plt.savefig('correlation_heatmap.png', dpi=300, bbox_inches='tight')
        plt.show()
        
        print("相关性分析完成，图表已保存")
    
    # 生成分析报告
    analysis_report = {
        'data_shape': df.shape,
        'missing_values': df.isnull().sum().to_dict(),
        'numeric_summary': df.describe().to_dict() if len(numeric_cols) > 0 else {},
        'categorical_summary': df.select_dtypes(include=['object']).describe().to_dict()
    }
    
    print("分析报告:")
    print(analysis_report)
    
except Exception as e:
    print(f"分析过程出错: {e}")
"""
        
        return ActionType.CODE_EXECUTION, {
            "code": code,
            "language": "python",
            "save_file": f"analysis_step_{self.current_step}.py"
        }
    
    def _plan_prediction_action(self) -> Tuple[ActionType, Dict[str, Any]]:
        """规划预测建模动作"""
        code = """
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report
from sklearn.preprocessing import LabelEncoder

try:
    # 数据预处理
    # 假设最后一列是目标变量
    X = df.iloc[:, :-1]
    y = df.iloc[:, -1]
    
    # 处理分类变量
    le = LabelEncoder()
    for col in X.select_dtypes(include=['object']).columns:
        X[col] = le.fit_transform(X[col].astype(str))
    
    if y.dtype == 'object':
        y = le.fit_transform(y)
    
    # 划分训练测试集
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )
    
    # 训练模型
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)
    
    # 预测和评估
    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    
    print(f"模型准确率: {accuracy:.4f}")
    print("\\n分类报告:")
    print(classification_report(y_test, y_pred))
    
    # 保存预测结果
    predictions_df = pd.DataFrame({
        'actual': y_test,
        'predicted': y_pred
    })
    predictions_df.to_csv('predictions.csv', index=False)
    print("预测结果已保存到 predictions.csv")
    
except Exception as e:
    print(f"建模过程出错: {e}")
"""
        
        return ActionType.CODE_EXECUTION, {
            "code": code,
            "language": "python",
            "save_file": f"prediction_step_{self.current_step}.py"
        }
    
    def _plan_sql_action(self) -> Tuple[ActionType, Dict[str, Any]]:
        """规划SQL查询动作"""
        # 基于任务描述生成SQL查询
        description = self.task_context["description"]
        
        # 简化的SQL生成逻辑
        if "select" in description.lower() or "查询" in description:
            sql_code = "SELECT * FROM patients LIMIT 10;"
        elif "count" in description.lower() or "统计" in description:
            sql_code = "SELECT COUNT(*) as total_count FROM patients;"
        else:
            sql_code = "SELECT name FROM sqlite_master WHERE type='table';"
        
        database = self.task_context["data"].get("database", "sample.db")
        
        return ActionType.CODE_EXECUTION, {
            "code": sql_code,
            "language": "sql",
            "database": database
        }
    
    def _generate_default_code(self) -> str:
        """生成默认代码"""
        return """
# 默认探索性代码
import pandas as pd
import numpy as np

print("开始执行任务...")
print("当前工作目录内容:")
import os
print(os.listdir('.'))
"""
    
    def _execute_and_observe(self, action_type: ActionType, action_params: Dict[str, Any]) -> Dict[str, Any]:
        """执行动作并观察结果"""
        self.state = AgentState.ACTING
        
        observation = self.action_space.execute_action(action_type, action_params)
        
        self.state = AgentState.OBSERVING
        return observation
    
    def _check_completion(self, observation: Dict[str, Any]) -> bool:
        """检查任务是否完成"""
        # 简化的完成检查逻辑
        if not observation.get("success", False):
            return False
        
        # 检查是否达到预期输出
        expected_outputs = self.task_context["data"].get("expected_outputs", [])
        if expected_outputs:
            import os
            for output_file in expected_outputs:
                if not os.path.exists(output_file):
                    return False
        
        # 如果执行了足够多的步骤且没有错误，认为完成
        return self.current_step >= 3
    
    def _print_step(self, step: Step):
        """打印步骤信息"""
        print(f"\n--- 步骤 {step.step_id + 1} ---")
        print(f"思考: {step.thought}")
        if step.action_type:
            print(f"动作: {step.action_type.value}")
            print(f"参数: {step.action_params}")
        print(f"观察: {step.observation}")
        print(f"状态: {step.state.value}")
    
    def _generate_final_result(self) -> Dict[str, Any]:
        """生成最终结果"""
        end_time = time.time()
        execution_time = end_time - self.task_context["start_time"]
        
        result = {
            "task_description": self.task_context["description"],
            "success": self.state == AgentState.COMPLETED,
            "total_steps": len(self.execution_trace),
            "execution_time": execution_time,
            "final_state": self.state.value,
            "execution_trace": [
                {
                    "step_id": step.step_id,
                    "thought": step.thought,
                    "action_type": step.action_type.value if step.action_type else None,
                    "success": step.observation.get("success", False) if step.observation else False,
                    "timestamp": step.timestamp
                }
                for step in self.execution_trace
            ]
        }
        
        if self.verbose:
            print(f"\n=== 任务执行完成 ===")
            print(f"成功: {result['success']}")
            print(f"总步骤: {result['total_steps']}")
            print(f"执行时间: {execution_time:.2f}秒")
        
        return result
    
    def get_metrics(self) -> Dict[str, Any]:
        """获取性能指标"""
        if not self.execution_trace:
            return {}
        
        successful_steps = sum(1 for step in self.execution_trace 
                             if step.observation and step.observation.get("success", False))
        
        return {
            "success_rate": successful_steps / len(self.execution_trace),
            "total_attempts": len(self.execution_trace),
            "average_time_per_step": (time.time() - self.task_context["start_time"]) / len(self.execution_trace),
            "completion_status": self.state.value
        }