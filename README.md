# NCERT Study App (Universal Web + Mobile)

## Overview
This project is an NCERT/CBSE-focused last‑minute study assistant. It builds PYQ-based, goal‑driven learning paths from existing open-source NCERT datasets, and delivers them through a **Universal App (Web, iOS, Android)** backed by **Supabase** and **Cloudflare AI**.

## High-Level Architecture
- `app/`: Expo (React Native) universal frontend with file-based routing.
- `supabase/`: PostgreSQL database for Curriculum catalog and User progress tracking + Auth.
- `ai-worker/`: Cloudflare Worker microservice exposing an `/api/ai-tutor` endpoint (powered by Llama 3 edge models).
- `pipeline/`: Python scripts that parse HuggingFace NCERT datasets and seed them directly into Supabase.

## Tech Stack
* **Frontend/Mobile**: Expo, React Native, Expo Router, NativeWind.
* **Backend Core**: Supabase (PostgreSQL, REST APIs, Auth).
* **AI Microservice**: Cloudflare Workers AI.
* **Pipeline**: Python (HuggingFace Datasets).

## Quick Start (Pipeline)
The repository includes a Python script that builds the NCERT learning track directly from HuggingFace to your database.

```bash
cd pipeline
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python 01_build_ncert/build.py
```

See [MASTER_PLAN.md](MASTER_PLAN.md) for detailed architecture mapping and database schemas.
