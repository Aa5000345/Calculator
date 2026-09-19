"""工具类 widget：手写 / OCR / 绘图动画。

合并自：ui/widgets/handwriting.py + ui/widgets/ocr_input.py
        + ui/widgets/plot_animation_widget.py

对外接口：
    HandwritingDialog   手写输入对话框
    OCRInputDialog      截图 / 图片识别对话框
    PolarAnimationWidget 极坐标动画组件
"""
from __future__ import annotations

from PySide6.QtCore import (
    Qt, QBuffer, QIODevice, QThread, Signal,
)
from PySide6.QtGui import (
    QImage, QPainter, QPen, QColor, QPixmap,
    QKeySequence, QShortcut,
)
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QFileDialog,
    QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPlainTextEdit, QPushButton, QScrollArea, QSizePolicy,
    QSpinBox, QVBoxLayout, QWidget,
)

from core import ai as _ai
from core import plot as _plot
from core.base import log_exc, secret_get


__all__ = [
    "HandwritingDialog",
    "OCRInputDialog",
    "PolarAnimationWidget",
]


# ===========================================================================
# 识别 Worker（手写 / OCR 共用）
# ===========================================================================

class _RecognizeWorker(QThread):
    done = Signal(dict)
    failed = Signal(str)

    def __init__(self, image_bytes: bytes, provider: str,
                 api_key: str, parent=None):
        super().__init__(parent)
        self._image_bytes = image_bytes
        self._provider = provider
        self._api_key = api_key
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def is_cancelled(self) -> bool:
        return self._cancelled

    def run(self):
        try:
            if self._cancelled:
                return
            r = _ai.recognize_image(
                self._image_bytes,
                provider=self._provider,
                api_key=self._api_key,
            )
            if self._cancelled:
                return
            self.done.emit(r if isinstance(r, dict) else {})
        except Exception as e:  # noqa: BLE001
            if not self._cancelled:
                self.failed.emit(str(e))


# ===========================================================================
# 手写输入
# ===========================================================================

class _HandwritingCanvas(QWidget):
    """鼠标 / 触摸笔画捕获。"""

    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(560, 260)
        self.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setStyleSheet(
            "background: #ffffff; border: 1px solid #888;"
            "border-radius: 4px;")
        self.setAttribute(Qt.WA_StaticContents, True)
        self.setCursor(Qt.CrossCursor)

        self._strokes: list = []
        self._cur: list = []
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
        img = QImage(self.width(), self.height(),
                     QImage.Format_RGB32)
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


class HandwritingDialog(QDialog):
    """手写输入对话框。"""

    expression_ready = Signal(str)

    def __init__(self, i18n, parent=None):
        super().__init__(parent)
        self.i18n = i18n
        self.setWindowTitle(i18n.t(
            "handwriting_title", "手写输入"))
        self.resize(700, 520)
        self.expression = ""

        self._worker: _RecognizeWorker | None = None

        # ---------------- 画板 ----------------
        self.canvas = _HandwritingCanvas(self)

        # ---------------- 工具行 ----------------
        b_undo = QPushButton(i18n.t("undo", "撤销"))
        b_clear = QPushButton(i18n.t("clear", "清空"))
        b_export = QPushButton(
            i18n.t("export_png", "导出 PNG"))
        b_undo.clicked.connect(self.canvas.undo)
        b_clear.clicked.connect(self.canvas.clear)
        b_export.clicked.connect(self._export_png)

        # ---------------- 识别后端 ----------------
        self.provider_box = QComboBox()
        self._populate_providers()

        self.b_recognize = QPushButton(
            i18n.t("recognize", "识别"))
        self.b_recognize.clicked.connect(self._recognize)

        tools = QHBoxLayout()
        tools.addWidget(b_undo)
        tools.addWidget(b_clear)
        tools.addWidget(b_export)
        tools.addStretch(1)
        tools.addWidget(QLabel(
            i18n.t("backend", "识别后端")))
        tools.addWidget(self.provider_box)
        tools.addWidget(self.b_recognize)

        # ---------------- 表达式输入 ----------------
        self.expr_edit = QLineEdit()
        self.expr_edit.setPlaceholderText(i18n.t(
            "handwriting_hint",
            "识别结果会出现在这里；也可直接手动输入"))
        self.expr_edit.returnPressed.connect(self._accept_expr)

        # ---------------- 状态 ----------------
        self.status = QLabel("")
        self.status.setStyleSheet("color: #888;")
        self.status.setWordWrap(True)

        # ---------------- 底部按钮 ----------------
        b_insert = QPushButton(
            i18n.t("insert_to_input", "插入到当前输入框"))
        b_insert.setDefault(True)
        b_insert.clicked.connect(self._accept_expr)
        b_cancel = QPushButton(i18n.t("cancel", "取消"))
        b_cancel.clicked.connect(self.reject)

        bottom = QHBoxLayout()
        bottom.addStretch(1)
        bottom.addWidget(b_cancel)
        bottom.addWidget(b_insert)

        # ---------------- 主布局 ----------------
        main = QVBoxLayout(self)
        main.addWidget(QLabel(i18n.t(
            "handwriting_prompt",
            "用鼠标 / 触控笔书写公式，或直接点「识别」。")))
        main.addWidget(self.canvas, 1)
        main.addLayout(tools)
        main.addWidget(QLabel(i18n.t("expr", "表达式")))
        main.addWidget(self.expr_edit)
        main.addWidget(self.status)
        main.addLayout(bottom)

    # ==================================================================

    def _populate_providers(self):
        try:
            api_key = secret_get("ai_api_key", "") or ""
        except Exception:
            api_key = ""
        self.provider_box.clear()
        for r in _ai.list_recognizers(api_key=api_key):
            label = r["label"] + (
                "" if r["available"]
                else f"（{r['hint']}）")
            self.provider_box.addItem(label, r["name"])
            idx = self.provider_box.count() - 1
            if not r["available"]:
                try:
                    item = self.provider_box.model().item(idx)
                    item.setEnabled(False)
                except Exception:
                    pass
        for i in range(self.provider_box.count()):
            try:
                it = self.provider_box.model().item(i)
                if it is not None and it.isEnabled():
                    self.provider_box.setCurrentIndex(i)
                    break
            except Exception:
                break

    # ==================================================================

    def _export_png(self):
        if self.canvas.is_empty():
            self.status.setText(
                self.i18n.t("canvas_empty", "画板为空"))
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export PNG", "handwriting.png",
            "PNG (*.png)")
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

    # ==================================================================
    # 识别
    # ==================================================================

    def _recognize(self):
        if (self._worker is not None
                and self._worker.isRunning()):
            self.status.setText(self.i18n.t(
                "recognize_busy", "识别进行中，请稍候…"))
            return

        if self.canvas.is_empty():
            self.status.setText(
                self.i18n.t("canvas_empty", "画板为空"))
            return

        provider = self.provider_box.currentData() or "manual"

        if provider == "manual":
            self.expr_edit.setFocus()
            self.status.setText(self.i18n.t(
                "manual_hint", "请直接手动输入表达式"))
            return

        try:
            api_key = secret_get("ai_api_key", "") or ""
        except Exception:
            api_key = ""

        try:
            infos = {
                r["name"]: r
                for r in _ai.list_recognizers(api_key=api_key)
            }
            info = infos.get(provider)
            if info is not None and not info.get("available"):
                self.status.setText(
                    f"✗ {info.get('label', provider)} "
                    f"不可用：{info.get('hint', '')}")
                return
        except Exception:
            pass

        if provider == "pix2tex":
            self.status.setText(self.i18n.t(
                "recognize_loading_pix2tex",
                "正在识别（首次使用 pix2tex 需加载模型，"
                "可能 30–60 秒）…"))
        else:
            self.status.setText(
                self.i18n.t("running", "识别中…"))

        self.b_recognize.setEnabled(False)
        QApplication.setOverrideCursor(Qt.BusyCursor)

        try:
            img = self.canvas.to_png_bytes()
            worker = _RecognizeWorker(
                img, provider, api_key, parent=self)
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
            log_exc(
                e, module="HandwritingDialog._on_recognize_done")

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

    # ==================================================================

    def _accept_expr(self):
        text = self.expr_edit.text().strip()
        if not text:
            self.status.setText(self.i18n.t(
                "expr_required", "请先输入或识别表达式"))
            self.expr_edit.setFocus()
            return
        self.expression = text
        try:
            self.expression_ready.emit(text)
        except Exception:
            pass
        self.accept()

    # ==================================================================

    def closeEvent(self, e):
        try:
            w = self._worker
            if w is not None and w.isRunning():
                w.cancel()
                w.wait(3000)
        except Exception:
            pass
        try:
            self._restore_cursor_and_button()
        except Exception:
            pass
        super().closeEvent(e)


# ===========================================================================
# 截图 / 图片识别
# ===========================================================================

class OCRInputDialog(QDialog):
    """截图 / 图片 → 表达式。支持打开文件 / Ctrl+V / 拖放。"""

    expression_ready = Signal(str)

    def __init__(self, i18n, parent=None):
        super().__init__(parent)
        self.i18n = i18n
        self.setWindowTitle(i18n.t(
            "ocr_title", "截图 / 图片识别"))
        self.resize(720, 560)
        self.setAcceptDrops(True)

        self.expression = ""
        self._image_bytes: bytes = b""
        self._worker: _RecognizeWorker | None = None

        # ---------------- 图片预览 ----------------
        self.preview = QLabel()
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumHeight(280)
        self.preview.setStyleSheet(
            "background: #fafafa;"
            "border: 1px dashed #888;"
            "border-radius: 4px;")
        self.preview.setText(i18n.t(
            "ocr_drop_hint",
            "点击「打开图片」、Ctrl+V 粘贴，或把图片拖到这里"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        wrapper = QWidget()
        wv = QVBoxLayout(wrapper)
        wv.addWidget(self.preview)
        scroll.setWidget(wrapper)

        # ---------------- 工具按钮 ----------------
        b_open = QPushButton(
            i18n.t("open_image", "打开图片"))
        b_open.clicked.connect(self._open_file)
        b_paste = QPushButton(
            i18n.t("paste_image", "粘贴 (Ctrl+V)"))
        b_paste.clicked.connect(self._paste)
        b_clear = QPushButton(i18n.t("clear", "清空"))
        b_clear.clicked.connect(self._clear)

        self.provider_box = QComboBox()
        self._populate_providers()
        self.b_recognize = QPushButton(
            i18n.t("recognize", "识别"))
        self.b_recognize.clicked.connect(self._recognize)

        tools = QHBoxLayout()
        tools.addWidget(b_open)
        tools.addWidget(b_paste)
        tools.addWidget(b_clear)
        tools.addStretch(1)
        tools.addWidget(QLabel(
            i18n.t("backend", "识别后端")))
        tools.addWidget(self.provider_box)
        tools.addWidget(self.b_recognize)

        # ---------------- 表达式输入 ----------------
        self.expr_edit = QLineEdit()
        self.expr_edit.setPlaceholderText(i18n.t(
            "ocr_expr_hint",
            "识别结果会出现在这里；也可直接手动输入"))
        self.expr_edit.returnPressed.connect(self._accept_expr)

        # ---------------- 状态 ----------------
        self.status = QLabel("")
        self.status.setStyleSheet("color: #888;")
        self.status.setWordWrap(True)

        # ---------------- 底部按钮 ----------------
        b_insert = QPushButton(
            i18n.t("insert_to_input", "插入到当前输入框"))
        b_insert.setDefault(True)
        b_insert.clicked.connect(self._accept_expr)
        b_cancel = QPushButton(i18n.t("cancel", "取消"))
        b_cancel.clicked.connect(self.reject)

        bottom = QHBoxLayout()
        bottom.addStretch(1)
        bottom.addWidget(b_cancel)
        bottom.addWidget(b_insert)

        # ---------------- 主布局 ----------------
        main = QVBoxLayout(self)
        main.addWidget(scroll, 1)
        main.addLayout(tools)
        main.addWidget(QLabel(i18n.t("expr", "表达式")))
        main.addWidget(self.expr_edit)
        main.addWidget(self.status)
        main.addLayout(bottom)

        sc = QShortcut(QKeySequence("Ctrl+V"), self)
        sc.activated.connect(self._paste)

    # ==================================================================

    def _populate_providers(self):
        try:
            api_key = secret_get("ai_api_key", "") or ""
        except Exception:
            api_key = ""
        self.provider_box.clear()
        for r in _ai.list_recognizers(api_key=api_key):
            label = r["label"] + (
                "" if r["available"]
                else f"（{r['hint']}）")
            self.provider_box.addItem(label, r["name"])
            idx = self.provider_box.count() - 1
            if not r["available"]:
                try:
                    self.provider_box.model().item(
                        idx).setEnabled(False)
                except Exception:
                    pass
        for i in range(self.provider_box.count()):
            try:
                it = self.provider_box.model().item(i)
                if it is not None and it.isEnabled():
                    self.provider_box.setCurrentIndex(i)
                    break
            except Exception:
                break

    # ==================================================================
    # 拖放
    # ==================================================================

    def dragEnterEvent(self, e):
        md = e.mimeData()
        if md.hasUrls() or md.hasImage():
            e.acceptProposedAction()

    def dropEvent(self, e):
        try:
            md = e.mimeData()
            if md.hasUrls():
                for url in md.urls():
                    path = url.toLocalFile()
                    if path:
                        self._load_file(path)
                        return
            elif md.hasImage():
                img = md.imageData()
                if isinstance(img, QImage):
                    self._set_image_from_qimage(img)
        except Exception as ex:
            log_exc(ex, module="OCRInputDialog.dropEvent")

    # ==================================================================

    def _open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Image", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.gif *.webp);;"
            "All Files (*)")
        if not path:
            return
        self._load_file(path)

    def _load_file(self, path: str):
        try:
            with open(path, "rb") as f:
                data = f.read()
            pm = QPixmap()
            if not pm.loadFromData(data):
                raise ValueError("无法加载图片")
            self._image_bytes = data
            self.preview.setPixmap(
                pm.scaled(600, 360, Qt.KeepAspectRatio,
                          Qt.SmoothTransformation))
            self.status.setText(path)
        except Exception as e:
            log_exc(e, module="OCRInputDialog._load_file")
            QMessageBox.warning(self, "Error", str(e))

    def _paste(self):
        try:
            cb = QApplication.clipboard()
            img: QImage = cb.image()
            if img is None or img.isNull():
                self.status.setText(self.i18n.t(
                    "no_image_in_clipboard",
                    "剪贴板里没有图片"))
                return
            self._set_image_from_qimage(img)
        except Exception as e:
            log_exc(e, module="OCRInputDialog._paste")

    def _set_image_from_qimage(self, img: QImage):
        try:
            buf = QBuffer()
            buf.open(QIODevice.WriteOnly)
            img.save(buf, "PNG")
            self._image_bytes = bytes(buf.data())
            pm = QPixmap.fromImage(img)
            self.preview.setPixmap(
                pm.scaled(600, 360, Qt.KeepAspectRatio,
                          Qt.SmoothTransformation))
            self.status.setText(
                self.i18n.t("image_loaded", "已加载图片"))
        except Exception as e:
            log_exc(
                e, module="OCRInputDialog._set_image_from_qimage")

    def _clear(self):
        self._image_bytes = b""
        self.preview.setPixmap(QPixmap())
        self.preview.setText(self.i18n.t(
            "ocr_drop_hint",
            "点击「打开图片」、Ctrl+V 粘贴，"
            "或把图片拖到这里"))
        self.expr_edit.clear()
        self.status.setText("")

    # ==================================================================
    # 识别
    # ==================================================================

    def _recognize(self):
        if (self._worker is not None
                and self._worker.isRunning()):
            self.status.setText(self.i18n.t(
                "recognize_busy", "识别进行中，请稍候…"))
            return

        if not self._image_bytes:
            self.status.setText(
                self.i18n.t("no_image", "请先加载图片"))
            return

        provider = self.provider_box.currentData() or "manual"
        if provider == "manual":
            self.expr_edit.setFocus()
            self.status.setText(self.i18n.t(
                "manual_hint", "请直接手动输入表达式"))
            return

        try:
            api_key = secret_get("ai_api_key", "") or ""
        except Exception:
            api_key = ""

        try:
            infos = {
                r["name"]: r
                for r in _ai.list_recognizers(api_key=api_key)
            }
            info = infos.get(provider)
            if info is not None and not info.get("available"):
                self.status.setText(
                    f"✗ {info.get('label', provider)} "
                    f"不可用：{info.get('hint', '')}")
                return
        except Exception:
            pass

        if provider == "pix2tex":
            self.status.setText(self.i18n.t(
                "recognize_loading_pix2tex",
                "正在识别（首次使用 pix2tex 需加载模型，"
                "可能 30–60 秒）…"))
        else:
            self.status.setText(
                self.i18n.t("running", "识别中…"))

        self.b_recognize.setEnabled(False)
        QApplication.setOverrideCursor(Qt.BusyCursor)

        try:
            worker = _RecognizeWorker(
                self._image_bytes, provider, api_key,
                parent=self)
            worker.done.connect(self._on_recognize_done)
            worker.failed.connect(self._on_recognize_failed)
            worker.finished.connect(self._on_worker_finished)
            self._worker = worker
            worker.start()
        except Exception as e:
            self._restore_cursor_and_button()
            log_exc(e, module="OCRInputDialog._recognize")
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
            log_exc(e, module="OCRInputDialog._on_recognize_done")

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

    # ==================================================================

    def _accept_expr(self):
        text = self.expr_edit.text().strip()
        if not text:
            self.status.setText(self.i18n.t(
                "expr_required", "请先输入或识别表达式"))
            self.expr_edit.setFocus()
            return
        self.expression = text
        try:
            self.expression_ready.emit(text)
        except Exception:
            pass
        self.accept()

    # ==================================================================

    def closeEvent(self, e):
        try:
            w = self._worker
            if w is not None and w.isRunning():
                w.cancel()
                w.wait(3000)
        except Exception:
            pass
        try:
            self._restore_cursor_and_button()
        except Exception:
            pass
        super().closeEvent(e)


# ===========================================================================
# 极坐标动画 + GIF 导出
# ===========================================================================

class _GifWorker(QThread):
    done = Signal(str)
    failed = Signal(str)

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            path = self._fn(*self._args, **self._kwargs)
            if not self._cancelled:
                self.done.emit(str(path))
        except Exception as e:  # noqa: BLE001
            if not self._cancelled:
                self.failed.emit(str(e))


class PolarAnimationWidget(QWidget):
    """极坐标动画 + GIF 导出。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker: _GifWorker | None = None

        self.expr = QLineEdit("1 + 0.5*cos(6*theta)")
        self.tmin = QLineEdit("0")
        self.tmax = QLineEdit("6.283185307")
        self.frames = QSpinBox()
        self.frames.setRange(2, 600)
        self.frames.setValue(60)
        self.fps = QSpinBox()
        self.fps.setRange(1, 60)
        self.fps.setValue(20)
        self.points = QSpinBox()
        self.points.setRange(50, 2000)
        self.points.setValue(400)

        self.animate_time = QCheckBox(
            "让 `t` 随时间变化（表达式里可用 t）")
        self.line_color = QLineEdit("#007acc")
        self.bg_color = QLineEdit("#1e1e1e")
        self.fg_color = QLineEdit("#ffffff")

        b_preview = QPushButton("预览 GIF（保存后查看）")
        b_preview.clicked.connect(self._export)
        b_stop = QPushButton("取消")
        b_stop.setEnabled(False)
        b_stop.clicked.connect(self._cancel)
        self._stop_btn = b_stop

        self.status = QLabel("")
        self.status.setStyleSheet("color: #888;")

        f = QFormLayout()
        f.addRow(QLabel("极坐标 r(theta)"), self.expr)
        f.addRow(QLabel("theta min"), self.tmin)
        f.addRow(QLabel("theta max"), self.tmax)
        f.addRow(QLabel("帧数"), self.frames)
        f.addRow(QLabel("FPS"), self.fps)
        f.addRow(QLabel("采样点数"), self.points)
        f.addRow(QLabel(""), self.animate_time)
        f.addRow(QLabel("线条颜色"), self.line_color)
        f.addRow(QLabel("背景色"), self.bg_color)
        f.addRow(QLabel("前景色"), self.fg_color)

        row = QHBoxLayout()
        row.addWidget(b_preview, 1)
        row.addWidget(b_stop)

        lay = QVBoxLayout(self)
        lay.addLayout(f)
        lay.addLayout(row)
        lay.addWidget(self.status)
        lay.addStretch(1)

    def _export(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "保存 GIF", "polar.gif", "GIF (*.gif)")
        if not path:
            return
        if self._worker is not None and self._worker.isRunning():
            return

        self._stop_btn.setEnabled(True)
        self.status.setText("正在渲染…")

        try:
            tmin = float(self.tmin.text())
            tmax = float(self.tmax.text())
        except ValueError:
            QMessageBox.warning(self, "Error", "theta 范围非法")
            self._stop_btn.setEnabled(False)
            return

        self._worker = _GifWorker(
            _plot.save_polar_gif,
            self.expr.text(),
            path,
            tmin=tmin, tmax=tmax,
            frames=self.frames.value(),
            points=self.points.value(),
            fps=self.fps.value(),
            animate_time=self.animate_time.isChecked(),
            line_color=self.line_color.text().strip() or "#007acc",
            bg_color=self.bg_color.text().strip() or "#1e1e1e",
            fg_color=self.fg_color.text().strip() or "#ffffff",
        )
        self._worker.done.connect(self._on_done)
        self._worker.failed.connect(self._on_failed)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_done(self, path: str):
        self.status.setText(f"✓ {path}")
        QMessageBox.information(self, "OK", path)

    def _on_failed(self, msg: str):
        self.status.setText(f"✗ {msg}")
        QMessageBox.warning(self, "Error", msg)

    def _on_finished(self):
        self._stop_btn.setEnabled(False)
        self._worker = None

    def _cancel(self):
        if self._worker is not None:
            self._worker.cancel()

    def closeEvent(self, e):
        try:
            if self._worker is not None and self._worker.isRunning():
                self._worker.cancel()
                self._worker.wait(2000)
        except Exception:
            pass
        super().closeEvent(e)