"""绘图采样：从 core.engine 拆出的独立模块。

为了不破坏旧接口，core.engine 仍保留同名函数（向后兼容）；
新代码请优先从本模块导入，逐步把 engine 的采样函数迁出。
"""
from __future__ import annotations

import numpy as np
import sympy as sp
from sympy.parsing.sympy_parser import (
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)


_TRANSFORMS = standard_transformations + (implicit_multiplication_application,)

_LOCALS = {
    "sin": sp.sin, "cos": sp.cos, "tan": sp.tan,
    "asin": sp.asin, "acos": sp.acos, "atan": sp.atan,
    "sinh": sp.sinh, "cosh": sp.cosh, "tanh": sp.tanh,
    "log": sp.log, "ln": sp.log, "log10": lambda x: sp.log(x, 10),
    "exp": sp.exp, "sqrt": sp.sqrt, "cbrt": sp.cbrt,
    "Abs": sp.Abs, "abs": sp.Abs,
    "sign": sp.sign, "floor": sp.floor, "ceil": sp.ceiling,
    "pi": sp.pi, "E": sp.E, "I": sp.I, "oo": sp.oo,
}


def _norm(expr) -> str:
    s = str(expr).strip()
    s = (s.replace("π", "pi").replace("×", "*").replace("÷", "/")
          .replace("−", "-").replace("^", "**"))
    return s


def _parse(expr):
    return parse_expr(_norm(expr), local_dict=dict(_LOCALS),
                      transformations=_TRANSFORMS)


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
    """直角坐标采样：返回 (xs, ys)。"""
    v = sp.Symbol(var)
    e = _parse(expr)
    f = sp.lambdify(v, e, modules=["numpy"])
    xs = np.linspace(float(xmin), float(xmax), int(points))
    with np.errstate(all="ignore"):
        try:
            ys = f(xs)
        except Exception as ex:  # noqa: BLE001
            raise RuntimeError(f"函数采样失败：{ex}") from ex
    return xs, _clean(ys)


def sample_polar(expr, tmin, tmax, points=800, var="theta"):
    """极坐标采样：返回 (xs, ys)。"""
    t = sp.Symbol(var)
    e = _parse(expr)
    f = sp.lambdify(t, e, modules=["numpy"])
    ts = np.linspace(float(tmin), float(tmax), int(points))
    with np.errstate(all="ignore"):
        try:
            rs = _clean(f(ts))
        except Exception as ex:  # noqa: BLE001
            raise RuntimeError(f"函数采样失败：{ex}") from ex
    return rs * np.cos(ts), rs * np.sin(ts)


def sample_parametric(xexpr, yexpr, tmin, tmax, points=800, var="t"):
    """参数方程采样：返回 (xs, ys)。"""
    t = sp.Symbol(var)
    fx = sp.lambdify(t, _parse(xexpr), modules=["numpy"])
    fy = sp.lambdify(t, _parse(yexpr), modules=["numpy"])
    ts = np.linspace(float(tmin), float(tmax), int(points))
    with np.errstate(all="ignore"):
        try:
            xs = fx(ts)
            ys = fy(ts)
        except Exception as ex:  # noqa: BLE001
            raise RuntimeError(f"函数采样失败：{ex}") from ex
    return _clean(xs), _clean(ys)


def _parse_lambda2(expr_text, vars_=("x", "y")):
    """返回 f(X, Y) —— 用于隐函数 contour。"""
    syms = [sp.Symbol(v) for v in vars_]
    e = _parse(expr_text)
    f = sp.lambdify(syms, e, modules=["numpy"])
    return lambda X, Y: f(X, Y)


def sample_surface(expr, xmin, xmax, ymin, ymax,
                   nx=60, ny=60, var_x="x", var_y="y"):
    """3D 曲面采样：返回 (X, Y, Z)。"""
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
            raise RuntimeError(f"曲面采样失败：{ex}") from ex
    Z = np.asarray(Z, dtype=float)
    Z[~np.isfinite(Z)] = np.nan
    return X, Y, Z


__all__ = [
    "sample_cartesian",
    "sample_polar",
    "sample_parametric",
    "sample_surface",
    "_parse_lambda2",
]