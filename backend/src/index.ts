// Prefer generated data (created by scripts/seed.ts) but fall back to mock data
import * as generated from './generatedData'
import * as mock from './mockData'

const {
  subjects: genSubjects,
  chapters: genChapters,
  topics: genTopics,
  topicContents: genTopicContents,
  pyqs: genPyqs,
  pyqExplanations: genPyqExplanations,
} = generated

const {
  subjects: mockSubjects,
  chapters: mockChapters,
  topics: mockTopics,
  topicContents: mockTopicContents,
  pyqs: mockPyqs,
  pyqExplanations: mockPyqExplanations,
} = mock

// choose generated if it has any topics (otherwise use mock)
const subjects = genSubjects.length ? genSubjects : mockSubjects
const chapters = genChapters.length ? genChapters : mockChapters
const topics = genTopics.length ? genTopics : mockTopics
const topicContents = genTopicContents.length ? genTopicContents : mockTopicContents
const pyqs = genPyqs.length ? genPyqs : mockPyqs
const pyqExplanations = genPyqExplanations.length ? genPyqExplanations : mockPyqExplanations

type StudyGoal = 'pass' | 'sixty' | 'eighty'

interface DailyTask {
  id: string
  subject: string
  subjectId: string
  topic: string
  topicId: string
  type: 'READ_NOTES' | 'PRACTICE_PYQ_SET' | 'REVISE_WRONGS'
  estimatedMinutes: number
  highYieldScore: number
}

interface DailyPlan {
  dateLabel: string
  tasks: DailyTask[]
}

function generateDailyPlan(options: {
  subjectIds: string[]
  dailyMinutes: number
  goal: StudyGoal
}): DailyPlan {
  const { subjectIds, dailyMinutes, goal } = options

  // Get all topics for the selected subjects, sorted by high yield score descending
  const subjectTopics = topics
    .filter((t) => {
      const chapter = chapters.find((c) => c.id === t.chapterId)
      return chapter && subjectIds.includes(chapter.subjectId)
    })
    .sort((a, b) => b.highYieldScore - a.highYieldScore)

  // For "pass" goal, only take top 60% high-yield topics
  const cutoff =
    goal === 'pass' ? 0.6 : goal === 'sixty' ? 0.8 : 1.0
  const candidateTopics = subjectTopics.slice(
    0,
    Math.ceil(subjectTopics.length * cutoff),
  )

  const tasks: DailyTask[] = []
  let minutesLeft = dailyMinutes

  for (const topic of candidateTopics) {
    if (minutesLeft <= 0) break
    const chapter = chapters.find((c) => c.id === topic.chapterId)
    const subject = subjects.find((s) => s.id === chapter?.subjectId)
    if (!subject) continue

    if (minutesLeft >= topic.estMinutes) {
      tasks.push({
        id: `read-${topic.id}`,
        subject: subject.name,
        subjectId: subject.id,
        topic: topic.title,
        topicId: topic.id,
        type: 'READ_NOTES',
        estimatedMinutes: topic.estMinutes,
        highYieldScore: topic.highYieldScore,
      })
      minutesLeft -= topic.estMinutes
    }

    // Add a practice task if there are PYQs for this topic and time permits
    const topicPyqs = pyqs.filter((p) => p.topicId === topic.id)
    if (topicPyqs.length > 0 && minutesLeft >= 10) {
      tasks.push({
        id: `practice-${topic.id}`,
        subject: subject.name,
        subjectId: subject.id,
        topic: topic.title,
        topicId: topic.id,
        type: 'PRACTICE_PYQ_SET',
        estimatedMinutes: Math.min(15, minutesLeft),
        highYieldScore: topic.highYieldScore,
      })
      minutesLeft -= Math.min(15, minutesLeft)
    }
  }

  return {
    dateLabel: 'Today',
    tasks,
  }
}

function json(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      'Content-Type': 'application/json',
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
    },
  })
}

export default {
  async fetch(request: Request): Promise<Response> {
    const url = new URL(request.url)
    const path = url.pathname

    // Handle CORS preflight
    if (request.method === 'OPTIONS') {
      return new Response(null, {
        status: 204,
        headers: {
          'Access-Control-Allow-Origin': '*',
          'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
          'Access-Control-Allow-Headers': 'Content-Type',
        },
      })
    }

    // Health check
    if (path === '/api/health') {
      return json({ status: 'ok', version: '2.0.0' })
    }

    // GET /api/subjects?classLevel=12
    if (path === '/api/subjects') {
      const classLevel = url.searchParams.get('classLevel') || '12'
      const filtered = subjects.filter((s) => s.classLevel === classLevel)
      return json(filtered)
    }

    // GET /api/subjects/:id/syllabus
    const syllabusMatch = path.match(/^\/api\/subjects\/([^/]+)\/syllabus$/)
    if (syllabusMatch) {
      const subjectId = decodeURIComponent(syllabusMatch[1])
      const subject = subjects.find(s => s.id === subjectId)
      if (!subject) return json({ error: 'Subject not found' }, 404)

      const subjectChapters = chapters.filter(c => c.subjectId === subjectId).sort((a, b) => a.orderIndex - b.orderIndex)

      const chaptersWithTopics = subjectChapters.map(chapter => {
        const chapterTopics = topics.filter(t => t.chapterId === chapter.id).sort((a, b) => a.orderIndex - b.orderIndex)

        const topicsWithContentFlag = chapterTopics.map(topic => {
          const hasContent = topicContents.some(tc => tc.topicId === topic.id) || pyqs.some(p => p.topicId === topic.id)
          return { ...topic, hasContent }
        })

        return {
          ...chapter,
          topics: topicsWithContentFlag
        }
      })

      return json({
        subject,
        chapters: chaptersWithTopics
      })
    }

    // GET /api/topics/:id/details?lang=en
    const detailsMatch = path.match(/^\/api\/topics\/([^/]+)\/details$/)
    if (detailsMatch) {
      const topicId = decodeURIComponent(detailsMatch[1])
      const lang = (url.searchParams.get('lang') || 'en') as 'en' | 'hi' | 'hinglish'

      const content = topicContents.find(
        (c) => c.topicId === topicId && c.lang === lang,
      ) ?? topicContents.find((c) => c.topicId === topicId && c.lang === 'en')

      const topicPyqs = pyqs.filter((p) => p.topicId === topicId)
      const withExplanations = topicPyqs.map((p) => {
        const exp =
          pyqExplanations.find((e) => e.pyqId === p.id && e.lang === lang) ??
          pyqExplanations.find((e) => e.pyqId === p.id && e.lang === 'en')
        return { ...p, explanation: exp ?? null }
      })

      if (!content && topicPyqs.length === 0) {
        return json({ error: 'Content not found' }, 404)
      }

      return json({
        topicId,
        content: content ?? null,
        pyqs: withExplanations
      })
    }

    // GET /api/subjects/:id/pyqs?lang=en
    const subjPyqsMatch = path.match(/^\/api\/subjects\/([^/]+)\/pyqs$/)
    if (subjPyqsMatch) {
      const subjectId = decodeURIComponent(subjPyqsMatch[1])
      const lang = (url.searchParams.get('lang') || 'en') as 'en' | 'hi' | 'hinglish'

      const subjectPyqs = pyqs.filter((p) => p.subjectId === subjectId)
      const withExplanations = subjectPyqs.map((p) => {
        const exp =
          pyqExplanations.find((e) => e.pyqId === p.id && e.lang === lang) ??
          pyqExplanations.find((e) => e.pyqId === p.id && e.lang === 'en')
        return { ...p, explanation: exp ?? null }
      })

      return json(withExplanations)
    }

    // GET /api/plan/today?subjects=maths-12,english-12&dailyMinutes=60&goal=pass
    if (path === '/api/plan/today') {
      const subjectsParam = url.searchParams.get('subjects') || ''
      const dailyMinutes = Number(url.searchParams.get('dailyMinutes') || '60')
      const goal = (url.searchParams.get('goal') || 'pass') as StudyGoal
      const subjectIds = subjectsParam
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean)

      // If no valid subjectIds given, derive from subject names (backwards compat)
      const resolvedIds =
        subjectIds.length > 0
          ? subjectIds
          : subjects.map((s) => s.id).slice(0, 2)

      const plan = generateDailyPlan({ subjectIds: resolvedIds, dailyMinutes, goal })
      return json(plan)
    }

    return json({ error: 'Not found' }, 404)
  },
}
