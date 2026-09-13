"""插件框架：扫描本地 plugins/ 目录，加载工具扩展。

插件只需在 .py 文件中定义：

    NAME = "My Plugin"
    VERSION = "1.0"
    DESCRIPTION = "..."
    def register(app_context):  # 可选
        ...

不会自动执行任何 UI 注入；仅提供元数据列举接口，供设置面板展示。
"""
from __future__ import annotations

import importlib.util
import json
import os
import pkgutil
import sys

from core.logger import log_info, log_warn


_META_FILES = {"plugin.json"}


class PluginInfo:
    def __init__(self, path, name, version="", description="",
                 author="", enabled=True):
        self.path = path
        self.name = name
        self.version = version
        self.description = description
        self.author = author
        self.enabled = enabled

    def to_dict(self):
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "enabled": self.enabled,
            "path": self.path,
        }


def discover(plugin_root: str) -> list[PluginInfo]:
    """扫描 plugin_root 下每个子目录，读取 plugin.json 或 __init__.py。"""
    if not os.path.isdir(plugin_root):
        return []
    out = []
    for entry in sorted(os.listdir(plugin_root)):
        sub = os.path.join(plugin_root, entry)
        if not os.path.isdir(sub):
            continue
        info = _read_meta(sub, entry)
        if info:
            out.append(info)
    return out


def _read_meta(sub, fallback_name):
    meta_path = os.path.join(sub, "plugin.json")
    if os.path.exists(meta_path):
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                d = json.load(f)
            return PluginInfo(
                path=sub,
                name=d.get("name") or fallback_name,
                version=d.get("version", ""),
                description=d.get("description", ""),
                author=d.get("author", ""),
                enabled=bool(d.get("enabled", True)),
            )
        except Exception as e:  # noqa: BLE001
            log_warn(f"plugin.json 读取失败 {meta_path}: {e}",
                     module="plugins")

    # 退化：只有 __init__.py 时，用目录名做元数据
    init_py = os.path.join(sub, "__init__.py")
    if os.path.exists(init_py):
        return PluginInfo(path=sub, name=fallback_name)
    return None


def load_plugin(info: PluginInfo, app_context=None):
    """尝试把插件作为模块加载；失败只记录日志。"""
    if not info.enabled:
        return False
    init_py = os.path.join(info.path, "__init__.py")
    if not os.path.exists(init_py):
        return False
    try:
        mod_name = f"multicalc_plugin_{os.path.basename(info.path)}"
        spec = importlib.util.spec_from_file_location(
            mod_name, init_py,
            submodule_search_locations=[info.path])
        if spec is None or spec.loader is None:
            return False
        mod = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = mod
        spec.loader.exec_module(mod)
        fn = getattr(mod, "register", None)
        if callable(fn):
            try:
                fn(app_context)
            except Exception as e:  # noqa: BLE001
                log_warn(f"plugin register failed {info.name}: {e}",
                         module="plugins")
        log_info(f"plugin loaded: {info.name}", module="plugins")
        return True
    except Exception as e:  # noqa: BLE001
        log_warn(f"plugin load failed {info.name}: {e}", module="plugins")
        return False