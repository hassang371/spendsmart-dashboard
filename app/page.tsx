"use client";
import Link from "next/link";
import { useEffect } from "react";
import { type AuthChangeEvent, type Session } from "@supabase/supabase-js";
import { useRouter } from "next/navigation";
import { ArrowRight, LayoutGrid, Zap, Shield, TrendingUp } from "lucide-react";
import { motion } from "framer-motion";
import { supabase } from "../lib/supabase/client";

export default function Home() {
    const router = useRouter();

    useEffect(() => {
        const checkSession = async () => {
            const {
                data: { user },
            } = await supabase.auth.getUser();

            if (user) {
                router.replace("/dashboard");
            }
        };

        checkSession();

        const { data: subscription } = supabase.auth.onAuthStateChange(
            (event: AuthChangeEvent, session: Session | null) => {
                if (event === "SIGNED_IN" && session) {
                    router.replace("/dashboard");
                }
            },
        );

        return () => subscription.subscription.unsubscribe();
    }, [router]);

    return (
        <main className="min-h-screen bg-background overflow-x-hidden">
            {/* Navbar */}
            <nav className="fixed top-0 w-full z-50 px-6 py-4 flex justify-between items-center backdrop-blur-md bg-background/80 border-b border-white/10">
                <motion.div
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    className="flex items-center gap-2"
                >
                    <div className="w-10 h-10 bg-primary rounded-xl flex items-center justify-center rotate-3 border-2 border-black shadow-slush-sm">
                        <span className="text-white font-mono font-bold text-xl">S</span>
                    </div>
                    <span className="font-mono font-bold text-xl tracking-tight hidden sm:block text-white">SpendSmart</span>
                </motion.div>
                <div className="flex gap-4">
                    <Link href="/login" className="px-6 py-2 rounded-xl font-bold border-2 border-white/20 hover:border-white transition-colors text-white">
                        Login
                    </Link>
                    <Link href="/signup" className="px-6 py-2 bg-primary text-white rounded-xl font-bold border-2 border-transparent hover:scale-105 transition-transform shadow-glow">
                        Get Started
                    </Link>
                </div>
            </nav>

            {/* Hero Section */}
            <section className="pt-32 pb-20 px-6 max-w-7xl mx-auto flex flex-col items-center text-center">
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-white/5 border border-white/10 mb-8"
                >
                    <span className="w-2 h-2 bg-success rounded-full animate-pulse"></span>
                    <span className="text-sm font-medium text-gray-400">Financial Clarity 2.0 is here</span>
                </motion.div>

                <motion.h1
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.2 }}
                    className="text-6xl md:text-8xl font-black tracking-tighter mb-8 leading-[0.9] text-white"
                >
                    YOUR MONEY. <br />
                    <span className="text-transparent bg-clip-text bg-gradient-to-r from-primary via-purple-500 to-pink-500 animate-gradient-x">
                        UNSTUCK.
                    </span>
                </motion.h1>

                <motion.p
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.3 }}
                    className="text-xl text-gray-400 max-w-2xl mb-12"
                >
                    Stop guessing. Start knowing. The first financial dashboard that actually keeps up with your chaotic life.
                </motion.p>

                <motion.div
                    initial={{ opacity: 0, scale: 0.9 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ delay: 0.4 }}
                    className="flex flex-col sm:flex-row gap-4 mb-20"
                >
                    <Link href="/login">
                        <button className="group px-8 py-4 bg-white text-black text-lg font-bold rounded-2xl border-b-4 border-gray-300 active:border-b-0 active:translate-y-1 transition-all flex items-center gap-2 w-full sm:w-auto justify-center">
                            Launch App
                            <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
                        </button>
                    </Link>
                    <button className="px-8 py-4 bg-white/5 text-white text-lg font-bold rounded-2xl border border-white/10 hover:bg-white/10 transition-colors">
                        Download for iOS
                    </button>
                </motion.div>

                {/* Hero Visual */}
                <motion.div
                    initial={{ opacity: 0, y: 40 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.5, duration: 1 }}
                    className="w-full max-w-5xl aspect-video rounded-3xl bg-gradient-to-br from-gray-900 to-black border border-white/10 shadow-2xl relative overflow-hidden group"
                >
                    <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-20"></div>
                    {/* Mock Dashboard UI */}
                    <div className="absolute top-10 left-10 right-10 bottom-0 bg-[#0F172A] rounded-t-2xl border-t border-l border-r border-white/10 p-6 opacity-80 group-hover:opacity-100 group-hover:translate-y-[-10px] transition-all duration-500">
                        <div className="flex gap-4 mb-8">
                            <motion.div whileHover={{ scale: 1.05 }} className="w-1/3 h-32 bg-white/5 rounded-xl transition-colors hover:bg-white/10 cursor-pointer"></motion.div>
                            <motion.div whileHover={{ scale: 1.05 }} className="w-1/3 h-32 bg-white/5 rounded-xl transition-colors hover:bg-white/10 cursor-pointer"></motion.div>
                            <motion.div whileHover={{ scale: 1.05 }} className="w-1/3 h-32 bg-white/5 rounded-xl transition-colors hover:bg-white/10 cursor-pointer"></motion.div>
                        </div>
                        <div className="w-full h-64 bg-white/5 rounded-xl border border-white/5 group-hover:border-primary/20 transition-colors"></div>
                    </div>
                </motion.div>
            </section>

            {/* Bento Grid Features */}
            <section className="py-20 px-6 max-w-7xl mx-auto">
                <motion.h2
                    initial={{ opacity: 0 }}
                    whileInView={{ opacity: 1 }}
                    viewport={{ once: true }}
                    className="text-4xl font-bold mb-12 text-center text-white"
                >
                    Everything you need. <span className="text-gray-500">Nothing you don&apos;t.</span>
                </motion.h2>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-6 auto-rows-[300px]">
                    {/* Large Card */}
                    <motion.div
                        whileHover={{ y: -5 }}
                        className="md:col-span-2 row-span-2 bg-secondary rounded-3xl p-8 border border-white/5 hover:border-primary/50 transition-colors group relative overflow-hidden cursor-pointer"
                    >
                        <div className="absolute top-0 right-0 w-64 h-64 bg-primary/20 blur-[100px] rounded-full group-hover:bg-primary/30 transition-all"></div>
                        <LayoutGrid className="w-12 h-12 text-primary mb-6" />
                        <h3 className="text-3xl font-bold mb-4 text-white">Unified Dashboard</h3>
                        <p className="text-gray-400 text-lg max-w-md">Connect all your accounts using our secure MCP integration. See your entire net worth in one glance.</p>
                    </motion.div>

                    {/* Tall Card */}
                    <motion.div
                        whileHover={{ scale: 1.02 }}
                        className="row-span-2 bg-[#F59E0B] text-black rounded-3xl p-8 border border-transparent relative overflow-hidden cursor-pointer"
                    >
                        <Zap className="w-12 h-12 mb-6" />
                        <h3 className="text-3xl font-bold mb-4">Instant Insights</h3>
                        <p className="text-black/80 text-lg">Real-time processing of your transaction data. No more waiting for end-of-month statements.</p>
                        <div className="absolute bottom-[-50px] right-[-50px] w-64 h-64 bg-white/20 rounded-full blur-2xl"></div>
                    </motion.div>

                    {/* Small Card */}
                    <motion.div
                        whileHover={{ x: 5 }}
                        className="bg-secondary rounded-3xl p-8 border border-white/5 flex flex-col justify-between hover:bg-white/5 transition-colors cursor-pointer"
                    >
                        <Shield className="w-10 h-10 text-success" />
                        <div>
                            <h4 className="text-xl font-bold text-white">Bank-Grade Security</h4>
                            <p className="text-gray-400 text-sm mt-2">RLS Policies & Encryption</p>
                        </div>
                    </motion.div>

                    {/* Small Card */}
                    <motion.div
                        whileHover={{ x: 5 }}
                        className="bg-secondary rounded-3xl p-8 border border-white/5 flex flex-col justify-between hover:bg-white/5 transition-colors cursor-pointer"
                    >
                        <TrendingUp className="w-10 h-10 text-purple-500" />
                        <div>
                            <h4 className="text-xl font-bold text-white">Smart Forecasts</h4>
                            <p className="text-gray-400 text-sm mt-2">Predict your balance</p>
                        </div>
                    </motion.div>
                </div>
            </section>

            {/* Footer */}
            <footer className="py-20 border-t border-white/10 text-center text-gray-500">
                <p>© 2026 SpendSmart Labs. Built with B.L.A.S.T. Protocol.</p>
            </footer>
        </main>
    );
}
