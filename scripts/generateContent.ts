#!/usr/bin/env ts-node
/**
 * scripts/generateContent.ts
 *
 * NIOS AI Content Generation Script
 * ═══════════════════════════════════════════════════════════════════════════
 * Reads a .raw.json file from ingest.ts, calls Gemini 2.0 Flash for each topic,
 * and produces a .content.json with notes, why-important, and common mistakes
 * in English and Hinglish.
 *
 * Usage:
 *   npx ts-node generateContent.ts --subject english-12
 *   npx ts-node generateContent.ts --subject english-12 --lang hinglish
 *   npx ts-node generateContent.ts --subject english-12 --resume   (skip done topics)
 *
 * Needs:
 *   .env with GEMINI_API_KEY=...
 *
 * Output:
 *   ../content/class12/english-12.content.json
 */

import fs from 'fs'
import path from 'path'
import dotenv from 'dotenv'
// AI provider abstraction
import type { RawSubjectJson, RawTopic, RawChapter } from './ingest'
import {
    AIProvider,
    GeneratedOutput,
    getProvider,
    rateLimited,
    RateLimitError,
} from './aiProviders'

dotenv.config()

// ── Types ─────────────────────────────────────────────────────────────────────

type Lang = 'en' | 'hinglish'

export interface GeneratedTopicContent {
    id: string                   // matches topicId in schema
    topicId: string
    lang: Lang
    summaryBullets: string[]     // 8-12 concise bullet points from the text
    whyImportant: string         // 2-3 sentence exam relevance
    commonMistakes: string[]     // 3-5 mistakes students often make
}

export interface ContentJson {
    subject: RawSubjectJson['subject']
    generatedAt: string
    model: string
    lang: Lang
    totalTopics: number
    topics: GeneratedTopicContent[]
}

// ── CLI ───────────────────────────────────────────────────────────────────────

interface Args {
    subject: string
    lang: Lang
    resume: boolean
    provider: string
}

function parseArgs(): Args {
    const raw = process.argv.slice(2)
    const get = (flag: string) => { const i = raw.indexOf(flag); return i >= 0 ? raw[i + 1] : undefined }
    const has = (flag: string) => raw.includes(flag)

    const subject = get('--subject')
    if (!subject) {
        console.error('Usage: npx ts-node generateContent.ts --subject <id> [--lang hinglish] [--resume]')
        process.exit(1)
    }

    const langArg = get('--lang')
    const lang: Lang = langArg === 'hinglish' ? 'hinglish' : 'en'

    const provider = get('--provider') || 'groq'
    return { subject, lang, resume: has('--resume'), provider }
}


// ── Rate limiter ──────────────────────────────────────────────────────────────
// (now handled by aiProviders.rateLimited, but keep constants for documentation below)

/**
 * Groq Free Tier for `llama-3.3-70b-versatile` (March 2026):
 * - RPM: 30 requests/min
 * - RPD: 1,000 requests/day (daily requests limit on free tier)
 * We'll use 25 req/min (2.4s gap) to stay under the RPM — but the RPD can still be reached.
 */
const CALLS_PER_MINUTE = 25
const DELAY_MS = Math.ceil((60 * 1000) / CALLS_PER_MINUTE)  // 2400 ms gap

let lastCallTime = 0

// rateLimitedCall removed; using exported rateLimited from aiProviders

// RateLimitError is exported from aiProviders; not needed here

// ── Gemini prompts ────────────────────────────────────────────────────────────

/**
 * Grounding rules embedded directly in the prompt — not as a separate system
 * instruction (Gemini free tier doesn't support separate system role), but as
 * the very first lines the model reads, so they carry maximum weight.
 */
const GROUNDING_RULES = `
STRICT RULES — YOU MUST FOLLOW ALL OF THEM:
1. Use ONLY the text provided between the <SOURCE> tags below. Never use your training knowledge.
2. If a concept is not explicitly mentioned in the <SOURCE> text, do NOT include it. Instead write: "Not covered in this excerpt."
3. Every bullet point must be directly extractable from the <SOURCE> text — no paraphrasing from memory.
4. Do NOT add examples, formulas, definitions, or theorems that are not present in the <SOURCE> text.
5. ACT LIKE A DIRECT, AUTHORITATIVE TEACHER.
   - Speak directly to the student regarding the facts: "Matrices are rectangular arrays of numbers used to solve linear equations."
   - DO NOT refer to the NIOS curriculum, the textbook, or the excerpt.
   - DO NOT use words like "Defines", "Explains", "This chapter covers", or "The text describes".
   - Just state the academic facts natively.
`.trim()

function buildPrompt(topic: RawTopic, chapterTitle: string, lang: Lang): string {
    const langInstruction = lang === 'hinglish'
        ? 'Write the JSON values in Hinglish (Hindi written in English script, e.g. "Is topic mein hum dekhenge ki..."). Keep math/technical terms in English.'
        : 'Write the JSON values in simple English suitable for a Class 12 student.'

    // Truncate to 4000 chars to give model more context (vs 3000 before)
    const sourceText = topic.rawText.length > 4000
        ? topic.rawText.slice(0, 4000) + '\n[...text continues, use only what is above]'
        : topic.rawText

    return `You are a strict, expert Class 12 teacher for NIOS students.
Your job is to read the textbook excerpt below and generate bite-sized, direct study notes for your students.
Speak directly to the student like a tutor. DO NOT talk about the excerpt itself.

${GROUNDING_RULES}

Chapter: ${chapterTitle}
Topic: ${topic.title}
Language: ${langInstruction}

<SOURCE>
${sourceText}
</SOURCE>

Now produce ONLY this JSON (no markdown, no extra text):
{
  "summaryBullets": [
    "8-12 bullet points — each one stating a pure, direct academic fact from the <SOURCE>",
    "Use direct tone. Bad: 'The text defines sets as collections'. Good: 'A set is a well-defined collection of objects.'",
    "DO NOT use words like 'Defines', 'Explains', or 'Covers'.",
    "If fewer than 8 distinct points exist in <SOURCE>, write fewer — do not pad with outside knowledge"
  ],
  "whyImportant": "1-2 sentences explaining why this specific concept matters mathematically or in daily life. Do NOT end with 'making it a relevant topic for students' or 'it is included in the curriculum'. Speak directly to the student's understanding! Do NOT mention 'NIOS' or 'the curriculum'. Base it ONLY on the <SOURCE>.",
  "commonMistakes": [
    "3-5 mistakes — only include mistakes that a student could logically make based on what the <SOURCE> says"
  ]
}`
}



// ── Path helpers ─────────────────────────────────────────────────────────────

function rawPath(subject: string): string | null {
    // Try to find the subject's raw file by scanning content/ directories
    const base = path.resolve(__dirname, '../content')
    for (const dir of fs.readdirSync(base).filter(d => d.startsWith('class'))) {
        const candidate = path.join(base, dir, `${subject}.raw.json`)
        if (fs.existsSync(candidate)) return candidate
    }
    return null
}

function outputPath(subject: string, lang: Lang, classLevel: string): string {
    const dir = path.resolve(__dirname, `../content/class${classLevel}`)
    fs.mkdirSync(dir, { recursive: true })
    const suffix = lang === 'en' ? '' : `.${lang}`
    return path.join(dir, `${subject}${suffix}.content.json`)
}

// ── Main ─────────────────────────────────────────────────────────────────────

async function main() {
    const args = parseArgs()

    // Load raw JSON
    const rawFile = rawPath(args.subject)
    if (!rawFile) {
        console.error(`❌ Could not find ${args.subject}.raw.json. Run ingest.ts first.`)
        process.exit(1)
    }

    const raw: RawSubjectJson = JSON.parse(fs.readFileSync(rawFile, 'utf-8'))
    console.log(`\n📚 Subject: ${raw.subject.name} (${raw.subject.classLevel})`)
    console.log(`📊 ${raw.totalChapters} chapters, ${raw.totalTopics} topics`)
    console.log(`🌐 Language: ${args.lang}`)

    // Load existing output for resume mode
    const outFile = outputPath(args.subject, args.lang, raw.subject.classLevel)
    
    // create AI provider instance
    let provider: AIProvider
    try {
        provider = getProvider(args.provider)
    } catch (e) {
        console.error('❌', (e as Error).message)
        process.exit(1)
    }

    console.log(`🔧 Using AI provider: ${provider.name}`)
    let existingTopics: Record<string, GeneratedTopicContent> = {}

    if (args.resume && fs.existsSync(outFile)) {
        const existing: ContentJson = JSON.parse(fs.readFileSync(outFile, 'utf-8'))
        existingTopics = Object.fromEntries(existing.topics.map((t) => [t.topicId, t]))
        const doneCount = Object.keys(existingTopics).length
        console.log(`🔄 Resume mode: ${doneCount} topics already done`)
    }

    // provider already initialised above


    // Process all topics
    const results: GeneratedTopicContent[] = []
    let processed = 0
    let skipped = 0

    for (const [chapterIdx, chapter] of raw.chapters.entries()) {
        console.log(`\n📖 Chapter ${chapter.orderIndex}: ${chapter.title}`)

        for (const topic of chapter.topics) {
            // Skip topics with no usable content (e.g. chapters found only in TOC)
            if (topic.rawText.trim().length < 100) {
                console.log(`  ⏭️  Skipping "${topic.title}" — insufficient text (${topic.rawText.length} chars)`)
                results.push({
                    id: `tc-${topic.id}-${args.lang}`,
                    topicId: topic.id,
                    lang: args.lang,
                    summaryBullets: ['Not covered in this excerpt — this chapter may need its PDF path updated in the subject config.'],
                    whyImportant: 'Content not available in extracted text.',
                    commonMistakes: ['Check that the PDF path in scripts/subjects/ config is correct.'],
                })
                skipped++
                continue
            }

            // If resume data exists, only skip fully-generated topics.
            // If the existing entry contains a failure placeholder, retry it.
            const existingEntry = existingTopics[topic.id]
            if (existingEntry) {
                const firstBullet = Array.isArray(existingEntry.summaryBullets) ? existingEntry.summaryBullets[0] : ''
                const isFailedPlaceholder = typeof firstBullet === 'string' && firstBullet.includes('[Content generation failed')
                if (!isFailedPlaceholder) {
                    results.push(existingEntry)
                    skipped++
                    continue
                } else {
                    console.log(`  🔁 Retrying "${topic.title}" — previous attempt failed`)
                }
            }

            process.stdout.write(`  ⚙️  ${topic.title}…`)

            const prompt = buildPrompt(topic, chapter.title, args.lang)
            let generated: GeneratedOutput
            try {
                generated = await rateLimited(() => provider.generate(prompt, topic.title))
            } catch (err) {
                if (err instanceof RateLimitError) {
                    console.error(`\n⛔ Provider ${provider.name} rate limit reached — saving checkpoint and exiting.`)
                    saveOutput(outFile, raw, args.lang, results, provider.name)
                    console.error(`📄 Checkpoint saved: ${outFile}`)
                    process.exit(2)
                }
                throw err
            }

            const entry: GeneratedTopicContent = {
                id: `tc-${topic.id}-${args.lang}`,
                topicId: topic.id,
                lang: args.lang,
                ...generated,
            }

            results.push(entry)
            processed++

            // Save checkpoint after every 5 topics (crash safety)
            if (processed % 5 === 0) {
                saveOutput(outFile, raw, args.lang, results, provider.name)
                process.stdout.write(` ✅ (checkpoint saved)\n`)
            } else {
                process.stdout.write(` ✅\n`)
            }
        }
    }

    saveOutput(outFile, raw, args.lang, results, provider.name)

    console.log(`\n✅ Done! ${processed} topics generated, ${skipped} skipped (resume)`)
    console.log(`📄 Output: ${outFile}`)
    console.log('\nNext step:')
    console.log(`  npx ts-node seed.ts --subject ${args.subject} --dry-run\n`)
}

function saveOutput(
    outFile: string,
    raw: RawSubjectJson,
    lang: Lang,
    topics: GeneratedTopicContent[],
    modelName: string,
) {
    const output: ContentJson = {
        subject: raw.subject,
        generatedAt: new Date().toISOString(),
        model: modelName,
        lang,
        totalTopics: topics.length,
        topics,
    }
    fs.writeFileSync(outFile, JSON.stringify(output, null, 2), 'utf-8')
}

main().catch((err) => {
    console.error('❌ Fatal error:', err)
    process.exit(1)
})
