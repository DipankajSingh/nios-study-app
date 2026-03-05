# NIOS Study App — Master Plan

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

Build a **mobile-first study companion** for NIOS (National Institute of Open Schooling) students targeting Class 10 and Class 12 exams. The app generates **personalized daily study plans** from AI-structured content derived directly from official NIOS textbook PDFs and historical PYQ (Previous Year Question) papers.

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
│  01_scrape → 02_extract → 03_structure → 04_verify          │
│      ↓           ↓            ↓              ↓              │
│  NIOS PDFs   Markdown     Structured      Verified          │
│              (Colab)       JSON (AI)       JSON              │
│                                              ↓              │
│                              05_solve → 06_seed             │
│                              PYQ sols   TypeScript          │
│                                           ↓                 │
│                                    backend/src/data/        │
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
│   ├── requirements.txt
│   ├── .env.example
│   │
│   ├── 01_scrape/              ← Scrape PDFs from NIOS → Google Drive
│   │   ├── scrape_nios.py      ← Interactive CLI scraper
│   │   ├── generate_subjects.py ← Regenerate subject lists
│   │   ├── subjects_10.json
│   │   ├── subjects_12.json
│   │   ├── downloads_registry.json
│   │   ├── credentials.json    ← Google OAuth (gitignored)
│   │   └── token.json          ← Auto-generated auth token (gitignored)
│   │
│   ├── 02_extract/             ← PDF → Markdown (Google Colab)
│   │   └── extract_pdf.py
│   │
│   ├── 03_structure/           ← Markdown → structured JSON (DeepSeek V3)
│   │   └── structure_content.py
│   │
│   ├── 04_verify/              ← Anti-hallucination verification
│   │   └── verify_content.py
│   │
│   ├── 05_solve/               ← PYQ extraction + solving (Claude)
│   │   └── solve_pyqs.py
│   │
│   ├── 06_seed/                ← JSON → TypeScript for backend
│   │   └── seed_backend.py
│   │
│   └── output/                 ← Pipeline artifacts (gitignored)
│       ├── extracted/
│       ├── structured/
│       ├── verified/
│       └── solved/
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

The pipeline transforms raw NIOS PDFs into structured, verified study content. Each stage has its own directory, CLI entry point, and checkpoint system for resumability.

| Stage            | Script                 | Input                    | Output              | Runs On          |
| ---------------- | ---------------------- | ------------------------ | ------------------- | ---------------- |
| **01 Scrape**    | `scrape_nios.py`       | NIOS website             | PDFs → Google Drive | Local            |
| **02 Extract**   | `extract_pdf.py`       | PDFs                     | Markdown files      | **Google Colab** |
| **03 Structure** | `structure_content.py` | Markdown/raw JSON        | Structured JSON     | Local (API)      |
| **04 Verify**    | `verify_content.py`    | Structured JSON + source | Verified JSON       | Local            |
| **05 Solve**     | `solve_pyqs.py`        | PYQ papers               | Solved PYQ JSON     | Local (API)      |
| **06 Seed**      | `seed_backend.py`      | Verified JSON + PYQs     | TypeScript file     | Local            |

### 4.2 Data Models (schemas.py)

All pipeline stages share Pydantic models defined in `pipeline/schemas.py`. This is the **single source of truth** for data shapes.

**Core models:**

```python
class Subject:       id, name, classLevel, description, icon
class Chapter:       id, subjectId, title, orderIndex
class Topic:         id, chapterId, title, orderIndex, highYieldScore, estMinutes
class TopicContent:  id, topicId, lang, summaryBullets, whyImportant, commonMistakes
class ContentBlock:  # Internal — carries exact_source_quote for verification
class PYQ:           id, subjectId, topicId, year, session, questionText, marks, difficulty, frequencyScore, questionType
class PYQExplanation: id, pyqId, lang, steps, hints, answer
```

**Verification model:**

```python
class ContentBlock(BaseModel):
    content: str
    exact_source_quote: str    # Must match source text
    is_verified: bool = False  # Set by verify stage
```

### 4.3 Stage Details

#### Stage 01: Scrape (`01_scrape/scrape_nios.py`)

Interactive CLI that scrapes NIOS chapter PDFs and uploads them directly to Google Drive.

```bash
cd pipeline/01_scrape
python scrape_nios.py
```

**How it works:**

1. **Select class** — prompts for Class 10 or Class 12
2. **Load subjects** — reads `subjects_10.json` or `subjects_12.json` (pre-scraped subject lists with NIOS page URLs)
3. **Select stream** — groups subjects into streams: Science, Commerce, Humanities, Languages, Vocational & Others
4. **Select subjects** — pick individual subjects or all in a stream
5. **Authenticate Google Drive** — uses OAuth via `credentials.json` → generates `token.json`
6. **Scrape each subject page** — for each selected subject:
   - Fetches the NIOS subject page (e.g. `nios.ac.in/.../Mathematics-(311).aspx`)
   - Finds all `.pdf` links on the page
   - Filters via `is_english_chapter()` — rejects Hindi-medium, TMAs, syllabi, lab manuals, full-book downloads, learner guides, etc.
   - Extracts chapter numbers from link text/URL (e.g. "Lesson 1", "L-2", "3 - Sets") → renames to `Chapter N.pdf`
7. **Upload to Drive** — creates folder structure: `NIOS Backup / Class 12 / Science / Mathematics (311) / Chapter N.pdf`
8. **Registry tracking** — `downloads_registry.json` tracks SUCCESS/ERROR per file, skips already-uploaded files on re-run
9. **Batch processing** — processes subjects in batches of 3, prompts before each batch

**Key filtering rules** (`is_english_chapter()`):

- Rejects non-English medium paths (`/hindi/`, `_hin/`, etc.)
- Rejects non-chapter material (TMA, assignment, syllabus, sample paper, practical, lab manual, FAQ, etc.)
- Rejects learner guides (`LG-1`, `LG-2`)
- Rejects full-book downloads (`book-1.pdf`, `book1.pdf`)
- Rejects Devanagari text for non-language subjects

**To regenerate subject lists:**

```bash
cd pipeline/01_scrape
python generate_subjects.py
```

This scrapes the NIOS course listing pages and writes `subjects_10.json` / `subjects_12.json`.

**After scraping:** Download the PDFs from Google Drive to `content/class12/<subject>/pdfs/` for local pipeline processing (stages 02+).

**Required files in `pipeline/01_scrape/`:**

- `credentials.json` — Google OAuth client credentials
- `token.json` — auto-generated after first auth
- `subjects_12.json` / `subjects_10.json` — subject URLs
- `downloads_registry.json` — upload tracking (reset when clearing Drive)

#### Stage 02: Extract (`02_extract/extract_pdf.py`)

Converts PDFs to structured Markdown using **Docling** on Google Colab (user's local machine lacks GPU power).

**Colab workflow:**

1. Copy `extract_pdf.py` cells to a Colab notebook
2. Mount Google Drive, configure paths
3. Run extraction — processes all PDFs, creates per-PDF markdown
4. Results saved to Google Drive, download to `pipeline/output/extracted/`

**Key features:**

- Checkpointing via `_extraction_checkpoint.json` (resumes mid-batch)
- Manifest file lists all extracted files with metadata
- Handles tables, equations, diagrams

#### Stage 03: Structure (`03_structure/structure_content.py`)

Sends extracted markdown to **DeepSeek V3** API to produce structured JSON matching the `schemas.py` models.

```bash
cd pipeline
python -m 03_structure.structure_content --subject maths-12 [--resume]
```

**Key features:**

- Text chunking with overlap for large chapters
- Retry logic via `tenacity` (exponential backoff)
- Per-chapter checkpointing
- Can process from extracted markdown or raw JSON files
- System prompt enforces: meaningful topic names (not "Part 1"), goal_tier assignment, mandatory `exact_source_quote`

**LLM prompt rules:**

- Each topic must have a descriptive name (e.g., "Quadratic Formula Derivation", not "Part 3")
- `high_yield_score` assigned based on PYQ frequency heuristics
- `est_minutes` assigned based on content complexity
- Every content bullet must carry `exact_source_quote` from the source text

#### Stage 04: Verify (`04_verify/verify_content.py`)

Anti-hallucination gate — checks every `exact_source_quote` against the source material.

```bash
cd pipeline
python -m 04_verify.verify_content --subject maths-12
```

**Three verification strategies:**

1. **Exact normalized match** — whitespace/case-normalized string comparison
2. **Sliding window overlap** — ≥85% token overlap in sliding windows
3. **Keyword density** — domain-specific keyword extraction and matching

**Outputs:**

- `VerifiedSubject` JSON with `is_verified` flags set
- `VerificationStats` with pass/fail counts and percentage

#### Stage 05: Solve PYQs (`05_solve/solve_pyqs.py`)

Extracts questions from PYQ papers and generates step-by-step solutions using **Claude 3.7 Sonnet**.

```bash
cd pipeline
python -m 05_solve.solve_pyqs --subject maths-12
```

**Two-step process:**

1. **Extract** — parse PYQ paper into individual questions with metadata (year, session, marks, type)
2. **Solve** — send each question to Claude for step-by-step explanation, hints, and model answer

**Key features:**

- Supports `.txt`, `.json`, `.pdf` input formats
- Per-question checkpointing
- `topic_id` left empty — mapped in post-processing by matching question text to topics

#### Stage 06: Seed Backend (`06_seed/seed_backend.py`)

Converts verified content + solved PYQs into TypeScript arrays for the backend worker.

```bash
cd pipeline
python -m 06_seed.seed_backend --subject maths-12
```

**Outputs:**

- `backend/src/data/generated.ts` — TypeScript with all data arrays
- `pipeline/output/seed_reference.json` — JSON copy for debugging

### 4.4 Configuration (`config.py`)

Central configuration file:

```python
# Paths
ROOT_DIR = Path(__file__).resolve().parent.parent   # nios-study-app/
PIPELINE_DIR = ROOT_DIR / "pipeline"
OUTPUT_DIR = PIPELINE_DIR / "output"
CONTENT_DIR = ROOT_DIR / "content"
BACKEND_DIR = ROOT_DIR / "backend"

# API keys loaded from .env
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY")

# Subject registry
SUBJECTS = {
    "maths-12": {
        "name": "Mathematics",
        "class_level": "12",
        "code": "311",
        "icon": "📐",
        "pdf_dir": CONTENT_DIR / "class12" / "maths-12" / "pdfs",
        "pyq_dir": CONTENT_DIR / "class12" / "maths-12" / "pyqs_raw",
    }
}
```

### 4.5 Running the Full Pipeline

```bash
# 1. Setup
cd pipeline
cp .env.example .env  # Add API keys
pip install -r requirements.txt

# 2. Scrape PDFs to Google Drive
cd 01_scrape && python scrape_nios.py   # Interactive: pick class → stream → subjects
cd ..

# 3. Download PDFs from Drive to content/class12/<subject>/pdfs/

# 4. Extract on Colab (copy extract_pdf.py cells to notebook)
#    Download results to pipeline/output/extracted/maths-12/

# 5. Structure content
python -m 03_structure.structure_content --subject maths-12

# 6. Verify (anti-hallucination)
python -m 04_verify.verify_content --subject maths-12

# 7. Solve PYQs
python -m 05_solve.solve_pyqs --subject maths-12

# 8. Seed backend
python -m 06_seed.seed_backend --subject maths-12

# 9. Deploy
cd ../backend && npx wrangler deploy
```

---

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
- **Python 3.10+** and **pip**
- **Google account** (for Colab PDF extraction)
- **API keys**: DeepSeek V3, Claude (Anthropic)

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
- [ ] Run full pipeline for maths-12 (pending API keys + Colab extraction)

### Phase 2: Content Quality

- [ ] Process all 38 maths-12 lesson PDFs through pipeline
- [ ] Solve all 6 PYQ papers (2019-2024)
- [ ] Map PYQ questions to topics
- [ ] Verify 85%+ content passes anti-hallucination check
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

| Decision                         | Rationale                                                                                                  |
| -------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| **Bundled data, no DB**          | Cloudflare Workers have instant cold start — no round-trip to D1. Content is static until pipeline re-runs |
| **Google Colab for extraction**  | User's machine lacks GPU for Docling. Colab provides free T4 GPU                                           |
| **DeepSeek V3 for structuring**  | Best cost/quality ratio for structured JSON generation. ~$0.14/M input tokens                              |
| **Claude for PYQ solving**       | Superior at step-by-step mathematical reasoning                                                            |
| **exact_source_quote**           | Forces the structuring LLM to ground every claim in source text. Verification stage catches fabrications   |
| **Numbered pipeline stages**     | Clear execution order, each stage independent with checkpointing — can resume mid-pipeline after failures  |
| **TypeScript arrays**            | Zero latency at query time — just array.filter(). No ORM overhead, no connection pooling                   |
| **Pydantic as schema authority** | Python pipeline produces the data, Pydantic enforces shape. TypeScript types mirror Pydantic models        |

---

_Last updated: March 2026_
