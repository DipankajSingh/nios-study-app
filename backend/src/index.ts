// ── NIOS Study App — Cloudflare Worker Router ────────────────────────────
//
// Thin routing layer. All business logic lives in routes/ and services/.
// Data loading lives in data/.

import { json, notFound, preflight } from './lib/response'
import { handleHealth } from './routes/health'
import { handleSubjects, handleSyllabus, handleTopicDetails, handleSubjectPyqs } from './routes/catalog'
import { handlePlanToday } from './routes/plan'

export default {
  async fetch(request: Request): Promise<Response> {
    const url = new URL(request.url)
    const path = url.pathname

    // CORS preflight
    if (request.method === 'OPTIONS') return preflight()

    // ── Health ───────────────────────────────────────────────────────────
    if (path === '/api/health') return handleHealth()

    // ── Catalog ──────────────────────────────────────────────────────────
    if (path === '/api/subjects') return handleSubjects(url)

    const syllabusMatch = path.match(/^\/api\/subjects\/([^/]+)\/syllabus$/)
    if (syllabusMatch) return handleSyllabus(decodeURIComponent(syllabusMatch[1]))

    const detailsMatch = path.match(/^\/api\/topics\/([^/]+)\/details$/)
    if (detailsMatch) return handleTopicDetails(decodeURIComponent(detailsMatch[1]), url)

    const pyqsMatch = path.match(/^\/api\/subjects\/([^/]+)\/pyqs$/)
    if (pyqsMatch) return handleSubjectPyqs(decodeURIComponent(pyqsMatch[1]), url)

    // ── Plan ─────────────────────────────────────────────────────────────
    if (path === '/api/plan/today') return handlePlanToday(url)

    return notFound('Not found')
  },
}
