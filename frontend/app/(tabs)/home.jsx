import { useEffect, useState } from 'react';
import { ScrollView, Text, View, ActivityIndicator, TouchableOpacity } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { supabase } from '@/lib/supabase';

export default function HomeScreen() {
  const router = useRouter();
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchProfile() {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) { setLoading(false); return; }
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
      <SafeAreaView style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }} className="bg-white dark:bg-slate-900">
        <ActivityIndicator color="#f97316" size="large" />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={{ flex: 1 }} className="bg-white dark:bg-slate-900">
      <ScrollView
        style={{ flex: 1 }}
        contentContainerStyle={{ paddingBottom: 40 }}
      >
        {/* Responsive content wrapper */}
        <View className="w-full self-center px-6" style={{ maxWidth: 700 }}>

          {/* Header */}
          <View className="pt-6 flex-row items-center justify-between">
            <View style={{ flex: 1, marginRight: 12 }}>
              <Text className="text-2xl font-bold text-slate-900 dark:text-white">Good morning ⚡</Text>
              {daysLeft !== null && (
                <Text className="text-slate-500 dark:text-slate-400 text-sm mt-0.5">
                  {daysLeft} days until exam — stay sharp!
                </Text>
              )}
            </View>
            <View className="flex-row items-center gap-3">
              {/* Streak badge */}
              <View className="bg-brand-50 border border-brand-200 rounded-xl px-3 py-2 items-center">
                <Text className="text-brand-500 font-bold text-lg">{profile?.streak_days ?? 0}🔥</Text>
                <Text className="text-brand-400 text-xs">streak</Text>
              </View>
              {/* Settings shortcut */}
              <TouchableOpacity
                onPress={() => router.push('/(tabs)/settings')}
                className="bg-slate-100 dark:bg-slate-800 rounded-xl w-10 h-10 items-center justify-center"
              >
                <Text style={{ fontSize: 18 }}>⚙️</Text>
              </TouchableOpacity>
            </View>
          </View>

          {/* Today's Goal Progress */}
          <View className="bg-slate-50 dark:bg-slate-800 rounded-2xl p-5 gap-3 mt-5">
            <Text className="font-semibold text-slate-900 dark:text-white">Today's Study Goal</Text>
            <View className="flex-row items-center gap-3">
              <View style={{ flex: 1 }} className="h-2.5 rounded-full bg-slate-200 dark:bg-slate-700">
                <View className="h-2.5 rounded-full bg-brand-500 w-1/4" />
              </View>
              <Text className="text-slate-500 text-sm">0 / {profile?.daily_goal_minutes ?? '—'} min</Text>
            </View>
            <Text className="text-xs text-slate-400">
              Complete your goal to maintain your streak!
            </Text>
          </View>

          {/* Revision due */}
          <View className="bg-slate-50 dark:bg-slate-800 rounded-2xl p-5 gap-2 mt-4">
            <Text className="font-semibold text-slate-900 dark:text-white">⏰ Due for Revision</Text>
            <Text className="text-slate-500 dark:text-slate-400 text-sm">Topics scheduled for review will appear here once you start studying.</Text>
          </View>

          {/* Quick Stats */}
          <Text className="font-semibold text-slate-700 dark:text-slate-300 mt-5 mb-3">Your Stats</Text>
          <View className="flex-row gap-3 flex-wrap">
            {[
              { label: 'Topics Studied', value: '--', emoji: '📖' },
              { label: 'PYQs Solved', value: '--', emoji: '✍️' },
              { label: 'Accuracy', value: '--', emoji: '🎯' },
            ].map(({ label, value, emoji }) => (
              <View key={label} style={{ flex: 1, minWidth: 100 }} className="bg-slate-50 dark:bg-slate-800 rounded-2xl p-4 items-center gap-1">
                <Text style={{ fontSize: 22 }}>{emoji}</Text>
                <Text className="text-2xl font-bold text-brand-500">{value}</Text>
                <Text className="text-xs text-slate-400 text-center">{label}</Text>
              </View>
            ))}
          </View>

        </View>
      </ScrollView>
    </SafeAreaView>
  );
}
