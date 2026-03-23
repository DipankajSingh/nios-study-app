import { useEffect, useState } from 'react';
import { useRouter, useLocalSearchParams } from 'expo-router';
import {
  ScrollView, Text, TouchableOpacity, View, ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { supabase } from '@/lib/supabase';

// Limit by target score
const TARGET_LIMITS = { pass: 30, '75': 100, '90': null }; // null = all

// Labels for the inline picker for anonymous users
const TARGET_OPTIONS = [
  { label: '✅ Just Pass', value: 'pass' },
  { label: '🎯 75%', value: '75' },
  { label: '🏆 90%+', value: '90' },
];

export default function SubjectScreen() {
  const router = useRouter();
  const { id } = useLocalSearchParams();

  const [subject, setSubject] = useState(null);
  const [topics, setTopics] = useState([]);
  const [loading, setLoading] = useState(true);
  const [target, setTarget] = useState(null); // null = loading from profile

  useEffect(() => {
    async function load() {
      // 1. Fetch subject info
      const { data: subjectData } = await supabase
        .from('subjects')
        .select('id, name, icon, class_level')
        .eq('id', id)
        .single();
      setSubject(subjectData);

      // 2. Get user's exam_target (if logged in, else from AsyncStorage)
      const { data: { user } } = await supabase.auth.getUser();
      let userTarget = 'pass'; // default
      if (user) {
        const { data: profile } = await supabase
          .from('user_profiles')
          .select('exam_target')
          .eq('id', user.id)
          .single();
        userTarget = profile?.exam_target ?? 'pass';
      } else {
        userTarget = (await AsyncStorage.getItem('anon_exam_target')) ?? 'pass';
      }
      setTarget(userTarget);
      await fetchTopics(id, userTarget);
    }
    load();
  }, [id]);

  async function fetchTopics(subjectId, examTarget) {
    setLoading(true);
    const limit = TARGET_LIMITS[examTarget];

    // 3. Get the chapter for this subject (one chapter per subject in our schema)
    const { data: chapters } = await supabase
      .from('chapters')
      .select('id')
      .eq('subject_id', subjectId);
    const chapterIds = (chapters ?? []).map((c) => c.id);
    if (chapterIds.length === 0) { setTopics([]); setLoading(false); return; }

    // 4. Fetch top-N topics ordered by high_yield_score DESC
    let query = supabase
      .from('topics')
      .select('id, title, high_yield_score, est_minutes, prerequisite_search_terms')
      .in('chapter_id', chapterIds)
      .order('high_yield_score', { ascending: false });
    if (limit !== null) query = query.limit(limit);
    const { data: topTopics } = await query;
    const topSet = new Set((topTopics ?? []).map((t) => t.id));

    // 5. Collect all prerequisite search terms from the selected topics
    const allPrereqTerms = [];
    for (const topic of (topTopics ?? [])) {
      const terms = topic.prerequisite_search_terms ?? [];
      for (const term of terms) {
        if (term && term.length > 2) allPrereqTerms.push(term.toLowerCase().trim());
      }
    }

    // 6. Fetch additional prerequisite topics by title match (within same subject)
    let prereqTopics = [];
    if (allPrereqTerms.length > 0) {
      // Use ilike on title for each unique term
      const uniqueTerms = [...new Set(allPrereqTerms)];
      // Build OR filter: title.ilike.%term%,...
      const orFilter = uniqueTerms.map((t) => `title.ilike.%${t}%`).join(',');
      const { data: matched } = await supabase
        .from('topics')
        .select('id, title, high_yield_score, est_minutes, prerequisite_search_terms')
        .in('chapter_id', chapterIds)
        .or(orFilter)
        .limit(50);
      prereqTopics = (matched ?? []).filter((t) => !topSet.has(t.id));
    }

    // 7. Merge: top topics first (sorted by score), then prereqs tagged
    const merged = [
      ...(topTopics ?? []),
      ...prereqTopics.map((t) => ({ ...t, _isPrereq: true })),
    ];
    setTopics(merged);
    setLoading(false);
  }

  function handleTargetChange(newTarget) {
    setTarget(newTarget);
    fetchTopics(id, newTarget);
  }

  const difficultyColor = (score) => {
    if (score >= 30) return 'bg-red-50 text-red-500 border-red-200';
    if (score >= 15) return 'bg-yellow-50 text-yellow-600 border-yellow-200';
    return 'bg-green-50 text-green-600 border-green-200';
  };

  return (
    <SafeAreaView style={{ flex: 1 }} className="bg-white dark:bg-slate-900">
      <ScrollView style={{ flex: 1 }} contentContainerStyle={{ paddingBottom: 40 }}>
        <View className="w-full self-center px-6" style={{ maxWidth: 700 }}>

          {/* Header */}
          <View className="pt-5 flex-row items-center gap-3">
            <TouchableOpacity onPress={() => router.back()} className="py-1 pr-2">
              <Text className="text-brand-500 text-base">← Back</Text>
            </TouchableOpacity>
            {subject && (
              <View style={{ flex: 1 }}>
                <Text className="text-xl font-bold text-slate-900 dark:text-white">
                  {subject.icon} {subject.name}
                </Text>
                <Text className="text-slate-400 text-xs">Class {subject.class_level}</Text>
              </View>
            )}
          </View>

          {/* Target picker */}
          <View className="mt-5 mb-1">
            <Text className="text-xs font-semibold text-slate-400 uppercase tracking-widest mb-2">Your Target</Text>
            <View className="flex-row gap-2 flex-wrap">
              {TARGET_OPTIONS.map((opt) => {
                const isSelected = target === opt.value;
                return (
                  <TouchableOpacity
                    key={opt.value}
                    onPress={() => handleTargetChange(opt.value)}
                    className={`rounded-xl border px-3 py-2 ${isSelected ? 'bg-brand-500 border-brand-500' : 'border-slate-200 dark:border-slate-700'}`}
                  >
                    <Text className={`text-sm font-semibold ${isSelected ? 'text-white' : 'text-slate-600 dark:text-slate-300'}`}>
                      {opt.label}
                    </Text>
                  </TouchableOpacity>
                );
              })}
            </View>
            {target && (
              <Text className="text-xs text-slate-400 mt-2">
                {target === 'pass'
                  ? `Showing top 30 topics · prerequisite topics included`
                  : target === '75'
                  ? `Showing top 100 topics · prerequisite topics included`
                  : `Showing all topics`}
              </Text>
            )}
          </View>

          {/* Topic list */}
          {loading ? (
            <View style={{ paddingTop: 60, alignItems: 'center' }}>
              <ActivityIndicator color="#f97316" size="large" />
            </View>
          ) : topics.length === 0 ? (
            <View className="bg-slate-50 dark:bg-slate-800 rounded-2xl p-6 items-center mt-4">
              <Text className="text-slate-400 text-center">No topics found.</Text>
            </View>
          ) : (
            <View className="gap-3 mt-4">
              {/* Prereq section header if any */}
              {topics.some((t) => t._isPrereq) && (
                <View>
                  <Text className="text-xs font-semibold text-slate-400 uppercase tracking-widest mb-2">
                    📌 {topics.filter((t) => !t._isPrereq).length} Key Topics
                  </Text>
                </View>
              )}
              {topics.filter((t) => !t._isPrereq).map((topic) => (
                <TopicCard key={topic.id} topic={topic} router={router} difficultyColor={difficultyColor} />
              ))}

              {topics.some((t) => t._isPrereq) && (
                <Text className="text-xs font-semibold text-slate-400 uppercase tracking-widest mt-2 mb-1">
                  🔗 Prerequisite Topics
                </Text>
              )}
              {topics.filter((t) => t._isPrereq).map((topic) => (
                <TopicCard key={topic.id} topic={topic} router={router} difficultyColor={difficultyColor} isPrereq />
              ))}
            </View>
          )}

        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

function TopicCard({ topic, router, difficultyColor, isPrereq = false }) {
  return (
    <TouchableOpacity
      onPress={() => router.push(`/topic/${topic.id}`)}
      className={`rounded-2xl px-5 py-4 flex-row items-center justify-between ${
        isPrereq
          ? 'bg-slate-50 dark:bg-slate-800 border border-dashed border-slate-300 dark:border-slate-600'
          : 'bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700'
      }`}
      style={{ shadowColor: '#000', shadowOpacity: 0.04, shadowRadius: 4, elevation: 1 }}
    >
      <View style={{ flex: 1, marginRight: 12 }}>
        <Text className="text-base font-semibold text-slate-900 dark:text-white leading-snug">
          {topic.title}
        </Text>
        <View className="flex-row items-center gap-2 mt-1.5">
          {topic.high_yield_score > 0 && (
            <View className={`rounded-full border px-2 py-0.5 ${difficultyColor(topic.high_yield_score)}`}>
              <Text className="text-xs font-semibold">
                {topic.high_yield_score >= 30 ? '🔥 High yield' : topic.high_yield_score >= 15 ? '⚡ Medium' : '📖 Core'}
              </Text>
            </View>
          )}
          <Text className="text-xs text-slate-400">⏱ {topic.est_minutes ?? '?'} min</Text>
        </View>
      </View>
      <Text className="text-slate-400 text-lg">→</Text>
    </TouchableOpacity>
  );
}
