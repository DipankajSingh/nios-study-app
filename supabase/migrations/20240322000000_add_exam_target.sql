-- Add exam_target to user_profiles
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS exam_target TEXT DEFAULT 'pass';
