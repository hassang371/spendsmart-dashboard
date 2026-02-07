"use client";

import { useState } from "react";
import { LogOut, Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { supabase } from "../../../lib/supabase/client";

export default function SettingsPage() {
  const router = useRouter();
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleLogout = async () => {
    setIsLoggingOut(true);
    setError(null);
    const { error: signOutError } = await supabase.auth.signOut();
    setIsLoggingOut(false);

    if (signOutError) {
      setError(signOutError.message);
      return;
    }

    router.replace("/login");
  };

  return (
    <div className="space-y-4">
      {error && <div className="rounded-2xl border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-200">{error}</div>}

      <div className="rounded-3xl border border-white/10 bg-secondary/70 p-8">
        <h2 className="text-3xl font-black text-white">Settings</h2>
        <p className="mt-2 text-sm text-gray-400">Account and session controls.</p>

        <div className="mt-6 rounded-2xl border border-white/10 bg-background/70 p-5">
          <h3 className="text-lg font-bold text-white">Session</h3>
          <p className="mt-1 text-sm text-gray-400">Sign out from this device securely.</p>

          <button
            type="button"
            onClick={handleLogout}
            disabled={isLoggingOut}
            className="mt-4 inline-flex items-center gap-2 rounded-xl bg-red-500 px-4 py-2 text-sm font-semibold text-white transition hover:bg-red-600 disabled:cursor-not-allowed disabled:opacity-70"
          >
            {isLoggingOut ? <Loader2 className="h-4 w-4 animate-spin" /> : <LogOut className="h-4 w-4" />}
            {isLoggingOut ? "Logging out..." : "Log out"}
          </button>
        </div>
      </div>
    </div>
  );
}
