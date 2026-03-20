-- ── Migration 00002: User Profiles & Spaced Repetition Progress Tracking ──

-- Extended user profile (supplements the base auth.users row)
CREATE TABLE user_profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    display_name TEXT,
    class_level TEXT NOT NULL DEFAULT '12',          -- '10' or '12'
    exam_date DATE,
    daily_goal_minutes INTEGER NOT NULL DEFAULT 60,
    streak_days INTEGER NOT NULL DEFAULT 0,
    last_goal_met_date DATE,                         -- for streak calculation
    baseline_completed BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Linking table: which subjects the user has selected
CREATE TABLE user_subjects (
    user_id UUID NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
    subject_id TEXT NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, subject_id)
);

-- Spaced repetition: tracks per-topic study state per user
CREATE TABLE user_progress (
    user_id UUID NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
    topic_id TEXT NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, topic_id),

    -- Repetition Schedule (Hybrid: time-decay + PYQ performance)
    repetition_interval_days INTEGER NOT NULL DEFAULT 7,   -- days until next review
    ease_factor REAL NOT NULL DEFAULT 2.5,                 -- SM-2 style multiplier
    next_review_at DATE NOT NULL DEFAULT CURRENT_DATE + 7,
    last_studied_at TIMESTAMPTZ,

    -- Override: failed a PYQ on this topic → urgent review
    needs_urgent_review BOOLEAN NOT NULL DEFAULT FALSE,

    -- Minutes studied count (to track daily goal completion)
    total_studied_minutes INTEGER NOT NULL DEFAULT 0
);

-- Baseline quiz results per subject
CREATE TABLE baseline_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
    subject_id TEXT NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    score_percent INTEGER NOT NULL DEFAULT 0,    -- 0–100
    attempted_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Daily study sessions for streak computation
CREATE TABLE study_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
    session_date DATE NOT NULL DEFAULT CURRENT_DATE,
    total_minutes INTEGER NOT NULL DEFAULT 0,
    goal_met BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (user_id, session_date)
);

-- ── Row Level Security (RLS) ──
ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_subjects ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_progress ENABLE ROW LEVEL SECURITY;
ALTER TABLE baseline_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE study_sessions ENABLE ROW LEVEL SECURITY;

-- Users can only see and modify their own data
CREATE POLICY "own_profile" ON user_profiles FOR ALL USING (auth.uid() = id);
CREATE POLICY "own_subjects" ON user_subjects FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "own_progress" ON user_progress FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "own_baseline" ON baseline_results FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "own_sessions" ON study_sessions FOR ALL USING (auth.uid() = user_id);

-- ── Indexes ──
CREATE INDEX user_progress_next_review_idx ON user_progress (user_id, next_review_at);
CREATE INDEX study_sessions_date_idx ON study_sessions (user_id, session_date);
