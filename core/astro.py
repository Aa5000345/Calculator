"""日出日落：使用 astral 计算；缺失时给出清晰提示。"""
from __future__ import annotations

import datetime as dt

from core.errors import InputError


def sun_times(date_str, latitude, longitude, timezone="Asia/Shanghai"):
    """返回当日日出、日落、昼长（小时）、太阳正午。"""
    try:
        d = dt.date.fromisoformat(str(date_str))
    except Exception:
        raise InputError("日期格式应为 YYYY-MM-DD",
                         friendly_key="err_date_format")
    try:
        lat = float(latitude)
        lon = float(longitude)
    except Exception as e:
        raise InputError(f"经纬度非法：{e}", friendly_key="err_input")

    try:
        from astral import LocationInfo
        from astral.sun import sun as _sun
        from zoneinfo import ZoneInfo
    except ImportError:
        raise InputError(
            "需要安装 astral：pip install astral",
            friendly_key="err_input")

    try:
        tz = ZoneInfo(timezone)
    except Exception:
        tz = dt.timezone.utc

    info = LocationInfo(latitude=lat, longitude=lon)
    try:
        s = _sun(info.observer, date=d, tzinfo=tz)
    except Exception as e:
        raise InputError(f"计算失败（极昼/极夜？）：{e}",
                         friendly_key="err_input")

    dawn = s.get("dawn")
    sunrise = s.get("sunrise")
    noon = s.get("noon")
    sunset = s.get("sunset")
    dusk = s.get("dusk")

    day_hours = None
    if sunrise and sunset:
        day_hours = (sunset - sunrise).total_seconds() / 3600.0

    def _fmt(x):
        return x.strftime("%Y-%m-%d %H:%M:%S") if x else None

    return {
        "dawn": _fmt(dawn),
        "sunrise": _fmt(sunrise),
        "noon": _fmt(noon),
        "sunset": _fmt(sunset),
        "dusk": _fmt(dusk),
        "day_hours": day_hours,
        "timezone": timezone,
    }