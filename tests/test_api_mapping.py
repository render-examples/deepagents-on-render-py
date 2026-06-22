"""Tests for request/response mapping in the runs router (no DB/network)."""

import pytest

from api.routes import runs
from models import Decision


def test_decision_to_dict_approve():
    assert runs._decision_to_dict(Decision(type="approve")) == {"type": "approve"}


def test_decision_to_dict_reject_with_message():
    out = runs._decision_to_dict(Decision(type="reject", message="not now"))
    assert out == {"type": "reject", "message": "not now"}


def test_decision_to_dict_edit():
    edited = {"name": "publish_report", "args": {"title": "x"}}
    out = runs._decision_to_dict(Decision(type="edit", edited_action=edited))
    assert out == {"type": "edit", "edited_action": edited}


class _FakeInterrupt:
    def __init__(self, value):
        self.value = value


class _FakeGraphOutput:
    def __init__(self, interrupts=(), value=None):
        self.interrupts = interrupts
        self.value = value or {}


@pytest.mark.asyncio
async def test_to_run_response_interrupted():
    interrupt = _FakeInterrupt(
        {
            "action_requests": [{"name": "publish_report", "args": {"title": "T"}}],
            "review_configs": [
                {"action_name": "publish_report", "allowed_decisions": ["approve", "reject"]}
            ],
        }
    )
    result = _FakeGraphOutput(interrupts=(interrupt,))
    resp = await runs._to_run_response("thread-1", result)

    assert resp.status == "interrupted"
    assert len(resp.action_requests) == 1
    action = resp.action_requests[0]
    assert action.name == "publish_report"
    assert action.args == {"title": "T"}
    assert action.allowed_decisions == ["approve", "reject"]
