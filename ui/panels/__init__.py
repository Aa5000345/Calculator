"""所有面板的统一入口（保持 from ui.panels import X 兼容）。"""
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

__all__ = [
    "BasicPanel", "ScientificPanel", "UnitPanel", "CurrencyPanel",
    "BasePanel", "MatrixPanel", "StatsPanel", "PlotPanel", "Plot3DPanel",
    "FinancePanel", "DatePanel", "RandomPanel", "ProbabilityPanel",
    "BitsPanel", "CryptoPanel", "LatexEditorPanel", "HistoryPanel",
    "SettingsPanel",
]