import { useEffect, useState } from 'react';
import { ScrollView, Text, TouchableOpacity, View, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { supabase } from '@/lib/supabase';

export default function LearningScreen() {
  const router = useRouter();
  const [subjects, setSubjects] = useState([]);
  const [urgentTopics, setUrgentTopics] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchData() {
      const { data: { user } } = await supabase.auth.getUser();

      if (user) {
        // Logged-in: load from Supabase
        const { data: userSubjects } = await supabase
          .from('user_subjects')
          .select('subject_id, subjects(id, name, icon)')
          .eq('user_id', user.id);
        setSubjects(userSubjects?.map((us) => us.subjects).filter(Boolean) ?? []);

        const today = new Date().toISOString().split('T')[0];
        const { data: due } = await supabase
          .from('user_progress')
          .select('topic_id, needs_urgent_review, next_review_at, topics(title)')
          .eq('user_id', user.id)
          .or(`needs_urgent_review.eq.true,next_review_at.lte.${today}`)
          .limit(5);
        setUrgentTopics(due ?? []);
      } else {
        // Anonymous: load from AsyncStorage
        try {
          const raw = await AsyncStorage.getItem('anon_subject_ids');
          const ids = raw ? JSON.parse(raw) : [];
          if (ids.length > 0) {
            const { data } = await supabase
              .from('subjects')
              .select('id, name, icon')
              .in('id', ids);
            setSubjects(data ?? []);
          }
        } catch { /* ignore */ }
      }

      setLoading(false);
    }
    fetchData();
  }, []);

  if (loading) {
    return (
      <SafeAreaView style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }} className="bg-white dark:bg-slate-900">
        <ActivityIndicator color="#f97316" size="large" />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={{ flex: 1 }} className="bg-white dark:bg-slate-900">
      <ScrollView style={{ flex: 1 }} contentContainerStyle={{ paddingBottom: 40 }}>
        <View className="w-full self-center px-6" style={{ maxWidth: 700 }}>

          <View className="pt-6 pb-2">
            <Text className="text-2xl font-bold text-slate-900 dark:text-white">Learning 📚</Text>
          </View>

          {/* Suggested revision */}
          {urgentTopics.length > 0 && (
            <View className="gap-3 mt-4">
              <Text className="font-semibold text-slate-700 dark:text-slate-300">📌 Suggested for you today</Text>
              {urgentTopics.map((item) => (
                <TouchableOpacity
                  key={item.topic_id}
                  className="bg-brand-50 dark:bg-slate-800 border border-brand-200 dark:border-brand-800 rounded-2xl px-4 py-4 flex-row items-center justify-between"
                  onPress={() => router.push(`/topic/${item.topic_id}`)}
                >
                  <View style={{ flex: 1, marginRight: 8 }}>
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

          {/* All subjects */}
          <Text className="font-semibold text-slate-700 dark:text-slate-300 mt-6 mb-3">Your Subjects</Text>
          {subjects.length === 0 ? (
            <View className="bg-slate-50 dark:bg-slate-800 rounded-2xl p-6 items-center">
              <Text className="text-slate-400 text-center">No subjects yet. Complete onboarding first.</Text>
            </View>
          ) : (
            <View className="gap-3">
              {subjects.map((subject) => (
                <TouchableOpacity
                  key={subject.id}
                  className="bg-slate-50 dark:bg-slate-800 rounded-2xl px-5 py-4 flex-row items-center justify-between"
                  onPress={() => router.push(`/subject/${subject.id}`)}
                >
                  <Text className="text-base font-semibold text-slate-900 dark:text-white">{subject.icon} {subject.name}</Text>
                  <Text className="text-slate-400">→</Text>
                </TouchableOpacity>
              ))}
            </View>
          )}

        </View>
      </ScrollView>
    </SafeAreaView>
  );
}
