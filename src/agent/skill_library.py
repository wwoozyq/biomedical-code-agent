"""
技能库 (Skill Library) — Agent as Tool Maker

核心思想（参考 Voyager）：
1. 任务成功后，让 LLM 把关键代码重构为带 type hint + docstring 的标准函数
2. 存入本地 .py 文件，同时提取 AST 调用链指纹
3. 新任务时，用 AST 调用链相似度检索匹配的技能
4. 以 import 方式注入 prompt，LLM 直接调用而非重写

与经验池的区别：
- 经验池存"文本反思"，注入方式是 few-shot（LLM 参考着重写）
- 技能库存"可执行函数"，注入方式是 import（LLM 直接调用）
"""

import json
import re
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field, asdict

from .ast_fingerprint import extract_call_chain, call_chain_similarity


@dataclass
class Skill:
    """一个技能 = 一个可复用的 Python 函数"""
    skill_id: str                    # 唯一标识，如 "skill_001"
    name: str                        # 函数名，如 "compute_substitution_freq"
    description: str                 # 功能描述（来自 docstring）
    source_code: str                 # 完整函数代码
    call_chain: List[str]            # AST 调用链指纹
    origin_task_id: str              # 来源任务 ID
    analysis_types: str              # 来源任务的分析类型
    imports: List[str]               # 需要的 import 语句
    timestamp: float = 0.0
    usage_count: int = 0             # 被检索使用的次数

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Skill":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


SKILL_EXTRACT_PROMPT = """\
你刚刚成功完成了一个生物医学数据分析任务。请将核心逻辑封装为一个可复用的 Python 函数。

## 成功代码
```python
{code}
```

## 任务描述
{query}

## 要求
1. 提取最核心的数据处理逻辑（不包括数据加载和结果打印）
2. 函数必须有完整的类型提示（Type Hint）和 docstring
3. 参数应该泛化（如用 df: pd.DataFrame 而非硬编码文件名）
4. 函数名用英文，描述性命名

## 请严格按以下 JSON 格式输出（不要输出其他内容）：
```json
{{
    "function_name": "compute_xxx",
    "imports": ["import pandas as pd", "from scipy import stats"],
    "source_code": "def compute_xxx(df: pd.DataFrame, col: str) -> pd.DataFrame:\\n    \\"\\"\\"描述功能。\\n\\n    Args:\\n        df: 输入数据框\\n        col: 目标列名\\n\\n    Returns:\\n        处理后的数据框\\n    \\"\\"\\"\\n    # 核心逻辑\\n    return result"
}}
```"""


class SkillLibrary:
    """
    技能库 — 存储、检索、管理可复用的代码技能

    检索策略：AST 调用链相似度（LCS）+ 分析类型匹配
    """

    def __init__(
        self,
        library_dir: str = "./skill_library",
        index_path: str = None,
        max_skills: int = 200,
    ):
        self.library_dir = Path(library_dir)
        self.library_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = Path(index_path or str(self.library_dir / "skill_index.json"))
        self.max_skills = max_skills
        self.skills: List[Skill] = []
        self._load_index()

    # ------------------------------------------------------------------
    # 持久化
    # ------------------------------------------------------------------

    def _load_index(self):
        """加载技能索引"""
        if self.index_path.exists():
            try:
                data = json.loads(self.index_path.read_text(encoding="utf-8"))
                self.skills = [Skill.from_dict(d) for d in data]
            except (json.JSONDecodeError, KeyError):
                self.skills = []

    def _save_index(self):
        """保存技能索引"""
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.index_path, "w", encoding="utf-8") as f:
            json.dump([s.to_dict() for s in self.skills], f, ensure_ascii=False, indent=2)

    # ------------------------------------------------------------------
    # 技能提取（Agent as Tool Maker）
    # ------------------------------------------------------------------

    def extract_skill(
        self,
        llm_client,
        code: str,
        query: str,
        task_id: str,
        analysis_types: str,
    ) -> Optional[Skill]:
        """
        从成功代码中提取技能。
        让 LLM 把代码重构为标准函数，然后提取 AST 指纹存入库。
        """
        if not code or len(code.strip()) < 50:
            return None

        prompt = SKILL_EXTRACT_PROMPT.format(
            code=code[:2000],
            query=query[:500],
        )

        try:
            reply = llm_client.chat([
                {"role": "system", "content": "你是一个 Python 代码重构专家。请严格按 JSON 格式输出。"},
                {"role": "user", "content": prompt},
            ], temperature=0.0, max_tokens=2048)

            # 解析 JSON
            json_match = re.search(r"```json\s*\n(.*?)```", reply, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group(1))
            else:
                parsed = json.loads(reply)

            func_name = parsed.get("function_name", "")
            source_code = parsed.get("source_code", "")
            imports = parsed.get("imports", [])

            if not func_name or not source_code:
                return None

            # 提取 AST 调用链
            call_chain = extract_call_chain(source_code)

            # 提取 docstring 作为描述
            description = self._extract_docstring(source_code) or query[:200]

            skill = Skill(
                skill_id=f"skill_{len(self.skills):04d}",
                name=func_name,
                description=description,
                source_code=source_code,
                call_chain=call_chain,
                origin_task_id=task_id,
                analysis_types=analysis_types,
                imports=imports,
                timestamp=time.time(),
            )

            self._add_skill(skill)
            return skill

        except Exception:
            return None

    def _add_skill(self, skill: Skill):
        """添加技能（去重 + 容量管理）"""
        # 去重：同名函数只保留最新的
        self.skills = [s for s in self.skills if s.name != skill.name]
        self.skills.append(skill)

        # 容量管理
        if len(self.skills) > self.max_skills:
            # 淘汰使用次数最少且最旧的
            self.skills.sort(key=lambda s: (s.usage_count, s.timestamp))
            self.skills = self.skills[-self.max_skills:]

        # 保存函数到 .py 文件
        self._save_skill_file(skill)
        self._save_index()

    def _save_skill_file(self, skill: Skill):
        """将技能函数保存为 .py 文件"""
        py_file = self.library_dir / f"{skill.name}.py"
        content = '"""Auto-generated skill: {desc}"""\n\n{imports}\n\n\n{code}\n'.format(
            desc=skill.description[:100],
            imports="\n".join(skill.imports),
            code=skill.source_code,
        )
        py_file.write_text(content, encoding="utf-8")

    @staticmethod
    def _extract_docstring(source_code: str) -> str:
        """从函数代码中提取 docstring"""
        match = re.search(r'"""(.*?)"""', source_code, re.DOTALL)
        if match:
            return match.group(1).strip().split("\n")[0]
        match = re.search(r"'''(.*?)'''", source_code, re.DOTALL)
        if match:
            return match.group(1).strip().split("\n")[0]
        return ""

    # ------------------------------------------------------------------
    # 技能检索（AST 调用链匹配）
    # ------------------------------------------------------------------

    def retrieve(
        self,
        code: str = "",
        query: str = "",
        analysis_types: str = "",
        top_k: int = 2,
    ) -> List[Skill]:
        """
        检索匹配的技能。

        检索策略（加权融合）：
        1. AST 调用链相似度（权重 0.6）— 代码结构匹配
        2. 分析类型匹配（权重 0.3）— 任务类型过滤
        3. 关键词重叠（权重 0.1）— 文本兜底

        Args:
            code: 当前任务已执行的代码（用于 AST 匹配）
            query: 任务描述文本
            analysis_types: 任务分析类型
            top_k: 返回数量
        """
        if not self.skills:
            return []

        query_chain = extract_call_chain(code) if code else []
        query_types = set(self._parse_types(analysis_types))
        query_keywords = set(self._extract_keywords(query))

        scored: List[tuple] = []
        for skill in self.skills:
            # AST 调用链相似度
            ast_score = call_chain_similarity(query_chain, skill.call_chain) if query_chain else 0.0

            # 分析类型匹配
            skill_types = set(self._parse_types(skill.analysis_types))
            type_score = len(query_types & skill_types) / max(len(query_types | skill_types), 1)

            # 关键词重叠
            skill_keywords = set(self._extract_keywords(skill.description))
            kw_score = len(query_keywords & skill_keywords) / max(len(query_keywords | skill_keywords), 1)

            # 加权融合
            total_score = ast_score * 0.6 + type_score * 0.3 + kw_score * 0.1
            scored.append((total_score, skill))

        scored.sort(key=lambda x: x[0], reverse=True)

        # 更新使用计数
        results = []
        for score, skill in scored[:top_k]:
            if score > 0.05:  # 最低阈值
                skill.usage_count += 1
                results.append(skill)

        if results:
            self._save_index()

        return results

    def format_for_prompt(self, skills: List[Skill]) -> str:
        """将检索到的技能格式化为 prompt 注入文本"""
        if not skills:
            return ""

        parts = ["## 可用技能函数（来自技能库，可直接调用）\n"]
        parts.append("以下函数已经过验证，你可以直接在代码中使用：\n")

        for i, skill in enumerate(skills):
            parts.append(f"### 技能 {i + 1}: `{skill.name}`")
            parts.append(f"```python\n{chr(10).join(skill.imports)}\n\n{skill.source_code}\n```")
            parts.append(f"用法提示：{skill.description}\n")

        parts.append("你可以直接复制上述函数定义到你的代码中使用，也可以参考其逻辑自行编写。")
        return "\n".join(parts)

    def get_stats(self) -> Dict[str, Any]:
        """技能库统计"""
        return {
            "total_skills": len(self.skills),
            "most_used": sorted(self.skills, key=lambda s: s.usage_count, reverse=True)[:3]
                         if self.skills else [],
            "analysis_types": list(set(s.analysis_types for s in self.skills)),
        }

    # ------------------------------------------------------------------
    # 工具方法
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_types(analysis_types: str) -> List[str]:
        if not analysis_types:
            return []
        try:
            types = eval(analysis_types) if analysis_types.startswith("[") else [analysis_types]
        except Exception:
            types = [analysis_types]
        return [t.strip().lower() for t in types if t.strip()]

    @staticmethod
    def _extract_keywords(text: str) -> List[str]:
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "have", "has", "had", "do", "does", "did", "will", "would",
            "of", "in", "to", "for", "with", "on", "at", "from", "by",
            "and", "or", "not", "but", "if", "this", "that", "it", "its",
            "all", "each", "every", "some", "such", "than", "too", "very",
        }
        words = re.findall(r"[a-zA-Z_]+", text.lower())
        return [w for w in words if w not in stop_words and len(w) > 2]
