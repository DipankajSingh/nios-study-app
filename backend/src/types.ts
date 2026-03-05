// ══════════════════════════════════════════════════════════════════════════════
// Shared TypeScript types — single source of truth for the backend.
// Keep in sync with pipeline/schemas.py (Python) and schema.sql.
// ══════════════════════════════════════════════════════════════════════════════

// ── Catalog (read-only, produced by pipeline) ─────────────────────────────

export interface Subject {
  id: string              // e.g. "maths-12"
  name: string
  classLevel: '10' | '12'
  description: string
  icon: string
}

export interface Chapter {
  id: string              // e.g. "maths-12-ch01"
  subjectId: string
  title: string
  orderIndex: number
}

export interface Topic {
  id: string              // e.g. "maths-12-ch01-t01"
  chapterId: string
  title: string
  orderIndex: number
  highYieldScore: number  // 0-100
  estMinutes: number
}

export interface TopicContent {
  id: string
  topicId: string
  lang: 'en' | 'hi' | 'hinglish'
  summaryBullets: string[]
  whyImportant: string
  commonMistakes: string[]
}

// ── PYQ Bank ──────────────────────────────────────────────────────────────

export interface Pyq {
  id: string
  subjectId: string
  topicId: string
  year: string
  session: string         // "March" or "October"
  questionText: string
  marks: number
  difficulty: 'easy' | 'medium' | 'hard'
  frequencyScore: number  // 1-10
  questionType: 'mcq' | 'short' | 'long' | 'numerical'
}

export interface PyqExplanation {
  id: string
  pyqId: string
  lang: 'en' | 'hi' | 'hinglish'
  steps: string[]
  hints: string[]
  answer: string
}

// ── API request/response types ───────────────────────────────────────────

export type StudyGoal = 'pass' | 'sixty' | 'eighty'
export type Lang = 'en' | 'hi' | 'hinglish'

export interface DailyTask {
  id: string
  subject: string
  subjectId: string
  topic: string
  topicId: string
  type: 'READ_NOTES' | 'PRACTICE_PYQ_SET' | 'REVISE_WRONGS'
  estimatedMinutes: number
  highYieldScore: number
}

export interface DailyPlan {
  dateLabel: string
  tasks: DailyTask[]
}

export interface PlanParams {
  subjectIds: string[]
  dailyMinutes: number
  goal: StudyGoal
  examDate?: string
  doneTopicIds?: string[]
}

// ── Topic detail response (assembled per-request) ────────────────────────

export interface TopicDetailsResponse {
  topicId: string
  content: TopicContent | null
  pyqs: Array<Pyq & { explanation: PyqExplanation | null }>
}

export interface SyllabusResponse {
  subject: Subject
  chapters: Array<Chapter & {
    topics: Array<Topic & { hasContent: boolean }>
  }>
}
