"""CLI 模式：从命令行直接运行表达式，不启动 GUI。

支持：
    python main.py -e "1+1"          → 打印结果
    python main.py --expr "1+1"      → 同上
    python main.py --cli "1+1"       → 同上
    python main.py "1+1"             → 裸表达式也支持
    python main.py -e "1+1" --json   → JSON 输出
    python main.py -e "sin(30)" --angle DEG
    python main.py --help
    python main.py --version

URL 参数（启动 GUI）：
    python main.py "?expr=1%2B1"
    python main.py "multicalc://expr=1%2B1"
"""
from __future__ import annotations

import json as _json
import sys
import urllib.parse

APP_VERSION = "1.0.0"


_HELP = """\
MultiCalc CLI

用法：
    python main.py [选项] [表达式]

选项：
    -e, --expr EXPR      计算 EXPR 并打印结果
    --cli EXPR           等价于 --expr
    --json               以 JSON 输出（含 expr / result / error / angle）
    --angle MODE         角度模式：RAD（默认）/ DEG
    --no-format          结果不做数字格式化
    -h, --help           显示本帮助
    -v, --version        显示版本号

URL 参数（启动 GUI）：
    ?expr=1+1            启动 GUI 并把 1+1 写入基础面板
    multicalc://expr=...

示例：
    python main.py -e "sqrt(2)"
    python main.py -e "sin(30)" --angle DEG
    python main.py -e "1+1" --json
"""


def _print_err(msg: str):
    print(f"error: {msg}", file=sys.stderr)


def _run_expr(expr: str, angle: str = "RAD",
              as_json: bool = False, no_format: bool = False) -> int:
    """执行一次表达式；返回退出码（0 成功 / 1 计算错误 / 3 环境错误）。"""
    try:
        from core import engine
    except Exception as e:
        _print_err(f"无法加载核心模块：{e}")
        return 3

    try:
        if no_format:
            result = engine.sci_eval(expr, angle_mode=angle)
            text = str(result)
        else:
            try:
                value, desc = engine.basic_calc_smart(expr, angle)
            except Exception:
                value, desc = engine.sci_eval(expr, angle), None
            if isinstance(value, tuple) and len(value) == 2:
                value, desc = value
            try:
                text = engine.format_result(value, "text")
            except Exception:
                text = str(value)
            if desc:
                text = f"{text}   ({desc})"
    except Exception as e:
        if as_json:
            print(_json.dumps({
                "expr": expr, "result": "", "error": str(e),
                "angle": angle,
            }, ensure_ascii=False))
        else:
            _print_err(str(e))
        return 1

    if as_json:
        print(_json.dumps({
            "expr": expr, "result": text, "error": "",
            "angle": angle,
        }, ensure_ascii=False))
    else:
        print(text)
    return 0


def extract_expr_from_argv(argv: list) -> str:
    """从 argv 中提取 URL 参数里的 ?expr=... 或 multicalc://expr=... 。"""
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


def try_run_cli(argv: list) -> tuple:
    """处理 CLI 参数。

    返回 (handled, exit_code)：
    - handled=True  表示已处理完毕，调用方应直接退出
    - handled=False 表示没有 CLI 相关参数，应走 GUI
    """
    if not argv:
        return False, 0

    args = list(argv)
    expr = ""
    as_json = False
    angle = "RAD"
    no_format = False

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
        if a == "--json":
            as_json = True
            i += 1
            continue
        if a == "--angle":
            if i + 1 >= len(args):
                _print_err("--angle 需要 RAD 或 DEG")
                return True, 2
            angle = str(args[i + 1]).upper()
            i += 2
            continue
        if a == "--no-format":
            no_format = True
            i += 1
            continue
        # 裸表达式（跳过 URL 参数）
        if not a.startswith("-") and not expr:
            if "expr=" in a or a.lower().startswith("multicalc://"):
                i += 1
                continue
            expr = a
            i += 1
            continue
        i += 1

    if not expr:
        return False, 0

    code = _run_expr(expr, angle=angle, as_json=as_json,
                     no_format=no_format)
    return True, code