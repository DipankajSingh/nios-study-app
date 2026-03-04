export type StudyGoal = 'pass' | 'sixty' | 'eighty'

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
