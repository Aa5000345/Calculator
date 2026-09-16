"""视觉输入识别层：手写 / 截图 → 表达式。

设计要点：
- 探测阶段绝不 import pix2tex / torch（避免启动时触发模型下载）
- 真正调用识别时才 import，且必须由用户显式触发
- 永远返回 dict：{"expr", "provider", "error"}
"""
from __future__ import annotations

import importlib.util
import io
import sys
from typing import Optional


# 缓存已加载的识别模型（pix2tex 加载一次可用多次）
_PIX2TEX_MODEL = None


# ---------------------------------------------------------------------------
# 后端探测（不 import 目标库）
# ---------------------------------------------------------------------------

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
    """Python 3.14+ 使用 pix2tex 的兼容性提醒（无则空串）。"""
    if sys.version_info < (3, 14):
        return ""
    return "（注意：Python 3.14 上 torch.jit 已弃用，pix2tex 可能不稳定）"


def list_recognizers(api_key: str = "") -> list[dict]:
    """返回可用识别器元数据，供 UI 显示（不触发任何重加载）。"""
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


# ---------------------------------------------------------------------------
# pix2tex（真正调用时才 import）
# ---------------------------------------------------------------------------

def _recognize_pix2tex(image_bytes: bytes) -> dict:
    global _PIX2TEX_MODEL

    # 二次检查：即使调用方绕过 UI 直接调本函数，也先探测
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
        # torch 在 Python 3.14 上可能抛各种错误
        return {"expr": "", "provider": "pix2tex",
                "error": f"pix2tex 初始化失败（{sys.version.split()[0]}）：{e}"}

    try:
        if _PIX2TEX_MODEL is None:
            # 这一步才是真正的加载（首次下载 ~97MB 权重）
            _PIX2TEX_MODEL = LatexOCR()
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        latex = _PIX2TEX_MODEL(img)
        return {"expr": (latex or "").strip(),
                "provider": "pix2tex", "error": ""}
    except Exception as e:  # noqa: BLE001
        return {"expr": "", "provider": "pix2tex",
                "error": f"识别失败：{e}"}


# ---------------------------------------------------------------------------
# OpenAI 视觉
# ---------------------------------------------------------------------------

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
        return {"expr": "", "provider": "openai_vision", "error": str(e)}

    try:
        b64 = base64.b64encode(image_bytes).decode("ascii")
        prompt = (
            "You are a calculator expression extractor. "
            "Read the math expression in the image and reply with ONLY "
            "the SymPy-compatible expression. No markdown, no explanation."
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
                         "image_url": {"url": f"data:image/png;base64,{b64}"}},
                    ],
                }],
                "temperature": 0.0,
            },
            timeout=timeout)
        data = r.json()
        text = (data.get("choices", [{}])[0]
                .get("message", {}).get("content", "")).strip()
        if "```" in text:
            import re
            text = re.sub(r"```[a-zA-Z]*\n?", "", text).replace("```", "")
        return {"expr": text.strip(),
                "provider": "openai_vision", "error": ""}
    except Exception as e:
        return {"expr": "", "provider": "openai_vision", "error": str(e)}


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

def recognize_image(image_bytes: bytes, provider: str = "auto",
                    api_key: str = "") -> dict:
    """从图片识别表达式。

    注意：本函数是同步阻塞的（pix2tex 首次可能 30–60s）。
    调用方应放在 QThread 里。
    """
    if not image_bytes:
        return {"expr": "", "provider": provider, "error": "图片为空"}

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
            "error": "无可用识别器：请安装 pix2tex 或在 AI 面板配置 API key"}