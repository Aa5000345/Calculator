"""自动更新：检查 + 下载 + SHA256 校验。

设计：
- 检查：调用 GitHub Releases API
- 下载：流式下载 release 里的 asset，可选校验 SHA256
- 不自动安装（跨平台复杂），下载完成后提示用户手动替换 / 重启
- 所有网络操作支持超时 + 取消 + 进度回调

默认 feed：
    https://api.github.com/repos/Aa5000345/Calculator/releases/latest

对外接口：
    check_update(current_version, feed_url, timeout, silent)
        -> UpdateInfo
    download_asset(info, dest_dir, progress_cb, cancelled, verify_sha)
        -> DownloadResult
    verify_sha256(path, expected_hex) -> bool
    should_auto_check(settings, interval_days=7) -> bool
    mark_checked(settings)
    get_release_asset(info, platform) -> dict | None
"""
from __future__ import annotations

import hashlib
import json
import os
import platform as plat_mod
import re
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from core import version as ver_mod
from core.errors import InputError, NetworkError
from core.logger import log_warn, log_info


DEFAULT_FEED = (
    "https://api.github.com/repos/Aa5000345/Calculator/"
    "releases/latest"
)

DEFAULT_TIMEOUT = 8.0
DOWNLOAD_TIMEOUT = 60.0
CHUNK_SIZE = 1 << 16        # 64 KiB
AUTO_CHECK_INTERVAL_DAYS = 7


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------

@dataclass
class ReleaseAsset:
    name: str
    url: str
    size: int = 0
    content_type: str = ""
    sha256: str = ""        # 若 release 提供了 checksum

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "url": self.url,
            "size": self.size,
            "content_type": self.content_type,
            "sha256": self.sha256,
        }


@dataclass
class UpdateInfo:
    has_update: bool = False
    current: str = ""
    latest: str = ""
    url: str = ""
    notes: str = ""
    published_at: str = ""
    assets: list = field(default_factory=list)
    error: str = ""
    raw: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "has_update": self.has_update,
            "current": self.current,
            "latest": self.latest,
            "url": self.url,
            "notes": self.notes,
            "published_at": self.published_at,
            "assets": [a.to_dict() if isinstance(a, ReleaseAsset)
                       else a for a in self.assets],
            "error": self.error,
        }


@dataclass
class DownloadProgress:
    done: int
    total: int
    speed_bps: float = 0.0

    @property
    def percent(self) -> float:
        if self.total <= 0:
            return 0.0
        return min(100.0, self.done / self.total * 100.0)


@dataclass
class DownloadResult:
    path: str = ""
    size: int = 0
    sha256: str = ""
    verified: bool = False
    error: str = ""
    elapsed: float = 0.0


# ---------------------------------------------------------------------------
# 版本对比（旧接口兼容）
# ---------------------------------------------------------------------------

def _parse_version(s: str):
    """旧接口：返回 tuple，供旧代码使用。"""
    v = ver_mod.parse(s)
    return v.to_tuple()


# ---------------------------------------------------------------------------
# 检查更新
# ---------------------------------------------------------------------------

def check_update(current_version: str = "1.0.0",
                 feed_url: str = DEFAULT_FEED,
                 timeout: float = DEFAULT_TIMEOUT,
                 silent: bool = False) -> UpdateInfo:
    """检查更新。

    Args:
        current_version: 当前版本（字符串或 Version）
        feed_url: GitHub Releases API URL
        timeout: 请求超时（秒）
        silent: True 时网络错误只写日志，不抛异常

    Returns:
        UpdateInfo
    """
    info = UpdateInfo(
        current=str(current_version),
        url=feed_url,
    )

    try:
        import requests
    except ImportError as e:
        info.error = f"需要 requests：{e}"
        if not silent:
            raise NetworkError(info.error)
        return info

    try:
        r = requests.get(
            feed_url,
            timeout=timeout,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "MultiCalc-Updater/1.0",
            },
        )
        if r.status_code == 404:
            info.error = "未找到 release（仓库无 release 或 URL 错误）"
            if not silent:
                raise NetworkError(info.error)
            return info
        r.raise_for_status()
        data = r.json()
    except Exception as e:  # noqa: BLE001
        info.error = f"网络失败：{e}"
        if not silent:
            log_warn(f"check_update failed: {e}", module="updater")
        return info

    info.raw = data if isinstance(data, dict) else {}

    tag = (info.raw.get("tag_name")
           or info.raw.get("name")
           or "").strip()
    info.latest = tag
    info.notes = str(info.raw.get("body") or "")
    info.published_at = str(info.raw.get("published_at") or "")
    info.url = str(info.raw.get("html_url") or feed_url)

    if not tag:
        info.error = "release 缺少 tag_name"
        return info

    # 解析 assets
    for a in info.raw.get("assets") or []:
        if not isinstance(a, dict):
            continue
        info.assets.append(ReleaseAsset(
            name=str(a.get("name") or ""),
            url=str(a.get("browser_download_url")
                    or a.get("url") or ""),
            size=int(a.get("size") or 0),
            content_type=str(a.get("content_type") or ""),
        ))

    # 检查是否有 checksum 文件（如 SHA256SUMS.txt）
    _attach_checksums(info)

    # 版本比较
    try:
        info.has_update = ver_mod.is_newer(tag, current_version)
    except Exception:
        info.has_update = _legacy_compare(tag, current_version)

    log_info(
        f"update check: current={current_version} "
        f"latest={tag} has_update={info.has_update}",
        module="updater")
    return info


def _attach_checksums(info: UpdateInfo):
    """如果 release 里有 SHA256SUMS 文件，尝试下载并附加到 assets。

    不阻塞：失败只记录日志。
    """
    sum_assets = [a for a in info.assets
                  if re.search(r"(?i)sha256|checksum",
                               a.name)]
    if not sum_assets:
        return
    try:
        import requests
        r = requests.get(sum_assets[0].url, timeout=5)
        text = r.text or ""
    except Exception:
        return

    # 解析 "hash  filename" 格式
    mapping = {}
    for line in text.splitlines():
        m = re.match(
            r"^\s*([0-9a-fA-F]{64})\s+[* ]?(.+?)\s*$", line)
        if m:
            mapping[m.group(2).strip()] = m.group(1).upper()

    if not mapping:
        return
    for a in info.assets:
        h = mapping.get(a.name)
        if h:
            a.sha256 = h


def _legacy_compare(a: str, b: str) -> bool:
    """旧式对比：只取前 3 段数字。"""
    def _p(s):
        parts = []
        for p in re.split(r"[._\-+]", str(s).lstrip("vV")):
            try:
                parts.append(int(p))
            except ValueError:
                parts.append(0)
        while len(parts) < 3:
            parts.append(0)
        return tuple(parts[:3])
    try:
        return _p(a) > _p(b)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# 平台匹配
# ---------------------------------------------------------------------------

def detect_platform() -> str:
    """返回 ``"windows"`` / ``"macos"`` / ``"linux"``。"""
    sysname = plat_mod.system().lower()
    if sysname.startswith("win"):
        return "windows"
    if sysname == "darwin":
        return "macos"
    return "linux"


def get_release_asset(info: UpdateInfo,
                      platform: Optional[str] = None) -> Optional[ReleaseAsset]:
    """选择当前平台最匹配的 asset。

    优先级：
        1. 平台特定的安装包（windows: .exe / .msi；macos: .dmg / .zip；
           linux: .AppImage / .deb）
        2. 通用 .zip
        3. 第一个非 checksum 文件
    """
    if not info.assets:
        return None
    plat = platform or detect_platform()

    if plat == "windows":
        patterns = [r"(?i)\.exe$", r"(?i)setup.*\.exe$",
                    r"(?i)\.msi$", r"(?i)win.*\.zip$",
                    r"(?i)\.zip$"]
    elif plat == "macos":
        patterns = [r"(?i)\.dmg$", r"(?i)mac.*\.zip$",
                    r"(?i)darwin.*\.zip$", r"(?i)\.zip$"]
    else:  # linux
        patterns = [r"(?i)\.AppImage$", r"(?i)\.deb$",
                    r"(?i)linux.*\.zip$", r"(?i)\.zip$"]

    excluded = re.compile(r"(?i)sha256|checksum|\.txt$|\.sig$")

    for pat in patterns:
        for a in info.assets:
            if excluded.search(a.name):
                continue
            if re.search(pat, a.name):
                return a

    # 兜底
    for a in info.assets:
        if not excluded.search(a.name):
            return a
    return None


# ---------------------------------------------------------------------------
# 下载
# ---------------------------------------------------------------------------

def download_asset(info: UpdateInfo,
                   dest_dir: str,
                   platform: Optional[str] = None,
                   progress_cb: Optional[Callable] = None,
                   cancelled: Optional[Callable] = None,
                   verify_sha: bool = True) -> DownloadResult:
    """下载 release asset 到目标目录。

    Args:
        info: check_update 返回的 UpdateInfo
        dest_dir: 保存目录（如 ~/.multicalc/updates）
        platform: 目标平台（默认自动检测）
        progress_cb: ``fn(DownloadProgress)`` 进度回调
        cancelled: ``fn() -> bool`` 取消检查
        verify_sha: 是否校验 SHA256（若 info 里有 sha256）

    Returns:
        DownloadResult
    """
    result = DownloadResult()
    if not info.has_update:
        result.error = "没有可用更新"
        return result

    asset = get_release_asset(info, platform)
    if asset is None:
        result.error = "未找到适合当前平台的下载文件"
        return result

    try:
        import requests
    except ImportError as e:
        result.error = f"需要 requests：{e}"
        return result

    os.makedirs(dest_dir, exist_ok=True)
    dest_path = os.path.join(dest_dir, asset.name)

    # 临时文件避免半成品
    tmp_path = dest_path + ".part"

    started = time.time()
    sha = hashlib.sha256()
    done = 0
    total = asset.size

    try:
        with requests.get(
                asset.url, stream=True,
                timeout=DOWNLOAD_TIMEOUT,
                headers={"User-Agent": "MultiCalc-Updater/1.0"}
        ) as r:
            r.raise_for_status()
            if total <= 0:
                try:
                    total = int(r.headers.get("Content-Length") or 0)
                except Exception:
                    total = 0

            last_ts = time.time()
            last_done = 0

            with open(tmp_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=CHUNK_SIZE):
                    if cancelled is not None and cancelled():
                        raise InputError("已取消")
                    if not chunk:
                        continue
                    f.write(chunk)
                    sha.update(chunk)
                    done += len(chunk)

                    if progress_cb is not None:
                        now = time.time()
                        dt = now - last_ts
                        speed = ((done - last_done) / dt
                                 if dt > 0 else 0.0)
                        if dt >= 0.25 or done == total:
                            progress_cb(DownloadProgress(
                                done, total, speed))
                            last_ts = now
                            last_done = done

        # 重命名为最终文件
        if os.path.exists(dest_path):
            try:
                os.remove(dest_path)
            except Exception:
                pass
        os.rename(tmp_path, dest_path)

        result.path = dest_path
        result.size = done
        result.sha256 = sha.hexdigest().upper()
        result.elapsed = time.time() - started

        # 校验
        if verify_sha and asset.sha256:
            result.verified = (
                result.sha256.upper() == asset.sha256.upper())
            if not result.verified:
                result.error = (
                    f"SHA256 不匹配：期望 {asset.sha256}，"
                    f"实际 {result.sha256}")
                try:
                    os.remove(dest_path)
                except Exception:
                    pass
                return result
        else:
            result.verified = bool(asset.sha256) is False

        log_info(
            f"downloaded {asset.name} -> {dest_path} "
            f"({done} bytes, {result.elapsed:.1f}s)",
            module="updater")
        return result

    except InputError as e:
        result.error = str(e)
        _cleanup(tmp_path)
        return result
    except Exception as e:  # noqa: BLE001
        result.error = f"下载失败：{e}"
        _cleanup(tmp_path)
        log_warn(f"download failed: {e}", module="updater")
        return result


def _cleanup(path: str):
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


def verify_sha256(path: str, expected_hex: str) -> bool:
    """校验文件 SHA256。"""
    if not os.path.isfile(path):
        return False
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            while True:
                chunk = f.read(CHUNK_SIZE)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest().upper() == str(expected_hex).upper()
    except Exception:
        return False


# ---------------------------------------------------------------------------
# 自动检查节流
# ---------------------------------------------------------------------------

def should_auto_check(settings,
                      interval_days: int = AUTO_CHECK_INTERVAL_DAYS) -> bool:
    """判断是否应该自动检查更新（基于上次检查时间）。"""
    if settings is None:
        return False
    try:
        if not settings.get("auto_check_updates", True):
            return False
        last = float(settings.get("last_update_check", 0) or 0)
    except Exception:
        return False
    if last <= 0:
        return True
    age_days = (time.time() - last) / 86400.0
    return age_days >= interval_days


def mark_checked(settings):
    """记录一次检查时间。"""
    if settings is None:
        return
    try:
        settings.set("last_update_check", time.time(),
                     notify=False)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# 旧接口兼容
# ---------------------------------------------------------------------------

def check_update_legacy(current_version: str = "1.0.0",
                        feed_url: str = DEFAULT_FEED,
                        timeout: float = DEFAULT_TIMEOUT):
    """旧接口：返回 (has_update, latest_version, url)。"""
    info = check_update(current_version, feed_url, timeout,
                        silent=True)
    return info.has_update, info.latest or current_version, info.url


__all__ = [
    "DEFAULT_FEED",
    "AUTO_CHECK_INTERVAL_DAYS",
    "ReleaseAsset",
    "UpdateInfo",
    "DownloadProgress",
    "DownloadResult",
    "check_update",
    "check_update_legacy",
    "download_asset",
    "verify_sha256",
    "should_auto_check",
    "mark_checked",
    "get_release_asset",
    "detect_platform",
]