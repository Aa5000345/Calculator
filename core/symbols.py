"""用户定义变量/函数存储。

支持语法：
    x = 5
    y = x * 2
    f(x) = x^2 + 1
    g(x, y) = x^2 + y^2

持久化到 ~/.multicalc/symbols.json（尽力而为，忽略失败）。
"""
from __future__ import annotations

import json
import os
import re
import threading

_LOCK = threading.RLock()
_SYMBOLS: dict = {}     # name -> sympy 对象
_RAW: dict = {}         # name -> 原始字符串（用于持久化与显示）
_PERSIST_PATH: str | None = None

_ASSIGN_RE = re.compile(
    r'^\s*([A-Za-z_]\w*)\s*(\([^)]*\))?\s*=(?!=)\s*(.+)$'
)


def set_persist_path(path: str):
    global _PERSIST_PATH
    _PERSIST_PATH = path
    _load()


def match_assignment(s: str):
    """如果 s 是赋值语句，返回 (name, args_str_or_None, rhs)；否则 None。"""
    m = _ASSIGN_RE.match(s)
    if not m:
        return None
    return m.group(1), m.group(2), m.group(3)


def get_all() -> dict:
    with _LOCK:
        return dict(_SYMBOLS)


def get_raw() -> dict:
    with _LOCK:
        return dict(_RAW)


def set_symbol(name: str, value, raw: str | None = None):
    with _LOCK:
        _SYMBOLS[name] = value
        if raw is not None:
            _RAW[name] = raw
        else:
            try:
                _RAW[name] = str(value)
            except Exception:
                _RAW[name] = ""
    _save()


def delete_symbol(name: str):
    with _LOCK:
        _SYMBOLS.pop(name, None)
        _RAW.pop(name, None)
    _save()


def clear():
    with _LOCK:
        _SYMBOLS.clear()
        _RAW.clear()
    _save()


def _load():
    if not _PERSIST_PATH or not os.path.exists(_PERSIST_PATH):
        return
    try:
        import sympy as sp
        with open(_PERSIST_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            for name, info in data.items():
                if isinstance(info, dict) and "raw" in info:
                    try:
                        _SYMBOLS[name] = sp.sympify(info["raw"])
                        _RAW[name] = info["raw"]
                    except Exception:
                        pass
    except Exception:
        pass


def _save():
    if not _PERSIST_PATH:
        return
    try:
        with _LOCK:
            out = {name: {"raw": raw} for name, raw in _RAW.items()}
        os.makedirs(os.path.dirname(_PERSIST_PATH), exist_ok=True)
        with open(_PERSIST_PATH, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# 默认持久化路径（可被 main.py 覆盖）
set_persist_path(os.path.join(
    os.path.expanduser("~"), ".multicalc", "symbols.json"))