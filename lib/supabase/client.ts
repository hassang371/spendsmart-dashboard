import { createBrowserClient } from "@supabase/ssr";

function getPublicEnvVar(value: string | undefined, name: string): string {
  if (!value) {
    throw new Error(`Missing ${name} environment variable.`);
  }
  return value;
}

const supabaseUrl = getPublicEnvVar(
  process.env.NEXT_PUBLIC_SUPABASE_URL,
  "NEXT_PUBLIC_SUPABASE_URL",
);
const supabaseAnonKey = getPublicEnvVar(
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY,
  "NEXT_PUBLIC_SUPABASE_ANON_KEY",
);

let browserClient: ReturnType<typeof createBrowserClient> | null = null;

export function getBrowserSupabaseClient() {
  if (!browserClient) {
    browserClient = createBrowserClient(supabaseUrl, supabaseAnonKey);
  }
  return browserClient;
}

export const supabase = getBrowserSupabaseClient();
