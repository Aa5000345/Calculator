"""键盘布局 DSL：用 dataclass + 二维列表描述，按模块切换。

设计：
- 每个布局是 6 列的网格，行数 4~6 行
- 底部 4 行为"通用数字块"（0-9 / 四则 / C / ⌫ / ( ) / = / 2ⁿᵈ）
- 顶部 1~2 行是模块专属功能键
- 通过 module_key 查找：`get_layout(module_key)`
- 未匹配的面板回退到 `LAYOUT_DEFAULT`
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Key:
    """一个按键。

    字段说明：
    - label       : 主标签
    - insert      : 点击时插入的文本
    - action      : 特殊动作（"equals" / "clear" / "backspace" / "second"
                    / "mem_*" / "cursor_*"）
    - alt_label   : 2ⁿᵈ 状态下的标签
    - alt_insert  : 2ⁿᵈ 状态下的插入文本
    - alt_action  : 2ⁿᵈ 状态下的动作
    - tooltip     : 悬浮提示
    - style       : 主题键（num / op / fn / danger / accent）
    - span        : 跨列数（暂只支持 1）
    """
    label: str
    insert: str = ""
    action: str = ""
    alt_label: str = ""
    alt_insert: str = ""
    alt_action: str = ""
    tooltip: str = ""
    style: str = "num"
    span: int = 1


@dataclass(frozen=True)
class Layout:
    name: str
    label: str
    rows: tuple  # tuple[tuple[Key, ...], ...]


# =====================================================================
# 通用数字块（所有布局共享底部 4 行）
# =====================================================================

_NUM_BLOCK = (
    (Key("7"), Key("8"), Key("9"), Key("/", "/", style="op"),
     Key("(", "(", style="op"), Key(")", ")", style="op")),
    (Key("4"), Key("5"), Key("6"), Key("*", "*", style="op"),
     Key("C", action="clear", style="danger"),
     Key("⌫", action="backspace", style="danger")),
    (Key("1"), Key("2"), Key("3"), Key("-", "-", style="op"),
     Key(".", "."), Key(",", ",")),
    (Key("0"), Key("00", "00"),
     Key("=", action="equals", style="accent"),
     Key("+", "+", style="op"),
     Key("%", "%", style="fn"),
     Key("2ⁿᵈ", action="second", style="fn")),
)


# =====================================================================
# 各模块布局
# =====================================================================

LAYOUT_BASIC = Layout(
    name="basic",
    label="基础",
    rows=_NUM_BLOCK,
)

LAYOUT_SCIENTIFIC = Layout(
    name="scientific",
    label="科学",
    rows=(
        (Key("sin", "sin(", alt_label="sin⁻¹", alt_insert="asin(", style="fn"),
         Key("cos", "cos(", alt_label="cos⁻¹", alt_insert="acos(", style="fn"),
         Key("tan", "tan(", alt_label="tan⁻¹", alt_insert="atan(", style="fn"),
         Key("ln", "log(", alt_label="eˣ", alt_insert="exp(", style="fn"),
         Key("log", "log10(", alt_label="10ˣ", alt_insert="10^", style="fn"),
         Key("√", "sqrt(", alt_label="∛", alt_insert="cbrt(", style="fn")),
        (Key("π", "pi", style="fn"),
         Key("e", "e", style="fn"),
         Key("x²", "^2", alt_label="x³", alt_insert="^3", style="fn"),
         Key("xʸ", "^", style="fn"),
         Key("!", "factorial(", alt_label="Γ", alt_insert="gamma(", style="fn"),
         Key("|x|", "Abs(", style="fn")),
    ) + _NUM_BLOCK,
)

LAYOUT_MATRIX = Layout(
    name="matrix",
    label="矩阵",
    rows=(
        (Key("det", "det", style="fn"), Key("inv", "inv", style="fn"),
         Key("T", "transpose", style="fn"), Key("rank", "rank", style="fn"),
         Key("rref", "rref", style="fn"), Key("tr", "trace", style="fn")),
    ) + _NUM_BLOCK,
)

LAYOUT_PLOT = Layout(
    name="plot",
    label="绘图",
    rows=(
        (Key("sin", "sin(", style="fn"), Key("cos", "cos(", style="fn"),
         Key("tan", "tan(", style="fn"), Key("exp", "exp(", style="fn"),
         Key("log", "log(", style="fn"), Key("ln", "ln(", style="fn")),
        (Key("x", "x", style="fn"), Key("t", "t", style="fn"),
         Key("θ", "theta", style="fn"), Key("π", "pi", style="fn"),
         Key("e", "e", style="fn"), Key("^", "^", style="fn")),
    ) + _NUM_BLOCK,
)

LAYOUT_PLOT3D = Layout(
    name="plot3d",
    label="3D 绘图",
    rows=(
        (Key("sin", "sin(", style="fn"), Key("cos", "cos(", style="fn"),
         Key("tan", "tan(", style="fn"), Key("exp", "exp(", style="fn"),
         Key("log", "log(", style="fn"), Key("ln", "ln(", style="fn")),
        (Key("x", "x", style="fn"), Key("y", "y", style="fn"),
         Key("t", "t", style="fn"), Key("π", "pi", style="fn"),
         Key("e", "e", style="fn"), Key("^", "^", style="fn")),
    ) + _NUM_BLOCK,
)

LAYOUT_FINANCE = Layout(
    name="finance",
    label="财务",
    rows=(
        (Key("$", "$", style="fn"), Key("%", "%", style="fn"),
         Key("±", "-", style="fn"), Key("^", "^", style="fn"),
         Key("(1+r)", "(1+r)", style="fn"), Key("n", "n", style="fn")),
    ) + _NUM_BLOCK,
)

LAYOUT_DATE = Layout(
    name="date",
    label="日期",
    rows=(
        (Key("7"), Key("8"), Key("9"), Key("-", "-", style="op"),
         Key(":", ":"), Key("空格", " ", style="fn")),
        (Key("4"), Key("5"), Key("6"), Key("/", "/", style="op"),
         Key(".", "."), Key("⌫", action="backspace", style="danger")),
        (Key("1"), Key("2"), Key("3"),
         Key("←", action="cursor_left", style="fn"),
         Key("→", action="cursor_right", style="fn"),
         Key("C", action="clear", style="danger")),
        (Key("0"), Key("00", "00"),
         Key("=", action="equals", style="accent"),
         Key("+", "+", style="op"),
         Key("↑", action="cursor_up", style="fn"),
         Key("↓", action="cursor_down", style="fn")),
    ),
)

LAYOUT_UNIT = Layout(
    name="unit",
    label="单位",
    rows=(
        (Key("km", " km", style="fn"), Key("m", " m", style="fn"),
         Key("cm", " cm", style="fn"), Key("mm", " mm", style="fn"),
         Key("kg", " kg", style="fn"), Key("g", " g", style="fn")),
        (Key("°C", " degC", style="fn"), Key("°F", " degF", style="fn"),
         Key("L", " L", style="fn"), Key("mL", " mL", style="fn"),
         Key("h", " h", style="fn"), Key("min", " min", style="fn")),
    ) + _NUM_BLOCK,
)

LAYOUT_CURRENCY = Layout(
    name="currency",
    label="汇率",
    rows=(
        (Key("USD", "USD", style="fn"), Key("CNY", "CNY", style="fn"),
         Key("EUR", "EUR", style="fn"), Key("JPY", "JPY", style="fn"),
         Key("GBP", "GBP", style="fn"), Key("HKD", "HKD", style="fn")),
    ) + _NUM_BLOCK,
)

LAYOUT_BASE = Layout(
    name="base",
    label="进制",
    rows=(
        (Key("7"), Key("8"), Key("9"), Key("A", "A", style="op"),
         Key("B", "B", style="op"), Key("C", "C", style="op")),
        (Key("4"), Key("5"), Key("6"), Key("D", "D", style="op"),
         Key("E", "E", style="op"), Key("F", "F", style="op")),
        (Key("1"), Key("2"), Key("3"),
         Key("0x", "0x", style="fn"),
         Key("0b", "0b", style="fn"),
         Key("0o", "0o", style="fn")),
        (Key("0"), Key("00", "00"),
         Key("=", action="equals", style="accent"),
         Key("C", action="clear", style="danger"),
         Key("⌫", action="backspace", style="danger"),
         Key("2ⁿᵈ", action="second", style="fn")),
    ),
)

LAYOUT_BITS = Layout(
    name="bits",
    label="位运算",
    rows=(
        (Key("0"), Key("1"),
         Key("&", " & ", style="op"),
         Key("|", " | ", style="op"),
         Key("^", " ^ ", style="op"),
         Key("~", "~", style="fn")),
        (Key("<<", " << ", style="op"),
         Key(">>", " >> ", style="op"),
         Key("A", "A", style="fn"), Key("B", "B", style="fn"),
         Key("C", "C", style="fn"), Key("D", "D", style="fn")),
        (Key("E", "E", style="fn"), Key("F", "F", style="fn"),
         Key("0x", "0x", style="fn"), Key("0b", "0b", style="fn"),
         Key(".", "."),
         Key("⌫", action="backspace", style="danger")),
        (Key("7"), Key("8"), Key("9"),
         Key("C", action="clear", style="danger"),
         Key("=", action="equals", style="accent"),
         Key("2ⁿᵈ", action="second", style="fn")),
    ),
)

# 加密工具复用进制布局（A-F + hex 前缀对 Base64/Hex/AES 输入都有用）
LAYOUT_CRYPTO = Layout(
    name="crypto_tools",
    label="加密",
    rows=LAYOUT_BASE.rows,
)

LAYOUT_LATEX = Layout(
    name="latex",
    label="LaTeX",
    rows=(
        (Key("\\", "\\", style="fn"), Key("{", "{", style="fn"),
         Key("}", "}", style="fn"), Key("_", "_", style="fn"),
         Key("^", "^", style="fn"), Key("$", "$", style="fn")),
        (Key("{}", "{}", style="fn"), Key("_{}", "_{}", style="fn"),
         Key("^{}", "^{}", style="fn"), Key("_{}^{}", "_{}^{}", style="fn"),
         Key("sqrt", "\\sqrt{}", style="fn"),
         Key("frac", "\\frac{}{}", style="fn")),
        (Key("α", "\\alpha ", style="fn"), Key("β", "\\beta ", style="fn"),
         Key("θ", "\\theta ", style="fn"), Key("π", "\\pi ", style="fn"),
         Key("∞", "\\infty ", style="fn"),
         Key("∂", "\\partial ", style="fn")),
        (Key("sin", "\\sin ", style="fn"), Key("cos", "\\cos ", style="fn"),
         Key("tan", "\\tan ", style="fn"), Key("log", "\\log ", style="fn"),
         Key("ln", "\\ln ", style="fn"),
         Key("lim", "\\lim_{x\\to 0} ", style="fn")),
    ),
)

LAYOUT_SCRIPT = Layout(
    name="script",
    label="脚本",
    rows=(
        (Key("7"), Key("8"), Key("9"), Key("/", "/", style="op"),
         Key("(", "(", style="op"), Key(")", ")", style="op")),
        (Key("4"), Key("5"), Key("6"), Key("*", "*", style="op"),
         Key("#", "#", style="fn"),
         Key("↵", "\n", style="fn")),
        (Key("1"), Key("2"), Key("3"), Key("-", "-", style="op"),
         Key("=", "=", style="fn"),
         Key("空格", " ", style="fn")),
        (Key("0"), Key("."),
         Key("x", "x", style="fn"), Key("y", "y", style="fn"),
         Key("C", action="clear", style="danger"),
         Key("⌫", action="backspace", style="danger")),
    ),
)

LAYOUT_DEFAULT = Layout(
    name="default",
    label="通用",
    rows=(
        (Key("sin", "sin(", style="fn"), Key("cos", "cos(", style="fn"),
         Key("tan", "tan(", style="fn"),
         Key("π", "pi", style="fn"), Key("e", "e", style="fn"),
         Key("^", "^", style="fn")),
    ) + _NUM_BLOCK,
)


# =====================================================================
# module_key → Layout
# =====================================================================

_LAYOUT_BY_MODULE = {
    "basic": LAYOUT_BASIC,
    "scientific": LAYOUT_SCIENTIFIC,
    "matrix": LAYOUT_MATRIX,
    "plot": LAYOUT_PLOT,
    "plot3d": LAYOUT_PLOT3D,
    "finance": LAYOUT_FINANCE,
    "date": LAYOUT_DATE,
    "unit": LAYOUT_UNIT,
    "currency": LAYOUT_CURRENCY,
    "base": LAYOUT_BASE,
    "bits": LAYOUT_BITS,
    "crypto_tools": LAYOUT_CRYPTO,
    "latex": LAYOUT_LATEX,
    "script": LAYOUT_SCRIPT,
    # 未列出的面板回退到 LAYOUT_DEFAULT：
    # stats / probability / random / data_table / tools /
    # snippets / timer / clipboard_history / history / settings / ai
}


def get_layout(module_key: str) -> Layout:
    """按 module_key 获取布局；未匹配则回退到 LAYOUT_DEFAULT。"""
    if not module_key:
        return LAYOUT_DEFAULT
    return _LAYOUT_BY_MODULE.get(str(module_key), LAYOUT_DEFAULT)


def get_layout_name(module_key: str) -> str:
    """获取布局的显示名（用于标题栏）。"""
    return get_layout(module_key).label


def all_module_keys() -> list:
    """已注册专属布局的所有 module_key。"""
    return list(_LAYOUT_BY_MODULE.keys())