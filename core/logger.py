"""日志：滚动文件 ~/.multicalc/logs/app.log"""
import logging
import os
from logging.handlers import RotatingFileHandler

_LOG_DIR = os.path.join(os.path.expanduser("~"), ".multicalc", "logs")
_LOG_PATH = os.path.join(_LOG_DIR, "app.log")
_LOGGER = None


def _build():
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
            h = RotatingFileHandler(_LOG_PATH, maxBytes=1_000_000,
                                    backupCount=3, encoding="utf-8")
            h.setFormatter(logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
            logger.addHandler(h)
        except Exception:
            pass
    _LOGGER = logger
    return logger


def get_logger():
    return _LOGGER or _build()


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


def log_path():
    return _LOG_PATH