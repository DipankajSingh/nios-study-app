import * as fs from 'fs'
import * as path from 'path'
import pdfParse from 'pdf-parse'
import Groq from 'groq-sdk'
require('dotenv').config()

/**
 * CLI Arguments:
 * --subject "maths-12"
 */
const args = process.argv.slice(2).reduce((acc, val, i, arr) => {
    if (val.startsWith('--')) acc[val.slice(2)] = arr[i + 1]
    return acc
}, {} as Record<string, string>)

if (!args.subject) {
    console.error('Usage: npx ts-node ingestPyqs.ts --subject <subjectId>')
    process.exit(1)
}

const pyqsDir = path.resolve(__dirname, `../content/class12/${args.subject}/pyqs_raw`)
const outFile = path.resolve(__dirname, `../content/class12/${args.subject}.pyqs.json`)
const groq = new Groq({ apiKey: process.env.GROQ_API_KEY })

if (!fs.existsSync(pyqsDir)) {
    console.error(`Folder not found: ${pyqsDir}. Please run scrapePyqs.ts first.`)
    process.exit(1)
}

/**
 * Extracts and solves questions from the raw messy PDF text.
 */
async function extractAndSolve(rawText: string, year: string, session: string): Promise<any[]> {
    const prompt = `
You are an expert transcriber and mathematics tutor. The following text from <RAW_PDF> is a messy PDF extraction of a Class 12 Previous Year Question Paper. It contains a mix of garbled Hindi fonts and English, as well as broken equations.

Your task is to:
1. Identify up to 10 actual mathematics questions (ignore instructions).
2. Clean up the text of each question into readable English.
3. Provide a step-by-step mathematical explanation/solution for each.
4. Provide the final answer.

Output strictly as a JSON object with a single "questions" array containing objects. Example format:
{
  "questions": [
    {
      "year": "${year}",
      "session": "${session}",
      "questionText": "Find the derivative of x^2 + 2x",
      "hints": ["Use the power rule.", "Derivative of a sum is sum of derivatives."],
      "steps": ["d/dx(x^2) = 2x", "d/dx(2x) = 2", "Add them: 2x + 2"],
      "finalAnswer": "2x + 2"
    }
  ]
}

DO NOT include any Markdown formatting like \`\`\`json. Output ONLY the raw JSON object.

<RAW_PDF_TEXT>
${rawText.slice(0, 15000)}
</RAW_PDF_TEXT>
`.trim()

    try {
        const response = await groq.chat.completions.create({
            model: 'llama-3.3-70b-versatile',
            messages: [{ role: 'user', content: prompt }],
            temperature: 0.1,
            response_format: { type: 'json_object' }
        })

        const content = response.choices[0]?.message?.content || '{ "questions": [] }'
        const parsed = JSON.parse(content)
        return parsed.questions || []
    } catch (err: any) {
        console.error(`  Groq API Error: ${err.message}`)
        return []
    }
}

async function run() {
    const files = fs.readdirSync(pyqsDir).filter(f => f.endsWith('.pdf')).sort()
    const pyqsDatabase: any[] = []

    console.log(`📂 Found ${files.length} Official PYQ PDFs in ${pyqsDir}`)

    for (const file of files) {
        // Filename format: 2015_April.pdf
        const [year, sessionRaw] = file.replace('.pdf', '').split('_')
        const session = sessionRaw === 'April' ? 'March' : 'October'

        console.log(`\n  📄 Processing PYQ: ${year} ${session}...`)

        const filePath = path.join(pyqsDir, file)
        const pdfBuffer = fs.readFileSync(filePath)

        let rawText = ''
        try {
            const data = await pdfParse(pdfBuffer)
            // Clean up horrific OCR/Font mojibake from Hindi sections by keeping mostly ASCII
            rawText = data.text.replace(/\\r\\n/g, '\\n').replace(/[^a-zA-Z0-9 \\n\\.\\(\\)\\=\\+\\-\\/\\*\\^]/g, ' ')
        } catch (e: any) {
            console.error(`    ❌ Failed to parse ${file}: ${e.message}`)
            continue
        }

        console.log(`    🧠 Sending to Groq AI for extraction and solving...`)
        const extractedQuestions = await extractAndSolve(rawText, year, session)

        if (extractedQuestions.length > 0) {
            pyqsDatabase.push(...extractedQuestions)
            console.log(`    ✅ Extracted and solved ${extractedQuestions.length} questions.`)
        } else {
            console.log(`    ⚠️  No questions extracted (Possible rate limit or parsing failure).`)
        }
    }

    fs.writeFileSync(outFile, JSON.stringify(pyqsDatabase, null, 2))
    console.log(`\n🎉 Successfully generated ${outFile} with ${pyqsDatabase.length} absolute PYQs!`)
}

run().catch(console.error)
