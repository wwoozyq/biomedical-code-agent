"""
AST 调用链指纹提取

从 Python 代码中提取 API 调用序列（忽略变量名、参数值），
用于结构化代码相似度匹配。

示例:
    代码: df = pd.read_csv("x.csv"); df.groupby("a").mean()
    指纹: ["pd.read_csv", "DataFrame.groupby", "GroupBy.mean"]
"""

import ast
from typing import List, Tuple


# 常见 pandas/scipy/lifelines 方法 → 归一化名称
# 让不同写法映射到同一个调用（如 pivot_table 和 groupby+agg 不做合并，保留区分度）
_NORMALIZE_MAP = {
    "read_csv": "pd.read_csv",
    "read_excel": "pd.read_csv",       # 等价归一化
    "read_table": "pd.read_csv",
    "read_json": "pd.read_json",
    "to_csv": "DataFrame.to_csv",
    "to_numeric": "pd.to_numeric",
    "merge": "pd.merge",
    "concat": "pd.concat",
    "value_counts": "Series.value_counts",
    "groupby": "DataFrame.groupby",
    "pivot_table": "DataFrame.pivot_table",
    "agg": "GroupBy.agg",
    "mean": "Aggregation.mean",
    "median": "Aggregation.median",
    "sum": "Aggregation.sum",
    "describe": "DataFrame.describe",
    "corr": "DataFrame.corr",
    "dropna": "DataFrame.dropna",
    "fillna": "DataFrame.fillna",
    "apply": "DataFrame.apply",
    "sort_values": "DataFrame.sort_values",
    "head": "DataFrame.head",
    "tail": "DataFrame.tail",
    "reset_index": "DataFrame.reset_index",
    "set_index": "DataFrame.set_index",
    "rename": "DataFrame.rename",
    "astype": "Series.astype",
    "map": "Series.map",
    "replace": "Series.replace",
    "unique": "Series.unique",
    "nunique": "Series.nunique",
    "isin": "Series.isin",
    "str": "Series.str",
    "dt": "Series.dt",
    # 可视化
    "plot": "DataFrame.plot",
    "savefig": "plt.savefig",
    "figure": "plt.figure",
    "subplot": "plt.subplot",
    "bar": "plt.bar",
    "hist": "plt.hist",
    "scatter": "plt.scatter",
    "boxplot": "DataFrame.boxplot",
    # 统计
    "ttest_ind": "scipy.ttest_ind",
    "chi2_contingency": "scipy.chi2_contingency",
    "mannwhitneyu": "scipy.mannwhitneyu",
    "pearsonr": "scipy.pearsonr",
    "spearmanr": "scipy.spearmanr",
    "fisher_exact": "scipy.fisher_exact",
    "kruskal": "scipy.kruskal",
    # 生存分析
    "KaplanMeierFitter": "lifelines.KaplanMeierFitter",
    "CoxPHFitter": "lifelines.CoxPHFitter",
    "fit": "Model.fit",
    "predict": "Model.predict",
    "score": "Model.score",
    # sklearn
    "train_test_split": "sklearn.train_test_split",
    "cross_val_score": "sklearn.cross_val_score",
    "LogisticRegression": "sklearn.LogisticRegression",
    "RandomForestClassifier": "sklearn.RandomForestClassifier",
}


class CallChainExtractor(ast.NodeVisitor):
    """遍历 AST，按代码执行顺序提取方法调用（内层调用先于外层）"""

    def __init__(self):
        self.calls: List[str] = []

    def visit_Call(self, node: ast.Call):
        # 先递归处理内层调用（参数和 func 链）
        self.generic_visit(node)
        # 再记录当前调用（保证执行顺序：内层先）
        name = self._resolve_call_name(node.func)
        if name:
            normalized = _NORMALIZE_MAP.get(name, name)
            self.calls.append(normalized)

    def _resolve_call_name(self, node) -> str:
        """从 AST 节点提取函数/方法名"""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return node.attr
        return ""


def extract_call_chain(code: str) -> List[str]:
    """
    从 Python 代码中提取调用链指纹。

    Args:
        code: Python 源代码字符串

    Returns:
        归一化后的 API 调用序列，如 ["pd.read_csv", "DataFrame.groupby", "GroupBy.agg"]
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []

    extractor = CallChainExtractor()
    extractor.visit(tree)
    return extractor.calls


def call_chain_lcs(chain_a: List[str], chain_b: List[str]) -> int:
    """
    计算两个调用链的最长公共子序列（LCS）长度。
    经典 DP，O(m*n) 时间。
    """
    m, n = len(chain_a), len(chain_b)
    if m == 0 or n == 0:
        return 0
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if chain_a[i - 1] == chain_b[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
    return dp[m][n]


def call_chain_similarity(chain_a: List[str], chain_b: List[str]) -> float:
    """
    基于 LCS 的调用链相似度，归一化到 [0, 1]。
    similarity = 2 * LCS / (len_a + len_b)
    """
    if not chain_a and not chain_b:
        return 0.0
    lcs_len = call_chain_lcs(chain_a, chain_b)
    total = len(chain_a) + len(chain_b)
    return 2.0 * lcs_len / total if total > 0 else 0.0
