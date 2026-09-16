"""手写公式画板：捕获笔画 → 可选识别 → 插入到当前输入框。

识别后端由 core.visual_input 提供；未安装时退化为手动输入。
识别过程在 QThread 中执行，避免首次加载 pix2tex 时 UI 冻结。
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QBuffer, QIODevice, Signal, QThread
from PySide6.QtGui import (
    QPainter, QPen, QColor, QImage, QPixmap,
)
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QWidget, QFileDialog, QMessageBox, QComboBox, QSizePolicy,
    QApplication,
)

from core import visual_input
from core import secrets as sec_mod
from core.logger import log_exc


# =====================================================================
# 识别 Worker
# =====================================================================

class _RecognizeWorker(QThread):
    done = Signal(dict)          # visual_input.recognize_image 的返回 dict
    failed = Signal(str)

    def __init__(self, image_bytes: bytes, provider: str, api_key: str,
                 parent=None):
        super().__init__(parent)
        self._image_bytes = image_bytes
        self._provider = provider
        self._api_key = api_key

    def run(self):
        try:
            r = visual_input.recognize_image(
                self._image_bytes,
                provider=self._provider,
                api_key=self._api_key,
            )
            self.done.emit(r if isinstance(r, dict) else {})
        except Exception as e:  # noqa: BLE001
            self.failed.emit(str(e))


# =====================================================================
# 画板
# =====================================================================

class _Canvas(QWidget):
    """鼠标 / 触摸笔画捕获。"""

    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(560, 260)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setStyleSheet(
            "background: #ffffff; border: 1px solid #888; border-radius: 4px;")
        self.setAttribute(Qt.WA_StaticContents, True)
        self.setCursor(Qt.CrossCursor)

        self._strokes: list[list[tuple[int, int]]] = []
        self._cur: list[tuple[int, int]] = []
        self._pen_width = 3

    # ------------------------------------------------------------------

    def clear(self):
        self._strokes.clear()
        self._cur.clear()
        self.update()
        self.changed.emit()

    def undo(self):
        if self._strokes:
            self._strokes.pop()
            self.update()
            self.changed.emit()

    def is_empty(self) -> bool:
        return not self._strokes and not self._cur

    # ------------------------------------------------------------------

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            p = e.position().toPoint()
            self._cur = [(p.x(), p.y())]
            self.update()
            e.accept()

    def mouseMoveEvent(self, e):
        if e.buttons() & Qt.LeftButton and self._cur is not None:
            p = e.position().toPoint()
            self._cur.append((p.x(), p.y()))
            self.update()
            e.accept()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            if self._cur:
                self._strokes.append(list(self._cur))
                self._cur = []
            self.update()
            self.changed.emit()
            e.accept()

    # ------------------------------------------------------------------

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.fillRect(self.rect(), QColor("#ffffff"))
        pen = QPen(QColor("#000000"), self._pen_width)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen)

        all_strokes = list(self._strokes)
        if self._cur:
            all_strokes.append(self._cur)
        for stroke in all_strokes:
            if len(stroke) == 1:
                p.drawPoint(stroke[0][0], stroke[0][1])
                continue
            for i in range(1, len(stroke)):
                p.drawLine(stroke[i - 1][0], stroke[i - 1][1],
                           stroke[i][0], stroke[i][1])
        p.end()

    # ------------------------------------------------------------------

    def to_png_bytes(self) -> bytes:
        img = QImage(self.width(), self.height(), QImage.Format_RGB32)
        img.fill(QColor("#ffffff"))
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing, True)
        pen = QPen(QColor("#000000"), self._pen_width)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen)
        for stroke in self._strokes:
            if len(stroke) == 1:
                p.drawPoint(stroke[0][0], stroke[0][1])
                continue
            for i in range(1, len(stroke)):
                p.drawLine(stroke[i - 1][0], stroke[i - 1][1],
                           stroke[i][0], stroke[i][1])
        p.end()

        buf = QBuffer()
        buf.open(QIODevice.WriteOnly)
        img.save(buf, "PNG")
        return bytes(buf.data())


# =====================================================================
# 对话框
# =====================================================================

class HandwritingDialog(QDialog):
    """手写输入对话框。

    使用：
        dlg = HandwritingDialog(i18n, parent)
        dlg.expression_ready.connect(on_ready)
        dlg.exec()
    """

    expression_ready = Signal(str)

    def __init__(self, i18n, parent=None):
        super().__init__(parent)
        self.i18n = i18n
        self.setWindowTitle(i18n.t("handwriting_title", "手写输入"))
        self.resize(700, 520)
        self.expression = ""

        self._worker: _RecognizeWorker | None = None

        # 画板
        self.canvas = _Canvas(self)

        # 工具行
        b_undo = QPushButton(i18n.t("undo", "撤销"))
        b_clear = QPushButton(i18n.t("clear", "清空"))
        b_export = QPushButton(i18n.t("export_png", "导出 PNG"))
        b_undo.clicked.connect(self.canvas.undo)
        b_clear.clicked.connect(self.canvas.clear)
        b_export.clicked.connect(self._export_png)

        # 识别后端
        self.provider_box = QComboBox()
        self._populate_providers()

        self.b_recognize = QPushButton(i18n.t("recognize", "识别"))
        self.b_recognize.clicked.connect(self._recognize)

        tools = QHBoxLayout()
        tools.addWidget(b_undo)
        tools.addWidget(b_clear)
        tools.addWidget(b_export)
        tools.addStretch(1)
        tools.addWidget(QLabel(i18n.t("backend", "识别后端")))
        tools.addWidget(self.provider_box)
        tools.addWidget(self.b_recognize)

        # 表达式输入
        self.expr_edit = QLineEdit()
        self.expr_edit.setPlaceholderText(
            i18n.t("handwriting_hint",
                   "识别结果会出现在这里；也可直接手动输入"))
        self.expr_edit.returnPressed.connect(self._accept_expr)

        # 状态
        self.status = QLabel("")
        self.status.setStyleSheet("color: #888;")
        self.status.setWordWrap(True)

        # 底部按钮
        b_insert = QPushButton(i18n.t("insert_to_input", "插入到当前输入框"))
        b_insert.setDefault(True)
        b_insert.clicked.connect(self._accept_expr)
        b_cancel = QPushButton(i18n.t("cancel", "取消"))
        b_cancel.clicked.connect(self.reject)

        bottom = QHBoxLayout()
        bottom.addStretch(1)
        bottom.addWidget(b_cancel)
        bottom.addWidget(b_insert)

        main = QVBoxLayout(self)
        main.addWidget(QLabel(
            i18n.t("handwriting_prompt",
                   "用鼠标 / 触控笔书写公式，或直接点「识别」。")))
        main.addWidget(self.canvas, 1)
        main.addLayout(tools)
        main.addWidget(QLabel(i18n.t("expr", "表达式")))
        main.addWidget(self.expr_edit)
        main.addWidget(self.status)
        main.addLayout(bottom)

    # ------------------------------------------------------------------

    def _populate_providers(self):
        try:
            api_key = sec_mod.get("ai_api_key", "") or ""
        except Exception:
            api_key = ""
        self.provider_box.clear()
        for r in visual_input.list_recognizers(api_key=api_key):
            label = r["label"] + ("" if r["available"] else f"（{r['hint']}）")
            self.provider_box.addItem(label, r["name"])
            idx = self.provider_box.count() - 1
            if not r["available"]:
                try:
                    item = self.provider_box.model().item(idx)
                    item.setEnabled(False)
                except Exception:
                    pass
        # 默认选第一个可用的
        for i in range(self.provider_box.count()):
            try:
                it = self.provider_box.model().item(i)
                if it is not None and it.isEnabled():
                    self.provider_box.setCurrentIndex(i)
                    break
            except Exception:
                break

    # ------------------------------------------------------------------

    def _export_png(self):
        if self.canvas.is_empty():
            self.status.setText(self.i18n.t("canvas_empty", "画板为空"))
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export PNG", "handwriting.png", "PNG (*.png)")
        if not path:
            return
        try:
            data = self.canvas.to_png_bytes()
            with open(path, "wb") as f:
                f.write(data)
            self.status.setText(path)
        except Exception as e:
            log_exc(e, module="HandwritingDialog._export_png")
            QMessageBox.warning(self, "Error", str(e))

    # ------------------------------------------------------------------
    # 识别（异步）
    # ------------------------------------------------------------------

    def _recognize(self):
        if self._worker is not None and self._worker.isRunning():
            self.status.setText(self.i18n.t(
                "recognize_busy", "识别进行中，请稍候…"))
            return

        if self.canvas.is_empty():
            self.status.setText(self.i18n.t("canvas_empty", "画板为空"))
            return

        provider = self.provider_box.currentData() or "manual"

        # 手动模式：不调用 OCR
        if provider == "manual":
            self.expr_edit.setFocus()
            self.status.setText(self.i18n.t(
                "manual_hint", "请直接手动输入表达式"))
            return

        try:
            api_key = sec_mod.get("ai_api_key", "") or ""
        except Exception:
            api_key = ""

        # 检查所选后端是否可用；不可用就直接提示
        try:
            infos = {r["name"]: r for r in
                     visual_input.list_recognizers(api_key=api_key)}
            info = infos.get(provider)
            if info is not None and not info.get("available"):
                self.status.setText(
                    f"✗ {info.get('label', provider)} "
                    f"不可用：{info.get('hint', '')}")
                return
        except Exception:
            pass

        # 提示阶段（首次加载 pix2tex 需要 30–60s）
        if provider == "pix2tex":
            self.status.setText(self.i18n.t(
                "recognize_loading_pix2tex",
                "正在识别（首次使用 pix2tex 需加载模型，可能 30–60 秒）…"))
        else:
            self.status.setText(self.i18n.t("running", "识别中…"))

        self.b_recognize.setEnabled(False)
        QApplication.setOverrideCursor(Qt.BusyCursor)

        try:
            img = self.canvas.to_png_bytes()
            worker = _RecognizeWorker(img, provider, api_key, parent=self)
            worker.done.connect(self._on_recognize_done)
            worker.failed.connect(self._on_recognize_failed)
            worker.finished.connect(self._on_worker_finished)
            self._worker = worker
            worker.start()
        except Exception as e:
            self._restore_cursor_and_button()
            log_exc(e, module="HandwritingDialog._recognize")
            self.status.setText(f"✗ {e}")

    def _on_recognize_done(self, r: dict):
        try:
            expr = (r or {}).get("expr") or ""
            provider = (r or {}).get("provider", "")
            err = (r or {}).get("error", "")
            if expr:
                self.expr_edit.setText(expr)
                self.status.setText(f"✓ provider={provider}")
            else:
                self.status.setText(
                    f"✗ {err or '未识别到表达式'}")
        except Exception as e:
            log_exc(e, module="HandwritingDialog._on_recognize_done")

    def _on_recognize_failed(self, msg: str):
        try:
            self.status.setText(f"✗ {msg}")
        except Exception:
            pass

    def _on_worker_finished(self):
        self._restore_cursor_and_button()
        self._worker = None

    def _restore_cursor_and_button(self):
        try:
            QApplication.restoreOverrideCursor()
        except Exception:
            pass
        try:
            self.b_recognize.setEnabled(True)
        except Exception:
            pass

    # ------------------------------------------------------------------

    def _accept_expr(self):
        text = self.expr_edit.text().strip()
        if not text:
            self.status.setText(
                self.i18n.t("expr_required", "请先输入或识别表达式"))
            self.expr_edit.setFocus()
            return
        self.expression = text
        try:
            self.expression_ready.emit(text)
        except Exception:
            pass
        self.accept()

    # ------------------------------------------------------------------

    def closeEvent(self, e):
        """关闭时等待 Worker 结束（避免线程销毁崩溃）。"""
        try:
            if self._worker is not None and self._worker.isRunning():
                self._worker.quit()
                self._worker.wait(3000)
        except Exception:
            pass
        try:
            self._restore_cursor_and_button()
        except Exception:
            pass
        super().closeEvent(e)