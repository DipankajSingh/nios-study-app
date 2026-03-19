# NCERT Study App — Master Plan

> **Single source of truth** for architecture decisions, project structure, content pipeline, backend API, and development workflow.

---

## 1. Project Vision
Build a **Universal (Web + Mobile)** study companion for NCERT/CBSE students targeting Class 10 and Class 12 exams. The app generates **personalized daily study plans** from verified open-source NCERT datasets and provides on-demand **AI Tutoring**.

### Core Principles
| Principle              | Implementation                                                                    |
| ---------------------- | --------------------------------------------------------------------------------- |
| **Universal Codebase** | Write once in Expo (React Native), deploy to Web, iOS, and Android seamlessly.  |
| **Modern BaaS**        | Supabase handles PostgreSQL, User Auth, and APIs off-the-shelf.                 |
| **Cost-Optimized AI**  | Cloudflare Workers acts as a standalone microservice for cheap LLM calls only.    |
| **Offline-Capable**    | The dataset is built locally and seeded to the database.                          |

---

## 2. Architecture Overview

```text
┌─────────────────────────────────────────────────────────────┐
│                    CONTENT PIPELINE (Python)                 │
│                                                             │
│       HuggingFace Dataset → 01_build_ncert → Supabase Seed   │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                   BACKEND & AI (Supabase + Cloudflare)       │
│                                                             │
│  [Supabase] PostgreSQL DB (Curriculum + User Progress)       │
│  [Supabase] Built-in Auth & Auto-generating REST APIs        │
│                                                             │
│  [Cloudflare Worker] AI Microservice (/api/ai-tutor)         │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                 FRONTEND (Expo / React Native)               │
│                                                             │
│  Universal App (Runs on Web browser, iOS, Android)          │
│  Connects directly to Supabase SDKs & Cloudflare AI calls   │
└─────────────────────────────────────────────────────────────┘
```

## 3. Tech Stack
* **Frontend/Mobile**: Expo (React Native), Expo Router, NativeWind (TailwindCSS)
* **Backend Core**: Supabase (PostgreSQL, GoTrue Auth, PostgREST)
* **AI Microservice**: Cloudflare Workers AI (Llama 3 endpoint)
* **Data Pipeline**: Python (HuggingFace Datasets API)

## 4. Project Structure (Future State)
```
ncert-study-app/
├── MASTER_PLAN.md              ← This document
├── README.md                   
│
├── pipeline/                   ← Content generation (Python)
│   ├── config.py               ← Paths configuration
│   └── 01_build_ncert/         ← Maps HuggingFace NCERT JSON to Supabase Seed
│       └── build.py
│
├── content/                    ← Scraped JSON/Parquet caches
│   └── ncert_dataset.json
│
├── ai-worker/                  ← Cloudflare Worker AI microservice
│   ├── src/index.ts            ← Serverless endpoint for AI tutor
│   └── wrangler.toml           
│
└── app/                        ← Master Expo App (Web + Mobile)
    ├── package.json
    ├── app/                    ← Expo Router file-based routing
    ├── components/             ← Universal UI components
    └── lib/
        └── supabase.ts         ← Supabase client connection
```

## 5. Database Schema (Supabase Postgres)
A normalized relational model for complex querying.

**Curriculum (Read-Heavy)**
* `subjects`: id, name, class_level
* `chapters`: id, subject_id, title, order_index
* `topics`: id, chapter_id, title, est_minutes
* `topic_contents`: id, topic_id, summary_bullets, why_important
* `pyqs`: id, topic_id, question_text, answer_text, difficulty

**User State (Read/Write)**
* `users`: id (from Auth), exam_date, daily_study_minutes, target_score
* `user_progress`: user_id, topic_id, is_completed, last_revised_at

## 6. The Content Pipeline
The pipeline is a single deterministic Python script (`01_build_ncert/build.py`) that downloads unstructured/semi-structured NCERT Datasets from HuggingFace, maps the fields (Topic, Explanation, Question, Answer) to our unified domain models, and outputs a Seed JSON/SQL file for direct Supabase database insertion.

## 7. Next Migration Steps
1. Delete legacy `web/` and `backend/` folders.
2. Initialize an Expo app (`npx create-expo-app`) in the `app/` folder.
3. Set up a Supabase project and apply the schema SQL.
4. Update `build.py` to push the dataset directly to Supabase via its Python SDK.
5. Initialize the `ai-worker/` using Cloudflare C3.
