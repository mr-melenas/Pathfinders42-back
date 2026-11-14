"""
ES: Cliente del LLM por API compatible con OpenAI (vLLM, Ollama, OpenRouter, Together, DashScope...).
Variables: LLM_BASE_URL (obligatoria, p. ej. https://host/v1), LLM_API_KEY, MODEL_LLM,
LLM_DISABLE_THINKING (1 por defecto: Qwen3 «piensa» antes de responder y aquí no interesa).
EN: OpenAI-compatible API client for the LLM (vLLM, Ollama, OpenRouter, Together, DashScope...).
Variables: LLM_BASE_URL (required, e.g. https://host/v1), LLM_API_KEY, MODEL_LLM,
LLM_DISABLE_THINKING (1 by default: Qwen3 "thinks" before answering, which we don't want here).
"""

import os
import re

import httpx

from .writer import build_messages

DEFAULT_MODEL = "gemma3:4b"


def llm_configured() -> bool:
    return bool(os.getenv("LLM_BASE_URL"))


def strip_thinking(text: str) -> str:
    """
    ES: Quita el bloque <think>...</think> (o uno sin cerrar al principio). EN: Removes the <think> block.
    """
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    text = re.sub(r"^\s*<think>.*", "", text, flags=re.S)
    return text.strip()


def chat_completion(messages: list[dict], max_tokens: int = 400) -> str:
    """
    ES: Una llamada a /chat/completions, determinista (temperature 0). EN: One deterministic /chat/completions call.
    """
    base_url = os.getenv("LLM_BASE_URL")
    if not base_url:
        raise RuntimeError("LLM_BASE_URL no está configurada.")

    body = {
        "model": os.getenv("MODEL_LLM") or DEFAULT_MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0,
    }
    if os.getenv("LLM_DISABLE_THINKING", "1") == "1":
        body["chat_template_kwargs"] = {"enable_thinking": False}  # vLLM/SGLang; others ignore it
    headers = {"Content-Type": "application/json"}
    if os.getenv("LLM_API_KEY"):
        headers["Authorization"] = f"Bearer {os.environ['LLM_API_KEY']}"
    response = httpx.post(f"{base_url.rstrip('/')}/chat/completions", headers=headers, json=body, timeout=90)
    response.raise_for_status()
    return strip_thinking(response.json()["choices"][0]["message"]["content"] or "")


class ApiGenerator:
    """
    ES: Generador con la misma firma que usa write_explanation(data, fragments, reminder).
    EN: Generator with the signature write_explanation expects (data, fragments, reminder).
    """

    def __call__(self, data: dict, fragments: list[dict], reminder: str = "") -> str:
        return chat_completion(build_messages(data, fragments, reminder))
