"""数字系统转换 + 符号库。

合并自：core/number_systems.py + core/glyph_library.py

对外接口：
    # 数字系统
    to_roman, from_roman, to_chinese, from_chinese,
    to_english, from_english, to_morse, from_morse,
    to_arabic, from_arabic, convert, list_systems, SYSTEMS
    # 符号库
    Glyph, Category, CATEGORIES, categories, get_category,
    all_glyphs, by_category, search, get_by_char,
    favorites, is_favorite, toggle_favorite
"""
from __future__ import annotations

import json
import os
import re
import threading
from dataclasses import dataclass

from core.base import InputError

__all__ = [
    # 数字系统
    "to_roman", "from_roman", "to_chinese", "from_chinese",
    "to_english", "from_english", "to_morse", "from_morse",
    "to_arabic", "from_arabic", "convert",
    "list_systems", "SYSTEMS",
    # 符号库
    "Glyph", "Category", "CATEGORIES", "categories",
    "get_category", "all_glyphs", "by_category", "search",
    "get_by_char", "favorites", "is_favorite", "toggle_favorite",
]


# ===========================================================================
# 数字系统：罗马
# ===========================================================================

_ROMAN_PAIRS = [
    (1000, "M"), (900, "CM"), (500, "D"), (400, "CD"),
    (100, "C"), (90, "XC"), (50, "L"), (40, "XL"),
    (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I"),
]

_ROMAN_VALUES = {
    "I": 1, "V": 5, "X": 10, "L": 50,
    "C": 100, "D": 500, "M": 1000,
}


def to_roman(n) -> str:
    try:
        n = int(n)
    except (TypeError, ValueError):
        raise InputError(f"不是整数：{n!r}")
    if n <= 0:
        raise InputError("罗马数字不支持 0 或负数")
    if n > 3999:
        raise InputError("经典罗马数字最大 3999（MMMCMXCIX）")

    out = []
    for value, sym in _ROMAN_PAIRS:
        while n >= value:
            out.append(sym)
            n -= value
    return "".join(out)


def from_roman(s) -> int:
    s = str(s).strip().upper().replace(" ", "")
    if not s:
        raise InputError("输入为空")
    total = 0
    prev = 0
    for ch in reversed(s):
        if ch not in _ROMAN_VALUES:
            raise InputError(f"非法罗马字符：{ch!r}")
        v = _ROMAN_VALUES[ch]
        if v < prev:
            total -= v
        else:
            total += v
            prev = v
    if total <= 0:
        raise InputError(f"非法罗马数字：{s}")
    return total


# ===========================================================================
# 数字系统：中文
# ===========================================================================

_CN_DIGITS_LOWER = "零一二三四五六七八九"
_CN_DIGITS_UPPER = "零壹贰叁肆伍陆柒捌玖"
_CN_UNITS_LOWER = ["", "十", "百", "千"]
_CN_UNITS_UPPER = ["", "拾", "佰", "仟"]
_CN_BIG_LOWER = ["", "万", "亿", "万亿"]
_CN_BIG_UPPER = ["", "万", "亿", "万亿"]


def _four_digits_to_chinese(n: int, digits: str,
                            units: list) -> str:
    if n == 0:
        return ""
    s = ""
    zero_pending = False
    for pos in range(3, -1, -1):
        d = (n // (10 ** pos)) % 10
        if d == 0:
            if s:
                zero_pending = True
            continue
        if zero_pending:
            s += digits[0]
            zero_pending = False
        s += digits[d] + units[pos]
    return s


def to_chinese(n, formal: bool = False) -> str:
    try:
        n = int(n)
    except (TypeError, ValueError):
        raise InputError(f"不是整数：{n!r}")
    if n < 0:
        return "负" + to_chinese(-n, formal)
    if n == 0:
        return "零"

    digits = _CN_DIGITS_UPPER if formal else _CN_DIGITS_LOWER
    units = _CN_UNITS_UPPER if formal else _CN_UNITS_LOWER
    big_units = _CN_BIG_UPPER if formal else _CN_BIG_LOWER

    groups = []
    m = n
    while m > 0:
        groups.append(m % 10000)
        m //= 10000

    parts = []
    for gi in range(len(groups) - 1, -1, -1):
        g = groups[gi]
        if g == 0:
            if parts and not parts[-1].endswith("零"):
                parts.append("零")
            continue
        s = _four_digits_to_chinese(g, digits, units)
        parts.append(s + big_units[gi])

    result = "".join(parts)
    result = re.sub(r"零+", "零", result).rstrip("零")

    if not formal and result.startswith("一十"):
        result = result[1:]

    return result


_CN_TO_DIGIT: dict = {}
for _i, _c in enumerate(_CN_DIGITS_LOWER):
    _CN_TO_DIGIT[_c] = _i
for _i, _c in enumerate(_CN_DIGITS_UPPER):
    _CN_TO_DIGIT[_c] = _i

_CN_UNIT_VALUES = {
    "十": 10, "拾": 10,
    "百": 100, "佰": 100,
    "千": 1000, "仟": 1000,
    "万": 10000, "萬": 10000,
    "亿": 100000000, "億": 100000000,
}


def from_chinese(s) -> int:
    s = str(s).strip()
    if not s:
        raise InputError("输入为空")
    neg = False
    if s.startswith("负"):
        neg = True
        s = s[1:]
    if s == "零":
        return 0

    total = 0
    section = 0
    number = 0
    for ch in s:
        if ch in _CN_TO_DIGIT:
            number = _CN_TO_DIGIT[ch]
        elif ch in _CN_UNIT_VALUES:
            unit = _CN_UNIT_VALUES[ch]
            if unit >= 10000:
                section = (section + number) * unit
                total += section
                section = 0
                number = 0
            else:
                if number == 0:
                    number = 1
                section += number * unit
                number = 0
        else:
            raise InputError(f"非法中文字符：{ch!r}")
    total += section + number
    return -total if neg else total


# ===========================================================================
# 数字系统：英文
# ===========================================================================

_EN_ONES = [
    "zero", "one", "two", "three", "four", "five", "six",
    "seven", "eight", "nine", "ten", "eleven", "twelve",
    "thirteen", "fourteen", "fifteen", "sixteen",
    "seventeen", "eighteen", "nineteen",
]
_EN_TENS = [
    "", "", "twenty", "thirty", "forty", "fifty",
    "sixty", "seventy", "eighty", "ninety",
]
_EN_SCALES = [
    (10 ** 12, "trillion"),
    (10 ** 9, "billion"),
    (10 ** 6, "million"),
    (10 ** 3, "thousand"),
]

_EN_NUM_WORDS: dict = {}
for _i, _w in enumerate(_EN_ONES):
    _EN_NUM_WORDS[_w] = _i
for _i, _w in enumerate(_EN_TENS):
    if _w:
        _EN_NUM_WORDS[_w] = _i * 10
_EN_NUM_WORDS.update({
    "hundred": 100, "thousand": 10 ** 3,
    "million": 10 ** 6, "billion": 10 ** 9,
    "trillion": 10 ** 12,
})


def to_english(n) -> str:
    try:
        n = int(n)
    except (TypeError, ValueError):
        raise InputError(f"不是整数：{n!r}")
    if n < 0:
        return "negative " + to_english(-n)
    if n < 20:
        return _EN_ONES[n]
    if n < 100:
        t, r = divmod(n, 10)
        base = _EN_TENS[t]
        return base if r == 0 else f"{base}-{_EN_ONES[r]}"
    if n < 1000:
        h, r = divmod(n, 100)
        base = f"{_EN_ONES[h]} hundred"
        return base if r == 0 else f"{base} {to_english(r)}"

    for scale_value, scale_name in _EN_SCALES:
        if n >= scale_value:
            q, r = divmod(n, scale_value)
            base = f"{to_english(q)} {scale_name}"
            return base if r == 0 else f"{base} {to_english(r)}"

    raise InputError(f"超出支持范围：{n}")


def from_english(s) -> int:
    s = str(s).strip().lower()
    if not s:
        raise InputError("输入为空")
    neg = False
    if s.startswith("negative "):
        neg = True
        s = s[len("negative "):]
    if s == "zero":
        return 0

    s = s.replace("-", " ")
    words = s.split()

    total = 0
    current = 0
    for w in words:
        if w not in _EN_NUM_WORDS:
            raise InputError(f"未知英文数字：{w!r}")
        v = _EN_NUM_WORDS[w]
        if v == 100:
            current = (current or 1) * 100
        elif v >= 1000:
            current = (current or 1) * v
            total += current
            current = 0
        else:
            current += v
    total += current
    return -total if neg else total


# ===========================================================================
# 数字系统：摩尔斯
# ===========================================================================

_MORSE_DIGITS = {
    0: "-----", 1: ".----", 2: "..---", 3: "...--", 4: "....-",
    5: ".....", 6: "-....", 7: "--...", 8: "---..", 9: "----.",
}
_MORSE_TO_DIGIT = {v: k for k, v in _MORSE_DIGITS.items()}


def to_morse(n) -> str:
    s = str(int(n))
    return " ".join(_MORSE_DIGITS[int(ch)] for ch in s)


def from_morse(s) -> int:
    parts = str(s).strip().split()
    if not parts:
        raise InputError("输入为空")
    out = []
    for p in parts:
        if p not in _MORSE_TO_DIGIT:
            raise InputError(f"非法摩尔斯数字：{p!r}")
        out.append(str(_MORSE_TO_DIGIT[p]))
    return int("".join(out))


# ===========================================================================
# 数字系统：统一接口
# ===========================================================================

SYSTEMS = {
    "arabic":         {"label": "阿拉伯数字",
                       "label_en": "Arabic"},
    "roman":          {"label": "罗马数字",
                       "label_en": "Roman"},
    "chinese":        {"label": "中文小写",
                       "label_en": "Chinese"},
    "chinese_formal": {"label": "中文大写",
                       "label_en": "Chinese Formal"},
    "english":        {"label": "英文单词",
                       "label_en": "English"},
    "morse":          {"label": "摩尔斯数字",
                       "label_en": "Morse"},
}


def list_systems() -> list:
    return [{"key": k, **v} for k, v in SYSTEMS.items()]


def to_arabic(value, from_system: str) -> int:
    if from_system == "arabic":
        try:
            return int(str(value).strip())
        except (TypeError, ValueError):
            raise InputError(f"不是整数：{value!r}")
    if from_system == "roman":
        return from_roman(value)
    if from_system in ("chinese", "chinese_formal"):
        return from_chinese(value)
    if from_system == "english":
        return from_english(value)
    if from_system == "morse":
        return from_morse(value)
    raise InputError(f"未知数字系统：{from_system}")


def from_arabic(n: int, to_system: str) -> str:
    if to_system == "arabic":
        return str(n)
    if to_system == "roman":
        return to_roman(n)
    if to_system == "chinese":
        return to_chinese(n, formal=False)
    if to_system == "chinese_formal":
        return to_chinese(n, formal=True)
    if to_system == "english":
        return to_english(n)
    if to_system == "morse":
        return to_morse(n)
    raise InputError(f"未知数字系统：{to_system}")


def convert(value, from_system: str, to_system: str) -> str:
    if from_system == to_system:
        return str(value)
    n = to_arabic(value, from_system)
    return from_arabic(n, to_system)


# ===========================================================================
# 符号库：数据结构
# ===========================================================================

@dataclass(frozen=True)
class Glyph:
    char: str
    name_zh: str
    name_en: str
    latex: str = ""
    category: str = ""
    tags: tuple = ()


@dataclass
class Category:
    key: str
    label_zh: str
    label_en: str
    icon: str = ""


CATEGORIES = [
    Category("greek",      "希腊字母",   "Greek",        "αβγ"),
    Category("math_op",    "数学运算",   "Math Ops",     "+−×÷"),
    Category("relation",   "关系符",     "Relations",    "=≠≤≥"),
    Category("set_logic",  "集合与逻辑", "Sets & Logic", "∈∀∃"),
    Category("calculus",   "微积分",     "Calculus",     "∫∂∑∏"),
    Category("linear",     "线性代数",   "Linear Alg.",  "⊗⊕"),
    Category("arrows",     "箭头",       "Arrows",       "→⇒⇔"),
    Category("number",     "序号/圈码",  "Numbers",      "①②③"),
    Category("currency",   "货币",       "Currency",     "$€¥£"),
    Category("units",      "单位",       "Units",        "°ÅΩ"),
    Category("sub_super",  "上下标",     "Sub/Super",    "₀¹₂³"),
    Category("fractions",  "分数",       "Fractions",    "½⅓¼"),
    Category("brackets",   "括号",       "Brackets",     "()[]"),
    Category("degrees",    "角度/温度",  "Degree",       "°′″℃"),
    Category("misc",       "其他",       "Misc",         "§¶†‡"),
]

_CAT_MAP = {c.key: c for c in CATEGORIES}


_ALL: list = []


def _g(char: str, zh: str, en: str, latex: str = "",
       cat: str = "", *tags: str):
    _ALL.append(Glyph(char, zh, en, latex, cat, tuple(tags)))


# ---------------- 希腊字母 ----------------

_GREEK = [
    ("α", "阿尔法",   "alpha",      r"\alpha"),
    ("β", "贝塔",     "beta",       r"\beta"),
    ("γ", "伽马",     "gamma",      r"\gamma"),
    ("δ", "德尔塔",   "delta",      r"\delta"),
    ("ε", "艾普西龙", "epsilon",    r"\epsilon"),
    ("ζ", "泽塔",     "zeta",       r"\zeta"),
    ("η", "伊塔",     "eta",        r"\eta"),
    ("θ", "西塔",     "theta",      r"\theta"),
    ("ι", "约塔",     "iota",       r"\iota"),
    ("κ", "卡帕",     "kappa",      r"\kappa"),
    ("λ", "拉姆达",   "lambda",     r"\lambda"),
    ("μ", "缪",       "mu",         r"\mu"),
    ("ν", "纽",       "nu",         r"\nu"),
    ("ξ", "克西",     "xi",         r"\xi"),
    ("ο", "奥密克戎", "omicron",    r"\omicron"),
    ("π", "派",       "pi",         r"\pi"),
    ("ρ", "柔",       "rho",        r"\rho"),
    ("σ", "西格玛",   "sigma",      r"\sigma"),
    ("τ", "陶",       "tau",        r"\tau"),
    ("υ", "宇普西龙", "upsilon",    r"\upsilon"),
    ("φ", "斐",       "phi",        r"\phi"),
    ("χ", "卡伊",     "chi",        r"\chi"),
    ("ψ", "普西",     "psi",        r"\psi"),
    ("ω", "欧米伽",   "omega",      r"\omega"),
    ("Γ", "伽马大写", "Gamma",      r"\Gamma"),
    ("Δ", "德尔塔大写", "Delta",    r"\Delta"),
    ("Θ", "西塔大写", "Theta",      r"\Theta"),
    ("Λ", "拉姆达大写", "Lambda",   r"\Lambda"),
    ("Ξ", "克西大写", "Xi",         r"\Xi"),
    ("Π", "派大写",   "Pi",         r"\Pi"),
    ("Σ", "西格玛大写", "Sigma",    r"\Sigma"),
    ("Φ", "斐大写",   "Phi",        r"\Phi"),
    ("Ψ", "普西大写", "Psi",        r"\Psi"),
    ("Ω", "欧米伽大写", "Omega",    r"\Omega"),
    ("ϑ", "西塔变体", "theta variant", r"\vartheta"),
    ("ϕ", "斐变体",   "phi variant",   r"\varphi"),
    ("ϖ", "派变体",   "pi variant",    r"\varpi"),
    ("ϱ", "柔变体",   "rho variant",   r"\varrho"),
    ("ς", "西格玛终形", "final sigma",  r"\varsigma"),
    ("ϵ", "艾普西龙变体", "epsilon variant", r"\varepsilon"),
]
for _ch, _zh, _en, _lx in _GREEK:
    _g(_ch, _zh, _en, _lx, "greek", "letter")

# ---------------- 数学运算 ----------------

_MATH_OPS = [
    ("+", "加",           "plus",          "+"),
    ("−", "减（Unicode）", "minus",         "-"),
    ("×", "乘",           "multiply",      r"\times"),
    ("÷", "除",           "divide",        r"\div"),
    ("±", "正负",         "plus-minus",    r"\pm"),
    ("∓", "负正",         "minus-plus",    r"\mp"),
    ("·", "点乘",         "dot",           r"\cdot"),
    ("⋅", "点乘（Unicode）", "dot op",      r"\cdot"),
    ("∗", "星号",         "asterisk",      r"\ast"),
    ("∘", "复合",         "compose",       r"\circ"),
    ("√", "平方根",       "sqrt",          r"\sqrt"),
    ("∛", "立方根",       "cbrt",          r"\sqrt[3]"),
    ("∜", "四次根",       "4th root",      r"\sqrt[4]"),
    ("∑", "求和",         "sum",           r"\sum"),
    ("∏", "求积",         "product",       r"\prod"),
    ("∐", "余积",         "coproduct",     r"\coprod"),
    ("∫", "积分",         "integral",      r"\int"),
    ("∬", "二重积分",     "double integral", r"\iint"),
    ("∭", "三重积分",     "triple integral", r"\iiint"),
    ("∮", "环路积分",     "contour integral", r"\oint"),
    ("∯", "曲面积分",     "surface integral", r"\oiint"),
    ("∂", "偏导",         "partial",       r"\partial"),
    ("∇", "梯度",         "nabla",         r"\nabla"),
    ("∞", "无穷",         "infinity",      r"\infty"),
    ("ℵ", "阿列夫",       "aleph",         r"\aleph"),
    ("ℶ", "贝特",         "beth",          r"\beth"),
    ("‰", "千分号",       "per mille",     r"\text{\textperthousand}"),
    ("‱", "万分号",       "per 10k",       ""),
    ("%", "百分号",       "percent",       r"\%"),
]
for _ch, _zh, _en, _lx in _MATH_OPS:
    _g(_ch, _zh, _en, _lx, "math_op")

# ---------------- 关系符 ----------------

_RELATIONS = [
    ("=", "等于",           "equals",       "="),
    ("≠", "不等于",         "not equal",    r"\neq"),
    ("≈", "约等于",         "approx",       r"\approx"),
    ("≃", "渐近等于",       "simeq",        r"\simeq"),
    ("≅", "同余",           "congruent",    r"\cong"),
    ("≡", "恒等",           "equiv",        r"\equiv"),
    ("≢", "不恒等",         "not equiv",    r"\not\equiv"),
    ("≤", "小于等于",       "less-equal",   r"\leq"),
    ("≥", "大于等于",       "greater-equal", r"\geq"),
    ("≪", "远小于",         "much less",    r"\ll"),
    ("≫", "远大于",         "much greater", r"\gg"),
    ("<", "小于",           "less",         "<"),
    (">", "大于",           "greater",      ">"),
    ("∝", "正比于",         "proportional", r"\propto"),
    ("∼", "相似",           "sim",          r"\sim"),
    ("≁", "不相似",         "not sim",      r"\nsim"),
    ("⊥", "垂直",           "perpendicular", r"\perp"),
    ("∥", "平行",           "parallel",     r"\parallel"),
    ("∦", "不平行",         "not parallel", r"\nparallel"),
    ("≐", "近似",           "doteq",        r"\doteq"),
    ("≑", "等或约",         "doteqdot",     r"\doteqdot"),
    ("≒", "约等号",         "falling dots", ""),
    ("≓", "反向约等",       "rising dots",  ""),
    ("≦", "小于等于（变体）", "leqq",       r"\leqq"),
    ("≧", "大于等于（变体）", "geqq",       r"\geqq"),
    ("⩽", "小于等于（slanted）", "leqslant", r"\leqslant"),
    ("⩾", "大于等于（slanted）", "geqslant", r"\geqslant"),
    ("≺", "前于",           "prec",         r"\prec"),
    ("≻", "后于",           "succ",         r"\succ"),
    ("⊂", "真子集",         "subset",       r"\subset"),
    ("⊃", "真超集",         "supset",       r"\supset"),
    ("⊆", "子集或等",       "subseteq",     r"\subseteq"),
    ("⊇", "超集或等",       "supseteq",     r"\supseteq"),
]
for _ch, _zh, _en, _lx in _RELATIONS:
    _g(_ch, _zh, _en, _lx, "relation")

# ---------------- 集合与逻辑 ----------------

_SET_LOGIC = [
    ("∈", "属于",           "in",           r"\in"),
    ("∉", "不属于",         "not in",       r"\notin"),
    ("∋", "包含",           "ni",           r"\ni"),
    ("∌", "不包含",         "not ni",       r"\not\ni"),
    ("∪", "并集",           "union",        r"\cup"),
    ("∩", "交集",           "intersection", r"\cap"),
    ("∖", "差集",           "setminus",     r"\setminus"),
    ("∅", "空集",           "empty set",    r"\emptyset"),
    ("⊂", "子集",           "subset",       r"\subset"),
    ("⊃", "超集",           "supset",       r"\supset"),
    ("⊄", "非子集",         "not subset",   r"\not\subset"),
    ("⊅", "非超集",         "not supset",   r"\not\supset"),
    ("⊆", "子集或等",       "subseteq",     r"\subseteq"),
    ("⊇", "超集或等",       "supseteq",     r"\supseteq"),
    ("⊈", "非子集或等",     "nsubseteq",    r"\nsubseteq"),
    ("⊉", "非超集或等",     "nsupseteq",    r"\nsupseteq"),
    ("⊕", "异或",           "oplus",        r"\oplus"),
    ("⊗", "张量积",         "otimes",       r"\otimes"),
    ("⊙", "圈点",           "odot",         r"\odot"),
    ("⊖", "圈减",           "ominus",       r"\ominus"),
    ("⊘", "圈斜线",         "oslash",       r"\oslash"),
    ("⊚", "圈环",           "circ",         r"\circledcirc"),
    ("∀", "任意",           "forall",       r"\forall"),
    ("∃", "存在",           "exists",       r"\exists"),
    ("∄", "不存在",         "not exists",   r"\nexists"),
    ("¬", "非",             "not",          r"\neg"),
    ("∧", "合取（与）",     "and",          r"\wedge"),
    ("∨", "析取（或）",     "or",           r"\vee"),
    ("⊻", "异或",           "xor",          r"\veebar"),
    ("⊼", "与非",           "nand",         r"\barwedge"),
    ("⊽", "或非",           "nor",          r"\barvee"),
    ("⊤", "真",             "top",          r"\top"),
    ("⊥", "假",             "bottom",       r"\bot"),
    ("⊢", "蕴含符号（证明）", "vdash",      r"\vdash"),
    ("⊣", "反蕴含",         "dashv",        r"\dashv"),
    ("⊨", "满足",           "models",       r"\models"),
    ("⊩", "强制",           "Vdash",        r"\Vdash"),
    ("∴", "所以",           "therefore",    r"\therefore"),
    ("∵", "因为",           "because",      r"\because"),
]
for _ch, _zh, _en, _lx in _SET_LOGIC:
    _g(_ch, _zh, _en, _lx, "set_logic")

# ---------------- 微积分 ----------------

_CALCULUS = [
    ("∫", "不定积分",     "integral",        r"\int"),
    ("∬", "二重积分",     "iint",            r"\iint"),
    ("∭", "三重积分",     "iiint",           r"\iiint"),
    ("∮", "闭路积分",     "oint",            r"\oint"),
    ("∯", "闭合曲面积分", "oiint",           r"\oiint"),
    ("∰", "闭合体积积分", "oiiint",          r"\oiiint"),
    ("∂", "偏导",         "partial",         r"\partial"),
    ("∇", "nabla",        "nabla",           r"\nabla"),
    ("∆", "增量",         "Delta",           r"\Delta"),
    ("∑", "求和",         "sum",             r"\sum"),
    ("∏", "求积",         "prod",            r"\prod"),
    ("∫₀¹", "定积分",     "def integral",    r"\int_0^1"),
    ("∫ₐᵇ", "区间积分",   "range integral",  r"\int_a^b"),
    ("′", "一阶导",       "prime",           "'"),
    ("″", "二阶导",       "double prime",    "''"),
    ("‴", "三阶导",       "triple prime",    "'''"),
    ("lim", "极限",       "limit",           r"\lim"),
    ("∑ᵢ", "带下标求和",  "sum_i",           r"\sum_i"),
    ("∏ᵢ", "带下标求积",  "prod_i",          r"\prod_i"),
    ("ε", "epsilon（微小）", "epsilon",      r"\epsilon"),
    ("δ", "delta（微小）", "delta",          r"\delta"),
    ("→", "趋近",         "to",              r"\to"),
    ("∞", "无穷",         "infty",           r"\infty"),
]
for _ch, _zh, _en, _lx in _CALCULUS:
    _g(_ch, _zh, _en, _lx, "calculus")

# ---------------- 线性代数 ----------------

_LINEAR = [
    ("⊕", "直和",       "direct sum",   r"\oplus"),
    ("⊗", "张量积",     "tensor",       r"\otimes"),
    ("⊙", "哈达玛积",   "hadamard",     r"\odot"),
    ("⊘", "除法符号",   "oslash",       r"\oslash"),
    ("⊞", "方框加",     "boxplus",      r"\boxplus"),
    ("⊟", "方框减",     "boxminus",     r"\boxminus"),
    ("⊠", "方框乘",     "boxtimes",     r"\boxtimes"),
    ("⊡", "方框点",     "boxdot",       r"\boxdot"),
    ("⟨", "左尖括号",   "left angle",   r"\langle"),
    ("⟩", "右尖括号",   "right angle",  r"\rangle"),
    ("‖", "范数",       "norm",         r"\|"),
    ("|", "绝对值",     "abs",          r"|"),
    ("⊤", "转置",       "transpose",    r"^{\top}"),
    ("†", "共轭转置",   "dagger",       r"^{\dagger}"),
    ("⋆", "伴随",       "star",         r"\star"),
    ("‖·‖", "范数",     "norm",         r"\|\cdot\|"),
    ("det", "行列式",   "det",          r"\det"),
    ("tr", "迹",        "tr",           r"\mathrm{tr}"),
    ("rank", "秩",      "rank",         r"\mathrm{rank}"),
    ("ker", "核",       "ker",          r"\ker"),
    ("Im", "像",        "Im",           r"\mathrm{Im}"),
]
for _ch, _zh, _en, _lx in _LINEAR:
    _g(_ch, _zh, _en, _lx, "linear")

# ---------------- 箭头 ----------------

_ARROWS = [
    ("→", "右箭头",     "rightarrow",   r"\rightarrow"),
    ("←", "左箭头",     "leftarrow",    r"\leftarrow"),
    ("↑", "上箭头",     "uparrow",      r"\uparrow"),
    ("↓", "下箭头",     "downarrow",    r"\downarrow"),
    ("↔", "左右箭头",   "leftrightarrow", r"\leftrightarrow"),
    ("↕", "上下箭头",   "updownarrow",  r"\updownarrow"),
    ("↗", "右上箭头",   "nearrow",      r"\nearrow"),
    ("↘", "右下箭头",   "searrow",      r"\searrow"),
    ("↙", "左下箭头",   "swarrow",      r"\swarrow"),
    ("↖", "左上箭头",   "nwarrow",      r"\nwarrow"),
    ("⇒", "双线右箭头", "Rightarrow",   r"\Rightarrow"),
    ("⇐", "双线左箭头", "Leftarrow",    r"\Leftarrow"),
    ("⇑", "双线上箭头", "Uparrow",      r"\Uparrow"),
    ("⇓", "双线下箭头", "Downarrow",    r"\Downarrow"),
    ("⇔", "双线左右",   "Leftrightarrow", r"\Leftrightarrow"),
    ("⇕", "双线上下",   "Updownarrow",  r"\Updownarrow"),
    ("⟶", "长右箭头",   "longrightarrow", r"\longrightarrow"),
    ("⟵", "长左箭头",   "longleftarrow",  r"\longleftarrow"),
    ("⟷", "长左右",     "longleftrightarrow", r"\longleftrightarrow"),
    ("⟹", "长双线右",   "Longrightarrow", r"\Longrightarrow"),
    ("⟸", "长双线左",   "Longleftarrow",  r"\Longleftarrow"),
    ("⟺", "长双线左右", "Longleftrightarrow", r"\Longleftrightarrow"),
    ("↦", "映射到",     "mapsto",       r"\mapsto"),
    ("↤", "反向映射",   "mapsfrom",     r"\mapsfrom"),
    ("↪", "钩子右",     "hookrightarrow", r"\hookrightarrow"),
    ("↩", "钩子左",     "hookleftarrow",  r"\hookleftarrow"),
    ("↠", "双头右",     "twoheadrightarrow", r"\twoheadrightarrow"),
    ("↞", "双头左",     "twoheadleftarrow",  r"\twoheadleftarrow"),
    ("⇀", "右鱼叉",     "rightharpoonup", r"\rightharpoonup"),
    ("↼", "左鱼叉",     "leftharpoonup",  r"\leftharpoonup"),
    ("⇁", "右鱼叉下",   "rightharpoondown", r"\rightharpoondown"),
    ("↽", "左鱼叉下",   "leftharpoondown",  r"\leftharpoondown"),
    ("⇌", "可逆",       "rightleftharpoons", r"\rightleftharpoons"),
    ("⇋", "可逆反",     "leftrightharpoons", r"\leftrightharpoons"),
    ("⇄", "右左",       "rightleftarrows", r"\rightleftarrows"),
    ("⇆", "左右",       "leftrightarrows", r"\leftrightarrows"),
    ("⇈", "双上",       "upuparrows",    r"\upuparrows"),
    ("⇊", "双下",       "downdownarrows", r"\downdownarrows"),
    ("↺", "逆时针",     "circlearrowleft", r"\circlearrowleft"),
    ("↻", "顺时针",     "circlearrowright", r"\circlearrowright"),
    ("⟳", "粗顺时针",   "cw open circle arrow", "⟳"),
    ("⟲", "粗逆时针",   "ccw open circle arrow", "⟲"),
    ("⇢", "虚线右",     "dashed right",  "⇢"),
    ("⇠", "虚线左",     "dashed left",   "⇠"),
    ("⇝", "波浪右",     "leadsto",       r"\leadsto"),
    ("↝", "波浪右（细）", "rightsquigarrow", r"\rightsquigarrow"),
    ("↭", "左右波浪",   "leftrightsquigarrow", r"\leftrightsquigarrow"),
    ("↶", "逆时针弯",   "curvearrowleft",  r"\curvearrowleft"),
    ("↷", "顺时针弯",   "curvearrowright", r"\curvearrowright"),
]
for _ch, _zh, _en, _lx in _ARROWS:
    _g(_ch, _zh, _en, _lx, "arrows")

# ---------------- 序号 / 圈码 ----------------

_CIRCLED = [
    ("①", "圈 1", "circled 1", ""), ("②", "圈 2", "circled 2", ""),
    ("③", "圈 3", "circled 3", ""), ("④", "圈 4", "circled 4", ""),
    ("⑤", "圈 5", "circled 5", ""), ("⑥", "圈 6", "circled 6", ""),
    ("⑦", "圈 7", "circled 7", ""), ("⑧", "圈 8", "circled 8", ""),
    ("⑨", "圈 9", "circled 9", ""), ("⑩", "圈 10", "circled 10", ""),
    ("⑪", "圈 11", "circled 11", ""), ("⑫", "圈 12", "circled 12", ""),
    ("⑬", "圈 13", "circled 13", ""), ("⑭", "圈 14", "circled 14", ""),
    ("⑮", "圈 15", "circled 15", ""), ("⑯", "圈 16", "circled 16", ""),
    ("⑰", "圈 17", "circled 17", ""), ("⑱", "圈 18", "circled 18", ""),
    ("⑲", "圈 19", "circled 19", ""), ("⑳", "圈 20", "circled 20", ""),
    ("⑴", "括号 1", "paren 1", ""), ("⑵", "括号 2", "paren 2", ""),
    ("⑶", "括号 3", "paren 3", ""), ("⑷", "括号 4", "paren 4", ""),
    ("⑸", "括号 5", "paren 5", ""), ("⑹", "括号 6", "paren 6", ""),
    ("⑺", "括号 7", "paren 7", ""), ("⑻", "括号 8", "paren 8", ""),
    ("⑼", "括号 9", "paren 9", ""), ("⑽", "括号 10", "paren 10", ""),
    ("⒈", "点 1", "dot 1", ""), ("⒉", "点 2", "dot 2", ""),
    ("⒊", "点 3", "dot 3", ""), ("⒋", "点 4", "dot 4", ""),
    ("⒌", "点 5", "dot 5", ""), ("⒍", "点 6", "dot 6", ""),
    ("⒎", "点 7", "dot 7", ""), ("⒏", "点 8", "dot 8", ""),
    ("⒐", "点 9", "dot 9", ""), ("⒑", "点 10", "dot 10", ""),
    ("Ⅰ", "罗马 1", "Roman I", ""), ("Ⅱ", "罗马 2", "Roman II", ""),
    ("Ⅲ", "罗马 3", "Roman III", ""), ("Ⅳ", "罗马 4", "Roman IV", ""),
    ("Ⅴ", "罗马 5", "Roman V", ""), ("Ⅵ", "罗马 6", "Roman VI", ""),
    ("Ⅶ", "罗马 7", "Roman VII", ""), ("Ⅷ", "罗马 8", "Roman VIII", ""),
    ("Ⅸ", "罗马 9", "Roman IX", ""), ("Ⅹ", "罗马 10", "Roman X", ""),
    ("Ⅺ", "罗马 11", "Roman XI", ""), ("Ⅻ", "罗马 12", "Roman XII", ""),
    ("ⓐ", "圈 a", "circled a", ""), ("ⓑ", "圈 b", "circled b", ""),
    ("ⓒ", "圈 c", "circled c", ""), ("ⓓ", "圈 d", "circled d", ""),
    ("Ⓐ", "圈 A", "circled A", ""), ("Ⓑ", "圈 B", "circled B", ""),
    ("Ⓒ", "圈 C", "circled C", ""), ("Ⓓ", "圈 D", "circled D", ""),
    ("❶", "实心圈 1", "filled 1", ""), ("❷", "实心圈 2", "filled 2", ""),
    ("❸", "实心圈 3", "filled 3", ""), ("❹", "实心圈 4", "filled 4", ""),
    ("❺", "实心圈 5", "filled 5", ""), ("❻", "实心圈 6", "filled 6", ""),
    ("❼", "实心圈 7", "filled 7", ""), ("❽", "实心圈 8", "filled 8", ""),
    ("❾", "实心圈 9", "filled 9", ""), ("❿", "实心圈 10", "filled 10", ""),
    ("㊀", "方框 1", "box 1", ""), ("㊁", "方框 2", "box 2", ""),
    ("㊂", "方框 3", "box 3", ""), ("㊃", "方框 4", "box 4", ""),
    ("㊄", "方框 5", "box 5", ""), ("㊅", "方框 6", "box 6", ""),
    ("㊆", "方框 7", "box 7", ""), ("㊇", "方框 8", "box 8", ""),
    ("㊈", "方框 9", "box 9", ""), ("㊉", "方框 10", "box 10", ""),
]
for _ch, _zh, _en, _lx in _CIRCLED:
    _g(_ch, _zh, _en, _lx, "number")

# ---------------- 货币 ----------------

_CURRENCY = [
    ("$", "美元", "dollar", "\\$"),
    ("€", "欧元", "euro", "€"),
    ("£", "英镑", "pound", "£"),
    ("¥", "人民币/日元", "yen/yuan", "¥"),
    ("₹", "印度卢比", "rupee", "₹"),
    ("₽", "俄罗斯卢布", "ruble", "₽"),
    ("₩", "韩元", "won", "₩"),
    ("₪", "以色列新谢克尔", "shekel", "₪"),
    ("₨", "卢比（缩写）", "rupee sign", "₨"),
    ("₫", "越南盾", "dong", "₫"),
    ("₴", "乌克兰格里夫纳", "hryvnia", "₴"),
    ("₦", "尼日利亚奈拉", "naira", "₦"),
    ("₵", "加纳塞地", "cedi", "₵"),
    ("₡", "哥斯达黎加科朗", "colón", "₡"),
    ("₲", "巴拉圭瓜拉尼", "guaraní", "₲"),
    ("₱", "菲律宾比索", "peso", "₱"),
    ("₸", "哈萨克斯坦坚戈", "tenge", "₸"),
    ("₺", "土耳其里拉", "lira", "₺"),
    ("₼", "阿塞拜疆马纳特", "manat", "₼"),
    ("₾", "格鲁吉亚拉里", "lari", "₾"),
    ("฿", "泰铢", "baht", "฿"),
    ("₿", "比特币", "bitcoin", "₿"),
    ("Ξ", "以太坊", "ether", "Ξ"),
    ("₮", "泰达币", "tether", "₮"),
    ("¢", "美分", "cent", "¢"),
    ("₠", "欧元（旧）", "ECU", "₠"),
    ("₣", "法国法郎", "french franc", "₣"),
    ("₤", "里拉", "lira sign", "₤"),
    ("₧", "西班牙比塞塔", "peseta", "₧"),
    ("₥", "密尔", "mill", "₥"),
    ("¤", "通用货币符号", "currency sign", "¤"),
]
for _ch, _zh, _en, _lx in _CURRENCY:
    _g(_ch, _zh, _en, _lx, "currency")

# ---------------- 单位 ----------------

_UNITS = [
    ("°", "度", "degree", "°"),
    ("′", "角分", "arcminute", "'"),
    ("″", "角秒", "arcsecond", "''"),
    ("℃", "摄氏度", "celsius", "°C"),
    ("℉", "华氏度", "fahrenheit", "°F"),
    ("K", "开尔文", "kelvin", "K"),
    ("Å", "埃", "angstrom", "Å"),
    ("Ω", "欧姆", "ohm", "Ω"),
    ("℧", "姆欧", "mho", "℧"),
    ("µ", "微（前缀）", "micro", r"\mu"),
    ("π", "π（圆周率）", "pi", r"\pi"),
    ("∅", "直径", "diameter", r"\varnothing"),
    ("‰", "千分号", "permille", "‰"),
    ("%", "百分比", "percent", "%"),
    ("‱", "万分号", "permyriad", "‱"),
    ("m", "米", "meter", "m"),
    ("s", "秒", "second", "s"),
    ("g", "克", "gram", "g"),
    ("L", "升", "liter", "L"),
    ("W", "瓦", "watt", "W"),
    ("Hz", "赫兹", "hertz", "Hz"),
    ("Pa", "帕斯卡", "pascal", "Pa"),
    ("J", "焦耳", "joule", "J"),
    ("N", "牛顿", "newton", "N"),
    ("V", "伏特", "volt", "V"),
    ("A", "安培", "ampere", "A"),
    ("F", "法拉", "farad", "F"),
    ("H", "亨利", "henry", "H"),
    ("T", "特斯拉", "tesla", "T"),
    ("Wb", "韦伯", "weber", "Wb"),
    ("Sv", "希沃特", "sievert", "Sv"),
    ("Gy", "戈瑞", "gray", "Gy"),
    ("Bq", "贝可勒尔", "becquerel", "Bq"),
    ("kat", "卡塔尔", "katal", "kat"),
]
for _ch, _zh, _en, _lx in _UNITS:
    _g(_ch, _zh, _en, _lx, "units")

# ---------------- 上下标 ----------------

_SUB_SUPER = [
    ("⁰", "上标 0", "superscript 0", "^0"),
    ("¹", "上标 1", "superscript 1", "^1"),
    ("²", "上标 2", "superscript 2", "^2"),
    ("³", "上标 3", "superscript 3", "^3"),
    ("⁴", "上标 4", "superscript 4", "^4"),
    ("⁵", "上标 5", "superscript 5", "^5"),
    ("⁶", "上标 6", "superscript 6", "^6"),
    ("⁷", "上标 7", "superscript 7", "^7"),
    ("⁸", "上标 8", "superscript 8", "^8"),
    ("⁹", "上标 9", "superscript 9", "^9"),
    ("⁺", "上标加", "superscript +", "^+"),
    ("⁻", "上标减", "superscript -", "^-"),
    ("⁼", "上标等", "superscript =", "^="),
    ("⁽", "上标左括号", "superscript (", "^("),
    ("⁾", "上标右括号", "superscript )", "^)"),
    ("ⁿ", "上标 n", "superscript n", "^n"),
    ("ⁱ", "上标 i", "superscript i", "^i"),
    ("₀", "下标 0", "subscript 0", "_0"),
    ("₁", "下标 1", "subscript 1", "_1"),
    ("₂", "下标 2", "subscript 2", "_2"),
    ("₃", "下标 3", "subscript 3", "_3"),
    ("₄", "下标 4", "subscript 4", "_4"),
    ("₅", "下标 5", "subscript 5", "_5"),
    ("₆", "下标 6", "subscript 6", "_6"),
    ("₇", "下标 7", "subscript 7", "_7"),
    ("₈", "下标 8", "subscript 8", "_8"),
    ("₉", "下标 9", "subscript 9", "_9"),
    ("₊", "下标加", "subscript +", "_+"),
    ("₋", "下标减", "subscript -", "_-"),
    ("₌", "下标等", "subscript =", "_="),
    ("₍", "下标左括号", "subscript (", "_("),
    ("₎", "下标右括号", "subscript )", "_)"),
    ("ₐ", "下标 a", "subscript a", "_a"),
    ("ₑ", "下标 e", "subscript e", "_e"),
    ("ₕ", "下标 h", "subscript h", "_h"),
    ("ᵢ", "下标 i", "subscript i", "_i"),
    ("ⱼ", "下标 j", "subscript j", "_j"),
    ("ₖ", "下标 k", "subscript k", "_k"),
    ("ₗ", "下标 l", "subscript l", "_l"),
    ("ₘ", "下标 m", "subscript m", "_m"),
    ("ₙ", "下标 n", "subscript n", "_n"),
    ("ₚ", "下标 p", "subscript p", "_p"),
    ("ᵣ", "下标 r", "subscript r", "_r"),
    ("ₛ", "下标 s", "subscript s", "_s"),
    ("ₜ", "下标 t", "subscript t", "_t"),
    ("ₓ", "下标 x", "subscript x", "_x"),
]
for _ch, _zh, _en, _lx in _SUB_SUPER:
    _g(_ch, _zh, _en, _lx, "sub_super")

# ---------------- 分数 ----------------

_FRACTIONS = [
    ("½", "二分之一", "1/2", "1/2"),
    ("⅓", "三分之一", "1/3", "1/3"),
    ("⅔", "三分之二", "2/3", "2/3"),
    ("¼", "四分之一", "1/4", "1/4"),
    ("¾", "四分之三", "3/4", "3/4"),
    ("⅕", "五分之一", "1/5", "1/5"),
    ("⅖", "五分之二", "2/5", "2/5"),
    ("⅗", "五分之三", "3/5", "3/5"),
    ("⅘", "五分之四", "4/5", "4/5"),
    ("⅙", "六分之一", "1/6", "1/6"),
    ("⅚", "六分之五", "5/6", "5/6"),
    ("⅐", "七分之一", "1/7", "1/7"),
    ("⅛", "八分之一", "1/8", "1/8"),
    ("⅜", "八分之三", "3/8", "3/8"),
    ("⅝", "八分之五", "5/8", "5/8"),
    ("⅞", "八分之七", "7/8", "7/8"),
    ("⅑", "九分之一", "1/9", "1/9"),
    ("⅒", "十分之一", "1/10", "1/10"),
    ("⁄", "分数斜杠", "fraction slash", "/"),
]
for _ch, _zh, _en, _lx in _FRACTIONS:
    _g(_ch, _zh, _en, _lx, "fractions")

# ---------------- 括号 ----------------

_BRACKETS = [
    ("(", "小括号", "paren", "("),
    (")", "小括号", "paren", ")"),
    ("[", "方括号", "bracket", "["),
    ("]", "方括号", "bracket", "]"),
    ("{", "花括号", "curly brace", "{"),
    ("}", "花括号", "curly brace", "}"),
    ("⟨", "尖括号", "angle", r"\langle"),
    ("⟩", "尖括号", "angle", r"\rangle"),
    ("⌈", "上取整", "ceil", r"\lceil"),
    ("⌉", "上取整", "ceil", r"\rceil"),
    ("⌊", "下取整", "floor", r"\lfloor"),
    ("⌋", "下取整", "floor", r"\rfloor"),
    ("⟦", "双方括号", "double bracket", r"\llbracket"),
    ("⟧", "双方括号", "double bracket", r"\rrbracket"),
    ("〈", "中文尖括号", "cjk angle", "〈"),
    ("〉", "中文尖括号", "cjk angle", "〉"),
    ("《", "书名号", "book title", "《"),
    ("》", "书名号", "book title", "》"),
    ("【", "方头括号", "square title", "【"),
    ("】", "方头括号", "square title", "】"),
    ("「", "中文引号", "cjk quote", "「"),
    ("」", "中文引号", "cjk quote", "」"),
    ("『", "中文双引号", "cjk dquote", "『"),
    ("』", "中文双引号", "cjk dquote", "』"),
]
for _ch, _zh, _en, _lx in _BRACKETS:
    _g(_ch, _zh, _en, _lx, "brackets")

# ---------------- 角度 / 温度 ----------------

_DEGREES = [
    ("°", "度", "degree", "°"),
    ("′", "角分", "arcmin", "'"),
    ("″", "角秒", "arcsec", "''"),
    ("‴", "微角秒", "triple prime", "'''"),
    ("℃", "摄氏度", "celsius", "°C"),
    ("℉", "华氏度", "fahrenheit", "°F"),
    ("K", "开尔文（符号）", "kelvin sign", "K"),
    ("°C", "摄氏度", "celsius", "°C"),
    ("°F", "华氏度", "fahrenheit", "°F"),
    ("°R", "兰氏度", "rankine", "°R"),
    ("rad", "弧度", "radian", "rad"),
    ("°deg", "度（写）", "degree text", "°"),
]
for _ch, _zh, _en, _lx in _DEGREES:
    _g(_ch, _zh, _en, _lx, "degrees")

# ---------------- 其他 ----------------

_MISC = [
    ("§", "节", "section", "§"),
    ("¶", "段落", "pilcrow", "¶"),
    ("†", "剑号", "dagger", r"\dagger"),
    ("‡", "双剑号", "double dagger", r"\ddagger"),
    ("•", "项目符号", "bullet", "•"),
    ("·", "中点", "middle dot", r"\cdot"),
    ("‣", "三角点", "triangle bullet", "‣"),
    ("※", "参考标记", "reference", "※"),
    ("○", "空心圆", "hollow circle", "○"),
    ("●", "实心圆", "filled circle", "●"),
    ("□", "空心方", "hollow square", "□"),
    ("■", "实心方", "filled square", "■"),
    ("◇", "空心菱", "hollow diamond", "◇"),
    ("◆", "实心菱", "filled diamond", "◆"),
    ("△", "三角", "triangle", "△"),
    ("▲", "实心三角", "filled triangle", "▲"),
    ("☆", "空心星", "hollow star", "☆"),
    ("★", "实心星", "filled star", "★"),
    ("✓", "对勾", "check", "✓"),
    ("✔", "粗对勾", "heavy check", "✔"),
    ("✗", "叉", "cross", "✗"),
    ("✘", "粗叉", "heavy cross", "✘"),
    ("☑", "打勾方框", "checked box", "☑"),
    ("☐", "空方框", "empty box", "☐"),
    ("☒", "打叉方框", "x box", "☒"),
    ("⚠", "警告", "warning", "⚠"),
    ("ℹ", "信息", "info", "ℹ"),
    ("™", "商标", "trademark", "™"),
    ("©", "版权", "copyright", "©"),
    ("®", "注册商标", "registered", "®"),
    ("№", "编号", "numero", "№"),
    ("℗", "录音版权", "sound recording copyright", "℗"),
    ("℠", "服务商标", "service mark", "℠"),
    ("♠", "黑桃", "spade", "♠"),
    ("♥", "红桃", "heart", "♥"),
    ("♦", "方块", "diamond", "♦"),
    ("♣", "梅花", "club", "♣"),
    ("♤", "黑桃（空心）", "spade suit white", "♤"),
    ("♡", "红桃（空心）", "heart suit white", "♡"),
    ("♢", "方块（空心）", "diamond suit white", "♢"),
    ("♧", "梅花（空心）", "club suit white", "♧"),
    ("♩", "四分音符", "quarter note", "♩"),
    ("♪", "八分音符", "eighth note", "♪"),
    ("♫", "双八分音符", "beamed notes", "♫"),
    ("♬", "双八分音符连", "beamed notes pair", "♬"),
    ("☀", "太阳", "sun", "☀"),
    ("☁", "云", "cloud", "☁"),
    ("☂", "雨伞", "umbrella", "☂"),
    ("☃", "雪人", "snowman", "☃"),
    ("☎", "电话", "phone", "☎"),
    ("✉", "信封", "envelope", "✉"),
    ("✎", "笔", "pencil", "✎"),
    ("✂", "剪刀", "scissors", "✂"),
    ("☞", "手指", "pointing", "☞"),
    ("☜", "手指（左）", "pointing left", "☜"),
    ("◐", "半圆", "circle half", "◐"),
    ("▣", "方框内圈", "square with dot", "▣"),
    ("▪", "小实心方", "small filled square", "▪"),
    ("▫", "小空心方", "small hollow square", "▫"),
]
for _ch, _zh, _en, _lx in _MISC:
    _g(_ch, _zh, _en, _lx, "misc")


# ===========================================================================
# 符号库：查询接口
# ===========================================================================

def all_glyphs() -> list:
    return list(_ALL)


def by_category(cat: str) -> list:
    return [g for g in _ALL if g.category == cat]


def categories() -> list:
    return list(CATEGORIES)


def get_category(key: str):
    return _CAT_MAP.get(key)


def search(query: str, limit: int = 500) -> list:
    """按关键词搜索符号。

    匹配范围：字符本身、中文名、英文名、LaTeX、分类、标签。
    """
    q = (query or "").strip().lower()
    if not q:
        return list(_ALL)[:limit]

    out = []
    for g in _ALL:
        haystack = (
            f"{g.char} {g.name_zh} {g.name_en} {g.latex} "
            f"{g.category} {' '.join(g.tags)}"
        ).lower()
        if q in haystack:
            out.append(g)
            if len(out) >= limit:
                break
    return out


def get_by_char(ch: str):
    for g in _ALL:
        if g.char == ch:
            return g
    return None


# ===========================================================================
# 符号库：收藏
# ===========================================================================

_FAV_LOCK = threading.RLock()
_FAV_CACHE: list | None = None


def _fav_path() -> str:
    return os.path.join(
        os.path.expanduser("~"),
        ".multicalc", "glyph_favorites.json")


def _load_fav() -> list:
    global _FAV_CACHE
    if _FAV_CACHE is not None:
        return _FAV_CACHE
    try:
        with open(_fav_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        _FAV_CACHE = ([str(x) for x in data]
                      if isinstance(data, list) else [])
    except Exception:
        _FAV_CACHE = []
    return _FAV_CACHE


def _save_fav(items: list):
    try:
        os.makedirs(os.path.dirname(_fav_path()), exist_ok=True)
        with open(_fav_path(), "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def favorites() -> list:
    with _FAV_LOCK:
        return list(_load_fav())


def is_favorite(ch: str) -> bool:
    with _FAV_LOCK:
        return ch in _load_fav()


def toggle_favorite(ch: str) -> bool:
    """切换收藏状态，返回新状态。"""
    global _FAV_CACHE
    with _FAV_LOCK:
        items = list(_load_fav())
        if ch in items:
            items.remove(ch)
            _save_fav(items)
            _FAV_CACHE = items
            return False
        items.append(ch)
        _save_fav(items)
        _FAV_CACHE = items
        return True