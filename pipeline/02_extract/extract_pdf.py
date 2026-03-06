"""
Stage 2 — PDF Extraction (Google Colab)

Matches the Google Drive folder structure created by 01_scrape/scrape_nios.py:

  NIOS Backup/
    Class 12/
      Science/
        Mathematics (311)/
          Chapter 1.pdf
          Chapter 2.pdf
          ...
    Class 10/
      ...

Extracted output is saved to:

  NIOS Backup/
    Extracted/
      Class 12/
        Mathematics (311)/
          Chapter 1/
            Chapter 1.md          ← full markdown (text + LaTeX + table refs)
            Chapter 1_tables.json ← all tables as structured JSON
            images/
              img_0001.png        ← figures, graphs, diagrams
              img_0002.png
          Chapter 2/
            ...
          _manifest.json
          _extraction_checkpoint.json

HOW TO USE:
  1. Open Google Colab → colab.research.google.com
  2. Create a new notebook
  3. Copy each CELL below into a separate Colab cell
  4. Edit CELL 2 to pick your class, stream, and subject
  5. Run all cells in order
"""

# ═══════════════════════════════════════════════════════════════════════════════
# CELL 1: Install & Mount
# ═══════════════════════════════════════════════════════════════════════════════
# --- Copy everything below into the FIRST Colab cell and run it ---
#
# !pip install -q "docling[vlm]" docling-core pydantic pillow pandas
#
# from google.colab import drive
# drive.mount('/content/drive')
# print("✅ Drive mounted")

# ═══════════════════════════════════════════════════════════════════════════════
# CELL 2: Configuration
# ═══════════════════════════════════════════════════════════════════════════════
# --- Copy everything below into the SECOND Colab cell ---

import os
import gc
import json
import re
import traceback
from pathlib import Path
from datetime import datetime, timezone

# ── Google Drive root ─────────────────────────────────────────────────────────
DRIVE_ROOT = Path("/content/drive/MyDrive")
NIOS_ROOT  = DRIVE_ROOT / "NIOS Backup"

# ── Pick what to extract ──────────────────────────────────────────────────────
# Change these to match what you scraped with scrape_nios.py
CLASS_NAME    = "Class 12"          # "Class 10" or "Class 12"
STREAM_NAME   = "Science"           # "Science", "Commerce", "Humanities", "Languages", "Vocational & Others"
SUBJECT_NAME  = "Mathematics (311)" # Exact folder name from Drive (e.g. "Physics (312)")

# ── Derived paths (match scraper's folder structure) ──────────────────────────
PDF_DIR    = NIOS_ROOT / CLASS_NAME / STREAM_NAME / SUBJECT_NAME
OUTPUT_DIR = NIOS_ROOT / "Extracted" / CLASS_NAME / SUBJECT_NAME

# ── Extract a subject ID for internal tracking ────────────────────────────────
# "Mathematics (311)" → "maths-12", "Physics (312)" → "physics-12"
_class_level = "12" if "12" in CLASS_NAME else "10"
_name_part = SUBJECT_NAME.split("(")[0].strip().lower().replace(" ", "-")
SUBJECT_ID = f"{_name_part}-{_class_level}"

print(f"📂 PDF source:   {PDF_DIR}")
print(f"📂 Output dir:   {OUTPUT_DIR}")
print(f"🏷️  Subject ID:   {SUBJECT_ID}")

# Verify the PDF folder exists
if PDF_DIR.exists():
    pdf_count = len(list(PDF_DIR.glob("*.pdf")))
    print(f"✅ Found {pdf_count} PDFs in source folder")
else:
    print(f"❌ PDF folder not found! Check CLASS_NAME / STREAM_NAME / SUBJECT_NAME")
    print(f"   Available folders in {NIOS_ROOT}:")
    if NIOS_ROOT.exists():
        for p in sorted(NIOS_ROOT.iterdir()):
            print(f"     {p.name}/")

# ═══════════════════════════════════════════════════════════════════════════════
# CELL 3: Extraction engine
# ═══════════════════════════════════════════════════════════════════════════════
# --- Copy everything below into the THIRD Colab cell ---

from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.pipeline_options import PdfPipelineOptions, TableFormerMode
from docling.datamodel.base_models import InputFormat
from docling_core.types.doc import ImageRefMode, PictureItem, TableItem


# ── Image filtering ───────────────────────────────────────────────────────────
# Skip small / decorative images (logos, icons, bullets, horizontal rules).
# Only keep images likely to be educational: diagrams, graphs, figures, charts.
MIN_IMAGE_WIDTH  = 150   # px — anything narrower is probably an icon/bullet
MIN_IMAGE_HEIGHT = 150   # px — anything shorter is probably a divider/logo
MIN_IMAGE_AREA   = 40000 # px² — catches small images that pass w/h individually
MAX_ASPECT_RATIO = 8.0   # skip extremely wide/tall strips (rules, banners)

def is_useful_image(pil_image) -> bool:
    """Return True if the image is large and proportioned enough to be educational content."""
    w, h = pil_image.size
    if w < MIN_IMAGE_WIDTH or h < MIN_IMAGE_HEIGHT:
        return False
    if w * h < MIN_IMAGE_AREA:
        return False
    ratio = max(w, h) / max(min(w, h), 1)
    if ratio > MAX_ASPECT_RATIO:
        return False
    return True


def build_converter():
    """
    Build a Docling converter with all extraction features enabled:
    - OCR for scanned pages
    - Formula enrichment (math → LaTeX)
    - Picture extraction (figures, graphs, diagrams)
    - Table structure recognition (TableFormer accurate mode)
    """
    pipeline_opts = PdfPipelineOptions()

    # ── Images & figures ──────────────────────────────────────────────────
    pipeline_opts.generate_picture_images = True      # extract figures/graphs as PNG
    pipeline_opts.generate_page_images = True         # needed for table image export via get_image()
    pipeline_opts.images_scale = 2.0                  # 2x resolution for clarity

    # ── Math formulas ─────────────────────────────────────────────────────
    pipeline_opts.do_formula_enrichment = True         # convert math to LaTeX

    # ── Tables ────────────────────────────────────────────────────────────
    pipeline_opts.do_table_structure = True             # detect table structure
    pipeline_opts.table_structure_options.mode = TableFormerMode.ACCURATE  # best quality

    # ── OCR (for scanned/image-based pages) ───────────────────────────────
    pipeline_opts.do_ocr = True                        # enable OCR fallback

    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_opts)
        }
    )
    return converter


def extract_chapter_number(filename: str) -> int | None:
    """Extract chapter number from 'Chapter 7.pdf' or 'Extra - ...' format."""
    m = re.match(r"Chapter\s+(\d+)", filename)
    if m:
        return int(m.group(1))
    return None


def extract_single_pdf(converter, pdf_path: Path, out_dir: Path) -> dict:
    """
    Extract one PDF → markdown + images + tables JSON.
    Returns chapter metadata dict.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    chapter_num = extract_chapter_number(pdf_path.name)
    stem = pdf_path.stem  # e.g. "Chapter 7"

    print(f"  🔄 Converting: {pdf_path.name} ...")
    conv_result = converter.convert(str(pdf_path))
    doc = conv_result.document

    # ── 1. Export full markdown with image references ─────────────────────
    # save_as_markdown writes the .md file and any referenced images beside it
    md_file = out_dir / f"{stem}.md"
    doc.save_as_markdown(md_file, image_mode=ImageRefMode.REFERENCED)
    md_text = md_file.read_text(encoding="utf-8")

    # Free the heavy conversion result early (keeps doc alive via local ref)
    del conv_result

    # ── 2. Extract and save images (figures, graphs, diagrams) ────────────
    img_dir = out_dir / "images"
    img_dir.mkdir(exist_ok=True)
    image_records = []

    # Use iterate_items() + isinstance checks (Docling v2.x API)
    picture_counter = 0
    table_counter = 0
    table_records = []

    skipped_images = 0

    for element, _level in doc.iterate_items():
        if isinstance(element, PictureItem):
            picture_counter += 1
            try:
                pil_image = element.get_image(doc)
                if pil_image is None:
                    continue

                # Filter out small / decorative images
                if not is_useful_image(pil_image):
                    skipped_images += 1
                    continue

                img_filename = f"img_{picture_counter:04d}.png"
                img_path = img_dir / img_filename
                with img_path.open("wb") as fp:
                    pil_image.save(fp, "PNG")
                image_records.append({
                    "filename": img_filename,
                    "type": "picture",
                    "size": list(pil_image.size),  # [width, height]
                    "element_id": str(getattr(element, "self_ref", picture_counter)),
                })
            except Exception as e:
                print(f"    ⚠️  Failed to save picture {picture_counter}: {e}")

        elif isinstance(element, TableItem):
            table_counter += 1
            table_data = {
                "table_index": table_counter - 1,
                "element_id": str(getattr(element, "self_ref", table_counter)),
            }

            # Try to get table as pandas DataFrame → list of dicts
            try:
                df = element.export_to_dataframe(doc=doc)
                table_data["headers"] = list(df.columns)
                table_data["rows"] = df.values.tolist()
                table_data["row_count"] = len(df)
                table_data["col_count"] = len(df.columns)
            except Exception:
                # Fallback: export as HTML snippet
                try:
                    table_data["html"] = element.export_to_html(doc=doc)
                except Exception:
                    table_data["html"] = "(table extraction failed)"

            # Save table as image via get_image() (requires generate_page_images=True)
            try:
                tbl_image = element.get_image(doc)
                if tbl_image is not None:
                    tbl_img_name = f"table_{table_counter:04d}.png"
                    with (img_dir / tbl_img_name).open("wb") as fp:
                        tbl_image.save(fp, "PNG")
                    table_data["image"] = tbl_img_name
                    image_records.append({
                        "filename": tbl_img_name,
                        "type": "table",
                        "element_id": str(getattr(element, "self_ref", table_counter)),
                    })
            except Exception:
                pass

            table_records.append(table_data)

    # Save tables JSON if any
    if table_records:
        tables_file = out_dir / f"{stem}_tables.json"
        tables_file.write_text(
            json.dumps(table_records, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )

    # ── 4. Clean up empty image dir ───────────────────────────────────────
    if not image_records and img_dir.exists():
        try:
            img_dir.rmdir()  # only removes if empty
        except OSError:
            pass

    # ── Summary ───────────────────────────────────────────────────────────
    print(
        f"  ✅ {pdf_path.name} → "
        f"{len(md_text):,} chars, "
        f"{len(image_records)} images ({skipped_images} small skipped), "
        f"{len(table_records)} tables"
    )

    # Free the document object (page images, OCR data, etc.)
    del doc
    gc.collect()

    return {
        "source_pdf": pdf_path.name,
        "chapter_number": chapter_num,
        "markdown_file": f"{stem}/{stem}.md",
        "markdown_chars": len(md_text),
        "images": image_records,
        "tables_count": len(table_records),
    }


def extract_subject(pdf_dir: Path, output_dir: Path) -> dict:
    """
    Extract all PDFs for a subject. Checkpoints after each PDF so you can
    resume if Colab disconnects.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # ── Load checkpoint ───────────────────────────────────────────────────
    checkpoint_file = output_dir / "_extraction_checkpoint.json"
    done_files: set[str] = set()
    if checkpoint_file.exists():
        ckpt = json.loads(checkpoint_file.read_text())
        done_files = set(ckpt.get("done_files", []))
        print(f"  ♻️  Resuming: {len(done_files)} already extracted")

    # ── Discover PDFs ─────────────────────────────────────────────────────
    pdf_files = sorted(pdf_dir.glob("*.pdf"),
                       key=lambda p: extract_chapter_number(p.name) or 999)
    if not pdf_files:
        print(f"  ❌ No PDFs found in {pdf_dir}")
        return {}

    remaining = [p for p in pdf_files if p.name not in done_files]
    print(f"  📚 {len(pdf_files)} PDFs total, {len(done_files)} done, {len(remaining)} to go\n")

    if not remaining:
        print("  ✅ All PDFs already extracted!")
        # Still re-generate manifest
    else:
        # Build converter once — reuse for all PDFs
        print("  🔧 Building Docling converter (this takes ~30s first time) ...")
        converter = build_converter()

        # ── Process each PDF ──────────────────────────────────────────────
        for idx, pdf_path in enumerate(remaining, 1):
            chapter_dir = output_dir / pdf_path.stem
            print(f"\n  [{idx}/{len(remaining)}]")
            try:
                extract_single_pdf(converter, pdf_path, chapter_dir)

                # Checkpoint
                done_files.add(pdf_path.name)
                checkpoint_file.write_text(json.dumps({
                    "subject_id": SUBJECT_ID,
                    "done_files": sorted(done_files),
                    "last_updated": datetime.now(timezone.utc).isoformat(),
                }, indent=2))

            except Exception as e:
                print(f"  ❌ FAILED: {pdf_path.name}")
                traceback.print_exc()
                continue

    # ── Write / update manifest ───────────────────────────────────────────
    # Re-scan output dir for the final manifest (covers resumed runs too)
    all_chapters = []
    for pdf_path in pdf_files:
        chapter_dir = output_dir / pdf_path.stem
        md_file = chapter_dir / f"{pdf_path.stem}.md"
        if not md_file.exists():
            continue

        chapter_num = extract_chapter_number(pdf_path.name)
        md_chars = md_file.stat().st_size

        # Count images
        img_dir = chapter_dir / "images"
        img_count = len(list(img_dir.glob("*.png"))) if img_dir.exists() else 0

        # Count tables
        tables_file = chapter_dir / f"{pdf_path.stem}_tables.json"
        tbl_count = 0
        if tables_file.exists():
            try:
                tbl_count = len(json.loads(tables_file.read_text()))
            except Exception:
                pass

        all_chapters.append({
            "source_pdf": pdf_path.name,
            "chapter_number": chapter_num,
            "markdown_file": f"{pdf_path.stem}/{pdf_path.stem}.md",
            "markdown_chars": md_chars,
            "image_count": img_count,
            "tables_count": tbl_count,
        })

    manifest = {
        "subject_id": SUBJECT_ID,
        "subject_name": SUBJECT_NAME,
        "class_name": CLASS_NAME,
        "stream": STREAM_NAME,
        "extracted_at": datetime.now(timezone.utc).isoformat(),
        "total_pdfs": len(pdf_files),
        "extracted_pdfs": len(done_files),
        "total_images": sum(c["image_count"] for c in all_chapters),
        "total_tables": sum(c["tables_count"] for c in all_chapters),
        "chapters": sorted(all_chapters, key=lambda c: c.get("chapter_number") or 999),
    }

    manifest_file = output_dir / "_manifest.json"
    manifest_file.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"\n{'='*60}")
    print(f"🎉 Extraction complete for {SUBJECT_NAME}!")
    print(f"   📄 {manifest['extracted_pdfs']}/{manifest['total_pdfs']} PDFs extracted")
    print(f"   🖼️  {manifest['total_images']} images saved")
    print(f"   📊 {manifest['total_tables']} tables extracted")
    print(f"   📋 Manifest: {manifest_file}")
    print(f"{'='*60}")

    return manifest


# ── Run ───────────────────────────────────────────────────────────────────────
manifest = extract_subject(PDF_DIR, OUTPUT_DIR)

# ═══════════════════════════════════════════════════════════════════════════════
# CELL 4 (Optional): Download extracted output as ZIP
# ═══════════════════════════════════════════════════════════════════════════════
# --- Useful if you want a local copy instead of accessing via Drive ---
#
# import shutil
# from google.colab import files
#
# zip_name = f"extracted_{SUBJECT_ID}"
# zip_path = shutil.make_archive(f"/content/{zip_name}", "zip", str(OUTPUT_DIR))
# files.download(zip_path)
# print(f"📦 Downloading {zip_name}.zip ({os.path.getsize(zip_path)/1024/1024:.1f} MB)")

# ═══════════════════════════════════════════════════════════════════════════════
# CELL 5 (Optional): Quick preview of one chapter's output
# ═══════════════════════════════════════════════════════════════════════════════
# --- Run this to peek at what was extracted ---
#
# preview_chapter = "Chapter 1"  # change as needed
# preview_dir = OUTPUT_DIR / preview_chapter
# if preview_dir.exists():
#     md_file = preview_dir / f"{preview_chapter}.md"
#     if md_file.exists():
#         text = md_file.read_text()
#         print(f"--- {preview_chapter} ({len(text):,} chars) ---")
#         print(text[:3000])
#         print(f"\n... ({len(text):,} total chars)")
#
#     tables_file = preview_dir / f"{preview_chapter}_tables.json"
#     if tables_file.exists():
#         tables = json.loads(tables_file.read_text())
#         print(f"\n--- {len(tables)} tables found ---")
#         for t in tables[:2]:
#             print(json.dumps(t, indent=2)[:500])
#
#     img_dir = preview_dir / "images"
#     if img_dir.exists():
#         imgs = list(img_dir.glob("*.png"))
#         print(f"\n--- {len(imgs)} images ---")
#         if imgs:
#             from IPython.display import display, Image
#             display(Image(filename=str(imgs[0]), width=400))
# else:
#     print(f"❌ {preview_chapter} not found. Available:")
#     for d in sorted(OUTPUT_DIR.iterdir()):
#         if d.is_dir() and not d.name.startswith("_"):
#             print(f"  {d.name}/")
