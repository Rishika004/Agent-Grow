"""
Content Agent Node -- Gemini-powered SEO blog post generation.

For each trending topic (max 2 per cycle), generates:
  - SEO-optimised blog post in Markdown
  - Meta description and target keyword
  - LinkedIn hook (3-line punchy post)

Drafts are saved to Supabase with status='pending_approval'.
"""

import json
import os
import uuid
from typing import Any, Dict, List

from google import genai
from supabase import create_client, Client

from src.agents.orchestrator import AgentState

# Content generation JSON schema expected from Gemini
DRAFT_SCHEMA = {
    "title": "string -- compelling, SEO-optimised blog post title",
    "slug": "string -- URL-friendly slug derived from title",
    "body_markdown": "string -- full blog post in Markdown (800-1200 words)",
    "meta_description": "string -- 150-160 char SEO meta description",
    "target_keyword": "string -- primary SEO keyword phrase",
    "linkedin_hook": "string -- 3-line punchy LinkedIn post version of the article",
}


def _build_content_prompt(
    niche: str,
    topic: Dict[str, Any],
    memory_context: List[str],
    competitor_examples: List[Dict[str, Any]],
) -> str:
    """
    Construct the user prompt for Gemini content generation.

    Injects memory context so the LLM avoids repeating topics and
    builds on what previously resonated with the audience.
    """
    memory_section = ""
    if memory_context:
        memory_section = (
            "\n\n## What worked in previous cycles (DO NOT repeat these topics):\n"
            + "\n".join(f"- {m}" for m in memory_context)
        )

    competitor_section = ""
    if competitor_examples:
        competitor_section = (
            "\n\n## Competitor content for inspiration (don't copy -- outperform):\n"
        )
        for c in competitor_examples[:2]:
            competitor_section += (
                f"- Title: {c.get('title', 'N/A')}\n"
                f"  Excerpt: {c.get('content', '')[:200]}...\n"
            )

    return f"""You are a world-class growth content writer specialising in **{niche}**.

Your task is to write a high-quality, SEO-optimised blog post based on this trending topic:

**Topic:** {topic.get('title', '')}
**Context:** {topic.get('content', '')[:500]}
**Source URL:** {topic.get('url', 'N/A')}
{memory_section}
{competitor_section}

## Instructions:
1. Write for a BuildAI audience: entrepreneurs, coaches, and small business owners interested in {niche}.
2. Use clear headings (H2/H3), bullet points, and a conversational but authoritative tone.
3. Include the target keyword naturally throughout the post (3-5 times).
4. End with a strong CTA aligned with building/using a no-code AI tool.
5. The LinkedIn hook must be punchy, start with a bold statement, and fit within 3 short lines.
6. Do NOT repeat any topics listed in the "what worked" section above.
7. IMPORTANT: Keep body_markdown between 500-700 words. Do NOT exceed 700 words.
8. CRITICAL: All string values in your JSON must have properly escaped special characters (newlines as \\n, quotes as \\").

## Required output format (respond ONLY with valid JSON):
{json.dumps(DRAFT_SCHEMA, indent=2)}"""


async def content_node(state: AgentState) -> AgentState:
    """
    Generate blog post drafts for the top 2 research topics using Gemini.

    Each draft is saved to Supabase 'drafts' table with status='pending_approval'
    and appended to state.content_drafts.

    Args:
        state: AgentState with research_output and memory_context populated.

    Returns:
        Updated AgentState with content_drafts filled.
    """
    print(f"\n[content_agent] >> Starting content generation | cycle={state.cycle_id}")

    # ── Validate prerequisites ─────────────────────────────────────────────
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key:
        state.errors.append("content_node: GEMINI_API_KEY not set")
        print("[content_agent] [FAIL] GEMINI_API_KEY missing -- skipping content generation")
        return state

    if not state.research_output or not state.research_output.get("topics"):
        state.errors.append("content_node: No research topics available")
        print("[content_agent] [FAIL] No topics from research -- skipping content generation")
        return state

    client = genai.Client(api_key=gemini_key)
    system_instruction = (
        f"You are a growth content writer for a {state.niche} business. "
        "You always respond with valid JSON only -- no markdown, no preamble, "
        "no explanation. Your content is SEO-optimised, engaging, and tailored "
        "for entrepreneurs."
    )
    supabase = _get_supabase_client()

    topics = state.research_output["topics"][:2]  # Max 2 drafts per cycle
    competitor_content = state.research_output.get("competitor_content", [])

    for idx, topic in enumerate(topics):
        print(
            f"[content_agent]   Generating draft {idx + 1}/{len(topics)}: "
            f"'{topic.get('title', '')[:60]}'"
        )
        try:
            # ── Call Gemini ────────────────────────────────────────────────
            prompt = _build_content_prompt(
                niche=state.niche,
                topic=topic,
                memory_context=state.memory_context,
                competitor_examples=competitor_content,
            )

            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    max_output_tokens=16384,
                    response_mime_type="application/json",
                ),
            )
            raw_content = response.text.strip()

            # ── Parse JSON response ────────────────────────────────────────
            if raw_content.startswith("```"):
                raw_content = raw_content.split("```")[1]
                if raw_content.startswith("json"):
                    raw_content = raw_content[4:]
                raw_content = raw_content.rstrip("`").strip()

            try:
                draft_data = json.loads(raw_content)
            except json.JSONDecodeError:
                # Attempt repair: extract individual fields via regex
                draft_data = _repair_json(raw_content)
                if not draft_data:
                    raise

            # Enrich with metadata
            draft_id = str(uuid.uuid4())
            draft = {
                "id": draft_id,
                "cycle_id": state.cycle_id,
                "user_id": state.user_id,
                "niche": state.niche,
                "status": "pending_approval",
                "source_topic_url": topic.get("url", ""),
                **draft_data,
            }

            # ── Persist to Supabase ────────────────────────────────────────
            if supabase:
                try:
                    supabase.table("drafts").insert(draft).execute()
                    print(f"[content_agent]   [OK] Draft saved to Supabase: {draft_id}")
                except Exception as db_err:
                    state.errors.append(f"content_node (supabase): {str(db_err)}")
                    print(f"[content_agent]   [FAIL] Supabase insert failed: {db_err}")

            state.content_drafts.append(draft)
            print(f"[content_agent]   [OK] Draft created: '{draft.get('title', 'untitled')}'")

        except json.JSONDecodeError as e:
            state.errors.append(f"content_node (json parse, topic {idx}): {str(e)}")
            print(f"[content_agent]   [FAIL] JSON parse failed for topic {idx}: {e}")
        except Exception as e:
            state.errors.append(f"content_node (topic {idx}): {str(e)}")
            print(f"[content_agent]   [FAIL] Generation failed for topic {idx}: {e}")

    print(
        f"[content_agent] [OK] Content generation complete | "
        f"{len(state.content_drafts)} drafts created"
    )
    return state


def _repair_json(raw: str) -> Dict[str, Any] | None:
    """
    Attempt to extract draft fields from malformed JSON using regex.
    Returns a dict if enough fields are found, or None to let the caller raise.
    """
    import re

    fields = {}
    for key in ["title", "slug", "meta_description", "target_keyword", "linkedin_hook"]:
        match = re.search(rf'"{key}"\s*:\s*"((?:[^"\\]|\\.)*)"', raw)
        if match:
            fields[key] = match.group(1).replace("\\n", "\n").replace('\\"', '"')

    # Extract body_markdown (longest field, most likely to be truncated)
    match = re.search(r'"body_markdown"\s*:\s*"((?:[^"\\]|\\.)*)"?', raw, re.DOTALL)
    if match:
        fields["body_markdown"] = match.group(1).replace("\\n", "\n").replace('\\"', '"')

    # Need at least title and body to consider it valid
    if "title" in fields and "body_markdown" in fields:
        fields.setdefault("slug", fields["title"].lower().replace(" ", "-")[:60])
        fields.setdefault("meta_description", "")
        fields.setdefault("target_keyword", "")
        fields.setdefault("linkedin_hook", "")
        print(f"[content_agent]   [WARN] Repaired malformed JSON -- extracted {len(fields)} fields")
        return fields

    return None


def _get_supabase_client() -> Client | None:
    """
    Initialise and return a Supabase client if credentials are available.
    Returns None (gracefully) if env vars are missing.
    """
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")
    if not url or not key:
        print("[content_agent] [WARN] Supabase credentials missing -- drafts won't be persisted")
        return None
    return create_client(url, key)
