// ── Catalog Routes ───────────────────────────────────────────────────────
// GET /api/subjects
// GET /api/subjects/:id/syllabus
// GET /api/subjects/:id/pyqs
// GET /api/topics/:id/details

import { subjects, chapters, topics, topicContents, pyqs, pyqExplanations } from '../data'
import { json, notFound } from '../lib/response'
import type { Lang } from '../types'

export function handleSubjects(url: URL): Response {
  const classLevel = url.searchParams.get('classLevel') || '12'
  return json(subjects.filter((s) => s.classLevel === classLevel))
}

export function handleSyllabus(subjectId: string): Response {
  const subject = subjects.find((s) => s.id === subjectId)
  if (!subject) return notFound('Subject not found')

  const subjectChapters = chapters
    .filter((c) => c.subjectId === subjectId)
    .sort((a, b) => a.orderIndex - b.orderIndex)

  const chaptersWithTopics = subjectChapters.map((chapter) => {
    const chapterTopics = topics
      .filter((t) => t.chapterId === chapter.id)
      .sort((a, b) => a.orderIndex - b.orderIndex)

    const topicsWithContentFlag = chapterTopics.map((topic) => {
      const hasContent =
        topicContents.some((tc) => tc.topicId === topic.id) ||
        pyqs.some((p) => p.topicId === topic.id)
      return { ...topic, hasContent }
    })

    return { ...chapter, topics: topicsWithContentFlag }
  })

  return json({ subject, chapters: chaptersWithTopics })
}

export function handleTopicDetails(topicId: string, url: URL): Response {
  const lang = (url.searchParams.get('lang') || 'en') as Lang

  const content =
    topicContents.find((c) => c.topicId === topicId && c.lang === lang) ??
    topicContents.find((c) => c.topicId === topicId && c.lang === 'en')

  const topicPyqs = pyqs.filter((p) => p.topicId === topicId)
  const withExplanations = topicPyqs.map((p) => {
    const exp =
      pyqExplanations.find((e) => e.pyqId === p.id && e.lang === lang) ??
      pyqExplanations.find((e) => e.pyqId === p.id && e.lang === 'en')
    return { ...p, explanation: exp ?? null }
  })

  if (!content && topicPyqs.length === 0) return notFound('Content not found')

  return json({ topicId, content: content ?? null, pyqs: withExplanations })
}

export function handleSubjectPyqs(subjectId: string, url: URL): Response {
  const lang = (url.searchParams.get('lang') || 'en') as Lang

  const subjectPyqs = pyqs.filter((p) => p.subjectId === subjectId)
  const withExplanations = subjectPyqs.map((p) => {
    const exp =
      pyqExplanations.find((e) => e.pyqId === p.id && e.lang === lang) ??
      pyqExplanations.find((e) => e.pyqId === p.id && e.lang === 'en')
    return { ...p, explanation: exp ?? null }
  })

  return json(withExplanations)
}
