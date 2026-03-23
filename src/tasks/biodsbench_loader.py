"""
BioDSBench 任务加载器 - 从 JSONL 文件加载 benchmark 任务
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional


class BioDSBenchLoader:
    """加载和解析 BioDSBench 任务"""

    def __init__(self, data_root: str = "./biodsbench_data"):
        self.data_root = Path(data_root)
        self.tasks_file = self.data_root / "python_tasks_with_class.jsonl"
        self.schemas_file = self.data_root / "python_task_table_schemas.jsonl"
        self._schemas_cache: Optional[Dict[str, Any]] = None

    def load_all_tasks(self) -> List[Dict[str, Any]]:
        """加载全部任务"""
        tasks = []
        with open(self.tasks_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    tasks.append(json.loads(line))
        return tasks

    def load_task_by_index(self, index: int) -> Dict[str, Any]:
        """按行号加载单个任务（0-based）"""
        tasks = self.load_all_tasks()
        if index < 0 or index >= len(tasks):
            raise IndexError(f"任务索引 {index} 超出范围 [0, {len(tasks)-1}]")
        return tasks[index]

    def load_task_by_id(self, unique_question_id: str) -> Dict[str, Any]:
        """按 unique_question_ids 加载任务"""
        for task in self.load_all_tasks():
            if task.get("unique_question_ids") == unique_question_id:
                return task
        raise KeyError(f"未找到任务: {unique_question_id}")

    def load_schemas(self) -> Dict[str, Any]:
        """加载 table schemas，按 study_ids 索引"""
        if self._schemas_cache is not None:
            return self._schemas_cache
        self._schemas_cache = {}
        with open(self.schemas_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    obj = json.loads(line)
                    sid = obj.get("study_ids", "")
                    self._schemas_cache[sid] = obj
        return self._schemas_cache

    def prepare_task(self, raw_task: Dict[str, Any]) -> Dict[str, Any]:
        """
        将原始 JSONL 任务转换为 agent 可用的格式：
        - 修正数据文件路径（biodsbench_processed_data → 本地 biodsbench_data）
        - 注入 table_schemas
        - 提取 test_cases
        """
        study_id = raw_task.get("study_ids", "")

        # 修正表路径
        raw_tables = raw_task.get("tables", "[]")
        if isinstance(raw_tables, str):
            raw_tables = json.loads(raw_tables)
        local_tables = [
            self._fix_table_path(t) for t in raw_tables
        ]

        # 获取 schema
        schemas = self.load_schemas()
        schema_info = schemas.get(study_id, {})
        schema_text = self._format_schema(schema_info)

        return {
            "unique_question_id": raw_task.get("unique_question_ids", ""),
            "study_ids": study_id,
            "query": raw_task.get("queries", ""),
            "tables": local_tables,
            "table_schemas": schema_text,
            "cot_instructions": raw_task.get("cot_instructions", ""),
            "test_cases": raw_task.get("test_cases", ""),
            "reference_answer": raw_task.get("reference_answer", ""),
            "analysis_types": raw_task.get("analysis_types", ""),
        }

    def _fix_table_path(self, original_path: str) -> str:
        """把 benchmark 路径映射到本地路径"""
        # biodsbench_processed_data/xxx/file.csv → biodsbench_data/xxx/file.csv
        p = original_path.replace("biodsbench_processed_data/", "")
        return str(self.data_root / p)

    def _format_schema(self, schema_obj: Dict[str, Any]) -> str:
        """把 schema 对象格式化为可读文本"""
        if not schema_obj:
            return ""
        table_schemas = schema_obj.get("table_schemas", [])
        # table_schemas 是一个字符串列表，每个字符串描述一张表
        if isinstance(table_schemas, list):
            return "\n\n".join(str(s) for s in table_schemas)
        if isinstance(table_schemas, str):
            return table_schemas
        return str(table_schemas)
