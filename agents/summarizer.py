"""
Summarizer agent — combines results from all specialized reviewers
into a single structured report. Runs in-process (no Render Workflow
task) since it's a lightweight synthesis step with no tools.
"""

from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent


SYSTEM_PROMPT = """\
You are a code review summarizer. You receive the results from
multiple specialized reviewers (security, style, logic).

Produce a structured summary with:
1. An overall assessment (approve / request changes / needs discussion).
2. A critical findings section (blocking issues, if any).
3. A suggestions section (non-blocking improvements).
4. A per-file breakdown of key findings.

Be concise. Do not repeat findings verbatim — synthesize and
prioritize. Deduplicate findings that appear in multiple reviews.
"""


def create_summarizer():
    """Return a compiled summarizer agent graph."""
    llm = ChatOpenAI(model="gpt-4o")
    return create_react_agent(
        model=llm,
        tools=[],
        prompt=SYSTEM_PROMPT,
    )
