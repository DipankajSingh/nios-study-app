// ── Health Route ─────────────────────────────────────────────────────────
// GET /api/health

import { json } from '../lib/response'

export function handleHealth(): Response {
  return json({ status: 'ok', version: '2.0.0' })
}
