"""用户自定义变量 / 函数存储。

支持的语法：
    x = 5
    y = x * 2
    f(x) = x^2 + 1
    g(x, y) = x^2 + y^2

持久化到 ~/.multicalc/symbols.json（尽力而为，忽略失败）。

变更（本轮）：
- 修复原文件 docstring 的乱码
- 新增 get_symbol / has / count / get_functions / get_variables
- 新增 export_json / import_json
- 增加线程安全保护
"""
from __future__ import annotations

import json
import os
import re
import threading

_LOCK = threading.RLock()
_SYMBOLS: dict = {}        # name -> sympy 对象
_RAW: dict = {}            # name -> 原始字符串（用于持久化与展示）
_PERSIST_PATH: str | None = None


# 匹配 `name = ...` 或 `name(args) = ...`（排除 `==`）
_ASSIGN_RE = re.compile(
    r'^\s*([A-Za-z_]\w*)\s*(\([^)]*\))?\s*=(?!=)\s*(.+)$'
)

# 匹配是否像函数（有参数括号）
_FUNC_NAME_RE = re.compile(r'^\s*([A-Za-z_]\w*)\s*\(')


# ---------------------------------------------------------------------------
# 持久化路径
# ---------------------------------------------------------------------------

def set_persist_path(path: str):
    global _PERSIST_PATH
    _PERSIST_PATH = path
    _load()


# ---------------------------------------------------------------------------
# 匹配
# ---------------------------------------------------------------------------

def match_assignment(s: str):
    """如果 s 是赋值语句，返回 ``(name, args_str_or_None, rhs)``；否则 None。

    例：
        "x = 5"            → ("x", None, "5")
        "f(x) = x^2 + 1"   → ("f", "(x)", "x^2 + 1")
        "1 + 1"            → None
    """
    m = _ASSIGN_RE.match(s)
    if not m:
        return None
    return m.group(1), m.group(2), m.group(3)


# ---------------------------------------------------------------------------
# 读取
# ---------------------------------------------------------------------------

def get_all() -> dict:
    """返回所有符号（name -> sympy 对象）。"""
    with _LOCK:
        return dict(_SYMBOLS)


def get_raw() -> dict:
    """返回所有符号的原始字符串（name -> str）。"""
    with _LOCK:
        return dict(_RAW)


def get_symbol(name: str, default=None):
    """取单个符号。"""
    with _LOCK:
        return _SYMBOLS.get(name, default)


def has(name: str) -> bool:
    with _LOCK:
        return name in _SYMBOLS


def count() -> int:
    with _LOCK:
        return len(_SYMBOLS)


def get_variables() -> dict:
    """只返回非函数符号（标量 / 表达式）。"""
    with _LOCK:
        out = {}
        for k, v in _SYMBOLS.items():
            if not _is_function(v):
                out[k] = v
        return out


def get_functions() -> dict:
    """只返回函数符号（Lambda）。"""
    with _LOCK:
        out = {}
        for k, v in _SYMBOLS.items():
            if _is_function(v):
                out[k] = v
        return out


def _is_function(v) -> bool:
    """判断一个 sympy 对象是否是 Lambda。"""
    try:
        import sympy as sp
        return isinstance(v, sp.Lambda)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# 写入
# ---------------------------------------------------------------------------

def set_symbol(name: str, value, raw: str | None = None):
    """设置一个符号。

    Args:
        name: 变量名
        value: sympy 对象
        raw: 原始字符串（None 时用 str(value)）
    """
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


def delete_symbol(name: str) -> bool:
    """删除一个符号，返回是否删除成功。"""
    with _LOCK:
        existed = name in _SYMBOLS
        _SYMBOLS.pop(name, None)
        _RAW.pop(name, None)
    if existed:
        _save()
    return existed


def clear():
    """清空所有符号。"""
    with _LOCK:
        _SYMBOLS.clear()
        _RAW.clear()
    _save()


# ---------------------------------------------------------------------------
# 导入 / 导出
# ---------------------------------------------------------------------------

def export_json(path: str) -> bool:
    """导出为 JSON。"""
    try:
        with _LOCK:
            data = {
                "version": 1,
                "symbols": {
                    name: {
                        "raw": _RAW.get(name, ""),
                        "is_function": _is_function(_SYMBOLS.get(name)),
                    }
                    for name in _SYMBOLS
                },
            }
        os.makedirs(os.path.dirname(os.path.abspath(path)) or ".",
                    exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def import_json(path: str, merge: bool = True) -> dict:
    """从 JSON 导入。

    Args:
        merge: True 时合并；False 时先清空

    Returns:
        ``{"imported": int, "skipped": int}``
    """
    import sympy as sp

    result = {"imported": 0, "skipped": 0}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return result

    symbols = data.get("symbols") if isinstance(data, dict) else None
    if not isinstance(symbols, dict):
        return result

    if not merge:
        clear()

    for name, info in symbols.items():
        try:
            raw = (info.get("raw")
                   if isinstance(info, dict) else str(info))
            if not raw:
                result["skipped"] += 1
                continue
            # 尝试用 sympify 恢复
            val = sp.sympify(raw)
            set_symbol(name, val, raw)
            result["imported"] += 1
        except Exception:
            result["skipped"] += 1
    return result


# ---------------------------------------------------------------------------
# 内部：加载 / 保存
# ---------------------------------------------------------------------------

def _load():
    if not _PERSIST_PATH or not os.path.exists(_PERSIST_PATH):
        return
    try:
        import sympy as sp
        with open(_PERSIST_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        with _LOCK:
            if isinstance(data, dict):
                # 兼容旧格式：{name: {"raw": str}}
                items = data.get("symbols", data)
                for name, info in items.items():
                    if isinstance(info, dict) and "raw" in info:
                        raw = str(info["raw"])
                    else:
                        raw = str(info)
                    if not raw:
                        continue
                    try:
                        _SYMBOLS[name] = sp.sympify(raw)
                        _RAW[name] = raw
                    except Exception:
                        pass
    except Exception:
        pass


def _save():
    if not _PERSIST_PATH:
        return
    try:
        with _LOCK:
            out = {
                "version": 1,
                "symbols": {
                    name: {"raw": raw}
                    for name, raw in _RAW.items()
                },
            }
        os.makedirs(
            os.path.dirname(_PERSIST_PATH), exist_ok=True)
        with open(_PERSIST_PATH, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# 默认持久化路径（可被 main.py 覆盖）
# ---------------------------------------------------------------------------

set_persist_path(os.path.join(
    os.path.expanduser("~"), ".multicalc", "symbols.json"))


__all__ = [
    "set_persist_path",
    "match_assignment",
    "get_all",
    "get_raw",
    "get_symbol",
    "has",
    "count",
    "get_variables",
    "get_functions",
    "set_symbol",
    "delete_symbol",
    "clear",
    "export_json",
    "import_json",
]