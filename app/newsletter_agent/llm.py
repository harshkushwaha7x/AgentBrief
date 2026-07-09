from __future__ import annotations

import os
from functools import lru_cache
from typing import Any


@lru_cache(maxsize=1)
def get_chat_model() -> Any | None:
    """Return a LangChain chat model when configured, otherwise None."""

    provider = os.getenv("NEWSLETTER_LLM_PROVIDER", "auto").strip().lower()

    if provider in {"auto", "gemini"} and os.getenv("GOOGLE_API_KEY"):
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
            temperature=0.3,
        )

    if provider in {"auto", "openai"} and os.getenv("OPENAI_API_KEY"):
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            temperature=0.3,
        )

    if provider in {"auto", "ollama"} and os.getenv("OLLAMA_MODEL"):
        from langchain_ollama import ChatOllama

        return ChatOllama(
            model=os.getenv("OLLAMA_MODEL", "llama3.1"),
            temperature=0.3,
        )

    return None


def invoke_text(model: Any | None, prompt: str) -> str | None:
    if model is None:
        return None

    try:
        response = model.invoke(prompt)
    except Exception:
        return None

    content = getattr(response, "content", response)
    if isinstance(content, list):
        return "\n".join(str(part) for part in content).strip()
    return str(content).strip()
