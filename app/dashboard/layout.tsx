"use client";

import { useEffect, useState } from "react";
import { type AuthChangeEvent, type Session } from "@supabase/supabase-js";
import { LayoutDashboard, Wallet, PieChart, Settings, Loader2 } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
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

    useEffect(() => {
        const loadUser = async () => {
            const { data, error } = await supabase.auth.getUser();
            if (error || !data.user) {
                router.replace("/login");
                return;
            }

            const fullName = data.user.user_metadata?.full_name as string | undefined;
            const fallback = data.user.email?.split("@")[0] || "User";
            setDisplayName(firstNameFromDisplayName(fullName || fallback));
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

    if (loading) {
        return (
            <div className="min-h-screen bg-background flex items-center justify-center">
                <Loader2 className="w-10 h-10 animate-spin text-primary" />
            </div>
        );
    }

    return (
        <div className="h-screen overflow-hidden bg-background p-4 md:p-7">
            <div className="mx-auto flex h-full max-w-[1700px] gap-4 md:gap-6">
                <aside className="hidden h-full w-72 flex-col rounded-[32px] border border-white/10 bg-gradient-to-b from-secondary to-[#0b1a2e] p-6 text-white shadow-slush md:flex">
                    <div className="mb-10 flex items-center gap-3 px-1">
                        <div className="flex h-11 w-11 items-center justify-center rounded-full border border-white/10 bg-background text-base font-black">S</div>
                        <span className="text-2xl font-bold tracking-tight">SpendSmart</span>
                    </div>

                    <nav className="flex-1 space-y-2">
                        <SidebarItem icon={<LayoutDashboard size={20} />} label="Overview" href="/dashboard" active={pathname === "/dashboard"} />
                        <SidebarItem icon={<Wallet size={20} />} label="Transactions" href="/dashboard/transactions" active={pathname === "/dashboard/transactions"} />
                        <SidebarItem icon={<PieChart size={20} />} label="Analytics" href="/dashboard/analytics" active={pathname === "/dashboard/analytics"} />
                        <SidebarItem icon={<Settings size={20} />} label="Settings" href="/dashboard/settings" active={pathname === "/dashboard/settings"} />
                    </nav>

                    <div className="mt-auto rounded-2xl border border-white/10 bg-background/80 px-4 py-3">
                        <div className="min-w-0">
                            <p className="truncate text-sm font-semibold text-white">{displayName}</p>
                            <p className="truncate text-xs text-slate-400">{email || "Signed in"}</p>
                        </div>
                    </div>
                </aside>

                <main className="h-full min-w-0 flex-1 overflow-y-auto overflow-x-hidden rounded-[32px] border border-white/10 bg-card p-6">
                    {children}
                </main>
            </div>
        </div>
    )
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
        <Link href={href} className={`
      flex items-center gap-3 px-4 py-3 rounded-full cursor-pointer transition-all duration-200
      ${active
                ? "bg-background text-white"
                : "text-white/90 hover:bg-white/10 hover:text-white"
            }
    `}>
            {icon}
            <span className="font-bold text-sm">{label}</span>
        </Link>
    );
}
