"""
Research Agent Node -- Tavily-powered trending topic discovery.

Uses Tavily's advanced search to find:
  1. Trending topics in the user's niche
  2. Competitor/high-performing blog posts this week

Results are stored in state.research_output for the content agent.
"""

import os
from typing import Any, Dict

from tavily import TavilyClient

from src.agents.orchestrator import AgentState


async def research_node(state: AgentState) -> AgentState:
    """
    Execute dual Tavily searches and populate state.research_output.

    Searches:
      - Trending topics for the user's niche (2026, advanced depth)
      - Best/competitor blog posts published this week

    Args:
        state: Current AgentState with user_id and niche populated.

    Returns:
        Updated AgentState with research_output filled or error appended.
    """
    print(f"\n[research_agent] >> Starting research | niche='{state.niche}'")

    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        state.errors.append("research_node: TAVILY_API_KEY not set")
        print("[research_agent] [FAIL] TAVILY_API_KEY missing -- skipping research")
        return state

    client = TavilyClient(api_key=api_key)

    topics: list[Dict[str, Any]] = []
    competitor_content: list[Dict[str, Any]] = []

    # ── Search 1: Trending topics ──────────────────────────────────────────
    try:
        print("[research_agent]   Searching trending topics...")
        trending_query = f"trending topics {state.niche} 2026"
        trending_results = client.search(
            query=trending_query,
            search_depth="advanced",
            max_results=5,
            include_answer=True,
        )

        for result in trending_results.get("results", []):
            topics.append(
                {
                    "title": result.get("title", ""),
                    "url": result.get("url", ""),
                    "content": result.get("content", ""),
                    "score": result.get("score", 0.0),
                }
            )
        print(f"[research_agent]   [OK] Found {len(topics)} trending topics")

    except Exception as e:
        state.errors.append(f"research_node (trending): {str(e)}")
        print(f"[research_agent]   [FAIL] Trending search failed: {e}")

    # ── Search 2: Competitor/best content this week ────────────────────────
    try:
        print("[research_agent]   Searching competitor content...")
        competitor_query = f"best {state.niche} blog posts this week"
        competitor_results = client.search(
            query=competitor_query,
            search_depth="basic",
            max_results=3,
            include_answer=False,
        )

        for result in competitor_results.get("results", []):
            competitor_content.append(
                {
                    "title": result.get("title", ""),
                    "url": result.get("url", ""),
                    "content": result.get("content", ""),
                    "score": result.get("score", 0.0),
                }
            )
        print(f"[research_agent]   [OK] Found {len(competitor_content)} competitor posts")

    except Exception as e:
        state.errors.append(f"research_node (competitor): {str(e)}")
        print(f"[research_agent]   [FAIL] Competitor search failed: {e}")

    # ── Store results in state ─────────────────────────────────────────────
    state.research_output = {
        "topics": topics,
        "competitor_content": competitor_content,
        "niche": state.niche,
        "cycle_id": state.cycle_id,
    }

    print(
        f"[research_agent] [OK] Research complete | "
        f"{len(topics)} topics, {len(competitor_content)} competitor posts"
    )
    return state
