// ── Response helpers ──────────────────────────────────────────────────────

const CORS_HEADERS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
}

export function json(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json', ...CORS_HEADERS },
  })
}

export function notFound(message = 'Not found'): Response {
  return json({ error: message }, 404)
}

export function badRequest(message = 'Bad request'): Response {
  return json({ error: message }, 400)
}

export function preflight(): Response {
  return new Response(null, { status: 204, headers: CORS_HEADERS })
}
