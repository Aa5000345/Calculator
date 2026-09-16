"""分享卡片：把表达式 + 结果 + LaTeX + 二维码渲染成 PNG。

依赖：
- Pillow（必需）
- qrcode（可选；未装时跳过二维码区域）

不依赖 matplotlib，渲染快、体积小。
"""
from __future__ import annotations

import datetime
import io
import os


# ---------------------------------------------------------------------------
# 主题
# ---------------------------------------------------------------------------

_THEMES = {
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


def _load_font(size: int, bold: bool = False):
    """尝试加载系统等宽/无衬线字体，全部失败则用 PIL 默认位图字体。"""
    try:
        from PIL import ImageFont
    except ImportError:
        return None

    # Windows / macOS / Linux 常见路径
    candidates = []
    if bold:
        candidates = [
            "C:/Windows/Fonts/msyhbd.ttc",     # 微软雅黑 Bold
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
    """生成二维码 PIL 图像（失败返回 None）。"""
    try:
        import qrcode
    except ImportError:
        return None
    try:
        qr = qrcode.QRCode(box_size=4, border=2)
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(
            fill_color=theme["qr_fg"], back_color=theme["qr_bg"]
        ).convert("RGB")
        return img.resize((size_px, size_px))
    except Exception:
        return None


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def render_share_card(expr: str,
                      result: str,
                      latex: str = "",
                      title: str = "MultiCalc",
                      footer: str = "",
                      out_path: str | None = None,
                      qr_data: str | None = None,
                      theme: str = "dark") -> bytes:
    """把一次计算结果渲染为分享卡片 PNG。

    参数：
    - expr：原始表达式
    - result：结果（字符串）
    - latex：LaTeX 表达式（可空；为空时跳过公式区）
    - title：卡片顶部标题
    - footer：底部提示（可空；默认写时间戳）
    - out_path：保存路径（None 时只返回 bytes）
    - qr_data：二维码内容（如表达式本身或 URL；None 时跳过）
    - theme：dark / light

    返回 PNG 字节。
    """
    try:
        from PIL import Image, ImageDraw
    except ImportError as e:
        raise RuntimeError(
            f"分享卡片需要 Pillow：pip install Pillow（{e}）") from e

    pal = _THEMES.get(theme, _THEMES["dark"])

    # 画布
    W, H = 860, 420
    img = Image.new("RGB", (W, H), pal["bg"])
    draw = ImageDraw.Draw(img)

    # 字体
    font_title = _load_font(26, bold=True)
    font_expr = _load_font(22)
    font_result = _load_font(38, bold=True)
    font_small = _load_font(15)

    # --- 顶栏标题 ---
    draw.text((32, 26), str(title), fill=pal["fg"], font=font_title)

    # --- 表达式 ---
    draw.text((32, 80), f"= {expr}", fill=pal["expr"], font=font_expr)

    # --- 结果（自动换行 + 截断） ---
    result_line = (result or "").strip().replace("\n", "  ")
    if len(result_line) > 48:
        result_line = result_line[:45] + "…"
    draw.text((32, 130), result_line, fill=pal["accent"], font=font_result)

    # --- LaTeX 行（纯文本兜底） ---
    if latex:
        lat = latex.strip()
        if len(lat) > 70:
            lat = lat[:67] + "…"
        draw.text((32, 200), f"$ {lat} $", fill=pal["expr"], font=font_expr)

    # --- 底部时间戳 / footer ---
    foot = footer or datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    draw.text((32, H - 40), foot, fill=pal["dim"], font=font_small)

    # --- 二维码 ---
    if qr_data:
        qr_px = 160
        qr_img = _qr_image(qr_data, qr_px, pal)
        if qr_img is not None:
            pos = (W - qr_px - 32, H - qr_px - 32)
            img.paste(qr_img, pos)

    # --- 输出 ---
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