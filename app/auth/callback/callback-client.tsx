"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Loader2 } from "lucide-react";
import { supabase } from "../../../lib/supabase/client";

export function CallbackClient() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [error, setError] = useState<string | null>(null);

  const nextPath = useMemo(() => {
    const next = searchParams.get("next");
    return next && next.startsWith("/") ? next : "/dashboard";
  }, [searchParams]);

  useEffect(() => {
    const completeAuth = async () => {
      const authError = searchParams.get("error_description") || searchParams.get("error");
      if (authError) {
        const { data } = await supabase.auth.getSession();
        if (data.session) {
          router.replace(nextPath);
          return;
        }

        setError(authError);
        return;
      }

      const code = searchParams.get("code");
      if (code) {
        const { error: exchangeError } = await supabase.auth.exchangeCodeForSession(code);
        if (exchangeError) {
          const { data } = await supabase.auth.getSession();
          if (data.session) {
            router.replace(nextPath);
            return;
          }

          setError(exchangeError.message);
          return;
        }
      }

      const { data } = await supabase.auth.getSession();
      if (!data.session) {
        setError("Authentication session not found. Please try logging in again.");
        return;
      }

      router.replace(nextPath);
    };

    completeAuth();
  }, [nextPath, router, searchParams]);

  if (error) {
    return (
      <main className="min-h-screen bg-background text-white flex items-center justify-center px-6">
        <div className="w-full max-w-md rounded-2xl border border-red-500/40 bg-red-500/10 p-6">
          <h1 className="text-xl font-bold mb-3">Google sign-in failed</h1>
          <p className="text-sm text-red-200 mb-4">{error}</p>
          <button
            type="button"
            onClick={() => router.replace("/login")}
            className="px-4 py-2 rounded-lg bg-white text-black font-semibold"
          >
            Back to Login
          </button>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-background text-white flex flex-col items-center justify-center gap-3">
      <Loader2 className="w-8 h-8 animate-spin text-primary" />
      <p className="text-sm text-gray-300">Completing sign-in...</p>
    </main>
  );
}
