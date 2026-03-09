#!/usr/bin/env python3
"""
Stage 2c — Upload Chapter URLs config (or PDFs) to a Kaggle Dataset

Two upload modes:

  default (recommended)
    Uploads the tiny chapter_urls/<subject>.json produced by
    generate_chapter_urls.py.  The Kaggle notebook reads this JSON and
    downloads the PDFs directly from NIOS — no local PDF storage needed.
    Dataset slug: nios-<subject>-urls

  --pdfs
    Uploads the locally stored chapter PDFs instead.
    Useful if NIOS blocks downloads inside Kaggle's environment.
    Dataset slug: nios-<subject>-pdfs

Authentication:
  Requires ~/.kaggle/kaggle.json with {"username": "...", "key": "..."}
  Get your token at: https://www.kaggle.com/settings → API → Create New Token

Usage:
    cd pipeline
    # Recommended — upload the small URLs config file:
    python 02_extract/upload_to_kaggle.py --subject maths-12 --username <you>

    # Fallback — upload the raw PDFs:
    python 02_extract/upload_to_kaggle.py --subject maths-12 --username <you> --pdfs

After the upload, open extract_pdf_kaggle.ipynb on Kaggle and add the
dataset as input, then run the notebook.
"""

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import SUBJECTS, CHAPTER_URLS_DIR, KAGGLE_USERNAME, ensure_dirs

URLS_DIR = CHAPTER_URLS_DIR


# ── Helpers ───────────────────────────────────────────────────────────────────

def check_kaggle_cli():
    """Abort with a helpful message if the kaggle CLI is not available."""
    result = subprocess.run(["kaggle", "--version"], capture_output=True)
    if result.returncode != 0:
        print("❌ kaggle CLI not found. Run: pip install kaggle")
        print("   Then add ~/.kaggle/kaggle.json with your API credentials.")
        print("   Get your key at: https://www.kaggle.com/settings → API → Create New Token")
        sys.exit(1)


def dataset_exists(dataset_id: str) -> bool:
    """Return True if the Kaggle dataset already exists."""
    result = subprocess.run(
        ["kaggle", "datasets", "files", dataset_id],
        capture_output=True,
    )
    return result.returncode == 0


def kaggle_upload(staging_dir: Path, dataset_id: str, version_notes: str, is_new: bool, public: bool):
    """Create or update a Kaggle dataset from staging_dir."""
    if is_new:
        cmd = ["kaggle", "datasets", "create", "-p", str(staging_dir)]
        if public:
            cmd.append("--public")
        print(f"📤 Creating new {'public' if public else 'private'} dataset: {dataset_id}")
    else:
        cmd = [
            "kaggle", "datasets", "version",
            "-p", str(staging_dir),
            "-m", version_notes,
        ]
        print(f"📤 Updating existing dataset: {dataset_id}")

    result = subprocess.run(cmd)
    if result.returncode != 0:
        print("❌ kaggle CLI returned a non-zero exit code.")
        sys.exit(result.returncode)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Upload chapter URL config (or PDFs) to a Kaggle dataset"
    )
    parser.add_argument("--subject", required=True, help="Subject ID, e.g. maths-12")
    parser.add_argument(
        "--username",
        default=KAGGLE_USERNAME or None,
        help="Kaggle username (default: KAGGLE_USERNAME from .env)",
    )
    parser.add_argument(
        "--pdfs", action="store_true",
        help="Upload raw PDF files instead of the URL config (fallback mode)",
    )
    parser.add_argument(
        "--public", action="store_true",
        help="Make the dataset public (default: private)",
    )
    parser.add_argument(
        "--version-notes", default="Update",
        help="Version notes when updating an existing dataset",
    )
    parser.add_argument(
        "--dataset-slug",
        help="Override the auto-generated slug",
    )
    args = parser.parse_args()

    if not args.username:
        print("❌ Kaggle username not set. Add KAGGLE_USERNAME=<you> to pipeline/.env or pass --username <you>")
        sys.exit(1)

    check_kaggle_cli()
    ensure_dirs()

    if args.subject not in SUBJECTS:
        print(f"❌ Unknown subject '{args.subject}'. Known: {list(SUBJECTS.keys())}")
        sys.exit(1)

    subject_cfg = SUBJECTS[args.subject]

    if args.pdfs:
        _upload_pdfs(args, subject_cfg)
    else:
        _upload_urls(args, subject_cfg)


def _stage_and_upload(staging_dir: Path, dataset_id: str, metadata: dict, args):
    """Write dataset-metadata.json into staging_dir and push to Kaggle."""
    with open(staging_dir / "dataset-metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)

    is_new = not dataset_exists(dataset_id)
    kaggle_upload(staging_dir, dataset_id, args.version_notes, is_new, args.public)

    slug = dataset_id.split("/")[1]
    print(f"\n✅ Done!")
    print(f"   Dataset URL: https://www.kaggle.com/datasets/{dataset_id}")
    return slug


def _upload_urls(args, subject_cfg):
    """Upload the small chapter_urls/<subject>.json config file."""
    urls_file = URLS_DIR / f"{args.subject}.json"
    if not urls_file.exists():
        print(f"❌ URL config not found: {urls_file}")
        print(f"   Run first: python 01_scrape/generate_chapter_urls.py --subject {args.subject}")
        sys.exit(1)

    with open(urls_file) as f:
        url_data = json.load(f)
    chapter_count = len(url_data.get("chapters", []))

    slug = args.dataset_slug or f"nios-{args.subject}-urls"
    dataset_id = f"{args.username}/{slug}"

    print(f"📋 Subject:    {subject_cfg['name']} (Class {subject_cfg['class_level']})")
    print(f"📄 URL config: {urls_file} ({chapter_count} chapters)")
    print(f"🗄️  Dataset:    {dataset_id}\n")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        shutil.copy2(urls_file, tmp_path / urls_file.name)
        metadata = {
            "title": f"NIOS {subject_cfg['name']} Class {subject_cfg['class_level']} — Chapter URLs",
            "id": dataset_id,
            "licenses": [{"name": "other"}],
        }
        slug = _stage_and_upload(tmp_path, dataset_id, metadata, args)

    print(f"\n   In your Kaggle notebook:")
    print(f"   1. Add dataset '{dataset_id}' as input")
    print(f"   2. Set SUBJECT = \"{args.subject}\" in the config cell")
    print(f"   3. Input path: /kaggle/input/{slug}/{args.subject}.json")


def _upload_pdfs(args, subject_cfg):
    """Upload raw chapter PDFs (fallback if NIOS blocks Kaggle downloads)."""
    pdf_dir = subject_cfg["pdf_dir"]
    if not pdf_dir.exists():
        print(f"❌ PDF directory not found: {pdf_dir}")
        sys.exit(1)

    pdfs = sorted(pdf_dir.glob("*.pdf"))
    if not pdfs:
        print(f"❌ No PDF files found in: {pdf_dir}")
        sys.exit(1)

    slug = args.dataset_slug or f"nios-{args.subject}-pdfs"
    dataset_id = f"{args.username}/{slug}"

    print(f"📋 Subject:    {subject_cfg['name']} (Class {subject_cfg['class_level']})")
    print(f"📂 Source:     {pdf_dir}")
    print(f"📄 PDFs found: {len(pdfs)}")
    print(f"🗄️  Dataset:    {dataset_id}\n")
    for pdf in pdfs:
        print(f"  📄 {pdf.name} ({pdf.stat().st_size / 1024:.0f} KB)")
    print()

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        for pdf in pdfs:
            shutil.copy2(pdf, tmp_path / pdf.name)
        metadata = {
            "title": f"NIOS {subject_cfg['name']} Class {subject_cfg['class_level']} PDFs",
            "id": dataset_id,
            "licenses": [{"name": "other"}],
        }
        slug = _stage_and_upload(tmp_path, dataset_id, metadata, args)

    print(f"\n   In your Kaggle notebook, add this dataset as input:")
    print(f"   Input path: /kaggle/input/{slug}/")


if __name__ == "__main__":
    main()
