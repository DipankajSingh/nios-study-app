import { useState, useCallback } from 'react';
import { useColorScheme as useRNColorScheme, Appearance } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';

const THEME_KEY = 'app_theme_override';

export function useColorScheme() {
  const [override, setOverride] = useState('system');
  const systemScheme = useRNColorScheme();

  const setTheme = useCallback(async (value) => {
    setOverride(value);
    await AsyncStorage.setItem(THEME_KEY, value);
    Appearance.setColorScheme(value === 'system' ? null : value);
  }, []);

  const colorScheme = override === 'system' ? systemScheme : override;

  return { colorScheme: colorScheme ?? 'light', override, setTheme };
}
