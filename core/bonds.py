"""债券定价：价格、YTM、久期、凸性。"""
from __future__ import annotations

from core.errors import InputError


def bond_price(face, coupon_rate, years, ytm, freq=1):
    """返回 {price, duration, convexity}。

    face: 面值；coupon_rate / ytm: 年化百分比；years: 年；freq: 年付次数。
    """
    try:
        F = float(face)
        c = float(coupon_rate) / 100.0
        y = float(ytm) / 100.0
        n = int(float(years) * freq)
        f = int(freq)
    except Exception as e:
        raise InputError(f"参数非法：{e}", friendly_key="err_input")
    if F <= 0 or n <= 0 or f <= 0:
        raise InputError("面值/年限/频次须为正", friendly_key="err_input")

    coupon = F * c / f
    y_f = y / f
    price = 0.0
    wsum = 0.0
    csum = 0.0
    for t in range(1, n + 1):
        cf = coupon + (F if t == n else 0.0)
        disc = (1 + y_f) ** t
        pv = cf / disc
        price += pv
        wsum += pv * t
        csum += pv * t * (t + 1)
    duration = wsum / price / f
    convexity = csum / price / (f ** 2)
    return {
        "price": price,
        "macaulay_duration": duration,
        "modified_duration": duration / (1 + y_f),
        "convexity": convexity,
        "coupon_per_period": coupon,
        "periods": n,
    }


def bond_ytm(face, coupon_rate, years, price, freq=1):
    """由价格反求 YTM（二分法）。"""
    try:
        F = float(face)
        target = float(price)
        n = int(float(years) * freq)
    except Exception as e:
        raise InputError(f"参数非法：{e}", friendly_key="err_input")

    def f(y):
        try:
            return bond_price(F, coupon_rate, years, y * 100.0, freq)["price"] - target
        except Exception:
            return 1e18

    lo, hi = -0.99, 5.0
    flo, fhi = f(lo), f(hi)
    if flo * fhi > 0:
        raise InputError("无法求解 YTM", friendly_key="err_no_solution")
    for _ in range(200):
        mid = (lo + hi) / 2
        fm = f(mid)
        if abs(fm) < 1e-8:
            return mid * 100.0
        if flo * fm < 0:
            hi = mid
        else:
            lo, flo = mid, fm
    return (lo + hi) / 2 * 100.0