#!/usr/bin/env ts-node
/**
 * scripts/seed.ts
 *
 * NIOS Content Seeder
 * ═══════════════════════════════════════════════════════════════════════════
 * Reads the generated .content.json and .pyqs.json files for a subject,
 * validates them, and generates backend/src/generatedData.ts.
 *
 * Usage (always preview first!):
 *   npx ts-node seed.ts --subject english-12 --dry-run
 *   npx ts-node seed.ts --subject english-12
 *
 * Output:
 *   Writes to ../backend/src/generatedData.ts
 */

import fs from 'fs'
import path from 'path'
import type { ContentJson, GeneratedTopicContent } from './generateContent'
import type { RawSubjectJson } from './ingest'

/**
 * Note: `ingestPyqs.ts` currently outputs a plain array and does not export types.
 * Keep PYQs optional here until that pipeline is upgraded to emit a stable schema.
 */
type GeneratedPyq = any
type PyqJson = { totalPyqs: number; pyqs: GeneratedPyq[] }

// ── CLI ───────────────────────────────────────────────────────────────────────

interface Args {
    subject: string
    dryRun: boolean
    lang: 'en' | 'hinglish'
}

function parseArgs(): Args {
    const raw = process.argv.slice(2)
    const get = (flag: string) => { const i = raw.indexOf(flag); return i >= 0 ? raw[i + 1] : undefined }
    const has = (flag: string) => raw.includes(flag)

    const subject = get('--subject')
    if (!subject) {
        console.error(`
Usage:
  npx ts-node seed.ts --subject english-12 --dry-run
  npx ts-node seed.ts --subject english-12
`)
        process.exit(1)
    }

    const langArg = get('--lang')
    return {
        subject,
        dryRun: has('--dry-run') || has('--dryrun'),
        lang: langArg === 'hinglish' ? 'hinglish' : 'en',
    }
}

// ── File finders ─────────────────────────────────────────────────────────────

function findFile(subject: string, suffix: string): string | null {
    const base = path.resolve(__dirname, '../content')
    if (!fs.existsSync(base)) return null
    for (const dir of fs.readdirSync(base).filter((d) => d.startsWith('class'))) {
        const candidate = path.join(base, dir, `${subject}${suffix}`)
        if (fs.existsSync(candidate)) return candidate
    }
    return null
}

function readSubjectConfig(subject: string): { description: string; icon: string } {
    const configPath = path.resolve(__dirname, `subjects/${subject}.json`)
    if (!fs.existsSync(configPath)) {
        return { description: '', icon: '📘' }
    }
    const cfg = JSON.parse(fs.readFileSync(configPath, 'utf-8')) as Partial<{
        description: string
        icon: string
    }>
    return {
        description: cfg.description ?? '',
        icon: cfg.icon ?? '📘',
    }
}

// ── Validation ────────────────────────────────────────────────────────────────

interface ValidationResult {
    ok: boolean
    errors: string[]
    warnings: string[]
}

function validateContent(content: ContentJson): ValidationResult {
    const errors: string[] = []
    const warnings: string[] = []

    for (const t of content.topics) {
        if (!t.topicId) errors.push(`Topic missing topicId: ${JSON.stringify(t).slice(0, 60)}`)
        if (!t.summaryBullets?.length) errors.push(`Topic ${t.topicId}: no summaryBullets`)
        if (!t.whyImportant) warnings.push(`Topic ${t.topicId}: missing whyImportant`)
        if (!t.commonMistakes?.length) warnings.push(`Topic ${t.topicId}: missing commonMistakes`)

        // Check for placeholder failures from generateContent.ts
        if (t.summaryBullets?.[0]?.includes('[Content generation failed')) {
            warnings.push(`Topic ${t.topicId}: has failed placeholder — re-run generateContent --resume`)
        }
    }

    return { ok: errors.length === 0, errors, warnings }
}

function validatePyqs(pyqs: PyqJson): ValidationResult {
    const errors: string[] = []
    const warnings: string[] = []

    for (const q of pyqs.pyqs) {
        if (!q.id) errors.push(`PYQ missing id`)
        if (!q.questionText) errors.push(`PYQ ${q.id}: no questionText`)
        if (!q.topicId) errors.push(`PYQ ${q.id}: no topicId`)
        if (!q.explanation?.steps?.length) warnings.push(`PYQ ${q.id}: missing explanation steps`)
    }

    return { ok: errors.length === 0, errors, warnings }
}

// ── TypeScript code generators ────────────────────────────────────────────────

function safeTsString(value: string): string {
    return value.replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/\r?\n/g, '\\n')
}

function estimateMinutesFromRawText(rawText: string): number {
    // Rough estimate: 140 wpm reading speed, clamp to sane bounds.
    const words = rawText.trim().split(/\s+/).filter(Boolean).length
    const minutes = Math.ceil(words / 140)
    return Math.max(5, Math.min(45, minutes))
}

function generateSubjectEntry(subject: RawSubjectJson['subject'], cfg: { description: string; icon: string }): string {
    return `  {
    id: '${safeTsString(subject.id)}',
    name: '${safeTsString(subject.name)}',
    classLevel: '${safeTsString(subject.classLevel)}',
    description: '${safeTsString(cfg.description)}',
    icon: '${safeTsString(cfg.icon)}',
  },`
}

function generateChapterEntries(rawSubject: RawSubjectJson): string {
    return rawSubject.chapters
        .map(
            (ch) =>
                `  { id: '${safeTsString(ch.id)}', subjectId: '${safeTsString(rawSubject.subject.id)}', title: '${safeTsString(ch.title)}', orderIndex: ${ch.orderIndex} },`,
        )
        .join('\n')
}

function generateTopicEntries(rawSubject: RawSubjectJson): string {
    return rawSubject.chapters
        .flatMap((ch) =>
            ch.topics.map((t) => {
                const estMinutes = estimateMinutesFromRawText(t.rawText ?? '')
                return `  { id: '${safeTsString(t.id)}', chapterId: '${safeTsString(ch.id)}', title: '${safeTsString(t.title)}', orderIndex: ${t.orderIndex}, highYieldScore: 75, estMinutes: ${estMinutes} },`
            }),
        )
        .join('\n')
}

function generateContentEntries(contents: GeneratedTopicContent[]): string {
    return contents
        .map((c) => {
            const bullets = c.summaryBullets.map((b) => `      '${safeTsString(b)}'`).join(',\n')
            const mistakes = c.commonMistakes.map((m) => `      '${safeTsString(m)}'`).join(',\n')
            return `  {
    id: '${safeTsString(c.id)}',
    topicId: '${safeTsString(c.topicId)}',
    lang: '${safeTsString(c.lang)}',
    summaryBullets: [
${bullets}
    ],
    whyImportant: '${safeTsString(c.whyImportant)}',
    commonMistakes: [
${mistakes}
    ],
  },`
        })
        .join('\n')
}

function generatePyqEntries(pyqs: GeneratedPyq[]): string {
    return pyqs
        .map(
            (q) => `    {
        id: '${q.id}',
        subjectId: '${q.subjectId}',
        topicId: '${q.topicId}',
        year: '${q.year}',
        session: '${q.session}',
        questionText: '${q.questionText.replace(/'/g, "\\'")}',
        marks: ${q.marks},
        difficulty: '${q.difficulty}',
        frequencyScore: ${q.frequencyScore},
        questionType: '${q.questionType}',
    },`,
        )
        .join('\n')
}

function generateExplanationEntries(pyqs: GeneratedPyq[]): string {
    return pyqs
        .filter((q) => q.explanation?.steps?.length)
        .map((q) => {
            const exp = q.explanation
            const steps = (exp.steps as string[]).map((s: string) => `            '${s.replace(/'/g, "\\'")}'`).join(',\n')
            const hints = (exp.hints as string[]).map((h: string) => `            '${h.replace(/'/g, "\\'")}'`).join(',\n')
            return `    {
        id: '${exp.id}',
        pyqId: '${exp.pyqId}',
        lang: '${exp.lang}',
        hints: [
${hints}
        ],
        steps: [
${steps}
        ],
        answer: '${exp.answer.replace(/'/g, "\\'")}',
    },`
        })
        .join('\n')
}

function generateBackendDataTs(opts: {
    rawSubject: RawSubjectJson
    subjectCfg: { description: string; icon: string }
    contents: GeneratedTopicContent[]
    pyqs: GeneratedPyq[]
}): string {
    const { rawSubject, subjectCfg, contents, pyqs } = opts

    return `// This file is AUTO-GENERATED by scripts/seed.ts. Do not edit by hand.
// Generated at: ${new Date().toISOString()}

import type {
  Subject,
  Chapter,
  Topic,
  TopicContent,
  Pyq,
  PyqExplanation,
} from './mockData'

export const subjects: Subject[] = [
${generateSubjectEntry(rawSubject.subject, subjectCfg)}
]

export const chapters: Chapter[] = [
${generateChapterEntries(rawSubject)}
]

export const topics: Topic[] = [
${generateTopicEntries(rawSubject)}
]

export const topicContents: TopicContent[] = [
${generateContentEntries(contents)}
]

export const pyqs: Pyq[] = [
${generatePyqEntries(pyqs)}
]

export const pyqExplanations: PyqExplanation[] = [
${generateExplanationEntries(pyqs)}
]
`
}

// ── Main ─────────────────────────────────────────────────────────────────────

async function main() {
    const args = parseArgs()

    // ---- Load raw JSON (for chapter/topic structure)
    const rawFile = findFile(args.subject, '.raw.json')
    if (!rawFile) {
        console.error(`❌ ${args.subject}.raw.json not found. Run ingest.ts first.`)
        process.exit(1)
    }
    const rawSubject: RawSubjectJson = JSON.parse(fs.readFileSync(rawFile, 'utf-8'))

    // ---- Load content JSON
    const langSuffix = args.lang === 'en' ? '' : `.${args.lang}`
    const contentFile = findFile(args.subject, `${langSuffix}.content.json`)
    if (!contentFile) {
        console.error(`❌ ${args.subject}${langSuffix}.content.json not found. Run generateContent.ts first.`)
        process.exit(1)
    }
    const content: ContentJson = JSON.parse(fs.readFileSync(contentFile, 'utf-8'))

    // ---- Load pyqs JSON (optional; schema not yet stable)
    const pyqFile = findFile(args.subject, '.pyqs.json')
    let pyqData: PyqJson | null = null
    if (pyqFile) {
        const parsed = JSON.parse(fs.readFileSync(pyqFile, 'utf-8'))
        if (Array.isArray(parsed)) {
            console.warn(`⚠️  ${args.subject}.pyqs.json is an array (legacy). Skipping PYQ seeding for now.`)
            pyqData = null
        } else {
            pyqData = parsed as PyqJson
            console.log(`✅ Loaded ${pyqData!.totalPyqs} PYQs from ${pyqFile}`)
        }
    } else {
        console.warn(`⚠️  No ${args.subject}.pyqs.json found — seeding content only (no PYQs)`)
    }

    // ---- Validate
    console.log('\n🔍 Validating content…')
    const contentValidation = validateContent(content)
    if (!contentValidation.ok) {
        console.error('❌ Content validation failed:')
        contentValidation.errors.forEach((e) => console.error('   •', e))
        process.exit(1)
    }
    if (contentValidation.warnings.length) {
        contentValidation.warnings.forEach((w) => console.warn('   ⚠️ ', w))
    }
    console.log(`✅ ${content.totalTopics} topic contents valid`)

    if (pyqData) {
        const pyqValidation = validatePyqs(pyqData)
        if (!pyqValidation.ok) {
            console.error('❌ PYQ validation failed:')
            pyqValidation.errors.forEach((e) => console.error('   •', e))
            process.exit(1)
        }
        if (pyqValidation.warnings.length)
            pyqValidation.warnings.forEach((w) => console.warn('   ⚠️ ', w))
        console.log(`✅ ${pyqData.totalPyqs} PYQs valid`)
    }

    // ---- Write generated backend data
    const generatedDataPath = path.resolve(__dirname, '../backend/src/generatedData.ts')
    const subjectCfg = readSubjectConfig(args.subject)

    const generatedTs = generateBackendDataTs({
        rawSubject,
        subjectCfg,
        contents: content.topics,
        pyqs: pyqData?.pyqs ?? [],
    })

    if (args.dryRun) {
        const previewPath = `/tmp/${args.subject}-generatedData-preview.ts`
        fs.writeFileSync(previewPath, generatedTs, 'utf-8')
        console.log(`\n🔍 DRY RUN — no changes made`)
        console.log(`📄 Preview written to: ${previewPath}`)
        console.log(`\nIf preview looks good:`)
        console.log(`   npx ts-node seed.ts --subject ${args.subject}\n`)
        return
    }

    // Backup existing generated data if present
    if (fs.existsSync(generatedDataPath)) {
        const bakPath = `${generatedDataPath}.bak.${Date.now()}`
        fs.copyFileSync(generatedDataPath, bakPath)
        console.log(`\n📦 Backed up existing generated data to: ${bakPath}`)
    }

    fs.writeFileSync(generatedDataPath, generatedTs, 'utf-8')
    console.log(`\n✅ Wrote ${generatedDataPath}`)
    console.log('\n🚀 Restart the backend to see the new content:')
    console.log('   cd backend && npx wrangler dev --port 8787\n')
}

main().catch((err) => {
    console.error('❌ Fatal error:', err)
    process.exit(1)
})
