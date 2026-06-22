"""Test fixtures and environment setup.

Sets dummy provider keys so model factories don't raise at import time. No test
here makes a real network or database call.
"""

import os

import pytest

os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("LLM_PROVIDER", "openai")


@pytest.fixture(autouse=True)
def _clean_workflow_env(monkeypatch):
    """Ensure each test starts without Workflow dispatch unless it opts in."""
    monkeypatch.delenv("RENDER_API_KEY", raising=False)
    monkeypatch.delenv("WORKFLOWS_DISABLED", raising=False)
    yield
