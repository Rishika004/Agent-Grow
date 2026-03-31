"""
Analytics Agent Node -- PostHog analytics reader + LLM-as-judge scorer.

For each published post, reads PostHog page view events, then uses
Gemini as an LLM judge to score content quality 1-10 based
on actual engagement metrics. Scores are stored for memory update.
"""

import json
import os
from typing import Any, Dict

from google import genai

from src.agents.orchestrator import AgentState
from src.tools.analytics_tool import get_post_analytics
from src.memory.mem0_client import store_memory


async def analytics_node(state: AgentState) -> AgentState:
    """
    Read PostHog analytics for published posts and score them with Gemini.

    For each approved draft:
      1. Fetch page views, bounce rate, time-on-page from PostHog
      2. Send analytics to Gemini as LLM-as-judge
      3. Store score + reasoning in state.analytics_scores
      4. Persist score to Mem0 for future cycles

    Args:
        state: AgentState with approved_ids and content_drafts populated.

    Returns:
        Updated AgentState with analytics_scores filled.
    """
    print(f"\n[analytics_agent] >> Starting analytics evaluation | cycle={state.cycle_id}")

    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key:
        state.errors.append("analytics_node: GEMINI_API_KEY not set")
        print("[analytics_agent] [FAIL] GEMINI_API_KEY missing -- skipping evaluation")
        return state

    if not state.approved_ids:
        print("[analytics_agent] [WARN] No approved drafts -- skipping analytics")
        return state

    client = genai.Client(api_key=gemini_key)

    draft_map: Dict[str, Dict[str, Any]] = {
        d["id"]: d for d in state.content_drafts if "id" in d
    }

    for draft_id in state.approved_ids:
        draft = draft_map.get(draft_id)
        if not draft:
            print(f"[analytics_agent]   [FAIL] Draft {draft_id} not found -- skipping")
            continue

        slug = draft.get("slug", "")
        title = draft.get("title", draft_id)
        print(f"[analytics_agent]   Evaluating: '{title[:60]}'")

        # ── Fetch PostHog analytics ────────────────────────────────────────
        analytics_data: Dict[str, Any] = {}
        try:
            analytics_data = await get_post_analytics(slug=slug)
            print(f"[analytics_agent]   [OK] Analytics fetched: {analytics_data}")
        except Exception as e:
            state.errors.append(f"analytics_node (posthog, {draft_id}): {str(e)}")
            print(f"[analytics_agent]   [FAIL] Analytics fetch failed: {e}")
            analytics_data = {
                "page_views": 0,
                "bounce_rate": "N/A",
                "avg_time_on_page": "N/A",
            }

        # ── LLM-as-judge scoring ───────────────────────────────────────────
        try:
            judge_prompt = (
                f"You are a content performance analyst evaluating blog post "
                f"engagement.\n\n"
                f"Post title: {title}\n"
                f"Target keyword: {draft.get('target_keyword', 'N/A')}\n"
                f"Analytics data:\n"
                f"  - Page views: {analytics_data.get('page_views', 0)}\n"
                f"  - Bounce rate: {analytics_data.get('bounce_rate', 'N/A')}\n"
                f"  - Avg time on page: "
                f"{analytics_data.get('avg_time_on_page', 'N/A')}\n"
                f"  - Unique visitors: "
                f"{analytics_data.get('unique_visitors', 0)}\n\n"
                f"Score this blog post 1-10 for engagement quality.\n"
                f"Consider: traffic volume, bounce rate (lower = better), "
                f"time on page (higher = better).\n"
                f"If analytics are zero/missing, score based on content quality "
                f"signals alone (score 5).\n\n"
                f"Respond ONLY with valid JSON (no markdown):\n"
                f'{{"score": <int 1-10>, "reasoning": "<2-3 sentences>", '
                f'"improvement_suggestion": "<1 actionable suggestion>", '
                f'"keywords_that_worked": ["<keyword1>", "<keyword2>"]}}'
            )

            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=judge_prompt,
                config=genai.types.GenerateContentConfig(
                    system_instruction="You are a content analytics expert. Respond only with valid JSON.",
                    max_output_tokens=512,
                ),
            )
            raw = response.text.strip()

            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]

            score_data = json.loads(raw)
            score_data["draft_id"] = draft_id
            score_data["analytics"] = analytics_data

            state.analytics_scores[draft_id] = score_data

            # ── Store to Mem0 for long-term learning ───────────────────────
            try:
                memory_content = (
                    f"Post titled '{title}' in niche '{state.niche}' "
                    f"scored {score_data.get('score', '?')}/10. "
                    f"Reason: {score_data.get('reasoning', '')} "
                    f"Keywords that worked: "
                    f"{', '.join(score_data.get('keywords_that_worked', []))}. "
                    f"Improvement: {score_data.get('improvement_suggestion', '')}"
                )
                await store_memory(
                    user_id=state.user_id,
                    content=memory_content,
                    metadata={
                        "cycle_id": state.cycle_id,
                        "draft_id": draft_id,
                        "score": score_data.get("score"),
                        "niche": state.niche,
                    },
                )
                print(
                    f"[analytics_agent]   [OK] Score "
                    f"{score_data.get('score')}/10 stored to Mem0"
                )
            except Exception as mem_err:
                state.errors.append(
                    f"analytics_node (mem0, {draft_id}): {str(mem_err)}"
                )
                print(f"[analytics_agent]   [FAIL] Mem0 store failed: {mem_err}")

        except json.JSONDecodeError as e:
            state.errors.append(f"analytics_node (json, {draft_id}): {str(e)}")
            print(f"[analytics_agent]   [FAIL] JSON parse failed for score: {e}")
        except Exception as e:
            state.errors.append(f"analytics_node (gemini, {draft_id}): {str(e)}")
            print(f"[analytics_agent]   [FAIL] Gemini scoring failed: {e}")

    print(
        f"[analytics_agent] [OK] Evaluation complete | "
        f"{len(state.analytics_scores)} posts scored"
    )
    return state
