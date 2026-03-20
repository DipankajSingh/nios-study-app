import { useState } from 'react';
import { useRouter } from 'expo-router';
import {
  Alert, ActivityIndicator, KeyboardAvoidingView, Platform,
  Text, TextInput, TouchableOpacity, View, ScrollView,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { supabase } from '@/lib/supabase';

export default function SignInScreen() {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleEmailSignIn() {
    if (!email || !password) return Alert.alert('Please fill in both fields.');
    setLoading(true);
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    setLoading(false);
    if (error) Alert.alert('Sign In Error', error.message);
    // On success, AuthGate redirects automatically
  }

  async function handleGoogleSignIn() {
    // TODO: implement Supabase Google OAuth
    Alert.alert('Coming soon', 'Google sign-in will be enabled once OAuth is configured in Supabase.');
  }

  function handleSkip() {
    router.replace('/(onboarding)/class');
  }

  return (
    <SafeAreaView style={{ flex: 1 }} className="bg-white dark:bg-slate-900">
      <KeyboardAvoidingView
        style={{ flex: 1 }}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      >
        <ScrollView contentContainerStyle={{ flexGrow: 1 }} keyboardShouldPersistTaps="handled">
          <View className="w-full self-center px-6" style={{ maxWidth: 480 }}>

            {/* Header row */}
            <View className="flex-row items-center justify-between pt-4 pb-2">
              <TouchableOpacity onPress={() => router.back()} className="py-2 pr-4">
                <Text className="text-brand-500 text-base">← Back</Text>
              </TouchableOpacity>
              <TouchableOpacity onPress={handleSkip} className="py-2">
                <Text className="text-slate-400 dark:text-slate-500 text-sm">Skip →</Text>
              </TouchableOpacity>
            </View>

            {/* Title */}
            <View className="pt-8 pb-6 gap-1">
              <Text className="text-3xl font-bold text-slate-900 dark:text-white">Welcome back</Text>
              <Text className="text-slate-500 dark:text-slate-400 text-base">
                Sign in to continue your revision.
              </Text>
            </View>

            {/* Google button */}
            <TouchableOpacity
              className="flex-row items-center justify-center gap-3 border border-slate-200 dark:border-slate-700 rounded-2xl py-4 bg-white dark:bg-slate-800 active:opacity-80 mb-6"
              onPress={handleGoogleSignIn}
            >
              <Text style={{ fontSize: 18 }}>🔵</Text>
              <Text className="text-slate-900 dark:text-white text-base font-semibold">
                Continue with Google
              </Text>
            </TouchableOpacity>

            {/* Divider */}
            <View className="flex-row items-center gap-3 mb-6">
              <View className="flex-1 h-px bg-slate-200 dark:bg-slate-700" />
              <Text className="text-slate-400 text-sm">or use email</Text>
              <View className="flex-1 h-px bg-slate-200 dark:bg-slate-700" />
            </View>

            {/* Email / Password fields */}
            <View className="gap-3">
              <TextInput
                className="border border-slate-200 dark:border-slate-700 rounded-xl px-4 py-3 text-slate-900 dark:text-white bg-slate-50 dark:bg-slate-800 text-base"
                placeholder="Email"
                placeholderTextColor="#94a3b8"
                autoCapitalize="none"
                keyboardType="email-address"
                value={email}
                onChangeText={setEmail}
              />
              <TextInput
                className="border border-slate-200 dark:border-slate-700 rounded-xl px-4 py-3 text-slate-900 dark:text-white bg-slate-50 dark:bg-slate-800 text-base"
                placeholder="Password"
                placeholderTextColor="#94a3b8"
                secureTextEntry
                value={password}
                onChangeText={setPassword}
              />

              <TouchableOpacity
                className="bg-brand-500 rounded-2xl py-4 items-center mt-2 active:opacity-80"
                onPress={handleEmailSignIn}
                disabled={loading}
              >
                {loading
                  ? <ActivityIndicator color="white" />
                  : <Text className="text-white text-base font-semibold">Sign In</Text>
                }
              </TouchableOpacity>
            </View>

            {/* Sign up link */}
            <TouchableOpacity
              className="py-6 items-center"
              onPress={() => router.replace('/(auth)/sign-up')}
            >
              <Text className="text-slate-500 dark:text-slate-400 text-sm">
                Don't have an account?{' '}
                <Text className="text-brand-500 font-semibold">Create one</Text>
              </Text>
            </TouchableOpacity>

          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
