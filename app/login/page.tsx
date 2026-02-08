"use client";
import React, { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ArrowLeft, Apple, Loader2 } from "lucide-react";
import { supabase } from "../../lib/supabase/client";
import { useRouter } from "next/navigation";
import Link from "next/link";
// Importing ScaleLogo from the components folder for consistency with new design
// If it's not exported properly, we might need to inline or adjust.
// import ScaleLogo from "../../components/landing/ScaleLogo"; 

export default function LoginPage() {
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [loading, setLoading] = useState(false);
    const [googleLoading, setGoogleLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
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
    }, [router]);

    const handleLogin = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        setError(null);

        const { error: loginError } = await supabase.auth.signInWithPassword({
            email,
            password,
        });

        if (loginError) {
            setError(loginError.message);
            setLoading(false);
        } else {
            router.push("/dashboard");
        }
    };

    const handleGoogleLogin = async () => {
        setGoogleLoading(true);
        setError(null);

        const redirectTo = `${window.location.origin}/auth/callback?next=/dashboard`;
        const { error: googleError } = await supabase.auth.signInWithOAuth({
            provider: "google",
            options: {
                redirectTo,
            },
        });

        if (googleError) {
            setError(googleError.message);
            setGoogleLoading(false);
        }
    };

    // New "More options" handler -> redirect to signup
    const handleMoreOptions = () => {
        router.push("/signup");
    };

    return (
        <AnimatePresence>
            <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="fixed inset-0 z-[100] flex flex-col bg-brand-slushBlue text-white overflow-hidden font-display"
            >
                {/* Top Bar */}
                <div className="absolute top-0 left-0 w-full p-8 flex justify-center z-20">
                    <h1 className="text-4xl font-bold tracking-tighter uppercase">SCALE</h1>
                </div>

                <Link
                    href="/"
                    className="absolute top-8 left-8 flex items-center gap-2 text-white/50 hover:text-white transition-colors z-30 font-sans font-bold uppercase tracking-widest text-sm"
                >
                    <ArrowLeft className="w-5 h-5" /> Back
                </Link>

                {/* Main Content */}
                <div className="relative flex-1 flex flex-col items-center justify-center w-full max-w-[1600px] mx-auto">

                    {/* Floating Elements (Background) */}
                    <motion.div
                        animate={{ y: [-10, 10, -10], rotate: [0, 5, 0] }}
                        transition={{ duration: 6, repeat: Infinity, ease: "easeInOut" }}
                        className="absolute top-[20%] left-[10%] z-10 w-24 md:w-40 pointer-events-none"
                    >
                        {/* Rocket */}
                        <svg viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg" className="w-full drop-shadow-2xl">
                            <path d="M50 5L65 30H35L50 5Z" fill="#FF7D45" stroke="black" strokeWidth="3" />
                            <rect x="35" y="30" width="30" height="40" fill="white" stroke="black" strokeWidth="3" />
                            <circle cx="50" cy="50" r="8" fill="#4892FF" stroke="black" strokeWidth="3" />
                            <path d="M35 60L20 80H40L35 60Z" fill="#FF7D45" stroke="black" strokeWidth="3" />
                            <path d="M65 60L80 80H60L65 60Z" fill="#FF7D45" stroke="black" strokeWidth="3" />
                        </svg>
                    </motion.div>

                    <motion.div
                        animate={{ y: [10, -10, 10], rotate: [0, -10, 0] }}
                        transition={{ duration: 7, repeat: Infinity, ease: "easeInOut" }}
                        className="absolute top-[15%] right-[5%] z-10 w-32 md:w-48 pointer-events-none"
                    >
                        {/* Coin */}
                        <div className="w-full aspect-square rounded-full bg-brand-yellow border-4 border-black flex items-center justify-center shadow-[8px_8px_0px_0px_rgba(0,0,0,1)]">
                            <div className="text-black text-6xl font-bold">:)</div>
                        </div>
                    </motion.div>

                    <motion.div
                        animate={{ y: [0, 20, 0] }}
                        transition={{ duration: 5, repeat: Infinity, ease: "easeInOut" }}
                        className="absolute bottom-[20%] left-[-2%] z-10 w-32 md:w-56 pointer-events-none"
                    >
                        {/* Wallet */}
                        <div className="w-full aspect-[4/3] bg-brand-violet border-4 border-black rounded-3xl relative shadow-[8px_8px_0px_0px_rgba(0,0,0,1)] transform rotate-12">
                            <div className="absolute right-4 top-1/2 -translate-y-1/2 w-8 h-12 bg-black/20 rounded-md border-2 border-black"></div>
                        </div>
                    </motion.div>

                    {/* Central Form / Text */}
                    <div className="relative z-20 text-center w-full max-w-md px-4">
                        <h1 className="text-[10vw] md:text-[5vw] leading-[0.85] font-bold uppercase tracking-tighter text-white drop-shadow-lg mb-8">
                            Login
                        </h1>

                        {error && (
                            <div className="mb-6 p-4 bg-brand-coral/20 border border-brand-coral rounded-xl text-brand-coral bg-black/40 backdrop-blur-md text-sm font-bold font-sans">
                                {error}
                            </div>
                        )}

                        <form onSubmit={handleLogin} className="flex flex-col gap-4 font-sans text-left">
                            <input
                                required
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                                type="email"
                                placeholder="Email"
                                className="w-full px-6 py-4 bg-white/10 backdrop-blur-md border border-white/20 rounded-full focus:outline-none focus:border-brand-blue focus:bg-white/20 transition-all text-white placeholder-white/50"
                            />
                            <input
                                required
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                type="password"
                                placeholder="Password"
                                className="w-full px-6 py-4 bg-white/10 backdrop-blur-md border border-white/20 rounded-full focus:outline-none focus:border-brand-blue focus:bg-white/20 transition-all text-white placeholder-white/50"
                            />
                            <button
                                disabled={loading}
                                type="submit"
                                className="w-full py-4 bg-brand-green text-black font-bold uppercase tracking-widest rounded-full hover:scale-105 transition-all shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] active:translate-y-1 active:shadow-none disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                                {loading ? <Loader2 className="w-5 h-5 animate-spin mx-auto" /> : "Continue"}
                            </button>
                        </form>
                    </div>

                    {/* Bottom Actions */}
                    <div className="absolute bottom-24 left-0 w-full flex flex-col items-center gap-4 z-30 px-4 mt-8">
                        <div className="flex flex-col sm:flex-row gap-4 w-full max-w-md">
                            <button
                                onClick={handleGoogleLogin}
                                disabled={googleLoading}
                                className="flex-1 flex items-center justify-center gap-2 bg-[#4285F4] hover:bg-[#3367D6] text-white font-sans font-bold py-4 px-6 rounded-full transition-all hover:scale-105 shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] active:translate-y-1 active:shadow-none disabled:opacity-70"
                            >
                                {googleLoading ? <Loader2 className="w-5 h-5 animate-spin" /> : (
                                    <>
                                        <span className="font-bold text-lg">G</span>
                                        <span>Google</span>
                                    </>
                                )}
                            </button>
                            <button className="flex-1 flex items-center justify-center gap-2 bg-[#333333] hover:bg-black text-white font-sans font-bold py-4 px-6 rounded-full transition-all hover:scale-105 shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] active:translate-y-1 active:shadow-none">
                                <Apple className="w-5 h-5 fill-current" />
                                <span>Apple</span>
                            </button>
                        </div>

                        <button
                            onClick={handleMoreOptions}
                            className="w-full max-w-md bg-white/10 hover:bg-white/20 backdrop-blur-md border border-white/30 text-white font-sans font-medium py-4 px-6 rounded-full transition-all uppercase tracking-widest text-xs"
                        >
                            More options
                        </button>
                    </div>

                    {/* Footer Legal */}
                    <div className="absolute bottom-8 left-0 w-full text-center text-white/40 text-xs font-sans pointer-events-none">
                        By continuing, you agree to our <a href="#" className="underline hover:text-white pointer-events-auto">Terms of Service</a> and <a href="#" className="underline hover:text-white pointer-events-auto">Privacy Policy</a>
                    </div>

                </div>
            </motion.div>
        </AnimatePresence>
    );
}
