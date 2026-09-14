"""个税：中国（累计预扣法）/ 美国联邦。"""
from __future__ import annotations

from core.errors import InputError


# 中国综合所得预扣率（年度累计）
_CN_BRACKETS = [
    (36000, 0.03, 0),
    (144000, 0.10, 2520),
    (300000, 0.20, 16920),
    (420000, 0.25, 31920),
    (660000, 0.30, 52920),
    (960000, 0.35, 85920),
    (float("inf"), 0.45, 181920),
]

# 美国 2024 单身联邦税率
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


def cn_income_tax(monthly_salary, social_insurance=0, special_deduction=0,
                  months=12):
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
        raise InputError(f"参数非法：{e}", friendly_key="err_input")
    if n <= 0:
        raise InputError("months 必须大于 0", friendly_key="err_input")

    # 累计收入、累计扣除
    cum_income = salary * n
    cum_deduct = (5000 + si + sd) * n
    cum_taxable = max(0.0, cum_income - cum_deduct)

    # 计算累计应纳税额
    cum_tax = _apply_brackets(cum_taxable, _CN_BRACKETS)

    # 假设前 n-1 个月已按月正常预扣，本月应扣 = 累计 - 已扣
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
        raise InputError(f"参数非法：{e}", friendly_key="err_input")

    taxable = max(0.0, inc - ded)
    brackets = _US_MARRIED if filing == "married" else _US_SINGLE
    return {
        "annual_income": inc,
        "taxable": taxable,
        "tax": _apply_brackets(taxable, brackets),
        "effective_rate": (_apply_brackets(taxable, brackets) / inc * 100.0
                           if inc > 0 else 0.0),
    }