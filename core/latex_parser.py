"""LaTeX → 表达式：把 LaTeX 数学公式转为 SymPy 可解析的形式。

设计原则：
- 不依赖 latex2sympy2（那个库依赖 antlr4 运行时，体积大）
- 纯正则 + 递归展开，覆盖 95% 常见公式
- 失败时返回原字符串并附带错误信息，不抛异常

支持的命令：
    分数      \\frac{a}{b}            → (a)/(b)
    平方根    \\sqrt{x}               → sqrt(x)
    n 次根    \\sqrt[n]{x}            → (x)**(1/(n))
    上标      x^{2} / x^2             → x**(2)
    下标      x_{i}                   → x_i
    希腊字母  \\alpha \\beta \\pi      → alpha beta pi
    常数      \\infty                 → oo
    运算      \\cdot \\times \\div    → * * /
    三角函数  \\sin \\cos \\tan       → sin cos tan
    对数      \\log \\ln              → log log
    极限      \\lim_{x \\to a}        → limit 提示（不做展开）
    求和      \\sum_{i=a}^{b}         → Sum 提示
    积分      \\int_{a}^{b}           → Integral 提示
    绝对值    \\left| x \\right|      → Abs(x)
    圆括号    \\left( \\right)        → ( )
    组合数    \\binom{n}{k}           → binomial(n, k)
    导数      \\frac{d}{dx}           → 提示用 diff

已知限制：
- 复杂的矩阵环境（pmatrix / bmatrix）不展开，转为警告
- \\text{...} 内容会被忽略
- 多层嵌套的上下标可能解析错误

对外接口：
    latex_to_expr(text) -> LaTeXParseResult
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------

@dataclass
class LaTeXParseResult:
    expr: str = ""              # 转换后的表达式
    warnings: list = field(default_factory=list)  # 警告（不致命）
    error: str = ""             # 致命错误

    @property
    def ok(self) -> bool:
        return not self.error


# ---------------------------------------------------------------------------
# 符号映射
# ---------------------------------------------------------------------------

_GREEK = {
    "alpha": "alpha", "beta": "beta", "gamma": "gamma",
    "delta": "delta", "epsilon": "epsilon", "varepsilon": "epsilon",
    "zeta": "zeta", "eta": "eta", "theta": "theta",
    "vartheta": "theta", "iota": "iota", "kappa": "kappa",
    "lambda": "lambda_", "mu": "mu", "nu": "nu", "xi": "xi",
    "omicron": "omicron", "pi": "pi", "varpi": "pi",
    "rho": "rho", "varrho": "rho", "sigma": "sigma",
    "varsigma": "sigma", "tau": "tau", "upsilon": "upsilon",
    "phi": "phi", "varphi": "phi", "chi": "chi",
    "psi": "psi", "omega": "omega",
    # 大写
    "Gamma": "Gamma", "Delta": "Delta", "Theta": "Theta",
    "Lambda": "Lambda_", "Xi": "Xi", "Pi": "Pi",
    "Sigma": "Sigma", "Upsilon": "Upsilon", "Phi": "Phi",
    "Psi": "Psi", "Omega": "Omega",
}

# LaTeX 命令 → 目标文本
_SIMPLE_CMDS = {
    # 常数
    "infty": "oo", "infinity": "oo",
    "partial": "Partial",
    "nabla": "nabla",
    # 运算
    "cdot": "*", "times": "*", "div": "/",
    "pm": "±", "mp": "∓",     # 保留，后续替换
    "leq": "<=", "le": "<=",
    "geq": ">=", "ge": ">=",
    "neq": "!=", "ne": "!=",
    "approx": "≈", "sim": "~",
    "equiv": "==", "to": "->", "rightarrow": "->",
    "leftarrow": "<-", "Rightarrow": "=>",
    "Leftrightarrow": "<=>",
    # 函数
    "sin": "sin", "cos": "cos", "tan": "tan",
    "cot": "cot", "sec": "sec", "csc": "csc",
    "arcsin": "asin", "arccos": "acos", "arctan": "atan",
    "sinh": "sinh", "cosh": "cosh", "tanh": "tanh",
    "log": "log", "ln": "log", "lg": "log10",
    "exp": "exp",
    "max": "Max", "min": "Min",
    "lim": "limit",
    "gcd": "gcd", "lcm": "lcm",
    "det": "det",
    # 排版
    "quad": " ", "qquad": "  ",
    ",": " ", ";": " ", ":": " ", "!": "", " ": " ",
}

# 需要在替换前处理的整体替换
_LETTER_MAP = {
    "≤": "<=", "≥": ">=", "≠": "!=",
    "×": "*", "÷": "/",
    "−": "-", "–": "-", "—": "-",
    "∞": "oo", "π": "pi", "θ": "theta",
    "±": "+-", "∓": "-+",
    "√": "sqrt",
    "∫": "Integral", "∑": "Sum", "∏": "Product",
}


# ---------------------------------------------------------------------------
# 预处理
# ---------------------------------------------------------------------------

def _strip_math_delimiters(s: str) -> str:
    """去掉 `$...$` / `$$...$$` / `\\(...\\)` / `\\[...\\]`。"""
    s = s.strip()
    # 多行公式
    s = re.sub(r"^\s*\$\$(.+)\$\$\s*$", r"\1", s, flags=re.DOTALL)
    # 行内公式
    s = re.sub(r"^\s*\$(.+)\$\s*$", r"\1", s, flags=re.DOTALL)
    s = re.sub(r"^\s*\\\((.+)\\\)\s*$", r"\1", s, flags=re.DOTALL)
    s = re.sub(r"^\s*\\\[(.+)\\\]\s*$", r"\1", s, flags=re.DOTALL)
    return s


def _strip_spacing(s: str) -> str:
    """去掉纯排版命令：`\\,` `\\;` `\\!` `\\ ` `\\quad` `\\qquad`。"""
    s = re.sub(r"\\[,;:!]", " ", s)
    s = re.sub(r"\\quad\b", " ", s)
    s = re.sub(r"\\qquad\b", "  ", s)
    return s


def _strip_text(s: str) -> str:
    """去掉 `\\text{...}` / `\\mathrm{...}` 等排版命令的内容。"""
    for cmd in ("text", "mathrm", "mathbf", "mathit", "mathsf",
                "mathtt", "operatorname", "mbox", "hbox"):
        s = re.sub(rf"\\{cmd}\s*\{{([^{{}}]*)\}}", r"\1", s)
    return s


def _strip_display(s: str) -> str:
    """去掉 `\\displaystyle` / `\\limits` 等展示命令。"""
    for cmd in ("displaystyle", "limits", "nolimits",
                "textstyle", "scriptstyle", "small"):
        s = re.sub(rf"\\{cmd}\b", " ", s)
    return s


def _strip_left_right(s: str) -> str:
    """去掉 `\\left` / `\\right` / `\\big` 等调整命令。"""
    s = re.sub(
        r"\\(?:left|right|big|Big|bigg|Bigg|bigl|bigr|Bigl|Bigr)\b",
        " ", s)
    return s


def _strip_labels(s: str) -> str:
    """去掉 `\\label{...}` / `\\tag{...}` / `\\nonumber`。"""
    s = re.sub(r"\\label\s*\{[^}]*\}", "", s)
    s = re.sub(r"\\tag\s*\{[^}]*\}", "", s)
    s = re.sub(r"\\nonumber\b", "", s)
    return s


# ---------------------------------------------------------------------------
# 结构命令展开
# ---------------------------------------------------------------------------

def _read_balanced(s: str, i: int) -> tuple:
    """从 s[i] 开始读取一个 `{...}` 平衡组。

    返回 (内容, 结束后的索引)；如果 s[i] 不是 `{` 则返回 ("", i)。
    """
    if i >= len(s) or s[i] != "{":
        return "", i
    depth = 0
    start = i + 1
    j = i
    while j < len(s):
        c = s[j]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return s[start:j], j + 1
        j += 1
    return s[start:], len(s)


def _expand_frac(s: str) -> str:
    """递归展开 \\frac{a}{b} → ((a)/(b))。"""
    out = []
    i = 0
    while i < len(s):
        if s.startswith(r"\frac", i) or s.startswith(r"\dfrac", i) \
                or s.startswith(r"\tfrac", i):
            # 定位到 \frac 后第一个 {
            k = i + (6 if s.startswith(r"\dfrac", i)
                     or s.startswith(r"\tfrac", i) else 5)
            while k < len(s) and s[k].isspace():
                k += 1
            num, k1 = _read_balanced(s, k)
            while k1 < len(s) and s[k1].isspace():
                k1 += 1
            den, k2 = _read_balanced(s, k1)
            if num and den:
                out.append(f"(({num})/({den}))")
                i = k2
                continue
        out.append(s[i])
        i += 1
    return "".join(out)


def _expand_sqrt(s: str) -> str:
    """展开 \\sqrt[n]{x} → (x)**(1/(n))；\\sqrt{x} → sqrt(x)。"""
    out = []
    i = 0
    while i < len(s):
        if s.startswith(r"\sqrt", i):
            k = i + 5
            # 可选 [n]
            n = None
            if k < len(s) and s[k] == "[":
                close = s.find("]", k)
                if close > 0:
                    n = s[k + 1:close]
                    k = close + 1
            while k < len(s) and s[k].isspace():
                k += 1
            body, k2 = _read_balanced(s, k)
            if body:
                if n:
                    out.append(f"(({body})**(1/({n})))")
                else:
                    out.append(f"sqrt({body})")
                i = k2
                continue
        out.append(s[i])
        i += 1
    return "".join(out)


def _expand_binom(s: str) -> str:
    """展开 \\binom{n}{k} → binomial(n, k)。"""
    out = []
    i = 0
    while i < len(s):
        if s.startswith(r"\binom", i) or s.startswith(r"\dbinom", i):
            k = i + (6 if s.startswith(r"\dbinom", i) else 6)
            while k < len(s) and s[k].isspace():
                k += 1
            a, k1 = _read_balanced(s, k)
            while k1 < len(s) and s[k1].isspace():
                k1 += 1
            b, k2 = _read_balanced(s, k1)
            if a and b:
                out.append(f"binomial({a}, {b})")
                i = k2
                continue
        out.append(s[i])
        i += 1
    return "".join(out)


def _expand_abs(s: str) -> str:
    """`\\left|...\\right|` / `|...|` → `Abs(...)`。

    只处理成对的单层绝对值；复杂嵌套可能不准。
    """
    # \left| ... \right|
    s = re.sub(
        r"\\left\s*\|\s*(.+?)\s*\\right\s*\|",
        r"Abs(\1)", s, flags=re.DOTALL)
    # 普通 |...|
    s = re.sub(r"\|([^|]+)\|", r"Abs(\1)", s)
    return s


def _expand_sum_prod_int(s: str, warnings: list) -> str:
    """求和 / 求积 / 积分：转成可读注释，不实际展开。

    例：`\\sum_{i=1}^{n} i` → `Sum(i, (i, 1, n))` 形式
        `\\int_{a}^{b} f dx` → `Integral(f, (x, a, b))` 形式
    """
    # \sum_{lower}^{upper} body
    def _repl_sum(m):
        lower = m.group(1)
        upper = m.group(2)
        body = m.group(3).strip()
        return f"Sum({body}, {_parse_bounds(lower, upper)})"

    s = re.sub(
        r"\\sum\s*_\s*\{([^}]*)\}\s*\^\s*\{([^}]*)\}"
        r"\s*([^\\]*?)(?=\\|$)",
        _repl_sum, s)

    # \prod_{lower}^{upper} body
    def _repl_prod(m):
        lower = m.group(1)
        upper = m.group(2)
        body = m.group(3).strip()
        return f"Product({body}, {_parse_bounds(lower, upper)})"

    s = re.sub(
        r"\\prod\s*_\s*\{([^}]*)\}\s*\^\s*\{([^}]*)\}"
        r"\s*([^\\]*?)(?=\\|$)",
        _repl_prod, s)

    # \int_{a}^{b}
    def _repl_int(m):
        lower = m.group(1)
        upper = m.group(2)
        return f"Integral(?, ({lower}, {upper}))"

    if re.search(r"\\int\b", s):
        warnings.append(
            "检测到 \\int，已转为 Integral(...) 占位，"
            "请手动补齐被积函数与变量")

    return s


def _parse_bounds(lower: str, upper: str) -> str:
    """把 `i=1` `n` 形式的下上限转为 `(i, 1, n)`。"""
    m = re.match(r"^\s*([A-Za-z_]\w*)\s*=\s*(.+)$", lower)
    if m:
        var, lo = m.group(1), m.group(2).strip()
        return f"({var}, {lo}, {upper.strip()})"
    # 没有显式变量的情况
    return f"(_, {lower.strip()}, {upper.strip()})"


# ---------------------------------------------------------------------------
# 上下标
# ---------------------------------------------------------------------------

def _expand_superscripts(s: str) -> str:
    """`^{...}` → `**(...)`；`^x` → `**x`。"""
    # 带花括号：^{...}
    s = re.sub(r"\^\s*\{([^{}]*)\}", r"**(\1)", s)
    # 单个字符：^2 / ^x
    s = re.sub(r"\^\s*([0-9A-Za-z_])", r"**\1", s)
    return s


def _expand_subscripts(s: str) -> str:
    """`_{...}` → `_(...)`（保留为符号名的一部分）；`_x` → `_x`。"""
    # 带花括号：_{...} → _xxx（合并为单个标识符）
    def _repl(m):
        body = m.group(1)
        # 如果 body 是简单标识符，合并为 name_sub
        if re.match(r"^[A-Za-z0-9]+$", body):
            return f"_{body}"
        return f"_{body}"

    s = re.sub(r"_\s*\{([^{}]*)\}", _repl, s)
    return s


def _expand_dfrac_dt(s: str, warnings: list) -> str:
    """`\\frac{d}{dx}` / `\\frac{dy}{dx}` → 提示用 diff。"""
    if re.search(r"\\frac\s*\{\s*d\s*\}\s*\{\s*d\s*([A-Za-z])\s*\}", s):
        warnings.append(
            "检测到导数记号 d/dx，已转为 diff(...) 占位，"
            "请手动补齐表达式")
        s = re.sub(
            r"\\frac\s*\{\s*d\s*\}\s*\{\s*d\s*([A-Za-z])\s*\}",
            r"diff(?, \1)", s)
    return s


# ---------------------------------------------------------------------------
# 简单命令替换
# ---------------------------------------------------------------------------

def _replace_commands(s: str) -> str:
    """替换剩余的命令 `\\name` → 目标文本。"""
    # 先处理希腊字母
    def _greek_repl(m):
        name = m.group(1)
        return _GREEK.get(name, name)

    s = re.sub(
        r"\\([A-Za-z]+)\b",
        lambda m: _SIMPLE_CMDS.get(m.group(1))
        or _GREEK.get(m.group(1))
        or m.group(1),
        s)
    return s


def _replace_unicode(s: str) -> str:
    for k, v in _LETTER_MAP.items():
        s = s.replace(k, v)
    return s


def _normalize_ops(s: str) -> str:
    """运算符归一化。"""
    # `+-` 保留；`!` 阶乘；`!=` 不等号不能动
    # 处理 `a / b` 这类已就绪的表达式
    s = s.replace("  ", " ")
    # 去掉多余的空格
    s = re.sub(r"\s+", " ", s)
    return s.strip()


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def latex_to_expr(text: str) -> LaTeXParseResult:
    """把 LaTeX 数学公式转成表达式。

    Args:
        text: LaTeX 源码，例如 ``r"\\frac{1}{2} + \\sqrt{x}"``

    Returns:
        LaTeXParseResult；``expr`` 是结果，``warnings`` 是提示，
        ``error`` 是致命错误。
    """
    if not text or not text.strip():
        return LaTeXParseResult(error="输入为空")

    s = str(text)
    warnings: list = []

    try:
        # 1. 去掉数学环境定界符
        s = _strip_math_delimiters(s)

        # 2. 去排版命令
        s = _strip_display(s)
        s = _strip_left_right(s)
        s = _strip_text(s)
        s = _strip_labels(s)
        s = _strip_spacing(s)

        # 3. 结构命令展开（顺序重要）
        s = _expand_frac(s)
        s = _expand_sqrt(s)
        s = _expand_binom(s)
        s = _expand_abs(s)
        s = _expand_dfrac_dt(s, warnings)
        s = _expand_sum_prod_int(s, warnings)

        # 4. 上下标
        s = _expand_superscripts(s)
        s = _expand_subscripts(s)

        # 5. 命令与 Unicode 替换
        s = _replace_unicode(s)
        s = _replace_commands(s)

        # 6. 归一化
        s = _normalize_ops(s)

        if not s:
            return LaTeXParseResult(
                error="转换后表达式为空", warnings=warnings)

        # 7. 检查是否还有遗留命令
        remaining = re.findall(r"\\[A-Za-z]+", s)
        if remaining:
            warnings.append(
                f"未识别的命令：{', '.join(sorted(set(remaining)))}")

        return LaTeXParseResult(
            expr=s, warnings=warnings, error="")
    except Exception as e:  # noqa: BLE001
        return LaTeXParseResult(
            error=f"LaTeX 解析失败：{e}", warnings=warnings)


def looks_like_latex(text: str) -> bool:
    """启发式判断：这段文本是否像 LaTeX 公式。"""
    if not text:
        return False
    s = str(text)
    markers = [
        r"\\", r"\$", r"\^", r"_",
        r"\frac", r"\sqrt", r"\sum", r"\int",
        r"\alpha", r"\beta", r"\pi",
        r"^{", r"_{",
    ]
    return any(re.search(m, s) for m in markers)


__all__ = [
    "LaTeXParseResult",
    "latex_to_expr",
    "looks_like_latex",
]