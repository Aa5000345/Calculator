"""计算内核：科学计算 / 线性代数 / 绘图采样 / 单位 / 汇率 / 财务 / 日期 / 随机数

最终版变更：
- 新增角度模式（DEG/RAD）支持；basic_calc / sci_eval / basic_calc_smart 接受 angle_mode
- _parse / _handle_assignment 支持 base_locals 注入
- sci_linprog 修复：import json as _json
"""
from __future__ import annotations

import datetime
import json as _json
import math
import random
import re

import numpy as np
import requests
import sympy as sp
from pint import UnitRegistry
from sympy.parsing.sympy_parser import (
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)

from core.errors import InputError, MathError, UnitError, NetworkError
from core.logger import log_warn
from core import symbols as _symbols_mod

ureg = UnitRegistry()

# ---------------------------------------------------------------------------
# 表达式解析
# ---------------------------------------------------------------------------

_MAX_EXPR_LEN = 4000
_FORBIDDEN_SUBSTR = (
    "__", "import", "eval", "exec", "open", "lambda",
    "globals", "locals", "getattr", "setattr", "delattr",
    "compile", "input", "breakpoint", "os.", "sys.", "subprocess",
    "pickle", "marshal", "shutil", "socket",
)

_LOCALS = {
    "sin": sp.sin, "cos": sp.cos, "tan": sp.tan,
    "asin": sp.asin, "acos": sp.acos, "atan": sp.atan,
    "atan2": sp.atan2,
    "sinh": sp.sinh, "cosh": sp.cosh, "tanh": sp.tanh,
    "asinh": sp.asinh, "acosh": sp.acosh, "atanh": sp.atanh,
    "log": sp.log, "ln": sp.log,
    "log10": lambda x: sp.log(x, 10),
    "exp": sp.exp, "sqrt": sp.sqrt, "cbrt": sp.cbrt,
    "Abs": sp.Abs, "abs": sp.Abs,
    "factorial": sp.factorial, "gamma": sp.gamma,
    "sign": sp.sign, "floor": sp.floor, "ceil": sp.ceiling,
    "Min": sp.Min, "Max": sp.Max,
    "pi": sp.pi, "E": sp.E, "I": sp.I, "oo": sp.oo,
    "re": sp.re, "im": sp.im, "conjugate": sp.conjugate,
}

# ---------------------------------------------------------------------------
# 角度模式：DEG / RAD
# ---------------------------------------------------------------------------

_DEG_TRIG = {
    "sin": lambda x: sp.sin(x * sp.pi / 180),
    "cos": lambda x: sp.cos(x * sp.pi / 180),
    "tan": lambda x: sp.tan(x * sp.pi / 180),
    "asin": lambda x: sp.asin(x) * 180 / sp.pi,
    "acos": lambda x: sp.acos(x) * 180 / sp.pi,
    "atan": lambda x: sp.atan(x) * 180 / sp.pi,
}


def _locals_for(angle_mode: str):
    """按角度模式返回参数字典；RAD 时直接返回 _LOCALS（零开销）。"""
    if str(angle_mode).upper() != "DEG":
        return _LOCALS
    out = dict(_LOCALS)
    out.update(_DEG_TRIG)
    return out


_TRANSFORMS = standard_transformations + (implicit_multiplication_application,)


def _norm(expr) -> str:
    s = str(expr).strip()
    s = (s.replace("π", "pi").replace("×", "*").replace("÷", "/")
          .replace("−", "-").replace("^", "**")
          .replace("≤", "<=").replace("≥", ">="))
    s = re.sub(r"(\d+)\s*!", r"factorial(\1)", s)
    return s


def _safety_check(s: str):
    if len(s) > _MAX_EXPR_LEN:
        raise InputError(
            f"表达式过长（上限 {_MAX_EXPR_LEN} 字符）",
            friendly_key="err_parse")
    low = s.lower()
    for pat in _FORBIDDEN_SUBSTR:
        if pat in low:
            raise InputError(f"表达式包含禁用内容：{pat!r}",
                             friendly_key="err_parse")


def _parse(expr, extra=None, base_locals=None):
    s = _norm(expr)
    if not s:
        raise InputError("表达式为空", friendly_key="err_empty_expr")
    _safety_check(s)

    base = base_locals if base_locals is not None else _LOCALS

    # 1) 赋值语句：name = ...  或  name(args) = ...
    assignment = _symbols_mod.match_assignment(s)
    if assignment is not None:
        return _handle_assignment(assignment, base)

    # 2) 普通表达式：把用户变量注入 local_dict
    local = dict(base)
    if extra:
        local.update(extra)
    for name, val in _symbols_mod.get_all().items():
        if name not in local:
            local[name] = val

    try:
        return parse_expr(s, local_dict=local, transformations=_TRANSFORMS)
    except SyntaxError as e:
        raise InputError(f"语法错误：{e}", friendly_key="err_syntax") from e
    except (TypeError, AttributeError) as e:
        raise InputError(f"表达式非法：{e}", friendly_key="err_parse") from e
    except Exception as e:  # noqa: BLE001
        raise InputError(f"无法解析：{e}", friendly_key="err_parse") from e


def _handle_assignment(assignment, base_locals=None):
    """处理 ``x = expr`` / ``f(x, y) = expr``。"""
    base = base_locals if base_locals is not None else _LOCALS
    name, args_str, rhs = assignment

    # --- 变量 ---
    if args_str is None:
        val = _parse(rhs, base_locals=base)
        _symbols_mod.set_symbol(name, val, raw=rhs)
        return val

    # --- 函数 ---
    args = [a.strip() for a in args_str[1:-1].split(",") if a.strip()]
    if not args:
        raise InputError("函数定义缺少参数", friendly_key="err_parse")
    syms = sp.symbols(" ".join(args))
    if not isinstance(syms, (tuple, list)):
        syms = (syms,)
    if len(syms) != len(args):
        raise InputError("函数参数名重复或非法", friendly_key="err_parse")

    local = dict(base)
    for n, s in zip(args, syms):
        local[n] = s
    for k, v in _symbols_mod.get_all().items():
        if k not in local:
            local[k] = v

    try:
        body = parse_expr(_norm(rhs), local_dict=local,
                          transformations=_TRANSFORMS)
    except Exception as e:  # noqa: BLE001
        raise InputError(f"函数体解析失败：{e}",
                         friendly_key="err_parse") from e

    lam = sp.Lambda(syms[0] if len(syms) == 1 else syms, body)
    raw_repr = f"{name}{args_str} = {rhs}"
    _symbols_mod.set_symbol(name, lam, raw=str(body))
    _symbols_mod._RAW[name] = raw_repr
    _symbols_mod._save()
    return lam


def _num(obj, digits: int = 15):
    val = sp.N(obj, digits)
    try:
        if getattr(val, "is_number", False) and getattr(val, "is_real", False):
            f = float(val)
            if abs(f - round(f)) < 1e-12 and abs(f) < 1e15:
                return int(round(f))
            return f
    except Exception:
        pass
    return val


# ---------------------------------------------------------------------------
# 结果格式化
# ---------------------------------------------------------------------------

def _format_scalar(obj, fmt: str, digits, sci, fraction, percent):
    """尝试对纯数字应用 digits / sci / fraction / percent；否则返回 None。"""
    try:
        is_number = (
            isinstance(obj, (int, float)) and not isinstance(obj, bool)
        ) or (hasattr(obj, "is_number") and obj.is_number)
    except Exception:
        is_number = False
    if not is_number:
        return None

    val = obj
    if percent:
        try:
            val = sp.N(val) * 100
        except Exception:
            return None

    if fraction and not sci:
        try:
            fr = sp.Rational(sp.N(val)).limit_denominator(10 ** 9)
            if fr.q != 1:
                if fmt == "latex":
                    return sp.latex(fr) + (r"\%" if percent else "")
                tail = "%" if percent else ""
                return f"{fr.p}/{fr.q}{tail}"
        except Exception:
            pass

    if sci:
        try:
            f = float(sp.N(val))
            s = f"{f:.{digits if digits is not None else 6}e}"
            return s + ("%" if percent else "")
        except Exception:
            return None

    if digits is not None:
        try:
            f = float(sp.N(val))
            s = f"{f:.{int(digits)}f}"
            if "." in s:
                s = s.rstrip("0").rstrip(".")
            return s + ("%" if percent else "")
        except Exception:
            return None

    if percent:
        try:
            f = float(sp.N(val))
            return f"{f:g}%"
        except Exception:
            return None
    return None


def _is_quantity(obj):
    try:
        from pint import Quantity
        return isinstance(obj, Quantity)
    except Exception:
        return False


def _try_unit_parse(s):
    """尝试用 pint 解析；若结果含单位且非无量纲，返回 Quantity；否则 None。"""
    try:
        result = ureg.parse_expression(str(s))
    except Exception:
        return None
    if not _is_quantity(result):
        return None
    try:
        if result.dimensionless:
            return None
    except Exception:
        pass
    return result


def _format_quantity(q, fmt="text", digits=None):
    """格式化 pint Quantity 为带单位的字符串。"""
    try:
        magnitude = q.magnitude
        if digits is not None:
            try:
                m = float(magnitude)
                text_num = f"{m:.{int(digits)}f}".rstrip("0").rstrip(".")
            except Exception:
                text_num = str(magnitude)
        else:
            try:
                m = float(magnitude)
                if abs(m - round(m)) < 1e-12 and abs(m) < 1e15:
                    text_num = str(int(round(m)))
                else:
                    text_num = f"{m:g}"
            except Exception:
                text_num = str(magnitude)

        units_str = f"{q.units:~}"
        if fmt == "latex":
            return f"{text_num}\\;\\mathrm{{{units_str}}}"
        return f"{text_num} {units_str}"
    except Exception:
        return str(q)


def format_result(obj, fmt: str = "text", *,
                  digits=None, sci=False, fraction=False, percent=False):
    """格式化结果。"""
    if obj is None:
        return ""
    if isinstance(obj, str):
        return obj
    if isinstance(obj, bool):
        return str(obj)
    if _is_quantity(obj):
        return _format_quantity(obj, fmt, digits)

    special = _format_scalar(obj, fmt, digits, sci, fraction, percent)
    if special is not None:
        return special

    try:
        if isinstance(obj, dict):
            items = [(k, _format_scalar(v, fmt, digits, sci, fraction, percent)
                      or v) for k, v in obj.items()]
            if fmt == "latex":
                return r",\quad ".join(
                    f"{sp.latex(k)} = {sp.latex(v) if not isinstance(v, str) else v}"
                    for k, v in items)
            if fmt == "unicode":
                return ",  ".join(
                    f"{k} = {sp.pretty(v, use_unicode=True) if not isinstance(v, str) else v}"
                    for k, v in items)
            return ",  ".join(f"{k} = {v}" for k, v in items)

        if isinstance(obj, (list, tuple, set)):
            items = list(obj)
            if not items:
                return "[]"
            if all(isinstance(x, dict) for x in items):
                return "\n".join(
                    format_result(x, fmt, digits=digits, sci=sci,
                                  fraction=fraction, percent=percent)
                    for x in items)
            converted = [
                _format_scalar(x, fmt, digits, sci, fraction, percent) or x
                for x in items
            ]
            if fmt == "latex":
                return r",\quad ".join(
                    sp.latex(x) if not isinstance(x, str) else x
                    for x in converted)
            if fmt == "unicode":
                return "\n".join(
                    sp.pretty(x, use_unicode=True)
                    if not isinstance(x, str) else x
                    for x in converted)
            return ",  ".join(str(x) for x in converted)

        if isinstance(obj, sp.MatrixBase):
            if fmt == "latex":
                return sp.latex(obj)
            return sp.pretty(obj, use_unicode=True)

        if fmt == "latex":
            return sp.latex(obj)
        if fmt == "unicode":
            return sp.pretty(obj, use_unicode=True)
    except Exception:
        pass
    return str(obj)


# ---------------------------------------------------------------------------
# 基础 / 科学计算
# ---------------------------------------------------------------------------

def basic_calc(expr, angle_mode="RAD"):
    q = _try_unit_parse(expr)
    if q is not None:
        return q

    e = _parse(expr, base_locals=_locals_for(angle_mode))
    try:
        val = sp.N(e, 30)
    except ZeroDivisionError as ex:
        raise MathError("除零错误", friendly_key="err_div_zero") from ex
    except Exception as ex:  # noqa: BLE001
        raise MathError(f"求值失败：{ex}") from ex

    if getattr(val, "is_number", False):
        c = None
        try:
            c = complex(val)
        except (TypeError, ValueError, OverflowError):
            c = None

        if c is not None:
            if math.isnan(c.real) or math.isnan(c.imag):
                raise MathError("结果未定义 (NaN)", friendly_key="err_nan")
            if math.isinf(c.real) or math.isinf(c.imag):
                raise MathError("结果无穷（除零或溢出）",
                                friendly_key="err_infinite")
        else:
            if getattr(val, "is_infinite", False):
                raise MathError("结果无穷（除零或溢出）",
                                friendly_key="err_infinite")

    return _num(val)


def scientific_calc(expr):
    return _parse(expr)


def sci_eval(expr, angle_mode="RAD"):
    q = _try_unit_parse(expr)
    if q is not None:
        return q
    return _num(_parse(expr, base_locals=_locals_for(angle_mode)))


def sci_simplify(expr):
    return sp.simplify(_parse(expr))


def sci_expand(expr):
    return sp.expand(_parse(expr))


def sci_factor(expr):
    return sp.factor(_parse(expr))


def sci_apart(expr):
    return sp.apart(_parse(expr))


def sci_trigsimp(expr):
    return sp.trigsimp(_parse(expr))


def sci_solve(expr, var: str = "x"):
    s = str(expr)
    if "=" in s:
        left, right = s.split("=", 1)
        e = _parse(left) - _parse(right)
    else:
        e = _parse(s)
    v = sp.Symbol(var.strip() or "x")
    return sp.solve(e, v)


def sci_solve_system(text: str, vars_str: str = "x, y"):
    eqs = []
    for line in re.split(r"[;\n]+", str(text)):
        line = line.strip()
        if not line:
            continue
        if "=" in line:
            left, right = line.split("=", 1)
            eqs.append(_parse(left) - _parse(right))
        else:
            eqs.append(_parse(line))
    names = [v.strip() for v in re.split(r"[,\s]+", vars_str) if v.strip()]
    if not names:
        names = ["x", "y"]
    syms = [sp.Symbol(n) for n in names]
    return sp.solve(eqs, syms, dict=True)


def sci_diff(expr, var: str = "x", order: int = 1):
    v = sp.Symbol(var.strip() or "x")
    return sp.simplify(sp.diff(_parse(expr), v, int(order)))


def sci_integrate(expr, var: str = "x", lower=None, upper=None):
    v = sp.Symbol(var.strip() or "x")
    e = _parse(expr)
    lo, up = (lower or "").strip(), (upper or "").strip()
    if lo and up:
        return sp.simplify(sp.integrate(e, (v, _parse(lo), _parse(up))))
    return sp.simplify(sp.integrate(e, v))


def sci_limit(expr, var: str = "x", point: str = "0", direction: str = "+"):
    v = sp.Symbol(var.strip() or "x")
    d = direction if direction in ("+", "-", "+-") else "+"
    return sp.limit(_parse(expr), v, _parse(point or "0"), dir=d)


def sci_series(expr, var: str = "x", point: str = "0", order: int = 6):
    v = sp.Symbol(var.strip() or "x")
    return sp.series(_parse(expr), v, _parse(point or "0"),
                     int(order)).removeO()


def sci_summation(expr, var: str = "n", lower: str = "1", upper: str = "10"):
    v = sp.Symbol(var.strip() or "n")
    return sp.summation(_parse(expr), (v, _parse(lower), _parse(upper)))


def sci_product(expr, var: str = "n", lower: str = "1", upper: str = "10"):
    v = sp.Symbol(var.strip() or "n")
    return sp.product(_parse(expr), (v, _parse(lower), _parse(upper)))


# 兼容旧接口
def solve_equation(eq, var="x"):
    return sci_solve(eq, var)


def integrate_expr(expr, var="x", lower=None, upper=None):
    return sci_integrate(expr, var, lower, upper)


def diff_expr(expr, var="x", n=1):
    return sci_diff(expr, var, n)


def limit_expr(expr, var="x", point="0"):
    return sci_limit(expr, var, point, "+")


# ---------------------------------------------------------------------------
# 矩阵 / 线性代数
# ---------------------------------------------------------------------------

def _parse_matrix(text):
    s = str(text).strip()
    if not s:
        raise InputError("矩阵为空", friendly_key="err_input")
    try:
        if "[" not in s and (";" in s or "\n" in s):
            rows = [r for r in re.split(r"[;\n]+", s) if r.strip()]
            data = [[_parse(x) for x in r.split(",")] for r in rows]
            return sp.Matrix(data)
        return sp.Matrix(_parse(s))
    except InputError:
        raise
    except Exception as e:  # noqa: BLE001
        raise InputError(f"矩阵解析失败：{e}", friendly_key="err_input") from e


def _is_singular(A):
    """对符号矩阵与数值矩阵都可靠的奇异性检查。"""
    try:
        if A.rows != A.cols:
            return True
        if A.free_symbols:
            try:
                return bool(A.det().equals(0))
            except Exception:
                return False
        return A.det() == 0
    except Exception:
        return False


def matrix_unary(action: str, text: str, scalar=None):
    A = _parse_matrix(text)
    if action == "det":
        return sp.simplify(A.det())
    if action == "inv":
        if A.rows != A.cols:
            raise MathError("非方阵无法求逆", friendly_key="err_math")
        if _is_singular(A):
            raise MathError("奇异矩阵不可逆", friendly_key="err_math")
        try:
            return sp.simplify(A.inv())
        except Exception as e:  # noqa: BLE001
            raise MathError(f"矩阵不可逆：{e}",
                            friendly_key="err_math") from e
    if action == "transpose":
        return A.T
    if action == "trace":
        if A.rows != A.cols:
            raise MathError("非方阵无迹", friendly_key="err_math")
        return sp.simplify(A.trace())
    if action == "rank":
        return A.rank()
    if action == "rref":
        return A.rref()[0]
    if action == "eigenvals":
        if A.rows != A.cols:
            raise MathError("非方阵无特征值", friendly_key="err_math")
        return A.eigenvals()
    if action == "eigenvects":
        if A.rows != A.cols:
            raise MathError("非方阵无特征向量", friendly_key="err_math")
        return A.eigenvects()
    if action == "charpoly":
        if A.rows != A.cols:
            raise MathError("非方阵无特征多项式", friendly_key="err_math")
        lam = sp.Symbol("lambda")
        return sp.simplify(A.charpoly(lam).as_expr())
    if action == "adjugate":
        if A.rows != A.cols:
            raise MathError("非方阵无伴随矩阵", friendly_key="err_math")
        return sp.simplify(A.adjugate())
    if action == "nullspace":
        return A.nullspace()
    if action == "columnspace":
        return A.columnspace()
    if action == "rowspace":
        return A.rowspace()
    if action == "lu":
        L, U, perm = A.LUdecomposition()
        return {"L": L, "U": U,
                "perm": sp.Matrix([list(perm)]) if perm else sp.Matrix([[0]])}
    if action == "qr":
        Q, R = A.QRdecomposition()
        return {"Q": Q, "R": R}
    if action == "exp":
        if A.rows != A.cols:
            raise MathError("非方阵无矩阵指数", friendly_key="err_math")
        return sp.simplify(A.exp())
    if action == "norm":
        return sp.simplify(A.norm())
    if action == "power":
        if A.rows != A.cols:
            raise MathError("非方阵无法求幂", friendly_key="err_math")
        n = int(scalar) if scalar not in (None, "") else 1
        return sp.simplify(A ** n)
    return A


def matrix_binary(action: str, a_text: str, b_text: str):
    A = _parse_matrix(a_text)
    B = _parse_matrix(b_text)
    if action == "mat_add":
        if A.shape != B.shape:
            raise MathError("矩阵维度不匹配", friendly_key="err_math")
        return sp.simplify(A + B)
    if action == "mat_sub":
        if A.shape != B.shape:
            raise MathError("矩阵维度不匹配", friendly_key="err_math")
        return sp.simplify(A - B)
    if action == "mat_mul":
        if A.cols != B.rows:
            raise MathError("矩阵维度不匹配（A 列数 ≠ B 行数）",
                            friendly_key="err_math")
        return sp.simplify(A * B)
    if action == "mat_hadamard":
        if A.shape != B.shape:
            raise MathError("Hadamard 积要求两个矩阵同型",
                            friendly_key="err_math")
        return sp.Matrix(A.rows, A.cols,
                         lambda i, j: sp.simplify(A[i, j] * B[i, j]))
    if action == "mat_kron":
        return sp.Matrix(sp.kronecker_product(A, B))
    if action == "mat_solve":
        try:
            return sp.simplify(A.solve(B))
        except Exception as e:  # noqa: BLE001
            raise MathError(f"无法求解 AX=B：{e}",
                            friendly_key="err_math") from e
    if action == "mat_lstsq":
        try:
            return sp.simplify(A.solve_least_squares(B))
        except Exception as e:  # noqa: BLE001
            raise MathError(f"最小二乘失败：{e}",
                            friendly_key="err_math") from e
    return A


def matrix_op(text, op="det"):
    return matrix_unary(op, text)


# ---------------------------------------------------------------------------
# 绘图采样
# ---------------------------------------------------------------------------

def _clean(arr):
    a = np.asarray(arr)
    if a.dtype == object:
        a = a.astype(complex)
    if np.iscomplexobj(a):
        a = np.where(np.abs(a.imag) < 1e-9, a.real, np.nan)
    try:
        return a.astype(float)
    except Exception:
        return np.full(a.shape, np.nan)


def sample_cartesian(expr, xmin, xmax, points=800, var="x"):
    v = sp.Symbol(var)
    e = _parse(expr)
    f = sp.lambdify(v, e, modules=["numpy"])
    xs = np.linspace(float(xmin), float(xmax), int(points))
    with np.errstate(all="ignore"):
        try:
            ys = f(xs)
        except Exception as ex:  # noqa: BLE001
            raise MathError(f"函数采样失败：{ex}",
                            friendly_key="err_math") from ex
    return xs, _clean(ys)


def sample_polar(expr, tmin, tmax, points=800, var="theta"):
    t = sp.Symbol(var)
    e = _parse(expr)
    f = sp.lambdify(t, e, modules=["numpy"])
    ts = np.linspace(float(tmin), float(tmax), int(points))
    with np.errstate(all="ignore"):
        try:
            rs = _clean(f(ts))
        except Exception as ex:  # noqa: BLE001
            raise MathError(f"函数采样失败：{ex}",
                            friendly_key="err_math") from ex
    return rs * np.cos(ts), rs * np.sin(ts)


def sample_parametric(xexpr, yexpr, tmin, tmax, points=800, var="t"):
    t = sp.Symbol(var)
    fx = sp.lambdify(t, _parse(xexpr), modules=["numpy"])
    fy = sp.lambdify(t, _parse(yexpr), modules=["numpy"])
    ts = np.linspace(float(tmin), float(tmax), int(points))
    with np.errstate(all="ignore"):
        try:
            xs = fx(ts)
            ys = fy(ts)
        except Exception as ex:  # noqa: BLE001
            raise MathError(f"函数采样失败：{ex}",
                            friendly_key="err_math") from ex
    return _clean(xs), _clean(ys)


def plot_data(expr, xmin, xmax, var="x", points=400):
    return sample_cartesian(expr, xmin, xmax, points, var)


# ---------------------------------------------------------------------------
# 统计
# ---------------------------------------------------------------------------

def stats_calc(text):
    try:
        nums = [float(x) for x in re.split(r"[\s,;]+", str(text).strip()) if x]
    except ValueError as e:
        raise InputError(f"数据含非法字符：{e}",
                         friendly_key="err_input") from e
    if not nums:
        raise InputError("没有数据", friendly_key="err_empty_data")
    arr = np.array(nums, dtype=float)
    return {
        "count": int(len(arr)),
        "mean": float(np.mean(arr)),
        "median": float(np.median(arr)),
        "std": float(np.std(arr, ddof=0)),
        "std_sample": float(np.std(arr, ddof=1)) if len(arr) > 1 else 0.0,
        "var": float(np.var(arr)),
        "min": float(np.min(arr)),
        "max": float(np.max(arr)),
        "range": float(np.max(arr) - np.min(arr)),
        "sum": float(np.sum(arr)),
        "q1": float(np.percentile(arr, 25)),
        "q3": float(np.percentile(arr, 75)),
    }


# ---------------------------------------------------------------------------
# 单位 / 进制
# ---------------------------------------------------------------------------

def unit_convert(value, from_unit, to_unit):
    try:
        q = float(value) * ureg(str(from_unit))
        return q.to(str(to_unit)).magnitude
    except Exception as e:  # noqa: BLE001
        raise UnitError(f"单位换算失败：{e}", friendly_key="err_unit") from e


_DIGITS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def base_convert(value, from_base, to_base):
    try:
        fb, tb = int(from_base), int(to_base)
    except ValueError as e:
        raise InputError("进制必须为整数",
                         friendly_key="err_base_range") from e
    if not (2 <= fb <= 36) or not (2 <= tb <= 36):
        raise InputError("进制范围应为 2~36", friendly_key="err_base_range")

    s = str(value).strip()
    if not s:
        raise InputError("数值为空", friendly_key="err_empty_expr")

    sign = ""
    if s[0] in "+-":
        sign, s = s[0], s[1:]

    if "." in s:
        raise InputError("暂不支持小数进制转换",
                         friendly_key="err_base_float")

    try:
        n = int(s, fb)
    except ValueError as e:
        raise InputError(f"非法字符：{e}",
                         friendly_key="err_base_char") from e

    if sign == "-":
        n = -n
    if tb == 10:
        return str(n)
    if n == 0:
        return "0"
    neg = n < 0
    n = abs(n)
    out = ""
    while n:
        out = _DIGITS[n % tb] + out
        n //= tb
    return ("-" if neg else "") + out


# ---------------------------------------------------------------------------
# 汇率（旧接口保留）
# ---------------------------------------------------------------------------

def fetch_rates(source="open.er-api.com"):
    if source == "open.er-api.com":
        try:
            r = requests.get("https://open.er-api.com/v6/latest/USD", timeout=10)
            data = r.json()
            if data.get("result") == "success":
                return data["rates"]
            raise NetworkError(data.get("error-type", "汇率获取失败"))
        except NetworkError:
            raise
        except Exception as e:  # noqa: BLE001
            raise NetworkError(str(e)) from e
    if source == "exchangerate.host":
        try:
            r = requests.get("https://api.exchangerate.host/latest", timeout=10)
            data = r.json()
            rates = data.get("rates")
            if not rates:
                raise NetworkError("汇率获取失败")
            return rates
        except NetworkError:
            raise
        except Exception as e:  # noqa: BLE001
            raise NetworkError(str(e)) from e
    raise NetworkError("未知汇率源")


def currency_convert(amount, from_cur, to_cur, rates):
    amount = float(amount)
    fc, tc = str(from_cur).upper(), str(to_cur).upper()
    if fc == tc:
        return amount
    if fc not in rates or tc not in rates:
        raise NetworkError(f"未知货币：{fc if fc not in rates else tc}",
                           friendly_key="err_currency")
    return amount / rates[fc] * rates[tc]


# ---------------------------------------------------------------------------
# 财务
# ---------------------------------------------------------------------------

def finance_loan(principal, annual_rate, years):
    p = float(principal)
    r = float(annual_rate) / 100 / 12
    n = int(float(years) * 12)
    if p < 0:
        raise InputError("本金不能为负", friendly_key="err_input")
    if n <= 0:
        raise InputError("年限必须大于 0", friendly_key="err_input")
    if r < 0:
        raise InputError("利率不能为负", friendly_key="err_input")
    if r == 0:
        m = p / n
    else:
        m = p * r * (1 + r) ** n / ((1 + r) ** n - 1)
    return {
        "monthly": m,
        "total": m * n,
        "interest": m * n - p,
        "months": n,
    }


def finance_compound(principal, annual_rate, years, times=1):
    p = float(principal)
    r = float(annual_rate) / 100
    t = float(years)
    try:
        m = int(times) if int(times) > 0 else 1
    except Exception:
        m = 1
    if p < 0 or t < 0 or r < 0:
        raise InputError("参数不能为负", friendly_key="err_input")
    return p * (1 + r / m) ** (m * t)


# ---------------------------------------------------------------------------
# 日期 / 随机
# ---------------------------------------------------------------------------

def date_diff(d1, d2):
    try:
        a = datetime.datetime.strptime(str(d1), "%Y-%m-%d").date()
        b = datetime.datetime.strptime(str(d2), "%Y-%m-%d").date()
    except ValueError as e:
        raise InputError(f"日期格式应为 YYYY-MM-DD：{e}",
                         friendly_key="err_input") from e
    return (b - a).days


def date_add(date_str, days):
    try:
        d = datetime.datetime.strptime(str(date_str), "%Y-%m-%d").date()
        n = int(days)
    except ValueError as e:
        raise InputError(f"日期或天数非法：{e}",
                         friendly_key="err_input") from e
    return (d + datetime.timedelta(days=n)).strftime("%Y-%m-%d")


def random_numbers(low, high, count=1, mode="int"):
    lo, hi, n = float(low), float(high), int(count)
    if n <= 0:
        raise InputError("数量必须大于 0", friendly_key="err_input")
    if lo > hi:
        raise InputError("最小值不能大于最大值", friendly_key="err_input")
    if mode == "int":
        return [random.randint(int(lo), int(hi)) for _ in range(n)]
    return [round(random.uniform(lo, hi), 10) for _ in range(n)]


# ===========================================================================
# 第三轮新增：基础 / 科学 / 进制 / 矩阵
# ===========================================================================

_PERCENT_PATTERNS = [
    (re.compile(r"^\s*([\d.]+)\s*%\s*off\s+([\d.]+)\s*$", re.I), "off"),
    (re.compile(r"^\s*([\d.]+)\s*%\s*on\s+([\d.]+)\s*$", re.I), "on"),
    (re.compile(r"^\s*([\d.]+)\s*%\s*of\s+([\d.]+)\s*$", re.I), "of"),
    (re.compile(r"^\s*tip\s+([\d.]+)\s*(?:%|percent)?\s+on\s+([\d.]+)\s*$",
                re.I), "tip"),
    (re.compile(r"^\s*tax\s+([\d.]+)\s*(?:%|percent)?\s+on\s+([\d.]+)\s*$",
                re.I), "tax"),
    (re.compile(r"^\s*discount\s+([\d.]+)\s*(?:%|percent)?\s+on\s+([\d.]+)\s*$",
                re.I), "off"),
]


def _percent_special(s: str):
    """识别 `X% of Y` 等语法。返回 (值, 描述) 或 None。"""
    for pat, kind in _PERCENT_PATTERNS:
        m = pat.match(s)
        if not m:
            continue
        a, b = float(m.group(1)), float(m.group(2))
        if kind == "off":
            return b * (1 - a / 100), f"{a}% off {b} = {b * (1 - a / 100)}"
        if kind == "on":
            return b * (1 + a / 100), f"{a}% on {b} = {b * (1 + a / 100)}"
        if kind == "of":
            return a / 100 * b, f"{a}% of {b} = {a / 100 * b}"
        if kind == "tip":
            return b + b * a / 100, (
                f"tip {a}% on {b} = {b * (1 + a / 100)} "
                f"(tip {b * a / 100})")
        if kind == "tax":
            return b + b * a / 100, (
                f"tax {a}% on {b} = {b * (1 + a / 100)} "
                f"(tax {b * a / 100})")
    m = re.match(r"^\s*([\d.]+)\s*%\s*$", s)
    if m:
        return float(m.group(1)) / 100, f"{m.group(1)}% = {float(m.group(1))/100}"
    return None


def basic_calc_smart(expr: str, angle_mode: str = "RAD"):
    """基础计算入口：先尝试百分比语法，失败则退回 basic_calc。

    返回 (值, 描述)；描述可能为 None。
    """
    s = _norm(expr)
    try:
        special = _percent_special(s)
    except Exception:
        special = None
    if special is not None:
        val, desc = special
        return _num(sp.N(sp.Float(val), 20)), desc
    return basic_calc(expr, angle_mode=angle_mode), None


def sci_complex_eval(expr):
    e = _parse(expr)
    try:
        return sp.N(e, 20)
    except Exception as ex:  # noqa: BLE001
        raise MathError(f"复数求值失败：{ex}") from ex


_INEQ_OPS = [
    (re.compile(r"<="), "<="),
    (re.compile(r">="), ">="),
    (re.compile(r"<(?!=)"), "<"),
    (re.compile(r">(?!=)"), ">"),
    (re.compile(r"=="), "=="),
]


def sci_solve_inequality(expr: str, var: str = "x"):
    s = str(expr).strip()
    if re.match(r"^\s*[\w\.]+\s*<=\s*[\w\.]+\s*<=\s*[\w\.]+\s*$", s):
        parts = re.split(r"<=", s)
        a, b, c = parts
        e1 = _parse(a) - _parse(b)
        e2 = _parse(b) - _parse(c)
        v = sp.Symbol(var.strip() or "x")
        from sympy import solve_univariate_inequality as sui
        try:
            return sp.And(sui(e1 <= 0, v, relational=False),
                          sui(e2 <= 0, v, relational=False))
        except Exception:
            pass

    for pat, op in _INEQ_OPS:
        if pat.search(s):
            left, right = pat.split(s, maxsplit=1)
            e = _parse(left) - _parse(right)
            v = sp.Symbol(var.strip() or "x")
            try:
                from sympy import solve_univariate_inequality as sui
                rel = {"<": sp.Lt, "<=": sp.Le,
                       ">": sp.Gt, ">=": sp.Ge}.get(op)
                if rel is None:
                    return sp.solve(e, v)
                expr_rel = rel(e, 0)
                return sui(expr_rel, v, relational=False)
            except Exception as ex:  # noqa: BLE001
                raise MathError(f"不等式求解失败：{ex}",
                                friendly_key="err_math") from ex
    return sci_solve(expr, var)


_SERIES_KINDS = {
    "taylor":  "series",
    "fps":     "fps",
    "laurent": "laurent",
    "asin":    "asin",
    "acos":    "acos",
    "atan":    "atan",
    "log":     "log",
    "exp":     "exp",
}


def sci_series_ext(expr, var: str = "x", point: str = "0",
                   order: int = 6, kind: str = "taylor"):
    v = sp.Symbol(var.strip() or "x")
    e = _parse(expr)
    n = int(order)
    p = _parse(point or "0")
    try:
        if kind == "taylor":
            return sp.series(e, v, p, n).removeO()
        if kind in ("asin", "acos", "atan", "log", "exp"):
            fn = getattr(sp, kind)
            return fn(e).series(v, p, n).removeO()
        if kind == "fps":
            return sp.fps(e, v, p, n).truncate()
        if kind == "laurent":
            return sp.series(e, v, p, n)
    except Exception as ex:  # noqa: BLE001
        raise MathError(f"级数展开失败：{ex}", friendly_key="err_math") from ex
    return sp.series(e, v, p, n).removeO()


def sci_steps_solve(expr: str, var: str = "x"):
    s = str(expr).strip()
    if "=" in s:
        left, right = s.split("=", 1)
        e = _parse(left) - _parse(right)
    else:
        e = _parse(s)
    v = sp.Symbol(var.strip() or "x")
    steps = [f"原始方程：{s}"]
    try:
        moved = sp.expand(e)
        steps.append(f"整理：{sp.pretty(moved)}")
    except Exception:
        moved = e
    try:
        factored = sp.factor(moved)
        if factored != moved:
            steps.append(f"因式分解：{factored} = 0")
    except Exception:
        pass
    try:
        sols = sp.solve(moved, v)
        steps.append(f"解：{v} = {sols}")
    except Exception as ex:
        raise MathError(f"求解失败：{ex}", friendly_key="err_math") from ex
    return sols, steps


def _digits_val(c: str) -> int:
    return _DIGITS.index(c.upper()) if c.upper() in _DIGITS else -1


def base_convert_float(value, from_base, to_base, precision: int = 12):
    try:
        fb, tb = int(from_base), int(to_base)
    except ValueError as e:
        raise InputError("进制必须为整数",
                         friendly_key="err_base_range") from e
    if not (2 <= fb <= 36) or not (2 <= tb <= 36):
        raise InputError("进制范围应为 2~36", friendly_key="err_base_range")

    s = str(value).strip()
    if not s:
        raise InputError("数值为空", friendly_key="err_empty_expr")

    sign = ""
    if s[0] in "+-":
        sign, s = s[0], s[1:]

    if "." in s:
        int_part, frac_part = s.split(".", 1)
    else:
        int_part, frac_part = s, ""

    try:
        n = int(int_part or "0", fb)
    except ValueError as e:
        raise InputError(f"非法字符：{e}", friendly_key="err_base_char") from e

    frac = 0.0
    for i, c in enumerate(frac_part):
        d = _digits_val(c)
        if d < 0 or d >= fb:
            raise InputError(f"非法字符：{c!r}", friendly_key="err_base_char")
        frac += d / (fb ** (i + 1))

    if tb == 10:
        val = n + frac
        if frac:
            out = f"{val:.{precision}f}".rstrip("0").rstrip(".")
        else:
            out = str(n)
        return ("-" if sign == "-" else "") + out

    if n == 0:
        int_out = "0"
    else:
        buf = []
        m = n
        while m:
            buf.append(_DIGITS[m % tb])
            m //= tb
        int_out = "".join(reversed(buf))

    frac_out = ""
    if frac > 0:
        f = frac
        for _ in range(precision):
            f *= tb
            d = int(f)
            frac_out += _DIGITS[d]
            f -= d
            if f < 1e-12:
                break
        frac_out = frac_out.rstrip("0")
        if frac_out:
            frac_out = "." + frac_out

    result = int_out + frac_out
    if n == 0 and not frac_out:
        result = "0"
    return ("-" if sign == "-" else "") + result


def ascii_convert(text, mode: str = "encode"):
    if mode == "encode":
        s = str(text)
        if not s:
            return ""
        codes = [str(ord(ch)) for ch in s]
        hexes = [format(ord(ch), "X") for ch in s]
        lines = [
            "字符  十进制  十六进制",
            "─" * 30,
        ]
        for ch, c, h in zip(s, codes, hexes):
            lines.append(f"{ch!r:>5}  {c:>6}  0x{h}")
        lines.append("")
        lines.append("十进制: " + " ".join(codes))
        lines.append("十六进制: " + " ".join("0x" + h for h in hexes))
        return "\n".join(lines)

    raw = re.split(r"[\s,;]+", str(text).strip())
    codes = []
    for tok in raw:
        if not tok:
            continue
        try:
            if tok.lower().startswith("0x"):
                codes.append(int(tok, 16))
            elif tok.lower().startswith("u+"):
                codes.append(int(tok[2:], 16))
            else:
                codes.append(int(tok))
        except ValueError:
            continue
    try:
        return "".join(chr(c) for c in codes)
    except Exception as e:  # noqa: BLE001
        raise InputError(f"码点非法：{e}", friendly_key="err_input") from e


def endian_swap(value, width: int = 32):
    try:
        w = int(width)
    except Exception:
        raise InputError("位宽非法", friendly_key="err_input")
    if w <= 0 or w % 8 != 0:
        raise InputError("位宽须为 8 的正数倍", friendly_key="err_input")
    nbytes = w // 8
    v = int(value) & ((1 << w) - 1)
    be_bytes = v.to_bytes(nbytes, "big", signed=False)
    le_bytes = be_bytes[::-1]
    swapped = int.from_bytes(be_bytes, "little", signed=False)
    return (
        swapped,
        be_bytes.hex().upper(),
        le_bytes.hex().upper(),
    )


def float_ieee754(value):
    import struct
    try:
        v = float(value)
    except Exception as e:
        raise InputError(f"非法浮点数：{e}", friendly_key="err_input") from e
    f32 = struct.pack(">f", v)
    f64 = struct.pack(">d", v)
    b32 = "".join(f"{b:08b}" for b in f32)
    b64 = "".join(f"{b:08b}" for b in f64)
    return {
        "float32_bin": b32,
        "float32_hex": "0x" + f32.hex().upper(),
        "float64_bin": b64,
        "float64_hex": "0x" + f64.hex().upper(),
    }


def matrix_random(rows: int, cols: int, kind: str = "int",
                  low=-9, high=9, seed=None):
    r, c = int(rows), int(cols)
    if r <= 0 or c <= 0:
        raise InputError("行列数须为正整数", friendly_key="err_input")
    rng = random.Random(seed)
    if kind == "int":
        lo, hi = int(low), int(high)
        return sp.Matrix(r, c, lambda i, j: rng.randint(lo, hi))
    if kind == "float":
        lo, hi = float(low), float(high)
        return sp.Matrix(r, c,
                         lambda i, j: round(rng.uniform(lo, hi), 4))
    if kind == "sym":
        names = ["a", "b", "c", "d", "x", "y", "z", "u", "v", "w"]
        return sp.Matrix(r, c,
                         lambda i, j: sp.Symbol(
                             f"{rng.choice(names)}{i+1}{j+1}"))
    raise InputError(f"未知类型：{kind}", friendly_key="err_input")


def matrix_from_csv_text(text: str):
    lines = [ln for ln in str(text).strip().splitlines() if ln.strip()]
    if not lines:
        raise InputError("CSV 为空", friendly_key="err_input")
    rows = []
    for ln in lines:
        if "\t" in ln:
            cells = ln.split("\t")
        elif "," in ln:
            cells = ln.split(",")
        elif ";" in ln:
            cells = ln.split(";")
        else:
            cells = ln.split()
        rows.append([c.strip() for c in cells if c.strip() != ""])
    maxlen = max(len(r) for r in rows)
    for r in rows:
        while len(r) < maxlen:
            r.append("0")
    return sp.Matrix([[sp.sympify(c) for c in r] for r in rows])


def matrix_to_csv_text(A: sp.MatrixBase) -> str:
    lines = []
    for i in range(A.rows):
        lines.append(",".join(str(A[i, j]) for j in range(A.cols)))
    return "\n".join(lines)


def matrix_solve_linear(A_text, b_text):
    A = _parse_matrix(A_text)
    try:
        b = _parse_matrix(b_text)
    except Exception:
        raw = re.split(r"[\s,;]+", str(b_text).strip())
        b = sp.Matrix([sp.sympify(x) for x in raw if x])

    steps = [f"A 形状：{A.rows}×{A.cols}",
             f"b 形状：{b.rows}×{b.cols}"]
    if A.rows != A.cols:
        steps.append("A 非方阵，使用最小二乘/伪逆")
        try:
            sol = A.solve(b)
            steps.append(f"解：{sol}")
            return sol, steps
        except Exception as e:
            raise MathError(f"求解失败：{e}", friendly_key="err_math") from e

    det = sp.simplify(A.det())
    steps.append(f"det(A) = {det}")
    try:
        if det == 0:
            steps.append("行列式为 0，可能无解或无穷多解")
        sol = A.solve(b)
        steps.append(f"解：{sol}")
        return sol, steps
    except Exception as e:
        raise MathError(f"求解失败：{e}", friendly_key="err_math") from e


def matrix_inv_steps(A_text):
    A = _parse_matrix(A_text)
    if A.rows != A.cols:
        raise MathError("非方阵无法求逆", friendly_key="err_math")
    steps = [f"A 形状：{A.rows}×{A.cols}"]
    det = sp.simplify(A.det())
    steps.append(f"det(A) = {det}")
    if _is_singular(A):
        raise MathError("奇异矩阵不可逆", friendly_key="err_math")
    try:
        _adj = sp.simplify(A.adjugate())
        steps.append("伴随矩阵 adj(A) 已计算")
        inv = sp.simplify(A.inv())
        steps.append("A⁻¹ = adj(A)/det(A)")
        return inv, steps
    except Exception as e:
        raise MathError(f"求逆失败：{e}", friendly_key="err_math") from e


def _parse_lambda2(expr_text, vars_=("x", "y")):
    syms = [sp.Symbol(v) for v in vars_]
    e = _parse(expr_text)
    f = sp.lambdify(syms, e, modules=["numpy"])
    return lambda X, Y: f(X, Y)


# ===========================================================================
# 第五轮新增：概率注册 / 3D 采样 / 插件桥
# ===========================================================================

def prob_fit(name, data):
    from core import probability as prob
    return prob.fit_distribution(name, data)


def prob_ci(data, alpha=0.05, sigma=None):
    from core import probability as prob
    return prob.confidence_interval_mean(data, alpha, sigma)


def prob_anova(*groups):
    from core import probability as prob
    return prob.anova_oneway(*groups)


def prob_chi2_ind(table):
    from core import probability as prob
    return prob.chi2_independence(table)


def prob_multi_regression(X, y):
    from core import probability as prob
    return prob.multiple_regression(X, y)


def sample_surface(expr, xmin, xmax, ymin, ymax,
                   nx=60, ny=60, var_x="x", var_y="y"):
    vx = sp.Symbol(var_x)
    vy = sp.Symbol(var_y)
    e = _parse(expr)
    f = sp.lambdify((vx, vy), e, modules=["numpy"])
    xs = np.linspace(float(xmin), float(xmax), int(nx))
    ys = np.linspace(float(ymin), float(ymax), int(ny))
    X, Y = np.meshgrid(xs, ys)
    with np.errstate(all="ignore"):
        try:
            Z = f(X, Y)
        except Exception as ex:  # noqa: BLE001
            raise MathError(f"曲面采样失败：{ex}",
                            friendly_key="err_math") from ex
    Z = np.asarray(Z, dtype=float)
    Z[~np.isfinite(Z)] = np.nan
    return X, Y, Z


# ===========================================================================
# 第六轮新增：ODE / 数值积分 / 优化
# ===========================================================================

def sci_dsolve(eq_str, func="y", var="x", ics=None):
    x = sp.Symbol(var)
    y = sp.Function(func)

    s = str(eq_str).strip()
    if "=" in s:
        lhs, rhs = s.split("=", 1)
        s = f"({lhs}) - ({rhs})"

    ph2 = "__ODED2__"
    ph1 = "__ODED1__"
    s = re.sub(rf"\b{func}''+", ph2, s)
    s = re.sub(rf"\b{func}'", ph1, s)
    s = re.sub(rf"\b{func}\b(?!\s*\()", f"{func}({var})", s)
    s = s.replace(ph2, f"Derivative({func}({var}), {var}, 2)")
    s = s.replace(ph1, f"Derivative({func}({var}), {var})")

    local = dict(_LOCALS)
    local[var] = x
    local[func] = y
    try:
        e = parse_expr(s, local_dict=local, transformations=_TRANSFORMS)
    except Exception as ex:
        raise InputError(f"ODE 解析失败：{ex}",
                         friendly_key="err_parse") from ex

    kwargs = {}
    if ics:
        kwargs["ics"] = ics
    try:
        sol = sp.dsolve(e, y(x), **kwargs)
    except Exception as ex:
        raise MathError(f"dsolve 失败：{ex}",
                        friendly_key="err_math") from ex
    return sol


def sci_quad(expr, var="x", lower=0, upper=1):
    v = sp.Symbol(var)
    e = _parse(expr)
    try:
        f = sp.lambdify(v, e, modules=["numpy", "scipy"])
    except Exception as ex:
        raise MathError(f"lambdify 失败：{ex}",
                        friendly_key="err_math") from ex
    from scipy import integrate as _si
    try:
        val, err = _si.quad(f, float(lower), float(upper))
    except Exception as ex:
        raise MathError(f"数值积分失败：{ex}",
                        friendly_key="err_math") from ex
    return {"value": float(val), "estimated_error": float(err)}


def sci_minimize(expr, var="x", x0=0, method="BFGS"):
    v = sp.Symbol(var)
    e = _parse(expr)
    try:
        f = sp.lambdify(v, e, modules=["numpy"])
    except Exception as ex:
        raise MathError(f"lambdify 失败：{ex}",
                        friendly_key="err_math") from ex
    from scipy.optimize import minimize as _min
    try:
        res = _min(lambda a: float(f(a[0])), [float(x0)], method=method)
    except Exception as ex:
        raise MathError(f"优化失败：{ex}",
                        friendly_key="err_math") from ex
    return {
        "x": float(res.x[0]),
        "minimum": float(res.fun),
        "success": bool(res.success),
        "message": str(res.message),
        "iterations": int(getattr(res, "nit", 0)),
    }


def sci_linprog(params_json):
    try:
        p = (_json.loads(params_json) if isinstance(params_json, str)
             else params_json)
    except Exception as ex:
        raise InputError(f"JSON 解析失败：{ex}",
                         friendly_key="err_input") from ex

    try:
        c = [float(x) for x in p.get("c", [])]
        A_ub = [[float(v) for v in row] for row in p.get("A_ub", [])] or None
        b_ub = [float(x) for x in p.get("b_ub", [])] or None
        bounds = p.get("bounds")
        if bounds:
            bounds = [
                (float(b[0]) if b[0] is not None else None,
                 float(b[1]) if b[1] is not None else None)
                for b in bounds
            ]
    except Exception as ex:
        raise InputError(f"参数非法：{ex}",
                         friendly_key="err_input") from ex

    from scipy.optimize import linprog
    try:
        res = linprog(c, A_ub=A_ub, b_ub=b_ub, bounds=bounds, method="highs")
    except Exception as ex:
        raise MathError(f"linprog 失败：{ex}",
                        friendly_key="err_math") from ex
    return {
        "x": [float(v) for v in res.x] if res.x is not None else [],
        "fun": float(res.fun) if res.fun is not None else None,
        "success": bool(res.success),
        "message": str(res.message),
    }