import { useEffect, useState } from 'react';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { ActivityIndicator, Text, TouchableOpacity, View, ScrollView } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { supabase } from '@/lib/supabase';

export default function BaselineScreen() {
  const router = useRouter();
  const { subjectIds } = useLocalSearchParams();

  const [questions, setQuestions] = useState([]);
  const [current, setCurrent] = useState(0);
  const [scores, setScores] = useState({});
  const [loading, setLoading] = useState(true);
  const [selectedAnswer, setSelectedAnswer] = useState(null);
  const [revealed, setRevealed] = useState(false);

  useEffect(() => {
    async function fetchBaseline() {
      const parsed = JSON.parse(subjectIds);
      const requests = parsed.map((sid) =>
        supabase
          .from('pyqs')
          .select('id, subject_id, question_text, difficulty')
          .eq('subject_id', sid)
          .limit(3)
      );
      const results = await Promise.all(requests);
      const all = results.flatMap((r) => r.data ?? []);
      setQuestions(all);
      setLoading(false);
    }
    fetchBaseline();
  }, []);

  async function finish() {
    const { data: { user } } = await supabase.auth.getUser();
    if (user) {
      const insertRows = Object.entries(scores).map(([subject_id, { correct, total }]) => ({
        user_id: user.id,
        subject_id,
        score_percent: Math.round((correct / total) * 100),
      }));
      if (insertRows.length > 0) {
        await supabase.from('baseline_results').insert(insertRows);
      }
      await supabase.from('user_profiles').update({ baseline_completed: true }).eq('id', user.id);
    }
    router.replace('/(tabs)/home');
  }

  if (loading) {
    return (
      <SafeAreaView style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }} className="bg-white dark:bg-slate-900">
        <ActivityIndicator color="#f97316" size="large" />
      </SafeAreaView>
    );
  }

  if (questions.length === 0 || current >= questions.length) {
    finish();
    return null;
  }

  const q = questions[current];
  const totalQ = questions.length;

  function handleAnswer(answer) {
    setSelectedAnswer(answer);
    setRevealed(true);
    setScores((prev) => {
      const prev_sub = prev[q.subject_id] ?? { correct: 0, total: 0 };
      return { ...prev, [q.subject_id]: { correct: prev_sub.correct, total: prev_sub.total + 1 } };
    });
  }

  function next() {
    setSelectedAnswer(null);
    setRevealed(false);
    if (current + 1 >= totalQ) {
      finish();
    } else {
      setCurrent((c) => c + 1);
    }
  }

  return (
    <SafeAreaView style={{ flex: 1 }} className="bg-white dark:bg-slate-900">
      <View className="w-full self-center flex-1" style={{ maxWidth: 600 }}>

        {/* Header */}
        <View className="px-6 pt-6 flex-row items-center justify-between">
          <View>
            <Text className="text-xs text-slate-400 uppercase tracking-widest">Baseline Quiz</Text>
            <Text className="text-lg font-bold text-slate-900 dark:text-white">Question {current + 1} / {totalQ}</Text>
          </View>
          <TouchableOpacity onPress={finish}>
            <Text className="text-brand-500 text-sm font-semibold">Skip all →</Text>
          </TouchableOpacity>
        </View>

        {/* Progress bar */}
        <View className="mx-6 mt-3 h-1.5 rounded-full bg-slate-200 dark:bg-slate-700">
          <View
            className="h-1.5 rounded-full bg-brand-500"
            style={{ width: `${((current + 1) / totalQ) * 100}%` }}
          />
        </View>

        {/* Question */}
        <ScrollView style={{ flex: 1 }} contentContainerStyle={{ padding: 24, gap: 16 }}>
          <View className="bg-slate-50 dark:bg-slate-800 rounded-2xl p-5">
            <Text className="text-base text-slate-900 dark:text-white leading-6">{q.question_text}</Text>
          </View>

          {!revealed && (
            <View className="gap-3">
              <Text className="text-slate-500 dark:text-slate-400 text-sm text-center">
                Read the question carefully. How well do you know this?
              </Text>
              {['I know this well ✓', 'Partially familiar ~', "I don't know ✗"].map((opt, i) => (
                <TouchableOpacity
                  key={i}
                  className={`border-2 rounded-2xl py-4 px-5 ${
                    i === 0 ? 'border-green-400' : i === 1 ? 'border-yellow-400' : 'border-red-400'
                  }`}
                  onPress={() => handleAnswer(opt)}
                >
                  <Text className="text-slate-900 dark:text-white font-semibold text-center">{opt}</Text>
                </TouchableOpacity>
              ))}
            </View>
          )}

          {revealed && (
            <View className="items-center gap-4">
              <Text className="text-slate-500 dark:text-slate-400">Response recorded!</Text>
              <TouchableOpacity className="bg-brand-500 rounded-2xl py-4 px-10 active:opacity-80" onPress={next}>
                <Text className="text-white font-semibold">{current + 1 >= totalQ ? 'Finish →' : 'Next →'}</Text>
              </TouchableOpacity>
            </View>
          )}
        </ScrollView>

      </View>
    </SafeAreaView>
  );
}
