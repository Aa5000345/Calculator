"""自动更新检测（基于 GitHub Releases 或自定义 URL）。

不自动下载或安装，仅提示有新版本。
"""
from __future__ import annotations

from core.logger import log_warn, log_info

DEFAULT_FEED = "https://api.github.com/repos/example/multicalc/releases/latest"


def _parse_version(s: str):
    s = str(s).lstrip("vV")
    parts = []
    for p in s.split("."):
        try:
            parts.append(int(p))
        except ValueError:
            parts.append(0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


def check_update(current_version: str = "1.0.0",
                 feed_url: str = DEFAULT_FEED,
                 timeout: float = 6.0):
    """返回 (has_update, latest_version, url) 或 (False, current, None)。"""
    try:
        import requests
        r = requests.get(feed_url, timeout=timeout,
                         headers={"Accept": "application/vnd.github+json"})
        data = r.json()
        tag = data.get("tag_name") or data.get("name") or ""
        url = data.get("html_url") or feed_url
        if not tag:
            return False, current_version, None
        has = _parse_version(tag) > _parse_version(current_version)
        log_info(f"update check: current={current_version} latest={tag}",
                 module="updater")
        return has, tag, url
    except Exception as e:  # noqa: BLE001
        log_warn(f"update check failed: {e}", module="updater")
        return False, current_version, None