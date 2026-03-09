#!/usr/bin/env python3
"""
Stage 2d — Download marker-extracted JSON from Kaggle Dataset

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
  Requires ~/.kaggle/kaggle.json with {"username": "...", "key": "..."}
  Get your token at: https://www.kaggle.com/settings → API → Create New Token

Usage:
    cd pipeline
    python 02_extract/download_from_kaggle.py --subject maths-12 --dataset <username>/nios-maths-12-extracted
    python 02_extract/download_from_kaggle.py --subject maths-12 --dataset <username>/nios-maths-12-extracted --resume

The CLI downloads the whole dataset as a zip and unpacks it, so --resume skips
the entire download if all expected files are already present.
"""

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import EXTRACTED_DIR, SUBJECTS, ensure_dirs


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
    parser.add_argument("--subject", required=True, help="Subject ID, e.g. maths-12")
    parser.add_argument(
        "--dataset", required=True,
        help="Kaggle dataset ID in the form <username>/<dataset-slug>",
    )
    parser.add_argument(
        "--resume", action="store_true",
        help="Skip the download if all JSON files are already present locally",
    )
    args = parser.parse_args()

    check_kaggle_cli()
    ensure_dirs()

    if args.subject not in SUBJECTS:
        print(f"❌ Unknown subject '{args.subject}'. Known: {list(SUBJECTS.keys())}")
        sys.exit(1)

    local_output = EXTRACTED_DIR / args.subject
    local_output.mkdir(parents=True, exist_ok=True)

    # --resume: skip if output dir already has JSON files
    if args.resume:
        existing = list(local_output.glob("*.json"))
        if existing:
            print(f"⏭️  Resume: {len(existing)} JSON file(s) already in {local_output}")
            print("   Delete the directory or omit --resume to re-download.")
            return

    print(f"📥 Downloading dataset: {args.dataset}")
    print(f"📂 Destination:        {local_output}\n")

    # kaggle datasets download unpacks the zip directly into --path
    with tempfile.TemporaryDirectory() as tmp:
        result = subprocess.run(
            [
                "kaggle", "datasets", "download",
                args.dataset,
                "--path", tmp,
                "--unzip",
            ]
        )
        if result.returncode != 0:
            print("❌ kaggle CLI download failed.")
            sys.exit(result.returncode)

        # Move all files from temp into the output directory
        downloaded = list(Path(tmp).glob("**/*"))
        files = [f for f in downloaded if f.is_file()]
        for src in files:
            dest = local_output / src.name
            src.replace(dest)

    json_files = sorted(local_output.glob("*.json"))
    total_kb = sum(f.stat().st_size for f in json_files) / 1024

    print(f"\n✅ {len(json_files)} JSON file(s) saved to: {local_output}")
    print(f"   Total size: {total_kb:.0f} KB")
    for f in json_files:
        print(f"  📄 {f.name}")

    print(f"\n   Next step:")
    print(f"   python 03_structure/structure_content.py --subject {args.subject} --dry-run")


if __name__ == "__main__":
    main()
