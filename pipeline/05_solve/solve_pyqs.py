#!/usr/bin/env python3
"""
Stage 5 — Solve PYQs (Past Year Questions)

Takes raw PYQ PDFs, extracts questions, and sends them to Claude for
step-by-step solutions with difficulty ratings and common error analysis.

Usage:
    cd pipeline
    python -m 05_solve.solve_pyqs --subject maths-12 [--resume]

Input: PYQ PDF scans in content/class12/<subject>/pyqs_raw/
Output: SolvedPYQSet JSON in output/solved/<subject>_pyqs.json

For each question, Claude provides:
  - Step-by-step solution with LaTeX
  - Difficulty rating (easy/medium/hard)
  - Common errors analysis
  - Mark distribution hints
"""

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import (
    CLAUDE_API_KEY, CLAUDE_BASE_URL, CLAUDE_MODEL,
    SOLVED_DIR, SUBJECTS, RATE_LIMIT_PAUSE, MAX_RETRIES,
    ensure_dirs,
)
from schemas import PYQ, PYQExplanation, SolvedPYQSet, Difficulty, QuestionType, Lang

# Reuse a single httpx client for connection pooling across all API calls
_http_client: httpx.Client | None = None

def _get_client() -> httpx.Client:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.Client(timeout=120)
    return _http_client


# ── Prompts ──────────────────────────────────────────────────────────────────

EXTRACTION_PROMPT = """\
You are an expert NIOS exam paper analyzer. Given the text of a Past Year Question paper, 
extract individual questions as a JSON array.

For each question, determine:
- question_text: The full question text (use LaTeX for math: $...$)
- marks: Number of marks (look for mark indicators like [2], (3 marks), etc.)
- question_type: "mcq", "short", "long", or "numerical"
- estimated_difficulty: "easy", "medium", or "hard"
- topic_hint: What topic this question likely belongs to

Output JSON array:
[
  {
    "question_text": "...",
    "marks": 2,
    "question_type": "short",
    "estimated_difficulty": "easy",
    "topic_hint": "Sets and Relations"
  }
]

Rules:
- Extract ALL questions, including sub-parts (a), (b), (c) as part of the parent question
- Preserve mathematical notation using LaTeX
- If marks are not visible, estimate from question length/complexity
- Be precise about the question text — do not rephrase
"""

SOLUTION_PROMPT = """\
You are a strict NIOS examiner and expert teacher. Solve the following Past Year Question 
from the NIOS {subject_name} (Code: {subject_code}) exam.

Question ({marks} marks, {year} {session}):
{question_text}

Provide:
1. **steps**: A JSON array of solution steps. Each step should be clear and use LaTeX for 
   math ($inline$ and $$display$$). Steps should match how marks are awarded.
2. **hints**: A JSON array of hints that would help a struggling student attempt this.
3. **answer**: A brief final answer (1-2 sentences).
4. **common_errors**: Where students most commonly lose marks on this specific question.
5. **difficulty**: Your assessment: "easy", "medium", or "hard".

Respond ONLY with this JSON:
{{
  "steps": ["Step 1: ...", "Step 2: ..."],
  "hints": ["Hint 1: ...", "Hint 2: ..."],
  "answer": "...",
  "common_errors": "...",
  "difficulty": "easy|medium|hard"
}}

RULES:
- Use LaTeX for ALL math notation
- Each step should clearly explain the mathematical reasoning
- Steps should follow NIOS marking scheme conventions
- Be concise but complete
"""


# ── API calls ────────────────────────────────────────────────────────────────

@retry(stop=stop_after_attempt(MAX_RETRIES), wait=wait_exponential(min=2, max=30))
def call_claude(prompt: str, system: str = "") -> str:
    """Call Claude API and return the text response."""
    headers = {
        "x-api-key": CLAUDE_API_KEY,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    payload = {
        "model": CLAUDE_MODEL,
        "max_tokens": 4096,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        payload["system"] = system

    client = _get_client()
    resp = client.post(CLAUDE_BASE_URL, headers=headers, json=payload)
    resp.raise_for_status()

    return resp.json()["content"][0]["text"]


def extract_questions_from_text(paper_text: str) -> list[dict]:
    """Send PYQ paper text to Claude for question extraction."""
    prompt = f"{EXTRACTION_PROMPT}\n\n---\nPAPER TEXT:\n{paper_text}\n---"
    response = call_claude(prompt)

    # Parse JSON from response
    response = response.strip()
    if response.startswith("```"):
        response = re.sub(r"^```(?:json)?\n?", "", response)
        response = re.sub(r"\n?```$", "", response)

    return json.loads(response)


def solve_question(question: dict, subject_cfg: dict, year: str, session: str) -> dict:
    """Send a single question to Claude for step-by-step solution."""
    prompt = SOLUTION_PROMPT.format(
        subject_name=subject_cfg["name"],
        subject_code=subject_cfg["code"],
        marks=question.get("marks", 2),
        year=year,
        session=session,
        question_text=question["question_text"],
    )

    response = call_claude(prompt)
    response = response.strip()
    if response.startswith("```"):
        response = re.sub(r"^```(?:json)?\n?", "", response)
        response = re.sub(r"\n?```$", "", response)

    return json.loads(response)


# ── PYQ text extraction (from raw text or pre-extracted) ─────────────────────

def read_pyq_paper(pyq_file: Path) -> tuple[str, str, str]:
    """Read a PYQ file and extract (text, year, session).
    
    Supports:
    - .txt files (pre-extracted text)
    - .json files (pre-structured)
    - .pdf files (needs OCR — prints warning)
    """
    filename = pyq_file.stem  # e.g. "2015_April"

    # Parse year and session from filename
    match = re.match(r"(\d{4})_?(April|October|March|Nov)?", filename, re.IGNORECASE)
    year = match.group(1) if match else "unknown"
    session = match.group(2) if match and match.group(2) else ""

    if pyq_file.suffix == ".txt":
        return pyq_file.read_text(encoding="utf-8"), year, session
    elif pyq_file.suffix == ".json":
        data = json.loads(pyq_file.read_text())
        return json.dumps(data), year, session
    elif pyq_file.suffix == ".pdf":
        print(f"    ⚠️  PDF PYQs need extraction first. Run extract_pdf.py in Colab with PYQ PDFs.")
        print(f"    ⚠️  Or manually create a .txt file with the extracted text.")
        return "", year, session
    else:
        return "", year, session


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Stage 5: Solve PYQs via Claude")
    parser.add_argument("--subject", required=True)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    ensure_dirs()

    if args.subject not in SUBJECTS:
        print(f"❌ Unknown subject '{args.subject}'")
        sys.exit(1)

    if not CLAUDE_API_KEY:
        print("❌ CLAUDE_API_KEY not set in .env")
        sys.exit(1)

    subject_cfg = SUBJECTS[args.subject]
    pyq_dir = subject_cfg["pyq_dir"]

    if not pyq_dir.exists():
        print(f"❌ PYQ directory not found: {pyq_dir}")
        sys.exit(1)

    # Find PYQ files (prefer .txt, fall back to .pdf)
    pyq_files = sorted(list(pyq_dir.glob("*.txt")) + list(pyq_dir.glob("*.pdf")))
    if not pyq_files:
        print(f"❌ No PYQ files found in {pyq_dir}")
        print(f"   Place PYQ text files as .txt (or .pdf for Colab extraction)")
        sys.exit(1)

    print(f"📝 PYQ Solver: {subject_cfg['name']} ({args.subject})")
    print(f"   Found {len(pyq_files)} PYQ papers\n")

    # Checkpoint
    output_file = SOLVED_DIR / f"{args.subject}_pyqs.json"
    checkpoint_file = SOLVED_DIR / f"{args.subject}_pyqs.checkpoint.json"
    done_papers: dict = {}
    if args.resume and checkpoint_file.exists():
        done_papers = json.loads(checkpoint_file.read_text())

    all_pyqs: list[PYQ] = []
    all_explanations: list[PYQExplanation] = []
    pyq_counter = 0

    for pyq_file in pyq_files:
        paper_key = pyq_file.stem
        if paper_key in done_papers:
            # Load from checkpoint
            saved = done_papers[paper_key]
            all_pyqs.extend(PYQ.model_validate(p) for p in saved.get("pyqs", []))
            all_explanations.extend(PYQExplanation.model_validate(e) for e in saved.get("explanations", []))
            pyq_counter = max(pyq_counter, max((int(p["id"].split("-q")[1]) for p in saved.get("pyqs", [])), default=0))
            print(f"  ⏭️  Skipping {pyq_file.name} (already solved)")
            continue

        print(f"\n  📄 Processing: {pyq_file.name}")
        text, year, session = read_pyq_paper(pyq_file)
        if not text:
            continue

        # Step 1: Extract questions
        print(f"    Extracting questions...")
        try:
            questions = extract_questions_from_text(text)
            print(f"    Found {len(questions)} questions")
        except Exception as e:
            print(f"    ❌ Extraction failed: {e}")
            continue

        time.sleep(RATE_LIMIT_PAUSE)

        # Step 2: Solve each question
        paper_pyqs = []
        paper_explanations = []

        for q_idx, question in enumerate(questions, 1):
            pyq_counter += 1
            pyq_id = f"pyq-{args.subject}-q{pyq_counter:04d}"

            print(f"    Solving Q{q_idx}/{len(questions)} ({question.get('marks', '?')} marks)...", end=" ", flush=True)
            try:
                solution = solve_question(question, subject_cfg, year, session)

                pyq = PYQ(
                    id=pyq_id,
                    subject_id=args.subject,
                    topic_id="",  # Will be mapped in a post-processing step
                    year=year,
                    session=session.capitalize() if session else "",
                    question_text=question["question_text"],
                    marks=question.get("marks", 2),
                    difficulty=Difficulty(solution.get("difficulty", question.get("estimated_difficulty", "medium"))),
                    frequency_score=1,
                    question_type=QuestionType(question.get("question_type", "short")),
                )
                paper_pyqs.append(pyq)

                explanation = PYQExplanation(
                    id=f"exp-{pyq_id}-en",
                    pyq_id=pyq_id,
                    lang=Lang.EN,
                    steps=solution.get("steps", []),
                    hints=solution.get("hints", []),
                    answer=solution.get("answer", ""),
                    common_errors=solution.get("common_errors", ""),
                )
                paper_explanations.append(explanation)
                print("✅")

            except Exception as e:
                print(f"❌ {e}")

            time.sleep(RATE_LIMIT_PAUSE)

        # Save checkpoint
        all_pyqs.extend(paper_pyqs)
        all_explanations.extend(paper_explanations)
        done_papers[paper_key] = {
            "pyqs": [p.model_dump() for p in paper_pyqs],
            "explanations": [e.model_dump() for e in paper_explanations],
        }
        checkpoint_file.write_text(json.dumps(done_papers, indent=2, default=str))
        print(f"    💾 Saved ({len(paper_pyqs)} pyqs from this paper)")

    # Write final output
    result = SolvedPYQSet(
        subject_id=args.subject,
        solved_at=datetime.now(timezone.utc).isoformat(),
        pyqs=all_pyqs,
        explanations=all_explanations,
    )
    output_file.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    print(f"\n🎉 Done! {len(all_pyqs)} PYQs solved → {output_file}")


if __name__ == "__main__":
    main()
