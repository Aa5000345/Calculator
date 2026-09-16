"""冒烟测试：遍历 all_panels() 全部实例化，防止面板崩溃。

覆盖 P0 修复点：
- widgets/__init__.py 导入不再失败
- base_convert / ai / crypto_tools 面板可构造
- 所有 25 个面板在新代码下不会抛异常

运行：pytest tests/test_smoke.py -v
"""
from __future__ import annotations

import os
import sys

# ---- 双保险：即使 conftest 因故未加载，也保证能 import core / ui ----
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# 无界面后端，必须在 import matplotlib 之前设置
os.environ.setdefault("MPLBACKEND", "Agg")
os.environ.setdefault("QT_API", "pyside6")

import pytest


# ---------------------------------------------------------------------------
# 轻量 Fake 环境：让面板不需要完整的 MainWindow / Settings 也能构造
# ---------------------------------------------------------------------------

class _FakeSettings:
    def __init__(self):
        self._data = {
            "language": "zh_CN",
            "theme": "dark",
            "result_format": "text",
            "result_digits": 0,
            "result_sci": False,
            "result_fraction": False,
            "result_percent": False,
            "visible_modules": {},
            "module_groups": [],
            "manual_rates": {},
            "button_layout": [],
            "angle_mode": "RAD",
            "ai_provider": "auto",
            "currency_source": "open.er-api.com",
            "tray_enabled": False,
            "inline_preview": True,
            "_drafts": {},
            "_themes": {},
        }

    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value, notify=True):
        self._data[key] = value

    def update(self, mapping, notify=True):
        self._data.update(mapping)

    def get_draft(self, key, default=""):
        return self._data.get("_drafts", {}).get(key, default)

    def set_draft(self, key, value):
        self._data.setdefault("_drafts", {})[key] = value

    def is_module_visible(self, key):
        return True

    def set_module_visible(self, key, visible):
        pass

    def add_listener(self, fn):
        pass

    def remove_listener(self, fn):
        pass

    def palette(self, override=None):
        return {"bg": "#1e1e1e", "fg": "#ffffff", "panel": "#2d2d30",
                "accent": "#007acc", "border": "#3f3f46", "hover": "#3a3d41"}

    def themes(self):
        return {}

    def flush(self):
        pass


class _FakeI18n:
    lang = "zh_CN"

    def t(self, key, default=None):
        return default if default is not None else key

    def load(self, lang):
        pass


class _FakeHistory:
    def add(self, *a, **kw):
        pass

    def list(self, **kw):
        return []

    def count(self, **kw):
        return 0

    def modules(self):
        return []

    def tags(self):
        return []

    def clear(self):
        pass

    def clear_module(self, m):
        pass

    def remove(self, i):
        pass

    def toggle_favorite(self, i):
        return False

    def set_favorite_value(self, i, v):
        pass

    def set_tags(self, i, t):
        pass

    def export_json(self, p):
        pass

    def export_csv(self, p):
        pass


class _Ctx:
    def __init__(self, base_path):
        self.base_path = base_path
        self.settings = _FakeSettings()
        self.i18n = _FakeI18n()
        self.history = _FakeHistory()
        self.main_window = None
        self.reuse_handler = lambda *a: None


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


@pytest.fixture(scope="module")
def base_path(tmp_path_factory):
    """准备一个带 config/ 的最小目录。"""
    p = tmp_path_factory.mktemp("multicalc_smoke")
    cfg = p / "config"
    cfg.mkdir()
    # 空离线汇率，避免 CurrencyPanel 试图联网
    (cfg / "rates_offline.json").write_text(
        '{"base":"USD","updated":0,"rates":{"USD":1,"CNY":7.2}}',
        encoding="utf-8")
    return str(p)


# ---------------------------------------------------------------------------
# 测试
# ---------------------------------------------------------------------------

def test_widgets_import():
    """P0-1：widgets/__init__.py 不应再抛 ImportError。"""
    from ui import widgets  # noqa: F401
    assert hasattr(widgets, "COMPACT_LAYOUT")
    assert hasattr(widgets, "SCI_LAYOUT")
    assert hasattr(widgets, "KeyButton")
    assert hasattr(widgets, "FocusTracker")


def test_keyboard_layouts_alias():
    """P0-2：向后兼容别名应为正确的 Layout 对象。"""
    from ui.widgets.keyboard_layouts import (
        LAYOUT_BASIC, LAYOUT_SCIENTIFIC,
    )
    from ui.widgets import COMPACT_LAYOUT, SCI_LAYOUT
    assert COMPACT_LAYOUT is LAYOUT_BASIC
    assert SCI_LAYOUT is LAYOUT_SCIENTIFIC


def test_base_convert_live_integer(qapp):
    """P0-3：进制联动 — 整数路径。"""
    from ui.panels.base_convert import BasePanel
    p = BasePanel(_FakeSettings(), _FakeI18n(), _FakeHistory())
    p.in_dec.setText("255")
    assert p.in_hex.text().upper() == "FF"
    assert p.in_bin.text() == "11111111"
    assert p.in_oct.text() == "377"


def test_base_convert_live_fraction(qapp):
    """P0-3：进制联动 — 小数路径（修复前不联动）。"""
    from ui.panels.base_convert import BasePanel
    p = BasePanel(_FakeSettings(), _FakeI18n(), _FakeHistory())
    p.in_dec.setText("10.5")
    # 10.5 = 1010.1 (bin) = A.8 (hex) = 12.4 (oct)
    assert p.in_bin.text() == "1010.1"
    assert p.in_hex.text().upper() == "A.8"
    assert p.in_oct.text() == "12.4"


def test_base_convert_hex_to_others(qapp):
    """P0-3：从十六进制为源时其他三个联动。"""
    from ui.panels.base_convert import BasePanel
    p = BasePanel(_FakeSettings(), _FakeI18n(), _FakeHistory())
    p.in_hex.setText("FF")
    assert p.in_dec.text() == "255"
    assert p.in_bin.text() == "11111111"
    assert p.in_oct.text() == "377"


def test_ai_panel_constructs(qapp):
    """P0-4：AI 面板（Worker 化后）可构造。"""
    from ui.panels.ai import AIPanel
    p = AIPanel(_FakeSettings(), _FakeI18n(), _FakeHistory())
    assert p.translate_btn is not None
    assert p.send_btn.isEnabled() is False


def test_crypto_panel_constructs(qapp):
    """P0-5：加密面板（RSA Worker 化后）可构造。"""
    from ui.panels.crypto_tools import CryptoPanel
    p = CryptoPanel(_FakeSettings(), _FakeI18n(), _FakeHistory())
    assert p.rsa_gen_btn is not None


def test_all_panels_instantiate(qapp, base_path):
    """遍历注册表，全部面板应能成功实例化。"""
    from core import rates as rates_mod
    try:
        rates_mod.init(base_path)
    except Exception:
        pass

    from ui.panels.registry import all_panels

    ctx = _Ctx(base_path)
    failures = []
    for spec in all_panels():
        try:
            w = spec.factory(ctx)
            assert w is not None
            try:
                if hasattr(w, "shutdown_workers"):
                    w.shutdown_workers(100)
            except Exception:
                pass
            try:
                w.setParent(None)
                w.deleteLater()
            except Exception:
                pass
        except Exception as e:  # noqa: BLE001
            failures.append((spec.key, repr(e)))

    assert not failures, f"面板实例化失败: {failures}"