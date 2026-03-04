#!/usr/bin/env ts-node
/**
 * scripts/generateContentBatch.ts
 *
 * NIOS AI Content Generation — Batch API version
 * ═══════════════════════════════════════════════════════════════════════════
 * Uses the Gemini Batch API (separate quota from real-time API) to process
 * all topics for a subject at once. Target: 29 maths topics in one job.
 *
 * Two-phase workflow:
 *   Phase 1 (submit):  Sends all topics to the Batch API, saves job name to
 *                      a .batch-job.json checkpoint file.
 *
 *   Phase 2 (collect): Polls the batch job status and when done, converts
 *                      the results to the same .content.json format that the
 *                      rest of the pipeline expects.
 *
 * Usage:
 *   node -r ts-node/register generateContentBatch.ts --subject maths-12
 *   node -r ts-node/register generateContentBatch.ts --subject maths-12 --collect
 *
 * Needs:
 *   .env with GEMINI_API_KEY=...
 *
 * Output:
 *   content/class{N}/{subjectId}.content.json
 */

import fs from 'fs'
import path from 'path'
import dotenv from 'dotenv'
import { GoogleGenAI } from '@google/genai'
import type { RawSubjectJson, RawTopic, RawChapter } from './ingest'
import type { GeneratedTopicContent, ContentJson } from './generateContent'

dotenv.config()

// ── Types ─────────────────────────────────────────────────────────────────────

type Lang = 'en' | 'hinglish'

interface BatchJobCheckpoint {
    jobName: string
    subjectId: string
    classLevel: string
    lang: Lang
    model: string
    submittedAt: string
    topicCount: number
    topicIds: string[]        // in order — we use this to map results back
}

// ── CLI ───────────────────────────────────────────────────────────────────────

interface Args {
    subject: string
    lang: Lang
    collect: boolean
}

function parseArgs(): Args {
    const raw = process.argv.slice(2)
    const get = (f: string) => { const i = raw.indexOf(f); return i >= 0 ? raw[i + 1] : undefined }
    const has = (f: string) => raw.includes(f)

    const subject = get('--subject')
    if (!subject) {
        console.error(`
Usage:
  node -r ts-node/register generateContentBatch.ts --subject maths-12
  node -r ts-node/register generateContentBatch.ts --subject maths-12 --collect
  node -r ts-node/register generateContentBatch.ts --subject maths-12 --lang hinglish
`)
        process.exit(1)
    }

    const langArg = get('--lang')
    return { subject, lang: langArg === 'hinglish' ? 'hinglish' : 'en', collect: has('--collect') }
}

// ── Prompt builder ────────────────────────────────────────────────────────────

const GROUNDING_RULES = `
STRICT RULES — YOU MUST FOLLOW ALL OF THEM:
1. Use ONLY the text provided between the <SOURCE> tags below. Never use your training knowledge.
2. If a concept is not explicitly mentioned in the <SOURCE> text, do NOT include it. Instead write: "Not covered in this excerpt."
3. Every bullet point must be directly extractable from the <SOURCE> text — no paraphrasing from memory.
4. Do NOT add examples, formulas, definitions, or theorems that are not present in the <SOURCE> text.
5. Before writing your answer, mentally verify: "Does the <SOURCE> text actually say this?" If unsure, omit it.
`.trim()

function buildPrompt(topic: RawTopic, chapterTitle: string, lang: Lang): string {
    const langInstruction = lang === 'hinglish'
        ? 'Write the JSON values in Hinglish (Hindi written in English script, e.g. "Is topic mein hum dekhenge ki..."). Keep math/technical terms in English.'
        : 'Write the JSON values in simple English suitable for a Class 12 student.'

    const sourceText = topic.rawText.length > 4000
        ? topic.rawText.slice(0, 4000) + '\n[...text continues, use only what is above]'
        : topic.rawText

    return `You are a study-note extractor for NIOS (National Institute of Open Schooling) India.
Your ONLY job is to extract and reformat information from the official NIOS textbook excerpt below.

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
    "8-12 bullet points — each one a key point DIRECTLY from the <SOURCE> text",
    "Start each bullet with an action word like: Defines, States, Explains, Shows, Lists",
    "If fewer than 8 distinct points exist in <SOURCE>, write fewer — do not pad with outside knowledge"
  ],
  "whyImportant": "1-2 sentences explaining exam relevance — base this ONLY on what the <SOURCE> covers, not general knowledge",
  "commonMistakes": [
    "3-5 mistakes — only include mistakes that a student could logically make based on what the <SOURCE> says"
  ]
}`
}


// ── File helpers ──────────────────────────────────────────────────────────────

function findRawFile(subject: string): string | null {
    const base = path.resolve(__dirname, '../content')
    if (!fs.existsSync(base)) return null
    for (const dir of fs.readdirSync(base).filter(d => d.startsWith('class'))) {
        const candidate = path.join(base, dir, `${subject}.raw.json`)
        if (fs.existsSync(candidate)) return candidate
    }
    return null
}

function contentOutputPath(subject: string, lang: Lang, classLevel: string): string {
    const dir = path.resolve(__dirname, `../content/class${classLevel}`)
    fs.mkdirSync(dir, { recursive: true })
    const suffix = lang === 'en' ? '' : `.${lang}`
    return path.join(dir, `${subject}${suffix}.content.json`)
}

function checkpointPath(subject: string, lang: Lang): string {
    const dir = path.resolve(__dirname, '../content')
    fs.mkdirSync(dir, { recursive: true })
    const suffix = lang === 'en' ? '' : `.${lang}`
    return path.join(dir, `${subject}${suffix}.batch-job.json`)
}

// ── Phase 1: Submit batch job ─────────────────────────────────────────────────

async function submitBatch(args: Args, raw: RawSubjectJson, ai: GoogleGenAI) {
    console.log(`\n📤 Submitting batch job for ${raw.subject.name} (${raw.totalTopics} topics)…`)

    // Build one inline request per topic
    const inlineRequests: { contents: { parts: { text: string }[]; role: string }[] }[] = []
    const topicIds: string[] = []

    for (const chapter of raw.chapters) {
        for (const topic of chapter.topics) {
            const prompt = buildPrompt(topic, chapter.title, args.lang)
            inlineRequests.push({
                contents: [{ parts: [{ text: prompt }], role: 'user' }],
            })
            topicIds.push(topic.id)
        }
    }

    console.log(`   📋 ${inlineRequests.length} requests ready`)

    // Use gemini-2.0-flash-lite for batch (has separate quota)
    const model = 'gemini-2.0-flash-lite'

    const batchJob = await ai.batches.create({
        model,
        src: inlineRequests,
        config: {
            displayName: `nios-${args.subject}-${args.lang}-${Date.now()}`,
        },
    })

    const checkpoint: BatchJobCheckpoint = {
        jobName: batchJob.name ?? '',
        subjectId: args.subject,
        classLevel: raw.subject.classLevel,
        lang: args.lang,
        model,
        submittedAt: new Date().toISOString(),
        topicCount: inlineRequests.length,
        topicIds,
    }

    const cpFile = checkpointPath(args.subject, args.lang)
    fs.writeFileSync(cpFile, JSON.stringify(checkpoint, null, 2))

    console.log(`\n✅ Batch job submitted!`)
    console.log(`   Job name: ${batchJob.name}`)
    console.log(`   Topics: ${inlineRequests.length}`)
    console.log(`   Checkpoint: ${cpFile}`)
    console.log('\n⏳ The batch job will complete in minutes to hours.')
    console.log('   Run with --collect to check status and save results:\n')
    console.log(`   node -r ts-node/register generateContentBatch.ts --subject ${args.subject} --collect\n`)
}

// ── Phase 2: Collect results ──────────────────────────────────────────────────

async function collectResults(args: Args, raw: RawSubjectJson, ai: GoogleGenAI) {
    const cpFile = checkpointPath(args.subject, args.lang)
    if (!fs.existsSync(cpFile)) {
        console.error(`❌ No batch job checkpoint found at ${cpFile}`)
        console.error('   Run without --collect first to submit a job.')
        process.exit(1)
    }

    const cp: BatchJobCheckpoint = JSON.parse(fs.readFileSync(cpFile, 'utf-8'))
    console.log(`\n🔍 Checking batch job: ${cp.jobName}`)
    console.log(`   Submitted: ${cp.submittedAt}`)
    console.log(`   Topics: ${cp.topicCount}`)

    const job = await ai.batches.get({ name: cp.jobName })
    const state = job.state ?? 'UNKNOWN'

    console.log(`   State: ${state}`)

    if (state === 'JOB_STATE_PENDING' || state === 'JOB_STATE_RUNNING') {
        console.log('\n⏳ Job is still processing. Run --collect again in a few minutes.\n')
        return
    }

    if (state === 'JOB_STATE_FAILED') {
        console.error('\n❌ Batch job failed:', JSON.stringify(job, null, 2).slice(0, 500))
        process.exit(1)
    }

    if (state === 'JOB_STATE_SUCCEEDED') {
        console.log('\n✅ Job completed! Parsing results…')

        // Build a topic map for quick lookup
        const topicMap = new Map<string, { chapter: RawChapter; topic: RawTopic }>()
        for (const chapter of raw.chapters) {
            for (const topic of chapter.topics) {
                topicMap.set(topic.id, { chapter, topic })
            }
        }

        const results: GeneratedTopicContent[] = []

        // The responses array mirrors the request order
        const responses = (job as unknown as { responses?: unknown[] }).responses ?? []

        for (let i = 0; i < cp.topicIds.length; i++) {
            const topicId = cp.topicIds[i]
            const response = responses[i] as {
                response?: {
                    candidates?: Array<{
                        content?: { parts?: Array<{ text?: string }> }
                    }>
                }
            } | undefined

            const rawText = response?.response?.candidates?.[0]?.content?.parts?.[0]?.text ?? ''
            const clean = rawText.replace(/^```(?:json)?\n?/i, '').replace(/\n?```$/i, '').trim()

            let parsed: { summaryBullets: string[]; whyImportant: string; commonMistakes: string[] }
            try {
                parsed = JSON.parse(clean)
                if (!Array.isArray(parsed.summaryBullets) || parsed.summaryBullets.length < 2) throw new Error('invalid')
            } catch {
                console.warn(`  ⚠️  Could not parse response for topic ${topicId} — using placeholder`)
                parsed = {
                    summaryBullets: ['[Content generation failed — re-run batch to retry]'],
                    whyImportant: 'Content could not be parsed.',
                    commonMistakes: ['[Not generated]'],
                }
            }

            results.push({
                id: `tc-${topicId}-${args.lang}`,
                topicId,
                lang: args.lang,
                ...parsed,
            })

            const info = topicMap.get(topicId)
            process.stdout.write(`  ✅ ${info?.topic.title ?? topicId}\n`)
        }

        const outFile = contentOutputPath(args.subject, args.lang, cp.classLevel)
        const output: ContentJson = {
            subject: raw.subject,
            generatedAt: new Date().toISOString(),
            model: cp.model,
            lang: args.lang,
            totalTopics: results.length,
            topics: results,
        }
        fs.writeFileSync(outFile, JSON.stringify(output, null, 2))

        console.log(`\n✅ ${results.length} topics saved to: ${outFile}`)
        console.log('\nNext step:')
        console.log(`  node -r ts-node/register seed.ts --subject ${args.subject} --dry-run\n`)

        // Clean up checkpoint
        fs.unlinkSync(cpFile)
        console.log(`🗑️  Checkpoint removed: ${cpFile}`)
    }
}

// ── Main ─────────────────────────────────────────────────────────────────────

async function main() {
    const args = parseArgs()

    const apiKey = process.env.GEMINI_API_KEY
    if (!apiKey || apiKey === 'your_gemini_api_key_here') {
        console.error('❌ Missing GEMINI_API_KEY in scripts/.env')
        process.exit(1)
    }

    const rawFile = findRawFile(args.subject)
    if (!rawFile) {
        console.error(`❌ Could not find ${args.subject}.raw.json — run ingest.ts first`)
        process.exit(1)
    }

    const raw: RawSubjectJson = JSON.parse(fs.readFileSync(rawFile, 'utf-8'))
    console.log(`\n📚 ${raw.subject.name} | Class ${raw.subject.classLevel} | ${raw.totalTopics} topics | lang: ${args.collect ? 'collecting' : args.lang}`)

    const ai = new GoogleGenAI({ apiKey })

    if (args.collect) {
        await collectResults(args, raw, ai)
    } else {
        await submitBatch(args, raw, ai)
    }
}

main().catch(err => {
    console.error('❌ Fatal:', err.message ?? err)
    process.exit(1)
})
