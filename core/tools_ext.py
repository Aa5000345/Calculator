"""工具扩展：二维码 / JWT / 正则 / 颜色。"""
from __future__ import annotations

import base64
import colorsys
import io
import json
import re

from core.errors import InputError


# =====================================================================
# 二维码
# =====================================================================

def qrcode_generate(text, path=None):
    """生成二维码。``qrcode`` 未安装时抛 InputError。"""
    try:
        import qrcode
    except ImportError:
        raise InputError(
            "需要安装 qrcode：pip install qrcode[pil]",
            friendly_key="err_input")
    qr = qrcode.QRCode(box_size=10, border=4)
    qr.add_data(str(text))
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    if path:
        img.save(path)
        return path
    return img


def qrcode_pixmap_bytes(text):
    """返回 PNG 字节。"""
    img = qrcode_generate(text)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# =====================================================================
# JWT
# =====================================================================

def jwt_decode(token):
    token = str(token).strip()
    parts = token.split(".")
    if len(parts) != 3:
        raise InputError("JWT 必须由 3 段组成", friendly_key="err_input")
    header_b64, payload_b64, signature_b64 = parts

    def _dec(s):
        pad = (-len(s)) % 4
        return base64.urlsafe_b64decode(s + "=" * pad).decode(
            "utf-8", errors="replace")

    try:
        header = json.loads(_dec(header_b64))
    except Exception as e:
        raise InputError(f"header 解析失败：{e}", friendly_key="err_input")
    try:
        payload = json.loads(_dec(payload_b64))
    except Exception as e:
        raise InputError(f"payload 解析失败：{e}", friendly_key="err_input")

    return {
        "header": header,
        "payload": payload,
        "signature": signature_b64,
        "signature_length": len(signature_b64),
    }


# =====================================================================
# 正则
# =====================================================================

def _flags(flags_str):
    fl = 0
    for f in (flags_str or ""):
        if f == "i": fl |= re.IGNORECASE
        elif f == "m": fl |= re.MULTILINE
        elif f == "s": fl |= re.DOTALL
        elif f == "x": fl |= re.VERBOSE
    return fl


def regex_test(pattern, text, flags=""):
    try:
        pat = re.compile(pattern, _flags(flags))
    except re.error as e:
        raise InputError(f"正则语法错误：{e}", friendly_key="err_input")
    matches = []
    for m in pat.finditer(text):
        matches.append({
            "span": list(m.span()),
            "match": m.group(0),
            "groups": list(m.groups()),
            "groupdict": m.groupdict(),
        })
    return {"count": len(matches), "matches": matches[:200]}


def regex_replace(pattern, repl, text, flags=""):
    try:
        return re.sub(pattern, repl, text, flags=_flags(flags))
    except re.error as e:
        raise InputError(f"正则语法错误：{e}", friendly_key="err_input")


# =====================================================================
# 颜色
# =====================================================================

def color_convert(value):
    """支持 ``#RRGGBB`` / ``#RGB`` / ``rgb(r,g,b)`` / ``(r,g,b)``。"""
    s = str(value).strip()
    r = g = b = None

    m = re.match(r"^#?([0-9A-Fa-f]{6})$", s)
    if m:
        hx = m.group(1)
        r, g, b = int(hx[0:2], 16), int(hx[2:4], 16), int(hx[4:6], 16)

    if r is None:
        m = re.match(r"^#?([0-9A-Fa-f]{3})$", s)
        if m:
            hx = m.group(1)
            r = int(hx[0] * 2, 16)
            g = int(hx[1] * 2, 16)
            b = int(hx[2] * 2, 16)

    if r is None:
        m = re.match(r"^rgba?\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)", s, re.I)
        if m:
            r, g, b = int(m.group(1)), int(m.group(2)), int(m.group(3))

    if r is None:
        m = re.match(r"^\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)", s)
        if m:
            r, g, b = int(m.group(1)), int(m.group(2)), int(m.group(3))

    if r is None:
        raise InputError("无法识别颜色格式", friendly_key="err_input")

    r = max(0, min(255, r))
    g = max(0, min(255, g))
    b = max(0, min(255, b))

    h, l, s_ = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)

    return {
        "hex": f"#{r:02X}{g:02X}{b:02X}",
        "rgb": (r, g, b),
        "hsl": (round(h * 360, 2), round(s_ * 100, 2), round(l * 100, 2)),
    }


def color_contrast(c1, c2):
    """WCAG 对比度与等级（AA / AAA）。"""
    def _lum(c):
        if isinstance(c, str):
            c = color_convert(c)["rgb"]
        r, g, b = [v / 255 for v in c]

        def _f(v):
            return (v / 12.92) if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

        return 0.2126 * _f(r) + 0.7152 * _f(g) + 0.0722 * _f(b)

    l1, l2 = _lum(c1), _lum(c2)
    if l1 < l2:
        l1, l2 = l2, l1
    ratio = (l1 + 0.05) / (l2 + 0.05)
    if ratio >= 7:
        level = "AAA"
    elif ratio >= 4.5:
        level = "AA"
    elif ratio >= 3:
        level = "AA Large"
    else:
        level = "Fail"
    return {"ratio": round(ratio, 2), "level": level}