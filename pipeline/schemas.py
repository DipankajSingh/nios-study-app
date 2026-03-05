"""
Pydantic Schemas — Single source of truth for ALL data shapes in the pipeline.

Every pipeline stage reads and writes these models.
The backend TypeScript types and the SQL schema must stay in sync with these.
"""

from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


# ══════════════════════════════════════════════════════════════════════════════
# ENUMS
# ══════════════════════════════════════════════════════════════════════════════

class ClassLevel(str, Enum):
    TEN = "10"
    TWELVE = "12"

class Lang(str, Enum):
    EN = "en"
    HI = "hi"
    HINGLISH = "hinglish"

class Difficulty(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"

class QuestionType(str, Enum):
    MCQ = "mcq"
    SHORT = "short"
    LONG = "long"
    NUMERICAL = "numerical"

class ContentBlockType(str, Enum):
    CONCEPT = "CONCEPT"
    FORMULA = "FORMULA"
    DIAGRAM = "DIAGRAM"
    CODE_SNIPPET = "CODE_SNIPPET"
    COMMON_MISTAKE = "COMMON_MISTAKE"

class GoalTier(str, Enum):
    CORE = "CORE"          # Must know to pass
    STANDARD = "STANDARD"  # Needed for 60-75%
    ADVANCED = "ADVANCED"  # Differentiates 80%+ scorers


# ══════════════════════════════════════════════════════════════════════════════
# CATALOG MODELS (read-only, produced by pipeline)
# ══════════════════════════════════════════════════════════════════════════════

class Subject(BaseModel):
    id: str                         # e.g. "maths-12"
    name: str
    class_level: ClassLevel
    code: str                       # NIOS subject code, e.g. "311"
    description: str = ""
    icon: str = "📘"
    total_marks: int = 100

class Chapter(BaseModel):
    id: str                         # e.g. "maths-12-ch01"
    subject_id: str
    title: str                      # human-readable, e.g. "Sets"
    order_index: int
    expected_weightage: int = 0     # marks typically from this chapter in exams

class Topic(BaseModel):
    id: str                         # e.g. "maths-12-ch01-t01"
    chapter_id: str
    title: str                      # meaningful name, e.g. "Definition and Representation of Sets"
    order_index: int
    goal_tier: GoalTier = GoalTier.STANDARD
    high_yield_score: int = Field(default=50, ge=0, le=100)
    est_minutes: int = Field(default=15, ge=1)
    prerequisite_topic_ids: list[str] = []
    related_topic_ids: list[str] = []


# ══════════════════════════════════════════════════════════════════════════════
# CONTENT MODELS (AI-generated, must be verified)
# ══════════════════════════════════════════════════════════════════════════════

class ContentBlock(BaseModel):
    """Atomic piece of educational content tied to a topic.
    
    The `exact_source_quote` field is MANDATORY for verification.
    Blocks without a valid quote that matches the source PDF text
    are rejected by the verification stage.
    """
    id: str
    topic_id: str
    type: ContentBlockType
    content_text: Optional[str] = None        # Markdown/LaTeX
    code_content: Optional[str] = None        # Exact code block
    code_language: Optional[str] = None       # "cpp", "python", "html", "sql"
    media_url: Optional[str] = None           # Cloudflare R2 URL
    media_caption: Optional[str] = None

    # ── Verification (MANDATORY) ──
    source_pdf_name: str
    source_page_number: int = 0
    exact_source_quote: Optional[str] = None  # Verbatim text from PDF
    is_verified: bool = False


class TopicContent(BaseModel):
    """Summarised pedagogical content for a topic in a specific language.
    Produced by the structuring stage from raw extracted text.
    """
    id: str                                   # e.g. "tc-maths-12-ch01-t01-en"
    topic_id: str
    lang: Lang
    summary_bullets: list[str]
    why_important: str
    common_mistakes: list[str]


# ══════════════════════════════════════════════════════════════════════════════
# PYQ MODELS
# ══════════════════════════════════════════════════════════════════════════════

class PYQ(BaseModel):
    """A Past Year Question extracted from NIOS exam papers."""
    id: str
    subject_id: str
    topic_id: str
    year: str                                 # e.g. "2023"
    session: str = ""                         # "March" or "October"
    question_text: str                        # Supports LaTeX
    marks: int
    difficulty: Difficulty = Difficulty.MEDIUM
    frequency_score: int = Field(default=1, ge=1, le=10)
    question_type: QuestionType = QuestionType.SHORT
    question_media_url: Optional[str] = None
    is_verified: bool = False

class PYQExplanation(BaseModel):
    """AI-generated step-by-step solution for a PYQ."""
    id: str
    pyq_id: str
    lang: Lang
    steps: list[str]                          # Step-by-step solution
    hints: list[str]                          # Hints for the student
    answer: str = ""                          # Brief model answer
    common_errors: str = ""                   # Where students lose marks


# ══════════════════════════════════════════════════════════════════════════════
# PIPELINE INTERMEDIATE MODELS
# ══════════════════════════════════════════════════════════════════════════════

class ExtractedChapter(BaseModel):
    """Output of Stage 2 (extraction): one chapter's worth of raw text."""
    chapter_id: str
    chapter_title: str
    order_index: int
    source_pdf: str
    markdown_text: str                        # Full extracted markdown
    image_paths: list[str] = []               # Local paths to extracted images

class ExtractedSubject(BaseModel):
    """Full extraction output for one subject."""
    subject: Subject
    extracted_at: str                         # ISO datetime
    chapters: list[ExtractedChapter]

class StructuredChapter(BaseModel):
    """Output of Stage 3 (structuring): parsed topics with content."""
    chapter: Chapter
    topics: list[Topic]
    topic_contents: list[TopicContent]
    content_blocks: list[ContentBlock] = []

class StructuredSubject(BaseModel):
    """Full structuring output for one subject."""
    subject: Subject
    structured_at: str
    chapters: list[StructuredChapter]

class VerifiedSubject(BaseModel):
    """Output of Stage 4 (verification): only verified content survives."""
    subject: Subject
    verified_at: str
    chapters: list[StructuredChapter]
    stats: VerificationStats

class VerificationStats(BaseModel):
    total_blocks: int = 0
    verified_blocks: int = 0
    rejected_blocks: int = 0
    total_topics: int = 0
    topics_with_content: int = 0

# Allow forward reference resolution
VerifiedSubject.model_rebuild()


class SolvedPYQSet(BaseModel):
    """Output of Stage 5 (solve): PYQs with solutions."""
    subject_id: str
    solved_at: str
    pyqs: list[PYQ]
    explanations: list[PYQExplanation]


# ══════════════════════════════════════════════════════════════════════════════
# SEED OUTPUT (what goes into backend/src/data/)
# ══════════════════════════════════════════════════════════════════════════════

class SeedData(BaseModel):
    """Complete dataset ready to be written as TypeScript for the backend."""
    generated_at: str
    subjects: list[Subject]
    chapters: list[Chapter]
    topics: list[Topic]
    topic_contents: list[TopicContent]
    pyqs: list[PYQ]
    pyq_explanations: list[PYQExplanation]
