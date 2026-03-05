// ── Plan Routes ──────────────────────────────────────────────────────────
// GET /api/plan/today

import { subjects } from '../data'
import { json } from '../lib/response'
import { generateDailyPlan } from '../services/planGenerator'
import type { StudyGoal } from '../types'

export function handlePlanToday(url: URL): Response {
  const subjectsParam = url.searchParams.get('subjects') || ''
  const dailyMinutes = Number(url.searchParams.get('dailyMinutes') || '60')
  const goal = (url.searchParams.get('goal') || 'pass') as StudyGoal
  const examDate = url.searchParams.get('examDate') || undefined
  const doneTopicsParam = url.searchParams.get('doneTopics') || ''

  const subjectIds = subjectsParam.split(',').map((s) => s.trim()).filter(Boolean)
  const doneTopicIds = doneTopicsParam.split(',').map((s) => s.trim()).filter(Boolean)

  const resolvedIds = subjectIds.length > 0
    ? subjectIds
    : subjects.map((s) => s.id).slice(0, 2)

  const plan = generateDailyPlan({
    subjectIds: resolvedIds,
    dailyMinutes,
    goal,
    examDate,
    doneTopicIds,
  })

  return json(plan)
}
