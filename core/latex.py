"""LaTeX 渲染 + 解析。

合并自：core/latex_ext.py + core/latex_parser.py

对外接口：
    # 渲染
    TEMPLATES, render_png, render_svg, render_bytes
    # 解析
    LaTeXParseResult, latex_to_expr, looks_like_latex
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass, field

__all__ = [
    "TEMPLATES", "render_png", "render_svg", "render_bytes",
    "LaTeXParseResult", "latex_to_expr", "looks_like_latex",
]


# ===========================================================================
# 模板库
# ===========================================================================

TEMPLATES = {
    "quadratic":   r"x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}",
    "binomial":    r"(a + b)^n = \sum_{k=0}^{n} \binom{n}{k} a^{n-k} b^k",
    "euler":       r"e^{i\pi} + 1 = 0",
    "gauss":       r"\int_{-\infty}^{\infty} e^{-x^2}\,dx = \sqrt{\pi}",
    "taylor":      r"f(x) = \sum_{n=0}^{\infty} \frac{f^{(n)}(a)}{n!}(x-a)^n",
    "derivative":  r"\frac{d}{dx} f(x) = \lim_{h\to 0}\frac{f(x+h)-f(x)}{h}",
    "integral":    r"\int_a^b f(x)\,dx = F(b) - F(a)",
    "ft":          (r"\hat{f}(\xi) = \int_{-\infty}^{\infty} "
                    r"f(x) e^{-2\pi i x \xi}\,dx"),
    "matrix_2x2":  r"\begin{pmatrix} a & b \\ c & d \end{pmatrix}",
    "determinant": (r"\det(A) = \sum_{\sigma \in S_n} "
                    r"\mathrm{sgn}(\sigma) \prod_{i=1}^{n} "
                    r"a_{i,\sigma(i)}"),
    "maxwell":     r"\nabla \cdot \mathbf{E} = \frac{\rho}{\varepsilon_0}",
    "schrodinger": r"i\hbar\frac{\partial}{\partial t}\Psi = \hat{H}\Psi",
    "einstein":    r"E = mc^2",
    "bayes":       (r"P(A\mid B) = \frac{P(B\mid A)P(A)}{P(B)}"),
    "normal_dist": (r"f(x) = \frac{1}{\sigma\sqrt{2\pi}} "
                    r"e^{-\frac{(x-\mu)^2}{2\sigma^2}}"),
    "cauchy":      (r"\left|\sum_{i=1}^{n} a_i b_i\right|^2 \leq "
                    r"\sum_{i=1}^{n} a_i^2 \sum_{i=1}^{n} b_i^2"),
}


# ===========================================================================
# 渲染
# ===========================================================================

def render_png(latex: str, path: str, fontsize: int = 18,
               dpi: int = 200, color: str = "#000000",
               transparent: bool = False) -> str:
    """渲染 LaTeX 到 PNG。"""
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg

    fig = Figure(figsize=(0.01, 0.01), dpi=dpi)
    if transparent:
        fig.patch.set_alpha(0.0)
    else:
        fig.patch.set_facecolor("white")
    try:
        fig.text(0, 0, f"${latex}$", fontsize=fontsize, color=color)
    except Exception as e:  # noqa: BLE001
        raise ValueError(f"LaTeX 渲染失败：{e}") from e
    FigureCanvasAgg(fig)
    fig.savefig(path, format="png", bbox_inches="tight",
                pad_inches=0.1, dpi=dpi, transparent=transparent)
    fig.clear()
    return path


def render_svg(latex: str, path: str, fontsize: int = 18,
               color: str = "#000000") -> str:
    """渲染 LaTeX 到 SVG。"""
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_svg import FigureCanvasSVG

    fig = Figure(figsize=(0.01, 0.01))
    fig.patch.set_facecolor("white")
    try:
        fig.text(0, 0, f"${latex}$", fontsize=fontsize, color=color)
    except Exception as e:  # noqa: BLE001
        raise ValueError(f"LaTeX 渲染失败：{e}") from e
    FigureCanvasSVG(fig)
    fig.savefig(path, format="svg", bbox_inches="tight",
                pad_inches=0.1)
    fig.clear()
    return path


def render_bytes(latex: str, fontsize: int = 18, dpi: int = 200,
                 color: str = "#000000") -> bytes | None:
    """返回 PNG 字节（透明背景）。失败返回 None。"""
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg

    fig = Figure(figsize=(0.01, 0.01), dpi=dpi)
    fig.patch.set_alpha(0.0)
    try:
        fig.text(0, 0, f"${latex}$", fontsize=fontsize, color=color)
    except Exception:
        fig.clear()
        return None
    buf = io.BytesIO()
    try:
        FigureCanvasAgg(fig)
        fig.savefig(buf, format="png", bbox_inches="tight",
                    pad_inches=0.08, transparent=True, dpi=dpi)
    except Exception:
        return None
    finally:
        fig.clear()
    return buf.getvalue()


# ===========================================================================
# 解析
# ===========================================================================

@dataclass
class LaTeXParseResult:
    expr: str = ""
    warnings: list = field(default_factory=list)
    error: str = ""

    @property
    def ok(self) -> bool:
        return not self.error


_GREEK = {
    "alpha": "alpha", "beta": "beta", "gamma": "gamma",
    "delta": "delta", "epsilon": "epsilon",
    "varepsilon": "epsilon", "zeta": "zeta", "eta": "eta",
    "theta": "theta", "vartheta": "theta", "iota": "iota",
    "kappa": "kappa", "lambda": "lambda_", "mu": "mu", "nu": "nu",
    "xi": "xi", "omicron": "omicron", "pi": "pi", "varpi": "pi",
    "rho": "rho", "varrho": "rho", "sigma": "sigma",
    "varsigma": "sigma", "tau": "tau", "upsilon": "upsilon",
    "phi": "phi", "varphi": "phi", "chi": "chi",
    "psi": "psi", "omega": "omega",
    "Gamma": "Gamma", "Delta": "Delta", "Theta": "Theta",
    "Lambda": "Lambda_", "Xi": "Xi", "Pi": "Pi",
    "Sigma": "Sigma", "Upsilon": "Upsilon", "Phi": "Phi",
    "Psi": "Psi", "Omega": "Omega",
}

_SIMPLE_CMDS = {
    "infty": "oo", "infinity": "oo",
    "partial": "Partial", "nabla": "nabla",
    "cdot": "*", "times": "*", "div": "/",
    "pm": "±", "mp": "∓",
    "leq": "<=", "le": "<=",
    "geq": ">=", "ge": ">=",
    "neq": "!=", "ne": "!=",
    "approx": "≈", "sim": "~",
    "equiv": "==", "to": "->", "rightarrow": "->",
    "leftarrow": "<-", "Rightarrow": "=>",
    "Leftrightarrow": "<=>",
    "sin": "sin", "cos": "cos", "tan": "tan",
    "cot": "cot", "sec": "sec", "csc": "csc",
    "arcsin": "asin", "arccos": "acos", "arctan": "atan",
    "sinh": "sinh", "cosh": "cosh", "tanh": "tanh",
    "log": "log", "ln": "log", "lg": "log10",
    "exp": "exp", "max": "Max", "min": "Min",
    "lim": "limit", "gcd": "gcd", "lcm": "lcm",
    "det": "det",
    "quad": " ", "qquad": "  ",
    ",": " ", ";": " ", ":": " ", "!": "", " ": " ",
}

_LETTER_MAP = {
    "≤": "<=", "≥": ">=", "≠": "!=",
    "×": "*", "÷": "/",
    "−": "-", "–": "-", "—": "-",
    "∞": "oo", "π": "pi", "θ": "theta",
    "±": "+-", "∓": "-+",
    "√": "sqrt",
    "∫": "Integral", "∑": "Sum", "∏": "Product",
}


def _strip_math_delimiters(s: str) -> str:
    s = s.strip()
    s = re.sub(r"^\s*\$\$(.+)\$\$\s*$", r"\1", s, flags=re.DOTALL)
    s = re.sub(r"^\s*\$(.+)\$\s*$", r"\1", s, flags=re.DOTALL)
    s = re.sub(r"^\s*\\\((.+)\\\)\s*$", r"\1", s, flags=re.DOTALL)
    s = re.sub(r"^\s*\\\[(.+)\\\]\s*$", r"\1", s, flags=re.DOTALL)
    return s


def _strip_spacing(s: str) -> str:
    s = re.sub(r"\\[,;:!]", " ", s)
    s = re.sub(r"\\quad\b", " ", s)
    s = re.sub(r"\\qquad\b", "  ", s)
    return s


def _strip_text(s: str) -> str:
    for cmd in ("text", "mathrm", "mathbf", "mathit", "mathsf",
                "mathtt", "operatorname", "mbox", "hbox"):
        s = re.sub(rf"\\{cmd}\s*\{{([^{{}}]*)\}}", r"\1", s)
    return s


def _strip_display(s: str) -> str:
    for cmd in ("displaystyle", "limits", "nolimits",
                "textstyle", "scriptstyle", "small"):
        s = re.sub(rf"\\{cmd}\b", " ", s)
    return s


def _strip_left_right(s: str) -> str:
    s = re.sub(
        r"\\(?:left|right|big|Big|bigg|Bigg|bigl|bigr|Bigl|Bigr)\b",
        " ", s)
    return s


def _strip_labels(s: str) -> str:
    s = re.sub(r"\\label\s*\{[^}]*\}", "", s)
    s = re.sub(r"\\tag\s*\{[^}]*\}", "", s)
    s = re.sub(r"\\nonumber\b", "", s)
    return s


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
        if (s.startswith(r"\frac", i)
                or s.startswith(r"\dfrac", i)
                or s.startswith(r"\tfrac", i)):
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
        if (s.startswith(r"\binom", i)
                or s.startswith(r"\dbinom", i)):
            k = i + 6
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
    """`\\left|...\\right|` / `|...|` → `Abs(...)`。"""
    s = re.sub(
        r"\\left\s*\|\s*(.+?)\s*\\right\s*\|",
        r"Abs(\1)", s, flags=re.DOTALL)
    s = re.sub(r"\|([^|]+)\|", r"Abs(\1)", s)
    return s


def _expand_sum_prod_int(s: str, warnings: list) -> str:
    """求和 / 求积 / 积分：转成可读注释，不实际展开。"""

    def _repl_sum(m):
        lower = m.group(1)
        upper = m.group(2)
        body = m.group(3).strip()
        return f"Sum({body}, {_parse_bounds(lower, upper)})"

    s = re.sub(
        r"\\sum\s*_\s*\{([^}]*)\}\s*\^\s*\{([^}]*)\}"
        r"\s*([^\\]*?)(?=\\|$)",
        _repl_sum, s)

    def _repl_prod(m):
        lower = m.group(1)
        upper = m.group(2)
        body = m.group(3).strip()
        return f"Product({body}, {_parse_bounds(lower, upper)})"

    s = re.sub(
        r"\\prod\s*_\s*\{([^}]*)\}\s*\^\s*\{([^}]*)\}"
        r"\s*([^\\]*?)(?=\\|$)",
        _repl_prod, s)

    if re.search(r"\\int\b", s):
        warnings.append(
            "检测到 \\int，已转为 Integral(...) 占位，"
            "请手动补齐被积函数与变量")

    return s


def _parse_bounds(lower: str, upper: str) -> str:
    m = re.match(r"^\s*([A-Za-z_]\w*)\s*=\s*(.+)$", lower)
    if m:
        var, lo = m.group(1), m.group(2).strip()
        return f"({var}, {lo}, {upper.strip()})"
    return f"(_, {lower.strip()}, {upper.strip()})"


def _expand_superscripts(s: str) -> str:
    s = re.sub(r"\^\s*\{([^{}]*)\}", r"**(\1)", s)
    s = re.sub(r"\^\s*([0-9A-Za-z_])", r"**\1", s)
    return s


def _expand_subscripts(s: str) -> str:
    def _repl(m):
        body = m.group(1)
        if re.match(r"^[A-Za-z0-9]+$", body):
            return f"_{body}"
        return f"_{body}"

    return re.sub(r"_\s*\{([^{}]*)\}", _repl, s)


def _expand_dfrac_dt(s: str, warnings: list) -> str:
    if re.search(r"\\frac\s*\{\s*d\s*\}\s*\{\s*d\s*([A-Za-z])\s*\}",
                 s):
        warnings.append(
            "检测到导数记号 d/dx，已转为 diff(...) 占位，"
            "请手动补齐表达式")
        s = re.sub(
            r"\\frac\s*\{\s*d\s*\}\s*\{\s*d\s*([A-Za-z])\s*\}",
            r"diff(?, \1)", s)
    return s


def _replace_commands(s: str) -> str:
    return re.sub(
        r"\\([A-Za-z]+)\b",
        lambda m: (_SIMPLE_CMDS.get(m.group(1))
                   or _GREEK.get(m.group(1))
                   or m.group(1)),
        s)


def _replace_unicode(s: str) -> str:
    for k, v in _LETTER_MAP.items():
        s = s.replace(k, v)
    return s


def _normalize_ops(s: str) -> str:
    s = s.replace("  ", " ")
    s = re.sub(r"\s+", " ", s)
    return s.strip()


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
        s = _strip_math_delimiters(s)
        s = _strip_display(s)
        s = _strip_left_right(s)
        s = _strip_text(s)
        s = _strip_labels(s)
        s = _strip_spacing(s)

        s = _expand_frac(s)
        s = _expand_sqrt(s)
        s = _expand_binom(s)
        s = _expand_abs(s)
        s = _expand_dfrac_dt(s, warnings)
        s = _expand_sum_prod_int(s, warnings)

        s = _expand_superscripts(s)
        s = _expand_subscripts(s)

        s = _replace_unicode(s)
        s = _replace_commands(s)
        s = _normalize_ops(s)

        if not s:
            return LaTeXParseResult(
                error="转换后表达式为空", warnings=warnings)

        remaining = re.findall(r"\\[A-Za-z]+", s)
        if remaining:
            warnings.append(
                f"未识别的命令："
                f"{', '.join(sorted(set(remaining)))}")

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