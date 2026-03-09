# NIOS Last-Minute Study Assistant

## Overview

This project is a NIOS-focused last‑minute study assistant. It builds PYQ-based, goal‑driven learning paths from official NIOS PDFs plus past year question papers, and delivers them through a web app (and later a mobile app) backed by serverless APIs and Cloudflare AI.

## Initial Scope (MVP)

- Web app (React + TypeScript, Vite) in the `web` folder.
- Core domain models for:
  - Class levels, subjects, chapters, topics.
  - PYQs (past year questions) with tags (year, marks, difficulty, topic, frequency).
  - Topic content (notes, common mistakes, why-important) in multiple languages.
  - Learning paths and daily tasks for each user based on exam date, daily time, and goal.
- API client layer designed to talk to future serverless backend (e.g. Cloudflare Workers).

## High-Level Architecture

- `pipeline/`: Python content generation pipeline (6 stages: scrape → extract → structure → verify → solve → seed).
- `web/`: React + TypeScript single-page app, mobile-first design.
  - Onboarding flow for class, subjects, goal, exam date, daily time, preferred language.
  - Today's Plan screen showing tasks per subject.
  - Subject and topic views (notes + PYQs + explanations).
- `backend/`: Cloudflare Worker exposing JSON APIs:
  - `/api/subjects`, `/api/topics/:id/details`, `/api/plan/today`, etc.
  - All content bundled as static TypeScript arrays (no database yet).
- `content/`: Raw source material (NIOS PDFs, PYQ papers downloaded from Drive).

## Tech Stack (current)

- Frontend:
  - React 19 + TypeScript 5.9 (Vite 7).
  - CSS (to be refined, likely with a utility-first framework in future).
- Backend:
  - Cloudflare Workers (TypeScript).
  - Static JSON data bundled in worker (no database yet).
- Pipeline:
  - Python 3.13 with Pydantic v2 for data validation.
  - marker-pdf on Kaggle (T4 GPU, 30h/week) for PDF extraction.
  - Gemini 2.5 Flash-Lite (free tier) for content structuring.
  - Claude (planned) for PYQ solving.
- Infrastructure:
  - Google Drive for raw PDF storage (Stage 01 scraper output).
  - Kaggle datasets for chapter URL configs and marker JSON output.
  - Kaggle (30h/week free T4 GPU) for PDF processing.

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

The repository includes a **6-stage Python pipeline** in `pipeline/` that transforms raw NIOS PDFs into structured, verified study content. See [MASTER_PLAN.md](MASTER_PLAN.md) for full architecture details.

### Quick Start

```bash
cd pipeline
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # Add your API keys (GEMINI_API_KEY required for Stage 03)
```

### Pipeline Stages

| Stage            | What it does                              | Command                                                                                                    |
| ---------------- | ----------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| **01 Scrape**    | Download NIOS PDFs → Google Drive         | `cd pipeline/01_scrape && python scrape_nios.py`                                                           |
| **02a URLs**     | Scrape chapter URLs from NIOS             | `python 02_extract/generate_chapter_urls.py --subject maths-12`                                            |
| **02b Upload**   | Upload URL config to Kaggle               | `python 02_extract/upload_to_kaggle.py --subject maths-12 --username <you>`                                |
| **02c Extract**  | PDF → JSON on Kaggle (marker-pdf, T4 GPU) | Open `extract_pdf_kaggle.ipynb` on Kaggle — add URL dataset as input, enable GPU + Internet, run all cells |
| **02d Download** | Pull extracted JSON from Kaggle           | `python 02_extract/download_from_kaggle.py --subject maths-12 --dataset <you>/nios-maths-12-extracted`     |
| **03 Structure** | JSON → structured JSON (Gemini)           | `python 03_structure/structure_content.py --subject maths-12`                                              |
| **04 Verify**    | Anti-hallucination check                  | `python 04_verify/verify_content.py --subject maths-12`                                                    |
| **05 Solve**     | PYQ extraction + solutions (Claude)       | `python 05_solve/solve_pyqs.py --subject maths-12`                                                         |
| **06 Seed**      | JSON → TypeScript for backend             | `python 06_seed/seed_backend.py --subject maths-12`                                                        |

### Stage 03 Options

```bash
# Preview what will be processed (no API calls)
python 03_structure/structure_content.py --subject maths-12 --dry-run

# Test with just 5 chunks (conserve free quota)
python 03_structure/structure_content.py --subject maths-12 --limit 5

# Resume from checkpoint after interruption
python 03_structure/structure_content.py --subject maths-12 --resume

# Use the thinking model (slower but higher quality)
python 03_structure/structure_content.py --subject maths-12 --provider gemini-flash
```

### Current Progress (maths-12)

- [x] 19 chapters scraped and uploaded to Google Drive
- [x] Chapter URLs scraped and saved (`chapter_urls/maths-12.json`)
- [ ] Extract chapters via Kaggle notebook (marker-pdf JSON output)
- [ ] Download extracted JSONs to `pipeline/output/extracted/maths-12/`
- [x] Stage 03 code production-ready (Gemini 2.5 Flash-Lite, smart 429 handling)
- [ ] Stage 03 full run
- [ ] Stages 04–06

> **Branch note:** Kaggle+marker extraction is on the `kaggle-marker` branch.
> Fallback to Colab+Docling: `git checkout master`

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
