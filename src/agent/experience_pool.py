"""
经验复用池 (Experience Pool) + 反思机制 (Reflection)

核心思想：
1. 每次任务完成后（无论成功失败），提取结构化经验存入 JSON 文件
2. 成功经验：记录有效的代码模式和解题策略
3. 失败经验：通过 LLM 反思提取教训（哪里出错、如何避免）
4. 新任务开始前，按 analysis_type 和关键词检索相似经验，注入 prompt 作为 few-shot
"""

import json
import time
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from collections import defaultdict


class Experience:
    """单条经验记录"""

    def __init__(
        self,
        task_id: str,
        query: str,
        analysis_types: str,
        success: bool,
        final_code: str,
        reflection: str = "",
        key_patterns: List[str] = None,
        steps_used: int = 0,
        timestamp: float = 0,
    ):
        self.task_id = task_id
        self.query = query
        self.analysis_types = analysis_types
        self.success = success
        self.final_code = final_code
        self.reflection = reflection
        self.key_patterns = key_patterns or []
        self.steps_used = steps_used
        self.timestamp = timestamp or time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "query": self.query,
            "analysis_types": self.analysis_types,
            "success": self.success,
            "final_code": self.final_code,
            "reflection": self.reflection,
            "key_patterns": self.key_patterns,
            "steps_used": self.steps_used,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Experience":
        return cls(**d)


class ExperiencePool:
    """
    经验复用池 — 持久化存储 + 相似检索

    持久化策略：
    - 每次 add_experience 后自动写入主文件
    - 写入前自动备份上一版本（最多保留 max_backups 份）
    - 支持 export_to / import_from 在不同经验池之间迁移
    - 支持 merge 合并多个经验池
    - 支持 max_size 容量上限，超出时淘汰最旧的失败经验
    """

    def __init__(
        self,
        pool_path: str = "./experience_pool.json",
        max_size: int = 500,
        max_backups: int = 3,
    ):
        self.pool_path = Path(pool_path)
        self.max_size = max_size
        self.max_backups = max_backups
        self.experiences: List[Experience] = []
        # 按 analysis_type 建索引，加速检索
        self._type_index: Dict[str, List[int]] = defaultdict(list)
        self._load()

    # ------------------------------------------------------------------
    # 持久化核心
    # ------------------------------------------------------------------

    def _load(self):
        """从文件加载经验池"""
        if self.pool_path.exists():
            try:
                with open(self.pool_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.experiences = [Experience.from_dict(d) for d in data]
                self._rebuild_index()
            except (json.JSONDecodeError, KeyError):
                self.experiences = []

    def _save(self):
        """持久化到文件（写入前自动备份）"""
        self.pool_path.parent.mkdir(parents=True, exist_ok=True)
        # 备份旧文件
        if self.pool_path.exists():
            self._rotate_backups()
        with open(self.pool_path, "w", encoding="utf-8") as f:
            json.dump(
                [e.to_dict() for e in self.experiences],
                f, ensure_ascii=False, indent=2,
            )

    def _rotate_backups(self):
        """滚动备份：pool.json → pool.json.1 → pool.json.2 → ... 删除最旧的"""
        for i in range(self.max_backups - 1, 0, -1):
            src = self.pool_path.with_suffix(f".json.{i}")
            dst = self.pool_path.with_suffix(f".json.{i + 1}")
            if src.exists():
                src.rename(dst)
        # 当前文件 → .1
        backup = self.pool_path.with_suffix(".json.1")
        if self.pool_path.exists():
            import shutil
            shutil.copy2(self.pool_path, backup)

    def _evict_if_needed(self):
        """容量管理：超出 max_size 时淘汰最旧的失败经验，再淘汰最旧的成功经验"""
        while len(self.experiences) > self.max_size:
            # 优先淘汰最旧的失败经验
            oldest_fail_idx = None
            for i, exp in enumerate(self.experiences):
                if not exp.success:
                    oldest_fail_idx = i
                    break
            if oldest_fail_idx is not None:
                self.experiences.pop(oldest_fail_idx)
            else:
                # 全是成功经验，淘汰最旧的
                self.experiences.pop(0)

    # ------------------------------------------------------------------
    # 导入 / 导出 / 合并
    # ------------------------------------------------------------------

    def export_to(self, path: str):
        """导出经验池到指定文件"""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(
                [e.to_dict() for e in self.experiences],
                f, ensure_ascii=False, indent=2,
            )

    def import_from(self, path: str, overwrite: bool = False):
        """
        从文件导入经验。
        overwrite=True: 同 task_id 时用导入的覆盖已有的
        overwrite=False: 同 task_id 时保留已有的
        """
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"经验池文件不存在: {path}")
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        incoming = [Experience.from_dict(d) for d in data]
        self.merge(incoming, overwrite=overwrite)

    def merge(self, other_experiences: List["Experience"], overwrite: bool = False):
        """合并另一组经验到当前池"""
        existing_ids = {e.task_id: i for i, e in enumerate(self.experiences)}
        for exp in other_experiences:
            if exp.task_id in existing_ids:
                if overwrite:
                    self.experiences[existing_ids[exp.task_id]] = exp
            else:
                self.experiences.append(exp)
        self._evict_if_needed()
        self._rebuild_index()
        self._save()

    def _rebuild_index(self):
        """重建 analysis_type 索引"""
        self._type_index.clear()
        for i, exp in enumerate(self.experiences):
            for atype in self._parse_types(exp.analysis_types):
                self._type_index[atype].append(i)

    def add_experience(self, exp: Experience):
        """添加一条经验（自动去重、容量管理、持久化）"""
        # 去重：同一个 task_id 只保留最新的
        self.experiences = [e for e in self.experiences if e.task_id != exp.task_id]
        self.experiences.append(exp)
        self._evict_if_needed()
        self._rebuild_index()
        self._save()

    def retrieve(
        self,
        query: str,
        analysis_types: str,
        top_k: int = 3,
        success_only: bool = True,
    ) -> List[Experience]:
        """
        检索相似经验：
        1. 先按 analysis_type 过滤候选集
        2. 再按关键词相似度排序
        3. 返回 top_k 条
        """
        target_types = set(self._parse_types(analysis_types))
        query_keywords = set(self._extract_keywords(query))

        candidates = []
        seen_ids = set()

        # 按 type 匹配找候选
        for atype in target_types:
            for idx in self._type_index.get(atype, []):
                if idx not in seen_ids:
                    seen_ids.add(idx)
                    exp = self.experiences[idx]
                    if success_only and not exp.success:
                        continue
                    candidates.append(exp)

        # 如果 type 匹配太少，放宽到全部成功经验
        if len(candidates) < top_k:
            for exp in self.experiences:
                if exp.task_id not in {c.task_id for c in candidates}:
                    if success_only and not exp.success:
                        continue
                    candidates.append(exp)

        # 按关键词重叠度排序
        def score(exp: Experience) -> float:
            exp_keywords = set(self._extract_keywords(exp.query))
            exp_types = set(self._parse_types(exp.analysis_types))
            type_overlap = len(target_types & exp_types)
            keyword_overlap = len(query_keywords & exp_keywords)
            return type_overlap * 10 + keyword_overlap

        candidates.sort(key=score, reverse=True)
        return candidates[:top_k]

    def retrieve_failures(
        self, analysis_types: str, top_k: int = 2
    ) -> List[Experience]:
        """检索相关的失败经验（用于避免重复犯错）"""
        return self.retrieve(
            query="", analysis_types=analysis_types,
            top_k=top_k, success_only=False,
        )

    def get_stats(self) -> Dict[str, Any]:
        """经验池统计"""
        total = len(self.experiences)
        success = sum(1 for e in self.experiences if e.success)
        return {
            "total": total,
            "success": success,
            "failure": total - success,
            "types": dict(self._type_index),
        }

    # ------------------------------------------------------------------
    # 工具方法
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_types(analysis_types: str) -> List[str]:
        """解析 analysis_types 字符串为列表"""
        if not analysis_types:
            return []
        # 格式如 "['Descriptive Statistics', 'Survival Outcome Analysis']"
        try:
            types = eval(analysis_types) if analysis_types.startswith("[") else [analysis_types]
        except Exception:
            types = [analysis_types]
        return [t.strip().lower() for t in types if t.strip()]

    @staticmethod
    def _extract_keywords(text: str) -> List[str]:
        """从文本中提取关键词（简单分词 + 停用词过滤）"""
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "will",
            "would", "could", "should", "may", "might", "shall", "can",
            "of", "in", "to", "for", "with", "on", "at", "from", "by",
            "and", "or", "not", "no", "but", "if", "then", "else",
            "this", "that", "these", "those", "it", "its", "what",
            "which", "who", "whom", "how", "when", "where", "why",
            "all", "each", "every", "both", "few", "more", "most",
            "other", "some", "such", "than", "too", "very", "just",
        }
        words = re.findall(r"[a-zA-Z_]+", text.lower())
        return [w for w in words if w not in stop_words and len(w) > 2]


class ReflectionEngine:
    """
    反思引擎 — 任务结束后让 LLM 做结构化反思
    提取：成功策略 / 失败原因 / 关键代码模式 / 教训
    """

    REFLECTION_PROMPT = """\
你刚刚完成了一个生物医学数据分析任务。请对你的执行过程做结构化反思。

## 任务
{query}

## 执行结果
- 成功: {success}
- 总步骤: {steps}
- 最终代码:
```python
{final_code}
```

## 执行过程中的错误（如有）
{errors}

## 请输出以下 JSON 格式的反思（不要输出其他内容）：
```json
{{
    "strategy": "简述你的解题策略（1-2句话）",
    "key_patterns": ["列出关键的代码模式，如 'pd.read_csv 加载数据', 'value_counts 统计分布' 等"],
    "mistakes": ["列出犯过的错误（如有）"],
    "lessons": ["列出学到的教训（如有）"],
    "improvement": "如果重做这道题，你会怎么改进（1句话）"
}}
```"""

    def __init__(self, llm_client):
        self.llm = llm_client

    def reflect(
        self,
        query: str,
        success: bool,
        steps: int,
        final_code: str,
        errors: str,
    ) -> Dict[str, Any]:
        """执行反思，返回结构化反思结果"""
        prompt = self.REFLECTION_PROMPT.format(
            query=query[:500],
            success="是" if success else "否",
            steps=steps,
            final_code=final_code[:1500],
            errors=errors[:500] if errors else "无",
        )

        try:
            reply = self.llm.chat([
                {"role": "system", "content": "你是一个善于反思和总结的 AI 助手。请严格按 JSON 格式输出。"},
                {"role": "user", "content": prompt},
            ], temperature=0.0, max_tokens=1024)

            # 提取 JSON
            json_match = re.search(r"```json\s*\n(.*?)```", reply, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(1))
            # 尝试直接解析
            return json.loads(reply)
        except Exception:
            return {
                "strategy": "",
                "key_patterns": [],
                "mistakes": [],
                "lessons": [],
                "improvement": "",
            }
