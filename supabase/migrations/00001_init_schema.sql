-- ── Curriculum Data (Read-Heavy) ──

CREATE TABLE subjects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    class_level TEXT NOT NULL, -- "10" or "12"
    description TEXT,
    icon TEXT,
    total_marks INTEGER DEFAULT 100
);

CREATE TABLE chapters (
    id TEXT PRIMARY KEY,
    subject_id TEXT NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    order_index INTEGER NOT NULL
);

CREATE TABLE topics (
    id TEXT PRIMARY KEY,
    chapter_id TEXT NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    order_index INTEGER NOT NULL,
    prerequisite_topic_ids TEXT[] DEFAULT '{}',
    prerequisite_search_terms TEXT[] DEFAULT '{}',
    high_yield_score INTEGER DEFAULT 50,
    est_minutes INTEGER DEFAULT 15
);

CREATE TABLE topic_contents (
    id TEXT PRIMARY KEY,
    topic_id TEXT NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    lang TEXT DEFAULT 'en',
    summary_bullets JSONB NOT NULL,
    why_important TEXT,
    common_mistakes JSONB
);

CREATE TABLE pyqs (
    id TEXT PRIMARY KEY,
    subject_id TEXT NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    topic_id TEXT NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    year TEXT DEFAULT '2024',
    session TEXT DEFAULT 'March',
    question_text TEXT NOT NULL,
    marks INTEGER DEFAULT 5,
    difficulty TEXT DEFAULT 'medium',
    frequency_score INTEGER DEFAULT 5,
    question_type TEXT DEFAULT 'short'
);

CREATE TABLE pyq_explanations (
    id TEXT PRIMARY KEY,
    pyq_id TEXT NOT NULL REFERENCES pyqs(id) ON DELETE CASCADE,
    lang TEXT DEFAULT 'en',
    steps JSONB NOT NULL,
    hints JSONB,
    answer TEXT,
    common_errors TEXT
);


-- ── Search & Performance Extensions ──
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS vector;

-- ── Indexes for Fast FTS and Trigram Search ──
-- 1. Index on topic title for instant Typo-Tolerant Trigram Auto-complete
CREATE INDEX topics_title_trgm_idx ON topics USING gin (title gin_trgm_ops);

-- 2. Index on PYQs for ultra-fast Full Text Search
CREATE INDEX pyqs_question_fts_idx ON pyqs USING gin (to_tsvector('english', question_text));

-- 3. Embeddings Column for AI Semantic Search (Future Proofing)
ALTER TABLE topics ADD COLUMN embedding vector(768);
CREATE INDEX topics_embedding_idx ON topics USING hnsw (embedding vector_cosine_ops);
