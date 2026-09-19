"""概率 / 随机 / 贝叶斯 / MCMC / 蒙特卡洛。

合并自：core/probability.py + core/random_ext.py
        + core/bayesian.py + core/mcmc.py + core.monte_carlo.py

对外接口：
    # 分布
    DISTS, pdf_or_pmf, cdf, quantile, sample
    # 检验 / 回归 / 拟合 / CI
    ttest_1samp, ttest_ind, chi2_test, linear_regression,
    fit_distribution, confidence_interval_mean,
    anova_oneway, chi2_independence, multiple_regression
    # 随机
    make_rng, distribution_sample, shuffle_list,
    sample_from_list, uuid_list, password_gen
    # 贝叶斯
    beta_binomial, normal_normal, gamma_poisson,
    posterior_credible_interval, bayes_factor
    # MCMC
    metropolis_hastings, gibbs,
    effective_sample_size, autocorrelation,
    gelman_rubin, trace_summary
    # 蒙特卡洛
    estimate_pi, integrate_1d, integrate_nd,
    expectation, variance_reduction_antithetic
"""
from __future__ import annotations

import math
import random
import secrets
import string
import uuid
from typing import Callable, Optional

import numpy as np
from scipy import stats as st

from core.base import InputError

__all__ = [
    # 分布
    "DISTS", "pdf_or_pmf", "cdf", "quantile", "sample",
    # 检验
    "ttest_1samp", "ttest_ind", "chi2_test",
    "linear_regression", "fit_distribution",
    "confidence_interval_mean", "anova_oneway",
    "chi2_independence", "multiple_regression",
    # 随机
    "make_rng", "distribution_sample", "shuffle_list",
    "sample_from_list", "uuid_list", "password_gen",
    # 贝叶斯
    "beta_binomial", "normal_normal", "gamma_poisson",
    "posterior_credible_interval", "bayes_factor",
    # MCMC
    "metropolis_hastings", "gibbs",
    "effective_sample_size", "autocorrelation",
    "gelman_rubin", "trace_summary",
    # 蒙特卡洛
    "estimate_pi", "integrate_1d", "integrate_nd",
    "expectation", "variance_reduction_antithetic",
]


# ===========================================================================
# 分布
# ===========================================================================

DISTS = {
    "norm":    (st.norm,     ["loc", "scale"]),
    "t":       (st.t,        ["df", "loc", "scale"]),
    "chi2":    (st.chi2,     ["df", "loc", "scale"]),
    "f":       (st.f,        ["dfn", "dfd", "loc", "scale"]),
    "binom":   (st.binom,    ["n", "p", "loc"]),
    "poisson": (st.poisson,  ["mu", "loc"]),
    "geom":    (st.geom,     ["p", "loc"]),
    "expon":   (st.expon,    ["loc", "scale"]),
    "uniform": (st.uniform,  ["loc", "scale"]),
    "beta":    (st.beta,     ["a", "b", "loc", "scale"]),
    "gamma":   (st.gamma,    ["a", "loc", "scale"]),
    "lognorm": (st.lognorm,  ["s", "loc", "scale"]),
}

_INT_KEYS = {"df", "dfn", "dfd", "n"}


def _build(name, params):
    if name not in DISTS:
        raise InputError(f"未知分布：{name}")
    fn, keys = DISTS[name]
    kw = {}
    for k in keys:
        if k not in params:
            continue
        v = params[k]
        if v in (None, ""):
            continue
        if k in _INT_KEYS:
            kw[k] = int(round(float(v)))
        else:
            kw[k] = float(v)
    if name in ("binom", "poisson", "geom") and "loc" in kw:
        kw["loc"] = int(round(kw["loc"]))
    return fn(**kw)


def pdf_or_pmf(name, x, params):
    d = _build(name, params)
    if name in ("binom", "poisson", "geom"):
        return float(d.pmf(x))
    return float(d.pdf(x))


def cdf(name, x, params):
    return float(_build(name, params).cdf(x))


def quantile(name, p, params):
    return float(_build(name, params).ppf(p))


def sample(name, params, n=1000):
    return _build(name, params).rvs(size=int(n)).tolist()


# ===========================================================================
# 假设检验 / 回归
# ===========================================================================

def ttest_1samp(data, mu0=0.0, alpha=0.05, tail="two"):
    data = np.asarray(data, dtype=float)
    if tail == "two":
        t, p = st.ttest_1samp(data, mu0)
    elif tail == "greater":
        t, p = st.ttest_1samp(data, mu0, alternative="greater")
    else:
        t, p = st.ttest_1samp(data, mu0, alternative="less")
    return {"t": float(t), "p": float(p),
            "reject_H0": bool(p < alpha)}


def ttest_ind(a, b, alpha=0.05):
    t, p = st.ttest_ind(a, b, equal_var=False)
    return {"t": float(t), "p": float(p),
            "reject_H0": bool(p < alpha)}


def chi2_test(observed, expected=None):
    obs = np.asarray(observed, dtype=float)
    if expected is None:
        exp = np.full_like(obs, obs.mean())
    else:
        exp = np.asarray(expected, dtype=float)
    chi, p = st.chisquare(obs, exp)
    return {"chi2": float(chi), "p": float(p)}


def linear_regression(x, y):
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if len(x) != len(y) or len(x) < 2:
        raise InputError("X/Y 数据长度不一致或过少")
    slope, intercept, r, p, se = st.linregress(x, y)
    return {"slope": float(slope), "intercept": float(intercept),
            "r": float(r), "r2": float(r * r), "p": float(p),
            "stderr": float(se)}


def fit_distribution(name, data):
    """把数据拟合到给定分布，返回估计参数与对数似然。"""
    if name not in DISTS:
        raise InputError(f"未知分布：{name}")
    fn, keys = DISTS[name]
    arr = np.asarray(data, dtype=float)
    if len(arr) < 5:
        raise InputError("拟合至少需要 5 个数据点")
    try:
        params = fn.fit(arr)
    except Exception as e:  # noqa: BLE001
        raise InputError(f"拟合失败：{e}") from e
    names = [p for p in getattr(fn, "shapes", "").split(", ") if p]
    out = {}
    n_shape = len(names)
    for i, nm in enumerate(names):
        out[nm] = float(params[i])
    if len(params) > n_shape:
        out["loc"] = float(params[n_shape])
    if len(params) > n_shape + 1:
        out["scale"] = float(params[n_shape + 1])
    try:
        ks, p = st.kstest(arr, fn.cdf, args=params)
        out["ks_stat"] = float(ks)
        out["ks_p"] = float(p)
    except Exception:
        pass
    return out


def confidence_interval_mean(data, alpha=0.05, sigma=None):
    """均值的置信区间。sigma 已知用 z；否则用 t。"""
    arr = np.asarray(data, dtype=float)
    n = len(arr)
    if n < 2:
        raise InputError("至少需要 2 个数据点")
    mean = float(np.mean(arr))
    if sigma is not None:
        se = float(sigma) / np.sqrt(n)
        crit = float(st.norm.ppf(1 - alpha / 2))
        method = "z (sigma known)"
    else:
        se = float(np.std(arr, ddof=1)) / np.sqrt(n)
        crit = float(st.t.ppf(1 - alpha / 2, df=n - 1))
        method = "t (sigma unknown)"
    return {
        "mean": mean,
        "n": n,
        "alpha": float(alpha),
        "stderr": se,
        "lower": mean - crit * se,
        "upper": mean + crit * se,
        "method": method,
    }


def anova_oneway(*groups, alpha=0.05):
    arrs = [np.asarray(g, dtype=float) for g in groups]
    if len(arrs) < 2:
        raise InputError("至少需要两组")
    f, p = st.f_oneway(*arrs)
    return {"F": float(f), "p": float(p),
            "reject_H0": bool(p < alpha), "k": len(arrs),
            "n_total": int(sum(len(a) for a in arrs))}


def chi2_independence(table):
    obs = np.asarray(table, dtype=float)
    chi, p, dof, expected = st.chi2_contingency(obs)
    return {"chi2": float(chi), "p": float(p),
            "dof": int(dof),
            "expected": expected.tolist()}


def multiple_regression(X, y):
    """多元线性回归。X 形状 (n, p)；y 长度 n。"""
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float).reshape(-1)
    if X.ndim != 2:
        raise InputError("X 必须是二维")
    n, p = X.shape
    if n != y.shape[0]:
        raise InputError("X 与 y 长度不一致")
    if n <= p + 1:
        raise InputError("样本量不足")

    Xd = np.hstack([np.ones((n, 1)), X])
    try:
        beta, *_ = np.linalg.lstsq(Xd, y, rcond=None)
    except Exception as e:  # noqa: BLE001
        raise InputError(f"求解失败：{e}") from e
    y_pred = Xd @ beta
    resid = y - y_pred
    ss_res = float(np.sum(resid ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
    dof = n - (p + 1)
    if dof <= 0:
        raise InputError("自由度不足")
    sigma2 = ss_res / dof
    try:
        cov = sigma2 * np.linalg.inv(Xd.T @ Xd)
        se = np.sqrt(np.diag(cov))
    except np.linalg.LinAlgError:
        se = np.full(p + 1, float("nan"))
    tvals = beta / se
    pvals = 2 * (1 - st.t.cdf(np.abs(tvals), df=dof))
    adj_r2 = 1 - (1 - r2) * (n - 1) / dof if dof > 0 else r2
    return {
        "coefficients": beta.tolist(),
        "std_errors": se.tolist(),
        "t": tvals.tolist(),
        "p": pvals.tolist(),
        "r2": float(r2),
        "adj_r2": float(adj_r2),
        "residual_std": float(np.sqrt(sigma2)),
        "n": int(n),
        "p": int(p),
        "predictions": y_pred.tolist(),
        "residuals": resid.tolist(),
    }


# ===========================================================================
# 随机
# ===========================================================================

_PW_SAFE = string.ascii_letters + string.digits
_PW_SYMBOLS = "!@#$%^&*()-_=+[]{};:,.<>/?"


def make_rng(seed=None):
    if seed in (None, "", "random"):
        return random.Random()
    try:
        return random.Random(int(seed))
    except (TypeError, ValueError):
        return random.Random(str(seed))


def distribution_sample(kind: str, n: int, params: dict, seed=None):
    """按分布抽样。kind: uniform | normal | exponential | int | choice。"""
    n = int(n)
    if n <= 0:
        raise InputError("数量必须大于 0",
                         friendly_key="err_input")
    rng = make_rng(seed)

    if kind == "uniform":
        lo = float(params.get("low", 0))
        hi = float(params.get("high", 1))
        if lo > hi:
            raise InputError("low > high",
                             friendly_key="err_input")
        return [rng.uniform(lo, hi) for _ in range(n)]
    if kind == "normal":
        mu = float(params.get("mu", 0))
        sigma = float(params.get("sigma", 1))
        if sigma <= 0:
            raise InputError("sigma 必须大于 0",
                             friendly_key="err_input")
        return [rng.gauss(mu, sigma) for _ in range(n)]
    if kind == "exponential":
        lam = float(params.get("lambda", 1))
        if lam <= 0:
            raise InputError("lambda 必须大于 0",
                             friendly_key="err_input")
        return [rng.expovariate(lam) for _ in range(n)]
    if kind == "int":
        lo = int(params.get("low", 0))
        hi = int(params.get("high", 100))
        if lo > hi:
            raise InputError("low > high",
                             friendly_key="err_input")
        return [rng.randint(lo, hi) for _ in range(n)]
    if kind == "choice":
        pool = params.get("pool") or []
        if not pool:
            raise InputError("候选池为空",
                             friendly_key="err_input")
        return [rng.choice(pool) for _ in range(n)]
    raise InputError(f"未知分布：{kind}",
                     friendly_key="err_input")


def shuffle_list(items, seed=None):
    arr = list(items)
    rng = make_rng(seed)
    rng.shuffle(arr)
    return arr


def sample_from_list(items, k, replace=False, seed=None):
    arr = list(items)
    k = int(k)
    if k < 0 or (not replace and k > len(arr)):
        raise InputError("抽样数量非法",
                         friendly_key="err_input")
    rng = make_rng(seed)
    if replace:
        return [rng.choice(arr) for _ in range(k)]
    return rng.sample(arr, k)


def uuid_list(n=1, version=4):
    n = int(n)
    if n <= 0:
        raise InputError("数量必须大于 0",
                         friendly_key="err_input")
    out = []
    for _ in range(n):
        if version == 1:
            out.append(str(uuid.uuid1()))
        elif version == 3:
            out.append(str(uuid.uuid3(
                uuid.NAMESPACE_DNS, secrets.token_hex(8))))
        elif version == 5:
            out.append(str(uuid.uuid5(
                uuid.NAMESPACE_DNS, secrets.token_hex(8))))
        else:
            out.append(str(uuid.uuid4()))
    return out


def password_gen(length=16, upper=True, lower=True, digits=True,
                 symbols=False, exclude_ambiguous=False):
    length = int(length)
    if length < 4:
        raise InputError("密码长度至少 4",
                         friendly_key="err_input")
    pools = []
    if upper:
        pools.append(string.ascii_uppercase)
    if lower:
        pools.append(string.ascii_lowercase)
    if digits:
        pools.append(string.digits)
    if symbols:
        pools.append(_PW_SYMBOLS)
    if not pools:
        raise InputError("至少启用一类字符",
                         friendly_key="err_input")

    if exclude_ambiguous:
        amb = "Il1O0"
        pools = ["".join(c for c in p if c not in amb)
                 for p in pools]

    rng = secrets.SystemRandom()
    pw = [rng.choice(p) for p in pools]
    all_chars = "".join(pools)
    while len(pw) < length:
        pw.append(rng.choice(all_chars))
    rng.shuffle(pw)
    return "".join(pw)


# ===========================================================================
# 贝叶斯
# ===========================================================================

def beta_binomial(alpha: float, beta: float,
                  successes: int, failures: int) -> dict:
    """Beta-Binomial 共轭更新。"""
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
        try:
            lo = (1 - level) / 2
            hi = 1 - lo
            return (float(st.beta.ppf(lo, aa, bb)),
                    float(st.beta.ppf(hi, aa, bb)))
        except Exception:
            return (float("nan"), float("nan"))

    return {
        "prior": {"alpha": a, "beta": b, "mean": _mean(a, b)},
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


def normal_normal(mu0: float, sigma0: float,
                  xbar: float, sigma: float,
                  n: int) -> dict:
    """正态-正态共轭更新（观测方差已知）。"""
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

    prec0 = 1.0 / (s0 * s0)
    prec_data = n / (sig * sig)
    prec_post = prec0 + prec_data

    mu_post = (prec0 * mu0 + prec_data * xb) / prec_post
    sigma_post = math.sqrt(1.0 / prec_post)

    return {
        "prior": {"mu": mu0, "sigma": s0},
        "data": {"xbar": xb, "sigma": sig, "n": n},
        "posterior": {
            "mu": mu_post, "sigma": sigma_post,
            "precision": prec_post,
        },
        "ci_95": (mu_post - 1.96 * sigma_post,
                  mu_post + 1.96 * sigma_post),
        "ci_99": (mu_post - 2.576 * sigma_post,
                  mu_post + 2.576 * sigma_post),
    }


def gamma_poisson(alpha: float, beta: float, counts) -> dict:
    """Gamma-Poisson 共轭更新。"""
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
            lo = (1 - level) / 2
            hi = 1 - lo
            return (float(st.gamma.ppf(lo, a_post,
                                       scale=1 / b_post)),
                    float(st.gamma.ppf(hi, a_post,
                                       scale=1 / b_post)))
        except Exception:
            return (float("nan"), float("nan"))

    return {
        "prior": {"alpha": a, "beta": b, "mean": a / b},
        "data": {"n": n, "total": total, "mean": total / n},
        "posterior": {
            "alpha": a_post, "beta": b_post,
            "mean": mean_post,
            "variance": var_post,
            "std": math.sqrt(var_post),
        },
        "ci_95": _ci(0.95),
        "ci_99": _ci(0.99),
    }


def posterior_credible_interval(
        sample_fn: Callable[[int], list],
        level: float = 0.95,
        n_samples: int = 50000) -> dict:
    """通用可信区间：从后验采样，取分位数。"""
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


def bayes_factor(log_lik_a: float, log_lik_b: float,
                 prior_odds: float = 1.0) -> dict:
    """从对数似然计算贝叶斯因子。"""
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


# ===========================================================================
# MCMC
# ===========================================================================

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
    """Metropolis-Hastings 采样。"""
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
            proposal_logp = float(
                log_posterior(proposal.tolist()))
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

        if (progress_cb is not None
                and i % max(1, total // 100) == 0):
            progress_cb(i, total)

    return _summarize(trace, accepted, n_samples, burn_in,
                      map_theta.tolist())


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

    cond_samplers: 每个维度的条件采样函数列表：
        ``fn_i(current_theta: list, rng) -> float``
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
                theta[d] = float(
                    cond_samplers[d](list(theta), rng))
            except Exception:
                pass
        if i >= burn_in:
            trace[idx] = theta
            idx += 1
        if (progress_cb is not None
                and i % max(1, total // 100) == 0):
            progress_cb(i, total)

    return _summarize(trace, n_samples, n_samples, burn_in, theta)


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
    """有效样本数（ESS）。基于自相关：ESS = n / (1 + 2 * sum(rho_k))。"""
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
        if rho < 0.05:
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
    """Gelman-Rubin 收敛诊断（R-hat）。< 1.1 通常认为收敛。"""
    if len(traces) < 2:
        raise InputError("至少需要 2 条链")
    arrs = [np.asarray(t, dtype=float) for t in traces]
    n = min(len(a) for a in arrs)
    if n < 5:
        raise InputError("链太短")

    arrs = [a[:n] for a in arrs]
    stacked = np.stack(arrs, axis=0)
    m = stacked.shape[0]
    chain_means = stacked.mean(axis=1)
    chain_vars = stacked.var(axis=1, ddof=1)

    W = float(chain_vars.mean())
    B = float(n * chain_means.var(ddof=1))

    if W <= 0:
        return float("nan")

    var_hat = (n - 1) / n * W + B / n
    return math.sqrt(var_hat / W)


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


# ===========================================================================
# 蒙特卡洛
# ===========================================================================

def estimate_pi(n: int = 1_000_000,
                seed: Optional[int] = None) -> dict:
    """用 Monte Carlo 估算 π。"""
    n = int(n)
    if n <= 0:
        raise InputError("n 必须 > 0")
    rng = np.random.default_rng(seed)
    x = rng.uniform(-1, 1, n)
    y = rng.uniform(-1, 1, n)
    inside = (x * x + y * y) <= 1.0
    k = int(inside.sum())
    pi_est = 4.0 * k / n
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


def integrate_1d(fn: Callable[[float], float],
                 a: float, b: float,
                 n: int = 1_000_000,
                 seed: Optional[int] = None,
                 progress_cb: Optional[Callable] = None,
                 cancelled: Optional[Callable] = None) -> dict:
    """Monte Carlo 一维积分 ∫_a^b fn(x) dx。"""
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


def integrate_nd(fn: Callable,
                 bounds: list,
                 n: int = 1_000_000,
                 seed: Optional[int] = None) -> dict:
    """多维 Monte Carlo 积分。bounds = [(a1,b1), (a2,b2), ...]。"""
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
    samples = rng.uniform(lows, highs, size=(n, dim))

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


def expectation(sample_fn: Callable[[int], list],
                g: Callable = lambda x: x,
                n: int = 1_000_000,
                seed: Optional[int] = None) -> dict:
    """估计 E[g(X)]。"""
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