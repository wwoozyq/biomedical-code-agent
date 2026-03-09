"""
数据分析任务处理器
"""

import os
import json
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Any, List
import matplotlib.pyplot as plt

from .base_task import BaseTask, TaskResult


class DataAnalysisTask(BaseTask):
    """数据分析任务处理器"""
    
    def process(self, agent_result: Dict[str, Any]) -> TaskResult:
        """处理数据分析任务结果"""
        start_time = agent_result.get("start_time", 0)
        end_time = agent_result.get("end_time", 0)
        execution_time = end_time - start_time if end_time > start_time else 0
        
        outputs = self._collect_outputs()
        validation_success = self.validate(outputs)
        metrics = self.get_metrics(outputs) if validation_success else {}
        
        errors = []
        if not validation_success:
            errors.append("输出验证失败")
        
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
        """验证数据分析输出"""
        validation_type = self.validation_criteria.get("type", "file_exists")
        checks = self.validation_criteria.get("checks", [])
        
        if validation_type == "file_exists":
            # 检查预期输出文件是否存在
            for expected_file in self.expected_outputs:
                if not os.path.exists(expected_file):
                    return False
            return True
        
        elif validation_type == "assertion":
            # 执行断言检查
            return self._run_assertion_checks(checks, outputs)
        
        elif validation_type == "statistical_test":
            # 执行统计测试
            return self._run_statistical_tests(checks, outputs)
        
        return True
    
    def get_metrics(self, outputs: Dict[str, Any]) -> Dict[str, float]:
        """计算数据分析指标"""
        metrics = {}
        
        # 文件输出指标
        metrics["files_generated"] = len([f for f in self.expected_outputs if os.path.exists(f)])
        metrics["expected_files_ratio"] = metrics["files_generated"] / max(len(self.expected_outputs), 1)
        
        # 数据质量指标
        try:
            if self.data_sources:
                df = pd.read_csv(self.data_sources[0])
                metrics["data_completeness"] = 1.0 - (df.isnull().sum().sum() / (df.shape[0] * df.shape[1]))
                metrics["data_size"] = df.shape[0]
                metrics["feature_count"] = df.shape[1]
        except Exception:
            pass
        
        # 可视化指标
        plot_files = [f for f in self.expected_outputs if f.endswith(('.png', '.jpg', '.pdf', '.svg'))]
        metrics["plots_generated"] = len([f for f in plot_files if os.path.exists(f)])
        
        return metrics
    
    def _collect_outputs(self) -> Dict[str, Any]:
        """收集任务输出"""
        outputs = {}
        
        # 收集生成的文件
        generated_files = []
        for expected_file in self.expected_outputs:
            if os.path.exists(expected_file):
                generated_files.append(expected_file)
                
                # 尝试读取文件内容
                try:
                    if expected_file.endswith('.csv'):
                        df = pd.read_csv(expected_file)
                        outputs[f"{expected_file}_shape"] = df.shape
                        outputs[f"{expected_file}_columns"] = df.columns.tolist()
                    elif expected_file.endswith('.json'):
                        with open(expected_file, 'r') as f:
                            outputs[f"{expected_file}_content"] = json.load(f)
                    elif expected_file.endswith(('.png', '.jpg', '.pdf', '.svg')):
                        outputs[f"{expected_file}_size"] = os.path.getsize(expected_file)
                except Exception as e:
                    outputs[f"{expected_file}_error"] = str(e)
        
        outputs["generated_files"] = generated_files
        
        # 收集统计摘要
        try:
            if self.data_sources and os.path.exists(self.data_sources[0]):
                df = pd.read_csv(self.data_sources[0])
                outputs["data_summary"] = {
                    "shape": df.shape,
                    "dtypes": df.dtypes.to_dict(),
                    "missing_values": df.isnull().sum().to_dict(),
                    "numeric_summary": df.describe().to_dict()
                }
        except Exception:
            pass
        
        return outputs
    
    def _run_assertion_checks(self, checks: List[str], outputs: Dict[str, Any]) -> bool:
        """运行断言检查"""
        for check in checks:
            if check == "file_exists":
                for expected_file in self.expected_outputs:
                    if not os.path.exists(expected_file):
                        return False
            
            elif check == "data_not_empty":
                try:
                    if self.data_sources:
                        df = pd.read_csv(self.data_sources[0])
                        if df.empty:
                            return False
                except Exception:
                    return False
            
            elif check == "plot_generated":
                plot_files = [f for f in self.expected_outputs if f.endswith(('.png', '.jpg', '.pdf', '.svg'))]
                if not any(os.path.exists(f) for f in plot_files):
                    return False
            
            elif check == "summary_stats":
                # 检查是否生成了统计摘要
                summary_files = [f for f in self.expected_outputs if 'summary' in f.lower()]
                if not any(os.path.exists(f) for f in summary_files):
                    return False
        
        return True
    
    def _run_statistical_tests(self, checks: List[str], outputs: Dict[str, Any]) -> bool:
        """运行统计测试"""
        try:
            if not self.data_sources or not os.path.exists(self.data_sources[0]):
                return False
            
            df = pd.read_csv(self.data_sources[0])
            
            for check in checks:
                if check == "normality_test":
                    # 检查数值列的正态性
                    numeric_cols = df.select_dtypes(include=[np.number]).columns
                    if len(numeric_cols) == 0:
                        return False
                
                elif check == "correlation_analysis":
                    # 检查相关性分析
                    numeric_cols = df.select_dtypes(include=[np.number]).columns
                    if len(numeric_cols) < 2:
                        return False
                    
                    corr_matrix = df[numeric_cols].corr()
                    if corr_matrix.isnull().all().all():
                        return False
                
                elif check == "missing_value_analysis":
                    # 检查缺失值分析
                    missing_counts = df.isnull().sum()
                    # 至少应该计算了缺失值统计
                    if missing_counts is None:
                        return False
            
            return True
            
        except Exception:
            return False