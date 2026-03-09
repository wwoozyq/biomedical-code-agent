"""
辅助工具函数
"""

import json
import yaml
from pathlib import Path
from typing import Dict, Any


def load_config(config_path: str) -> Dict[str, Any]:
    """加载配置文件"""
    config_file = Path(config_path)
    
    if not config_file.exists():
        return {}
    
    try:
        if config_file.suffix.lower() in ['.yaml', '.yml']:
            with open(config_file, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        elif config_file.suffix.lower() == '.json':
            with open(config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            raise ValueError(f"不支持的配置文件格式: {config_file.suffix}")
    except Exception as e:
        print(f"加载配置文件失败: {e}")
        return {}


def save_results(file_path: Path, results: Dict[str, Any]):
    """保存结果到文件"""
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False, default=str)
    except Exception as e:
        print(f"保存结果失败: {e}")


def format_execution_time(seconds: float) -> str:
    """格式化执行时间"""
    if seconds < 60:
        return f"{seconds:.2f}秒"
    elif seconds < 3600:
        minutes = seconds // 60
        remaining_seconds = seconds % 60
        return f"{int(minutes)}分{remaining_seconds:.1f}秒"
    else:
        hours = seconds // 3600
        remaining_minutes = (seconds % 3600) // 60
        return f"{int(hours)}小时{int(remaining_minutes)}分"


def validate_task_config(config: Dict[str, Any]) -> bool:
    """验证任务配置"""
    required_fields = ["task_id", "task_type", "description"]
    
    for field in required_fields:
        if field not in config:
            print(f"缺少必需字段: {field}")
            return False
    
    valid_task_types = ["data_analysis", "prediction", "sql_query"]
    if config["task_type"] not in valid_task_types:
        print(f"无效的任务类型: {config['task_type']}")
        return False
    
    return True