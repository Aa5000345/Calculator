"""导出历史条目为 Jupyter Notebook (.ipynb, nbformat v4)。

不依赖 nbformat 包；直接拼装标准 JSON。
"""
from __future__ import annotations

import datetime
import json


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


def _md_cell(text: str) -> dict:
    src = str(text).splitlines(keepends=True)
    if not src or not src[-1].endswith("\n"):
        src.append("\n")
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": src,
    }


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


def build_notebook(items, title: str = "MultiCalc Session") -> dict:
    """items: [{"module","expr","result","latex"(opt),"time"(opt)}]。

    每一条生成两个 cell：
    1) Markdown cell —— 元信息（模块 / 时间）
    2) Code cell —— `expr` + 打印结果
    """
    cells = []
    cells.append(_md_cell(f"# {title}\n\n"
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

        # 代码 cell：原式 + 注释结果
        safe_expr = expr
        lines = [f"# {safe_expr}"]
        if result:
            lines.append(f"# = {result}")
        # 使用多行注释保留原样，避免破坏 IPython 语义
        code = "\n".join(lines)
        cells.append(_code_cell(code))

    nb = {
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
    return nb


def export_to_ipynb(items, path: str, title: str = "MultiCalc Session"):
    """把 items 写到 path（.ipynb）。"""
    nb = build_notebook(items, title=title)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(nb, f, ensure_ascii=False, indent=1)
    return path