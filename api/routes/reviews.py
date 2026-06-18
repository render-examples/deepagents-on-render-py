"""POST /reviews — dispatches the code review pipeline."""

import logging
import re

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from render_sdk import RenderAsync

from api.security import require_api_key
from models import ReviewRequest

logger = logging.getLogger(__name__)

router = APIRouter()

_PR_URL_RE = re.compile(
    r"https?://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)/pull/(?P<number>\d+)"
)


class PRReviewRequest(BaseModel):
    pr_url: str = Field(min_length=1, max_length=500)


async def _fetch_pr_diff(pr_url: str) -> tuple[str, str]:
    """Parse a GitHub PR URL and fetch its diff.

    Returns (diff_text, "owner/repo").
    """
    m = _PR_URL_RE.match(pr_url.strip())
    if not m:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid GitHub PR URL. Expected: https://github.com/owner/repo/pull/123",
        )

    owner, repo, number = m.group("owner"), m.group("repo"), m.group("number")
    diff_url = f"https://github.com/{owner}/{repo}/pull/{number}.diff"

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        resp = await client.get(diff_url)

    if resp.status_code == 404:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"PR not found or not public: {owner}/{repo}#{number}",
        )
    if resp.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"GitHub returned {resp.status_code} when fetching the diff.",
        )

    return resp.text, f"{owner}/{repo}"


@router.post("/reviews", dependencies=[Depends(require_api_key)])
async def create_review(request: ReviewRequest):
    """Dispatch the orchestrator as a Render Workflow task."""
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


@router.post("/reviews/pr", dependencies=[Depends(require_api_key)])
async def create_review_from_pr(request: PRReviewRequest):
    """Fetch a public GitHub PR diff and dispatch a review."""
    diff, repo = await _fetch_pr_diff(request.pr_url)

    try:
        render = RenderAsync()
        result = await render.workflows.run_task(
            "code-review/orchestrate_review",
            [diff, repo, {}],
        )
        return result.output
    except Exception:
        logger.exception("Failed to dispatch review for PR %s", request.pr_url)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to dispatch review pipeline.",
        )
