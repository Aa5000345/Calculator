"""数学笔记本数据模型：cells 列表 + 持久化 + 导出。

设计原则：
- core 层不依赖 Qt，也不依赖具体 engine 接口
- 执行逻辑由调用方（UI）通过 run_cell 回调注入
- .mcnb 是自有格式（JSON），.ipynb 导出兼容 Jupyter

数据结构：
    Notebook:
        cells: list[NotebookCell]
        metadata: dict

    NotebookCell:
        kind: "code" | "markdown"
        source: str
        result: str         # 上次执行结果（展示用）
        error: str          # 上次执行错误
        exec_count: int     # 执行计数

文件格式（.mcnb）：
    {
      "format": "mcnb",
      "version": 1,
      "app": "MultiCalc",
      "created": "2025-01-01T12:00:00",
      "modified": "...",
      "metadata": {...},
      "cells": [
        {"kind": "code", "source": "1+1", "result": "2", ...},
        {"kind": "markdown", "source": "# 标题", ...}
      ]
    }
"""
from __future__ import annotations

import datetime
import json
import os
from dataclasses import dataclass, field
from typing import Optional


MCNB_FORMAT = "mcnb"
MCNB_VERSION = 1


# ---------------------------------------------------------------------------
# 单元格
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# 笔记本
# ---------------------------------------------------------------------------

@dataclass
class Notebook:
    cells: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    path: Optional[str] = None
    created: str = ""
    modified: str = ""

    # ---------------- 构造 ----------------

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
        """插入新单元格，返回索引。"""
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
        nb = cls(
            cells=cells or [NotebookCell(kind="code", source="")],
            metadata=dict(d.get("metadata") or {}),
            created=str(d.get("created") or ""),
            modified=str(d.get("modified") or ""),
        )
        return nb

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

        # 判断是 .mcnb 还是 .ipynb
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

        # 未知格式：尝试当作纯 cells 数组
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
        # 开头加一个 markdown 标题
        if title:
            cells.append(_md_cell(f"# {title}\n"))

        for c in self.cells:
            if c.kind == "markdown":
                cells.append(_md_cell(c.source))
            else:
                code = c.source
                # 若上次执行有结果，作为注释保留
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
                    "generated_at": datetime.datetime.now().isoformat(),
                    "source": "Notebook.export_ipynb",
                },
            },
            "nbformat": 4,
            "nbformat_minor": 5,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(nb, f, ensure_ascii=False, indent=1)
        return path


# ---------------------------------------------------------------------------
# ipynb 解析
# ---------------------------------------------------------------------------

def _cell_source_to_str(src) -> str:
    """Jupyter 的 source 可能是 str 或 list[str]。"""
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
            cells.append(NotebookCell(
                kind="markdown", source=src))
            continue
        if kind == "code":
            # 提取 `# =>` 作为上次结果
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


__all__ = [
    "NotebookCell",
    "Notebook",
    "MCNB_FORMAT",
    "MCNB_VERSION",
]