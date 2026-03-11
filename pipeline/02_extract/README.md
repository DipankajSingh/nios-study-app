# Stage 02 Extract Workflow

This folder contains scripts for the extraction pipeline around Kaggle + marker-pdf.

## Scripts

- `upload_to_kaggle.py`
  - Uploads chapter URL config JSON to Kaggle (`nios-<subject>-urls`).
- `download_chapters_local.py`
  - Downloads chapter PDFs locally from `01_scrape/chapter_urls/<subject>.json`.
- `download_from_kaggle.py`
  - Downloads marker-extracted chapter JSON files from Kaggle to local output.
- `extract_pdf_kaggle.ipynb`
  - Kaggle notebook that downloads PDFs and runs marker extraction.

## Local chapter download (optional)

Run this when you want local chapter PDFs before Kaggle upload.

**Interactive mode** (prompts for class → stream → subjects):

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
