"use client";

import { useEffect, useRef, useState } from "react";
import { type AuthChangeEvent, type Session } from "@supabase/supabase-js";
import { LayoutDashboard, Wallet, PieChart, Settings, LogOut, UserPlus, Check, MoreVertical, Sun, Moon } from "lucide-react";
import Link from "next/link";
import Image from "next/image";
import { usePathname, useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { useTheme } from "next-themes";
import { supabase } from "../../lib/supabase/client";

function firstNameFromDisplayName(value: string): string {
    const cleaned = value.trim().replace(/\s+/g, " ");
    if (!cleaned) return "User";
    return cleaned.split(" ")[0] || "User";
}

type StoredSession = {
    user_id: string;
    email: string;
    name: string;
    avatar_url?: string;
    access_token: string;
    refresh_token: string;
    expires_at?: number;
};

function readStoredSessions(): StoredSession[] {
    const raw = localStorage.getItem("supabase-multi-auth");
    if (!raw) return [];
    try {
        const parsed = JSON.parse(raw) as unknown;
        if (!Array.isArray(parsed)) return [];
        return parsed.filter((item): item is StoredSession => {
            if (!item || typeof item !== "object") return false;
            const value = item as Record<string, unknown>;
            return (
                typeof value.email === "string" &&
                typeof value.access_token === "string" &&
                typeof value.refresh_token === "string" &&
                typeof value.user_id === "string"
            );
        });
    } catch {
        return [];
    }
}

export default function DashboardLayout({
    children,
}: {
    children: React.ReactNode
}) {
    const router = useRouter();
    const pathname = usePathname();
    const { theme, setTheme } = useTheme();

    // Auth States
    const [displayName, setDisplayName] = useState("User");
    const [email, setEmail] = useState("");
    const [avatarUrl, setAvatarUrl] = useState<string | null>(null);
    const [isProfileOpen, setIsProfileOpen] = useState(false);
    const profileMenuRef = useRef<HTMLDivElement | null>(null);

    const [savedSessions, setSavedSessions] = useState<StoredSession[]>([]);

    useEffect(() => {
        const loadUser = async () => {
            const { data, error } = await supabase.auth.getUser();
            if (error || !data.user) {
                return;
            }

            const fullName = data.user.user_metadata?.full_name as string | undefined;
            const avatar = data.user.user_metadata?.avatar_url as string | undefined;
            const fallback = data.user.email?.split("@")[0] || "User";
            const userEmail = data.user.email || "";

            setDisplayName(firstNameFromDisplayName(fullName || fallback));
            setEmail(userEmail);
            setAvatarUrl(avatar || null);
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

                let sessions = readStoredSessions();
                sessions = sessions.filter((s) => s.email !== userEmail);
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
                } else if (event === "SIGNED_IN" || event === "TOKEN_REFRESHED" || event === "USER_UPDATED") {
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
        let sessions = readStoredSessions();
        sessions = sessions.filter((s) => s.email !== email);
        localStorage.setItem('supabase-multi-auth', JSON.stringify(sessions));
        await supabase.auth.signOut();
        router.replace("/login");
    };

    const handleSwitchAccount = async (session: StoredSession) => {
        if (session.email === email) return;

        // Optimistic UI: Close menu immediately
        setIsProfileOpen(false);

        const { data, error } = await supabase.auth.setSession({
            access_token: session.access_token,
            refresh_token: session.refresh_token,
        });

        if (error || !data.session) {
            console.error("Failed to switch account - session invalid:", error);
            // Remove invalid session
            const validSessions = readStoredSessions().filter((s) => s.email !== session.email);
            localStorage.setItem('supabase-multi-auth', JSON.stringify(validSessions));
            setSavedSessions(validSessions);

            // Start - Error Handling Update
            if (confirm(`Session for ${session.email} has expired. Would you like to log in again?`)) {
                await supabase.auth.signOut(); // Ensure we are clean state before login
                router.push("/login");
            }
            return;
        }

        // Force reload to ensure all state is clean
        window.location.reload();
    };

    const handleAddAccount = () => {
        supabase.auth.signOut().then(() => {
            router.push("/login");
        });
    };

    const toggleTheme = () => {
        setTheme(theme === "dark" ? "light" : "dark");
    };

    return (
        <div className="h-screen overflow-hidden bg-background p-4 md:p-6 font-sans text-foreground selection:bg-primary/30 transition-colors duration-300">
            <div className="mx-auto flex h-full max-w-[1700px] gap-6">
                <aside className="hidden h-full w-72 flex-col rounded-[2.5rem] bg-card border border-border p-6 shadow-2xl md:flex shrink-0 transition-colors duration-300">
                    <div
                        onClick={toggleTheme}
                        className="mb-10 flex items-center gap-3 px-2 cursor-pointer group select-none"
                    >
                        <div className="relative flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-blue-500 to-indigo-600 text-white font-black text-lg shadow-lg shadow-blue-500/20 group-hover:scale-105 transition-transform duration-200">
                            {theme === "light" ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
                        </div>
                        <span className="text-xl font-bold tracking-tight text-foreground/90 group-hover:text-primary transition-colors">SpendSmart</span>
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
                                    className="absolute bottom-full mb-4 w-full rounded-2xl bg-popover border border-border shadow-xl overflow-hidden z-50 p-1"
                                >
                                    <div className="px-3 py-2 text-[10px] font-bold text-muted-foreground uppercase tracking-wide flex justify-between items-center">
                                        <span>Switch Accounts</span>
                                    </div>

                                    <div className="max-h-[150px] overflow-y-auto custom-scrollbar mb-1 space-y-0.5">
                                        {savedSessions.map((s) => (
                                            <button
                                                key={s.email}
                                                onClick={() => handleSwitchAccount(s)}
                                                className={`w-full flex items-center justify-between px-3 py-2 rounded-xl text-sm font-medium transition-colors ${s.email === email ? "bg-muted text-foreground" : "text-muted-foreground hover:text-foreground hover:bg-muted/50"}`}
                                            >
                                                <div className="flex items-center gap-2 min-w-0">
                                                    {s.avatar_url ? (
                                                        <Image src={s.avatar_url} alt={s.name || s.email} width={20} height={20} className="w-5 h-5 rounded-full" />
                                                    ) : (
                                                        <div className="w-5 h-5 rounded-full bg-blue-500/50 flex items-center justify-center text-[8px] font-bold text-white">
                                                            {s.name?.[0] || s.email[0]}
                                                        </div>
                                                    )}
                                                    <span className="truncate max-w-[100px]">{s.email}</span>
                                                </div>
                                                {s.email === email && <Check size={14} className="text-primary shrink-0" />}
                                            </button>
                                        ))}
                                    </div>

                                    <button
                                        onClick={handleAddAccount}
                                        className="w-full flex items-center gap-3 px-3 py-2 rounded-xl text-sm font-medium text-blue-500 hover:bg-blue-500/10 transition-colors border-t border-border mt-1"
                                    >
                                        <UserPlus size={16} />
                                        Add Account
                                    </button>

                                    <button
                                        onClick={handleSignOut}
                                        className="w-full flex items-center gap-3 px-3 py-2 rounded-xl text-sm font-medium text-destructive hover:bg-destructive/10 transition-colors"
                                    >
                                        <LogOut size={16} />
                                        Sign Out
                                    </button>
                                </motion.div>
                            )}
                        </AnimatePresence>

                        <button
                            onClick={() => setIsProfileOpen(!isProfileOpen)}
                            className={`w-full flex items-center gap-3 rounded-2xl border p-3 transition-all duration-200 group ${isProfileOpen ? "bg-muted border-border" : "bg-card border-border hover:border-border/80 hover:bg-muted/50"}`}
                        >
                            {avatarUrl ? (
                                <Image src={avatarUrl} alt={displayName} width={40} height={40} className="h-10 w-10 rounded-full object-cover border-2 border-border" />
                            ) : (
                                <div className="h-10 w-10 flex items-center justify-center rounded-full bg-secondary text-primary-foreground text-sm font-bold border-2 border-border">
                                    {displayName[0]}
                                </div>
                            )}
                            <div className="flex-1 min-w-0 text-left">
                                <p className="truncate text-sm font-bold text-foreground group-hover:text-primary transition-colors">{displayName}</p>
                                <p className="truncate text-xs text-muted-foreground">{email}</p>
                            </div>
                            <MoreVertical size={16} className={`text-muted-foreground transition-transform ${isProfileOpen ? "rotate-90" : ""}`} />
                        </button>
                    </div>
                </aside>

                <main className="h-full min-w-0 flex-1 overflow-visible rounded-[2.5rem] border border-border bg-background shadow-xl relative transition-colors duration-300">
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
                        ? "bg-primary text-white shadow-lg shadow-blue-500/25"
                        : "text-muted-foreground hover:bg-muted hover:text-foreground"
                    }
            `}
            >
                {icon}
                <span className="font-bold text-sm tracking-wide">{label}</span>
            </motion.div>
        </Link>
    );
}
