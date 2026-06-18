"""POST /reviews — dispatches the code review pipeline."""

from fastapi import APIRouter
from render import RenderAsync

from models import ReviewRequest

router = APIRouter()


@router.post("/reviews")
async def create_review(request: ReviewRequest):
    """Dispatch the orchestrator as a Render Workflow task.

    The orchestrator agent analyzes the diff, fans out reviewer
    sub-agents on isolated instances, and returns a structured
    review report.
    """
    render = RenderAsync()
    result = await render.workflows.run_task(
        "code-review/orchestrate_review", [request.diff]
    )
    return result.output
