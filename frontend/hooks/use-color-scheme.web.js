import { useState, useEffect, useCallback } from 'react';
import { useColorScheme as useRNColorScheme } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';

const THEME_KEY = 'app_theme_override';

function applyTheme(effective) {
  if (typeof document === 'undefined') return;
  if (effective === 'dark') {
    document.documentElement.classList.add('dark');
  } else {
    document.documentElement.classList.remove('dark');
  }
}

export function useColorScheme() {
  const systemScheme = useRNColorScheme() ?? 'light';
  const [override, setOverride] = useState('system');
  const [hasHydrated, setHasHydrated] = useState(false);

  // Load persisted preference on mount
  useEffect(() => {
    AsyncStorage.getItem(THEME_KEY).then((val) => {
      const saved = val === 'light' || val === 'dark' || val === 'system' ? val : 'system';
      setOverride(saved);
      setHasHydrated(true);
      applyTheme(saved === 'system' ? systemScheme : saved);
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Keep DOM in sync whenever override or systemScheme changes
  useEffect(() => {
    if (!hasHydrated) return;
    applyTheme(override === 'system' ? systemScheme : override);
  }, [override, systemScheme, hasHydrated]);

  const setTheme = useCallback(async (value) => {
    setOverride(value); // triggers re-render → useEffect above syncs DOM
    await AsyncStorage.setItem(THEME_KEY, value);
  }, []);

  const colorScheme = (override === 'system' ? systemScheme : override) ?? 'light';

  return {
    colorScheme: hasHydrated ? colorScheme : 'light',
    override,
    setTheme,
  };
}
