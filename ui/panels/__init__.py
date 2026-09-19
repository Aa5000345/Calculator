"""所有面板的统一入口。

合并后的新布局：
    basic / scientific / convert / data / math / finance
    / tools / productivity / ai / system

保留独立导出，便于外部按类名引用。
"""
from .basic import BasicPanel, BasePanel, BitsPanel
from .scientific import ScientificPanel, MatrixPanel
from .convert import (
    UnitPanel, CurrencyPanel, NumberSystemsPanel,
)
from .data import (
    StatsPanel, ProbabilityPanel, BayesianTab,
    RandomPanel, DataTablePanel, DataOpsPanel,
)
from .math import (
    PlotPanel, Plot3DPanel, PipelinePanel, LatexEditorPanel,
)
from .finance import FinancePanel, DatePanel
from .tools import (
    CryptoPanel, CryptoAdvancedTab, FileCryptoTab,
    ToolsPanel, GlyphPanel, SnippetsPanel,
)
from .productivity import (
    TimerPanel, ClipboardHistoryPanel,
    NotebookPanel, ScriptPanel,
)
from .ai import AIPanel, AIChatTab
from .system import (
    HistoryPanel, SettingsPanel, ShortcutSettingsPanel,
)


__all__ = [
    # 基础
    "BasicPanel", "BasePanel", "BitsPanel",
    # 科学
    "ScientificPanel", "MatrixPanel",
    # 转换
    "UnitPanel", "CurrencyPanel", "NumberSystemsPanel",
    # 数据
    "StatsPanel", "ProbabilityPanel", "BayesianTab",
    "RandomPanel", "DataTablePanel", "DataOpsPanel",
    # 数学
    "PlotPanel", "Plot3DPanel", "PipelinePanel",
    "LatexEditorPanel",
    # 财务
    "FinancePanel", "DatePanel",
    # 工具
    "CryptoPanel", "CryptoAdvancedTab", "FileCryptoTab",
    "ToolsPanel", "GlyphPanel", "SnippetsPanel",
    # 生产力
    "TimerPanel", "ClipboardHistoryPanel",
    "NotebookPanel", "ScriptPanel",
    # AI
    "AIPanel", "AIChatTab",
    # 系统
    "HistoryPanel", "SettingsPanel", "ShortcutSettingsPanel",
]