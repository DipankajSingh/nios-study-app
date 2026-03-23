-- ── Migration 00003: Per-PYQ Attempt Tracking ──
-- Tracks every individual question a user attempts, enabling smart filters
-- (Unattempted / Review / Mastered) and driving SM-2 topic-level scheduling.

CREATE TABLE pyq_attempts (
    user_id     UUID    NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
    pyq_id      TEXT    NOT NULL REFERENCES pyqs(id) ON DELETE CASCADE,
    topic_id    TEXT    NOT NULL REFERENCES topics(id) ON DELETE CASCADE,   -- denormalized for fast SM-2 lookups
    subject_id  TEXT    NOT NULL REFERENCES subjects(id) ON DELETE CASCADE, -- denormalized for fast subject filtering
    -- rating: 'hard' → needs urgent review  |  'good' → normal spacing  |  'easy' → mastered
    rating      TEXT    NOT NULL DEFAULT 'hard' CHECK (rating IN ('hard', 'good', 'easy')),
    attempted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, pyq_id)
);

-- ── Row Level Security ──
ALTER TABLE pyq_attempts ENABLE ROW LEVEL SECURITY;
CREATE POLICY "own_attempts" ON pyq_attempts FOR ALL USING (auth.uid() = user_id);

-- ── Indexes ──
CREATE INDEX pyq_attempts_subject_idx ON pyq_attempts (user_id, subject_id);
CREATE INDEX pyq_attempts_topic_idx   ON pyq_attempts (user_id, topic_id, rating);
