import { useRouter } from 'expo-router';
import { Text, View, TouchableOpacity, Image } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

export default function WelcomeScreen() {
  const router = useRouter();

  return (
    <SafeAreaView className="flex-1 bg-white dark:bg-slate-900">
      <View className="flex-1 items-center justify-center px-8 gap-6">
        {/* Brand Logo Placeholder */}
        <View className="w-24 h-24 rounded-3xl bg-brand-500 items-center justify-center mb-2">
          <Text className="text-white text-5xl font-bold">⚡</Text>
        </View>

        <Text className="text-4xl font-bold text-slate-900 dark:text-white text-center">
          Crush your exam.{'\n'}
          <Text className="text-brand-500">Last minute.</Text>
        </Text>

        <Text className="text-base text-slate-500 dark:text-slate-400 text-center leading-6">
          Smart revision powered by your syllabus, your time, and your weak spots.
        </Text>
      </View>

      {/* CTA Buttons */}
      <View className="px-6 pb-8 gap-3">
        <TouchableOpacity
          className="bg-brand-500 rounded-2xl py-4 items-center active:opacity-80"
          onPress={() => router.push('/(auth)/sign-up')}
        >
          <Text className="text-white text-base font-semibold">Get Started</Text>
        </TouchableOpacity>

        <TouchableOpacity
          className="border border-slate-200 dark:border-slate-700 rounded-2xl py-4 items-center active:opacity-80"
          onPress={() => router.push('/(auth)/sign-in')}
        >
          <Text className="text-slate-900 dark:text-white text-base font-semibold">I already have an account</Text>
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
}
