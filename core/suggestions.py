"""智能建议引擎：基于规则的轻量推荐，不需要 LLM。

设计原则：
- 纯规则，零外部依赖
- 建议由 (kind, text, action, priority) 组成
- action 由 UI 层解释（例如 "plot"、"convert"、"compare"）

建议类型：
    plot      绘图建议
    convert   单位 / 货币换算
    compare   与历史对比
    calc      继续计算
    tip       使用提示
    warn      警告（溢出 / 性能）
    explain   解释（可选的 AI 解释）
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Suggestion:
    kind: str                # plot / convert / compare / calc / tip / warn / explain
    text: str                # 展示给用户的文案
    action: str = ""         # UI 动作标识
    payload: dict = field(default_factory=dict)  # 动作参数
    priority: int = 50       # 0 = 最低，100 = 最高


# ---------------------------------------------------------------------------
# 规则表
# ---------------------------------------------------------------------------

# 三角函数 / 指数函数 → 绘图建议
_TRIG_RE = re.compile(r"\b(sin|cos|tan|exp|log|ln|sqrt)\s*\(", re.I)

# 带货币代码
_CURRENCY_RE = re.compile(r"\b([A-Z]{3})\b")

# 大阶乘
_FACTORIAL_RE = re.compile(r"(\d+)\s*!")

# 大整数（可能溢出）
_BIG_INT_RE = re.compile(r"\b\d{15,}\b")

# 百分比语法
_PERCENT_RE = re.compile(r"^\s*[\d.]+\s*%\s*(off|on|of)\s+[\d.]+\s*$",
                         re.I)

# 数学常数
_CONSTANTS = ("pi", "e", "E", "oo", "I")

# 单位关键词
_UNIT_HINTS = (
    "km", "m", "cm", "mm", "kg", "g", "mg", "lb", "oz",
    "l", "ml", "gal", "c", "f", "k", "s", "ms", "min",
    "h", "day", "week", "year",
)


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def suggest(
        input_text: str,
        *,
        history_exprs: Optional[list] = None,
        last_result: str = "",
        module_key: str = "",
        limit: int = 3,
) -> list:
    """根据输入给建议。

    Args:
        input_text: 当前输入框内容
        history_exprs: 历史表达式列表（可选）
        last_result: 上一次结果
        module_key: 当前面板 key
        limit: 最多返回几条

    Returns:
        list[Suggestion]，按 priority 降序
    """
    text = (input_text or "").strip()
    out: list[Suggestion] = []

    # ---------- 1. 三角函数 → 绘图 ----------
    if _TRIG_RE.search(text):
        out.append(Suggestion(
            kind="plot",
            text="试试绘制它的图像？",
            action="plot",
            payload={"expr": text},
            priority=80,
        ))

    # ---------- 2. 货币换算 ----------
    m = _CURRENCY_RE.search(text)
    if m and m.group(1) not in ("USD",) or text.upper().count("USD"):
        codes = _CURRENCY_RE.findall(text.upper())
        if len(codes) == 1 and codes[0] not in ("USD",):
            out.append(Suggestion(
                kind="convert",
                text=f"换算 {codes[0]} → USD？",
                action="convert",
                payload={"from": codes[0], "to": "USD"},
                priority=70,
            ))
        elif len(codes) == 2 and codes[0] != codes[1]:
            out.append(Suggestion(
                kind="convert",
                text=f"换算 {codes[0]} → {codes[1]}？",
                action="convert",
                payload={"from": codes[0], "to": codes[1]},
                priority=75,
            ))

    # ---------- 3. 大整数警告 ----------
    m = _BIG_INT_RE.search(text)
    if m:
        out.append(Suggestion(
            kind="warn",
            text="数字很大，建议用科学计数法或 Float",
            action="tip",
            priority=60,
        ))

    # ---------- 4. 大阶乘警告 ----------
    m = _FACTORIAL_RE.search(text)
    if m:
        try:
            n = int(m.group(1))
            if n > 20:
                out.append(Suggestion(
                    kind="warn",
                    text=f"{n}! 结果巨大，可能耗时较长",
                    action="tip",
                    priority=65,
                ))
            elif n < 10:
                # 小阶乘：建议更大的
                out.append(Suggestion(
                    kind="calc",
                    text=f"要不要试试 {n + 1}! 或 {n * 2}!？",
                    action="replace",
                    payload={"expr": f"{n * 2}!"},
                    priority=40,
                ))
        except ValueError:
            pass

    # ---------- 5. 百分比语法提示 ----------
    if "%" in text and not _PERCENT_RE.match(text):
        out.append(Suggestion(
            kind="tip",
            text="支持 `20% off 100` / `tip 15% on 200`",
            action="tip",
            priority=35,
        ))

    # ---------- 6. 单位换算 ----------
    for u in _UNIT_HINTS:
        if re.search(rf"\b\d+(\.\d+)?\s*{u}\b", text, re.I):
            out.append(Suggestion(
                kind="convert",
                text="发送到单位面板换算？",
                action="send_unit",
                payload={"text": text},
                priority=55,
            ))
            break

    # ---------- 7. 与历史对比 ----------
    if (history_exprs and text and last_result
            and module_key == "basic"):
        prev = _find_similar(text, history_exprs)
        if prev and prev != text:
            out.append(Suggestion(
                kind="compare",
                text=f"上次你算过 {prev[:30]}",
                action="recall",
                payload={"expr": prev},
                priority=45,
            ))

    # ---------- 8. 一般表达式 → 各种后续动作 ----------
    if text and _is_expr_like(text):
        if module_key in ("basic", "scientific", "pipeline"):
            out.append(Suggestion(
                kind="tip",
                text="可以用管道：`%s | round(3)`" % text[:20],
                action="send_pipeline",
                payload={"text": text},
                priority=30,
            ))

    # ---------- 9. 常量提示 ----------
    if any(c in text for c in _CONSTANTS):
        out.append(Suggestion(
            kind="tip",
            text="常量：pi / e / oo(∞) / I(虚数)",
            action="tip",
            priority=20,
        ))

    # 排序 + 截断
    out.sort(key=lambda s: -s.priority)
    return out[:limit]


# ---------------------------------------------------------------------------
# 辅助
# ---------------------------------------------------------------------------

def _is_expr_like(text: str) -> bool:
    s = str(text).strip()
    if not s:
        return False
    if not re.search(r"\d", s):
        return False
    return bool(re.match(r"^[\d\.\+\-\*/\(\)\^\sA-Za-z_,!]+$", s))


def _find_similar(text: str, history: list) -> str:
    """在历史里找和 text 相似度最高的表达式（简单前缀匹配）。"""
    s = text.lower()
    best = ""
    best_score = 0
    for h in history[:50]:
        hh = str(h).strip().lower()
        if not hh or hh == s:
            continue
        # 计算共同前缀长度
        score = 0
        for a, b in zip(s, hh):
            if a == b:
                score += 1
            else:
                break
        if score > best_score and score >= 3:
            best_score = score
            best = str(h)
    return best


__all__ = ["Suggestion", "suggest"]