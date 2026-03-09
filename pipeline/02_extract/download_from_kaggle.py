#!/usr/bin/env python3
"""
Stage 2d — Download marker-extracted JSON from Kaggle Datasets

Downloads the marker-pdf extracted chapter JSON files from a Kaggle dataset
(produced by the Kaggle extraction notebook) to the local
pipeline/output/extracted/<subject>/ directory so that Stage 3
(structure_content.py) can process them.

Expected Kaggle dataset structure (produced by extract_pdf_kaggle.ipynb):
  <username>/nios-<subject>-extracted/
    ├── Chapter 1.json
    ├── Chapter 2.json
    ├── ...
    └── _manifest.json

Authentication:
  Set KAGGLE_API_TOKEN and KAGGLE_USERNAME in pipeline/.env
  Get your token at: https://www.kaggle.com/settings → API → Create New Token

Usage:
    cd pipeline
    # Single subject (--dataset required):
    python 02_extract/download_from_kaggle.py --subject maths-12 --dataset <username>/nios-maths-12-extracted

    # All subjects (dataset slugs auto-derived from KAGGLE_USERNAME):
    python 02_extract/download_from_kaggle.py --all
    python 02_extract/download_from_kaggle.py --all --resume
"""

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import EXTRACTED_DIR, KAGGLE_USERNAME, SUBJECTS, ensure_dirs


# ── Helpers ───────────────────────────────────────────────────────────────────

def check_kaggle_cli():
    """Abort with a helpful message if the kaggle CLI is not available."""
    result = subprocess.run(["kaggle", "--version"], capture_output=True)
    if result.returncode != 0:
        print("❌ kaggle CLI not found. Run: pip install kaggle")
        print("   Then add ~/.kaggle/kaggle.json with your API credentials.")
        print("   Get your key at: https://www.kaggle.com/settings → API → Create New Token")
        sys.exit(1)


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Download marker-extracted chapter JSON files from Kaggle"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--subject", help="Subject ID, e.g. maths-12")
    group.add_argument(
        "--all", action="store_true",
        help="Download extracted JSON for every subject in the registry",
    )
    parser.add_argument(
        "--dataset",
        help="Kaggle dataset ID (<username>/<slug>). Required with --subject; auto-derived with --all.",
    )
    parser.add_argument(
        "--resume", action="store_true",
        help="Skip subjects whose output directory already has JSON files",
    )
    args = parser.parse_args()

    check_kaggle_cli()
    ensure_dirs()

    if args.all:
        if args.dataset:
            print("⚠️  --dataset is ignored when --all is used (dataset is auto-derived per subject)")
        if not KAGGLE_USERNAME:
            print("❌ KAGGLE_USERNAME not set. Add it to pipeline/.env")
            sys.exit(1)
        subjects_to_run = list(SUBJECTS.keys())
    else:
        if args.subject not in SUBJECTS:
            print(f"❌ Unknown subject '{args.subject}'. Known: {list(SUBJECTS.keys())}")
            sys.exit(1)
        if not args.dataset:
            print("❌ --dataset is required when using --subject")
            sys.exit(1)
        subjects_to_run = [args.subject]

    failed = []
    for subject_id in subjects_to_run:
        print(f"\n{'='*60}")
        dataset_id = f"{KAGGLE_USERNAME}/nios-{subject_id}-extracted" if args.all else args.dataset
        ok = _download_subject(subject_id, dataset_id, args.resume)
        if not ok:
            failed.append(subject_id)

    if args.all:
        print(f"\n{'='*60}")
        print(f"✅ Done: {len(subjects_to_run) - len(failed)}/{len(subjects_to_run)} subjects downloaded")
        if failed:
            print(f"❌ Failed: {', '.join(failed)}")


def _download_subject(subject_id: str, dataset_id: str, resume: bool) -> bool:
    """Download extracted JSON for one subject. Returns True on success."""
    local_output = EXTRACTED_DIR / subject_id
    local_output.mkdir(parents=True, exist_ok=True)

    if resume:
        existing = list(local_output.glob("*.json"))
        if existing:
            print(f"⏭️  Resume: {len(existing)} JSON file(s) already in {local_output}")
            print("   Delete the directory or omit --resume to re-download.")
            return True

    print(f"📥 Downloading dataset: {dataset_id}")
    print(f"📂 Destination:        {local_output}\n")

    with tempfile.TemporaryDirectory() as tmp:
        result = subprocess.run(
            [
                "kaggle", "datasets", "download",
                dataset_id,
                "--path", tmp,
                "--unzip",
            ]
        )
        if result.returncode != 0:
            print("❌ kaggle CLI download failed.")
            return False

        for src in Path(tmp).glob("**/*"):
            if src.is_file():
                src.replace(local_output / src.name)

    json_files = sorted(local_output.glob("*.json"))
    total_kb = sum(f.stat().st_size for f in json_files) / 1024

    print(f"\n✅ {len(json_files)} JSON file(s) saved to: {local_output}")
    print(f"   Total size: {total_kb:.0f} KB")
    for f in json_files:
        print(f"  📄 {f.name}")

    print(f"\n   Next step:")
    print(f"   python 03_structure/structure_content.py --subject {subject_id} --dry-run")
    return True


if __name__ == "__main__":
    main()
