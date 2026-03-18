# NCERT Study App — Master Plan

> **Single source of truth** for architecture decisions, project structure, content pipeline, backend API, and development workflow.

---

## Table of Contents

1. [Project Vision](#1-project-vision)
2. [Architecture Overview](#2-architecture-overview)
3. [Project Structure](#3-project-structure)
4. [Content Generation Pipeline](#4-content-generation-pipeline)
5. [Backend API Design](#5-backend-api-design)
6. [Database Schema](#6-database-schema)
7. [Frontend Architecture](#7-frontend-architecture)
8. [Development Workflow](#8-development-workflow)
9. [Deployment](#9-deployment)
10. [Roadmap](#10-roadmap)

---

## 1. Project Vision

Build a **mobile-first study companion** for NCERT/CBSE students targeting Class 10 and Class 12 exams. The app generates **personalized daily study plans** from AI-structured content derived directly from official NIOS textbook PDFs and historical PYQ (Previous Year Question) papers.

### Core Principles

| Principle              | Implementation                                                                    |
| ---------------------- | --------------------------------------------------------------------------------- |
| **Zero hallucination** | Every content block carries an `exact_source_quote` verified against source text  |
| **Exam-first**         | PYQ frequency scores drive topic priority; study plans adapt to exam date         |
| **Offline-capable**    | All content pre-generated and baked into the worker bundle (no runtime LLM calls) |
| **Low-cost**           | Cloudflare Workers free tier (100K requests/day), no database costs initially     |
| **Multilingual**       | Content in English, Hindi, and Hinglish (planned)                                 |

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    CONTENT PIPELINE (Python)                 │
│                                                             │
│       HuggingFace Dataset → 01_build_ncert → TypeScript      │
│                                    ↓                        │
│                             backend/src/data/               │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                   BACKEND (Cloudflare Worker)                │
│                                                             │
│  index.ts (router) → routes/ → services/                    │
│       ↓                                                     │
│  Static JSON data (bundled in worker)                        │
│  Plan generator (runs at request time)                       │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                    FRONTEND (React + Vite)                   │
│                                                             │
│  Mobile-first SPA                                           │
│  Subject browser → Topic viewer → Daily plan                │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Project Structure

```
nios-study-app/
├── MASTER_PLAN.md              ← This document
├── README.md                   ← Quick start guide
├── schema.sql                  ← D1 database schema (future)
├── LICENSE
│
├── pipeline/                   ← Content generation (Python)
│   ├── config.py               ← Paths, API keys, subject registry
│   ├── schemas.py              ← Pydantic models (shared data shapes)
│   ├── 01_build_ncert/         ← Maps HuggingFace NCERT JSON to TS
│   │   └── build.py
│   └── output/                 ← Pipeline artifacts (gitignored)
│
├── content/                    ← Raw source material (downloaded from Drive)
│   └── class12/
│       └── maths-12/
│           ├── pdfs/           ← 38 NIOS lesson PDFs
│           └── pyqs_raw/       ← 6 PYQ papers (2019-2024)
│
├── backend/                    ← Cloudflare Worker API
│   ├── package.json
│   ├── wrangler.toml
│   └── src/
│       ├── index.ts            ← Thin router (dispatches to routes/)
│       ├── types.ts            ← Shared TypeScript interfaces
│       ├── routes/
│       │   ├── catalog.ts      ← Subject/chapter/topic/PYQ endpoints
│       │   ├── plan.ts         ← Daily plan generation endpoint
│       │   └── health.ts       ← Health check
│       ├── services/
│       │   └── planGenerator.ts ← Smart plan algorithm
│       ├── data/
│       │   ├── index.ts        ← Data loader (generated → mock fallback)
│       │   └── generated.ts    ← Re-exports from pipeline output
│       ├── lib/
│       │   └── response.ts     ← JSON/CORS helpers
│       ├── generatedData.ts    ← Pipeline-generated content
│       └── mockData.ts         ← Fallback mock data
│
└── web/                        ← React frontend
    ├── package.json
    ├── vite.config.ts
    └── src/
        ├── App.tsx             ← Main SPA component
        ├── api.ts              ← Backend API client
        ├── catalogApi.ts       ← Catalog-specific API calls
        ├── domain.ts           ← Shared domain types
        └── main.tsx            ← Entry point
```

---

## 4. Content Generation Pipeline

### 4.1 Pipeline Overview
The pipeline transforms raw HuggingFace NCERT datasets into structured study content. It is a single deterministic script that maps existing JSON properties (like `Explanation`, `Question`, `Answer`) directly to our TypeScript models.

| Stage | Script | Input | Output | Runs On |
| --- | --- | --- | --- | --- |
| **01 Build NCERT** | `build.py` | HuggingFace JSON | `generated.ts` | Local |

### 4.2 Data Models (`schemas.py`)
All pipelines share Pydantic models defined in `schemas.py`. This is the single source of truth for data shapes.
* `Subject`, `Chapter`, `Topic`, `TopicContent`
* `PYQ`, `PYQExplanation`

## 5. Backend API Design

### 5.1 Architecture

The backend is a **Cloudflare Worker** — a single JavaScript bundle deployed to Cloudflare's edge. All content is bundled as static TypeScript arrays (no database yet).

**Module layout:**

```
backend/src/
├── index.ts              ← Router: URL matching → handler dispatch
├── types.ts              ← Shared interfaces (Subject, Chapter, Topic, etc.)
├── routes/
│   ├── catalog.ts        ← Read-only content endpoints
│   ├── plan.ts           ← Plan generation endpoint
│   └── health.ts         ← Health check
├── services/
│   └── planGenerator.ts  ← Smart plan algorithm
├── data/
│   ├── index.ts          ← Data loader (generated with mock fallback)
│   └── generated.ts      ← Re-exports from pipeline output
└── lib/
    └── response.ts       ← JSON serialization + CORS headers
```

### 5.2 API Endpoints

| Method | Path                                                                                 | Description                                       |
| ------ | ------------------------------------------------------------------------------------ | ------------------------------------------------- |
| `GET`  | `/api/health`                                                                        | Health check + version                            |
| `GET`  | `/api/subjects?classLevel=12`                                                        | List subjects for a class level                   |
| `GET`  | `/api/subjects/:id/syllabus`                                                         | Full chapter → topic tree with `hasContent` flags |
| `GET`  | `/api/topics/:id/details?lang=en`                                                    | Topic content + PYQs with explanations            |
| `GET`  | `/api/subjects/:id/pyqs?lang=en`                                                     | All PYQs for a subject with explanations          |
| `GET`  | `/api/plan/today?subjects=...&dailyMinutes=60&goal=pass&examDate=...&doneTopics=...` | Generate personalized daily study plan            |

### 5.3 Plan Generator Algorithm

The plan generator in `services/planGenerator.ts` implements a smart scheduling algorithm:

**Input parameters:**

- `subjectIds` — which subjects to study
- `dailyMinutes` — available study time
- `goal` — `pass` | `sixty` | `eighty`
- `examDate` — ISO date string for deadline awareness
- `doneTopicIds` — already completed topics to exclude

**Algorithm:**

1. **Priority scoring**: Each topic scored by `highYieldScore` + PYQ frequency boost + goal multiplier
2. **Days remaining**: Spreads undone topics across remaining days until exam
3. **Goal-based cutoff**: `pass` = top 60% topics, `sixty` = top 80%, `eighty` = all
4. **Round-robin**: Alternates between subjects to prevent single-subject domination
5. **Time budgeting**: Fills daily time with READ_NOTES + PRACTICE_PYQ_SET tasks
6. **Spaced repetition**: 20% of daily time reserved for REVISE_WRONGS on completed topics

**Task types:**

- `READ_NOTES` — Study the topic content (bullets, why important, common mistakes)
- `PRACTICE_PYQ_SET` — Practice PYQs related to the topic
- `REVISE_WRONGS` — Revisit previously studied topics that have PYQs

### 5.4 Response Format

All responses use consistent JSON with CORS headers:

```typescript
// lib/response.ts
export function json(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "Content-Type": "application/json",
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
    },
  });
}
```

### 5.5 Data Loading Strategy

```
Pipeline output (generated.ts)
       ↓ (if non-empty)
   Data loader (data/index.ts)
       ↓ (else fallback)
   Mock data (mockData.ts)
```

The `data/index.ts` module exports unified arrays that routes import. This means routes never need to know whether they're using generated or mock data.

---

## 6. Database Schema

The `schema.sql` defines tables for **Cloudflare D1** (SQLite-based). Currently NOT wired — all data is baked into the worker bundle. The schema is designed for future migration.

**Table groups:**

| Group             | Tables                                | Purpose                                   |
| ----------------- | ------------------------------------- | ----------------------------------------- |
| **Catalog**       | Subject, Chapter, Topic, TopicContent | Read-only study content                   |
| **PYQ Bank**      | PYQ, PYQExplanation                   | Question bank with solutions              |
| **User**          | User                                  | Profile with goal, exam date, preferences |
| **Learning Path** | LearningPath, LearningPathStep        | Generated study schedules                 |
| **Progress**      | UserProgress, TaskCompletion          | Per-topic completion tracking             |

**Migration plan:**

1. Phase 1 (current): All data in TypeScript arrays, no persistence
2. Phase 2: Wire D1 for user progress only (catalog stays bundled)
3. Phase 3: Move catalog to D1, add R2 for PDF storage

---

## 7. Frontend Architecture

### 7.1 Current State

Single-page React app (`web/src/App.tsx` — ~1095 lines) with:

- Subject grid → Chapter accordion → Topic detail view
- Daily plan view with task cards
- Language selector (en/hi/hinglish)
- Mobile-first responsive design

### 7.2 Tech Stack

- **React 19** + **TypeScript 5.9**
- **Vite 7** for dev/build
- No component library — custom CSS
- No state management library — useState/useEffect

### 7.3 Future Improvements

- [ ] Split App.tsx into components (SubjectGrid, ChapterList, TopicDetail, PlanView)
- [ ] Add React Router for deep linking
- [ ] Add offline support via service worker
- [ ] PWA manifest for mobile install
- [ ] Progress persistence (localStorage → D1 sync)

---

## 8. Development Workflow

### 8.1 Prerequisites

- **Node.js 18+** and **npm**
- **Python 3.10+** and **pip** (tested with 3.13)
- **Google account** (for Colab PDF extraction and Drive storage)
- **API keys**: Gemini (free tier, for Stage 03), Claude (Anthropic, for Stage 05)
- **Optional**: DeepSeek V3 (alternative for Stage 03)

### 8.2 Local Development

**Backend:**

```bash
cd backend
npm install
npx wrangler dev   # Starts local worker at http://localhost:8787
```

**Frontend:**

```bash
cd web
npm install
npm run dev        # Starts Vite dev server at http://localhost:5173
```

**Pipeline:**

```bash
cd pipeline
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # Add your API keys
```

### 8.3 Adding a New Subject

1. Ensure subject exists in `pipeline/01_scrape/subjects_12.json` (run `generate_subjects.py` to refresh)
2. Run scraper: `cd pipeline/01_scrape && python scrape_nios.py` → select the subject
3. Download PDFs from Google Drive to `content/class12/<subject>/pdfs/`
4. Add entry to `pipeline/config.py` → `SUBJECTS` dict
5. Run full pipeline (stages 02-06)
6. Deploy: `cd backend && npx wrangler deploy`

---

## 9. Deployment

### 9.1 Backend (Cloudflare Workers)

```bash
cd backend
npx wrangler deploy
```

**Configuration** (`wrangler.toml`):

- Worker name: `nios-study-app`
- Compatibility date: 2025-04-01
- Main entry: `src/index.ts`

**Limits (free tier):**

- 100,000 requests/day
- 10ms CPU time per request
- 1MB worker size (compressed)

### 9.2 Frontend

Options:

- **Cloudflare Pages**: `cd web && npm run build`, deploy `dist/`
- **Vercel/Netlify**: Connect GitHub repo, auto-deploy
- **GitHub Pages**: Static build, configure base URL

---

## 10. Roadmap

### Phase 1: Foundation (Current)

- [x] Project restructure with modular pipeline
- [x] Backend API modularization (routes/services/data)
- [x] Smart plan generator with exam-date awareness
- [x] Anti-hallucination verification pipeline
- [x] Pydantic schemas as single source of truth
- [x] Colab extraction notebook with memory management & image filtering
- [x] Drive download helper script (`download_from_drive.py`)
- [x] Gemini provider with smart 429 handling (retry_in parsing, backslash sanitizer)
- [x] 19 chapters extracted to Markdown (Chapter 1-19, Chapter 20 empty in source)
- [ ] Run full Stage 03 for maths-12 (421 chunks, ~63 min estimated)
- [ ] Run Stages 04-06

### Phase 2: Content Quality

- [ ] Complete Stage 03 structuring for all 19 maths-12 chapters
- [ ] Run Stage 04 verification — target 85%+ pass rate
- [ ] Solve all 6 PYQ papers (2019-2024) via Stage 05
- [ ] Map PYQ questions to topics
- [ ] Generate Hindi and Hinglish content

### Phase 3: User Experience

- [ ] Split frontend into proper components
- [ ] Add user onboarding flow (class, subjects, goal, exam date)
- [ ] Implement progress tracking (localStorage)
- [ ] PWA support (offline access, install prompt)
- [ ] Add spaced repetition reminders

### Phase 4: Scale

- [ ] Add more subjects (English, Science, Social Studies)
- [ ] Wire Cloudflare D1 for user data persistence
- [ ] Add R2 storage for PDF viewing in-app
- [ ] User authentication
- [ ] Analytics dashboard

### Phase 5: Intelligence

- [ ] Adaptive learning path (adjusts based on quiz performance)
- [ ] Weak topic detection from PYQ practice scores
- [ ] Exam simulator (timed mock tests from PYQ bank)
- [ ] AI tutor chat (Claude-powered, with source citations)

---

## Key Design Decisions

| Decision                         | Rationale                                                                                                                               |
| -------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| **Bundled data, no DB**          | Cloudflare Workers have instant cold start — no round-trip to D1. Content is static until pipeline re-runs                              |
| **Kaggle for extraction**        | GPU T4 acceleration for marker-pdf. Kaggle provides free T4/A100 GPU access                                                             |
| **Gemini 2.5 Flash-Lite**        | Free tier, fastest model (2.7s/chunk), no thinking overhead, designed for high-volume at-scale usage. DeepSeek V3 available as fallback |
| **OpenAI-compatible endpoint**   | Gemini's `/v1beta/openai` endpoint lets us use the same httpx code for any OpenAI-compatible provider                                   |
| **Claude for PYQ solving**       | Superior at step-by-step mathematical reasoning                                                                                         |
| **exact_source_quote**           | Forces the structuring LLM to ground every claim in source text. Verification stage catches fabrications                                |
| **Numbered pipeline stages**     | Clear execution order, each stage independent with checkpointing — can resume mid-pipeline after failures                               |
| **TypeScript arrays**            | Zero latency at query time — just array.filter(). No ORM overhead, no connection pooling                                                |
| **Pydantic as schema authority** | Python pipeline produces the data, Pydantic enforces shape. TypeScript types mirror Pydantic models                                     |

---

_Last updated: March 2026_
