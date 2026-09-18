"""AI 多轮对话：保留上下文，让「刚才那个结果乘 2」可行。

设计：
- Conversation 保存消息列表（role / content / expr / result）
- 上下文构建：把最近 N 轮拼成 prompt 前缀
- 代词解析：「它」「那个」「刚才」「上一个」指向上一个表达式
- 持久化：~/.multicalc/ai_conversations.json（只保留最近 20 个会话）
- 不依赖 Qt；由 UI 层调用

用法：
    conv = Conversation()
    conv.add_user("100 的 15%")
    conv.add_assistant(expr="100 * 15 / 100", result="15")

    # 多轮翻译
    r = translate_with_context("刚才的结果乘 2", config, conv)
    # r.expr == "(100 * 15 / 100) * 2"
"""
from __future__ import annotations

import datetime
import json
import os
import re
import threading
from dataclasses import dataclass, field
from typing import Optional

from core import ai as ai_mod
from core.logger import log_exc, log_warn


# ---------------------------------------------------------------------------
# 数据
# ---------------------------------------------------------------------------

@dataclass
class Message:
    role: str = "user"       # "user" | "assistant" | "system"
    content: str = ""        # 原文
    expr: str = ""           # 翻译后的表达式（assistant 才有）
    result: str = ""         # 计算结果（assistant 才有）
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.datetime.now().isoformat(
                timespec="seconds")

    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "content": self.content,
            "expr": self.expr,
            "result": self.result,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Message":
        return cls(
            role=str(d.get("role") or "user"),
            content=str(d.get("content") or ""),
            expr=str(d.get("expr") or ""),
            result=str(d.get("result") or ""),
            timestamp=str(d.get("timestamp") or ""),
        )


@dataclass
class Conversation:
    id: str = ""
    title: str = ""
    messages: list = field(default_factory=list)
    created: str = ""
    modified: str = ""

    def __post_init__(self):
        now = datetime.datetime.now().isoformat(timespec="seconds")
        if not self.id:
            self.id = datetime.datetime.now().strftime(
                "%Y%m%d%H%M%S%f")
        if not self.created:
            self.created = now
        if not self.modified:
            self.modified = now

    # ---------------- 操作 ----------------

    def add_user(self, text: str):
        self.messages.append(Message(
            role="user", content=str(text)))
        self._touch()

    def add_assistant(self, content: str = "",
                      expr: str = "", result: str = ""):
        self.messages.append(Message(
            role="assistant", content=str(content),
            expr=str(expr), result=str(result)))
        self._touch()

    def add_system(self, text: str):
        self.messages.append(Message(
            role="system", content=str(text)))
        self._touch()

    def _touch(self):
        self.modified = datetime.datetime.now().isoformat(
            timespec="seconds")

    def clear(self):
        self.messages.clear()
        self._touch()

    def last_assistant(self) -> Optional[Message]:
        for m in reversed(self.messages):
            if m.role == "assistant":
                return m
        return None

    def last_user(self) -> Optional[Message]:
        for m in reversed(self.messages):
            if m.role == "user":
                return m
        return None

    def last_expr(self) -> str:
        """最近一次翻译后的表达式。"""
        m = self.last_assistant()
        return m.expr if m else ""

    def last_result(self) -> str:
        m = self.last_assistant()
        return m.result if m else ""

    def history_pairs(self, max_turns: int = 5) -> list:
        """返回最近 N 轮的 (user_content, assistant_expr) 列表。"""
        pairs = []
        user_text = ""
        for m in self.messages:
            if m.role == "user":
                user_text = m.content
            elif m.role == "assistant" and user_text:
                pairs.append((user_text, m.expr or m.content))
                user_text = ""
        return pairs[-max_turns:]

    def build_context(self, max_turns: int = 5) -> str:
        """构建多轮上下文（用于 prompt 前缀）。"""
        pairs = self.history_pairs(max_turns)
        if not pairs:
            return ""
        lines = []
        for u, e in pairs:
            lines.append(f"User: {u}")
            lines.append(f"Expression: {e}")
        return "\n".join(lines)

    # ---------------- 序列化 ----------------

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "created": self.created,
            "modified": self.modified,
            "messages": [m.to_dict() for m in self.messages],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Conversation":
        return cls(
            id=str(d.get("id") or ""),
            title=str(d.get("title") or ""),
            created=str(d.get("created") or ""),
            modified=str(d.get("modified") or ""),
            messages=[Message.from_dict(x)
                      for x in (d.get("messages") or [])],
        )


# ---------------------------------------------------------------------------
# 代词解析
# ---------------------------------------------------------------------------

# 「它 / 那个 / 刚才 / 上一个 / 上一步」等代词
_PRONOUN_RE = re.compile(
    r"(那个|那|这个|这|它|其|刚才|上一个|上一步|上一轮|之前|前面|"
    r"刚刚|刚|the\s+last|previous|that|it)\b",
    re.IGNORECASE,
)

# 「再乘 2」/「乘以 2」/「乘以它」
_RESTATE_RE = re.compile(
    r"^(?:再|然后|接着|继续)?\s*"
    r"(乘|乘以|除|除以|加|加上|减|减去|的|幂|平方|立方)"
    r"\s*([0-9.]+|那个|它|结果)?\s*$"
)

_MATH_OP_MAP = {
    "乘": "*", "乘以": "*",
    "除": "/", "除以": "/",
    "加": "+", "加上": "+",
    "减": "-", "减去": "-",
    "幂": "**",
    "平方": "**2", "立方": "**3",
    "的": "*",  # 「的」在中文自然语言里常表示乘法
}


def resolve_pronoun(text: str, last_expr: str) -> str:
    """把文本里的代词替换为上一个表达式。

    例：
        resolve_pronoun("刚才的结果乘 2", "100 * 15 / 100")
        → "(100 * 15 / 100) * 2"
    """
    if not text or not last_expr:
        return text

    s = str(text).strip()

    # 直接是「再乘 2」/「乘以它」
    m = _RESTATE_RE.match(s)
    if m:
        op_cn = m.group(1)
        operand = m.group(2) or "它"
        op = _MATH_OP_MAP.get(op_cn, "")
        if op:
            if operand in ("那个", "它", "结果", ""):
                operand = f"({last_expr})"
            else:
                operand = f"({operand})"
            if op_cn in ("平方", "立方"):
                return f"({last_expr}){op}"
            return f"({last_expr}) {op} {operand}"

    # 含代词的复杂句子：把代词替换为上一个表达式
    if _PRONOUN_RE.search(s):
        # 把代词包成括号表达式，交给 RuleProvider / LLM 继续
        s = _PRONOUN_RE.sub(f"({last_expr})", s, count=1)

    return s


# ---------------------------------------------------------------------------
# 多轮翻译
# ---------------------------------------------------------------------------

def translate_with_context(
        prompt: str,
        config: Optional[ai_mod.AIConfig] = None,
        conversation: Optional[Conversation] = None,
        *,
        resolve_references: bool = True,
) -> ai_mod.AIResult:
    """带上下文的多轮翻译。

    Args:
        prompt: 本轮用户输入
        config: AI 配置
        conversation: 会话（提供上下文）
        resolve_references: 是否自动解析代词

    Returns:
        ai_mod.AIResult（沿用原结构）
    """
    prompt = (prompt or "").strip()
    if not prompt:
        return ai_mod.AIResult(error="输入为空")

    # 1) 代词解析
    effective = prompt
    if resolve_references and conversation is not None:
        last = conversation.last_expr()
        if last:
            effective = resolve_pronoun(prompt, last)

    # 2) 如果解析后变成了纯表达式，直接返回，不走 LLM
    if effective != prompt and _looks_like_expr(effective):
        return ai_mod.AIResult(
            expr=effective,
            explain=f"上下文替换：{prompt} → {effective}",
            confidence=0.85,
            provider="context",
        )

    # 3) 构建上下文前缀
    ctx = ""
    if conversation is not None:
        ctx = conversation.build_context(max_turns=5)

    context = {"history": ctx} if ctx else None

    # 4) 调用原 translate
    try:
        return ai_mod.translate(effective, config, context)
    except Exception as e:
        log_exc(e, module="ai_conversation.translate_with_context")
        return ai_mod.AIResult(error=str(e))


def _looks_like_expr(text: str) -> bool:
    """粗略判断：文本是否像纯表达式（无中文/自然语言）。"""
    s = str(text).strip()
    if not s:
        return False
    # 含中文汉字 → 不像表达式
    if re.search(r"[\u4e00-\u9fff]", s):
        return False
    # 必须只含数字、运算符、括号、字母、空格、点
    return bool(re.match(
        r"^[\d\.\+\-\*/\(\)\^\sA-Za-z_,]+$", s))


# ---------------------------------------------------------------------------
# 会话管理
# ---------------------------------------------------------------------------

_LOCK = threading.RLock()
_CACHE: list | None = None
_MAX_CONVERSATIONS = 20


def _path() -> str:
    return os.path.join(
        os.path.expanduser("~"),
        ".multicalc", "ai_conversations.json")


def _load() -> list:
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    try:
        with open(_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            _CACHE = [Conversation.from_dict(x)
                      for x in data if isinstance(x, dict)]
        else:
            _CACHE = []
    except Exception:
        _CACHE = []
    return _CACHE


def _save(items: list):
    global _CACHE
    try:
        os.makedirs(os.path.dirname(_path()), exist_ok=True)
        # 只保留最近 N 个
        items = items[-_MAX_CONVERSATIONS:]
        with open(_path(), "w", encoding="utf-8") as f:
            json.dump([c.to_dict() for c in items],
                      f, ensure_ascii=False, indent=2)
        _CACHE = items
    except Exception as e:
        log_warn(f"save conversations failed: {e}",
                 module="ai_conversation")


def list_conversations() -> list:
    with _LOCK:
        return list(_load())


def add_conversation(conv: Conversation):
    with _LOCK:
        items = list(_load())
        # 替换同 id
        items = [c for c in items if c.id != conv.id]
        items.append(conv)
        _save(items)


def remove_conversation(conv_id: str):
    with _LOCK:
        items = [c for c in _load() if c.id != conv_id]
        _save(items)


def clear_conversations():
    with _LOCK:
        _save([])


def new_conversation(title: str = "") -> Conversation:
    conv = Conversation(title=title or "新对话")
    return conv


__all__ = [
    "Message",
    "Conversation",
    "translate_with_context",
    "resolve_pronoun",
    "list_conversations",
    "add_conversation",
    "remove_conversation",
    "clear_conversations",
    "new_conversation",
]