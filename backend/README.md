# NIOS Study Backend (Cloudflare Workers Skeleton)

## Overview

This folder contains a minimal Cloudflare Workers backend skeleton for the NIOS last‑minute study assistant. It is designed to be cheap to run (serverless, pay‑as‑you‑go) and easy to consume from both the web app and a future mobile app.

The first endpoint implemented is a mock `/api/plan/today` route that mirrors the in‑app mock plan generator and returns a simple JSON daily plan based on query parameters.

**Data sources:**

- `src/mockData.ts` contains hand‑curated sample subjects, chapters, topics, and notes. It acts as a fallback dataset so the API works even before you run the content‑generation pipeline.
- `src/generatedData.ts` is produced by `scripts/seed.ts` and holds the real content coming from the AI. The worker automatically uses generated data if it contains any topics; otherwise it continues serving the mock file.

Unused sample files such as `mathData.ts` and backups have been removed to avoid confusion.

## Planned Responsibilities

- Expose JSON APIs for:
  - User profile and onboarding settings.
  - Subjects, chapters, topics, and PYQs.
  - Learning‑path generation and daily plans.
  - Practice attempts and progress tracking.
  - AI‑assisted explanations and doubt resolution (via Cloudflare AI).
- Store data in a relational database (Cloudflare D1 / Postgres) and object storage for NIOS PDFs and preprocessed content.

## Development (once Wrangler is installed)

1. Install Wrangler globally if you haven't:

   ```bash
   npm install -g wrangler
   ```

2. From this `backend` directory, run the dev server:

   ```bash
   wrangler dev
   ```

3. Test the mock endpoint in your browser or via curl:

   ```bash
   curl "http://127.0.0.1:8787/api/plan/today?subjects=Maths,English&dailyMinutes=60&goal=pass"
   ```

   You should see a JSON response with a few mock tasks.
