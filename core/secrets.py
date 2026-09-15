"""API 密钥独立存储：~/.multicalc/secrets.json。

与 settings.json 分离，避免在导入/导出设置时泄露密钥。
"""
from __future__ import annotations

import json
import os
import threading

_LOCK = threading.RLock()


def _path() -> str:
    return os.path.join(os.path.expanduser("~"),
                        ".multicalc", "secrets.json")


def get(key: str, default=None):
    with _LOCK:
        try:
            with open(_path(), "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get(key, default)
        except Exception:
            return default


def set(key: str, value):
    """写入或删除一个键（value=None 时删除）。"""
    with _LOCK:
        path = _path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if not isinstance(data, dict):
                    data = {}
            else:
                data = {}
        except Exception:
            data = {}
        if value is None:
            data.pop(key, None)
        else:
            data[key] = value
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            # 尽力收紧密钥文件权限（Windows 上无效果，静默忽略）
            try:
                os.chmod(path, 0o600)
            except Exception:
                pass
        except Exception:
            pass


def all_keys() -> dict:
    with _LOCK:
        try:
            with open(_path(), "r", encoding="utf-8") as f:
                return json.load(f) or {}
        except Exception:
            return {}