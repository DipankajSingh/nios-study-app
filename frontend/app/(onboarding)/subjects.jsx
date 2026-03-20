import { useEffect, useState } from 'react';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { FlatList, Text, TouchableOpacity, View, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { supabase } from '@/lib/supabase';

export default function SubjectsScreen() {
  const router = useRouter();
  const { classLevel } = useLocalSearchParams();

  const [subjects, setSubjects] = useState([]);
  const [selected, setSelected] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchSubjects() {
      const { data, error } = await supabase
        .from('subjects')
        .select('id, name')
        .eq('class_level', classLevel);
      if (!error) setSubjects(data ?? []);
      setLoading(false);
    }
    fetchSubjects();
  }, [classLevel]);

  function toggleSubject(id) {
    setSelected((prev) =>
      prev.includes(id) ? prev.filter((s) => s !== id) : [...prev, id]
    );
  }

  return (
    <SafeAreaView style={{ flex: 1 }} className="bg-white dark:bg-slate-900">
      <View className="w-full self-center flex-1" style={{ maxWidth: 520 }}>

        <View className="px-6">
          {/* Progress: 2 of 3 */}
          <View className="flex-row gap-2 pt-6">
            {[1, 2, 3].map((step) => (
              <View key={step} className={`h-1 flex-1 rounded-full ${step <= 2 ? 'bg-brand-500' : 'bg-slate-200 dark:bg-slate-700'}`} />
            ))}
          </View>

          <View className="pt-10 gap-2 pb-4">
            <Text className="text-2xl font-bold text-slate-900 dark:text-white">Pick your subjects</Text>
            <Text className="text-slate-500 dark:text-slate-400">Select all subjects you're studying for Class {classLevel}.</Text>
          </View>
        </View>

        {loading ? (
          <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
            <ActivityIndicator color="#f97316" />
          </View>
        ) : (
          <FlatList
            style={{ flex: 1 }}
            data={subjects}
            keyExtractor={(item) => item.id}
            contentContainerStyle={{ gap: 12, paddingBottom: 16, paddingHorizontal: 24 }}
            renderItem={({ item }) => {
              const isSelected = selected.includes(item.id);
              return (
                <TouchableOpacity
                  className={`border-2 rounded-2xl px-5 py-4 flex-row items-center justify-between ${
                    isSelected ? 'border-brand-500 bg-brand-50' : 'border-slate-200 dark:border-slate-700'
                  }`}
                  onPress={() => toggleSubject(item.id)}
                >
                  <Text className={`text-base font-semibold ${isSelected ? 'text-brand-600' : 'text-slate-900 dark:text-white'}`}>
                    {item.name}
                  </Text>
                  {isSelected && <Text className="text-brand-500 text-lg">✓</Text>}
                </TouchableOpacity>
              );
            }}
          />
        )}

        <TouchableOpacity
          className={`rounded-2xl py-4 items-center mb-8 mt-2 mx-6 ${selected.length > 0 ? 'bg-brand-500 active:opacity-80' : 'bg-slate-200 dark:bg-slate-700'}`}
          disabled={selected.length === 0}
          onPress={() =>
            router.push({
              pathname: '/(onboarding)/goals',
              params: { classLevel, subjectIds: JSON.stringify(selected) },
            })
          }
        >
          <Text className={`text-base font-semibold ${selected.length > 0 ? 'text-white' : 'text-slate-400'}`}>Next →</Text>
        </TouchableOpacity>

      </View>
    </SafeAreaView>
  );
}
