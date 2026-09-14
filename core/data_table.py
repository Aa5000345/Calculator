"""数据表核心：列管理、公式列、导入/导出。

公式列语法：``=[列名] + [另一列]``，支持 sqrt/log/exp/sin/cos/abs 等。
"""
from __future__ import annotations

import ast
import csv
import io
import json
import math
import re

from core.errors import InputError


class DataTable:
    """轻量数据表。存储为 list[list[str]]；公式保存在 columns 上。"""

    def __init__(self):
        self.columns: list[str] = []
        self.rows: list[list[str]] = []
        self.formulas: dict[str, str] = {}   # 列名 -> 公式

    # ------------------------------------------------------------------
    # 基础
    # ------------------------------------------------------------------

    def set_columns(self, cols: list[str]):
        self.columns = [str(c) for c in cols]

    def add_row(self, row=None):
        n = len(self.columns)
        self.rows.append(list(row) if row else [""] * n)

    def remove_row(self, idx):
        if 0 <= idx < len(self.rows):
            self.rows.pop(idx)

    def set_cell(self, r, c, v):
        while r >= len(self.rows):
            self.add_row()
        while c >= len(self.rows[r]):
            self.rows[r].append("")
        self.rows[r][c] = str(v)

    def get_cell(self, r, c):
        try:
            return self.rows[r][c]
        except IndexError:
            return ""

    def to_list_of_dicts(self):
        return [dict(zip(self.columns, r)) for r in self.rows]

    # ------------------------------------------------------------------
    # 公式
    # ------------------------------------------------------------------

    def set_formula(self, col_name, expr):
        if col_name not in self.columns:
            raise InputError(f"未知列：{col_name}", friendly_key="err_input")
        if expr:
            self.formulas[col_name] = str(expr)
        else:
            self.formulas.pop(col_name, None)

    def recalc_all(self):
        """按列顺序计算所有公式列。"""
        for r in range(len(self.rows)):
            for c, col in enumerate(self.columns):
                formula = self.formulas.get(col)
                if not formula:
                    continue
                try:
                    v = self._eval_formula(formula, r)
                    self.set_cell(r, c, v)
                except Exception:
                    self.set_cell(r, c, "#ERR")

    # ------------------------------------------------------------------
    # 导入 / 导出
    # ------------------------------------------------------------------

    def from_csv(self, text):
        rows = list(csv.reader(io.StringIO(text)))
        if not rows:
            return
        self.columns = rows[0]
        self.rows = rows[1:]
        n = len(self.columns)
        for r in self.rows:
            while len(r) < n:
                r.append("")

    def to_csv(self):
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(self.columns)
        for r in self.rows:
            w.writerow(r)
        return buf.getvalue()

    def from_json(self, text):
        data = json.loads(text)
        if isinstance(data, list) and data and isinstance(data[0], dict):
            self.columns = list(data[0].keys())
            self.rows = [[str(d.get(c, "")) for c in self.columns]
                         for d in data]
        elif isinstance(data, dict):
            self.columns = [str(k) for k in data.keys()]
            self.rows = [[str(v) for v in data.values()]]

    def to_json(self):
        return json.dumps(self.to_list_of_dicts(),
                          ensure_ascii=False, indent=2)

    # ------------------------------------------------------------------
    # 公式求值
    # ------------------------------------------------------------------

    _SAFE_NAMES = {"abs": abs, "min": min, "max": max, "round": round,
                   "sqrt": math.sqrt, "log": math.log, "log10": math.log10,
                   "exp": math.exp, "sin": math.sin, "cos": math.cos,
                   "tan": math.tan, "pi": math.pi, "e": math.e}

    def _eval_formula(self, formula, row_idx):
        s = str(formula).strip()
        if s.startswith("="):
            s = s[1:]

        def _repl(m):
            name = m.group(1).strip()
            if name not in self.columns:
                raise ValueError(f"未知列 {name!r}")
            idx = self.columns.index(name)
            v = self.get_cell(row_idx, idx)
            try:
                return repr(float(v))
            except (TypeError, ValueError):
                raise ValueError(f"列 {name} 非数值：{v!r}")

        expr = re.sub(r"\[([^\]]+)\]", _repl, s)

        try:
            tree = ast.parse(expr, mode="eval")
        except SyntaxError as e:
            raise ValueError(f"公式语法错误：{e}")

        for node in ast.walk(tree):
            ok = isinstance(node, (
                ast.BinOp, ast.UnaryOp, ast.Num, ast.Constant,
                ast.Expression, ast.Add, ast.Sub, ast.Mult, ast.Div,
                ast.Pow, ast.Mod, ast.FloorDiv, ast.USub, ast.UAdd,
                ast.Load, ast.Call,
            ))
            if not ok:
                if isinstance(node, ast.Name):
                    if node.id not in self._SAFE_NAMES:
                        raise ValueError(f"未定义名称：{node.id}")
                else:
                    raise ValueError(
                        f"不允许的语法：{type(node).__name__}")

        return eval(compile(tree, "<formula>", "eval"),
                    {"__builtins__": {}}, dict(self._SAFE_NAMES))