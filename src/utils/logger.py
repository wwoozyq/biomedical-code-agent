"""
日志工具
"""

import logging
import json
from pathlib import Path
from typing import List, Dict, Any


def setup_logger(name: str = "biomedical_agent", verbose: bool = True) -> logging.Logger:
    """设置日志器"""
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    
    # 清除现有处理器
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG if verbose else logging.INFO)
    
    # 格式化器
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(formatter)
    
    logger.addHandler(console_handler)
    
    # 文件处理器
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    file_handler = logging.FileHandler(log_dir / "agent.log", encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    
    return logger


def log_execution_trace(file_path: Path, execution_trace: List[Dict[str, Any]]):
    """记录执行轨迹"""
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(execution_trace, f, indent=2, ensure_ascii=False, default=str)
    except Exception as e:
        logging.getLogger("biomedical_agent").error(f"保存执行轨迹失败: {e}")