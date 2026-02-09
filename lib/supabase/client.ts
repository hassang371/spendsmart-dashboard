import { createBrowserClient } from "@supabase/ssr";

function getPublicEnvVar(value: string | undefined, name: string): string {
  if (!value) {
    throw new Error(
      `Supabase not configured: missing ${name} environment variable. ` +
      `Please create a .env.local file in the dashboard directory with NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY.`
    );
  }
  return value;
}

let supabaseUrl: string;
let supabaseAnonKey: string;

try {
  supabaseUrl = getPublicEnvVar(
    process.env.NEXT_PUBLIC_SUPABASE_URL,
    "NEXT_PUBLIC_SUPABASE_URL",
  );
  supabaseAnonKey = getPublicEnvVar(
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY,
    "NEXT_PUBLIC_SUPABASE_ANON_KEY",
  );
} catch (e) {
  const message = e instanceof Error ? e.message : "Supabase not configured.";
  if (typeof window !== "undefined") {
    const container = document.createElement("div");
    container.style.cssText = "display:flex;align-items:center;justify-content:center;height:100vh;font-family:system-ui;padding:2rem;text-align:center";
    const inner = document.createElement("div");
    const h1 = document.createElement("h1");
    h1.style.cssText = "color:#e11d48;margin-bottom:1rem";
    h1.textContent = "Configuration Error";
    const p = document.createElement("p");
    p.textContent = message;
    inner.appendChild(h1);
    inner.appendChild(p);
    container.appendChild(inner);
    document.body.replaceChildren(container);
  }
  throw e;
}

let browserClient: ReturnType<typeof createBrowserClient> | null = null;

export function getBrowserSupabaseClient() {
  if (!browserClient) {
    browserClient = createBrowserClient(supabaseUrl, supabaseAnonKey);
  }
  return browserClient;
}

export const supabase = getBrowserSupabaseClient();
