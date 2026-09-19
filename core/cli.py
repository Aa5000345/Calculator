"""CLI 模式：从命令行直接运行表达式，不启动 GUI。

支持：
    # 单条表达式
    python main.py -e "1+1"
    python main.py --expr "1+1"
    python main.py --cli "1+1"
    python main.py "1+1"

    # 输出格式
    python main.py -e "1+1" --json          # JSON 输出
    python main.py -e "1+1" -o json         # 同上
    python main.py -e "1+1" -o text         # 默认
    python main.py -e "1+1" -o csv          # CSV 输出
    python main.py -e "1+1" --quiet         # 只输出结果

    # 角度模式
    python main.py -e "sin(30)" --angle DEG

    # 从 stdin 读多行
    echo "1+1" | python main.py --pipe
    type exprs.txt | python main.py --pipe -o json

    # 执行 Jupyter notebook
    python main.py --nb my.ipynb

    # 其它
    python main.py --help
    python main.py --version

URL 参数（启动 GUI）：
    python main.py "?expr=1%2B1"
    python main.py "multicalc://expr=1%2B1"
"""
from __future__ import annotations

import csv as _csv
import io as _io
import json as _json
import os
import sys
import urllib.parse

APP_VERSION = "1.4.0"


# ---------------------------------------------------------------------------
# 帮助文本
# ---------------------------------------------------------------------------

_HELP = f"""\
MultiCalc CLI v{APP_VERSION}

用法：
    python main.py [选项] [表达式]

选项：
    -e, --expr EXPR      计算 EXPR 并打印结果
    --cli EXPR           等价于 --expr
    --pipe               从 stdin 逐行读取表达式
    --nb FILE            执行 Jupyter Notebook (.ipynb)
    -o, --output FORMAT  输出格式：text（默认）/ json / csv
    --json               等价于 -o json
    --csv                等价于 -o csv
    --angle MODE         角度模式：RAD（默认）/ DEG
    --no-format          结果不做数字格式化
    --quiet              只输出结果，不打印额外信息
    -h, --help           显示本帮助
    -v, --version        显示版本号

URL 参数（启动 GUI）：
    ?expr=1+1            启动 GUI 并把 1+1 写入基础面板
    multicalc://expr=...

示例：
    python main.py -e "sqrt(2)"
    python main.py -e "sin(30)" --angle DEG
    python main.py -e "1+1" --json
    echo "1+1" | python main.py --pipe -o csv
    python main.py --nb session.ipynb
"""


def _print_err(msg: str):
    print(f"error: {msg}", file=sys.stderr)


# ---------------------------------------------------------------------------
# 单条计算
# ---------------------------------------------------------------------------

def _compute_one(expr: str, angle: str = "RAD",
                 no_format: bool = False) -> dict:
    """计算单条表达式，返回 dict。

    Returns:
        ``{"expr", "result", "error", "angle", "elapsed_ms"}``
    """
    import time
    t0 = time.perf_counter()
    out = {
        "expr": expr,
        "result": "",
        "error": "",
        "angle": angle,
        "elapsed_ms": 0.0,
    }

    try:
        from core import engine
    except Exception as e:
        out["error"] = f"无法加载核心模块：{e}"
        return out

    try:
        if no_format:
            value = engine.sci_eval(expr, angle_mode=angle)
            text = str(value)
        else:
            try:
                result = engine.basic_calc_smart(expr, angle)
                if (isinstance(result, tuple)
                        and len(result) == 2):
                    value, desc = result
                else:
                    value, desc = result, None
            except Exception:
                value, desc = engine.sci_eval(
                    expr, angle_mode=angle), None
            try:
                text = engine.format_result(value, "text")
            except Exception:
                text = str(value)
            if desc:
                text = f"{text}   ({desc})"
        out["result"] = text
    except Exception as e:  # noqa: BLE001
        out["error"] = str(e)

    out["elapsed_ms"] = (time.perf_counter() - t0) * 1000.0
    return out


def _format_output(results: list, fmt: str,
                   quiet: bool = False) -> str:
    """把结果列表格式化为指定格式。"""
    fmt = (fmt or "text").lower()

    if fmt == "json":
        if len(results) == 1:
            return _json.dumps(
                results[0], ensure_ascii=False)
        return _json.dumps(
            results, ensure_ascii=False, indent=2)

    if fmt == "csv":
        buf = _io.StringIO()
        w = _csv.writer(buf)
        w.writerow(["expr", "result", "error",
                    "angle", "elapsed_ms"])
        for r in results:
            w.writerow([
                r.get("expr", ""),
                r.get("result", ""),
                r.get("error", ""),
                r.get("angle", ""),
                f"{r.get('elapsed_ms', 0):.2f}",
            ])
        return buf.getvalue().rstrip("\n")

    # 默认 text
    if len(results) == 1:
        r = results[0]
        if r.get("error"):
            return f"error: {r['error']}"
        return r.get("result", "")

    # 多行：逐行输出 "expr = result"
    lines = []
    for r in results:
        e = r.get("expr", "")
        if r.get("error"):
            lines.append(f"{e} = [error] {r['error']}")
        else:
            lines.append(f"{e} = {r.get('result', '')}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 运行路径
# ---------------------------------------------------------------------------

def _run_expr_list(exprs: list, angle: str,
                   fmt: str, no_format: bool,
                   quiet: bool) -> int:
    """计算多条表达式并输出。"""
    results = []
    any_error = False
    for e in exprs:
        e = e.strip()
        if not e or e.startswith("#"):
            continue
        r = _compute_one(e, angle=angle, no_format=no_format)
        results.append(r)
        if r.get("error"):
            any_error = True

    if not results:
        if not quiet:
            _print_err("没有可执行的表达式")
        return 1

    text = _format_output(results, fmt, quiet=quiet)
    print(text)
    return 1 if any_error else 0


def _run_pipe(angle: str, fmt: str, no_format: bool,
              quiet: bool) -> int:
    """从 stdin 逐行读取。"""
    try:
        text = sys.stdin.read()
    except Exception as e:
        _print_err(f"读取 stdin 失败：{e}")
        return 3

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        _print_err("stdin 为空")
        return 1
    return _run_expr_list(
        lines, angle, fmt, no_format, quiet)


def _run_notebook(path: str, angle: str, fmt: str,
                  no_format: bool, quiet: bool) -> int:
    """执行 Jupyter Notebook 的 code cell。"""
    if not os.path.isfile(path):
        _print_err(f"notebook 不存在：{path}")
        return 3

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = _json.load(f)
    except Exception as e:
        _print_err(f"读取 notebook 失败：{e}")
        return 3

    cells = data.get("cells") if isinstance(data, dict) else None
    if not cells:
        _print_err("notebook 没有 cells")
        return 1

    exprs = []
    for c in cells:
        if not isinstance(c, dict):
            continue
        if c.get("cell_type") != "code":
            continue
        src = c.get("source")
        if isinstance(src, list):
            src = "".join(str(x) for x in src)
        for ln in str(src or "").splitlines():
            ln = ln.strip()
            if not ln or ln.startswith("#"):
                continue
            exprs.append(ln)

    if not exprs:
        _print_err("notebook 里没有可执行的表达式")
        return 1

    return _run_expr_list(exprs, angle, fmt, no_format, quiet)


# ---------------------------------------------------------------------------
# URL 参数
# ---------------------------------------------------------------------------

def extract_expr_from_argv(argv: list) -> str:
    """从 argv 中提取 URL 参数里的 ``?expr=...``。"""
    for a in argv or []:
        s = str(a)
        if s.lower().startswith("multicalc://"):
            q = s.split("://", 1)[1]
            if "?" in q:
                q = q.split("?", 1)[1]
            params = urllib.parse.parse_qs(q)
            vals = params.get("expr") or []
            if vals:
                return vals[0]
        if "expr=" in s:
            q = s.split("?", 1)[1] if "?" in s else s
            params = urllib.parse.parse_qs(q)
            vals = params.get("expr") or []
            if vals:
                return vals[0]
    return ""


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def try_run_cli(argv: list) -> tuple:
    """处理 CLI 参数。

    Returns:
        ``(handled, exit_code)``
        - handled=True  → 已处理完毕，调用方应直接退出
        - handled=False → 没有 CLI 参数，应走 GUI
    """
    if not argv:
        return False, 0

    args = list(argv)
    expr = ""
    as_pipe = False
    nb_path = ""
    fmt = "text"
    angle = "RAD"
    no_format = False
    quiet = False

    i = 0
    while i < len(args):
        a = args[i]

        if a in ("-h", "--help"):
            print(_HELP)
            return True, 0
        if a in ("-v", "--version"):
            print(APP_VERSION)
            return True, 0

        if a in ("-e", "--expr", "--cli"):
            if i + 1 >= len(args):
                _print_err(f"{a} 需要一个表达式")
                return True, 2
            expr = args[i + 1]
            i += 2
            continue

        if a == "--pipe":
            as_pipe = True
            i += 1
            continue

        if a in ("--nb", "--notebook"):
            if i + 1 >= len(args):
                _print_err(f"{a} 需要一个文件路径")
                return True, 2
            nb_path = args[i + 1]
            i += 2
            continue

        if a in ("-o", "--output"):
            if i + 1 >= len(args):
                _print_err(f"{a} 需要格式：text / json / csv")
                return True, 2
            fmt = str(args[i + 1]).lower()
            if fmt not in ("text", "json", "csv"):
                _print_err(f"未知输出格式：{fmt}")
                return True, 2
            i += 2
            continue

        if a == "--json":
            fmt = "json"
            i += 1
            continue

        if a == "--csv":
            fmt = "csv"
            i += 1
            continue

        if a == "--angle":
            if i + 1 >= len(args):
                _print_err("--angle 需要 RAD 或 DEG")
                return True, 2
            angle = str(args[i + 1]).upper()
            if angle not in ("RAD", "DEG"):
                _print_err(f"未知角度模式：{angle}")
                return True, 2
            i += 2
            continue

        if a == "--no-format":
            no_format = True
            i += 1
            continue

        if a == "--quiet":
            quiet = True
            i += 1
            continue

        # 裸表达式（跳过 URL 参数）
        if not a.startswith("-") and not expr:
            if ("expr=" in a
                    or a.lower().startswith("multicalc://")):
                i += 1
                continue
            expr = a
            i += 1
            continue

        i += 1

    # 派发
    if as_pipe:
        code = _run_pipe(angle, fmt, no_format, quiet)
        return True, code

    if nb_path:
        code = _run_notebook(nb_path, angle, fmt,
                             no_format, quiet)
        return True, code

    if expr:
        code = _run_expr_list(
            [expr], angle, fmt, no_format, quiet)
        return True, code

    return False, 0


__all__ = [
    "APP_VERSION",
    "try_run_cli",
    "extract_expr_from_argv",
]
