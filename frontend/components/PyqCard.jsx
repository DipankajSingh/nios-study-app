import { useState } from 'react';
import {
  View, Text, TouchableOpacity, ActivityIndicator,
} from 'react-native';
import { supabase } from '@/lib/supabase';
import MathText from '@/components/MathText';
import { useColorScheme } from '@/hooks/use-color-scheme';

const DIFFICULTY_STYLE = {
  easy:   { label: '🟢 Easy',   cls: 'bg-green-50  border-green-200  text-green-600'  },
  medium: { label: '🟡 Medium', cls: 'bg-yellow-50 border-yellow-200 text-yellow-600' },
  hard:   { label: '🔴 Hard',   cls: 'bg-red-50    border-red-200    text-red-500'    },
};

const RATING_CONFIG = [
  { key: 'hard', label: '🔴 Hard',    bg: 'bg-red-50    border-red-300',    text: 'text-red-600'    },
  { key: 'good', label: '🟡 Good',    bg: 'bg-yellow-50 border-yellow-300', text: 'text-yellow-700'  },
  { key: 'easy', label: '🟢 Easy',    bg: 'bg-green-50  border-green-300',  text: 'text-green-700'  },
];

/**
 * Shared PYQ Card component used both in:
 *   - topic/[id].jsx  (Study view)
 *   - (tabs)/pyq.jsx  (Practice Arena)
 *
 * Props:
 *   pyq       - { id, question_text, difficulty, year, marks, topic_id, subject_id }
 *   topicId   - fallback if pyq.topic_id missing
 *   subjectId - fallback if pyq.subject_id missing
 *   initialAttempt - existing attempt status ('hard'|'good'|'easy'|null) from parent query
 */
export default function PyqCard({ pyq, topicId, subjectId, initialAttempt = null }) {
  const [isOpen, setIsOpen]         = useState(false);
  const [ans, setAns]               = useState(null);
  const [generatingAI, setGenAI]    = useState(false);
  const [attempt, setAttempt]       = useState(initialAttempt);
  const [rating, setRating]         = useState(false);

  const { colorScheme } = useColorScheme();
  const isDark = colorScheme === 'dark';
  const textColor   = isDark ? '#e2e8f0' : '#0f172a'; // slate-200 / slate-900
  const mutedColor  = isDark ? '#94a3b8' : '#334155'; // slate-400 / slate-700

  const diff = DIFFICULTY_STYLE[pyq.difficulty] ?? DIFFICULTY_STYLE.medium;
  const tid  = pyq.topic_id   ?? topicId;
  const sid  = pyq.subject_id ?? subjectId;

  async function toggle() {
    const next = !isOpen;
    setIsOpen(next);
    if (next && !ans) {
      const { data } = await supabase
        .from('pyq_explanations')
        .select('answer, steps, hints')
        .eq('pyq_id', pyq.id)
        .single();
      setAns(data);
    }
  }

  async function generateSteps() {
    setGenAI(true);
    try {
      const { data, error } = await supabase.functions.invoke('generate-pyq-steps', {
        body: { pyq_id: pyq.id },
      });
      if (error) throw error;
      setAns((prev) => ({ ...prev, steps: data.steps, hints: data.hints }));
    } catch (e) {
      console.error('AI Error:', e);
    } finally {
      setGenAI(false);
    }
  }

  async function rateQuestion(r) {
    setRating(true);
    const { data: { user } } = await supabase.auth.getUser();
    if (user) {
      await supabase.from('pyq_attempts').upsert({
        user_id: user.id, pyq_id: pyq.id, topic_id: tid, subject_id: sid, rating: r,
      }, { onConflict: 'user_id,pyq_id' });
      // Also bump user_progress for SM-2
      const today = new Date();
      const intervalMap = { hard: 1, good: 4, easy: 10 };
      const reviewDate = new Date(today.getTime() + intervalMap[r] * 86400000);
      const iso = reviewDate.toISOString().split('T')[0];
      await supabase.from('user_progress').upsert({
        user_id: user.id, topic_id: tid,
        needs_urgent_review: r === 'hard',
        next_review_at: iso,
        last_studied_at: today.toISOString(),
      }, { onConflict: 'user_id,topic_id', ignoreDuplicates: false });
    }
    setAttempt(r);
    setRating(false);
  }

  const validSteps = Array.isArray(ans?.steps)
    ? ans.steps.filter((s) => typeof s === 'string' && s.trim().length > 0 && s.trim() !== ans.answer?.trim())
    : [];

  // badge shown on collapsed card
  const attemptBadge = {
    easy: { label: '✅ Mastered', cls: 'bg-green-100 text-green-700' },
    good: { label: '✔ Done',     cls: 'bg-blue-100  text-blue-700'  },
    hard: { label: '🔁 Review',  cls: 'bg-red-100   text-red-700'   },
  };

  return (
    <TouchableOpacity
      onPress={toggle}
      activeOpacity={0.85}
      className={`rounded-2xl border overflow-hidden ${
        isOpen
          ? 'border-brand-300 dark:border-brand-700'
          : 'border-slate-200 dark:border-slate-700'
      } bg-white dark:bg-slate-800`}
      style={{ shadowColor: '#000', shadowOpacity: 0.04, shadowRadius: 4, elevation: 1 }}
    >
      {/* ── Question Row ── */}
      <View className="px-5 py-4 flex-row items-start gap-3">
        <View style={{ flex: 1 }}>
          <MathText text={pyq.question_text} color={textColor} fontSize={14} />
          <View className="flex-row items-center gap-2 mt-2 flex-wrap">
            <View className={`border rounded-full px-2 py-0.5 ${diff.cls}`}>
              <Text className="text-xs font-semibold">{diff.label}</Text>
            </View>
            {pyq.year  && <Text className="text-xs text-slate-400">{pyq.year}</Text>}
            {pyq.marks && pyq.marks !== 5 && <Text className="text-xs text-slate-400">{pyq.marks} marks</Text>}
            {attempt && (
              <View className={`rounded-full px-2 py-0.5 ${attemptBadge[attempt].cls}`}>
                <Text className="text-xs font-semibold">{attemptBadge[attempt].label}</Text>
              </View>
            )}
          </View>
        </View>
        <Text className="text-slate-400 text-base pt-1">{isOpen ? '▲' : '▼'}</Text>
      </View>

      {/* ── Expanded Answer ── */}
      {isOpen && (
        <View className="px-5 pb-5 border-t border-slate-100 dark:border-slate-700">
          {!ans ? (
            <View className="pt-4 items-center"><ActivityIndicator size="small" color="#f97316" /></View>
          ) : (
            <View className="pt-4 gap-3">
              {/* Answer */}
              {ans.answer && (
                <View>
                  <Text className="text-xs font-semibold text-slate-400 uppercase tracking-widest mb-1">Answer</Text>
                  <MathText text={ans.answer} color={mutedColor} fontSize={14} />
                </View>
              )}

              {/* Steps */}
              {validSteps.length > 0 ? (
                <View>
                  <Text className="text-xs font-semibold text-slate-400 uppercase tracking-widest mb-2 mt-4">Steps</Text>
                  {validSteps.map((step, i) => (
                    <View key={i} className="flex-row gap-2 mb-1.5">
                      <View className="w-5 h-5 rounded-full bg-brand-500 items-center justify-center mt-0.5">
                        <Text className="text-white text-xs font-bold">{i + 1}</Text>
                      </View>
                      <MathText text={step} color={mutedColor} fontSize={14} className="flex-1" />
                    </View>
                  ))}
                </View>
              ) : (
                <View className="mt-4 pt-4 border-t border-slate-100 dark:border-slate-700">
                  <TouchableOpacity
                    className={`flex-row items-center justify-center gap-2 py-3 rounded-xl border ${
                      generatingAI
                        ? 'border-brand-200 bg-brand-50 opacity-70'
                        : 'border-brand-500 bg-brand-50 dark:border-brand-500 dark:bg-transparent'
                    }`}
                    onPress={generateSteps}
                    disabled={generatingAI}
                  >
                    {generatingAI
                      ? <ActivityIndicator size="small" color="#f97316" />
                      : <Text className="text-base">✨</Text>}
                    <Text className={`font-semibold ${generatingAI ? 'text-brand-400' : 'text-brand-600 dark:text-brand-400'}`}>
                      {generatingAI ? 'Generating…' : 'Generate Step-by-Step Breakdown'}
                    </Text>
                  </TouchableOpacity>
                </View>
              )}

              {/* Hints */}
              {Array.isArray(ans.hints) && ans.hints.length > 0 && (
                <View className="bg-yellow-50 dark:bg-slate-700 rounded-xl p-3">
                  <Text className="text-xs font-semibold text-yellow-600 dark:text-yellow-400 mb-1">💡 Hints</Text>
                  {ans.hints.map((h, i) => (
                    <MathText key={i} text={`• ${h}`} color={isDark ? '#fef08a' : '#a16207'} fontSize={14} className="mb-0.5" />
                  ))}
                </View>
              )}

              {/* ── Self-Rating Bar ── */}
              <View className="mt-4 pt-4 border-t border-slate-100 dark:border-slate-700">
                <Text className="text-xs font-semibold text-slate-400 uppercase tracking-widest mb-2">
                  How well did you know this?
                </Text>
                <View className="flex-row gap-2">
                  {RATING_CONFIG.map((cfg) => (
                    <TouchableOpacity
                      key={cfg.key}
                      onPress={() => rateQuestion(cfg.key)}
                      disabled={rating}
                      className={`flex-1 py-2 rounded-xl border items-center ${cfg.bg} ${
                        attempt === cfg.key ? 'opacity-100' : 'opacity-70'
                      }`}
                    >
                      {rating && attempt !== cfg.key
                        ? null
                        : <Text className={`text-xs font-bold ${cfg.text}`}>{cfg.label}</Text>}
                    </TouchableOpacity>
                  ))}
                </View>
              </View>
            </View>
          )}
        </View>
      )}
    </TouchableOpacity>
  );
}
