"use client";

import { useEffect, useState } from "react";
import { User, AlertTriangle, Loader2, Moon, Sun, Download, FileText, ChevronRight, Check, X } from "lucide-react";
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

  const [password, setPassword] = useState("");
  const [verifying, setVerifying] = useState(false);

  // Toast States
  const [toast, setToast] = useState<{ type: "success" | "error"; message: string } | null>(null);

  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => setToast(null), 5000);
      return () => clearTimeout(timer);
    }
  }, [toast]);

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

    try {
      const { error } = await supabase.auth.updateUser({
        data: { full_name: newName }
      });

      if (error) throw error;

      setUser(prev => prev ? { ...prev, name: newName } : null);
      setToast({ type: "success", message: "Profile updated successfully." });
      setIsEditingProfile(false);
    } catch (err) {
      setToast({ type: "error", message: err instanceof Error ? err.message : "Failed to update profile." });
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
        setToast({ type: "error", message: "No transactions found to export." });
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
      link.setAttribute("download", `scale_export_${new Date().toISOString().split('T')[0]}.csv`);
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);

      setToast({ type: "success", message: "Data exported successfully." });
    } catch (err) {
      setToast({ type: "error", message: "Failed to export data." });
      console.error(err);
    } finally {
      setExporting(false);
    }
  };

  const handleDeleteAllData = async () => {
    if (!user?.id || !user.email) {
      setToast({ type: "error", message: "Unable to verify account. Please sign in again." });
      return;
    }

    if (!password) {
      setToast({ type: "error", message: "Please enter your password to confirm." });
      return;
    }

    setVerifying(true);

    // Verify password
    const { error: authError } = await supabase.auth.signInWithPassword({
      email: user.email,
      password: password
    });

    if (authError) {
      setVerifying(false);
      setToast({ type: "error", message: "Incorrect password." });
      return;
    }

    setDeletingData(true);

    try {
      const { error: deleteError } = await supabase
        .from("transactions")
        .delete()
        .eq("user_id", user.id);

      if (deleteError) throw deleteError;

      sessionStorage.removeItem(`overview-cache:${user.id}`);
      sessionStorage.removeItem(`transactions-cache:${user.id}`);

      setToast({ type: "success", message: "All your transaction data has been permanently deleted." });
      setShowDeleteConfirm(false);
      setPassword("");
    } catch (deleteError) {
      setToast({ type: "error", message: deleteError instanceof Error ? deleteError.message : "Failed to delete data." });
    } finally {
      setDeletingData(false);
      setVerifying(false);
    }
  };

  if (loading) return <div className="flex h-full items-center justify-center"><Loader2 className="animate-spin text-primary" /></div>;

  return (
    <div className="relative mx-auto w-full max-w-6xl p-4 md:p-6 space-y-4 h-[calc(100vh-4rem)] overflow-y-auto no-scrollbar">
      {/* Header */}
      <div className="flex flex-col gap-1 border-b border-border pb-4">
        <h1 className="text-2xl font-black tracking-tight text-foreground">Settings</h1>
        <p className="text-muted-foreground text-xs font-medium">Manage your profile, preferences, and data.</p>
      </div>

      {/* Fixed Toast Notification */}
      {toast && (
        <div className="absolute top-6 right-6 z-[100] animate-in slide-in-from-top-5 fade-in duration-300">
          <div className={`flex items-center gap-3 rounded-2xl border px-5 py-3.5 shadow-xl backdrop-blur-md ${toast.type === "success"
            ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-500"
            : "border-destructive/20 bg-destructive/10 text-destructive"
            }`}>
            {toast.type === "success" ? <Check size={18} strokeWidth={2.5} /> : <AlertTriangle size={18} strokeWidth={2.5} />}
            <p className="font-bold text-sm tracking-wide">{toast.message}</p>
          </div>
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-3 items-start">
        {/* Profile Section */}
        <section className="group relative overflow-hidden rounded-3xl border border-border bg-card p-6 shadow-sm transition-all hover:shadow-md h-full">
          <div className="relative z-10 flex flex-col h-full">
            <div className="mb-6 flex items-center gap-4">
              <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-blue-500/10 text-blue-500 ring-4 ring-blue-500/5">
                <User size={20} strokeWidth={2.5} />
              </div>
              <div>
                <h2 className="text-base font-bold text-foreground">Profile Details</h2>
                <p className="text-[10px] font-medium text-muted-foreground">Update your personal information</p>
              </div>
            </div>

            {isEditingProfile ? (
              <form onSubmit={handleUpdateProfile} className="space-y-4">
                <div className="space-y-1.5">
                  <label className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Full Name</label>
                  <input
                    type="text"
                    value={newName}
                    onChange={(e) => setNewName(e.target.value)}
                    className="w-full rounded-xl bg-muted/50 border border-border px-3 py-2 text-sm font-medium text-foreground transition-all focus:bg-background focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary/50"
                  />
                </div>
                <div className="flex gap-2 pt-2">
                  <button
                    type="button"
                    onClick={() => setIsEditingProfile(false)}
                    className="flex-1 rounded-xl border border-border bg-background px-3 py-2 text-xs font-bold text-muted-foreground hover:bg-muted/50 transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={savingProfile}
                    className="flex-1 rounded-xl bg-primary px-3 py-2 text-xs font-bold text-primary-foreground hover:opacity-90 transition-opacity flex items-center justify-center gap-2"
                  >
                    {savingProfile && <Loader2 size={14} className="animate-spin" />}
                    Save
                  </button>
                </div>
              </form>
            ) : (
              <div className="space-y-4">
                <div
                  className="group/item flex cursor-pointer items-center justify-between rounded-xl border border-transparent bg-muted/30 p-3 transition-all hover:border-border hover:bg-muted/50"
                  onClick={() => setIsEditingProfile(true)}
                >
                  <div className="space-y-0.5">
                    <label className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground/70">Full Name</label>
                    <p className="font-semibold text-sm text-foreground">{user?.name || "User"}</p>
                  </div>
                  <ChevronRight size={16} className="text-muted-foreground/50 opacity-0 transition-all group-hover/item:opacity-100 group-hover/item:translate-x-1" />
                </div>

                <div className="rounded-xl border border-transparent bg-muted/30 p-3">
                  <div className="space-y-0.5">
                    <label className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground/70">Email Address</label>
                    <p className="font-semibold text-sm text-foreground">{user?.email}</p>
                  </div>
                </div>

                <div className="pt-1">
                  <button
                    onClick={() => setIsEditingProfile(true)}
                    className="w-full rounded-xl border border-border bg-background px-3 py-2 text-xs font-bold text-foreground hover:bg-muted/50 transition-colors"
                  >
                    Edit Profile
                  </button>
                </div>
              </div>
            )}
          </div>
        </section>

        {/* Middle Column: Preferences */}
        <div className="space-y-4">
          {/* Appearance */}
          <section className="rounded-3xl border border-border bg-card p-5 shadow-sm transition-all hover:shadow-md">
            <div className="mb-4 flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-purple-500/10 text-purple-500 ring-4 ring-purple-500/5">
                <Sun size={18} strokeWidth={2.5} />
              </div>
              <div>
                <h2 className="text-sm font-bold text-foreground">Appearance</h2>
                <p className="text-[10px] font-medium text-muted-foreground">Customize interface theme</p>
              </div>
            </div>

            <div className="flex items-center justify-between rounded-xl border border-border bg-muted/30 p-3 transition-colors">
              <div className="flex items-center gap-3">
                <div className={`flex h-8 w-8 items-center justify-center rounded-full transition-colors ${theme === 'dark' ? 'bg-indigo-500/20 text-indigo-400' : 'bg-orange-500/20 text-orange-500'}`}>
                  {mounted && theme === 'dark' ? <Moon size={14} /> : <Sun size={14} />}
                </div>
                <div>
                  <p className="text-xs font-bold text-foreground">Mode</p>
                  <p className="text-[10px] font-medium text-muted-foreground">{mounted ? (theme === 'dark' ? 'Dark' : 'Light') : 'System'}</p>
                </div>
              </div>
              <button
                onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
                className="rounded-lg border border-border bg-background px-3 py-1.5 text-[10px] font-bold text-foreground shadow-sm hover:bg-muted transition-all active:scale-95"
              >
                Switch
              </button>
            </div>
          </section>

          {/* Data Export */}
          <section className="rounded-3xl border border-border bg-card p-5 shadow-sm transition-all hover:shadow-md">
            <div className="mb-4 flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-emerald-500/10 text-emerald-500 ring-4 ring-emerald-500/5">
                <FileText size={18} strokeWidth={2.5} />
              </div>
              <div>
                <h2 className="text-sm font-bold text-foreground">Data</h2>
                <p className="text-[10px] font-medium text-muted-foreground">Export history</p>
              </div>
            </div>

            <button
              onClick={handleExportData}
              disabled={exporting}
              className="group flex w-full items-center justify-between rounded-xl border border-border bg-muted/30 p-3 transition-all hover:border-emerald-500/30 hover:bg-emerald-500/5 hover:shadow-sm"
            >
              <div className="flex items-center gap-3">
                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-emerald-500/10 text-emerald-500 transition-transform group-hover:scale-110">
                  {exporting ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
                </div>
                <div className="text-left">
                  <p className="text-xs font-bold text-foreground group-hover:text-emerald-600 dark:group-hover:text-emerald-400 transition-colors">CSV Export</p>
                </div>
              </div>
              <div className="rounded-md bg-background px-2 py-1 text-[10px] font-bold text-foreground border border-border group-hover:border-emerald-500/20">
                Download
              </div>
            </button>
          </section>
        </div>

        {/* Right Column: Danger Zone */}
        <section className="rounded-3xl border border-destructive/20 bg-destructive/5 p-5 shadow-sm h-full flex flex-col justify-between">
          <div className="flex items-center gap-3 mb-4">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-destructive/10 text-destructive ring-4 ring-destructive/5">
              <AlertTriangle size={18} strokeWidth={2.5} />
            </div>
            <div>
              <h2 className="text-sm font-bold text-destructive">Danger Zone</h2>
              <p className="text-[10px] font-medium text-destructive/70">Irreversible actions</p>
            </div>
          </div>

          <div className="space-y-4">
            <p className="text-xs font-medium text-destructive/70 leading-relaxed">
              Deleting your data will permanently remove all transactions and analytics history.
            </p>

            <button
              type="button"
              onClick={() => {
                setShowDeleteConfirm(true);
                setPassword("");
              }}
              className="w-full shrink-0 rounded-xl border border-destructive/30 bg-background px-4 py-2.5 text-xs font-bold text-destructive hover:bg-destructive hover:text-destructive-foreground transition-all shadow-sm active:scale-95"
            >
              Delete All Data
            </button>
          </div>
        </section>
      </div>

      {showDeleteConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <form
            onSubmit={(e) => { e.preventDefault(); handleDeleteAllData(); }}
            className="relative w-full max-w-sm rounded-2xl border border-destructive/30 bg-card p-6 shadow-2xl animate-in fade-in zoom-in-95 duration-200"
          >
            <button
              type="button"
              onClick={() => (deletingData || verifying ? null : setShowDeleteConfirm(false))}
              className="absolute right-4 top-4 text-muted-foreground hover:text-foreground"
            >
              <X size={18} />
            </button>

            <div className="mb-4 flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-destructive/10 text-destructive">
                <AlertTriangle size={20} />
              </div>
              <h3 className="text-lg font-black text-foreground">Delete Data?</h3>
            </div>

            <p className="text-sm text-muted-foreground mb-4">
              Permanently remove all transactions. Enter password to confirm.
            </p>

            <input
              type="password"
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-xl border border-border bg-muted/50 px-4 py-2 text-foreground focus:outline-none focus:ring-2 focus:ring-destructive/50"
              autoFocus
            />

            <div className="mt-6 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setShowDeleteConfirm(false)}
                disabled={deletingData || verifying}
                className="rounded-xl border border-border bg-muted/50 px-3 py-2 text-xs font-semibold text-muted-foreground hover:bg-muted disabled:opacity-60"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={deletingData || verifying || !password}
                className="inline-flex items-center gap-2 rounded-xl bg-destructive px-3 py-2 text-xs font-bold text-destructive-foreground hover:opacity-90 disabled:opacity-60"
              >
                {deletingData || verifying ? <Loader2 className="h-3 w-3 animate-spin" /> : null}
                {deletingData ? "Deleting..." : verifying ? "Verifying..." : "Confirm Delete"}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
