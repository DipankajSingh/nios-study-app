import { useRouter } from 'expo-router';
import { Text, View, TouchableOpacity, Dimensions, ScrollView } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

const GOOGLE_ICON = '🇬'; // placeholder — replace with actual SVG/image if desired

export default function WelcomeScreen() {
  const router = useRouter();

  function handleSkip() {
    // Anonymous usage — skip auth, go straight to onboarding
    router.replace('/(onboarding)/class');
  }

  function handleGoogleSignIn() {
    // TODO: wire up Supabase Google OAuth
    // supabase.auth.signInWithOAuth({ provider: 'google' })
    router.push('/(auth)/sign-in');
  }

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: 'transparent' }} className="bg-white dark:bg-slate-900">
      <ScrollView
        contentContainerStyle={{ flexGrow: 1 }}
        keyboardShouldPersistTaps="handled"
      >
        {/* Responsive container — max width on web */}
        <View className="flex-1 w-full self-center px-6" style={{ maxWidth: 480 }}>

          {/* Skip button top-right */}
          <View className="items-end pt-4 pb-2">
            <TouchableOpacity onPress={handleSkip} className="px-3 py-2">
              <Text className="text-slate-400 dark:text-slate-500 text-sm font-medium">
                Skip for now →
              </Text>
            </TouchableOpacity>
          </View>

          {/* Hero */}
          <View className="flex-1 items-center justify-center gap-5 py-12">
            <View className="w-24 h-24 rounded-3xl bg-brand-500 items-center justify-center shadow-lg">
              <Text style={{ fontSize: 48 }}>⚡</Text>
            </View>

            <View className="gap-3 items-center">
              <Text className="text-4xl font-bold text-slate-900 dark:text-white text-center leading-tight">
                Crush your exam.{'\n'}
                <Text className="text-brand-500">Last minute.</Text>
              </Text>
              <Text className="text-base text-slate-500 dark:text-slate-400 text-center leading-relaxed px-2">
                Smart revision powered by your syllabus, your time, and your weak spots.
              </Text>
            </View>
          </View>

          {/* Action Buttons */}
          <View className="pb-8 gap-3">
            {/* Primary CTA */}
            <TouchableOpacity
              className="bg-brand-500 rounded-2xl py-4 items-center active:opacity-80"
              onPress={() => router.push('/(auth)/sign-up')}
            >
              <Text className="text-white text-base font-semibold">Get Started</Text>
            </TouchableOpacity>

            {/* Google */}
            <TouchableOpacity
              className="flex-row items-center justify-center gap-3 border border-slate-200 dark:border-slate-700 rounded-2xl py-4 bg-white dark:bg-slate-800 active:opacity-80"
              onPress={handleGoogleSignIn}
            >
              <Text style={{ fontSize: 18 }}>🔵</Text>
              <Text className="text-slate-900 dark:text-white text-base font-semibold">
                Continue with Google
              </Text>
            </TouchableOpacity>

            {/* Already have account */}
            <TouchableOpacity
              className="py-3 items-center active:opacity-70"
              onPress={() => router.push('/(auth)/sign-in')}
            >
              <Text className="text-slate-500 dark:text-slate-400 text-sm">
                Already have an account?{' '}
                <Text className="text-brand-500 font-semibold">Sign in</Text>
              </Text>
            </TouchableOpacity>
          </View>

        </View>
      </ScrollView>
    </SafeAreaView>
  );
}
