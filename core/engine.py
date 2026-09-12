"""计算内核：科学计算 / 线性代数 / 绘图采样 / 单位 / 汇率 / 财务 / 日期 / 随机数"""
from __future__ import annotations

import datetime
import json
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

ureg = UnitRegistry()

# ---------------------------------------------------------------------------
# 表达式解析
# ---------------------------------------------------------------------------

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

_TRANSFORMS = standard_transformations + (implicit_multiplication_application,)


def _norm(expr) -> str:
    s = str(expr).strip()
    s = (s.replace("π", "pi").replace("×", "*").replace("÷", "/")
          .replace("−", "-").replace("^", "**")
          .replace("≤", "<=").replace("≥", ">="))
    s = re.sub(r"(\d+)\s*!", r"factorial(\1)", s)
    return s


def _parse(expr, extra=None):
    s = _norm(expr)
    if not s:
        raise ValueError("表达式为空")
    local = dict(_LOCALS)
    if extra:
        local.update(extra)
    return parse_expr(s, local_dict=local, transformations=_TRANSFORMS)


def _num(obj, digits: int = 15):
    val = sp.N(obj, digits)
    try:
        if val.is_number and val.is_real:
            f = float(val)
            if abs(f - round(f)) < 1e-12 and abs(f) < 1e15:
                return int(round(f))
            return f
    except Exception:
        pass
    return val


# ---------------------------------------------------------------------------
# 结果格式化（text / unicode / latex）
# ---------------------------------------------------------------------------

def format_result(obj, fmt: str = "text") -> str:
    if obj is None:
        return ""
    if isinstance(obj, str):
        return obj
    if isinstance(obj, bool):
        return str(obj)

    try:
        if isinstance(obj, dict):
            if fmt == "latex":
                return r",\quad ".join(
                    f"{sp.latex(k)} = {sp.latex(v)}" for k, v in obj.items())
            if fmt == "unicode":
                return ",  ".join(
                    f"{k} = {sp.pretty(v, use_unicode=True)}" for k, v in obj.items())
            return ",  ".join(f"{k} = {v}" for k, v in obj.items())

        if isinstance(obj, (list, tuple, set)):
            items = list(obj)
            if not items:
                return "[]"
            if all(isinstance(x, dict) for x in items):
                return "\n".join(format_result(x, fmt) for x in items)
            if fmt == "latex":
                return r",\quad ".join(sp.latex(x) for x in items)
            if fmt == "unicode":
                return "\n".join(sp.pretty(x, use_unicode=True) for x in items)
            return ",  ".join(str(x) for x in items)

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

def basic_calc(expr):
    return _num(_parse(expr))


def scientific_calc(expr):
    return _parse(expr)


def sci_eval(expr):
    return _num(_parse(expr))


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
    return sp.series(_parse(expr), v, _parse(point or "0"), int(order)).removeO()


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
        raise ValueError("矩阵为空")
    if "[" not in s and (";" in s or "\n" in s):
        rows = [r for r in re.split(r"[;\n]+", s) if r.strip()]
        data = [[_parse(x) for x in r.split(",")] for r in rows]
        return sp.Matrix(data)
    return sp.Matrix(_parse(s))


def matrix_unary(action: str, text: str, scalar=None):
    A = _parse_matrix(text)
    if action == "det":
        return sp.simplify(A.det())
    if action == "inv":
        return sp.simplify(A.inv())
    if action == "transpose":
        return A.T
    if action == "trace":
        return sp.simplify(A.trace())
    if action == "rank":
        return A.rank()
    if action == "rref":
        return A.rref()[0]
    if action == "eigenvals":
        return A.eigenvals()
    if action == "eigenvects":
        return A.eigenvects()
    if action == "charpoly":
        lam = sp.Symbol("lambda")
        return sp.simplify(A.charpoly(lam).as_expr())
    if action == "adjugate":
        return sp.simplify(A.adjugate())
    if action == "nullspace":
        return A.nullspace()
    if action == "columnspace":
        return A.columnspace()
    if action == "rowspace":
        return A.rowspace()
    if action == "lu":
        L, U, perm = A.LUdecomposition()
        return {"L": L, "U": U, "perm": sp.Matrix([list(perm)]) if perm else sp.Matrix([[0]])}
    if action == "qr":
        Q, R = A.QRdecomposition()
        return {"Q": Q, "R": R}
    if action == "exp":
        return sp.simplify(A.exp())
    if action == "norm":
        return sp.simplify(A.norm())
    if action == "power":
        n = int(scalar) if scalar not in (None, "") else 1
        return sp.simplify(A ** n)
    return A


def matrix_binary(action: str, a_text: str, b_text: str):
    A = _parse_matrix(a_text)
    B = _parse_matrix(b_text)
    if action == "mat_add":
        return sp.simplify(A + B)
    if action == "mat_sub":
        return sp.simplify(A - B)
    if action == "mat_mul":
        return sp.simplify(A * B)
    if action == "mat_hadamard":
        if A.shape != B.shape:
            raise ValueError("Hadamard 积要求两个矩阵同型")
        return sp.Matrix(A.shape[0], A.shape[1],
                         lambda i, j: sp.simplify(A[i, j] * B[i, j]))
    if action == "mat_kron":
        return sp.Matrix(sp.kronecker_product(A, B))
    if action == "mat_solve":
        return sp.simplify(A.solve(B))
    if action == "mat_lstsq":
        return sp.simplify(A.solve_least_squares(B))
    return A


def matrix_op(text, op="det"):
    """兼容旧接口"""
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
        ys = f(xs)
    return xs, _clean(ys)


def sample_polar(expr, tmin, tmax, points=800, var="theta"):
    t = sp.Symbol(var)
    e = _parse(expr)
    f = sp.lambdify(t, e, modules=["numpy"])
    ts = np.linspace(float(tmin), float(tmax), int(points))
    with np.errstate(all="ignore"):
        rs = _clean(f(ts))
    return rs * np.cos(ts), rs * np.sin(ts)


def sample_parametric(xexpr, yexpr, tmin, tmax, points=800, var="t"):
    t = sp.Symbol(var)
    fx = sp.lambdify(t, _parse(xexpr), modules=["numpy"])
    fy = sp.lambdify(t, _parse(yexpr), modules=["numpy"])
    ts = np.linspace(float(tmin), float(tmax), int(points))
    with np.errstate(all="ignore"):
        xs = fx(ts)
        ys = fy(ts)
    return _clean(xs), _clean(ys)


def plot_data(expr, xmin, xmax, var="x", points=400):
    """兼容旧接口"""
    return sample_cartesian(expr, xmin, xmax, points, var)


# ---------------------------------------------------------------------------
# 统计
# ---------------------------------------------------------------------------

def stats_calc(text):
    nums = [float(x) for x in re.split(r"[\s,;]+", str(text).strip()) if x]
    if not nums:
        raise ValueError("没有数据")
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
    q = float(value) * ureg(str(from_unit))
    return q.to(str(to_unit)).magnitude


_DIGITS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def base_convert(value, from_base, to_base):
    fb, tb = int(from_base), int(to_base)
    n = int(str(value), fb)
    if tb == 10:
        return str(n)
    if n == 0:
        return "0"
    sign = "-" if n < 0 else ""
    n = abs(n)
    out = ""
    while n:
        out = _DIGITS[n % tb] + out
        n //= tb
    return sign + out


# ---------------------------------------------------------------------------
# 汇率
# ---------------------------------------------------------------------------

def fetch_rates(source="open.er-api.com"):
    if source == "open.er-api.com":
        r = requests.get("https://open.er-api.com/v6/latest/USD", timeout=10)
        data = r.json()
        if data.get("result") == "success":
            return data["rates"]
        raise RuntimeError(data.get("error-type", "汇率获取失败"))
    if source == "exchangerate.host":
        r = requests.get("https://api.exchangerate.host/latest", timeout=10)
        data = r.json()
        rates = data.get("rates")
        if not rates:
            raise RuntimeError("汇率获取失败")
        return rates
    raise RuntimeError("未知汇率源")


def currency_convert(amount, from_cur, to_cur, rates):
    amount = float(amount)
    fc, tc = str(from_cur).upper(), str(to_cur).upper()
    if fc == tc:
        return amount
    if fc not in rates or tc not in rates:
        raise KeyError(f"未知货币：{fc if fc not in rates else tc}")
    return amount / rates[fc] * rates[tc]


# ---------------------------------------------------------------------------
# 财务
# ---------------------------------------------------------------------------

def finance_loan(principal, annual_rate, years):
    p = float(principal)
    r = float(annual_rate) / 100 / 12
    n = int(float(years) * 12)
    if n <= 0:
        raise ValueError("年限必须大于 0")
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
    m = int(times) if int(times) > 0 else 1
    return p * (1 + r / m) ** (m * t)


# ---------------------------------------------------------------------------
# 日期 / 随机
# ---------------------------------------------------------------------------

def date_diff(d1, d2):
    a = datetime.datetime.strptime(str(d1), "%Y-%m-%d").date()
    b = datetime.datetime.strptime(str(d2), "%Y-%m-%d").date()
    return (b - a).days


def date_add(date_str, days):
    d = datetime.datetime.strptime(str(date_str), "%Y-%m-%d").date()
    return (d + datetime.timedelta(days=int(days))).strftime("%Y-%m-%d")


def random_numbers(low, high, count=1, mode="int"):
    lo, hi, n = float(low), float(high), int(count)
    if n <= 0:
        raise ValueError("数量必须大于 0")
    if mode == "int":
        return [random.randint(int(lo), int(hi)) for _ in range(n)]
    return [round(random.uniform(lo, hi), 10) for _ in range(n)]
