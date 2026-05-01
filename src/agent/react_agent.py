"""
ReAct 智能体核心实现 v2
- LLM 驱动的 Thought → Action → Observation 循环
- 经验复用池 (Experience Pool) + 相似任务 few-shot 注入
- 反思机制 (Reflection) — 任务结束后结构化反思并存入经验池
- 主动验证 (Proactive Validation) — 每步执行后自动跑 test_cases
- 渐进式提示 (Progressive Prompting) — 根据步骤阶段调整提示策略
"""

from typing import Dict, Any, List, Optional, Tuple
import json
import time
import re
import io
import sys
import traceback
from dataclasses import dataclass
from enum import Enum

from .action_space import ActionSpace, ActionType
from .experience_pool import ExperiencePool, Experience, ReflectionEngine
from .skill_library import SkillLibrary
from .sandbox import Sandbox
from .attribution_agent import AttributionAgent, AttributionResult
from ..llm.client import LLMClient


class AgentState(Enum):
    THINKING = "thinking"
    ACTING = "acting"
    OBSERVING = "observing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Step:
    step_id: int
    thought: str
    action_type: Optional[ActionType]
    action_params: Optional[Dict[str, Any]]
    observation: Optional[Dict[str, Any]]
    timestamp: float
    state: AgentState


SYSTEM_PROMPT = """\
你是一个生物医学数据科学编码智能体，擅长处理临床数据、基因组数据和生存分析。
你的工作流程遵循 ReAct 范式：Thought → Action → Observation，循环迭代直到任务完成。

## 回复格式（严格遵守）

Thought: <分析当前状态，规划下一步>

Action:
```python
<要执行的 Python 代码>
```

## 核心规则

1. 每次只输出一个代码块
2. 用 print() 输出关键中间结果（数据形状、列名、前几行、统计值）
3. 任务要求生成的变量（output_df, n, pvalue 等）必须在代码中明确定义
4. 出错时分析原因并修正，不要重复同样的错误
5. 验证失败时仔细对比期望值和实际值，调整数据处理逻辑
6. 当且仅当你确信所有要求的变量都已正确生成时，在 Thought 中写 "任务完成"

## 常见生物医学数据处理模式

- 临床数据通常有 PATIENT_ID, SAMPLE_ID 等标识列
- 字符串类型的数值列需要先转换: pd.to_numeric(col, errors='coerce')
- value_counts() 返回的列名是 'count'（pandas >= 2.0）
- 生存分析用 lifelines 库的 KaplanMeierFitter
- 合并表用 pd.merge()，注意 on 参数的列名匹配
"""


class ReActAgent:
    """基于 ReAct 范式的推理编码智能体 v2"""

    def __init__(
        self,
        llm_client: LLMClient,
        max_iterations: int = 10,
        sandbox_dir: str = "./sandbox",
        data_dir: str = "./data",
        verbose: bool = True,
        experience_pool: Optional[ExperiencePool] = None,
        enable_reflection: bool = True,
        use_sandbox: bool = False,
        sandbox_timeout: int = 60,
        skill_library: Optional[SkillLibrary] = None,
        enable_attribution: bool = True,
        attribution_agent: Optional[AttributionAgent] = None,
    ):
        self.llm = llm_client
        self.max_iterations = max_iterations
        self.verbose = verbose
        self.action_space = ActionSpace(sandbox_dir, data_dir)
        self.experience_pool = experience_pool
        self.enable_reflection = enable_reflection
        self.reflection_engine = ReflectionEngine(llm_client) if enable_reflection else None
        self.use_sandbox = use_sandbox
        self.skill_library = skill_library
        self.enable_attribution = enable_attribution
        self.attribution_agent = (
            attribution_agent
            if attribution_agent is not None
            else AttributionAgent(llm_client, use_llm=True)
            if enable_attribution
            else None
        )

        # 执行状态
        self.current_step = 0
        self.execution_trace: List[Step] = []
        self.task_context: Dict[str, Any] = {}
        self.state = AgentState.THINKING
        self.messages: List[Dict[str, str]] = []
        self._exec_namespace: Dict[str, Any] = {}
        self._sandbox: Optional[Sandbox] = Sandbox(timeout=sandbox_timeout) if use_sandbox else None

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------

    def solve_task(
        self, task_description: str, task_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """解决给定任务"""
        self.task_context = {
            "description": task_description,
            "data": task_data,
            "start_time": time.time(),
        }

        if self.verbose:
            print(f"\n{'='*60}")
            print(f"📋 任务: {task_description[:120]}")
            print(f"⚙️  最大迭代: {self.max_iterations}")
            print(f"{'='*60}")

        # 重置
        self.current_step = 0
        self.execution_trace = []
        self.state = AgentState.THINKING
        self._exec_namespace = {}
        if self._sandbox is not None:
            self._sandbox.reset()

        # 构建初始 prompt（含经验注入）
        self.messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": self._build_task_prompt(task_description, task_data)},
        ]

        # 标记是否已注入过技能（只在第一次成功执行后注入一次）
        self._skill_injected = False

        # 主循环
        while (
            self.current_step < self.max_iterations
            and self.state not in (AgentState.COMPLETED, AgentState.FAILED)
        ):
            try:
                # 1. 调用 LLM
                llm_reply = self._call_llm()

                # 2. 解析 Thought + Code
                thought, code = self._parse_reply(llm_reply)

                if self.verbose:
                    print(f"\n--- Step {self.current_step + 1} ---")
                    print(f"💭 Thought: {thought[:200]}")

                # 3. 执行代码
                observation = self._execute_code(code)

                if self.verbose:
                    if observation.get("error"):
                        print(f"❌ Error: {observation['error'][:300]}")
                    else:
                        print(f"✅ Output: {observation.get('stdout', '')[:400]}")

                # 4. 记录
                step = Step(
                    step_id=self.current_step,
                    thought=thought,
                    action_type=ActionType.CODE_EXECUTION,
                    action_params={"code": code},
                    observation=observation,
                    timestamp=time.time(),
                    state=self.state,
                )
                self.execution_trace.append(step)

                obs_text = self._format_observation(observation)
                self.messages.append({"role": "assistant", "content": llm_reply})

                # 4.5 AST 技能检索：第一步成功执行后，用已执行代码做 AST 匹配
                if (
                    not self._skill_injected
                    and self.skill_library
                    and observation.get("success")
                    and code
                ):
                    # 收集已执行的所有代码
                    all_code = "\n".join(
                        s.action_params.get("code", "")
                        for s in self.execution_trace
                        if s.action_params and s.observation and s.observation.get("success")
                    )
                    if all_code.strip():
                        matched_skills = self.skill_library.retrieve(
                            code=all_code,
                            query=self.task_context.get("description", ""),
                            analysis_types=self.task_context["data"].get("analysis_types", ""),
                            top_k=2,
                        )
                        skill_text = self.skill_library.format_for_prompt(matched_skills)
                        if skill_text:
                            self.messages.append({
                                "role": "user",
                                "content": f"💡 根据你已执行的代码，以下技能函数可能有帮助：\n\n{skill_text}",
                            })
                            self._skill_injected = True
                            if self.verbose:
                                print(f"🛠️ AST 技能注入: {[s.name for s in matched_skills]}")

                # 5. 主动验证：每步执行成功后都跑 test_cases
                test_cases = self.task_context["data"].get("test_cases", "")
                validation_detail = ""
                if observation.get("success") and test_cases and test_cases.strip():
                    passed, detail = self._run_test_cases(test_cases)
                    if passed:
                        if self.verbose:
                            print(f"🎉 验证通过: {detail}")
                        self.state = AgentState.COMPLETED
                        self._post_task_reflection(success=True)
                        break
                    validation_detail = detail
                    observation["validation_failed"] = detail
                    if self.verbose:
                        print(f"⚠️ 自动验证未通过: {detail[:300]}")

                attribution_text = ""
                if observation.get("error") or validation_detail:
                    attribution = self._attribute_failure(code, observation, validation_detail)
                    if attribution is not None:
                        observation["attribution"] = attribution.to_dict()
                        attribution_text = self.attribution_agent.format_for_prompt(attribution)
                        if self.verbose:
                            print(f"🧭 归因: {attribution.error_type} - {attribution.root_cause[:120]}")

                # 6. LLM 说完成但验证没过 → 反馈继续
                if "任务完成" in thought or "任务已完成" in thought:
                    if test_cases and test_cases.strip():
                        passed, detail = self._run_test_cases(test_cases)
                        if passed:
                            if self.verbose:
                                print(f"🎉 验证通过: {detail}")
                            self.state = AgentState.COMPLETED
                            self._post_task_reflection(success=True)
                            break
                        else:
                            if self.verbose:
                                print(f"⚠️ 验证失败: {detail}")
                            feedback = (
                                f"Observation:\n{obs_text}\n\n"
                                f"⚠️ 自动验证未通过:\n{detail}\n\n"
                                f"请仔细分析失败原因，修正代码。注意对比期望值和实际值。"
                            )
                            self.messages.append({"role": "user", "content": feedback})
                            self.current_step += 1
                            continue
                    else:
                        self.state = AgentState.COMPLETED
                        self._post_task_reflection(success=True)
                        break

                # 7. 渐进式提示：根据步骤阶段调整反馈
                nudge = self._get_progressive_nudge()
                validation_text = ""
                if validation_detail:
                    validation_text = f"\n\n⚠️ 自动验证未通过:\n{validation_detail}"
                attribution_block = f"\n\n{attribution_text}" if attribution_text else ""
                self.messages.append({
                    "role": "user",
                    "content": f"Observation:\n{obs_text}{validation_text}{attribution_block}\n\n{nudge}",
                })
                self.current_step += 1

            except Exception as e:
                error_step = Step(
                    step_id=self.current_step,
                    thought=f"系统异常: {str(e)}",
                    action_type=None,
                    action_params=None,
                    observation={"error": str(e), "success": False},
                    timestamp=time.time(),
                    state=AgentState.FAILED,
                )
                self.execution_trace.append(error_step)
                self.state = AgentState.FAILED
                if self.verbose:
                    print(f"💥 系统异常: {e}")
                break

        # 如果循环结束还没完成，做失败反思
        if self.state != AgentState.COMPLETED:
            self._post_task_reflection(success=False)

        return self._generate_final_result()

    def get_exec_namespace(self) -> Dict[str, Any]:
        return self._exec_namespace

    def get_metrics(self) -> Dict[str, Any]:
        if not self.execution_trace:
            return {}
        successful = sum(
            1 for s in self.execution_trace
            if s.observation and s.observation.get("success", False)
        )
        elapsed = time.time() - self.task_context.get("start_time", time.time())
        return {
            "success_rate": successful / len(self.execution_trace),
            "total_attempts": len(self.execution_trace),
            "average_time_per_step": elapsed / len(self.execution_trace),
            "completion_status": self.state.value,
        }

    # ------------------------------------------------------------------
    # Prompt 构建
    # ------------------------------------------------------------------

    def _build_task_prompt(self, description: str, task_data: Dict[str, Any]) -> str:
        """构建初始任务 prompt，含经验注入"""
        tables = task_data.get("tables", [])
        table_schemas = task_data.get("table_schemas", "")
        cot = task_data.get("cot_instructions", "")
        test_cases = task_data.get("test_cases", "")
        analysis_types = task_data.get("analysis_types", "")

        parts = [f"## 任务\n{description}"]

        if tables:
            parts.append(f"## 可用数据文件\n{json.dumps(tables, ensure_ascii=False)}")

        if table_schemas:
            parts.append(f"## 数据表 Schema\n{table_schemas}")

        if cot:
            parts.append(f"## 解题提示\n{cot}")

        if test_cases:
            parts.append(
                f"## 验证条件（你的代码必须让以下断言全部通过）\n```python\n{test_cases}\n```"
            )

        # 经验注入：检索相似成功经验作为 few-shot
        if self.experience_pool:
            similar = self.experience_pool.retrieve(
                query=description, analysis_types=analysis_types, top_k=2
            )
            if similar:
                examples = []
                for i, exp in enumerate(similar):
                    examples.append(
                        f"### 示例 {i+1} (类型: {exp.analysis_types})\n"
                        f"任务: {exp.query[:150]}\n"
                        f"成功代码:\n```python\n{exp.final_code[:800]}\n```"
                    )
                    if exp.reflection:
                        examples.append(f"策略: {exp.reflection}")
                parts.append("## 参考经验（来自相似任务的成功解法）\n" + "\n\n".join(examples))

            # 注入失败教训
            failures = self.experience_pool.retrieve_failures(
                analysis_types=analysis_types, top_k=1
            )
            failure_lessons = [
                f for f in failures
                if not f.success and f.reflection
            ]
            if failure_lessons:
                lessons = failure_lessons[0]
                parts.append(
                    f"## ⚠️ 避免以下错误\n"
                    f"之前在类似任务中犯过的错: {lessons.reflection}"
                )

        # 技能注入：检索匹配的可复用函数
        if self.skill_library:
            matched_skills = self.skill_library.retrieve(
                query=description, analysis_types=analysis_types, top_k=2
            )
            skill_text = self.skill_library.format_for_prompt(matched_skills)
            if skill_text:
                parts.append(skill_text)

        parts.append("请开始分析，先思考再写代码。")
        return "\n\n".join(parts)

    def _get_progressive_nudge(self) -> str:
        """渐进式提示：根据当前步骤给出不同的引导"""
        step = self.current_step
        remaining = self.max_iterations - step - 1

        if step == 0:
            return "请继续。如果数据已加载，开始处理任务逻辑。"
        elif remaining <= 2:
            return (
                f"⏰ 注意：只剩 {remaining} 步机会了。"
                f"请直接写出完整的解题代码，确保生成所有要求的变量，然后声明任务完成。"
            )
        elif remaining <= 4:
            return "请继续推进。如果核心逻辑已完成，尝试运行验证条件确认结果正确。"
        else:
            return "请继续。如果任务已完成，请在 Thought 中写明 '任务完成'。"

    # ------------------------------------------------------------------
    # LLM 调用 & 解析
    # ------------------------------------------------------------------

    def _call_llm(self) -> str:
        return self.llm.chat(self.messages)

    def _parse_reply(self, reply: str) -> Tuple[str, str]:
        """从 LLM 回复中提取 Thought 和代码"""
        thought = ""
        thought_match = re.search(r"Thought:\s*(.*?)(?=Action:|```)", reply, re.DOTALL)
        if thought_match:
            thought = thought_match.group(1).strip()
        else:
            code_start = reply.find("```")
            if code_start > 0:
                thought = reply[:code_start].strip()
            else:
                thought = reply.strip()

        code = ""
        code_match = re.search(r"```(?:python)?\s*\n(.*?)```", reply, re.DOTALL)
        if code_match:
            code = code_match.group(1).strip()

        return thought, code

    # ------------------------------------------------------------------
    # 代码执行 & 验证
    # ------------------------------------------------------------------

    def _execute_code(self, code: str) -> Dict[str, Any]:
        """在持久命名空间中执行 Python 代码，捕获 stdout"""
        if not code:
            return {"success": True, "stdout": "(无代码执行)", "error": None}

        # 沙箱模式：子进程隔离执行
        if self._sandbox is not None:
            result = self._sandbox.execute(code)
            # 同步命名空间供 test_cases 验证使用
            self._exec_namespace = self._sandbox.get_namespace()
            return result

        # 直接执行模式（向后兼容）
        old_stdout = sys.stdout
        sys.stdout = captured = io.StringIO()

        try:
            exec(code, self._exec_namespace)
            stdout_text = captured.getvalue()
            return {"success": True, "stdout": stdout_text, "error": None}
        except Exception:
            stdout_text = captured.getvalue()
            err = traceback.format_exc()
            return {"success": False, "stdout": stdout_text, "error": err}
        finally:
            sys.stdout = old_stdout

    def _run_test_cases(self, test_cases_str: str) -> Tuple[bool, str]:
        """在当前命名空间中运行 test_cases 断言"""
        assertions = [
            line.strip()
            for line in test_cases_str.strip().split("\n")
            if line.strip() and line.strip().startswith("assert")
        ]
        if not assertions:
            return True, "无有效断言"

        failed = []
        for i, assertion in enumerate(assertions):
            try:
                exec(assertion, self._exec_namespace)
            except AssertionError:
                failed.append(f"断言 {i+1} 失败: {assertion}")
            except Exception as e:
                failed.append(f"断言 {i+1} 异常: {assertion} ({type(e).__name__}: {e})")

        if failed:
            return False, "\n".join(failed)
        return True, f"全部 {len(assertions)} 条断言通过"

    def _format_observation(self, obs: Dict[str, Any]) -> str:
        parts = []
        if obs.get("stdout"):
            parts.append(f"[stdout]\n{obs['stdout'][:2000]}")
        if obs.get("error"):
            parts.append(f"[error]\n{obs['error'][:2000]}")
        if not parts:
            parts.append("代码执行成功，无输出。")
        return "\n".join(parts)

    def _attribute_failure(
        self,
        code: str,
        observation: Dict[str, Any],
        validation_detail: str = "",
    ) -> Optional[AttributionResult]:
        """Call the attribution sub-agent on execution or validation failure."""
        if not self.attribution_agent:
            return None
        history = []
        for step in self.execution_trace[-3:]:
            history.append({
                "step_id": step.step_id,
                "thought": step.thought,
                "success": step.observation.get("success", False) if step.observation else False,
                "error": step.observation.get("error", "") if step.observation else "",
            })
        return self.attribution_agent.analyze(
            task_description=self.task_context.get("description", ""),
            code=code,
            observation=observation,
            test_detail=validation_detail,
            history=history,
            task_data=self.task_context.get("data", {}),
        )

    # ------------------------------------------------------------------
    # 反思 & 经验存储
    # ------------------------------------------------------------------

    def _post_task_reflection(self, success: bool):
        """任务结束后执行反思并存入经验池"""
        if not self.experience_pool:
            return

        task_data = self.task_context.get("data", {})
        qid = task_data.get("unique_question_id", "unknown")
        query = self.task_context.get("description", "")
        analysis_types = task_data.get("analysis_types", "")

        # 提取最终成功的代码（取最后一个成功步骤的代码）
        final_code = ""
        errors = ""
        for step in reversed(self.execution_trace):
            if step.action_params and step.action_params.get("code"):
                if step.observation and step.observation.get("success"):
                    final_code = step.action_params["code"]
                    break
        # 收集错误信息
        error_list = []
        for step in self.execution_trace:
            if step.observation and step.observation.get("error"):
                error_list.append(step.observation["error"][:200])
        errors = "\n".join(error_list[-3:])  # 最近 3 个错误

        # LLM 反思
        reflection_text = ""
        key_patterns = []
        if self.reflection_engine:
            try:
                ref = self.reflection_engine.reflect(
                    query=query, success=success,
                    steps=len(self.execution_trace),
                    final_code=final_code, errors=errors,
                )
                reflection_text = ref.get("strategy", "")
                key_patterns = ref.get("key_patterns", [])
                if ref.get("lessons"):
                    reflection_text += " | 教训: " + "; ".join(ref["lessons"])
            except Exception:
                pass  # 反思失败不影响主流程

        exp = Experience(
            task_id=qid,
            query=query,
            analysis_types=analysis_types,
            success=success,
            final_code=final_code,
            reflection=reflection_text,
            key_patterns=key_patterns,
            steps_used=len(self.execution_trace),
        )
        self.experience_pool.add_experience(exp)

        if self.verbose and reflection_text:
            print(f"🔍 反思: {reflection_text[:200]}")

        # 技能提取：成功任务 → 让 LLM 重构为可复用函数 → 存入技能库
        if success and self.skill_library and final_code:
            try:
                skill = self.skill_library.extract_skill(
                    llm_client=self.llm,
                    code=final_code,
                    query=query,
                    task_id=qid,
                    analysis_types=analysis_types,
                )
                if skill and self.verbose:
                    print(f"🛠️ 技能提取: {skill.name} (调用链长度: {len(skill.call_chain)})")
            except Exception:
                pass  # 技能提取失败不影响主流程

    # ------------------------------------------------------------------
    # 结果生成
    # ------------------------------------------------------------------

    def _generate_final_result(self) -> Dict[str, Any]:
        elapsed = time.time() - self.task_context["start_time"]
        result = {
            "task_description": self.task_context["description"],
            "success": self.state == AgentState.COMPLETED,
            "total_steps": len(self.execution_trace),
            "execution_time": elapsed,
            "final_state": self.state.value,
            "execution_trace": [
                {
                    "step_id": s.step_id,
                    "thought": s.thought,
                    "action_type": s.action_type.value if s.action_type else None,
                    "code": s.action_params.get("code", "") if s.action_params else "",
                    "success": s.observation.get("success", False) if s.observation else False,
                    "stdout": s.observation.get("stdout", "") if s.observation else "",
                    "error": s.observation.get("error", "") if s.observation else "",
                    "validation_failed": s.observation.get("validation_failed", "") if s.observation else "",
                    "attribution": s.observation.get("attribution", {}) if s.observation else {},
                    "timestamp": s.timestamp,
                }
                for s in self.execution_trace
            ],
        }
        if self.verbose:
            status = "✅ 成功" if result["success"] else "❌ 失败"
            print(f"\n{'='*60}")
            print(f"结果: {status} | 步骤: {result['total_steps']} | 耗时: {elapsed:.1f}s")
            print(f"{'='*60}")
        return result
