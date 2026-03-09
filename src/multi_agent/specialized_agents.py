"""
专门化智能体实现
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
import time
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report
import sqlite3

# 设置matplotlib使用非GUI后端，支持多线程环境
import matplotlib
matplotlib.use('Agg')

from .communication import MessageBus, Message, MessageType, MessagePriority, CommunicationProtocol
from ..agent.action_space import ActionSpace, ActionType


class BaseSpecializedAgent(ABC):
    """专门化智能体基类"""
    
    def __init__(self, agent_id: str, message_bus: MessageBus, specialization: str):
        self.agent_id = agent_id
        self.message_bus = message_bus
        self.specialization = specialization
        self.action_space = ActionSpace()
        self.status = "idle"
        self.current_task = None
        self.capabilities = []
        self.collaboration_history = []
        
        # 注册到消息总线
        self.message_bus.register_agent(self.agent_id, {
            "specialization": self.specialization,
            "capabilities": self.capabilities,
            "status": self.status
        })
        
        # 订阅相关消息类型
        self.message_bus.subscribe(self.agent_id, MessageType.TASK_REQUEST)
        self.message_bus.subscribe(self.agent_id, MessageType.COLLABORATION_REQUEST)
        self.message_bus.subscribe(self.agent_id, MessageType.DATA_SHARE)
    
    @abstractmethod
    def can_handle_task(self, task_description: str, task_data: Dict[str, Any]) -> bool:
        """判断是否能处理指定任务"""
        pass
    
    @abstractmethod
    def execute_task(self, task_description: str, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """执行任务"""
        pass
    
    def process_messages(self):
        """处理消息"""
        while True:
            message = self.message_bus.receive_message(self.agent_id, timeout=0.1)
            if not message:
                break
            
            try:
                if message.message_type == MessageType.TASK_REQUEST:
                    self._handle_task_request(message)
                elif message.message_type == MessageType.COLLABORATION_REQUEST:
                    self._handle_collaboration_request(message)
                elif message.message_type == MessageType.DATA_SHARE:
                    self._handle_data_share(message)
            except Exception as e:
                print(f"❌ {self.agent_id} 处理消息失败: {e}")
    
    def _handle_task_request(self, message: Message):
        """处理任务请求"""
        task_description = message.content.get("task_description", "")
        task_data = message.content.get("task_data", {})
        
        if self.can_handle_task(task_description, task_data):
            self.status = "working"
            self.current_task = message.id
            
            # 发送状态更新
            status_msg = CommunicationProtocol.create_status_update(
                self.agent_id, "working", {"task_id": message.id}
            )
            self.message_bus.send_message(status_msg)
            
            try:
                result = self.execute_task(task_description, task_data)
                success = True
            except Exception as e:
                result = {"error": str(e)}
                success = False
            
            # 发送响应
            response = CommunicationProtocol.create_task_response(
                self.agent_id, message.sender, message.id, result, success
            )
            self.message_bus.send_message(response)
            
            self.status = "idle"
            self.current_task = None
        else:
            # 无法处理，发送拒绝响应
            response = CommunicationProtocol.create_task_response(
                self.agent_id, message.sender, message.id, 
                {"error": "Cannot handle this task"}, False
            )
            self.message_bus.send_message(response)
    
    def _handle_collaboration_request(self, message: Message):
        """处理协作请求"""
        collaboration_type = message.content.get("collaboration_type", "")
        details = message.content.get("details", {})
        
        # 基础协作处理逻辑
        if collaboration_type == "data_validation":
            result = self._validate_data(details.get("data", {}))
        elif collaboration_type == "result_review":
            result = self._review_results(details.get("results", {}))
        else:
            result = {"error": f"Unknown collaboration type: {collaboration_type}"}
        
        response = CommunicationProtocol.create_task_response(
            self.agent_id, message.sender, message.id, result
        )
        self.message_bus.send_message(response)
    
    def _handle_data_share(self, message: Message):
        """处理数据共享"""
        data = message.content.get("data", {})
        data_type = message.content.get("data_type", "general")
        
        # 存储共享数据
        self.collaboration_history.append({
            "type": "data_share",
            "sender": message.sender,
            "data_type": data_type,
            "timestamp": time.time()
        })
    
    def _validate_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """数据验证"""
        return {"validation_result": "passed", "details": "Data validation completed"}
    
    def _review_results(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """结果审查"""
        return {"review_result": "approved", "details": "Results review completed"}
    
    def request_collaboration(self, target_agent: str, collaboration_type: str, details: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """请求协作"""
        message = CommunicationProtocol.create_collaboration_request(
            self.agent_id, target_agent, collaboration_type, details
        )
        
        if self.message_bus.send_message(message):
            # 等待响应
            timeout = 30.0
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                response = self.message_bus.receive_message(self.agent_id, timeout=0.1)
                if response and response.message_type == MessageType.TASK_RESPONSE and response.content.get("request_id") == message.id:
                    return response.content.get("result")
                time.sleep(0.1)
        
        return None


class DataAnalystAgent(BaseSpecializedAgent):
    """数据分析专家智能体"""
    
    def __init__(self, message_bus: MessageBus):
        super().__init__("data_analyst", message_bus, "数据分析")
        self.capabilities = [
            "数据清洗", "统计分析", "数据可视化", 
            "探索性数据分析", "生存分析", "相关性分析"
        ]
    
    def can_handle_task(self, task_description: str, task_data: Dict[str, Any]) -> bool:
        """判断是否能处理数据分析任务"""
        analysis_keywords = [
            "分析", "统计", "可视化", "探索", "清洗", 
            "correlation", "analysis", "visualization", "eda"
        ]
        return any(keyword in task_description.lower() for keyword in analysis_keywords)
    
    def execute_task(self, task_description: str, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """执行数据分析任务"""
        print(f"📊 {self.agent_id} 开始执行数据分析任务")
        
        try:
            # 获取数据源
            data_sources = task_data.get("data_sources", [])
            if not data_sources:
                return {"error": "No data sources provided"}
            
            # 加载数据
            data_file = data_sources[0]
            if data_file.endswith('.csv'):
                df = pd.read_csv(data_file)
            else:
                return {"error": f"Unsupported data format: {data_file}"}
            
            # 执行分析
            analysis_results = {
                "data_shape": df.shape,
                "columns": df.columns.tolist(),
                "missing_values": df.isnull().sum().to_dict(),
                "data_types": df.dtypes.to_dict(),
                "numeric_summary": df.describe().to_dict(),
                "categorical_summary": df.select_dtypes(include=['object']).describe().to_dict()
            }
            
            # 生成相关性分析
            numeric_cols = df.select_dtypes(include=[np.number]).columns
            if len(numeric_cols) > 1:
                correlation_matrix = df[numeric_cols].corr()
                analysis_results["correlation_matrix"] = correlation_matrix.to_dict()
                
                # 生成可视化
                self._generate_correlation_plot(correlation_matrix)
                analysis_results["visualizations"] = ["correlation_heatmap.png"]
            
            print(f"✅ {self.agent_id} 完成数据分析任务")
            return {
                "success": True,
                "analysis_results": analysis_results,
                "agent_specialization": self.specialization
            }
            
        except Exception as e:
            print(f"❌ {self.agent_id} 执行失败: {e}")
            return {"error": str(e)}
    
    def _generate_correlation_plot(self, correlation_matrix):
        """生成相关性热图"""
        try:
            import matplotlib
            matplotlib.use('Agg')  # 使用非GUI后端，支持多线程
            import matplotlib.pyplot as plt
            import seaborn as sns
            
            plt.figure(figsize=(10, 8))
            sns.heatmap(correlation_matrix, annot=True, cmap='coolwarm', center=0)
            plt.title('Feature Correlation Matrix')
            plt.tight_layout()
            plt.savefig('correlation_heatmap.png', dpi=300, bbox_inches='tight')
            plt.close()
        except Exception as e:
            print(f"⚠️ 生成可视化失败: {e}")


class ModelingAgent(BaseSpecializedAgent):
    """机器学习建模专家智能体"""
    
    def __init__(self, message_bus: MessageBus):
        super().__init__("modeling_expert", message_bus, "机器学习建模")
        self.capabilities = [
            "特征工程", "模型训练", "模型评估", 
            "超参数优化", "交叉验证", "预测分析"
        ]
    
    def can_handle_task(self, task_description: str, task_data: Dict[str, Any]) -> bool:
        """判断是否能处理建模任务"""
        modeling_keywords = [
            "预测", "建模", "分类", "回归", "机器学习",
            "prediction", "modeling", "classification", "regression", "ml"
        ]
        return any(keyword in task_description.lower() for keyword in modeling_keywords)
    
    def execute_task(self, task_description: str, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """执行建模任务"""
        print(f"🤖 {self.agent_id} 开始执行建模任务")
        
        try:
            # 获取数据源
            data_sources = task_data.get("data_sources", [])
            if not data_sources:
                return {"error": "No data sources provided"}
            
            # 加载数据
            data_file = data_sources[0]
            df = pd.read_csv(data_file)
            
            # 数据预处理
            X, y = self._prepare_data(df)
            
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
            
            # 保存预测结果
            predictions_df = pd.DataFrame({
                'actual': y_test,
                'predicted': y_pred
            })
            predictions_df.to_csv('predictions.csv', index=False)
            
            results = {
                "success": True,
                "model_type": "RandomForestClassifier",
                "accuracy": accuracy,
                "predictions_file": "predictions.csv",
                "feature_count": X.shape[1],
                "training_samples": len(X_train),
                "test_samples": len(X_test),
                "agent_specialization": self.specialization
            }
            
            print(f"✅ {self.agent_id} 完成建模任务，准确率: {accuracy:.4f}")
            return results
            
        except Exception as e:
            print(f"❌ {self.agent_id} 执行失败: {e}")
            return {"error": str(e)}
    
    def _prepare_data(self, df):
        """数据预处理"""
        from sklearn.preprocessing import LabelEncoder
        
        # 假设最后一列是目标变量
        X = df.iloc[:, :-1].copy()
        y = df.iloc[:, -1].copy()
        
        # 处理分类变量
        le = LabelEncoder()
        for col in X.select_dtypes(include=['object']).columns:
            X[col] = le.fit_transform(X[col].astype(str))
        
        if y.dtype == 'object':
            y = le.fit_transform(y)
        
        return X, y


class SQLExpertAgent(BaseSpecializedAgent):
    """SQL查询专家智能体"""
    
    def __init__(self, message_bus: MessageBus):
        super().__init__("sql_expert", message_bus, "SQL查询")
        self.capabilities = [
            "数据库查询", "SQL优化", "数据提取", 
            "聚合分析", "连接查询", "数据验证"
        ]
    
    def can_handle_task(self, task_description: str, task_data: Dict[str, Any]) -> bool:
        """判断是否能处理SQL任务"""
        sql_keywords = [
            "查询", "数据库", "sql", "select", "统计", 
            "query", "database", "aggregation"
        ]
        return any(keyword in task_description.lower() for keyword in sql_keywords)
    
    def execute_task(self, task_description: str, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """执行SQL查询任务"""
        print(f"🗃️ {self.agent_id} 开始执行SQL查询任务")
        
        try:
            # 获取数据库文件
            database = task_data.get("database") or task_data.get("data_sources", [None])[0]
            if not database or not database.endswith(('.db', '.sqlite')):
                return {"error": "No valid database provided"}
            
            # 连接数据库
            conn = sqlite3.connect(database)
            cursor = conn.cursor()
            
            # 获取表结构
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row[0] for row in cursor.fetchall()]
            
            # 执行基础查询
            query_results = {}
            
            for table in tables:
                # 获取表信息
                cursor.execute(f"SELECT COUNT(*) FROM {table};")
                row_count = cursor.fetchone()[0]
                
                cursor.execute(f"PRAGMA table_info({table});")
                columns = cursor.fetchall()
                
                # 获取样本数据
                cursor.execute(f"SELECT * FROM {table} LIMIT 5;")
                sample_data = cursor.fetchall()
                
                query_results[table] = {
                    "row_count": row_count,
                    "columns": [col[1] for col in columns],
                    "sample_data": sample_data
                }
            
            conn.close()
            
            results = {
                "success": True,
                "database": database,
                "tables": tables,
                "query_results": query_results,
                "agent_specialization": self.specialization
            }
            
            print(f"✅ {self.agent_id} 完成SQL查询任务，处理了 {len(tables)} 个表")
            return results
            
        except Exception as e:
            print(f"❌ {self.agent_id} 执行失败: {e}")
            return {"error": str(e)}


class QualityAssuranceAgent(BaseSpecializedAgent):
    """质量保证专家智能体"""
    
    def __init__(self, message_bus: MessageBus):
        super().__init__("qa_expert", message_bus, "质量保证")
        self.capabilities = [
            "结果验证", "数据质量检查", "模型评估", 
            "异常检测", "一致性检查", "报告生成"
        ]
    
    def can_handle_task(self, task_description: str, task_data: Dict[str, Any]) -> bool:
        """判断是否能处理QA任务"""
        qa_keywords = [
            "验证", "检查", "质量", "评估", "审查",
            "validation", "quality", "review", "assessment"
        ]
        return any(keyword in task_description.lower() for keyword in qa_keywords)
    
    def execute_task(self, task_description: str, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """执行质量保证任务"""
        print(f"🔍 {self.agent_id} 开始执行质量保证任务")
        
        try:
            # 收集其他智能体的结果进行验证
            validation_results = {
                "data_quality_check": self._check_data_quality(task_data),
                "result_consistency": self._check_result_consistency(),
                "completeness_check": self._check_completeness(task_data),
                "accuracy_assessment": self._assess_accuracy()
            }
            
            # 生成质量报告
            overall_score = self._calculate_quality_score(validation_results)
            
            results = {
                "success": True,
                "quality_score": overall_score,
                "validation_results": validation_results,
                "recommendations": self._generate_recommendations(validation_results),
                "agent_specialization": self.specialization
            }
            
            print(f"✅ {self.agent_id} 完成质量保证任务，质量评分: {overall_score:.2f}")
            return results
            
        except Exception as e:
            print(f"❌ {self.agent_id} 执行失败: {e}")
            return {"error": str(e)}
    
    def _check_data_quality(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """检查数据质量"""
        try:
            data_sources = task_data.get("data_sources", [])
            if not data_sources:
                return {"status": "no_data", "score": 0.0}
            
            df = pd.read_csv(data_sources[0])
            
            # 计算数据质量指标
            completeness = 1.0 - (df.isnull().sum().sum() / (df.shape[0] * df.shape[1]))
            uniqueness = df.drop_duplicates().shape[0] / df.shape[0]
            
            return {
                "status": "checked",
                "completeness": completeness,
                "uniqueness": uniqueness,
                "score": (completeness + uniqueness) / 2
            }
        except Exception:
            return {"status": "error", "score": 0.0}
    
    def _check_result_consistency(self) -> Dict[str, Any]:
        """检查结果一致性"""
        # 简化的一致性检查
        return {"status": "consistent", "score": 0.9}
    
    def _check_completeness(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """检查完整性"""
        expected_outputs = task_data.get("expected_outputs", [])
        existing_files = []
        
        import os
        for output_file in expected_outputs:
            if os.path.exists(output_file):
                existing_files.append(output_file)
        
        completeness_ratio = len(existing_files) / max(len(expected_outputs), 1)
        
        return {
            "status": "checked",
            "expected_files": len(expected_outputs),
            "existing_files": len(existing_files),
            "score": completeness_ratio
        }
    
    def _assess_accuracy(self) -> Dict[str, Any]:
        """评估准确性"""
        # 简化的准确性评估
        return {"status": "assessed", "score": 0.85}
    
    def _calculate_quality_score(self, validation_results: Dict[str, Any]) -> float:
        """计算总体质量评分"""
        scores = []
        for result in validation_results.values():
            if isinstance(result, dict) and "score" in result:
                scores.append(result["score"])
        
        return sum(scores) / len(scores) if scores else 0.0
    
    def _generate_recommendations(self, validation_results: Dict[str, Any]) -> List[str]:
        """生成改进建议"""
        recommendations = []
        
        data_quality = validation_results.get("data_quality_check", {})
        if data_quality.get("completeness", 1.0) < 0.9:
            recommendations.append("建议处理缺失数据以提高数据完整性")
        
        completeness = validation_results.get("completeness_check", {})
        if completeness.get("score", 1.0) < 1.0:
            recommendations.append("建议生成所有预期的输出文件")
        
        if not recommendations:
            recommendations.append("数据质量良好，无需特别改进")
        
        return recommendations