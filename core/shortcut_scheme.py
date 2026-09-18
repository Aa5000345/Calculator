"""快捷键方案管理：预设 + 导入导出。

预设方案：
    default   项目默认
    vscode    VSCode 风格（命令面板用 Ctrl+Shift+P）
    jetbrains JetBrains 风格
    emacs     尽量接近 Emacs（部分用 M- 前缀的不可用，用 Ctrl+ 代替）

存储：
    ~/.multicalc/shortcuts.json   用户当前方案
    ~/.multicalc/shortcuts_scheme_name.txt   当前方案名（default / vscode / ...）

对外接口：
    list_presets() -> list[dict]
    get_preset(name) -> dict
    apply_preset(name, save=True) -> bool
    export_current(path) -> bool
    import_from(path, merge=True) -> dict
    current_scheme_name() -> str
"""
from __future__ import annotations

import json
import os
import threading

from core import shortcut_config as sc_cfg
from core import shortcut_meta as sc_meta
from core.errors import InputError
from core.logger import log_info, log_warn


_LOCK = threading.RLock()
_SCHEME_NAME_FILE = "shortcuts_scheme_name.txt"


# ===========================================================================
# 预设方案
# ===========================================================================

# 只覆盖默认不同的键位；未列出的走 default
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
    """返回所有预设方案（不含 overrides）。"""
    return [
        {
            "name": k,
            "label_zh": v["label_zh"],
            "label_en": v["label_en"],
            "description": v["description"],
        }
        for k, v in _PRESETS.items()
    ]


def get_preset(name: str) -> dict:
    """返回预设方案的完整键位 dict。"""
    p = _PRESETS.get(str(name).lower())
    if p is None:
        raise InputError(f"未知方案：{name}")

    # 从默认元数据构造完整键位表
    result = {}
    for m in sc_meta.all_metas():
        result[m.command_id] = m.default
    result.update(p["overrides"])
    return result


def get_preset_info(name: str) -> dict:
    """返回预设方案的元信息（含完整键位表）。"""
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


# ===========================================================================
# 方案应用
# ===========================================================================

def _scheme_name_path() -> str:
    return os.path.join(
        os.path.expanduser("~"),
        ".multicalc", _SCHEME_NAME_FILE)


def current_scheme_name() -> str:
    try:
        with open(_scheme_name_path(), "r", encoding="utf-8") as f:
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
    """应用预设方案。

    Args:
        name: 预设名（default / vscode / ...）
        save: 是否持久化（True 时写入 shortcuts.json）

    Returns:
        True 成功
    """
    with _LOCK:
        try:
            keys = get_preset(name)
        except InputError:
            return False

        if save:
            try:
                for cmd_id, key in keys.items():
                    sc_cfg.set(cmd_id, key)
            except Exception as e:
                log_warn(f"apply preset failed: {e}",
                         module="shortcut_scheme")
                return False

        _save_scheme_name(name)
        log_info(f"applied shortcut preset: {name}",
                 module="shortcut_scheme")
        return True


def reset_to_default() -> bool:
    """恢复默认（等价于 apply_preset('default')）。"""
    return apply_preset("default")


# ===========================================================================
# 导入 / 导出
# ===========================================================================

def export_current(path: str) -> bool:
    """把当前生效的键位导出为 JSON。

    格式：
        {
          "scheme": "custom",
          "exported_at": "2025-01-01T12:00:00",
          "keys": {"global.command_palette": "Ctrl+K", ...}
        }
    """
    try:
        import datetime
        keys = {}
        for m in sc_meta.all_metas():
            keys[m.command_id] = sc_cfg.get(m.command_id)
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

    Args:
        path: 文件路径
        merge: True 时只覆盖文件里出现的命令；False 时先重置为默认
        save: 是否持久化

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

    known_ids = {m.command_id for m in sc_meta.all_metas()}

    with _LOCK:
        if not merge:
            reset_to_default()

        for cmd_id, key in keys.items():
            if cmd_id not in known_ids:
                result["unknown"].append(cmd_id)
                continue
            try:
                sc_cfg.set(cmd_id, str(key or ""))
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


# ===========================================================================
# 冲突检测
# ===========================================================================

def detect_conflicts(keys: dict = None,
                     include_system: bool = True) -> list:
    """检测键位冲突。

    Args:
        keys: ``{command_id: key}``；None 时用当前生效的
        include_system: 是否包含系统级冲突

    Returns:
        list of dict：``{key, scope, commands: [id],
        is_system: bool}``
    """
    if keys is None:
        keys = {m.command_id: sc_cfg.get(m.command_id)
                for m in sc_meta.all_metas()}

    by_key: dict = {}
    for cmd_id, key in keys.items():
        if not key:
            continue
        m = sc_meta.get_meta(cmd_id)
        scope = m.scope if m else "global"
        by_key.setdefault(key, []).append({
            "command_id": cmd_id,
            "scope": scope,
        })

    out = []
    sys_keys = sc_meta.system_conflicts() if include_system else set()

    for key, items in by_key.items():
        # 同作用域内 ≥2 才叫冲突（不同作用域可共存）
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

        # 系统冲突单独报告（即使只有一个命令使用）
        if key in sys_keys and len(items) >= 1:
            out.append({
                "key": key,
                "scope": "system",
                "commands": [it["command_id"] for it in items],
                "is_system": True,
            })

    # 去重（key + scope）
    seen = set()
    unique = []
    for c in out:
        sig = (c["key"], c["scope"])
        if sig in seen:
            continue
        seen.add(sig)
        unique.append(c)
    return unique


__all__ = [
    "list_presets",
    "get_preset",
    "get_preset_info",
    "apply_preset",
    "reset_to_default",
    "current_scheme_name",
    "export_current",
    "import_from",
    "detect_conflicts",
]