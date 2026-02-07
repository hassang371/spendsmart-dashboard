"use client";

import { useEffect, useMemo, useState } from "react";
import { type AuthChangeEvent, type Session } from "@supabase/supabase-js";
import { LayoutDashboard, Wallet, PieChart, Settings, Bell, LogOut, Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { supabase } from "../../lib/supabase/client";

export default function DashboardLayout({
    children,
}: {
    children: React.ReactNode
}) {
    const router = useRouter();
    const [loading, setLoading] = useState(true);
    const [displayName, setDisplayName] = useState("User");
    const [email, setEmail] = useState("");

    useEffect(() => {
        const loadUser = async () => {
            const { data, error } = await supabase.auth.getUser();
            if (error || !data.user) {
                router.replace("/login");
                return;
            }

            const fullName = data.user.user_metadata?.full_name as string | undefined;
            setDisplayName(fullName || data.user.email?.split("@")[0] || "User");
            setEmail(data.user.email || "");
            setLoading(false);
        };

        loadUser();

        const { data: subscription } = supabase.auth.onAuthStateChange(
            (_event: AuthChangeEvent, session: Session | null) => {
            if (!session) {
                router.replace("/login");
            }
            },
        );

        return () => subscription.subscription.unsubscribe();
    }, [router]);

    const greetingName = useMemo(() => {
        if (!displayName) {
            return "there";
        }
        return displayName.split(" ")[0];
    }, [displayName]);

    const handleLogout = async () => {
        await supabase.auth.signOut();
        router.replace("/login");
    };

    if (loading) {
        return (
            <div className="min-h-screen bg-background flex items-center justify-center">
                <Loader2 className="w-10 h-10 animate-spin text-primary" />
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-background flex">
            {/* Sidebar - Slush Style */}
            <aside className="w-64 bg-secondary border-r border-white/5 hidden md:flex flex-col p-6 fixed h-full z-20">
                <div className="flex items-center gap-3 mb-12 px-2">
                    <div className="w-8 h-8 bg-primary rounded-lg flex items-center justify-center rotate-3 border border-black shadow-[1px_1px_0px_0px_rgba(0,0,0,1)]">
                        <span className="text-white font-mono font-bold text-sm">S</span>
                    </div>
                    <span className="font-mono font-bold text-lg tracking-tight">SpendSmart</span>
                </div>

                <nav className="flex-1 space-y-2">
                    <SidebarItem icon={<LayoutDashboard size={20} />} label="Overview" active />
                    <SidebarItem icon={<Wallet size={20} />} label="Transactions" />
                    <SidebarItem icon={<PieChart size={20} />} label="Analytics" />
                    <SidebarItem icon={<Settings size={20} />} label="Settings" />
                </nav>

                <div className="mt-auto pt-6 border-t border-white/5">
                    <button
                        type="button"
                        onClick={handleLogout}
                        className="w-full flex items-center gap-3 px-3 py-2 rounded-xl hover:bg-white/5 cursor-pointer group transition-colors text-left"
                    >
                        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-purple-500 to-pink-500 flex-shrink-0"></div>
                        <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium truncate group-hover:text-white transition-colors">{displayName}</p>
                            <p className="text-xs text-gray-500 truncate">{email || "Signed in"}</p>
                        </div>
                        <LogOut size={16} className="text-gray-500 group-hover:text-red-400 transition-colors" />
                    </button>
                </div>
            </aside>

            {/* Main Content Area */}
            <main className="flex-1 md:ml-64 p-8 relative overflow-hidden">
                {/* Background Decoration */}
                <div className="absolute top-[-20%] right-[-10%] w-[500px] h-[500px] bg-primary/10 blur-[120px] rounded-full pointer-events-none"></div>

                <header className="flex justify-between items-center mb-8 relative z-10">
                    <div>
                        <h1 className="text-3xl font-bold">Good evening, {greetingName}</h1>
                        <p className="text-gray-400">Here&apos;s what&apos;s happening with your money today.</p>
                    </div>
                    <div className="flex items-center gap-4">
                        <button className="p-2 rounded-full border border-white/10 hover:bg-white/5 transition-colors relative">
                            <Bell size={20} />
                            <span className="absolute top-2 right-2 w-2 h-2 bg-red-500 rounded-full"></span>
                        </button>
                        <button className="px-4 py-2 bg-primary text-white rounded-xl font-bold shadow-glow hover:scale-105 transition-transform text-sm">
                            + Add Funds
                        </button>
                    </div>
                </header>

                <div className="relative z-10">
                    {children}
                </div>
            </main>
        </div>
    )
}

function SidebarItem({ icon, label, active = false }: { icon: React.ReactNode, label: string, active?: boolean }) {
    return (
        <div className={`
      flex items-center gap-3 px-3 py-3 rounded-xl cursor-pointer transition-all duration-200
      ${active
                ? "bg-primary text-white shadow-glow translate-x-1"
                : "text-gray-400 hover:bg-white/5 hover:text-white hover:translate-x-1"
            }
    `}>
            {icon}
            <span className="font-bold text-sm">{label}</span>
        </div>
    );
}
