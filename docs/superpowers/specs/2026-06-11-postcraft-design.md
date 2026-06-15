# PostCraft — LinkedIn Post Generator: Design Spec
**Date:** 2026-06-11  
**Status:** Approved

---

## Overview

PostCraft is an agentic AI system that generates audience-targeted LinkedIn posts from three input types: GitHub links, images, and plain text experience. It uses a 5-node LangGraph pipeline, RAG from a curated style library, and Gemini 2.5 Flash for writing and evaluation. Users can edit posts inline and optionally publish directly to LinkedIn.

---

## User Flow

1. User lands on the page
2. Picks input type: **GitHub Link / Image / Text**
3. Picks audience: **Founder / Engineer / Job Seeker / Recruiter**
4. Picks tone: **Professional / Casual / Storytelling / Bold**
5. Optionally pastes 1–2 of their own past LinkedIn posts (voice training)
6. Hits **Generate**
7. Sees 3 post variants with LLM-as-judge scores (1–10)
8. Edits inline
9. **Copies to clipboard** OR **publishes directly to LinkedIn**

---

## Architecture

```
User (Browser)
      │
      ▼
Next.js Frontend (Vercel)
      │  REST API calls
      ▼
FastAPI Backend (AWS EC2 t2.micro)
      │
      ▼
LangGraph Pipeline
  ├── Intake Agent        → classifies input type, extracts raw data
  ├── Enrichment Agent   → GitHub API / Gemini Vision / text parse
  ├── RAG Agent          → Supabase pgvector similarity search
  ├── Writer Agent       → Gemini 2.5 Flash generates 3 variants
  └── Critic Agent       → LLM-as-judge scores all 3, picks best
      │
      ▼
Supabase
  ├── style_library      → curated posts with pgvector embeddings
  └── generated_drafts   → saved generation history + usage logs
```

---

## Agent Nodes

| Node | Input | Output |
|------|-------|--------|
| Intake | raw user input (URL / image / text) | input type + cleaned structured data |
| Enrichment | GitHub URL → GitHub API; image → Gemini Vision; text → parse | structured facts dict |
| RAG | enriched context + audience type | 5 similar style posts from Supabase |
| Writer | facts + style examples + audience + tone + user voice samples | 3 LinkedIn post variants |
| Critic | 3 variants | scores 1–10 each, best pick, one improvement tip per variant |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14, Tailwind CSS, shadcn/ui |
| Backend | FastAPI, LangGraph, Python 3.11 |
| LLM | Gemini 2.5 Flash (writing + vision + judge) |
| Embeddings | Google text-embedding-004 (768 dimensions) |
| Database | Supabase PostgreSQL + pgvector |
| GitHub data | GitHub REST API (public repos, no auth needed) |
| LinkedIn publish | linkedin-api (unofficial, credential-based) |
| Frontend deploy | Vercel (free tier) |
| Backend deploy | AWS EC2 t2.micro (free tier, 12 months) |

---

## Monitoring & Analytics

| Tool | Purpose |
|------|---------|
| Vercel Analytics | Traffic — page views, unique visitors, countries, devices |
| PostHog | Behaviour — input type usage, audience selection, drop-off points |
| Supabase `usage_logs` table | Usage — posts generated, generation time, errors, feature breakdown |

All three are free at this scale.

---

## Database Schema

### `style_library` (RAG corpus)
```sql
CREATE TABLE style_library (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  text TEXT NOT NULL,
  audience TEXT,        -- founder | engineer | jobseeker | recruiter
  tone TEXT,            -- professional | casual | storytelling | bold
  embedding VECTOR(768),
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### `generated_drafts` (history + logs)
```sql
CREATE TABLE generated_drafts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  input_type TEXT,      -- github | image | text
  audience TEXT,
  tone TEXT,
  variants JSONB,       -- array of 3 generated posts with scores
  best_variant TEXT,
  published BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### `usage_logs` (PostHog alternative / backup)
```sql
CREATE TABLE usage_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  event TEXT,           -- generate | copy | publish | error
  input_type TEXT,
  audience TEXT,
  generation_time_ms INTEGER,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## Folder Structure

```
postcraft/
├── frontend/                    (Next.js — deploy to Vercel)
│   ├── app/
│   │   ├── page.tsx             # main input UI
│   │   ├── layout.tsx
│   │   └── api/
│   │       └── generate/
│   │           └── route.ts     # proxy to FastAPI backend
│   ├── components/
│   │   ├── InputSelector.tsx    # GitHub / Image / Text tabs
│   │   ├── AudienceSelector.tsx
│   │   ├── ToneSelector.tsx
│   │   ├── VoiceSamples.tsx     # past posts input
│   │   ├── PostVariants.tsx     # 3 cards with scores
│   │   ├── InlineEditor.tsx     # editable post card
│   │   └── PublishButton.tsx    # copy + LinkedIn publish
│   └── package.json
│
├── backend/                     (FastAPI — deploy to AWS EC2)
│   ├── main.py                  # FastAPI app entry point
│   ├── agents/
│   │   ├── orchestrator.py      # AgentState + LangGraph graph
│   │   ├── intake_agent.py      # input classifier node
│   │   ├── enrichment_agent.py  # GitHub API + Vision + text node
│   │   ├── rag_agent.py         # Supabase pgvector retrieval node
│   │   ├── writer_agent.py      # Gemini 2.5 Flash writer node
│   │   └── critic_agent.py      # LLM-as-judge scoring node
│   ├── tools/
│   │   ├── github_tool.py       # GitHub REST API wrapper
│   │   ├── vision_tool.py       # Gemini Vision image analysis
│   │   └── linkedin_tool.py     # linkedin-api publish wrapper
│   ├── memory/
│   │   └── supabase_rag.py      # embed + retrieve from pgvector
│   └── requirements.txt
│
├── posts.json                   # style library source data
├── seed_posts.py                # one-time Supabase seeding script
└── docs/
    └── superpowers/
        └── specs/
            └── 2026-06-11-postcraft-design.md
```

---

## API Contract

### `POST /api/generate`
**Request:**
```json
{
  "input_type": "github",
  "input_value": "https://github.com/user/repo",
  "audience": "engineer",
  "tone": "storytelling",
  "voice_samples": ["optional past post 1", "optional past post 2"]
}
```

**Response:**
```json
{
  "variants": [
    { "text": "...", "score": 8, "improvement": "Add a hook in line 1" },
    { "text": "...", "score": 7, "improvement": "Make the CTA clearer" },
    { "text": "...", "score": 6, "improvement": "Use shorter sentences" }
  ],
  "best_index": 0,
  "generation_time_ms": 4200
}
```

### `POST /api/publish`
**Request:**
```json
{
  "text": "final edited post text",
  "linkedin_email": "user@email.com",
  "linkedin_password": "password"
}
```

---

## Error Handling

- Each agent node catches exceptions independently — one failure does not crash the pipeline
- GitHub API unavailable → Enrichment Agent falls back to URL metadata only
- Gemini Vision fails → Vision node returns empty facts, Writer uses text description
- RAG returns 0 results → Writer proceeds with tone prompt only (no style examples)
- LinkedIn publish fails → UI shows error, copy-to-clipboard always works as fallback

---

## Out of Scope (V1)

- User authentication / accounts
- Saving post history per user (no login)
- Scheduling LinkedIn posts
- Auto-growing style library via scraping
- Support for Twitter/X or other platforms
