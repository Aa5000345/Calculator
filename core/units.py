"""单位类别元数据：供 UI 下拉与快捷按钮使用。

- ``label``：类别中文名
- ``base``：pint 可识别的基准单位
- ``units``：[(显示名, pint 名), ...]
- ``temperature`` 类别需要特殊换算（pint 通过 offset unit 支持，
  但为了方便 UI 只做线性转换之外的最小支持，这里标记）。
"""
from __future__ import annotations

UNIT_CATEGORIES = {
    "length": {
        "label": "长度", "base": "m",
        "units": [
            ("m", "m"), ("km", "km"), ("cm", "cm"), ("mm", "mm"),
            ("μm", "um"), ("nm", "nm"),
            ("mi", "mi"), ("yd", "yd"), ("ft", "ft"), ("in", "in"),
            ("nmi", "nmi"), ("ly", "ly"), ("au", "au"),
        ],
    },
    "mass": {
        "label": "质量", "base": "kg",
        "units": [
            ("kg", "kg"), ("g", "g"), ("mg", "mg"), ("μg", "ug"),
            ("t", "metric_ton"), ("lb", "lb"), ("oz", "oz"),
            ("st", "stone"), ("ct", "carat"),
        ],
    },
    "area": {
        "label": "面积", "base": "m^2",
        "units": [
            ("m²", "m^2"), ("km²", "km^2"), ("cm²", "cm^2"),
            ("ha", "hectare"), ("acre", "acre"),
            ("ft²", "ft^2"), ("in²", "in^2"),
        ],
    },
    "volume": {
        "label": "体积", "base": "m^3",
        "units": [
            ("m³", "m^3"), ("L", "L"), ("mL", "mL"), ("cm³", "cm^3"),
            ("gal", "gallon"), ("qt", "quart"), ("pt", "pint"),
            ("cup", "cup"), ("floz", "fluid_ounce"),
        ],
    },
    "temperature": {
        "label": "温度", "base": "kelvin",
        "units": [
            ("K", "kelvin"), ("°C", "degree_Celsius"),
            ("°F", "degree_Fahrenheit"), ("°R", "degree_Rankine"),
        ],
    },
    "speed": {
        "label": "速度", "base": "m/s",
        "units": [
            ("m/s", "m/s"), ("km/h", "km/h"), ("mph", "mph"),
            ("knot", "knot"), ("ft/s", "ft/s"),
        ],
    },
    "pressure": {
        "label": "压力", "base": "Pa",
        "units": [
            ("Pa", "Pa"), ("kPa", "kPa"), ("MPa", "MPa"),
            ("bar", "bar"), ("atm", "atm"),
            ("mmHg", "mmHg"), ("psi", "psi"),
        ],
    },
    "energy": {
        "label": "能量", "base": "J",
        "units": [
            ("J", "J"), ("kJ", "kJ"), ("cal", "cal"),
            ("kcal", "kcal"), ("Wh", "Wh"), ("kWh", "kWh"),
            ("eV", "eV"), ("BTU", "BTU"),
        ],
    },
    "power": {
        "label": "功率", "base": "W",
        "units": [
            ("W", "W"), ("kW", "kW"), ("MW", "MW"), ("hp", "hp"),
        ],
    },
    "data": {
        "label": "数据", "base": "byte",
        "units": [
            ("B", "byte"), ("KB", "kbyte"), ("MB", "Mbyte"),
            ("GB", "Gbyte"), ("TB", "Tbyte"),
            ("KiB", "KiB"), ("MiB", "MiB"), ("GiB", "GiB"),
            ("bit", "bit"),
        ],
    },
    "time": {
        "label": "时间", "base": "s",
        "units": [
            ("s", "s"), ("ms", "ms"), ("μs", "us"),
            ("min", "minute"), ("h", "hour"), ("d", "day"),
            ("wk", "week"), ("yr", "year"),
        ],
    },
    "angle": {
        "label": "角度", "base": "rad",
        "units": [
            ("rad", "rad"), ("deg", "deg"), ("grad", "grad"),
            ("arcmin", "arcmin"), ("arcsec", "arcsec"),
        ],
    },
}


def categories() -> list[str]:
    return list(UNIT_CATEGORIES.keys())


def get_category(key: str):
    return UNIT_CATEGORIES.get(key)


def default_units(key: str):
    """返回 (from_unit, to_unit) 默认对。"""
    cat = UNIT_CATEGORIES.get(key)
    if not cat:
        return ("m", "cm")
    units = cat["units"]
    if len(units) >= 2:
        return (units[0][1], units[1][1])
    return (units[0][1], units[0][1])