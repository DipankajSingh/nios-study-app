const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8787'

export async function fetchSubjects(classLevel) {
    const res = await fetch(
        `${API_BASE}/api/subjects?classLevel=${encodeURIComponent(classLevel)}`
    )
    if (!res.ok) throw new Error('Failed to fetch subjects')
    return res.json()
}

export async function fetchSyllabus(subjectId) {
    const res = await fetch(
        `${API_BASE}/api/subjects/${encodeURIComponent(subjectId)}/syllabus`
    )
    if (!res.ok) throw new Error('Failed to fetch syllabus')
    return res.json()
}

export async function fetchTopicDetails(topicId, lang = 'en') {
    try {
        const res = await fetch(
            `${API_BASE}/api/topics/${encodeURIComponent(topicId)}/details?lang=${lang}`
        )
        if (!res.ok) return null
        return res.json()
    } catch {
        return null
    }
}

export async function fetchSubjectPyqs(subjectId, lang = 'en') {
    const res = await fetch(
        `${API_BASE}/api/subjects/${encodeURIComponent(subjectId)}/pyqs?lang=${lang}`
    )
    if (!res.ok) throw new Error('Failed to fetch subject PYQs')
    return res.json()
}
