"use client";

import { useEffect, useState } from "react";
import { User, AlertTriangle, Loader2, Moon, Sun, Download, FileText, ChevronRight } from "lucide-react";
import { supabase } from "../../../lib/supabase/client";
import { useTheme } from "next-themes";

type Transaction = {
  id: string;
  description: string;
  amount: number;
  transaction_date: string;
  category: string;
  type?: string;
  merchant_name?: string;
};

export default function SettingsPage() {
  const [user, setUser] = useState<{ id: string; email: string; name: string } | null>(null);
  const [loading, setLoading] = useState(true);

  // Modals & States
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deletingData, setDeletingData] = useState(false);

  const [isEditingProfile, setIsEditingProfile] = useState(false);
  const [newName, setNewName] = useState("");
  const [savingProfile, setSavingProfile] = useState(false);

  const [exporting, setExporting] = useState(false);

  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    (async () => {
      const { data } = await supabase.auth.getUser();
      if (data?.user) {
        setUser({
          id: data.user.id,
          email: data.user.email || "",
          name: data.user.user_metadata?.full_name || "User",
        });
        setNewName(data.user.user_metadata?.full_name || "");
      }
      setLoading(false);
    })();
  }, []);

  // --- Handlers ---

  const handleUpdateProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newName.trim()) return;

    setSavingProfile(true);
    setError(null);
    setMessage(null);

    try {
      const { error } = await supabase.auth.updateUser({
        data: { full_name: newName }
      });

      if (error) throw error;

      setUser(prev => prev ? { ...prev, name: newName } : null);
      setMessage("Profile updated successfully.");
      setIsEditingProfile(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update profile.");
    } finally {
      setSavingProfile(false);
    }
  };

  const handleExportData = async () => {
    if (!user?.id) return;
    setExporting(true);
    try {
      const { data: txsd, error } = await supabase
        .from("transactions")
        .select("*")
        .eq("user_id", user.id)
        .order("transaction_date", { ascending: false });

      if (error) throw error;

      if (!txsd || txsd.length === 0) {
        setError("No transactions found to export.");
        return;
      }

      const transactions = txsd as Transaction[];

      // Convert to CSV
      const headers = ["Date", "Description", "Amount", "Category", "Merchant", "Type"];
      const csvContent = [
        headers.join(","),
        ...transactions.map(tx => [
          tx.transaction_date,
          `"${(tx.description || "").replace(/"/g, '""')}"`,
          tx.amount,
          tx.category,
          `"${(tx.merchant_name || "").replace(/"/g, '""')}"`,
          tx.type || "expense"
        ].join(","))
      ].join("\n");

      const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", `spendsmart_export_${new Date().toISOString().split('T')[0]}.csv`);
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);

      setMessage("Data exported successfully.");
    } catch (err) {
      setError("Failed to export data.");
      console.error(err);
    } finally {
      setExporting(false);
    }
  };

  const handleDeleteAllData = async () => {
    if (!user?.id) {
      setError("Unable to verify account. Please sign in again.");
      return;
    }

    setDeletingData(true);
    setError(null);
    setMessage(null);

    try {
      const { error: deleteError } = await supabase
        .from("transactions")
        .delete()
        .eq("user_id", user.id);

      if (deleteError) throw deleteError;

      sessionStorage.removeItem(`overview-cache:${user.id}`);
      sessionStorage.removeItem(`transactions-cache:${user.id}`);

      setMessage("All your transaction data has been permanently deleted.");
      setShowDeleteConfirm(false);
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : "Failed to delete data.");
    } finally {
      setDeletingData(false);
    }
  };

  if (loading) return <div className="flex h-full items-center justify-center"><Loader2 className="animate-spin text-primary" /></div>;

  return (
    <div className="space-y-6 max-w-4xl mx-auto pb-10">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-black tracking-tighter text-foreground">Settings</h1>
          <p className="text-muted-foreground text-sm">Manage your account preferences and data.</p>
        </div>
      </div>

      {message && (
        <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-500 font-medium">
          {message}
        </div>
      )}

      {error && (
        <div className="rounded-xl border border-destructive/20 bg-destructive/10 px-4 py-3 text-sm text-destructive font-medium">
          {error}
        </div>
      )}

      <div className="grid gap-6 md:grid-cols-2">
        {/* Account Information */}
        <section className="rounded-3xl border border-border bg-card p-6 shadow-xl relative overflow-hidden">
          <div className="relative z-10">
            <div className="mb-6 flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-500/10 text-blue-500">
                <User size={20} />
              </div>
              <h2 className="text-lg font-bold text-foreground">Profile</h2>
            </div>

            {isEditingProfile ? (
              <form onSubmit={handleUpdateProfile} className="space-y-4">
                <div>
                  <label className="text-xs font-bold uppercase text-muted-foreground mb-1 block">Full Name</label>
                  <input
                    type="text"
                    value={newName}
                    onChange={(e) => setNewName(e.target.value)}
                    className="w-full rounded-xl bg-muted/50 border border-border px-3 py-2 text-foreground focus:outline-none focus:ring-2 focus:ring-primary/50"
                  />
                </div>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => setIsEditingProfile(false)}
                    className="px-4 py-2 rounded-xl text-sm font-medium text-muted-foreground hover:bg-muted transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={savingProfile}
                    className="px-4 py-2 rounded-xl text-sm font-bold bg-primary text-primary-foreground hover:opacity-90 transition-opacity flex items-center gap-2"
                  >
                    {savingProfile && <Loader2 size={14} className="animate-spin" />}
                    Save Changes
                  </button>
                </div>
              </form>
            ) : (
              <div className="space-y-4">
                <div className="group cursor-pointer" onClick={() => setIsEditingProfile(true)}>
                  <label className="text-xs font-bold uppercase text-muted-foreground group-hover:text-primary transition-colors">Full Name</label>
                  <div className="flex justify-between items-center">
                    <p className="font-medium text-foreground text-lg">{user?.name || "User"}</p>
                    <ChevronRight size={16} className="text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
                  </div>
                </div>
                <div>
                  <label className="text-xs font-bold uppercase text-muted-foreground">Email Address</label>
                  <p className="font-medium text-foreground/80">{user?.email}</p>
                </div>
                <div className="pt-2">
                  <button
                    onClick={() => setIsEditingProfile(true)}
                    className="text-sm font-bold text-primary hover:underline decoration-2 underline-offset-4"
                  >
                    Edit Profile
                  </button>
                </div>
              </div>
            )}
          </div>
        </section>

        {/* Appearance & Preferences */}
        <div className="space-y-6">
          <section className="rounded-3xl border border-border bg-card p-6 shadow-xl">
            <div className="mb-4 flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-purple-500/10 text-purple-500">
                <Sun size={20} />
              </div>
              <h2 className="text-lg font-bold text-foreground">Appearance</h2>
            </div>

            <div className="flex items-center justify-between p-3 rounded-2xl bg-muted/30 border border-transparent hover:border-border transition-colors">
              <div className="flex items-center gap-3">
                <div className={`w-8 h-8 rounded-full flex items-center justify-center ${theme === 'dark' ? 'bg-indigo-500/20 text-indigo-400' : 'bg-orange-500/20 text-orange-500'}`}>
                  {mounted && theme === 'dark' ? <Moon size={14} /> : <Sun size={14} />}
                </div>
                <div>
                  <p className="font-bold text-sm text-foreground">Theme Mode</p>
                  <p className="text-xs text-muted-foreground">Switch between light and dark</p>
                </div>
              </div>
              <button
                onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
                className="px-4 py-2 rounded-xl bg-background border border-border text-xs font-bold shadow-sm hover:bg-muted transition-colors"
              >
                {mounted && theme === 'dark' ? 'Dark' : 'Light'}
              </button>
            </div>
          </section>

          <section className="rounded-3xl border border-border bg-card p-6 shadow-xl">
            <div className="mb-4 flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-500/10 text-emerald-500">
                <FileText size={20} />
              </div>
              <h2 className="text-lg font-bold text-foreground">Data Management</h2>
            </div>

            <button
              onClick={handleExportData}
              disabled={exporting}
              className="w-full flex items-center justify-between p-3 rounded-2xl bg-muted/30 border border-transparent hover:border-emerald-500/30 hover:bg-emerald-500/5 group transition-all"
            >
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-full bg-emerald-500/10 text-emerald-500 flex items-center justify-center group-hover:scale-110 transition-transform">
                  <Download size={14} />
                </div>
                <div className="text-left">
                  <p className="font-bold text-sm text-foreground group-hover:text-emerald-500 transition-colors">Export CSV</p>
                  <p className="text-xs text-muted-foreground">Download your transaction history</p>
                </div>
              </div>
              {exporting && <Loader2 size={16} className="animate-spin text-emerald-500" />}
            </button>
          </section>
        </div>
      </div>

      <section className="rounded-3xl border border-destructive/20 bg-destructive/5 p-6 shadow-xl mt-8">
        <div className="mb-6 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-destructive/10 text-destructive">
            <AlertTriangle size={20} />
          </div>
          <div>
            <h2 className="text-lg font-bold text-destructive">Danger Zone</h2>
            <p className="text-sm text-destructive/70">Irreversible actions regarding your data.</p>
          </div>
        </div>

        <div className="flex items-center justify-between p-4 rounded-2xl border border-destructive/10 bg-background/50">
          <div>
            <p className="font-bold text-sm text-foreground">Delete All Financial Data</p>
            <p className="text-xs text-muted-foreground">Delete all transactions but keep your account.</p>
          </div>
          <button
            type="button"
            onClick={() => setShowDeleteConfirm(true)}
            className="rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-2 text-xs font-bold text-destructive hover:bg-destructive/20 transition-colors"
          >
            Delete Data
          </button>
        </div>
      </section>

      {showDeleteConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <button
            type="button"
            onClick={() => (deletingData ? null : setShowDeleteConfirm(false))}
            className="absolute inset-0 bg-background/80 backdrop-blur-sm"
            aria-label="Close confirmation"
          />

          <div className="relative w-full max-w-md rounded-2xl border border-destructive/30 bg-card p-6 shadow-2xl animate-in fade-in zoom-in-95 duration-200">
            <div className="mb-4 flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-destructive/10 text-destructive">
                <AlertTriangle size={20} />
              </div>
              <h3 className="text-lg font-black text-foreground">Delete All Data?</h3>
            </div>

            <p className="text-sm text-muted-foreground">
              This will permanently delete all your transactions. This action cannot be undone.
            </p>

            <div className="mt-6 flex justify-end gap-3">
              <button
                type="button"
                onClick={() => setShowDeleteConfirm(false)}
                disabled={deletingData}
                className="rounded-xl border border-border bg-muted/50 px-4 py-2 text-sm font-semibold text-muted-foreground hover:bg-muted disabled:opacity-60"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleDeleteAllData}
                disabled={deletingData}
                className="inline-flex items-center gap-2 rounded-xl bg-destructive px-4 py-2 text-sm font-bold text-destructive-foreground hover:opacity-90 disabled:opacity-60"
              >
                {deletingData ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                {deletingData ? "Deleting..." : "Yes, Delete Permanently"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
