"""Custom orchestrator tools.

``publish_report`` is the human-in-the-loop gate. It is registered in
``interrupt_on`` so the agent pauses before it runs, letting a human approve,
edit, or reject the final report. On approval it persists the report to
Postgres (the ``reports`` table) and returns a confirmation.
"""

from __future__ import annotations

from langchain.tools import ToolRuntime, tool

from db.reports import insert_report


@tool
async def publish_report(
    title: str,
    summary: str,
    body: str,
    sources: list[str],
    runtime: ToolRuntime,
) -> str:
    """Publish the final research report.

    Call this exactly once, after research and editing are complete, with the
    finished report. This is a gated action: a human reviews it before it runs.

    Args:
        title: A concise report title.
        summary: A 2-4 sentence executive summary.
        body: The full report body in Markdown.
        sources: A list of sources or references cited in the report.
    """
    thread_id = (runtime.config or {}).get("configurable", {}).get("thread_id", "unknown")
    row = await insert_report(
        thread_id=thread_id,
        title=title,
        summary=summary,
        body=body,
        sources=sources or [],
    )
    return f"Report '{title}' published (id={row['id']})."
