"""
Orchestrator agent — analyzes a PR diff and dispatches specialized
reviewer agents via Render Workflow tasks.

The orchestrator is itself a LangChain agent. Its tools dispatch
sub-agents on dedicated Render Workflow instances. When the LLM
returns multiple tool calls in one response, LangGraph executes
them concurrently — giving us parallel fan-out.
"""

import json

from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent


SYSTEM_PROMPT = """\
You are a code review orchestrator. Given a PR diff, you:

1. Analyze the diff to determine which reviews are needed.
2. Dispatch the appropriate reviewers using your tools.
   - Always run security review.
   - Run style and logic reviews for substantive code changes
     (skip them for pure config, docs, or whitespace-only changes).
   - Call multiple reviewers in a single response for parallelism.
3. After all reviews complete, call summarize_reviews with the
   collected results to produce a final structured report.
"""


@tool
async def run_security_review(diff: str) -> str:
    """Dispatch a security review on dedicated compute via Render Workflows."""
    from render import RenderAsync

    render = RenderAsync()
    result = await render.workflows.run_task("code-review/security_review", [diff])
    return json.dumps(result.output)


@tool
async def run_style_review(diff: str) -> str:
    """Dispatch a style review on dedicated compute via Render Workflows."""
    from render import RenderAsync

    render = RenderAsync()
    result = await render.workflows.run_task("code-review/style_review", [diff])
    return json.dumps(result.output)


@tool
async def run_logic_review(diff: str) -> str:
    """Dispatch a logic review on dedicated compute via Render Workflows."""
    from render import RenderAsync

    render = RenderAsync()
    result = await render.workflows.run_task("code-review/logic_review", [diff])
    return json.dumps(result.output)


@tool
async def summarize_reviews(reviews_json: str) -> str:
    """Summarize collected review results into a final report. Runs in-process."""
    from agents.summarizer import create_summarizer

    summarizer = create_summarizer()
    result = await summarizer.ainvoke(
        {"messages": [{"role": "user", "content": reviews_json}]}
    )
    return result["messages"][-1].content


def create_orchestrator():
    """Return a compiled orchestrator agent graph."""
    llm = ChatOpenAI(model="gpt-4o")
    return create_react_agent(
        model=llm,
        tools=[
            run_security_review,
            run_style_review,
            run_logic_review,
            summarize_reviews,
        ],
        prompt=SYSTEM_PROMPT,
    )
