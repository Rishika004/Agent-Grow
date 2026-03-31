# AgentGrow

An autonomous AI growth agent that runs daily for BuildAI users. It researches trending topics, writes SEO blog posts using Google Gemini 2.5 Flash, waits for human approval, publishes to Ghost CMS, posts to LinkedIn, reads PostHog analytics, and improves each cycle using persistent Mem0 memory.

Built as a portfolio project targeting [BuildAI](https://buildai.space) — a no-code AI SaaS company.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        GROWTH AGENT PIPELINE                        │
│                    (LangGraph StateGraph)                            │
│                                                                     │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────────────┐   │
│  │ load_memory  │──▶│   research   │──▶│      content         │   │
│  │  (Mem0 AI)   │   │   (Tavily)   │   │  (Gemini 2.5 Flash)  │   │
│  └──────────────┘   └──────────────┘   └──────────┬───────────┘   │
│                                                    │               │
│                                         ┌──────────▼───────────┐  │
│                                         │   await_approval     │  │
│                                         │  ⏸ HUMAN IN LOOP     │  │
│                                         │  POST /approve/{id}  │  │
│                                         └──────────┬───────────┘  │
│                                                    │               │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────▼───────────┐  │
│  │update_memory │◀──│   evaluate   │◀──│      linkedin        │  │
│  │   (Mem0)     │   │ LLM-as-judge │   │  (linkedin-api)      │  │
│  └──────────────┘   │  (Gemini)    │   └──────────────────────┘  │
│         │           └──────────────┘                              │
│         ▼                                                          │
│        END                                                         │
└─────────────────────────────────────────────────────────────────────┘

External Integrations:
  Tavily ──────────── web research & trend discovery
  Gemini 2.5 Flash ── content writing + LLM-as-judge scoring
  Ghost CMS ──────── blog post publishing (Admin API + JWT)
  linkedin-api ────── LinkedIn post publishing (unofficial)
  PostHog ─────────── analytics reading (page views, engagement)
  Mem0 ────────────── persistent vector memory (what worked before)
  Supabase ────────── draft storage + pgvector for self-hosted Mem0
  FastAPI ─────────── approval UI endpoints + scheduler webhook
```

---

## Agent Node Reference

| Node | Description |
|------|-------------|
| `load_memory` | Fetches last 5 relevant memories from Mem0 to inject into content prompts |
| `research` | Runs dual Tavily searches: trending topics + competitor posts for the niche |
| `content` | Calls Gemini 2.5 Flash to write 2 SEO blog posts + LinkedIn hooks per cycle |
| `await_approval` | Pauses the graph (LangGraph interrupt) until a human approves via API |
| `linkedin` | Posts the approved LinkedIn hook to the user's LinkedIn profile |
| `evaluate` | Fetches PostHog analytics and uses Gemini as LLM-as-judge to score 1-10 |
| `update_memory` | Stores scored post data to Mem0 so the next cycle improves |

---

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/Rishika004/Agent-Grow.git
cd Agent-Grow
```

### 2. Create a virtual environment and install dependencies

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure environment variables

```bash
cp .env.example .env
# Edit .env and fill in your API keys
```

Required keys:

| Variable | Where to get it |
|----------|-----------------|
| `GEMINI_API_KEY` | [aistudio.google.com](https://aistudio.google.com/apikey) |
| `TAVILY_API_KEY` | [tavily.com](https://tavily.com) |
| `SUPABASE_URL` + `SUPABASE_SERVICE_KEY` | Supabase project settings |
| `MEM0_API_KEY` | [mem0.ai](https://mem0.ai) |
| `GHOST_API_URL` + `GHOST_ADMIN_KEY` | Ghost Admin → Integrations |
| `POSTHOG_API_KEY` + `POSTHOG_PROJECT_ID` | PostHog project settings |
| `LINKEDIN_EMAIL` + `LINKEDIN_PASSWORD` | Your LinkedIn credentials |

### 4. Create Supabase table

Run this SQL in your Supabase project:

```sql
CREATE TABLE drafts (
  id UUID PRIMARY KEY,
  cycle_id TEXT,
  user_id TEXT,
  niche TEXT,
  status TEXT DEFAULT 'pending_approval',
  title TEXT,
  slug TEXT UNIQUE,
  body_markdown TEXT,
  meta_description TEXT,
  target_keyword TEXT,
  linkedin_hook TEXT,
  source_topic_url TEXT,
  rejection_reason TEXT,
  approved_at TIMESTAMPTZ,
  rejected_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## Running

### Test one cycle (CLI)

```bash
python -m src.main
```

This runs a full cycle, pauses at `await_approval`, and prints results.

### Start the API server

```bash
uvicorn src.main:app --reload --port 8000
```

### Trigger a cycle via API

```bash
curl -X POST http://localhost:8000/api/run \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user-001", "niche": "no-code app building for coaches"}'
```

### Review pending drafts

```bash
curl http://localhost:8000/api/tasks
```

### Approve a draft (resumes publishing pipeline)

```bash
curl -X POST http://localhost:8000/api/approve/{draft_id}
```

### Reject a draft

```bash
curl -X POST http://localhost:8000/api/reject/{draft_id} \
  -H "Content-Type: application/json" \
  -d '{"reason": "Topic is too generic"}'
```

### Weekly report

```bash
curl http://localhost:8000/api/reports/weekly
```

---

## Scheduling Daily Runs (n8n)

1. Create an n8n workflow with a **Cron** trigger (e.g., `0 8 * * *` for 8am daily)
2. Add an **HTTP Request** node:
   - Method: `POST`
   - URL: `http://your-server:8000/scheduler/trigger`
   - Header: `X-Webhook-Secret: your-secret`
   - Body: `{"user_id": "user-001", "niche": "no-code app building for coaches", "trigger_source": "n8n"}`

---

## Running Tests

```bash
pytest tests/ -v
```

---

## Project Structure

```
growth-agent/
├── src/
│   ├── main.py                  # Entry point + FastAPI app composition
│   ├── agents/
│   │   ├── orchestrator.py      # AgentState + LangGraph StateGraph
│   │   ├── research_agent.py    # Tavily research node
│   │   ├── content_agent.py     # Gemini 2.5 Flash content node
│   │   ├── linkedin_agent.py    # LinkedIn posting node
│   │   └── analytics_agent.py  # PostHog + LLM-as-judge node
│   ├── tools/
│   │   ├── tavily_tool.py       # Tavily search wrapper
│   │   ├── linkedin_tool.py     # linkedin-api wrapper
│   │   ├── cms_tool.py          # Ghost Admin API + JWT
│   │   └── analytics_tool.py   # PostHog API queries
│   ├── memory/
│   │   └── mem0_client.py       # Mem0 store + retrieve wrappers
│   ├── api/
│   │   └── routes.py            # FastAPI endpoints
│   └── scheduler/
│       └── trigger.py           # Webhook trigger for n8n/cron
├── tests/
│   ├── test_research.py
│   └── test_content.py
├── .env.example
├── requirements.txt
└── README.md
```

---

## Tech Stack

- **Python 3.11+** — Modern async Python
- **LangGraph** — Agent orchestration with interrupt/resume support
- **Google Gemini 2.5 Flash** — Content writing + LLM-as-judge evaluation
- **Tavily** — Real-time web research
- **Mem0** — Persistent agent memory with semantic search
- **Supabase** — PostgreSQL database for draft storage
- **Ghost CMS** — Blog publishing via Admin API
- **linkedin-api** — LinkedIn posting (unofficial, credentials-based)
- **PostHog** — Analytics event querying
- **FastAPI** — REST API for approval workflow + scheduling

---

*Built for BuildAI internship portfolio — [buildai.space](https://buildai.space)*
