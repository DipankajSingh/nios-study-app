# NIOS Study App — Project State
> Last updated: 2026-03-21

## What This App Is
A last-minute smart revision app for **NIOS students** (classes 10, 11, 12). It uses spaced repetition, PYQ performance, and user-set goals to tell students exactly what to study.

---

## Tech Stack
| Layer | Tech |
|---|---|
| Frontend | Expo (React Native) – universal web/Android/iOS |
| Styling | NativeWind v4 (TailwindCSS) – respects system dark/light mode |
| Backend | Supabase (PostgreSQL) – local Docker instance |
| Auth | Supabase Auth – email/password + Google OAuth + **skip (anonymous)** |
| Language | Plain JavaScript (no TypeScript) |
| Routing | Expo Router (file-based) |

---

## App Flow

```
App opens
  └── AuthGate checks Supabase session
        ├── No session → (auth)/welcome
        │     ├── "Get Started" → sign-up
        │     ├── "Sign in with Google" → OAuth
        │     ├── "I already have an account" → sign-in
        │     └── "Continue without account" → onboarding (anonymous)
        │
        ├── Has session, onboarding not done → (onboarding)/class
        │     └── class → subjects → goals (time + exam date) → baseline quiz (optional, skippable)
        │
        └── Has session, onboarding done → (tabs)/home
              ├── Home tab — streak, exam countdown, daily goal bar
              ├── Learning tab — suggestions + subject drill-down
              └── PYQ tab — searchable question bank
```

---

## Screens Built

### Auth (`app/(auth)/`)
| Screen | File | Status |
|---|---|---|
| Welcome | `welcome.jsx` | ✅ Built — needs Google + Skip buttons |
| Sign In | `sign-in.jsx` | ✅ Built — needs Google login |
| Sign Up | `sign-up.jsx` | ✅ Built |

### Onboarding (`app/(onboarding)/`)
| Screen | File | Status |
|---|---|---|
| Class picker | `class.jsx` | ✅ Built |
| Subject multi-select | `subjects.jsx` | ✅ Built — fetches from DB |
| Goals (time + exam date) | `goals.jsx` | ✅ Built — saves to DB |
| Baseline quiz | `baseline.jsx` | ✅ Built — optional, skippable |

### Main Tabs (`app/(tabs)/`)
| Tab | File | Status |
|---|---|---|
| Home | `home.jsx` | ✅ Scaffold — exam countdown, streak, daily progress |
| Learning | `learning.jsx` | ✅ Scaffold — suggestions + subject list |
| PYQ | `pyq.jsx` | ✅ Scaffold — FTS search |

---

## Database Schema

### Curriculum Tables (`00001_init_schema.sql`)
- `subjects` — subject name, class level, code
- `chapters` — belongs to subject
- `topics` — belongs to chapter, has `prerequisites` (array of topic IDs)
- `pyqs` — PYQ question, answer, explanation, marks, year, linked to topic

### User Tracking Tables (`00002_user_tracking.sql`)
- `user_profiles` — class, exam date, daily goal minutes, streak
- `user_subjects` — which subjects the user selected
- `user_progress` — per-topic spaced repetition state (SM-2: ease factor, next_review_at, needs_urgent_review)
- `baseline_results` — self-assessment scores per subject from onboarding quiz
- `study_sessions` — daily minutes studied (for streak calculation)
- All tables have Row Level Security (RLS) — users only see their own data.

---

## Key Design Decisions Agreed On

| Decision | Detail |
|---|---|
| Auth is skippable | User can choose "Continue without account" and use the app anonymously |
| Google sign-in | Available on welcome screen and sign-in screen |
| Spaced repetition | Hybrid: time-decay (SM-2) + PYQ failure flag (`needs_urgent_review`) |
| Prerequisites | Shown non-intrusively, with count + tick if any prereq is completed |
| Marking topics | NOT permanent — hybrid soft-mark system |
| Baseline quiz | Assesses all selected subjects, individually skippable |
| Streaks | Secondary feature — schema exists, UI not wired yet |
| Leaderboard | Secondary feature — not started |
| Naming | Implies "last minute" energy |

---

## What's NOT Built Yet

| Feature | Priority |
|---|---|
| Subject → Chapter → Topic drill-down screen | 🔴 High |
| Prerequisite UI (count + tick marks) | 🔴 High |
| Google OAuth integration | 🔴 High |
| Skip login (anonymous mode) | 🔴 High |
| Spaced rep algorithm runtime (SM-2 code) | 🟡 Medium |
| Streak calculation logic | 🟡 Medium |
| Topic detail / study view | 🟡 Medium |
| PYQ answer/explanation view | 🟡 Medium |
| Leaderboard | 🟢 Low |
| Push notifications | 🟢 Low |
| AI "explain this PYQ" | 🟢 Low |

---

## Known Issues
- [ ] Auth screens not fully responsive on web (fixed in progress)
- [ ] No root index route → showed "Unmatched Route" on first load (fixed with `app/index.jsx` redirect)
- [ ] Google OAuth not integrated yet
- [ ] Skip/anonymous login not wired

---

## How to Run Locally

```bash
# 1. Start Supabase (Docker must be running)
npx supabase start

# 2. Start the frontend (web)
cd frontend
npx expo start --web --port 8083

# App opens at http://localhost:8083
```

---

## Branch
All work is on the `ncert-migration` branch of:
`https://github.com/DipankajSingh/nios-study-app`
