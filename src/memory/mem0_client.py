"""
Mem0 persistent memory client.

Provides core functions for the growth agent's long-term memory:
  - store_memory(): Persist post performance data after each cycle
  - retrieve_memories(): Fetch relevant memories at cycle start
  - store_cycle_memory(): Convenience wrapper for end-of-cycle bulk store

Uses Mem0's managed cloud API (MEM0_API_KEY) by default.
Falls back gracefully if the API key is not configured.
"""

import os
from typing import Any, Dict, List, Optional


def _get_mem0_client():
    """
    Instantiate and return a Mem0 client.

    Returns:
        MemoryClient instance or None if MEM0_API_KEY is missing.
    """
    api_key = os.getenv("MEM0_API_KEY")
    if not api_key:
        print("[mem0_client] [WARN] MEM0_API_KEY not set -- memory features disabled")
        return None
    try:
        from mem0 import MemoryClient
        return MemoryClient(api_key=api_key)
    except ImportError:
        print("[mem0_client] [WARN] mem0ai package not installed -- memory features disabled")
        return None


async def store_memory(
    user_id: str,
    content: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    Store a memory entry in Mem0 for a specific user.

    Memory format follows the growth agent standard:
    "Post titled '{title}' in niche '{niche}' scored {score}/10.
     Reason: {reasoning}. Keywords that worked: {keywords}"

    Args:
        user_id: Unique identifier for the BuildAI user.
        content: The memory content string to store.
        metadata: Optional dict of metadata tags (cycle_id, score, niche, etc.).

    Returns:
        True if stored successfully, False otherwise.
    """
    print(f"[mem0_client] Storing memory for user '{user_id}' ({len(content)} chars)")
    client = _get_mem0_client()
    if client is None:
        return False

    try:
        client.add(
            messages=[{"role": "assistant", "content": content}],
            user_id=user_id,
            metadata=metadata or {},
        )
        print(f"[mem0_client] [OK] Memory stored for user '{user_id}'")
        return True
    except Exception as e:
        print(f"[mem0_client] [FAIL] Failed to store memory: {e}")
        return False


async def retrieve_memories(
    user_id: str,
    query: str,
    limit: int = 5,
) -> List[str]:
    """
    Search and retrieve relevant memories for a user from Mem0.

    Used at cycle start to inject historical performance context
    into Gemini's content generation prompts.

    Args:
        user_id: Unique identifier for the BuildAI user.
        query: Semantic search query (e.g. "best performing content in niche").
        limit: Maximum number of memories to return.

    Returns:
        List of memory content strings, most relevant first.
    """
    print(f"[mem0_client] Retrieving memories for user '{user_id}' | query='{query}'")
    client = _get_mem0_client()
    if client is None:
        return []

    try:
        response = client.search(
            query=query,
            filters={"user_id": user_id},
            limit=limit,
        )
        # Mem0 v2 API returns {"results": [...]} dict
        result_list = response.get("results", []) if isinstance(response, dict) else response
        memories = [r.get("memory", "") for r in result_list if r.get("memory")]
        print(f"[mem0_client] [OK] Retrieved {len(memories)} memories")
        return memories
    except Exception as e:
        print(f"[mem0_client] [FAIL] Failed to retrieve memories: {e}")
        return []


async def store_cycle_memory(
    user_id: str,
    niche: str,
    cycle_id: str,
    content_drafts: List[Dict[str, Any]],
    analytics_scores: Dict[str, Any],
) -> None:
    """
    Persist end-of-cycle performance data for all scored drafts to Mem0.

    Called by the update_memory graph node after analytics evaluation.
    Formats each draft's score into the standard memory string.

    Args:
        user_id: BuildAI user identifier.
        niche: User's content niche.
        cycle_id: Unique cycle run ID.
        content_drafts: List of draft dicts from the content node.
        analytics_scores: Score dict keyed by draft_id from the analytics node.
    """
    print(f"[mem0_client] Storing cycle memory for {len(analytics_scores)} scored posts")

    for draft in content_drafts:
        draft_id = draft.get("id", "")
        score_data = analytics_scores.get(draft_id, {})

        if not score_data:
            continue

        title = draft.get("title", "Untitled")
        score = score_data.get("score", "?")
        reasoning = score_data.get("reasoning", "")
        keywords = score_data.get("keywords_that_worked", [])
        improvement = score_data.get("improvement_suggestion", "")

        memory_content = (
            f"Post titled '{title}' in niche '{niche}' "
            f"scored {score}/10. "
            f"Reason: {reasoning} "
            f"Keywords that worked: {', '.join(keywords) if keywords else 'none recorded'}. "
            f"Improvement suggestion: {improvement} "
            f"[cycle: {cycle_id}]"
        )

        await store_memory(
            user_id=user_id,
            content=memory_content,
            metadata={
                "cycle_id": cycle_id,
                "draft_id": draft_id,
                "niche": niche,
                "score": score,
                "title": title,
            },
        )
