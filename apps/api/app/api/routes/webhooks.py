"""GitHub webhook receiver with strict constant-time HMAC-SHA256 verification."""

import json
import logging
from typing import cast

from fastapi import APIRouter, HTTPException, Request, Response, status

from app.core.config import Settings
from app.services.github import verify_github_webhook_signature

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


@router.post("/github")
async def receive_github_webhook(request: Request, response: Response) -> dict[str, object]:
    """Verify X-Hub-Signature-256 HMAC and accept GitHub pull_request events."""
    settings = cast(Settings, request.app.state.settings)
    raw_body = await request.body()

    if not settings.github_webhook_secret:
        logger.error("GitHub webhook received while GITHUB_WEBHOOK_SECRET is unconfigured")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Webhook secret is not configured",
        )

    signature = request.headers.get("X-Hub-Signature-256")
    if not verify_github_webhook_signature(raw_body, signature, settings.github_webhook_secret):
        logger.warning("Rejected GitHub webhook due to invalid or missing HMAC signature")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature",
        )

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid JSON webhook payload: {exc}",
        ) from exc

    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Webhook payload must be a JSON object",
        )

    event = request.headers.get("X-GitHub-Event", "unknown")
    if event == "ping":
        return {"status": "pong"}

    if event == "pull_request":
        action = str(payload.get("action") or "")
        if action in {"opened", "synchronize", "reopened"}:
            repo_obj = payload.get("repository")
            pr_obj = payload.get("pull_request")
            repo_name = (
                str(repo_obj.get("full_name"))
                if isinstance(repo_obj, dict) and repo_obj.get("full_name")
                else ""
            )
            pr_number = pr_obj.get("number") if isinstance(pr_obj, dict) else None
            response.status_code = status.HTTP_202_ACCEPTED
            return {
                "status": "accepted",
                "event": "pull_request",
                "action": action,
                "pr_number": pr_number,
                "repository": repo_name,
            }

    return {"status": "ignored", "event": event}
