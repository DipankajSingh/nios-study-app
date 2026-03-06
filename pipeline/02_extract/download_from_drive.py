#!/usr/bin/env python3
"""
Stage 2b — Download Extracted Content from Google Drive

Downloads the Colab-extracted markdown+images from Google Drive into
the local pipeline/output/extracted/<subject>/ directory so that
Stage 3 (structure_content.py) can process them.

Drive structure (created by the Colab notebook):
  NIOS Backup / Extracted / Class 12 / Mathematics (311) /
    ├── Chapter 1/
    │   ├── Chapter 1.md
    │   ├── Chapter 1_tables.json
    │   └── images/
    │       ├── img_0001.png
    │       └── table_0001.png
    ├── Chapter 2/ ...
    ├── _manifest.json
    └── _extraction_checkpoint.json

Usage:
    cd pipeline
    python -m 02_extract.download_from_drive --subject maths-12
    python -m 02_extract.download_from_drive --subject maths-12 --resume
"""

import argparse
import io
import json
import os
import sys
import time
from pathlib import Path

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

# Add parent to path so we can import config
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import (
    CREDENTIALS_FILE,
    TOKEN_FILE,
    EXTRACTED_DIR,
    SUBJECTS,
    PIPELINE_DIR,
    ensure_dirs,
)

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
# Separate token file so we don't clobber the scraper's drive.file token
DOWNLOAD_TOKEN_FILE = PIPELINE_DIR / "token_readonly.json"

# ── Google Drive auth ────────────────────────────────────────────────────────

def get_drive_service():
    """Authenticate and return a Google Drive API service."""
    creds = None
    if DOWNLOAD_TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(DOWNLOAD_TOKEN_FILE), SCOPES)
        # If existing token doesn't cover our required scopes, re-auth
        if creds and not set(SCOPES).issubset(set(creds.scopes or [])):
            print("⚠️  Existing token missing required scopes, re-authenticating...")
            creds = None
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"⚠️  Token refresh failed: {e}. Re-authenticating...")
                DOWNLOAD_TOKEN_FILE.unlink(missing_ok=True)
                return get_drive_service()
        else:
            if not CREDENTIALS_FILE.exists():
                print(f"❌ credentials.json not found at {CREDENTIALS_FILE}")
                print("   Get it from Google Cloud Console → APIs & Services → Credentials")
                sys.exit(1)
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)
        with open(DOWNLOAD_TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
    return build("drive", "v3", credentials=creds)


# ── Drive helpers ────────────────────────────────────────────────────────────

def find_folder_by_path(service, path_parts: list[str]) -> str | None:
    """
    Walk the Drive folder tree to find a folder by path.
    e.g. ["NIOS Backup", "Extracted", "Class 12", "Mathematics (311)"]
    Returns the folder ID or None.
    """
    parent_id = "root"
    for part in path_parts:
        query = (
            f"mimeType='application/vnd.google-apps.folder' "
            f"and name='{part}' "
            f"and '{parent_id}' in parents "
            f"and trashed=false"
        )
        resp = service.files().list(q=query, fields="files(id, name)", pageSize=10).execute()
        files = resp.get("files", [])
        if not files:
            return None
        parent_id = files[0]["id"]
    return parent_id


def list_children(service, folder_id: str) -> list[dict]:
    """List all non-trashed children (files and folders) in a Drive folder."""
    items = []
    page_token = None
    while True:
        resp = service.files().list(
            q=f"'{folder_id}' in parents and trashed=false",
            fields="nextPageToken, files(id, name, mimeType, size)",
            pageSize=200,
            pageToken=page_token,
        ).execute()
        items.extend(resp.get("files", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return items


def download_file(service, file_id: str, dest_path: Path):
    """Download a file from Drive to a local path."""
    request = service.files().get_media(fileId=file_id)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(dest_path, "wb") as f:
        downloader = MediaIoBaseDownload(f, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()


def download_folder_recursive(
    service,
    folder_id: str,
    local_dir: Path,
    done_files: set[str],
    stats: dict,
    depth: int = 0,
):
    """Recursively download a Drive folder to a local directory."""
    local_dir.mkdir(parents=True, exist_ok=True)
    children = list_children(service, folder_id)

    for child in children:
        name = child["name"]
        child_id = child["id"]
        is_folder = child["mimeType"] == "application/vnd.google-apps.folder"

        if is_folder:
            download_folder_recursive(
                service, child_id, local_dir / name, done_files, stats, depth + 1
            )
        else:
            rel_path = str(local_dir / name)
            if rel_path in done_files:
                stats["skipped"] += 1
                continue

            local_path = local_dir / name
            # Skip if file already exists locally (resume mode)
            if local_path.exists():
                done_files.add(rel_path)
                stats["skipped"] += 1
                continue

            indent = "  " * (depth + 1)
            size_kb = int(child.get("size", 0)) / 1024
            print(f"{indent}📥 {name} ({size_kb:.1f} KB)")
            try:
                download_file(service, child_id, local_path)
                done_files.add(rel_path)
                stats["downloaded"] += 1
                stats["bytes"] += int(child.get("size", 0))
            except Exception as e:
                print(f"{indent}❌ Failed: {e}")
                stats["failed"] += 1
            # Gentle rate limit
            time.sleep(0.1)


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Download Colab-extracted content from Google Drive"
    )
    parser.add_argument("--subject", required=True, help="Subject ID, e.g. maths-12")
    parser.add_argument("--resume", action="store_true",
                        help="Skip files already downloaded (based on size match)")
    parser.add_argument("--drive-root", default="NIOS Backup",
                        help="Root folder name in Drive (default: 'NIOS Backup')")
    args = parser.parse_args()

    ensure_dirs()

    if args.subject not in SUBJECTS:
        print(f"❌ Unknown subject '{args.subject}'. Known: {list(SUBJECTS.keys())}")
        sys.exit(1)

    subject_cfg = SUBJECTS[args.subject]
    class_name = f"Class {subject_cfg['class_level']}"
    subject_folder = f"{subject_cfg['name']} ({subject_cfg['code']})"

    # Drive path: NIOS Backup / Extracted / Class 12 / Mathematics (311)
    drive_path = [args.drive_root, "Extracted", class_name, subject_folder]
    local_output = EXTRACTED_DIR / args.subject

    print(f"🔑 Authenticating with Google Drive...")
    service = get_drive_service()

    print(f"🔍 Looking for: {' / '.join(drive_path)}")
    folder_id = find_folder_by_path(service, drive_path)

    if not folder_id:
        print(f"\n❌ Folder not found in Drive!")
        print(f"   Expected path: {' / '.join(drive_path)}")
        print(f"\n   Checking what exists under '{args.drive_root}'...")

        # Help debug by showing what's available
        root_id = find_folder_by_path(service, [args.drive_root])
        if not root_id:
            print(f"   '{args.drive_root}' folder not found in Drive at all.")
        else:
            children = list_children(service, root_id)
            print(f"   Contents of '{args.drive_root}':")
            for c in sorted(children, key=lambda x: x["name"]):
                icon = "📁" if c["mimeType"] == "application/vnd.google-apps.folder" else "📄"
                print(f"     {icon} {c['name']}")

            # Check Extracted subfolder
            extracted_id = find_folder_by_path(service, [args.drive_root, "Extracted"])
            if extracted_id:
                children = list_children(service, extracted_id)
                print(f"\n   Contents of '{args.drive_root}/Extracted':")
                for c in sorted(children, key=lambda x: x["name"]):
                    icon = "📁" if c["mimeType"] == "application/vnd.google-apps.folder" else "📄"
                    print(f"     {icon} {c['name']}")
        sys.exit(1)

    # List chapters in the subject folder
    children = list_children(service, folder_id)
    folders = [c for c in children if c["mimeType"] == "application/vnd.google-apps.folder"]
    files = [c for c in children if c["mimeType"] != "application/vnd.google-apps.folder"]

    print(f"\n📚 Found in Drive:")
    print(f"   📁 {len(folders)} chapter folders")
    print(f"   📄 {len(files)} top-level files ({', '.join(f['name'] for f in files)})")
    print(f"\n📂 Downloading to: {local_output}\n")

    stats = {"downloaded": 0, "skipped": 0, "failed": 0, "bytes": 0}
    done_files: set[str] = set()

    # Download top-level files first (manifest, checkpoint)
    for f in files:
        local_path = local_output / f["name"]
        if args.resume and local_path.exists():
            stats["skipped"] += 1
            continue
        print(f"  📥 {f['name']}")
        download_file(service, f["id"], local_path)
        stats["downloaded"] += 1
        stats["bytes"] += int(f.get("size", 0))

    # Download each chapter folder
    for folder in sorted(folders, key=lambda f: f["name"]):
        print(f"\n  📖 {folder['name']}/")
        download_folder_recursive(
            service,
            folder["id"],
            local_output / folder["name"],
            done_files,
            stats,
            depth=1,
        )

    # Summary
    mb = stats["bytes"] / (1024 * 1024)
    print(f"\n{'='*60}")
    print(f"✅ Download complete!")
    print(f"   📥 Downloaded: {stats['downloaded']} files ({mb:.1f} MB)")
    if stats["skipped"]:
        print(f"   ⏭️  Skipped:    {stats['skipped']} files (already exist)")
    if stats["failed"]:
        print(f"   ❌ Failed:     {stats['failed']} files")
    print(f"   📂 Output:     {local_output}")
    print(f"{'='*60}")

    # Verify we can find markdown files
    md_files = sorted(local_output.rglob("*.md"))
    if md_files:
        print(f"\n📄 Found {len(md_files)} markdown files ready for Stage 3:")
        for md in md_files[:5]:
            print(f"   {md.relative_to(local_output)}")
        if len(md_files) > 5:
            print(f"   ... and {len(md_files) - 5} more")
        print(f"\nNext step:")
        print(f"   python -m 03_structure.structure_content --subject {args.subject}")
    else:
        print(f"\n⚠️  No .md files found — extraction may still be running in Colab.")


if __name__ == "__main__":
    main()
