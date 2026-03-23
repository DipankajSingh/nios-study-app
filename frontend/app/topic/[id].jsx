import { useEffect, useState } from 'react';
import { useRouter, useLocalSearchParams } from 'expo-router';
import {
  ScrollView, Text, TouchableOpacity, View, ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { supabase } from '@/lib/supabase';
import MathText from '@/components/MathText';
import PyqCard from '@/components/PyqCard';

export default function TopicScreen() {
  const router = useRouter();
  const { id } = useLocalSearchParams();

  const [topic, setTopic] = useState(null);
  const [content, setContent] = useState(null);
  const [pyqs, setPyqs] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      const [topicRes, contentRes, pyqRes] = await Promise.all([
        supabase.from('topics').select('id, title, high_yield_score, est_minutes, chapter_id').eq('id', id).single(),
        supabase.from('topic_contents').select('summary_bullets, why_important').eq('topic_id', id).single(),
        supabase.from('pyqs').select('id, question_text, difficulty, year, marks, topic_id, subject_id').eq('topic_id', id).order('frequency_score', { ascending: false }).limit(10),
      ]);
      setTopic(topicRes.data);
      setContent(contentRes.data);
      setPyqs(pyqRes.data ?? []);
      setLoading(false);
    }
    load();
  }, [id]);


  if (loading) {
    return (
      <SafeAreaView style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }} className="bg-white dark:bg-slate-900">
        <ActivityIndicator color="#f97316" size="large" />
      </SafeAreaView>
    );
  }

  const bullets = content?.summary_bullets ?? [];
  const whyImportant = content?.why_important ?? '';

  return (
    <SafeAreaView style={{ flex: 1 }} className="bg-white dark:bg-slate-900">
      <ScrollView style={{ flex: 1 }} contentContainerStyle={{ paddingBottom: 60 }}>
        <View className="w-full self-center px-6" style={{ maxWidth: 700 }}>

          {/* Header */}
          <View className="pt-5 flex-row items-start gap-3">
            <TouchableOpacity onPress={() => router.back()} className="pt-1 pr-2">
              <Text className="text-brand-500 text-base">← Back</Text>
            </TouchableOpacity>
            <View style={{ flex: 1 }}>
              <Text className="text-xl font-bold text-slate-900 dark:text-white leading-snug">
                {topic?.title}
              </Text>
              <View className="flex-row items-center gap-2 mt-1">
                {topic?.high_yield_score >= 30 && (
                  <View className="bg-orange-50 border border-orange-200 rounded-full px-2 py-0.5">
                    <Text className="text-orange-500 text-xs font-semibold">🔥 High yield</Text>
                  </View>
                )}
                <Text className="text-slate-400 text-xs">⏱ {topic?.est_minutes ?? '?'} min read</Text>
              </View>
            </View>
          </View>

          {/* Summary bullets */}
          {bullets.length > 0 && (
            <View className="mt-6 bg-slate-50 dark:bg-slate-800 rounded-2xl p-5 gap-3">
              <Text className="font-semibold text-slate-900 dark:text-white text-base">📋 Summary</Text>
              <View className="gap-2">
                {bullets.map((bullet, i) => (
                  <View key={i} className="flex-row gap-2">
                    <Text className="text-brand-500 font-bold mt-0.5">•</Text>
                    <MathText text={bullet} color="#334155" fontSize={14} className="flex-1" />
                  </View>
                ))}
              </View>
            </View>
          )}

          {/* Why it matters */}
          {!!whyImportant && (
            <View className="mt-4 bg-brand-50 dark:bg-slate-800 border border-brand-100 dark:border-brand-900 rounded-2xl p-5 gap-2">
              <Text className="font-semibold text-brand-700 dark:text-brand-300 text-base">💡 Why it matters</Text>
              <MathText text={whyImportant} color="#0284c7" fontSize={14} />
            </View>
          )}

          {/* PYQs */}
          <View className="mt-6 mb-4">
            <Text className="font-semibold text-slate-700 dark:text-slate-300 text-base mb-3">
              📝 Past Year Questions {pyqs.length > 0 ? `(${pyqs.length})` : ''}
            </Text>
            {pyqs.length === 0 ? (
              <View className="bg-slate-50 dark:bg-slate-800 rounded-2xl p-5 items-center">
                <Text className="text-slate-400 text-sm">No PYQs found for this topic yet.</Text>
              </View>
            ) : (
              <View className="gap-3">
                {pyqs.map((pyq) => (
                  <PyqCard key={pyq.id} pyq={pyq} />
                ))}
              </View>
            )}
          </View>

        </View>
      </ScrollView>
    </SafeAreaView>
  );
}
