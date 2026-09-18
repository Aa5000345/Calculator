"""数据表列运算：聚合、排序、筛选、统计分析。

设计：
- 纯逻辑，不依赖 Qt
- 接受 list[list] 或 list[dict] 形式的数据
- 返回结构化结果，便于 UI 展示
- 支持列引用语法：[A] / [B] / [A,B]

对外接口：
    aggregate(values, op) -> float
    aggregate_all(values) -> dict
    parse_column_ref(s) -> list[str]
    column_values(rows, headers, name) -> list
    sort_rows(rows, headers, col, descending) -> list
    filter_rows(rows, headers, col, op, value) -> list
    analyze_rows(rows, headers) -> dict
    apply_formula_rows(rows, headers, formula) -> list
"""
from __future__ import annotations

import math
import re
from typing import Optional

from core.errors import InputError


# ---------------------------------------------------------------------------
# 聚合操作
# ---------------------------------------------------------------------------

AGG_OPS = {
    "sum": "求和",
    "mean": "平均值",
    "median": "中位数",
    "std": "标准差（总体）",
    "std_s": "标准差（样本）",
    "var": "方差（总体）",
    "var_s": "方差（样本）",
    "min": "最小值",
    "max": "最大值",
    "count": "计数",
    "range": "极差",
    "product": "乘积",
    "q1": "第一四分位",
    "q3": "第三四分位",
    "iqr": "四分位距",
    "mode": "众数",
    "skew": "偏度",
    "kurt": "峰度",
}


def _to_floats(values) -> list:
    """把值列表转为浮点列表，跳过非数字。"""
    out = []
    for v in values:
        if v is None or v == "":
            continue
        try:
            out.append(float(v))
        except (TypeError, ValueError):
            continue
    return out


def aggregate(values, op: str = "sum") -> float:
    """对一组值做聚合。

    Args:
        values: 数字列表
        op: 见 ``AGG_OPS``

    Returns:
        聚合结果
    """
    nums = _to_floats(values)
    if not nums:
        return 0.0
    op = op.lower()
    n = len(nums)

    if op == "sum":
        return float(sum(nums))
    if op == "mean":
        return sum(nums) / n
    if op == "median":
        s = sorted(nums)
        mid = n // 2
        if n % 2 == 0:
            return (s[mid - 1] + s[mid]) / 2
        return s[mid]
    if op == "std":
        m = sum(nums) / n
        return math.sqrt(sum((x - m) ** 2 for x in nums) / n)
    if op == "std_s":
        if n < 2:
            return 0.0
        m = sum(nums) / n
        return math.sqrt(
            sum((x - m) ** 2 for x in nums) / (n - 1))
    if op == "var":
        m = sum(nums) / n
        return sum((x - m) ** 2 for x in nums) / n
    if op == "var_s":
        if n < 2:
            return 0.0
        m = sum(nums) / n
        return sum((x - m) ** 2 for x in nums) / (n - 1)
    if op == "min":
        return float(min(nums))
    if op == "max":
        return float(max(nums))
    if op == "count":
        return float(n)
    if op == "range":
        return float(max(nums) - min(nums))
    if op == "product":
        p = 1.0
        for x in nums:
            p *= x
        return p
    if op in ("q1", "q3"):
        s = sorted(nums)

        def _quantile(q):
            if n == 1:
                return s[0]
            pos = (n - 1) * q
            lo = int(math.floor(pos))
            hi = int(math.ceil(pos))
            if lo == hi:
                return s[lo]
            frac = pos - lo
            return s[lo] * (1 - frac) + s[hi] * frac
        return _quantile(0.25 if op == "q1" else 0.75)
    if op == "iqr":
        return aggregate(nums, "q3") - aggregate(nums, "q1")
    if op == "mode":
        counts: dict = {}
        for x in nums:
            counts[x] = counts.get(x, 0) + 1
        return float(max(counts.items(), key=lambda kv: kv[1])[0])
    if op == "skew":
        if n < 3:
            return 0.0
        m = sum(nums) / n
        sd = math.sqrt(sum((x - m) ** 2 for x in nums) / n)
        if sd == 0:
            return 0.0
        s = sum(((x - m) / sd) ** 3 for x in nums) / n
        return s
    if op == "kurt":
        if n < 4:
            return 0.0
        m = sum(nums) / n
        sd = math.sqrt(sum((x - m) ** 2 for x in nums) / n)
        if sd == 0:
            return 0.0
        k = sum(((x - m) / sd) ** 4 for x in nums) / n - 3.0
        return k

    raise InputError(f"未知聚合操作：{op}")


def aggregate_all(values) -> dict:
    """一次算出所有聚合结果。"""
    out = {}
    for op in AGG_OPS:
        try:
            out[op] = aggregate(values, op)
        except Exception:
            out[op] = None
    return out


# ---------------------------------------------------------------------------
# 列引用解析
# ---------------------------------------------------------------------------

_COL_REF_RE = re.compile(r"\[([^\]]+)\]")


def parse_column_ref(s: str) -> list:
    """解析 ``[A]`` / ``[A,B]`` / ``[A] + [B]`` 里的列引用。"""
    return [m.strip() for m in _COL_REF_RE.findall(str(s))]


def column_values(rows: list, headers: list, name: str) -> list:
    """从表格提取某一列的值。"""
    if name not in headers:
        raise InputError(f"未知列：{name!r}")
    idx = headers.index(name)
    out = []
    for r in rows:
        if idx < len(r):
            out.append(r[idx])
        else:
            out.append("")
    return out


# ---------------------------------------------------------------------------
# 排序 / 筛选
# ---------------------------------------------------------------------------

def sort_rows(rows: list, headers: list, col: str,
              descending: bool = False) -> list:
    """按某列排序。"""
    if col not in headers:
        raise InputError(f"未知列：{col!r}")
    idx = headers.index(col)

    def _key(row):
        v = row[idx] if idx < len(row) else ""
        # 尝试数字
        try:
            return (0, float(v))
        except (TypeError, ValueError):
            return (1, str(v))

    return sorted(rows, key=_key, reverse=descending)


FILTER_OPS = {
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
    ">":  lambda a, b: a > b,
    ">=": lambda a, b: a >= b,
    "<":  lambda a, b: a < b,
    "<=": lambda a, b: a <= b,
    "contains": lambda a, b: str(b) in str(a),
    "startswith": lambda a, b: str(a).startswith(str(b)),
    "endswith": lambda a, b: str(a).endswith(str(b)),
    "is_empty": lambda a, b: str(a).strip() == "",
    "not_empty": lambda a, b: str(a).strip() != "",
}


def filter_rows(rows: list, headers: list, col: str,
                op: str, value="") -> list:
    """按条件筛选。"""
    if col not in headers:
        raise InputError(f"未知列：{col!r}")
    idx = headers.index(col)
    fn = FILTER_OPS.get(op)
    if fn is None:
        raise InputError(f"未知筛选操作：{op!r}")

    out = []
    for r in rows:
        v = r[idx] if idx < len(r) else ""
        # 对 > < >= <= 尝试数字比较
        if op in (">", ">=", "<", "<="):
            try:
                va = float(v)
                vb = float(value)
                if fn(va, vb):
                    out.append(r)
            except (TypeError, ValueError):
                continue
        else:
            if fn(v, value):
                out.append(r)
    return out


# ---------------------------------------------------------------------------
# 分析
# ---------------------------------------------------------------------------

def analyze_rows(rows: list, headers: list) -> dict:
    """对每一列做完整的描述统计。"""
    out = {}
    for h in headers:
        vals = column_values(rows, headers, h)
        nums = _to_floats(vals)
        if nums:
            stats = {
                "type": "numeric",
                "count": len(nums),
                "mean": aggregate(nums, "mean"),
                "median": aggregate(nums, "median"),
                "std": aggregate(nums, "std"),
                "min": aggregate(nums, "min"),
                "max": aggregate(nums, "max"),
                "sum": aggregate(nums, "sum"),
            }
        else:
            stats = {
                "type": "text",
                "count": len(vals),
                "unique": len(set(str(v) for v in vals)),
            }
        out[h] = stats
    return out


# ---------------------------------------------------------------------------
# 公式计算
# ---------------------------------------------------------------------------

_SAFE_FUNCS = {
    "abs": abs, "min": min, "max": max, "round": round,
    "sum": sum, "len": len,
    "sqrt": math.sqrt, "log": math.log, "log10": math.log10,
    "exp": math.exp, "sin": math.sin, "cos": math.cos,
    "tan": math.tan, "pi": math.pi, "e": math.e,
    "mean": lambda *a: sum(a) / max(1, len(a)),
    "std": lambda *a: (
        math.sqrt(sum((x - sum(a) / len(a)) ** 2 for x in a) / len(a))
        if a else 0.0),
}


def apply_formula_rows(rows: list, headers: list,
                       formula: str) -> list:
    """对每一行应用公式。

    支持：
    - ``[A] + [B]``     单元格算术
    - ``sum([A])``      整列聚合（每行结果相同）
    - ``mean([A,B])``   多列聚合
    """
    s = str(formula).strip()
    if s.startswith("="):
        s = s[1:]

    # 检查是否是整列聚合
    agg_match = re.match(
        r"^\s*(sum|mean|std|min|max|median|count)\s*\(\s*"
        r"\[([^\]]+)\]\s*\)\s*$", s, re.I)
    if agg_match:
        op = agg_match.group(1).lower()
        names = [n.strip() for n in agg_match.group(2).split(",")]
        vals = []
        for n in names:
            vals.extend(_to_floats(column_values(rows, headers, n)))
        if op == "sum":
            r = aggregate(vals, "sum")
        elif op == "mean":
            r = aggregate(vals, "mean")
        elif op == "std":
            r = aggregate(vals, "std")
        elif op == "min":
            r = aggregate(vals, "min")
        elif op == "max":
            r = aggregate(vals, "max")
        elif op == "median":
            r = aggregate(vals, "median")
        else:
            r = float(len(vals))
        return [r] * len(rows)

    # 逐行计算
    out = []
    for r in rows:
        expr = s
        for m in _COL_REF_RE.finditer(s):
            name = m.group(1).strip()
            if name not in headers:
                out.append("#ERR")
                break
            idx = headers.index(name)
            v = r[idx] if idx < len(r) else ""
            try:
                fv = float(v)
                expr = expr.replace(m.group(0), repr(fv))
            except (TypeError, ValueError):
                out.append("#ERR")
                break
        else:
            try:
                val = eval(
                    compile(expr, "<formula>", "eval"),
                    {"__builtins__": {}},
                    dict(_SAFE_FUNCS))
                out.append(val)
            except Exception:
                out.append("#ERR")
    return out


# ---------------------------------------------------------------------------
# 与 Stats 面板联动
# ---------------------------------------------------------------------------

def to_stats_text(values) -> str:
    """把值列表转为统计面板能接受的文本。"""
    nums = _to_floats(values)
    return " ".join(f"{x:g}" for x in nums)


__all__ = [
    "AGG_OPS",
    "FILTER_OPS",
    "aggregate",
    "aggregate_all",
    "parse_column_ref",
    "column_values",
    "sort_rows",
    "filter_rows",
    "analyze_rows",
    "apply_formula_rows",
    "to_stats_text",
]