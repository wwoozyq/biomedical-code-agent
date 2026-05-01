"""
BioDSBench v2 runner - with experience pool and reflection
"""
import json
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from collections import defaultdict

from .biodsbench_loader import BioDSBenchLoader
from ..agent.react_agent import ReActAgent
from ..agent.experience_pool import ExperiencePool
from ..agent.skill_library import SkillLibrary
from ..llm.client import LLMClient


class BenchmarkRunner:

    def __init__(
        self,
        llm_client: LLMClient,
        data_root: str = "./biodsbench_data",
        output_dir: str = "./benchmark_output",
        max_iterations: int = 8,
        verbose: bool = True,
        enable_experience: bool = True,
        enable_reflection: bool = True,
        use_sandbox: bool = False,
        enable_skills: bool = False,
        enable_attribution: bool = False,
    ):
        self.llm = llm_client
        self.loader = BioDSBenchLoader(data_root)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.max_iterations = max_iterations
        self.verbose = verbose
        self.enable_reflection = enable_reflection
        self.enable_attribution = enable_attribution
        self.use_sandbox = use_sandbox
        self.experience_pool = None
        self.skill_library = None
        if enable_experience:
            pool_path = self.output_dir / "experience_pool.json"
            self.experience_pool = ExperiencePool(str(pool_path))
            if self.verbose:
                stats = self.experience_pool.get_stats()
                print("📚 经验池: {} 条 ({} 成功)".format(stats["total"], stats["success"]))
        if enable_skills:
            skill_dir = self.output_dir / "skill_library"
            self.skill_library = SkillLibrary(library_dir=str(skill_dir))
            if self.verbose:
                stats = self.skill_library.get_stats()
                print("🛠️ 技能库: {} 个技能".format(stats["total_skills"]))

    def run_single_task(self, task_index: int) -> Dict[str, Any]:
        raw_task = self.loader.load_task_by_index(task_index)
        prepared = self.loader.prepare_task(raw_task)
        result = self._execute_and_verify(prepared)
        result["task_index"] = task_index
        return result

    def run_task_by_id(self, unique_question_id: str) -> Dict[str, Any]:
        raw_task = self.loader.load_task_by_id(unique_question_id)
        prepared = self.loader.prepare_task(raw_task)
        return self._execute_and_verify(prepared)

    def run_batch(self, start=0, end=None, task_indices=None):
        all_tasks = self.loader.load_all_tasks()
        if task_indices is not None:
            indices = task_indices
        else:
            if end is None:
                end = len(all_tasks)
            indices = list(range(start, min(end, len(all_tasks))))
        results = []
        for i, idx in enumerate(indices):
            print("\n" + "#" * 60)
            print("  任务 {}/{} (index={})".format(i + 1, len(indices), idx))
            print("#" * 60)
            try:
                result = self.run_single_task(idx)
                results.append(result)
            except Exception as e:
                results.append({"task_index": idx, "unique_question_id": "", "passed": False, "error": str(e), "execution_time": 0})
                if self.verbose:
                    print("💥 任务 {} 异常: {}".format(idx, e))
        summary = self._compute_summary(results)
        output_file = self.output_dir / "benchmark_results.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump({"summary": summary, "details": results}, f, ensure_ascii=False, indent=2, default=str)
        print("\n📊 结果已保存到 {}".format(output_file))
        self._print_summary(summary)
        return {"summary": summary, "details": results}

    def _execute_and_verify(self, prepared):
        qid = prepared["unique_question_id"]
        query = prepared["query"]
        test_cases_str = prepared.get("test_cases", "")
        agent = ReActAgent(
            llm_client=self.llm,
            max_iterations=self.max_iterations,
            verbose=self.verbose,
            experience_pool=self.experience_pool,
            enable_reflection=self.enable_reflection,
            use_sandbox=self.use_sandbox,
            skill_library=self.skill_library,
            enable_attribution=self.enable_attribution,
        )
        agent_result = agent.solve_task(query, prepared)
        passed, test_details = self._verify_test_cases(test_cases_str, agent.get_exec_namespace())
        result = {
            "task_index": None,
            "unique_question_id": qid,
            "query": query[:200],
            "analysis_types": prepared.get("analysis_types", ""),
            "passed": passed,
            "test_details": test_details,
            "agent_success": agent_result["success"],
            "total_steps": agent_result["total_steps"],
            "execution_time": agent_result["execution_time"],
            "execution_trace": agent_result["execution_trace"],
        }
        status = "✅ PASS" if passed else "❌ FAIL"
        print("\n{}  [{}]  steps={}  time={:.1f}s".format(status, qid, agent_result["total_steps"], agent_result["execution_time"]))
        if not passed:
            print("  验证详情: {}".format(test_details[:200]))
        log_file = self.output_dir / "task_{}.json".format(qid)
        with open(log_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2, default=str)
        return result

    def _verify_test_cases(self, test_cases_str, namespace):
        if not test_cases_str or not test_cases_str.strip():
            return True, "无 test_cases"
        assertions = [line.strip() for line in test_cases_str.strip().split("\n") if line.strip() and line.strip().startswith("assert")]
        if not assertions:
            return True, "无有效断言"
        failed = []
        for i, assertion in enumerate(assertions):
            try:
                exec(assertion, namespace)
            except AssertionError as e:
                failed.append("断言 {} 失败: {}  ({})".format(i + 1, assertion, e))
            except Exception as e:
                failed.append("断言 {} 异常: {}  ({}: {})".format(i + 1, assertion, type(e).__name__, e))
        if failed:
            return False, "; ".join(failed)
        return True, "全部 {} 条断言通过".format(len(assertions))

    def _compute_summary(self, results):
        total = len(results)
        passed = sum(1 for r in results if r.get("passed", False))
        times = [r.get("execution_time", 0) for r in results]
        steps = [r.get("total_steps", 0) for r in results]
        type_stats = defaultdict(lambda: {"total": 0, "passed": 0})
        for r in results:
            atypes = r.get("analysis_types", "unknown")
            type_stats[atypes]["total"] += 1
            if r.get("passed"):
                type_stats[atypes]["passed"] += 1
        return {
            "total_tasks": total,
            "passed": passed,
            "failed": total - passed,
            "pass_rate": round(passed / total, 4) if total > 0 else 0,
            "avg_execution_time": round(sum(times) / total, 2) if total > 0 else 0,
            "avg_steps": round(sum(steps) / total, 2) if total > 0 else 0,
            "total_time": round(sum(times), 2),
            "by_type": dict(type_stats),
        }

    def _print_summary(self, summary):
        print("\n" + "=" * 60)
        print("📊 Benchmark 汇总")
        print("=" * 60)
        print("  总任务数:   {}".format(summary["total_tasks"]))
        print("  通过:       {}".format(summary["passed"]))
        print("  失败:       {}".format(summary["failed"]))
        print("  通过率:     {:.1f}%".format(summary["pass_rate"] * 100))
        print("  平均步骤:   {}".format(summary["avg_steps"]))
        print("  平均耗时:   {}s".format(summary["avg_execution_time"]))
        print("  总耗时:     {}s".format(summary["total_time"]))
        if summary.get("by_type"):
            print("\n  按类型统计:")
            for atype, stats in summary["by_type"].items():
                rate = stats["passed"] / stats["total"] * 100 if stats["total"] > 0 else 0
                print("    {}: {}/{} ({:.0f}%)".format(atype[:60], stats["passed"], stats["total"], rate))
        print("=" * 60)
