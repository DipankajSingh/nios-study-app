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

- `web/`: React + TypeScript single-page app, mobile-first design.
  - Onboarding flow for class, subjects, goal, exam date, daily time, preferred language.
  - Today’s Plan screen showing tasks per subject.
  - Subject and topic views (notes + PYQs + explanations).
- `backend/` (planned): Serverless functions (Cloudflare Workers or similar) exposing JSON APIs:
  - `/api/subjects`, `/api/topics`, `/api/plan/today`, `/api/practice/attempt`, `/api/ai/explain`, etc.
  - Backed by a relational database (D1 / Postgres) and object storage for PDFs.

## Tech Stack (current)

- Frontend:
  - React + TypeScript (Vite).
  - CSS (to be refined, likely with a utility-first framework in future).
- Backend (planned):
  - Cloudflare Workers (TypeScript).
  - Cloudflare D1 / Postgres for structured data.
  - Cloudflare R2 / other free storage for NIOS PDFs and preprocessed JSON.
  - Cloudflare AI for summarisation, explanations, and doubt assistance (always constrained by NIOS content).

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

## Backend generation pipeline

The repository includes a simple content-generation pipeline in `scripts/`:

1. Copy `scripts/.env.example` to `scripts/.env` and fill in your API key(s):

   ```bash
   cp scripts/.env.example scripts/.env
   # edit the file to set GROQ_API_KEY=...
   ```

2. Generate topic notes (uses Groq by default; runs in "resume" mode):

   ```bash
   cd scripts
   npx ts-node generateContent.ts --subject maths-12 --resume
   # optionally specify provider if more are supported:
   npx ts-node generateContent.ts --subject maths-12 --resume --provider groq
   ```

   If you hit the free-tier rate limit, either add payment or repeat the command
   after the limit resets. The script checkpoints progress automatically.

3. Seed the backend data from generated JSON:

   ```bash
   npx ts-node seed.ts --subject maths-12 --dry-run    # preview only
   npx ts-node seed.ts --subject maths-12             # write to backend/src/generatedData.ts
   ```

4. Start the backend (Cloudflare Worker) and the web app:
   ```bash
   cd backend && npm install && npm run dev   # worker on localhost:8787
   cd ../web && npm install && npm run dev     # frontend on localhost:5173
   ```

The `content/` directory already contains generated files so you can skip steps
1–3 initially if you just want to run the app.

## Next Steps

- Implement the onboarding flow in the web app (class, subjects, goal, exam date, daily time, language).
- Define TypeScript models for subjects, topics, PYQs, topic content, learning paths, and tasks.
- Add a simple in-memory/mock API layer in the web app to simulate serverless responses.
- Create a minimal Cloudflare Worker project for real APIs once the data contracts stabilise.
