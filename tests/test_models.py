"""Tests for shared Pydantic models."""

import pytest
from pydantic import ValidationError

from models import (
    Severity,
    Assessment,
    ReviewRequest,
    Finding,
    ReviewResult,
    ReviewReport,
    FileSummary,
)


class TestReviewRequest:
    def test_minimal(self):
        req = ReviewRequest(diff="diff content", repo="my-org/my-repo")
        assert req.diff == "diff content"
        assert req.repo == "my-org/my-repo"
        assert req.context == {}

    def test_with_context(self):
        req = ReviewRequest(
            diff="diff",
            repo="org/repo",
            context={"pr_number": 42},
        )
        assert req.context["pr_number"] == 42

    def test_missing_required_fields(self):
        with pytest.raises(ValidationError):
            ReviewRequest()


class TestFinding:
    def test_full(self):
        f = Finding(
            file_path="src/main.py",
            line_number=10,
            severity=Severity.high,
            category="security",
            description="Hardcoded API key",
        )
        assert f.severity == Severity.high
        assert f.line_number == 10

    def test_optional_line_number(self):
        f = Finding(
            file_path="src/main.py",
            severity=Severity.low,
            category="style",
            description="Missing docstring",
        )
        assert f.line_number is None

    def test_severity_values(self):
        for sev in ("critical", "high", "medium", "low"):
            f = Finding(
                file_path="f.py",
                severity=sev,
                category="test",
                description="test",
            )
            assert f.severity == sev


class TestReviewResult:
    def test_empty_findings(self):
        r = ReviewResult(reviewer="security", summary="No issues found.")
        assert r.findings == []

    def test_with_findings(self):
        r = ReviewResult(
            reviewer="logic",
            summary="Found 1 issue",
            findings=[
                Finding(
                    file_path="a.py",
                    severity=Severity.medium,
                    category="logic",
                    description="Off-by-one",
                )
            ],
        )
        assert len(r.findings) == 1


class TestReviewReport:
    def test_approve(self):
        report = ReviewReport(
            assessment=Assessment.approve,
            summary="LGTM",
        )
        assert report.assessment == Assessment.approve
        assert report.critical_findings == []
        assert report.suggestions == []
        assert report.file_summaries == []

    def test_request_changes(self):
        finding = Finding(
            file_path="x.py",
            severity=Severity.critical,
            category="security",
            description="Hardcoded secret",
            line_number=5,
        )
        report = ReviewReport(
            assessment=Assessment.request_changes,
            summary="Critical security issue",
            critical_findings=[finding],
        )
        assert len(report.critical_findings) == 1
        assert report.critical_findings[0].severity == Severity.critical

    def test_serialization_roundtrip(self):
        report = ReviewReport(
            assessment=Assessment.needs_discussion,
            summary="Needs review",
            suggestions=[
                Finding(
                    file_path="a.py",
                    severity=Severity.low,
                    category="style",
                    description="Consider renaming",
                )
            ],
            file_summaries=[
                FileSummary(file_path="a.py", summary="Minor style nits")
            ],
        )
        data = report.model_dump()
        restored = ReviewReport.model_validate(data)
        assert restored == report
