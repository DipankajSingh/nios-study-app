import { useEffect, useState } from 'react';
import { ScrollView, Text, View, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { supabase } from '@/lib/supabase';

export default function HomeScreen() {
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchProfile() {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) return;
      const { data } = await supabase
        .from('user_profiles')
        .select('*, user_subjects(subject_id)')
        .eq('id', user.id)
        .single();
      setProfile(data);
      setLoading(false);
    }
    fetchProfile();
  }, []);

  const daysLeft = profile?.exam_date
    ? Math.max(0, Math.ceil((new Date(profile.exam_date) - new Date()) / (1000 * 60 * 60 * 24)))
    : null;

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
        {/* Header */}
        <View className="pt-6 flex-row items-center justify-between">
          <View>
            <Text className="text-2xl font-bold text-slate-900 dark:text-white">Good morning ⚡</Text>
            {daysLeft !== null && (
              <Text className="text-slate-500 dark:text-slate-400 text-sm mt-0.5">
                {daysLeft} days until exam — stay sharp!
              </Text>
            )}
          </View>
          {/* Streak badge */}
          <View className="bg-brand-50 border border-brand-200 rounded-xl px-3 py-2 items-center">
            <Text className="text-brand-500 font-bold text-lg">{profile?.streak_days ?? 0}🔥</Text>
            <Text className="text-brand-400 text-xs">streak</Text>
          </View>
        </View>

        {/* Today's Goal Progress */}
        <View className="bg-slate-50 dark:bg-slate-800 rounded-2xl p-5 gap-3">
          <Text className="font-semibold text-slate-900 dark:text-white">Today's Study Goal</Text>
          <View className="flex-row items-center gap-3">
            <View className="flex-1 h-2.5 rounded-full bg-slate-200 dark:bg-slate-700">
              {/* Progress will be dynamic once we track minutes in study_sessions */}
              <View className="h-2.5 rounded-full bg-brand-500 w-1/4" />
            </View>
            <Text className="text-slate-500 text-sm">0 / {profile?.daily_goal_minutes} min</Text>
          </View>
          <Text className="text-xs text-slate-400">
            Complete your goal to maintain your streak! Your streak only counts when you finish the full {profile?.daily_goal_minutes} minutes.
          </Text>
        </View>

        {/* Revision due */}
        <View className="bg-slate-50 dark:bg-slate-800 rounded-2xl p-5 gap-2">
          <Text className="font-semibold text-slate-900 dark:text-white">⏰ Due for Revision</Text>
          <Text className="text-slate-500 dark:text-slate-400 text-sm">Topics scheduled for review today will appear here once you start studying.</Text>
        </View>

        {/* Quick Stats */}
        <Text className="font-semibold text-slate-700 dark:text-slate-300">Your Stats</Text>
        <View className="flex-row gap-3">
          {[
            { label: 'Topics Studied', value: '--' },
            { label: 'PYQs Solved', value: '--' },
            { label: 'Accuracy', value: '--' },
          ].map(({ label, value }) => (
            <View key={label} className="flex-1 bg-slate-50 dark:bg-slate-800 rounded-2xl p-4 items-center gap-1">
              <Text className="text-2xl font-bold text-brand-500">{value}</Text>
              <Text className="text-xs text-slate-400 text-center">{label}</Text>
            </View>
          ))}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}
