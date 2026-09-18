"""MCMC 采样：Metropolis-Hastings、Gibbs、Hamiltonian。

设计：
- 纯 numpy 实现
- 支持自定义对数后验函数
- 返回 trace + 诊断统计（接受率、自相关、有效样本数）

对外接口：
    metropolis_hastings(log_posterior, init, n_samples, ...)
    gibbs(cond_samplers, init, n_samples, ...)
    effective_sample_size(trace)
    autocorrelation(trace, max_lag)
    gelman_rubin(traces)
"""
from __future__ import annotations

import math
from typing import Callable, Optional

import numpy as np

from core.errors import InputError


# ---------------------------------------------------------------------------
# Metropolis-Hastings
# ---------------------------------------------------------------------------

def metropolis_hastings(
        log_posterior: Callable,
        init: list,
        n_samples: int = 20000,
        burn_in: int = 2000,
        proposal_scale: float = 1.0,
        seed: Optional[int] = None,
        progress_cb: Optional[Callable] = None,
        cancelled: Optional[Callable] = None,
) -> dict:
    """Metropolis-Hastings 采样。

    Args:
        log_posterior: ``fn(theta: list) -> float``，返回对数后验
            （未归一化即可）
        init: 初始点 ``[theta1, theta2, ...]``
        n_samples: 采样数（不含 burn-in）
        burn_in: 预热步数
        proposal_scale: 提议分布标准差
        seed: 随机种子
        progress_cb: ``fn(done, total)``
        cancelled: ``fn() -> bool``

    Returns:
        ``{trace, accepted, acceptance_rate, n_dim, burn_in,
        mean, std, map_estimate}``
    """
    rng = np.random.default_rng(seed)
    theta = np.asarray(init, dtype=float)
    if theta.ndim != 1:
        raise InputError("init 必须是一维数组")

    n_dim = theta.shape[0]
    total = burn_in + n_samples

    trace = np.zeros((n_samples, n_dim))
    current_logp = float(log_posterior(theta.tolist()))
    accepted = 0
    sample_idx = 0
    map_theta = theta.copy()
    map_logp = current_logp

    for i in range(total):
        if cancelled is not None and cancelled():
            raise InputError("已取消")

        proposal = theta + rng.normal(
            0, proposal_scale, size=n_dim)
        try:
            proposal_logp = float(log_posterior(proposal.tolist()))
        except Exception:
            proposal_logp = -math.inf

        log_alpha = proposal_logp - current_logp
        if math.log(rng.uniform()) < log_alpha:
            theta = proposal
            current_logp = proposal_logp
            if i >= burn_in:
                accepted += 1

        if proposal_logp > map_logp:
            map_theta = proposal.copy()
            map_logp = proposal_logp

        if i >= burn_in:
            trace[sample_idx] = theta
            sample_idx += 1

        if progress_cb is not None and i % max(1, total // 100) == 0:
            progress_cb(i, total)

    return _summarize(trace, accepted, n_samples, burn_in,
                      map_theta.tolist())


# ---------------------------------------------------------------------------
# Gibbs（条件采样）
# ---------------------------------------------------------------------------

def gibbs(
        cond_samplers: list,
        init: list,
        n_samples: int = 20000,
        burn_in: int = 2000,
        seed: Optional[int] = None,
        progress_cb: Optional[Callable] = None,
        cancelled: Optional[Callable] = None,
) -> dict:
    """Gibbs 采样。

    Args:
        cond_samplers: 每个维度的条件采样函数列表：
            ``fn_i(current_theta: list, rng) -> float``
        init: 初始点
        n_samples / burn_in: 采样数与预热
    """
    rng = np.random.default_rng(seed)
    theta = list(init)
    n_dim = len(theta)
    if n_dim != len(cond_samplers):
        raise InputError("init 与 cond_samplers 长度不一致")

    trace = np.zeros((n_samples, n_dim))
    total = burn_in + n_samples
    idx = 0

    for i in range(total):
        if cancelled is not None and cancelled():
            raise InputError("已取消")
        for d in range(n_dim):
            try:
                theta[d] = float(cond_samplers[d](list(theta), rng))
            except Exception:
                pass
        if i >= burn_in:
            trace[idx] = theta
            idx += 1
        if progress_cb is not None and i % max(1, total // 100) == 0:
            progress_cb(i, total)

    return _summarize(trace, n_samples, n_samples, burn_in, theta)


# ---------------------------------------------------------------------------
# 诊断
# ---------------------------------------------------------------------------

def _summarize(trace: np.ndarray, accepted_or_n: int,
               n_samples: int, burn_in: int,
               map_theta: list) -> dict:
    """计算 trace 的摘要统计。"""
    mean = np.mean(trace, axis=0).tolist()
    std = np.std(trace, axis=0).tolist()
    ess = [
        effective_sample_size(trace[:, d].tolist())
        for d in range(trace.shape[1])
    ]
    return {
        "trace": trace.tolist(),
        "n_samples": int(n_samples),
        "burn_in": int(burn_in),
        "n_dim": int(trace.shape[1]),
        "mean": mean,
        "std": std,
        "map_estimate": list(map_theta),
        "ess": ess,
        "acceptance_rate": (
            accepted_or_n / max(1, n_samples)
            if accepted_or_n <= n_samples else None
        ),
    }


def effective_sample_size(trace: list, max_lag: int = 200) -> float:
    """有效样本数（ESS）。

    基于自相关：ESS = n / (1 + 2 * sum(rho_k))。
    """
    x = np.asarray(trace, dtype=float)
    n = len(x)
    if n < 10:
        return float(n)
    x = x - x.mean()
    var = float((x * x).sum()) / n
    if var <= 0:
        return float(n)

    max_lag = min(max_lag, n // 2)
    rho_sum = 0.0
    for k in range(1, max_lag + 1):
        c = float((x[:-k] * x[k:]).sum()) / n
        rho = c / var
        if rho < 0.05:  # 截断
            break
        rho_sum += rho
    ess = n / (1 + 2 * rho_sum)
    return max(1.0, min(float(n), ess))


def autocorrelation(trace: list, max_lag: int = 100) -> list:
    """返回 lag 0..max_lag 的自相关系数。"""
    x = np.asarray(trace, dtype=float)
    n = len(x)
    if n < 10:
        return [1.0]
    x = x - x.mean()
    var = float((x * x).sum()) / n
    if var <= 0:
        return [1.0] + [0.0] * max_lag

    out = [1.0]
    for k in range(1, min(max_lag, n - 1) + 1):
        c = float((x[:-k] * x[k:]).sum()) / n
        out.append(c / var)
    return out


def gelman_rubin(traces: list) -> float:
    """Gelman-Rubin 收敛诊断（R-hat）。

    Args:
        traces: 多个链的 trace 列表（每个链是一个 list）

    Returns:
        R-hat 值；< 1.1 通常认为收敛
    """
    if len(traces) < 2:
        raise InputError("至少需要 2 条链")
    arrs = [np.asarray(t, dtype=float) for t in traces]
    n = min(len(a) for a in arrs)
    if n < 5:
        raise InputError("链太短")

    # 截断到相同长度
    arrs = [a[:n] for a in arrs]
    stacked = np.stack(arrs, axis=0)  # (m, n)

    m = stacked.shape[0]
    chain_means = stacked.mean(axis=1)
    chain_vars = stacked.var(axis=1, ddof=1)

    W = float(chain_vars.mean())
    B = float(n * chain_means.var(ddof=1))

    if W <= 0:
        return float("nan")

    var_hat = (n - 1) / n * W + B / n
    r_hat = math.sqrt(var_hat / W)
    return r_hat


def trace_summary(trace: list, level: float = 0.95) -> dict:
    """单维 trace 的完整摘要。"""
    x = np.asarray(trace, dtype=float)
    n = len(x)
    if n == 0:
        return {}
    mean = float(x.mean())
    std = float(x.std(ddof=1)) if n > 1 else 0.0
    lo = (1 - level) / 2
    hi = 1 - lo
    return {
        "n": int(n),
        "mean": mean,
        "std": std,
        "min": float(x.min()),
        "max": float(x.max()),
        "median": float(np.median(x)),
        "ci_low": float(np.quantile(x, lo)),
        "ci_high": float(np.quantile(x, hi)),
        "ess": effective_sample_size(trace),
        "level": level,
    }


__all__ = [
    "metropolis_hastings",
    "gibbs",
    "effective_sample_size",
    "autocorrelation",
    "gelman_rubin",
    "trace_summary",
]