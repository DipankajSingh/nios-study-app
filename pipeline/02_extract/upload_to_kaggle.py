#!/usr/bin/env python3
"""
Stage 2c — Upload Chapter URLs config (or PDFs) to a Kaggle Dataset

Two upload modes:

  --urls-only  (default / recommended)
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
    python 02_extract/upload_to_kaggle.py --subject maths-12 --username <you> --urls-only

    # Fallback — upload the raw PDFs:
    python 02_extract/upload_to_kaggle.py --subject maths-12 --username <you> --pdfs

After the upload, open extract_pdf_kaggle.ipynb on Kaggle and add the
dataset as input, then run the notebook.
"""

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import SUBJECTS, ensure_dirs

URLS_DIR = Path(__file__).resolve().parent / "chapter_urls"


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


# ── Helpers ───────────────────────────────────────────────────────────────────

def dataset_exists(api, dataset_id: str) -> bool:
    """Return True if the Kaggle dataset already exists."""
    try:
        api.dataset_list_files(dataset_id)
        return True
    except Exception:
        return False


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Upload chapter URL config (or PDFs) to a Kaggle dataset"
    )
    parser.add_argument("--subject", required=True, help="Subject ID, e.g. maths-12")
    parser.add_argument("--username", required=True, help="Your Kaggle username")
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

    # --pdfs overrides the default --urls-only
    upload_pdfs = args.pdfs

    ensure_dirs()

    if args.subject not in SUBJECTS:
        print(f"❌ Unknown subject '{args.subject}'. Known: {list(SUBJECTS.keys())}")
        sys.exit(1)

    subject_cfg = SUBJECTS[args.subject]

    if upload_pdfs:
        _upload_pdfs(args, subject_cfg)
    else:
        _upload_urls(args, subject_cfg)


def _upload_urls(args, subject_cfg):
    """Upload the small chapter_urls/<subject>.json config file."""
    urls_file = URLS_DIR / f"{args.subject}.json"
    if not urls_file.exists():
        print(f"❌ URL config not found: {urls_file}")
        print(f"   Run first: python 02_extract/generate_chapter_urls.py --subject {args.subject}")
        sys.exit(1)

    with open(urls_file) as f:
        url_data = json.load(f)
    chapter_count = len(url_data.get("chapters", []))

    slug = args.dataset_slug or f"nios-{args.subject}-urls"
    dataset_id = f"{args.username}/{slug}"

    print(f"📋 Subject:    {subject_cfg['name']} (Class {subject_cfg['class_level']})")
    print(f"📄 URL config: {urls_file} ({chapter_count} chapters)")
    print(f"🗄️  Dataset:    {dataset_id}\n")

    api = get_kaggle_api()

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        shutil.copy2(urls_file, tmp_path / urls_file.name)

        metadata = {
            "title": f"NIOS {subject_cfg['name']} Class {subject_cfg['class_level']} — Chapter URLs",
            "id": dataset_id,
            "licenses": [{"name": "other"}],
        }
        with open(tmp_path / "dataset-metadata.json", "w") as f:
            json.dump(metadata, f, indent=2)

        exists = dataset_exists(api, dataset_id)
        if exists:
            print(f"📤 Updating existing dataset: {dataset_id}")
            api.dataset_create_version(
                str(tmp_path),
                version_notes=args.version_notes,
                quiet=False,
                dir_mode="zip",
            )
        else:
            visibility = "public" if args.public else "private"
            print(f"📤 Creating new {visibility} dataset: {dataset_id}")
            api.dataset_create_new(
                str(tmp_path),
                public=args.public,
                quiet=False,
                dir_mode="zip",
            )

    print(f"\n✅ Done!")
    print(f"   Dataset URL: https://www.kaggle.com/datasets/{dataset_id}")
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
        size_kb = pdf.stat().st_size / 1024
        print(f"  📄 {pdf.name} ({size_kb:.0f} KB)")
    print()

    api = get_kaggle_api()

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        for pdf in pdfs:
            shutil.copy2(pdf, tmp_path / pdf.name)

        metadata = {
            "title": f"NIOS {subject_cfg['name']} Class {subject_cfg['class_level']} PDFs",
            "id": dataset_id,
            "licenses": [{"name": "other"}],
        }
        with open(tmp_path / "dataset-metadata.json", "w") as f:
            json.dump(metadata, f, indent=2)

        exists = dataset_exists(api, dataset_id)
        if exists:
            print(f"📤 Updating existing dataset: {dataset_id}")
            api.dataset_create_version(
                str(tmp_path),
                version_notes=args.version_notes,
                quiet=False,
                dir_mode="zip",
            )
        else:
            visibility = "public" if args.public else "private"
            print(f"📤 Creating new {visibility} dataset: {dataset_id}")
            api.dataset_create_new(
                str(tmp_path),
                public=args.public,
                quiet=False,
                dir_mode="zip",
            )

    print(f"\n✅ Done!")
    print(f"   Dataset URL: https://www.kaggle.com/datasets/{dataset_id}")
    print(f"\n   In your Kaggle notebook, add this dataset as input:")
    print(f"   Input path: /kaggle/input/{slug}/")


if __name__ == "__main__":
    main()
