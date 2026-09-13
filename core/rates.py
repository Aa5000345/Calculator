"""汇率管理：可插拔汇率源 + 6h 缓存 + 离线回退 + 手动币对保存。

修复：
- ensure_fresh() 不再把离线兜底当成在线成功刷新 updated；
- load_plugin_dir() 改用 importlib.util.spec_from_file_location，无需
  包目录有 __init__.py，也不必把 plugins/rates 加进 sys.path；
- fetch_rates() 返回 (rates, source_name, is_online)。
"""
from __future__ import annotations

import importlib.util
import json
import os
import pkgutil
import sys
import time

from core.errors import NetworkError
from core.logger import log_warn, log_info

_CACHE_TTL = 6 * 3600


# ---------------- 插件基类与注册表 ----------------

class RateSource:
    """汇率源插件基类。name 唯一；fetch() 返回 {code: rate_per_USD}。"""

    name = "base"
    label = "Base"
    priority = 100
    is_online = True

    def fetch(self) -> dict:
        raise NotImplementedError


_REGISTRY: dict[str, RateSource] = {}


def register_source(src: RateSource):
    _REGISTRY[src.name] = src
    log_info(f"register rate source: {src.name}", module="rates")


def list_sources():
    return sorted(_REGISTRY.values(), key=lambda s: s.priority)


def get_source(name):
    return _REGISTRY.get(name)


# ---------------- 内置源 ----------------

class OpenErApiSource(RateSource):
    name = "open.er-api.com"
    label = "open.er-api.com"
    priority = 10
    is_online = True

    def fetch(self):
        import requests
        r = requests.get("https://open.er-api.com/v6/latest/USD", timeout=10)
        d = r.json()
        if d.get("result") == "success":
            return d.get("rates") or {}
        raise NetworkError("open.er-api.com 返回异常")


class ExchangeRateHostSource(RateSource):
    name = "exchangerate.host"
    label = "exchangerate.host"
    priority = 20
    is_online = True

    def fetch(self):
        import requests
        r = requests.get("https://api.exchangerate.host/latest", timeout=10)
        d = r.json()
        rates = d.get("rates")
        if rates:
            return rates
        raise NetworkError("exchangerate.host 返回异常")


class FallbackOfflineSource(RateSource):
    """兜底：使用离线文件。永远可用，但明确标记为离线。"""

    name = "offline"
    label = "Offline"
    priority = 999
    is_online = False

    def __init__(self, base_path):
        self.base_path = base_path

    def fetch(self):
        return load_offline(self.base_path).get("rates", {})


# ---------------- 动态加载外部插件 ----------------

def load_plugin_dir(dir_path):
    """加载 `plugins/rates/*.py`。

    每个文件可定义 RateSource 子类并实现 `register()` 回调；
    不要求目录是包（无需 __init__.py），也不需要把它加入 sys.path。
    """
    if not os.path.isdir(dir_path):
        return
    parent = os.path.dirname(dir_path)
    if parent and parent not in sys.path:
        sys.path.insert(0, parent)
    for mod_info in pkgutil.iter_modules([dir_path]):
        mod_path = os.path.join(dir_path, mod_info.name + ".py")
        try:
            spec = importlib.util.spec_from_file_location(
                f"multicalc_rates_{mod_info.name}", mod_path)
            if spec is None or spec.loader is None:
                continue
            mod = importlib.util.module_from_spec(spec)
            # 让插件内可以用相对名互相 import
            sys.modules[spec.name] = mod
            spec.loader.exec_module(mod)
            if hasattr(mod, "register"):
                mod.register()
                log_info(f"plugin loaded: {mod_info.name}", module="rates")
        except Exception as e:  # noqa: BLE001
            log_warn(f"plugin load failed: {mod_info.name}: {e}",
                     module="rates")


# ---------------- 初始化 ----------------

def init(base_path, plugin_dir=None):
    _REGISTRY.clear()
    register_source(OpenErApiSource())
    register_source(ExchangeRateHostSource())
    register_source(FallbackOfflineSource(base_path))
    if plugin_dir:
        load_plugin_dir(plugin_dir)


# ---------------- 离线文件 ----------------

def _offline_path(base_path):
    return os.path.join(base_path, "config", "rates_offline.json")


_DEFAULT_OFFLINE = {
    "base": "USD", "updated": 0,
    "rates": {"USD": 1, "CNY": 7.2, "EUR": 0.92, "JPY": 150,
              "GBP": 0.79, "HKD": 7.8},
}


def load_offline(base_path):
    path = _offline_path(base_path)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return dict(_DEFAULT_OFFLINE)


def save_offline(base_path, data):
    try:
        path = _offline_path(base_path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# ---------------- 获取 ----------------

def fetch_rates(preferred=None):
    """按优先级（或 preferred）尝试所有源。

    返回 ``(rates, source_name, is_online)``。
    """
    order = list_sources()
    if preferred:
        src = get_source(preferred)
        if src:
            order = [src] + [s for s in order if s.name != preferred]
    last = None
    for src in order:
        try:
            rates = src.fetch()
            if rates:
                log_info(f"rate source ok: {src.name}", module="rates")
                return rates, src.name, bool(getattr(src, "is_online", True))
        except Exception as e:  # noqa: BLE001
            last = e
            log_warn(f"rate source fail {src.name}: {e}", module="rates")
    raise NetworkError(f"所有汇率源均失败：{last}")


def ensure_fresh(base_path, force=False, source=None):
    """返回最新缓存；仅在线成功才刷新 updated。

    离线兜底时不会把 ``updated`` 覆盖为当前时间——否则接下来 6 小时
    都不会再尝试联网。
    """
    data = load_offline(base_path)
    now = time.time()
    if not force and (now - float(data.get("updated", 0))) < _CACHE_TTL:
        return data
    try:
        rates, src_name, is_online = fetch_rates(preferred=source)
        if is_online:
            new_data = {
                "base": "USD", "updated": now,
                "source": src_name, "rates": rates,
            }
            save_offline(base_path, new_data)
            return new_data
        # 离线兜底：保留原 updated；只有现有数据完全为空时填充默认值
        if not data.get("rates"):
            data = {"base": "USD", "updated": 0,
                    "source": src_name, "rates": rates}
        return data
    except Exception:
        return data


def convert(amount, from_cur, to_cur, rates):
    amount = float(amount)
    fc, tc = str(from_cur).upper(), str(to_cur).upper()
    if fc == tc:
        return amount
    if fc not in rates:
        raise NetworkError(f"未知币种：{fc}", friendly_key="err_currency")
    if tc not in rates:
        raise NetworkError(f"未知币种：{tc}", friendly_key="err_currency")
    return amount / rates[fc] * rates[tc]


def batch_convert(amount, from_cur, targets, rates):
    return {t: convert(amount, from_cur, t, rates) for t in targets}