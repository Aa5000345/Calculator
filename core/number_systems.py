"""数字系统转换：阿拉伯数字 ↔ 罗马 / 中文 / 英文 / 摩尔斯。

支持范围：
- 罗马数字：1 ~ 3999（经典）
- 中文数字：0 ~ 9999_9999_9999（万亿级别）
- 中文大写：同上
- 英文单词：0 ~ 999_999_999_999_999（quadrillion 级别）
- 摩尔斯数字：0 ~ 任意位阿拉伯数字

对外接口：
    to_roman(n) / from_roman(s)
    to_chinese(n, formal=False) / from_chinese(s)
    to_english(n) / from_english(s)
    to_morse(n) / from_morse(s)
    convert(value, from_system, to_system) -> str
    list_systems() -> list[dict]
"""
from __future__ import annotations

import re

from core.errors import InputError


# ===========================================================================
# 罗马数字
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


def to_roman(n: int) -> str:
    """阿拉伯数字 → 罗马数字。范围 1 ~ 3999。"""
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


def from_roman(s: str) -> int:
    """罗马数字 → 阿拉伯数字。大小写不敏感。"""
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
# 中文数字
# ===========================================================================

_CN_DIGITS_LOWER = "零一二三四五六七八九"
_CN_DIGITS_UPPER = "零壹贰叁肆伍陆柒捌玖"
_CN_UNITS_LOWER = ["", "十", "百", "千"]
_CN_UNITS_UPPER = ["", "拾", "佰", "仟"]
_CN_BIG_LOWER = ["", "万", "亿", "万亿"]
_CN_BIG_UPPER = ["", "万", "亿", "万亿"]


def _four_digits_to_chinese(n: int, digits: str,
                            units: list) -> str:
    """处理 0 ~ 9999 的四位数字。"""
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


def to_chinese(n: int, formal: bool = False) -> str:
    """阿拉伯数字 → 中文数字。

    Args:
        n: 整数，范围 0 ~ 9999_9999_9999
        formal: 是否用大写（壹贰叁…）

    Returns:
        如 ``"一千零一"`` / ``"壹仟零壹"``
    """
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

    # 分成 4 位一组
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

    # 小写习惯：10~19 → "十X" 而非 "一十X"
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


def from_chinese(s: str) -> int:
    """中文数字 → 阿拉伯数字。支持小写与大写。"""
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
                    number = 1     # 处理 "十" 前面没有数字
                section += number * unit
                number = 0
        else:
            raise InputError(f"非法中文字符：{ch!r}")
    total += section + number
    return -total if neg else total


# ===========================================================================
# 英文数字
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


def to_english(n: int) -> str:
    """阿拉伯数字 → 英文单词。范围 0 ~ 999_999_999_999_999。"""
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


def from_english(s: str) -> int:
    """英文单词 → 阿拉伯数字。支持连字符与美式拼写。"""
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
# 摩尔斯数字
# ===========================================================================

_MORSE_DIGITS = {
    0: "-----", 1: ".----", 2: "..---", 3: "...--", 4: "....-",
    5: ".....", 6: "-....", 7: "--...", 8: "---..", 9: "----.",
}
_MORSE_TO_DIGIT = {v: k for k, v in _MORSE_DIGITS.items()}


def to_morse(n: int) -> str:
    s = str(int(n))
    return " ".join(_MORSE_DIGITS[int(ch)] for ch in s)


def from_morse(s: str) -> int:
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
# 统一接口
# ===========================================================================

SYSTEMS = {
    "arabic":         {"label": "阿拉伯数字", "label_en": "Arabic"},
    "roman":          {"label": "罗马数字", "label_en": "Roman"},
    "chinese":        {"label": "中文小写", "label_en": "Chinese"},
    "chinese_formal": {"label": "中文大写", "label_en": "Chinese Formal"},
    "english":        {"label": "英文单词", "label_en": "English"},
    "morse":          {"label": "摩尔斯数字", "label_en": "Morse"},
}


def list_systems() -> list:
    return [{"key": k, **v} for k, v in SYSTEMS.items()]


def to_arabic(value, from_system: str) -> int:
    """把任意系统的值转为阿拉伯整数。"""
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
    """把阿拉伯整数转为目标系统。"""
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
    """任意系统间转换。"""
    if from_system == to_system:
        return str(value)
    n = to_arabic(value, from_system)
    return from_arabic(n, to_system)


__all__ = [
    "to_roman", "from_roman",
    "to_chinese", "from_chinese",
    "to_english", "from_english",
    "to_morse", "from_morse",
    "to_arabic", "from_arabic",
    "convert", "list_systems", "SYSTEMS",
]