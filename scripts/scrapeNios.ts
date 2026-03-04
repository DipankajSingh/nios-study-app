import * as fs from 'fs'
import * as path from 'path'
import * as stream from 'stream'
import { promisify } from 'util'
import * as cheerio from 'cheerio'

const pipeline = promisify(stream.pipeline)

/**
 * CLI Arguments:
 * --url "https://www.nios.ac.in/..."
 * --subject "maths-12"
 */
const args = process.argv.slice(2).reduce((acc, val, i, arr) => {
    if (val.startsWith('--')) acc[val.slice(2)] = arr[i + 1]
    return acc
}, {} as Record<string, string>)

if (!args.url || !args.subject) {
    console.error('Usage: npx ts-node scrapeNios.ts --url <URL> --subject <subjectId>')
    process.exit(1)
}

const outDir = path.resolve(__dirname, `../content/class12/${args.subject}/pdfs`)
if (!fs.existsSync(outDir)) {
    fs.mkdirSync(outDir, { recursive: true })
}

async function run() {
    console.log(`🌐 Fetching HTML from ${args.url}...`)
    const response = await fetch(args.url)
    if (!response.ok) throw new Error(`Failed to fetch: ${response.statusText}`)

    const html = await response.text()
    const $ = cheerio.load(html)

    const pdfLinks: { text: string, url: string, rawFilename: string }[] = []

    $('a[href]').each((i, el) => {
        let href = $(el).attr('href')?.trim() || ''
        const text = $(el).text().trim().replace(/[^a-zA-Z0-9 -]/g, '')

        // Match only English Lesson PDFs for now
        if (href.toLowerCase().includes('lesson') && href.endsWith('.pdf') && href.includes('Eng')) {
            // Some links might be relative
            if (href.startsWith('/')) {
                href = 'https://www.nios.ac.in' + href
            }

            // Extract the original filename
            const rawFilename = href.split('/').pop() || `Lesson_${i}.pdf`

            // Deduplicate (some pages have multiple links to the same PDF)
            if (!pdfLinks.some(link => link.rawFilename === rawFilename)) {
                pdfLinks.push({ text, url: href, rawFilename })
            }
        }
    })

    console.log(`\n📊 Found ${pdfLinks.length} unique English Chapter PDFs.`)

    for (const [index, link] of pdfLinks.entries()) {
        // Pad the index to 2 digits for numerical sorting (e.g. 01_Lesson.pdf)
        const orderNum = (index + 1).toString().padStart(2, '0')
        // Clean the filename so it is easy to ingest
        const safeName = link.rawFilename.replace(/[^a-zA-Z0-9_\.]/g, '')
        const finalFilename = `${orderNum}_${safeName}`
        const filePath = path.join(outDir, finalFilename)

        console.log(`⬇️  Downloading ${orderNum}/${pdfLinks.length}: ${link.text}...`)

        try {
            const pdfRes = await fetch(link.url)
            if (!pdfRes.ok || !pdfRes.body) throw new Error(`HTTP ${pdfRes.status}`)

            // @ts-ignore - native fetch Web Stream to Node Stream conversion
            await pipeline(pdfRes.body, fs.createWriteStream(filePath))
            console.log(`   ✅ Saved as ${finalFilename}`)
        } catch (err: any) {
            console.error(`   ❌ Failed to download ${link.url}: ${err.message}`)
        }
    }

    console.log(`\n🎉 All downloads complete! Files saved to ${outDir}`)
}

run().catch(console.error)
