// ── Plan Generator Service ───────────────────────────────────────────────
//
// Features:
// 1. Exam-date awareness — spreads topics across remaining days
// 2. Completed topics exclusion — skips done topics
// 3. Subject balancing — round-robin across subjects
// 4. PYQ frequency boost — "most-asked" topics get priority
// 5. Spaced repetition — REVISE_WRONGS for completed topics with PYQs
// 6. Goal-based weighting — pass=high-yield only, eighty=full coverage

import { subjects, chapters, topics, pyqs } from '../data'
import type { StudyGoal, DailyTask, DailyPlan, PlanParams } from '../types'

function computeTopicPriority(
  topic: typeof topics[number],
  goal: StudyGoal,
): number {
  let score = topic.highYieldScore

  // PYQ frequency boost (0-10 scale → 0-20 bonus)
  const topicPyqs = pyqs.filter((p) => p.topicId === topic.id)
  if (topicPyqs.length > 0) {
    const avgFreq = topicPyqs.reduce((s, p) => s + p.frequencyScore, 0) / topicPyqs.length
    score += avgFreq * 2
  }

  // Goal multiplier
  if (goal === 'pass') score *= 1.3
  else if (goal === 'sixty') score *= 1.1

  return score
}

export function generateDailyPlan(params: PlanParams): DailyPlan {
  const { subjectIds, dailyMinutes, goal, examDate, doneTopicIds = [] } = params
  const doneSet = new Set(doneTopicIds)

  // 1. Days remaining
  let daysLeft = 30
  if (examDate) {
    const diff = new Date(examDate).getTime() - Date.now()
    daysLeft = Math.max(1, Math.ceil(diff / 86_400_000))
  }

  // 2. Per-subject sorted queues (excluding done)
  type Enriched = typeof topics[number] & { _sid: string; _sname: string; _pri: number }
  const queues = new Map<string, Enriched[]>()

  for (const sid of subjectIds) {
    const sub = subjects.find((s) => s.id === sid)
    if (!sub) continue

    const q = topics
      .filter((t) => {
        if (doneSet.has(t.id)) return false
        const ch = chapters.find((c) => c.id === t.chapterId)
        return ch && ch.subjectId === sid
      })
      .map((t) => ({ ...t, _sid: sid, _sname: sub.name, _pri: computeTopicPriority(t, goal) }))
      .sort((a, b) => b._pri - a._pri)

    const cutoff = goal === 'pass' ? 0.6 : goal === 'sixty' ? 0.8 : 1.0
    queues.set(sid, q.slice(0, Math.ceil(q.length * cutoff)))
  }

  // 3. Today's slice
  let totalUndone = 0
  for (const q of queues.values()) totalUndone += q.length
  const topicsPerDay = Math.max(1, Math.ceil(totalUndone / daysLeft))

  // 4. Round-robin pick
  const picked: Enriched[] = []
  const iters = new Map<string, number>(subjectIds.map((s) => [s, 0]))
  let count = 0, stuck = 0

  while (count < topicsPerDay && stuck < subjectIds.length) {
    stuck = 0
    for (const sid of subjectIds) {
      if (count >= topicsPerDay) break
      const q = queues.get(sid)
      const i = iters.get(sid) ?? 0
      if (!q || i >= q.length) { stuck++; continue }
      picked.push(q[i])
      iters.set(sid, i + 1)
      count++
    }
  }

  // 5. Build tasks within time budget
  const tasks: DailyTask[] = []
  const revBudget = doneTopicIds.length > 0 ? Math.min(Math.floor(dailyMinutes * 0.2), 20) : 0
  let minutesLeft = dailyMinutes - revBudget

  for (const t of picked) {
    if (minutesLeft <= 0) break

    if (minutesLeft >= t.estMinutes) {
      tasks.push({
        id: `read-${t.id}`, subject: t._sname, subjectId: t._sid,
        topic: t.title, topicId: t.id, type: 'READ_NOTES',
        estimatedMinutes: t.estMinutes, highYieldScore: t.highYieldScore,
      })
      minutesLeft -= t.estMinutes
    }

    const tPyqs = pyqs.filter((p) => p.topicId === t.id)
    if (tPyqs.length > 0 && minutesLeft >= 10) {
      const time = Math.min(15, minutesLeft)
      tasks.push({
        id: `practice-${t.id}`, subject: t._sname, subjectId: t._sid,
        topic: t.title, topicId: t.id, type: 'PRACTICE_PYQ_SET',
        estimatedMinutes: time, highYieldScore: t.highYieldScore,
      })
      minutesLeft -= time
    }
  }

  // 6. Spaced repetition for done topics
  if (revBudget > 0) {
    let rev = revBudget
    const candidates = topics
      .filter((t) => doneSet.has(t.id) && pyqs.some((p) => p.topicId === t.id))
      .sort((a, b) => b.highYieldScore - a.highYieldScore)

    for (const t of candidates) {
      if (rev < 5) break
      const ch = chapters.find((c) => c.id === t.chapterId)
      const sub = subjects.find((s) => s.id === ch?.subjectId)
      if (!sub || !subjectIds.includes(sub.id)) continue
      tasks.push({
        id: `revise-${t.id}`, subject: sub.name, subjectId: sub.id,
        topic: t.title, topicId: t.id, type: 'REVISE_WRONGS',
        estimatedMinutes: 5, highYieldScore: t.highYieldScore,
      })
      rev -= 5
    }
  }

  return { dateLabel: 'Today', tasks }
}
