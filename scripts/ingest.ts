import * as fs from 'fs'
import * as path from 'path'
import pdfParse from 'pdf-parse'

// ── Exported types (used by generateContent.ts and seed.ts) ──────────────────

export interface RawTopic {
    id: string
    orderIndex: number
    title: string
    rawText: string
}

export interface RawChapter {
    id: string
    orderIndex: number
    title: string
    topics: RawTopic[]
}

export interface RawSubjectJson {
    subject: {
        id: string
        name: string
        classLevel: string
        code: string
    }
    generatedAt: string
    totalChapters: number
    totalTopics: number
    chapters: RawChapter[]
}

/**
 * CLI Arguments:
 * --subject "maths-12"
 *
 * Reads PDFs from: content/class12/<subject>/pdfs/
 * Reads config from: scripts/subjects/<subject>.json
 * Outputs to:       content/class12/<subject>.raw.json
 */
const args = process.argv.slice(2).reduce((acc, val, i, arr) => {
    if (val.startsWith('--')) acc[val.slice(2)] = arr[i + 1]
    return acc
}, {} as Record<string, string>)

if (!args.subject) {
    console.error('Usage: npx ts-node ingest.ts --subject <subjectId>')
    process.exit(1)
}

const pdfDir = path.resolve(__dirname, `../content/class12/${args.subject}/pdfs`)
const outFile = path.resolve(__dirname, `../content/class12/${args.subject}.raw.json`)

if (!fs.existsSync(pdfDir)) {
    console.error(`Folder not found: ${pdfDir}`)
    process.exit(1)
}

async function run() {
    const files = fs.readdirSync(pdfDir).filter(f => f.endsWith('.pdf')).sort()

    // Load subject config
    const configPath = path.resolve(__dirname, `subjects/${args.subject}.json`)
    if (!fs.existsSync(configPath)) {
        console.error(`Subject config not found: ${configPath}`)
        process.exit(1)
    }
    const subjectConfig = JSON.parse(fs.readFileSync(configPath, 'utf-8'))

    const chapters: RawChapter[] = []

    console.log(`📂 Found ${files.length} Chapter PDFs in ${pdfDir}`)

    for (const [index, file] of files.entries()) {
        const orderIndex = index + 1
        const chapterId = `${args.subject}-ch${String(orderIndex).padStart(2, '0')}`
        console.log(`  📄 Processing Chapter ${orderIndex}: ${file}...`)

        const filePath = path.join(pdfDir, file)
        const pdfBuffer = fs.readFileSync(filePath)

        let text = ''
        try {
            const data = await pdfParse(pdfBuffer)
            text = data.text
        } catch (e: any) {
            console.error(`    ❌ Failed to parse ${file}: ${e.message}`)
            continue
        }

        // Clean up text
        text = text
            .replace(/\r\n/g, '\n')
            .replace(/\n([a-z])/g, ' $1')  // rejoin soft-wrapped lines
            .replace(/\s+/g, ' ')           // collapse whitespace
            .trim()

        // Derive a readable chapter title from filename
        const chapterTitle = file
            .replace('.pdf', '')
            .replace(/^\d+_/, '')   // strip leading "01_" prefix
            .replace(/_/g, ' ')
            .trim()

        // Chunk into ~2500-char "topic" blocks
        const CHUNK_SIZE = 2500
        const topics: RawTopic[] = []

        for (let i = 0, topicIndex = 1; i < text.length; i += CHUNK_SIZE, topicIndex++) {
            const rawTextChunk = text.slice(i, i + CHUNK_SIZE).trim()
            if (rawTextChunk.length < 200) continue  // skip tiny trailing chunks

            topics.push({
                id: `${chapterId}-t${String(topicIndex).padStart(2, '0')}`,
                orderIndex: topicIndex,
                title: `Part ${topicIndex}`,
                rawText: rawTextChunk,
            })
        }

        chapters.push({
            id: chapterId,
            orderIndex,
            title: chapterTitle,
            topics,
        })
    }

    const totalTopics = chapters.reduce((sum, ch) => sum + ch.topics.length, 0)

    const output: RawSubjectJson = {
        subject: {
            id: subjectConfig.id,
            name: subjectConfig.name,
            classLevel: subjectConfig.classLevel,
            code: subjectConfig.subjectCode,
        },
        generatedAt: new Date().toISOString(),
        totalChapters: chapters.length,
        totalTopics,
        chapters,
    }

    fs.writeFileSync(outFile, JSON.stringify(output, null, 2))
    console.log(`\n✅ Successfully generated ${outFile}`)
    console.log(`   📖 ${chapters.length} chapters, ${totalTopics} topics`)
}

run().catch(console.error)
