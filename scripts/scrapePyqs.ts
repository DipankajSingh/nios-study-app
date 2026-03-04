import * as fs from 'fs'
import * as path from 'path'
import * as stream from 'stream'
import { promisify } from 'util'
import * as cheerio from 'cheerio'

const pipeline = promisify(stream.pipeline)

/**
 * CLI Arguments:
 * --subject "maths-12"
 * --code "311"
 */
const args = process.argv.slice(2).reduce((acc, val, i, arr) => {
    if (val.startsWith('--')) acc[val.slice(2)] = arr[i + 1]
    return acc
}, {} as Record<string, string>)

if (!args.subject || !args.code) {
    console.error('Usage: npx ts-node scrapePyqs.ts --subject <subjectId> --code <code>')
    process.exit(1)
}

const outDir = path.resolve(__dirname, `../content/class12/${args.subject}/pyqs_raw`)
if (!fs.existsSync(outDir)) {
    fs.mkdirSync(outDir, { recursive: true })
}

// Known URLs where NIOS hosts recent and older academic PYQs
const pyqSources = [
    'https://www.nios.ac.in/student-information-section/question-paper-of-previous-year-examination-academic.aspx',
    // In actual production, we can append more index pages if NIOS fragments them by year
]

async function run() {
    console.log(`🔍 Searching for Subject Code '${args.code}' PYQs...`)

    const pyqLinks: { text: string, url: string, year: string, session: string }[] = []

    for (const sourceUrl of pyqSources) {
        console.log(`🌐 Fetching HTML from ${sourceUrl}...`)
        const response = await fetch(sourceUrl)
        if (!response.ok) throw new Error(`Failed to fetch: ${response.statusText}`)

        const html = await response.text()
        const $ = cheerio.load(html)

        $('a[href]').each((i, el) => {
            let href = $(el).attr('href')?.trim() || ''
            const text = $(el).text().trim()

            // Check if anchor text contains the subject code (e.g. "311 - ")
            if (href.endsWith('.pdf') && text.includes(args.code)) {
                if (href.startsWith('/')) href = 'https://www.nios.ac.in' + href

                // Try to extract year and session (April vs Oct)
                const isApril = /April|Apr/i.test(text)
                const isOct = /October|Oct/i.test(text)
                const session = isApril ? 'April' : isOct ? 'October' : 'Unknown'

                const yearMatch = text.match(/(20\d{2})/)
                const year = yearMatch ? yearMatch[1] : 'Unknown'

                // Only add if we haven't already added this exact URL
                if (!pyqLinks.some(link => link.url === href)) {
                    pyqLinks.push({ text, url: href, year, session })
                }
            }
        })
    }

    console.log(`\n📊 Found ${pyqLinks.length} Official PYQ PDFs for ${args.subject}.`)

    for (const link of pyqLinks) {
        // e.g. 2013_April.pdf
        const safeName = `${link.year}_${link.session}.pdf`
        const filePath = path.join(outDir, safeName)

        console.log(`⬇️  Downloading ${safeName} (${link.text})...`)

        try {
            const pdfRes = await fetch(link.url)
            if (!pdfRes.ok || !pdfRes.body) throw new Error(`HTTP ${pdfRes.status}`)

            // @ts-ignore
            await pipeline(pdfRes.body, fs.createWriteStream(filePath))
            console.log(`   ✅ Saved as ${safeName}`)
        } catch (err: any) {
            console.error(`   ❌ Failed to download ${link.url}: ${err.message}`)
        }
    }

    console.log(`\n🎉 All PYQ downloads complete! Files saved to ${outDir}`)
}

run().catch(console.error)
