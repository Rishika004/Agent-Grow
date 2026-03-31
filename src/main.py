"""
Growth Agent -- Main entry point.

Two modes:
  1. Test mode (default): Run one full agent cycle with test values
     and print results to stdout. Useful for local development.
  2. API mode: Launch the FastAPI server for production use.

Usage:
  # Test one cycle:
  python -m src.main

  # Start API server:
  uvicorn src.main:app --reload --port 8000
"""

import asyncio
import os

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import app as routes_app
from src.scheduler.trigger import router as scheduler_router

# ── Compose the FastAPI application ──────────────────────────────────────────

app = FastAPI(
    title="Growth Agent",
    description=(
        "Autonomous AI growth agent for BuildAI -- "
        "research, write, approve, publish, and learn."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount the routes sub-app and scheduler router
app.mount("/api", routes_app)
app.include_router(scheduler_router)


# Forward root-level endpoints to the routes app for convenience
@app.get("/health")
async def health():
    """Root health check."""
    return {"status": "ok", "service": "growth-agent"}


# ── Test cycle runner ─────────────────────────────────────────────────────────


async def run_test_cycle() -> None:
    """
    Execute one complete growth agent cycle with test configuration.

    Loads environment variables, constructs a test AgentState, and runs
    the LangGraph pipeline to completion (or until the approval interrupt).
    """
    from src.agents.orchestrator import AgentState, growth_graph

    print("=" * 60)
    print("  GROWTH AGENT -- Test Cycle")
    print("=" * 60)

    # Check for required keys (warn but don't crash)
    required_keys = [
        "GEMINI_API_KEY",
        "TAVILY_API_KEY",
        "SUPABASE_URL",
        "MEM0_API_KEY",
    ]
    missing = [k for k in required_keys if not os.getenv(k)]
    if missing:
        print(f"\n[WARN] Warning: Missing env vars: {', '.join(missing)}")
        print("  Agent will run but API calls will fail gracefully.\n")

    # Construct test state
    test_state = AgentState(
        user_id="test-user-001",
        niche="no-code app building for coaches",
    )

    print(f"\nUser ID  : {test_state.user_id}")
    print(f"Niche    : {test_state.niche}")
    print(f"Cycle ID : {test_state.cycle_id}")
    print("\nStarting pipeline...\n")

    try:
        config = {"configurable": {"thread_id": test_state.cycle_id}}
        result = await growth_graph.ainvoke(
            test_state.model_dump(), config=config
        )

        print("\n" + "=" * 60)
        print("  CYCLE RESULTS")
        print("=" * 60)
        print(
            f"  Memory context items : "
            f"{len(result.get('memory_context', []))}"
        )
        print(
            f"  Research topics      : "
            f"{len((result.get('research_output') or {}).get('topics', []))}"
        )
        print(
            f"  Content drafts       : "
            f"{len(result.get('content_drafts', []))}"
        )
        print(f"  Approved IDs         : {result.get('approved_ids', [])}")
        print(
            f"  LinkedIn posts       : "
            f"{len(result.get('linkedin_posts', []))}"
        )
        print(
            f"  Analytics scores     : "
            f"{len(result.get('analytics_scores', {}))}"
        )
        print(
            f"  Errors               : "
            f"{len(result.get('errors', []))}"
        )

        if result.get("errors"):
            print("\n  Errors encountered:")
            for err in result["errors"]:
                print(f"    [FAIL] {err}")

        if result.get("content_drafts"):
            print("\n  Drafts generated:")
            for draft in result["content_drafts"]:
                print(
                    f"    * [{draft.get('status', '?')}] "
                    f"{draft.get('title', 'Untitled')}"
                )

        print("\n" + "=" * 60)
        print("  Pipeline paused at await_approval.")
        print("  Use POST /approve/{draft_id} to resume.")
        print("=" * 60 + "\n")

    except Exception as e:
        print(f"\n[FAIL] Test cycle failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(run_test_cycle())
