"""统一异常类型与错误分类。

变更（本轮）：
- 增加 default_user_message 类属性（用户级兜底文案）；
- 新增 user_message()：i18n → message → default_user_message 三级 fallback；
- friendly() 保留为旧接口别名；
- to_report() 输出技术级详情。
"""
from __future__ import annotations


class CalcError(Exception):
    """所有计算类错误基类。

    - ``message``：用户级文案（优先展示）
    - ``detail``：技术级详情（仅「复制错误详情」里出现）
    - ``friendly_key``：i18n key
    - ``default_user_message``：i18n 缺失时的兜底用户级文案
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

    # 旧接口别名（保持向后兼容）
    def friendly(self, i18n=None) -> str:
        return self.user_message_str(i18n)

    def to_report(self) -> str:
        """用于「复制错误详情」。"""
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