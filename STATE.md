# Study App — Project State
> Last updated: 2026-03-21

## What This App Is
A last-minute smart revision app for **students in classes 10, 11, and 12**. It uses spaced repetition, PYQ performance, and user-set goals to tell students exactly what to study — and in what order.

---

## Tech Stack
| Layer | Tech |
|---|---|
| Frontend | Expo (SDK 54, React Native) — universal web/Android/iOS |
| Styling | NativeWind v4 (TailwindCSS) — respects system dark/light mode |
| Backend | Supabase (PostgreSQL) — local Docker instance |
| Auth | Supabase Auth — email/password + Google OAuth (placeholder) + skip (anonymous) |
| Language | Plain JavaScript (no TypeScript) |
| Routing | Expo Router (file-based) |

---

## App Flow

```
App opens
  └── AuthGate checks Supabase session
        ├── No session → (auth)/welcome
        │     ├── "Get Started" → sign-up
        │     ├── "Sign in with Google" → OAuth (placeholder)
        │     ├── "I already have an account" → sign-in
        │     └── "Skip →" → onboarding (anonymous)
        │
        ├── Has session + onboarding not done → (onboarding)/class
        │     └── class → subjects → goals → baseline quiz (skippable)
        │
        └── Has session + onboarding done → (tabs)/home
              ├── Home — streak, exam countdown, daily goal bar
              ├── Learning — smart suggestions + subject drill-down
              └── PYQ — searchable previous year question bank
```

---

## Task Checklist

### Auth Screens
- [x] Welcome screen — Skip button, Google button (placeholder), "Get Started" → sign-up
- [x] Sign-in screen — Skip button, Google button (placeholder), email/password auth
- [x] Sign-up screen — Skip button, Google button (placeholder), email/password register
- [x] Root `index.jsx` redirects to `/(auth)/welcome`
- [x] AuthGate allows unauthenticated users through onboarding and tabs (skip flow)
- [ ] Google OAuth — full Supabase integration (needs Google Client ID)
- [ ] Anonymous user → real user upgrade on sign-up

### Onboarding Screens
- [x] Class picker (`class.jsx`) — responsive, back button to welcome
- [x] Subject multi-select (`subjects.jsx`) — fetches from DB, back button
- [x] Goals screen (`goals.jsx`) — daily time + exam date, saves to DB, back button
- [x] Baseline quiz (`baseline.jsx`) — self-assessment PYQs, skippable
- [ ] Redirect flow: session with `baseline_completed = true` → home (not wired to AuthGate yet)

### Main Tabs
- [x] Home tab scaffold — streak badge, exam countdown, daily goal progress bar, stats cards
- [x] Learning tab scaffold — urgent review suggestions + subject list
- [x] PYQ tab scaffold — full-text search across user's selected subjects
- [ ] Subject → Chapter → Topic drill-down screens
- [ ] Topic detail / study view (summary bullets, why important, common mistakes)
- [ ] PYQ answer / explanation modal

### Responsiveness
- [x] Auth screens — `maxWidth: 480` + `ScrollView` + `KeyboardAvoidingView`
- [x] Onboarding screens — `maxWidth: 520` + `ScrollView`
- [x] Tab screens — `maxWidth: 700` + stats grid `flex-wrap`

### Database (Supabase Local)
- [x] `subjects` table seeded — classes 10, 11, 12 with all subjects
- [x] `chapters` and `topics` tables seeded (physics-12 and chemistry-12 have full content)
- [x] `pyqs` table — populated for physics-12 and chemistry-12
- [x] User tracking tables: `user_profiles`, `user_subjects`, `user_progress`, `baseline_results`, `study_sessions`
- [x] Row Level Security (RLS) enabled on all user tables
- [ ] Chapters + topics for all other subjects (needs content pipeline run)

### Spaced Repetition
- [x] DB schema: SM-2 fields on `user_progress` (`ease_factor`, `next_review_at`, `needs_urgent_review`)
- [ ] SM-2 algorithm runtime — calculate next review after topic is studied
- [ ] Streak calculation logic — update streak on daily session completion

### Secondary Features (not started)
- [ ] Leaderboard
- [ ] Push notifications
- [ ] AI "explain this PYQ"
- [ ] Offline mode / local caching

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
- [ ] `baseline_completed` flag not used in AuthGate yet
- [ ] Chapters/topics missing for most subjects (only physics-12 and chemistry-12 are populated)
- [ ] Google OAuth is a placeholder — shows "Coming soon" alert

---

## How to Run Locally

```bash
# 1. Start Supabase (Docker must be running)
npx supabase start

# 2. Start the frontend (web)
cd frontend
npx expo start --web --port 8083
# Opens at http://localhost:8083
```

---

## Branch
All work is on the `ncert-migration` branch:
`https://github.com/DipankajSingh/nios-study-app`
