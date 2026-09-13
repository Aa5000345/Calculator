"""统一异常类型与错误分类。"""
from __future__ import annotations


class CalcError(Exception):
    """所有计算类错误基类。"""
    code = "calc_error"
    friendly_key = "err_calc"

    def __init__(self, message="", *, detail=None, code=None, friendly_key=None):
        super().__init__(message)
        self.message = str(message)
        self.detail = detail if detail is not None else self.message
        if code:
            self.code = code
        if friendly_key:
            self.friendly_key = friendly_key

    def friendly(self, i18n=None) -> str:
        if i18n is not None:
            try:
                msg = i18n.t(self.friendly_key, None)
            except Exception:
                msg = None
            if msg and msg != self.friendly_key:
                return msg
        return self.message or self.friendly_key

    def to_report(self) -> str:
        """用于"复制错误详情"。"""
        return (f"code: {self.code}\n"
                f"friendly_key: {self.friendly_key}\n"
                f"message: {self.message}\n"
                f"detail: {self.detail}")


class InputError(CalcError):
    code = "input_error"
    friendly_key = "err_input"


class MathError(CalcError):
    code = "math_error"
    friendly_key = "err_math"


class NetworkError(CalcError):
    code = "network_error"
    friendly_key = "err_network"


class UnitError(CalcError):
    code = "unit_error"
    friendly_key = "err_unit"


class CancelledError(CalcError):
    code = "cancelled"
    friendly_key = "err_cancelled"