-- NIOS Study App – Canonical D1 Schema
-- This is the source of truth. All subject data is seeded into these tables.

-- ============================================================
-- CATALOG (read-only, seeded from content pipeline)
-- ============================================================
--Might need to change in future--
CREATE TABLE IF NOT EXISTS Subject (
  id           TEXT PRIMARY KEY,
  name         TEXT NOT NULL,
  class_level  TEXT NOT NULL CHECK(class_level IN ('10', '12')),
  description  TEXT,
  icon         TEXT   -- emoji or asset key, e.g. '📐'
);

CREATE TABLE IF NOT EXISTS Chapter (
  id           TEXT PRIMARY KEY,
  subject_id   TEXT NOT NULL REFERENCES Subject(id),
  title        TEXT NOT NULL,
  order_index  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS Topic (
  id              TEXT PRIMARY KEY,
  chapter_id      TEXT NOT NULL REFERENCES Chapter(id),
  title           TEXT NOT NULL,
  order_index     INTEGER NOT NULL,
  high_yield_score INTEGER NOT NULL DEFAULT 50,  -- 0-100, used by plan generator
  est_minutes     INTEGER NOT NULL DEFAULT 15    -- estimated study time
);

-- AI-generated pedagogical content (pre-computed, stored per language)
CREATE TABLE IF NOT EXISTS TopicContent (
  id               TEXT PRIMARY KEY,
  topic_id         TEXT NOT NULL REFERENCES Topic(id),
  lang             TEXT NOT NULL CHECK(lang IN ('en', 'hi', 'hinglish')),
  summary_bullets  TEXT NOT NULL,  -- JSON array of bullet strings
  why_important    TEXT NOT NULL,
  common_mistakes  TEXT NOT NULL,  -- JSON array of mistake strings
  UNIQUE(topic_id, lang)
);

-- ============================================================
-- PYQ BANK
-- ============================================================

CREATE TABLE IF NOT EXISTS PYQ (
  id              TEXT PRIMARY KEY,
  subject_id      TEXT NOT NULL REFERENCES Subject(id),
  topic_id        TEXT NOT NULL REFERENCES Topic(id),
  year            TEXT NOT NULL,
  session         TEXT,           -- 'March' or 'October'
  question_text   TEXT NOT NULL,
  marks           INTEGER NOT NULL,
  difficulty      TEXT NOT NULL CHECK(difficulty IN ('easy', 'medium', 'hard')),
  frequency_score INTEGER NOT NULL DEFAULT 1,  -- how many times asked historically
  question_type   TEXT NOT NULL CHECK(question_type IN ('mcq', 'short', 'long', 'numerical'))
);

-- AI-generated step-by-step explanations per PYQ per language
CREATE TABLE IF NOT EXISTS PYQExplanation (
  id       TEXT PRIMARY KEY,
  pyq_id   TEXT NOT NULL REFERENCES PYQ(id),
  lang     TEXT NOT NULL CHECK(lang IN ('en', 'hi', 'hinglish')),
  steps    TEXT NOT NULL,  -- JSON array of step strings
  hints    TEXT NOT NULL,  -- JSON array of hint strings
  answer   TEXT,           -- brief model answer
  UNIQUE(pyq_id, lang)
);

-- ============================================================
-- USER (simple, client-generated UUID for now – no auth yet)
-- ============================================================

CREATE TABLE IF NOT EXISTS User (
  id               TEXT PRIMARY KEY,  -- client-generated UUID
  class_level      TEXT NOT NULL CHECK(class_level IN ('10', '12')),
  goal             TEXT NOT NULL CHECK(goal IN ('pass', 'sixty', 'eighty')),
  exam_date        TEXT NOT NULL,     -- ISO date string
  daily_minutes    INTEGER NOT NULL,
  preferred_lang   TEXT NOT NULL CHECK(preferred_lang IN ('en', 'hi', 'hinglish')),
  subjects         TEXT NOT NULL,     -- JSON array of subject IDs
  created_at       TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ============================================================
-- LEARNING PATH
-- ============================================================

CREATE TABLE IF NOT EXISTS LearningPath (
  id           TEXT PRIMARY KEY,
  user_id      TEXT NOT NULL REFERENCES User(id),
  subject_id   TEXT NOT NULL REFERENCES Subject(id),
  generated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS LearningPathStep (
  id            TEXT PRIMARY KEY,
  path_id       TEXT NOT NULL REFERENCES LearningPath(id),
  day_index     INTEGER NOT NULL,  -- 1 = today, 2 = tomorrow, etc.
  task_type     TEXT NOT NULL CHECK(task_type IN ('READ_NOTES', 'PRACTICE_PYQ_SET', 'REVISE_WRONGS')),
  topic_id      TEXT NOT NULL REFERENCES Topic(id),
  est_minutes   INTEGER NOT NULL
);

-- ============================================================
-- USER PROGRESS
-- ============================================================

CREATE TABLE IF NOT EXISTS UserProgress (
  id             TEXT PRIMARY KEY,
  user_id        TEXT NOT NULL REFERENCES User(id),
  topic_id       TEXT NOT NULL REFERENCES Topic(id),
  status         TEXT NOT NULL CHECK(status IN ('not_started', 'in_progress', 'done')) DEFAULT 'not_started',
  correct_count  INTEGER NOT NULL DEFAULT 0,
  incorrect_count INTEGER NOT NULL DEFAULT 0,
  last_reviewed  TEXT,
  UNIQUE(user_id, topic_id)
);

CREATE TABLE IF NOT EXISTS TaskCompletion (
  id           TEXT PRIMARY KEY,
  user_id      TEXT NOT NULL REFERENCES User(id),
  step_id      TEXT NOT NULL REFERENCES LearningPathStep(id),
  completed_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE(user_id, step_id)
);

-- ============================================================
-- INDEXES
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_chapter_subject ON Chapter(subject_id);
CREATE INDEX IF NOT EXISTS idx_topic_chapter   ON Topic(chapter_id);
CREATE INDEX IF NOT EXISTS idx_pyq_topic       ON PYQ(topic_id);
CREATE INDEX IF NOT EXISTS idx_pyq_subject     ON PYQ(subject_id);
CREATE INDEX IF NOT EXISTS idx_content_topic   ON TopicContent(topic_id);
CREATE INDEX IF NOT EXISTS idx_progress_user   ON UserProgress(user_id);
CREATE INDEX IF NOT EXISTS idx_step_path       ON LearningPathStep(path_id);
