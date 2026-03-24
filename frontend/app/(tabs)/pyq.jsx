import { useEffect, useState, useCallback } from 'react';
import {
  FlatList, Text, TouchableOpacity, View, ActivityIndicator,
  ScrollView, TextInput,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { supabase } from '@/lib/supabase';
import PyqCard from '@/components/PyqCard';

const FILTERS = ['All', 'Unattempted', 'Review', 'Mastered'];
const PAGE_SIZE = 10;

export default function PYQArenaScreen() {
  const [userId, setUserId]           = useState(null);
  const [subjects, setSubjects]       = useState([]);
  const [activeSub, setActiveSub]     = useState(null);  // { id, name }
  const [filter, setFilter]           = useState('All');
  const [search, setSearch]           = useState('');
  const [pyqs, setPyqs]               = useState([]);
  const [attempts, setAttempts]       = useState({}); // pyq_id -> rating
  const [loading, setLoading]         = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [page, setPage]               = useState(0);
  const [hasMore, setHasMore]         = useState(true);
  const [statsMap, setStatsMap]       = useState({}); // subjectId -> { total, attempted, mastered }

  /* ── 1. Boot: get user & subjects ── */
  useEffect(() => {
    (async () => {
      const { data: { user } } = await supabase.auth.getUser();
      setUserId(user?.id ?? null);

      let subIds = [];
      if (user) {
        const { data } = await supabase
          .from('user_subjects')
          .select('subject_id, subjects(id, name, icon)')
          .eq('user_id', user.id);
        let list = (data ?? []).map((r) => r.subjects).filter(Boolean);
        // Fallback: user signed up after anonymous onboarding — subjects may only be in AsyncStorage
        if (!list.length) {
          const raw = await AsyncStorage.getItem('anon_subject_ids');
          const ids = raw ? JSON.parse(raw) : [];
          if (ids.length) {
            const { data: subs } = await supabase.from('subjects').select('id, name, icon').in('id', ids);
            list = subs ?? [];
          }
        }
        setSubjects(list);
        subIds = list.map((s) => s.id);
        if (list.length) setActiveSub(list[0]);
      } else {
        // Anonymous: read from AsyncStorage
        const raw = await AsyncStorage.getItem('anon_subject_ids');
        const ids = raw ? JSON.parse(raw) : [];
        if (ids.length) {
          const { data } = await supabase.from('subjects').select('id, name, icon').in('id', ids);
          setSubjects(data ?? []);
          if (data?.length) setActiveSub(data[0]);
          subIds = ids;
        }
      }

      // Pre-fetch stats for all subjects
      if (user && subIds.length) {
        fetchStats(user.id, subIds);
      }

      setLoading(false);
    })();
  }, []);

  /* ── 2. Fetch per-subject stats (attempted / mastered counts) ── */
  async function fetchStats(uid, subIds) {
    const { data } = await supabase
      .from('pyq_attempts')
      .select('subject_id, rating')
      .eq('user_id', uid)
      .in('subject_id', subIds);

    const map = {};
    for (const row of (data ?? [])) {
      if (!map[row.subject_id]) map[row.subject_id] = { attempted: 0, mastered: 0 };
      map[row.subject_id].attempted++;
      if (row.rating === 'easy') map[row.subject_id].mastered++;
    }
    setStatsMap(map);
  }

  /* ── 3. Load PYQs when subject / filter / search changes ── */
  useEffect(() => {
    if (!activeSub) return;
    setPyqs([]);
    setPage(0);
    setHasMore(true);
    loadPage(0, activeSub.id, filter, search);
  }, [activeSub, filter, search]);

  async function loadPage(pageNum, subId, f, q) {
    if (pageNum === 0) setLoading(true); else setLoadingMore(true);

    const from = pageNum * PAGE_SIZE;
    const to   = from + PAGE_SIZE - 1;

    let rows = [];
    let attMap = {};

    if ((f === 'Review' || f === 'Mastered' || f === 'Unattempted') && userId) {
      // Server-side filter via pyq_attempts JOIN
      const ratingFilter = f === 'Review' ? 'hard' : f === 'Mastered' ? 'easy' : null;

      if (f === 'Unattempted') {
        // Get IDs the user HAS attempted, then exclude them
        const { data: attAll } = await supabase
          .from('pyq_attempts')
          .select('pyq_id, rating')
          .eq('user_id', userId)
          .eq('subject_id', subId);
        const attemptedIds = (attAll ?? []).map((a) => a.pyq_id);
        for (const a of (attAll ?? [])) attMap[a.pyq_id] = a.rating;

        let req = supabase
          .from('pyqs')
          .select('id, question_text, difficulty, year, marks, topic_id, subject_id')
          .eq('subject_id', subId)
          .order('frequency_score', { ascending: false })
          .range(from, to);
        if (attemptedIds.length) req = req.not('id', 'in', `(${attemptedIds.join(',')})`);
        if (q.trim().length > 2) req = req.textSearch('question_text', q.trim(), { type: 'websearch' });
        const { data } = await req;
        rows = data ?? [];
      } else {
        // Review or Mastered — fetch from pyq_attempts, then get pyq details
        const { data: attRows } = await supabase
          .from('pyq_attempts')
          .select('pyq_id, rating')
          .eq('user_id', userId)
          .eq('subject_id', subId)
          .eq('rating', ratingFilter)
          .range(from, to);
        const attemptRows = attRows ?? [];
        for (const a of attemptRows) attMap[a.pyq_id] = a.rating;

        if (attemptRows.length) {
          const ids = attemptRows.map((a) => a.pyq_id);
          let req = supabase
            .from('pyqs')
            .select('id, question_text, difficulty, year, marks, topic_id, subject_id')
            .in('id', ids)
            .order('frequency_score', { ascending: false });
          if (q.trim().length > 2) req = req.textSearch('question_text', q.trim(), { type: 'websearch' });
          const { data } = await req;
          rows = data ?? [];
        }
        // hasMore based on attempt count, not pyq count
        setHasMore(attemptRows.length === PAGE_SIZE);
      }
    } else {
      // All filter (or not logged in)
      let req = supabase
        .from('pyqs')
        .select('id, question_text, difficulty, year, marks, topic_id, subject_id')
        .eq('subject_id', subId)
        .order('frequency_score', { ascending: false })
        .range(from, to);
      if (q.trim().length > 2) req = req.textSearch('question_text', q.trim(), { type: 'websearch' });
      const { data } = await req;
      rows = data ?? [];

      // Fetch attempt statuses for these PYQs
      if (userId && rows.length) {
        const ids = rows.map((r) => r.id);
        const { data: attRows } = await supabase
          .from('pyq_attempts')
          .select('pyq_id, rating')
          .eq('user_id', userId)
          .in('pyq_id', ids);
        for (const a of (attRows ?? [])) attMap[a.pyq_id] = a.rating;
      }
      setHasMore(rows.length === PAGE_SIZE);
    }

    setAttempts((prev) => ({ ...prev, ...attMap }));
    setPyqs((prev) => (pageNum === 0 ? rows : [...prev, ...rows]));
    setPage(pageNum + 1);

    if (pageNum === 0) setLoading(false); else setLoadingMore(false);
  }

  const loadMore = useCallback(() => {
    if (!hasMore || loadingMore || loading) return;
    loadPage(page, activeSub.id, filter, search);
  }, [page, hasMore, loadingMore, loading, activeSub, filter, search]);

  /* ── 4. Render ── */
  if (!subjects.length && !loading) {
    return (
      <SafeAreaView style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}
        className="bg-white dark:bg-slate-900">
        <Text className="text-slate-400 text-base text-center px-8">
          Complete onboarding to choose subjects, then come back to practise PYQs!
        </Text>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={{ flex: 1 }} className="bg-white dark:bg-slate-900">

      {/* ── Header ── */}
      <View className="px-6 pt-5 pb-3" style={{ maxWidth: 700, width: '100%', alignSelf: 'center' }}>
        <Text className="text-2xl font-bold text-slate-900 dark:text-white">📝 PYQ Practice</Text>
        <Text className="text-slate-400 text-sm mt-0.5">Practise by subject · track your progress</Text>
      </View>

      {/* ── Subject Pill Selector ── */}
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={{ paddingHorizontal: 24, gap: 10, paddingBottom: 4 }}
        style={{ flexGrow: 0 }}
      >
        {subjects.map((s) => {
          const st = statsMap[s.id];
          const isActive = activeSub?.id === s.id;
          return (
            <TouchableOpacity
              key={s.id}
              onPress={() => setActiveSub(s)}
              className={`px-4 py-2 rounded-2xl border ${
                isActive
                  ? 'bg-brand-500 border-brand-500'
                  : 'bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700'
              }`}
            >
              <Text className={`font-semibold text-sm ${isActive ? 'text-white' : 'text-slate-700 dark:text-slate-300'}`}>
                {s.icon ?? '📖'} {s.name}
              </Text>
              {st && (
                <Text className={`text-xs mt-0.5 ${isActive ? 'text-orange-100' : 'text-slate-400'}`}>
                  {st.mastered}/{st.attempted} mastered
                </Text>
              )}
            </TouchableOpacity>
          );
        })}
      </ScrollView>

      {/* ── Filters + Search ── */}
      <View style={{ maxWidth: 700, width: '100%', alignSelf: 'center', paddingHorizontal: 24, marginTop: 12, gap: 10 }}>
        {/* Status filter chips */}
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8 }}>
          {FILTERS.map((f) => (
            <TouchableOpacity
              key={f}
              onPress={() => setFilter(f)}
              className={`px-3 py-1.5 rounded-full border ${
                filter === f
                  ? 'bg-slate-800 dark:bg-white border-slate-800 dark:border-white'
                  : 'bg-transparent border-slate-300 dark:border-slate-600'
              }`}
            >
              <Text className={`text-xs font-semibold ${
                filter === f ? 'text-white dark:text-slate-900' : 'text-slate-500 dark:text-slate-400'
              }`}>{f}</Text>
            </TouchableOpacity>
          ))}
        </ScrollView>

        {/* Search bar */}
        <TextInput
          className="border border-slate-200 dark:border-slate-700 rounded-xl px-4 py-2.5 text-slate-900 dark:text-white bg-slate-50 dark:bg-slate-800 text-sm"
          placeholder="Search by keyword…"
          placeholderTextColor="#94a3b8"
          value={search}
          onChangeText={setSearch}
          returnKeyType="search"
        />
      </View>

      {/* ── PYQ Feed ── */}
      {loading ? (
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
          <ActivityIndicator color="#f97316" size="large" />
        </View>
      ) : (
        <FlatList
          style={{ flex: 1 }}
          contentContainerStyle={{
            paddingHorizontal: 24, paddingTop: 14, paddingBottom: 40, gap: 12,
            maxWidth: 700, alignSelf: 'center', width: '100%',
          }}
          data={pyqs}
          keyExtractor={(item) => item.id}
          onEndReached={loadMore}
          onEndReachedThreshold={0.3}
          renderItem={({ item }) => (
            <PyqCard
              pyq={item}
              topicId={item.topic_id}
              subjectId={item.subject_id}
              initialAttempt={attempts[item.id] ?? null}
            />
          )}
          ListEmptyComponent={
            <Text className="text-center text-slate-400 mt-16 px-8">
              {filter === 'Mastered'
                ? '🎉 No mastered questions yet — keep practising!'
                : filter === 'Review'
                ? '✅ Nothing marked for review — great job!'
                : 'No questions match your search.'}
            </Text>
          }
          ListFooterComponent={
            loadingMore
              ? <ActivityIndicator color="#f97316" style={{ marginTop: 16 }} />
              : hasMore ? null
              : pyqs.length > 0
                ? <Text className="text-center text-slate-400 text-xs mt-4">— End of results —</Text>
                : null
          }
        />
      )}
    </SafeAreaView>
  );
}
