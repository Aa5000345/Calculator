"""LaTeX 渲染组件：基于 matplotlib mathtext，无额外依赖。

使用 functools.lru_cache 缓存渲染结果（线程安全，容量 512）。
"""
from __future__ import annotations

import io
from functools import lru_cache

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel

from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure


@lru_cache(maxsize=512)
def _render_bytes_cached(latex: str, fontsize: int, dpi: int,
                         color: str) -> bytes | None:
    """渲染 LaTeX 到 PNG 字节。

    用 lru_cache 缓存；参数全部可哈希（str / int）。
    返回 None 表示渲染失败（会缓存 None，避免重复尝试）。
    """
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


def _render_bytes(latex: str, fontsize: int, dpi: int,
                  color: str) -> bytes | None:
    """包装：把不可哈希的入参规范化后调用缓存版本。"""
    try:
        return _render_bytes_cached(str(latex), int(fontsize),
                                    int(dpi), str(color))
    except Exception:
        return None


def clear_cache():
    """手动清空缓存（例如主题切换后）。"""
    try:
        _render_bytes_cached.cache_clear()
    except Exception:
        pass


class LatexLabel(QLabel):
    """把 LaTeX 渲染成 QPixmap 显示；失败时退化为纯文本。"""

    def __init__(self, parent=None, fontsize=14, dpi=200):
        super().__init__(parent)
        self.fontsize = fontsize
        self.dpi = dpi
        self._color = "#ffffff"
        self._latex = ""
        self._fallback = ""
        self.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.setWordWrap(True)
        self.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.setMinimumHeight(40)

    def set_color(self, color: str):
        if color == self._color:
            return
        self._color = color
        if self._latex:
            self.set_latex(self._latex, self._fallback)

    def set_latex(self, latex: str, fallback: str = ""):
        self._latex = latex or ""
        self._fallback = fallback or latex or ""
        if not self._latex:
            self.setPixmap(QPixmap())
            self.setText(self._fallback)
            return
        data = _render_bytes(self._latex, self.fontsize, self.dpi,
                             self._color)
        if data is None:
            self.setPixmap(QPixmap())
            self.setText(self._fallback)
            return
        pm = QPixmap()
        if not pm.loadFromData(data, "PNG"):
            self.setText(self._fallback)
            return
        self.setText("")
        self.setPixmap(pm)
        self.resize(pm.size())