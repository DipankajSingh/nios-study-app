import { useState } from 'react';
import { useRouter } from 'expo-router';
import { Alert, ActivityIndicator, KeyboardAvoidingView, Platform, Text, TextInput, TouchableOpacity, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { supabase } from '@/lib/supabase';

export default function SignUpScreen() {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleEmailSignUp() {
    setLoading(true);
    const { error } = await supabase.auth.signUp({ email, password });
    setLoading(false);
    if (error) {
      Alert.alert('Sign Up Error', error.message);
    } else {
      // After sign-up, AuthGate will redirect to onboarding once session is live
      router.replace('/(onboarding)/class');
    }
  }

  return (
    <SafeAreaView className="flex-1 bg-white dark:bg-slate-900">
      <KeyboardAvoidingView
        className="flex-1"
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      >
        <TouchableOpacity className="px-6 pt-4" onPress={() => router.back()}>
          <Text className="text-brand-500 text-base">← Back</Text>
        </TouchableOpacity>

        <View className="px-6 pt-8 gap-2">
          <Text className="text-3xl font-bold text-slate-900 dark:text-white">Create account</Text>
          <Text className="text-slate-500 dark:text-slate-400">Let's set up your revision plan.</Text>
        </View>

        <View className="px-6 pt-8 gap-4">
          <TextInput
            className="border border-slate-200 dark:border-slate-700 rounded-xl px-4 py-3 text-slate-900 dark:text-white bg-slate-50 dark:bg-slate-800"
            placeholder="Email"
            placeholderTextColor="#94a3b8"
            autoCapitalize="none"
            keyboardType="email-address"
            value={email}
            onChangeText={setEmail}
          />
          <TextInput
            className="border border-slate-200 dark:border-slate-700 rounded-xl px-4 py-3 text-slate-900 dark:text-white bg-slate-50 dark:bg-slate-800"
            placeholder="Password (min. 8 characters)"
            placeholderTextColor="#94a3b8"
            secureTextEntry
            value={password}
            onChangeText={setPassword}
          />

          <TouchableOpacity
            className="bg-brand-500 rounded-2xl py-4 items-center mt-2 active:opacity-80"
            onPress={handleEmailSignUp}
            disabled={loading}
          >
            {loading
              ? <ActivityIndicator color="white" />
              : <Text className="text-white text-base font-semibold">Continue</Text>
            }
          </TouchableOpacity>

          <Text className="text-center text-slate-500 dark:text-slate-400 text-sm">
            Already have an account?{' '}
            <Text className="text-brand-500 font-semibold" onPress={() => router.replace('/(auth)/sign-in')}>
              Sign in
            </Text>
          </Text>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
