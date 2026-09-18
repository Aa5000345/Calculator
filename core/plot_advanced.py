"""高级绘图辅助：多 Y 轴、区间填色、极坐标动画、GIF 导出。

设计：
- 与 matplotlib Figure 配合使用
- 不直接依赖 Qt（UI 层负责把 Figure 嵌入 Canvas）
- 帧缓冲用 list[np.ndarray] 表示（避免保存临时文件）

对外接口：
    sample_fill_between(f_expr, g_expr, xmin, xmax, points)
    add_twin_axis(fig, ...) -> ax2
    render_polar_frames(expr, tmin, tmax, frames) -> list
    save_gif_from_frames(frames, path, fps, dpi)
    save_gif_from_figure(fig, update_fn, n_frames, path, fps)
    save_gif_pillow(frames, path, fps)
"""
from __future__ import annotations

import io
import math
import os
from typing import Callable, Optional

import numpy as np


# ---------------------------------------------------------------------------
# 区间填色
# ---------------------------------------------------------------------------

def sample_fill_between(
        f_expr: str, g_expr: str,
        xmin: float, xmax: float,
        points: int = 400, var: str = "x"):
    """采样两条曲线，返回 (xs, ys_f, ys_g)。

    Args:
        f_expr: 上曲线表达式
        g_expr: 下曲线表达式（可为空，默认 0）
        xmin, xmax: 区间
        points: 采样点数

    Returns:
        ``(xs, ys_f, ys_g)``，都是 numpy 数组
    """
    from core import plot_sample as ps

    if not f_expr:
        raise ValueError("f_expr 不能为空")
    g = g_expr.strip() if g_expr else "0"

    xs, ys_f = ps.sample_cartesian(
        f_expr, xmin, xmax, points, var)
    _, ys_g = ps.sample_cartesian(
        g, xmin, xmax, points, var)
    return xs, ys_f, ys_g


# ---------------------------------------------------------------------------
# 多 Y 轴
# ---------------------------------------------------------------------------

def add_twin_axis(fig, base_ax=None,
                  ylabel: str = "", color: str = "#ff7f0e"):
    """在 Figure 上加一个共享 X 轴的右 Y 轴。

    Args:
        fig: matplotlib Figure
        base_ax: 基础轴（None 时用 gca）
        ylabel: 右轴标签
        color: 右轴颜色

    Returns:
        ax2（twinx 轴对象）
    """
    if base_ax is None:
        base_ax = fig.gca()
    ax2 = base_ax.twinx()
    ax2.set_ylabel(ylabel, color=color)
    ax2.tick_params(axis="y", colors=color)
    for s in ax2.spines.values():
        s.set_color(color)
    return ax2


# ---------------------------------------------------------------------------
# 极坐标动画
# ---------------------------------------------------------------------------

def render_polar_frames(
        expr: str,
        tmin: float = 0.0,
        tmax: float = 2 * math.pi,
        frames: int = 60,
        points: int = 400,
        var: str = "theta",
        animate_time: bool = False,
) -> list:
    """生成极坐标动画的每一帧。

    Args:
        expr: 极坐标表达式 ``r(theta)``；若 animate_time=True，
              表达式中可含 ``t`` 作为时间变量
        tmin, tmax: theta 范围
        frames: 帧数
        points: 每帧采样点数
        var: 变量名
        animate_time: 是否让 ``t`` 随时间变化

    Returns:
        list[tuple[xs, ys]]，每帧一个
    """
    from core import plot_sample as ps
    import sympy as sp

    out = []
    for i in range(int(frames)):
        progress = i / max(1, frames - 1)

        if animate_time:
            # 用 sympy 把 t 替换为当前值
            try:
                t_sym = sp.Symbol("t", real=True)
                expr_sym = sp.sympify(
                    str(expr).replace("^", "**"))
                t_val = progress * 2 * math.pi
                e_sub = expr_sym.subs({t_sym: t_val})
                cur_expr = str(e_sub)
            except Exception:
                cur_expr = expr
        else:
            cur_expr = expr

        try:
            xs, ys = ps.sample_polar(
                cur_expr, tmin, tmax, points, var)
            out.append((xs, ys))
        except Exception:
            out.append((np.array([]), np.array([])))

    return out


# ---------------------------------------------------------------------------
# GIF 导出
# ---------------------------------------------------------------------------

def save_gif_pillow(frames: list, path: str, fps: int = 20,
                    loop: int = 0):
    """把帧缓冲写成 GIF。

    Args:
        frames: list of PIL.Image
        path: 输出路径
        fps: 帧率
        loop: 0 = 无限循环
    """
    if not frames:
        raise ValueError("帧列表为空")
    try:
        from PIL import Image
    except ImportError:
        raise RuntimeError("需要 Pillow：pip install Pillow")

    duration_ms = int(1000 / max(1, fps))
    first = frames[0]
    rest = frames[1:] if len(frames) > 1 else []
    first.save(
        path,
        save_all=True,
        append_images=rest,
        duration=duration_ms,
        loop=loop,
        optimize=False,
    )
    return path


def render_figure_to_frames(
        fig,
        update_fn: Callable,
        n_frames: int,
        dpi: int = 100,
) -> list:
    """用一个 Figure + 更新函数渲染 N 帧。

    Args:
        fig: matplotlib Figure
        update_fn: ``fn(fig, frame_idx)``，负责更新图形
        n_frames: 帧数
        dpi: 分辨率

    Returns:
        list of PIL.Image
    """
    try:
        from PIL import Image
    except ImportError:
        raise RuntimeError("需要 Pillow")

    frames = []
    for i in range(int(n_frames)):
        update_fn(fig, i)
        buf = io.BytesIO()
        try:
            fig.savefig(buf, format="png", dpi=dpi,
                        bbox_inches="tight", pad_inches=0.05)
        except Exception:
            continue
        buf.seek(0)
        try:
            img = Image.open(buf).convert("RGBA")
            # 转 RGB（GIF 不支持 RGBA 透明）
            bg = Image.new("RGB", img.size, (30, 30, 30))
            bg.paste(img, mask=img.split()[-1])
            frames.append(bg)
        except Exception:
            continue
    return frames


def save_gif_from_figure(
        fig,
        update_fn: Callable,
        n_frames: int,
        path: str,
        fps: int = 20,
        dpi: int = 100,
):
    """一步：渲染 + 保存 GIF。"""
    frames = render_figure_to_frames(
        fig, update_fn, n_frames, dpi=dpi)
    if not frames:
        raise RuntimeError("未能生成任何帧")
    return save_gif_pillow(frames, path, fps=fps)


# ---------------------------------------------------------------------------
# 极坐标 GIF
# ---------------------------------------------------------------------------

def save_polar_gif(
        expr: str,
        path: str,
        tmin: float = 0.0,
        tmax: float = 2 * math.pi,
        frames: int = 60,
        points: int = 400,
        fps: int = 20,
        animate_time: bool = False,
        line_color: str = "#007acc",
        bg_color: str = "#1e1e1e",
        fg_color: str = "#ffffff",
        dpi: int = 100,
        figure_size: tuple = (5, 5),
):
    """绘制极坐标动画并保存为 GIF。"""
    import matplotlib
    matplotlib.use("Agg", force=False)
    from matplotlib.figure import Figure

    data = render_polar_frames(
        expr, tmin, tmax, frames, points,
        animate_time=animate_time)

    fig = Figure(figsize=figure_size, dpi=dpi)
    fig.patch.set_facecolor(bg_color)

    frames_pil = []
    try:
        from PIL import Image
    except ImportError:
        raise RuntimeError("需要 Pillow")

    # 计算统一的范围
    all_x = []
    all_y = []
    for xs, ys in data:
        if len(xs):
            all_x.extend(np.asarray(xs).ravel().tolist())
            all_y.extend(np.asarray(ys).ravel().tolist())
    if all_x:
        xmin, xmax = min(all_x), max(all_x)
        ymin, ymax = min(all_y), max(all_y)
        # 保证正方形
        cx = (xmin + xmax) / 2
        cy = (ymin + ymax) / 2
        half = max(xmax - xmin, ymax - ymin) / 2 * 1.15
        if half < 1e-9:
            half = 1.0
        lim = ((cx - half, cx + half), (cy - half, cy + half))
    else:
        lim = ((-1, 1), (-1, 1))

    for i, (xs, ys) in enumerate(data):
        fig.clear()
        ax = fig.add_subplot(111)
        ax.set_facecolor(bg_color)
        ax.tick_params(colors=fg_color)
        for s in ax.spines.values():
            s.set_color(fg_color)

        if len(xs):
            # 已画过的部分：完整
            ax.plot(xs, ys, color=line_color, linewidth=1.8)
            # 头部：亮点
            ax.plot([xs[-1]], [ys[-1]], "o",
                    color="#ff8800", markersize=6)

        ax.set_xlim(lim[0])
        ax.set_ylim(lim[1])
        ax.set_aspect("equal")
        ax.grid(True, color="#666", alpha=0.3, linewidth=0.5)

        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=dpi,
                    bbox_inches="tight", pad_inches=0.05)
        buf.seek(0)
        try:
            img = Image.open(buf).convert("RGBA")
            bg = Image.new("RGB", img.size, (30, 30, 30))
            bg.paste(img, mask=img.split()[-1])
            frames_pil.append(bg)
        except Exception:
            continue

    if not frames_pil:
        raise RuntimeError("未能生成任何帧")
    return save_gif_pillow(frames_pil, path, fps=fps)


# ---------------------------------------------------------------------------
# fill_between
# ---------------------------------------------------------------------------

def apply_fill_between(ax, xs, ys_f, ys_g,
                       color: str = "#007acc",
                       alpha: float = 0.35,
                       label: str = ""):
    """在轴上填充两条曲线之间的区域。

    Args:
        ax: matplotlib axis
        xs, ys_f, ys_g: 采样数据
        color: 填充色
        alpha: 透明度
        label: 图例标签（可选）
    """
    try:
        ax.fill_between(
            xs, ys_f, ys_g,
            color=color, alpha=alpha,
            label=label or None)
    except Exception:
        # 退化为 where 参数
        try:
            mask = np.isfinite(ys_f) & np.isfinite(ys_g)
            ax.fill_between(
                xs, ys_f, ys_g,
                where=mask, color=color, alpha=alpha,
                label=label or None)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# 便捷：从数据表绘图
# ---------------------------------------------------------------------------

def plot_xy_from_lists(ax, xs: list, ys: list,
                       color: str = "#007acc",
                       label: str = "",
                       kind: str = "line",
                       marker: str = "o",
                       marker_size: int = 4):
    """从两个列表绘图。

    kind: "line" | "scatter" | "line+marker"
    """
    try:
        xs_a = np.asarray(xs, dtype=float)
        ys_a = np.asarray(ys, dtype=float)
    except Exception:
        raise ValueError("X/Y 数据必须都是数字")
    if len(xs_a) != len(ys_a):
        raise ValueError("X/Y 长度不一致")

    if kind == "scatter":
        ax.scatter(xs_a, ys_a, c=color, s=marker_size ** 2,
                   label=label or None)
    elif kind == "line+marker":
        ax.plot(xs_a, ys_a, color=color, linewidth=1.4,
                marker=marker, markersize=marker_size,
                label=label or None)
    else:
        ax.plot(xs_a, ys_a, color=color, linewidth=1.4,
                label=label or None)


__all__ = [
    "sample_fill_between",
    "add_twin_axis",
    "render_polar_frames",
    "save_gif_pillow",
    "render_figure_to_frames",
    "save_gif_from_figure",
    "save_polar_gif",
    "apply_fill_between",
    "plot_xy_from_lists",
]