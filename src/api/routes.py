"""
FastAPI routes for the Growth Agent API.

Endpoints:
  POST /run              -- Trigger a new agent cycle
  GET  /tasks            -- List pending approval drafts from Supabase
  POST /approve/{id}     -- Approve a draft, resume LangGraph graph
  POST /reject/{id}      -- Reject a draft with optional reason
  GET  /reports/weekly   -- Last 7 days of published content + analytics scores
"""

import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(
    title="Growth Agent API",
    description=(
        "Autonomous AI growth agent for BuildAI -- "
        "content research, writing, and publishing."
    ),
    version="1.0.0",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Pydantic request/response models ─────────────────────────────────────────


class RunCycleRequest(BaseModel):
    """Request body for POST /run."""

    user_id: str
    niche: str


class ApproveRequest(BaseModel):
    """Optional body for POST /approve/{draft_id}."""

    notes: Optional[str] = None


class RejectRequest(BaseModel):
    """Request body for POST /reject/{draft_id}."""

    reason: str


class DraftResponse(BaseModel):
    """Single draft as returned by GET /tasks."""

    id: str
    title: str
    slug: str
    status: str
    niche: str
    meta_description: Optional[str] = None
    target_keyword: Optional[str] = None
    created_at: Optional[str] = None


class CycleResponse(BaseModel):
    """Response from POST /run."""

    cycle_id: str
    status: str
    message: str


# ── In-memory state store (replace with Redis/Supabase in production) ─────────
_active_cycles: Dict[str, Any] = {}


def _get_supabase():
    """Return a Supabase client or raise HTTPException if unconfigured."""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise HTTPException(
            status_code=503,
            detail="Supabase not configured -- set SUPABASE_URL and SUPABASE_SERVICE_KEY",
        )
    from supabase import create_client

    return create_client(url, key)


# ── Routes ────────────────────────────────────────────────────────────────────


@app.post("/run", response_model=CycleResponse, summary="Trigger a new agent cycle")
async def run_cycle(request: RunCycleRequest) -> CycleResponse:
    """
    Start a new growth agent cycle for the given user and niche.

    Initialises AgentState and runs the LangGraph pipeline asynchronously.
    The graph will pause at await_approval -- use /approve or /reject to resume.
    """
    from src.agents.orchestrator import AgentState, growth_graph

    cycle_id = str(uuid.uuid4())
    state = AgentState(
        user_id=request.user_id,
        niche=request.niche,
        cycle_id=cycle_id,
    )

    _active_cycles[cycle_id] = {"state": state, "status": "running"}

    print(
        f"[api] POST /run | cycle={cycle_id} | "
        f"user={request.user_id} | niche={request.niche}"
    )

    try:
        config = {"configurable": {"thread_id": cycle_id}}
        result = await growth_graph.ainvoke(state.model_dump(), config=config)
        _active_cycles[cycle_id]["status"] = "awaiting_approval"
        _active_cycles[cycle_id]["result"] = result
        print(f"[api] Cycle {cycle_id} paused at await_approval")
    except Exception as e:
        _active_cycles[cycle_id]["status"] = "error"
        print(f"[api] Cycle {cycle_id} failed: {e}")
        raise HTTPException(status_code=500, detail=f"Cycle failed: {str(e)}")

    drafts = _active_cycles[cycle_id].get("result", {}).get("content_drafts", [])
    return CycleResponse(
        cycle_id=cycle_id,
        status="awaiting_approval",
        message=(
            f"Cycle started. {len(drafts)} drafts ready for review at GET /tasks"
        ),
    )


@app.get("/tasks", response_model=List[DraftResponse], summary="List pending drafts")
async def get_tasks() -> List[DraftResponse]:
    """
    Return all drafts with status='pending_approval' from Supabase.
    """
    print("[api] GET /tasks")
    try:
        supabase = _get_supabase()
        response = (
            supabase.table("drafts")
            .select(
                "id, title, slug, status, niche, "
                "meta_description, target_keyword, created_at"
            )
            .eq("status", "pending_approval")
            .order("created_at", desc=True)
            .execute()
        )
        return [DraftResponse(**row) for row in (response.data or [])]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch tasks: {str(e)}")


@app.post(
    "/approve/{draft_id}", summary="Approve a draft and resume publishing"
)
async def approve_draft(
    draft_id: str, body: Optional[ApproveRequest] = None
) -> Dict[str, Any]:
    """
    Approve a draft by ID.

    Updates draft status in Supabase to 'approved', then resumes
    the LangGraph pipeline so LinkedIn posting and analytics evaluation proceed.
    """
    print(f"[api] POST /approve/{draft_id}")
    try:
        supabase = _get_supabase()

        update_response = (
            supabase.table("drafts")
            .update(
                {
                    "status": "approved",
                    "approved_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            .eq("id", draft_id)
            .execute()
        )

        if not update_response.data:
            raise HTTPException(status_code=404, detail=f"Draft {draft_id} not found")

        # Find the active cycle containing this draft and resume the graph
        for cycle_id, cycle_data in _active_cycles.items():
            if cycle_data.get("status") == "awaiting_approval":
                result = cycle_data.get("result", {})
                draft_ids = [d.get("id") for d in result.get("content_drafts", [])]
                if draft_id in draft_ids:
                    result["approved_ids"] = result.get("approved_ids", []) + [
                        draft_id
                    ]
                    config = {"configurable": {"thread_id": cycle_id}}
                    try:
                        from src.agents.orchestrator import growth_graph

                        await growth_graph.ainvoke(None, config=config)
                        cycle_data["status"] = "completed"
                        print(f"[api] [OK] Cycle {cycle_id} resumed and completed")
                    except Exception as resume_err:
                        print(f"[api] [FAIL] Graph resume failed: {resume_err}")
                    break

        return {
            "status": "approved",
            "draft_id": draft_id,
            "message": "Draft approved and publishing pipeline resumed",
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Approval failed: {str(e)}")


@app.post("/reject/{draft_id}", summary="Reject a draft")
async def reject_draft(draft_id: str, body: RejectRequest) -> Dict[str, Any]:
    """
    Reject a draft by ID with a mandatory reason.
    """
    print(f"[api] POST /reject/{draft_id} | reason='{body.reason[:80]}'")
    try:
        supabase = _get_supabase()

        update_response = (
            supabase.table("drafts")
            .update(
                {
                    "status": "rejected",
                    "rejection_reason": body.reason,
                    "rejected_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            .eq("id", draft_id)
            .execute()
        )

        if not update_response.data:
            raise HTTPException(status_code=404, detail=f"Draft {draft_id} not found")

        return {
            "status": "rejected",
            "draft_id": draft_id,
            "reason": body.reason,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Rejection failed: {str(e)}")


@app.get("/reports/weekly", summary="Weekly performance report")
async def weekly_report() -> Dict[str, Any]:
    """
    Return published content and analytics scores for the last 7 days.
    """
    print("[api] GET /reports/weekly")
    try:
        supabase = _get_supabase()
        since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

        response = (
            supabase.table("drafts")
            .select(
                "id, title, slug, status, niche, "
                "target_keyword, created_at, approved_at"
            )
            .in_("status", ["approved", "published"])
            .gte("created_at", since)
            .order("created_at", desc=True)
            .execute()
        )

        drafts = response.data or []

        return {
            "period": "last_7_days",
            "total_published": len(drafts),
            "drafts": drafts,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Report failed: {str(e)}")


@app.get("/health", summary="Health check")
async def health_check() -> Dict[str, str]:
    """Simple health check endpoint for monitoring and uptime checks."""
    return {"status": "ok", "service": "growth-agent-api"}
