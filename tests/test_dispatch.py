"""Tests for the Workflow-dispatch integration (the core of this example)."""

import sys
import types

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from agents.subagents import RESEARCH_AGENT
from dispatch import workflow_subagent as ws


def test_task_name_maps_hyphens_to_underscores():
    assert ws._task_name(RESEARCH_AGENT) == "research_agent"


def test_workflows_enabled_requires_api_key(monkeypatch):
    assert ws.workflows_enabled() is False
    monkeypatch.setenv("RENDER_API_KEY", "rnd_x")
    assert ws.workflows_enabled() is True


def test_workflows_disabled_overrides_api_key(monkeypatch):
    monkeypatch.setenv("RENDER_API_KEY", "rnd_x")
    monkeypatch.setenv("WORKFLOWS_DISABLED", "true")
    assert ws.workflows_enabled() is False


def test_task_text_extracts_last_message():
    state = {"messages": [HumanMessage(content="research quantum computing")]}
    assert ws._task_text(state) == "research quantum computing"


@pytest.mark.asyncio
async def test_dispatch_routes_to_workflow(monkeypatch):
    """When Workflows are enabled, the runnable calls run_task with the right path."""
    calls = {}

    class _FakeRun:
        # TaskRunDetails exposes a ``results`` list of the task's return values.
        results = ["findings about quantum computing"]

    class _FakeWorkflows:
        async def run_task(self, path, args):
            calls["path"] = path
            calls["args"] = args
            return _FakeRun()

    class _FakeRenderAsync:
        def __init__(self):
            self.workflows = _FakeWorkflows()

    fake_module = types.ModuleType("render_sdk")
    fake_module.RenderAsync = _FakeRenderAsync
    monkeypatch.setitem(sys.modules, "render_sdk", fake_module)
    monkeypatch.setenv("RENDER_API_KEY", "rnd_x")
    monkeypatch.setenv("WORKFLOW_NAME", "deep-agents")

    subagent = ws.workflow_subagent(RESEARCH_AGENT)
    state = {"messages": [HumanMessage(content="quantum computing")]}
    result = await subagent["runnable"].ainvoke(state)

    assert calls["path"] == "deep-agents/research_agent"
    assert calls["args"] == ["quantum computing"]
    messages = result["messages"]
    assert isinstance(messages[-1], AIMessage)
    assert "quantum computing" in messages[-1].text


class _Run:
    def __init__(self, results):
        self.results = results


def test_extract_output_plain_string():
    assert ws._extract_output(_Run(["hello"])) == "hello"


def test_extract_output_unwraps_envelope():
    assert ws._extract_output(_Run([{"output": "hello"}])) == "hello"


def test_extract_output_empty():
    assert ws._extract_output(_Run([])) == ""


def test_extract_output_serializes_non_string():
    assert ws._extract_output(_Run([{"a": 1}])) == '{"a": 1}'


def test_workflow_subagent_shape():
    subagent = ws.workflow_subagent(RESEARCH_AGENT)
    assert subagent["name"] == "research-agent"
    assert subagent["description"]
    assert subagent["runnable"] is not None
