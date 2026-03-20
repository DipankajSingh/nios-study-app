import { useEffect, useState } from 'react';
import { FlatList, ScrollView, Text, TouchableOpacity, View, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { supabase } from '@/lib/supabase';

export default function LearningScreen() {
  const router = useRouter();
  const [subjects, setSubjects] = useState([]);
  const [urgentTopics, setUrgentTopics] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchData() {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) return;

      // Fetch subjects the user selected
      const { data: userSubjects } = await supabase
        .from('user_subjects')
        .select('subject_id, subjects(id, name)')
        .eq('user_id', user.id);

      setSubjects(userSubjects?.map((us) => us.subjects) ?? []);

      // Fetch topics that need urgent review or are due today
      const today = new Date().toISOString().split('T')[0];
      const { data: due } = await supabase
        .from('user_progress')
        .select('topic_id, needs_urgent_review, next_review_at, topics(title)')
        .eq('user_id', user.id)
        .or(`needs_urgent_review.eq.true,next_review_at.lte.${today}`)
        .limit(5);

      setUrgentTopics(due ?? []);
      setLoading(false);
    }
    fetchData();
  }, []);

  if (loading) {
    return (
      <SafeAreaView className="flex-1 items-center justify-center bg-white dark:bg-slate-900">
        <ActivityIndicator color="#f97316" size="large" />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView className="flex-1 bg-white dark:bg-slate-900">
      <ScrollView className="flex-1 px-6" contentContainerClassName="gap-5 pb-10">
        <View className="pt-6">
          <Text className="text-2xl font-bold text-slate-900 dark:text-white">Learning 📚</Text>
        </View>

        {/* Suggested revision */}
        {urgentTopics.length > 0 && (
          <View className="gap-3">
            <Text className="font-semibold text-slate-700 dark:text-slate-300">📌 Suggested for you today</Text>
            {urgentTopics.map((item) => (
              <TouchableOpacity
                key={item.topic_id}
                className="bg-brand-50 dark:bg-brand-900/20 border border-brand-200 dark:border-brand-800 rounded-2xl px-4 py-4 flex-row items-center justify-between"
                onPress={() => router.push(`/topic/${item.topic_id}`)}
              >
                <View className="flex-1 pr-3">
                  <Text className="text-brand-600 dark:text-brand-400 font-semibold">{item.topics?.title}</Text>
                  {item.needs_urgent_review && (
                    <Text className="text-red-400 text-xs mt-0.5">⚡ Urgent — failed a related PYQ</Text>
                  )}
                </View>
                <Text className="text-brand-400">→</Text>
              </TouchableOpacity>
            ))}
          </View>
        )}

        {/* All selected subjects */}
        <Text className="font-semibold text-slate-700 dark:text-slate-300">Your Subjects</Text>
        {subjects.map((subject) => (
          <TouchableOpacity
            key={subject.id}
            className="bg-slate-50 dark:bg-slate-800 rounded-2xl px-5 py-4 flex-row items-center justify-between"
            onPress={() => router.push(`/subject/${subject.id}`)}
          >
            <Text className="text-base font-semibold text-slate-900 dark:text-white">{subject.name}</Text>
            <Text className="text-slate-400">→</Text>
          </TouchableOpacity>
        ))}

        {subjects.length === 0 && (
          <Text className="text-slate-400 text-center mt-8">No subjects found. Complete onboarding first.</Text>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}
