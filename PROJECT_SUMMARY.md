# Project Summary

This project implements a reasoning code agent for biomedical data science tasks. It targets BioDSBench-style tasks where the agent must generate Python code, execute it on real clinical or genomics tables, observe runtime or assertion feedback, and iteratively repair the solution.

## Core Components

- `src/agent/react_agent.py`: ReAct-style main loop with code generation, execution, proactive test-case validation, progressive prompting, memory injection, skill injection, and failure attribution.
- `src/agent/action_space.py`: Four action categories: `request_info`, `terminal`, `code_execution`, and `debugging`.
- `src/agent/sandbox.py`: Optional isolated execution environment with subprocess execution, timeout control, static safety checks, and persistent namespace transfer.
- `src/agent/attribution_agent.py`: Failure attribution sub-agent that classifies execution and validation failures and returns structured repair hints.
- `src/agent/experience_pool.py`: Episodic memory and reflection pool for task-level experience reuse.
- `src/agent/skill_library.py`: Skill library for reusable code patterns extracted from successful solutions.
- `src/tasks/benchmark_runner.py`: BioDSBench benchmark runner that records task-level results, traces, timing, and validation details.

## Reproducibility

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the no-API smoke test:

```bash
python3 smoke_test.py
```

Run project validation:

```bash
python3 validate_project.py
```

Run a BioDSBench task after configuring `DASHSCOPE_API_KEY`:

```bash
python3 run_benchmark.py --task-index 0 --model qwen-turbo --attribution
```

Run ablation groups:

```bash
python3 run_ablation.py --groups A AT B C D F --max-tasks 30 --resume
```

Benchmark outputs are written to `benchmark_output*/benchmark_results.json` or `ablation_output/*/benchmark_results.json`, with per-task traces stored as `task_*.json`.
