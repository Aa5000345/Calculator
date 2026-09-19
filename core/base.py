"""基础层：异常 / 日志 / 密钥 / 版本。

合并自：errors.py + logger.py + secrets.py + version.py

对外接口：
    # 异常
    CalcError, InputError, MathError, NetworkError, UnitError, CancelledError

    # 日志
    get_logger, log_exc, log_info, log_warn, log_error, log_path

    # 密钥（~/.multicalc/secrets.json）
    secret_get, secret_set, secret_all

    # 版本
    Version, parse_version, compare_version, is_newer
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading
from dataclasses import dataclass
from logging.handlers import RotatingFileHandler

__all__ = [
    # errors
    "CalcError", "InputError", "MathError", "NetworkError",
    "UnitError", "CancelledError",
    # logger
    "get_logger", "log_exc", "log_info", "log_warn", "log_error",
    "log_path",
    # secrets
    "secret_get", "secret_set", "secret_all",
    # version
    "Version", "parse_version", "compare_version", "is_newer",
]


# ===========================================================================
# 异常
# ===========================================================================

class CalcError(Exception):
    """所有计算类错误基类。

    - ``message``：用户级文案（优先展示）
    - ``detail``：技术级详情（"复制错误详情"里出现）
    - ``friendly_key``：i18n key
    - ``default_user_message``：i18n 缺失时的兜底文案
    """
    code = "calc_error"
    friendly_key = "err_calc"
    default_user_message = "计算错误"

    def __init__(self, message="", *, detail=None, code=None,
                 friendly_key=None, user_message=None):
        super().__init__(message)
        self.message = str(message)
        self.detail = detail if detail is not None else self.message
        if code:
            self.code = code
        if friendly_key:
            self.friendly_key = friendly_key
        if user_message:
            self.default_user_message = str(user_message)

    def user_message_str(self, i18n=None) -> str:
        """优先级：i18n 翻译 → self.message → default_user_message。"""
        if i18n is not None:
            try:
                msg = i18n.t(self.friendly_key, None)
                if msg and msg != self.friendly_key:
                    return msg
            except Exception:
                pass
        if self.message:
            return self.message
        return self.default_user_message or self.friendly_key

    def friendly(self, i18n=None) -> str:
        """旧接口别名，保持向后兼容。"""
        return self.user_message_str(i18n)

    def to_report(self) -> str:
        return (f"code: {self.code}\n"
                f"friendly_key: {self.friendly_key}\n"
                f"message: {self.message}\n"
                f"detail: {self.detail}")


class InputError(CalcError):
    code = "input_error"
    friendly_key = "err_input"
    default_user_message = "输入无效"


class MathError(CalcError):
    code = "math_error"
    friendly_key = "err_math"
    default_user_message = "数学错误"


class NetworkError(CalcError):
    code = "network_error"
    friendly_key = "err_network"
    default_user_message = "网络错误"


class UnitError(CalcError):
    code = "unit_error"
    friendly_key = "err_unit"
    default_user_message = "单位换算错误"


class CancelledError(CalcError):
    code = "cancelled"
    friendly_key = "err_cancelled"
    default_user_message = "已取消"


# ===========================================================================
# 日志
# ===========================================================================

_LOG_DIR = os.path.join(os.path.expanduser("~"), ".multicalc", "logs")
_LOG_PATH = os.path.join(_LOG_DIR, "app.log")
_LOGGER: logging.Logger | None = None


def _build_logger() -> logging.Logger:
    global _LOGGER
    try:
        os.makedirs(_LOG_DIR, exist_ok=True)
    except Exception:
        pass
    logger = logging.getLogger("multicalc")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    if not logger.handlers:
        try:
            h = RotatingFileHandler(
                _LOG_PATH, maxBytes=1_000_000,
                backupCount=3, encoding="utf-8")
            h.setFormatter(logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
            logger.addHandler(h)
        except Exception:
            pass
    _LOGGER = logger
    return logger


def get_logger() -> logging.Logger:
    return _LOGGER or _build_logger()


def log_exc(exc, *, module="ui", extra=None):
    msg = f"[{module}] {type(exc).__name__}: {exc}"
    if extra:
        msg += f" | {extra}"
    get_logger().exception(msg)


def log_info(msg, *, module="app"):
    get_logger().info(f"[{module}] {msg}")


def log_warn(msg, *, module="app"):
    get_logger().warning(f"[{module}] {msg}")


def log_error(msg, *, module="app"):
    get_logger().error(f"[{module}] {msg}")


def log_path() -> str:
    return _LOG_PATH


# ===========================================================================
# 密钥（与 settings.json 分离，避免导入/导出设置时泄露）
# ===========================================================================

_SECRETS_LOCK = threading.RLock()


def _secrets_path() -> str:
    return os.path.join(os.path.expanduser("~"),
                        ".multicalc", "secrets.json")


def secret_get(key: str, default=None):
    """读取密钥。文件不存在时返回 default。"""
    with _SECRETS_LOCK:
        try:
            with open(_secrets_path(), "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get(key, default)
        except Exception:
            return default


def secret_set(key: str, value):
    """写入或删除一个键（value=None 时删除）。"""
    with _SECRETS_LOCK:
        path = _secrets_path()
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
            try:
                os.chmod(path, 0o600)
            except Exception:
                pass
        except Exception:
            pass


def secret_all() -> dict:
    with _SECRETS_LOCK:
        try:
            with open(_secrets_path(), "r", encoding="utf-8") as f:
                return json.load(f) or {}
        except Exception:
            return {}


# ===========================================================================
# 版本（semver 2.0 简化版）
# ===========================================================================

_VERSION_RE = re.compile(
    r"^\s*v?"
    r"(?P<major>\d+)"
    r"(?:\.(?P<minor>\d+))?"
    r"(?:\.(?P<patch>\d+))?"
    r"(?:[-_](?P<pre>[0-9A-Za-z.\-]+))?"
    r"(?:\+(?P<meta>[0-9A-Za-z.\-]+))?"
    r"\s*$"
)


@dataclass
class Version:
    major: int = 0
    minor: int = 0
    patch: int = 0
    pre: tuple = ()
    meta: str = ""
    raw: str = ""

    def __str__(self) -> str:
        s = f"{self.major}.{self.minor}.{self.patch}"
        if self.pre:
            s += "-" + ".".join(str(x) for x in self.pre)
        if self.meta:
            s += "+" + self.meta
        return s

    def to_tuple(self) -> tuple:
        return (self.major, self.minor, self.patch)


def _parse_pre(s: str) -> tuple:
    """把 pre-release 字符串拆成 (type_rank, parts)。

    type_rank: 0=alpha, 1=beta, 2=rc, 3=其它
    """
    if not s:
        return ()
    lower = s.lower()
    if lower.startswith("alpha") or lower.startswith("a"):
        rank = 0
        rest = s[5:] if lower.startswith("alpha") else s[1:]
    elif lower.startswith("beta") or lower.startswith("b"):
        rank = 1
        rest = s[4:] if lower.startswith("beta") else s[1:]
    elif lower.startswith("rc"):
        rank = 2
        rest = s[2:]
    else:
        rank = 3
        rest = s

    nums = []
    for seg in rest.replace("-", ".").split("."):
        seg = seg.strip()
        if not seg:
            continue
        try:
            nums.append(int(seg))
        except ValueError:
            nums.append(seg)
    return (rank, tuple(nums))


def parse_version(v) -> Version:
    s = str(v or "").strip()
    m = _VERSION_RE.match(s)
    if not m:
        return Version(raw=s)
    return Version(
        major=int(m.group("major") or 0),
        minor=int(m.group("minor") or 0),
        patch=int(m.group("patch") or 0),
        pre=_parse_pre(m.group("pre") or ""),
        meta=m.group("meta") or "",
        raw=s,
    )


def compare_version(a, b) -> int:
    """返回 -1 / 0 / 1。"""
    va = a if isinstance(a, Version) else parse_version(a)
    vb = b if isinstance(b, Version) else parse_version(b)

    ta, tb = va.to_tuple(), vb.to_tuple()
    if ta < tb:
        return -1
    if ta > tb:
        return 1

    if not va.pre and not vb.pre:
        return 0
    if not va.pre:
        return 1
    if not vb.pre:
        return -1

    ra, pa = va.pre
    rb, pb = vb.pre
    if ra != rb:
        return -1 if ra < rb else 1
    if pa == pb:
        return 0
    for x, y in zip(pa, pb):
        if type(x) is type(y):
            if x < y:
                return -1
            if x > y:
                return 1
        else:
            # 数字 < 字符串
            if isinstance(x, int) and isinstance(y, str):
                return -1
            if isinstance(x, str) and isinstance(y, int):
                return 1
            xs, ys = str(x), str(y)
            if xs < ys:
                return -1
            if xs > ys:
                return 1
    if len(pa) < len(pb):
        return -1
    if len(pa) > len(pb):
        return 1
    return 0


def is_newer(latest, current) -> bool:
    return compare_version(latest, current) > 0