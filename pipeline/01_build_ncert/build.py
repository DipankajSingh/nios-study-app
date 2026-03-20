"""
build.py — Seed generator for the Study App

Reads: content/ncert_dataset.json  (HuggingFace: ParthKadam2003/NCERT_Dataset)
Writes: supabase/seed.sql

Scope:
  - Grades: 11, 12
  - Subjects: Physics, Chemistry, Biology, Accountancy, Business Studies,
               Political Science, Geography, History, Sociology,
               Economics, Psychology
  - No limit cap — processes the full dataset
"""

import os
import json
import uuid

# ── Config ────────────────────────────────────────────────────────────────────

SUPPORTED_GRADES = {"11", "12"}

# Map raw dataset subject names → canonical subject names + icons
SUBJECT_WHITELIST = {
    "physics":           ("Physics",           "⚛️"),
    "chemistry":         ("Chemistry",         "🧪"),
    "biology":           ("Biology",           "🌱"),
    "accountancy":       ("Accountancy",       "🧾"),
    "business studies":  ("Business Studies",  "💼"),
    "political science": ("Political Science", "🗳️"),
    "geography":         ("Geography",         "🗺️"),
    "history":           ("History",           "🏛️"),
    "socialogy":         ("Sociology",         "🧑‍🤝‍🧑"),   # dataset has this typo
    "sociology":         ("Sociology",         "🧑‍🤝‍🧑"),
    "economics":         ("Economics",         "📊"),
    "psychology":        ("Psychology",        "🧠"),
}

LOCAL_PATH = "/home/dipankaj/Desktop/nios-study-app/content/ncert_dataset.json"
OUT_PATH   = "/home/dipankaj/Desktop/nios-study-app/supabase/seed.sql"

# ── Helpers ───────────────────────────────────────────────────────────────────

def generate_id():
    return uuid.uuid4().hex[:8]

def dq(s):
    """Dollar-quote a string for safe PostgreSQL embedding."""
    clean = str(s).replace("$$", " ").strip()
    return f"$${clean}$$"

# ── Main ──────────────────────────────────────────────────────────────────────

def run():
    print(f"Loading dataset from {LOCAL_PATH}...")

    # Stream line-by-line to avoid loading entire 118MB into RAM at once
    rows = []
    with open(LOCAL_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    print(f"Loaded {len(rows):,} rows. Filtering and building SQL...")

    subjects_map  = {}   # subject_id → True
    chapters_map  = {}   # subject_id → chapter_id
    topics_set    = {}   # "{subject_id}-{topic_title}" → topic_id

    subs_sql     = []
    chaps_sql    = []
    topics_sql   = []
    tcontents_sql = []
    pyqs_sql     = []
    exps_sql     = []

    skipped = 0

    for row in rows:
        grade     = str(row.get("grade", "")).strip()
        subj_raw  = str(row.get("subject", "")).strip().lower()

        # Filter: grade and subject whitelist
        if grade not in SUPPORTED_GRADES:
            skipped += 1
            continue
        if subj_raw not in SUBJECT_WHITELIST:
            skipped += 1
            continue

        canonical_name, icon = SUBJECT_WHITELIST[subj_raw]
        subject_id = f"{canonical_name.lower().replace(' ', '-')}-{grade}"

        # ── 1. Subject (once per subject_id) ────────────────────────────────
        if subject_id not in subjects_map:
            subjects_map[subject_id] = True
            subs_sql.append(
                f"({dq(subject_id)}, {dq(canonical_name)}, {dq(grade)}, "
                f"{dq(f'Class {grade} {canonical_name}')}, {dq(icon)}, 100)"
            )
            chapter_id = f"{subject_id}-ch01"
            chapters_map[subject_id] = chapter_id
            chaps_sql.append(
                f"({dq(chapter_id)}, {dq(subject_id)}, "
                f"{dq('All ' + canonical_name + ' Concepts')}, 1)"
            )

        chapter_id = chapters_map[subject_id]

        # ── 2. Topic (deduplicated by title within subject) ──────────────────
        topic_title = str(row.get("Topic", "General Topic")).strip()
        topic_key   = f"{subject_id}::{topic_title}"

        if topic_key not in topics_set:
            topic_id = f"{subject_id}-t{len(topics_set)}"
            topics_set[topic_key] = topic_id

            try:
                est_time = int(float(row.get("EstimatedTime", 15)))
            except (ValueError, TypeError):
                est_time = 15

            try:
                complexity = float(row.get("QuestionComplexity", 5))
                high_yield = min(100, max(0, int(complexity * 10)))
            except (ValueError, TypeError):
                high_yield = 50

            raw_prereq  = str(row.get("Prerequisites", ""))
            prereq_list = [
                p.strip() for p in raw_prereq.replace(";", ",").replace(" and ", ",").split(",")
                if len(p.strip()) > 2
            ]
            prereq_terms = (
                dq("{" + ",".join([f'"{p}"' for p in prereq_list]) + "}")
                if prereq_list else "DEFAULT"
            )

            topics_sql.append(
                f"({dq(topic_id)}, {dq(chapter_id)}, {dq(topic_title)}, "
                f"{len(topics_set)}, DEFAULT, {prereq_terms}, {high_yield}, {est_time})"
            )

            # topic_contents — bullets from Explanation field
            explanation = str(row.get("Explanation", ""))
            bullets = [s.strip() + "." for s in explanation.split(".") if len(s.strip()) > 5][:5]
            if not bullets:
                bullets = [topic_title]
            why_imp = dq(raw_prereq or "Essential exam concept")

            tcontents_sql.append(
                f"({dq('tc-' + topic_id)}, {dq(topic_id)}, 'en', "
                f"{dq(json.dumps(bullets))}::jsonb, {why_imp}, "
                f"{dq(json.dumps([]))}::jsonb)"
            )

        topic_id = topics_set[topic_key]

        # ── 3. PYQ ──────────────────────────────────────────────────────────
        pyq_id   = f"pyq-{generate_id()}"
        diff_raw = str(row.get("Difficulty", "Medium")).strip().lower()
        if diff_raw not in ("easy", "medium", "hard"):
            diff_raw = "medium"
        q_text = str(row.get("Question", "")).strip()
        if not q_text:
            continue

        pyqs_sql.append(
            f"({dq(pyq_id)}, {dq(subject_id)}, {dq(topic_id)}, "
            f"'2024', 'March', {dq(q_text)}, 5, {dq(diff_raw)}, 5, 'short')"
        )

        # ── 4. PYQ Explanation ───────────────────────────────────────────────
        answer = str(row.get("Answer", "")).strip()
        exps_sql.append(
            f"({dq('exp-' + pyq_id)}, {dq(pyq_id)}, 'en', "
            f"{dq(json.dumps([answer]))}::jsonb, "
            f"{dq(json.dumps([]))}::jsonb, "
            f"{dq(answer)}, {dq('')})"
        )

    print(f"Skipped {skipped:,} rows (out of scope grade/subject).")
    print(f"Subjects: {len(subs_sql)}, Topics: {len(topics_set):,}, PYQs: {len(pyqs_sql):,}")

    # ── Write seed.sql ────────────────────────────────────────────────────────
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write("-- Auto-generated seed: Class 11 & 12, all subjects\n\n")

        if subs_sql:
            f.write("INSERT INTO subjects (id, name, class_level, description, icon, total_marks) VALUES\n")
            f.write(",\n".join(subs_sql) + "\nON CONFLICT (id) DO NOTHING;\n\n")

        if chaps_sql:
            f.write("INSERT INTO chapters (id, subject_id, title, order_index) VALUES\n")
            f.write(",\n".join(chaps_sql) + "\nON CONFLICT (id) DO NOTHING;\n\n")

        if topics_sql:
            f.write("INSERT INTO topics (id, chapter_id, title, order_index, prerequisite_topic_ids, prerequisite_search_terms, high_yield_score, est_minutes) VALUES\n")
            f.write(",\n".join(topics_sql) + "\nON CONFLICT (id) DO NOTHING;\n\n")

        if tcontents_sql:
            f.write("INSERT INTO topic_contents (id, topic_id, lang, summary_bullets, why_important, common_mistakes) VALUES\n")
            f.write(",\n".join(tcontents_sql) + "\nON CONFLICT (id) DO NOTHING;\n\n")

        if pyqs_sql:
            f.write("INSERT INTO pyqs (id, subject_id, topic_id, year, session, question_text, marks, difficulty, frequency_score, question_type) VALUES\n")
            f.write(",\n".join(pyqs_sql) + "\nON CONFLICT (id) DO NOTHING;\n\n")

        if exps_sql:
            f.write("INSERT INTO pyq_explanations (id, pyq_id, lang, steps, hints, answer, common_errors) VALUES\n")
            f.write(",\n".join(exps_sql) + "\nON CONFLICT (id) DO NOTHING;\n\n")

    print(f"\n✅ Seed written to {OUT_PATH}")
    print(f"   {len(subs_sql)} subjects, {len(chaps_sql)} chapters, {len(topics_set)} topics, {len(pyqs_sql)} PYQs")


if __name__ == "__main__":
    run()
