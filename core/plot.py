"""绘图采样 + 高级绘图。

合并自：core/plot_sample.py + core/plot_advanced.py

依赖：numpy / sympy / matplotlib（GIF 用 Pillow）

对外接口：
    # 采样
    sample_cartesian, sample_polar, sample_parametric,
    sample_surface, parse_lambda2
    # 高级
    sample_fill_between, add_twin_axis,
    render_polar_frames, save_gif_pillow,
    render_figure_to_frames, save_gif_from_figure,
    save_polar_gif, apply_fill_between, plot_xy_from_lists
"""
from __future__ import annotations

import io
import math
from typing import Callable

import numpy as np
import sympy as sp

from core.engine import _parse, _clean

__all__ = [
    # 采样
    "sample_cartesian", "sample_polar", "sample_parametric",
    "sample_surface", "parse_lambda2",
    # 高级
    "sample_fill_between", "add_twin_axis",
    "render_polar_frames", "save_gif_pillow",
    "render_figure_to_frames", "save_gif_from_figure",
    "save_polar_gif", "apply_fill_between", "plot_xy_from_lists",
]


# ===========================================================================
# 采样
# ===========================================================================

def sample_cartesian(expr, xmin, xmax, points=800, var="x"):
    """直角坐标采样：返回 (xs, ys)。"""
    v = sp.Symbol(var)
    e = _parse(expr)
    f = sp.lambdify(v, e, modules=["numpy"])
    xs = np.linspace(float(xmin), float(xmax), int(points))
    with np.errstate(all="ignore"):
        try:
            ys = f(xs)
        except Exception as ex:  # noqa: BLE001
            raise RuntimeError(f"函数采样失败：{ex}") from ex
    return xs, _clean(ys)


def sample_polar(expr, tmin, tmax, points=800, var="theta"):
    """极坐标采样：返回 (xs, ys)。"""
    t = sp.Symbol(var)
    e = _parse(expr)
    f = sp.lambdify(t, e, modules=["numpy"])
    ts = np.linspace(float(tmin), float(tmax), int(points))
    with np.errstate(all="ignore"):
        try:
            rs = _clean(f(ts))
        except Exception as ex:  # noqa: BLE001
            raise RuntimeError(f"函数采样失败：{ex}") from ex
    return rs * np.cos(ts), rs * np.sin(ts)


def sample_parametric(xexpr, yexpr, tmin, tmax, points=800,
                      var="t"):
    """参数方程采样：返回 (xs, ys)。"""
    t = sp.Symbol(var)
    fx = sp.lambdify(t, _parse(xexpr), modules=["numpy"])
    fy = sp.lambdify(t, _parse(yexpr), modules=["numpy"])
    ts = np.linspace(float(tmin), float(tmax), int(points))
    with np.errstate(all="ignore"):
        try:
            xs = fx(ts)
            ys = fy(ts)
        except Exception as ex:  # noqa: BLE001
            raise RuntimeError(f"函数采样失败：{ex}") from ex
    return _clean(xs), _clean(ys)


def parse_lambda2(expr_text, vars_=("x", "y")):
    """返回 f(X, Y) —— 用于隐函数 contour。

    这是公开 API（旧名 `_parse_lambda2` 保留为别名）。
    """
    syms = [sp.Symbol(v) for v in vars_]
    e = _parse(expr_text)
    f = sp.lambdify(syms, e, modules=["numpy"])
    return lambda X, Y: f(X, Y)


# 向后兼容别名
_parse_lambda2 = parse_lambda2


def sample_surface(expr, xmin, xmax, ymin, ymax,
                   nx=60, ny=60, var_x="x", var_y="y"):
    """3D 曲面采样：返回 (X, Y, Z)。"""
    vx = sp.Symbol(var_x)
    vy = sp.Symbol(var_y)
    e = _parse(expr)
    f = sp.lambdify((vx, vy), e, modules=["numpy"])
    xs = np.linspace(float(xmin), float(xmax), int(nx))
    ys = np.linspace(float(ymin), float(ymax), int(ny))
    X, Y = np.meshgrid(xs, ys)
    with np.errstate(all="ignore"):
        try:
            Z = f(X, Y)
        except Exception as ex:  # noqa: BLE001
            raise RuntimeError(f"曲面采样失败：{ex}") from ex
    Z = np.asarray(Z, dtype=float)
    Z[~np.isfinite(Z)] = np.nan
    return X, Y, Z


# ===========================================================================
# 区间填色
# ===========================================================================

def sample_fill_between(f_expr: str, g_expr: str,
                        xmin: float, xmax: float,
                        points: int = 400, var: str = "x"):
    """采样两条曲线，返回 (xs, ys_f, ys_g)。"""
    if not f_expr:
        raise ValueError("f_expr 不能为空")
    g = g_expr.strip() if g_expr else "0"

    xs, ys_f = sample_cartesian(f_expr, xmin, xmax, points, var)
    _, ys_g = sample_cartesian(g, xmin, xmax, points, var)
    return xs, ys_f, ys_g


# ===========================================================================
# 多 Y 轴
# ===========================================================================

def add_twin_axis(fig, base_ax=None,
                  ylabel: str = "",
                  color: str = "#ff7f0e"):
    """在 Figure 上加一个共享 X 轴的右 Y 轴。"""
    if base_ax is None:
        base_ax = fig.gca()
    ax2 = base_ax.twinx()
    ax2.set_ylabel(ylabel, color=color)
    ax2.tick_params(axis="y", colors=color)
    for s in ax2.spines.values():
        s.set_color(color)
    return ax2


# ===========================================================================
# 极坐标动画
# ===========================================================================

def render_polar_frames(
        expr: str,
        tmin: float = 0.0,
        tmax: float = 2 * math.pi,
        frames: int = 60,
        points: int = 400,
        var: str = "theta",
        animate_time: bool = False,
) -> list:
    """生成极坐标动画的每一帧。返回 list[(xs, ys)]。"""
    out = []
    for i in range(int(frames)):
        progress = i / max(1, frames - 1)

        if animate_time:
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
            xs, ys = sample_polar(
                cur_expr, tmin, tmax, points, var)
            out.append((xs, ys))
        except Exception:
            out.append((np.array([]), np.array([])))
    return out


# ===========================================================================
# GIF 导出
# ===========================================================================

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
        from PIL import Image  # noqa: F401
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
        update_fn: ``fn(fig, frame_idx)``
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

    try:
        from PIL import Image
    except ImportError:
        raise RuntimeError("需要 Pillow")

    all_x = []
    all_y = []
    for xs, ys in data:
        if len(xs):
            all_x.extend(np.asarray(xs).ravel().tolist())
            all_y.extend(np.asarray(ys).ravel().tolist())
    if all_x:
        xmin, xmax = min(all_x), max(all_x)
        ymin, ymax = min(all_y), max(all_y)
        cx = (xmin + xmax) / 2
        cy = (ymin + ymax) / 2
        half = max(xmax - xmin, ymax - ymin) / 2 * 1.15
        if half < 1e-9:
            half = 1.0
        lim = ((cx - half, cx + half), (cy - half, cy + half))
    else:
        lim = ((-1, 1), (-1, 1))

    frames_pil = []
    for i, (xs, ys) in enumerate(data):
        fig.clear()
        ax = fig.add_subplot(111)
        ax.set_facecolor(bg_color)
        ax.tick_params(colors=fg_color)
        for s in ax.spines.values():
            s.set_color(fg_color)

        if len(xs):
            ax.plot(xs, ys, color=line_color, linewidth=1.8)
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


# ===========================================================================
# fill_between
# ===========================================================================

def apply_fill_between(ax, xs, ys_f, ys_g,
                       color: str = "#007acc",
                       alpha: float = 0.35,
                       label: str = ""):
    """在轴上填充两条曲线之间的区域。"""
    try:
        ax.fill_between(
            xs, ys_f, ys_g,
            color=color, alpha=alpha,
            label=label or None)
    except Exception:
        try:
            mask = np.isfinite(ys_f) & np.isfinite(ys_g)
            ax.fill_between(
                xs, ys_f, ys_g,
                where=mask, color=color, alpha=alpha,
                label=label or None)
        except Exception:
            pass


# ===========================================================================
# 便捷：从数据表绘图
# ===========================================================================

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