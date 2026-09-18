"""面板注册表：新增面板只需在这里加一行。

变更历史：
- 第 2 轮：工厂函数改为懒加载
- 第 5~18 轮：新增 pipeline / notebook / glyph / number_systems /
            data_ops / shortcuts 面板
- 第 16 轮：合并插件注册表（plugin_registry.panels()）
"""
from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from typing import Any, Callable


def _lazy(module_path: str, class_name: str):
    """返回一个延迟导入的工厂函数。"""
    def _factory(*args, **kwargs):
        mod = importlib.import_module(module_path)
        cls = getattr(mod, class_name)
        return cls(*args, **kwargs)
    return _factory


@dataclass
class PanelSpec:
    key: str
    group: str
    title_key: str
    title_default: str
    factory: Callable[[Any], Any]
    keywords: tuple = field(default_factory=tuple)


# ===========================================================================
# 内置面板
# ===========================================================================

def _builtin_panels() -> list:
    """返回全部内置面板规格（延迟导入）。"""
    return [
        # ---------------- 基础 ----------------
        PanelSpec("basic", "基础", "basic", "Basic",
                  lambda c: _lazy("ui.panels.basic", "BasicPanel")(
                      c.settings, c.i18n, c.history),
                  keywords=("calc", "arith", "percent",
                            "计算", "四则")),
        PanelSpec("scientific", "基础", "scientific", "Scientific",
                  lambda c: _lazy(
                      "ui.panels.scientific", "ScientificPanel")(
                      c.settings, c.i18n, c.history),
                  keywords=("sympy", "solve", "diff", "integrate",
                            "科学", "微积分")),
        # ---------------- 转换 ----------------
        PanelSpec("unit", "转换", "unit", "Unit Convert",
                  lambda c: _lazy("ui.panels.unit", "UnitPanel")(
                      c.settings, c.i18n, c.history),
                  keywords=("unit", "convert", "单位", "换算")),
        PanelSpec("currency", "转换", "currency", "Currency",
                  lambda c: _lazy(
                      "ui.panels.currency", "CurrencyPanel")(
                      c.base_path, c.settings, c.i18n, c.history),
                  keywords=("rate", "fx", "汇率", "货币")),
        PanelSpec("base", "转换", "base", "Base Convert",
                  lambda c: _lazy(
                      "ui.panels.base_convert", "BasePanel")(
                      c.settings, c.i18n, c.history),
                  keywords=("radix", "hex", "bin", "进制", "ascii")),
        PanelSpec("number_systems", "转换", "number_systems",
                  "Number Systems",
                  lambda c: _lazy(
                      "ui.panels.number_systems_panel",
                      "NumberSystemsPanel")(
                      c.settings, c.i18n, c.history),
                  keywords=("roman", "chinese", "english", "morse",
                            "数字", "罗马", "中文数字")),
        # ---------------- 数据 ----------------
        PanelSpec("stats", "数据", "stats", "Statistics",
                  lambda c: _lazy("ui.panels.stats", "StatsPanel")(
                      c.settings, c.i18n, c.history),
                  keywords=("stats", "mean", "median", "统计")),
        PanelSpec("probability", "数据", "prob", "Probability",
                  lambda c: _lazy(
                      "ui.panels.probability", "ProbabilityPanel")(
                      c.settings, c.i18n, c.history),
                  keywords=("dist", "pdf", "cdf", "ttest",
                            "概率", "贝叶斯")),
        PanelSpec("random", "数据", "random", "Random",
                  lambda c: _lazy(
                      "ui.panels.random_panel", "RandomPanel")(
                      c.settings, c.i18n, c.history),
                  keywords=("rand", "uuid", "password", "随机")),
        PanelSpec("data_table", "数据", "data_table", "Data Table",
                  lambda c: _lazy(
                      "ui.panels.data_table", "DataTablePanel")(
                      c.settings, c.i18n, c.history),
                  keywords=("table", "csv", "数据表", "公式")),
        PanelSpec("data_ops", "数据", "data_ops", "Data Ops",
                  lambda c: _lazy(
                      "ui.panels.data_ops_panel", "DataOpsPanel")(
                      c.settings, c.i18n, c.history),
                  keywords=("aggregate", "sort", "filter",
                            "数据运算", "聚合")),
        # ---------------- 数学 ----------------
        PanelSpec("matrix", "数学", "matrix", "Matrix",
                  lambda c: _lazy("ui.panels.matrix", "MatrixPanel")(
                      c.settings, c.i18n, c.history),
                  keywords=("matrix", "det", "eigen", "矩阵")),
        PanelSpec("plot", "数学", "plot", "Plot",
                  lambda c: _lazy("ui.panels.plot", "PlotPanel")(
                      c.settings, c.i18n, c.history),
                  keywords=("plot", "curve", "graph", "绘图")),
        PanelSpec("plot3d", "数学", "plot3d", "3D Plot",
                  lambda c: _lazy(
                      "ui.panels.plot3d", "Plot3DPanel")(
                      c.settings, c.i18n, c.history),
                  keywords=("surface", "3d", "3D")),
        PanelSpec("pipeline", "数学", "pipeline", "Pipeline",
                  lambda c: _lazy(
                      "ui.panels.pipeline_panel", "PipelinePanel")(
                      c.settings, c.i18n, c.history),
                  keywords=("pipe", "workflow", "管道", "工作流")),
        # ---------------- 财务 ----------------
        PanelSpec("finance", "财务", "finance", "Finance",
                  lambda c: _lazy(
                      "ui.panels.finance", "FinancePanel")(
                      c.settings, c.i18n, c.history),
                  keywords=("loan", "npv", "irr", "bond", "财务")),
        PanelSpec("date", "财务", "date", "Date",
                  lambda c: _lazy("ui.panels.date", "DatePanel")(
                      c.settings, c.i18n, c.history),
                  keywords=("date", "time", "日期", "农历")),
        # ---------------- 工具 ----------------
        PanelSpec("bits", "工具", "bits", "Bits",
                  lambda c: _lazy("ui.panels.bits", "BitsPanel")(
                      c.settings, c.i18n, c.history),
                  keywords=("bit", "crc", "hash", "位")),
        PanelSpec("crypto_tools", "工具", "crypto_tools",
                  "Crypto Tools",
                  lambda c: _lazy(
                      "ui.panels.crypto_tools", "CryptoPanel")(
                      c.settings, c.i18n, c.history),
                  keywords=("aes", "rsa", "totp", "pqc", "加密", "哈希")),
        PanelSpec("latex", "工具", "latex_editor", "LaTeX Editor",
                  lambda c: _lazy(
                      "ui.panels.latex_editor", "LatexEditorPanel")(
                      c.settings, c.i18n, c.history),
                  keywords=("latex", "formula", "公式")),
        PanelSpec("tools", "工具", "tools", "Tools",
                  lambda c: _lazy("ui.panels.tools", "ToolsPanel")(
                      c.settings, c.i18n, c.history),
                  keywords=("qr", "jwt", "regex", "color", "工具")),
        PanelSpec("glyph", "工具", "glyph", "Symbols",
                  lambda c: _lazy(
                      "ui.panels.glyph_panel", "GlyphPanel")(
                      c.settings, c.i18n, c.history),
                  keywords=("symbol", "unicode", "latex",
                            "符号", "字典", "希腊")),
        # ---------------- 生产力 ----------------
        PanelSpec("snippets", "生产力", "snippets", "Snippets",
                  lambda c: _lazy(
                      "ui.panels.snippets", "SnippetsPanel")(
                      c.settings, c.i18n, c.history),
                  keywords=("snippet", "片段", "收藏")),
        PanelSpec("timer", "生产力", "timer", "Timer",
                  lambda c: _lazy(
                      "ui.panels.timer_panel", "TimerPanel")(
                      c.settings, c.i18n, c.history),
                  keywords=("timer", "countdown", "计时")),
        PanelSpec("clipboard_history", "生产力",
                  "clipboard_history", "Clipboard",
                  lambda c: _lazy(
                      "ui.panels.clipboard_history",
                      "ClipboardHistoryPanel")(
                      c.settings, c.i18n, c.history),
                  keywords=("clip", "history", "剪贴板")),
        PanelSpec("script", "生产力", "script", "Script",
                  lambda c: _lazy(
                      "ui.panels.script", "ScriptPanel")(
                      c.settings, c.i18n, c.history),
                  keywords=("script", "batch", "脚本")),
        PanelSpec("notebook", "生产力", "notebook", "Notebook",
                  lambda c: _lazy(
                      "ui.panels.notebook_panel",
                      "NotebookPanel")(
                      c.settings, c.i18n, c.history),
                  keywords=("notebook", "jupyter", "笔记本", "cell")),
        # ---------------- AI ----------------
        PanelSpec("ai", "AI", "ai", "AI Assistant",
                  lambda c: _lazy("ui.panels.ai", "AIPanel")(
                      c.settings, c.i18n, c.history),
                  keywords=("ai", "llm", "ollama", "openai",
                            "自然语言")),
        # ---------------- 系统 ----------------
        PanelSpec("history", "系统", "history", "History",
                  lambda c: _make_history(c),
                  keywords=("history", "历史")),
        PanelSpec("settings", "系统", "settings", "Settings",
                  lambda c: _lazy(
                      "ui.panels.settings", "SettingsPanel")(
                      c.settings, c.i18n, c.main_window),
                  keywords=("settings", "pref", "设置")),
        PanelSpec("shortcuts", "系统", "shortcuts", "Shortcuts",
                  lambda c: _lazy(
                      "ui.panels.shortcut_settings_panel",
                      "ShortcutSettingsPanel")(
                      c.settings, c.i18n, c.history),
                  keywords=("shortcut", "key", "快捷键", "键位")),
    ]


def _make_history(ctx):
    from ui.panels.history import HistoryPanel
    panel = HistoryPanel(ctx.history, ctx.i18n)
    panel.set_reuse_handler(ctx.reuse_handler)
    return panel


# ===========================================================================
# 插件面板
# ===========================================================================

def _plugin_panels() -> list:
    """从运行时注册表拉取插件注册的面板。

    插件的 PanelPlugin 子类通过 @register_panel 装饰器注册。
    这里把它们的 cls 包装成 PanelSpec。
    """
    try:
        from core import plugin_registry as reg_mod
        records = reg_mod.get_registry().panels()
    except Exception:
        return []

    out = []
    for rec in records:
        try:
            cls = rec.cls
            spec = PanelSpec(
                key=getattr(cls, "key", ""),
                group=getattr(cls, "group", "插件"),
                title_key=getattr(cls, "title_key", "")
                or getattr(cls, "key", ""),
                title_default=getattr(cls, "title_default", "")
                or getattr(cls, "key", ""),
                factory=_make_plugin_factory(cls),
                keywords=tuple(getattr(cls, "keywords", ()) or ()),
            )
            if spec.key:
                out.append(spec)
        except Exception:
            continue
    return out


def _make_plugin_factory(cls):
    """把插件面板类包装为工厂函数。"""
    def _factory(ctx):
        instance = cls()
        # 插件面板可能不需要 settings/i18n/history，但我们尽量注入
        for attr, value in (
                ("settings", ctx.settings),
                ("i18n", ctx.i18n),
                ("history", ctx.history),
                ("base_path", getattr(ctx, "base_path", "")),
                ("main_window", ctx.main_window)):
            try:
                if not hasattr(instance, attr):
                    setattr(instance, attr, value)
            except Exception:
                pass
        return instance.create_widget({
            "settings": ctx.settings,
            "i18n": ctx.i18n,
            "history": ctx.history,
            "main_window": ctx.main_window,
            "base_path": getattr(ctx, "base_path", ""),
        })
    return _factory


# ===========================================================================
# 主入口
# ===========================================================================

def all_panels() -> list:
    """返回全部面板规格（内置 + 插件）。"""
    specs = _builtin_panels()
    # 合并插件面板（按 key 去重，内置优先）
    seen = {s.key for s in specs}
    for s in _plugin_panels():
        if s.key and s.key not in seen:
            specs.append(s)
            seen.add(s.key)
    return specs


def all_keywords() -> dict:
    """返回 {key: keywords}，供命令面板 / 侧边栏搜索使用。"""
    return {spec.key: tuple(spec.keywords)
            for spec in all_panels()}


__all__ = ["PanelSpec", "all_panels", "all_keywords"]