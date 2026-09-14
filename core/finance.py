"""财务扩展：NPV / IRR（多解检测）/ 等额本金 / 摊销表 / 折旧 / TVM。"""
from __future__ import annotations

from core.errors import InputError


# ---------------------------------------------------------------------------
# NPV / IRR
# ---------------------------------------------------------------------------

def npv(rate, cashflows):
    """rate 单位 %；cashflows[0] 为 t=0。"""
    r = float(rate) / 100.0
    if r <= -1:
        raise InputError("折现率须大于 -100%",
                         friendly_key="err_finance_rate")
    return sum(float(cf) / (1 + r) ** i for i, cf in enumerate(cashflows))


def _irr_f(r):
    return lambda cf: sum(c / (1 + r) ** i for i, c in enumerate(cf))


def irr_all(cashflows, lo=-0.9999, hi=10.0, samples=2000):
    """扫描法找 IRR 的所有实数根。

    返回按升序排列的 IRR 百分比列表。
    """
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
            # 二分细化
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

    # 去重（相同根相差 < 1e-6）
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


# ---------------------------------------------------------------------------
# 等额本息 / 等额本金
# ---------------------------------------------------------------------------

def loan_schedule(principal, annual_rate, years, kind="equal_payment"):
    """生成贷款摊销表。

    kind:
      - ``equal_payment``  等额本息
      - ``equal_principal`` 等额本金
    返回 dict：
      - monthly_payment     每月还款额（等额本金时为首月）
      - total_payment
      - total_interest
      - months
      - schedule            列表，每项 {period, payment, principal, interest, remaining}
    """
    p = float(principal)
    r_year = float(annual_rate) / 100.0
    n = int(float(years) * 12)
    if p < 0:
        raise InputError("本金不能为负", friendly_key="err_finance_neg")
    if n <= 0:
        raise InputError("年限必须大于 0",
                         friendly_key="err_finance_zero_years")
    if r_year < 0:
        raise InputError("利率不能为负", friendly_key="err_finance_neg")

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
    a = loan_schedule(principal, annual_rate, years, "equal_payment")
    b = loan_schedule(principal, annual_rate, years, "equal_principal")
    return {
        "equal_payment": {k: a[k] for k in
                          ("monthly_payment", "total_payment",
                           "total_interest", "months")},
        "equal_principal": {k: b[k] for k in
                            ("first_month", "last_month",
                             "total_payment", "total_interest", "months")},
        "savings": {
            "total_payment": round(
                a["total_payment"] - b["total_payment"], 2),
            "total_interest": round(
                a["total_interest"] - b["total_interest"], 2),
        },
    }


# ---------------------------------------------------------------------------
# 货币时间价值 / 折旧
# ---------------------------------------------------------------------------

def tvm(pv=None, fv=None, rate=None, nper=None, pmt=None, kind="end"):
    """TVM：已知四项求第五项。

    - pv : 现值（支出为负，收入为正）
    - fv : 终值
    - rate : 每期利率（%）
    - nper : 期数
    - pmt  : 每期支付
    - kind : "end" | "begin"

    返回缺失的一项；若五项都给则返回 fv。
    """
    given = sum(x is not None for x in (pv, fv, rate, nper, pmt))
    if given < 4:
        raise InputError("TVM 需要至少四项已知",
                         friendly_key="err_finance_tvm")

    if pmt is None:
        # 由 pv, fv, rate, nper 求 pmt
        r = float(rate) / 100.0
        n = float(nper)
        pv = float(pv)
        fv = float(fv)
        if r == 0:
            return -(fv + pv) / n
        # FV = PV(1+r)^n + PMT * [((1+r)^n - 1) / r] * (1 + r * begin)
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
        # 二分法：已知 pv, fv, pmt, rate
        r = float(rate) / 100.0
        pv = float(pv)
        fv = float(fv)
        p = float(pmt)
        adj = (1 + r) if kind == "begin" else 1.0

        def f(n):
            if r == 0:
                return pv + p * n + fv
            return pv * (1 + r) ** n + p * ((1 + r) ** n - 1) / r * adj + fv

        lo, hi = 0.01, 10000.0
        for _ in range(200):
            mid = (lo + hi) / 2
            if f(lo) * f(mid) <= 0:
                hi = mid
            else:
                lo = mid
        return (lo + hi) / 2

    if rate is None:
        # 二分求 rate
        pv = float(pv)
        fv = float(fv)
        n = float(nper)
        p = float(pmt)
        adj_begin = kind == "begin"

        def f(r):
            if abs(r) < 1e-12:
                return pv + p * n + fv
            adj = (1 + r) if adj_begin else 1.0
            return pv * (1 + r) ** n + p * ((1 + r) ** n - 1) / r * adj + fv

        lo, hi = -0.9999, 10.0
        flo, fhi = f(lo), f(hi)
        if flo * fhi > 0:
            raise InputError("折现率无解", friendly_key="err_no_solution")
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


def depreciation(cost, salvage, life, method="straight", factor=2.0,
                 year=None):
    """折旧计算。

    method:
      - ``straight``        直线法
      - ``sum_of_years``    年数总和法
      - ``double_declining`` 双倍余额递减法
    返回每年的折旧额与净值；若给定 year，再返回该年折旧额。
    """
    c = float(cost)
    s = float(salvage)
    n = int(life)
    if c < 0 or s < 0 or n <= 0:
        raise InputError("参数非法", friendly_key="err_input")
    if s > c:
        raise InputError("残值不能超过成本", friendly_key="err_input")

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

def xirr(cashflows, dates, guess=0.1):
    """不规则现金流 IRR。

    cashflows: 数值列表；dates: ISO 日期字符串列表（同长度）。
    返回年化收益率（%）。
    """
    import datetime as _dt

    if len(cashflows) != len(dates) or len(cashflows) < 2:
        raise InputError("现金流与日期长度需一致且至少 2 项",
                         friendly_key="err_input")

    parsed = []
    for d in dates:
        try:
            parsed.append(_dt.date.fromisoformat(str(d)))
        except Exception:
            raise InputError(f"日期非法：{d}", friendly_key="err_date_format")

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
        raise InputError("XIRR 无解", friendly_key="err_no_solution")
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