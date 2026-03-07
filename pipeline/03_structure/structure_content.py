#!/usr/bin/env python3
"""
Stage 3 — Structure Content

Takes the extracted Markdown (from Stage 2 / Colab) and calls an LLM API
to produce structured JSON matching our Pydantic schemas.

Supported providers: gemini (default, flash-lite), gemini-flash, deepseek

Usage:
    cd pipeline
    python 03_structure/structure_content.py --subject maths-12
    python 03_structure/structure_content.py --subject maths-12 --provider deepseek
    python 03_structure/structure_content.py --subject maths-12 --provider gemini-flash
    python 03_structure/structure_content.py --subject maths-12 --dry-run
    python 03_structure/structure_content.py --subject maths-12 --resume
    python 03_structure/structure_content.py --subject maths-12 --limit 5  # test first 5 chunks

What it does for each chapter:
  1. Reads the extracted markdown file
  2. Splits into chunks (~3000 chars with overlap)
  3. Sends each chunk to the LLM with a strict structuring prompt
  4. Collects structured topics + content blocks
  5. Writes a StructuredSubject JSON to output/structured/<subject>.json

Rate limiting:
  - Gemini flash-lite free tier: 30 RPM → 4s pause between requests
  - Gemini flash (thinking) free tier: 10 RPM → 6s pause
  - DeepSeek: generous limits → 2s pause
  - On 429 errors: progressive backoff (30s, 60s, 90s...)

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
from tenacity import (
    retry, stop_after_attempt, wait_exponential,
    retry_if_exception_type, before_sleep_log,
)
import logging

logging.basicConfig(level=logging.WARNING)
_logger = logging.getLogger(__name__)

# Add parent to path so we can import config and schemas
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import (
    DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL,
    GEMINI_API_KEY, GEMINI_BASE_URL, GEMINI_MODEL,
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


# ── Provider configuration ───────────────────────────────────────────────────
# Each provider returns (base_url, api_key, model_name) for OpenAI-compatible calls.

PROVIDERS = {
    "deepseek": {
        "base_url": DEEPSEEK_BASE_URL,
        "api_key": DEEPSEEK_API_KEY,
        "model": DEEPSEEK_MODEL,
        "label": "DeepSeek V3",
        "pause": RATE_LIMIT_PAUSE,  # 2s — generous limits
        "max_retries": MAX_RETRIES,
    },
    "gemini": {
        "base_url": GEMINI_BASE_URL,
        "api_key": GEMINI_API_KEY,
        "model": GEMINI_MODEL,   # gemini-2.5-flash-lite — fast, no thinking overhead
        "label": "Gemini Flash-Lite",
        "pause": 4.0,   # Free tier: 30 RPM → 2s safe, but 4s conservative
        "max_retries": 5,  # More retries for rate-limit recovery
    },
    "gemini-flash": {
        "base_url": GEMINI_BASE_URL,
        "api_key": GEMINI_API_KEY,
        "model": "gemini-2.5-flash",   # Thinking model — higher quality, 2x slower
        "label": "Gemini 2.5 Flash (thinking)",
        "pause": 6.0,   # Free tier: 10 RPM → 6s/req
        "max_retries": 5,
    },
}

# Active provider — set by main() based on --provider flag
_active_provider: dict = PROVIDERS["deepseek"]
_chunk_limit: int = 0  # 0 = no limit; set by --limit flag
_chunks_processed: int = 0  # tracks total chunks processed

def set_provider(name: str):
    global _active_provider
    if name not in PROVIDERS:
        raise ValueError(f"Unknown provider '{name}'. Choose from: {list(PROVIDERS.keys())}")
    _active_provider = PROVIDERS[name]


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
8. BE CONCISE: Keep summary_bullets to 2-4 items max. Keep why_important to 1-2 sentences.
   Keep exact_source_quote to ONE KEY sentence (not a whole paragraph).
   Aim for 2-4 content_blocks per topic, not more.
   The entire response must fit in ~4000 tokens.
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


def _repair_truncated_json(text: str) -> dict | None:
    """Attempt to repair a truncated JSON response by closing open structures.

    When finish_reason='length', the JSON is valid up to truncation point.
    We try progressively aggressive repair strategies.
    """
    # Common closing suffixes to try (from least to most aggressive)
    close_suffixes = [
        ']}',           # close topics array + root object
        '"]}',          # close truncated string + topics array + root
        '"}]}',         # close string + content_blocks array + topic + topics array + root
        '"}]}]}',       # close string + nested arrays
        '"]}]}]}',      # deeply nested close
    ]

    # Strategy 1: Walk backwards to find a valid truncation point
    for end_pos in range(len(text) - 1, max(0, len(text) - 2000), -1):
        candidate = text[:end_pos + 1]
        for suffix in close_suffixes:
            try:
                result = json.loads(candidate + suffix)
                if isinstance(result, dict) and "topics" in result:
                    return result
            except json.JSONDecodeError:
                continue

    # Strategy 2: Find last complete JSON object boundary
    last_brace = text.rfind("},")
    if last_brace > 0:
        candidate = text[:last_brace + 1]
        for suffix in close_suffixes:
            try:
                result = json.loads(candidate + suffix)
                if isinstance(result, dict):
                    return result
            except json.JSONDecodeError:
                continue

    return None


# ── JSON backslash fix ────────────────────────────────────────────────────────

_VALID_JSON_ESCAPES = frozenset('"\\/bfnrtu')

def _fix_json_backslashes(raw: str) -> str:
    r"""Fix invalid JSON backslash escapes while preserving valid ones.

    LLMs often produce LaTeX in JSON strings like \\left, \\{, \\text, etc.
    which are invalid JSON escapes. This function correctly handles:
      - \\left  (two chars \\ then left) -> kept as-is (valid JSON: literal backslash)
      - \left   (one char \ then left) -> doubled to \\left (now valid JSON)
      - \\\left (three chars) -> \\\\left (two valid pairs)

    The key insight: valid JSON escape sequences consume TWO characters (\\ pair).
    We walk the string, consuming pairs for valid escapes and doubling lone \.
    """
    out = []
    i = 0
    length = len(raw)
    while i < length:
        ch = raw[i]
        if ch == '\\' and i + 1 < length:
            next_ch = raw[i + 1]
            if next_ch in _VALID_JSON_ESCAPES:
                # Valid JSON escape — consume both characters
                out.append(ch)
                out.append(next_ch)
                i += 2
            else:
                # Invalid escape (e.g. \l from \left, \{ from LaTeX)
                # Double the backslash to make it a literal \ in JSON
                out.append('\\')
                out.append('\\')
                i += 1  # Only advance past the backslash
        else:
            out.append(ch)
            i += 1
    return ''.join(out)


# ── LLM API call ─────────────────────────────────────────────────────────────

def call_structuring_api(chunk: str, subject: dict, pdf_name: str,
                          chunk_idx: int, total_chunks: int) -> dict:
    """Send a chunk to the active LLM provider and parse the JSON response.

    Handles rate limits (429) with progressive backoff: 30s → 60s → 120s.
    Other HTTP errors and JSON parse errors use standard exponential backoff.
    """
    user_msg = USER_PROMPT_TEMPLATE.format(
        subject_name=subject["name"],
        subject_code=subject["code"],
        class_level=subject["class_level"],
        pdf_name=pdf_name,
        chunk_index=chunk_idx,
        total_chunks=total_chunks,
        chunk_text=chunk,
    )

    prov = _active_provider
    max_retries = prov.get("max_retries", MAX_RETRIES)
    headers = {
        "Authorization": f"Bearer {prov['api_key']}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": prov["model"],
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        "temperature": 0.1,  # Low temp for factual extraction
        "max_tokens": 16384,
        "response_format": {"type": "json_object"},
    }

    client = _get_client()
    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            resp = client.post(f"{prov['base_url']}/chat/completions",
                               headers=headers, json=payload)

            # Handle rate limits specially
            if resp.status_code == 429:
                retry_after = int(resp.headers.get("retry-after", 0))
                wait_time = max(retry_after, 30 * attempt)  # 30s, 60s, 90s...
                print(f"\n    ⏳ Rate limited (429). Waiting {wait_time}s (attempt {attempt}/{max_retries})...",
                      end=" ", flush=True)
                time.sleep(wait_time)
                continue

            resp.raise_for_status()

            raw_resp = resp.json()
            finish_reason = raw_resp["choices"][0].get("finish_reason", "unknown")
            content = raw_resp["choices"][0]["message"].get("content")

            # Guard: thinking models may return empty content when max_tokens
            # is too low (thinking tokens consume the budget first)
            if not content:
                last_error = f"Empty content (finish_reason={finish_reason})"
                if attempt < max_retries:
                    wait = 5 * attempt
                    print(f"\n    ⚠️  {last_error}. Retrying in {wait}s...")
                    time.sleep(wait)
                    continue
                raise RuntimeError(last_error)

            # Parse JSON from response (handle markdown fences)
            content = content.strip()
            if content.startswith("```"):
                content = re.sub(r"^```(?:json)?\n?", "", content)
                content = re.sub(r"\n?```$", "", content)

            # Fix invalid JSON backslash escapes from LaTeX (e.g. \left \{ \text)
            # Valid JSON escapes: \" \\ \/ \b \f \n \r \t \uXXXX
            # Regex approach FAILS on \\left (two chars: \,\,l,e,f,t) because
            # it can't tell "second half of \\ pair" from "new invalid escape".
            # Character-by-character correctly consumes \\ pairs then catches
            # lone backslashes followed by invalid chars.
            content = _fix_json_backslashes(content)

            try:
                return json.loads(content)
            except json.JSONDecodeError:
                # If truncated due to length, try to repair JSON
                if finish_reason == "length":
                    repaired = _repair_truncated_json(content)
                    if repaired is not None:
                        print(f"\n    🔧 Repaired truncated JSON ({len(content)} chars)", end=" ")
                        return repaired

                last_error = f"JSON parse failed (finish_reason={finish_reason}, {len(content)} chars)"
                if attempt < max_retries:
                    wait = 2 ** attempt
                    print(f"\n    ⚠️  {last_error}. Retrying in {wait}s...")
                    print(f"    → First 200 chars: {content[:200]}")
                    time.sleep(wait)
                else:
                    print(f"\n    ⚠️  {last_error} (giving up)")
                    print(f"    → First 300 chars: {content[:300]}")
                    raise

        except httpx.HTTPStatusError as e:
            last_error = f"HTTP {e.response.status_code}"
            status = e.response.status_code
            if status == 429:
                wait_time = 30 * attempt
                print(f"\n    ⏳ Rate limited (429). Waiting {wait_time}s (attempt {attempt}/{max_retries})...",
                      end=" ", flush=True)
                time.sleep(wait_time)
            elif 500 <= status < 600:
                wait = 2 ** attempt
                print(f"\n    ⚠️  Server error ({status}). Retrying in {wait}s...")
                time.sleep(wait)
            else:
                print(f"\n    ❌ HTTP {status}: {e.response.text[:200]}")
                raise
        except httpx.TimeoutException:
            wait = 5 * attempt
            last_error = "Timeout"
            print(f"\n    ⏳ Timeout. Retrying in {wait}s (attempt {attempt}/{max_retries})...")
            time.sleep(wait)

    raise RuntimeError(f"All {max_retries} attempts failed. Last error: {last_error}")


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
        # Respect --limit flag (global chunk counter)
        if _chunk_limit > 0:
            global _chunks_processed
            if _chunks_processed >= _chunk_limit:
                print(f"      ⏹️  Reached --limit {_chunk_limit}. Stopping.")
                break
            _chunks_processed += 1

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

        time.sleep(_active_provider.get("pause", RATE_LIMIT_PAUSE))

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
    parser.add_argument("--provider", default="gemini", choices=list(PROVIDERS.keys()),
                        help="LLM provider to use (default: gemini)")
    parser.add_argument("--limit", type=int, default=0,
                        help="Max chunks to process (0 = all). For testing.")
    parser.add_argument("--extracted-dir", type=str, default=None,
                        help="Override extracted markdown directory")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be processed without calling the API")
    args = parser.parse_args()

    ensure_dirs()

    if args.subject not in SUBJECTS:
        print(f"❌ Unknown subject '{args.subject}'. Known: {list(SUBJECTS.keys())}")
        sys.exit(1)

    # Set and validate the chosen provider
    set_provider(args.provider)
    prov = _active_provider
    if not prov["api_key"]:
        key_name = f"{args.provider.upper()}_API_KEY"
        print(f"❌ {key_name} not set. Add it to pipeline/.env")
        sys.exit(1)

    # Set chunk limit for testing
    global _chunk_limit, _chunks_processed
    _chunk_limit = args.limit
    _chunks_processed = 0

    print(f"🤖 Provider: {prov['label']} | model: {prov['model']}")
    if _chunk_limit:
        print(f"🔢 Chunk limit: {_chunk_limit}")

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
    print(f"📄 Found {len(md_files)} markdown files")
    print(f"⏱️  Rate limit pause: {prov.get('pause', RATE_LIMIT_PAUSE)}s/req\n")

    # Dry-run: just list files and sizes, then exit
    if args.dry_run:
        total_chunks = 0
        for md_file in md_files:
            text = md_file.read_text(encoding="utf-8")
            chunks = chunk_text(text)
            total_chunks += len(chunks)
            print(f"  📄 {md_file.relative_to(extracted_dir)}: {len(text):,} chars → {len(chunks)} chunks")
        est_time = total_chunks * prov.get("pause", RATE_LIMIT_PAUSE) + total_chunks * 5  # ~5s per API call
        print(f"\n📊 Total: {len(md_files)} files, {total_chunks} chunks")
        print(f"⏱️  Estimated time: ~{est_time / 60:.0f} min (at {prov.get('pause', RATE_LIMIT_PAUSE)}s pause + ~5s/API call)")
        return

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

        # Stop the whole pipeline if --limit reached
        if _chunk_limit > 0 and _chunks_processed >= _chunk_limit:
            print(f"\n⏹️  Global --limit {_chunk_limit} reached. Stopping pipeline.")
            break

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
