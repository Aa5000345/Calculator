"""面板注册表：新增面板只需在这里加一行。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Any


@dataclass
class PanelSpec:
    key: str
    group: str
    title_key: str
    title_default: str
    factory: Callable[[Any], Any]
    # 关键词：供命令面板分类 / 侧边栏搜索 / 使用统计使用
    keywords: tuple = field(default_factory=tuple)


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
                  lambda c: BasicPanel(c.settings, c.i18n, c.history),
                  keywords=("calc", "arith", "percent", "计算", "四则")),
        PanelSpec("scientific", "基础", "scientific", "Scientific",
                  lambda c: ScientificPanel(c.settings, c.i18n, c.history),
                  keywords=("sympy", "solve", "diff", "integrate",
                            "科学", "微积分")),
        # ---------------- 转换 ----------------
        PanelSpec("unit", "转换", "unit", "Unit Convert",
                  lambda c: UnitPanel(c.settings, c.i18n, c.history),
                  keywords=("unit", "convert", "单位", "换算")),
        PanelSpec("currency", "转换", "currency", "Currency",
                  lambda c: CurrencyPanel(c.base_path, c.settings,
                                          c.i18n, c.history),
                  keywords=("rate", "fx", "汇率", "货币")),
        PanelSpec("base", "转换", "base", "Base Convert",
                  lambda c: BasePanel(c.settings, c.i18n, c.history),
                  keywords=("radix", "hex", "bin", "进制", "ascii")),
        # ---------------- 数据 ----------------
        PanelSpec("stats", "数据", "stats", "Statistics",
                  lambda c: StatsPanel(c.settings, c.i18n, c.history),
                  keywords=("stats", "mean", "median", "统计")),
        PanelSpec("probability", "数据", "prob", "Probability",
                  lambda c: ProbabilityPanel(c.settings, c.i18n, c.history),
                  keywords=("dist", "pdf", "cdf", "ttest", "概率")),
        PanelSpec("random", "数据", "random", "Random",
                  lambda c: RandomPanel(c.settings, c.i18n, c.history),
                  keywords=("rand", "uuid", "password", "随机")),
        PanelSpec("data_table", "数据", "data_table", "Data Table",
                  lambda c: DataTablePanel(c.settings, c.i18n, c.history),
                  keywords=("table", "csv", "数据表", "公式")),
        # ---------------- 数学 ----------------
        PanelSpec("matrix", "数学", "matrix", "Matrix",
                  lambda c: MatrixPanel(c.settings, c.i18n, c.history),
                  keywords=("matrix", "det", "eigen", "矩阵")),
        PanelSpec("plot", "数学", "plot", "Plot",
                  lambda c: PlotPanel(c.settings, c.i18n, c.history),
                  keywords=("plot", "curve", "graph", "绘图")),
        PanelSpec("plot3d", "数学", "plot3d", "3D Plot",
                  lambda c: Plot3DPanel(c.settings, c.i18n, c.history),
                  keywords=("surface", "3d", "3D")),
        # ---------------- 财务 ----------------
        PanelSpec("finance", "财务", "finance", "Finance",
                  lambda c: FinancePanel(c.settings, c.i18n, c.history),
                  keywords=("loan", "npv", "irr", "bond", "财务")),
        PanelSpec("date", "财务", "date", "Date",
                  lambda c: DatePanel(c.settings, c.i18n, c.history),
                  keywords=("date", "time", "日期", "农历")),
        # ---------------- 工具 ----------------
        PanelSpec("bits", "工具", "bits", "Bits",
                  lambda c: BitsPanel(c.settings, c.i18n, c.history),
                  keywords=("bit", "crc", "hash", "位")),
        PanelSpec("crypto_tools", "工具", "crypto_tools", "Crypto Tools",
                  lambda c: CryptoPanel(c.settings, c.i18n, c.history),
                  keywords=("aes", "rsa", "totp", "加密", "哈希")),
        PanelSpec("latex", "工具", "latex_editor", "LaTeX Editor",
                  lambda c: LatexEditorPanel(c.settings, c.i18n, c.history),
                  keywords=("latex", "formula", "公式")),
        PanelSpec("tools", "工具", "tools", "Tools",
                  lambda c: ToolsPanel(c.settings, c.i18n, c.history),
                  keywords=("qr", "jwt", "regex", "color", "工具")),
        # ---------------- 生产力 ----------------
        PanelSpec("snippets", "生产力", "snippets", "Snippets",
                  lambda c: SnippetsPanel(c.settings, c.i18n, c.history),
                  keywords=("snippet", "片段", "收藏")),
        PanelSpec("timer", "生产力", "timer", "Timer",
                  lambda c: TimerPanel(c.settings, c.i18n, c.history),
                  keywords=("timer", "countdown", "计时")),
        PanelSpec("clipboard_history", "生产力", "clipboard_history",
                  "Clipboard",
                  lambda c: ClipboardHistoryPanel(c.settings, c.i18n,
                                                  c.history),
                  keywords=("clip", "history", "剪贴板")),
        PanelSpec("script", "生产力", "script", "Script",
                  lambda c: ScriptPanel(c.settings, c.i18n, c.history),
                  keywords=("script", "batch", "脚本")),
        # ---------------- AI ----------------
        PanelSpec("ai", "AI", "ai", "AI Assistant",
                  lambda c: AIPanel(c.settings, c.i18n, c.history),
                  keywords=("ai", "llm", "ollama", "openai", "自然语言")),
        # ---------------- 系统 ----------------
        PanelSpec("history", "系统", "history", "History",
                  lambda c: _make_history(c),
                  keywords=("history", "历史")),
        PanelSpec("settings", "系统", "settings", "Settings",
                  lambda c: SettingsPanel(c.settings, c.i18n,
                                          c.main_window),
                  keywords=("settings", "pref", "设置")),
    ]


def _make_history(ctx):
    from .history import HistoryPanel
    panel = HistoryPanel(ctx.history, ctx.i18n)
    panel.set_reuse_handler(ctx.reuse_handler)
    return panel


def all_keywords() -> dict:
    """返回 {key: keywords}，供命令面板 / 侧边栏搜索使用。"""
    return {spec.key: tuple(spec.keywords) for spec in all_panels()}