import { DarkTheme, DefaultTheme, ThemeProvider } from '@react-navigation/native';
import { Stack, useRouter, useSegments } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useEffect, useState } from 'react';
import { ActivityIndicator, View } from 'react-native';
import 'react-native-reanimated';
import '../global.css';

import { supabase } from '@/lib/supabase';
import { useColorScheme } from '@/hooks/use-color-scheme';

function AuthGate({ children }) {
  const router = useRouter();
  const segments = useSegments();
  const [session, setSession] = useState(undefined); // undefined = loading

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session);
    });
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session);
    });
    return () => subscription.unsubscribe();
  }, []);

  useEffect(() => {
    if (session === undefined) return; // still loading

    const inAuthGroup = segments[0] === '(auth)';
    const inOnboarding = segments[0] === '(onboarding)';
    const inTabs = segments[0] === '(tabs)';

    // If authenticated user is still in auth/onboarding screens → push to main app
    if (session && (inAuthGroup || inOnboarding)) {
      router.replace('/(tabs)/home');
      return;
    }

    // Unauthenticated users are allowed in:
    //   (auth) → normal flow
    //   (onboarding) → they chose to skip login
    //   (tabs) → they completed onboarding without logging in
    //   subject / topic → drill-down screens reachable from (tabs)
    const inSubject = segments[0] === 'subject';
    const inTopic = segments[0] === 'topic';
    const inSettings = segments[0] === '(tabs)'; // settings is inside (tabs)
    if (!session && !inAuthGroup && !inOnboarding && !inTabs && !inSubject && !inTopic) {
      router.replace('/(auth)/welcome');
    }
  }, [session, segments]);

  if (session === undefined) {
    return (
      <View className="flex-1 items-center justify-center bg-white dark:bg-slate-900">
        <ActivityIndicator size="large" color="#f97316" />
      </View>
    );
  }

  return children;
}

export default function RootLayout() {
  const { colorScheme } = useColorScheme();

  return (
    <ThemeProvider value={colorScheme === 'dark' ? DarkTheme : DefaultTheme}>
      <AuthGate>
        <Stack screenOptions={{ headerShown: false }}>
          <Stack.Screen name="(auth)" />
          <Stack.Screen name="(onboarding)" />
          <Stack.Screen name="(tabs)" />
        </Stack>
      </AuthGate>
      <StatusBar style="auto" />
    </ThemeProvider>
  );
}
