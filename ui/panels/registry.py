"""面板注册表：新增面板只需在这里加一行。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Any


@dataclass
class PanelSpec:
    key: str
    group: str
    title_key: str
    title_default: str
    factory: Callable[[Any], Any]


def all_panels() -> list[PanelSpec]:
    # 延迟导入，避免循环
    from .basic import BasicPanel
    from .scientific import ScientificPanel
    from .unit import UnitPanel
    from .currency import CurrencyPanel
    from .base_convert import BasePanel
    from .matrix import MatrixPanel
    from .stats import StatsPanel
    from .plot import PlotPanel
    from .plot3d import Plot3DPanel
    from .finance import FinancePanel
    from .date import DatePanel
    from .random_panel import RandomPanel
    from .probability import ProbabilityPanel
    from .bits import BitsPanel
    from .crypto_tools import CryptoPanel
    from .latex_editor import LatexEditorPanel
    from .history import HistoryPanel
    from .settings import SettingsPanel
    from .data_table import DataTablePanel
    from .tools import ToolsPanel
    from .snippets import SnippetsPanel
    from .timer_panel import TimerPanel
    from .clipboard_history import ClipboardHistoryPanel
    from .ai import AIPanel
    from .script import ScriptPanel

    return [
        # ---------------- 基础 ----------------
        PanelSpec("basic", "基础", "basic", "Basic",
                  lambda c: BasicPanel(c.settings, c.i18n, c.history)),
        PanelSpec("scientific", "基础", "scientific", "Scientific",
                  lambda c: ScientificPanel(c.settings, c.i18n, c.history)),
        # ---------------- 转换 ----------------
        PanelSpec("unit", "转换", "unit", "Unit Convert",
                  lambda c: UnitPanel(c.settings, c.i18n, c.history)),
        PanelSpec("currency", "转换", "currency", "Currency",
                  lambda c: CurrencyPanel(c.base_path, c.settings,
                                          c.i18n, c.history)),
        PanelSpec("base", "转换", "base", "Base Convert",
                  lambda c: BasePanel(c.settings, c.i18n, c.history)),
        # ---------------- 数据 ----------------
        PanelSpec("stats", "数据", "stats", "Statistics",
                  lambda c: StatsPanel(c.settings, c.i18n, c.history)),
        PanelSpec("probability", "数据", "prob", "Probability",
                  lambda c: ProbabilityPanel(c.settings, c.i18n, c.history)),
        PanelSpec("random", "数据", "random", "Random",
                  lambda c: RandomPanel(c.settings, c.i18n, c.history)),
        PanelSpec("data_table", "数据", "data_table", "Data Table",
                  lambda c: DataTablePanel(c.settings, c.i18n, c.history)),
        # ---------------- 数学 ----------------
        PanelSpec("matrix", "数学", "matrix", "Matrix",
                  lambda c: MatrixPanel(c.settings, c.i18n, c.history)),
        PanelSpec("plot", "数学", "plot", "Plot",
                  lambda c: PlotPanel(c.settings, c.i18n, c.history)),
        PanelSpec("plot3d", "数学", "plot3d", "3D Plot",
                  lambda c: Plot3DPanel(c.settings, c.i18n, c.history)),
        # ---------------- 财务 ----------------
        PanelSpec("finance", "财务", "finance", "Finance",
                  lambda c: FinancePanel(c.settings, c.i18n, c.history)),
        PanelSpec("date", "财务", "date", "Date",
                  lambda c: DatePanel(c.settings, c.i18n, c.history)),
        # ---------------- 工具 ----------------
        PanelSpec("bits", "工具", "bits", "Bits",
                  lambda c: BitsPanel(c.settings, c.i18n, c.history)),
        PanelSpec("crypto_tools", "工具", "crypto_tools", "Crypto Tools",
                  lambda c: CryptoPanel(c.settings, c.i18n, c.history)),
        PanelSpec("latex", "工具", "latex_editor", "LaTeX Editor",
                  lambda c: LatexEditorPanel(c.settings, c.i18n, c.history)),
        PanelSpec("tools", "工具", "tools", "Tools",
                  lambda c: ToolsPanel(c.settings, c.i18n, c.history)),
        # ---------------- 生产力 ----------------
        PanelSpec("snippets", "生产力", "snippets", "Snippets",
                  lambda c: SnippetsPanel(c.settings, c.i18n, c.history)),
        PanelSpec("timer", "生产力", "timer", "Timer",
                  lambda c: TimerPanel(c.settings, c.i18n, c.history)),
        PanelSpec("clipboard_history", "生产力", "clipboard_history",
                  "Clipboard",
                  lambda c: ClipboardHistoryPanel(c.settings, c.i18n,
                                                  c.history)),
        PanelSpec("script", "生产力", "script", "Script",
                  lambda c: ScriptPanel(c.settings, c.i18n, c.history)),
        # ---------------- AI ----------------
        PanelSpec("ai", "AI", "ai", "AI Assistant",
                  lambda c: AIPanel(c.settings, c.i18n, c.history)),
        # ---------------- 系统 ----------------
        PanelSpec("history", "系统", "history", "History",
                  lambda c: _make_history(c)),
        PanelSpec("settings", "系统", "settings", "Settings",
                  lambda c: SettingsPanel(c.settings, c.i18n,
                                          c.main_window)),
    ]


def _make_history(ctx):
    from .history import HistoryPanel
    panel = HistoryPanel(ctx.history, ctx.i18n)
    panel.set_reuse_handler(ctx.reuse_handler)
    return panel