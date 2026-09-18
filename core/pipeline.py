"""工作流管道：把多个计算步骤串起来。

语法：
    <初始表达式> | <步骤1> | <步骤2> | ...

步骤类型（按识别顺序）：
1. 转换：`to <unit>` / `-> <unit>` / `in <unit>`
   - 单位换算：`1 km | to m`
   - 货币换算：`100 USD | to CNY`
2. 格式化：`as <format>`
   - `as fraction` / `as percent` / `as sci` / `as latex`
3. 函数调用：`<name>` 或 `<name>(<args>)`
   - `sqrt` / `abs` / `round(3)` / `log(10)`
4. 算术：`<op> <expr>` 或 `<expr> <op>`
   - `* 2` / `+ 5` / `** 2`
   - 表达式里用 `_` 代表上一步结果

示例：
    "1 km | to m"
    "100 USD | to CNY"
    "1 km | to m | * 2 | round(3)"
    "5 | sqrt | round(2)"
    "0.1 | as fraction"

设计原则：
- core 层不依赖 Qt
- 货币换算通过 rate_provider 回调注入，避免 core 层直接依赖 rates
- 每步产出 StepResult，便于 UI 展示中间过程
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from core.errors import CalcError, InputError, MathError


# ---------------------------------------------------------------------------
# 分隔符与正则
# ---------------------------------------------------------------------------

_PIPE_SPLIT_RE = re.compile(r"\s*[|｜]\s*")

# "to m" / "-> m" / "in m" / "convert to m" / "→ m"
_CONVERT_RE = re.compile(
    r"^(?:to|->|in|into|convert\s+to|→)\s+(.+)$", re.I)

# "as fraction" / "as percent"
_FORMAT_RE = re.compile(
    r"^as\s+([\w\u4e00-\u9fa5]+)(?:\s+(.+))?$", re.I)

# "sqrt" / "round(3)"
_CALL_RE = re.compile(r"^([a-zA-Z_]\w*)\s*(?:\(([^)]*)\))?\s*$")

# "* 2" / "+ 5" / "** 2" / "/ 3"
_ARITH_PREFIX_RE = re.compile(r"^(\*\*|[+\-*/%^])\s*(.+)$")

# "2 *" / "5 +" / "10 /"
_ARITH_SUFFIX_RE = re.compile(r"^(.+?)\s*(\*\*|[+\-*/%^])$")

# 初始表达式里的 "100 USD"
_INIT_CURRENCY_RE = re.compile(
    r"^\s*(-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)\s*([A-Z]{3,5})\s*$")

# 货币代码：3~5 个大写字母
_CURRENCY_RE = re.compile(r"^[A-Z]{3,5}$")


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------

@dataclass
class Step:
    """一个管道步骤。

    kind:
        - ``"init"``    初始表达式
        - ``"convert"`` 单位 / 货币转换
        - ``"format"``  格式化
        - ``"call"``    函数调用
        - ``"arith"``   算术运算
        - ``"empty"``   空步骤（跳过）
        - ``"invalid"`` 无法识别
    """
    kind: str
    raw: str
    payload: Any = None


@dataclass
class StepResult:
    """一步的执行结果。"""
    step: Step
    value: Any = None
    display: str = ""
    error: str = ""

    @property
    def ok(self) -> bool:
        return not self.error


@dataclass
class PipelineResult:
    """整条管道的执行结果。"""
    steps: list = field(default_factory=list)
    final: Any = None
    final_display: str = ""
    error: str = ""

    @property
    def ok(self) -> bool:
        return not self.error


@dataclass
class _CurrencyAmount:
    """管道内部使用：代表一个带货币单位的数量。"""
    amount: float
    code: str


# ---------------------------------------------------------------------------
# 已知函数名
# ---------------------------------------------------------------------------

_KNOWN_FUNCS = {
    "sqrt", "cbrt", "abs", "floor", "ceil", "round",
    "log", "ln", "log10", "exp",
    "sin", "cos", "tan", "asin", "acos", "atan",
    "sinh", "cosh", "tanh",
    "factorial", "gamma", "sign",
}


def _is_known_func(name: str) -> bool:
    return name.lower() in _KNOWN_FUNCS


# ---------------------------------------------------------------------------
# 解析
# ---------------------------------------------------------------------------

def _classify_step(raw: str) -> Step:
    """把一个步骤字符串归类。"""
    s = (raw or "").strip()
    if not s:
        return Step(kind="empty", raw=s)

    # 1) 转换：to X / -> X / in X
    m = _CONVERT_RE.match(s)
    if m:
        return Step(kind="convert", raw=s,
                    payload=m.group(1).strip())

    # 2) 格式化：as X
    m = _FORMAT_RE.match(s)
    if m:
        return Step(kind="format", raw=s,
                    payload=(m.group(1).lower(),
                             (m.group(2) or "").strip()))

    # 3) 算术（前缀）：* 2 / + 5 / ** 2
    m = _ARITH_PREFIX_RE.match(s)
    if m:
        return Step(kind="arith", raw=s,
                    payload=(m.group(1), m.group(2).strip()))

    # 4) 算术（后缀）：2 * / 5 +
    m = _ARITH_SUFFIX_RE.match(s)
    if m:
        return Step(kind="arith", raw=s,
                    payload=(m.group(2), m.group(1).strip()))

    # 5) 函数调用：sqrt / round(3)
    m = _CALL_RE.match(s)
    if m:
        name = m.group(1)
        args = (m.group(2) or "").strip()
        if _is_known_func(name):
            return Step(kind="call", raw=s,
                        payload=(name, args))

    # 6) 兜底：含 `_` 的表达式按算术处理
    if "_" in s:
        return Step(kind="arith", raw=s, payload=("_expr", s))

    raise InputError(f"无法识别的管道步骤：{s!r}")


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def execute_pipeline(
        text: str,
        *,
        angle_mode: str = "RAD",
        rate_provider: Optional[
            Callable[[float, str, str], float]] = None,
) -> PipelineResult:
    """执行管道。

    Args:
        text: 管道文本，例如 ``"1 km | to m | * 2"``
        angle_mode: ``"RAD"`` 或 ``"DEG"``
        rate_provider: 货币换算回调
            ``fn(amount, from_code, to_code) -> float``；
            为 None 时货币换算会失败

    Returns:
        PipelineResult（含每步的中间结果）
    """
    text = (text or "").strip()
    if not text:
        return PipelineResult(error="输入为空")

    parts = _PIPE_SPLIT_RE.split(text)
    if not parts:
        return PipelineResult(error="输入为空")

    init_text = parts[0].strip()
    if not init_text:
        return PipelineResult(error="管道初始表达式为空")

    # 初始表达式
    try:
        init_val, init_display = _eval_init(
            init_text, angle_mode)
    except Exception as e:
        msg = _error_msg(e)
        return PipelineResult(error=f"初始表达式失败：{msg}")

    steps: list[StepResult] = [
        StepResult(
            step=Step(kind="init", raw=init_text),
            value=init_val,
            display=init_display,
        )
    ]

    current = init_val
    for raw in parts[1:]:
        try:
            step = _classify_step(raw)
        except CalcError as e:
            msg = _error_msg(e)
            steps.append(StepResult(
                step=Step(kind="invalid", raw=raw),
                error=msg,
            ))
            return PipelineResult(steps=steps, error=msg)

        if step.kind == "empty":
            continue

        try:
            current, display = _apply_step(
                step, current, angle_mode, rate_provider)
            steps.append(StepResult(
                step=step, value=current, display=display))
        except Exception as e:
            msg = _error_msg(e)
            steps.append(StepResult(step=step, error=msg))
            return PipelineResult(steps=steps, error=msg)

    final_display = steps[-1].display if steps else ""
    return PipelineResult(
        steps=steps,
        final=current,
        final_display=final_display,
    )


# ---------------------------------------------------------------------------
# 步骤执行
# ---------------------------------------------------------------------------

def _apply_step(step: Step, current: Any, angle_mode: str,
                rate_provider) -> tuple:
    """应用一个步骤，返回 ``(新值, 展示字符串)``。"""
    if step.kind == "convert":
        return _do_convert(step.payload, current, rate_provider)
    if step.kind == "format":
        return _do_format(step.payload, current)
    if step.kind == "call":
        return _do_call(step.payload, current, angle_mode)
    if step.kind == "arith":
        return _do_arith(step.payload, current, angle_mode)
    raise InputError(f"未知步骤类型：{step.kind}")


def _eval_init(text: str, angle_mode: str):
    """解析初始表达式，支持 "100 USD" 形式。"""
    m = _INIT_CURRENCY_RE.match(text)
    if m:
        amount = float(m.group(1))
        code = m.group(2).upper()
        cur = _CurrencyAmount(amount, code)
        return cur, f"{amount:g} {code}"

    from core import engine
    val = engine.sci_eval(text, angle_mode)
    return val, _format_value(val)


def _do_convert(target: str, current: Any,
                rate_provider) -> tuple:
    target = target.strip()

    if _CURRENCY_RE.match(target):
        return _do_currency_convert(current, target, rate_provider)

    return _do_unit_convert(current, target)


def _do_currency_convert(current: Any, target: str,
                         rate_provider) -> tuple:
    if not isinstance(current, _CurrencyAmount):
        raise InputError(
            f"无法把 {_format_value(current)} 转换为货币 {target}")

    if rate_provider is None:
        raise InputError("缺少汇率服务，无法换算货币")

    try:
        new_amount = rate_provider(
            current.amount, current.code, target)
    except Exception as e:
        raise InputError(f"货币换算失败：{e}")

    result = _CurrencyAmount(new_amount, target)
    return result, f"{new_amount:g} {target}"


def _do_unit_convert(current: Any, target: str) -> tuple:
    from pint import Quantity

    if isinstance(current, Quantity):
        try:
            new = current.to(target)
        except Exception as e:
            raise InputError(f"单位换算失败：{e}")
        return new, _format_value(new)

    raise InputError(
        f"无法把 {_format_value(current)} 转换为 {target}"
        f"（缺少源单位）")


def _do_format(payload, current) -> tuple:
    fmt, _extra = payload
    from core import engine

    aliases = {
        "fraction": "fraction", "frac": "fraction", "分数": "fraction",
        "percent": "percent", "pct": "percent", "百分比": "percent",
        "sci": "sci", "scientific": "sci", "科学": "sci",
        "text": "text", "plain": "text", "普通": "text",
        "latex": "latex",
    }
    kind = aliases.get(fmt)
    if kind is None:
        raise InputError(f"未知格式：{fmt!r}")

    try:
        if kind == "fraction":
            display = engine.format_result(
                current, "text", fraction=True)
        elif kind == "percent":
            display = engine.format_result(
                current, "text", percent=True)
        elif kind == "sci":
            display = engine.format_result(
                current, "text", sci=True)
        elif kind == "latex":
            display = engine.format_result(current, "latex")
        else:
            display = engine.format_result(current, "text")
    except Exception as e:
        raise InputError(f"格式化失败：{e}")

    return current, display


def _do_call(payload, current, angle_mode) -> tuple:
    name, args = payload
    from core import engine

    cur_str = _value_to_expr(current)
    if args:
        expr = f"{name}({cur_str}, {args})"
    else:
        expr = f"{name}({cur_str})"

    try:
        val = engine.sci_eval(expr, angle_mode)
    except Exception as e:
        raise MathError(f"{name} 调用失败：{_error_msg(e)}")

    return val, _format_value(val)


def _do_arith(payload, current, angle_mode) -> tuple:
    op, expr = payload
    from core import engine

    cur_str = _value_to_expr(current)

    if op == "_expr":
        # 表达式里已含 `_`，直接替换
        full = expr.replace("_", f"({cur_str})")
    else:
        full = f"({cur_str}) {op} ({expr})"

    try:
        val = engine.sci_eval(full, angle_mode)
    except Exception as e:
        raise MathError(f"算术运算失败：{_error_msg(e)}")

    return val, _format_value(val)


# ---------------------------------------------------------------------------
# 辅助
# ---------------------------------------------------------------------------

def _format_value(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, _CurrencyAmount):
        return f"{v.amount:g} {v.code}"
    try:
        from core import engine
        return engine.format_result(v, "text")
    except Exception:
        return str(v)


def _value_to_expr(v: Any) -> str:
    """把值转为可嵌入表达式的字符串。"""
    if isinstance(v, _CurrencyAmount):
        raise InputError(
            f"货币 {v.code} 不能参与算术；"
            f"请先 `to <单位>` 或 `to <货币>`")

    try:
        from pint import Quantity
        if isinstance(v, Quantity):
            # pint 支持 "1.5 * kilometer" 形式
            return f"({v.magnitude}) * {v.units}"
    except Exception:
        pass

    return str(v)


def _error_msg(e: Exception) -> str:
    try:
        from core.errors import CalcError
        if isinstance(e, CalcError):
            return e.message or str(e)
    except Exception:
        pass
    return str(e)


# ---------------------------------------------------------------------------
# 便捷接口
# ---------------------------------------------------------------------------

def split_steps(text: str) -> list:
    """只分割不执行，用于 UI 预览。"""
    parts = _PIPE_SPLIT_RE.split((text or "").strip())
    return [p.strip() for p in parts if p.strip()]


def has_pipe(text: str) -> bool:
    """判断文本是否包含管道分隔符。"""
    return bool(_PIPE_SPLIT_RE.search(text or ""))


__all__ = [
    "Step",
    "StepResult",
    "PipelineResult",
    "execute_pipeline",
    "split_steps",
    "has_pipe",
]