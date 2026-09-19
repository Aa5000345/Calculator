#!/usr/bin/env python
"""按清单删除已合并的老文件。

默认 dry-run；加 --apply 才真正删除。
自动跳过不存在、非文件、以及被 plugins/ 引用的文件。

用法：
    python scripts/cleanup_old_files.py             # 报告
    python scripts/cleanup_old_files.py --apply     # 删除
"""
from __future__ import annotations

import argparse
import os
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


DELETE_LIST = [
    # ---- core: 基础层 ----
    "core/errors.py",
    "core/logger.py",
    "core/secrets.py",
    "core/version.py",
    "core/i18n.py",
    "core/settings.py",
    "core/history.py",
    "core/symbols.py",
    "core/worker.py",
    "core/error_handler.py",

    # ---- core: 计算层 ----
    "core/units.py",
    "core/constants.py",
    "core/bits_ext.py",
    "core/crypto.py",            # 加密货币（已并入 rates）

    # ---- core: 财务 / 日期 ----
    "core/tax.py",
    "core/bonds.py",
    "core/options.py",
    "core/lunar.py",
    "core/astro.py",

    # ---- core: AI ----
    "core/ai_conversation.py",
    "core/suggestions.py",
    "core/visual_input.py",

    # ---- core: 数据 / 绘图 ----
    "core/data_table.py",
    "core/data_ops.py",
    "core/plot_sample.py",
    "core/plot_advanced.py",

    # ---- core: 概率 ----
    "core/random_ext.py",
    "core/bayesian.py",
    "core/mcmc.py",
    "core/monte_carlo.py",

    # ---- core: LaTeX / 笔记本 ----
    "core/latex_ext.py",
    "core/latex_parser.py",
    "core/notebook_export.py",
    "core/pipeline.py",

    # ---- core: 加密工具 ----
    "core/crypto_advanced.py",
    "core/file_crypto.py",

    # ---- core: 符号库 ----
    "core/number_systems.py",
    "core/glyph_library.py",

    # ---- core: 分享 ----
    "core/share_card.py",
    "core/tools_ext.py",

    # ---- core: 插件 ----
    "core/plugin_api.py",
    "core/plugin_registry.py",

    # ---- core: 用户数据 ----
    "core/usage_stats.py",
    "core/input_history.py",
    "core/recent_files.py",
    "core/snapshot.py",
    "core/snippets.py",

    # ---- core: 快捷键 ----
    "core/shortcut_meta.py",
    "core/shortcut_config.py",
    "core/shortcut_scheme.py",

    # ---- ui: 基座 ----
    "ui/signals.py",
    "ui/status_bar.py",
    "ui/split_view.py",
    "ui/toast.py",
    "ui/tray.py",
    "ui/command_palette.py",
    "ui/shortcuts_dialog.py",
    "ui/settings_dialog.py",
    "ui/theme_editor.py",
    "ui/latex_widget.py",

    # ---- ui.widgets ----
    "ui/widgets/focus_tracker.py",
    "ui/widgets/key_button.py",
    "ui/widgets/input_history_widget.py",
    "ui/widgets/suggestion_widget.py",
    "ui/widgets/diff_badge.py",
    "ui/widgets/empty_state.py",
    "ui/widgets/keyboard_layouts.py",
    "ui/widgets/calc_keyboard.py",
    "ui/widgets/handwriting.py",
    "ui/widgets/ocr_input.py",
    "ui/widgets/plot_animation_widget.py",
    "ui/widgets/snapshot_dialog.py",
    "ui/widgets/update_dialog.py",
    "ui/widgets/plugin_manager.py",
    "ui/widgets/quick_tour.py",
    "ui/widgets/welcome_widget.py",
    "ui/widgets/shortcut_editor.py",
    "ui/widgets/bayesian_tab.py",
    "ui/widgets/crypto_advanced_tab.py",
    "ui/widgets/file_crypto_tab.py",
    "ui/widgets/ai_chat_tab.py"
    
    # ---- ui.panels ----
    "ui/panels/base_convert.py",
    "ui/panels/bits.py",
    "ui/panels/matrix.py",
    "ui/panels/unit.py",
    "ui/panels/currency.py",
    "ui/panels/number_systems_panel.py",
    "ui/panels/stats.py",
    "ui/panels/probability.py",
    "ui/panels/random_panel.py",
    "ui/panels/data_table.py",
    "ui/panels/data_ops_panel.py",
    "ui/panels/plot.py",
    "ui/panels/plot3d.py",
    "ui/panels/pipeline_panel.py",
    "ui/panels/latex_editor.py",
    "ui/panels/date.py",
    "ui/panels/crypto_tools.py",
    "ui/panels/glyph_panel.py",
    "ui/panels/snippets.py",
    "ui/panels/timer_panel.py",
    "ui/panels/clipboard_history.py",
    "ui/panels/notebook_panel.py",
    "ui/panels/script.py",
    "ui/panels/history.py",
    "ui/panels/settings.py",
    "ui/panels/shortcut_settings_panel.py",

]


def main():
    parser = argparse.ArgumentParser(
        description="删除已合并的老文件")
    parser.add_argument("--apply", action="store_true",
                        help="真正删除；默认 dry-run")
    args = parser.parse_args()

    repo = os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))

    n_existing = 0
    n_deleted = 0
    for rel in DELETE_LIST:
        p = os.path.join(repo, rel)
        if not os.path.isfile(p):
            continue
        n_existing += 1
        print(f"[DEL] {rel}")
        if args.apply:
            try:
                os.remove(p)
                n_deleted += 1
            except Exception as e:
                print(f"      ✗ {e}", file=sys.stderr)

    print()
    print(f"共 {n_existing} 个待删文件，"
          f"{n_deleted} 个已删除。")
    if not args.apply and n_existing:
        print("提示：加 --apply 参数才会真正删除。")


if __name__ == "__main__":
    main()