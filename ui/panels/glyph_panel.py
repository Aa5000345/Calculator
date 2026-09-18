"""字典面板：符号库。

变更历史：
- 第 7 轮：新增
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication, QLabel, QLineEdit, QPushButton, QVBoxLayout,
    QHBoxLayout, QComboBox, QScrollArea, QWidget, QGridLayout,
    QMenu,
)

from core import glyph_library as gl
from core.logger import log_exc
from .base import CalcPanel


# 每行列数
COLUMNS = 12


class _GlyphButton(QPushButton):
    """单个符号按钮。"""

    def __init__(self, glyph: gl.Glyph, parent=None):
        super().__init__(glyph.char, parent)
        self.glyph = glyph
        self.setFixedSize(40, 40)
        f = QFont()
        f.setPointSize(14)
        self.setFont(f)
        self.setToolTip(
            f"{glyph.name_zh} / {glyph.name_en}\n"
            f"LaTeX: {glyph.latex or '—'}")
        self.setFocusPolicy(Qt.NoFocus)


class GlyphPanel(CalcPanel):
    module_key = "glyph"

    def __init__(self, settings, i18n, history):
        super().__init__(settings, i18n, history)

        # ---------------- 顶部 ----------------
        self.search = QLineEdit()
        self.search.setPlaceholderText(
            i18n.t("glyph_search_hint",
                   "搜索符号（中文 / 英文 / LaTeX）…"))
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._on_search)

        self.cat_box = QComboBox()
        self.cat_box.addItem(
            i18n.t("glyph_all", "全部"), "__all__")
        self.cat_box.addItem(
            i18n.t("glyph_favorites", "收藏 ⭐"), "__fav__")
        for c in gl.categories():
            label = i18n.t(
                f"glyph_cat_{c.key}", c.label_zh)
            self.cat_box.addItem(f"{c.icon}  {label}", c.key)
        self.cat_box.currentIndexChanged.connect(
            lambda _: self._refresh())

        top = QHBoxLayout()
        top.addWidget(self.search, 1)
        top.addWidget(self.cat_box)
        top.addWidget(self.make_kb_button())

        # ---------------- 网格 ----------------
        self._grid_widget = QWidget()
        self._grid = QGridLayout(self._grid_widget)
        self._grid.setContentsMargins(8, 8, 8, 8)
        self._grid.setSpacing(4)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._grid_widget)

        # ---------------- 状态 ----------------
        self.status = QLabel("")
        self.status.setStyleSheet(
            "color: #888; padding: 2px 6px; font-size: 9pt;")
        self.status.setWordWrap(True)

        # ---------------- 布局 ----------------
        main = QVBoxLayout(self)
        main.addLayout(top)
        main.addWidget(scroll, 1)
        main.addWidget(self.status)

        self._refresh()

    # ==================================================================
    # 刷新
    # ==================================================================

    def _current_glyphs(self):
        cat = self.cat_box.currentData()
        query = self.search.text().strip()

        if query:
            return gl.search(query)
        if cat == "__fav__":
            favs = set(gl.favorites())
            return [g for g in gl.all_glyphs()
                    if g.char in favs]
        if cat == "__all__" or not cat:
            return gl.all_glyphs()
        return gl.by_category(cat)

    def _refresh(self):
        # 清空
        while self._grid.count():
            item = self._grid.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()

        glyphs = self._current_glyphs()
        for i, g in enumerate(glyphs):
            btn = _GlyphButton(g)
            btn.clicked.connect(
                lambda _=False, gg=g: self._on_click(gg))
            btn.setContextMenuPolicy(Qt.CustomContextMenu)
            btn.customContextMenuRequested.connect(
                lambda pos, gg=g, bb=btn:
                self._on_context_menu(pos, gg, bb))
            r, c = divmod(i, COLUMNS)
            self._grid.addWidget(btn, r, c)

        for c in range(COLUMNS):
            self._grid.setColumnStretch(c, 1)

        n = len(glyphs)
        self.status.setText(
            self.i18n.t("glyph_count", "共 {n} 个符号")
            .format(n=n))

    # ==================================================================
    # 交互
    # ==================================================================

    def _on_search(self, _):
        self._refresh()

    def _on_click(self, glyph: gl.Glyph):
        try:
            QApplication.clipboard().setText(glyph.char)
            self.status.setText(
                self.i18n.t(
                    "glyph_copied",
                    "已复制：{c}  {name}")
                .format(c=glyph.char, name=glyph.name_zh))
            try:
                from ui.toast import toast
                toast(self.window(),
                      f"{glyph.char}  {glyph.name_zh}",
                      level="success", duration=1200)
            except Exception:
                pass
        except Exception as e:
            log_exc(e, module="GlyphPanel._on_click")

    def _insert_to_target(self, glyph: gl.Glyph):
        try:
            from ui.widgets.focus_tracker import FocusTracker
            tracker = FocusTracker.instance()
            if tracker.insert_text(glyph.char):
                self.status.setText(
                    self.i18n.t(
                        "glyph_inserted", "已插入：{c}")
                    .format(c=glyph.char))
                return
        except Exception:
            pass
        QApplication.clipboard().setText(glyph.char)
        self.status.setText(
            self.i18n.t(
                "glyph_copied", "已复制：{c}  {name}")
            .format(c=glyph.char, name=glyph.name_zh))

    def _on_context_menu(self, pos, glyph: gl.Glyph, btn):
        menu = QMenu(self)

        a_copy = menu.addAction(
            self.i18n.t("glyph_menu_copy", "复制符号"))
        a_insert = menu.addAction(
            self.i18n.t("glyph_menu_insert",
                        "插入到焦点输入框"))
        a_copy_latex = menu.addAction(
            self.i18n.t("glyph_menu_copy_latex",
                        "复制 LaTeX"))
        a_copy_char = menu.addAction(
            self.i18n.t("glyph_menu_copy_char",
                        "复制 Unicode 字符"))
        menu.addSeparator()
        is_fav = gl.is_favorite(glyph.char)
        a_fav = menu.addAction(
            self.i18n.t("glyph_menu_unfav", "取消收藏")
            if is_fav
            else self.i18n.t("glyph_menu_fav", "加入收藏"))
        menu.addSeparator()
        a_info = menu.addAction(
            self.i18n.t("glyph_menu_info", "查看详情…"))

        chosen = menu.exec(btn.mapToGlobal(pos))
        if chosen is None:
            return

        try:
            if chosen is a_copy:
                QApplication.clipboard().setText(glyph.char)
                self.status.setText(
                    self.i18n.t(
                        "glyph_copied",
                        "已复制：{c}  {name}")
                    .format(c=glyph.char,
                            name=glyph.name_zh))
            elif chosen is a_insert:
                self._insert_to_target(glyph)
            elif chosen is a_copy_latex:
                if glyph.latex:
                    QApplication.clipboard().setText(glyph.latex)
                    self.status.setText(
                        self.i18n.t(
                            "glyph_latex_copied",
                            "已复制 LaTeX：{lx}")
                        .format(lx=glyph.latex))
            elif chosen is a_copy_char:
                QApplication.clipboard().setText(glyph.char)
                self.status.setText(
                    self.i18n.t(
                        "glyph_copied",
                        "已复制：{c}  {name}")
                    .format(c=glyph.char,
                            name=glyph.name_zh))
            elif chosen is a_fav:
                new_state = gl.toggle_favorite(glyph.char)
                if new_state:
                    self.status.setText(
                        self.i18n.t(
                            "glyph_fav_added",
                            "已加入收藏：{c}")
                        .format(c=glyph.char))
                else:
                    self.status.setText(
                        self.i18n.t(
                            "glyph_fav_removed",
                            "已取消收藏：{c}")
                        .format(c=glyph.char))
                if self.cat_box.currentData() == "__fav__":
                    self._refresh()
            elif chosen is a_info:
                self._show_info(glyph)
        except Exception as e:
            log_exc(e, module="GlyphPanel._on_context_menu")

    def _show_info(self, glyph: gl.Glyph):
        from PySide6.QtWidgets import QMessageBox
        text = (
            f"字符：{glyph.char}\n"
            f"中文名：{glyph.name_zh}\n"
            f"英文名：{glyph.name_en}\n"
            f"LaTeX：{glyph.latex or '—'}\n"
            f"分类：{glyph.category}\n"
            f"Unicode：U+{ord(glyph.char):04X}")
        QMessageBox.information(
            self,
            self.i18n.t("glyph_menu_info", "符号详情"),
            text)

    # ==================================================================

    def on_settings_changed(self, key=None):
        pass

    def set_theme_colors(self, fg, bg, panel):
        pass


__all__ = ["GlyphPanel"]