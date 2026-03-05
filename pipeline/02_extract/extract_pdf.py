"""
Stage 2 — PDF Extraction (Google Colab)

HOW TO USE:
  1. Open Google Colab (colab.research.google.com)
  2. Upload this file OR copy each cell block into a Colab notebook
  3. Make sure your PDFs are in Google Drive at:
       My Drive / nios-study-app / content / class12 / <subject> / pdfs /
  4. Run the cells in order

The script extracts text, LaTeX math, and images from NIOS PDFs using Docling,
then saves structured markdown back to Google Drive.
"""

# ═══════════════════════════════════════════════════════════════════════════════
# CELL 1: Install & Mount
# ═══════════════════════════════════════════════════════════════════════════════
# !pip install -q "docling[vlm]" pydantic
#
# from google.colab import drive
# drive.mount('/content/drive')

# ═══════════════════════════════════════════════════════════════════════════════
# CELL 2: Configuration
# ═══════════════════════════════════════════════════════════════════════════════

import os
import json
from pathlib import Path
from datetime import datetime, timezone

DRIVE_BASE = Path("/content/drive/MyDrive/nios-study-app")

# Subject to process — change this for each subject
SUBJECT_ID    = "maths-12"
CLASS_LEVEL   = "12"
SUBJECT_CODE  = "311"
SUBJECT_NAME  = "Mathematics"

PDF_DIR    = DRIVE_BASE / "content" / f"class{CLASS_LEVEL}" / SUBJECT_ID / "pdfs"
OUTPUT_DIR = DRIVE_BASE / "pipeline_output" / "extracted" / SUBJECT_ID

print(f"PDF source:  {PDF_DIR}")
print(f"Output dir:  {OUTPUT_DIR}")

# ═══════════════════════════════════════════════════════════════════════════════
# CELL 3: Extract all PDFs for the subject
# ═══════════════════════════════════════════════════════════════════════════════

from docling.document_converter import DocumentConverter
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.datamodel.base_models import InputFormat


def extract_single_pdf(pdf_path: Path, out_dir: Path) -> dict:
    """Extract one PDF → markdown + images. Returns chapter metadata."""
    out_dir.mkdir(parents=True, exist_ok=True)

    pipeline_options = PdfPipelineOptions()
    pipeline_options.generate_picture_images = True
    pipeline_options.do_formula_enrichment = True  # Math → LaTeX

    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfPipelineOptions(pipeline_options=pipeline_options)
        }
    )

    print(f"  🔄 Processing: {pdf_path.name}")
    result = converter.convert(str(pdf_path))

    # Save markdown
    md_text = result.document.export_to_markdown()
    md_file = out_dir / (pdf_path.stem + ".md")
    md_file.write_text(md_text, encoding="utf-8")

    # Save images
    img_dir = out_dir / "images"
    img_dir.mkdir(exist_ok=True)
    image_paths = []
    for element in result.document.pictures:
        if element.image:
            img_path = img_dir / f"img_{element.id}.png"
            element.image.save(str(img_path))
            image_paths.append(str(img_path))

    print(f"  ✅ {pdf_path.name} → {len(md_text)} chars, {len(image_paths)} images")

    return {
        "source_pdf": pdf_path.name,
        "markdown_file": str(md_file),
        "markdown_length": len(md_text),
        "image_count": len(image_paths),
        "image_paths": image_paths,
    }


def extract_subject(pdf_dir: Path, output_dir: Path, subject_id: str) -> dict:
    """Extract all PDFs for a subject. Skips already-extracted files."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load checkpoint if exists
    checkpoint_file = output_dir / "_extraction_checkpoint.json"
    done_files = set()
    if checkpoint_file.exists():
        checkpoint = json.loads(checkpoint_file.read_text())
        done_files = set(checkpoint.get("done_files", []))
        print(f"  ♻️  Resuming: {len(done_files)} already extracted")

    pdf_files = sorted(pdf_dir.glob("*.pdf"))
    if not pdf_files:
        print(f"  ❌ No PDFs found in {pdf_dir}")
        return {}

    print(f"  📚 Found {len(pdf_files)} PDFs, {len(done_files)} already done")

    results = []
    for pdf_path in pdf_files:
        if pdf_path.name in done_files:
            print(f"  ⏭️  Skipping (already done): {pdf_path.name}")
            continue

        chapter_dir = output_dir / pdf_path.stem
        try:
            result = extract_single_pdf(pdf_path, chapter_dir)
            results.append(result)

            # Save checkpoint after each successful extraction
            done_files.add(pdf_path.name)
            checkpoint_file.write_text(json.dumps({
                "subject_id": subject_id,
                "done_files": list(done_files),
                "last_updated": datetime.now(timezone.utc).isoformat(),
            }, indent=2))

        except Exception as e:
            print(f"  ❌ FAILED: {pdf_path.name}: {e}")
            continue

    # Write manifest
    manifest = {
        "subject_id": subject_id,
        "subject_name": SUBJECT_NAME,
        "class_level": CLASS_LEVEL,
        "code": SUBJECT_CODE,
        "extracted_at": datetime.now(timezone.utc).isoformat(),
        "total_pdfs": len(pdf_files),
        "extracted_pdfs": len(done_files),
        "chapters": results,
    }
    manifest_file = output_dir / "_manifest.json"
    manifest_file.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"\n🎉 Extraction complete! Manifest: {manifest_file}")
    return manifest


# Run extraction
manifest = extract_subject(PDF_DIR, OUTPUT_DIR, SUBJECT_ID)

# ═══════════════════════════════════════════════════════════════════════════════
# CELL 4 (Optional): Download as ZIP
# ═══════════════════════════════════════════════════════════════════════════════
# import shutil
# from google.colab import files
# zip_path = shutil.make_archive('/content/extracted', 'zip', str(OUTPUT_DIR))
# files.download(zip_path)
# print("📦 Download started!")
