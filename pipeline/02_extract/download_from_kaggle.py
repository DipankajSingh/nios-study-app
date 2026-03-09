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
"""

import argparse
import shutil
import sys
import tempfile
import time
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import EXTRACTED_DIR, SUBJECTS, ensure_dirs


# ── Kaggle auth ───────────────────────────────────────────────────────────────

def get_kaggle_api():
    try:
        from kaggle.api.kaggle_api_extended import KaggleApiExtended
    except ImportError:
        print("❌ kaggle package not installed. Run: pip install kaggle")
        sys.exit(1)

    api = KaggleApiExtended()
    try:
        api.authenticate()
    except Exception as e:
        print(f"❌ Kaggle authentication failed: {e}")
        print("   Create ~/.kaggle/kaggle.json with your API credentials.")
        print("   Get your key at: https://www.kaggle.com/settings → API → Create New Token")
        sys.exit(1)
    return api


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
        help="Skip files that already exist locally",
    )
    args = parser.parse_args()

    ensure_dirs()

    if args.subject not in SUBJECTS:
        print(f"❌ Unknown subject '{args.subject}'. Known: {list(SUBJECTS.keys())}")
        sys.exit(1)

    local_output = EXTRACTED_DIR / args.subject
    local_output.mkdir(parents=True, exist_ok=True)

    print(f"🔑 Authenticating with Kaggle...")
    api = get_kaggle_api()

    print(f"\n🔍 Checking dataset: {args.dataset}")
    try:
        file_list = api.dataset_list_files(args.dataset)
        files = file_list.files if hasattr(file_list, "files") else []
    except Exception as e:
        print(f"❌ Cannot access dataset '{args.dataset}': {e}")
        print("   Check the dataset ID and that you have access to it.")
        sys.exit(1)

    if not files:
        print("❌ Dataset is empty or has no accessible files.")
        sys.exit(1)

    print(f"\n📚 Found {len(files)} file(s) in dataset:")
    for f in sorted(files, key=lambda x: x.name):
        size_kb = (f.totalBytes or 0) / 1024
        print(f"  📄 {f.name} ({size_kb:.1f} KB)")

    # Partition into skip / download lists
    skipped = []
    to_download = []
    for f in files:
        dest = local_output / f.name
        if args.resume and dest.exists():
            skipped.append(f.name)
        else:
            to_download.append(f)

    if skipped:
        print(f"\n⏭️  Skipping {len(skipped)} already-present file(s)")

    if not to_download:
        print("\n✅ Nothing to download — all files already present.")
        return

    print(f"\n📂 Downloading {len(to_download)} file(s) to: {local_output}\n")

    stats = {"downloaded": 0, "failed": 0, "bytes": 0}

    # Download each file into a temp dir then move to avoid partial writes
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        for f in sorted(to_download, key=lambda x: x.name):
            dest = local_output / f.name
            size_kb = (f.totalBytes or 0) / 1024
            print(f"  📥 {f.name} ({size_kb:.1f} KB)")

            try:
                api.dataset_download_file(
                    args.dataset,
                    f.name,
                    path=str(tmp_path),
                    quiet=True,
                    force=True,
                )

                tmp_file = tmp_path / f.name

                # Kaggle sometimes wraps the file in a zip
                if not tmp_file.exists():
                    tmp_zip = tmp_path / (f.name + ".zip")
                    if tmp_zip.exists():
                        with zipfile.ZipFile(tmp_zip) as z:
                            z.extractall(tmp_path)
                        tmp_zip.unlink()

                if tmp_file.exists():
                    shutil.move(str(tmp_file), str(dest))
                    stats["downloaded"] += 1
                    stats["bytes"] += f.totalBytes or 0
                else:
                    print(f"  ⚠️  File not found in download response: {f.name}")
                    stats["failed"] += 1

            except Exception as e:
                print(f"  ❌ Failed to download {f.name}: {e}")
                stats["failed"] += 1

            time.sleep(0.1)  # gentle rate limit

    total_mb = stats["bytes"] / (1024 * 1024)
    print(f"\n{'─' * 50}")
    print(f"  ✅ Downloaded: {stats['downloaded']}")
    print(f"  ⏭️  Skipped:    {len(skipped)}")
    print(f"  ❌ Failed:     {stats['failed']}")
    print(f"  📦 Total:      {total_mb:.1f} MB")
    print(f"{'─' * 50}")
    print(f"\n📂 Files saved to: {local_output}")

    if stats["failed"] == 0:
        print(f"\n   Next step:")
        print(f"   python 03_structure/structure_content.py --subject {args.subject} --dry-run")


if __name__ == "__main__":
    main()
