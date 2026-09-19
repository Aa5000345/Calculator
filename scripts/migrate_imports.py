#!/usr/bin/env python
"""批量把老的 import 路径改写为合并后的路径。

用法：
    python scripts/migrate_imports.py             # dry-run，只报告
    python scripts/migrate_imports.py --apply     # 真正改写
    python scripts/migrate_imports.py --path core # 只处理某个目录

退出码：
    0 —— 全部处理完成
    1 —— 有待处理项（dry-run 时）或发生错误
"""
from __future__ import annotations

import argparse
import os
import re
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# 路径映射表（老 → 新）
# ---------------------------------------------------------------------------
MAPPING = {
    # ---- core: 基础层合并 ----
    "core.errors":         "core.base",
    "core.logger":         "core.base",
    "core.secrets":        "core.base",
    "core.version":        "core.base",
    "core.i18n":           "core.state",
    "core.settings":       "core.state",
    "core.history":        "core.state",
    "core.symbols":        "core.state",
    "core.worker":         "core.runtime",
    "core.error_handler":  "core.runtime",

    # ---- core: 计算层 ----
    "core.units":          "core.engine",
    "core.constants":      "core.engine",
    "core.bits_ext":       "core.bits",
    "core.crypto":         "core.rates",     # 加密货币

    # ---- core: 财务 / 日期 ----
    "core.tax":            "core.finance",
    "core.bonds":          "core.finance",
    "core.options":        "core.finance",
    "core.lunar":          "core.dates",
    "core.astro":          "core.dates",

    # ---- core: AI ----
    "core.ai_conversation": "core.ai",
    "core.suggestions":     "core.ai",
    "core.visual_input":    "core.ai",

    # ---- core: 数据 / 绘图 ----
    "core.data_table":      "core.data",
    "core.data_ops":        "core.data",
    "core.plot_sample":     "core.plot",
    "core.plot_advanced":   "core.plot",

    # ---- core: 概率 ----
    "core.random_ext":      "core.probability",
    "core.bayesian":        "core.probability",
    "core.mcmc":            "core.probability",
    "core.monte_carlo":     "core.probability",

    # ---- core: LaTeX / 笔记本 ----
    "core.latex_ext":       "core.latex",
    "core.latex_parser":    "core.latex",
    "core.notebook_export": "core.notebook",
    "core.pipeline":        "core.notebook",

    # ---- core: 加密工具 ----
    "core.crypto_advanced": "core.crypto_tools",
    "core.file_crypto":     "core.crypto_tools",

    # ---- core: 符号库 / 数字系统 ----
    "core.number_systems":  "core.symbols_lib",
    "core.glyph_library":   "core.symbols_lib",

    # ---- core: 分享 / 工具 ----
    "core.share_card":      "core.share",
    "core.tools_ext":       "core.share",

    # ---- core: 插件 ----
    "core.plugin_api":      "core.plugins",
    "core.plugin_registry": "core.plugins",

    # ---- core: 用户数据 ----
    "core.usage_stats":     "core.user_data",
    "core.input_history":   "core.user_data",
    "core.recent_files":    "core.user_data",
    "core.snapshot":        "core.user_data",
    "core.snippets":        "core.user_data",

    # ---- core: 快捷键 ----
    "core.shortcut_meta":   "core.shortcuts",
    "core.shortcut_config": "core.shortcuts",
    "core.shortcut_scheme": "core.shortcuts",

    # ---- ui: 基座 ----
    "ui.signals":           "ui.shell",
    "ui.status_bar":        "ui.shell",
    "ui.split_view":        "ui.shell",
    "ui.toast":             "ui.shell",
    "ui.tray":              "ui.shell",
    "ui.command_palette":   "ui.dialogs",
    "ui.shortcuts_dialog":  "ui.dialogs",
    "ui.settings_dialog":   "ui.dialogs",
    "ui.theme_editor":      "ui.dialogs",
    "ui.latex_widget":      "ui.dialogs",

    # ---- ui.widgets ----
    "ui.widgets.focus_tracker":       "ui.widgets.input",
    "ui.widgets.key_button":          "ui.widgets.input",
    "ui.widgets.input_history_widget": "ui.widgets.input",
    "ui.widgets.suggestion_widget":   "ui.widgets.input",
    "ui.widgets.diff_badge":          "ui.widgets.input",
    "ui.widgets.empty_state":         "ui.widgets.input",
    "ui.widgets.keyboard_layouts":    "ui.widgets.keyboard",
    "ui.widgets.calc_keyboard":       "ui.widgets.keyboard",
    "ui.widgets.handwriting":         "ui.widgets.tools",
    "ui.widgets.ocr_input":           "ui.widgets.tools",
    "ui.widgets.plot_animation_widget": "ui.widgets.tools",
    "ui.widgets.snapshot_dialog":     "ui.widgets.dialogs",
    "ui.widgets.update_dialog":       "ui.widgets.dialogs",
    "ui.widgets.plugin_manager":      "ui.widgets.dialogs",
    "ui.widgets.quick_tour":          "ui.widgets.dialogs",
    "ui.widgets.welcome_widget":      "ui.widgets.dialogs",
    "ui.widgets.shortcut_editor":     "ui.widgets.dialogs",
    "ui.widgets.bayesian_tab":        "ui.panels.data",
    "ui.widgets.crypto_advanced_tab": "ui.panels.tools",
    "ui.widgets.file_crypto_tab":     "ui.panels.tools",

    # ---- ui.panels ----
    "ui.panels.base_convert":         "ui.panels.basic",
    "ui.panels.bits":                 "ui.panels.basic",
    "ui.panels.matrix":               "ui.panels.scientific",
    "ui.panels.unit":                 "ui.panels.convert",
    "ui.panels.currency":             "ui.panels.convert",
    "ui.panels.number_systems_panel": "ui.panels.convert",
    "ui.panels.stats":                "ui.panels.data",
    "ui.panels.probability":          "ui.panels.data",
    "ui.panels.random_panel":         "ui.panels.data",
    "ui.panels.data_table":           "ui.panels.data",
    "ui.panels.data_ops_panel":       "ui.panels.data",
    "ui.panels.plot":                 "ui.panels.math",
    "ui.panels.plot3d":               "ui.panels.math",
    "ui.panels.pipeline_panel":       "ui.panels.math",
    "ui.panels.latex_editor":         "ui.panels.math",
    "ui.panels.date":                 "ui.panels.finance",
    "ui.panels.crypto_tools":         "ui.panels.tools",
    "ui.panels.glyph_panel":          "ui.panels.tools",
    "ui.panels.snippets":             "ui.panels.tools",
    "ui.panels.timer_panel":          "ui.panels.productivity",
    "ui.panels.clipboard_history":    "ui.panels.productivity",
    "ui.panels.notebook_panel":       "ui.panels.productivity",
    "ui.panels.script":               "ui.panels.productivity",
    "ui.panels.history":              "ui.panels.system",
    "ui.panels.settings":             "ui.panels.system",
    "ui.panels.shortcut_settings_panel": "ui.panels.system",
}


# 需要人工复核的函数名变化（脚本只警告，不改）
_NAME_CHANGE_HINTS = {
    "core.secrets":      "get → secret_get；set → secret_set",
    "core.version":      "parse → parse_version；is_newer 保留",
    "core.symbols":      "clear → clear_symbols；export/import 变名",
    "core.usage_stats":  "bump → usage_bump；score → usage_score",
    "core.input_history": "record → input_record；list_versions → input_list_versions",
    "core.recent_files": "add → recent_add；list_all → recent_list_all",
    "core.snippets":     "load → snippet_load；add → snippet_add",
    "core.snapshot":     "get_manager → get_snapshot_manager",
    "core.tools_ext":    "（无变化，函数名保留）",
}


FROM_RE = re.compile(r"^(\s*)from\s+([\w.]+)\s+import\s+(.+?)\s*$")
IMPORT_RE = re.compile(r"^(\s*)import\s+([\w.]+)(\s+as\s+\w+)?\s*$")


def rewrite_line(line: str, warnings: list, path: str):
    m = FROM_RE.match(line)
    if m:
        indent, mod, rest = m.groups()
        if mod in MAPPING:
            new_mod = MAPPING[mod]
            warnings.append(
                f"{path}: {mod} → {new_mod}"
                + (f"  ⚠ {_NAME_CHANGE_HINTS[mod]}"
                   if mod in _NAME_CHANGE_HINTS else ""))
            return f"{indent}from {new_mod} import {rest}"

    m = IMPORT_RE.match(line)
    if m:
        indent, mod, alias = m.groups()
        if mod in MAPPING:
            new_mod = MAPPING[mod]
            warnings.append(
                f"{path}: {mod} → {new_mod}"
                + (f"  ⚠ {_NAME_CHANGE_HINTS[mod]}"
                   if mod in _NAME_CHANGE_HINTS else ""))
            return f"{indent}import {new_mod}{alias or ''}"

    return line


def process_file(path: str, apply: bool, warnings: list):
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception:
        return False

    new_lines = []
    changed = False
    for line in lines:
        new = rewrite_line(line, warnings, path)
        if new != line:
            changed = True
        new_lines.append(new)

    if changed and apply:
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.writelines(new_lines)
        except Exception as e:
            print(f"[ERROR] 写入失败 {path}: {e}",
                  file=sys.stderr)
    return changed


def iter_py_files(root: str):
    skip_dirs = {"__pycache__", ".git", ".venv", "venv",
                 "build", "dist", ".mypy_cache"}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames
                       if d not in skip_dirs]
        for fn in filenames:
            if fn.endswith(".py"):
                yield os.path.join(dirpath, fn)


def main():
    parser = argparse.ArgumentParser(
        description="批量改写 import 路径")
    parser.add_argument("--apply", action="store_true",
                        help="真正写入；默认 dry-run")
    parser.add_argument("--path", default=None,
                        help="只处理指定目录（默认整仓库）")
    args = parser.parse_args()

    repo = os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))
    root = args.path or repo

    warnings: list = []
    n_changed = 0
    n_total = 0
    for p in iter_py_files(root):
        n_total += 1
        if process_file(p, args.apply, warnings):
            n_changed += 1

    if warnings:
        print(f"\n发现 {len(warnings)} 处需要改写：")
        for w in warnings:
            print(f"  {w}")
        print()
    else:
        print("没有需要改写的 import。")

    print(f"扫描 {n_total} 个文件，"
          f"{n_changed} 个文件有改动。")
    if not args.apply and n_changed:
        print("\n提示：加 --apply 参数才会真正写入。")


if __name__ == "__main__":
    main()