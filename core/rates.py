"""汇率 + 加密货币。

合并自：core/rates.py + core/crypto.py

对外接口：
    # 汇率源
    RateSource, register_source, list_sources, get_source
    init(base_path, plugin_dir=None)
    load_offline, save_offline, fetch_rates, ensure_fresh
    convert, batch_convert
    # 加密货币
    COINS, list_coins, fetch_prices, get_cached
"""
from __future__ import annotations

import importlib.util
import json
import os
import pkgutil
import sys
import time

from core.base import NetworkError, log_info, log_warn


__all__ = [
    "RateSource", "register_source", "list_sources", "get_source",
    "init", "load_offline", "save_offline",
    "fetch_rates", "ensure_fresh", "convert", "batch_convert",
    "COINS", "list_coins", "fetch_prices", "get_cached",
]


# ===========================================================================
# 汇率源
# ===========================================================================

_CACHE_TTL = 6 * 3600


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


def list_sources() -> list:
    return sorted(_REGISTRY.values(), key=lambda s: s.priority)


def get_source(name):
    return _REGISTRY.get(name)


class OpenErApiSource(RateSource):
    name = "open.er-api.com"
    label = "open.er-api.com"
    priority = 10
    is_online = True

    def fetch(self):
        import requests
        r = requests.get(
            "https://open.er-api.com/v6/latest/USD", timeout=10)
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
        r = requests.get(
            "https://api.exchangerate.host/latest", timeout=10)
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


def load_plugin_dir(dir_path):
    """加载 `plugins/rates/*.py`（无需 __init__.py）。"""
    if not os.path.isdir(dir_path):
        return
    for mod_info in pkgutil.iter_modules([dir_path]):
        mod_path = os.path.join(dir_path, mod_info.name + ".py")
        try:
            spec = importlib.util.spec_from_file_location(
                f"multicalc_rates_{mod_info.name}", mod_path)
            if spec is None or spec.loader is None:
                continue
            mod = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = mod
            spec.loader.exec_module(mod)
            if hasattr(mod, "register"):
                mod.register()
                log_info(f"plugin loaded: {mod_info.name}",
                         module="rates")
        except Exception as e:  # noqa: BLE001
            log_warn(f"plugin load failed: {mod_info.name}: {e}",
                     module="rates")


def init(base_path, plugin_dir=None):
    _REGISTRY.clear()
    register_source(OpenErApiSource())
    register_source(ExchangeRateHostSource())
    register_source(FallbackOfflineSource(base_path))
    if plugin_dir:
        load_plugin_dir(plugin_dir)


# ===========================================================================
# 离线文件
# ===========================================================================

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


# ===========================================================================
# 获取
# ===========================================================================

def fetch_rates(preferred=None):
    """按优先级（或 preferred）尝试所有源。

    返回 ``(rates, source_name, is_online)``。
    """
    order = list_sources()
    if preferred:
        src = get_source(preferred)
        if src:
            order = [src] + [s for s in order
                             if s.name != preferred]
    last = None
    for src in order:
        try:
            rates = src.fetch()
            if rates:
                log_info(f"rate source ok: {src.name}",
                         module="rates")
                return (rates, src.name,
                        bool(getattr(src, "is_online", True)))
        except Exception as e:  # noqa: BLE001
            last = e
            log_warn(f"rate source fail {src.name}: {e}",
                     module="rates")
    raise NetworkError(f"所有汇率源均失败：{last}")


def ensure_fresh(base_path, force=False, source=None):
    """返回最新缓存；仅在线成功才刷新 updated。

    离线兜底时不会把 ``updated`` 覆盖为当前时间——否则接下来
    6 小时都不会再尝试联网。
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
        # 离线兜底：保留原 updated
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
        raise NetworkError(f"未知币种：{fc}",
                           friendly_key="err_currency")
    if tc not in rates:
        raise NetworkError(f"未知币种：{tc}",
                           friendly_key="err_currency")
    return amount / rates[fc] * rates[tc]


def batch_convert(amount, from_cur, targets, rates):
    return {t: convert(amount, from_cur, t, rates)
            for t in targets}


# ===========================================================================
# 加密货币
# ===========================================================================

COINS = {
    "BTC":   ("bitcoin",       "₿"),
    "ETH":   ("ethereum",      "Ξ"),
    "USDT":  ("tether",        "₮"),
    "BNB":   ("binancecoin",   "BNB"),
    "SOL":   ("solana",        "SOL"),
    "XRP":   ("ripple",        "XRP"),
    "ADA":   ("cardano",       "ADA"),
    "DOGE":  ("dogecoin",      "Ð"),
    "DOT":   ("polkadot",      "DOT"),
    "MATIC": ("matic-network", "MATIC"),
    "LTC":   ("litecoin",      "Ł"),
    "LINK":  ("chainlink",     "LINK"),
    "AVAX":  ("avalanche-2",   "AVAX"),
    "TRX":   ("tron",          "TRX"),
    "SHIB":  ("shiba-inu",     "SHIB"),
}

_COIN_CACHE: dict = {"ts": 0, "data": {}}
_COIN_TTL = 300


def list_coins() -> list:
    return sorted(COINS.keys())


def fetch_prices(vs="usd") -> dict:
    """返回 {SYMBOL: price}，失败抛 NetworkError。"""
    now = time.time()
    if (now - _COIN_CACHE["ts"] < _COIN_TTL
            and _COIN_CACHE["data"]):
        return _COIN_CACHE["data"]

    ids = ",".join(v[0] for v in COINS.values())
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {"ids": ids, "vs_currencies": vs}
    try:
        import requests
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        if not isinstance(data, dict):
            raise NetworkError("CoinGecko 返回异常")
        out = {}
        for sym, (cid, _icon) in COINS.items():
            if cid in data and vs in data[cid]:
                out[sym] = float(data[cid][vs])
        _COIN_CACHE["ts"] = now
        _COIN_CACHE["data"] = out
        log_info(f"crypto prices updated: {len(out)}",
                 module="crypto")
        return out
    except Exception as e:  # noqa: BLE001
        log_warn(f"crypto fetch failed: {e}", module="crypto")
        raise NetworkError(
            f"加密货币汇率获取失败：{e}") from e


def get_cached() -> dict:
    return dict(_COIN_CACHE["data"])