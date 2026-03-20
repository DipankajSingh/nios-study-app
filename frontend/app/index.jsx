import { Redirect } from 'expo-router';

// The root "/" automatically redirects to the auth welcome screen.
// The root layout's AuthGate will handle redirecting to onboarding or tabs
// based on actual auth state once the Supabase session is loaded.
export default function Index() {
  return <Redirect href="/(auth)/welcome" />;
}
