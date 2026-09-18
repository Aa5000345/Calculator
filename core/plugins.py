"""插件框架：扫描本地 plugins/ 目录，加载工具扩展。

变更历史：
- 第 3 轮：初版（discover / load_plugin）
- 第 16 轮：
  - load_plugin 加载前标记注册来源（core.plugin_registry）
  - 新增 load_all()：一次性加载所有启用插件并返回汇总
- 第 20 轮：最终版（标注来源 + 汇总统计）

插件只需在 __init__.py 中定义：

    NAME = "My Plugin"
    VERSION = "1.0"

    def register(app_context):  # 可选
        from core.plugin_api import register_panel, register_command
        ...

不会自动执行任何 UI 注入；通过 core.plugin_api 的装饰器或
register_* 函数向运行时注册表注册扩展点。
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys

from core.logger import log_info, log_warn


_META_FILES = {"plugin.json"}


# ===========================================================================
# 元数据
# ===========================================================================

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

    def __repr__(self):
        return (f"<PluginInfo name={self.name!r} "
                f"v{self.version} enabled={self.enabled}>")


# ===========================================================================
# 发现
# ===========================================================================

def discover(plugin_root: str) -> list:
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
            log_warn(
                f"plugin.json 读取失败 {meta_path}: {e}",
                module="plugins")

    # 退化：只有 __init__.py 时，用目录名做元数据
    init_py = os.path.join(sub, "__init__.py")
    if os.path.exists(init_py):
        return PluginInfo(path=sub, name=fallback_name)
    return None


# ===========================================================================
# 加载
# ===========================================================================

def load_plugin(info: PluginInfo, app_context=None) -> bool:
    """尝试把插件作为模块加载；失败只记录日志。

    加载前会调用 `plugin_registry.set_source(info.name)`，
    这样插件内通过装饰器注册的扩展点都会被标记来源。
    """
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

        # --- 标记注册来源（供装饰器使用） ---
        try:
            from core import plugin_registry as reg_mod
            reg_mod.get_registry().set_source(info.name)
        except Exception:
            pass

        # --- 执行模块（触发装饰器注册） ---
        spec.loader.exec_module(mod)

        # --- 调用可选的 register() 回调 ---
        fn = getattr(mod, "register", None)
        if callable(fn):
            try:
                fn(app_context)
            except Exception as e:  # noqa: BLE001
                log_warn(
                    f"plugin register failed {info.name}: {e}",
                    module="plugins")

        log_info(f"plugin loaded: {info.name}",
                 module="plugins")
        return True

    except Exception as e:  # noqa: BLE001
        log_warn(f"plugin load failed {info.name}: {e}",
                 module="plugins")
        return False
    finally:
        # 恢复来源标记（避免影响后续非插件代码）
        try:
            from core import plugin_registry as reg_mod
            reg_mod.get_registry().set_source("")
        except Exception:
            pass


def load_all(plugin_root: str, app_context=None) -> dict:
    """加载 plugin_root 下所有已启用的插件。

    Returns:
        {
            "root": str,
            "total": int,          # discover 到的总数
            "enabled": int,        # 启用的数量
            "loaded": int,         # 成功加载数
            "failed": int,         # 加载失败数
            "details": [
                {"name", "path", "enabled", "ok", "error"},
                ...
            ],
        }
    """
    infos = discover(plugin_root)
    result = {
        "root": plugin_root,
        "total": len(infos),
        "enabled": 0,
        "loaded": 0,
        "failed": 0,
        "details": [],
    }

    for info in infos:
        detail = {
            "name": info.name,
            "path": info.path,
            "enabled": bool(info.enabled),
            "ok": False,
            "error": "",
        }

        if not info.enabled:
            detail["error"] = "disabled"
            result["details"].append(detail)
            continue

        result["enabled"] += 1
        try:
            ok = load_plugin(info, app_context)
        except Exception as e:  # noqa: BLE001
            ok = False
            detail["error"] = str(e)

        detail["ok"] = bool(ok)
        if ok:
            result["loaded"] += 1
        else:
            result["failed"] += 1
            if not detail["error"]:
                detail["error"] = "load failed"
        result["details"].append(detail)

    log_info(
        f"plugins loaded: {result['loaded']}/{result['enabled']} "
        f"(total {result['total']})",
        module="plugins")
    return result


# ===========================================================================
# 卸载（运行时移除注册）
# ===========================================================================

def unload_plugin(info: PluginInfo) -> bool:
    """从运行时注册表移除某插件的所有注册。

    注意：已加载的模块仍在 sys.modules 中（不主动卸载，
    以避免破坏已实例化的面板对象）。
    """
    try:
        from core import plugin_registry as reg_mod
        reg_mod.get_registry().remove_source(info.name)
        log_info(f"plugin unloaded: {info.name}",
                 module="plugins")
        return True
    except Exception as e:  # noqa: BLE001
        log_warn(f"plugin unload failed {info.name}: {e}",
                 module="plugins")
        return False


__all__ = [
    "PluginInfo",
    "discover",
    "load_plugin",
    "load_all",
    "unload_plugin",
]