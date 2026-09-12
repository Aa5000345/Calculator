import re
import json
import math
import random
import datetime

import sympy as sp
import numpy as np
import requests
from pint import UnitRegistry

ureg = UnitRegistry()


def _to_sympy(expr):
    expr = expr.replace("^", "**")
    expr = expr.replace("π", "pi")
    expr = re.sub(r"(\d+)!", r"factorial(\1)", expr)
    return sp.sympify(expr, locals={
        "sin": sp.sin,
        "cos": sp.cos,
        "tan": sp.tan,
        "asin": sp.asin,
        "acos": sp.acos,
        "atan": sp.atan,
        "log": sp.log,
        "ln": sp.log,
        "exp": sp.exp,
        "sqrt": sp.sqrt,
        "factorial": sp.factorial,
        "pi": sp.pi,
        "E": sp.E,
        "I": sp.I,
    })


def basic_calc(expr):
    return sp.N(_to_sympy(expr))


def scientific_calc(expr):
    return _to_sympy(expr)


def format_result(obj, fmt="text"):
    try:
        if fmt == "latex":
            return sp.latex(obj)
        if fmt == "unicode":
            return sp.pretty(obj, use_unicode=True)
    except Exception:
        pass
    return str(obj)


def solve_equation(eq, var="x"):
    if "=" in eq:
        left, right = eq.split("=", 1)
        expr = _to_sympy(left) - _to_sympy(right)
    else:
        expr = _to_sympy(eq)
    v = sp.Symbol(var)
    return sp.solve(expr, v)


def integrate_expr(expr, var="x", lower=None, upper=None):
    v = sp.Symbol(var)
    e = _to_sympy(expr)
    if lower is not None and upper is not None:
        return sp.integrate(e, (v, sp.sympify(lower), sp.sympify(upper)))
    return sp.integrate(e, v)


def diff_expr(expr, var="x", n=1):
    v = sp.Symbol(var)
    return sp.diff(_to_sympy(expr), v, int(n))


def limit_expr(expr, var="x", point="0"):
    v = sp.Symbol(var)
    return sp.limit(_to_sympy(expr), v, sp.sympify(point))


def matrix_op(text, op="det"):
    m = sp.Matrix(sp.sympify(text))
    if op == "det":
        return m.det()
    if op == "inv":
        return m.inv()
    if op == "transpose":
        return m.T
    if op == "eigenvals":
        return m.eigenvals()
    if op == "eigenvects":
        return m.eigenvects()
    if op == "rref":
        return m.rref()
    if op == "rank":
        return m.rank()
    return m


def stats_calc(text):
    nums = [float(x) for x in re.split(r"[\s,;]+", text.strip()) if x]
    arr = np.array(nums)
    return {
        "count": len(arr),
        "mean": float(np.mean(arr)),
        "median": float(np.median(arr)),
        "std": float(np.std(arr)),
        "var": float(np.var(arr)),
        "min": float(np.min(arr)),
        "max": float(np.max(arr)),
        "sum": float(np.sum(arr)),
    }


def plot_data(expr, xmin, xmax, var="x", points=400):
    v = sp.Symbol(var)
    e = _to_sympy(expr)
    f = sp.lambdify(v, e, "numpy")
    xs = np.linspace(float(xmin), float(xmax), int(points))
    ys = f(xs)
    return xs, ys


def unit_convert(value, from_unit, to_unit):
    q = float(value) * ureg(from_unit)
    return q.to(to_unit).magnitude


def base_convert(value, from_base, to_base):
    n = int(str(value), int(from_base))
    if int(to_base) == 10:
        return str(n)

    digits = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    if n == 0:
        return "0"

    sign = "-" if n < 0 else ""
    n = abs(n)
    out = ""
    while n:
        out = digits[n % int(to_base)] + out
        n //= int(to_base)
    return sign + out


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
        return data["rates"]

    raise RuntimeError("未知汇率源")


def currency_convert(amount, from_cur, to_cur, rates):
    amount = float(amount)
    if from_cur == to_cur:
        return amount
    return amount / rates[from_cur] * rates[to_cur]


def finance_loan(principal, annual_rate, years):
    p = float(principal)
    r = float(annual_rate) / 100 / 12
    n = int(float(years) * 12)
    if r == 0:
        m = p / n
    else:
        m = p * r * (1 + r) ** n / ((1 + r) ** n - 1)
    return {
        "monthly": m,
        "total": m * n,
        "interest": m * n - p,
    }


def finance_compound(principal, annual_rate, years, times=1):
    p = float(principal)
    r = float(annual_rate) / 100
    t = float(years)
    m = int(times)
    return p * (1 + r / m) ** (m * t)


def date_diff(d1, d2):
    a = datetime.datetime.strptime(d1, "%Y-%m-%d").date()
    b = datetime.datetime.strptime(d2, "%Y-%m-%d").date()
    return (b - a).days


def date_add(date_str, days):
    d = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
    return (d + datetime.timedelta(days=int(days))).strftime("%Y-%m-%d")


def random_numbers(low, high, count=1, mode="int"):
    low, high, count = float(low), float(high), int(count)
    if mode == "int":
        return [random.randint(int(low), int(high)) for _ in range(count)]
    return [random.uniform(low, high) for _ in range(count)]