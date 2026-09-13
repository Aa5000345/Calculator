"""物理 / 数学常数库。

每个条目：(符号, 数值, [单位], 中文说明)。
数值用 sympy 对象以保证精度；用 `sp.Float(x, 20)` 可提升精度。
"""
from __future__ import annotations

import sympy as sp

MATH_CONSTANTS = {
    "pi":     ("π",   sp.pi,            "",    "圆周率"),
    "E":      ("e",   sp.E,             "",    "自然常数"),
    "golden": ("φ",   (1 + sp.sqrt(5)) / 2, "", "黄金比例"),
    "euler":  ("γ",   sp.EulerGamma,    "",    "欧拉-马歇罗尼常数"),
    "catalan":("G",   sp.Catalan,       "",    "卡塔兰常数"),
    "oo":     ("∞",   sp.oo,            "",    "无穷大"),
}

PHYSICS_CONSTANTS = {
    "c":     ("c",    299792458.0,            "m/s",         "真空中光速"),
    "h":     ("h",    6.62607015e-34,         "J·s",         "普朗克常数"),
    "hbar":  ("ℏ",    1.054571817e-34,        "J·s",         "约化普朗克常数"),
    "G":     ("G",    6.67430e-11,            "m³/(kg·s²)",  "万有引力常数"),
    "e":     ("e",    1.602176634e-19,        "C",           "元电荷"),
    "me":    ("mₑ",   9.1093837015e-31,       "kg",          "电子质量"),
    "mp":    ("mₚ",   1.67262192369e-27,      "kg",          "质子质量"),
    "mn":    ("mₙ",   1.67492749804e-27,      "kg",          "中子质量"),
    "NA":    ("N_A",  6.02214076e23,          "1/mol",       "阿伏伽德罗常数"),
    "kB":    ("k_B",  1.380649e-23,           "J/K",         "玻尔兹曼常数"),
    "R":     ("R",    8.31446261815324,       "J/(mol·K)",   "摩尔气体常数"),
    "F":     ("F",    96485.33212,            "C/mol",       "法拉第常数"),
    "sigma": ("σ",    5.670374419e-8,         "W/(m²·K⁴)",   "斯特藩-玻尔兹曼常数"),
    "mu0":   ("μ₀",   1.25663706212e-6,       "N/A²",        "真空磁导率"),
    "eps0":  ("ε₀",   8.8541878128e-12,       "F/m",         "真空电容率"),
    "atm":   ("atm",  101325.0,               "Pa",          "标准大气压"),
    "g":     ("g",    9.80665,                "m/s²",        "标准重力加速度"),
    "au":    ("au",   1.495978707e11,         "m",           "天文单位"),
    "ly":    ("ly",   9.4607304725808e15,     "m",           "光年"),
    "pc":    ("pc",   3.0856775814914e16,     "m",           "秒差距"),
}


def all_constants():
    """合并两套常数，返回 {key: (sym, val, unit, desc)}。"""
    out = {}
    for k, (sym, val, desc) in MATH_CONSTANTS.items():
        out[k] = (sym, val, "", desc)
    for k, (sym, val, unit, desc) in PHYSICS_CONSTANTS.items():
        out[k] = (sym, val, unit, desc)
    return out


def lookup(key: str):
    return all_constants().get(key)