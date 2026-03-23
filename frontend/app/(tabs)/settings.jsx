import { useEffect, useState, useCallback } from 'react';
import { useRouter } from 'expo-router';
import {
  ScrollView, Text, TouchableOpacity, View, Switch, ActivityIndicator, Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { useColorScheme } from '@/hooks/use-color-scheme';
import { supabase } from '@/lib/supabase';

const CLASS_OPTIONS = ['11', '12'];

const TARGET_OPTIONS = [
  { label: '✅ Just Pass', value: 'pass' },
  { label: '🎯 Score 75%', value: '75' },
  { label: '🏆 Score 90%+', value: '90' },
];

const TIME_OPTIONS = [
  { label: '30 min', value: 30 },
  { label: '1 hr', value: 60 },
  { label: '2 hrs', value: 120 },
  { label: '3+ hrs', value: 180 },
];

function SectionHeader({ title }) {
  return (
    <Text className="text-xs font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-widest mt-8 mb-3 px-1">
      {title}
    </Text>
  );
}

function SettingsRow({ label, right, onPress }) {
  const content = (
    <View className="bg-white dark:bg-slate-800 rounded-2xl px-5 py-4 flex-row items-center justify-between"
      style={{ shadowColor: '#000', shadowOpacity: 0.03, shadowRadius: 4, elevation: 1 }}>
      <Text className="text-slate-900 dark:text-white text-base font-medium">{label}</Text>
      {right}
    </View>
  );
  return onPress ? (
    <TouchableOpacity onPress={onPress} activeOpacity={0.75}>{content}</TouchableOpacity>
  ) : content;
}

export default function SettingsScreen() {
  const router = useRouter();
  const { colorScheme, override: themeOverride, setTheme } = useColorScheme();
  const isDark = colorScheme === 'dark';

  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  // Preferences
  const [classLevel, setClassLevel] = useState('11');
  const [examTarget, setExamTarget] = useState('pass');
  const [dailyMinutes, setDailyMinutes] = useState(60);

  const load = useCallback(async () => {
    const { data: { user: u } } = await supabase.auth.getUser();
    setUser(u);

    if (u) {
      const { data } = await supabase
        .from('user_profiles')
        .select('class_level, exam_target, daily_goal_minutes')
        .eq('id', u.id)
        .single();
      if (data) {
        setClassLevel(data.class_level ?? '11');
        setExamTarget(data.exam_target ?? 'pass');
        setDailyMinutes(data.daily_goal_minutes ?? 60);
      }
    } else {
      setClassLevel((await AsyncStorage.getItem('anon_class_level')) ?? '11');
      setExamTarget((await AsyncStorage.getItem('anon_exam_target')) ?? 'pass');
      const m = await AsyncStorage.getItem('anon_daily_minutes');
      setDailyMinutes(m ? parseInt(m, 10) : 60);
    }
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  async function savePrefs() {
    setSaving(true);
    if (user) {
      await supabase.from('user_profiles').upsert({
        id: user.id,
        class_level: classLevel,
        exam_target: examTarget,
        daily_goal_minutes: dailyMinutes,
      });
    } else {
      await AsyncStorage.setItem('anon_class_level', classLevel);
      await AsyncStorage.setItem('anon_exam_target', examTarget);
      await AsyncStorage.setItem('anon_daily_minutes', String(dailyMinutes));
    }
    setSaving(false);
    Alert.alert('Saved', 'Your preferences have been updated.');
  }

  async function handleSignOut() {
    await supabase.auth.signOut();
    await AsyncStorage.multiRemove([
      'anon_subject_ids', 'anon_exam_target', 'anon_class_level', 'anon_daily_minutes',
    ]);
    router.replace('/(auth)/welcome');
  }

  if (loading) {
    return (
      <SafeAreaView style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}
        className="bg-slate-50 dark:bg-slate-900">
        <ActivityIndicator color="#f97316" size="large" />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={{ flex: 1 }} className="bg-slate-50 dark:bg-slate-900">
      <ScrollView style={{ flex: 1 }} contentContainerStyle={{ paddingBottom: 60 }}>
        <View className="w-full self-center px-5" style={{ maxWidth: 640 }}>

          {/* Title */}
          <View className="pt-6 pb-1">
            <Text className="text-2xl font-bold text-slate-900 dark:text-white">Settings ⚙️</Text>
          </View>

          {/* ── Account ── */}
          <SectionHeader title="Account" />
          <View className="bg-white dark:bg-slate-800 rounded-2xl px-5 py-4 gap-1">
            <Text className="text-xs text-slate-400">Signed in as</Text>
            <Text className="text-slate-900 dark:text-white font-semibold text-base">
              {user ? user.email : 'Anonymous user'}
            </Text>
          </View>

          {/* ── Profile ── */}
          <SectionHeader title="Profile" />

          {/* Class level */}
          <View className="bg-white dark:bg-slate-800 rounded-2xl px-5 py-4 gap-3">
            <Text className="text-slate-900 dark:text-white font-medium text-base">Class</Text>
            <View className="flex-row gap-3">
              {CLASS_OPTIONS.map((cls) => {
                const sel = classLevel === cls;
                return (
                  <TouchableOpacity
                    key={cls}
                    onPress={() => setClassLevel(cls)}
                    className={`flex-1 py-3 rounded-xl items-center border-2 ${sel ? 'border-brand-500 bg-brand-50 dark:bg-brand-950' : 'border-slate-200 dark:border-slate-700'}`}
                  >
                    <Text className={`font-semibold text-base ${sel ? 'text-brand-500' : 'text-slate-700 dark:text-slate-300'}`}>
                      Class {cls}
                    </Text>
                  </TouchableOpacity>
                );
              })}
            </View>
          </View>

          {/* ── Study Preferences ── */}
          <SectionHeader title="Study Preferences" />

          {/* Target score */}
          <View className="bg-white dark:bg-slate-800 rounded-2xl px-5 py-4 gap-3">
            <Text className="text-slate-900 dark:text-white font-medium text-base">Target Score</Text>
            <View className="gap-2">
              {TARGET_OPTIONS.map((opt) => {
                const sel = examTarget === opt.value;
                return (
                  <TouchableOpacity
                    key={opt.value}
                    onPress={() => setExamTarget(opt.value)}
                    className={`flex-row items-center justify-between py-3 px-4 rounded-xl border-2 ${sel ? 'border-brand-500 bg-brand-50 dark:bg-brand-950' : 'border-slate-100 dark:border-slate-700'}`}
                  >
                    <Text className={`font-semibold ${sel ? 'text-brand-600' : 'text-slate-800 dark:text-slate-200'}`}>
                      {opt.label}
                    </Text>
                    {sel && <Text className="text-brand-500 text-base">✓</Text>}
                  </TouchableOpacity>
                );
              })}
            </View>
          </View>

          {/* Daily study time */}
          <View className="bg-white dark:bg-slate-800 rounded-2xl px-5 py-4 gap-3 mt-3">
            <Text className="text-slate-900 dark:text-white font-medium text-base">Daily Study Time</Text>
            <View className="flex-row gap-2 flex-wrap">
              {TIME_OPTIONS.map((opt) => {
                const sel = dailyMinutes === opt.value;
                return (
                  <TouchableOpacity
                    key={opt.value}
                    onPress={() => setDailyMinutes(opt.value)}
                    className={`px-4 py-2.5 rounded-xl border-2 ${sel ? 'border-brand-500 bg-brand-50 dark:bg-brand-950' : 'border-slate-200 dark:border-slate-700'}`}
                  >
                    <Text className={`font-semibold ${sel ? 'text-brand-600' : 'text-slate-700 dark:text-slate-300'}`}>
                      {opt.label}
                    </Text>
                  </TouchableOpacity>
                );
              })}
            </View>
          </View>

          {/* Save preferences button */}
          <TouchableOpacity
            className="bg-brand-500 rounded-2xl py-4 items-center mt-4 active:opacity-80"
            onPress={savePrefs}
            disabled={saving}
          >
            {saving
              ? <ActivityIndicator color="white" />
              : <Text className="text-white text-base font-semibold">Save Preferences</Text>
            }
          </TouchableOpacity>

          {/* ── App ── */}
          <SectionHeader title="App" />
          <View className="bg-white dark:bg-slate-800 rounded-2xl px-5 py-4 gap-3"
            style={{ shadowColor: '#000', shadowOpacity: 0.03, shadowRadius: 4, elevation: 1 }}>
            <Text className="text-slate-900 dark:text-white font-medium text-base">Theme</Text>
            <View className="flex-row gap-2">
              {[{ key: 'light', label: '☀️ Light' }, { key: 'dark', label: '🌙 Dark' }, { key: 'system', label: '⚙️ Auto' }].map((opt) => (
                <TouchableOpacity
                  key={opt.key}
                  onPress={() => setTheme(opt.key)}
                  className={`flex-1 py-2.5 rounded-xl items-center border-2 ${
                    themeOverride === opt.key
                      ? 'border-brand-500 bg-brand-50 dark:bg-brand-950'
                      : 'border-slate-200 dark:border-slate-700'
                  }`}
                >
                  <Text className={`text-xs font-semibold ${
                    themeOverride === opt.key ? 'text-brand-600 dark:text-brand-400' : 'text-slate-500 dark:text-slate-400'
                  }`}>{opt.label}</Text>
                </TouchableOpacity>
              ))}
            </View>
          </View>
          <View className="bg-white dark:bg-slate-800 rounded-2xl px-5 divide-y divide-slate-100 dark:divide-slate-700 mt-3"
            style={{ shadowColor: '#000', shadowOpacity: 0.03, shadowRadius: 4, elevation: 1 }}>
            <SettingsRow
              label="App Version"
              right={<Text className="text-slate-400 text-sm">1.0.0-beta</Text>}
            />
          </View>

          {/* ── Account actions ── */}
          <SectionHeader title="Session" />
          <View className="gap-3">
            {user ? (
              <TouchableOpacity
                className="bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-2xl py-4 items-center active:opacity-80"
                onPress={() =>
                  Alert.alert('Sign Out', 'Are you sure you want to sign out?', [
                    { text: 'Cancel', style: 'cancel' },
                    { text: 'Sign Out', style: 'destructive', onPress: handleSignOut },
                  ])
                }
              >
                <Text className="text-red-500 font-semibold text-base">Sign Out</Text>
              </TouchableOpacity>
            ) : (
              <TouchableOpacity
                className="bg-brand-500 rounded-2xl py-4 items-center active:opacity-80"
                onPress={() => router.push('/(auth)/sign-in')}
              >
                <Text className="text-white font-semibold text-base">Sign In / Create Account</Text>
              </TouchableOpacity>
            )}
          </View>

        </View>
      </ScrollView>
    </SafeAreaView>
  );
}
