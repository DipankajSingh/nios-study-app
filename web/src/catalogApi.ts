// DTO types matching the backend API responses

export interface SubjectDto {
  id: string
  name: string
  classLevel: '10' | '12'
  description: string
  icon: string
}

export interface ChapterDto {
  id: string
  subjectId: string
  title: string
  orderIndex: number
}

export interface TopicDto {
  id: string
  chapterId: string
  title: string
  orderIndex: number
  highYieldScore: number
  estMinutes: number
  hasContent?: boolean
}

export interface SyllabusChapterDto extends ChapterDto {
  topics: TopicDto[]
}

export interface SyllabusDto {
  subject: SubjectDto
  chapters: SyllabusChapterDto[]
}

export interface TopicContentDto {
  id: string
  topicId: string
  lang: 'en' | 'hi' | 'hinglish'
  summaryBullets: string[]
  whyImportant: string
  commonMistakes: string[]
}

export interface PyqExplanationDto {
  id: string
  pyqId: string
  lang: 'en' | 'hi' | 'hinglish'
  steps: string[]
  hints: string[]
  answer: string
}

export interface PyqDto {
  id: string
  subjectId: string
  topicId: string
  year: string
  session: string
  questionText: string
  marks: number
  difficulty: 'easy' | 'medium' | 'hard'
  frequencyScore: number
  questionType: 'mcq' | 'short' | 'long' | 'numerical'
  explanation: PyqExplanationDto | null
}

export interface TopicDetailsDto {
  topicId: string
  content: TopicContentDto | null
  pyqs: PyqDto[]
}

const API_BASE =
  import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8787'

export async function fetchSubjects(
  classLevel: '10' | '12',
): Promise<SubjectDto[]> {
  const res = await fetch(
    `${API_BASE}/api/subjects?classLevel=${encodeURIComponent(classLevel)}`,
  )
  if (!res.ok) throw new Error('Failed to fetch subjects')
  return (await res.json()) as SubjectDto[]
}

export async function fetchSyllabus(subjectId: string): Promise<SyllabusDto> {
  const res = await fetch(
    `${API_BASE}/api/subjects/${encodeURIComponent(subjectId)}/syllabus`,
  )
  if (!res.ok) throw new Error('Failed to fetch syllabus')
  return (await res.json()) as SyllabusDto
}

export async function fetchTopicDetails(
  topicId: string,
  lang: 'en' | 'hi' | 'hinglish' = 'en',
): Promise<TopicDetailsDto | null> {
  try {
    const res = await fetch(
      `${API_BASE}/api/topics/${encodeURIComponent(topicId)}/details?lang=${lang}`,
    )
    if (!res.ok) return null
    return (await res.json()) as TopicDetailsDto
  } catch {
    return null
  }
}

export async function fetchSubjectPyqs(
  subjectId: string,
  lang: 'en' | 'hi' | 'hinglish' = 'en',
): Promise<PyqDto[]> {
  const res = await fetch(
    `${API_BASE}/api/subjects/${encodeURIComponent(subjectId)}/pyqs?lang=${lang}`,
  )
  if (!res.ok) throw new Error('Failed to fetch subject PYQs')
  return (await res.json()) as PyqDto[]
}

