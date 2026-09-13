"""国际化：语言包 + 数字/日期/货币本地化。"""
import datetime
import json
import os

try:
    from babel.numbers import format_decimal, format_currency
    from babel.dates import format_date as babel_format_date
    _HAS_BABEL = True
except Exception:
    _HAS_BABEL = False


class I18n:
    def __init__(self, dir_path, lang="zh_CN"):
        self.dir = dir_path
        self.lang = lang
        self.trans = {}
        self.load(lang)

    def load(self, lang):
        path = os.path.join(self.dir, f"{lang}.json")
        if not os.path.exists(path):
            path = os.path.join(self.dir, "en_US.json")
            lang = "en_US"
        with open(path, "r", encoding="utf-8") as f:
            self.trans = json.load(f)
        self.lang = lang

    def t(self, key, default=None):
        return self.trans.get(key, default if default is not None else key)

    # ---------------- 本地化 ----------------

    def format_number(self, value, decimals=None):
        try:
            if _HAS_BABEL:
                if decimals is not None:
                    pattern = "#,##0." + ("0" * decimals) if decimals else "#,##0"
                    return format_decimal(value, format=pattern,
                                          locale=self.lang)
                return format_decimal(value, locale=self.lang)
        except Exception:
            pass
        try:
            if decimals is None:
                return f"{value:,}"
            return f"{value:,.{decimals}f}"
        except Exception:
            return str(value)

    def format_currency(self, value, currency="USD"):
        try:
            if _HAS_BABEL:
                return format_currency(value, currency, locale=self.lang)
        except Exception:
            pass
        return f"{value:.2f} {currency}"

    def format_date(self, dt, fmt="medium"):
        try:
            if _HAS_BABEL:
                if isinstance(dt, str):
                    dt = datetime.datetime.strptime(dt, "%Y-%m-%d").date()
                return babel_format_date(dt, format=fmt, locale=self.lang)
        except Exception:
            pass
        if isinstance(dt, (datetime.date, datetime.datetime)):
            return dt.strftime("%Y-%m-%d")
        return str(dt)