import { useEffect, useState } from 'react';
import { FlatList, Text, TouchableOpacity, View, ActivityIndicator, TextInput } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { supabase } from '@/lib/supabase';

export default function PYQScreen() {
  const [pyqs, setPyqs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [subjectIds, setSubjectIds] = useState([]);

  useEffect(() => {
    async function fetchUserSubjects() {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) return;
      const { data } = await supabase
        .from('user_subjects')
        .select('subject_id')
        .eq('user_id', user.id);
      const ids = (data ?? []).map((s) => s.subject_id);
      setSubjectIds(ids);
      fetchPyqs(ids, '');
    }
    fetchUserSubjects();
  }, []);

  async function fetchPyqs(ids, query) {
    setLoading(true);
    let req = supabase
      .from('pyqs')
      .select('id, question_text, year, marks, difficulty, subject_id, subjects(name)')
      .in('subject_id', ids)
      .limit(30);

    if (query.trim().length > 2) {
      req = req.textSearch('question_text', query.trim(), { type: 'websearch' });
    }

    const { data } = await req;
    setPyqs(data ?? []);
    setLoading(false);
  }

  function handleSearch(text) {
    setSearch(text);
    fetchPyqs(subjectIds, text);
  }

  const diffColor = { easy: 'text-green-500', medium: 'text-yellow-500', hard: 'text-red-500' };

  return (
    <SafeAreaView className="flex-1 bg-white dark:bg-slate-900">
      <View className="px-6 pt-6 gap-3">
        <Text className="text-2xl font-bold text-slate-900 dark:text-white">Previous Year Q's 📝</Text>
        {/* Full Text Search */}
        <TextInput
          className="border border-slate-200 dark:border-slate-700 rounded-xl px-4 py-3 text-slate-900 dark:text-white bg-slate-50 dark:bg-slate-800"
          placeholder="Search by keyword..."
          placeholderTextColor="#94a3b8"
          value={search}
          onChangeText={handleSearch}
        />
      </View>

      {loading ? (
        <View className="flex-1 items-center justify-center">
          <ActivityIndicator color="#f97316" size="large" />
        </View>
      ) : (
        <FlatList
          className="flex-1 mt-4"
          data={pyqs}
          keyExtractor={(item) => item.id}
          contentContainerClassName="px-6 gap-4 pb-10"
          renderItem={({ item }) => (
            <View className="bg-slate-50 dark:bg-slate-800 rounded-2xl p-4 gap-2">
              <View className="flex-row items-center gap-2 flex-wrap">
                <View className="bg-slate-200 dark:bg-slate-700 rounded-lg px-2 py-0.5">
                  <Text className="text-xs text-slate-600 dark:text-slate-300 font-semibold">{item.subjects?.name}</Text>
                </View>
                <View className="bg-slate-200 dark:bg-slate-700 rounded-lg px-2 py-0.5">
                  <Text className="text-xs text-slate-500 dark:text-slate-400">{item.year}</Text>
                </View>
                <Text className={`text-xs font-semibold ${diffColor[item.difficulty] ?? 'text-slate-400'}`}>
                  {item.difficulty}
                </Text>
                <Text className="text-xs text-slate-400 ml-auto">{item.marks}M</Text>
              </View>
              <Text className="text-sm text-slate-800 dark:text-slate-200 leading-5">{item.question_text}</Text>
            </View>
          )}
          ListEmptyComponent={
            <Text className="text-center text-slate-400 mt-10">No PYQs found. Try a different keyword.</Text>
          }
        />
      )}
    </SafeAreaView>
  );
}
