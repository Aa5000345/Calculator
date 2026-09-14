"""农历：优先使用 lunardate / zhdate；缺失时给出清晰提示。"""
from __future__ import annotations

import datetime as dt

from core.errors import InputError


def solar_to_lunar(date_str):
    """公历 → 农历。返回 {lunar_year, month, day, is_leap, ganzhi, animal}。"""
    try:
        d = dt.date.fromisoformat(str(date_str))
    except Exception:
        raise InputError("日期格式应为 YYYY-MM-DD",
                         friendly_key="err_date_format")
    try:
        from lunardate import LunarDate
        ld = LunarDate.fromSolarDate(d.year, d.month, d.day)
        # 生肖、天干地支
        gz = _ganzhi(ld.year)
        return {
            "lunar_year": ld.year,
            "month": ld.month,
            "day": ld.day,
            "is_leap": bool(ld.isLeapMonth),
            "ganzhi": gz,
            "animal": _animal(ld.year),
            "chinese": f"{gz}年 {ld.month}月{ld.day}日",
        }
    except ImportError:
        raise InputError(
            "需要安装 lunardate：pip install lunardate",
            friendly_key="err_input")


_GAN = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
_ZHI = ["子", "丑", "寅", "卯", "辰", "巳",
        "午", "未", "申", "酉", "戌", "亥"]
_ANIMALS = ["鼠", "牛", "虎", "兔", "龙", "蛇",
            "马", "羊", "猴", "鸡", "狗", "猪"]


def _ganzhi(year):
    return _GAN[(year - 4) % 10] + _ZHI[(year - 4) % 12]


def _animal(year):
    return _ANIMALS[(year - 4) % 12]