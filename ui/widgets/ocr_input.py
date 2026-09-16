"""截图 / 图片 → 表达式。

支持：打开文件 / Ctrl+V 粘贴 / 拖放。识别在 QThread 中执行。
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import QPixmap, QImage, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QComboBox, QFileDialog, QMessageBox, QApplication, QScrollArea,
    QWidget,
)

from core import visual_input
from core import secrets as sec_mod
from core.logger import log_exc


class _RecognizeWorker(QThread):
    done = Signal(dict)
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


class OCRInputDialog(QDialog):
    expression_ready = Signal(str)

    def __init__(self, i18n, parent=None):
        super().__init__(parent)
        self.i18n = i18n
        self.setWindowTitle(i18n.t("ocr_title", "截图 / 图片识别"))
        self.resize(720, 560)
        self.setAcceptDrops(True)

        self.expression = ""
        self._image_bytes: bytes = b""
        self._worker: _RecognizeWorker | None = None

        # 图片预览
        self.preview = QLabel()
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumHeight(280)
        self.preview.setStyleSheet(
            "background: #fafafa; border: 1px dashed #888; border-radius: 4px;")
        self.preview.setText(i18n.t(
            "ocr_drop_hint",
            "点击「打开图片」、Ctrl+V 粘贴，或把图片拖到这里"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        wrapper = QWidget()
        wv = QVBoxLayout(wrapper)
        wv.addWidget(self.preview)
        scroll.setWidget(wrapper)

        b_open = QPushButton(i18n.t("open_image", "打开图片"))
        b_open.clicked.connect(self._open_file)
        b_paste = QPushButton(i18n.t("paste_image", "粘贴 (Ctrl+V)"))
        b_paste.clicked.connect(self._paste)
        b_clear = QPushButton(i18n.t("clear", "清空"))
        b_clear.clicked.connect(self._clear)

        self.provider_box = QComboBox()
        self._populate_providers()
        self.b_recognize = QPushButton(i18n.t("recognize", "识别"))
        self.b_recognize.clicked.connect(self._recognize)

        tools = QHBoxLayout()
        tools.addWidget(b_open)
        tools.addWidget(b_paste)
        tools.addWidget(b_clear)
        tools.addStretch(1)
        tools.addWidget(QLabel(i18n.t("backend", "识别后端")))
        tools.addWidget(self.provider_box)
        tools.addWidget(self.b_recognize)

        self.expr_edit = QLineEdit()
        self.expr_edit.setPlaceholderText(
            i18n.t("ocr_expr_hint",
                   "识别结果会出现在这里；也可直接手动输入"))
        self.expr_edit.returnPressed.connect(self._accept_expr)

        self.status = QLabel("")
        self.status.setStyleSheet("color: #888;")
        self.status.setWordWrap(True)

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
        main.addWidget(scroll, 1)
        main.addLayout(tools)
        main.addWidget(QLabel(i18n.t("expr", "表达式")))
        main.addWidget(self.expr_edit)
        main.addWidget(self.status)
        main.addLayout(bottom)

        sc = QShortcut(QKeySequence("Ctrl+V"), self)
        sc.activated.connect(self._paste)

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
                    self.provider_box.model().item(idx).setEnabled(False)
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

    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------

    def _open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Image", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.gif *.webp);;All Files (*)")
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
                    "no_image_in_clipboard", "剪贴板里没有图片"))
                return
            self._set_image_from_qimage(img)
        except Exception as e:
            log_exc(e, module="OCRInputDialog._paste")

    def _set_image_from_qimage(self, img: QImage):
        try:
            from PySide6.QtCore import QBuffer, QIODevice
            buf = QBuffer()
            buf.open(QIODevice.WriteOnly)
            img.save(buf, "PNG")
            self._image_bytes = bytes(buf.data())
            pm = QPixmap.fromImage(img)
            self.preview.setPixmap(
                pm.scaled(600, 360, Qt.KeepAspectRatio,
                          Qt.SmoothTransformation))
            self.status.setText(self.i18n.t("image_loaded", "已加载图片"))
        except Exception as e:
            log_exc(e, module="OCRInputDialog._set_image_from_qimage")

    def _clear(self):
        self._image_bytes = b""
        self.preview.setPixmap(QPixmap())
        self.preview.setText(self.i18n.t(
            "ocr_drop_hint",
            "点击「打开图片」、Ctrl+V 粘贴，或把图片拖到这里"))
        self.expr_edit.clear()
        self.status.setText("")

    # ------------------------------------------------------------------

    def _recognize(self):
        if self._worker is not None and self._worker.isRunning():
            self.status.setText(self.i18n.t(
                "recognize_busy", "识别进行中，请稍候…"))
            return

        if not self._image_bytes:
            self.status.setText(self.i18n.t("no_image", "请先加载图片"))
            return

        provider = self.provider_box.currentData() or "manual"
        if provider == "manual":
            self.expr_edit.setFocus()
            self.status.setText(self.i18n.t(
                "manual_hint", "请直接手动输入表达式"))
            return

        try:
            api_key = sec_mod.get("ai_api_key", "") or ""
        except Exception:
            api_key = ""

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

        if provider == "pix2tex":
            self.status.setText(self.i18n.t(
                "recognize_loading_pix2tex",
                "正在识别（首次使用 pix2tex 需加载模型，可能 30–60 秒）…"))
        else:
            self.status.setText(self.i18n.t("running", "识别中…"))

        self.b_recognize.setEnabled(False)
        QApplication.setOverrideCursor(Qt.BusyCursor)

        try:
            worker = _RecognizeWorker(self._image_bytes, provider, api_key,
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
                self.status.setText(f"✗ {err or '未识别到表达式'}")
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