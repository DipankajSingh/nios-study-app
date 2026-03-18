# NCERT Last-Minute Study Assistant

## Overview

This project is an NCERT/CBSE-focused last‑minute study assistant. It builds PYQ-based, goal‑driven learning paths from existing open-source NCERT datasets, and delivers them through a web app (and later a mobile app) backed by serverless APIs (Cloudflare Workers).

## Initial Scope (MVP)

- Web app (React + TypeScript, Vite) in the `web` folder.
- Core domain models for:
  - Class levels, subjects, chapters, topics.
  - PYQs (past year questions) with tags (year, marks, difficulty, topic, frequency).
  - Topic content (notes, common mistakes, why-important) in multiple languages.
  - Learning paths and daily tasks for each user based on exam date, daily time, and goal.
- API client layer designed to talk to future serverless backend (e.g. Cloudflare Workers).

## High-Level Architecture

- `pipeline/`: Python pure scripting pipeline that pulls from HuggingFace NCERT datasets and builds static TypeScript arrays.
- `web/`: React + TypeScript single-page app, mobile-first design.
  - Onboarding flow for class, subjects, goal, exam date, daily time, preferred language.
  - Today's Plan screen showing tasks per subject.
  - Subject and topic views (notes + PYQs + explanations).
- `backend/`: Cloudflare Worker exposing JSON APIs:
  - `/api/subjects`, `/api/topics/:id/details`, `/api/plan/today`, etc.
  - All content bundled as static TypeScript arrays (no database yet).
- `content/`: Raw downloaded NCERT dataset JSONs/CSVs.

## Tech Stack (current)

- Frontend:
  - React 19 + TypeScript 5.9 (Vite 7).
  - CSS (Vanilla, to be refined).
- Backend:
  - Cloudflare Workers (TypeScript).
  - Static JSON data bundled in worker (no database yet).
- Pipeline:
  - Python 3.13 for pure text parsing and dataset mapping.
  - Maps HuggingFace NCERT JSON straight to TypeScript.
- Infrastructure:
  - 100% Free architecture (No GPU or LLM APIs required).

## Running the Web App

From the `web` directory:

1. Install dependencies:

   ```bash
   npm install
   ```

2. Start the dev server:

   ```bash
   npm run dev
   ```

3. Open the local URL printed in the terminal (usually `http://localhost:5173`).

## Content Generation Pipeline

The repository includes a **Python pipeline** in `pipeline/` that transforms raw HuggingFace NCERT datasets into structured study content. See [MASTER_PLAN.md](MASTER_PLAN.md) for full architecture details.

### Quick Start

```bash
cd pipeline
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### Pipeline Stage

| Stage            | What it does                                         | Command                                                                                                              |
| ---------------- | ---------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| **01 Build NCERT** | Download HuggingFace dataset format & map to TS Arrays | `python 01_build_ncert/build.py` |

## Running the App

**Backend** (Cloudflare Worker):

```bash
cd backend && npm install && npm run dev   # worker on localhost:8787
```

**Frontend** (React + Vite):

```bash
cd web && npm install && npm run dev       # frontend on localhost:5173
```

## Next Steps

- [ ] Complete Stage 03 full run for maths-12 (Gemini free tier, ~63 min)
- [ ] Run verification (Stage 04) and seed backend (Stage 06)
- [ ] Process PYQ papers through Stage 05
- [ ] Add more subjects (English, Science, Social Studies)
- [ ] Frontend component split and routing
- [ ] PWA support for offline access
