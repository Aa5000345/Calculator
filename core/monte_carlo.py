"""蒙特卡洛方法：积分、期望、方差、π 估算。

设计：
- 纯 numpy，无外部依赖
- 支持进度回调与取消
- 返回结果 + 估计误差

对外接口：
    estimate_pi(n)
    integrate_1d(fn, a, b, n)
    integrate_nd(fn, bounds, n)
    expectation(sample_fn, g, n)
    variance_reduction_antithetic(fn, a, b, n)
"""
from __future__ import annotations

import math
from typing import Callable, Optional

import numpy as np

from core.errors import InputError


# ---------------------------------------------------------------------------
# π 估算
# ---------------------------------------------------------------------------

def estimate_pi(n: int = 1_000_000,
                seed: Optional[int] = None) -> dict:
    """用 Monte Carlo 估算 π。

    方法：在 [-1,1]² 内撒 n 个点，落在单位圆内的比例 × 4。
    """
    n = int(n)
    if n <= 0:
        raise InputError("n 必须 > 0")
    rng = np.random.default_rng(seed)
    x = rng.uniform(-1, 1, n)
    y = rng.uniform(-1, 1, n)
    inside = (x * x + y * y) <= 1.0
    k = int(inside.sum())
    pi_est = 4.0 * k / n
    # 标准误
    p = k / n
    se = 4.0 * math.sqrt(p * (1 - p) / n)
    return {
        "pi_estimate": pi_est,
        "true_value": math.pi,
        "abs_error": abs(pi_est - math.pi),
        "std_error": se,
        "n": n,
        "inside": k,
    }


# ---------------------------------------------------------------------------
# 一维积分
# ---------------------------------------------------------------------------

def integrate_1d(fn: Callable[[float], float],
                 a: float, b: float,
                 n: int = 1_000_000,
                 seed: Optional[int] = None,
                 progress_cb: Optional[Callable] = None,
                 cancelled: Optional[Callable] = None) -> dict:
    """Monte Carlo 一维积分 ∫_a^b fn(x) dx。

    均匀采样，方差估计基于样本。
    """
    try:
        a = float(a)
        b = float(b)
        n = int(n)
    except (TypeError, ValueError) as e:
        raise InputError(f"参数非法：{e}")
    if n <= 0:
        raise InputError("n 必须 > 0")
    if b <= a:
        raise InputError("要求 b > a")

    rng = np.random.default_rng(seed)
    xs = rng.uniform(a, b, n)

    if cancelled is not None and cancelled():
        raise InputError("已取消")

    ys = np.array([float(fn(float(x))) for x in xs])
    if progress_cb is not None:
        progress_cb(n, n)

    # ys 中可能含 NaN/Inf，剔除
    mask = np.isfinite(ys)
    if not mask.any():
        raise InputError("函数在区间内全部为 NaN/Inf")
    ys = ys[mask]

    mean_y = float(ys.mean())
    std_y = float(ys.std(ddof=1)) if len(ys) > 1 else 0.0
    integral = (b - a) * mean_y
    se = (b - a) * std_y / math.sqrt(len(ys))

    return {
        "integral": integral,
        "std_error": se,
        "n": n,
        "valid": int(len(ys)),
        "mean_f": mean_y,
        "std_f": std_y,
        "interval": (a, b),
    }


# ---------------------------------------------------------------------------
# 多维积分
# ---------------------------------------------------------------------------

def integrate_nd(fn: Callable,
                 bounds: list,
                 n: int = 1_000_000,
                 seed: Optional[int] = None) -> dict:
    """多维 Monte Carlo 积分。

    Args:
        fn: ``fn(*args) -> float``
        bounds: ``[(a1, b1), (a2, b2), ...]``
        n: 采样数
    """
    n = int(n)
    if n <= 0:
        raise InputError("n 必须 > 0")
    if not bounds:
        raise InputError("bounds 不能为空")

    lows = np.array([float(b[0]) for b in bounds])
    highs = np.array([float(b[1]) for b in bounds])
    if np.any(highs <= lows):
        raise InputError("每个维度要求 b > a")

    volume = float(np.prod(highs - lows))
    dim = len(bounds)

    rng = np.random.default_rng(seed)
    # 生成 n 个点
    samples = rng.uniform(lows, highs, size=(n, dim))

    # 向量化调用（fn 可能不支持），逐点
    ys = np.empty(n, dtype=float)
    for i in range(n):
        try:
            ys[i] = float(fn(*samples[i].tolist()))
        except Exception:
            ys[i] = float("nan")

    mask = np.isfinite(ys)
    if not mask.any():
        raise InputError("函数在区域上全部为 NaN/Inf")
    ys = ys[mask]

    mean_y = float(ys.mean())
    std_y = float(ys.std(ddof=1)) if len(ys) > 1 else 0.0
    integral = volume * mean_y
    se = volume * std_y / math.sqrt(len(ys))

    return {
        "integral": integral,
        "std_error": se,
        "volume": volume,
        "dim": dim,
        "n": n,
        "valid": int(len(ys)),
    }


# ---------------------------------------------------------------------------
# 期望
# ---------------------------------------------------------------------------

def expectation(sample_fn: Callable[[int], list],
                g: Callable = lambda x: x,
                n: int = 1_000_000,
                seed: Optional[int] = None) -> dict:
    """估计 E[g(X)]。

    Args:
        sample_fn: ``fn(n) -> list``，从分布采样
        g: 变换函数
        n: 采样数
    """
    n = int(n)
    try:
        xs = list(sample_fn(n))
    except Exception as e:
        raise InputError(f"采样失败：{e}")
    if not xs:
        raise InputError("采样结果为空")

    ys = np.array([float(g(x)) for x in xs], dtype=float)
    mask = np.isfinite(ys)
    ys = ys[mask]
    if len(ys) == 0:
        raise InputError("变换结果全部无效")

    mean = float(ys.mean())
    std = float(ys.std(ddof=1)) if len(ys) > 1 else 0.0
    se = std / math.sqrt(len(ys))

    return {
        "expectation": mean,
        "std_error": se,
        "std": std,
        "n": len(ys),
        "ci_95": (mean - 1.96 * se, mean + 1.96 * se),
    }


# ---------------------------------------------------------------------------
# 方差缩减：对偶变量
# ---------------------------------------------------------------------------

def variance_reduction_antithetic(
        fn: Callable[[float], float],
        a: float, b: float,
        n: int = 500_000,
        seed: Optional[int] = None) -> dict:
    """对偶变量法：用 U 和 1-U 采样两次，取平均。"""
    n = int(n)
    if n % 2 == 1:
        n += 1
    half = n // 2
    rng = np.random.default_rng(seed)
    u = rng.uniform(0, 1, half)
    xs1 = a + (b - a) * u
    xs2 = a + (b - a) * (1 - u)

    ys1 = np.array([float(fn(float(x))) for x in xs1])
    ys2 = np.array([float(fn(float(x))) for x in xs2])
    ys = (ys1 + ys2) / 2.0

    mask = np.isfinite(ys)
    ys = ys[mask]
    mean = float(ys.mean())
    std = float(ys.std(ddof=1)) if len(ys) > 1 else 0.0
    integral = (b - a) * mean
    se = (b - a) * std / math.sqrt(len(ys))

    return {
        "integral": integral,
        "std_error": se,
        "n": n,
        "half_pairs": half,
        "method": "antithetic",
    }


__all__ = [
    "estimate_pi",
    "integrate_1d",
    "integrate_nd",
    "expectation",
    "variance_reduction_antithetic",
]