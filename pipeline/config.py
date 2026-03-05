"""
Pipeline Configuration — Single source of truth for all paths, keys, and constants.
Copy .env.example → .env and fill in your API keys before running any pipeline stage.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# ── Paths ────────────────────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parent.parent          # nios-study-app/
PIPELINE_DIR = Path(__file__).resolve().parent             # pipeline/
CONTENT_DIR = ROOT_DIR / "content"
BACKEND_DIR = ROOT_DIR / "backend"

# Pipeline I/O directories
OUTPUT_DIR       = PIPELINE_DIR / "output"
EXTRACTED_DIR    = OUTPUT_DIR / "extracted"     # Markdown from Colab/docling
STRUCTURED_DIR   = OUTPUT_DIR / "structured"   # JSON from DeepSeek
VERIFIED_DIR     = OUTPUT_DIR / "verified"     # Verified clean JSON
SOLVED_DIR       = OUTPUT_DIR / "solved"       # PYQs with solutions

# ── Environment ──────────────────────────────────────────────────────────────
load_dotenv(PIPELINE_DIR / ".env")

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
CLAUDE_API_KEY   = os.getenv("CLAUDE_API_KEY", "")
GROQ_API_KEY     = os.getenv("GROQ_API_KEY", "")

# ── API endpoints ────────────────────────────────────────────────────────────
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
DEEPSEEK_MODEL    = "deepseek-chat"           # DeepSeek V3

CLAUDE_BASE_URL   = "https://api.anthropic.com/v1/messages"
CLAUDE_MODEL      = "claude-sonnet-4-20250514"

# ── Processing defaults ──────────────────────────────────────────────────────
CHUNK_SIZE        = 3000      # chars per chunk sent to structuring API
CHUNK_OVERLAP     = 200       # overlap between chunks
RATE_LIMIT_PAUSE  = 2.0       # seconds between API calls
MAX_RETRIES       = 3

# ── Subject registry ────────────────────────────────────────────────────────
# Maps subject IDs to their content directories and PDF code prefixes.
# Add new subjects here as you scrape them.
SUBJECTS = {
    "maths-12": {
        "name": "Mathematics",
        "class_level": "12",
        "code": "311",
        "icon": "📐",
        "pdf_dir": CONTENT_DIR / "class12" / "maths-12" / "pdfs",
        "pyq_dir": CONTENT_DIR / "class12" / "maths-12" / "pyqs_raw",
    },
    # Add more subjects as they are scraped:
    # "english-12": { ... },
    # "physics-12": { ... },
}


def ensure_dirs():
    """Create all output directories if they don't exist."""
    for d in [EXTRACTED_DIR, STRUCTURED_DIR, VERIFIED_DIR, SOLVED_DIR]:
        d.mkdir(parents=True, exist_ok=True)


if __name__ == "__main__":
    ensure_dirs()
    print(f"ROOT_DIR:       {ROOT_DIR}")
    print(f"PIPELINE_DIR:   {PIPELINE_DIR}")
    print(f"CONTENT_DIR:    {CONTENT_DIR}")
    print(f"OUTPUT_DIR:     {OUTPUT_DIR}")
    print(f"DeepSeek key:   {'set' if DEEPSEEK_API_KEY else 'MISSING'}")
    print(f"Claude key:     {'set' if CLAUDE_API_KEY else 'MISSING'}")
    print(f"Groq key:       {'set' if GROQ_API_KEY else 'MISSING'}")
    print(f"Subjects:       {list(SUBJECTS.keys())}")
