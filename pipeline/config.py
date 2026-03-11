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
OUTPUT_DIR        = PIPELINE_DIR / "output"
CHAPTER_URLS_DIR  = PIPELINE_DIR / "01_scrape" / "chapter_urls"  # Stage 1 output
PDF_OUTPUT_ROOT   = OUTPUT_DIR / "pdfs"         # local chapter PDFs (Stage 2b)
EXTRACTED_DIR     = OUTPUT_DIR / "extracted"    # marker-pdf JSONs from Kaggle
STRUCTURED_DIR    = OUTPUT_DIR / "structured"   # JSON from DeepSeek
VERIFIED_DIR      = OUTPUT_DIR / "verified"     # Verified clean JSON
SOLVED_DIR        = OUTPUT_DIR / "solved"       # PYQs with solutions

# ── Environment ──────────────────────────────────────────────────────────────
load_dotenv(PIPELINE_DIR / ".env")

DEEPSEEK_API_KEY  = os.getenv("DEEPSEEK_API_KEY", "")
CLAUDE_API_KEY    = os.getenv("CLAUDE_API_KEY", "")
GROQ_API_KEY      = os.getenv("GROQ_API_KEY", "")
GEMINI_API_KEY    = os.getenv("GEMINI_API_KEY", "")
KAGGLE_USERNAME   = os.getenv("KAGGLE_USERNAME", "")
KAGGLE_API_TOKEN  = os.getenv("KAGGLE_API_TOKEN", "")

# ── API endpoints ────────────────────────────────────────────────────────────
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL    = "deepseek-chat"           # DeepSeek V3

CLAUDE_BASE_URL   = "https://api.anthropic.com/v1/messages"
CLAUDE_MODEL      = "claude-sonnet-4-20250514"

# Gemini via OpenAI-compatible endpoint
GEMINI_BASE_URL   = "https://generativelanguage.googleapis.com/v1beta/openai"
GEMINI_MODEL      = "gemini-2.5-flash-lite"   # Stable, free tier, fastest, no thinking overhead

# ── Processing defaults ──────────────────────────────────────────────────────
CHUNK_SIZE        = 3000      # chars per chunk sent to structuring API
CHUNK_OVERLAP     = 200       # overlap between chunks
RATE_LIMIT_PAUSE  = 2.0       # seconds between API calls
MAX_RETRIES       = 3

# ── Subject registry ─────────────────────────────────────────────────────────
# Single source of truth for every NIOS subject the app will support.
# Fields:
#   name        — human-readable subject name
#   class_level — "10" or "12"
#   code        — NIOS subject code
#   stream      — Science | Commerce | Humanities | Languages | Vocational
#   icon        — emoji shown in the app UI
#   nios_url    — NIOS page that lists all chapter PDF links
#   pyq_dir     — local path for past-year question PDFs (Stage 5)

def _s(name, level, code, stream, icon, url_slug):
    """Build a subject entry. url_slug is the path segment in the NIOS URL."""
    base = (
        "sr-secondary-courses" if level == "12" else "secondary-courses"
    )
    return {
        "name": name,
        "class_level": level,
        "code": code,
        "stream": stream,
        "icon": icon,
        "nios_url": f"https://nios.ac.in/online-course-material/{base}/{url_slug}.aspx",
        "pyq_dir": CONTENT_DIR / f"class{level}" / f"{name.lower().replace(' ', '-')}-{level}" / "pyqs_raw",
    }


SUBJECTS = {
    # ── Class 12 — Science ───────────────────────────────────────────────────
    "maths-12":      _s("Mathematics",       "12", "311", "Science",    "📐", "Mathematics-(311)"),
    "physics-12":    _s("Physics",            "12", "312", "Science",    "⚛️",  "Physics-(312)"),
    "chemistry-12":  _s("Chemistry",          "12", "313", "Science",    "🧪", "Chemistry-(313)"),
    "biology-12":    _s("Biology",            "12", "314", "Science",    "🧬", "Biology-(314)"),
    "cs-12":         _s("Computer Science",   "12", "330", "Science",    "💻", "Computer-Science-(330)"),
    # ── Class 12 — Commerce ──────────────────────────────────────────────────
    "economics-12":  _s("Economics",          "12", "318", "Commerce",   "📊", "Economics-(318)"),
    "business-12":   _s("Business Studies",   "12", "319", "Commerce",   "🏢", "Business-Studies-(319)"),
    "accountancy-12":_s("Accountancy",        "12", "320", "Commerce",   "🧾", "Accountancy-(320)"),
    # ── Class 12 — Humanities ────────────────────────────────────────────────
    "history-12":    _s("History",            "12", "315", "Humanities", "🏛️",  "History-(315)"),
    "geography-12":  _s("Geography",          "12", "316", "Humanities", "🌍", "Geography-(316)"),
    "polsci-12":     _s("Political Science",  "12", "317", "Humanities", "🗳️",  "Political-Science-(317)"),
    "psychology-12": _s("Psychology",         "12", "328", "Humanities", "🧠", "Psychology-(328)"),
    "sociology-12":  _s("Sociology",          "12", "331", "Humanities", "👥", "Sociology-(331)"),
    # ── Class 12 — Languages ─────────────────────────────────────────────────
    "english-12":    _s("English",            "12", "302", "Languages",  "🔤", "English-(302)"),
    "hindi-12":      _s("Hindi",              "12", "301", "Languages",  "🔤", "Hindi-(301)"),
    # ── Class 10 — Core ──────────────────────────────────────────────────────
    # Note: Class 10 NIOS pages use a "-Syllabus" suffix in the URL slug.
    "maths-10":      _s("Mathematics",        "10", "211", "Science",    "📐", "Mathematics-(211)-Syllabus"),
    "science-10":    _s("Science",            "10", "212", "Science",    "🔬", "Science-and-Technology-(212)-Syllabus"),
    "social-sci-10": _s("Social Science",     "10", "213", "Humanities", "🌐", "Social-Science-(213)-Syllabus"),
    "economics-10":  _s("Economics",          "10", "214", "Commerce",   "📊", "economics-(214)-syllabus"),
    "business-10":   _s("Business Studies",   "10", "215", "Commerce",   "🏢", "business-studies-(215)-syllabus"),
    "english-10":    _s("English",            "10", "202", "Languages",  "🔤", "english-(202)-syllabus"),
    "hindi-10":      _s("Hindi",              "10", "201", "Languages",  "🔤", "hindi-(201)-syllabus"),
}


def ensure_dirs():
    """Create all output directories if they don't exist."""
    for d in [CHAPTER_URLS_DIR, PDF_OUTPUT_ROOT, EXTRACTED_DIR, STRUCTURED_DIR, VERIFIED_DIR, SOLVED_DIR]:
        d.mkdir(parents=True, exist_ok=True)


if __name__ == "__main__":
    ensure_dirs()
    print(f"ROOT_DIR:       {ROOT_DIR}")
    print(f"PIPELINE_DIR:   {PIPELINE_DIR}")
    print(f"CONTENT_DIR:    {CONTENT_DIR}")
    print(f"OUTPUT_DIR:     {OUTPUT_DIR}")
    print(f"DeepSeek key:   {'set' if DEEPSEEK_API_KEY else 'MISSING'}")
    print(f"Claude key:     {'set' if CLAUDE_API_KEY else 'MISSING'}")
    print(f"Gemini key:     {'set' if GEMINI_API_KEY else 'MISSING'}")
    print(f"Groq key:       {'set' if GROQ_API_KEY else 'MISSING'}")
    print(f"Subjects:       {list(SUBJECTS.keys())}")
