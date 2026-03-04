# NIOS to Google Drive Scraper

This is a Python automation script that programmatically scrapes educational PDFs (chapters and lessons) from the National Institute of Open Schooling (NIOS) website and directly uploads them to a designated Google Drive folder. 

It organizes the files neatly by Class (10th/12th) -> Academic Stream (Science, Commerce, Arts, etc.) -> Subject.

## Features
- **Smart Filtering:** Automatically excludes administrative documents, sample papers, learner guides, syllabuses, and irrelevant PDFs, ensuring only actual study chapters are grabbed.
- **Curriculum Deduplication:** Intelligently favors "New" curriculums and discards legacy curriculums to avoid duplicate or outdated files.
- **Language Filtering:** Filters out unwanted regional language subjects, keeping only English and Hindi language subjects by default.
- **Categorization:** Sorts subjects into 5 distinct logical streams (Science, Commerce, Humanities, Languages, Vocational & Others).
- **Interactive CLI:** Prompts the user to pick a Class, select a Stream, and choose either the entire stream or specific subjects to download.
- **Filename Normalization:** Extracts canonical chapter numbering and renames files to a clean `Chapter X.pdf` format. Supplemental materials are tagged as `Extra - X.pdf`.
- **Resilient Uploads & Checkpointing:** Uses `downloads_registry.json` to track successful uploads to Google Drive. If the script is interrupted, it will skip already-uploaded files upon restart.

## Prerequisites

1. **Python 3.x**
2. **Google Cloud Project credentials:** 
   - Ensure you have `credentials.json` for a Google Service Account or OAuth 2.0 flow placed in this directory.
   - The script creates and stores `token.json` after the first successful OAuth login.

## Installation

Install the required Python packages:
```bash
pip install -r requirements.txt
```
*(If on Ubuntu or modern Linux, you may need to add `--break-system-packages` or use a Python virtual environment depending on your system's `pip` policy).*

## Usage

1. **Generate Subject Lists (Optional/First Time)**
   Run the following to scrape the NIOS site for the latest subjects and save them to `subjects_10.json` and `subjects_12.json`:
   ```bash
   python3 generate_subjects.py
   ```

2. **Run the Scraper**
   Execute the main script:
   ```bash
   python3 scrape_nios.py
   ```
   Follow the interactive prompts to select your Class, Stream, and Subjects.

## Folder Structure Output
Files are automatically grouped in your Google Drive under a root `NIOS Backup` folder:
```
NIOS Backup
└── Class 12
    ├── Science
    │   ├── Physics (312)
    │   │   ├── Chapter 1.pdf
    │   │   └── Chapter 2.pdf
    │   └── Mathematics (311)
    ├── Commerce
    │   └── Economics (318)
    └── Humanities
```
