"""加密货币汇率：通过 CoinGecko 免费 API 获取。

不依赖额外包，使用 requests；离线时返回空。
"""
from __future__ import annotations

import time

from core.errors import NetworkError
from core.logger import log_warn, log_info

# 常用币种 ID 映射
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

_CACHE = {"ts": 0, "data": {}}
_TTL = 300  # 5 分钟


def list_coins():
    return sorted(COINS.keys())


def fetch_prices(vs="usd"):
    """返回 {SYMBOL: price}，失败抛 NetworkError。"""
    now = time.time()
    if now - _CACHE["ts"] < _TTL and _CACHE["data"]:
        return _CACHE["data"]

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
        _CACHE["ts"] = now
        _CACHE["data"] = out
        log_info(f"crypto prices updated: {len(out)}", module="crypto")
        return out
    except Exception as e:  # noqa: BLE001
        log_warn(f"crypto fetch failed: {e}", module="crypto")
        raise NetworkError(f"加密货币汇率获取失败：{e}") from e


def get_cached():
    return dict(_CACHE["data"])