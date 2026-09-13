"""概率分布、假设检验、线性回归。

修复：``_build`` 对 df / dfn / dfd / n / loc 等参数区分数值类型，
避免 scipy 在部分分布上因 float 参数报错。
"""
from __future__ import annotations

import numpy as np
from scipy import stats as st

DISTS = {
    "norm":     (st.norm,     ["loc", "scale"]),
    "t":        (st.t,        ["df", "loc", "scale"]),
    "chi2":     (st.chi2,     ["df", "loc", "scale"]),
    "f":        (st.f,        ["dfn", "dfd", "loc", "scale"]),
    "binom":    (st.binom,    ["n", "p", "loc"]),
    "poisson":  (st.poisson,  ["mu", "loc"]),
    "geom":     (st.geom,     ["p", "loc"]),
    "expon":    (st.expon,    ["loc", "scale"]),
    "uniform":  (st.uniform,  ["loc", "scale"]),
    "beta":     (st.beta,     ["a", "b", "loc", "scale"]),
    "gamma":    (st.gamma,    ["a", "loc", "scale"]),
    "lognorm":  (st.lognorm,  ["s", "loc", "scale"]),
}

# 离散参数或必须为整数的键
_INT_KEYS = {"df", "dfn", "dfd", "n"}


def _build(name, params):
    if name not in DISTS:
        raise ValueError(f"未知分布：{name}")
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
    # 离散分布 loc 必须为整数
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


# ---------------- 假设检验 ----------------

def ttest_1samp(data, mu0=0.0, alpha=0.05, tail="two"):
    data = np.asarray(data, dtype=float)
    if tail == "two":
        t, p = st.ttest_1samp(data, mu0)
    elif tail == "greater":
        t, p = st.ttest_1samp(data, mu0, alternative="greater")
    else:
        t, p = st.ttest_1samp(data, mu0, alternative="less")
    return {"t": float(t), "p": float(p), "reject_H0": bool(p < alpha)}


def ttest_ind(a, b, alpha=0.05):
    t, p = st.ttest_ind(a, b, equal_var=False)
    return {"t": float(t), "p": float(p), "reject_H0": bool(p < alpha)}


def chi2_test(observed, expected=None):
    obs = np.asarray(observed, dtype=float)
    if expected is None:
        exp = np.full_like(obs, obs.mean())
    else:
        exp = np.asarray(expected, dtype=float)
    chi, p = st.chisquare(obs, exp)
    return {"chi2": float(chi), "p": float(p)}


# ---------------- 线性回归 ----------------

def linear_regression(x, y):
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if len(x) != len(y) or len(x) < 2:
        raise ValueError("X/Y 数据长度不一致或过少")
    slope, intercept, r, p, se = st.linregress(x, y)
    return {"slope": float(slope), "intercept": float(intercept),
            "r": float(r), "r2": float(r * r), "p": float(p),
            "stderr": float(se)}

# ===========================================================================
# 第五轮新增：分布拟合 / 置信区间 / ANOVA / 卡方独立性 / 多元回归
# ===========================================================================

def fit_distribution(name, data):
    """把数据拟合到给定分布，返回估计参数与对数似然。"""
    if name not in DISTS:
        raise ValueError(f"未知分布：{name}")
    fn, keys = DISTS[name]
    arr = np.asarray(data, dtype=float)
    if len(arr) < 5:
        raise ValueError("拟合至少需要 5 个数据点")
    try:
        params = fn.fit(arr)
    except Exception as e:  # noqa: BLE001
        raise ValueError(f"拟合失败：{e}") from e
    # 参数命名参考 scipy 的返回顺序（shape, loc, scale）
    names = [p for p in getattr(fn, "shapes", "").split(", ") if p]
    out = {}
    n_shape = len(names)
    for i, nm in enumerate(names):
        out[nm] = float(params[i])
    if len(params) > n_shape:
        out["loc"] = float(params[n_shape])
    if len(params) > n_shape + 1:
        out["scale"] = float(params[n_shape + 1])
    # KS 检验
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
        raise ValueError("至少需要 2 个数据点")
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
        raise ValueError("至少需要两组")
    f, p = st.f_oneway(*arrs)
    return {"F": float(f), "p": float(p),
            "reject_H0": bool(p < alpha), "k": len(arrs),
            "n_total": int(sum(len(a) for a in arrs))}


def chi2_independence(table):
    obs = np.asarray(table, dtype=float)
    chi, p, dof, expected = st.chi2_contingency(obs)
    return {"chi2": float(chi), "p": float(p), "dof": int(dof),
            "expected": expected.tolist()}


def multiple_regression(X, y):
    """多元线性回归。

    X: list[list[float]] 形状 (n, p)；y: list[float] 长度 n。
    返回系数、R²、标准误、t 值、p 值。
    """
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float).reshape(-1)
    if X.ndim != 2:
        raise ValueError("X 必须是二维")
    n, p = X.shape
    if n != y.shape[0]:
        raise ValueError("X 与 y 长度不一致")
    if n <= p + 1:
        raise ValueError("样本量不足")

    # 加截距项
    Xd = np.hstack([np.ones((n, 1)), X])
    try:
        beta, *_ = np.linalg.lstsq(Xd, y, rcond=None)
    except Exception as e:  # noqa: BLE001
        raise ValueError(f"求解失败：{e}") from e
    y_pred = Xd @ beta
    resid = y - y_pred
    ss_res = float(np.sum(resid ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
    dof = n - (p + 1)
    if dof <= 0:
        raise ValueError("自由度不足")
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