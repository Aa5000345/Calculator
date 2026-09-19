"""面板共享工具：错误展示 / 异步执行 / 布局清理 / 统一 ResultView /
InlinePreviewBar（实时预览）/ 内联校验 / 差异徽章集成。

依赖（合并后）：
    core.base      —— CalcError / log_exc / log_path
    core.runtime   —— Worker
    core.share     —— render_share_card（分享卡片）
    ui.dialogs     —— LatexLabel
    ui.shell       —— bus / toast（延迟导入）
    ui.widgets.input —— DiffBadge（延迟导入）

对外接口：
    _clear_layout, friendly_error, run_async,
    mark_field_error, clear_field_error,
    InlinePreviewBar, CollapsibleGroup, ResultView
"""
from __future__ import annotations

import csv as _csv
import io as _io
import json as _json
import re as _re

from PySide6.QtCore import (
    Qt, Signal, QPropertyAnimation, QEasingCurve, QTimer,
)
from PySide6.QtWidgets import (
    QWidget, QPlainTextEdit, QPushButton, QVBoxLayout,
    QHBoxLayout, QTabWidget, QScrollArea, QMessageBox,
    QApplication, QLabel, QMenu, QToolButton, QFrame,
    QGraphicsOpacityEffect,
)

from core.base import CalcError, log_exc, log_path
from core.runtime import Worker
from ui.dialogs import LatexLabel


# =====================================================================
# 通用工具
# =====================================================================

def _clear_layout(layout):
    while layout.count():
        item = layout.takeAt(0)
        w = item.widget()
        if w is not None:
            w.setParent(None)
            w.deleteLater()
        else:
            sub = item.layout()
            if sub is not None:
                _clear_layout(sub)


def friendly_error(i18n, exc, module="ui"):
    """把异常转为用户级文案。"""
    try:
        log_exc(exc, module=module)
    except Exception:
        pass
    if isinstance(exc, CalcError):
        try:
            return exc.friendly(i18n)
        except Exception:
            return str(exc)
    return f"{type(exc).__name__}: {exc}"


def run_async(parent_widget, fn, *args,
              on_done=None, on_fail=None, on_cancel=None,
              cancel_btn=None, main_btn=None, **kwargs):
    """在 QThread 中执行 fn，返回 Worker。"""
    w = Worker(fn, *args, **kwargs)

    if cancel_btn is not None:
        cancel_btn.setEnabled(True)
        cancel_btn._current_worker = w
        if not getattr(cancel_btn, "_cancel_connected", False):
            def _on_cancel_clicked(_btn=cancel_btn):
                wk = getattr(_btn, "_current_worker", None)
                if wk is not None:
                    try:
                        wk.cancel()
                    except Exception:
                        pass
            cancel_btn.clicked.connect(_on_cancel_clicked)
            cancel_btn._cancel_connected = True

    def _restore():
        if cancel_btn is not None:
            cancel_btn.setEnabled(False)
        if main_btn is not None:
            main_btn.setEnabled(True)

    def _done(r):
        _restore()
        if on_done:
            on_done(r)

    def _fail(e):
        _restore()
        if on_fail:
            on_fail(e)

    def _cancelled():
        _restore()
        if on_cancel:
            on_cancel()

    w.done.connect(_done)
    w.failed.connect(_fail)
    w.cancelled.connect(_cancelled)
    w.finished.connect(w.deleteLater)
    w.start()
    return w


# =====================================================================
# 内联校验辅助（红框 + tooltip）
# =====================================================================

_ERROR_QSS = (
    "border: 1px solid #ff5555;"
    "border-radius: 4px;"
)


def mark_field_error(widget, msg: str = ""):
    """给输入控件加红框 + tooltip。多次调用安全，会保留原样式表。"""
    try:
        if not hasattr(widget, "_prev_qss_saved"):
            widget._prev_qss_saved = widget.styleSheet()
        widget.setStyleSheet(_ERROR_QSS)
        widget.setToolTip(msg or "")
    except Exception:
        pass


def clear_field_error(widget):
    """清除红框，恢复原样式表。"""
    try:
        if getattr(widget, "_prev_qss_saved", None) is not None:
            widget.setStyleSheet(widget._prev_qss_saved)
            widget._prev_qss_saved = None
        else:
            widget.setStyleSheet("")
        widget.setToolTip("")
    except Exception:
        pass


# =====================================================================
# 实时预览条
# =====================================================================

# 使用词边界，避免 sin / cos 命中 integrate 这种误伤
_SKIP_RE = _re.compile(
    r"\b(integrate|solve|limit|dsolve|quad|minimize|linprog|"
    r"summation|product|ode|dsolve)\b",
    _re.IGNORECASE,
)


class InlinePreviewBar(QLabel):
    """输入时显示实时预览的灰色小字。"""

    def __init__(self, calc_fn=None, parent=None):
        super().__init__(parent)
        self._calc_fn = calc_fn
        self._enabled_getter = None
        self._pending = ""

        self.setStyleSheet(
            "color: #888; padding-left: 2px; font-size: 10pt;")
        self.setMinimumHeight(18)
        self.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(300)
        self._timer.timeout.connect(self._do_preview)

    def set_calc_fn(self, fn):
        self._calc_fn = fn

    def attach(self, line_edit, enabled_getter=None):
        self._enabled_getter = enabled_getter
        line_edit.textChanged.connect(self._on_text)

    def refresh(self, text=None):
        """外部触发预览刷新（多输入框联动场景）。"""
        if text is None:
            text = self._pending
        self._on_text(text)

    def _on_text(self, text):
        self._pending = text or ""
        if not self._should_preview(self._pending):
            self.setText("")
            return
        self._timer.start()

    @staticmethod
    def _should_preview(text: str) -> bool:
        s = (text or "").strip()
        if not s or len(s) > 40:
            return False
        return _SKIP_RE.search(s) is None

    def _do_preview(self):
        try:
            if self._enabled_getter is not None:
                if not self._enabled_getter():
                    self.setText("")
                    return
        except Exception:
            pass
        if self._calc_fn is None:
            return
        try:
            result = self._calc_fn(self._pending)
            if result is None:
                self.setText("")
                return
            if isinstance(result, tuple) and len(result) == 2:
                value, _ = result
            else:
                value = result
            text = str(value)
            if len(text) > 80:
                text = text[:77] + "…"
            self.setText(f"= {text}")
        except Exception:
            self.setText("")


# =====================================================================
# 可折叠步骤组
# =====================================================================

class CollapsibleGroup(QFrame):
    """简单可折叠容器（默认收起）。"""

    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)

        self._btn = QToolButton()
        self._btn.setText(title)
        self._btn.setCheckable(True)
        self._btn.setChecked(False)
        self._btn.setToolButtonStyle(
            Qt.ToolButtonTextBesideIcon)
        self._btn.setArrowType(Qt.RightArrow)
        self._btn.setStyleSheet(
            "QToolButton{border:none;padding:2px;}")
        self._btn.toggled.connect(self._toggle)

        self.body = QWidget()
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(12, 4, 4, 4)
        self.body.setVisible(False)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._btn)
        lay.addWidget(self.body)

    def _toggle(self, checked):
        self.body.setVisible(checked)
        self._btn.setArrowType(
            Qt.DownArrow if checked else Qt.RightArrow)

    def add_widget(self, w):
        self.body_layout.addWidget(w)

    def add_text(self, text):
        lbl = QLabel(str(text))
        lbl.setWordWrap(True)
        lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lbl.setStyleSheet("font-family: Consolas, monospace;")
        self.body_layout.addWidget(lbl)


# =====================================================================
# 统一结果查看器
# =====================================================================

class ResultView(QWidget):
    """统一结果查看器。

    - 文本 + LaTeX + 步骤三个 Tab
    - 错误卡片（含重试）
    - 耗时显示
    - 右键菜单（复制 / 发送 / 分屏）
    - 差异徽章（对比上次结果）
    """

    elapsed_changed = Signal(float)

    def __init__(self, i18n, parent=None):
        super().__init__(parent)
        self.i18n = i18n
        self._last_error = ""
        self._last_text = ""
        self._last_latex = ""
        self._last_retry = None
        self._anim = None
        self._flash_overlay = None
        self._prev_text = ""

        # ---- 主文本 + LaTeX ----
        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)

        self.latex = LatexLabel(fontsize=16)
        latex_scroll = QScrollArea()
        latex_scroll.setWidgetResizable(True)
        latex_scroll.setWidget(self.latex)

        # ---- 步骤 ----
        self.steps_scroll = QScrollArea()
        self.steps_scroll.setWidgetResizable(True)
        self.steps_container = QWidget()
        self.steps_layout = QVBoxLayout(self.steps_container)
        self.steps_layout.setContentsMargins(4, 4, 4, 4)
        self.steps_scroll.setWidget(self.steps_container)

        self.tabs = QTabWidget()
        self.tabs.addTab(self.text, i18n.t("plain_text", "Plain"))
        self.tabs.addTab(latex_scroll,
                         i18n.t("latex_preview", "LaTeX"))
        self.tabs.addTab(self.steps_scroll,
                         i18n.t("steps", "步骤"))

        # ---- 差异徽章 ----
        try:
            from ui.widgets.input import DiffBadge
            self.diff_badge = DiffBadge(i18n)
        except Exception:
            self.diff_badge = None

        # ---- 错误卡片 ----
        self.error_card = QFrame()
        self.error_card.setFrameShape(QFrame.StyledPanel)
        self.error_card.setVisible(False)
        ec = QHBoxLayout(self.error_card)
        self.error_label = QLabel()
        self.error_label.setWordWrap(True)
        ec.addWidget(self.error_label, 1)

        self.btn_copy_err = QPushButton(
            i18n.t("copy_error", "复制详情"))
        self.btn_view_log = QPushButton(
            i18n.t("view_log", "查看日志"))
        self.btn_retry = QPushButton(i18n.t("retry", "重试"))
        ec.addWidget(self.btn_copy_err)
        ec.addWidget(self.btn_view_log)
        ec.addWidget(self.btn_retry)

        self.btn_copy_err.clicked.connect(self._copy_error)
        self.btn_view_log.clicked.connect(self._view_log)
        self.btn_retry.clicked.connect(self._retry)

        # ---- 耗时 + 徽章行 ----
        self.elapsed_label = QLabel("")
        self.elapsed_label.setStyleSheet("color: #888;")
        row = QHBoxLayout()
        row.addWidget(self.elapsed_label)
        if self.diff_badge is not None:
            row.addWidget(self.diff_badge)
        row.addStretch(1)

        # ---- 布局 ----
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.tabs, 1)
        lay.addWidget(self.error_card)
        lay.addLayout(row)

        # ---- 右键菜单 ----
        for w in (self.text, self.latex):
            w.setContextMenuPolicy(Qt.CustomContextMenu)
            w.customContextMenuRequested.connect(
                self._show_context_menu)

    # ------------------------------------------------------------------

    def show_result(self, text, latex="", steps=None, elapsed=None,
                    highlight=True):
        if self._last_text:
            self._prev_text = self._last_text

        self._last_text = text or ""
        self._last_latex = latex or ""
        self._last_error = ""
        self._last_retry = None

        self.text.setPlainText(self._last_text)
        self.latex.set_latex(self._last_latex, self._last_text)
        self.error_card.setVisible(False)

        self._fill_steps(steps)

        if elapsed is not None:
            self._set_elapsed(elapsed)

        if self.diff_badge is not None:
            try:
                if self._prev_text and self._last_text:
                    self.diff_badge.update_from(
                        self._prev_text, self._last_text)
                else:
                    self.diff_badge.clear()
            except Exception:
                self.diff_badge.clear()

        if highlight:
            self._flash()

    def show_error(self, exc, elapsed=None, retry_cb=None,
                   steps=None):
        msg = friendly_error(self.i18n, exc, "ui")
        self._last_error = msg
        self._last_text = msg
        self._last_latex = ""
        self._last_retry = retry_cb

        self.text.setPlainText(msg)
        self.latex.set_latex("", msg)
        self.error_label.setText(msg)
        self.error_card.setVisible(True)
        self.btn_retry.setVisible(retry_cb is not None)

        self._fill_steps(steps)

        if elapsed is not None:
            self._set_elapsed(elapsed)

        if self.diff_badge is not None:
            self.diff_badge.clear()

    def set_color(self, color):
        self.latex.set_color(color)

    def clear_diff_badge(self):
        if self.diff_badge is not None:
            self.diff_badge.clear()

    def reset_history(self):
        """清空差异对比基准（例如切换面板时）。"""
        self._prev_text = ""
        if self.diff_badge is not None:
            self.diff_badge.clear()

    # ------------------------------------------------------------------

    def _fill_steps(self, steps):
        _clear_layout(self.steps_layout)
        if steps:
            for i, step in enumerate(steps):
                box = CollapsibleGroup(f"Step {i + 1}")
                box.add_text(step)
                self.steps_layout.addWidget(box)
            self.steps_layout.addStretch(1)

    def _set_elapsed(self, seconds):
        try:
            s = float(seconds)
            self.elapsed_label.setText(f"⏱ {s:.3f}s")
            self.elapsed_changed.emit(s)
        except Exception:
            self.elapsed_label.setText("")

    def _flash(self):
        """用临时叠加层做高亮动画 —— 不改动 styleSheet。"""
        try:
            from PySide6.QtGui import QColor

            old = self._flash_overlay
            if old is not None:
                try:
                    old.deleteLater()
                except Exception:
                    pass

            vp = self.text.viewport()
            if vp is None:
                return

            overlay = QFrame(vp)
            overlay.setAttribute(
                Qt.WA_TransparentForMouseEvents, True)
            overlay.setFrameShape(QFrame.NoFrame)
            bg = self.text.palette().base().color()
            hi = QColor(bg).lighter(130).name()
            overlay.setStyleSheet(
                f"background-color: {hi};")
            overlay.setGeometry(vp.rect())
            overlay.show()
            overlay.raise_()

            effect = QGraphicsOpacityEffect(overlay)
            effect.setOpacity(1.0)
            overlay.setGraphicsEffect(effect)

            anim = QPropertyAnimation(
                effect, b"opacity", self)
            anim.setDuration(450)
            anim.setStartValue(1.0)
            anim.setEndValue(0.0)
            anim.setEasingCurve(QEasingCurve.InOutQuad)

            def _cleanup():
                try:
                    overlay.deleteLater()
                except Exception:
                    pass
                if self._flash_overlay is overlay:
                    self._flash_overlay = None

            anim.finished.connect(_cleanup)
            anim.start(QPropertyAnimation.DeleteWhenStopped)
            self._anim = anim
            self._flash_overlay = overlay
            QTimer.singleShot(900, _cleanup)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # 右键菜单
    # ------------------------------------------------------------------

    def _show_context_menu(self, pos):
        i18n = self.i18n
        menu = QMenu(self)
        a_text = menu.addAction(
            i18n.t("copy_as_text", "复制为文本"))
        a_latex = menu.addAction(
            i18n.t("copy_as_latex", "复制为 LaTeX"))
        a_json = menu.addAction(
            i18n.t("copy_as_json", "复制为 JSON"))
        a_csv = menu.addAction(
            i18n.t("copy_as_csv", "复制为 CSV"))
        a_md = menu.addAction(
            i18n.t("copy_as_markdown", "复制为 Markdown"))
        a_card = menu.addAction(
            i18n.t("share_card", "分享卡片 (PNG)…"))
        menu.addSeparator()

        send_menu = menu.addMenu(i18n.t("send_to", "发送到…"))
        a_send_unit = send_menu.addAction(
            i18n.t("send_to_unit", "单位面板"))
        a_send_sci = send_menu.addAction(
            i18n.t("send_to_sci", "科学计算"))
        a_send_table = send_menu.addAction(
            i18n.t("send_to_table", "数据表（新行）"))
        a_send_snippet = send_menu.addAction(
            i18n.t("send_to_snippet", "保存为片段"))
        a_send_plot = send_menu.addAction(
            i18n.t("send_to_plot", "绘图面板"))
        a_split = send_menu.addAction(
            i18n.t("open_in_split", "在新分屏打开"))

        chosen = menu.exec(self.text.mapToGlobal(pos))
        if chosen is None:
            return
        try:
            if chosen is a_text:
                QApplication.clipboard().setText(self._last_text)
            elif chosen is a_latex:
                QApplication.clipboard().setText(
                    self._last_latex or self._last_text)
            elif chosen is a_json:
                payload = {
                    "text": self._last_text,
                    "latex": self._last_latex,
                    "error": self._last_error or None,
                }
                QApplication.clipboard().setText(
                    _json.dumps(payload, ensure_ascii=False,
                                indent=2))
            elif chosen is a_csv:
                buf = _io.StringIO()
                w = _csv.writer(buf)
                w.writerow(["text", "latex"])
                w.writerow([self._last_text, self._last_latex])
                QApplication.clipboard().setText(buf.getvalue())
            elif chosen is a_md:
                self._copy_as_markdown()
            elif chosen is a_card:
                self._save_share_card()
            elif chosen is a_send_unit:
                from ui.shell import bus
                bus().send_to_unit.emit(self._last_text)
            elif chosen is a_send_sci:
                from ui.shell import bus
                bus().send_to_sci.emit(self._last_text)
            elif chosen is a_send_table:
                from ui.shell import bus
                bus().send_to_table.emit(self._last_text)
            elif chosen is a_send_snippet:
                from ui.shell import bus
                preview = (self._last_text or "").strip().splitlines()
                name = (preview[0][:30] if preview else "snippet")
                bus().send_to_snippet.emit(
                    name, self._last_text)
            elif chosen is a_send_plot:
                from ui.shell import bus
                bus().send_to_plot.emit(self._last_text)
            elif chosen is a_split:
                self._open_in_split()
        except Exception as e:
            log_exc(e, module="ResultView._show_context_menu")

    def _open_in_split(self):
        try:
            from ui.shell import bus
            w = self.window()
            opener = getattr(w, "open_current_in_split", None)
            if callable(opener):
                opener()
            if self._last_text:
                bus().send_to_sci.emit(self._last_text)
        except Exception as e:
            log_exc(e, module="ResultView._open_in_split")

    def _copy_as_markdown(self):
        try:
            text = self._last_text or ""
            latex = self._last_latex or ""
            parts = []
            if text:
                parts.append(f"```\n{text}\n```")
            if latex:
                parts.append(f"$$\n{latex}\n$$")
            md = "\n\n".join(parts) if parts else text
            QApplication.clipboard().setText(md)
            QMessageBox.information(
                self, "OK", self.i18n.t("copied", "已复制"))
        except Exception as e:
            log_exc(e, module="ResultView._copy_as_markdown")

    def _save_share_card(self):
        """弹出保存对话框，生成分享卡片 PNG（含二维码）。"""
        try:
            from PySide6.QtWidgets import QFileDialog
            from core import share as sc_mod
        except Exception as e:
            log_exc(e,
                    module="ResultView._save_share_card.import")
            return

        ts = __import__("datetime").datetime.now().strftime(
            "%Y%m%d_%H%M%S")
        default_name = f"multicalc_{ts}.png"
        path, _ = QFileDialog.getSaveFileName(
            self, self.i18n.t("share_card", "分享卡片"),
            default_name, "PNG (*.png)")
        if not path:
            return

        qr_data = (self._last_latex
                   or self._last_text or "").strip()
        if len(qr_data) > 180:
            qr_data = qr_data[:180]

        expr = ""
        try:
            lines = (self._last_text or "").splitlines()
            if lines:
                expr = lines[0][:80]
        except Exception:
            expr = ""

        try:
            sc_mod.render_share_card(
                expr=expr,
                result=self._last_text or "",
                latex=self._last_latex or "",
                title="MultiCalc",
                out_path=path,
                qr_data=qr_data or None,
                theme="dark",
            )
            try:
                from ui.shell import toast
                toast(self.window(), path, level="success")
            except Exception:
                QMessageBox.information(self, "OK", path)
        except Exception as e:
            log_exc(e, module="ResultView._save_share_card")
            QMessageBox.warning(self, "Error", str(e))

    def _copy_error(self):
        try:
            payload = self._last_error + "\n\nlog: " + log_path()
            QApplication.clipboard().setText(payload)
            QMessageBox.information(
                self, "OK", self.i18n.t("copied", "已复制"))
        except Exception as e:
            log_exc(e, module="ResultView._copy_error")

    def _view_log(self):
        try:
            QMessageBox.information(self, "Log", log_path())
        except Exception:
            pass

    def _retry(self):
        if self._last_retry is None:
            return
        try:
            self._last_retry()
        except Exception as e:
            log_exc(e, module="ResultView._retry")


__all__ = [
    "_clear_layout",
    "friendly_error",
    "run_async",
    "mark_field_error",
    "clear_field_error",
    "InlinePreviewBar",
    "CollapsibleGroup",
    "ResultView",
]