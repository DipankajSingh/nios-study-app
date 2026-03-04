import { Groq } from 'groq-sdk'

export interface GeneratedOutput {
    summaryBullets: string[]
    whyImportant: string
    commonMistakes: string[]
}

export interface AIProvider {
    name: string
    generate(prompt: string, topicTitle: string): Promise<GeneratedOutput>
}

// Generic rate-limiter utility shared by providers
const CALLS_PER_MINUTE = 25
const DELAY_MS = Math.ceil((60 * 1000) / CALLS_PER_MINUTE)
let lastCallTime = 0
export async function rateLimited<T>(fn: () => Promise<T>): Promise<T> {
    const now = Date.now()
    const elapsed = now - lastCallTime
    if (elapsed < DELAY_MS) {
        const wait = DELAY_MS - elapsed
        process.stdout.write(`  ⏳ Rate limit — waiting ${(wait / 1000).toFixed(1)}s…\r`)
        await new Promise((r) => setTimeout(r, wait))
    }
    lastCallTime = Date.now()
    return fn()
}

// Custom error used by providers to signal they hit an external rate limit/day cap
export class RateLimitError extends Error {
    constructor(message?: string) {
        super(message)
        this.name = 'RateLimitError'
    }
}

// --- Providers ---------------------------------------------------------------

export class GroqProvider implements AIProvider {
    public name = 'groq'
    private client: Groq

    constructor(apiKey: string) {
        this.client = new Groq({ apiKey })
    }

    async generate(prompt: string, topicTitle: string): Promise<GeneratedOutput> {
        try {
            const result = await this.client.chat.completions.create({
                model: 'llama-3.3-70b-versatile',
                messages: [{ role: 'user', content: prompt }],
                temperature: 0.1,
                response_format: { type: 'json_object' },
            })

            const text = result.choices[0]?.message?.content?.trim() || ''
            const clean = text.replace(/^```(?:json)?\n?/i, '').replace(/\n?```$/i, '').trim()
            const parsed = JSON.parse(clean) as GeneratedOutput

            if (!Array.isArray(parsed.summaryBullets) || parsed.summaryBullets.length < 1) {
                throw new Error('summaryBullets missing or empty')
            }
            return parsed
        } catch (err: unknown) {
            const errMsg = String((err as Error).message ?? '')
            const isRateLimit = /429|Too Many Requests|Requests per day|rate limit|RPD/i.test(errMsg) || (err as any)?.status === 429
            if (isRateLimit) {
                throw new RateLimitError(errMsg)
            }
            throw err
        }
    }
}

// Factory helper
export function getProvider(name: string): AIProvider {
    switch (name.toLowerCase()) {
        case 'groq': {
            const apiKey = process.env.GROQ_API_KEY
            if (!apiKey) {
                throw new Error('GROQ_API_KEY not set in environment')
            }
            return new GroqProvider(apiKey)
        }
        default:
            throw new Error(`Unknown AI provider: ${name}`)
    }
}
