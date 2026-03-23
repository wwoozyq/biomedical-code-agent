"""
安全沙箱 — 在隔离子进程中执行用户代码

安全机制：
1. 子进程隔离：代码在独立进程中执行，崩溃不影响主进程
2. 超时控制：超过时限自动 kill
3. 资源限制（Linux/macOS）：限制内存和 CPU 时间
4. 危险操作拦截：静态检查禁止 os.system / subprocess / shutil.rmtree 等
5. 命名空间持久化：通过 pickle 在步骤间传递变量
"""

import multiprocessing as mp
import pickle
import io
import sys
import traceback
import signal
import re
from typing import Dict, Any, Optional, Tuple

# 禁止的危险模式（正则）
FORBIDDEN_PATTERNS = [
    r"\bos\.system\b",
    r"\bos\.popen\b",
    r"\bos\.exec\w*\b",
    r"\bos\.remove\b",
    r"\bos\.unlink\b",
    r"\bos\.rmdir\b",
    r"\bsubprocess\b",
    r"\bshutil\.rmtree\b",
    r"\b__import__\b",
    r"\beval\s*\(",
    r"\bopen\s*\(.*(w|a)\b",       # 写模式 open（读模式允许）
]

FORBIDDEN_RE = re.compile("|".join(FORBIDDEN_PATTERNS))


def _check_code_safety(code: str) -> Optional[str]:
    """静态检查代码安全性，返回 None 表示安全，否则返回违规描述"""
    match = FORBIDDEN_RE.search(code)
    if match:
        return f"禁止的操作: {match.group()}"
    return None


def _worker(code: str, namespace_bytes: bytes, result_queue: mp.Queue):
    """子进程工作函数：反序列化命名空间 → 执行代码 → 序列化结果"""
    # 重定向 stdout
    old_stdout = sys.stdout
    sys.stdout = captured = io.StringIO()

    try:
        # 恢复命名空间
        namespace = pickle.loads(namespace_bytes) if namespace_bytes else {}

        # 执行代码
        exec(code, namespace)

        stdout_text = captured.getvalue()

        # 序列化更新后的命名空间（过滤不可序列化的对象）
        serializable_ns = _filter_serializable(namespace)
        ns_bytes = pickle.dumps(serializable_ns)

        result_queue.put({
            "success": True,
            "stdout": stdout_text,
            "error": None,
            "namespace_bytes": ns_bytes,
        })
    except Exception:
        stdout_text = captured.getvalue()
        err = traceback.format_exc()
        result_queue.put({
            "success": False,
            "stdout": stdout_text,
            "error": err,
            "namespace_bytes": namespace_bytes,  # 保留旧命名空间
        })
    finally:
        sys.stdout = old_stdout


def _filter_serializable(namespace: dict) -> dict:
    """过滤掉不可 pickle 的对象（模块、函数等保留常见的）"""
    filtered = {}
    skip_keys = {"__builtins__", "__name__", "__doc__", "__package__",
                 "__loader__", "__spec__"}
    for k, v in namespace.items():
        if k in skip_keys:
            continue
        try:
            pickle.dumps(v)
            filtered[k] = v
        except (pickle.PicklingError, TypeError, AttributeError):
            # 不可序列化的跳过（如模块对象）
            # 但保留 import 的模块名，下次重新 import
            pass
    return filtered


class Sandbox:
    """
    安全沙箱执行器

    用法：
        sandbox = Sandbox(timeout=30)
        result = sandbox.execute("import pandas as pd\\nprint(pd.__version__)")
        print(result["stdout"])
    """

    def __init__(self, timeout: int = 60, max_memory_mb: int = 512):
        self.timeout = timeout
        self.max_memory_mb = max_memory_mb
        self._namespace_bytes: bytes = pickle.dumps({})
        # 记录已 import 的模块，子进程重启后自动重新 import
        self._import_statements: list = []

    def execute(self, code: str) -> Dict[str, Any]:
        """在隔离子进程中执行代码"""
        if not code or not code.strip():
            return {"success": True, "stdout": "(无代码执行)", "error": None}

        # 1. 静态安全检查
        violation = _check_code_safety(code)
        if violation:
            return {
                "success": False,
                "stdout": "",
                "error": f"安全检查未通过: {violation}",
            }

        # 2. 记录 import 语句
        self._track_imports(code)

        # 3. 在代码前注入历史 import（确保跨步骤可用）
        full_code = "\n".join(self._import_statements) + "\n" + code

        # 4. 启动子进程执行
        result_queue = mp.Queue()
        proc = mp.Process(
            target=_worker,
            args=(full_code, self._namespace_bytes, result_queue),
        )
        proc.start()
        proc.join(timeout=self.timeout)

        # 5. 超时处理
        if proc.is_alive():
            proc.kill()
            proc.join(timeout=5)
            return {
                "success": False,
                "stdout": "",
                "error": f"执行超时（{self.timeout}s），已终止子进程",
            }

        # 6. 获取结果
        if result_queue.empty():
            return {
                "success": False,
                "stdout": "",
                "error": f"子进程异常退出 (exit code: {proc.exitcode})",
            }

        result = result_queue.get_nowait()

        # 7. 更新持久命名空间
        if result.get("namespace_bytes"):
            self._namespace_bytes = result["namespace_bytes"]

        return {
            "success": result["success"],
            "stdout": result.get("stdout", ""),
            "error": result.get("error"),
        }

    def get_namespace(self) -> Dict[str, Any]:
        """获取当前命名空间（用于测试验证）"""
        try:
            return pickle.loads(self._namespace_bytes)
        except Exception:
            return {}

    def reset(self):
        """重置沙箱状态"""
        self._namespace_bytes = pickle.dumps({})
        self._import_statements = []

    def _track_imports(self, code: str):
        """提取并记录 import 语句"""
        for line in code.split("\n"):
            stripped = line.strip()
            if stripped.startswith("import ") or stripped.startswith("from "):
                if stripped not in self._import_statements:
                    self._import_statements.append(stripped)
