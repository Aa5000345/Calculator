"""快捷键元数据 + 用户自定义 + 预设方案。

合并自：core/shortcut_meta.py + core/shortcut_config.py
        + core/shortcut_scheme.py

对外接口：
    # 元数据（shortcut_meta）
    ShortcutMeta, GROUPS, all_metas, get_meta,
    list_groups, list_by_group, search,
    system_conflicts, is_system_conflict

    # 用户覆盖（shortcut_config）
    DEFAULTS, LABELS（通过 __getattr__ 动态生成）
    get, get_all, set, reset, conflicts,
    label, defaults, labels

    # 预设方案（shortcut_scheme）
    list_presets, get_preset, get_preset_info,
    apply_preset, reset_to_default,
    current_scheme_name, export_current,
    import_from, detect_conflicts
"""
from __future__ import annotations

import datetime
import json
import os
import threading
from dataclasses import dataclass
from typing import Optional

from core.base import InputError, log_info, log_warn

__all__ = [
    # 元数据
    "ShortcutMeta", "GROUPS",
    "all_metas", "get_meta",
    "list_groups", "list_by_group", "search",
    "system_conflicts", "is_system_conflict",
    # 用户覆盖
    "get", "get_all", "set", "reset", "conflicts",
    "label", "defaults", "labels",
    # 方案
    "list_presets", "get_preset", "get_preset_info",
    "apply_preset", "reset_to_default",
    "current_scheme_name", "export_current",
    "import_from", "detect_conflicts",
]


# ===========================================================================
# 元数据
# ===========================================================================

@dataclass(frozen=True)
class ShortcutMeta:
    command_id: str
    label: str
    default: str
    group: str
    scope: str = "global"
    label_en: str = ""
    description: str = ""
    keywords: tuple = ()
    builtin: bool = True


GROUPS = [
    ("general",    "通用", "General"),
    ("tools",      "工具", "Tools"),
    ("navigation", "导航", "Navigation"),
    ("window",     "窗口", "Window"),
    ("editing",    "编辑", "Editing"),
    ("panels",     "面板", "Panels"),
    ("features",   "功能", "Features"),
]


_ALL: list = []


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


# ---- general ----
_m("global.settings", "打开设置面板", "Ctrl+,", "general", "global",
   "Open settings", "打开设置面板", "设置", "settings")
_m("global.shortcuts_help", "快捷键速查表", "F1", "general",
   "global", "Shortcuts help", "显示当前所有快捷键",
   "快捷键", "帮助")
_m("global.quit", "退出应用", "", "general", "global", "Quit",
   "退出 MultiCalc", "退出", "quit")

# ---- tools ----
_m("global.command_palette", "命令面板", "Ctrl+K", "tools",
   "global", "Command palette",
   "模糊搜索命令 / 历史 / 直接计算", "命令", "palette", "搜索")
_m("global.toggle_keyboard", "显示/隐藏浮动键盘",
   "Ctrl+Shift+K", "tools", "global", "Toggle keyboard",
   "呼出或隐藏浮动计算器键盘", "键盘", "keyboard")
_m("global.handwriting", "手写输入", "Ctrl+Shift+H", "tools",
   "global", "Handwriting", "打开手写画板（需 pix2tex）",
   "手写", "OCR", "handwriting")
_m("global.ocr", "图片识别", "Ctrl+Shift+O", "tools", "global",
   "OCR input", "打开截图 / 图片识别（需 pix2tex 或 OpenAI）",
   "识别", "OCR", "图片")
_m("global.glyph_panel", "打开符号字典", "", "tools", "global",
   "Symbol dictionary", "快速跳到符号面板",
   "符号", "字典", "glyph")

# ---- navigation ----
_m("global.toggle_sidebar", "切换侧边栏", "Ctrl+Shift+L",
   "navigation", "global", "Toggle sidebar",
   "显示或隐藏模块侧边栏", "侧边栏", "sidebar")
_m("global.open_in_split", "在分屏打开", "Ctrl+\\", "navigation",
   "global", "Open in split", "当前面板在右侧副区中打开",
   "分屏", "split")
_m("global.close_split", "关闭分屏", "", "navigation", "global",
   "Close split", "关闭右侧副区", "分屏", "split")
_m("nav.module_1", "切换到第 1 个可见模块", "Ctrl+1", "navigation",
   "global", "Go to module 1")
_m("nav.module_2", "切换到第 2 个可见模块", "Ctrl+2", "navigation",
   "global", "Go to module 2")
_m("nav.module_3", "切换到第 3 个可见模块", "Ctrl+3", "navigation",
   "global", "Go to module 3")
_m("nav.module_4", "切换到第 4 个可见模块", "Ctrl+4", "navigation",
   "global", "Go to module 4")
_m("nav.module_5", "切换到第 5 个可见模块", "Ctrl+5", "navigation",
   "global", "Go to module 5")
_m("nav.module_6", "切换到第 6 个可见模块", "Ctrl+6", "navigation",
   "global", "Go to module 6")
_m("nav.module_7", "切换到第 7 个可见模块", "Ctrl+7", "navigation",
   "global", "Go to module 7")
_m("nav.module_8", "切换到第 8 个可见模块", "Ctrl+8", "navigation",
   "global", "Go to module 8")
_m("nav.module_9", "切换到第 9 个可见模块", "Ctrl+9", "navigation",
   "global", "Go to module 9")

# ---- window ----
_m("global.focus_mode", "专注模式", "F11", "window", "global",
   "Focus mode", "隐藏菜单栏 / 侧边栏，只留当前面板",
   "专注", "focus", "全屏")
_m("global.toggle_tray", "切换系统托盘", "", "window", "global",
   "Toggle tray")
_m("global.new_window", "新建窗口", "", "window", "global",
   "New window", "打开一个独立的 MultiCalc 窗口",
   "窗口", "window")

# ---- editing ----
_m("panel.calc", "计算", "Ctrl+Return", "editing", "panel",
   "Calculate", "执行当前面板的计算", "计算", "calc")
_m("panel.cancel", "取消运行中的任务", "Esc", "editing", "panel",
   "Cancel", "中止后台计算", "取消", "cancel")
_m("panel.clear", "清空输入", "Ctrl+L", "editing", "panel",
   "Clear", "清空当前输入框", "清空", "clear")
_m("panel.undo", "撤销", "Ctrl+Z", "editing", "panel", "Undo",
   "撤销上一次输入改动", "撤销", "undo")
_m("panel.redo", "重做", "Ctrl+Shift+Z", "editing", "panel",
   "Redo")
_m("panel.history_up", "历史（上一条）", "Up", "editing", "widget",
   "History up")
_m("panel.history_down", "历史（下一条）", "Down", "editing",
   "widget", "History down")
_m("panel.select_all", "全选", "Ctrl+A", "editing", "widget",
   "Select all")
_m("panel.copy", "复制", "Ctrl+C", "editing", "widget", "Copy")
_m("panel.paste", "粘贴", "Ctrl+V", "editing", "widget", "Paste")

# ---- panels ----
_m("panels.calculate", "计算（同 panel.calc）", "", "panels",
   "panel", "Calculate alias")
_m("panels.new_cell", "笔记本：新增 Code cell", "Ctrl+Shift+C",
   "panels", "panel", "New code cell")
_m("panels.new_md_cell", "笔记本：新增 Markdown cell",
   "Ctrl+Shift+M", "panels", "panel", "New markdown cell")
_m("panels.run_all", "笔记本：运行全部",
   "Ctrl+Shift+Return", "panels", "panel", "Run all cells")
_m("panels.save_nb", "笔记本：保存", "Ctrl+S", "panels", "panel",
   "Save notebook")

# ---- features ----
_m("global.snapshot_save", "保存会话快照", "Ctrl+Shift+Z",
   "features", "global", "Save snapshot",
   "把当前状态存为一个快照", "快照", "snapshot")
_m("global.snapshot_timeline", "打开时间线", "Ctrl+Shift+Y",
   "features", "global", "Snapshot timeline",
   "查看 / 恢复历史快照", "时间线", "timeline")
_m("global.check_update", "检查更新", "", "features", "global",
   "Check for updates")
_m("global.export_session", "导出 .mcsession", "", "features",
   "global", "Export session")
_m("global.import_session", "打开 .mcsession", "", "features",
   "global", "Import session")


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


# ===========================================================================
# 用户覆盖
# ===========================================================================

_CONFIG_LOCK = threading.RLock()
_CONFIG_CACHE: Optional[dict] = None


def _config_path() -> str:
    return os.path.join(os.path.expanduser("~"),
                        ".multicalc", "shortcuts.json")


def _defaults_map() -> dict:
    return {m.command_id: m.default for m in _ALL}


def _labels_map() -> dict:
    return {m.command_id: m.label for m in _ALL}


def __getattr__(name: str):
    """兼容老代码 `shortcut_config.DEFAULTS` / `.LABELS`。"""
    if name == "DEFAULTS":
        return _defaults_map()
    if name == "LABELS":
        return _labels_map()
    raise AttributeError(
        f"module {__name__!r} has no attribute {name!r}")


def _config_load() -> dict:
    global _CONFIG_CACHE
    if _CONFIG_CACHE is not None:
        return _CONFIG_CACHE
    try:
        with open(_config_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        _CONFIG_CACHE = data if isinstance(data, dict) else {}
    except Exception:
        _CONFIG_CACHE = {}
    return _CONFIG_CACHE


def _config_save(data: dict):
    try:
        path = _config_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def get(command_id: str, default: str | None = None) -> str:
    """取某个命令的快捷键；用户未覆盖则返回默认。"""
    with _CONFIG_LOCK:
        data = _config_load()
    if command_id in data:
        return str(data[command_id])
    if default is not None:
        return default
    m = get_meta(command_id)
    return m.default if m else ""


def get_all() -> dict:
    """返回 {command_id: key} 合并后的完整表。"""
    out = _defaults_map()
    with _CONFIG_LOCK:
        data = _config_load()
    out.update(data)
    return out


def set(command_id: str, key: str):
    """设置某个命令的快捷键；key 为空则删除（回退默认）。"""
    global _CONFIG_CACHE
    with _CONFIG_LOCK:
        data = dict(_config_load())
        if key:
            data[command_id] = str(key)
        else:
            data.pop(command_id, None)
        _config_save(data)
        _CONFIG_CACHE = data


def reset(command_id: str | None = None):
    """重置某个命令或全部命令。"""
    global _CONFIG_CACHE
    with _CONFIG_LOCK:
        if command_id is None:
            _config_save({})
            _CONFIG_CACHE = {}
            return
        data = dict(_config_load())
        data.pop(command_id, None)
        _config_save(data)
        _CONFIG_CACHE = data


def conflicts() -> list:
    """简单冲突检测：返回 [(key, [command_id, ...]), ...]。"""
    all_keys = get_all()
    by_key: dict = {}
    for cmd, key in all_keys.items():
        if not key:
            continue
        by_key.setdefault(key, []).append(cmd)
    return [(k, v) for k, v in by_key.items() if len(v) > 1]


def label(command_id: str) -> str:
    m = get_meta(command_id)
    return m.label if m else command_id


def defaults() -> dict:
    return _defaults_map()


def labels() -> dict:
    return _labels_map()


# ===========================================================================
# 预设方案
# ===========================================================================

_SCHEME_NAME_FILE = "shortcuts_scheme_name.txt"

_PRESETS = {
    "default": {
        "label_zh": "项目默认",
        "label_en": "Default",
        "description": "MultiCalc 默认键位",
        "overrides": {},
    },
    "vscode": {
        "label_zh": "VSCode 风格",
        "label_en": "VSCode",
        "description": "命令面板用 Ctrl+Shift+P，与 VSCode 一致",
        "overrides": {
            "global.command_palette": "Ctrl+Shift+P",
            "global.toggle_sidebar": "Ctrl+B",
            "global.open_in_split": "Ctrl+Alt+\\",
            "panel.calc": "Ctrl+Enter",
            "panel.undo": "Ctrl+Z",
            "panel.redo": "Ctrl+Y",
            "global.focus_mode": "Ctrl+K Z",
        },
    },
    "jetbrains": {
        "label_zh": "JetBrains 风格",
        "label_en": "JetBrains",
        "description": "命令面板用 Ctrl+Shift+A，与 IDEA 一致",
        "overrides": {
            "global.command_palette": "Ctrl+Shift+A",
            "global.settings": "Ctrl+Alt+S",
            "panel.calc": "Ctrl+Enter",
            "global.toggle_sidebar": "Ctrl+B",
            "global.open_in_split": "Ctrl+\\",
        },
    },
    "emacs": {
        "label_zh": "Emacs 风格",
        "label_en": "Emacs",
        "description": "尽量接近 Emacs（部分键位受限，用 Ctrl+ 代替）",
        "overrides": {
            "global.command_palette": "Alt+X",
            "global.settings": "Ctrl+X Ctrl+S",
            "panel.calc": "Ctrl+X Ctrl+E",
            "panel.cancel": "Ctrl+G",
            "panel.undo": "Ctrl+/",
            "panel.clear": "Ctrl+X Ctrl+K",
            "global.toggle_sidebar": "Ctrl+X Ctrl+B",
        },
    },
}


def list_presets() -> list:
    return [{
        "name": k,
        "label_zh": v["label_zh"],
        "label_en": v["label_en"],
        "description": v["description"],
    } for k, v in _PRESETS.items()]


def get_preset(name: str) -> dict:
    p = _PRESETS.get(str(name).lower())
    if p is None:
        raise InputError(f"未知方案：{name}")
    result = {m.command_id: m.default for m in _ALL}
    result.update(p["overrides"])
    return result


def get_preset_info(name: str) -> dict:
    p = _PRESETS.get(str(name).lower())
    if p is None:
        raise InputError(f"未知方案：{name}")
    return {
        "name": name,
        "label_zh": p["label_zh"],
        "label_en": p["label_en"],
        "description": p["description"],
        "keys": get_preset(name),
    }


def _scheme_name_path() -> str:
    return os.path.join(os.path.expanduser("~"),
                        ".multicalc", _SCHEME_NAME_FILE)


def current_scheme_name() -> str:
    try:
        with open(_scheme_name_path(), "r",
                  encoding="utf-8") as f:
            name = f.read().strip()
        if name in _PRESETS:
            return name
    except Exception:
        pass
    return "custom"


def _save_scheme_name(name: str):
    try:
        path = _scheme_name_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(str(name))
    except Exception as e:
        log_warn(f"save scheme name failed: {e}",
                 module="shortcut_scheme")


def apply_preset(name: str, save: bool = True) -> bool:
    with _CONFIG_LOCK:
        try:
            keys = get_preset(name)
        except InputError:
            return False

        if save:
            try:
                for cmd_id, key in keys.items():
                    set(cmd_id, key)
            except Exception as e:
                log_warn(f"apply preset failed: {e}",
                         module="shortcut_scheme")
                return False

        _save_scheme_name(name)
        log_info(f"applied shortcut preset: {name}",
                 module="shortcut_scheme")
        return True


def reset_to_default() -> bool:
    return apply_preset("default")


def export_current(path: str) -> bool:
    try:
        keys = {m.command_id: get(m.command_id)
                for m in all_metas()}
        payload = {
            "format": "multicalc.shortcuts",
            "version": 1,
            "scheme": current_scheme_name(),
            "exported_at": datetime.datetime.now().isoformat(
                timespec="seconds"),
            "keys": keys,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        log_warn(f"export shortcuts failed: {e}",
                 module="shortcut_scheme")
        return False


def import_from(path: str, merge: bool = True,
                save: bool = True) -> dict:
    """从 JSON 导入键位。

    Returns:
        ``{"ok": bool, "applied": int, "skipped": int,
        "unknown": list}``
    """
    result = {"ok": False, "applied": 0,
              "skipped": 0, "unknown": []}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        result["error"] = f"读取失败：{e}"
        return result

    if not isinstance(data, dict):
        result["error"] = "格式非法：顶层必须是对象"
        return result
    keys = data.get("keys")
    if not isinstance(keys, dict):
        result["error"] = "格式非法：缺少 keys 字段"
        return result

    known_ids = {m.command_id for m in all_metas()}

    with _CONFIG_LOCK:
        if not merge:
            reset_to_default()

        for cmd_id, key in keys.items():
            if cmd_id not in known_ids:
                result["unknown"].append(cmd_id)
                continue
            try:
                set(cmd_id, str(key or ""))
                result["applied"] += 1
            except Exception:
                result["skipped"] += 1

        _save_scheme_name("custom")

    result["ok"] = True
    log_info(
        f"imported shortcuts: {result['applied']} applied, "
        f"{len(result['unknown'])} unknown",
        module="shortcut_scheme")
    return result


def detect_conflicts(keys: dict = None,
                     include_system: bool = True) -> list:
    """检测键位冲突。

    Returns:
        list of dict：``{key, scope, commands: [id],
        is_system: bool}``
    """
    if keys is None:
        keys = {m.command_id: get(m.command_id)
                for m in all_metas()}

    by_key: dict = {}
    for cmd_id, key in keys.items():
        if not key:
            continue
        m = get_meta(cmd_id)
        scope = m.scope if m else "global"
        by_key.setdefault(key, []).append({
            "command_id": cmd_id, "scope": scope,
        })

    out = []
    sys_keys = system_conflicts() if include_system else set()

    for key, items in by_key.items():
        by_scope: dict = {}
        for it in items:
            by_scope.setdefault(it["scope"], []).append(
                it["command_id"])

        for scope, cmd_ids in by_scope.items():
            if len(cmd_ids) >= 2:
                out.append({
                    "key": key,
                    "scope": scope,
                    "commands": cmd_ids,
                    "is_system": key in sys_keys,
                })

        if key in sys_keys and len(items) >= 1:
            out.append({
                "key": key,
                "scope": "system",
                "commands": [it["command_id"] for it in items],
                "is_system": True,
            })

    seen = set()
    unique = []
    for c in out:
        sig = (c["key"], c["scope"])
        if sig in seen:
            continue
        seen.add(sig)
        unique.append(c)
    return unique