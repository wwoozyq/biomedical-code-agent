"""
预测建模任务处理器
"""

import os
import json
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Any, List
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, mean_squared_error, r2_score

from .base_task import BaseTask, TaskResult


class PredictionTask(BaseTask):
    """预测建模任务处理器"""
    
    def process(self, agent_result: Dict[str, Any]) -> TaskResult:
        """处理预测建模任务结果"""
        start_time = agent_result.get("start_time", 0)
        end_time = agent_result.get("end_time", 0)
        execution_time = end_time - start_time if end_time > start_time else 0
        
        outputs = self._collect_outputs()
        validation_success = self.validate(outputs)
        metrics = self.get_metrics(outputs) if validation_success else {}
        
        errors = []
        if not validation_success:
            errors.append("预测结果验证失败")
        
        # 检查执行轨迹中的错误
        execution_trace = agent_result.get("execution_trace", [])
        for step in execution_trace:
            if not step.get("success", True):
                errors.append(f"步骤 {step.get('step_id', 'unknown')} 执行失败")
        
        return TaskResult(
            success=validation_success and len(errors) == 0,
            outputs=outputs,
            metrics=metrics,
            errors=errors,
            execution_time=execution_time
        )
    
    def validate(self, outputs: Dict[str, Any]) -> bool:
        """验证预测建模输出"""
        validation_type = self.validation_criteria.get("type", "prediction_file")
        
        if validation_type == "prediction_file":
            # 检查预测文件是否存在且格式正确
            prediction_files = [f for f in self.expected_outputs if 'prediction' in f.lower()]
            if not prediction_files:
                return False
            
            for pred_file in prediction_files:
                if not os.path.exists(pred_file):
                    return False
                
                try:
                    df = pd.read_csv(pred_file)
                    # 检查是否包含必要的列
                    required_cols = self.validation_criteria.get("required_columns", ["predicted"])
                    for col in required_cols:
                        if col not in df.columns:
                            return False
                except Exception:
                    return False
            
            return True
        
        elif validation_type == "metrics_threshold":
            # 检查指标是否达到阈值
            return self._check_metrics_threshold(outputs)
        
        elif validation_type == "model_file":
            # 检查模型文件是否存在
            model_files = [f for f in self.expected_outputs if any(ext in f for ext in ['.pkl', '.joblib', '.h5', '.pt'])]
            return any(os.path.exists(f) for f in model_files)
        
        return True
    
    def get_metrics(self, outputs: Dict[str, Any]) -> Dict[str, float]:
        """计算预测建模指标"""
        metrics = {}
        
        # 文件输出指标
        metrics["files_generated"] = len([f for f in self.expected_outputs if os.path.exists(f)])
        metrics["expected_files_ratio"] = metrics["files_generated"] / max(len(self.expected_outputs), 1)
        
        # 预测性能指标
        try:
            prediction_files = [f for f in self.expected_outputs if 'prediction' in f.lower() and os.path.exists(f)]
            if prediction_files:
                df = pd.read_csv(prediction_files[0])
                
                if 'actual' in df.columns and 'predicted' in df.columns:
                    y_true = df['actual']
                    y_pred = df['predicted']
                    
                    # 判断是分类还是回归任务
                    if self._is_classification_task(y_true, y_pred):
                        metrics.update(self._calculate_classification_metrics(y_true, y_pred))
                    else:
                        metrics.update(self._calculate_regression_metrics(y_true, y_pred))
                
                metrics["prediction_count"] = len(df)
        except Exception:
            pass
        
        # 数据处理指标
        try:
            if self.data_sources and os.path.exists(self.data_sources[0]):
                df = pd.read_csv(self.data_sources[0])
                metrics["original_data_size"] = df.shape[0]
                metrics["feature_count"] = df.shape[1] - 1  # 假设最后一列是目标变量
                metrics["data_completeness"] = 1.0 - (df.isnull().sum().sum() / (df.shape[0] * df.shape[1]))
        except Exception:
            pass
        
        return metrics
    
    def _collect_outputs(self) -> Dict[str, Any]:
        """收集预测任务输出"""
        outputs = {}
        
        # 收集生成的文件
        generated_files = []
        for expected_file in self.expected_outputs:
            if os.path.exists(expected_file):
                generated_files.append(expected_file)
                
                try:
                    if expected_file.endswith('.csv'):
                        df = pd.read_csv(expected_file)
                        outputs[f"{expected_file}_shape"] = df.shape
                        outputs[f"{expected_file}_columns"] = df.columns.tolist()
                        
                        # 如果是预测文件，提取预测统计
                        if 'prediction' in expected_file.lower():
                            if 'predicted' in df.columns:
                                outputs[f"{expected_file}_prediction_stats"] = {
                                    "count": len(df),
                                    "unique_predictions": df['predicted'].nunique(),
                                    "prediction_distribution": df['predicted'].value_counts().to_dict()
                                }
                    
                    elif expected_file.endswith('.json'):
                        with open(expected_file, 'r') as f:
                            content = json.load(f)
                            outputs[f"{expected_file}_content"] = content
                            
                            # 如果是指标文件，提取关键指标
                            if 'metric' in expected_file.lower():
                                outputs["model_metrics"] = content
                
                except Exception as e:
                    outputs[f"{expected_file}_error"] = str(e)
        
        outputs["generated_files"] = generated_files
        
        return outputs
    
    def _is_classification_task(self, y_true, y_pred) -> bool:
        """判断是否为分类任务"""
        # 简单启发式：如果唯一值数量较少，认为是分类任务
        unique_true = len(np.unique(y_true))
        unique_pred = len(np.unique(y_pred))
        
        return unique_true <= 20 and unique_pred <= 20
    
    def _calculate_classification_metrics(self, y_true, y_pred) -> Dict[str, float]:
        """计算分类指标"""
        try:
            metrics = {}
            
            # 基础指标
            metrics["accuracy"] = accuracy_score(y_true, y_pred)
            
            # 多分类情况使用macro平均
            average_method = 'binary' if len(np.unique(y_true)) == 2 else 'macro'
            
            metrics["precision"] = precision_score(y_true, y_pred, average=average_method, zero_division=0)
            metrics["recall"] = recall_score(y_true, y_pred, average=average_method, zero_division=0)
            metrics["f1_score"] = f1_score(y_true, y_pred, average=average_method, zero_division=0)
            
            return metrics
        except Exception:
            return {"accuracy": 0.0}
    
    def _calculate_regression_metrics(self, y_true, y_pred) -> Dict[str, float]:
        """计算回归指标"""
        try:
            metrics = {}
            
            metrics["mse"] = mean_squared_error(y_true, y_pred)
            metrics["rmse"] = np.sqrt(metrics["mse"])
            metrics["r2_score"] = r2_score(y_true, y_pred)
            
            # 平均绝对误差
            metrics["mae"] = np.mean(np.abs(y_true - y_pred))
            
            # 平均绝对百分比误差
            non_zero_mask = y_true != 0
            if np.any(non_zero_mask):
                metrics["mape"] = np.mean(np.abs((y_true[non_zero_mask] - y_pred[non_zero_mask]) / y_true[non_zero_mask])) * 100
            
            return metrics
        except Exception:
            return {"mse": float('inf')}
    
    def _check_metrics_threshold(self, outputs: Dict[str, Any]) -> bool:
        """检查指标是否达到阈值"""
        thresholds = self.validation_criteria.get("thresholds", {})
        model_metrics = outputs.get("model_metrics", {})
        
        for metric_name, threshold in thresholds.items():
            if metric_name not in model_metrics:
                return False
            
            metric_value = model_metrics[metric_name]
            
            # 对于错误类指标（如MSE），值应该小于阈值
            if metric_name.lower() in ['mse', 'rmse', 'mae']:
                if metric_value > threshold:
                    return False
            else:
                # 对于性能类指标（如accuracy, f1），值应该大于阈值
                if metric_value < threshold:
                    return False
        
        return True