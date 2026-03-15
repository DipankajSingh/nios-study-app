# NIOS Chapter Content Extractor with Marker

A comprehensive approach for extracting text, equations, tables, and images from NIOS chapter PDFs using marker-pdf on Kaggle. Designed for GPU acceleration with resume capability and hierarchical JSON output.

## 🚀 Features

- **Complete Content Extraction**: Text, equations, tables, and images
- **Schema Compliance**: Follows your pipeline's ExtractedSubject/ExtractedChapter models
- **Resume Capability**: Automatically continues from where it left off
- **Memory Efficient**: Processes one PDF at a time for Kaggle's memory constraints
- **Image Linking**: Images are properly extracted and linked to their content
- **Robust Error Handling**: Continues processing even if some files fail
- **Progress Tracking**: Detailed logging and progress tracking

## 📁 Expected Directory Structure

Your Kaggle dataset should be organized as:

```
/kaggle/input/datasets/dipankaj/nios-chapter-pdfs/
├── class10/
│   ├── maths-10/
│   │   ├── Chapter 01.pdf
│   │   ├── Chapter 02.pdf
│   │   └── Chapter N.pdf
│   ├── science-10/
│   │   └── Chapter *.pdf
│   └── <subject-id>/
└── class12/
    ├── maths-12/
    │   └── Chapter *.pdf
    ├── physics-12/
    │   └── Chapter *.pdf
    └── <subject-id>/
```

## 🏃‍♂️ Quick Start

### In Kaggle Notebook

1. Copy the `extract_with_marker.py` script to your notebook
2. Run the extraction:

```python
# Basic usage - processes all PDFs
exec(open('/kaggle/working/extract_with_marker.py').read())
```

Or use the main function:

```python
from extract_with_marker import NIOSMarkerExtractor, ExtractionConfig

# Default configuration
config = ExtractionConfig()
extractor = NIOSMarkerExtractor(config)

# Run extraction
stats = extractor.run_extraction()
print(f"Processed {stats['subjects_processed']} subjects")
```

### Custom Configuration

```python
from extract_with_marker import NIOSMarkerExtractor, ExtractionConfig

# Custom paths and settings
config = ExtractionConfig(
    input_base_path="/kaggle/input/your-dataset-name",
    output_base_path="/kaggle/working/extracted",
    images_base_path="/kaggle/working/images",
    max_image_size=1024 * 1024 * 10  # 10MB max per image
)

extractor = NIOSMarkerExtractor(config)
stats = extractor.run_extraction()
```

## 📊 Output Structure

### Subject JSON Files

Each subject generates a JSON file following your schema:

```json
{
  "subject": {
    "id": "maths-12",
    "name": "Maths 12",
    "class_level": "12",
    "code": "",
    "description": "",
    "icon": "📘",
    "total_marks": 100
  },
  "extracted_at": "2026-03-14T10:30:00",
  "chapters": [
    {
      "chapter_id": "maths-12-ch01",
      "chapter_title": "Chapter 01",
      "order_index": 1,
      "source_pdf": "/kaggle/input/.../Chapter 01.pdf",
      "markdown_text": "# Chapter 01\n\n## Introduction...",
      "image_paths": ["maths-12-ch01/image_001.png", ...]
    }
  ]
}
```

### Directory Structure (Output)

```
/kaggle/working/
├── extracted/
│   ├── maths-12.json
│   ├── physics-12.json
│   └── science-10.json
├── images/
│   ├── maths-12-ch01/
│   │   ├── image_001.png
│   │   └── image_002.png
│   └── physics-12-ch01/
├── extraction.log
├── extraction_progress.json
└── extraction_stats.json
```

## 🔄 Resume Functionality

The script automatically tracks progress and can resume interrupted extractions:

- **Progress File**: `/kaggle/working/extraction_progress.json`
- **Completed Files**: Skipped on subsequent runs
- **Failed Files**: Logged but can be retried by deleting from progress

To force a complete re-extraction, delete the progress file:

```python
import os
os.remove('/kaggle/working/extraction_progress.json')
```

## 🖼️ Image Extraction

The script uses multiple strategies to extract images from PDFs:

1. **Document Pictures**: Main image containers in Marker
2. **Page Images**: Images found at page level
3. **Alternative Formats**: Figures, diagrams, and media attachments
4. **Multiple Data Formats**: PIL images, base64, and binary data

Images are saved as PNG files and linked by relative paths in the JSON output.

## ⚙️ Configuration Options

```python
@dataclass
class ExtractionConfig:
    input_base_path: str = "/kaggle/input/datasets/dipankaj/nios-chapter-pdfs"
    output_base_path: str = "/kaggle/working/extracted"
    images_base_path: str = "/kaggle/working/images"
    resume_file: str = "/kaggle/working/extraction_progress.json"
    batch_size: int = 1  # PDFs processed at once
    max_image_size: int = 5242880  # 5MB max per image
    supported_image_formats: tuple = ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff')
```

## 🔍 Monitoring Progress

- **Real-time Logs**: Watch extraction progress in real-time
- **Statistics**: Final stats saved to `extraction_stats.json`
- **Error Tracking**: Failed files logged for later investigation

## 📋 Example Log Output

```
2026-03-14 10:30:00 - INFO - 📚 NIOS Marker Extractor initialized
2026-03-14 10:30:01 - INFO - 📊 Discovered 5 subjects with 45 total PDFs
2026-03-14 10:30:02 - INFO - 🔄 Processing subject: maths-12 (8 chapters)
2026-03-14 10:30:15 - INFO - 📄 Extracting chapter 1/8: Chapter 01.pdf
2026-03-14 10:30:25 - INFO - 📊 Extracted: 15,420 chars text, 3 images
2026-03-14 10:30:26 - INFO - ✅ Successfully extracted: Chapter 01.pdf
```

## 🚨 Troubleshooting

### Common Issues

1. **Input Not Found**: Verify dataset path in Kaggle
2. **Memory Issues**: Script processes one PDF at a time to avoid this
3. **Image Extraction Fails**: Multiple fallback strategies implemented
4. **Progress File Corruption**: Delete and restart extraction

### Debug Mode

Enable debug logging:

```python
import logging
logging.getLogger().setLevel(logging.DEBUG)
```

### Checking Results

```python
# Load and inspect results
import json
from pathlib import Path

output_dir = Path("/kaggle/working/extracted")
for json_file in output_dir.glob("*.json"):
    with open(json_file) as f:
        data = json.load(f)
    print(f"Subject: {data['subject']['name']}")
    print(f"Chapters: {len(data['chapters'])}")
```

## 📝 Requirements

The script automatically installs Marker on Kaggle:

```bash
pip install marker-pdf
```

Dependencies included with Marker:

- PyPDF processing backends
- Image processing libraries (PIL)
- PDF layout analysis models

## 🔧 Advanced Usage

### Processing Specific Subjects

Modify the `discover_pdf_files()` method to filter subjects:

```python
# Only process math subjects
subjects = extractor.discover_pdf_files()
math_subjects = {k: v for k, v in subjects.items() if 'math' in k.lower()}
```

### Custom Image Processing

Extend the `ImageExtractor` class for custom image processing:

```python
class CustomImageExtractor(ImageExtractor):
    def _save_pil_image(self, img_obj, image_path):
        # Custom image processing logic
        return super()._save_pil_image(img_obj, image_path)
```

## 📈 Performance

- **Memory Usage**: ~500MB peak per PDF
- **Speed**: ~1-2 minutes per chapter (depending on size)
- **Concurrent Processing**: Designed for single-threaded processing
- **Storage**: JSON files are compact, images stored efficiently

## 📄 Legacy Scripts

For reference, this folder also contains the old extraction workflow:

- `upload_to_kaggle.py` - Upload chapter URLs to Kaggle
- `download_chapters_local.py` - Download PDFs locally
- `download_from_kaggle.py` - Download marker-extracted content
- `extract_pdf_kaggle.ipynb` - Legacy marker-based extraction

## 📄 License

This script is designed for educational content extraction and should comply with NIOS content usage policies.

```bash
cd pipeline
python 02_extract/download_chapters_local.py
```

**Non-interactive mode** (for scripting/CI):

```bash
python 02_extract/download_chapters_local.py --subject maths-12
python 02_extract/download_chapters_local.py --class 12
python 02_extract/download_chapters_local.py --all
```

Output structure:

```text
pipeline/output/pdfs/
  class12/
    maths-12/
      chapters/
        Chapter 1.pdf
        Chapter 2.pdf
        ...
      _manifest.json
  _registry.json        ← tracks every chapter; re-runs skip SUCCESS entries
```

Notes:

- Downloads are automatically skipped if already recorded as `SUCCESS` in `_registry.json`.
- Use `--max-retries`, `--timeout`, and `--min-bytes` for stricter control.

## Kaggle URL-config workflow (default)

1. Generate chapter URLs:

```bash
cd pipeline
python 01_scrape/generate_chapter_urls.py --subject maths-12
```

2. Upload URLs JSON to Kaggle:

```bash
python 02_extract/upload_to_kaggle.py --subject maths-12 --username <your-kaggle-username>
```

3. Run extraction notebook on Kaggle:

- Open `extract_pdf_kaggle.ipynb`
- Add dataset `nios-maths-12-urls` as input
- Enable Internet + GPU
- Run all cells

4. Download extracted JSON locally:

```bash
python 02_extract/download_from_kaggle.py --subject maths-12 --dataset <username>/nios-maths-12-extracted
```

## Optional: Upload local PDFs to Kaggle manually

If you downloaded local PDFs and want to upload those files as a Kaggle dataset:

```bash
kaggle datasets init -p pipeline/output/pdfs/class12/maths-12/chapters
# edit generated dataset-metadata.json
kaggle datasets create -p pipeline/output/pdfs/class12/maths-12/chapters
```
