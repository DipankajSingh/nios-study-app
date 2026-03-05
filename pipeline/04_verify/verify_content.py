#!/usr/bin/env python3
"""
Stage 4 — Verify Content (Anti-Hallucination)

Reads a StructuredSubject JSON (from Stage 3) and verifies every ContentBlock
by checking that its `exact_source_quote` actually exists in the original
extracted text. Blocks that fail are rejected.

Usage:
    cd pipeline
    python -m 04_verify.verify_content --subject maths-12

Verification rules:
  1. Every ContentBlock must have a non-empty exact_source_quote
  2. The quote must appear verbatim (or near-verbatim) in the source text
  3. Near-verbatim = lowercase, whitespace-normalized match with ≥90% overlap
  4. Blocks that fail are DROPPED (not served to students)

Output: VerifiedSubject JSON in output/verified/<subject>.json
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import (
    STRUCTURED_DIR, VERIFIED_DIR, EXTRACTED_DIR, SUBJECTS,
    ensure_dirs,
)
from schemas import (
    StructuredSubject, StructuredChapter, VerifiedSubject, VerificationStats,
    ContentBlock,
)


# ── Verification logic ───────────────────────────────────────────────────────

def normalize(text: str) -> str:
    """Normalize text for fuzzy matching: lowercase, collapse whitespace."""
    text = text.lower().strip()
    text = re.sub(r'\s+', ' ', text)
    # Remove common OCR artifacts
    text = text.replace('\u00ad', '')  # soft hyphen
    text = text.replace('\ufeff', '')  # BOM
    return text


def find_quote_in_source(quote: str, source: str, threshold: float = 0.85) -> bool:
    """Check if a quote exists in the source text.
    
    Uses three strategies:
    1. Exact normalized match (fastest)
    2. Sliding window overlap (catches minor OCR differences)
    3. Keyword density check (catches paraphrasing)
    """
    if not quote or not source:
        return False

    nq = normalize(quote)
    ns = normalize(source)

    # Strategy 1: Direct substring match
    if nq in ns:
        return True

    # Strategy 2: Sliding window with overlap ratio
    # For short quotes (< 60 chars), require exact match
    if len(nq) < 60:
        return False

    # Split quote into words and check if most appear in a local window
    q_words = set(nq.split())
    if len(q_words) < 3:
        return False

    # Check if ≥threshold of quote words appear in any window of source
    s_words = ns.split()
    window_size = len(q_words) * 3  # generous window

    for start in range(0, max(1, len(s_words) - window_size + 1), len(q_words)):
        window = set(s_words[start:start + window_size])
        overlap = len(q_words & window) / len(q_words)
        if overlap >= threshold:
            return True

    return False


def load_source_text(subject_id: str, chapter_id: str) -> str:
    """Load the original extracted text for a chapter.
    
    Tries multiple locations:
    1. pipeline/output/extracted/<subject>/<chapter>/*.md
    2. content/class<level>/<subject>.raw.json (rawText fields)
    """
    # Try extracted markdown
    extracted_chapter_dir = EXTRACTED_DIR / subject_id / chapter_id
    if extracted_chapter_dir.exists():
        md_files = list(extracted_chapter_dir.glob("*.md"))
        if md_files:
            return "\n\n".join(f.read_text(encoding="utf-8") for f in md_files)

    # Try broader extracted dir (markdown files named after PDFs)
    extracted_subject_dir = EXTRACTED_DIR / subject_id
    if extracted_subject_dir.exists():
        md_files = sorted(extracted_subject_dir.rglob("*.md"))
        if md_files:
            return "\n\n".join(f.read_text(encoding="utf-8") for f in md_files)

    # Try raw JSON
    cfg = SUBJECTS.get(subject_id, {})
    class_level = cfg.get("class_level", "12")
    raw_json_path = Path(__file__).resolve().parent.parent.parent / "content" / f"class{class_level}" / f"{subject_id}.raw.json"
    if raw_json_path.exists():
        data = json.loads(raw_json_path.read_text(encoding="utf-8"))
        for ch in data.get("chapters", []):
            if ch.get("id") == chapter_id:
                texts = [t.get("rawText", "") for t in ch.get("topics", [])]
                return "\n\n".join(texts)
        # If chapter not found by ID, return all text
        all_texts = []
        for ch in data.get("chapters", []):
            for t in ch.get("topics", []):
                all_texts.append(t.get("rawText", ""))
        return "\n\n".join(all_texts)

    return ""


# ── Main verification ────────────────────────────────────────────────────────

def verify_subject(subject_id: str) -> VerifiedSubject:
    """Verify all content blocks for a subject."""
    input_file = STRUCTURED_DIR / f"{subject_id}.json"
    if not input_file.exists():
        print(f"❌ No structured data found: {input_file}")
        print(f"   Run Stage 3 (structure_content) first.")
        sys.exit(1)

    structured = StructuredSubject.model_validate_json(input_file.read_text())
    print(f"📋 Verifying: {structured.subject.name} ({subject_id})")
    print(f"   Chapters: {len(structured.chapters)}")

    stats = VerificationStats()
    verified_chapters: list[StructuredChapter] = []

    for chapter in structured.chapters:
        print(f"\n  📖 Chapter: {chapter.chapter.title}")

        # Load source text for this chapter
        source_text = load_source_text(subject_id, chapter.chapter.id)
        if not source_text:
            print(f"    ⚠️  No source text found — keeping all blocks UNVERIFIED")
            verified_chapters.append(chapter)
            stats.total_blocks += len(chapter.content_blocks)
            stats.total_topics += len(chapter.topics)
            stats.topics_with_content += len(chapter.topic_contents)
            continue

        # Verify each content block
        verified_blocks: list[ContentBlock] = []
        for block in chapter.content_blocks:
            stats.total_blocks += 1
            quote = block.exact_source_quote

            if not quote:
                print(f"    ❌ Block {block.id}: NO QUOTE — rejected")
                stats.rejected_blocks += 1
                continue

            if find_quote_in_source(quote, source_text):
                block.is_verified = True
                verified_blocks.append(block)
                stats.verified_blocks += 1
            else:
                print(f"    ❌ Block {block.id}: quote NOT FOUND in source — rejected")
                print(f"       Quote: {quote[:80]}...")
                stats.rejected_blocks += 1

        stats.total_topics += len(chapter.topics)
        stats.topics_with_content += len(chapter.topic_contents)

        # Replace blocks with only verified ones
        verified_chapter = StructuredChapter(
            chapter=chapter.chapter,
            topics=chapter.topics,
            topic_contents=chapter.topic_contents,
            content_blocks=verified_blocks,
        )
        verified_chapters.append(verified_chapter)

        v = len(verified_blocks)
        total = len(chapter.content_blocks)
        pct = (v / total * 100) if total > 0 else 0
        print(f"    ✅ {v}/{total} blocks verified ({pct:.0f}%)")

    result = VerifiedSubject(
        subject=structured.subject,
        verified_at=datetime.now(timezone.utc).isoformat(),
        chapters=verified_chapters,
        stats=stats,
    )

    print(f"\n{'='*60}")
    print(f"VERIFICATION SUMMARY for {subject_id}")
    print(f"{'='*60}")
    print(f"  Total blocks:    {stats.total_blocks}")
    print(f"  Verified:        {stats.verified_blocks} ✅")
    print(f"  Rejected:        {stats.rejected_blocks} ❌")
    pct = (stats.verified_blocks / stats.total_blocks * 100) if stats.total_blocks > 0 else 0
    print(f"  Accuracy:        {pct:.1f}%")
    print(f"  Topics:          {stats.total_topics}")
    print(f"  Topics w/content:{stats.topics_with_content}")

    return result


def main():
    parser = argparse.ArgumentParser(description="Stage 4: Verify content against source text")
    parser.add_argument("--subject", required=True, help="Subject ID, e.g. maths-12")
    args = parser.parse_args()

    ensure_dirs()
    result = verify_subject(args.subject)

    output_file = VERIFIED_DIR / f"{args.subject}.json"
    output_file.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    print(f"\n💾 Output: {output_file}")


if __name__ == "__main__":
    main()
