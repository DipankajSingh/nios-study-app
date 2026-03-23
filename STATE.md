# Study App — Project State
> Last updated: 2026-03-24 03:28 IST

## What This App Is
A smart last-minute revision app for **Class 11 & 12 NIOS students**. Uses spaced repetition, PYQ performance, and user-set goals to prioritise what to study.

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

> ❌ Math, English, Hindi — not in source dataset
> ❌ No MCQs in dataset — all PYQs are descriptive/long-answer format

---

## Tech Stack
| Layer | Tech |
|---|---|
| Frontend | Expo SDK 54 (React Native) — web/Android/iOS |
| Styling | NativeWind v4 (Tailwind) with `darkMode: 'class'` |
| Backend | Supabase (PostgreSQL) — local Docker |
| Auth | Supabase Auth — email/password + Google OAuth (placeholder) + skip |
| Language | JavaScript (no TypeScript) |
| Routing | Expo Router (file-based) |
| Math rendering | KaTeX via `react-native-math-view` / custom `MathText` component |
| AI | Gemini via Supabase Edge Function (`generate-pyq-steps`) |

---

## How to Run
```bash
# Start local DB (Docker required)
npx supabase start

# Start app
cd frontend
npx expo start --web --port 8083
```

## Re-seeding the Database
```bash
# Regenerate seed.sql from ncert_dataset.json
cd pipeline && python3 01_build_ncert/build.py

# Apply to local Supabase (requires Docker)
docker cp supabase/seed.sql supabase_db_nios-study-app:/tmp/seed.sql
docker exec supabase_db_nios-study-app psql -U postgres -d postgres -f /tmp/seed.sql
```

---

## Key AsyncStorage Keys
| Key | Value | Set by |
|---|---|---|
| `anon_subject_ids` | `JSON.stringify(string[])` of subject UUIDs | `goals.jsx` onboarding |
| `anon_exam_target` | `'pass'` \| `'75'` \| `'90'` | `goals.jsx` onboarding |
| `anon_class_level` | `'11'` \| `'12'` | `goals.jsx` onboarding |
| `anon_daily_minutes` | number as string | `goals.jsx` onboarding |
| `app_theme_override` | `'light'` \| `'dark'` \| `'system'` | `settings.jsx` / `use-color-scheme` hook |

---

## Database Schema (Key Tables)

| Table | Purpose |
|---|---|
| `subjects` | id, name, icon, class_level |
| `chapters` | id, subject_id, title, order |
| `topics` | id, chapter_id, subject_id, title, high_yield_score, est_minutes, frequency_score |
| `topic_contents` | topic_id, summary_bullets[], why_important |
| `pyqs` | id, topic_id, subject_id, question_text, difficulty, year, marks, frequency_score |
| `pyq_explanations` | pyq_id, answer, steps[], hints[] |
| `pyq_attempts` | user_id, pyq_id, topic_id, subject_id, rating ('hard'\|'good'\|'easy'), attempted_at |
| `user_profiles` | id (user_id), class_level, exam_target, daily_goal_minutes |
| `user_subjects` | user_id, subject_id |
| `user_progress` | user_id, topic_id, needs_urgent_review, next_review_at, last_studied_at |
| `baseline_results` | user_id, topic_id, confidence |
| `study_sessions` | user_id, topic_id, duration_seconds |

> All tables have RLS enabled. `pyq_attempts` unique constraint on `(user_id, pyq_id)`.

---

## Supabase Edge Functions
| Function | Purpose |
|---|---|
| `generate-pyq-steps` | Calls Gemini to generate step-by-step solution + hints for a PYQ. Stores result back into `pyq_explanations`. |

---

## File Structure (Frontend)

```
frontend/
├── app/
│   ├── (auth)/         welcome.jsx  sign-in.jsx  sign-up.jsx
│   ├── (onboarding)/   class.jsx  subjects.jsx  goals.jsx  baseline.jsx
│   ├── (tabs)/         _layout.jsx  home.jsx  learning.jsx  pyq.jsx  settings.jsx
│   ├── subject/[id].jsx   ← subject → chapter list
│   ├── topic/[id].jsx     ← topic detail: summary + PYQs
│   └── _layout.jsx        ← AuthGate + ThemeProvider root
├── components/
│   ├── MathText.jsx       ← Universal LaTeX/plain-text renderer (KaTeX on web)
│   └── PyqCard.jsx        ← Shared PYQ card: expand, AI steps, self-rating bar
├── hooks/
│   ├── use-color-scheme.js       ← Native: returns { colorScheme, override, setTheme }
│   └── use-color-scheme.web.js   ← Web: DOM class toggle, AsyncStorage persist
├── lib/
│   └── supabase.js
├── global.css
└── tailwind.config.js    ← darkMode: 'class' (critical for NativeWind dark mode on web)
```

---

## Checklist

### ✅ Done

#### Auth Screens
- [x] Welcome screen — Skip, Google (placeholder), email sign-up/in
- [x] Sign-in screen — responsive, back button
- [x] Sign-up screen — responsive, back button
- [x] Root `index.jsx` redirects to `/(auth)/welcome`
- [x] `AuthGate` — unauthenticated users allowed through onboarding + tabs (skip flow)
- [x] `AuthGate` — authenticated users redirected directly to home (skip onboarding)

#### Onboarding Screens
- [x] Class picker — grades **11 & 12 only** (class 10 removed)
- [x] Class picker — back button, 3-segment progress bar
- [x] Subject picker — fetches live from DB filtered by `class_level`
- [x] Subject picker — back button, multi-select, orange checkmark
- [x] Goals screen — 4 time options (30 min / 1 hr / 2 hr / 3+ hr)
- [x] Goals screen — date picker (HTML `<input type="date">` on web, native picker on mobile)
- [x] Goals screen — saves `user_profiles` + `user_subjects` for logged-in users
- [x] Goals screen — saves `anon_subject_ids`, `anon_exam_target`, `anon_class_level`, `anon_daily_minutes` to AsyncStorage for anonymous users
- [x] Goals screen — safe `JSON.parse` for `subjectIds` param
- [x] Baseline quiz — self-assessment, skippable ("Skip all →")
- [x] Baseline quiz — **crash fixed**: `finish()` moved from render into `useEffect`
- [x] Baseline quiz — safe `JSON.parse` for `subjectIds` param

#### Main Tabs
- [x] Home tab — greeting, streak badge, today's goal bar, due-for-revision card, stats cards (scaffold)
- [x] Learning tab — dynamically renders real user subjects from `user_subjects` (or AsyncStorage for anon)
- [x] **PYQ tab — full Practice Arena** (see details below)
- [x] Settings tab — profile, theme toggle, preferences, sign out
- [x] Tab bar — Home 🏠 / Learning 📚 / PYQs 📝 / Settings ⚙️
- [x] Tab bar crash fixed — missing `Text` import in `(tabs)/_layout.jsx`

#### PYQ Practice Arena (`pyq.jsx`)
- [x] Subject pill selector (horizontal scrollable) showing all user-selected subjects
- [x] Per-subject mastery stats in subject pills (e.g. "3/10 mastered")
- [x] Status filter chips: **All / Unattempted / Review / Mastered**
- [x] Keyword search bar (text search, debounced on 3+ chars)
- [x] Lazy-loaded PYQ feed with pagination (`PAGE_SIZE = 10`)
- [x] "Load more" / end of results footer
- [x] Attempt status badges on collapsed cards (✅ Mastered / ✔ Done / 🔁 Review)
- [x] AsyncStorage fallback for both anonymous and signed-in users

#### Shared `PyqCard` Component (`components/PyqCard.jsx`)
- [x] Expand/collapse question card
- [x] Fetches answer from `pyq_explanations` on first open
- [x] Renders answer with `MathText` (LaTeX + plain text)
- [x] Shows numbered step-by-step solution
- [x] "✨ Generate Step-by-Step Breakdown" button when no steps exist
- [x] Calls `generate-pyq-steps` Edge Function
- [x] Hints section (`💡 Hints`)
- [x] **Self-rating bar**: 🔴 Hard / 🟡 Good / 🟢 Easy
- [x] Rating upserts `pyq_attempts` table
- [x] Rating also upserts `user_progress` (SM-2 `next_review_at` scheduling: Hard→+1d, Good→+4d, Easy→+10d)
- [x] Used in both `pyq.jsx` (Practice Arena) and `topic/[id].jsx` (Study View)

#### Topic Drill-down (`topic/[id].jsx`)
- [x] Summary bullets + "Why important" section
- [x] Top 10 PYQs for the topic (sorted by `frequency_score`)
- [x] PYQs rendered via shared `PyqCard`

#### Settings Tab
- [x] Account status (signed-in email or "Anonymous user")
- [x] Class level selector (11 / 12)
- [x] Target score selector (Just Pass / 75% / 90%+)
- [x] Daily study time selector (30min / 1hr / 2hr / 3+hr)
- [x] **Theme toggle (☀️ Light / 🌙 Dark / ⚙️ Auto)** — persists to AsyncStorage, applies immediately
- [x] Save Preferences button
- [x] Sign Out / Sign In button

#### Math Rendering (`components/MathText.jsx`)
- [x] Universal LaTeX parser — handles `\(...\)`, `\[...\]`, `$$...$$`, `$...$`
- [x] KaTeX rendering on web
- [x] Falls back to plain text on native

#### Dark Mode / Theming
- [x] `tailwind.config.js` — `darkMode: 'class'` (critical for NativeWind web)
- [x] `use-color-scheme.web.js` — toggles `dark` class on `document.documentElement`
- [x] `use-color-scheme.js` (native) — same API: `{ colorScheme, override, setTheme }`
- [x] All layouts (`_layout.jsx`, `(tabs)/_layout.jsx`) use destructured `{ colorScheme }`
- [x] Theme preference persists across sessions via `app_theme_override` in AsyncStorage

#### Database
- [x] 22 subjects seeded (11 subjects × grades 11 & 12)
- [x] 22,479 topics seeded
- [x] 91,916 PYQs seeded
- [x] 91,916 PYQ explanations seeded
- [x] `user_profiles`, `user_subjects`, `user_progress`, `baseline_results`, `study_sessions` tables with RLS
- [x] `pyq_attempts` table — migration `00003_pyq_attempts.sql` — RLS enabled, unique on `(user_id, pyq_id)`
- [x] Pipeline script `pipeline/01_build_ncert/build.py` — covers all 11 subjects, grades 11+12, no row limit

#### Responsiveness
- [x] Auth screens — max-width 480
- [x] Onboarding screens — max-width 520
- [x] Tab screens — max-width 700

#### Bug Fixes
- [x] **AI Generation Crash**: Gemini Edge Function failing on local Deno due to 10-second wall-clock limits + raw LaTeX breaking JSON. Fixed via `application/json` schema + optimised prompt.
- [x] **PYQ Empty Steps Bug**: Empty AI explanations rendering as duplicate answers. Fixed with step deduplication filter.
- [x] **Tab Bar Stretching**: Fixed floating custom Tab Bar centering on desktop/web.
- [x] **Anonymous Drill-down Redirect**: AuthGate erroneously bouncing anon users to Welcome when drilling into Subjects/Topics.
- [x] **PYQ AsyncStorage Key Mismatch**: `pyq.jsx` was reading `selectedSubjectIds` but onboarding saved `anon_subject_ids`. Fixed to use `anon_subject_ids` consistently.
- [x] **`Appearance.setColorScheme` on Web**: Not a function on web — replaced with direct DOM class toggle.
- [x] **Dark mode not applying**: `tailwind.config.js` was missing `darkMode: 'class'`, causing NativeWind dark variants to be ignored on web.
- [x] **Logged-in users with no DB subjects**: Added AsyncStorage fallback for signed-in users who completed anonymous onboarding before creating an account.

---

### ❌ Not Done Yet

#### Core Study Flow (highest priority)
- [ ] Mark topic as "Studied" from topic drill-down (without going through PYQ)
- [ ] SM-2 full algorithm — update `ease_factor`, `interval_days` in `user_progress`

#### Spaced Repetition
- [ ] "Due for Revision" list on Home tab (real data from `user_progress`)
- [ ] Streak calculation (from `study_sessions`)

#### Home Tab — real data
- [ ] Show actual `daily_goal_minutes` and today's progress

#### Auth
- [ ] Wire `baseline_completed` flag in AuthGate — skip onboarding on return visits for logged-in users
- [ ] Google OAuth (needs Google Console Client ID)
- [ ] Anonymous → real account upgrade after sign-up

#### Secondary / Nice-to-have
- [ ] Leaderboard
- [ ] Push notifications
- [ ] Offline mode

---

## Known Bugs (open)
| Bug | Status |
|---|---|
| Logged-in users re-onboard on every app open (`baseline_completed` not checked in AuthGate) | ❌ open |
| Google OAuth shows "Coming soon" alert | ❌ placeholder |
| Home "0 / — min" goal bar (no real session data yet) | ❌ expected — sessions not built |
| SM-2 `next_review_at` is a simplified linear schedule, not true SM-2 (ease factor not tracked) | ❌ partial |
