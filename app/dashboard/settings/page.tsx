"use client";

import { useEffect, useState } from "react";
import { User, Bell } from "lucide-react";
import { supabase } from "../../../lib/supabase/client";

export default function SettingsPage() {
  const [user, setUser] = useState<{ email: string; name: string } | null>(null);

  useEffect(() => {
    supabase.auth.getUser().then((response: any) => {
      const { data } = response;
      if (data?.user) {
        setUser({
          email: data.user.email || "",
          name: data.user.user_metadata?.full_name || "User",
        });
      }
    });
  }, []);

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-black tracking-tighter text-white">Settings</h1>

      <div className="grid gap-6 md:grid-cols-2">
        {/* Account Information */}
        <section className="rounded-3xl border border-white/5 bg-[#111827] p-6 shadow-xl">
          <div className="mb-4 flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-500/20 text-blue-400">
              <User size={20} />
            </div>
            <h2 className="text-lg font-bold text-white">Account Information</h2>
          </div>

          <div className="space-y-4">
            <div>
              <label className="text-xs font-bold uppercase text-gray-500">Full Name</label>
              <p className="font-medium text-white">{user?.name || "Loading..."}</p>
            </div>
            <div>
              <label className="text-xs font-bold uppercase text-gray-500">Email Address</label>
              <p className="font-medium text-white">{user?.email || "Loading..."}</p>
            </div>
            <div className="pt-2">
              <button className="text-sm font-bold text-blue-400 hover:text-blue-300">Edit Profile</button>
            </div>
          </div>
        </section>

        {/* Preferences (Placeholder) */}
        <section className="rounded-3xl border border-white/5 bg-[#111827] p-6 shadow-xl">
          <div className="mb-4 flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-purple-500/20 text-purple-400">
              <Bell size={20} />
            </div>
            <h2 className="text-lg font-bold text-white">Preferences</h2>
          </div>
          <p className="text-sm text-gray-400">Notification settings coming soon.</p>
        </section>
      </div>
    </div>
  );
}
