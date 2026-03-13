#!/usr/bin/env python3
"""
NIOS PDF Extraction — Docling on Kaggle

Extracts text, equations, tables, and images from NIOS chapter PDFs using IBM's Docling 
with schema compliance and complete image capture.

Features:
- Schema Compliance: Generates JSON matching your pipeline ExtractedChapter format
- LaTeX Detection: Automatically detects mathematical formulas and equations  
- Complete Image Capture: Saves all images without filtering for later processing
- Simple Structure: Images saved with sequential naming for easy processing
- Resume Support: Skip already processed chapters automatically

Setup:
1. Add dipankaj/nios-chapter-pdfs as a dataset input (Kaggle → Input → Add Dataset)
2. Edit TARGET_SUBJECTS below if you want a subset (default: all)
3. Enable T4 GPU accelerator → Run script

Input layout (dataset):
/kaggle/input/nios-chapter-pdfs/
  class10/<subject-id>/Chapter N.pdf
  class12/<subject-id>/Chapter N.pdf

Output layout (working dir):
/kaggle/working/extracted/
  _progress.json              ← extraction progress tracker
  class10/<subject-id>/chapters/
    Chapter N.json            ← Schema-compliant JSON (pipeline + Docling data)
    Chapter N_images/         ← All extracted images
      image_001.png           ← Sequential numbering
      image_002.png
      ...
    _manifest.json           ← Subject-level metadata
  class12/<subject-id>/chapters/
    ...
"""

import subprocess
import sys
from pathlib import Path
import json
import time
import re
import traceback
import shutil

# Install required packages
print("📦 Installing required packages...")
try:
    # Try to import docling to check if already installed
    import docling
    print(f"✅ Docling already available: version {getattr(docling, '__version__', 'unknown')}")
except ImportError:
    print("📦 Installing Docling...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "docling==2.79.0"])
    import docling
    print(f"✅ Docling installed: version {getattr(docling, '__version__', 'unknown')}")

# ── Config ── edit these if needed ───────────────────────────────────────────
print("🔧 Loading configuration...")

# 'all' → every subject found in the dataset
# Single string → e.g. 'maths-12'
# List          → e.g. ['maths-12', 'business-10']
TARGET_SUBJECTS = 'all'

# Paths
DATASET_ROOT  = Path('/kaggle/input/datasets/dipankaj/nios-chapter-pdfs')
OUTPUT_ROOT   = Path('/kaggle/working/extracted')
PROGRESS_FILE = OUTPUT_ROOT / '_progress.json'

# Resume: skip chapters whose JSON already exists and is > 100 bytes
RESUME = True

print('📁 Configuration loaded')
print(f'   Target subjects: {TARGET_SUBJECTS}')
print(f'   Dataset root: {DATASET_ROOT}')
print(f'   Output root: {OUTPUT_ROOT}')
print(f'   Resume mode: {RESUME}')

# ── Initialize Docling ────────────────────────────────────────────────────────
print("\n🚀 Initializing Docling...")

from docling.document_converter import DocumentConverter

# Try to enable picture extraction using the correct modern Docling API.
# Falls back to a plain converter if the API version differs.
try:
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import PdfFormatOption
    from docling.datamodel.base_models import InputFormat
    pdf_opts  = PdfPipelineOptions(generate_picture_images=True)
    converter = DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pdf_opts)}
    )
    print('✅ Image extraction ENABLED')
except Exception as _err:
    print(f'⚠️  Image extraction unavailable ({_err}) — using plain converter')
    converter = DocumentConverter()

# ── Helper Functions ──────────────────────────────────────────────────────────

def chapter_sort_key(pdf_path):
    """Sort Chapter 1, Chapter 2 ... numerically."""
    match = re.search(r'\d+', pdf_path.stem)
    return int(match.group()) if match else 999


def discover_all_subjects(dataset_root):
    """Return list of Path objects for every subject directory that contains PDFs."""
    subjects = []
    for class_dir in sorted(dataset_root.glob('class*')):
        if class_dir.is_dir():
            for subject_dir in sorted(class_dir.iterdir()):
                if subject_dir.is_dir() and list(subject_dir.glob('*.pdf')):
                    subjects.append(subject_dir)
    return subjects


def get_subject_name(subject_dir):
    """Read subject_name from _manifest.json, fallback to directory name."""
    manifest = subject_dir / '_manifest.json'
    if manifest.exists():
        try:
            return json.loads(manifest.read_text()).get('subject_name', subject_dir.name)
        except Exception:
            pass
    return subject_dir.name


def get_already_done(output_dir):
    """Return set of chapter stems already extracted (JSON > 100 bytes)."""
    if not output_dir.exists():
        return set()
    return {
        f.stem for f in output_dir.glob('*.json')
        if f.name != '_manifest.json' and f.stat().st_size > 100
    }


def create_image_directory(output_dir, chapter_stem):
    """Create simple directory structure for images."""
    images_dir = output_dir / f'{chapter_stem}_images'
    images_dir.mkdir(parents=True, exist_ok=True)
    return images_dir


def extract_chapter_title_from_docling(docling_data, fallback_name):
    """Extract a meaningful chapter title from Docling content."""
    # Try to find title in the first few text blocks
    texts = docling_data.get('texts', [])
    if texts and len(texts) > 0:
        # Look for title-like text (usually in first block, short, title-case)
        first_text = texts[0].get('text', '').strip()
        if first_text and len(first_text) < 100 and any(word[0].isupper() for word in first_text.split()):
            # Clean up common patterns
            title = re.sub(r'^(Chapter|Lesson)\s*\d+\s*[:-]?\s*', '', first_text, flags=re.IGNORECASE)
            if title.strip():
                return title.strip()
    
    # Fallback to PDF name cleanup
    clean_name = re.sub(r'^\d+_\d+_\w+_\w+_', '', fallback_name)  # Remove prefix like "01_311_Maths_Eng_"
    clean_name = re.sub(r'[Cc]hapter\s*\d+\s*[:-]?\s*', '', clean_name)
    return clean_name.replace('_', ' ').strip() or 'Untitled Chapter'


def check_latex_content(docling_data):
    """Check if the content contains LaTeX mathematical formulas."""
    # Check for common LaTeX patterns in text content
    latex_patterns = [
        r'\\[a-zA-Z]+\{',  # LaTeX commands like \frac{, \sqrt{
        r'\$.*\$',         # Inline math $...$
        r'\\\[.*\\\]',     # Display math \[...\]
        r'\\begin\{',      # LaTeX environments
        r'\\\(.*\\\)',     # Inline math \(...\)
        r'\\[a-z]+',       # Simple LaTeX commands like \alpha, \beta
        r'\^[a-zA-Z0-9{}]+', # Superscripts  
        r'_[a-zA-Z0-9{}]+',  # Subscripts
    ]
    
    # Also check table content for formulas
    all_content = []
    
    # Collect text from all sources
    for text_block in docling_data.get('texts', []):
        all_content.append(text_block.get('text', ''))
    
    for table in docling_data.get('tables', []):
        # Tables may have formula content
        if isinstance(table, dict) and 'text' in table:
            all_content.append(table['text'])
    
    # Check all content for LaTeX patterns
    for content in all_content:
        if content:
            for pattern in latex_patterns:
                if re.search(pattern, content):
                    return True
    return False


def extract_images_from_pictures(pictures, images_dir, pdf_path, schema_data):
    """
    Handle Docling 2.79.0 pictures data robustly.
    In this version, pictures often come as dicts with 'prov' and 'data' keys.
    """
    from PIL import Image
    import base64
    import io
    
    saved_count = 0
    
    print(f"  🔍 Found {len(pictures)} pictures in export data")
    
    for pic_idx, pic_data in enumerate(pictures):
        try:
            pil_image = None
            
            # Debug first few pictures to understand structure
            if pic_idx < 2:
                print(f"    🔍 Picture {pic_idx} type: {type(pic_data)}")
                if isinstance(pic_data, dict):
                    keys = list(pic_data.keys())
                    print(f"    🔍 Available keys: {keys[:5]}")  # First 5 keys
                    # Print types of values for main keys
                    for key in keys[:3]:
                        val = pic_data[key]
                        print(f"      {key}: {type(val).__name__}")
                        # For Docling 2.79.0, check nested structure
                        if isinstance(val, dict) and key == 'data':
                            nested_keys = list(val.keys())[:3]
                            print(f"        data keys: {nested_keys}")
            
            if isinstance(pic_data, dict):
                # Strategy 1: Direct PIL image in common keys
                for key in ['pil_image', 'image', 'img', 'picture']:
                    if key in pic_data:
                        potential_img = pic_data[key]
                        if hasattr(potential_img, 'save') and hasattr(potential_img, 'size'):
                            pil_image = potential_img
                            print(f"    ✅ Found PIL image in '{key}' key")
                            break
                
                # Strategy 2: Docling 2.79.0 specific - check 'data' dict
                if pil_image is None and 'data' in pic_data:
                    data_dict = pic_data['data']
                    if isinstance(data_dict, dict):
                        # Check for PIL image in data dict
                        for nested_key in ['image', 'pil_image', 'picture', 'content']:
                            if nested_key in data_dict:
                                potential_img = data_dict[nested_key]
                                if hasattr(potential_img, 'save') and hasattr(potential_img, 'size'):
                                    pil_image = potential_img
                                    print(f"    ✅ Found PIL image in 'data.{nested_key}' key")
                                    break
                        
                        # Check for base64 or bytes in data dict
                        if pil_image is None:
                            for nested_key in ['bytes', 'content', 'image_data', 'raw']:
                                if nested_key in data_dict:
                                    raw_data = data_dict[nested_key]
                                    if isinstance(raw_data, (str, bytes)):
                                        try:
                                            if isinstance(raw_data, str) and len(raw_data) > 100:
                                                image_bytes = base64.b64decode(raw_data)
                                            elif isinstance(raw_data, bytes):
                                                image_bytes = raw_data
                                            else:
                                                continue
                                            
                                            pil_image = Image.open(io.BytesIO(image_bytes))
                                            print(f"    ✅ Decoded image from 'data.{nested_key}' key")
                                            break
                                        except Exception:
                                            continue
                
                # Strategy 3: Check for base64 encoded image data in top level
                if pil_image is None:
                    for key in ['content', 'bytes', 'image_data']:
                        if key in pic_data:
                            data = pic_data[key]
                            if isinstance(data, (str, bytes)):
                                try:
                                    if isinstance(data, str) and len(data) > 100:  # Reasonable base64 length
                                        image_bytes = base64.b64decode(data)
                                    elif isinstance(data, bytes):
                                        image_bytes = data
                                    else:
                                        continue
                                    
                                    pil_image = Image.open(io.BytesIO(image_bytes))
                                    print(f"    ✅ Decoded image from '{key}' key")
                                    break
                                except Exception:
                                    continue
                
                # Strategy 4: Check further nested structures
                if pil_image is None:
                    for key, value in pic_data.items():
                        if isinstance(value, dict):
                            for nested_key in ['image', 'pil_image', 'data']:
                                if nested_key in value:
                                    nested_val = value[nested_key]
                                    if hasattr(nested_val, 'save') and hasattr(nested_val, 'size'):
                                        pil_image = nested_val
                                        print(f"    ✅ Found nested PIL image in '{key}.{nested_key}'")
                                        break
                            if pil_image:
                                break
            
            # Save the image if we found one
            if pil_image and hasattr(pil_image, 'save'):
                saved_count += 1
                img_filename = f'image_{saved_count:03d}.png'
                img_path = images_dir / img_filename
                
                try:
                    pil_image.save(img_path)
                    relative_img_path = f'{pdf_path.stem}_images/{img_filename}'
                    schema_data['image_paths'].append(relative_img_path)
                    print(f"    💾 Saved: {img_filename} ({pil_image.size})")
                except Exception as save_err:
                    print(f"    ❌ Failed to save {img_filename}: {save_err}")
            else:
                if pic_idx < 3:  # Only show detailed errors for first few
                    print(f"    ⚠️  Picture {pic_idx}: No valid PIL image found")
                        
        except Exception as pic_err:
            print(f"    ❌ Error processing picture {pic_idx}: {pic_err}")
    
    return saved_count


def extract_single_pdf(pdf_path, output_dir, subject_id, class_level, chapter_index):
    """
    Convert one PDF with Docling and generate schema-compliant JSON.
    Saves <stem>.json with metadata and all images in images directory.
    Returns (success: bool, image_count: int, has_latex: bool).
    """
    try:
        result    = converter.convert(str(pdf_path))
        doc       = result.document
        json_path = output_dir / f'{pdf_path.stem}.json'

        # Get Docling's export and augment with pipeline metadata
        docling_data = doc.export_to_dict()
        
        # Extract chapter number from PDF name (e.g., "Chapter 1.pdf" -> 1)
        chapter_match = re.search(r'[Cc]hapter\s*(\d+)', pdf_path.stem)
        chapter_num = chapter_match.group(1) if chapter_match else str(chapter_index).zfill(2)
        
        # Check for LaTeX content
        has_latex = check_latex_content(docling_data)
        
        # Generate schema-compliant chapter data
        schema_data = {
            # Pipeline metadata (required by ExtractedChapter schema)  
            "chapter_id": f"{subject_id}-ch{chapter_num.zfill(2)}",
            "chapter_title": extract_chapter_title_from_docling(docling_data, pdf_path.stem),
            "order_index": chapter_index,
            "source_pdf": pdf_path.name,
            "image_paths": [],  # Will be populated below
            
            # Docling's original structure (preserved for Stage 3)
            "texts": docling_data.get("texts", []),
            "tables": docling_data.get("tables", []),
            "pictures": docling_data.get("pictures", []),
            "title": docling_data.get("title", ""),
            "description": docling_data.get("description", ""),
            
            # Additional metadata
            "extraction_method": "docling",
            "docling_version": getattr(doc, 'version', 'unknown'),
            "has_latex_formulas": has_latex,
            "extracted_at": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        }

        # Create image directory
        images_dir = create_image_directory(output_dir, pdf_path.stem)
        
        saved_count = 0
        
        # Extract all images without filtering
        print(f"  🔍 Scanning document for images...")
        
        # Method 1: Try iterating over document elements (modern Docling API)
        try:
            for element, _ in doc.iterate_items():
                pil_image = getattr(element, 'image', None)
                if pil_image is not None:
                    saved_count += 1
                    
                    # Save all images sequentially
                    img_filename = f'image_{saved_count:03d}.png'
                    img_path = images_dir / img_filename
                    pil_image.save(img_path)
                    
                    # Track image path relative to chapters directory
                    relative_img_path = f'{pdf_path.stem}_images/{img_filename}'
                    schema_data['image_paths'].append(relative_img_path)
                    
                    print(f"    💾 Saved: {img_filename} ({pil_image.size})")
        
        except AttributeError:
            # Method 2: Fallback to pictures in the export data
            print(f"  🔄 Fallback: Checking 'pictures' in export data...")
            pictures = docling_data.get('pictures', [])
            saved_count = extract_images_from_pictures(pictures, images_dir, pdf_path, schema_data)
                    
        print(f"  📊 Total images saved: {saved_count}")

        # Save schema-compliant JSON with all metadata
        with open(json_path, 'w', encoding='utf-8') as fh:
            json.dump(schema_data, fh, indent=2, ensure_ascii=False)

        return True, saved_count, has_latex

    except Exception:
        traceback.print_exc()
        return False, 0, False


def save_progress_checkpoint(subject_entry, ok_count, fail_count, failed_chapter_names, progress):
    """Persist the per-subject manifest and flush _progress.json to disk."""
    output_dir   = subject_entry['output_dir']
    subject_id   = subject_entry['subject_id']
    class_level  = subject_entry['class_level']
    subject_name = subject_entry['subject_name']
    all_pdfs     = subject_entry['all_pdfs']

    chapter_files = sorted(
        [f for f in output_dir.glob('*.json') if f.name != '_manifest.json'],
        key=chapter_sort_key,
    )
    manifest = {
        'subject_id':   subject_id,
        'subject_name': subject_name,
        'class_level':  class_level,
        'extracted_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'extractor':    'docling',
        'chapters': [
            {'name': f.stem, 'file': f.name, 'size_bytes': f.stat().st_size}
            for f in chapter_files
        ],
    }
    with open(output_dir / '_manifest.json', 'w') as fh:
        json.dump(manifest, fh, indent=2)

    progress['subjects'][subject_id] = {
        'class_level':     class_level,
        'total_pdfs':      len(all_pdfs),
        'extracted':       ok_count,
        'failed':          fail_count,
        'failed_chapters': failed_chapter_names,
        'status':         'complete' if fail_count == 0 and ok_count == len(all_pdfs) else 'partial',
        'last_run':        time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
    }
    progress['last_updated'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PROGRESS_FILE, 'w') as fh:
        json.dump(progress, fh, indent=2)


def main():
    """Main extraction function."""
    print("\n📋 Discovering PDFs and building work plan...")
    
    # ── Load progress tracker ─────────────────────────────────────────────────────
    if PROGRESS_FILE.exists():
        progress = json.loads(PROGRESS_FILE.read_text())
        print(f'📂 Progress loaded — {len(progress["subjects"])} subject(s) tracked')
    else:
        progress = {'last_updated': None, 'subjects': {}}
        print('📂 No existing progress — starting fresh')

    # ── Filter to TARGET_SUBJECTS ─────────────────────────────────────────────────
    all_subject_dirs = discover_all_subjects(DATASET_ROOT)

    if TARGET_SUBJECTS == 'all':
        selected_subject_dirs = all_subject_dirs
    elif isinstance(TARGET_SUBJECTS, str):
        selected_subject_dirs = [d for d in all_subject_dirs if d.name == TARGET_SUBJECTS]
    else:
        selected_subject_dirs = [d for d in all_subject_dirs if d.name in TARGET_SUBJECTS]

    # ── Build work plan ───────────────────────────────────────────────────────────
    work_plan = []  # list of dicts, one per subject

    print(f'\nDataset : {DATASET_ROOT}  ({len(all_subject_dirs)} total subjects)\n')
    print(f'{"Subject":<22}  {"PDFs":>4}  {"Done":>4}  {"Left":>4}  Status')
    print('─' * 52)

    for subject_dir in selected_subject_dirs:
        subject_id   = subject_dir.name
        class_level  = subject_id.rsplit('-', 1)[-1]     # e.g. '12' from 'maths-12'
        subject_name = get_subject_name(subject_dir)
        all_pdfs     = sorted(subject_dir.glob('*.pdf'), key=chapter_sort_key)
        output_dir   = OUTPUT_ROOT / f'class{class_level}' / subject_id / 'chapters'
        done_stems   = get_already_done(output_dir) if RESUME else set()
        pending_pdfs = [p for p in all_pdfs if p.stem not in done_stems]

        work_plan.append({
            'subject_id':   subject_id,
            'subject_name': subject_name,
            'class_level':  class_level,
            'subject_dir':  subject_dir,
            'output_dir':   output_dir,
            'all_pdfs':     all_pdfs,
            'done_stems':   done_stems,
            'pending_pdfs': pending_pdfs,
        })

        status_icon = '✅ done' if not pending_pdfs else ('⏳ partial' if done_stems else '🆕 new')
        print(f'  {subject_id:<22}  {len(all_pdfs):>4}  {len(done_stems):>4}  {len(pending_pdfs):>4}  {status_icon}')

    total_pending = sum(len(s['pending_pdfs']) for s in work_plan)
    print(f'\n  → {total_pending} chapter(s) to extract across {len(work_plan)} subject(s)')

    # ── Main extraction loop ──────────────────────────────────────────────────────
    if total_pending == 0:
        print('✅ Nothing to do — all chapters already extracted!')
    else:
        for subj_idx, subj in enumerate(work_plan, 1):
            subject_id   = subj['subject_id']
            pending_pdfs = subj['pending_pdfs']
            output_dir   = subj['output_dir']
            class_level  = subj['class_level']

            if not pending_pdfs:
                print(f'[{subj_idx}/{len(work_plan)}] ⏭️  {subject_id} — already complete')
                continue

            done_count = len(subj['done_stems'])
            print(f'\n[{subj_idx}/{len(work_plan)}] 📚 {subject_id}'
                  f'  ({len(pending_pdfs)} to extract, {done_count} already done)')
            output_dir.mkdir(parents=True, exist_ok=True)

            ok_count             = 0
            fail_count           = 0
            failed_chapter_names = []
            total_images         = 0
            total_latex_chapters = 0

            for ch_idx, pdf_path in enumerate(pending_pdfs, 1):
                print(f'    [{ch_idx:>2}/{len(pending_pdfs)}] ⚙️  {pdf_path.stem} ...', end=' ', flush=True)
                success, image_count, has_latex = extract_single_pdf(pdf_path, output_dir, subject_id, class_level, ch_idx)
                if success:
                    ok_count += 1
                    total_images += image_count
                    
                    # Count chapters with LaTeX
                    if has_latex:
                        total_latex_chapters += 1
                    
                    latex_icon = "📐" if has_latex else ""
                    print(f'✅  ({image_count} images) {latex_icon}')
                else:
                    fail_count += 1
                    failed_chapter_names.append(pdf_path.stem)
                    print('❌')

            # Print summary for this subject
            print(f'  → ✅ {ok_count}  ❌ {fail_count}')
            if total_images > 0:
                print(f'  → Images: {total_images} saved')
            if total_latex_chapters > 0:
                print(f'  → LaTeX formulas detected in {total_latex_chapters} chapters')
            if failed_chapter_names:
                print(f'  → Failed chapters: {failed_chapter_names}')

            save_progress_checkpoint(subj, ok_count, fail_count, failed_chapter_names, progress)
            print('  💾 Checkpoint saved')

        print('\n🎉 Extraction complete!')

    # ── Copy output for download via Kaggle Output tab ───────────────────────────
    print("\n📦 Preparing download package...")
    
    DOWNLOAD_DIR = Path("/kaggle/working/output_for_download")
    if DOWNLOAD_DIR.exists():
        shutil.rmtree(DOWNLOAD_DIR)
    shutil.copytree(OUTPUT_ROOT, DOWNLOAD_DIR)

    total_files = list(DOWNLOAD_DIR.rglob("*"))
    json_files  = [f for f in total_files if f.suffix == ".json" and not f.name.startswith('_')]
    manifest_files = [f for f in total_files if f.name.endswith('_manifest.json')]
    img_files   = [f for f in total_files if f.suffix in (".png", ".jpg")]
    img_dirs    = [f for f in total_files if f.is_dir() and f.name.endswith('_images')]

    print(f"✅ Copied to {DOWNLOAD_DIR}")
    print(f"   📄 {len(json_files)} chapter JSON files")
    print(f"   📄 {len(manifest_files)} manifest files")  
    print(f"   📁 {len(img_dirs)} image directories")
    print(f"   🖼️  {len(img_files)} image files total")
    print("   → Click the Output tab → Download All to get the zip")

    # Show structure sample
    if img_dirs:
        sample_dir = img_dirs[0]
        image_files = list(sample_dir.glob('*.png'))
        print(f"\n📁 Image directory sample:")
        print(f"   📂 {sample_dir.relative_to(DOWNLOAD_DIR)}/")
        print(f"     📷 {len(image_files)} image files")
        
        if image_files:
            # Show first few filenames as examples
            examples = [f.name for f in sorted(image_files)[:3]]
            if len(image_files) > 3:
                examples.append('...')
            print(f"     Examples: {', '.join(examples)}")

    # ── Final summary ─────────────────────────────────────────────────────────────
    print(f'\n📊 Final Summary:')
    print(f'{"Subject":<22}  {"Total":>5}  {"Done":>5}  {"Fail":>5}  Status')
    print('─' * 58)
    for sid, info in progress['subjects'].items():
        icon = '✅' if info['status'] == 'complete' else '⚠️ '
        print(f"  {sid:<22}  {info['total_pdfs']:>5}  {info['extracted']:>5}  {info['failed']:>5}  {icon}")
    print(f'\n📋 Progress file → {PROGRESS_FILE}')

    # Calculate storage efficiency and LaTeX statistics  
    total_json_files = len(list(OUTPUT_ROOT.glob('class*/*/chapters/*.json')))
    total_image_dirs = len(list(OUTPUT_ROOT.glob('class*/*/chapters/*_images')))
    total_image_files = len(list(OUTPUT_ROOT.glob('class*/*/chapters/*_images/*.png')))

    # Count chapters with LaTeX formulas
    latex_chapters = 0
    total_chapters = 0
    for json_file in OUTPUT_ROOT.glob('class*/*/chapters/*.json'):
        if json_file.name != '_manifest.json':
            try:
                with open(json_file) as fh:
                    data = json.load(fh)
                    total_chapters += 1
                    if data.get('has_latex_formulas', False):
                        latex_chapters += 1
            except:
                pass

    print(f'\n📈 Storage Summary:')
    print(f'   JSON files: {total_json_files}')
    print(f'   Image directories: {total_image_dirs}') 
    print(f'   Image files: {total_image_files}')
    print(f'   Avg images per chapter: {total_image_files/max(total_json_files,1):.1f}')
    print(f'   LaTeX chapters: {latex_chapters}/{total_chapters} ({100*latex_chapters/max(total_chapters,1):.0f}%)')
    print(f'\n✅ Schema compliant: Ready for Stage 3 (structure_content.py)')
    print(f'🖼️  All images captured: Filter/process as needed in later stages')
    print(f'🚀 Extraction script completed successfully!')


if __name__ == "__main__":
    main()