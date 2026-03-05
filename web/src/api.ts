import type { DailyPlan, StudyGoal } from './domain'

const API_BASE =
  import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8787'

export async function fetchDailyPlan(params: {
  subjectIds: string[]
  dailyMinutes: number
  goal: StudyGoal
  examDate?: string
  doneTopicIds?: string[]
}): Promise<DailyPlan> {
  const query = new URLSearchParams({
    subjects: params.subjectIds.join(','),
    dailyMinutes: String(params.dailyMinutes),
    goal: params.goal,
  })
  if (params.examDate) {
    query.set('examDate', params.examDate)
  }
  if (params.doneTopicIds && params.doneTopicIds.length > 0) {
    query.set('doneTopics', params.doneTopicIds.join(','))
  }

  const res = await fetch(`${API_BASE}/api/plan/today?${query.toString()}`)

  if (!res.ok) {
    throw new Error(`Backend error: ${res.status}`)
  }

  return (await res.json()) as DailyPlan
}
