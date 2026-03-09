"""
任务处理模块
"""

from .base_task import BaseTask
from .data_analysis import DataAnalysisTask
from .prediction import PredictionTask
from .sql_query import SQLQueryTask

__all__ = ['BaseTask', 'DataAnalysisTask', 'PredictionTask', 'SQLQueryTask']