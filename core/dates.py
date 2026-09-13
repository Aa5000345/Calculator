"""日期扩展：工作日 / 节假日 / 时区 / 时间戳 / 年龄。

修复：工作日计算真正排除 ``holidays`` 库中的法定节假日。
"""
from __future__ import annotations

import datetime as dt

import holidays as holiday_lib
import pytz
from dateutil import parser as dateparser


def parse_date(s):
    try:
        return dateparser.parse(str(s)).date()
    except Exception as e:  # noqa: BLE001
        from core.errors import InputError
        raise InputError(f"日期非法：{e}", friendly_key="err_date_format")


def is_leap(year) -> bool:
    return (year % 4 == 0 and year % 100 != 0) or year % 400 == 0


def _holiday_set(country: str, years) -> set:
    years = sorted({int(y) for y in years})
    if not years:
        return set()
    try:
        h = holiday_lib.country_holidays(country.upper(), years=years)
        return set(h.keys())
    except Exception:
        return set()


def date_diff_info(d1, d2, country: str = "CN",
                   exclude_holidays: bool = True) -> dict:
    """日期差信息。

    - ``workdays`` 真正排除周末 + ``country`` 的法定节假日；
    - ``holidays_in_range`` 记录区间内被排除的节假日数量。
    """
    a, b = parse_date(d1), parse_date(d2)
    days = (b - a).days
    info = {
        "days": days,
        "abs_days": abs(days),
        "weeks": abs(days) // 7,
        "remaining_days": abs(days) % 7,
        "cross_year": a.year != b.year,
        "leap_in_range": any(
            is_leap(y) for y in range(min(a.year, b.year),
                                      max(a.year, b.year) + 1)),
        "country": (country or "CN").upper(),
        "exclude_holidays": bool(exclude_holidays),
    }

    holiday_set = set()
    if exclude_holidays:
        holiday_set = _holiday_set(
            country or "CN",
            range(min(a.year, b.year), max(a.year, b.year) + 2),
        )

    workdays = 0
    holiday_count = 0
    cur = a
    step = 1 if b >= a else -1
    while cur != b:
        is_work = cur.weekday() < 5
        if exclude_holidays and cur in holiday_set:
            if is_work:
                holiday_count += 1
            is_work = False
        if is_work:
            workdays += 1
        cur += dt.timedelta(days=step)

    info["workdays"] = workdays
    info["holidays_in_range"] = holiday_count
    return info


def add_days(date_str, days):
    d = parse_date(date_str)
    return (d + dt.timedelta(days=int(days))).strftime("%Y-%m-%d")


def country_holidays(country, year):
    try:
        h = holiday_lib.country_holidays(country.upper(), years=int(year))
        return {str(k): str(v) for k, v in h.items()}
    except Exception:
        return {}


def to_timestamp(date_str, tz="UTC"):
    d = parse_date(date_str)
    zone = pytz.timezone(tz)
    aware = zone.localize(dt.datetime.combine(d, dt.time()))
    return int(aware.timestamp())


def from_timestamp(ts, tz="UTC"):
    zone = pytz.timezone(tz)
    return dt.datetime.fromtimestamp(float(ts), zone).strftime(
        "%Y-%m-%d %H:%M:%S %Z")


def age(birth, as_of=None):
    b = parse_date(birth)
    a = parse_date(as_of) if as_of else dt.date.today()
    years = a.year - b.year - ((a.month, a.day) < (b.month, b.day))
    months = (a.month - b.month) % 12
    # 近似 days：本年内剩余天数
    anchor_year = a.year if (a.month, a.day) >= (b.month, b.day) else a.year - 1
    try:
        anchor = dt.date(anchor_year, b.month,
                         min(b.day, 28) if b.month == 2 else b.day)
    except ValueError:
        anchor = dt.date(anchor_year, b.month, 28)
    days = (a - anchor).days
    return {
        "years": years,
        "months": months,
        "days": days,
        "total_days": (a - b).days,
    }
# ===========================================================================
# 第四轮新增：倒计时 / 周数 / 季度 / 时区转换 / 精确年龄
# ===========================================================================

def countdown(target, from_date=None):
    """距目标日期剩余天数、周数、小时、分钟。"""
    t = parse_date(target)
    a = parse_date(from_date) if from_date else dt.date.today()
    delta = t - a
    total_days = delta.days
    return {
        "target": str(t),
        "from": str(a),
        "days": total_days,
        "weeks": total_days // 7,
        "remaining_days": total_days % 7,
        "total_hours": total_days * 24,
        "total_minutes": total_days * 24 * 60,
        "past": total_days < 0,
    }


def week_info(date_str):
    """返回 ISO 周信息、季度、年内第几天。"""
    d = parse_date(date_str)
    iso = d.isocalendar()  # (year, week, weekday)
    quarter = (d.month - 1) // 3 + 1
    day_of_year = d.timetuple().tm_yday
    return {
        "date": str(d),
        "iso_year": iso[0],
        "iso_week": iso[1],
        "iso_weekday": iso[2],
        "quarter": quarter,
        "day_of_year": day_of_year,
        "weekday_name": d.strftime("%A"),
    }


def week_range(date_str):
    """返回该日期所在 ISO 周的起止日期。"""
    d = parse_date(date_str)
    start = d - dt.timedelta(days=d.weekday())
    end = start + dt.timedelta(days=6)
    return {"start": str(start), "end": str(end),
            "iso_week": d.isocalendar()[1]}


def timezone_convert(datetime_str, from_tz, to_tz):
    """时区转换。

    datetime_str 支持 'YYYY-MM-DD HH:MM[:SS]' 或 'YYYY-MM-DD'。
    """
    s = str(datetime_str).strip()
    parsed = None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            parsed = dt.datetime.strptime(s, fmt)
            break
        except ValueError:
            continue
    if parsed is None:
        raise ValueError(f"日期时间格式非法：{s}")

    src = pytz.timezone(from_tz)
    dst = pytz.timezone(to_tz)
    aware = src.localize(parsed)
    converted = aware.astimezone(dst)
    return {
        "input": parsed.strftime("%Y-%m-%d %H:%M:%S"),
        "from_tz": from_tz,
        "to_tz": to_tz,
        "output": converted.strftime("%Y-%m-%d %H:%M:%S %Z%z"),
        "utc": converted.astimezone(pytz.UTC).strftime(
            "%Y-%m-%d %H:%M:%S UTC"),
    }


def age_precise(birth, as_of=None):
    """年龄精确到年、月、日、总天数、总周数、总小时。"""
    b = parse_date(birth)
    a = parse_date(as_of) if as_of else dt.date.today()

    years = a.year - b.year
    months = a.month - b.month
    days = a.day - b.day
    if days < 0:
        months -= 1
        # 上个月的天数
        prev_month = a.month - 1 or 12
        prev_year = a.year if a.month > 1 else a.year - 1
        try:
            last_month_days = (
                dt.date(prev_year, prev_month % 12 or 12, 1)
                + dt.timedelta(days=31)
            ).replace(day=1) - dt.timedelta(days=1)
            days += last_month_days.day
        except Exception:
            days += 30
    if months < 0:
        years -= 1
        months += 12

    total_days = (a - b).days
    return {
        "years": years,
        "months": months,
        "days": days,
        "total_days": total_days,
        "total_weeks": total_days // 7,
        "total_hours": total_days * 24,
        "total_months": years * 12 + months,
        "next_birthday_days": _days_to_next_birthday(b, a),
    }


def _days_to_next_birthday(birth: dt.date, today: dt.date) -> int:
    try:
        this_year = birth.replace(year=today.year)
    except ValueError:  # 2/29
        this_year = dt.date(today.year, 2, 28)
    if this_year < today:
        try:
            next_year = birth.replace(year=today.year + 1)
        except ValueError:
            next_year = dt.date(today.year + 1, 2, 28)
        return (next_year - today).days
    return (this_year - today).days


def date_info(date_str):
    """综合日期信息：周数、季度、闰年、星座、生肖。"""
    d = parse_date(date_str)
    return {
        **week_info(str(d)),
        "leap": is_leap(d.year),
        "zodiac": _zodiac(d),
        "chinese_zodiac": _chinese_zodiac(d.year),
    }


_ZODIAC_RANGES = [
    ((1, 20), "水瓶座"), ((2, 19), "双鱼座"), ((3, 21), "白羊座"),
    ((4, 20), "金牛座"), ((5, 21), "双子座"), ((6, 22), "巨蟹座"),
    ((7, 23), "狮子座"), ((8, 23), "处女座"), ((9, 23), "天秤座"),
    ((10, 24), "天蝎座"), ((11, 22), "射手座"), ((12, 22), "摩羯座"),
]


def _zodiac(d: dt.date) -> str:
    md = (d.month, d.day)
    for (m, day), name in _ZODIAC_RANGES:
        if md < (m, day):
            prev = _ZODIAC_RANGES[_ZODIAC_RANGES.index(
                ((m, day), name)) - 1][1]
            return prev
    return "摩羯座"


_CHINESE_ZODIAC = ["鼠", "牛", "虎", "兔", "龙", "蛇",
                   "马", "羊", "猴", "鸡", "狗", "猪"]


def _chinese_zodiac(year: int) -> str:
    return _CHINESE_ZODIAC[(year - 4) % 12]
