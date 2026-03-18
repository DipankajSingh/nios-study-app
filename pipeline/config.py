import os
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parent.parent          # ncert-study-app/
PIPELINE_DIR = Path(__file__).resolve().parent             # pipeline/
CONTENT_DIR = ROOT_DIR / "content"                         # For raw HF datasets
BACKEND_DIR = ROOT_DIR / "backend"

def ensure_dirs():
    """Create all output directories if they don't exist."""
    CONTENT_DIR.mkdir(parents=True, exist_ok=True)

if __name__ == "__main__":
    ensure_dirs()
    print(f"ROOT_DIR:       {ROOT_DIR}")
    print(f"PIPELINE_DIR:   {PIPELINE_DIR}")
    print(f"CONTENT_DIR:    {CONTENT_DIR}")
