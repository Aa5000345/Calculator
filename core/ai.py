"""AI 助手：自然语言 → 表达式翻译层。

Provider 链（按 auto 顺序）：
    1. OllamaProvider     —— 本地 LLM，自动探测 localhost:11434
    2. OpenAIProvider     —— 云端 GPT（需 API key）
    3. AnthropicProvider  —— 云端 Claude（需 API key）
    4. RuleProvider       —— 本地正则兜底（永远可用）

对外只暴露：
    AIConfig
    AIResult
    translate(prompt, config, context=None) -> AIResult
    RuleProvider / OllamaProvider / OpenAIProvider / AnthropicProvider
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from core.logger import log_exc, log_warn


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------

@dataclass
class AIConfig:
    provider: str = "auto"        # auto / rule / ollama / openai / anthropic
    model: str = ""               # 留空使用 provider 默认
    base_url: str = ""            # Ollama: http://localhost:11434
    api_key: str = ""             # 云端服务需要
    timeout: float = 20.0
    enabled: bool = True


@dataclass
class AIResult:
    expr: str = ""
    explain: str = ""
    confidence: float = 0.0
    provider: str = ""
    error: str = ""

    def to_dict(self):
        return {
            "expr": self.expr, "explain": self.explain,
            "confidence": self.confidence, "provider": self.provider,
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# RuleProvider：本地正则兜底
# ---------------------------------------------------------------------------

# 每条：(正则, 匹配组 → (表达式, 解释))
_RULE_PATTERNS = [
    # 百分比
    (re.compile(r"^\s*([\d.]+)\s*的\s*([\d.]+)\s*%\s*$"),
     lambda m: (f"{m.group(1)} * {m.group(2)} / 100",
                f"{m.group(1)} 的 {m.group(2)}%")),
    (re.compile(r"^\s*([\d.]+)\s*的百分之\s*([\d.]+)\s*$"),
     lambda m: (f"{m.group(1)} * {m.group(2)} / 100",
                f"{m.group(1)} 的百分之 {m.group(2)}")),
    (re.compile(r"^\s*([\d.]+)\s*percent\s*of\s*([\d.]+)\s*$", re.I),
     lambda m: (f"{m.group(1)} / 100 * {m.group(2)}",
                f"{m.group(1)}% of {m.group(2)}")),
    # 平方 / 立方 / 平方根 / 立方根
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
    # 三角函数 / 对数
    (re.compile(r"^\s*([\d.]+)\s*的\s*(sin|cos|tan|log|ln|exp|asin|acos|atan)\s*$",
                re.I),
     lambda m: (f"{m.group(2).lower()}({m.group(1)})",
                f"{m.group(1)} 的 {m.group(2).lower()}")),
    # 阶乘
    (re.compile(r"^\s*([\d]+)\s*的\s*阶乘\s*$"),
     lambda m: (f"factorial({m.group(1)})", f"{m.group(1)} 的阶乘")),
    # 倒数
    (re.compile(r"^\s*([\d.]+)\s*的\s*倒数\s*$"),
     lambda m: (f"1 / {m.group(1)}", f"{m.group(1)} 的倒数")),
    # 货币提示（不直接算，让用户切到汇率面板）
    (re.compile(r"^\s*([\d.]+)\s*([A-Z]{3})\s*(?:换成|兑|to|->)\s*([A-Z]{3})\s*$",
                re.I),
     lambda m: (f"{m.group(1)}  {m.group(2).upper()} -> {m.group(3).upper()}",
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


# ---------------------------------------------------------------------------
# 提示词（云端与本地共用）
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are a calculator translator. "
    "Convert the user's natural language into a math expression "
    "that the Python library SymPy can evaluate. "
    "Allowed tokens: numbers, + - * / ** ( ) sqrt cbrt log ln log10 exp "
    "sin cos tan asin acos atan sinh cosh tanh abs factorial pi e "
    "and variable names. "
    "Reply with ONLY the expression. Do not add explanation or markdown."
)


def _extract_expr(text: str) -> str:
    """从 LLM 输出中提取第一行可用的表达式。"""
    if not text:
        return ""
    # 去 markdown 代码块
    text = re.sub(r"```[a-zA-Z]*\n?", "", text).replace("```", "")
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return ""
    # 优先返回第一行看起来像表达式的
    expr_re = re.compile(r"^[\d\.\+\-\*/\(\)\^a-zA-Z_, ]+$")
    for ln in lines:
        if expr_re.match(ln):
            return ln
    return lines[0]


# ---------------------------------------------------------------------------
# OllamaProvider
# ---------------------------------------------------------------------------

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
                "prompt": f"{_SYSTEM_PROMPT}\n\nUser: {prompt}\nExpression:",
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


# ---------------------------------------------------------------------------
# OpenAIProvider
# ---------------------------------------------------------------------------

class OpenAIProvider:
    name = "openai"
    label = "OpenAI"

    def __init__(self, api_key="", model="gpt-4o-mini",
                 base_url="https://api.openai.com/v1", timeout=20.0):
        self.api_key = api_key or ""
        self.model = model or "gpt-4o-mini"
        self.base_url = (base_url or "https://api.openai.com/v1").rstrip("/")
        self.timeout = float(timeout)

    def is_available(self) -> bool:
        return bool(self.api_key)

    def translate(self, prompt, context=None) -> AIResult:
        if not self.api_key:
            return AIResult(provider=self.name, error="未配置 API key")
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
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": str(prompt)},
                    ],
                    "temperature": 0.0,
                },
                timeout=self.timeout)
            data = r.json()
            text = (data.get("choices", [{}])[0]
                    .get("message", {}).get("content", "")).strip()
            expr = _extract_expr(text)
            if not expr:
                return AIResult(provider=self.name,
                                error=str(data)[:120])
            return AIResult(expr=expr, explain=text,
                            confidence=0.8, provider=self.name)
        except Exception as e:
            log_warn(f"openai translate failed: {e}", module="ai")
            return AIResult(provider=self.name, error=str(e))


# ---------------------------------------------------------------------------
# AnthropicProvider
# ---------------------------------------------------------------------------

class AnthropicProvider:
    name = "anthropic"
    label = "Anthropic Claude"

    def __init__(self, api_key="", model="claude-3-5-sonnet-latest",
                 timeout=20.0):
        self.api_key = api_key or ""
        self.model = model or "claude-3-5-sonnet-latest"
        self.timeout = float(timeout)

    def is_available(self) -> bool:
        return bool(self.api_key)

    def translate(self, prompt, context=None) -> AIResult:
        if not self.api_key:
            return AIResult(provider=self.name, error="未配置 API key")
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
                    "messages": [{"role": "user", "content": str(prompt)}],
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


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def _build_providers(cfg: AIConfig):
    pref = (cfg.provider or "auto").lower()
    if pref == "rule":
        return [RuleProvider()]
    if pref == "ollama":
        return [
            OllamaProvider(model=cfg.model, base_url=cfg.base_url,
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
            AnthropicProvider(api_key=cfg.api_key, model=cfg.model,
                              timeout=cfg.timeout),
            RuleProvider(),
        ]

    # auto
    out = []
    ollama = OllamaProvider(model=cfg.model, base_url=cfg.base_url,
                            timeout=cfg.timeout)
    if ollama.is_available():
        out.append(ollama)
    if cfg.api_key:
        out.append(OpenAIProvider(api_key=cfg.api_key, model=cfg.model,
                                  timeout=cfg.timeout))
    out.append(RuleProvider())
    return out


def translate(prompt: str, config: AIConfig | None = None,
              context=None) -> AIResult:
    """主翻译入口。

    依次尝试可用 provider，返回第一个成功的结果；
    全部失败则用本地规则再试一次。
    """
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

    # 兜底再试一次规则
    try:
        rule_res = RuleProvider().translate(prompt, context)
        if rule_res.expr:
            return rule_res
    except Exception:
        pass

    return AIResult(error=last_error or "无可用 provider")


def available_providers(config: AIConfig | None = None) -> list[str]:
    """返回当前配置下可用的 provider 名称列表。"""
    cfg = config or AIConfig()
    names = []
    if OllamaProvider(model=cfg.model, base_url=cfg.base_url).is_available():
        names.append("ollama")
    if cfg.api_key:
        names.append("openai")
        names.append("anthropic")
    names.append("rule")
    return names