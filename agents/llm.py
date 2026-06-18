"""Shared LLM factory — returns the right chat model based on which API key is set.

Set ANTHROPIC_API_KEY to use Claude, or OPENAI_API_KEY to use GPT.
If both are set, Anthropic takes priority (override with LLM_PROVIDER=openai).
"""

import os

from langchain_core.language_models.chat_models import BaseChatModel


def get_llm() -> BaseChatModel:
    """Return a chat model based on available API keys."""
    provider = os.environ.get("LLM_PROVIDER", "").lower()
    has_anthropic = bool(os.environ.get("ANTHROPIC_API_KEY"))
    has_openai = bool(os.environ.get("OPENAI_API_KEY"))

    use_anthropic = (
        provider == "anthropic"
        or (has_anthropic and provider != "openai")
    )

    if use_anthropic:
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(model="claude-sonnet-4-20250514")

    if has_openai or provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model="gpt-4o")

    raise RuntimeError(
        "No LLM API key found. Set OPENAI_API_KEY or ANTHROPIC_API_KEY."
    )
