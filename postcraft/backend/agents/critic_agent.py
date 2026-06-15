"""
Critic Agent Node — LLM-as-judge.
Scores all 3 variants 1-10 and picks the best one.
Adds score and improvement tip to each variant dict.
"""

import json
import os

from google import genai
from google.genai import types

from agents.orchestrator import AgentState


async def critic_node(state: AgentState) -> AgentState:
    print(f"\n[critic] Scoring {len(state.variants)} variants")

    if not state.variants:
        state.errors.append("critic_node: no variants to score")
        return state

    try:
        api_key = os.getenv("GEMINI_API_KEY", "")
        client = genai.Client(api_key=api_key)

        variants_text = "\n\n".join(
            f"VARIANT {i+1}:\n{v['text']}"
            for i, v in enumerate(state.variants)
        )

        judge_prompt = (
            f"You are a LinkedIn content expert judging 3 post variants.\n\n"
            f"Audience: {state.audience}\n"
            f"Tone: {state.tone}\n\n"
            f"{variants_text}\n\n"
            f"Score each variant 1-10 based on:\n"
            f"- Hook strength (does line 1 make you stop scrolling?)\n"
            f"- Audience fit (right tone and content for {state.audience}?)\n"
            f"- Readability (good use of line breaks and structure?)\n"
            f"- CTA clarity (does it prompt action?)\n\n"
            f"Respond ONLY with a JSON array of exactly 3 objects:\n"
            f'[{{"score": <1-10>, "improvement": "<one actionable sentence>"}}, ...]'
        )

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=judge_prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                max_output_tokens=512,
                system_instruction="You are a content quality judge. Output ONLY valid JSON.",
            ),
        )

        raw = response.text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.rstrip("`").strip()

        scores = json.loads(raw)

        for i, score_data in enumerate(scores):
            if i < len(state.variants):
                state.variants[i]["score"] = score_data.get("score", 5)
                state.variants[i]["improvement"] = score_data.get("improvement", "")

        best = max(range(len(state.variants)), key=lambda i: state.variants[i].get("score", 0))
        state.best_index = best

        print(f"[critic] Scores: {[v.get('score') for v in state.variants]} | Best: variant {best+1}")

    except Exception as e:
        state.errors.append(f"critic_node: {str(e)}")
        print(f"[critic] Scoring failed: {e}")
        state.best_index = 0

    return state
