import "jsr:@supabase/functions-js/edge-runtime.d.ts"
import { serve } from "https://deno.land/std@0.168.0/http/server.ts"
import { createClient } from "https://esm.sh/@supabase/supabase-js@2"
import { GoogleGenerativeAI } from "npm:@google/generative-ai"

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
}

serve(async (req) => {
  // Handle CORS preflight
  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: corsHeaders })
  }

  try {
    const { pyq_id } = await req.json()
    if (!pyq_id) throw new Error('pyq_id is required')

    const supabaseUrl = Deno.env.get('SUPABASE_URL') ?? ''
    
    // We use the service_role key to bypass RLS and save the generated steps directly,
    // so both anonymous and regular users can trigger it securely.
    const serviceRoleKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? ''
    const supabase = createClient(supabaseUrl, serviceRoleKey)

    // Fetch the question text
    const { data: pyq, error: pyqErr } = await supabase
      .from('pyqs')
      .select('question_text')
      .eq('id', pyq_id)
      .single()
    
    if (pyqErr || !pyq) throw new Error('Could not find PYQ')

    // Fetch the target answer text
    const { data: exp, error: expErr } = await supabase
      .from('pyq_explanations')
      .select('answer')
      .eq('pyq_id', pyq_id)
      .single()
    
    if (expErr || !exp) throw new Error('Could not find pyq_explanation')

    const geminiKey = Deno.env.get('GEMINI_API_KEY') || 'AIzaSyC0VyUw3JFfxcP2BYPI6yMlxEq0XvnUZhg'
    if (!geminiKey) throw new Error('GEMINI_API_KEY is not set')

    const genAI = new GoogleGenerativeAI(geminiKey)
    const model = genAI.getGenerativeModel({ 
      model: "gemini-2.5-flash",
      generationConfig: { responseMimeType: "application/json" }
    })

    const prompt = `You are a physics tutor. Break down this question and answer:
Q: ${pyq.question_text}
A: ${exp.answer}

Return STRICTLY JSON:
{
  "steps": ["step 1 (max 1 sentence)", "step 2"],
  "hints": ["hint 1"]
}
Keep it extremely brief and concise to ensure fast generation.`

    const result = await model.generateContent(prompt)
    const text = result.response.text().replace(/```json/gi, '').replace(/```/g, '').trim()
    
    let parsed;
    try {
      parsed = JSON.parse(text)
    } catch (e) {
      throw new Error("JSON Parse Error. Raw Text: " + text)
    }

    // Save the computed steps back into the database
    const { error: updateErr } = await supabase
      .from('pyq_explanations')
      .update({
        steps: parsed.steps,
        hints: parsed.hints
      })
      .eq('pyq_id', pyq_id)

    if (updateErr) console.error("Error updating explanation:", updateErr)

    // Return the steps immediately to the client
    return new Response(
      JSON.stringify({ steps: parsed.steps, hints: parsed.hints }),
      { headers: { ...corsHeaders, 'Content-Type': 'application/json' }, status: 200 }
    )
  } catch (error) {
    return new Response(JSON.stringify({ error: error.message }), {
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      status: 400,
    })
  }
})
