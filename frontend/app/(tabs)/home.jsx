import { useEffect, useState, useCallback } from 'react';
import { ScrollView, Text, View, ActivityIndicator, TouchableOpacity } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { supabase } from '@/lib/supabase';

function greeting() {
  const h = new Date().getHours();
  if (h < 12) return 'Good morning ☀️';
  if (h < 17) return 'Good afternoon 🌤️';
  return 'Good evening 🌙';
}

function computeStreak(sessions) {
  // sessions = [{ session_date: 'YYYY-MM-DD' }, ...] ordered DESC
  if (!sessions?.length) return 0;
  const dateSet = new Set(sessions.map((s) => s.session_date));
  let streak = 0;
  const today = new Date();
  for (let i = 0; i < 365; i++) {
    const d = new Date(today);
    d.setDate(today.getDate() - i);
    const key = d.toISOString().split('T')[0];
    if (dateSet.has(key)) streak++;
    else break;
  }
  return streak;
}

export default function HomeScreen() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);

  // User
  const [user, setUser]         = useState(null);
  const [profile, setProfile]   = useState(null);

  // Stats
  const [streak, setStreak]         = useState(0);
  const [todayMinutes, setToday]    = useState(0);
  const [dueTopics, setDueTopics]   = useState([]);
  const [topicsStudied, setTopics]  = useState(0);
  const [pyqsSolved, setPyqs]       = useState(0);
  const [accuracy, setAccuracy]     = useState(null); // 0-100 or null

  const load = useCallback(async () => {
    setLoading(true);
    const { data: { user: u } } = await supabase.auth.getUser();
    setUser(u);

    if (!u) { setLoading(false); return; }

    const today = new Date().toISOString().split('T')[0];

    const [profileRes, sessionsRes, todayRes, dueRes, topicsRes, pyqRes] = await Promise.all([
      // Profile (daily_goal_minutes, exam_date)
      supabase.from('user_profiles').select('daily_goal_minutes, exam_target').eq('id', u.id).single(),

      // All recent sessions for streak (last 60 days)
      supabase.from('study_sessions')
        .select('session_date')
        .eq('user_id', u.id)
        .gte('session_date', (() => { const d = new Date(); d.setDate(d.getDate() - 60); return d.toISOString().split('T')[0]; })())
        .order('session_date', { ascending: false }),

      // Today's session for goal bar
      supabase.from('study_sessions')
        .select('total_minutes')
        .eq('user_id', u.id)
        .eq('session_date', today)
        .single(),

      // Due for revision — topics where next_review_at <= today
      supabase.from('user_progress')
        .select('topic_id, next_review_at, needs_urgent_review, topics(id, title, subject_id, subjects(name, icon))')
        .eq('user_id', u.id)
        .lte('next_review_at', today)
        .order('needs_urgent_review', { ascending: false })
        .limit(5),

      // Topics studied count
      supabase.from('user_progress')
        .select('topic_id', { count: 'exact', head: true })
        .eq('user_id', u.id)
        .not('last_studied_at', 'is', null),

      // PYQ attempts for solved count + accuracy
      supabase.from('pyq_attempts')
        .select('rating')
        .eq('user_id', u.id),
    ]);

    setProfile(profileRes.data);
    setStreak(computeStreak(sessionsRes.data ?? []));
    setToday(todayRes.data?.total_minutes ?? 0);
    setDueTopics(dueRes.data ?? []);
    setTopics(topicsRes.count ?? 0);

    const attempts = pyqRes.data ?? [];
    setPyqs(attempts.length);
    if (attempts.length > 0) {
      const easy = attempts.filter((a) => a.rating === 'easy').length;
      setAccuracy(Math.round((easy / attempts.length) * 100));
    }

    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const goalMinutes = profile?.daily_goal_minutes ?? 60;
  const goalPct     = Math.min(1, todayMinutes / goalMinutes);
  const goalMet     = todayMinutes >= goalMinutes;

  if (loading) {
    return (
      <SafeAreaView style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }} className="bg-white dark:bg-slate-900">
        <ActivityIndicator color="#f97316" size="large" />
      </SafeAreaView>
    );
  }

  // ── Anonymous / not logged in ──
  if (!user) {
    return (
      <SafeAreaView style={{ flex: 1 }} className="bg-white dark:bg-slate-900">
        <ScrollView contentContainerStyle={{ paddingBottom: 40 }}>
          <View className="w-full self-center px-6" style={{ maxWidth: 700 }}>
            <View className="pt-6">
              <Text className="text-2xl font-bold text-slate-900 dark:text-white">{greeting()}</Text>
              <Text className="text-slate-400 text-sm mt-1">Your NIOS study companion</Text>
            </View>
            <View className="mt-6 bg-brand-50 dark:bg-slate-800 border border-brand-100 dark:border-brand-700 rounded-2xl p-6 items-center gap-3">
              <Text style={{ fontSize: 40 }}>📊</Text>
              <Text className="font-bold text-slate-900 dark:text-white text-lg text-center">Track your progress</Text>
              <Text className="text-slate-500 dark:text-slate-400 text-sm text-center">Sign in to see your streak, daily goal, due topics, and study stats.</Text>
              <TouchableOpacity
                className="bg-brand-500 rounded-2xl px-8 py-3 mt-2 active:opacity-80"
                onPress={() => router.push('/(auth)/sign-in')}
              >
                <Text className="text-white font-semibold">Sign In / Create Account</Text>
              </TouchableOpacity>
            </View>
          </View>
        </ScrollView>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={{ flex: 1 }} className="bg-white dark:bg-slate-900">
      <ScrollView style={{ flex: 1 }} contentContainerStyle={{ paddingBottom: 40 }}>
        <View className="w-full self-center px-6" style={{ maxWidth: 700 }}>

          {/* ── Header ── */}
          <View className="pt-6 flex-row items-center justify-between">
            <View style={{ flex: 1, marginRight: 12 }}>
              <Text className="text-2xl font-bold text-slate-900 dark:text-white">{greeting()}</Text>
              <Text className="text-slate-500 dark:text-slate-400 text-sm mt-0.5">
                {goalMet ? '🎉 Daily goal complete!' : 'Keep up the momentum!'}
              </Text>
            </View>
            <View className="flex-row items-center gap-3">
              {/* Streak badge */}
              <View className="bg-brand-50 dark:bg-slate-800 border border-brand-200 dark:border-slate-700 rounded-xl px-3 py-2 items-center">
                <Text className="text-brand-500 font-bold text-lg">{streak}🔥</Text>
                <Text className="text-brand-400 text-xs">streak</Text>
              </View>
              <TouchableOpacity
                onPress={() => router.push('/(tabs)/settings')}
                className="bg-slate-100 dark:bg-slate-800 rounded-xl w-10 h-10 items-center justify-center"
              >
                <Text style={{ fontSize: 18 }}>⚙️</Text>
              </TouchableOpacity>
            </View>
          </View>

          {/* ── Today's Goal Bar ── */}
          <View className={`rounded-2xl p-5 gap-3 mt-5 ${goalMet ? 'bg-green-50 dark:bg-green-950' : 'bg-slate-50 dark:bg-slate-800'}`}>
            <View className="flex-row items-center justify-between">
              <Text className={`font-semibold ${goalMet ? 'text-green-700 dark:text-green-400' : 'text-slate-900 dark:text-white'}`}>
                Today's Study Goal
              </Text>
              <Text className={`text-sm font-semibold ${goalMet ? 'text-green-600 dark:text-green-400' : 'text-slate-500 dark:text-slate-400'}`}>
                {todayMinutes} / {goalMinutes} min
              </Text>
            </View>
            <View className="h-2.5 rounded-full bg-slate-200 dark:bg-slate-700">
              <View
                className={`h-2.5 rounded-full ${goalMet ? 'bg-green-500' : 'bg-brand-500'}`}
                style={{ width: `${Math.round(goalPct * 100)}%` }}
              />
            </View>
            <Text className="text-xs text-slate-400">
              {goalMet
                ? 'Amazing! You met your goal for today 🎉'
                : `${goalMinutes - todayMinutes} min left to meet your goal`}
            </Text>
          </View>

          {/* ── Due for Revision ── */}
          <View className="mt-5">
            <Text className="font-semibold text-slate-700 dark:text-slate-300 mb-3">⏰ Due for Revision</Text>
            {dueTopics.length === 0 ? (
              <View className="bg-slate-50 dark:bg-slate-800 rounded-2xl p-5">
                <Text className="text-slate-400 text-sm text-center">
                  {topicsStudied === 0
                    ? 'Start studying topics to schedule your first revision! 📚'
                    : '✅ All caught up — nothing due today!'}
                </Text>
              </View>
            ) : (
              <View className="gap-2">
                {dueTopics.map((p) => {
                  const topic = p.topics;
                  const sub   = topic?.subjects;
                  return (
                    <TouchableOpacity
                      key={p.topic_id}
                      onPress={() => router.push(`/topic/${p.topic_id}`)}
                      className="bg-slate-50 dark:bg-slate-800 rounded-2xl px-5 py-4 flex-row items-center gap-3 active:opacity-75"
                      style={{ shadowColor: '#000', shadowOpacity: 0.03, shadowRadius: 4, elevation: 1 }}
                    >
                      <Text style={{ fontSize: 22 }}>{sub?.icon ?? '📖'}</Text>
                      <View style={{ flex: 1 }}>
                        <Text className="text-slate-900 dark:text-white font-medium text-sm" numberOfLines={1}>
                          {topic?.title}
                        </Text>
                        <Text className="text-slate-400 text-xs mt-0.5">{sub?.name}</Text>
                      </View>
                      {p.needs_urgent_review && (
                        <View className="bg-red-50 border border-red-200 rounded-full px-2 py-0.5">
                          <Text className="text-red-500 text-xs font-semibold">Urgent</Text>
                        </View>
                      )}
                      <Text className="text-slate-300 dark:text-slate-600 text-base">›</Text>
                    </TouchableOpacity>
                  );
                })}
              </View>
            )}
          </View>

          {/* ── Stats ── */}
          <Text className="font-semibold text-slate-700 dark:text-slate-300 mt-6 mb-3">Your Stats</Text>
          <View className="flex-row gap-3 flex-wrap">
            {[
              { label: 'Topics Studied', value: topicsStudied,   emoji: '📖' },
              { label: 'PYQs Solved',    value: pyqsSolved,      emoji: '✍️' },
              { label: 'Accuracy',       value: accuracy !== null ? `${accuracy}%` : '—', emoji: '🎯' },
            ].map(({ label, value, emoji }) => (
              <View
                key={label}
                style={{ flex: 1, minWidth: 100 }}
                className="bg-slate-50 dark:bg-slate-800 rounded-2xl p-4 items-center gap-1"
              >
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
