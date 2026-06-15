# PostCraft Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the FastAPI + LangGraph backend for PostCraft — a 5-node agentic pipeline that takes GitHub links, images, or text and generates 3 audience-targeted LinkedIn post variants with LLM-as-judge scoring.

**Architecture:** FastAPI serves a single `/generate` endpoint that invokes a LangGraph StateGraph pipeline. Five nodes run in sequence: Intake → Enrichment → RAG → Writer → Critic. Supabase pgvector stores the style library for RAG retrieval. Gemini 2.5 Flash handles writing, vision, and judging.

**Tech Stack:** Python 3.11, FastAPI, LangGraph, Google Gemini 2.5 Flash, Google text-embedding-004, Supabase pgvector, httpx, linkedin-api, python-dotenv

---

## File Map

```
postcraft/
├── backend/
│   ├── main.py                     # FastAPI app, /generate + /publish + /health
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── orchestrator.py         # AgentState + LangGraph graph builder
│   │   ├── intake_agent.py         # classify input type node
│   │   ├── enrichment_agent.py     # GitHub API + Gemini Vision + text parse node
│   │   ├── rag_agent.py            # Supabase pgvector retrieval node
│   │   ├── writer_agent.py         # Gemini writer node (3 variants)
│   │   └── critic_agent.py         # LLM-as-judge scoring node
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── github_tool.py          # fetch repo metadata via GitHub REST API
│   │   ├── vision_tool.py          # analyze image with Gemini Vision
│   │   └── linkedin_tool.py        # post to LinkedIn via linkedin-api
│   ├── memory/
│   │   ├── __init__.py
│   │   └── supabase_rag.py         # embed query + retrieve similar posts
│   └── requirements.txt
├── seed_posts.py                   # one-time script: embed + store posts.json
├── posts.json                      # style library source (already exists)
├── .env.example
└── tests/
    ├── test_intake.py
    ├── test_enrichment.py
    ├── test_rag.py
    ├── test_writer.py
    ├── test_critic.py
    └── test_api.py
```

---

## Task 1: Project Setup

**Files:**
- Create: `postcraft/backend/requirements.txt`
- Create: `postcraft/.env.example`
- Create: `postcraft/backend/__init__.py`
- Create: `postcraft/backend/agents/__init__.py`
- Create: `postcraft/backend/tools/__init__.py`
- Create: `postcraft/backend/memory/__init__.py`

- [ ] **Step 1: Create the postcraft folder structure**

```bash
mkdir -p postcraft/backend/agents
mkdir -p postcraft/backend/tools
mkdir -p postcraft/backend/memory
mkdir -p postcraft/tests
touch postcraft/backend/__init__.py
touch postcraft/backend/agents/__init__.py
touch postcraft/backend/tools/__init__.py
touch postcraft/backend/memory/__init__.py
touch postcraft/tests/__init__.py
```

- [ ] **Step 2: Create requirements.txt**

Create `postcraft/backend/requirements.txt`:

```
langgraph>=0.2.55
langchain-core>=0.3.30
google-genai>=1.0.0
fastapi>=0.115.6
uvicorn[standard]>=0.32.1
python-dotenv>=1.0.1
pydantic>=2.10.3
httpx>=0.28.1
supabase>=2.10.0
linkedin-api>=2.1.1
pytest>=8.3.4
pytest-asyncio>=0.24.0
```

- [ ] **Step 3: Create .env.example**

Create `postcraft/.env.example`:

```
GEMINI_API_KEY=your-gemini-api-key
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your-service-role-key
LINKEDIN_EMAIL=your-linkedin-email
LINKEDIN_PASSWORD=your-linkedin-password
GITHUB_TOKEN=optional-increases-rate-limit
```

- [ ] **Step 4: Create .env from example and fill in keys**

```bash
cp postcraft/.env.example postcraft/.env
# Edit postcraft/.env and fill in your actual keys
```

- [ ] **Step 5: Install dependencies**

```bash
cd postcraft/backend
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
```

- [ ] **Step 6: Commit**

```bash
git add postcraft/
git commit -m "feat: postcraft project structure and dependencies"
```

---

## Task 2: Supabase Schema Setup

**Files:**
- No code files — SQL run in Supabase dashboard

- [ ] **Step 1: Enable pgvector in Supabase**

Go to your Supabase project → SQL Editor → run:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

Expected output: `Success. No rows returned`

- [ ] **Step 2: Create style_library table**

```sql
CREATE TABLE style_library (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  text TEXT NOT NULL,
  audience TEXT CHECK (audience IN ('founder', 'engineer', 'jobseeker', 'recruiter')),
  tone TEXT CHECK (tone IN ('professional', 'casual', 'storytelling', 'bold')),
  embedding VECTOR(768),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX ON style_library
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 50);
```

- [ ] **Step 3: Create generated_drafts table**

```sql
CREATE TABLE generated_drafts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  input_type TEXT CHECK (input_type IN ('github', 'image', 'text')),
  audience TEXT,
  tone TEXT,
  variants JSONB,
  best_index INTEGER,
  generation_time_ms INTEGER,
  published BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

- [ ] **Step 4: Create usage_logs table**

```sql
CREATE TABLE usage_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  event TEXT,
  input_type TEXT,
  audience TEXT,
  generation_time_ms INTEGER,
  error TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

- [ ] **Step 5: Verify tables exist**

In Supabase → Table Editor, confirm you see: `style_library`, `generated_drafts`, `usage_logs`

---

## Task 3: Supabase RAG Client

**Files:**
- Create: `postcraft/backend/memory/supabase_rag.py`
- Create: `postcraft/tests/test_rag.py`

- [ ] **Step 1: Write the failing test**

Create `postcraft/tests/test_rag.py`:

```python
import pytest
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from unittest.mock import patch, MagicMock
from memory.supabase_rag import embed_text, retrieve_similar_posts


def test_embed_text_returns_list_of_floats():
    with patch('memory.supabase_rag.genai') as mock_genai:
        mock_genai.embed_content.return_value = {"embedding": [0.1] * 768}
        result = embed_text("test text")
        assert isinstance(result, list)
        assert len(result) == 768
        assert all(isinstance(x, float) for x in result)


def test_retrieve_similar_posts_returns_list():
    with patch('memory.supabase_rag.get_supabase_client') as mock_client_fn:
        mock_client = MagicMock()
        mock_client_fn.return_value = mock_client
        mock_client.rpc.return_value.execute.return_value.data = [
            {"text": "post 1", "audience": "founder", "tone": "bold"},
            {"text": "post 2", "audience": "founder", "tone": "professional"},
        ]
        with patch('memory.supabase_rag.embed_text', return_value=[0.1] * 768):
            results = retrieve_similar_posts(
                query="I built an AI tool",
                audience="founder",
                limit=5
            )
        assert isinstance(results, list)
        assert len(results) == 2
        assert results[0]["text"] == "post 1"


def test_retrieve_similar_posts_returns_empty_on_error():
    with patch('memory.supabase_rag.get_supabase_client') as mock_client_fn:
        mock_client_fn.side_effect = Exception("Supabase unavailable")
        with patch('memory.supabase_rag.embed_text', return_value=[0.1] * 768):
            results = retrieve_similar_posts(
                query="test",
                audience="engineer",
                limit=5
            )
        assert results == []
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
cd postcraft
python -m pytest tests/test_rag.py -v
```

Expected: `ImportError` or `ModuleNotFoundError` — module doesn't exist yet.

- [ ] **Step 3: Implement supabase_rag.py**

Create `postcraft/backend/memory/supabase_rag.py`:

```python
"""
Supabase pgvector RAG client.
Embeds queries with Google text-embedding-004 and retrieves
similar posts from the style_library table.
"""

import os
from typing import Any, Dict, List, Optional

import google.generativeai as genai
from supabase import create_client, Client


def get_supabase_client() -> Client:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
    return create_client(url, key)


def embed_text(text: str) -> List[float]:
    """Embed text using Google text-embedding-004 (768 dimensions)."""
    api_key = os.getenv("GEMINI_API_KEY")
    genai.configure(api_key=api_key)
    result = genai.embed_content(
        model="models/text-embedding-004",
        content=text,
        task_type="retrieval_query",
    )
    return result["embedding"]


def retrieve_similar_posts(
    query: str,
    audience: str,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """
    Embed the query and return the most similar posts from style_library.
    Filters by audience type. Returns empty list on any error.
    """
    print(f"[rag] Retrieving similar posts | audience={audience} | query='{query[:60]}'")
    try:
        embedding = embed_text(query)
        client = get_supabase_client()

        # Use Supabase RPC for pgvector similarity search
        response = client.rpc(
            "match_style_posts",
            {
                "query_embedding": embedding,
                "audience_filter": audience,
                "match_count": limit,
            },
        ).execute()

        posts = response.data or []
        print(f"[rag] Retrieved {len(posts)} similar posts")
        return posts

    except Exception as e:
        print(f"[rag] RAG retrieval failed: {e}")
        return []


def store_draft(
    input_type: str,
    audience: str,
    tone: str,
    variants: List[Dict[str, Any]],
    best_index: int,
    generation_time_ms: int,
) -> Optional[str]:
    """Store a generated draft to generated_drafts table. Returns the draft ID."""
    try:
        client = get_supabase_client()
        response = client.table("generated_drafts").insert({
            "input_type": input_type,
            "audience": audience,
            "tone": tone,
            "variants": variants,
            "best_index": best_index,
            "generation_time_ms": generation_time_ms,
        }).execute()
        return response.data[0]["id"] if response.data else None
    except Exception as e:
        print(f"[rag] Failed to store draft: {e}")
        return None


def log_event(
    event: str,
    input_type: str = "",
    audience: str = "",
    generation_time_ms: int = 0,
    error: str = "",
) -> None:
    """Log a usage event to usage_logs table."""
    try:
        client = get_supabase_client()
        client.table("usage_logs").insert({
            "event": event,
            "input_type": input_type,
            "audience": audience,
            "generation_time_ms": generation_time_ms,
            "error": error,
        }).execute()
    except Exception as e:
        print(f"[rag] Failed to log event: {e}")
```

- [ ] **Step 4: Create the Supabase RPC function**

In Supabase → SQL Editor, run:

```sql
CREATE OR REPLACE FUNCTION match_style_posts(
  query_embedding VECTOR(768),
  audience_filter TEXT,
  match_count INT DEFAULT 5
)
RETURNS TABLE (
  id UUID,
  text TEXT,
  audience TEXT,
  tone TEXT,
  similarity FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT
    s.id,
    s.text,
    s.audience,
    s.tone,
    1 - (s.embedding <=> query_embedding) AS similarity
  FROM style_library s
  WHERE s.audience = audience_filter
  ORDER BY s.embedding <=> query_embedding
  LIMIT match_count;
END;
$$;
```

- [ ] **Step 5: Run tests to confirm they pass**

```bash
cd postcraft
python -m pytest tests/test_rag.py -v
```

Expected: All 3 tests PASS

- [ ] **Step 6: Commit**

```bash
git add postcraft/backend/memory/supabase_rag.py postcraft/tests/test_rag.py
git commit -m "feat: supabase rag client with pgvector retrieval"
```

---

## Task 4: Seeding Script

**Files:**
- Create: `postcraft/seed_posts.py`

- [ ] **Step 1: Create seed_posts.py**

Create `postcraft/seed_posts.py`:

```python
"""
One-time script to embed posts.json and store in Supabase style_library.
Run once: python seed_posts.py
"""

import json
import os
import sys

from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

import google.generativeai as genai
from supabase import create_client


def embed_text(text: str) -> list[float]:
    api_key = os.getenv("GEMINI_API_KEY")
    genai.configure(api_key=api_key)
    result = genai.embed_content(
        model="models/text-embedding-004",
        content=text,
        task_type="retrieval_document",
    )
    return result["embedding"]


def seed():
    posts_path = os.path.join(os.path.dirname(__file__), '..', 'posts.json')
    with open(posts_path, "r", encoding="utf-8") as f:
        posts = json.load(f)

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")
    supabase = create_client(url, key)

    print(f"Seeding {len(posts)} posts into style_library...")

    for i, post in enumerate(posts):
        try:
            embedding = embed_text(post["text"])
            supabase.table("style_library").insert({
                "text": post["text"],
                "audience": post["audience"],
                "tone": post["tone"],
                "embedding": embedding,
            }).execute()
            print(f"[{i+1}/{len(posts)}] OK: {post['text'][:60]}...")
        except Exception as e:
            print(f"[{i+1}/{len(posts)}] FAIL: {e}")

    print("Seeding complete.")


if __name__ == "__main__":
    seed()
```

- [ ] **Step 2: Run the seeding script**

```bash
cd postcraft
python seed_posts.py
```

Expected output:
```
Seeding 17 posts into style_library...
[1/17] OK: I quit my 9-5 six months ago...
[2/17] OK: Just shipped v2 of my open source project...
...
Seeding complete.
```

- [ ] **Step 3: Verify in Supabase**

Go to Supabase → Table Editor → `style_library`. Confirm 17 rows exist with the `embedding` column populated.

- [ ] **Step 4: Commit**

```bash
git add postcraft/seed_posts.py
git commit -m "feat: supabase style library seeding script"
```

---

## Task 5: Agent State + Orchestrator

**Files:**
- Create: `postcraft/backend/agents/orchestrator.py`

- [ ] **Step 1: Create orchestrator.py**

Create `postcraft/backend/agents/orchestrator.py`:

```python
"""
PostCraft agent orchestrator.

Defines AgentState and the LangGraph StateGraph:
intake -> enrichment -> rag -> writer -> critic -> END
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from langgraph.graph import END, StateGraph


class AgentState(BaseModel):
    # ── Inputs ────────────────────────────────────────────────────────────────
    input_type: str = Field(..., description="github | image | text")
    input_value: str = Field(..., description="URL, base64 image, or raw text")
    audience: str = Field(..., description="founder | engineer | jobseeker | recruiter")
    tone: str = Field(..., description="professional | casual | storytelling | bold")
    voice_samples: List[str] = Field(default_factory=list, description="User's own past posts")

    # ── Pipeline state ────────────────────────────────────────────────────────
    enriched_facts: Dict[str, Any] = Field(default_factory=dict)
    style_examples: List[Dict[str, Any]] = Field(default_factory=list)
    variants: List[Dict[str, Any]] = Field(default_factory=list)
    best_index: int = Field(default=0)
    errors: List[str] = Field(default_factory=list)

    class Config:
        arbitrary_types_allowed = True


def build_graph() -> StateGraph:
    from agents.intake_agent import intake_node
    from agents.enrichment_agent import enrichment_node
    from agents.rag_agent import rag_node
    from agents.writer_agent import writer_node
    from agents.critic_agent import critic_node

    graph = StateGraph(AgentState)

    graph.add_node("intake", intake_node)
    graph.add_node("enrichment", enrichment_node)
    graph.add_node("rag", rag_node)
    graph.add_node("writer", writer_node)
    graph.add_node("critic", critic_node)

    graph.set_entry_point("intake")
    graph.add_edge("intake", "enrichment")
    graph.add_edge("enrichment", "rag")
    graph.add_edge("rag", "writer")
    graph.add_edge("writer", "critic")
    graph.add_edge("critic", END)

    return graph.compile()


postcraft_graph = build_graph()
```

- [ ] **Step 2: Commit**

```bash
git add postcraft/backend/agents/orchestrator.py
git commit -m "feat: agent state and langgraph orchestrator"
```

---

## Task 6: Intake Agent

**Files:**
- Create: `postcraft/backend/agents/intake_agent.py`
- Create: `postcraft/tests/test_intake.py`

- [ ] **Step 1: Write the failing test**

Create `postcraft/tests/test_intake.py`:

```python
import pytest
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from agents.orchestrator import AgentState
from agents.intake_agent import intake_node
import asyncio


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_github_url_classified_correctly():
    state = AgentState(
        input_type="github",
        input_value="https://github.com/user/repo",
        audience="engineer",
        tone="professional",
    )
    result = run(intake_node(state))
    assert result.enriched_facts["input_type"] == "github"
    assert result.enriched_facts["raw_value"] == "https://github.com/user/repo"
    assert result.enriched_facts["owner"] == "user"
    assert result.enriched_facts["repo"] == "repo"


def test_text_input_classified_correctly():
    state = AgentState(
        input_type="text",
        input_value="I just finished my internship at Google",
        audience="jobseeker",
        tone="casual",
    )
    result = run(intake_node(state))
    assert result.enriched_facts["input_type"] == "text"
    assert result.enriched_facts["raw_value"] == "I just finished my internship at Google"


def test_image_input_classified_correctly():
    state = AgentState(
        input_type="image",
        input_value="data:image/png;base64,abc123",
        audience="founder",
        tone="bold",
    )
    result = run(intake_node(state))
    assert result.enriched_facts["input_type"] == "image"
    assert result.enriched_facts["raw_value"] == "data:image/png;base64,abc123"


def test_invalid_github_url_adds_error():
    state = AgentState(
        input_type="github",
        input_value="not-a-github-url",
        audience="engineer",
        tone="professional",
    )
    result = run(intake_node(state))
    assert len(result.errors) > 0
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
cd postcraft
python -m pytest tests/test_intake.py -v
```

Expected: `ImportError` — module doesn't exist yet.

- [ ] **Step 3: Implement intake_agent.py**

Create `postcraft/backend/agents/intake_agent.py`:

```python
"""
Intake Agent Node — classifies input type and extracts metadata.

For GitHub: parses owner/repo from URL.
For image: validates base64 format.
For text: trims and validates non-empty.
"""

import re
from agents.orchestrator import AgentState


async def intake_node(state: AgentState) -> AgentState:
    print(f"\n[intake] input_type={state.input_type}")

    if state.input_type == "github":
        return _handle_github(state)
    elif state.input_type == "image":
        return _handle_image(state)
    elif state.input_type == "text":
        return _handle_text(state)
    else:
        state.errors.append(f"intake: unknown input_type '{state.input_type}'")
        return state


def _handle_github(state: AgentState) -> AgentState:
    pattern = r"https?://github\.com/([^/]+)/([^/\s]+)"
    match = re.search(pattern, state.input_value.strip())
    if not match:
        state.errors.append(
            f"intake: '{state.input_value}' is not a valid GitHub URL. "
            "Expected format: https://github.com/owner/repo"
        )
        state.enriched_facts = {"input_type": "github", "raw_value": state.input_value}
        return state

    owner, repo = match.group(1), match.group(2).rstrip("/")
    state.enriched_facts = {
        "input_type": "github",
        "raw_value": state.input_value,
        "owner": owner,
        "repo": repo,
        "github_url": f"https://github.com/{owner}/{repo}",
    }
    print(f"[intake] GitHub repo: {owner}/{repo}")
    return state


def _handle_image(state: AgentState) -> AgentState:
    state.enriched_facts = {
        "input_type": "image",
        "raw_value": state.input_value,
    }
    print(f"[intake] Image input detected ({len(state.input_value)} chars)")
    return state


def _handle_text(state: AgentState) -> AgentState:
    text = state.input_value.strip()
    if not text:
        state.errors.append("intake: text input is empty")
    state.enriched_facts = {
        "input_type": "text",
        "raw_value": text,
    }
    print(f"[intake] Text input: '{text[:80]}'")
    return state
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd postcraft
python -m pytest tests/test_intake.py -v
```

Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add postcraft/backend/agents/intake_agent.py postcraft/tests/test_intake.py
git commit -m "feat: intake agent classifies github/image/text inputs"
```

---

## Task 7: GitHub Tool

**Files:**
- Create: `postcraft/backend/tools/github_tool.py`

- [ ] **Step 1: Create github_tool.py**

Create `postcraft/backend/tools/github_tool.py`:

```python
"""
GitHub REST API tool.
Fetches public repo metadata: name, description, language, stars, README excerpt.
No auth required for public repos. Set GITHUB_TOKEN to increase rate limits.
"""

import os
from typing import Any, Dict

import httpx


async def fetch_github_repo(owner: str, repo: str) -> Dict[str, Any]:
    """
    Fetch metadata for a public GitHub repo.

    Returns dict with: name, description, language, stars, topics,
    readme_excerpt, repo_url. Returns partial data on API errors.
    """
    print(f"[github_tool] Fetching {owner}/{repo}")

    headers = {"Accept": "application/vnd.github+json"}
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    result: Dict[str, Any] = {
        "name": repo,
        "owner": owner,
        "repo_url": f"https://github.com/{owner}/{repo}",
        "description": "",
        "language": "",
        "stars": 0,
        "topics": [],
        "readme_excerpt": "",
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        # Fetch repo metadata
        try:
            resp = await client.get(
                f"https://api.github.com/repos/{owner}/{repo}",
                headers=headers,
            )
            if resp.status_code == 200:
                data = resp.json()
                result["description"] = data.get("description") or ""
                result["language"] = data.get("language") or ""
                result["stars"] = data.get("stargazers_count", 0)
                result["topics"] = data.get("topics", [])
                result["forks"] = data.get("forks_count", 0)
            else:
                print(f"[github_tool] Repo API returned {resp.status_code}")
        except Exception as e:
            print(f"[github_tool] Repo fetch failed: {e}")

        # Fetch README
        try:
            resp = await client.get(
                f"https://api.github.com/repos/{owner}/{repo}/readme",
                headers={**headers, "Accept": "application/vnd.github.raw"},
            )
            if resp.status_code == 200:
                readme = resp.text
                result["readme_excerpt"] = readme[:1500]
            else:
                print(f"[github_tool] README not found ({resp.status_code})")
        except Exception as e:
            print(f"[github_tool] README fetch failed: {e}")

    print(f"[github_tool] Done: stars={result['stars']} lang={result['language']}")
    return result
```

- [ ] **Step 2: Commit**

```bash
git add postcraft/backend/tools/github_tool.py
git commit -m "feat: github tool fetches repo metadata and readme"
```

---

## Task 8: Vision Tool

**Files:**
- Create: `postcraft/backend/tools/vision_tool.py`

- [ ] **Step 1: Create vision_tool.py**

Create `postcraft/backend/tools/vision_tool.py`:

```python
"""
Gemini Vision tool.
Analyzes an uploaded image and extracts key facts for LinkedIn post generation.
Accepts base64-encoded image strings.
"""

import base64
import os
from typing import Any, Dict

from google import genai
from google.genai import types


async def analyze_image(image_base64: str) -> Dict[str, Any]:
    """
    Send image to Gemini Vision and extract structured facts.

    Args:
        image_base64: Base64 encoded image (with or without data URI prefix).

    Returns:
        dict with keys: description, key_facts, suggested_topic, achievement
    """
    print("[vision_tool] Analyzing image with Gemini Vision")

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return _empty_vision_result("GEMINI_API_KEY not set")

    # Strip data URI prefix if present
    if "," in image_base64:
        image_base64 = image_base64.split(",", 1)[1]

    try:
        image_bytes = base64.b64decode(image_base64)
    except Exception as e:
        return _empty_vision_result(f"Invalid base64: {e}")

    try:
        client = genai.Client(api_key=api_key)

        prompt = (
            "You are analyzing an image to extract facts for a LinkedIn post.\n\n"
            "Look at this image carefully and extract:\n"
            "1. What is shown (product, achievement, event, certificate, project, etc.)\n"
            "2. Key facts visible (numbers, metrics, names, dates)\n"
            "3. The main achievement or story this image represents\n"
            "4. Suggested LinkedIn post topic based on the image\n\n"
            "Respond ONLY with valid JSON:\n"
            '{"description": "...", "key_facts": ["fact1", "fact2"], '
            '"achievement": "...", "suggested_topic": "..."}'
        )

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                prompt,
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                max_output_tokens=512,
            ),
        )

        import json
        data = json.loads(response.text.strip())
        print(f"[vision_tool] Extracted: {data.get('suggested_topic', '')}")
        return data

    except Exception as e:
        print(f"[vision_tool] Vision analysis failed: {e}")
        return _empty_vision_result(str(e))


def _empty_vision_result(reason: str) -> Dict[str, Any]:
    return {
        "description": "",
        "key_facts": [],
        "achievement": "",
        "suggested_topic": "",
        "error": reason,
    }
```

- [ ] **Step 2: Commit**

```bash
git add postcraft/backend/tools/vision_tool.py
git commit -m "feat: gemini vision tool for image analysis"
```

---

## Task 9: Enrichment Agent

**Files:**
- Create: `postcraft/backend/agents/enrichment_agent.py`
- Create: `postcraft/tests/test_enrichment.py`

- [ ] **Step 1: Write the failing test**

Create `postcraft/tests/test_enrichment.py`:

```python
import pytest
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from unittest.mock import patch, AsyncMock
from agents.orchestrator import AgentState
from agents.enrichment_agent import enrichment_node
import asyncio


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_github_enrichment_calls_github_tool():
    state = AgentState(
        input_type="github",
        input_value="https://github.com/user/repo",
        audience="engineer",
        tone="professional",
        enriched_facts={
            "input_type": "github",
            "raw_value": "https://github.com/user/repo",
            "owner": "user",
            "repo": "repo",
        }
    )
    mock_repo_data = {
        "name": "repo",
        "description": "A cool tool",
        "language": "Python",
        "stars": 42,
        "topics": ["ai", "python"],
        "readme_excerpt": "This tool does amazing things",
        "repo_url": "https://github.com/user/repo",
    }
    with patch('agents.enrichment_agent.fetch_github_repo', new_callable=AsyncMock) as mock_gh:
        mock_gh.return_value = mock_repo_data
        result = run(enrichment_node(state))
    assert result.enriched_facts["github"] == mock_repo_data
    assert result.enriched_facts["summary"] != ""


def test_text_enrichment_populates_summary():
    state = AgentState(
        input_type="text",
        input_value="I completed my ML internship",
        audience="jobseeker",
        tone="casual",
        enriched_facts={
            "input_type": "text",
            "raw_value": "I completed my ML internship",
        }
    )
    result = run(enrichment_node(state))
    assert "summary" in result.enriched_facts
    assert "I completed my ML internship" in result.enriched_facts["summary"]
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
cd postcraft
python -m pytest tests/test_enrichment.py -v
```

Expected: `ImportError` — module doesn't exist yet.

- [ ] **Step 3: Implement enrichment_agent.py**

Create `postcraft/backend/agents/enrichment_agent.py`:

```python
"""
Enrichment Agent Node.

Routes to the correct enrichment strategy based on input_type:
- github: calls GitHub API to get repo metadata + README
- image: calls Gemini Vision to extract facts
- text: cleans and structures the raw text input
"""

from agents.orchestrator import AgentState
from tools.github_tool import fetch_github_repo
from tools.vision_tool import analyze_image


async def enrichment_node(state: AgentState) -> AgentState:
    print(f"\n[enrichment] input_type={state.enriched_facts.get('input_type')}")

    input_type = state.enriched_facts.get("input_type", state.input_type)

    if input_type == "github":
        return await _enrich_github(state)
    elif input_type == "image":
        return await _enrich_image(state)
    else:
        return _enrich_text(state)


async def _enrich_github(state: AgentState) -> AgentState:
    owner = state.enriched_facts.get("owner", "")
    repo = state.enriched_facts.get("repo", "")

    if not owner or not repo:
        state.errors.append("enrichment: missing owner/repo from intake")
        return state

    try:
        repo_data = await fetch_github_repo(owner, repo)
        state.enriched_facts["github"] = repo_data

        # Build a structured summary for the writer
        summary_parts = [f"GitHub project: {repo_data['name']}"]
        if repo_data.get("description"):
            summary_parts.append(f"Description: {repo_data['description']}")
        if repo_data.get("language"):
            summary_parts.append(f"Primary language: {repo_data['language']}")
        if repo_data.get("stars"):
            summary_parts.append(f"GitHub stars: {repo_data['stars']}")
        if repo_data.get("topics"):
            summary_parts.append(f"Topics: {', '.join(repo_data['topics'])}")
        if repo_data.get("readme_excerpt"):
            summary_parts.append(f"README excerpt:\n{repo_data['readme_excerpt'][:800]}")

        state.enriched_facts["summary"] = "\n".join(summary_parts)
        print(f"[enrichment] GitHub enrichment complete: {owner}/{repo}")

    except Exception as e:
        state.errors.append(f"enrichment (github): {str(e)}")
        state.enriched_facts["summary"] = f"GitHub project: {owner}/{repo}"

    return state


async def _enrich_image(state: AgentState) -> AgentState:
    image_b64 = state.enriched_facts.get("raw_value", "")

    try:
        vision_data = await analyze_image(image_b64)
        state.enriched_facts["vision"] = vision_data

        summary_parts = []
        if vision_data.get("description"):
            summary_parts.append(f"Image shows: {vision_data['description']}")
        if vision_data.get("achievement"):
            summary_parts.append(f"Achievement: {vision_data['achievement']}")
        if vision_data.get("key_facts"):
            summary_parts.append(f"Key facts: {', '.join(vision_data['key_facts'])}")
        if vision_data.get("suggested_topic"):
            summary_parts.append(f"Suggested topic: {vision_data['suggested_topic']}")

        state.enriched_facts["summary"] = "\n".join(summary_parts) if summary_parts else "Image input"
        print(f"[enrichment] Vision enrichment complete")

    except Exception as e:
        state.errors.append(f"enrichment (vision): {str(e)}")
        state.enriched_facts["summary"] = "Image input"

    return state


def _enrich_text(state: AgentState) -> AgentState:
    raw = state.enriched_facts.get("raw_value", "").strip()
    state.enriched_facts["summary"] = raw
    print(f"[enrichment] Text enrichment: '{raw[:80]}'")
    return state
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd postcraft
python -m pytest tests/test_enrichment.py -v
```

Expected: All 2 tests PASS

- [ ] **Step 5: Commit**

```bash
git add postcraft/backend/agents/enrichment_agent.py postcraft/tests/test_enrichment.py
git commit -m "feat: enrichment agent routes github/image/text to correct tool"
```

---

## Task 10: RAG Agent

**Files:**
- Create: `postcraft/backend/agents/rag_agent.py`

- [ ] **Step 1: Create rag_agent.py**

Create `postcraft/backend/agents/rag_agent.py`:

```python
"""
RAG Agent Node.
Retrieves the 5 most similar posts from the style_library using pgvector.
Uses the enriched summary as the search query.
"""

from agents.orchestrator import AgentState
from memory.supabase_rag import retrieve_similar_posts


async def rag_node(state: AgentState) -> AgentState:
    print(f"\n[rag] Retrieving style examples | audience={state.audience}")

    summary = state.enriched_facts.get("summary", "")
    if not summary:
        print("[rag] No summary available — skipping RAG")
        return state

    try:
        posts = retrieve_similar_posts(
            query=summary,
            audience=state.audience,
            limit=5,
        )
        state.style_examples = posts
        print(f"[rag] Retrieved {len(posts)} style examples")
    except Exception as e:
        state.errors.append(f"rag_node: {str(e)}")
        print(f"[rag] RAG failed: {e} — continuing without examples")
        state.style_examples = []

    return state
```

- [ ] **Step 2: Commit**

```bash
git add postcraft/backend/agents/rag_agent.py
git commit -m "feat: rag agent retrieves style examples from supabase pgvector"
```

---

## Task 11: Writer Agent

**Files:**
- Create: `postcraft/backend/agents/writer_agent.py`
- Create: `postcraft/tests/test_writer.py`

- [ ] **Step 1: Write the failing test**

Create `postcraft/tests/test_writer.py`:

```python
import pytest
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from unittest.mock import patch, MagicMock
from agents.orchestrator import AgentState
from agents.writer_agent import writer_node, _build_writer_prompt
import asyncio


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_build_writer_prompt_contains_audience():
    state = AgentState(
        input_type="text",
        input_value="I built an AI tool",
        audience="founder",
        tone="bold",
        enriched_facts={"summary": "I built an AI tool that automates LinkedIn posts"},
        style_examples=[{"text": "Example post 1"}, {"text": "Example post 2"}],
    )
    prompt = _build_writer_prompt(state)
    assert "founder" in prompt.lower()
    assert "bold" in prompt.lower()
    assert "Example post 1" in prompt


def test_writer_node_produces_3_variants():
    state = AgentState(
        input_type="text",
        input_value="I built an AI tool",
        audience="engineer",
        tone="professional",
        enriched_facts={"summary": "Built a RAG pipeline"},
        style_examples=[],
    )
    mock_response = MagicMock()
    mock_response.text = '''[
        {"text": "Variant 1 post text here"},
        {"text": "Variant 2 post text here"},
        {"text": "Variant 3 post text here"}
    ]'''

    with patch('agents.writer_agent.genai') as mock_genai:
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client
        mock_client.models.generate_content.return_value = mock_response
        result = run(writer_node(state))

    assert len(result.variants) == 3
    assert result.variants[0]["text"] == "Variant 1 post text here"
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
cd postcraft
python -m pytest tests/test_writer.py -v
```

Expected: `ImportError` — module doesn't exist yet.

- [ ] **Step 3: Implement writer_agent.py**

Create `postcraft/backend/agents/writer_agent.py`:

```python
"""
Writer Agent Node.
Uses Gemini 2.5 Flash to generate 3 LinkedIn post variants.
Injects RAG style examples and user voice samples into the prompt.
"""

import json
import os
from typing import Any, Dict, List

from google import genai
from google.genai import types

from agents.orchestrator import AgentState


def _build_writer_prompt(state: AgentState) -> str:
    style_section = ""
    if state.style_examples:
        examples = "\n\n".join(
            f"Example {i+1}:\n{ex['text']}"
            for i, ex in enumerate(state.style_examples[:5])
        )
        style_section = f"\n\n## High-performing LinkedIn posts in this style:\n{examples}"

    voice_section = ""
    if state.voice_samples:
        samples = "\n\n".join(
            f"Sample {i+1}:\n{s}"
            for i, s in enumerate(state.voice_samples[:2])
        )
        voice_section = (
            f"\n\n## User's own writing style (mimic this voice exactly):\n{samples}"
        )

    audience_context = {
        "founder": "entrepreneurs, startup founders, and business builders",
        "engineer": "software engineers, developers, and technical builders",
        "jobseeker": "professionals actively seeking new roles and career opportunities",
        "recruiter": "hiring managers, talent leaders, and HR professionals",
    }.get(state.audience, state.audience)

    tone_guidance = {
        "professional": "authoritative, data-driven, polished. Use formal language.",
        "casual": "conversational, friendly, relatable. Write like you're talking to a friend.",
        "storytelling": "narrative arc with a hook, middle, and lesson. Personal and emotional.",
        "bold": "short punchy sentences. Contrarian takes. Strong opinions. Make people stop scrolling.",
    }.get(state.tone, state.tone)

    return f"""You are a world-class LinkedIn ghostwriter.

## Task
Write 3 distinct LinkedIn posts based on this content:

{state.enriched_facts.get('summary', state.input_value)}

## Audience
{state.audience} — writing FOR {audience_context}

## Tone
{state.tone} — {tone_guidance}

## LinkedIn Post Rules
- Start with a hook that stops scrolling (first line is everything)
- Use line breaks generously — no big walls of text
- Include 1 strong CTA at the end (comment, DM, follow, share)
- NO hashtags unless they add real value
- Length: 150-300 words per variant
- Each variant must have a completely different hook and angle
{style_section}{voice_section}

## Output Format
Respond ONLY with a JSON array of exactly 3 objects:
[
  {{"text": "full post text variant 1"}},
  {{"text": "full post text variant 2"}},
  {{"text": "full post text variant 3"}}
]"""


async def writer_node(state: AgentState) -> AgentState:
    print(f"\n[writer] Generating 3 variants | audience={state.audience} tone={state.tone}")

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        state.errors.append("writer_node: GEMINI_API_KEY not set")
        return state

    try:
        client = genai.Client(api_key=api_key)
        prompt = _build_writer_prompt(state)

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                max_output_tokens=4096,
                system_instruction=(
                    "You are a LinkedIn ghostwriter. Output ONLY valid JSON arrays. "
                    "No markdown, no preamble, no explanation."
                ),
            ),
        )

        raw = response.text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.rstrip("`").strip()

        variants = json.loads(raw)
        if not isinstance(variants, list) or len(variants) != 3:
            raise ValueError(f"Expected list of 3, got: {type(variants)} len={len(variants) if isinstance(variants, list) else 'N/A'}")

        state.variants = variants
        print(f"[writer] Generated {len(variants)} variants")

    except Exception as e:
        state.errors.append(f"writer_node: {str(e)}")
        print(f"[writer] Generation failed: {e}")

    return state
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd postcraft
python -m pytest tests/test_writer.py -v
```

Expected: All 2 tests PASS

- [ ] **Step 5: Commit**

```bash
git add postcraft/backend/agents/writer_agent.py postcraft/tests/test_writer.py
git commit -m "feat: writer agent generates 3 linkedin post variants with gemini"
```

---

## Task 12: Critic Agent

**Files:**
- Create: `postcraft/backend/agents/critic_agent.py`
- Create: `postcraft/tests/test_critic.py`

- [ ] **Step 1: Write the failing test**

Create `postcraft/tests/test_critic.py`:

```python
import pytest
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from unittest.mock import patch, MagicMock
from agents.orchestrator import AgentState
from agents.critic_agent import critic_node
import asyncio


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_critic_adds_scores_to_variants():
    state = AgentState(
        input_type="text",
        input_value="test",
        audience="founder",
        tone="bold",
        variants=[
            {"text": "Variant 1"},
            {"text": "Variant 2"},
            {"text": "Variant 3"},
        ]
    )
    mock_response = MagicMock()
    mock_response.text = '''[
        {"score": 8, "improvement": "Add a stronger hook"},
        {"score": 7, "improvement": "Include a metric"},
        {"score": 6, "improvement": "Shorten the CTA"}
    ]'''

    with patch('agents.critic_agent.genai') as mock_genai:
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client
        mock_client.models.generate_content.return_value = mock_response
        result = run(critic_node(state))

    assert result.variants[0]["score"] == 8
    assert result.variants[1]["score"] == 7
    assert result.variants[2]["score"] == 6
    assert result.best_index == 0
    assert "improvement" in result.variants[0]


def test_critic_skips_if_no_variants():
    state = AgentState(
        input_type="text",
        input_value="test",
        audience="founder",
        tone="bold",
        variants=[]
    )
    result = run(critic_node(state))
    assert result.variants == []
    assert len(result.errors) > 0
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
cd postcraft
python -m pytest tests/test_critic.py -v
```

Expected: `ImportError` — module doesn't exist yet.

- [ ] **Step 3: Implement critic_agent.py**

Create `postcraft/backend/agents/critic_agent.py`:

```python
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

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        state.errors.append("critic_node: GEMINI_API_KEY not set")
        return state

    try:
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

        # Pick the best variant index
        best = max(range(len(state.variants)), key=lambda i: state.variants[i].get("score", 0))
        state.best_index = best

        print(f"[critic] Scores: {[v.get('score') for v in state.variants]} | Best: variant {best+1}")

    except Exception as e:
        state.errors.append(f"critic_node: {str(e)}")
        print(f"[critic] Scoring failed: {e}")
        state.best_index = 0

    return state
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd postcraft
python -m pytest tests/test_critic.py -v
```

Expected: All 2 tests PASS

- [ ] **Step 5: Commit**

```bash
git add postcraft/backend/agents/critic_agent.py postcraft/tests/test_critic.py
git commit -m "feat: critic agent scores variants with llm-as-judge"
```

---

## Task 13: LinkedIn Tool

**Files:**
- Create: `postcraft/backend/tools/linkedin_tool.py`

- [ ] **Step 1: Create linkedin_tool.py**

Create `postcraft/backend/tools/linkedin_tool.py`:

```python
"""
LinkedIn publishing tool.
Uses linkedin-api (unofficial, credentials-based) to post text updates.
"""

import os
from typing import Any, Dict


async def post_to_linkedin(text: str, email: str, password: str) -> Dict[str, Any]:
    """
    Post text to LinkedIn as the authenticated user.

    Args:
        text: The post content.
        email: LinkedIn account email.
        password: LinkedIn account password.

    Returns:
        dict with status: "posted" | "failed", and optional error/post_id.
    """
    print(f"[linkedin_tool] Posting to LinkedIn ({len(text)} chars)")

    try:
        from linkedin_api import Linkedin
        api = Linkedin(email, password)
        api.add_connection  # validate login worked

        # linkedin-api uses create_share for text posts
        response = api._post(
            "/v2/ugcPosts",
            data={
                "author": f"urn:li:person:{api.get_profile()['entityUrn'].split(':')[-1]}",
                "lifecycleState": "PUBLISHED",
                "specificContent": {
                    "com.linkedin.ugc.ShareContent": {
                        "shareCommentary": {"text": text},
                        "shareMediaCategory": "NONE",
                    }
                },
                "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
            }
        )

        print(f"[linkedin_tool] Posted successfully")
        return {"status": "posted", "post_id": response.get("id", "")}

    except Exception as e:
        print(f"[linkedin_tool] Post failed: {e}")
        return {"status": "failed", "error": str(e)}
```

- [ ] **Step 2: Commit**

```bash
git add postcraft/backend/tools/linkedin_tool.py
git commit -m "feat: linkedin publishing tool"
```

---

## Task 14: FastAPI Endpoint

**Files:**
- Create: `postcraft/backend/main.py`
- Create: `postcraft/tests/test_api.py`

- [ ] **Step 1: Write the failing test**

Create `postcraft/tests/test_api.py`:

```python
import pytest
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient


def test_health_endpoint():
    with patch.dict(os.environ, {"GEMINI_API_KEY": "test", "SUPABASE_URL": "http://x", "SUPABASE_SERVICE_KEY": "key"}):
        from main import app
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


def test_generate_endpoint_returns_variants():
    mock_state = MagicMock()
    mock_state.variants = [
        {"text": "Post 1", "score": 8, "improvement": "Better hook"},
        {"text": "Post 2", "score": 7, "improvement": "Add metric"},
        {"text": "Post 3", "score": 6, "improvement": "Shorter CTA"},
    ]
    mock_state.best_index = 0
    mock_state.errors = []

    with patch.dict(os.environ, {"GEMINI_API_KEY": "test", "SUPABASE_URL": "http://x", "SUPABASE_SERVICE_KEY": "key"}):
        with patch('main.postcraft_graph') as mock_graph:
            mock_graph.ainvoke = AsyncMock(return_value=mock_state.model_dump() if hasattr(mock_state, 'model_dump') else {
                "variants": mock_state.variants,
                "best_index": 0,
                "errors": [],
            })
            from main import app
            client = TestClient(app)
            response = client.post("/generate", json={
                "input_type": "text",
                "input_value": "I built an AI tool",
                "audience": "founder",
                "tone": "bold",
                "voice_samples": [],
            })

        assert response.status_code == 200
        data = response.json()
        assert "variants" in data
        assert "best_index" in data
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
cd postcraft
python -m pytest tests/test_api.py::test_health_endpoint -v
```

Expected: `ImportError` — main.py doesn't exist yet.

- [ ] **Step 3: Implement main.py**

Create `postcraft/backend/main.py`:

```python
"""
PostCraft FastAPI application.

Endpoints:
  GET  /health        — health check
  POST /generate      — run the 5-node agent pipeline
  POST /publish       — post to LinkedIn
"""

import os
import time
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agents.orchestrator import AgentState, postcraft_graph
from memory.supabase_rag import store_draft, log_event

app = FastAPI(
    title="PostCraft API",
    description="Agentic LinkedIn post generator",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class GenerateRequest(BaseModel):
    input_type: str       # github | image | text
    input_value: str      # URL, base64 image, or text
    audience: str         # founder | engineer | jobseeker | recruiter
    tone: str             # professional | casual | storytelling | bold
    voice_samples: List[str] = []


class PublishRequest(BaseModel):
    text: str
    linkedin_email: str
    linkedin_password: str


@app.get("/health")
async def health():
    return {"status": "ok", "service": "postcraft-api"}


@app.post("/generate")
async def generate(request: GenerateRequest) -> Dict[str, Any]:
    """
    Run the full 5-node agent pipeline and return 3 scored post variants.
    """
    print(f"\n[api] POST /generate | type={request.input_type} audience={request.audience}")
    start = time.time()

    state = AgentState(
        input_type=request.input_type,
        input_value=request.input_value,
        audience=request.audience,
        tone=request.tone,
        voice_samples=request.voice_samples,
    )

    try:
        result = await postcraft_graph.ainvoke(state.model_dump())
        elapsed = int((time.time() - start) * 1000)

        variants = result.get("variants", [])
        best_index = result.get("best_index", 0)
        errors = result.get("errors", [])

        # Store to Supabase
        store_draft(
            input_type=request.input_type,
            audience=request.audience,
            tone=request.tone,
            variants=variants,
            best_index=best_index,
            generation_time_ms=elapsed,
        )

        log_event(
            event="generate",
            input_type=request.input_type,
            audience=request.audience,
            generation_time_ms=elapsed,
        )

        print(f"[api] Generated {len(variants)} variants in {elapsed}ms")
        return {
            "variants": variants,
            "best_index": best_index,
            "generation_time_ms": elapsed,
            "errors": errors,
        }

    except Exception as e:
        log_event(event="error", input_type=request.input_type, error=str(e))
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")


@app.post("/publish")
async def publish(request: PublishRequest) -> Dict[str, Any]:
    """Post the selected text to LinkedIn."""
    from tools.linkedin_tool import post_to_linkedin

    print(f"[api] POST /publish | {len(request.text)} chars")

    result = await post_to_linkedin(
        text=request.text,
        email=request.linkedin_email,
        password=request.linkedin_password,
    )

    log_event(event="publish")

    if result.get("status") == "failed":
        raise HTTPException(status_code=500, detail=result.get("error", "Publish failed"))

    return result
```

- [ ] **Step 4: Run all tests**

```bash
cd postcraft
python -m pytest tests/ -v
```

Expected: All tests PASS

- [ ] **Step 5: Start the server and test manually**

```bash
cd postcraft/backend
uvicorn main:app --reload --port 8000
```

In a new terminal:
```bash
curl http://localhost:8000/health
```

Expected:
```json
{"status": "ok", "service": "postcraft-api"}
```

- [ ] **Step 6: Test the generate endpoint**

```bash
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{
    "input_type": "text",
    "input_value": "I just completed my first open source project with 100 GitHub stars",
    "audience": "engineer",
    "tone": "storytelling",
    "voice_samples": []
  }'
```

Expected: JSON with `variants` array of 3 posts, each with `text`, `score`, `improvement`.

- [ ] **Step 7: Commit**

```bash
git add postcraft/backend/main.py postcraft/tests/test_api.py
git commit -m "feat: fastapi endpoints for generate and publish"
```

---

## Task 15: Run Full Test Suite

- [ ] **Step 1: Run all tests**

```bash
cd postcraft
python -m pytest tests/ -v --tb=short
```

Expected: All tests PASS

- [ ] **Step 2: Final commit**

```bash
git add -A
git commit -m "feat: postcraft backend complete - all tests passing"
```

---

## Done

The backend is complete. You can now:
- `POST /generate` with a GitHub URL, image, or text → get 3 scored LinkedIn post variants
- `POST /publish` to push a post live to LinkedIn
- `GET /health` for uptime checks

**Next:** Implement Plan 2 — the Next.js frontend.
