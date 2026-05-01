"""
Failure attribution agent for BioDSBench code-generation tasks.

The attribution agent diagnoses why a generated code attempt failed and
returns a compact, structured repair hint for the main ReAct agent.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional


ERROR_TYPES = [
    "数据路径错误",
    "字段理解错误",
    "表关联错误",
    "筛选口径错误",
    "统计逻辑错误",
    "输出格式错误",
    "依赖/API 错误",
    "未知错误",
]


ATTRIBUTION_SYSTEM_PROMPT = """\
你是一个生物医学数据科学代码调试归因智能体。
你的任务不是直接重写完整代码，而是判断当前失败最可能来自哪里，并给主智能体提供可执行的修正方向。

请严格输出 JSON，不要输出 Markdown，不要输出额外解释。
JSON 字段：
{
  "error_type": "数据路径错误/字段理解错误/表关联错误/筛选口径错误/统计逻辑错误/输出格式错误/依赖API错误/未知错误",
  "root_cause": "一句话说明最可能失败原因",
  "evidence": ["从错误信息、断言、stdout 或代码中看到的证据"],
  "check_points": ["下一轮优先检查的表、字段、变量或中间结果"],
  "fix_suggestion": "给主智能体的具体修正建议",
  "confidence": 0.0
}
"""


@dataclass
class AttributionResult:
    error_type: str
    root_cause: str
    evidence: List[str]
    check_points: List[str]
    fix_suggestion: str
    confidence: float = 0.5
    source: str = "rule"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AttributionAgent:
    """Diagnose execution and validation failures for the main agent."""

    def __init__(self, llm_client=None, use_llm: bool = True):
        self.llm = llm_client
        self.use_llm = use_llm and llm_client is not None

    def analyze(
        self,
        task_description: str,
        code: str,
        observation: Dict[str, Any],
        test_detail: str = "",
        history: Optional[List[Dict[str, Any]]] = None,
        task_data: Optional[Dict[str, Any]] = None,
    ) -> AttributionResult:
        """Return a structured diagnosis for the current failed attempt."""
        if self.use_llm:
            try:
                return self._analyze_with_llm(
                    task_description=task_description,
                    code=code,
                    observation=observation,
                    test_detail=test_detail,
                    history=history or [],
                    task_data=task_data or {},
                )
            except Exception:
                # The diagnosis must never break the main solving loop.
                pass

        return self._rule_based_attribution(
            code=code,
            observation=observation,
            test_detail=test_detail,
        )

    def format_for_prompt(self, result: AttributionResult) -> str:
        """Format a diagnosis as a concise prompt block for the main agent."""
        evidence = "; ".join(result.evidence[:3]) if result.evidence else "无明确证据"
        checks = "; ".join(result.check_points[:4]) if result.check_points else "重新检查任务要求和断言"
        return (
            "## 归因子智能体诊断\n"
            f"- 错误类型: {result.error_type}\n"
            f"- 可能原因: {result.root_cause}\n"
            f"- 证据: {evidence}\n"
            f"- 优先检查: {checks}\n"
            f"- 修正建议: {result.fix_suggestion}\n"
            f"- 置信度: {result.confidence:.2f}"
        )

    def _analyze_with_llm(
        self,
        task_description: str,
        code: str,
        observation: Dict[str, Any],
        test_detail: str,
        history: List[Dict[str, Any]],
        task_data: Dict[str, Any],
    ) -> AttributionResult:
        history_summary = []
        for item in history[-3:]:
            history_summary.append({
                "step_id": item.get("step_id"),
                "thought": item.get("thought", "")[:300],
                "success": item.get("success", False),
                "error": item.get("error", "")[:500],
            })

        payload = {
            "task": task_description,
            "analysis_types": task_data.get("analysis_types", ""),
            "tables": task_data.get("tables", []),
            "test_cases": task_data.get("test_cases", "")[:1200],
            "current_code": code[:2500],
            "stdout": observation.get("stdout", "")[:1500],
            "error": observation.get("error", "")[:2000],
            "failed_test": test_detail[:1500],
            "recent_history": history_summary,
        }
        reply = self.llm.chat(
            [
                {"role": "system", "content": ATTRIBUTION_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False, indent=2)},
            ],
            temperature=0.0,
            max_tokens=1024,
        )
        parsed = self._parse_json(reply)
        error_type = parsed.get("error_type", "未知错误")
        if error_type == "依赖API错误":
            error_type = "依赖/API 错误"
        if error_type not in ERROR_TYPES:
            error_type = "未知错误"

        return AttributionResult(
            error_type=error_type,
            root_cause=str(parsed.get("root_cause", "未能明确判断失败原因"))[:300],
            evidence=self._ensure_list(parsed.get("evidence"))[:5],
            check_points=self._ensure_list(parsed.get("check_points"))[:5],
            fix_suggestion=str(parsed.get("fix_suggestion", "根据失败断言重新检查代码逻辑"))[:500],
            confidence=self._safe_confidence(parsed.get("confidence", 0.5)),
            source="llm",
        )

    @staticmethod
    def _parse_json(text: str) -> Dict[str, Any]:
        text = text.strip()
        fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
        if fenced:
            text = fenced.group(1).strip()
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            text = text[start:end + 1]
        return json.loads(text)

    @staticmethod
    def _ensure_list(value: Any) -> List[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(v) for v in value if str(v).strip()]
        return [str(value)]

    @staticmethod
    def _safe_confidence(value: Any) -> float:
        try:
            return max(0.0, min(1.0, float(value)))
        except Exception:
            return 0.5

    def _rule_based_attribution(
        self,
        code: str,
        observation: Dict[str, Any],
        test_detail: str,
    ) -> AttributionResult:
        text = "\n".join([
            code or "",
            observation.get("stdout", "") or "",
            observation.get("error", "") or "",
            test_detail or "",
        ])
        lower = text.lower()

        if "filenotfounderror" in lower or "no such file" in lower:
            return AttributionResult(
                error_type="数据路径错误",
                root_cause="代码读取的数据文件路径与当前运行目录或任务提供路径不一致。",
                evidence=self._pick_evidence(text, ["FileNotFoundError", "No such file", "文件路径"]),
                check_points=["tables 中的数据路径", "data_root", "相对路径是否以 ../biodsbench_data 开头"],
                fix_suggestion="先打印或检查可用数据文件路径，使用任务上下文给出的路径读取数据，不要自行猜测文件名。",
                confidence=0.85,
            )
        if "keyerror" in lower or "not in index" in lower or "columns" in lower and "assert" in lower:
            return AttributionResult(
                error_type="字段理解错误",
                root_cause="代码使用的列名、字段大小写或输出列名可能与真实数据/断言不一致。",
                evidence=self._pick_evidence(text, ["KeyError", "not in index", "columns", "assert"]),
                check_points=["DataFrame.columns", "任务 schema", "断言要求的输出列名"],
                fix_suggestion="下一轮先打印相关表的列名，再按真实列名修改字段访问和输出 DataFrame 列名。",
                confidence=0.78,
            )
        if any(k in lower for k in ["patient_id", "sample_id", "merge", "join"]):
            if any(k in lower for k in ["assertionerror", "shape", "expected", "sum"]):
                return AttributionResult(
                    error_type="表关联错误",
                    root_cause="断言数值或形状不匹配，且代码涉及患者和样本层级连接，可能存在连接键或去重口径错误。",
                    evidence=self._pick_evidence(text, ["PATIENT_ID", "SAMPLE_ID", "merge", "AssertionError", "shape"]),
                    check_points=["PATIENT_ID 与 SAMPLE_ID 的层级", "merge 的 on/how 参数", "drop_duplicates 的位置"],
                    fix_suggestion="明确输出应在患者层级还是样本层级统计，连接后打印行数和唯一患者/样本数再重算结果。",
                    confidence=0.72,
                )
        if any(k in lower for k in ["assertionerror", "expected", "期望", "实际", "=="]):
            if any(k in lower for k in ["pvalue", "survival", "kaplan", "logrank", "mean", "median", "ratio"]):
                return AttributionResult(
                    error_type="统计逻辑错误",
                    root_cause="代码可以运行但统计量未通过断言，可能是统计方法、分母、事件定义或数值口径不一致。",
                    evidence=self._pick_evidence(text, ["AssertionError", "pvalue", "median", "ratio", "survival"]),
                    check_points=["统计分母", "分组变量", "生存事件编码", "缺失值处理"],
                    fix_suggestion="对照断言和题意重新检查统计口径，打印关键中间表和分组计数后再生成最终变量。",
                    confidence=0.7,
                )
            return AttributionResult(
                error_type="输出格式错误",
                root_cause="代码运行成功但最终变量、类型、列名、排序或数值没有满足测试断言。",
                evidence=self._pick_evidence(text, ["AssertionError", "assert", "shape", "columns"]),
                check_points=["最终变量名", "输出对象类型", "DataFrame 列名与排序", "断言中的精确数值"],
                fix_suggestion="直接围绕失败断言修正最终输出结构，确保变量名、列顺序、索引和数据类型完全匹配。",
                confidence=0.68,
            )
        if any(k in lower for k in ["modulenotfounderror", "importerror", "attributeerror", "typeerror"]):
            return AttributionResult(
                error_type="依赖/API 错误",
                root_cause="第三方库、函数接口或对象类型使用不匹配导致运行失败。",
                evidence=self._pick_evidence(text, ["ModuleNotFoundError", "ImportError", "AttributeError", "TypeError"]),
                check_points=["import 语句", "库版本差异", "函数返回对象类型"],
                fix_suggestion="避免使用非必要依赖，优先用 pandas/scipy/matplotlib 的基础接口重写该步骤。",
                confidence=0.74,
            )
        return AttributionResult(
            error_type="未知错误",
            root_cause="当前错误信息不足，暂时无法稳定归因。",
            evidence=self._pick_evidence(text, ["Traceback", "AssertionError", "Error"]),
            check_points=["stdout", "error", "test_cases", "最近一轮代码"],
            fix_suggestion="下一轮增加关键中间结果打印，先定位数据形状、列名和最终变量是否符合断言。",
            confidence=0.45,
        )

    @staticmethod
    def _pick_evidence(text: str, needles: List[str]) -> List[str]:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        hits = []
        for needle in needles:
            for line in lines:
                if needle.lower() in line.lower() and line not in hits:
                    hits.append(line[:220])
                    break
        return hits[:4]
