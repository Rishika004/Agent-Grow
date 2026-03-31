"""
Scheduler trigger module.

Provides a FastAPI router (webhook endpoint) that can be called
by external schedulers (n8n, cron, GitHub Actions) to fire a new
agent cycle without needing to hit the main /run endpoint directly.
"""

import os
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel

import httpx

router = APIRouter(prefix="/scheduler", tags=["scheduler"])

# Simple shared secret for webhook authentication
WEBHOOK_SECRET = os.getenv("SCHEDULER_WEBHOOK_SECRET", "change-me-in-production")


class ScheduledRunRequest(BaseModel):
    """Payload sent by n8n or other cron orchestrators to trigger a daily run."""

    user_id: str
    niche: str
    trigger_source: str = "n8n"  # "n8n" | "cron" | "manual" | "github_actions"


@router.post("/trigger", summary="Webhook trigger for scheduled agent cycles")
async def trigger_cycle(
    request: ScheduledRunRequest,
    x_webhook_secret: str = Header(default=""),
) -> Dict[str, Any]:
    """
    Authenticate and forward a scheduled cycle trigger to the main /run endpoint.

    Called by n8n or any cron-based scheduler on a daily schedule.
    Validates the shared secret before initiating a new cycle.

    Args:
        request: Scheduled run parameters (user_id, niche, trigger_source).
        x_webhook_secret: Shared secret header for authentication.

    Returns:
        Forwarded response from POST /run, including cycle_id.
    """
    print(
        f"[scheduler] >> Trigger received | "
        f"source={request.trigger_source} | user={request.user_id}"
    )

    # ── Authenticate webhook ───────────────────────────────────────────────
    if x_webhook_secret != WEBHOOK_SECRET:
        print("[scheduler] [FAIL] Invalid webhook secret")
        raise HTTPException(status_code=401, detail="Invalid webhook secret")

    # ── Forward to main run endpoint ───────────────────────────────────────
    api_host = os.getenv("API_HOST", "http://localhost:8000")
    run_url = f"{api_host}/run"

    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                run_url,
                json={"user_id": request.user_id, "niche": request.niche},
            )
            response.raise_for_status()
            result = response.json()

        print(f"[scheduler] [OK] Cycle triggered: {result.get('cycle_id')}")
        return {
            "triggered_by": request.trigger_source,
            **result,
        }

    except httpx.HTTPError as e:
        error_msg = f"Failed to trigger cycle: {str(e)}"
        print(f"[scheduler] [FAIL] {error_msg}")
        raise HTTPException(status_code=500, detail=error_msg)
