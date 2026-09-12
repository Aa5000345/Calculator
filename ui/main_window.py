from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QPushButton,
    QListWidget, QStackedWidget
)

from ui.panels import (
    BasicPanel, ScientificPanel, UnitPanel, CurrencyPanel, BasePanel,
    MatrixPanel, StatsPanel, PlotPanel, FinancePanel, DatePanel,
    RandomPanel, HistoryPanel, SettingsPanel
)


class MainWindow(QMainWindow):
    def __init__(self, base_path, settings, i18n, history):
        super().__init__()
        self.base_path = base_path
        self.settings = settings
        self.i18n = i18n
        self.history = history

        self.setWindowTitle(i18n.t("app_title"))
        self.resize(1200, 800)

        central = QWidget()
        self.setCentralWidget(central)
        main = QHBoxLayout(central)
        main.setContentsMargins(0, 0, 0, 0)

        self.sidebar = QWidget()
        side_layout = QVBoxLayout(self.sidebar)
        self.toggle = QPushButton("≡")
        self.toggle.clicked.connect(self.toggle_sidebar)
        self.list = QListWidget()
        self.list.currentRowChanged.connect(self.switch)
        side_layout.addWidget(self.toggle)
        side_layout.addWidget(self.list)

        self.stack = QStackedWidget()
        main.addWidget(self.sidebar)
        main.addWidget(self.stack, 1)

        self.panels = []
        self.add_panel(i18n.t("basic"), BasicPanel(settings, i18n, history))
        self.add_panel(i18n.t("scientific"), ScientificPanel(settings, i18n, history))
        self.add_panel(i18n.t("unit"), UnitPanel(settings, i18n, history))
        self.add_panel(i18n.t("currency"), CurrencyPanel(base_path, settings, i18n, history))
        self.add_panel(i18n.t("base"), BasePanel(settings, i18n, history))
        self.add_panel(i18n.t("matrix"), MatrixPanel(settings, i18n, history))
        self.add_panel(i18n.t("stats"), StatsPanel(settings, i18n, history))
        self.add_panel(i18n.t("plot"), PlotPanel(settings, i18n, history))
        self.add_panel(i18n.t("finance"), FinancePanel(settings, i18n, history))
        self.add_panel(i18n.t("date"), DatePanel(settings, i18n, history))
        self.add_panel(i18n.t("random"), RandomPanel(settings, i18n, history))
        self.add_panel(i18n.t("history"), HistoryPanel(history, i18n))
        self.add_panel(i18n.t("settings"), SettingsPanel(settings, i18n, self))

        self.list.setCurrentRow(0)
        self.apply_theme()

    def add_panel(self, name, widget):
        self.list.addItem(name)
        self.stack.addWidget(widget)
        self.panels.append(widget)

    def switch(self, idx):
        if idx >= 0:
            self.stack.setCurrentIndex(idx)

    def toggle_sidebar(self):
        self.list.setVisible(not self.list.isVisible())

    def apply_theme(self):
        theme = self.settings.get("theme", "dark")
        family = self.settings.get("font_family", "Microsoft YaHei")
        size = self.settings.get("font_size", 11)

        if theme == "dark":
            bg = "#1e1e1e"
            fg = "#ffffff"
            panel = "#2d2d30"
            accent = "#007acc"
        else:
            bg = "#f5f5f5"
            fg = "#000000"
            panel = "#ffffff"
            accent = "#0066cc"

        self.setStyleSheet(f"""
        QWidget {{
            background: {bg};
            color: {fg};
            font-family: '{family}';
            font-size: {size}pt;
        }}
        QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
            background: {panel};
            color: {fg};
            border: 1px solid #888;
            padding: 4px;
        }}
        QPushButton {{
            background: {panel};
            color: {fg};
            border: 1px solid #888;
            padding: 6px;
            border-radius: 4px;
        }}
        QPushButton:hover {{
            background: {accent};
            color: white;
        }}
        QListWidget {{
            background: {panel};
            color: {fg};
            border: none;
        }}
        QListWidget::item:selected {{
            background: {accent};
            color: white;
        }}
        """)