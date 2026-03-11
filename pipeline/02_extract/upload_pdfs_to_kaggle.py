#!/usr/bin/env python3
"""
Stage 2b → Kaggle — Upload all chapter PDFs as a single Kaggle Dataset

Packs every subject's chapters into one dataset (nios-chapter-pdfs) with
the folder layout:
    class10/<subject-id>/Chapter 1.pdf ...
    class12/<subject-id>/Chapter 1.pdf ...

The Kaggle extraction notebook mounts this one dataset and picks the
subject folder it needs.

Usage:
    cd pipeline
    python 02_extract/upload_pdfs_to_kaggle.py           # all downloaded subjects
    python 02_extract/upload_pdfs_to_kaggle.py --class 12
    python 02_extract/upload_pdfs_to_kaggle.py --subject maths-12
    python 02_extract/upload_pdfs_to_kaggle.py --public   # make dataset public
    python 02_extract/upload_pdfs_to_kaggle.py --setup-creds  # write kaggle.json

Authentication:
    Add KAGGLE_USERNAME and KAGGLE_API_TOKEN to pipeline/.env
"""

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import PDF_OUTPUT_ROOT, KAGGLE_USERNAME, SUBJECTS

# Resolve kaggle CLI relative to the running Python (works inside a venv)
_KAGGLE_BIN = str(Path(sys.executable).parent / "kaggle")

DATASET_SLUG = "nios-chapter-pdfs"


def check_kaggle_cli() -> None:
    result = subprocess.run([_KAGGLE_BIN, "--version"], capture_output=True)
    if result.returncode != 0:
        print("❌ kaggle CLI not found.  Run: pip install kaggle")
        sys.exit(1)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _dataset_exists(dataset_id: str) -> bool:
    result = subprocess.run(
        [_KAGGLE_BIN, "datasets", "files", dataset_id],
        capture_output=True,
    )
    return result.returncode == 0


def _kaggle_upload(staging_dir: Path, dataset_id: str, version_notes: str, is_new: bool, public: bool) -> None:
    if is_new:
        cmd = [_KAGGLE_BIN, "datasets", "create", "-p", str(staging_dir), "--dir-mode", "zip"]
        if public:
            cmd.append("--public")
        action = f"Creating {'public' if public else 'private'}"
    else:
        cmd = [_KAGGLE_BIN, "datasets", "version", "-p", str(staging_dir), "-m", version_notes, "--dir-mode", "zip"]
        action = "Updating"

    print(f"📤 {action} dataset: {dataset_id}")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print("❌ kaggle CLI returned a non-zero exit code.")
        sys.exit(result.returncode)


def _subjects_for_class(class_level: str) -> list[str]:
    return [sid for sid, cfg in SUBJECTS.items() if cfg["class_level"] == class_level]


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Upload all NIOS chapter PDFs as a single Kaggle dataset.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    filter_group = parser.add_mutually_exclusive_group()
    filter_group.add_argument("--subject", metavar="ID", help="Include only this subject, e.g. maths-12")
    filter_group.add_argument("--class", dest="class_level", choices=["10", "12"], metavar="{10,12}",
                              help="Include only subjects of this class level")

    parser.add_argument("--username", default=KAGGLE_USERNAME or None,
                        help="Kaggle username (default: KAGGLE_USERNAME from .env)")
    parser.add_argument("--public", action="store_true", help="Make dataset public (default: private)")
    parser.add_argument("--version-notes", default="Update chapter PDFs",
                        help="Version notes when updating an existing dataset")
    args = parser.parse_args()

    if not args.username:
        print("❌ Kaggle username not set.")
        print("   Add KAGGLE_USERNAME=<you> to pipeline/.env, or pass --username <you>")
        sys.exit(1)

    check_kaggle_cli()

    # ── Resolve which subjects to include ────────────────────────────────────
    if args.subject:
        if args.subject not in SUBJECTS:
            print(f"❌ Unknown subject '{args.subject}'. Known: {', '.join(SUBJECTS)}")
            sys.exit(1)
        subjects = [args.subject]
    elif args.class_level:
        subjects = _subjects_for_class(args.class_level)
    else:
        # Default: all subjects that have PDFs on disk
        subjects = [
            sid for sid in SUBJECTS
            if (PDF_OUTPUT_ROOT / f"class{SUBJECTS[sid]['class_level']}" / sid / "chapters").exists()
        ]

    if not subjects:
        print("❌ No downloaded subjects found. Run download_chapters_local.py first.")
        sys.exit(1)

    # ── Build staging directory ───────────────────────────────────────────────
    dataset_id = f"{args.username}/{DATASET_SLUG}"
    print(f"\n🗄️  Dataset: {dataset_id}")
    print(f"📦 Including {len(subjects)} subject(s):\n")

    total_pdfs = 0
    total_mb = 0.0
    missing = []

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        for sid in subjects:
            cfg = SUBJECTS[sid]
            class_level = cfg["class_level"]
            chapters_dir = PDF_OUTPUT_ROOT / f"class{class_level}" / sid / "chapters"

            if not chapters_dir.exists():
                print(f"  ⚠️  Skipping {sid} — chapters directory not found")
                missing.append(sid)
                continue

            pdfs = sorted(chapters_dir.glob("*.pdf"))
            if not pdfs:
                print(f"  ⚠️  Skipping {sid} — no PDFs found")
                missing.append(sid)
                continue

            # Mirror the local layout:  class<level>/<subject-id>/
            dest = tmp_path / f"class{class_level}" / sid
            dest.mkdir(parents=True, exist_ok=True)
            for pdf in pdfs:
                shutil.copy2(pdf, dest / pdf.name)

            # Copy manifest alongside subject folder
            manifest_src = chapters_dir.parent / "_manifest.json"
            if manifest_src.exists():
                shutil.copy2(manifest_src, dest / "_manifest.json")

            count = len(pdfs)
            size_mb = sum(p.stat().st_size for p in pdfs) / 1_048_576
            total_pdfs += count
            total_mb += size_mb
            print(f"  ✅ {cfg['name']} Class {class_level} ({sid}) — {count} PDFs  ({size_mb:.1f} MB)")

        if not total_pdfs:
            print("\n❌ Nothing to upload.")
            sys.exit(1)

        print(f"\n  Total: {total_pdfs} PDFs  ({total_mb:.1f} MB)")
        if missing:
            print(f"  Skipped: {', '.join(missing)}")

        # Write dataset-metadata.json
        subjects_list = ", ".join(
            f"{SUBJECTS[s]['name']} (Class {SUBJECTS[s]['class_level']})"
            for s in subjects if s not in missing
        )
        metadata = {
            "title": "NIOS Chapter PDFs — Class 10 & 12",
            "id": dataset_id,
            "licenses": [{"name": "other"}],
            "subtitle": "NIOS Class 10 & 12 chapter PDFs from nios.ac.in",
            "description": (
                "## NIOS Chapter PDFs\n\n"
                "Chapter-wise PDF textbooks published by the **National Institute of Open Schooling (NIOS)**, "
                "India, downloaded from [nios.ac.in](https://nios.ac.in).\n\n"
                "### Subjects included\n"
                f"{subjects_list}\n\n"
                f"**Total:** {total_pdfs} PDFs across {len(subjects) - len(missing)} subjects\n\n"
                "### Folder layout\n"
                "```\n"
                "class10/<subject-id>/Chapter N.pdf\n"
                "class12/<subject-id>/Chapter N.pdf\n"
                "```\n"
                "Each subject folder also contains a `_manifest.json` with chapter titles and source URLs.\n\n"
                "### Usage\n"
                "Add this dataset as input to a Kaggle notebook. PDFs are available at:\n"
                "`/kaggle/input/nios-chapter-pdfs/class10/<subject>/` or `class12/<subject>/`\n\n"
                "### Source\n"
                "All content is © NIOS (National Institute of Open Schooling), Government of India. "
                "This dataset is for educational and research use only."
            ),
            "keywords": ["education", "india"],
        }
        with open(tmp_path / "dataset-metadata.json", "w") as fh:
            json.dump(metadata, fh, indent=2)

        print()
        is_new = not _dataset_exists(dataset_id)
        _kaggle_upload(tmp_path, dataset_id, args.version_notes, is_new, args.public)

    print(f"\n✅ Done: https://www.kaggle.com/datasets/{dataset_id}")
    print(f"\n   In your Kaggle notebook, the PDFs will be at:")
    print(f"   /kaggle/input/{DATASET_SLUG}/class10/<subject>/")
    print(f"   /kaggle/input/{DATASET_SLUG}/class12/<subject>/")


if __name__ == "__main__":
    main()
