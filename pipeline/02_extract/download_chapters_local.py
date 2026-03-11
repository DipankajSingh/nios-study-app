#!/usr/bin/env python3
"""
Stage 2b — Download NIOS chapter PDFs offline, with class-level structure

Interactive mode (no flags):
  Prompts you to select class → stream → subjects → confirm each batch.
  This replicates the interactive class → stream → subject selection workflow.

Non-interactive (CI / scripting):
  --subject maths-12          download one subject
  --class 12                  download all class-12 subjects
  --all                       download everything

Output structure (mirrors content/):
  pipeline/output/pdfs/
    class12/
      maths-12/
        chapters/
          Chapter 1.pdf
          Chapter 2.pdf  ...
        _manifest.json
    class10/
      maths-10/
        chapters/ ...
        _manifest.json

A registry file (pipeline/output/pdfs/_registry.json) tracks every chapter
that was successfully downloaded so re-runs skip already-done work even
without --resume.

Prerequisites:
    python 01_scrape/generate_chapter_urls.py --subject maths-12
    # or for everything:
    python 01_scrape/generate_chapter_urls.py --all

After downloading, upload to Kaggle:
    kaggle datasets init -p pipeline/output/pdfs/class12/maths-12/chapters
    # edit dataset-metadata.json, then:
    kaggle datasets create -p pipeline/output/pdfs/class12/maths-12/chapters
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import CHAPTER_URLS_DIR, PDF_OUTPUT_ROOT, SUBJECTS

# ── Constants ─────────────────────────────────────────────────────────────────

REGISTRY_FILE   = PDF_OUTPUT_ROOT / "_registry.json"
BATCH_SIZE      = 3

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# Stream groupings derived from SUBJECTS registry
STREAMS = ["Science", "Commerce", "Humanities", "Languages"]


# ── Registry ──────────────────────────────────────────────────────────────────

def _load_registry() -> dict:
    if REGISTRY_FILE.exists():
        with open(REGISTRY_FILE, encoding="utf-8") as fh:
            return json.load(fh)
    return {}


def _save_registry(registry: dict) -> None:
    REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(REGISTRY_FILE, "w", encoding="utf-8") as fh:
        json.dump(registry, fh, indent=2)


def _registry_key(subject_id: str, chapter_name: str) -> str:
    return f"{subject_id}::{chapter_name}"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _safe_pdf_name(raw_name: str, fallback_index: int) -> str:
    name = raw_name.strip() if raw_name else ""
    if not name:
        name = f"Chapter {fallback_index}.pdf"
    name = re.sub(r'[\\/:*?"<>|]', "_", name)
    if not name.lower().endswith(".pdf"):
        name += ".pdf"
    return name


def _download_file(url: str, dest: Path, timeout: int, max_retries: int) -> bool:
    for attempt in range(max_retries):
        try:
            with requests.get(url, headers=HEADERS, timeout=timeout, stream=True) as resp:
                resp.raise_for_status()
                with open(dest, "wb") as fh:
                    for chunk in resp.iter_content(chunk_size=8192):
                        if chunk:
                            fh.write(chunk)
            return True
        except Exception as exc:
            wait = 2 ** attempt
            print(f"      attempt {attempt + 1}/{max_retries} failed: {exc}  retry in {wait}s")
            time.sleep(wait)
    return False


def _subjects_for_stream(stream: str, class_level: str | None = None) -> list[str]:
    return [
        sid for sid, cfg in SUBJECTS.items()
        if cfg["stream"] == stream
        and (class_level is None or cfg["class_level"] == class_level)
    ]


def _subjects_for_class(class_level: str) -> list[str]:
    return [sid for sid, cfg in SUBJECTS.items() if cfg["class_level"] == class_level]


def _chapters_dir(subject_id: str) -> Path:
    lvl = SUBJECTS[subject_id]["class_level"]
    return PDF_OUTPUT_ROOT / f"class{lvl}" / subject_id / "chapters"


# ── Per-subject download ──────────────────────────────────────────────────────

def _process_subject(
    subject_id: str,
    registry: dict,
    timeout: int,
    max_retries: int,
    min_bytes: int,
) -> bool:
    """Download all chapters for one subject. Returns True when no failures."""
    cfg         = SUBJECTS[subject_id]
    class_level = cfg["class_level"]
    subject_name = cfg["name"]

    urls_path = CHAPTER_URLS_DIR / f"{subject_id}.json"
    if not urls_path.exists():
        print(f"  [skip] URL config missing: {urls_path}")
        print(f"         Run: python 01_scrape/generate_chapter_urls.py --subject {subject_id}")
        return False

    with open(urls_path, encoding="utf-8") as fh:
        url_data = json.load(fh)

    chapters = url_data.get("chapters", [])
    if not chapters:
        print(f"  [fail] No chapters listed in {urls_path}")
        return False

    chapters_dir = _chapters_dir(subject_id)
    subject_dir  = chapters_dir.parent
    chapters_dir.mkdir(parents=True, exist_ok=True)

    total = len(chapters)
    print(f"\n  -> {subject_name} ({subject_id})  Class {class_level}  —  {total} chapter(s)")
    print(f"     {chapters_dir}")

    stats: dict[str, int] = {"ok": 0, "skip": 0, "fail": 0}
    manifest_chapters: list[dict] = []

    for idx, ch in enumerate(chapters, start=1):
        raw_name  = ch.get("name", "")
        url       = ch.get("url", "").strip()
        file_name = _safe_pdf_name(raw_name, idx)
        out_file  = chapters_dir / file_name
        reg_key   = _registry_key(subject_id, file_name)
        prefix    = f"     [{idx:>2}/{total}]"

        entry: dict = {
            "index": idx,
            "name": file_name,
            "url": url,
            "status": "pending",
            "size_bytes": 0,
        }

        if not url:
            print(f"{prefix} FAIL  {file_name}  (no URL)")
            stats["fail"] += 1
            entry["status"] = "failed"
            manifest_chapters.append(entry)
            continue

        # Skip if already downloaded (registry check)
        if registry.get(reg_key) == "SUCCESS" and out_file.exists() and out_file.stat().st_size >= min_bytes:
            size_kb = out_file.stat().st_size // 1024
            print(f"{prefix} skip  {file_name}  ({size_kb} KB — already downloaded)")
            stats["skip"] += 1
            entry["status"] = "skipped"
            entry["size_bytes"] = out_file.stat().st_size
            manifest_chapters.append(entry)
            continue

        print(f"{prefix} get   {file_name}")
        ok = _download_file(url, out_file, timeout=timeout, max_retries=max_retries)

        if ok and out_file.exists() and out_file.stat().st_size >= min_bytes:
            size_kb = out_file.stat().st_size // 1024
            print(f"             -> {size_kb} KB  [SUCCESS]")
            stats["ok"] += 1
            entry["status"]     = "downloaded"
            entry["size_bytes"] = out_file.stat().st_size
            registry[reg_key]   = "SUCCESS"
            _save_registry(registry)
        else:
            print(f"             -> [FAILED]")
            stats["fail"] += 1
            entry["status"]     = "failed"
            entry["size_bytes"] = out_file.stat().st_size if out_file.exists() else 0
            registry[reg_key]   = "FAILED"
            _save_registry(registry)

        manifest_chapters.append(entry)

    # Write per-subject manifest
    total_bytes = sum(e["size_bytes"] for e in manifest_chapters)
    manifest = {
        "subject":      subject_id,
        "subject_name": subject_name,
        "class_level":  class_level,
        "code":         cfg["code"],
        "stream":       cfg["stream"],
        "source_url":   url_data.get("source_url"),
        "downloaded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "paths": {
            "urls_json":    str(urls_path),
            "chapters_dir": str(chapters_dir),
        },
        "stats": {**stats, "total_bytes": total_bytes},
        "chapters": manifest_chapters,
    }
    with open(subject_dir / "_manifest.json", "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, ensure_ascii=False)

    total_kb = total_bytes // 1024
    print(
        f"     Summary: ok={stats['ok']}  skip={stats['skip']}  fail={stats['fail']}"
        f"  ({total_kb} KB total)"
    )
    return stats["fail"] == 0


# ── Batch runner ──────────────────────────────────────────────────────────────

def _run_subjects(subjects: list[str], timeout: int, max_retries: int, min_bytes: int) -> None:
    """Process subjects in confirm-batches of BATCH_SIZE, with a shared registry."""
    registry = _load_registry()
    failed: list[str] = []

    for i in range(0, len(subjects), BATCH_SIZE):
        batch = subjects[i : i + BATCH_SIZE]

        print(f"\n--- Next batch ({i + 1}–{min(i + BATCH_SIZE, len(subjects))} of {len(subjects)}) ---")
        for n, sid in enumerate(batch, 1):
            cfg = SUBJECTS[sid]
            print(f"  {n}. {cfg['name']} ({sid})  Class {cfg['class_level']}")

        ans = input("\nProcess this batch? [y / n / quit]: ").strip().lower()
        if ans in ("q", "quit"):
            print("Exiting.")
            break
        if ans != "y":
            print("Skipping batch.")
            continue

        for sid in batch:
            ok = _process_subject(sid, registry, timeout, max_retries, min_bytes)
            if not ok:
                failed.append(sid)

    print("\n" + "=" * 72)
    done = len(subjects) - len(failed)
    print(f"Done: {done}/{len(subjects)} subjects")
    if failed:
        print(f"Failed: {', '.join(failed)}")
    print(f"Registry: {REGISTRY_FILE}")


# ── Interactive mode ──────────────────────────────────────────────────────────

def _interactive(timeout: int, max_retries: int, min_bytes: int) -> None:
    print("=" * 72)
    print("NIOS Offline Chapter Downloader")
    print("=" * 72)

    # Step 1: Class
    print("\nSelect class:")
    print("  1) Class 10 (Secondary)")
    print("  2) Class 12 (Senior Secondary)")
    print("  3) Both")
    choice = input("Choice [1/2/3]: ").strip()
    if choice == "1":
        class_levels = ["10"]
    elif choice == "2":
        class_levels = ["12"]
    elif choice == "3":
        class_levels = ["10", "12"]
    else:
        print("Invalid choice. Exiting.")
        sys.exit(1)

    all_selected: list[str] = []

    for class_level in class_levels:
        print(f"\n--- Class {class_level} ---")

        # Step 2: Stream
        streams_available = sorted({
            SUBJECTS[sid]["stream"]
            for sid in SUBJECTS
            if SUBJECTS[sid]["class_level"] == class_level
        })
        print("Select stream:")
        for i, s in enumerate(streams_available, 1):
            count = len(_subjects_for_stream(s, class_level))
            print(f"  {i}) {s}  ({count} subject(s))")
        print(f"  {len(streams_available) + 1}) All streams")

        s_choice = input(f"Choice [1-{len(streams_available) + 1}]: ").strip()
        try:
            s_idx = int(s_choice) - 1
        except ValueError:
            print("Invalid choice. Exiting.")
            sys.exit(1)

        if s_idx == len(streams_available):
            stream_subjects = _subjects_for_class(class_level)
            selected_stream = "ALL"
        elif 0 <= s_idx < len(streams_available):
            selected_stream = streams_available[s_idx]
            stream_subjects = _subjects_for_stream(selected_stream, class_level)
        else:
            print("Invalid choice. Exiting.")
            sys.exit(1)

        # Step 3: Subject within stream
        print(f"\nSubjects in {selected_stream} — Class {class_level}:")
        for i, sid in enumerate(stream_subjects, 1):
            cfg = SUBJECTS[sid]
            urls_ok = "✓" if (CHAPTER_URLS_DIR / f"{sid}.json").exists() else "✗ (no URL config)"
            print(f"  {i}) {cfg['name']} ({sid})  {urls_ok}")
        print(f"  {len(stream_subjects) + 1}) All in {selected_stream}")

        sub_choice = input(
            f"Enter numbers comma-separated, or {len(stream_subjects) + 1} for all: "
        ).strip()

        if sub_choice == str(len(stream_subjects) + 1):
            chosen = stream_subjects
        else:
            indices = []
            for tok in sub_choice.split(","):
                tok = tok.strip()
                if tok.isdigit():
                    indices.append(int(tok) - 1)
            chosen = [stream_subjects[i] for i in indices if 0 <= i < len(stream_subjects)]

        if not chosen:
            print("No subjects selected for this class.")
        else:
            all_selected.extend(chosen)

    if not all_selected:
        print("Nothing to download. Exiting.")
        sys.exit(0)

    print(f"\nWill download {len(all_selected)} subject(s) in batches of {BATCH_SIZE}.")
    _run_subjects(all_selected, timeout, max_retries, min_bytes)


# ── Non-interactive entry point ───────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Download NIOS chapter PDFs offline. "
            "Run with no flags for interactive mode."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--subject", metavar="ID", help="Single subject, e.g. maths-12")
    group.add_argument(
        "--class", dest="class_level", choices=["10", "12"],
        metavar="{10,12}", help="All subjects for class 10 or 12",
    )
    group.add_argument("--all", action="store_true", help="All registered subjects")

    parser.add_argument("--timeout",     type=int, default=60,   metavar="SEC")
    parser.add_argument("--max-retries", type=int, default=4,    metavar="N")
    parser.add_argument("--min-bytes",   type=int, default=4096, metavar="B")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    PDF_OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    # No selection flags → interactive
    if not args.subject and not args.class_level and not args.all:
        _interactive(args.timeout, args.max_retries, args.min_bytes)
        return

    # Resolve subjects for non-interactive mode
    if args.all:
        subjects = list(SUBJECTS.keys())
    elif args.class_level:
        subjects = _subjects_for_class(args.class_level)
        if not subjects:
            print(f"No subjects registered for class {args.class_level}.")
            sys.exit(1)
    else:
        if args.subject not in SUBJECTS:
            print(f"Unknown subject '{args.subject}'. Known: {', '.join(SUBJECTS)}")
            sys.exit(1)
        subjects = [args.subject]

    print("=" * 72)
    print(f"NIOS Offline Chapter Downloader  —  {len(subjects)} subject(s)")
    print("=" * 72)
    _run_subjects(subjects, args.timeout, args.max_retries, args.min_bytes)


if __name__ == "__main__":
    main()
