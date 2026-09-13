"""LaTeX 工具：模板库 + PNG/SVG 渲染 + 复制。"""
from __future__ import annotations

import io
import os

TEMPLATES = {
    "quadratic":      r"x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}",
    "binomial":       r"(a + b)^n = \sum_{k=0}^{n} \binom{n}{k} a^{n-k} b^k",
    "euler":          r"e^{i\pi} + 1 = 0",
    "gauss":          r"\int_{-\infty}^{\infty} e^{-x^2}\,dx = \sqrt{\pi}",
    "taylor":         r"f(x) = \sum_{n=0}^{\infty} \frac{f^{(n)}(a)}{n!}(x-a)^n",
    "derivative":     r"\frac{d}{dx} f(x) = \lim_{h\to 0}\frac{f(x+h)-f(x)}{h}",
    "integral":       r"\int_a^b f(x)\,dx = F(b) - F(a)",
    "ft":             r"\hat{f}(\xi) = \int_{-\infty}^{\infty} f(x) e^{-2\pi i x \xi}\,dx",
    "matrix_2x2":     r"\begin{pmatrix} a & b \\ c & d \end{pmatrix}",
    "determinant":    r"\det(A) = \sum_{\sigma \in S_n} \mathrm{sgn}(\sigma) \prod_{i=1}^{n} a_{i,\sigma(i)}",
    "maxwell":        r"\nabla \cdot \mathbf{E} = \frac{\rho}{\varepsilon_0}",
    "schrodinger":    r"i\hbar\frac{\partial}{\partial t}\Psi = \hat{H}\Psi",
    "einstein":       r"E = mc^2",
    "bayes":          r"P(A\mid B) = \frac{P(B\mid A)P(A)}{P(B)}",
    "normal_dist":    r"f(x) = \frac{1}{\sigma\sqrt{2\pi}} e^{-\frac{(x-\mu)^2}{2\sigma^2}}",
    "cauchy":         r"\left|\sum_{i=1}^{n} a_i b_i\right|^2 \leq \sum_{i=1}^{n} a_i^2 \sum_{i=1}^{n} b_i^2",
}


def render_png(latex: str, path: str, fontsize: int = 18,
               dpi: int = 200, color: str = "#000000",
               transparent: bool = False) -> str:
    """渲染 LaTeX 到 PNG。"""
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg

    fig = Figure(figsize=(0.01, 0.01), dpi=dpi)
    if transparent:
        fig.patch.set_alpha(0.0)
    else:
        fig.patch.set_facecolor("white")
    try:
        fig.text(0, 0, f"${latex}$", fontsize=fontsize, color=color)
    except Exception as e:  # noqa: BLE001
        raise ValueError(f"LaTeX 渲染失败：{e}") from e
    FigureCanvasAgg(fig)
    fig.savefig(path, format="png", bbox_inches="tight",
                pad_inches=0.1, dpi=dpi, transparent=transparent)
    fig.clear()
    return path


def render_svg(latex: str, path: str, fontsize: int = 18,
               color: str = "#000000") -> str:
    """渲染 LaTeX 到 SVG。"""
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_svg import FigureCanvasSVG

    fig = Figure(figsize=(0.01, 0.01))
    fig.patch.set_facecolor("white")
    try:
        fig.text(0, 0, f"${latex}$", fontsize=fontsize, color=color)
    except Exception as e:  # noqa: BLE001
        raise ValueError(f"LaTeX 渲染失败：{e}") from e
    FigureCanvasSVG(fig)
    fig.savefig(path, format="svg", bbox_inches="tight", pad_inches=0.1)
    fig.clear()
    return path


def render_bytes(latex: str, fontsize: int = 18, dpi: int = 200,
                 color: str = "#000000") -> bytes | None:
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg

    fig = Figure(figsize=(0.01, 0.01), dpi=dpi)
    fig.patch.set_alpha(0.0)
    try:
        fig.text(0, 0, f"${latex}$", fontsize=fontsize, color=color)
    except Exception:
        fig.clear()
        return None
    buf = io.BytesIO()
    try:
        FigureCanvasAgg(fig)
        fig.savefig(buf, format="png", bbox_inches="tight",
                    pad_inches=0.08, transparent=True, dpi=dpi)
    except Exception:
        return None
    finally:
        fig.clear()
    return buf.getvalue()