"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, Loader2 } from "lucide-react";
import { supabase } from "../../lib/supabase/client";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";

export default function LoginPage() {
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [loading, setLoading] = useState(false);
    const [googleLoading, setGoogleLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const router = useRouter();

    useEffect(() => {
        const checkSession = async () => {
            const { data } = await supabase.auth.getSession();
            if (data.session) {
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

    return (
        <div className="min-h-screen bg-background flex flex-col md:flex-row">
            {/* Visual Side */}
            <div className="hidden md:flex w-1/2 bg-secondary items-center justify-center p-12 relative overflow-hidden">
                <div className="absolute inset-0 bg-slush-gradient opacity-10"></div>
                <div className="absolute top-[-20%] left-[-20%] w-[140%] h-[140%] bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-20 animate-pulse"></div>

                <motion.div
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ duration: 0.8 }}
                    className="relative z-10 max-w-md"
                >
                    <h2 className="text-5xl font-black mb-6 leading-tight">
                        See where your money goes. <br />
                        <span className="text-primary">Finally.</span>
                    </h2>
                    <p className="text-xl text-gray-400">Join 10,000+ users tracking their net worth with B.L.A.S.T. precision.</p>

                    {/* Abstract Phone/Card Visual */}
                    <motion.div
                        animate={{ y: [0, -10, 0] }}
                        transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
                        className="mt-12 bg-background border border-white/10 rounded-3xl p-6 rotate-3 shadow-2xl hover:rotate-0 transition-transform duration-500"
                    >
                        <div className="flex justify-between items-center mb-8">
                            <div className="w-12 h-12 bg-primary/20 rounded-full"></div>
                            <div className="w-20 h-4 bg-white/10 rounded-full"></div>
                        </div>
                        <div className="space-y-4">
                            <div className="h-16 bg-white/5 rounded-xl w-full"></div>
                            <div className="h-16 bg-white/5 rounded-xl w-full"></div>
                            <div className="h-16 bg-white/5 rounded-xl w-full"></div>
                        </div>
                    </motion.div>
                </motion.div>
            </div>

            {/* Form Side */}
            <div className="flex-1 flex flex-col justify-center items-center p-8 bg-background relative">
                <Link href="/" className="absolute top-8 left-8 flex items-center gap-2 text-gray-400 hover:text-white transition-colors">
                    <ArrowLeft className="w-4 h-4" /> Back
                </Link>

                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.2 }}
                    className="w-full max-w-sm"
                >
                    <div className="mb-10 text-center">
                        <motion.div
                            whileHover={{ rotate: 10 }}
                            className="w-12 h-12 bg-primary rounded-xl flex items-center justify-center rotate-3 border-2 border-black shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] mx-auto mb-4 cursor-pointer"
                        >
                            <span className="text-white font-mono font-bold text-xl">S</span>
                        </motion.div>
                        <h1 className="text-3xl font-bold">Welcome back</h1>
                    </div>

                    {error && (
                        <div className="mb-6 p-4 bg-red-500/10 border border-red-500/50 rounded-xl text-red-500 text-sm">
                            {error}
                        </div>
                    )}

                    <form onSubmit={handleLogin} className="space-y-4">
                        <div>
                            <label className="block text-sm font-medium text-gray-400 mb-1">Email</label>
                            <input
                                required
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                                type="email"
                                placeholder="name@example.com"
                                className="w-full px-4 py-3 bg-secondary border border-white/10 rounded-xl focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary transition-all text-white placeholder-gray-600"
                            />
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-gray-400 mb-1">Password</label>
                            <input
                                required
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                type="password"
                                placeholder="••••••••"
                                className="w-full px-4 py-3 bg-secondary border border-white/10 rounded-xl focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary transition-all text-white placeholder-gray-600"
                            />
                        </div>

                        <button
                            disabled={loading}
                            type="submit"
                            className="w-full py-3 bg-white text-black font-bold rounded-xl hover:bg-gray-200 transition-colors mt-4 flex items-center justify-center gap-2 disabled:opacity-50"
                        >
                            {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : "Continue"}
                        </button>

                        <div className="relative my-8">
                            <div className="absolute inset-0 flex items-center"><div className="w-full border-t border-white/10"></div></div>
                            <div className="relative flex justify-center text-sm"><span className="px-2 bg-background text-gray-500">or</span></div>
                        </div>

                        <button
                            type="button"
                            onClick={handleGoogleLogin}
                            disabled={googleLoading}
                            className="w-full py-3 bg-secondary border border-white/10 text-white font-medium rounded-xl hover:bg-white/5 transition-colors flex items-center justify-center gap-2 disabled:opacity-50"
                        >
                            {googleLoading ? <Loader2 className="w-5 h-5 animate-spin" /> : "Continue with Google"}
                        </button>
                    </form>

                    <p className="mt-8 text-center text-sm text-gray-500">
                        Don&apos;t have an account? <Link href="/signup" className="text-primary hover:underline">Sign up</Link>
                    </p>
                </motion.div>
            </div>
        </div>
    );
}
