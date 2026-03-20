import { useState } from 'react';
import { useRouter } from 'expo-router';
import { Text, TouchableOpacity, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

const CLASSES = ['10', '11', '12'];

export default function ClassScreen() {
  const router = useRouter();
  const [selected, setSelected] = useState(null);

  return (
    <SafeAreaView className="flex-1 bg-white dark:bg-slate-900 px-6">
      {/* Progress: 1 of 3 */}
      <View className="flex-row gap-2 pt-6">
        {[1, 2, 3].map((step) => (
          <View key={step} className={`h-1 flex-1 rounded-full ${step === 1 ? 'bg-brand-500' : 'bg-slate-200 dark:bg-slate-700'}`} />
        ))}
      </View>

      <View className="pt-10 gap-2">
        <Text className="text-2xl font-bold text-slate-900 dark:text-white">Which class are you in?</Text>
        <Text className="text-slate-500 dark:text-slate-400">We'll load the right syllabus for you.</Text>
      </View>

      <View className="pt-8 gap-3">
        {CLASSES.map((cls) => (
          <TouchableOpacity
            key={cls}
            className={`border-2 rounded-2xl py-5 items-center ${selected === cls ? 'border-brand-500 bg-brand-50' : 'border-slate-200 dark:border-slate-700'}`}
            onPress={() => setSelected(cls)}
          >
            <Text className={`text-xl font-semibold ${selected === cls ? 'text-brand-500' : 'text-slate-900 dark:text-white'}`}>
              Class {cls}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      <View className="flex-1" />

      <TouchableOpacity
        className={`rounded-2xl py-4 items-center mb-8 ${selected ? 'bg-brand-500 active:opacity-80' : 'bg-slate-200 dark:bg-slate-700'}`}
        disabled={!selected}
        onPress={() => router.push({ pathname: '/(onboarding)/subjects', params: { classLevel: selected } })}
      >
        <Text className={`text-base font-semibold ${selected ? 'text-white' : 'text-slate-400'}`}>Next →</Text>
      </TouchableOpacity>
    </SafeAreaView>
  );
}
