#!/usr/bin/env python3
"""
Stage 2a — Generate Chapter PDF URLs for a Subject

Scrapes the NIOS website for a given subject and saves the chapter PDF URLs
to a JSON config file. This config is then uploaded to Kaggle as a tiny
dataset so the Kaggle extraction notebook can download the PDFs directly
from NIOS — no local PDF storage or Google Drive needed.

Output:
    pipeline/02_extract/chapter_urls/<subject>.json

That JSON is then uploaded to Kaggle via:
    python 02_extract/upload_to_kaggle.py --subject maths-12 --username <you> --urls-only

Usage:
    cd pipeline
    python 02_extract/generate_chapter_urls.py --subject maths-12
    python 02_extract/generate_chapter_urls.py --subject maths-12 --list-only
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin, unquote

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import SUBJECTS

BASE_URL = "https://nios.ac.in"
URLS_DIR = Path(__file__).resolve().parent / "chapter_urls"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# Subject page URLs — the NIOS page that lists all chapter PDF links for a subject
SUBJECT_PAGES = {
    "maths-12": "https://nios.ac.in/online-course-material/sr-secondary-courses/Mathematics-(311).aspx",
    # Add more subjects here as needed:
    # "physics-12": "https://nios.ac.in/online-course-material/sr-secondary-courses/Physics-(312).aspx",
    # "chemistry-12": "https://nios.ac.in/online-course-material/sr-secondary-courses/Chemistry-(313).aspx",
}


# ── Scraping helpers (ported from 01_scrape/scrape_nios.py) ──────────────────

def fetch_page(url: str):
    for attempt in range(4):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=20)
            resp.raise_for_status()
            return BeautifulSoup(resp.content, "html.parser")
        except Exception as e:
            wait = 2 ** attempt
            print(f"  ⚠️  Fetch failed ({e}). Retrying in {wait}s...")
            time.sleep(wait)
    return None


def _is_english_chapter(text: str, href: str, subject_name: str) -> bool:
    text_lower = text.lower()
    href_lower = href.lower()
    subject_lower = subject_name.lower()

    language_subjects = [
        "hindi", "urdu", "bengali", "tamil", "odia", "punjabi", "sanskrit",
        "arabic", "sindhi", "persian", "bhoti", "malayalam", "kannada",
        "telugu", "marathi", "assamese", "gujarati",
    ]
    is_lang_subject = any(lang in subject_lower for lang in language_subjects)

    non_english_path_segments = [
        "/hindi/", "/urdu/", "/gujarati/", "/bengali/", "/tamil/", "/odia/",
        "/punjabi/", "/assamese/", "/marathi/", "/telugu/", "/malayalam/",
        "/kannada/", "_hindi/", "_urdu/", "_hin/", "hin_lesson", "_hindi_",
    ]
    if not is_lang_subject:
        for seg in non_english_path_segments:
            if seg in href_lower:
                return False

    exclusions = [
        "tma", "assignment", "syllabus", "sample paper", "question paper",
        "curriculum", "practical", "guidelines", "bifurcation", "worksheet",
        "ws-", "ws_", "learner guide", "first page", "inst.pdf", "(tma)",
        "contents", "content-", "index", "front page",
        "lab manual", "laboratory manual", "lab_manual", "lab-manual",
        "aicte", "circular", "equivalency", "government order", "govt. order",
        "frequently asked questions", "faq",
    ]
    if any(ex in text_lower or ex in href_lower for ex in exclusions):
        return False

    basename = os.path.basename(href_lower)
    if re.match(r"lg[-_]\d", basename) or re.match(r"lg[-_]\d", text_lower):
        return False
    if re.match(r"book[-_ ]?\d", basename) or re.search(r"\bbook[-_ ]?\d", text_lower):
        return False
    if "download book" in text_lower or "part1.zip" in href_lower or "whole" in text_lower:
        return False

    if not is_lang_subject:
        if re.search(r"[\u0900-\u097F]", text):
            return False
        if not re.search(r"[A-Za-z]", text):
            return False

    return True


def _extract_chapter_number(text: str, href: str):
    text_lower = text.lower()
    basename = os.path.basename(href).lower()

    for pattern in [
        r"\b(?:lesson|chapter|l)[-_ ]*(\d+)",
        r"\b(?:lesson|chapter|l)[-_ ]*(\d+)",
    ]:
        for src in [text_lower, basename]:
            m = re.search(pattern, src)
            if m:
                return int(m.group(1))

    m = re.match(r"^(\d+)[ \-:\.]", text_lower)
    if m:
        return int(m.group(1))
    m = re.match(r"^(\d+)$", text_lower.strip())
    if m:
        return int(m.group(1))

    return None


def get_chapter_pdfs(subject_url: str, subject_name: str) -> list[dict]:
    """Scrape the NIOS subject page and return a list of {name, url} dicts."""
    print(f"  🌐 Fetching {subject_url}")
    soup = fetch_page(subject_url)
    if not soup:
        print("  ❌ Failed to fetch subject page.")
        return []

    chapters = []
    seen_urls: set[str] = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = a.text.strip().replace("\n", " ").replace("\r", "")

        if not href.lower().endswith(".pdf"):
            continue
        if not _is_english_chapter(text, href, subject_name):
            continue

        link = urljoin(BASE_URL, href)
        if link in seen_urls:
            continue
        seen_urls.add(link)

        chapter_num = _extract_chapter_number(text, href)
        if chapter_num is not None:
            name = f"Chapter {chapter_num}.pdf"
        else:
            clean = "".join(x for x in text if x.isalnum() or x in " -_.").strip()
            if not clean or len(clean) < 3:
                clean = os.path.basename(unquote(href)).split("?")[0]
            if not clean.lower().endswith(".pdf"):
                clean += ".pdf"
            name = f"Extra - {clean}"

        if name not in [c["name"] for c in chapters]:
            chapters.append({"name": name, "url": link})

    return sorted(chapters, key=lambda c: (
        0 if c["name"].startswith("Chapter") else 1,
        int(re.search(r"\d+", c["name"]).group()) if re.search(r"\d+", c["name"]) else 999,
    ))


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Scrape NIOS chapter PDF URLs and save for Kaggle notebook"
    )
    parser.add_argument("--subject", required=True, help="Subject ID, e.g. maths-12")
    parser.add_argument(
        "--list-only", action="store_true",
        help="Print the URLs but do not save the JSON file",
    )
    args = parser.parse_args()

    if args.subject not in SUBJECTS:
        print(f"❌ Unknown subject '{args.subject}'. Known: {list(SUBJECTS.keys())}")
        sys.exit(1)

    if args.subject not in SUBJECT_PAGES:
        print(f"❌ No NIOS page configured for '{args.subject}'.")
        print(f"   Add it to SUBJECT_PAGES in this script.")
        sys.exit(1)

    subject_cfg = SUBJECTS[args.subject]
    subject_name = subject_cfg["name"]
    subject_url = SUBJECT_PAGES[args.subject]

    print(f"📐 Subject:  {subject_name} (Class {subject_cfg['class_level']})")
    print(f"🌐 Page:     {subject_url}\n")

    chapters = get_chapter_pdfs(subject_url, subject_name)

    if not chapters:
        print("❌ No chapter PDFs found. Check the subject URL and try again.")
        sys.exit(1)

    numbered = [c for c in chapters if c["name"].startswith("Chapter")]
    extras = [c for c in chapters if not c["name"].startswith("Chapter")]
    print(f"\n📚 Found {len(chapters)} chapter PDF(s):")
    for c in chapters:
        print(f"  📄 {c['name']}")
        print(f"      {c['url']}")

    if extras:
        print(f"\n  ↳ {len(extras)} 'Extra' file(s) (unnumbered chapters)")

    if args.list_only:
        return

    URLS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = URLS_DIR / f"{args.subject}.json"

    payload = {
        "subject": args.subject,
        "subject_name": subject_name,
        "class_level": subject_cfg["class_level"],
        "code": subject_cfg["code"],
        "source_url": subject_url,
        "chapters": chapters,
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Saved {len(chapters)} URLs → {out_path}")
    print(f"\n   Next steps:")
    print(f"   1. Upload this config to Kaggle:")
    print(f"      python 02_extract/upload_to_kaggle.py --subject {args.subject} --username <you> --urls-only")
    print(f"   2. Open the Kaggle notebook and run it.")
    print(f"   3. After the notebook finishes:")
    print(f"      python 02_extract/download_from_kaggle.py --subject {args.subject} --dataset <you>/nios-{args.subject}-extracted")


if __name__ == "__main__":
    main()
