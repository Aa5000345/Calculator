from __future__ import annotations

import argparse
import os
import sys

# 强制 UTF-8 输出（CI 上 cp1252 环境不再崩）
for _sn in ("stdout", "stderr"):
    _s = getattr(sys, _sn, None)
    if _s is not None and hasattr(_s, "reconfigure"):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)
DEFAULT_OUT = os.path.join(ROOT, "assets", "icon.ico")


# ---------------------------------------------------------------------------
# 字体
# ---------------------------------------------------------------------------

def _load_font(size: int):
    """按优先级尝试系统粗体字体，全失败则用 PIL 默认。"""
    try:
        from PIL import ImageFont
    except ImportError:
        return None

    candidates = [
        "C:/Windows/Fonts/msyhbd.ttc",       # 微软雅黑 Bold
        "C:/Windows/Fonts/segoeuib.ttf",     # Segoe UI Bold
        "C:/Windows/Fonts/arialbd.ttf",      # Arial Bold
        "/System/Library/Fonts/HelveticaNeue.ttc",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
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


# ---------------------------------------------------------------------------
# 渐变
# ---------------------------------------------------------------------------

def _make_gradient(size: int, c_top, c_mid, c_bottom):
    """三段垂直渐变（top → mid → bottom）。"""
    from PIL import Image
    img = Image.new("RGB", (size, size), c_top)
    px = img.load()
    for y in range(size):
        t = y / max(1, size - 1)
        if t < 0.5:
            u = t * 2
            r = int(c_top[0] + (c_mid[0] - c_top[0]) * u)
            g = int(c_top[1] + (c_mid[1] - c_top[1]) * u)
            b = int(c_top[2] + (c_mid[2] - c_top[2]) * u)
        else:
            u = (t - 0.5) * 2
            r = int(c_mid[0] + (c_bottom[0] - c_mid[0]) * u)
            g = int(c_mid[1] + (c_bottom[1] - c_mid[1]) * u)
            b = int(c_mid[2] + (c_bottom[2] - c_mid[2]) * u)
        for x in range(size):
            px[x, y] = (r, g, b)
    return img


# ---------------------------------------------------------------------------
# 图标绘制
# ---------------------------------------------------------------------------

def _render_icon(size: int):
    """返回 PIL.Image（RGBA）。

    设计：
    - 圆角方形渐变背景：浅蓝 → 中蓝 → 深蓝
    - 白色粗体 M，带轻微阴影
    - 底部一条圆角装饰线
    - 顶部一层极淡的高光
    """
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        raise SystemExit("需要 Pillow：pip install Pillow")

    # --- 背景渐变 ---
    gradient = _make_gradient(
        size,
        c_top=(96, 165, 250),      # #60A5FA 亮蓝
        c_mid=(59, 130, 246),      # #3B82F6 中蓝
        c_bottom=(30, 58, 138),    # #1E3A8A 深蓝
    )

    # --- 圆角遮罩 ---
    mask = Image.new("L", (size, size), 0)
    md = ImageDraw.Draw(mask)
    pad = max(2, size // 32)
    radius = max(16, size // 5)
    md.rounded_rectangle(
        [pad, pad, size - pad, size - pad],
        radius=radius, fill=255,
    )

    bg = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    bg.paste(gradient, (0, 0), mask)

    # --- 顶部高光（极淡，增加立体感）---
    highlight = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    hd = ImageDraw.Draw(highlight)
    hd.rounded_rectangle(
        [pad, pad, size - pad, size // 2],
        radius=radius, fill=(255, 255, 255, 16),
    )
    bg = Image.alpha_composite(bg, highlight)

    draw = ImageDraw.Draw(bg)

    # --- 中央白色 M ---
    font = _load_font(int(size * 0.62))
    text = "M"
    if font is not None:
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        # 视觉居中（略偏上，给底部装饰线留位置）
        tx = (size - tw) // 2 - bbox[0]
        ty = int((size - th) / 2 - bbox[1]) - size // 20
        # 阴影
        shadow_offset = max(1, size // 128)
        draw.text((tx + shadow_offset, ty + shadow_offset),
                  text, font=font, fill=(0, 0, 0, 70))
        # 主字
        draw.text((tx, ty), text, font=font, fill=(255, 255, 255, 255))

    # --- 底部装饰线 ---
    line_w = int(size * 0.34)
    line_h = max(2, size // 48)
    lx = (size - line_w) // 2
    ly = int(size * 0.80)
    draw.rounded_rectangle(
        [lx, ly, lx + line_w, ly + line_h],
        radius=line_h // 2,
        fill=(255, 255, 255, 210),
    )

    # --- 内描边（增加精致感）---
    border = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    bd = ImageDraw.Draw(border)
    bd.rounded_rectangle(
        [pad, pad, size - pad, size - pad],
        radius=radius, outline=(255, 255, 255, 40),
        width=max(1, size // 128),
    )
    bg = Image.alpha_composite(bg, border)

    return bg


# ---------------------------------------------------------------------------
# 输出
# ---------------------------------------------------------------------------

def _ensure_dir(path: str):
    d = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(d, exist_ok=True)


def make_ico(out_path: str, force: bool = False) -> str:
    if os.path.exists(out_path) and not force:
        print(f"[SKIP] 已存在：{out_path}（加 --force 覆盖）")
        return out_path

    _ensure_dir(out_path)
    base = _render_icon(256)
    sizes = [16, 24, 32, 48, 64, 128, 256]
    try:
        base.save(out_path, format="ICO",
                  sizes=[(s, s) for s in sizes])
    except Exception as e:
        raise SystemExit(f"保存 ICO 失败：{e}")

    size_kb = os.path.getsize(out_path) / 1024
    print(f"[OK] 生成 {out_path}（{size_kb:.1f} KB）")
    return out_path


def make_png(out_path: str, size: int = 256, force: bool = False) -> str:
    if os.path.exists(out_path) and not force:
        print(f"[SKIP] 已存在：{out_path}（加 --force 覆盖）")
        return out_path

    _ensure_dir(out_path)
    img = _render_icon(size)
    img.save(out_path, format="PNG")
    size_kb = os.path.getsize(out_path) / 1024
    print(f"[OK] 生成 {out_path}（{size_kb:.1f} KB）")
    return out_path


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="生成 MultiCalc 图标")
    parser.add_argument(
        "-o", "--out", default=None,
        help=f"输出路径（默认 {DEFAULT_OUT} 或 <repo>/assets/icon.png）")
    parser.add_argument(
        "--png", action="store_true", help="生成 PNG 而不是 ICO")
    parser.add_argument(
        "--size", type=int, default=256, help="PNG 尺寸（默认 256）")
    parser.add_argument(
        "--force", action="store_true", help="已存在也覆盖")
    args = parser.parse_args()

    if args.png:
        out = args.out or os.path.join(ROOT, "assets", "icon.png")
        make_png(out, size=args.size, force=args.force)
    else:
        out = args.out or DEFAULT_OUT
        make_ico(out, force=args.force)


if __name__ == "__main__":
    main()