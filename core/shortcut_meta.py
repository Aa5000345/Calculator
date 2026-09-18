"""快捷键元数据：所有可自定义命令的描述 / 默认键位 / 分组 / 作用域。

设计：
- 命令 ID 稳定不变（`global.xxx` / `panel.xxx` / `nav.xxx`）
- 分组用于 UI 折叠 / 分类
- 作用域用于冲突检测：
    - `global`    全局快捷键（App 级）
    - `panel`     面板级（面板获得焦点时生效）
    - `widget`    输入框内（输入框获得焦点时生效）
- 系统冲突警告：某些组合键在 OS 层面被占用，警告但不禁用

对外接口：
    all_metas() -> list[ShortcutMeta]
    get_meta(id) -> ShortcutMeta | None
    list_groups() -> list[str]
    list_by_group(group) -> list[ShortcutMeta]
    search(q) -> list[ShortcutMeta]
    system_conflicts() -> set[str]
"""
from __future__ import annotations

from dataclasses import dataclass, field


# ===========================================================================
# 数据结构
# ===========================================================================

@dataclass(frozen=True)
class ShortcutMeta:
    command_id: str
    label: str                # 中文名
    default: str              # 默认键位（空字符串表示无默认）
    group: str                # 分组 key
    scope: str = "global"     # global / panel / widget
    label_en: str = ""        # 英文名
    description: str = ""     # 详细说明
    keywords: tuple = ()      # 搜索关键词
    builtin: bool = True      # 是否内置（False = 插件注册）


# ===========================================================================
# 分组定义
# ===========================================================================

GROUPS = [
    ("general",     "通用",     "General"),
    ("tools",       "工具",     "Tools"),
    ("navigation",  "导航",     "Navigation"),
    ("window",      "窗口",     "Window"),
    ("editing",     "编辑",     "Editing"),
    ("panels",      "面板",     "Panels"),
    ("features",    "功能",     "Features"),
]


_GROUP_MAP = {k: (zh, en) for k, zh, en in GROUPS}


# ===========================================================================
# 元数据表
# ===========================================================================

_ALL: list[ShortcutMeta] = []


def _m(command_id: str, label: str, default: str,
       group: str, scope: str = "global",
       label_en: str = "", description: str = "",
       *keywords: str):
    _ALL.append(ShortcutMeta(
        command_id=command_id,
        label=label,
        default=default,
        group=group,
        scope=scope,
        label_en=label_en or label,
        description=description,
        keywords=tuple(keywords),
    ))


# ---- general：通用 ----
_m("global.settings", "打开设置面板", "Ctrl+,",
   "general", "global", "Open settings",
   "打开设置面板", "设置", "settings")
_m("global.shortcuts_help", "快捷键速查表", "F1",
   "general", "global", "Shortcuts help",
   "显示当前所有快捷键", "快捷键", "帮助")
_m("global.quit", "退出应用", "",
   "general", "global", "Quit",
   "退出 MultiCalc", "退出", "quit")

# ---- tools：工具 ----
_m("global.command_palette", "命令面板", "Ctrl+K",
   "tools", "global", "Command palette",
   "模糊搜索命令 / 历史 / 直接计算",
   "命令", "palette", "搜索")
_m("global.toggle_keyboard", "显示/隐藏浮动键盘", "Ctrl+Shift+K",
   "tools", "global", "Toggle keyboard",
   "呼出或隐藏浮动计算器键盘",
   "键盘", "keyboard")
_m("global.handwriting", "手写输入", "Ctrl+Shift+H",
   "tools", "global", "Handwriting",
   "打开手写画板（需 pix2tex）",
   "手写", "OCR", "handwriting")
_m("global.ocr", "图片识别", "Ctrl+Shift+O",
   "tools", "global", "OCR input",
   "打开截图 / 图片识别（需 pix2tex 或 OpenAI）",
   "识别", "OCR", "图片")
_m("global.glyph_panel", "打开符号字典", "",
   "tools", "global", "Symbol dictionary",
   "快速跳到符号面板",
   "符号", "字典", "glyph")

# ---- navigation：导航 ----
_m("global.toggle_sidebar", "切换侧边栏", "Ctrl+Shift+L",
   "navigation", "global", "Toggle sidebar",
   "显示或隐藏模块侧边栏",
   "侧边栏", "sidebar")
_m("global.open_in_split", "在分屏打开", "Ctrl+\\",
   "navigation", "global", "Open in split",
   "当前面板在右侧副区中打开",
   "分屏", "split")
_m("global.close_split", "关闭分屏", "",
   "navigation", "global", "Close split",
   "关闭右侧副区",
   "分屏", "split")
_m("nav.module_1", "切换到第 1 个可见模块", "Ctrl+1",
   "navigation", "global", "Go to module 1")
_m("nav.module_2", "切换到第 2 个可见模块", "Ctrl+2",
   "navigation", "global", "Go to module 2")
_m("nav.module_3", "切换到第 3 个可见模块", "Ctrl+3",
   "navigation", "global", "Go to module 3")
_m("nav.module_4", "切换到第 4 个可见模块", "Ctrl+4",
   "navigation", "global", "Go to module 4")
_m("nav.module_5", "切换到第 5 个可见模块", "Ctrl+5",
   "navigation", "global", "Go to module 5")
_m("nav.module_6", "切换到第 6 个可见模块", "Ctrl+6",
   "navigation", "global", "Go to module 6")
_m("nav.module_7", "切换到第 7 个可见模块", "Ctrl+7",
   "navigation", "global", "Go to module 7")
_m("nav.module_8", "切换到第 8 个可见模块", "Ctrl+8",
   "navigation", "global", "Go to module 8")
_m("nav.module_9", "切换到第 9 个可见模块", "Ctrl+9",
   "navigation", "global", "Go to module 9")

# ---- window：窗口 ----
_m("global.focus_mode", "专注模式", "F11",
   "window", "global", "Focus mode",
   "隐藏菜单栏 / 侧边栏，只留当前面板",
   "专注", "focus", "全屏")
_m("global.toggle_tray", "切换系统托盘", "",
   "window", "global", "Toggle tray")
_m("global.new_window", "新建窗口", "",
   "window", "global", "New window",
   "打开一个独立的 MultiCalc 窗口",
   "窗口", "window")

# ---- editing：编辑 ----
_m("panel.calc", "计算", "Ctrl+Return",
   "editing", "panel", "Calculate",
   "执行当前面板的计算", "计算", "calc")
_m("panel.cancel", "取消运行中的任务", "Esc",
   "editing", "panel", "Cancel",
   "中止后台计算", "取消", "cancel")
_m("panel.clear", "清空输入", "Ctrl+L",
   "editing", "panel", "Clear",
   "清空当前输入框", "清空", "clear")
_m("panel.undo", "撤销", "Ctrl+Z",
   "editing", "panel", "Undo",
   "撤销上一次输入改动", "撤销", "undo")
_m("panel.redo", "重做", "Ctrl+Shift+Z",
   "editing", "panel", "Redo")
_m("panel.history_up", "历史（上一条）", "Up",
   "editing", "widget", "History up")
_m("panel.history_down", "历史（下一条）", "Down",
   "editing", "widget", "History down")
_m("panel.select_all", "全选", "Ctrl+A",
   "editing", "widget", "Select all")
_m("panel.copy", "复制", "Ctrl+C",
   "editing", "widget", "Copy")
_m("panel.paste", "粘贴", "Ctrl+V",
   "editing", "widget", "Paste")

# ---- panels：面板 ----
_m("panels.calculate", "计算（同 panel.calc）", "",
   "panels", "panel", "Calculate alias")
_m("panels.new_cell", "笔记本：新增 Code cell", "Ctrl+Shift+C",
   "panels", "panel", "New code cell")
_m("panels.new_md_cell", "笔记本：新增 Markdown cell", "Ctrl+Shift+M",
   "panels", "panel", "New markdown cell")
_m("panels.run_all", "笔记本：运行全部", "Ctrl+Shift+Return",
   "panels", "panel", "Run all cells")
_m("panels.save_nb", "笔记本：保存", "Ctrl+S",
   "panels", "panel", "Save notebook")

# ---- features：功能 ----
_m("global.snapshot_save", "保存会话快照", "Ctrl+Shift+Z",
   "features", "global", "Save snapshot",
   "把当前状态存为一个快照", "快照", "snapshot")
_m("global.snapshot_timeline", "打开时间线", "Ctrl+Shift+Y",
   "features", "global", "Snapshot timeline",
   "查看 / 恢复历史快照", "时间线", "timeline")
_m("global.check_update", "检查更新", "",
   "features", "global", "Check for updates")
_m("global.export_session", "导出 .mcsession", "",
   "features", "global", "Export session")
_m("global.import_session", "打开 .mcsession", "",
   "features", "global", "Import session")


# ===========================================================================
# 查询接口
# ===========================================================================

def all_metas() -> list:
    return list(_ALL)


def get_meta(command_id: str):
    for m in _ALL:
        if m.command_id == command_id:
            return m
    return None


def list_groups() -> list:
    return [(k, zh, en) for k, zh, en in GROUPS]


def list_by_group(group: str) -> list:
    return [m for m in _ALL if m.group == group]


def search(q: str, limit: int = 100) -> list:
    """按关键词搜索。

    匹配：command_id / label / label_en / keywords
    """
    s = (q or "").strip().lower()
    if not s:
        return list(_ALL)[:limit]
    out = []
    for m in _ALL:
        haystack = " ".join([
            m.command_id, m.label, m.label_en,
            m.description, " ".join(m.keywords),
        ]).lower()
        if s in haystack:
            out.append(m)
            if len(out) >= limit:
                break
    return out


# ===========================================================================
# 系统冲突警告
# ===========================================================================

# 各平台常见的系统级快捷键（只警告，不禁用）
_SYSTEM_CONFLICTS = {
    "windows": {
        "Win+L", "Win+D", "Win+E", "Win+R", "Win+I", "Win+S",
        "Win+A", "Win+X", "Win+Tab", "Alt+Tab", "Alt+F4",
        "Ctrl+Alt+Del", "Ctrl+Shift+Esc", "Ctrl+Alt+Esc",
        "Win+Ctrl+D", "Win+Ctrl+F4", "Win+Ctrl+Left",
        "Win+Ctrl+Right", "Win+Shift+S",
    },
    "macos": {
        "Cmd+Q", "Cmd+Tab", "Cmd+W", "Cmd+H", "Cmd+M",
        "Cmd+Space", "Cmd+Ctrl+Q", "Cmd+Shift+Q",
        "Cmd+Ctrl+F", "Cmd+Option+Esc",
    },
    "linux": {
        "Ctrl+Alt+T", "Ctrl+Alt+L", "Ctrl+Alt+Del",
        "Alt+F4", "Alt+Tab", "Super+L",
    },
}


def system_conflicts(platform: str = "") -> set:
    """返回当前平台上会与系统冲突的键位集合。"""
    if not platform:
        import sys
        if sys.platform.startswith("win"):
            platform = "windows"
        elif sys.platform == "darwin":
            platform = "macos"
        else:
            platform = "linux"
    return set(_SYSTEM_CONFLICTS.get(platform.lower(), set()))


def is_system_conflict(key_sequence: str,
                       platform: str = "") -> bool:
    if not key_sequence:
        return False
    return key_sequence in system_conflicts(platform)


__all__ = [
    "ShortcutMeta",
    "GROUPS",
    "all_metas",
    "get_meta",
    "list_groups",
    "list_by_group",
    "search",
    "system_conflicts",
    "is_system_conflict",
]