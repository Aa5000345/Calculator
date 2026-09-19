"""结果差异对比：给相邻两次结果加差异徽章。

用途：
- 基础面板算出 5 后，再算 8 → 显示 "+3"
- 百分比变化："+60%"
- 单位相同的 Quantity → 单位一致时对比数值
- 表达式的相似度提示："上次你算过 sin(x)"

对外接口：
    DiffResult, compare, describe, find_similar_in_history
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

__all__ = [
    "DiffResult",
    "compare",
    "describe",
    "find_similar_in_history",
]


# ===========================================================================
# 数据结构
# ===========================================================================

@dataclass
class DiffResult:
    kind: str = "none"          # none / numeric / text / ratio
    delta: float | None = None
    ratio: float | None = None
    percent: float | None = None
    direction: str = ""         # "+" / "-" / "="
    prev_repr: str = ""
    curr_repr: str = ""
    detail: str = ""

    @property
    def has_diff(self) -> bool:
        return self.kind != "none"


# ===========================================================================
# 数值提取
# ===========================================================================

_NUM_RE = re.compile(
    r"^\s*(-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)\s*(.*)$"
)


def _extract_number(s: Any) -> tuple:
    """从字符串提取 (数值, 单位后缀)。

    返回 (float, suffix) 或 (None, "")。
    """
    text = str(s or "").strip()
    m = _NUM_RE.match(text)
    if not m:
        return None, ""

    try:
        v = float(m.group(1))
    except ValueError:
        return None, ""

    suffix = m.group(2).strip()
    return v, suffix


# ===========================================================================
# 主接口
# ===========================================================================

def compare(prev: Any, curr: Any,
            tolerance: float = 1e-12) -> DiffResult:
    """比较两个结果。

    Args:
        prev: 上一次结果（str / number / None）
        curr: 当前结果（str / number / None）
        tolerance: 视为相等的相对容差

    Returns:
        DiffResult
    """
    out = DiffResult(
        prev_repr=_short(prev),
        curr_repr=_short(curr),
    )

    if prev is None or curr is None:
        return out
    if str(prev) == "" or str(curr) == "":
        return out
    if str(prev) == str(curr):
        out.kind = "numeric"
        out.delta = 0.0
        out.ratio = 1.0
        out.percent = 0.0
        out.direction = "="
        return out

    prev_num, prev_unit = _extract_number(prev)
    curr_num, curr_unit = _extract_number(curr)

    if prev_num is not None and curr_num is not None:
        if prev_unit and curr_unit and prev_unit != curr_unit:
            out.kind = "text"
            out.detail = f"单位不同：{prev_unit} → {curr_unit}"
            return out
        if not prev_unit and curr_unit:
            out.kind = "text"
            out.detail = f"新增单位：{curr_unit}"
            return out
        if prev_unit and not curr_unit:
            out.kind = "text"
            out.detail = f"去掉单位：{prev_unit}"
            return out

        delta = curr_num - prev_num
        out.kind = "numeric"
        out.delta = delta

        if abs(prev_num) > tolerance:
            out.ratio = curr_num / prev_num
            out.percent = (out.ratio - 1.0) * 100.0
        else:
            out.ratio = None
            out.percent = None

        if abs(delta) < tolerance * max(1.0, abs(prev_num)):
            out.direction = "="
        elif delta > 0:
            out.direction = "+"
        else:
            out.direction = "-"
        return out

    out.kind = "text"
    if prev_unit and curr_unit and prev_unit != curr_unit:
        out.detail = f"单位不同：{prev_unit} → {curr_unit}"
    return out


def _short(x: Any, n: int = 24) -> str:
    s = str(x or "")
    if len(s) <= n:
        return s
    return s[:n - 1] + "…"


# ===========================================================================
# 描述
# ===========================================================================

def _t(key: str, default: str, i18n=None) -> str:
    """内部辅助：优先使用 i18n 翻译。"""
    if i18n is None:
        return default
    try:
        v = i18n.t(key, None)
        if v and v != key:
            return v
    except Exception:
        pass
    return default


def describe(diff: DiffResult, i18n=None) -> str:
    """把 DiffResult 渲染为一行文本。

    例：
        "+3"          （整数差）
        "+3.5 (+70%)" （含百分比）
        "-0.02 (-4.0%)"
        "= 相同"
    """
    if not diff.has_diff:
        return ""

    if diff.kind == "text":
        return diff.detail or ""

    d = diff.delta
    if d is None:
        return ""

    if d == 0:
        delta_text = _t("diff_same", "相同", i18n)
    else:
        sign = "+" if d > 0 else "-"
        absd = abs(d)
        if absd == int(absd) and absd < 1e15:
            delta_text = f"{sign}{int(absd)}"
        elif absd >= 1e6 or absd < 1e-3:
            delta_text = f"{sign}{absd:.3g}"
        else:
            delta_text = f"{sign}{absd:g}"

    if diff.percent is not None and abs(diff.percent) >= 0.01:
        pct = diff.percent
        sign_p = "+" if pct > 0 else "-"
        pct_text = f" ({sign_p}{abs(pct):.2f}%)"
    else:
        pct_text = ""

    return f"{delta_text}{pct_text}"


# ===========================================================================
# 与历史对比
# ===========================================================================

def find_similar_in_history(curr: str,
                            history_exprs: list,
                            threshold: float = 0.6) -> str | None:
    """在历史里找与 curr 相似度最高的表达式。

    简单 token 重叠度算法。
    """
    if not curr or not history_exprs:
        return None

    def _tokens(s: str) -> set:
        return set(re.findall(r"[A-Za-z]+|\d+|\S", str(s)))

    curr_tokens = _tokens(curr)
    if not curr_tokens:
        return None

    best = None
    best_score = threshold
    for h in history_exprs[:50]:
        h = str(h).strip()
        if not h or h == curr:
            continue
        h_tokens = _tokens(h)
        if not h_tokens:
            continue
        inter = curr_tokens & h_tokens
        union = curr_tokens | h_tokens
        score = len(inter) / max(1, len(union))
        if score > best_score:
            best_score = score
            best = h
    return best