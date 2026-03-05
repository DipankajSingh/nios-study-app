// ── Data loader ──────────────────────────────────────────────────────────
// Loads generated data (from pipeline) with fallback to mock data.

import * as generated from './generated'
import * as mock from '../mockData'

function pick<T>(gen: T[], fallback: T[]): T[] {
  return gen.length > 0 ? gen : fallback
}

export const subjects       = pick(generated.subjects,       mock.subjects)
export const chapters       = pick(generated.chapters,       mock.chapters)
export const topics         = pick(generated.topics,         mock.topics)
export const topicContents  = pick(generated.topicContents,  mock.topicContents)
export const pyqs           = pick(generated.pyqs,           mock.pyqs)
export const pyqExplanations = pick(generated.pyqExplanations, mock.pyqExplanations)
