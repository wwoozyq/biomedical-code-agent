#!/usr/bin/env python3
"""
No-API smoke test for the ReAct loop and attribution agent.

This test uses a deterministic fake LLM. It verifies that a failed assertion
is diagnosed, fed back into the next turn, and then corrected.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.agent.attribution_agent import AttributionAgent
from src.agent.react_agent import ReActAgent


class FakeLLM:
    def __init__(self):
        self.calls = 0

    def chat(self, messages, temperature=None, max_tokens=None):
        self.calls += 1
        if self.calls == 1:
            return (
                "Thought: 先给出一个会触发断言反馈的初始答案\n\n"
                "Action:\n```python\nn = 1\nprint('n =', n)\n```"
            )
        return (
            "Thought: 根据自动验证和归因提示修正最终变量，任务完成\n\n"
            "Action:\n```python\nn = 42\nprint('n =', n)\n```"
        )


def main() -> bool:
    agent = ReActAgent(
        llm_client=FakeLLM(),
        max_iterations=3,
        verbose=False,
        enable_reflection=False,
        enable_attribution=True,
        attribution_agent=AttributionAgent(use_llm=False),
    )
    result = agent.solve_task(
        "Define an integer variable n whose value is 42.",
        {
            "unique_question_id": "smoke_test",
            "analysis_types": "['Descriptive Statistics']",
            "test_cases": "assert 'n' in globals()\nassert isinstance(n, int)\nassert n == 42",
        },
    )

    assert result["success"] is True
    assert result["total_steps"] == 2
    first_step = result["execution_trace"][0]
    assert first_step["validation_failed"]
    assert first_step["attribution"]["error_type"] in {
        "输出格式错误",
        "统计逻辑错误",
        "未知错误",
    }
    assert agent.get_exec_namespace()["n"] == 42
    print("Smoke test passed: ReAct validation and attribution loop works.")
    return True


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
