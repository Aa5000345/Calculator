"""AI 助手：翻译 / 多轮对话 / 智能建议 / 视觉输入。

合并自：core/ai.py + core/ai_conversation.py
        + core/suggestions.py + core.visual_input.py

对外接口：
    # 翻译
    AIConfig, AIResult, translate, available_providers
    # 多轮对话
    Message, Conversation, translate_with_context,
    resolve_pronoun, new_conversation,
    list_conversations, add_conversation,
    remove_conversation, clear_conversations
    # 智能建议
    Suggestion, suggest
    # 视觉输入
    list_recognizers, recognize_image
"""
from __future__ import annotations

import datetime
import importlib.util
import io
import json
import math
import os
import re
import sys
import threading
from dataclasses import dataclass, field
from typing import Optional

from core.base import log_exc, log_warn

__all__ = [
    # 翻译
    "AIConfig", "AIResult", "translate", "available_providers",
    # 对话
    "Message", "Conversation", "translate_with_context",
    "resolve_pronoun", "new_conversation",
    "list_conversations", "add_conversation",
    "remove_conversation", "clear_conversations",
    # 建议
    "Suggestion", "suggest",
    # 视觉输入
    "list_recognizers", "recognize_image",
]


# ===========================================================================
# 数据结构
# ===========================================================================

@dataclass
class AIConfig:
    provider: str = "auto"
    model: str = ""
    base_url: str = ""
    api_key: str = ""
    timeout: float = 20.0
    enabled: bool = True


@dataclass
class AIResult:
    expr: str = ""
    explain: str = ""
    confidence: float = 0.0
    provider: str = ""
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "expr": self.expr, "explain": self.explain,
            "confidence": self.confidence,
            "provider": self.provider, "error": self.error,
        }


# ===========================================================================
# 规则兜底
# ===========================================================================

_RULE_PATTERNS = [
    (re.compile(r"^\s*([\d.]+)\s*的\s*([\d.]+)\s*%\s*$"),
     lambda m: (f"{m.group(1)} * {m.group(2)} / 100",
                f"{m.group(1)} 的 {m.group(2)}%")),
    (re.compile(r"^\s*([\d.]+)\s*的百分之\s*([\d.]+)\s*$"),
     lambda m: (f"{m.group(1)} * {m.group(2)} / 100",
                f"{m.group(1)} 的百分之 {m.group(2)}")),
    (re.compile(r"^\s*([\d.]+)\s*percent\s*of\s*([\d.]+)\s*$",
                re.I),
     lambda m: (f"{m.group(1)} / 100 * {m.group(2)}",
                f"{m.group(1)}% of {m.group(2)}")),
    (re.compile(r"^\s*([\d.]+)\s*的\s*平方根\s*$"),
     lambda m: (f"sqrt({m.group(1)})", f"{m.group(1)} 的平方根")),
    (re.compile(r"^\s*([\d.]+)\s*的\s*立方根\s*$"),
     lambda m: (f"cbrt({m.group(1)})", f"{m.group(1)} 的立方根")),
    (re.compile(r"^\s*([\d.]+)\s*的\s*平方\s*$"),
     lambda m: (f"{m.group(1)}^2", f"{m.group(1)} 的平方")),
    (re.compile(r"^\s*([\d.]+)\s*的\s*立方\s*$"),
     lambda m: (f"{m.group(1)}^3", f"{m.group(1)} 的立方")),
    (re.compile(r"^\s*([\d.]+)\s*的\s*([\d.]+)\s*次方\s*$"),
     lambda m: (f"{m.group(1)}^{m.group(2)}",
                f"{m.group(1)} 的 {m.group(2)} 次方")),
    (re.compile(r"^\s*([\d.]+)\s*的\s*"
                r"(sin|cos|tan|log|ln|exp|asin|acos|atan)\s*$",
                re.I),
     lambda m: (f"{m.group(2).lower()}({m.group(1)})",
                f"{m.group(1)} 的 {m.group(2).lower()}")),
    (re.compile(r"^\s*([\d]+)\s*的\s*阶乘\s*$"),
     lambda m: (f"factorial({m.group(1)})",
                f"{m.group(1)} 的阶乘")),
    (re.compile(r"^\s*([\d.]+)\s*的\s*倒数\s*$"),
     lambda m: (f"1 / {m.group(1)}", f"{m.group(1)} 的倒数")),
    (re.compile(r"^\s*([\d.]+)\s*([A-Z]{3})\s*(?:换成|兑|to|->)"
                r"\s*([A-Z]{3})\s*$", re.I),
     lambda m: (f"{m.group(1)}  {m.group(2).upper()} -> "
                f"{m.group(3).upper()}",
                "请复制到汇率换算面板进行换算")),
]


class RuleProvider:
    name = "rule"
    label = "本地规则"

    def is_available(self) -> bool:
        return True

    def translate(self, prompt, context=None) -> AIResult:
        s = (prompt or "").strip()
        if not s:
            return AIResult(provider=self.name, error="空输入")
        for pat, fn in _RULE_PATTERNS:
            m = pat.match(s)
            if not m:
                continue
            try:
                expr, explain = fn(m)
                return AIResult(
                    expr=expr, explain=explain,
                    confidence=0.9, provider=self.name)
            except Exception:
                continue
        return AIResult(provider=self.name, error="规则未匹配")


# ===========================================================================
# LLM Provider
# ===========================================================================

_SYSTEM_PROMPT = (
    "You are a calculator translator. "
    "Convert the user's natural language into a math expression "
    "that the Python library SymPy can evaluate. "
    "Allowed tokens: numbers, + - * / ** ( ) sqrt cbrt log ln log10 "
    "exp sin cos tan asin acos atan sinh cosh tanh abs factorial pi e "
    "and variable names. "
    "Reply with ONLY the expression. Do not add explanation or "
    "markdown."
)


def _extract_expr(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"```[a-zA-Z]*\n?", "", text).replace("```", "")
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return ""
    expr_re = re.compile(r"^[\d\.\+\-\*/\(\)\^a-zA-Z_, ]+$")
    for ln in lines:
        if expr_re.match(ln):
            return ln
    return lines[0]


class OllamaProvider:
    name = "ollama"
    label = "Ollama (本地)"
    DEFAULT_MODEL = "qwen2.5:7b"
    DEFAULT_URL = "http://localhost:11434"

    def __init__(self, model="", base_url="", timeout=20.0):
        self.model = model or self.DEFAULT_MODEL
        self.base_url = (base_url or self.DEFAULT_URL).rstrip("/")
        self.timeout = float(timeout)

    def is_available(self) -> bool:
        try:
            import requests
            r = requests.get(f"{self.base_url}/api/tags", timeout=2.0)
            return r.status_code == 200
        except Exception:
            return False

    def translate(self, prompt, context=None) -> AIResult:
        try:
            import requests
            payload = {
                "model": self.model,
                "prompt": (f"{_SYSTEM_PROMPT}\n\nUser: {prompt}\n"
                           f"Expression:"),
                "stream": False,
                "options": {"temperature": 0.0},
            }
            r = requests.post(f"{self.base_url}/api/generate",
                              json=payload, timeout=self.timeout)
            data = r.json()
            text = (data.get("response") or "").strip()
            expr = _extract_expr(text)
            if not expr:
                return AIResult(provider=self.name,
                                error="模型未返回有效表达式")
            return AIResult(expr=expr, explain=text,
                            confidence=0.7, provider=self.name)
        except Exception as e:
            log_warn(f"ollama translate failed: {e}", module="ai")
            return AIResult(provider=self.name, error=str(e))


class OpenAIProvider:
    name = "openai"
    label = "OpenAI"

    def __init__(self, api_key="", model="gpt-4o-mini",
                 base_url="https://api.openai.com/v1",
                 timeout=20.0):
        self.api_key = api_key or ""
        self.model = model or "gpt-4o-mini"
        self.base_url = (base_url
                         or "https://api.openai.com/v1").rstrip("/")
        self.timeout = float(timeout)

    def is_available(self) -> bool:
        return bool(self.api_key)

    def translate(self, prompt, context=None) -> AIResult:
        if not self.api_key:
            return AIResult(provider=self.name,
                            error="未配置 API key")
        try:
            import requests
            r = requests.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system",
                         "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": str(prompt)},
                    ],
                    "temperature": 0.0,
                },
                timeout=self.timeout)
            data = r.json()
            text = (data.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")).strip()
            expr = _extract_expr(text)
            if not expr:
                return AIResult(provider=self.name,
                                error=str(data)[:120])
            return AIResult(expr=expr, explain=text,
                            confidence=0.8, provider=self.name)
        except Exception as e:
            log_warn(f"openai translate failed: {e}", module="ai")
            return AIResult(provider=self.name, error=str(e))


class AnthropicProvider:
    name = "anthropic"
    label = "Anthropic Claude"

    def __init__(self, api_key="",
                 model="claude-3-5-sonnet-latest",
                 timeout=20.0):
        self.api_key = api_key or ""
        self.model = model or "claude-3-5-sonnet-latest"
        self.timeout = float(timeout)

    def is_available(self) -> bool:
        return bool(self.api_key)

    def translate(self, prompt, context=None) -> AIResult:
        if not self.api_key:
            return AIResult(provider=self.name,
                            error="未配置 API key")
        try:
            import requests
            r = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "max_tokens": 512,
                    "system": _SYSTEM_PROMPT,
                    "messages": [
                        {"role": "user", "content": str(prompt)}],
                },
                timeout=self.timeout)
            data = r.json()
            text = ""
            for block in data.get("content", []):
                if block.get("type") == "text":
                    text += block.get("text", "")
            text = text.strip()
            expr = _extract_expr(text)
            if not expr:
                return AIResult(provider=self.name,
                                error=str(data)[:120])
            return AIResult(expr=expr, explain=text,
                            confidence=0.8, provider=self.name)
        except Exception as e:
            log_warn(f"anthropic translate failed: {e}", module="ai")
            return AIResult(provider=self.name, error=str(e))


# ===========================================================================
# 主入口：translate / available_providers
# ===========================================================================

def _build_providers(cfg: AIConfig):
    pref = (cfg.provider or "auto").lower()
    if pref == "rule":
        return [RuleProvider()]
    if pref == "ollama":
        return [
            OllamaProvider(model=cfg.model,
                           base_url=cfg.base_url,
                           timeout=cfg.timeout),
            RuleProvider(),
        ]
    if pref == "openai":
        return [
            OpenAIProvider(api_key=cfg.api_key, model=cfg.model,
                           timeout=cfg.timeout),
            RuleProvider(),
        ]
    if pref == "anthropic":
        return [
            AnthropicProvider(api_key=cfg.api_key,
                              model=cfg.model,
                              timeout=cfg.timeout),
            RuleProvider(),
        ]

    # auto
    out = []
    ollama = OllamaProvider(model=cfg.model,
                            base_url=cfg.base_url,
                            timeout=cfg.timeout)
    if ollama.is_available():
        out.append(ollama)
    if cfg.api_key:
        out.append(OpenAIProvider(api_key=cfg.api_key,
                                  model=cfg.model,
                                  timeout=cfg.timeout))
    out.append(RuleProvider())
    return out


def translate(prompt: str, config: AIConfig | None = None,
              context=None) -> AIResult:
    """主翻译入口：依次尝试可用 provider，返回第一个成功结果。"""
    cfg = config or AIConfig()
    prompt = (prompt or "").strip()
    if not prompt:
        return AIResult(error="输入为空")

    providers = _build_providers(cfg)
    last_error = ""
    for p in providers:
        try:
            if not p.is_available():
                continue
            res = p.translate(prompt, context)
            if res.expr and not res.error:
                return res
            last_error = res.error or last_error
        except Exception as e:
            log_exc(e, module=f"ai.translate.{p.name}")
            last_error = str(e)

    try:
        rule_res = RuleProvider().translate(prompt, context)
        if rule_res.expr:
            return rule_res
    except Exception:
        pass

    return AIResult(error=last_error or "无可用 provider")


def available_providers(config: AIConfig | None = None) -> list:
    cfg = config or AIConfig()
    names = []
    if OllamaProvider(model=cfg.model,
                      base_url=cfg.base_url).is_available():
        names.append("ollama")
    if cfg.api_key:
        names.append("openai")
        names.append("anthropic")
    names.append("rule")
    return names


# ===========================================================================
# 多轮对话
# ===========================================================================

@dataclass
class Message:
    role: str = "user"
    content: str = ""
    expr: str = ""
    result: str = ""
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

    def add_user(self, text: str):
        self.messages.append(Message(role="user", content=str(text)))
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
        m = self.last_assistant()
        return m.expr if m else ""

    def last_result(self) -> str:
        m = self.last_assistant()
        return m.result if m else ""

    def history_pairs(self, max_turns: int = 5) -> list:
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
        pairs = self.history_pairs(max_turns)
        if not pairs:
            return ""
        lines = []
        for u, e in pairs:
            lines.append(f"User: {u}")
            lines.append(f"Expression: {e}")
        return "\n".join(lines)

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


# ---------------- 代词解析 ----------------

_PRONOUN_RE = re.compile(
    r"(那个|那|这个|这|它|其|刚才|上一个|上一步|上一轮|之前|前面|"
    r"刚刚|刚|the\s+last|previous|that|it)\b",
    re.IGNORECASE,
)

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
    "的": "*",
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

    if _PRONOUN_RE.search(s):
        s = _PRONOUN_RE.sub(f"({last_expr})", s, count=1)

    return s


def _looks_like_expr(text: str) -> bool:
    s = str(text).strip()
    if not s:
        return False
    if re.search(r"[\u4e00-\u9fff]", s):
        return False
    return bool(re.match(
        r"^[\d\.\+\-\*/\(\)\^\sA-Za-z_,]+$", s))


def translate_with_context(
        prompt: str,
        config: Optional[AIConfig] = None,
        conversation: Optional[Conversation] = None,
        *,
        resolve_references: bool = True,
) -> AIResult:
    """带上下文的多轮翻译。"""
    prompt = (prompt or "").strip()
    if not prompt:
        return AIResult(error="输入为空")

    effective = prompt
    if resolve_references and conversation is not None:
        last = conversation.last_expr()
        if last:
            effective = resolve_pronoun(prompt, last)

    if effective != prompt and _looks_like_expr(effective):
        return AIResult(
            expr=effective,
            explain=f"上下文替换：{prompt} → {effective}",
            confidence=0.85,
            provider="context",
        )

    ctx = ""
    if conversation is not None:
        ctx = conversation.build_context(max_turns=5)
    context = {"history": ctx} if ctx else None

    try:
        return translate(effective, config, context)
    except Exception as e:
        log_exc(e, module="ai.translate_with_context")
        return AIResult(error=str(e))


# ---------------- 会话持久化 ----------------

_CONV_LOCK = threading.RLock()
_CONV_CACHE: list | None = None
_MAX_CONVERSATIONS = 20


def _conv_path() -> str:
    return os.path.join(
        os.path.expanduser("~"),
        ".multicalc", "ai_conversations.json")


def _load_conversations() -> list:
    global _CONV_CACHE
    if _CONV_CACHE is not None:
        return _CONV_CACHE
    try:
        with open(_conv_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            _CONV_CACHE = [Conversation.from_dict(x)
                           for x in data
                           if isinstance(x, dict)]
        else:
            _CONV_CACHE = []
    except Exception:
        _CONV_CACHE = []
    return _CONV_CACHE


def _save_conversations(items: list):
    global _CONV_CACHE
    try:
        os.makedirs(os.path.dirname(_conv_path()),
                    exist_ok=True)
        items = items[-_MAX_CONVERSATIONS:]
        with open(_conv_path(), "w", encoding="utf-8") as f:
            json.dump([c.to_dict() for c in items], f,
                      ensure_ascii=False, indent=2)
        _CONV_CACHE = items
    except Exception as e:
        log_warn(f"save conversations failed: {e}",
                 module="ai")


def list_conversations() -> list:
    with _CONV_LOCK:
        return list(_load_conversations())


def add_conversation(conv: Conversation):
    with _CONV_LOCK:
        items = list(_load_conversations())
        items = [c for c in items if c.id != conv.id]
        items.append(conv)
        _save_conversations(items)


def remove_conversation(conv_id: str):
    with _CONV_LOCK:
        items = [c for c in _load_conversations()
                 if c.id != conv_id]
        _save_conversations(items)


def clear_conversations():
    with _CONV_LOCK:
        _save_conversations([])


def new_conversation(title: str = "") -> Conversation:
    return Conversation(title=title or "新对话")


# ===========================================================================
# 智能建议
# ===========================================================================

@dataclass
class Suggestion:
    kind: str
    text: str
    action: str = ""
    payload: dict = field(default_factory=dict)
    priority: int = 50


_TRIG_RE = re.compile(
    r"\b(sin|cos|tan|exp|log|ln|sqrt)\s*\(", re.I)
_CURRENCY_RE = re.compile(r"\b([A-Z]{3})\b")
_FACTORIAL_RE = re.compile(r"(\d+)\s*!")
_BIG_INT_RE = re.compile(r"\b\d{15,}\b")
_PERCENT_RE = re.compile(
    r"^\s*[\d.]+\s*%\s*(off|on|of)\s+[\d.]+\s*$", re.I)
_CONSTANTS = ("pi", "e", "E", "oo", "I")
_UNIT_HINTS = (
    "km", "m", "cm", "mm", "kg", "g", "mg", "lb", "oz",
    "l", "ml", "gal", "c", "f", "k", "s", "ms", "min",
    "h", "day", "week", "year",
)


def _is_expr_like(text: str) -> bool:
    s = str(text).strip()
    if not s:
        return False
    if not re.search(r"\d", s):
        return False
    return bool(re.match(
        r"^[\d\.\+\-\*/\(\)\^\sA-Za-z_,!]+$", s))


def _find_similar(text: str, history: list) -> str:
    s = text.lower()
    best = ""
    best_score = 0
    for h in history[:50]:
        hh = str(h).strip().lower()
        if not hh or hh == s:
            continue
        score = 0
        for a, b in zip(s, hh):
            if a == b:
                score += 1
            else:
                break
        if score > best_score and score >= 3:
            best_score = score
            best = str(h)
    return best


def suggest(input_text: str, *,
            history_exprs: Optional[list] = None,
            last_result: str = "",
            module_key: str = "",
            limit: int = 3) -> list:
    """根据输入给建议。返回 list[Suggestion]（按 priority 降序）。"""
    text = (input_text or "").strip()
    out: list = []

    # 1. 三角函数 → 绘图
    if _TRIG_RE.search(text):
        out.append(Suggestion(
            kind="plot",
            text="试试绘制它的图像？",
            action="plot",
            payload={"expr": text},
            priority=80,
        ))

    # 2. 货币换算（保留原判断逻辑，避免行为变化）
    m = _CURRENCY_RE.search(text)
    if m and m.group(1) not in ("USD",) \
            or text.upper().count("USD"):
        codes = _CURRENCY_RE.findall(text.upper())
        if len(codes) == 1 and codes[0] not in ("USD",):
            out.append(Suggestion(
                kind="convert",
                text=f"换算 {codes[0]} → USD？",
                action="convert",
                payload={"from": codes[0], "to": "USD"},
                priority=70,
            ))
        elif len(codes) == 2 and codes[0] != codes[1]:
            out.append(Suggestion(
                kind="convert",
                text=f"换算 {codes[0]} → {codes[1]}？",
                action="convert",
                payload={"from": codes[0], "to": codes[1]},
                priority=75,
            ))

    # 3. 大整数警告
    if _BIG_INT_RE.search(text):
        out.append(Suggestion(
            kind="warn",
            text="数字很大，建议用科学计数法或 Float",
            action="tip",
            priority=60,
        ))

    # 4. 大阶乘警告
    m = _FACTORIAL_RE.search(text)
    if m:
        try:
            n = int(m.group(1))
            if n > 20:
                out.append(Suggestion(
                    kind="warn",
                    text=f"{n}! 结果巨大，可能耗时较长",
                    action="tip",
                    priority=65,
                ))
            elif n < 10:
                out.append(Suggestion(
                    kind="calc",
                    text=f"要不要试试 {n + 1}! 或 {n * 2}!？",
                    action="replace",
                    payload={"expr": f"{n * 2}!"},
                    priority=40,
                ))
        except ValueError:
            pass

    # 5. 百分比语法提示
    if "%" in text and not _PERCENT_RE.match(text):
        out.append(Suggestion(
            kind="tip",
            text="支持 `20% off 100` / `tip 15% on 200`",
            action="tip",
            priority=35,
        ))

    # 6. 单位换算
    for u in _UNIT_HINTS:
        if re.search(rf"\b\d+(\.\d+)?\s*{u}\b", text, re.I):
            out.append(Suggestion(
                kind="convert",
                text="发送到单位面板换算？",
                action="send_unit",
                payload={"text": text},
                priority=55,
            ))
            break

    # 7. 与历史对比
    if (history_exprs and text and last_result
            and module_key == "basic"):
        prev = _find_similar(text, history_exprs)
        if prev and prev != text:
            out.append(Suggestion(
                kind="compare",
                text=f"上次你算过 {prev[:30]}",
                action="recall",
                payload={"expr": prev},
                priority=45,
            ))

    # 8. 一般表达式 → 管道建议
    if text and _is_expr_like(text):
        if module_key in ("basic", "scientific", "pipeline"):
            out.append(Suggestion(
                kind="tip",
                text="可以用管道：`%s | round(3)`" % text[:20],
                action="send_pipeline",
                payload={"text": text},
                priority=30,
            ))

    # 9. 常量提示
    if any(c in text for c in _CONSTANTS):
        out.append(Suggestion(
            kind="tip",
            text="常量：pi / e / oo(∞) / I(虚数)",
            action="tip",
            priority=20,
        ))

    out.sort(key=lambda s: -s.priority)
    return out[:limit]


# ===========================================================================
# 视觉输入（手写 / 截图 → 表达式）
# ===========================================================================

_PIX2TEX_MODEL = None


def _has_pix2tex() -> bool:
    """判断 pix2tex 是否已安装。

    ⚠ 使用 find_spec 而不是 import —— pix2tex 的 __init__ 会 import torch
    并可能在首次使用时下载模型权重（~97 MB），绝不能在启动阶段触发。
    """
    try:
        return importlib.util.find_spec("pix2tex") is not None
    except Exception:
        return False


def _has_openai_vision(api_key: str = "") -> bool:
    return bool(api_key)


def _py314_note() -> str:
    if sys.version_info < (3, 14):
        return ""
    return ("（注意：Python 3.14 上 torch.jit 已弃用，"
            "pix2tex 可能不稳定）")


def list_recognizers(api_key: str = "") -> list:
    """返回可用识别器元数据（不触发任何重加载）。"""
    out = []
    pix_ok = _has_pix2tex()
    out.append({
        "name": "pix2tex",
        "label": "pix2tex（LaTeX OCR）",
        "available": pix_ok,
        "hint": ("pip install pix2tex" if not pix_ok
                 else _py314_note() or ""),
    })
    api_ok = _has_openai_vision(api_key)
    out.append({
        "name": "openai_vision",
        "label": "OpenAI 视觉（gpt-4o）",
        "available": api_ok,
        "hint": "在 AI 面板设置 API key" if not api_ok else "",
    })
    out.append({
        "name": "manual",
        "label": "手动输入",
        "available": True,
        "hint": "画完/贴图后直接在输入框敲表达式",
    })
    return out


def _recognize_pix2tex(image_bytes: bytes) -> dict:
    global _PIX2TEX_MODEL

    if not _has_pix2tex():
        return {"expr": "", "provider": "pix2tex",
                "error": "未安装 pix2tex：pip install pix2tex"}

    try:
        from pix2tex.cli import LatexOCR
        from PIL import Image
    except ImportError as e:
        return {"expr": "", "provider": "pix2tex",
                "error": f"pix2tex 导入失败：{e}"}
    except Exception as e:  # noqa: BLE001
        return {"expr": "", "provider": "pix2tex",
                "error": (f"pix2tex 初始化失败"
                          f"（{sys.version.split()[0]}）：{e}")}

    try:
        if _PIX2TEX_MODEL is None:
            _PIX2TEX_MODEL = LatexOCR()
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        latex = _PIX2TEX_MODEL(img)
        return {"expr": (latex or "").strip(),
                "provider": "pix2tex", "error": ""}
    except Exception as e:  # noqa: BLE001
        return {"expr": "", "provider": "pix2tex",
                "error": f"识别失败：{e}"}


def _recognize_openai_vision(image_bytes: bytes, api_key: str,
                             model: str = "gpt-4o-mini",
                             timeout: float = 30.0) -> dict:
    if not api_key:
        return {"expr": "", "provider": "openai_vision",
                "error": "未配置 API key"}
    try:
        import base64
        import requests
    except Exception as e:
        return {"expr": "", "provider": "openai_vision",
                "error": str(e)}

    try:
        b64 = base64.b64encode(image_bytes).decode("ascii")
        prompt = (
            "You are a calculator expression extractor. "
            "Read the math expression in the image and reply with ONLY "
            "the SymPy-compatible expression. No markdown, no "
            "explanation."
        )
        r = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}",
                     "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url",
                         "image_url": {
                             "url": (f"data:image/png;base64,"
                                     f"{b64}")}},
                    ],
                }],
                "temperature": 0.0,
            },
            timeout=timeout)
        data = r.json()
        text = (data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")).strip()
        if "```" in text:
            text = re.sub(r"```[a-zA-Z]*\n?", "", text)
            text = text.replace("```", "")
        return {"expr": text.strip(),
                "provider": "openai_vision", "error": ""}
    except Exception as e:
        return {"expr": "", "provider": "openai_vision",
                "error": str(e)}


def recognize_image(image_bytes: bytes, provider: str = "auto",
                    api_key: str = "") -> dict:
    """从图片识别表达式。

    注意：本函数是同步阻塞的（pix2tex 首次可能 30–60s）。
    调用方应放在 QThread 里。
    """
    if not image_bytes:
        return {"expr": "", "provider": provider,
                "error": "图片为空"}

    if provider == "manual":
        return {"expr": "", "provider": "manual", "error": ""}

    if provider == "pix2tex":
        return _recognize_pix2tex(image_bytes)

    if provider == "openai_vision":
        return _recognize_openai_vision(image_bytes, api_key)

    # auto：优先 pix2tex，其次 openai_vision
    if _has_pix2tex():
        r = _recognize_pix2tex(image_bytes)
        if r["expr"]:
            return r
    if api_key:
        r = _recognize_openai_vision(image_bytes, api_key)
        if r["expr"]:
            return r
    return {"expr": "", "provider": "auto",
            "error": ("无可用识别器：请安装 pix2tex 或在 AI 面板"
                      "配置 API key")}