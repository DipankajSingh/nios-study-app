#!/usr/bin/env python3
"""
Stage 3 — Structure Content

Takes the extracted Markdown (from Stage 2 / Colab) and calls an LLM API
(DeepSeek V3 by default) to produce structured JSON matching our Pydantic schemas.

Usage:
    cd pipeline
    python -m 03_structure.structure_content --subject maths-12 [--resume]

What it does for each chapter:
  1. Reads the extracted markdown file
  2. Splits into chunks (~3000 chars with overlap)
  3. Sends each chunk to the LLM with a strict structuring prompt
  4. Collects structured topics + content blocks
  5. Writes a StructuredSubject JSON to output/structured/<subject>.json

Checkpointing: after each chapter is processed, progress is saved.
Use --resume to continue from where you left off.
"""

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

# Add parent to path so we can import config and schemas
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import (
    DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL,
    EXTRACTED_DIR, STRUCTURED_DIR, SUBJECTS,
    CHUNK_SIZE, CHUNK_OVERLAP, RATE_LIMIT_PAUSE, MAX_RETRIES,
    ensure_dirs,
)
from schemas import (
    Subject, Chapter, Topic, TopicContent, ContentBlock,
    StructuredChapter, StructuredSubject,
    GoalTier, Lang, ContentBlockType,
)

# Reuse a single httpx client for connection pooling across all API calls
_http_client: httpx.Client | None = None

def _get_client() -> httpx.Client:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.Client(timeout=120)
    return _http_client


# ── Prompts ──────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are an expert educational data extractor specializing in NIOS (National Institute of Open Schooling) study material.

Your task: Read the provided chunk of NIOS study material (in Markdown) and extract structured educational content.

OUTPUT FORMAT: Respond with a JSON object containing:
{
  "chapter_title": "Human-readable chapter title (e.g. 'Sets', 'Trigonometry', NOT the filename)",
  "topics": [
    {
      "title": "Specific topic name (e.g. 'Representation of Sets', NOT 'Part 1')",
      "goal_tier": "CORE | STANDARD | ADVANCED",
      "est_minutes": <integer 5-30>,
      "summary_bullets": ["bullet 1", "bullet 2", ...],
      "why_important": "One paragraph on exam relevance",
      "common_mistakes": ["mistake 1", "mistake 2", ...],
      "content_blocks": [
        {
          "type": "CONCEPT | FORMULA | DIAGRAM | CODE_SNIPPET | COMMON_MISTAKE",
          "content_text": "The actual content in Markdown. Use LaTeX ($...$) for math.",
          "exact_source_quote": "MANDATORY: Copy-paste the EXACT verbatim sentence(s) from the source text that this content is based on. This is used for verification."
        }
      ]
    }
  ]
}

CRITICAL RULES:
1. TOPIC NAMES must be meaningful and specific (e.g. "Subset and Superset", NOT "Part 5")
2. GOAL_TIER assignment:
   - CORE: Basic definitions, direct formulas, frequently asked in exams
   - STANDARD: Application problems, proofs that appear regularly
   - ADVANCED: Complex multi-step problems, rarely asked topics
3. EVERY content_block MUST have an exact_source_quote copied VERBATIM from the input.
   If you cannot find a verbatim quote, do NOT create that block.
4. Use LaTeX delimiters for all math: inline $x^2$ and display $$\\sum_{i=1}^{n}$$
5. Do NOT invent facts. Only extract what is present in the source text.
6. If the chunk contains exercises/questions, note them but focus on teaching content.
7. Merge related ideas into coherent topics rather than creating one topic per paragraph.
"""

USER_PROMPT_TEMPLATE = """\
Subject: {subject_name} (Code: {subject_code}, Class {class_level})
Chapter PDF: {pdf_name}
Chunk {chunk_index} of {total_chunks}:

---
{chunk_text}
---

Extract structured educational content from this chunk. Follow the JSON format exactly.
"""


# ── Text chunking ────────────────────────────────────────────────────────────

def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks at paragraph boundaries."""
    if len(text) <= size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + size

        # Try to break at a paragraph boundary
        if end < len(text):
            # Look for double newline near the end
            break_point = text.rfind("\n\n", start + size // 2, end + overlap)
            if break_point != -1:
                end = break_point + 2
            else:
                # Fall back to single newline
                break_point = text.rfind("\n", start + size // 2, end + overlap)
                if break_point != -1:
                    end = break_point + 1

        chunks.append(text[start:end].strip())
        start = end - overlap if end < len(text) else len(text)

    return [c for c in chunks if len(c) > 50]  # Skip tiny fragments


# ── LLM API call ─────────────────────────────────────────────────────────────

@retry(stop=stop_after_attempt(MAX_RETRIES), wait=wait_exponential(min=2, max=30))
def call_structuring_api(chunk: str, subject: dict, pdf_name: str,
                          chunk_idx: int, total_chunks: int) -> dict:
    """Send a chunk to DeepSeek V3 and parse the JSON response."""
    user_msg = USER_PROMPT_TEMPLATE.format(
        subject_name=subject["name"],
        subject_code=subject["code"],
        class_level=subject["class_level"],
        pdf_name=pdf_name,
        chunk_index=chunk_idx,
        total_chunks=total_chunks,
        chunk_text=chunk,
    )

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        "temperature": 0.1,  # Low temp for factual extraction
        "max_tokens": 4096,
        "response_format": {"type": "json_object"},
    }

    client = _get_client()
    resp = client.post(f"{DEEPSEEK_BASE_URL}/chat/completions",
                       headers=headers, json=payload)
    resp.raise_for_status()

    content = resp.json()["choices"][0]["message"]["content"]

    # Parse JSON from response (handle markdown fences)
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\n?", "", content)
        content = re.sub(r"\n?```$", "", content)

    return json.loads(content)


# ── Processing pipeline ──────────────────────────────────────────────────────

def process_chapter(
    md_file: Path,
    subject_cfg: dict,
    subject_id: str,
    chapter_index: int,
) -> StructuredChapter | None:
    """Process one chapter markdown file → StructuredChapter."""
    md_text = md_file.read_text(encoding="utf-8")
    if len(md_text) < 100:
        print(f"    ⏭️  Skipping {md_file.name} (too short: {len(md_text)} chars)")
        return None

    pdf_name = md_file.stem  # e.g. "01_311_Maths_Eng_Lesson1"
    chunks = chunk_text(md_text)
    print(f"    📄 {md_file.name}: {len(md_text)} chars → {len(chunks)} chunks")

    all_topics_raw: list[dict] = []
    chapter_title = pdf_name  # Will be overridden by LLM

    for i, chunk in enumerate(chunks, 1):
        print(f"      Chunk {i}/{len(chunks)}...", end=" ", flush=True)
        try:
            result = call_structuring_api(chunk, subject_cfg, pdf_name, i, len(chunks))
            if "chapter_title" in result and result["chapter_title"]:
                chapter_title = result["chapter_title"]
            all_topics_raw.extend(result.get("topics", []))
            print("✅")
        except Exception as e:
            print(f"❌ {e}")
            continue

        time.sleep(RATE_LIMIT_PAUSE)

    if not all_topics_raw:
        print(f"    ⚠️  No topics extracted from {md_file.name}")
        return None

    # ── Build typed models ──
    chapter_id = f"{subject_id}-ch{chapter_index:02d}"
    chapter = Chapter(
        id=chapter_id,
        subject_id=subject_id,
        title=chapter_title,
        order_index=chapter_index,
    )

    topics: list[Topic] = []
    topic_contents: list[TopicContent] = []
    content_blocks: list[ContentBlock] = []

    for t_idx, raw_topic in enumerate(all_topics_raw, 1):
        topic_id = f"{chapter_id}-t{t_idx:02d}"
        topic = Topic(
            id=topic_id,
            chapter_id=chapter_id,
            title=raw_topic.get("title", f"Topic {t_idx}"),
            order_index=t_idx,
            goal_tier=GoalTier(raw_topic.get("goal_tier", "STANDARD")),
            high_yield_score=_tier_to_score(raw_topic.get("goal_tier", "STANDARD")),
            est_minutes=raw_topic.get("est_minutes", 15),
        )
        topics.append(topic)

        # TopicContent
        tc = TopicContent(
            id=f"tc-{topic_id}-en",
            topic_id=topic_id,
            lang=Lang.EN,
            summary_bullets=raw_topic.get("summary_bullets", []),
            why_important=raw_topic.get("why_important", ""),
            common_mistakes=raw_topic.get("common_mistakes", []),
        )
        topic_contents.append(tc)

        # ContentBlocks
        for b_idx, raw_block in enumerate(raw_topic.get("content_blocks", []), 1):
            block = ContentBlock(
                id=f"cb-{topic_id}-{b_idx:02d}",
                topic_id=topic_id,
                type=ContentBlockType(raw_block.get("type", "CONCEPT")),
                content_text=raw_block.get("content_text"),
                source_pdf_name=pdf_name,
                exact_source_quote=raw_block.get("exact_source_quote"),
                is_verified=False,
            )
            content_blocks.append(block)

    return StructuredChapter(
        chapter=chapter,
        topics=topics,
        topic_contents=topic_contents,
        content_blocks=content_blocks,
    )


def _tier_to_score(tier: str) -> int:
    """Map goal tier to a default high-yield score."""
    return {"CORE": 85, "STANDARD": 65, "ADVANCED": 40}.get(tier, 65)


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Stage 3: Structure extracted content via LLM")
    parser.add_argument("--subject", required=True, help="Subject ID, e.g. maths-12")
    parser.add_argument("--resume", action="store_true", help="Resume from checkpoint")
    parser.add_argument("--extracted-dir", type=str, default=None,
                        help="Override extracted markdown directory")
    args = parser.parse_args()

    ensure_dirs()

    if args.subject not in SUBJECTS:
        print(f"❌ Unknown subject '{args.subject}'. Known: {list(SUBJECTS.keys())}")
        sys.exit(1)

    if not DEEPSEEK_API_KEY:
        print("❌ DEEPSEEK_API_KEY not set. Copy .env.example → .env and add your key.")
        sys.exit(1)

    subject_cfg = SUBJECTS[args.subject]
    subject = Subject(
        id=args.subject,
        name=subject_cfg["name"],
        class_level=subject_cfg["class_level"],
        code=subject_cfg["code"],
        icon=subject_cfg.get("icon", "📘"),
    )

    # Find extracted markdowns
    extracted_dir = Path(args.extracted_dir) if args.extracted_dir else EXTRACTED_DIR / args.subject
    if not extracted_dir.exists():
        # Also try the raw content JSON approach (existing maths-12.raw.json)
        raw_json = Path(__file__).resolve().parent.parent.parent / "content" / f"class{subject_cfg['class_level']}" / f"{args.subject}.raw.json"
        if raw_json.exists():
            print(f"📋 Found existing raw JSON: {raw_json}")
            print(f"   This file already has extracted text. Processing directly...")
            _process_from_raw_json(raw_json, subject, subject_cfg, args)
            return
        print(f"❌ No extracted data found at {extracted_dir}")
        print(f"   Run Stage 2 (Colab extraction) first, then place output in {extracted_dir}")
        sys.exit(1)

    # Find markdown files
    md_files = sorted(extracted_dir.rglob("*.md"))
    if not md_files:
        print(f"❌ No .md files in {extracted_dir}")
        sys.exit(1)

    print(f"📚 Subject: {subject.name} ({args.subject})")
    print(f"📁 Source: {extracted_dir}")
    print(f"📄 Found {len(md_files)} markdown files\n")

    # Checkpoint
    output_file = STRUCTURED_DIR / f"{args.subject}.json"
    checkpoint_file = STRUCTURED_DIR / f"{args.subject}.checkpoint.json"
    done_chapters: dict = {}
    if args.resume and checkpoint_file.exists():
        done_chapters = json.loads(checkpoint_file.read_text())
        print(f"♻️  Resuming: {len(done_chapters)} chapters already done\n")

    structured_chapters: list[StructuredChapter] = []

    # Load already-done chapters from checkpoint
    for ch_id, ch_data in done_chapters.items():
        structured_chapters.append(StructuredChapter.model_validate(ch_data))

    for idx, md_file in enumerate(md_files, 1):
        ch_key = md_file.stem
        if ch_key in done_chapters:
            print(f"  ⏭️  [{idx}/{len(md_files)}] Skipping {md_file.name} (done)")
            continue

        print(f"\n  📖 [{idx}/{len(md_files)}] Processing: {md_file.name}")
        chapter = process_chapter(md_file, subject_cfg, args.subject, idx)

        if chapter:
            structured_chapters.append(chapter)
            done_chapters[ch_key] = chapter.model_dump()
            checkpoint_file.write_text(json.dumps(done_chapters, indent=2, default=str))
            print(f"    💾 Checkpoint saved ({len(done_chapters)} chapters)")

    # Write final output
    result = StructuredSubject(
        subject=subject,
        structured_at=datetime.now(timezone.utc).isoformat(),
        chapters=structured_chapters,
    )
    output_file.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    print(f"\n🎉 Done! Output: {output_file}")
    print(f"   Chapters: {len(structured_chapters)}")
    total_topics = sum(len(ch.topics) for ch in structured_chapters)
    total_blocks = sum(len(ch.content_blocks) for ch in structured_chapters)
    print(f"   Topics: {total_topics}, Content blocks: {total_blocks}")


def _process_from_raw_json(raw_json: Path, subject: Subject, subject_cfg: dict, args):
    """Alternative path: process from existing raw JSON (content/class12/maths-12.raw.json)."""
    data = json.loads(raw_json.read_text())
    chapters_raw = data.get("chapters", [])

    output_file = STRUCTURED_DIR / f"{args.subject}.json"
    checkpoint_file = STRUCTURED_DIR / f"{args.subject}.checkpoint.json"
    done_chapters: dict = {}
    if args.resume and checkpoint_file.exists():
        done_chapters = json.loads(checkpoint_file.read_text())

    structured_chapters: list[StructuredChapter] = []
    for ch_id, ch_data in done_chapters.items():
        structured_chapters.append(StructuredChapter.model_validate(ch_data))

    for ch_raw in chapters_raw:
        ch_key = ch_raw["id"]
        if ch_key in done_chapters:
            continue

        # Concatenate all topic rawText into one big markdown
        all_text = "\n\n".join(t.get("rawText", "") for t in ch_raw.get("topics", []))
        if len(all_text) < 100:
            continue

        # Write temp markdown
        tmp_md = STRUCTURED_DIR / f"_tmp_{ch_key}.md"
        tmp_md.write_text(all_text, encoding="utf-8")

        print(f"\n  📖 Processing: {ch_raw.get('title', ch_key)}")
        chapter = process_chapter(tmp_md, subject_cfg, args.subject, ch_raw["orderIndex"])

        if chapter:
            structured_chapters.append(chapter)
            done_chapters[ch_key] = chapter.model_dump()
            checkpoint_file.write_text(json.dumps(done_chapters, indent=2, default=str))

        tmp_md.unlink(missing_ok=True)

    result = StructuredSubject(
        subject=subject,
        structured_at=datetime.now(timezone.utc).isoformat(),
        chapters=structured_chapters,
    )
    output_file.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    print(f"\n🎉 Done! Output: {output_file}")


if __name__ == "__main__":
    main()
