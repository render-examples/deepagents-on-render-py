"""Shared model factory — picks a chat model from whichever API key is set.

Set ``ANTHROPIC_API_KEY`` to use Claude, or ``OPENAI_API_KEY`` to use GPT.
If both are set, Anthropic wins unless ``LLM_PROVIDER=openai``.

``create_deep_agent`` and ``create_agent`` both also accept a provider string
like ``"anthropic:claude-sonnet-4-6"`` directly, but centralizing the choice
here keeps the agent definitions provider-agnostic and easy to fork.
"""

from __future__ import annotations

import os

DEFAULT_ANTHROPIC_MODEL = "anthropic:claude-sonnet-4-6"
DEFAULT_OPENAI_MODEL = "openai:gpt-4o"


def get_model_id() -> str:
    """Return a ``provider:model`` identifier based on available API keys."""
    provider = os.environ.get("LLM_PROVIDER", "").lower()
    has_anthropic = bool(os.environ.get("ANTHROPIC_API_KEY"))
    has_openai = bool(os.environ.get("OPENAI_API_KEY"))

    use_anthropic = provider == "anthropic" or (has_anthropic and provider != "openai")
    if use_anthropic:
        return os.environ.get("ANTHROPIC_MODEL", DEFAULT_ANTHROPIC_MODEL)
    if has_openai or provider == "openai":
        return os.environ.get("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)

    raise RuntimeError(
        "No LLM API key found. Set OPENAI_API_KEY or ANTHROPIC_API_KEY "
        "(optionally LLM_PROVIDER=openai|anthropic to disambiguate)."
    )
