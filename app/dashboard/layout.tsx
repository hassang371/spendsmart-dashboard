"use client";

import { useEffect, useRef, useState } from "react";
import { type AuthChangeEvent, type Session } from "@supabase/supabase-js";
import { LayoutDashboard, Wallet, PieChart, Settings, Loader2, LogOut, UserPlus, Check, MoreVertical } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { supabase } from "../../lib/supabase/client";

function firstNameFromDisplayName(value: string): string {
    const cleaned = value.trim().replace(/\s+/g, " ");
    if (!cleaned) return "User";
    return cleaned.split(" ")[0] || "User";
}

export default function DashboardLayout({
    children,
}: {
    children: React.ReactNode
}) {
    const router = useRouter();
    const pathname = usePathname();
    const [loading, setLoading] = useState(true);
    const [displayName, setDisplayName] = useState("User");
    const [email, setEmail] = useState("");
    const [avatarUrl, setAvatarUrl] = useState<string | null>(null);
    const [isProfileOpen, setIsProfileOpen] = useState(false);
    const profileMenuRef = useRef<HTMLDivElement | null>(null);

    const [savedSessions, setSavedSessions] = useState<any[]>([]);

    useEffect(() => {
        const loadUser = async () => {
            const { data, error } = await supabase.auth.getUser();
            if (error || !data.user) {
                // If checking auth and failed, maybe clear data?
                // But for layout, we act as a guard.
                // However, wait for onAuthStateChange to handle redirects.
                return;
            }

            const fullName = data.user.user_metadata?.full_name as string | undefined;
            const avatar = data.user.user_metadata?.avatar_url as string | undefined;
            const fallback = data.user.email?.split("@")[0] || "User";
            const userEmail = data.user.email || "";

            setDisplayName(firstNameFromDisplayName(fullName || fallback));
            setEmail(userEmail);
            setAvatarUrl(avatar || null);
            setLoading(false);

            // --- Multi-Account Sync ---
            const { data: { session } } = await supabase.auth.getSession();
            if (session) {
                const currentSessionInfo = {
                    user_id: data.user.id,
                    email: userEmail,
                    name: fullName || fallback,
                    avatar_url: avatar,
                    access_token: session.access_token,
                    refresh_token: session.refresh_token,
                    expires_at: session.expires_at,
                };

                const stored = localStorage.getItem('supabase-multi-auth');
                let sessions = stored ? JSON.parse(stored) : [];
                // Remove existing entry for this user to update it
                sessions = sessions.filter((s: any) => s.email !== userEmail);
                // Add updated
                sessions.push(currentSessionInfo);
                localStorage.setItem('supabase-multi-auth', JSON.stringify(sessions));
                setSavedSessions(sessions);
            }
        };

        loadUser();

        const { data: subscription } = supabase.auth.onAuthStateChange(
            (event: AuthChangeEvent, session: Session | null) => {
                if (event === "SIGNED_OUT" || !session) {
                    router.replace("/login");
                } else if (event === "SIGNED_IN" || event === "TOKEN_REFRESHED") {
                    // Update session list on sign in / refresh
                    loadUser();
                }
            },
        );

        return () => subscription.subscription.unsubscribe();
    }, [router]);

    useEffect(() => {
        ["/dashboard", "/dashboard/transactions", "/dashboard/analytics", "/dashboard/settings"].forEach((route) => {
            router.prefetch(route);
        });
    }, [router]);

    useEffect(() => {
        if (!isProfileOpen) return;

        const onPointerDown = (event: MouseEvent) => {
            const target = event.target as Node;
            if (profileMenuRef.current && !profileMenuRef.current.contains(target)) {
                setIsProfileOpen(false);
            }
        };

        document.addEventListener("mousedown", onPointerDown);
        return () => document.removeEventListener("mousedown", onPointerDown);
    }, [isProfileOpen]);

    const handleSignOut = async () => {
        // Remove current session from local storage list
        const stored = localStorage.getItem('supabase-multi-auth');
        if (stored) {
            let sessions = JSON.parse(stored);
            sessions = sessions.filter((s: any) => s.email !== email);
            localStorage.setItem('supabase-multi-auth', JSON.stringify(sessions));
        }
        await supabase.auth.signOut();
        router.replace("/login");
    };

    const handleSwitchAccount = async (session: any) => {
        if (session.email === email) return; // Already complex

        setLoading(true);
        const { error } = await supabase.auth.setSession({
            access_token: session.access_token,
            refresh_token: session.refresh_token,
        });

        if (error) {
            console.error("Failed to switch account:", error);
            // If token is invalid, maybe remove it?
            const stored = localStorage.getItem('supabase-multi-auth');
            if (stored) {
                const sessions = JSON.parse(stored).filter((s: any) => s.email !== session.email);
                localStorage.setItem('supabase-multi-auth', JSON.stringify(sessions));
                setSavedSessions(sessions);
            }
            setLoading(false);
            return;
        }

        // Reload will happen via onAuthStateChange --> loadUser
        setIsProfileOpen(false);
    };

    const handleAddAccount = () => {
        // We need to sign out current user locally (but keep in LC) ? 
        // No, we just go to login page. But Login page will redirect back if we are logged in.
        // So we need a special param to force show login form even if logged in? 
        // Or simply: Creating a new client instance is hard.
        // Easiest: clear cookies/storage for *supabase-js* only, but keep our 'supabase-multi-auth'.
        // Actually, supabase.auth.signOut() clears the current session.
        // Since we saved it in 'supabase-multi-auth', it is safe to sign out.
        // Then user logs in -> new session -> added to list.

        // Wait, if we signOut, the Layout will redirect to /login due to logic above.
        // That is exactly what we want!
        // But we want to ensure we don't 'forget' the current user.
        // We already updated LC in loadUser.

        supabase.auth.signOut().then(() => {
            router.push("/login");
        });
    };

    return (
        <div className="h-screen overflow-hidden bg-[#0B1221] p-4 md:p-6 font-sans text-slate-200 selection:bg-blue-500/30">
            <div className="mx-auto flex h-full max-w-[1700px] gap-6">
                <aside className="hidden h-full w-72 flex-col rounded-[2.5rem] bg-[#111827] border border-white/5 p-6 shadow-2xl md:flex shrink-0">
                    <div className="mb-10 flex items-center gap-3 px-2">
                        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-blue-500 to-indigo-600 text-white font-black text-lg shadow-lg shadow-blue-500/20">S</div>
                        <span className="text-xl font-bold tracking-tight text-white">SpendSmart</span>
                    </div>

                    <nav className="flex-1 space-y-2">
                        <SidebarItem icon={<LayoutDashboard size={20} />} label="Overview" href="/dashboard" active={pathname === "/dashboard"} />
                        <SidebarItem icon={<Wallet size={20} />} label="Transactions" href="/dashboard/transactions" active={pathname === "/dashboard/transactions"} />
                        <SidebarItem icon={<PieChart size={20} />} label="Analytics" href="/dashboard/analytics" active={pathname === "/dashboard/analytics"} />
                        <SidebarItem icon={<Settings size={20} />} label="Settings" href="/dashboard/settings" active={pathname === "/dashboard/settings"} />
                    </nav>

                    <div ref={profileMenuRef} className="relative mt-auto">
                        <AnimatePresence>
                            {isProfileOpen && (
                                <motion.div
                                    initial={{ opacity: 0, y: 10, scale: 0.95 }}
                                    animate={{ opacity: 1, y: 0, scale: 1 }}
                                    exit={{ opacity: 0, scale: 0.95, y: 10 }}
                                    className="absolute bottom-full mb-4 w-full rounded-2xl bg-[#1F2937] border border-white/10 shadow-xl overflow-hidden z-50 p-1"
                                >
                                    <div className="px-3 py-2 text-[10px] font-bold text-gray-400 uppercase tracking-wide flex justify-between items-center">
                                        <span>Switch Accounts</span>
                                    </div>

                                    <div className="max-h-[150px] overflow-y-auto custom-scrollbar mb-1 space-y-0.5">
                                        {savedSessions.map((s) => (
                                            <button
                                                key={s.email}
                                                onClick={() => handleSwitchAccount(s)}
                                                className={`w-full flex items-center justify-between px-3 py-2 rounded-xl text-sm font-medium transition-colors ${s.email === email ? "bg-white/10 text-white" : "text-gray-400 hover:text-white hover:bg-white/5"}`}
                                            >
                                                <div className="flex items-center gap-2 min-w-0">
                                                    {s.avatar_url ? (
                                                        <img src={s.avatar_url} className="w-5 h-5 rounded-full" />
                                                    ) : (
                                                        <div className="w-5 h-5 rounded-full bg-blue-500/50 flex items-center justify-center text-[8px] font-bold text-white">
                                                            {s.name?.[0] || s.email[0]}
                                                        </div>
                                                    )}
                                                    <span className="truncate max-w-[100px]">{s.email}</span>
                                                </div>
                                                {s.email === email && <Check size={14} className="text-blue-400 shrink-0" />}
                                            </button>
                                        ))}
                                    </div>

                                    <button
                                        onClick={handleAddAccount}
                                        className="w-full flex items-center gap-3 px-3 py-2 rounded-xl text-sm font-medium text-blue-400 hover:bg-blue-500/10 transition-colors border-t border-white/5 mt-1"
                                    >
                                        <UserPlus size={16} />
                                        Add Account
                                    </button>

                                    <button
                                        onClick={handleSignOut}
                                        className="w-full flex items-center gap-3 px-3 py-2 rounded-xl text-sm font-medium text-red-400 hover:bg-red-500/10 transition-colors"
                                    >
                                        <LogOut size={16} />
                                        Sign Out
                                    </button>
                                </motion.div>
                            )}
                        </AnimatePresence>

                        <button
                            onClick={() => setIsProfileOpen(!isProfileOpen)}
                            className={`w-full flex items-center gap-3 rounded-2xl border p-3 transition-all duration-200 group ${isProfileOpen ? "bg-white/10 border-white/20" : "bg-[#1F2937]/50 border-white/5 hover:border-white/10 hover:bg-[#1F2937]"}`}
                        >
                            {avatarUrl ? (
                                <img src={avatarUrl} alt={displayName} className="h-10 w-10 rounded-full object-cover border-2 border-[#1F2937]" />
                            ) : (
                                <div className="h-10 w-10 flex items-center justify-center rounded-full bg-gradient-to-br from-gray-700 to-gray-800 text-sm font-bold border-2 border-[#1F2937]">
                                    {displayName[0]}
                                </div>
                            )}
                            <div className="flex-1 min-w-0 text-left">
                                <p className="truncate text-sm font-bold text-white group-hover:text-blue-400 transition-colors">{displayName}</p>
                                <p className="truncate text-xs text-gray-500">{email}</p>
                            </div>
                            <MoreVertical size={16} className={`text-gray-500 transition-transform ${isProfileOpen ? "rotate-90" : ""}`} />
                        </button>
                    </div>
                </aside>

                <main className="h-full min-w-0 flex-1 overflow-visible rounded-[2.5rem] border border-white/5 bg-[#0B1221] shadow-xl relative">
                    {/* Background ambient glow could go here */}
                    <div className="h-full overflow-y-auto overflow-x-hidden p-6 custom-scrollbar relative z-10">
                        {children}
                    </div>
                </main>
            </div>
        </div>
    );
}

function SidebarItem({
    icon,
    label,
    href,
    active = false,
}: {
    icon: React.ReactNode,
    label: string,
    href: string,
    active?: boolean,
}) {
    return (
        <Link href={href} prefetch>
            <motion.div
                whileHover={{ x: 4 }}
                whileTap={{ scale: 0.98 }}
                className={`
                flex items-center gap-3 px-4 py-3.5 rounded-2xl cursor-pointer transition-all duration-200 mb-1
                ${active
                        ? "bg-blue-600 text-white shadow-lg shadow-blue-500/25"
                        : "text-gray-400 hover:bg-white/5 hover:text-white"
                    }
            `}
            >
                {icon}
                <span className="font-bold text-sm tracking-wide">{label}</span>
            </motion.div>
        </Link>
    );
}
