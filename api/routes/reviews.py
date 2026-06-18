"""POST /reviews — dispatches the code review pipeline."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from render_sdk import RenderAsync

from api.security import require_api_key
from models import ReviewRequest

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/reviews", dependencies=[Depends(require_api_key)])
async def create_review(request: ReviewRequest):
    """Dispatch the orchestrator as a Render Workflow task.

    The orchestrator agent analyzes the diff, fans out reviewer
    sub-agents on isolated instances, and returns a structured
    review report.
    """
    try:
        render = RenderAsync()
        result = await render.workflows.run_task(
            "code-review/orchestrate_review",
            [request.diff, request.repo, request.context],
        )
        return result.output
    except Exception:
        logger.exception("Failed to dispatch review for repo %s", request.repo)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to dispatch review pipeline.",
        )
