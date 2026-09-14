"""期权定价：Black-Scholes + Greeks。"""
from __future__ import annotations

import math

from core.errors import InputError


def _norm_cdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def _norm_pdf(x):
    return math.exp(-0.5 * x * x) / math.sqrt(2 * math.pi)


def black_scholes(S, K, T, r, sigma, kind="call"):
    """S: 现价；K: 行权价；T: 年；r: 无风险利率（%）；sigma: 波动率（%）。"""
    try:
        S = float(S); K = float(K); T = float(T)
        r = float(r) / 100.0
        sigma = float(sigma) / 100.0
    except Exception as e:
        raise InputError(f"参数非法：{e}", friendly_key="err_input")
    if S <= 0 or K <= 0 or T <= 0 or sigma <= 0:
        raise InputError("参数须为正", friendly_key="err_input")

    d1 = (math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    disc = math.exp(-r * T)

    if kind == "call":
        price = S * _norm_cdf(d1) - K * disc * _norm_cdf(d2)
        delta = _norm_cdf(d1)
        rho = K * T * disc * _norm_cdf(d2) / 100.0
        theta = (-S * _norm_pdf(d1) * sigma / (2 * math.sqrt(T))
                 - r * K * disc * _norm_cdf(d2)) / 365.0
    else:
        price = K * disc * _norm_cdf(-d2) - S * _norm_cdf(-d1)
        delta = _norm_cdf(d1) - 1
        rho = -K * T * disc * _norm_cdf(-d2) / 100.0
        theta = (-S * _norm_pdf(d1) * sigma / (2 * math.sqrt(T))
                 + r * K * disc * _norm_cdf(-d2)) / 365.0

    gamma = _norm_pdf(d1) / (S * sigma * math.sqrt(T))
    vega = S * _norm_pdf(d1) * math.sqrt(T) / 100.0

    return {
        "price": price,
        "delta": delta,
        "gamma": gamma,
        "vega": vega,
        "theta": theta,
        "rho": rho,
        "d1": d1,
        "d2": d2,
    }