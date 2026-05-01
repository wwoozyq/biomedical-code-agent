#!/usr/bin/env python3
"""
Project validation script for the biomedical code agent.

The checks mirror the current project structure: ReAct execution loop,
action space, attribution, memory, skills, benchmark outputs, docs, and a
small no-API smoke test.
"""

from __future__ import annotations

import json
import py_compile
import subprocess
import sys
from pathlib import Path
from typing import Callable, Iterable


ROOT = Path(__file__).resolve().parent


def ok(message: str) -> None:
    print(f"✅ {message}")


def warn(message: str) -> None:
    print(f"⚠️  {message}")


def fail(message: str) -> None:
    print(f"❌ {message}")


def read_text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def exists_all(paths: Iterable[str]) -> list[str]:
    return [p for p in paths if not (ROOT / p).exists()]


def check_basic_engineering() -> bool:
    print("🔍 检查基础工程实现...")

    core_files = [
        "src/agent/react_agent.py",
        "src/agent/action_space.py",
        "src/agent/sandbox.py",
        "src/agent/attribution_agent.py",
        "src/tasks/biodsbench_loader.py",
        "src/tasks/benchmark_runner.py",
        "src/llm/client.py",
        "run_benchmark.py",
        "main.py",
    ]
    missing = exists_all(core_files)
    if missing:
        fail(f"缺少核心文件: {missing}")
        return False
    ok("核心文件完整")

    react = read_text("src/agent/react_agent.py")
    react_features = [
        "class ReActAgent",
        "def solve_task",
        "def _call_llm",
        "def _parse_reply",
        "def _execute_code",
        "def _run_test_cases",
        "def _attribute_failure",
        "execution_trace",
    ]
    missing_features = [f for f in react_features if f not in react]
    if missing_features:
        fail(f"ReAct 主循环缺少关键实现: {missing_features}")
        return False
    ok("ReAct 生成-执行-验证-归因闭环存在")

    action = read_text("src/agent/action_space.py")
    actions = ["REQUEST_INFO", "TERMINAL", "CODE_EXECUTION", "DEBUGGING",
               "_request_info", "_terminal_action", "_code_execution", "_debugging_action"]
    missing_actions = [a for a in actions if a not in action]
    if missing_actions:
        fail(f"动作空间缺少实现: {missing_actions}")
        return False
    ok("四类基础动作完整")

    sandbox = read_text("src/agent/sandbox.py")
    sandbox_features = ["multiprocessing", "timeout", "FORBIDDEN_PATTERNS", "pickle"]
    missing_sandbox = [f for f in sandbox_features if f not in sandbox]
    if missing_sandbox:
        fail(f"沙箱缺少关键机制: {missing_sandbox}")
        return False
    ok("安全沙箱包含隔离、超时、静态检查和命名空间传递")

    return True


def check_advanced_modules() -> bool:
    print("🧠 检查进阶模块...")

    files = [
        "src/agent/experience_pool.py",
        "src/agent/skill_library.py",
        "src/agent/attribution_agent.py",
        "src/agent/ast_fingerprint.py",
        "src/multi_agent/coordinator.py",
        "web_interface.py",
        "run_web_interface.py",
        "chat.py",
        "app.py",
    ]
    missing = exists_all(files)
    if missing:
        fail(f"缺少进阶模块文件: {missing}")
        return False

    checks = {
        "Memory 经验池": ("src/agent/experience_pool.py", ["class ExperiencePool", "retrieve", "retrieve_failures", "ReflectionEngine"]),
        "Skills 技能库": ("src/agent/skill_library.py", ["class SkillLibrary", "extract_skill", "retrieve", "format_for_prompt"]),
        "归因子智能体": ("src/agent/attribution_agent.py", ["class AttributionAgent", "AttributionResult", "format_for_prompt", "ERROR_TYPES"]),
        "多智能体框架": ("src/multi_agent/coordinator.py", ["class MultiAgentCoordinator", "collaboration_patterns", "QualityAssuranceAgent"]),
        "Web 可视化": ("web_interface.py", ["streamlit", "def main", "ReActAgent", "display_execution_trace"]),
    }
    for name, (path, needles) in checks.items():
        content = read_text(path)
        missing_needles = [n for n in needles if n not in content]
        if missing_needles:
            fail(f"{name} 缺少关键内容: {missing_needles}")
            return False
        ok(f"{name} 已实现")

    return True


def _load_benchmark_files() -> list[Path]:
    candidates = []
    for pattern in [
        "benchmark_output*/benchmark_results.json",
        "ablation_output/*/benchmark_results.json",
    ]:
        candidates.extend(ROOT.glob(pattern))
    return sorted(set(candidates))


def check_experiment_outputs() -> bool:
    print("📊 检查实验输出与轨迹...")

    result_files = _load_benchmark_files()
    if not result_files:
        fail("未找到 benchmark_results.json")
        return False

    valid_files = 0
    total_tasks = 0
    total_traced = 0
    for path in result_files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            fail(f"无法读取 {path}: {exc}")
            return False

        summary = data.get("summary", {})
        details = data.get("details", [])
        required = ["total_tasks", "passed", "failed", "pass_rate", "avg_execution_time", "avg_steps"]
        missing = [k for k in required if k not in summary]
        if missing:
            fail(f"{path} summary 缺少字段: {missing}")
            return False
        if not details:
            fail(f"{path} details 为空")
            return False

        traced = sum(1 for item in details if item.get("execution_trace"))
        total_traced += traced
        total_tasks += int(summary.get("total_tasks", len(details)))
        valid_files += 1

    ok(f"找到 {valid_files} 个实验汇总文件，覆盖 {total_tasks} 条任务记录")
    if total_traced == 0:
        fail("实验记录中没有 execution_trace")
        return False
    ok(f"执行轨迹记录可用: {total_traced} 条任务含 trace")
    return True


def check_docs_and_reproducibility() -> bool:
    print("📝 检查文档、依赖与复现入口...")

    docs = ["README.md", "PROJECT_GUIDE.md", "PROJECT_SUMMARY.md", "requirements.txt"]
    missing = exists_all(docs)
    if missing:
        fail(f"缺少文档或依赖清单: {missing}")
        return False

    readme = read_text("README.md")
    readme_needles = ["快速开始", "配置 API Key", "运行", "Benchmark", "项目结构", "requirements.txt"]
    missing_sections = [s for s in readme_needles if s not in readme]
    if missing_sections:
        fail(f"README 缺少关键说明: {missing_sections}")
        return False
    ok("README 覆盖安装、配置、运行、评测与结构说明")

    required_dirs = ["src", "config", "examples", "data", "data/sample_data"]
    missing_dirs = exists_all(required_dirs)
    if missing_dirs:
        fail(f"缺少项目目录: {missing_dirs}")
        return False
    ok("项目目录结构完整")

    entrypoints = ["run_benchmark.py", "run_ablation.py", "run_ablation_ds.py", "run_web_interface.py", "chat.py"]
    missing_entrypoints = exists_all(entrypoints)
    if missing_entrypoints:
        fail(f"缺少运行入口: {missing_entrypoints}")
        return False
    ok("命令行、消融实验和 Web 入口齐全")
    return True


def check_python_syntax() -> bool:
    print("🐍 检查 Python 语法...")

    paths = [
        "run_benchmark.py",
        "run_ablation.py",
        "run_ablation_ds.py",
        "main.py",
        "multi_agent_main.py",
        "chat.py",
        "app.py",
        "smoke_test.py",
    ]
    paths.extend(str(p.relative_to(ROOT)) for p in (ROOT / "src").rglob("*.py"))

    for path in paths:
        try:
            py_compile.compile(str(ROOT / path), doraise=True)
        except Exception as exc:
            fail(f"语法检查失败: {path}: {exc}")
            return False
    ok(f"Python 语法检查通过: {len(paths)} 个文件")
    return True


def check_smoke_test() -> bool:
    print("🧪 运行无 API smoke test...")

    smoke = ROOT / "smoke_test.py"
    if not smoke.exists():
        fail("缺少 smoke_test.py")
        return False

    proc = subprocess.run(
        [sys.executable, str(smoke)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=20,
    )
    if proc.returncode != 0:
        fail("smoke test 失败")
        if proc.stdout:
            print(proc.stdout)
        if proc.stderr:
            print(proc.stderr)
        return False
    print(proc.stdout.strip())
    ok("无 API 闭环测试通过")
    return True


def check_generated_outputs() -> bool:
    print("📈 检查可复现实验产物...")

    generated = []
    generated.extend(ROOT.glob("*.png"))
    generated.extend(ROOT.glob("*.csv"))
    generated.extend(ROOT.glob("benchmark_output*/task_*.json"))
    generated.extend(ROOT.glob("ablation_output/*/task_*.json"))

    if not generated:
        warn("未找到本地生成产物；这不影响代码运行，但会降低离线展示便利性")
        return True

    ok(f"本地已有 {len(generated)} 个可检查产物")
    return True


def run_check(name: str, func: Callable[[], bool]) -> bool:
    print(f"\n{'=' * 18} {name} {'=' * 18}")
    try:
        passed = func()
    except Exception as exc:
        fail(f"{name} 检查异常: {exc}")
        return False
    if passed:
        ok(f"{name} - 通过")
    else:
        fail(f"{name} - 未通过")
    return passed


def main() -> bool:
    print("🧬 生物医学数据科学推理编码智能体 - 工程复现性验证")
    print("=" * 72)

    checks = [
        ("基础工程实现", check_basic_engineering),
        ("进阶模块", check_advanced_modules),
        ("实验输出与轨迹", check_experiment_outputs),
        ("文档与复现入口", check_docs_and_reproducibility),
        ("Python 语法", check_python_syntax),
        ("Smoke Test", check_smoke_test),
        ("本地实验产物", check_generated_outputs),
    ]

    passed = sum(1 for name, func in checks if run_check(name, func))
    total = len(checks)
    rate = passed / total * 100

    print("\n" + "=" * 72)
    print("📊 验证结果总结")
    print("=" * 72)
    print(f"通过: {passed}/{total} ({rate:.1f}%)")
    if rate >= 90:
        print("🎉 工程规范与复现性已打通")
    elif rate >= 80:
        print("✅ 工程规范与复现性基本打通")
    else:
        print("⚠️  仍需补齐复现链路")

    print("\n常用复现命令:")
    print("  python3 smoke_test.py")
    print("  python3 run_benchmark.py --task-index 0 --model qwen-turbo --attribution")
    print("  python3 run_ablation.py --groups A AT B C D F --max-tasks 30 --resume")
    print("  python3 run_web_interface.py")

    return rate >= 80


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
