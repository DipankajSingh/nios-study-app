import { Platform, AppState } from 'react-native';
import 'react-native-url-polyfill/auto';
import { createClient } from '@supabase/supabase-js';

// Local Docker Supabase instance
const supabaseUrl = 'http://127.0.0.1:54321';
const supabaseAnonKey = 'sb_publishable_ACJWlzQHlZjBrEguHvfOxg_3BJgxAaH';

// On web we use localStorage directly (works in browser and skips in SSR).
// On native we use AsyncStorage.
function buildStorage() {
  if (Platform.OS === 'web') {
    // Gracefully degrade when running in Node SSR context (no window)
    if (typeof window === 'undefined') return undefined;
    return {
      getItem: (key) => Promise.resolve(window.localStorage.getItem(key)),
      setItem: (key, value) => { window.localStorage.setItem(key, value); return Promise.resolve(); },
      removeItem: (key) => { window.localStorage.removeItem(key); return Promise.resolve(); },
    };
  }
  // Native: lazy-require to avoid SSR issues
  const AsyncStorage = require('@react-native-async-storage/async-storage').default;
  return AsyncStorage;
}

export const supabase = createClient(supabaseUrl, supabaseAnonKey, {
  auth: {
    storage: buildStorage(),
    autoRefreshToken: true,
    persistSession: true,
    detectSessionInUrl: Platform.OS === 'web',
  },
});

// Only manage AppState refresh on native (no AppState on web)
if (Platform.OS !== 'web') {
  AppState.addEventListener('change', (state) => {
    if (state === 'active') {
      supabase.auth.startAutoRefresh();
    } else {
      supabase.auth.stopAutoRefresh();
    }
  });
}

