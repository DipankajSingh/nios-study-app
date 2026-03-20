# Study App — Project State
> Last updated: 2026-03-21

## What This App Is
A smart last-minute revision app for **Class 11 & 12 students**. Uses spaced repetition, PYQ performance, and user-set goals to prioritise what to study.

---

## Scope (Confirmed)
- **Grades:** 11 and 12 only
- **Source dataset:** `content/ncert_dataset.json` (~123K rows, NCERT content)
- **Subjects (same list for both grades):**

| Subject | In DB |
|---|---|
| Physics | ✅ |
| Chemistry | ✅ |
| Biology | ✅ |
| Accountancy | ✅ |
| Business Studies | ✅ |
| Political Science | ✅ |
| Geography | ✅ |
| History | ✅ |
| Sociology | ✅ |
| Economics | ✅ |
| Psychology | ✅ |

> ❌ No Math, English, or Hindi — not in source dataset

---

## Tech Stack
| Layer | Tech |
|---|---|
| Frontend | Expo SDK 54 (React Native) — web/Android/iOS |
| Styling | NativeWind v4 (Tailwind) |
| Backend | Supabase (PostgreSQL) — local Docker |
| Auth | Supabase Auth — email/password + Google OAuth (placeholder) + skip |
| Language | JavaScript (no TypeScript) |
| Routing | Expo Router (file-based) |

---

## Task Checklist

### Auth Screens
- [x] Welcome — Skip, Google (placeholder), email sign-up/in
- [x] Sign-in — responsive, back button, Skip
- [x] Sign-up — responsive, back button, Skip
- [x] Root `index.jsx` redirects to `/(auth)/welcome`
- [x] AuthGate — skip flow allowed through onboarding + tabs
- [ ] Google OAuth (needs Client ID from Google Console)
- [ ] Anonymous → real user upgrade after sign-up

### Onboarding Screens
- [x] Class picker (`class.jsx`) — grades 11 & 12 only, back button, responsive
- [x] Subject picker (`subjects.jsx`) — fetches from DB, back button, responsive
- [x] Goals screen (`goals.jsx`) — daily time picker + exam date, back button, responsive
- [x] **Date picker crash on web fixed** — HTML `<input type="date">` on web
- [x] Baseline quiz (`baseline.jsx`) — self-assessment, skippable
- [ ] Wire `baseline_completed` flag in AuthGate to skip onboarding on return visits

### Main Tabs
- [x] Home tab scaffold — streak, exam countdown, daily goal bar, stats cards
- [x] Learning tab scaffold — urgent suggestions + subject list
- [x] PYQ tab scaffold — full-text search
- [ ] Subject → Chapter → Topic drill-down screens
- [ ] Topic detail / study view
- [ ] PYQ answer / explanation modal

### Responsiveness
- [x] Auth screens — maxWidth 480
- [x] Onboarding screens — maxWidth 520
- [x] Tab screens — maxWidth 700, flex-wrap

### Database — Subjects & Content
- [x] **22 subjects seeded** — 11 subjects × 2 grades (11 & 12)
- [x] **22,479 topics seeded** from ncert_dataset.json
- [x] **91,916 PYQs seeded** from ncert_dataset.json
- [x] **91,916 PYQ explanations seeded**
- [x] User tracking tables: `user_profiles`, `user_subjects`, `user_progress`, `baseline_results`, `study_sessions`
- [x] Row Level Security (RLS) enabled on all user tables
- [x] Pipeline script (`pipeline/01_build_ncert/build.py`) updated and working

### Spaced Repetition
- [x] DB schema: SM-2 fields (`ease_factor`, `next_review_at`, `needs_urgent_review`)
- [ ] SM-2 algorithm runtime
- [ ] Streak calculation

### Secondary (not started)
- [ ] Leaderboard
- [ ] Push notifications
- [ ] AI "explain this"
- [ ] Offline mode

---

## Database Schema (Quick Reference)

### Curriculum
- `subjects` — id, name, class_level, icon, total_marks
- `chapters` — id, subject_id, title, order_index
- `topics` — id, chapter_id, title, prerequisites[], high_yield_score, est_minutes
- `topic_contents` — summary_bullets (JSONB), why_important, common_mistakes
- `pyqs` — question_text, year, marks, difficulty, subject_id, topic_id
- `pyq_explanations` — steps, hints, answer, common_errors

### User Tracking
- `user_profiles` — class_level, exam_date, daily_goal_minutes, streak_days, baseline_completed
- `user_subjects` — user_id + subject_id
- `user_progress` — topic_id, ease_factor, interval_days, next_review_at, needs_urgent_review
- `baseline_results` — subject_id, score_percent
- `study_sessions` — date, minutes_studied

---

## Known Issues
- [ ] `baseline_completed` flag not used in AuthGate yet (users re-onboard on every login)
- [ ] Google OAuth is a placeholder — shows "Coming soon" alert

---

## How to Run
```bash
npx supabase start       # start local DB (Docker required)
cd frontend
npx expo start --web --port 8083
```

---

## Re-seeding the Database
```bash
# Regenerate seed.sql from ncert_dataset.json
cd pipeline && python3 01_build_ncert/build.py

# Apply to local Supabase (requires Docker)
docker cp supabase/seed.sql supabase_db_nios-study-app:/tmp/seed.sql
docker exec supabase_db_nios-study-app psql -U postgres -d postgres -f /tmp/seed.sql
```

## Branch
`ncert-migration` on `https://github.com/DipankajSingh/nios-study-app`
