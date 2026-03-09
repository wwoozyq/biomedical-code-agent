"""
动作空间定义和实现
"""

from enum import Enum
from typing import Dict, Any, Optional, List
import subprocess
import sqlite3
import traceback
from pathlib import Path
import json


class ActionType(Enum):
    """四类基础动作类型"""
    REQUEST_INFO = "request_info"
    TERMINAL = "terminal"
    CODE_EXECUTION = "code_execution"
    DEBUGGING = "debugging"


class ActionSpace:
    """动作空间管理器"""
    
    def __init__(self, sandbox_dir: str = "./sandbox", data_dir: str = "./data"):
        self.sandbox_dir = Path(sandbox_dir)
        self.data_dir = Path(data_dir)
        self.sandbox_dir.mkdir(exist_ok=True)
        self.data_dir.mkdir(exist_ok=True)
        
        # 执行历史
        self.execution_history = []
        
    def execute_action(self, action_type: ActionType, params: Dict[str, Any]) -> Dict[str, Any]:
        """执行指定类型的动作"""
        try:
            if action_type == ActionType.REQUEST_INFO:
                return self._request_info(params)
            elif action_type == ActionType.TERMINAL:
                return self._terminal_action(params)
            elif action_type == ActionType.CODE_EXECUTION:
                return self._code_execution(params)
            elif action_type == ActionType.DEBUGGING:
                return self._debugging_action(params)
            else:
                return {"success": False, "error": f"Unknown action type: {action_type}"}
        except Exception as e:
            return {"success": False, "error": str(e), "traceback": traceback.format_exc()}
    
    def _request_info(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """检索数据信息"""
        data_source = params.get("data_source", "")
        query_type = params.get("query_type", "describe")
        
        try:
            if data_source.endswith('.csv'):
                import pandas as pd
                df = pd.read_csv(self.data_dir / data_source)
                
                if query_type == "describe":
                    info = {
                        "shape": df.shape,
                        "columns": df.columns.tolist(),
                        "dtypes": df.dtypes.to_dict(),
                        "head": df.head().to_dict(),
                        "describe": df.describe().to_dict()
                    }
                elif query_type == "schema":
                    info = {
                        "columns": df.columns.tolist(),
                        "dtypes": df.dtypes.to_dict(),
                        "shape": df.shape
                    }
                else:
                    info = {"data": df.to_dict()}
                    
                return {"success": True, "data": info}
                
            elif data_source.endswith('.db') or data_source.endswith('.sqlite'):
                conn = sqlite3.connect(self.data_dir / data_source)
                cursor = conn.cursor()
                
                if query_type == "schema":
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                    tables = [row[0] for row in cursor.fetchall()]
                    
                    schema_info = {}
                    for table in tables:
                        cursor.execute(f"PRAGMA table_info({table});")
                        columns = cursor.fetchall()
                        schema_info[table] = columns
                    
                    conn.close()
                    return {"success": True, "data": {"tables": tables, "schema": schema_info}}
                else:
                    # 执行自定义查询
                    query = params.get("query", "")
                    if query:
                        cursor.execute(query)
                        results = cursor.fetchall()
                        conn.close()
                        return {"success": True, "data": {"results": results}}
                    
            return {"success": False, "error": "Unsupported data source or query type"}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _terminal_action(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """终端命令执行"""
        command = params.get("command", "")
        working_dir = params.get("working_dir", str(self.sandbox_dir))
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=working_dir,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode
            }
            
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Command timeout"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _code_execution(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """代码执行"""
        code = params.get("code", "")
        language = params.get("language", "python")
        save_file = params.get("save_file", None)
        
        if save_file:
            # 保存代码到文件
            code_file = self.sandbox_dir / save_file
            with open(code_file, 'w', encoding='utf-8') as f:
                f.write(code)
        
        try:
            if language.lower() == "python":
                # 创建或使用持久的执行环境
                if not hasattr(self, '_exec_globals'):
                    self._exec_globals = {
                        '__builtins__': __builtins__,
                        'sandbox_dir': str(self.sandbox_dir),
                        'data_dir': str(self.data_dir)
                    }
                    
                    # 添加常用库
                    import sys
                    sys.path.append(str(self.sandbox_dir))
                    
                    self._exec_locals = {}
                
                # 执行代码
                exec(code, self._exec_globals, self._exec_locals)
                
                # 提取结果
                output_vars = {k: v for k, v in self._exec_locals.items() 
                             if not k.startswith('_')}
                
                return {
                    "success": True,
                    "output_vars": str(output_vars),
                    "locals": list(self._exec_locals.keys())
                }
                
            elif language.lower() == "sql":
                # SQL 执行
                db_file = params.get("database", "")
                if not db_file:
                    return {"success": False, "error": "Database file required for SQL execution"}
                
                conn = sqlite3.connect(self.data_dir / db_file)
                cursor = conn.cursor()
                cursor.execute(code)
                
                if code.strip().upper().startswith('SELECT'):
                    results = cursor.fetchall()
                    columns = [description[0] for description in cursor.description]
                    conn.close()
                    return {
                        "success": True,
                        "results": results,
                        "columns": columns
                    }
                else:
                    conn.commit()
                    conn.close()
                    return {"success": True, "message": "Query executed successfully"}
            
            else:
                return {"success": False, "error": f"Unsupported language: {language}"}
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "traceback": traceback.format_exc()
            }
    
    def _debugging_action(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """调试信息处理"""
        error_info = params.get("error_info", "")
        error_type = params.get("error_type", "runtime")
        
        try:
            # 解析错误信息并提供建议
            suggestions = []
            
            if "NameError" in error_info:
                suggestions.append("检查变量名是否正确定义和拼写")
                suggestions.append("确认所需的库是否已导入")
                
            elif "FileNotFoundError" in error_info:
                suggestions.append("检查文件路径是否正确")
                suggestions.append("确认文件是否存在于指定位置")
                
            elif "KeyError" in error_info:
                suggestions.append("检查字典键或DataFrame列名是否存在")
                suggestions.append("使用.get()方法或先检查键是否存在")
                
            elif "IndexError" in error_info:
                suggestions.append("检查列表或数组的索引范围")
                suggestions.append("确认数据结构不为空")
                
            elif "TypeError" in error_info:
                suggestions.append("检查数据类型是否匹配")
                suggestions.append("确认函数参数类型正确")
                
            elif "ValueError" in error_info:
                suggestions.append("检查输入值的格式和范围")
                suggestions.append("确认数据预处理步骤正确")
                
            else:
                suggestions.append("检查代码逻辑和语法")
                suggestions.append("查看完整的错误堆栈信息")
            
            # 生成调试建议
            debug_advice = {
                "error_analysis": error_info,
                "suggestions": suggestions,
                "next_steps": [
                    "根据建议修改代码",
                    "添加必要的错误处理",
                    "验证输入数据格式",
                    "重新执行修正后的代码"
                ]
            }
            
            return {"success": True, "debug_advice": debug_advice}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_execution_history(self) -> List[Dict[str, Any]]:
        """获取执行历史"""
        return self.execution_history
    
    def clear_sandbox(self):
        """清理沙箱环境"""
        import shutil
        if self.sandbox_dir.exists():
            shutil.rmtree(self.sandbox_dir)
        self.sandbox_dir.mkdir(exist_ok=True)