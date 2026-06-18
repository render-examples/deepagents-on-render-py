"""Shared Pydantic models for the code review pipeline."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

# Upper bound on a submitted diff (~256 KB). Large enough for real PRs,
# small enough to cap LLM token spend and request memory.
MAX_DIFF_CHARS = 256_000


class Severity(str, Enum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"


class Assessment(str, Enum):
    approve = "approve"
    request_changes = "request_changes"
    needs_discussion = "needs_discussion"


class ReviewRequest(BaseModel):
    """Input to POST /reviews.

    `diff` is bounded to keep a single request from pushing an
    unbounded payload into the LLM (latency, memory, and cost).
    """

    diff: str = Field(min_length=1, max_length=MAX_DIFF_CHARS)
    repo: str = Field(min_length=1, max_length=200)
    context: dict = Field(default_factory=dict)


class Finding(BaseModel):
    """A single issue found by a reviewer."""

    file_path: str
    line_number: Optional[int] = None
    severity: Severity
    category: str  # "security", "style", "logic"
    description: str


class ReviewResult(BaseModel):
    """Output from a single reviewer agent."""

    reviewer: str  # "security", "style", "logic"
    findings: list[Finding] = Field(default_factory=list)
    summary: str


class FileSummary(BaseModel):
    """Per-file breakdown in the final report."""

    file_path: str
    findings: list[Finding] = Field(default_factory=list)
    summary: str


class ReviewReport(BaseModel):
    """Final output from the summarizer — the complete review."""

    assessment: Assessment
    summary: str
    critical_findings: list[Finding] = Field(default_factory=list)
    suggestions: list[Finding] = Field(default_factory=list)
    file_summaries: list[FileSummary] = Field(default_factory=list)
    reviewer_results: list[ReviewResult] = Field(default_factory=list)
