import { useEffect, useState, useCallback } from "react";
import "./App.css";
import {
  fetchSubjects,
  fetchSyllabus,
  fetchTopicDetails,
  fetchSubjectPyqs,
  type SubjectDto,
  type SyllabusChapterDto,
  type SyllabusDto,
  type TopicDetailsDto,
  type PyqDto,
} from "./catalogApi";
import { fetchDailyPlan } from "./api";
import type { DailyPlan } from "./domain";

// ---- Types -----------------------------------------------

type StudyGoal = "pass" | "sixty" | "eighty";
type Lang = "en" | "hi" | "hinglish";
type Screen = "onboarding" | "today" | "browse" | "topic" | "practice";
type BrowseView = "subjects" | "chapters" | "topics";
type TopicTab = "notes" | "pyqs";

interface OnboardingState {
  classLevel: "10" | "12";
  subjectIds: string[];
  examMonth: string;
  examYear: string;
  dailyMinutes: number | "";
  goal: StudyGoal;
  language: Lang;
}

interface PracticeSession {
  subjectId: string;
  pyqs: PyqDto[];
  currentIndex: number;
  revealed: boolean;
}

// ---- Constants -------------------------------------------

const EXAM_MONTHS = ["March/April", "October/November"];
const SK_ONBOARDING = "nios_v2_onboarding";
const SK_PLAN = "nios_v2_plan";
const SK_DONE_TOPICS = "nios_v2_done_topics";
const SK_DONE_TASKS = "nios_v2_done_tasks";

const GOAL_LABELS: Record<StudyGoal, string> = {
  pass: "Just Pass",
  sixty: "60%+",
  eighty: "80%+",
};

const LANG_LABELS: Record<Lang, string> = {
  en: "English",
  hi: "Hindi",
  hinglish: "Hinglish",
};

function getSubjectColor(subjectId: string): string {
  const map: Record<string, string> = {
    "maths-12": "#38bdf8",
    "english-12": "#a78bfa",
    "science-12": "#34d399",
    "sst-12": "#fbbf24",
  };
  return map[subjectId] || "#38bdf8";
}

function getYieldColor(score: number): string {
  if (score >= 85) return "#34d399";
  if (score >= 70) return "#fbbf24";
  return "#8da4c4";
}

function ls<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

function lsSet(key: string, value: unknown) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* ignore */
  }
}

// ============================================================
// ONBOARDING WIZARD
// ============================================================

const WIZARD_STEPS = 5;

function OnboardingScreen({
  onDone,
}: {
  onDone: (state: OnboardingState) => void;
}) {
  const [step, setStep] = useState(0);
  const [classLevel, setClassLevel] = useState<"10" | "12">("12");
  const [subjects, setSubjects] = useState<SubjectDto[]>([]);
  const [subjectIds, setSubjectIds] = useState<string[]>([]);
  const [examMonth, setExamMonth] = useState(EXAM_MONTHS[0]);
  const [examYear, setExamYear] = useState(String(new Date().getFullYear()));
  const [dailyMinutes, setDailyMinutes] = useState<number | "">(60);
  const [goal, setGoal] = useState<StudyGoal>("pass");
  const [language, setLanguage] = useState<Lang>("hinglish");

  useEffect(() => {
    fetchSubjects(classLevel)
      .then(setSubjects)
      .catch(() => {});
  }, [classLevel]);

  const toggleSubject = (id: string) => {
    setSubjectIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );
  };

  const canNext = () => {
    if (step === 0) return true;
    if (step === 1) return subjectIds.length > 0;
    if (step === 2) return !!examMonth && !!examYear;
    if (step === 3) return !!dailyMinutes;
    if (step === 4) return true;
    return true;
  };

  const next = () => {
    if (step < WIZARD_STEPS - 1) setStep((s) => s + 1);
    else {
      onDone({
        classLevel,
        subjectIds,
        examMonth,
        examYear,
        dailyMinutes,
        goal,
        language,
      });
    }
  };

  const back = () => setStep((s) => s - 1);

  return (
    <div className="onboarding-screen">
      <div className="onboarding-logo">📚</div>
      <div className="onboarding-brand">NIOS Study</div>
      <div className="onboarding-tagline">
        PYQ-based daily plans, built from official NIOS material.
      </div>

      {/* Progress dots */}
      <div className="wizard-progress">
        {Array.from({ length: WIZARD_STEPS }).map((_, i) => (
          <div
            key={i}
            className={`wizard-dot ${i < step ? "done" : i === step ? "active" : ""}`}
          />
        ))}
      </div>

      {/* Step 0 – Class */}
      {step === 0 && (
        <>
          <div className="wizard-step-label">Step 1 of {WIZARD_STEPS}</div>
          <div className="wizard-step-title">What class are you in?</div>
          <div className="pill-grid">
            {(["10", "12"] as const).map((c) => (
              <button
                key={c}
                className={`pill ${classLevel === c ? "selected" : ""}`}
                onClick={() => {
                  setClassLevel(c);
                  setSubjectIds([]);
                }}
              >
                Class {c}
              </button>
            ))}
          </div>
        </>
      )}

      {/* Step 1 – Subjects */}
      {step === 1 && (
        <>
          <div className="wizard-step-label">Step 2 of {WIZARD_STEPS}</div>
          <div className="wizard-step-title">Pick your subjects</div>
          <p className="hint-text" style={{ marginBottom: "1rem" }}>
            Select all subjects you need to study. We'll build plans for each.
          </p>
          <div className="pill-grid">
            {subjects.map((s) => (
              <button
                key={s.id}
                className={`pill ${subjectIds.includes(s.id) ? "selected" : ""}`}
                onClick={() => toggleSubject(s.id)}
              >
                {s.icon} {s.name}
              </button>
            ))}
          </div>
          {subjects.length === 0 && (
            <p className="hint-text">Loading subjects…</p>
          )}
        </>
      )}

      {/* Step 2 – Exam date */}
      {step === 2 && (
        <>
          <div className="wizard-step-label">Step 3 of {WIZARD_STEPS}</div>
          <div className="wizard-step-title">When is your exam?</div>
          <div className="field-group">
            <div className="field-row">
              <select
                className="field-input"
                value={examMonth}
                onChange={(e) => setExamMonth(e.target.value)}
              >
                {EXAM_MONTHS.map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </select>
              <input
                className="field-input"
                type="number"
                placeholder="Year (e.g. 2026)"
                value={examYear}
                min={2025}
                max={2035}
                onChange={(e) => setExamYear(e.target.value)}
              />
            </div>
          </div>
        </>
      )}

      {/* Step 3 – Daily time + Goal */}
      {step === 3 && (
        <>
          <div className="wizard-step-label">Step 4 of {WIZARD_STEPS}</div>
          <div className="wizard-step-title">Time & goal</div>
          <div className="field-group">
            <label className="field-label">Daily study time (minutes)</label>
            <input
              className="field-input"
              type="number"
              placeholder="e.g. 45"
              value={dailyMinutes}
              min={10}
              max={300}
              onChange={(e) =>
                setDailyMinutes(e.target.value ? Number(e.target.value) : "")
              }
            />
          </div>
          <div className="field-label" style={{ marginBottom: "0.75rem" }}>
            My target score
          </div>
          <div className="pill-grid">
            {(Object.keys(GOAL_LABELS) as StudyGoal[]).map((g) => (
              <button
                key={g}
                className={`pill ${goal === g ? "selected" : ""}`}
                onClick={() => setGoal(g)}
              >
                {GOAL_LABELS[g]}
              </button>
            ))}
          </div>
        </>
      )}

      {/* Step 4 – Language */}
      {step === 4 && (
        <>
          <div className="wizard-step-label">Step 5 of {WIZARD_STEPS}</div>
          <div className="wizard-step-title">How do you want explanations?</div>
          <p className="hint-text" style={{ marginBottom: "1rem" }}>
            Notes and AI explanations will be shown in your chosen language.
          </p>
          <div className="pill-grid">
            {(Object.keys(LANG_LABELS) as Lang[]).map((l) => (
              <button
                key={l}
                className={`pill ${language === l ? "selected" : ""}`}
                onClick={() => setLanguage(l)}
              >
                {LANG_LABELS[l]}
              </button>
            ))}
          </div>
        </>
      )}

      <div className="wizard-nav">
        {step > 0 && (
          <button className="btn-secondary" onClick={back}>
            ← Back
          </button>
        )}
        <button className="btn-primary" onClick={next} disabled={!canNext()}>
          {step === WIZARD_STEPS - 1 ? "Start studying 🚀" : "Continue →"}
        </button>
      </div>
    </div>
  );
}

// ============================================================
// TODAY SCREEN
// ============================================================

function TodayScreen({
  onboarding,
  onGoTopic,
}: {
  onboarding: OnboardingState;
  onGoTopic: (topicId: string) => void;
}) {
  const [plan, setPlan] = useState<DailyPlan | null>(ls(SK_PLAN, null));
  const [loading, setLoading] = useState(!plan);
  const [error, setError] = useState<string | null>(null);
  const [doneTasks, setDoneTasks] = useState<string[]>(ls(SK_DONE_TASKS, []));

  useEffect(() => {
    if (plan) return;
    setLoading(true);
    // Build ISO exam date from onboarding month/year
    const examMonthMap: Record<string, string> = {
      "March/April": "04",
      "October/November": "11",
    };
    const mm = examMonthMap[onboarding.examMonth] || "04";
    const examDate = `${onboarding.examYear}-${mm}-01`;
    const savedDoneTopics: string[] = ls(SK_DONE_TOPICS, []);

    fetchDailyPlan({
      subjectIds: onboarding.subjectIds,
      dailyMinutes: onboarding.dailyMinutes || 60,
      goal: onboarding.goal,
      examDate,
      doneTopicIds: savedDoneTopics,
    })
      .then((p) => {
        setPlan(p);
        lsSet(SK_PLAN, p);
      })
      .catch(() => setError("Could not reach backend. Is it running?"))
      .finally(() => setLoading(false));
  }, [onboarding, plan]);

  const toggleTaskDone = (taskId: string) => {
    setDoneTasks((prev) => {
      const next = prev.includes(taskId)
        ? prev.filter((x) => x !== taskId)
        : [...prev, taskId];
      lsSet(SK_DONE_TASKS, next);
      return next;
    });
  };

  const tasks = plan?.tasks ?? [];
  const doneCount = tasks.filter((t) => doneTasks.includes(t.id)).length;
  const totalMins = tasks.reduce((a, t) => a + t.estimatedMinutes, 0);
  const doneMins = tasks
    .filter((t) => doneTasks.includes(t.id))
    .reduce((a, t) => a + t.estimatedMinutes, 0);

  const pct = tasks.length ? (doneCount / tasks.length) * 100 : 0;

  return (
    <div className="screen">
      {/* Hero */}
      <div className="today-hero">
        <div className="today-hero-label">
          {new Date().toLocaleDateString("en-IN", {
            weekday: "long",
            day: "numeric",
            month: "short",
          })}
        </div>
        <div className="today-hero-title">Today's Study Plan</div>
        <div className="today-progress-bar-wrap">
          <div
            className="today-progress-bar-fill"
            style={{ width: `${pct}%` }}
          />
        </div>
        <div className="today-progress-meta">
          <span>
            {doneCount}/{tasks.length} tasks done
          </span>
          <span>
            {doneMins}/{totalMins} min
          </span>
        </div>
      </div>

      {error && <div className="error-text">{error}</div>}

      {loading ? (
        <div>
          <div className="skeleton-block wide" />
          <div className="skeleton-block med" />
          <div className="skeleton-block wide" />
          <div className="skeleton-block short" />
        </div>
      ) : tasks.length === 0 ? (
        <div className="empty-state">
          <span className="empty-icon">📋</span>
          <div className="empty-title">No tasks generated</div>
          <div className="empty-desc">
            Make sure the backend is running and try again.
          </div>
        </div>
      ) : (
        <>
          <div className="section-title">Tasks</div>
          <div className="task-list">
            {tasks.map((task) => {
              const done = doneTasks.includes(task.id);
              const clr = getSubjectColor(task.subjectId);
              return (
                <button
                  key={task.id}
                  className={`task-card ${done ? "done" : ""}`}
                  onClick={() => {
                    if (task.topicId) onGoTopic(task.topicId);
                  }}
                >
                  <div
                    className={`task-done-check ${done ? "checked" : ""}`}
                    onClick={(e) => {
                      e.stopPropagation();
                      toggleTaskDone(task.id);
                    }}
                    role="checkbox"
                    aria-checked={done}
                  >
                    {done && "✓"}
                  </div>
                  <div className="task-card-body">
                    <div className="task-subject-badge" style={{ color: clr }}>
                      {task.subject}
                    </div>
                    <div className="task-topic-name">{task.topic}</div>
                    <div className="task-meta-row">
                      <span className="task-type-chip">
                        {task.type === "READ_NOTES"
                          ? "📖 Notes"
                          : "✏️ Practice"}
                      </span>
                      <span className="task-time-chip">
                        ~{task.estimatedMinutes} min
                      </span>
                    </div>
                  </div>
                  {task.highYieldScore >= 80 && (
                    <div className="yield-badge">⭐ High</div>
                  )}
                </button>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}

// ============================================================
// BROWSE SCREEN
// ============================================================

function BrowseScreen({
  onboarding,
  onGoTopic,
}: {
  onboarding: OnboardingState;
  onGoTopic: (topicId: string) => void;
}) {
  const [view, setView] = useState<BrowseView>("subjects");
  const [allSubjects, setAllSubjects] = useState<SubjectDto[]>([]);
  const [syllabus, setSyllabus] = useState<SyllabusDto | null>(null);
  const [selectedChapter, setSelectedChapter] =
    useState<SyllabusChapterDto | null>(null);

  useEffect(() => {
    fetchSubjects(onboarding.classLevel)
      .then((subs) => {
        // Filter to only the subjects the user enrolled in
        const enrolled = subs.filter((s) =>
          onboarding.subjectIds.includes(s.id),
        );
        setAllSubjects(enrolled.length > 0 ? enrolled : subs);
      })
      .catch(() => {});
  }, [onboarding]);

  const pickSubject = async (sub: SubjectDto) => {
    const data = await fetchSyllabus(sub.id);
    setSyllabus(data);
    setView("chapters");
  };

  const pickChapter = (chap: SyllabusChapterDto) => {
    setSelectedChapter(chap);
    setView("topics");
  };

  const goBack = () => {
    if (view === "topics") setView("chapters");
    else if (view === "chapters") setView("subjects");
  };

  return (
    <div className="screen">
      <div className="page-header">
        {view !== "subjects" && (
          <button className="back-btn" onClick={goBack}>
            ←
          </button>
        )}
        <div>
          <div className="page-title">
            {view === "subjects"
              ? "Browse"
              : view === "chapters"
                ? (syllabus?.subject.name ?? "Chapters")
                : (selectedChapter?.title ?? "Topics")}
          </div>
          {view === "subjects" && (
            <div className="page-subtitle">Your enrolled subjects</div>
          )}
        </div>
      </div>

      {view === "subjects" && (
        <div className="subject-grid">
          {allSubjects.map((sub) => (
            <button
              key={sub.id}
              className="subject-card"
              onClick={() => pickSubject(sub)}
              style={{
                borderTopColor: getSubjectColor(sub.id),
                borderTopWidth: "3px",
              }}
            >
              <span className="subject-card-icon">{sub.icon}</span>
              <div className="subject-card-name">{sub.name}</div>
              <div className="subject-card-desc">{sub.description}</div>
            </button>
          ))}
        </div>
      )}

      {view === "chapters" && syllabus && (
        <div className="chapter-list">
          {syllabus.chapters.map((chap) => (
            <button
              key={chap.id}
              className="chapter-item"
              onClick={() => pickChapter(chap)}
            >
              <div>
                <div className="chapter-item-title">{chap.title}</div>
                <div className="chapter-item-meta">
                  Chapter {chap.orderIndex}
                </div>
              </div>
              <span className="chevron">›</span>
            </button>
          ))}
        </div>
      )}

      {view === "topics" && selectedChapter && (
        <div className="topics-list">
          {selectedChapter.topics.map((topic) => (
            <button
              key={topic.id}
              className="topic-item"
              onClick={() => onGoTopic(topic.id)}
              style={topic.hasContent === false ? { opacity: 0.5 } : {}}
            >
              <div
                className="topic-yield-bar"
                style={{ background: getYieldColor(topic.highYieldScore) }}
              />
              <div className="topic-item-body">
                <div className="topic-item-title">{topic.title}</div>
                <div className="topic-item-meta">
                  <span>⭐ {topic.highYieldScore}% yield</span>
                  <span>· ~{topic.estMinutes} min</span>
                </div>
              </div>
              <span className="chevron">›</span>
            </button>
          ))}
          {selectedChapter.topics.length === 0 && (
            <p style={{ color: "var(--text-muted)", fontSize: "0.85rem" }}>
              No topics found.
            </p>
          )}
        </div>
      )}
    </div>
  );
}

// ============================================================
// TOPIC DETAIL SCREEN
// ============================================================

function TopicDetailScreen({
  topicId,
  lang,
  onBack,
}: {
  topicId: string;
  lang: Lang;
  onBack: () => void;
}) {
  const [details, setDetails] = useState<TopicDetailsDto | null>(null);
  const [tab, setTab] = useState<TopicTab>("notes");
  const [loadingContent, setLoadingContent] = useState(true);
  const [doneTopics, setDoneTopics] = useState<string[]>(
    ls(SK_DONE_TOPICS, []),
  );

  const isDone = doneTopics.includes(topicId);

  const toggleDone = () => {
    setDoneTopics((prev) => {
      const next = prev.includes(topicId)
        ? prev.filter((x) => x !== topicId)
        : [...prev, topicId];
      lsSet(SK_DONE_TOPICS, next);
      return next;
    });
  };

  useEffect(() => {
    setLoadingContent(true);
    setDetails(null);

    fetchTopicDetails(topicId, lang)
      .then(setDetails)
      .catch(() => {})
      .finally(() => setLoadingContent(false));
  }, [topicId, lang]);

  const content = details?.content;
  const pyqs = details?.pyqs ?? [];

  // Derive topic name from content or a fallback
  const topicTitle = content
    ? undefined // we'll show in the hero
    : null;

  return (
    <div className="screen">
      <div className="page-header">
        <button className="back-btn" onClick={onBack}>
          ←
        </button>
        <div>
          <div className="page-title">
            {content ? "Topic Detail" : "Loading…"}
          </div>
        </div>
      </div>

      {/* Hero */}
      {content && (
        <div className="topic-detail-hero">
          <div className="topic-chip-row" style={{ marginBottom: "0.6rem" }}>
            <span className="topic-chip chip-time">📖 Study topic</span>
          </div>
          <div className="topic-detail-title">{topicTitle}</div>
          <p
            style={{
              fontSize: "0.85rem",
              color: "var(--text-secondary)",
              lineHeight: 1.5,
            }}
          >
            {content.whyImportant}
          </p>
        </div>
      )}

      {/* Tabs */}
      <div className="tab-bar">
        <button
          className={`tab-btn ${tab === "notes" ? "active" : ""}`}
          onClick={() => setTab("notes")}
        >
          📝 Notes
        </button>
        <button
          className={`tab-btn ${tab === "pyqs" ? "active" : ""}`}
          onClick={() => setTab("pyqs")}
        >
          ✏️ PYQs {pyqs.length > 0 && `(${pyqs.length})`}
        </button>
      </div>

      {/* Notes Tab */}
      {tab === "notes" && (
        <div className="notes-section">
          {loadingContent ? (
            <>
              <div className="skeleton-block wide" />
              <div className="skeleton-block med" />
              <div className="skeleton-block wide" />
              <div className="skeleton-block short" />
            </>
          ) : content ? (
            <>
              <div className="notes-card">
                <div className="notes-card-label bullets">Key Points</div>
                <ul className="bullet-list">
                  {content.summaryBullets.map((b, i) => (
                    <li key={i}>
                      <div className="bullet-dot blue" />
                      <span>{b}</span>
                    </li>
                  ))}
                </ul>
              </div>

              <div className="notes-card">
                <div className="notes-card-label mistakes">Common Mistakes</div>
                <ul className="bullet-list">
                  {content.commonMistakes.map((m, i) => (
                    <li key={i}>
                      <div className="bullet-dot rose" />
                      <span>{m}</span>
                    </li>
                  ))}
                </ul>
              </div>

              <button
                className={`mark-done-btn ${isDone ? "done-state" : ""}`}
                onClick={toggleDone}
              >
                {isDone ? "✓ Marked as Done" : "✅ Mark as Done"}
              </button>
            </>
          ) : (
            <div className="empty-state">
              <span className="empty-icon">📭</span>
              <div className="empty-title">Notes not available yet</div>
              <div className="empty-desc">
                Content for this topic is coming soon.
              </div>
            </div>
          )}
        </div>
      )}

      {/* PYQs Tab */}
      {tab === "pyqs" && (
        <div>
          {pyqs.length === 0 ? (
            <div className="empty-state">
              <span className="empty-icon">📝</span>
              <div className="empty-title">No PYQs for this topic yet</div>
              <div className="empty-desc">
                Check back as we add more question papers.
              </div>
            </div>
          ) : (
            pyqs.map((q) => <TopicPyqCard key={q.id} pyq={q} />)
          )}
        </div>
      )}
    </div>
  );
}

function TopicPyqCard({ pyq }: { pyq: PyqDto }) {
  const [revealed, setRevealed] = useState(false);
  const diffClass = `chip-diff-${pyq.difficulty}`;

  return (
    <div className="pyq-card" style={{ marginBottom: "0.875rem" }}>
      <div className="pyq-meta-row">
        <span className={`pyq-chip chip-year`}>
          {pyq.year} {pyq.session}
        </span>
        <span className={`pyq-chip chip-marks`}>{pyq.marks}m</span>
        <span className={`pyq-chip ${diffClass}`}>{pyq.difficulty}</span>
      </div>
      <p className="pyq-question">{pyq.questionText}</p>

      {!revealed && (
        <button
          className="reveal-answer-btn"
          style={{ marginTop: "0.875rem" }}
          onClick={() => setRevealed(true)}
        >
          Show Answer & Explanation
        </button>
      )}

      {revealed && pyq.explanation && (
        <div className="answer-section" style={{ marginTop: "0.875rem" }}>
          {pyq.explanation.hints.length > 0 && (
            <div className="hints-section" style={{ marginBottom: "0.75rem" }}>
              <div className="answer-label">Hints</div>
              {pyq.explanation.hints.map((h, i) => (
                <div key={i} className="hint-item">
                  <span className="hint-bullet">💡</span>
                  <span>{h}</span>
                </div>
              ))}
            </div>
          )}
          <div className="answer-label">Step-by-Step</div>
          <ol className="step-list">
            {pyq.explanation.steps.map((s, i) => (
              <li key={i} className="step-item">
                <div className="step-num">{i + 1}</div>
                <span>{s}</span>
              </li>
            ))}
          </ol>
          {pyq.explanation.answer && (
            <>
              <div className="answer-label" style={{ marginTop: "0.75rem" }}>
                Answer
              </div>
              <div className="answer-text">{pyq.explanation.answer}</div>
            </>
          )}
        </div>
      )}
    </div>
  );
}

// ============================================================
// PRACTICE SCREEN
// ============================================================

function PracticeScreen({ onboarding }: { onboarding: OnboardingState }) {
  const [subjects, setSubjects] = useState<SubjectDto[]>([]);
  const [session, setSession] = useState<PracticeSession | null>(null);
  const [revealed, setRevealed] = useState(false);
  const [results, setResults] = useState<
    Record<string, "correct" | "incorrect">
  >({});

  useEffect(() => {
    fetchSubjects(onboarding.classLevel)
      .then((subs) =>
        setSubjects(subs.filter((s) => onboarding.subjectIds.includes(s.id))),
      )
      .catch(() => {});
  }, [onboarding]);

  const startPractice = useCallback(
    async (subjectId: string) => {
      const allPyqs = await fetchSubjectPyqs(subjectId, onboarding.language);
      // Shuffle
      const shuffled = [...allPyqs].sort(() => Math.random() - 0.5);
      setSession({
        subjectId,
        pyqs: shuffled,
        currentIndex: 0,
        revealed: false,
      });
      setRevealed(false);
      setResults({});
    },
    [onboarding.language],
  );

  const current = session?.pyqs[session.currentIndex];

  const markResult = (res: "correct" | "incorrect") => {
    if (!current || !session) return;
    setResults((prev) => ({ ...prev, [current.id]: res }));
    if (session.currentIndex + 1 < session.pyqs.length) {
      setSession({ ...session, currentIndex: session.currentIndex + 1 });
      setRevealed(false);
    } else {
      // Done
      setSession(null);
    }
  };

  if (!session) {
    const correctCount = Object.values(results).filter(
      (r) => r === "correct",
    ).length;
    const total = Object.keys(results).length;
    return (
      <div className="screen">
        <div className="page-header">
          <div>
            <div className="page-title">Practice</div>
            <div className="page-subtitle">Past Year Questions by subject</div>
          </div>
        </div>

        {total > 0 && (
          <div className="today-hero" style={{ marginBottom: "1.25rem" }}>
            <div className="today-hero-label">Session Complete 🎉</div>
            <div className="today-hero-title">
              {correctCount}/{total} Correct
            </div>
          </div>
        )}

        <div className="section-title">Choose a subject</div>
        <div className="practice-selector">
          {subjects.map((s) => (
            <button
              key={s.id}
              className="practice-subject-btn"
              onClick={() => startPractice(s.id)}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "0.75rem",
                }}
              >
                <span style={{ fontSize: "1.5rem" }}>{s.icon}</span>
                <div>
                  <div
                    className="chapter-item-title"
                    style={{ color: getSubjectColor(s.id) }}
                  >
                    {s.name}
                  </div>
                  <div className="chapter-item-meta">Start a PYQ session</div>
                </div>
              </div>
              <span className="chevron">›</span>
            </button>
          ))}
        </div>
      </div>
    );
  }

  if (!current) return null;

  const diffClass = `chip-diff-${current.difficulty}`;
  const qNum = session.currentIndex + 1;
  const total = session.pyqs.length;

  return (
    <div className="screen">
      <div className="practice-header">
        <button className="back-btn" onClick={() => setSession(null)}>
          ←
        </button>
        <div className="practice-counter">
          {qNum} / {total}
        </div>
      </div>

      {/* Progress */}
      <div
        className="today-progress-bar-wrap"
        style={{ marginBottom: "1.25rem" }}
      >
        <div
          className="today-progress-bar-fill"
          style={{ width: `${(qNum / total) * 100}%` }}
        />
      </div>

      <div className="pyq-card">
        <div className="pyq-meta-row">
          <span className="pyq-chip chip-year">
            {current.year} {current.session}
          </span>
          <span className="pyq-chip chip-marks">{current.marks}m</span>
          <span className={`pyq-chip ${diffClass}`}>{current.difficulty}</span>
        </div>
        <p className="pyq-question">{current.questionText}</p>
      </div>

      {!revealed ? (
        <button className="reveal-answer-btn" onClick={() => setRevealed(true)}>
          💡 Reveal Answer
        </button>
      ) : (
        current.explanation && (
          <div className="answer-section">
            {current.explanation.hints.length > 0 && (
              <div
                className="hints-section"
                style={{ marginBottom: "0.75rem" }}
              >
                <div className="answer-label">Hints</div>
                {current.explanation.hints.map((h, i) => (
                  <div key={i} className="hint-item">
                    <span className="hint-bullet">💡</span>
                    <span>{h}</span>
                  </div>
                ))}
              </div>
            )}
            <div className="answer-label">Solution</div>
            <ol className="step-list">
              {current.explanation.steps.map((s, i) => (
                <li key={i} className="step-item">
                  <div className="step-num">{i + 1}</div>
                  <span>{s}</span>
                </li>
              ))}
            </ol>
            {current.explanation.answer && (
              <>
                <div className="answer-label" style={{ marginTop: "0.75rem" }}>
                  Answer
                </div>
                <div className="answer-text">{current.explanation.answer}</div>
              </>
            )}
          </div>
        )
      )}

      {revealed && (
        <div className="practice-nav-row" style={{ marginTop: "1rem" }}>
          <button
            className="practice-result-btn correct"
            onClick={() => markResult("correct")}
          >
            ✅ Got it
          </button>
          <button
            className="practice-result-btn incorrect"
            onClick={() => markResult("incorrect")}
          >
            ❌ Missed it
          </button>
        </div>
      )}
    </div>
  );
}

// ============================================================
// MAIN APP
// ============================================================

export default function App() {
  const [screen, setScreen] = useState<Screen>("onboarding");
  const [onboarding, setOnboarding] = useState<OnboardingState | null>(
    ls<OnboardingState | null>(SK_ONBOARDING, null),
  );
  const [prevScreen, setPrevScreen] = useState<Screen>("today");
  const [topicId, setTopicId] = useState<string | null>(null);

  // If we already have onboarding data, skip to today
  useEffect(() => {
    if (onboarding) {
      setScreen("today");
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleOnboardingDone = (state: OnboardingState) => {
    lsSet(SK_ONBOARDING, state);
    setOnboarding(state);
    setScreen("today");
  };

  const goToTopic = (id: string) => {
    setTopicId(id);
    setPrevScreen(screen);
    setScreen("topic");
  };

  const goBack = () => {
    setScreen(prevScreen === "topic" ? "today" : prevScreen);
    setTopicId(null);
  };

  if (screen === "onboarding" || !onboarding) {
    return <OnboardingScreen onDone={handleOnboardingDone} />;
  }

  return (
    <div className="app-shell">
      {/* Screens */}
      {screen === "today" && (
        <TodayScreen
          key="today"
          onboarding={onboarding}
          onGoTopic={goToTopic}
        />
      )}
      {screen === "browse" && (
        <BrowseScreen
          key="browse"
          onboarding={onboarding}
          onGoTopic={goToTopic}
        />
      )}
      {screen === "topic" && topicId && (
        <TopicDetailScreen
          key={topicId}
          topicId={topicId}
          lang={onboarding.language}
          onBack={goBack}
        />
      )}
      {screen === "practice" && (
        <PracticeScreen key="practice" onboarding={onboarding} />
      )}

      {/* Bottom Nav */}
      <nav className="bottom-nav">
        <button
          className={`nav-item ${screen === "today" ? "active" : ""}`}
          onClick={() => setScreen("today")}
        >
          <span className="nav-icon">🏠</span>
          Today
        </button>
        <button
          className={`nav-item ${screen === "browse" || screen === "topic" ? "active" : ""}`}
          onClick={() => setScreen("browse")}
        >
          <span className="nav-icon">📚</span>
          Browse
        </button>
        <button
          className={`nav-item ${screen === "practice" ? "active" : ""}`}
          onClick={() => setScreen("practice")}
        >
          <span className="nav-icon">✏️</span>
          Practice
        </button>
      </nav>
    </div>
  );
}
