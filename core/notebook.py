"""笔记本 + 导出 + 管道。

合并自：core/notebook.py + core/notebook_export.py + core/pipeline.py

对外接口：
    # 笔记本
    NotebookCell, Notebook
    # 导出
    build_notebook, export_to_ipynb
    # 管道
    Step, StepResult, PipelineResult,
    execute_pipeline, split_steps, has_pipe
"""
from __future__ import annotations

import datetime
import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from core.base import CalcError, InputError, MathError

__all__ = [
    "NotebookCell", "Notebook",
    "build_notebook", "export_to_ipynb",
    "Step", "StepResult", "PipelineResult",
    "execute_pipeline", "split_steps", "has_pipe",
    "MCNB_FORMAT", "MCNB_VERSION",
]


# ===========================================================================
# 笔记本
# ===========================================================================

MCNB_FORMAT = "mcnb"
MCNB_VERSION = 1


@dataclass
class NotebookCell:
    kind: str = "code"           # "code" | "markdown"
    source: str = ""
    result: str = ""
    error: str = ""
    exec_count: int = 0

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "source": self.source,
            "result": self.result,
            "error": self.error,
            "exec_count": self.exec_count,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "NotebookCell":
        if not isinstance(d, dict):
            return cls()
        kind = str(d.get("kind") or "code")
        if kind not in ("code", "markdown"):
            kind = "code"
        return cls(
            kind=kind,
            source=str(d.get("source") or ""),
            result=str(d.get("result") or ""),
            error=str(d.get("error") or ""),
            exec_count=int(d.get("exec_count") or 0),
        )


@dataclass
class Notebook:
    cells: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    path: Optional[str] = None
    created: str = ""
    modified: str = ""

    def __post_init__(self):
        now = datetime.datetime.now().isoformat(timespec="seconds")
        if not self.created:
            self.created = now
        if not self.modified:
            self.modified = now
        if not self.cells:
            self.cells = [NotebookCell(kind="code", source="")]

    # ---------------- 单元格操作 ----------------

    def add_cell(self, kind: str = "code",
                 source: str = "", index: Optional[int] = None) -> int:
        cell = NotebookCell(kind=kind, source=source)
        if index is None or index < 0 or index > len(self.cells):
            self.cells.append(cell)
            return len(self.cells) - 1
        self.cells.insert(index, cell)
        return index

    def remove_cell(self, index: int) -> bool:
        if 0 <= index < len(self.cells):
            self.cells.pop(index)
            return True
        return False

    def move_cell(self, from_idx: int, to_idx: int) -> bool:
        if not (0 <= from_idx < len(self.cells)):
            return False
        if not (0 <= to_idx < len(self.cells)):
            return False
        if from_idx == to_idx:
            return True
        cell = self.cells.pop(from_idx)
        self.cells.insert(to_idx, cell)
        return True

    def clear_outputs(self):
        for c in self.cells:
            c.result = ""
            c.error = ""
            c.exec_count = 0

    # ---------------- 序列化 ----------------

    def to_dict(self) -> dict:
        self.modified = datetime.datetime.now().isoformat(
            timespec="seconds")
        return {
            "format": MCNB_FORMAT,
            "version": MCNB_VERSION,
            "app": "MultiCalc",
            "created": self.created,
            "modified": self.modified,
            "metadata": dict(self.metadata),
            "cells": [c.to_dict() for c in self.cells],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Notebook":
        if not isinstance(d, dict):
            return cls()
        cells = [NotebookCell.from_dict(x)
                 for x in (d.get("cells") or [])]
        return cls(
            cells=cells or [NotebookCell(kind="code", source="")],
            metadata=dict(d.get("metadata") or {}),
            created=str(d.get("created") or ""),
            modified=str(d.get("modified") or ""),
        )

    # ---------------- 文件 IO ----------------

    def save(self, path: str) -> str:
        """保存为 .mcnb（JSON）。"""
        data = self.to_dict()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        self.path = path
        return path

    @classmethod
    def load(cls, path: str) -> "Notebook":
        """从 .mcnb 或 .ipynb 加载。"""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if (isinstance(data, dict)
                and data.get("format") == MCNB_FORMAT):
            nb = cls.from_dict(data)
            nb.path = path
            return nb

        if (isinstance(data, dict)
                and "nbformat" in data
                and "cells" in data):
            nb = _from_ipynb(data)
            nb.path = path
            return nb

        if isinstance(data, list):
            nb = cls.from_dict({"cells": data})
            nb.path = path
            return nb

        raise ValueError("无法识别的 notebook 格式")

    # ---------------- 导出 ----------------

    def export_ipynb(self, path: str,
                     title: str = "MultiCalc Notebook") -> str:
        """导出为 Jupyter Notebook (.ipynb)。"""
        cells = []
        if title:
            cells.append(_md_cell(f"# {title}\n"))

        for c in self.cells:
            if c.kind == "markdown":
                cells.append(_md_cell(c.source))
            else:
                code = c.source
                if c.result:
                    code = code.rstrip() + f"\n# => {c.result}"
                cells.append(_code_cell(code))

        nb = {
            "cells": cells,
            "metadata": {
                "kernelspec": {
                    "display_name": "Python 3",
                    "language": "python",
                    "name": "python3",
                },
                "language_info": {
                    "name": "python",
                    "version": "3",
                    "mimetype": "text/x-python",
                    "file_extension": ".py",
                    "pygments_lexer": "ipython3",
                    "codemirror_mode": {
                        "name": "ipython", "version": 3},
                },
                "multicalc": {
                    "generated_at":
                        datetime.datetime.now().isoformat(),
                    "source": "Notebook.export_ipynb",
                },
            },
            "nbformat": 4,
            "nbformat_minor": 5,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(nb, f, ensure_ascii=False, indent=1)
        return path


# ===========================================================================
# ipynb 解析
# ===========================================================================

def _cell_source_to_str(src) -> str:
    if isinstance(src, list):
        return "".join(str(x) for x in src)
    return str(src or "")


def _from_ipynb(data: dict) -> Notebook:
    cells = []
    for c in data.get("cells") or []:
        if not isinstance(c, dict):
            continue
        kind = c.get("cell_type") or "code"
        src = _cell_source_to_str(c.get("source"))
        if kind == "markdown":
            cells.append(NotebookCell(kind="markdown", source=src))
            continue
        if kind == "code":
            result = ""
            clean_lines = []
            for line in src.splitlines():
                if line.strip().startswith("# =>"):
                    result = line.split("# =>", 1)[1].strip()
                else:
                    clean_lines.append(line)
            cells.append(NotebookCell(
                kind="code",
                source="\n".join(clean_lines).rstrip(),
                result=result,
            ))
    return Notebook(cells=cells or [NotebookCell(kind="code")])


def _md_cell(text: str) -> dict:
    src = str(text).splitlines(keepends=True)
    if not src or not src[-1].endswith("\n"):
        src.append("\n")
    return {"cell_type": "markdown", "metadata": {}, "source": src}


def _code_cell(text: str) -> dict:
    src = str(text).splitlines(keepends=True)
    if not src or not src[-1].endswith("\n"):
        src.append("\n")
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": src,
    }


# ===========================================================================
# 历史 → ipynb 导出（notebook_export.py）
# ===========================================================================

def _empty_kernel_meta() -> dict:
    return {
        "display_name": "Python 3",
        "language": "python",
        "name": "python3",
    }


def _empty_language_info() -> dict:
    return {
        "name": "python",
        "version": "3",
        "mimetype": "text/x-python",
        "file_extension": ".py",
        "pygments_lexer": "ipython3",
        "codemirror_mode": {"name": "ipython", "version": 3},
        "nbconvert_exporter": "python",
    }


def build_notebook(items, title: str = "MultiCalc Session") -> dict:
    """items: [{"module","expr","result","latex"(opt),"time"(opt)}]。

    每一条生成两个 cell：Markdown（元信息）+ Code（表达式 + 注释结果）。
    """
    cells = []
    cells.append(_md_cell(
        f"# {title}\n\n"
        f"导出时间："
        f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"))

    for i, it in enumerate(items, 1):
        mod = (it.get("module") or "").strip()
        expr = (it.get("expr") or "").strip()
        result = (it.get("result") or "").strip()
        tm = (it.get("time") or "").strip()
        latex = (it.get("latex") or "").strip()
        if not expr:
            continue

        header_parts = [f"### {i}. {mod or 'calc'}"]
        if tm:
            header_parts.append(f"*{tm}*")
        if latex:
            header_parts.append(f"$$ {latex} $$")
        cells.append(_md_cell("\n\n".join(header_parts)))

        lines = [f"# {expr}"]
        if result:
            lines.append(f"# = {result}")
        code = "\n".join(lines)
        cells.append(_code_cell(code))

    return {
        "cells": cells,
        "metadata": {
            "kernelspec": _empty_kernel_meta(),
            "language_info": _empty_language_info(),
            "multicalc": {
                "generated_at": datetime.datetime.now().isoformat(),
                "count": len(cells),
            },
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def export_to_ipynb(items, path: str,
                    title: str = "MultiCalc Session") -> str:
    """把 items 写到 path（.ipynb）。"""
    nb = build_notebook(items, title=title)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(nb, f, ensure_ascii=False, indent=1)
    return path


# ===========================================================================
# 管道
# ===========================================================================

_PIPE_SPLIT_RE = re.compile(r"\s*[|｜]\s*")

_CONVERT_RE = re.compile(
    r"^(?:to|->|in|into|convert\s+to|→)\s+(.+)$", re.I)

_FORMAT_RE = re.compile(
    r"^as\s+([\w\u4e00-\u9fa5]+)(?:\s+(.+))?$", re.I)

_CALL_RE = re.compile(r"^([a-zA-Z_]\w*)\s*(?:\(([^)]*)\))?\s*$")

_ARITH_PREFIX_RE = re.compile(r"^(\*\*|[+\-*/%^])\s*(.+)$")

_ARITH_SUFFIX_RE = re.compile(r"^(.+?)\s*(\*\*|[+\-*/%^])$")

_INIT_CURRENCY_RE = re.compile(
    r"^\s*(-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)\s*([A-Z]{3,5})\s*$")

_CURRENCY_RE = re.compile(r"^[A-Z]{3,5}$")

_KNOWN_FUNCS = {
    "sqrt", "cbrt", "abs", "floor", "ceil", "round",
    "log", "ln", "log10", "exp",
    "sin", "cos", "tan", "asin", "acos", "atan",
    "sinh", "cosh", "tanh",
    "factorial", "gamma", "sign",
}


@dataclass
class Step:
    kind: str
    raw: str
    payload: Any = None


@dataclass
class StepResult:
    step: Step
    value: Any = None
    display: str = ""
    error: str = ""

    @property
    def ok(self) -> bool:
        return not self.error


@dataclass
class PipelineResult:
    steps: list = field(default_factory=list)
    final: Any = None
    final_display: str = ""
    error: str = ""

    @property
    def ok(self) -> bool:
        return not self.error


@dataclass
class _CurrencyAmount:
    amount: float
    code: str


def _is_known_func(name: str) -> bool:
    return name.lower() in _KNOWN_FUNCS


def _classify_step(raw: str) -> Step:
    s = (raw or "").strip()
    if not s:
        return Step(kind="empty", raw=s)

    m = _CONVERT_RE.match(s)
    if m:
        return Step(kind="convert", raw=s,
                    payload=m.group(1).strip())

    m = _FORMAT_RE.match(s)
    if m:
        return Step(kind="format", raw=s,
                    payload=(m.group(1).lower(),
                             (m.group(2) or "").strip()))

    m = _ARITH_PREFIX_RE.match(s)
    if m:
        return Step(kind="arith", raw=s,
                    payload=(m.group(1), m.group(2).strip()))

    m = _ARITH_SUFFIX_RE.match(s)
    if m:
        return Step(kind="arith", raw=s,
                    payload=(m.group(2), m.group(1).strip()))

    m = _CALL_RE.match(s)
    if m:
        name = m.group(1)
        args = (m.group(2) or "").strip()
        if _is_known_func(name):
            return Step(kind="call", raw=s, payload=(name, args))

    if "_" in s:
        return Step(kind="arith", raw=s, payload=("_expr", s))

    raise InputError(f"无法识别的管道步骤：{s!r}")


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
            ``fn(amount, from_code, to_code) -> float``
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

    try:
        init_val, init_display = _eval_init(
            init_text, angle_mode)
    except Exception as e:
        return PipelineResult(
            error=f"初始表达式失败：{_error_msg(e)}")

    steps: list = [StepResult(
        step=Step(kind="init", raw=init_text),
        value=init_val, display=init_display)]

    current = init_val
    for raw in parts[1:]:
        try:
            step = _classify_step(raw)
        except CalcError as e:
            msg = _error_msg(e)
            steps.append(StepResult(
                step=Step(kind="invalid", raw=raw), error=msg))
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
        steps=steps, final=current, final_display=final_display)


def _apply_step(step: Step, current: Any, angle_mode: str,
                rate_provider) -> tuple:
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
    m = _INIT_CURRENCY_RE.match(text)
    if m:
        amount = float(m.group(1))
        code = m.group(2).upper()
        return (_CurrencyAmount(amount, code),
                f"{amount:g} {code}")

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
        "fraction": "fraction", "frac": "fraction",
        "分数": "fraction",
        "percent": "percent", "pct": "percent",
        "百分比": "percent",
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
        full = expr.replace("_", f"({cur_str})")
    else:
        full = f"({cur_str}) {op} ({expr})"

    try:
        val = engine.sci_eval(full, angle_mode)
    except Exception as e:
        raise MathError(f"算术运算失败：{_error_msg(e)}")

    return val, _format_value(val)


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
    if isinstance(v, _CurrencyAmount):
        raise InputError(
            f"货币 {v.code} 不能参与算术；"
            f"请先 `to <单位>` 或 `to <货币>`")

    try:
        from pint import Quantity
        if isinstance(v, Quantity):
            return f"({v.magnitude}) * {v.units}"
    except Exception:
        pass

    return str(v)


def _error_msg(e: Exception) -> str:
    try:
        if isinstance(e, CalcError):
            return e.message or str(e)
    except Exception:
        pass
    return str(e)


def split_steps(text: str) -> list:
    """只分割不执行，用于 UI 预览。"""
    parts = _PIPE_SPLIT_RE.split((text or "").strip())
    return [p.strip() for p in parts if p.strip()]


def has_pipe(text: str) -> bool:
    return bool(_PIPE_SPLIT_RE.search(text or ""))