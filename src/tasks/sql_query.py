"""
SQL查询任务处理器
"""

import os
import json
import sqlite3
import pandas as pd
from pathlib import Path
from typing import Dict, Any, List, Tuple

from .base_task import BaseTask, TaskResult


class SQLQueryTask(BaseTask):
    """SQL查询任务处理器"""
    
    def process(self, agent_result: Dict[str, Any]) -> TaskResult:
        """处理SQL查询任务结果"""
        start_time = agent_result.get("start_time", 0)
        end_time = agent_result.get("end_time", 0)
        execution_time = end_time - start_time if end_time > start_time else 0
        
        outputs = self._collect_outputs()
        validation_success = self.validate(outputs)
        metrics = self.get_metrics(outputs) if validation_success else {}
        
        errors = []
        if not validation_success:
            errors.append("SQL查询结果验证失败")
        
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
        """验证SQL查询输出"""
        validation_type = self.validation_criteria.get("type", "result_comparison")
        
        if validation_type == "result_comparison":
            return self._validate_result_comparison(outputs)
        elif validation_type == "schema_check":
            return self._validate_schema_check(outputs)
        elif validation_type == "row_count":
            return self._validate_row_count(outputs)
        elif validation_type == "data_integrity":
            return self._validate_data_integrity(outputs)
        
        return True
    
    def get_metrics(self, outputs: Dict[str, Any]) -> Dict[str, float]:
        """计算SQL查询指标"""
        metrics = {}
        
        # 查询执行指标
        query_results = outputs.get("query_results", [])
        metrics["queries_executed"] = len(query_results)
        
        successful_queries = sum(1 for result in query_results if result.get("success", False))
        metrics["query_success_rate"] = successful_queries / max(len(query_results), 1)
        
        # 结果数据指标
        total_rows = 0
        total_columns = 0
        
        for result in query_results:
            if result.get("success", False) and "results" in result:
                results = result["results"]
                if isinstance(results, list):
                    total_rows += len(results)
                    if results and isinstance(results[0], (list, tuple)):
                        total_columns = max(total_columns, len(results[0]))
        
        metrics["total_rows_returned"] = total_rows
        metrics["max_columns_returned"] = total_columns
        
        # 数据库连接指标
        database_file = self.task_config.get("database", "")
        if database_file and os.path.exists(database_file):
            try:
                conn = sqlite3.connect(database_file)
                cursor = conn.cursor()
                
                # 获取表数量
                cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table';")
                table_count = cursor.fetchone()[0]
                metrics["database_table_count"] = table_count
                
                conn.close()
            except Exception:
                pass
        
        return metrics
    
    def _collect_outputs(self) -> Dict[str, Any]:
        """收集SQL查询输出"""
        outputs = {}
        
        # 收集生成的文件
        generated_files = []
        query_results = []
        
        for expected_file in self.expected_outputs:
            if os.path.exists(expected_file):
                generated_files.append(expected_file)
                
                try:
                    if expected_file.endswith('.csv'):
                        df = pd.read_csv(expected_file)
                        outputs[f"{expected_file}_shape"] = df.shape
                        outputs[f"{expected_file}_columns"] = df.columns.tolist()
                        outputs[f"{expected_file}_data"] = df.to_dict('records')
                    
                    elif expected_file.endswith('.json'):
                        with open(expected_file, 'r') as f:
                            content = json.load(f)
                            outputs[f"{expected_file}_content"] = content
                            
                            # 如果是查询结果文件
                            if 'result' in expected_file.lower():
                                query_results.append({
                                    "success": True,
                                    "results": content,
                                    "file": expected_file
                                })
                
                except Exception as e:
                    outputs[f"{expected_file}_error"] = str(e)
                    query_results.append({
                        "success": False,
                        "error": str(e),
                        "file": expected_file
                    })
        
        outputs["generated_files"] = generated_files
        outputs["query_results"] = query_results
        
        # 尝试直接执行数据库查询获取结果
        database_file = self.task_config.get("database", "")
        if database_file and os.path.exists(database_file):
            outputs["database_info"] = self._get_database_info(database_file)
        
        return outputs
    
    def _get_database_info(self, database_file: str) -> Dict[str, Any]:
        """获取数据库信息"""
        try:
            conn = sqlite3.connect(database_file)
            cursor = conn.cursor()
            
            # 获取表列表
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row[0] for row in cursor.fetchall()]
            
            # 获取每个表的信息
            table_info = {}
            for table in tables:
                cursor.execute(f"PRAGMA table_info({table});")
                columns = cursor.fetchall()
                
                cursor.execute(f"SELECT COUNT(*) FROM {table};")
                row_count = cursor.fetchone()[0]
                
                table_info[table] = {
                    "columns": columns,
                    "row_count": row_count
                }
            
            conn.close()
            
            return {
                "tables": tables,
                "table_info": table_info,
                "total_tables": len(tables)
            }
        
        except Exception as e:
            return {"error": str(e)}
    
    def _validate_result_comparison(self, outputs: Dict[str, Any]) -> bool:
        """验证结果比较"""
        expected_results = self.validation_criteria.get("expected_results", [])
        query_results = outputs.get("query_results", [])
        
        if not expected_results or not query_results:
            return False
        
        # 简化的结果比较逻辑
        for expected in expected_results:
            found_match = False
            
            for actual in query_results:
                if not actual.get("success", False):
                    continue
                
                actual_results = actual.get("results", [])
                
                # 比较结果集
                if self._compare_results(expected, actual_results):
                    found_match = True
                    break
            
            if not found_match:
                return False
        
        return True
    
    def _validate_schema_check(self, outputs: Dict[str, Any]) -> bool:
        """验证模式检查"""
        expected_schema = self.validation_criteria.get("expected_schema", {})
        database_info = outputs.get("database_info", {})
        
        if not expected_schema or not database_info:
            return False
        
        table_info = database_info.get("table_info", {})
        
        for table_name, expected_columns in expected_schema.items():
            if table_name not in table_info:
                return False
            
            actual_columns = [col[1] for col in table_info[table_name]["columns"]]  # 列名在索引1
            
            for expected_col in expected_columns:
                if expected_col not in actual_columns:
                    return False
        
        return True
    
    def _validate_row_count(self, outputs: Dict[str, Any]) -> bool:
        """验证行数"""
        expected_counts = self.validation_criteria.get("expected_row_counts", {})
        database_info = outputs.get("database_info", {})
        
        if not expected_counts or not database_info:
            return False
        
        table_info = database_info.get("table_info", {})
        
        for table_name, expected_count in expected_counts.items():
            if table_name not in table_info:
                return False
            
            actual_count = table_info[table_name]["row_count"]
            
            # 支持范围检查
            if isinstance(expected_count, dict):
                min_count = expected_count.get("min", 0)
                max_count = expected_count.get("max", float('inf'))
                
                if not (min_count <= actual_count <= max_count):
                    return False
            else:
                if actual_count != expected_count:
                    return False
        
        return True
    
    def _validate_data_integrity(self, outputs: Dict[str, Any]) -> bool:
        """验证数据完整性"""
        integrity_checks = self.validation_criteria.get("integrity_checks", [])
        database_file = self.task_config.get("database", "")
        
        if not integrity_checks or not database_file or not os.path.exists(database_file):
            return False
        
        try:
            conn = sqlite3.connect(database_file)
            cursor = conn.cursor()
            
            for check in integrity_checks:
                check_type = check.get("type", "")
                
                if check_type == "no_nulls":
                    table = check.get("table", "")
                    column = check.get("column", "")
                    
                    cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE {column} IS NULL;")
                    null_count = cursor.fetchone()[0]
                    
                    if null_count > 0:
                        conn.close()
                        return False
                
                elif check_type == "unique_values":
                    table = check.get("table", "")
                    column = check.get("column", "")
                    
                    cursor.execute(f"SELECT COUNT(*) FROM {table};")
                    total_count = cursor.fetchone()[0]
                    
                    cursor.execute(f"SELECT COUNT(DISTINCT {column}) FROM {table};")
                    unique_count = cursor.fetchone()[0]
                    
                    if total_count != unique_count:
                        conn.close()
                        return False
                
                elif check_type == "foreign_key":
                    # 外键约束检查
                    parent_table = check.get("parent_table", "")
                    child_table = check.get("child_table", "")
                    foreign_key = check.get("foreign_key", "")
                    reference_key = check.get("reference_key", "")
                    
                    query = f"""
                    SELECT COUNT(*) FROM {child_table} c
                    LEFT JOIN {parent_table} p ON c.{foreign_key} = p.{reference_key}
                    WHERE p.{reference_key} IS NULL AND c.{foreign_key} IS NOT NULL;
                    """
                    
                    cursor.execute(query)
                    orphan_count = cursor.fetchone()[0]
                    
                    if orphan_count > 0:
                        conn.close()
                        return False
            
            conn.close()
            return True
        
        except Exception:
            return False
    
    def _compare_results(self, expected: Any, actual: List[Any]) -> bool:
        """比较查询结果"""
        try:
            # 简化的结果比较
            if isinstance(expected, list):
                return len(expected) == len(actual) and all(e in actual for e in expected)
            elif isinstance(expected, dict):
                # 如果期望结果是字典，检查关键字段
                if "row_count" in expected:
                    return len(actual) == expected["row_count"]
                elif "contains" in expected:
                    return all(item in actual for item in expected["contains"])
            
            return str(expected) == str(actual)
        
        except Exception:
            return False