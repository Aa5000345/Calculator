"""分享卡片 + 工具扩展（二维码 / JWT / 正则 / 颜色）。

合并自：core/share_card.py + core/tools_ext.py

对外接口：
    # 分享卡片
    render_share_card
    # 二维码
    qrcode_generate, qrcode_pixmap_bytes
    # JWT
    jwt_decode
    # 正则
    regex_test, regex_replace
    # 颜色
    color_convert, color_contrast
"""
from __future__ import annotations

import base64
import colorsys
import datetime
import io
import json
import os
import re

from core.base import InputError

__all__ = [
    "render_share_card",
    "qrcode_generate", "qrcode_pixmap_bytes",
    "jwt_decode",
    "regex_test", "regex_replace",
    "color_convert", "color_contrast",
]


# ===========================================================================
# 分享卡片
# ===========================================================================

_SHARE_THEMES = {
    "dark": {
        "bg": "#1e1e2e", "fg": "#ffffff", "expr": "#cdd6f4",
        "accent": "#cba6f7", "dim": "#6c7086",
        "qr_fg": "#1e1e2e", "qr_bg": "#cdd6f4",
    },
    "light": {
        "bg": "#ffffff", "fg": "#24292f", "expr": "#57606a",
        "accent": "#0969da", "dim": "#8c959f",
        "qr_fg": "#ffffff", "qr_bg": "#24292f",
    },
}


def _share_load_font(size: int, bold: bool = False):
    try:
        from PIL import ImageFont
    except ImportError:
        return None

    if bold:
        candidates = [
            "C:/Windows/Fonts/msyhbd.ttc",
            "C:/Windows/Fonts/arialbd.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]
    else:
        candidates = [
            "C:/Windows/Fonts/msyh.ttc",
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/consola.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    try:
        return ImageFont.load_default()
    except Exception:
        return None


def _qr_image(data: str, size_px: int, theme: dict):
    try:
        import qrcode
    except ImportError:
        return None
    try:
        qr = qrcode.QRCode(box_size=4, border=2)
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(
            fill_color=theme["qr_fg"],
            back_color=theme["qr_bg"],
        ).convert("RGB")
        return img.resize((size_px, size_px))
    except Exception:
        return None


def render_share_card(expr: str,
                      result: str,
                      latex: str = "",
                      title: str = "MultiCalc",
                      footer: str = "",
                      out_path: str | None = None,
                      qr_data: str | None = None,
                      theme: str = "dark") -> bytes:
    """把一次计算结果渲染为分享卡片 PNG。"""
    try:
        from PIL import Image, ImageDraw
    except ImportError as e:
        raise RuntimeError(
            f"分享卡片需要 Pillow：pip install Pillow（{e}）") from e

    pal = _SHARE_THEMES.get(theme, _SHARE_THEMES["dark"])

    W, H = 860, 420
    img = Image.new("RGB", (W, H), pal["bg"])
    draw = ImageDraw.Draw(img)

    font_title = _share_load_font(26, bold=True)
    font_expr = _share_load_font(22)
    font_result = _share_load_font(38, bold=True)
    font_small = _share_load_font(15)

    draw.text((32, 26), str(title), fill=pal["fg"], font=font_title)
    draw.text((32, 80), f"= {expr}", fill=pal["expr"], font=font_expr)

    result_line = (result or "").strip().replace("\n", "  ")
    if len(result_line) > 48:
        result_line = result_line[:45] + "…"
    draw.text((32, 130), result_line,
              fill=pal["accent"], font=font_result)

    if latex:
        lat = latex.strip()
        if len(lat) > 70:
            lat = lat[:67] + "…"
        draw.text((32, 200), f"$ {lat} $",
                  fill=pal["expr"], font=font_expr)

    foot = footer or datetime.datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S")
    draw.text((32, H - 40), foot, fill=pal["dim"], font=font_small)

    if qr_data:
        qr_px = 160
        qr_img = _qr_image(qr_data, qr_px, pal)
        if qr_img is not None:
            pos = (W - qr_px - 32, H - qr_px - 32)
            img.paste(qr_img, pos)

    buf = io.BytesIO()
    img.save(buf, "PNG")
    data = buf.getvalue()

    if out_path:
        try:
            with open(out_path, "wb") as f:
                f.write(data)
        except Exception as e:
            raise RuntimeError(f"保存失败：{e}") from e

    return data


# ===========================================================================
# 二维码
# ===========================================================================

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


def qrcode_pixmap_bytes(text) -> bytes:
    """返回 PNG 字节。"""
    img = qrcode_generate(text)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ===========================================================================
# JWT
# ===========================================================================

def jwt_decode(token) -> dict:
    token = str(token).strip()
    parts = token.split(".")
    if len(parts) != 3:
        raise InputError("JWT 必须由 3 段组成",
                         friendly_key="err_input")
    header_b64, payload_b64, signature_b64 = parts

    def _dec(s):
        pad = (-len(s)) % 4
        return base64.urlsafe_b64decode(s + "=" * pad).decode(
            "utf-8", errors="replace")

    try:
        header = json.loads(_dec(header_b64))
    except Exception as e:
        raise InputError(f"header 解析失败：{e}",
                         friendly_key="err_input")
    try:
        payload = json.loads(_dec(payload_b64))
    except Exception as e:
        raise InputError(f"payload 解析失败：{e}",
                         friendly_key="err_input")

    return {
        "header": header,
        "payload": payload,
        "signature": signature_b64,
        "signature_length": len(signature_b64),
    }


# ===========================================================================
# 正则
# ===========================================================================

def _flags(flags_str):
    fl = 0
    for f in (flags_str or ""):
        if f == "i":
            fl |= re.IGNORECASE
        elif f == "m":
            fl |= re.MULTILINE
        elif f == "s":
            fl |= re.DOTALL
        elif f == "x":
            fl |= re.VERBOSE
    return fl


def regex_test(pattern, text, flags="") -> dict:
    try:
        pat = re.compile(pattern, _flags(flags))
    except re.error as e:
        raise InputError(f"正则语法错误：{e}",
                         friendly_key="err_input")
    matches = []
    for m in pat.finditer(text):
        matches.append({
            "span": list(m.span()),
            "match": m.group(0),
            "groups": list(m.groups()),
            "groupdict": m.groupdict(),
        })
    return {"count": len(matches), "matches": matches[:200]}


def regex_replace(pattern, repl, text, flags="") -> str:
    try:
        return re.sub(pattern, repl, text, flags=_flags(flags))
    except re.error as e:
        raise InputError(f"正则语法错误：{e}",
                         friendly_key="err_input")


# ===========================================================================
# 颜色
# ===========================================================================

def color_convert(value) -> dict:
    """支持 ``#RRGGBB`` / ``#RGB`` / ``rgb(r,g,b)`` / ``(r,g,b)``。"""
    s = str(value).strip()
    r = g = b = None

    m = re.match(r"^#?([0-9A-Fa-f]{6})$", s)
    if m:
        hx = m.group(1)
        r, g, b = (int(hx[0:2], 16), int(hx[2:4], 16),
                   int(hx[4:6], 16))

    if r is None:
        m = re.match(r"^#?([0-9A-Fa-f]{3})$", s)
        if m:
            hx = m.group(1)
            r = int(hx[0] * 2, 16)
            g = int(hx[1] * 2, 16)
            b = int(hx[2] * 2, 16)

    if r is None:
        m = re.match(
            r"^rgba?\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)",
            s, re.I)
        if m:
            r, g, b = (int(m.group(1)), int(m.group(2)),
                       int(m.group(3)))

    if r is None:
        m = re.match(r"^\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)", s)
        if m:
            r, g, b = (int(m.group(1)), int(m.group(2)),
                       int(m.group(3)))

    if r is None:
        raise InputError("无法识别颜色格式",
                         friendly_key="err_input")

    r = max(0, min(255, r))
    g = max(0, min(255, g))
    b = max(0, min(255, b))

    h, l, s_ = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)

    return {
        "hex": f"#{r:02X}{g:02X}{b:02X}",
        "rgb": (r, g, b),
        "hsl": (round(h * 360, 2), round(s_ * 100, 2),
                round(l * 100, 2)),
    }


def color_contrast(c1, c2) -> dict:
    """WCAG 对比度与等级（AA / AAA）。"""

    def _lum(c):
        if isinstance(c, str):
            c = color_convert(c)["rgb"]
        r, g, b = [v / 255 for v in c]

        def _f(v):
            return ((v / 12.92) if v <= 0.03928
                    else ((v + 0.055) / 1.055) ** 2.4)

        return (0.2126 * _f(r) + 0.7152 * _f(g)
                + 0.0722 * _f(b))

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