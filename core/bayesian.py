"""贝叶斯推断：共轭先验 + 后验计算。

设计：
- 纯数值实现，无外部依赖
- 共轭先验：Beta-Binomial / Normal-Normal / Gamma-Poisson
- 后验计算 + 可信区间 + 后验预测分布

对外接口：
    beta_binomial(alpha, beta, successes, failures) -> dict
    normal_normal(mu0, sigma0, xbar, sigma, n) -> dict
    gamma_poisson(alpha, beta, counts) -> dict
    posterior_credible_interval(posterior_fn, level) -> tuple
    bayes_factor(log_lik_a, log_lik_b) -> dict
"""
from __future__ import annotations

import math
from typing import Callable, Optional

from core.errors import InputError


# ---------------------------------------------------------------------------
# Beta-Binomial
# ---------------------------------------------------------------------------

def beta_binomial(alpha: float, beta: float,
                  successes: int, failures: int) -> dict:
    """Beta-Binomial 共轭更新。

    Args:
        alpha, beta: Beta 先验参数
        successes: 观测到的成功数
        failures: 观测到的失败数

    Returns:
        ``{prior, posterior, mean, mode, variance, ci_95, ci_99,
        prior_predictive_mean, posterior_predictive_mean}``
    """
    try:
        a = float(alpha)
        b = float(beta)
        s = int(successes)
        f = int(failures)
    except (TypeError, ValueError) as e:
        raise InputError(f"参数非法：{e}")

    if a <= 0 or b <= 0:
        raise InputError("Beta 参数必须 > 0")
    if s < 0 or f < 0:
        raise InputError("观测数不能为负")

    a_post = a + s
    b_post = b + f

    def _mean(aa, bb):
        return aa / (aa + bb)

    def _mode(aa, bb):
        if aa > 1 and bb > 1:
            return (aa - 1) / (aa + bb - 2)
        return float("nan")

    def _var(aa, bb):
        n = aa + bb
        return aa * bb / (n * n * (n + 1))

    def _ci(aa, bb, level):
        # Beta 分位数（用 scipy.stats.beta）
        try:
            from scipy import stats as st
            lo = (1 - level) / 2
            hi = 1 - lo
            return (float(st.beta.ppf(lo, aa, bb)),
                    float(st.beta.ppf(hi, aa, bb)))
        except Exception:
            return (float("nan"), float("nan"))

    return {
        "prior": {"alpha": a, "beta": b,
                  "mean": _mean(a, b)},
        "posterior": {
            "alpha": a_post, "beta": b_post,
            "mean": _mean(a_post, b_post),
            "mode": _mode(a_post, b_post),
            "variance": _var(a_post, b_post),
            "std": math.sqrt(_var(a_post, b_post)),
        },
        "ci_95": _ci(a_post, b_post, 0.95),
        "ci_99": _ci(a_post, b_post, 0.99),
        "prior_predictive_mean": _mean(a, b),
        "posterior_predictive_mean": _mean(a_post, b_post),
        "data": {"successes": s, "failures": f},
    }


# ---------------------------------------------------------------------------
# Normal-Normal（已知方差）
# ---------------------------------------------------------------------------

def normal_normal(mu0: float, sigma0: float,
                  xbar: float, sigma: float,
                  n: int) -> dict:
    """正态-正态共轭更新（观测方差已知）。

    Args:
        mu0, sigma0: 先验均值和标准差
        xbar: 样本均值
        sigma: 观测标准差（已知）
        n: 样本量
    """
    try:
        mu0 = float(mu0)
        s0 = float(sigma0)
        xb = float(xbar)
        sig = float(sigma)
        n = int(n)
    except (TypeError, ValueError) as e:
        raise InputError(f"参数非法：{e}")

    if s0 <= 0 or sig <= 0 or n <= 0:
        raise InputError("sigma0 / sigma / n 必须为正")

    # 后验精度 = 先验精度 + 数据精度
    prec0 = 1.0 / (s0 * s0)
    prec_data = n / (sig * sig)
    prec_post = prec0 + prec_data

    mu_post = (prec0 * mu0 + prec_data * xb) / prec_post
    sigma_post = math.sqrt(1.0 / prec_post)

    return {
        "prior": {"mu": mu0, "sigma": s0},
        "data": {"xbar": xb, "sigma": sig, "n": n},
        "posterior": {
            "mu": mu_post,
            "sigma": sigma_post,
            "precision": prec_post,
        },
        "ci_95": (mu_post - 1.96 * sigma_post,
                  mu_post + 1.96 * sigma_post),
        "ci_99": (mu_post - 2.576 * sigma_post,
                  mu_post + 2.576 * sigma_post),
    }


# ---------------------------------------------------------------------------
# Gamma-Poisson
# ---------------------------------------------------------------------------

def gamma_poisson(alpha: float, beta: float,
                  counts) -> dict:
    """Gamma-Poisson 共轭更新。

    Args:
        alpha, beta: Gamma 先验参数（shape, rate）
        counts: 观测到的计数列表
    """
    try:
        a = float(alpha)
        b = float(beta)
        counts_list = [int(c) for c in counts]
    except (TypeError, ValueError) as e:
        raise InputError(f"参数非法：{e}")

    if a <= 0 or b <= 0:
        raise InputError("Gamma 参数必须 > 0")
    if not counts_list:
        raise InputError("计数列表不能为空")
    if any(c < 0 for c in counts_list):
        raise InputError("计数不能为负")

    n = len(counts_list)
    total = sum(counts_list)

    a_post = a + total
    b_post = b + n

    mean_post = a_post / b_post
    var_post = a_post / (b_post * b_post)

    def _ci(level):
        try:
            from scipy import stats as st
            lo = (1 - level) / 2
            hi = 1 - lo
            return (float(st.gamma.ppf(lo, a_post, scale=1 / b_post)),
                    float(st.gamma.ppf(hi, a_post, scale=1 / b_post)))
        except Exception:
            return (float("nan"), float("nan"))

    return {
        "prior": {"alpha": a, "beta": b,
                  "mean": a / b},
        "data": {"n": n, "total": total,
                 "mean": total / n},
        "posterior": {
            "alpha": a_post, "beta": b_post,
            "mean": mean_post,
            "variance": var_post,
            "std": math.sqrt(var_post),
        },
        "ci_95": _ci(0.95),
        "ci_99": _ci(0.99),
    }


# ---------------------------------------------------------------------------
# 通用：可信区间
# ---------------------------------------------------------------------------

def posterior_credible_interval(
        sample_fn: Callable[[int], list],
        level: float = 0.95,
        n_samples: int = 50000) -> dict:
    """通用可信区间：从后验采样，取分位数。

    Args:
        sample_fn: ``fn(n) -> list``，返回 n 个后验样本
        level: 可信水平（0.95 / 0.99）
        n_samples: 采样数量

    Returns:
        ``{mean, median, std, ci_low, ci_high, level}``
    """
    try:
        samples = list(sample_fn(int(n_samples)))
    except Exception as e:
        raise InputError(f"采样失败：{e}")

    if not samples:
        raise InputError("采样结果为空")

    samples.sort()
    n = len(samples)
    mean = sum(samples) / n
    var = sum((x - mean) ** 2 for x in samples) / n

    lo = (1 - level) / 2
    hi = 1 - lo
    i_lo = max(0, min(n - 1, int(lo * n)))
    i_hi = max(0, min(n - 1, int(hi * n)))
    median = samples[n // 2]

    return {
        "mean": mean,
        "median": median,
        "std": math.sqrt(var),
        "ci_low": samples[i_lo],
        "ci_high": samples[i_hi],
        "level": level,
        "n_samples": n,
    }


# ---------------------------------------------------------------------------
# 贝叶斯因子
# ---------------------------------------------------------------------------

def bayes_factor(log_lik_a: float, log_lik_b: float,
                 prior_odds: float = 1.0) -> dict:
    """从对数似然计算贝叶斯因子。

    Args:
        log_lik_a: 模型 A 的边缘对数似然
        log_lik_b: 模型 B 的边缘对数似然
        prior_odds: 先验几率 P(A) / P(B)

    Returns:
        ``{log_bf, bf, posterior_odds, interpretation}``
    """
    try:
        la = float(log_lik_a)
        lb = float(log_lik_b)
        po = float(prior_odds)
    except (TypeError, ValueError) as e:
        raise InputError(f"参数非法：{e}")
    if po <= 0:
        raise InputError("先验几率必须 > 0")

    log_bf = la - lb
    bf = math.exp(log_bf)
    posterior_odds = bf * po

    # Jeffreys 解释尺度
    if bf < 1:
        interp = "支持 B"
        bf_cmp = 1.0 / bf if bf > 0 else float("inf")
    else:
        interp = "支持 A"
        bf_cmp = bf

    if bf_cmp < 3:
        strength = "无实质证据"
    elif bf_cmp < 10:
        strength = "弱证据"
    elif bf_cmp < 30:
        strength = "中等证据"
    elif bf_cmp < 100:
        strength = "强证据"
    else:
        strength = "极强证据"

    return {
        "log_bf": log_bf,
        "bf": bf,
        "posterior_odds": posterior_odds,
        "interpretation": f"{strength}，{interp}",
    }


__all__ = [
    "beta_binomial",
    "normal_normal",
    "gamma_poisson",
    "posterior_credible_interval",
    "bayes_factor",
]