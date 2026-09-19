"""财务 / 债券 / 期权 / 个税。

合并自：core/finance.py + core/tax.py + core.bonds.py + core.options.py

对外接口：
    # 现金流
    npv, irr, irr_all, xirr
    # 贷款
    loan_schedule, equal_principal, compare_plans
    # 时间价值 / 折旧
    tvm, depreciation
    # 债券
    bond_price, bond_ytm
    # 期权
    black_scholes
    # 个税
    cn_income_tax, us_federal_tax
"""
from __future__ import annotations

import datetime as _dt
import math

from core.base import InputError

__all__ = [
    "npv", "irr", "irr_all", "xirr",
    "loan_schedule", "equal_principal", "compare_plans",
    "tvm", "depreciation",
    "bond_price", "bond_ytm",
    "black_scholes",
    "cn_income_tax", "us_federal_tax",
]


# ===========================================================================
# 现金流：NPV / IRR / XIRR
# ===========================================================================

def npv(rate, cashflows):
    """rate 单位 %；cashflows[0] 为 t=0。"""
    r = float(rate) / 100.0
    if r <= -1:
        raise InputError("折现率须大于 -100%",
                         friendly_key="err_finance_rate")
    return sum(float(cf) / (1 + r) ** i
               for i, cf in enumerate(cashflows))


def _irr_f(r):
    return lambda cf: sum(c / (1 + r) ** i
                          for i, c in enumerate(cf))


def irr_all(cashflows, lo=-0.9999, hi=10.0, samples=2000):
    """扫描法找 IRR 的所有实数根。返回百分比列表（升序）。"""
    cfs = [float(x) for x in cashflows]
    if len(cfs) < 2:
        return []
    if all(x >= 0 for x in cfs) or all(x <= 0 for x in cfs):
        raise InputError("现金流符号单一，IRR 无解",
                         friendly_key="err_no_solution")

    f = _irr_f(0)
    step = (hi - lo) / samples
    roots = []
    prev_r = lo
    prev_v = f(prev_r)
    for i in range(1, samples + 1):
        r = lo + i * step
        v = f(r)
        if prev_v == 0:
            roots.append(prev_r)
        elif v == 0:
            roots.append(r)
        elif prev_v * v < 0:
            a, b = prev_r, r
            fa = prev_v
            for _ in range(80):
                m = (a + b) / 2
                fm = f(m)
                if fa * fm <= 0:
                    b = m
                else:
                    a, fa = m, fm
            roots.append((a + b) / 2)
        prev_r, prev_v = r, v

    uniq = []
    for r in sorted(roots):
        if not uniq or abs(r - uniq[-1]) > 1e-6:
            uniq.append(r)
    return [r * 100 for r in uniq]


def irr(cashflows, guess=0.1):
    """兼容旧接口：返回第一个 IRR。"""
    roots = irr_all(cashflows)
    if not roots:
        raise InputError("IRR 无解", friendly_key="err_no_solution")
    return roots[0]


def xirr(cashflows, dates, guess=0.1):
    """不规则现金流 IRR。dates 为 ISO 日期字符串列表。返回年化 %。"""
    if len(cashflows) != len(dates) or len(cashflows) < 2:
        raise InputError("现金流与日期长度需一致且至少 2 项",
                         friendly_key="err_input")

    parsed = []
    for d in dates:
        try:
            parsed.append(_dt.date.fromisoformat(str(d)))
        except Exception:
            raise InputError(f"日期非法：{d}",
                             friendly_key="err_date_format")

    base = min(parsed)
    years = [(d - base).days / 365.0 for d in parsed]
    cfs = [float(c) for c in cashflows]

    def f(r):
        if r <= -1:
            return float("inf")
        return sum(c / (1 + r) ** t for c, t in zip(cfs, years))

    lo, hi = -0.9999, 10.0
    flo, fhi = f(lo), f(hi)
    if flo * fhi > 0:
        raise InputError("XIRR 无解",
                         friendly_key="err_no_solution")
    for _ in range(200):
        mid = (lo + hi) / 2
        fm = f(mid)
        if abs(fm) < 1e-9:
            return mid * 100.0
        if flo * fm < 0:
            hi = mid
        else:
            lo, flo = mid, fm
    return (lo + hi) / 2 * 100.0


# ===========================================================================
# 贷款：等额本息 / 等额本金 / 对比
# ===========================================================================

def loan_schedule(principal, annual_rate, years,
                  kind="equal_payment"):
    """生成贷款摊销表。

    kind:
      - equal_payment    等额本息
      - equal_principal  等额本金
    """
    p = float(principal)
    r_year = float(annual_rate) / 100.0
    n = int(float(years) * 12)
    if p < 0:
        raise InputError("本金不能为负",
                         friendly_key="err_finance_neg")
    if n <= 0:
        raise InputError("年限必须大于 0",
                         friendly_key="err_finance_zero_years")
    if r_year < 0:
        raise InputError("利率不能为负",
                         friendly_key="err_finance_neg")

    r = r_year / 12.0
    schedule = []

    if kind == "equal_payment":
        if r == 0:
            m = p / n
        else:
            m = p * r * (1 + r) ** n / ((1 + r) ** n - 1)
        remaining = p
        total_payment = 0.0
        for i in range(1, n + 1):
            interest = remaining * r
            principal_part = m - interest
            remaining -= principal_part
            total_payment += m
            schedule.append({
                "period": i,
                "payment": round(m, 2),
                "principal": round(principal_part, 2),
                "interest": round(interest, 2),
                "remaining": round(max(remaining, 0.0), 2),
            })
        return {
            "kind": kind,
            "monthly_payment": round(m, 2),
            "first_month": round(m, 2),
            "last_month": round(m, 2),
            "total_payment": round(total_payment, 2),
            "total_interest": round(total_payment - p, 2),
            "months": n,
            "schedule": schedule,
        }

    if kind == "equal_principal":
        principal_part = p / n
        remaining = p
        total_payment = 0.0
        first = principal_part + p * r
        last = principal_part + principal_part * r
        for i in range(1, n + 1):
            interest = remaining * r
            payment = principal_part + interest
            remaining -= principal_part
            total_payment += payment
            schedule.append({
                "period": i,
                "payment": round(payment, 2),
                "principal": round(principal_part, 2),
                "interest": round(interest, 2),
                "remaining": round(max(remaining, 0.0), 2),
            })
        return {
            "kind": kind,
            "monthly_payment": round(first, 2),
            "first_month": round(first, 2),
            "last_month": round(last, 2),
            "total_payment": round(total_payment, 2),
            "total_interest": round(total_payment - p, 2),
            "months": n,
            "schedule": schedule,
        }

    raise InputError(f"未知贷款类型：{kind}",
                     friendly_key="err_finance_neg")


def equal_principal(principal, annual_rate, years):
    """兼容旧接口：等额本金摘要。"""
    info = loan_schedule(principal, annual_rate, years,
                         kind="equal_principal")
    return {
        "principal_part": round(float(principal) / info["months"], 2),
        "first_month": info["first_month"],
        "last_month": info["last_month"],
        "total": info["total_payment"],
        "interest": info["total_interest"],
        "months": info["months"],
    }


def compare_plans(principal, annual_rate, years):
    """等额本息 vs 等额本金对比摘要。"""
    a = loan_schedule(principal, annual_rate, years,
                      "equal_payment")
    b = loan_schedule(principal, annual_rate, years,
                      "equal_principal")
    return {
        "equal_payment": {k: a[k] for k in
                          ("monthly_payment", "total_payment",
                           "total_interest", "months")},
        "equal_principal": {k: b[k] for k in
                            ("first_month", "last_month",
                             "total_payment", "total_interest",
                             "months")},
        "savings": {
            "total_payment": round(
                a["total_payment"] - b["total_payment"], 2),
            "total_interest": round(
                a["total_interest"] - b["total_interest"], 2),
        },
    }


# ===========================================================================
# 时间价值 / 折旧
# ===========================================================================

def tvm(pv=None, fv=None, rate=None, nper=None, pmt=None,
        kind="end"):
    """TVM：已知四项求第五项。

    - pv : 现值（支出为负，收入为正）
    - fv : 终值
    - rate : 每期利率（%）
    - nper : 期数
    - pmt  : 每期支付
    - kind : "end" | "begin"
    """
    given = sum(x is not None for x in (pv, fv, rate, nper, pmt))
    if given < 4:
        raise InputError("TVM 需要至少四项已知",
                         friendly_key="err_finance_tvm")

    if pmt is None:
        r = float(rate) / 100.0
        n = float(nper)
        pv = float(pv)
        fv = float(fv)
        if r == 0:
            return -(fv + pv) / n
        factor = (1 + r) ** n
        adj = (1 + r) if kind == "begin" else 1.0
        return -((pv * factor + fv) * r / ((factor - 1) * adj))

    if pv is None:
        r = float(rate) / 100.0
        n = float(nper)
        fv = float(fv)
        p = float(pmt)
        adj = (1 + r) if kind == "begin" else 1.0
        if r == 0:
            return -(fv + p * n)
        factor = (1 + r) ** n
        return -(fv + p * (factor - 1) / r * adj) / factor

    if fv is None:
        r = float(rate) / 100.0
        n = float(nper)
        pv = float(pv)
        p = float(pmt)
        adj = (1 + r) if kind == "begin" else 1.0
        if r == 0:
            return -(pv + p * n)
        factor = (1 + r) ** n
        return -(pv * factor + p * (factor - 1) / r * adj)

    if nper is None:
        r = float(rate) / 100.0
        pv = float(pv)
        fv = float(fv)
        p = float(pmt)
        adj = (1 + r) if kind == "begin" else 1.0

        def f(n):
            if r == 0:
                return pv + p * n + fv
            return (pv * (1 + r) ** n
                    + p * ((1 + r) ** n - 1) / r * adj + fv)

        lo, hi = 0.01, 10000.0
        for _ in range(200):
            mid = (lo + hi) / 2
            if f(lo) * f(mid) <= 0:
                hi = mid
            else:
                lo = mid
        return (lo + hi) / 2

    if rate is None:
        pv = float(pv)
        fv = float(fv)
        n = float(nper)
        p = float(pmt)
        adj_begin = kind == "begin"

        def f(r):
            if abs(r) < 1e-12:
                return pv + p * n + fv
            adj = (1 + r) if adj_begin else 1.0
            return (pv * (1 + r) ** n
                    + p * ((1 + r) ** n - 1) / r * adj + fv)

        lo, hi = -0.9999, 10.0
        flo, fhi = f(lo), f(hi)
        if flo * fhi > 0:
            raise InputError("折现率无解",
                             friendly_key="err_no_solution")
        for _ in range(200):
            mid = (lo + hi) / 2
            fm = f(mid)
            if abs(fm) < 1e-9:
                return mid * 100
            if flo * fm < 0:
                hi = mid
            else:
                lo, flo = mid, fm
        return (lo + hi) / 2 * 100

    return None


def depreciation(cost, salvage, life, method="straight",
                 factor=2.0, year=None):
    """折旧计算。

    method:
      - straight         直线法
      - sum_of_years     年数总和法
      - double_declining 双倍余额递减法
    """
    c = float(cost)
    s = float(salvage)
    n = int(life)
    if c < 0 or s < 0 or n <= 0:
        raise InputError("参数非法", friendly_key="err_input")
    if s > c:
        raise InputError("残值不能超过成本",
                         friendly_key="err_input")

    out = []
    if method == "straight":
        d = (c - s) / n
        book = c
        for i in range(1, n + 1):
            book -= d
            out.append({
                "year": i,
                "depreciation": round(d, 2),
                "book_value": round(max(book, s), 2),
            })
    elif method == "sum_of_years":
        total = n * (n + 1) / 2
        book = c
        for i in range(1, n + 1):
            d = (c - s) * (n - i + 1) / total
            book -= d
            out.append({
                "year": i,
                "depreciation": round(d, 2),
                "book_value": round(max(book, s), 2),
            })
    elif method == "double_declining":
        rate = factor / n
        book = c
        for i in range(1, n + 1):
            d = book * rate
            if book - d < s:
                d = book - s
            book -= d
            out.append({
                "year": i,
                "depreciation": round(d, 2),
                "book_value": round(max(book, s), 2),
            })
    else:
        raise InputError(f"未知折旧方法：{method}",
                         friendly_key="err_input")

    result = {"method": method, "schedule": out}
    if year is not None:
        yi = int(year)
        if 1 <= yi <= n:
            result["year"] = yi
            result["depreciation"] = out[yi - 1]["depreciation"]
            result["book_value"] = out[yi - 1]["book_value"]
    return result


# ===========================================================================
# 债券
# ===========================================================================

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
        raise InputError(f"参数非法：{e}",
                         friendly_key="err_input")
    if F <= 0 or n <= 0 or f <= 0:
        raise InputError("面值/年限/频次须为正",
                         friendly_key="err_input")

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
        raise InputError(f"参数非法：{e}",
                         friendly_key="err_input")

    def f(y):
        try:
            return (bond_price(F, coupon_rate, years,
                               y * 100.0, freq)["price"]
                    - target)
        except Exception:
            return 1e18

    lo, hi = -0.99, 5.0
    flo, fhi = f(lo), f(hi)
    if flo * fhi > 0:
        raise InputError("无法求解 YTM",
                         friendly_key="err_no_solution")
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


# ===========================================================================
# 期权：Black-Scholes + Greeks
# ===========================================================================

def _norm_cdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def _norm_pdf(x):
    return math.exp(-0.5 * x * x) / math.sqrt(2 * math.pi)


def black_scholes(S, K, T, r, sigma, kind="call"):
    """S: 现价；K: 行权价；T: 年；r: 无风险利率（%）；
    sigma: 波动率（%）。"""
    try:
        S = float(S); K = float(K); T = float(T)
        r = float(r) / 100.0
        sigma = float(sigma) / 100.0
    except Exception as e:
        raise InputError(f"参数非法：{e}",
                         friendly_key="err_input")
    if S <= 0 or K <= 0 or T <= 0 or sigma <= 0:
        raise InputError("参数须为正", friendly_key="err_input")

    d1 = ((math.log(S / K)
           + (r + 0.5 * sigma * sigma) * T)
          / (sigma * math.sqrt(T)))
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


# ===========================================================================
# 个税
# ===========================================================================

_CN_BRACKETS = [
    (36000, 0.03, 0),
    (144000, 0.10, 2520),
    (300000, 0.20, 16920),
    (420000, 0.25, 31920),
    (660000, 0.30, 52920),
    (960000, 0.35, 85920),
    (float("inf"), 0.45, 181920),
]

_US_SINGLE = [
    (11600, 0.10, 0),
    (47150, 0.12, 1160),
    (100525, 0.22, 5426),
    (191950, 0.24, 17168.5),
    (243725, 0.32, 39110.5),
    (609350, 0.35, 55678.5),
    (float("inf"), 0.37, 183647.25),
]

_US_MARRIED = [
    (23200, 0.10, 0),
    (94300, 0.12, 2320),
    (201050, 0.22, 10852),
    (383900, 0.24, 34337),
    (487450, 0.32, 78221),
    (731200, 0.35, 111357),
    (float("inf"), 0.37, 367354),
]


def _apply_brackets(taxable, brackets):
    for limit, rate, quick in brackets:
        if taxable <= limit:
            return taxable * rate - quick
    return 0.0


def cn_income_tax(monthly_salary, social_insurance=0,
                  special_deduction=0, months=12):
    """中国个税（累计预扣法简化版）。

    monthly_salary: 月薪；social_insurance: 每月三险一金；
    special_deduction: 每月专项附加扣除；months: 已工作月数。
    """
    try:
        salary = float(monthly_salary)
        si = float(social_insurance)
        sd = float(special_deduction)
        n = int(months)
    except Exception as e:
        raise InputError(f"参数非法：{e}",
                         friendly_key="err_input")
    if n <= 0:
        raise InputError("months 必须大于 0",
                         friendly_key="err_input")

    cum_income = salary * n
    cum_deduct = (5000 + si + sd) * n
    cum_taxable = max(0.0, cum_income - cum_deduct)
    cum_tax = _apply_brackets(cum_taxable, _CN_BRACKETS)

    prev_income = salary * (n - 1)
    prev_deduct = (5000 + si + sd) * (n - 1)
    prev_taxable = max(0.0, prev_income - prev_deduct)
    prev_tax = _apply_brackets(prev_taxable, _CN_BRACKETS)

    return {
        "monthly_tax": cum_tax - prev_tax,
        "cumulative_income": cum_income,
        "cumulative_deduct": cum_deduct,
        "cumulative_taxable": cum_taxable,
        "cumulative_tax": cum_tax,
        "net_monthly": salary - si - (cum_tax - prev_tax),
    }


def us_federal_tax(annual_income, filing="single",
                   deductions=14600.0):
    """美国联邦所得税。

    filing: "single" / "married"。
    deductions: 标准扣除额（2024 单身 14600，夫妻 29200）。
    """
    try:
        inc = float(annual_income)
        ded = float(deductions)
    except Exception as e:
        raise InputError(f"参数非法：{e}",
                         friendly_key="err_input")

    taxable = max(0.0, inc - ded)
    brackets = _US_MARRIED if filing == "married" else _US_SINGLE
    tax = _apply_brackets(taxable, brackets)
    return {
        "annual_income": inc,
        "taxable": taxable,
        "tax": tax,
        "effective_rate": (tax / inc * 100.0 if inc > 0 else 0.0),
    }