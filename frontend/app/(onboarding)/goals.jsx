import { useState } from 'react';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { Platform, Text, TouchableOpacity, View, ActivityIndicator, ScrollView } from 'react-native';
import DateTimePicker from '@react-native-community/datetimepicker';
import { SafeAreaView } from 'react-native-safe-area-context';
import { supabase } from '@/lib/supabase';

const TIME_OPTIONS = [
  { label: '30 min / day', value: 30 },
  { label: '1 hour / day', value: 60 },
  { label: '2 hours / day', value: 120 },
  { label: '3+ hours / day', value: 180 },
];

export default function GoalsScreen() {
  const router = useRouter();
  const { classLevel, subjectIds } = useLocalSearchParams();

  const [dailyMinutes, setDailyMinutes] = useState(null);
  const [examDate, setExamDate] = useState(new Date());
  const [showDatePicker, setShowDatePicker] = useState(false);
  const [saving, setSaving] = useState(false);

  async function handleSave() {
    setSaving(true);
    const { data: { user } } = await supabase.auth.getUser();

    if (user) {
      const parsedSubjects = JSON.parse(subjectIds);
      await supabase.from('user_profiles').upsert({
        id: user.id,
        class_level: classLevel,
        exam_date: examDate.toISOString().split('T')[0],
        daily_goal_minutes: dailyMinutes,
      });
      await supabase.from('user_subjects').upsert(
        parsedSubjects.map((sid) => ({ user_id: user.id, subject_id: sid }))
      );
    }

    setSaving(false);
    router.push({ pathname: '/(onboarding)/baseline', params: { subjectIds } });
  }

  const formattedDate = examDate.toLocaleDateString('en-IN', { day: 'numeric', month: 'long', year: 'numeric' });

  return (
    <SafeAreaView style={{ flex: 1 }} className="bg-white dark:bg-slate-900">
      <ScrollView contentContainerStyle={{ flexGrow: 1 }} keyboardShouldPersistTaps="handled">
        <View className="w-full self-center px-6 flex-1" style={{ maxWidth: 520 }}>

          {/* Progress: 3 of 3 */}
          <View className="flex-row gap-2 pt-6">
            {[1, 2, 3].map((step) => (
              <View key={step} className="h-1 flex-1 rounded-full bg-brand-500" />
            ))}
          </View>

          <View className="pt-10 gap-2">
            <Text className="text-2xl font-bold text-slate-900 dark:text-white">Set your targets</Text>
            <Text className="text-slate-500 dark:text-slate-400">We'll build a personalised plan around your schedule.</Text>
          </View>

          {/* Daily time */}
          <Text className="mt-8 mb-3 text-sm font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-widest">Daily Study Time</Text>
          <View className="gap-3">
            {TIME_OPTIONS.map((opt) => (
              <TouchableOpacity
                key={opt.value}
                className={`border-2 rounded-2xl py-4 px-5 ${dailyMinutes === opt.value ? 'border-brand-500 bg-brand-50' : 'border-slate-200 dark:border-slate-700'}`}
                onPress={() => setDailyMinutes(opt.value)}
              >
                <Text className={`font-semibold ${dailyMinutes === opt.value ? 'text-brand-600' : 'text-slate-900 dark:text-white'}`}>
                  {opt.label}
                </Text>
              </TouchableOpacity>
            ))}
          </View>

          {/* Exam date */}
          <Text className="mt-8 mb-3 text-sm font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-widest">Exam Date (approx)</Text>
          <TouchableOpacity
            className="border-2 border-slate-200 dark:border-slate-700 rounded-2xl py-4 px-5"
            onPress={() => setShowDatePicker(true)}
          >
            <Text className="text-slate-900 dark:text-white font-semibold">{formattedDate}</Text>
          </TouchableOpacity>

          {showDatePicker && (
            <DateTimePicker
              value={examDate}
              mode="date"
              minimumDate={new Date()}
              onChange={(_, date) => { setShowDatePicker(false); if (date) setExamDate(date); }}
            />
          )}

          <View style={{ flex: 1, minHeight: 40 }} />

          <TouchableOpacity
            className={`rounded-2xl py-4 items-center mb-8 ${dailyMinutes ? 'bg-brand-500 active:opacity-80' : 'bg-slate-200 dark:bg-slate-700'}`}
            disabled={!dailyMinutes || saving}
            onPress={handleSave}
          >
            {saving
              ? <ActivityIndicator color="white" />
              : <Text className={`text-base font-semibold ${dailyMinutes ? 'text-white' : 'text-slate-400'}`}>Save & Continue →</Text>
            }
          </TouchableOpacity>

        </View>
      </ScrollView>
    </SafeAreaView>
  );
}
