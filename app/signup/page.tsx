"use client";
import { useState } from "react";
import Link from "next/link";
import { ArrowLeft, Loader2 } from "lucide-react";
import { supabase } from "../../lib/supabase/client";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";

export default function SignupPage() {
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [name, setName] = useState("");
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const router = useRouter();

    const handleSignup = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        setError(null);

        const { error: signupError } = await supabase.auth.signUp({
            email,
            password,
            options: {
                data: {
                    full_name: name,
                },
            },
        });

        if (signupError) {
            setError(signupError.message);
        } else {
            // Check if email confirmation is required? usually yes.
            // For now, let's assume auto-login or redirect.
            router.push("/dashboard");
        }
        setLoading(false);
    };

    const handleGoogleLogin = async () => {
        setLoading(true);
        const { error } = await supabase.auth.signInWithOAuth({
            provider: "google",
            options: {
                redirectTo: `${window.location.origin}/auth/callback`,
            },
        });

        if (error) {
            setError(error.message);
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen bg-background flex flex-col md:flex-row">
            {/* Visual Side */}
            <div className="hidden md:flex w-1/2 bg-secondary items-center justify-center p-12 relative overflow-hidden">
                <div className="absolute inset-0 bg-slush-gradient opacity-10"></div>
                <div className="absolute top-[-20%] left-[-20%] w-[140%] h-[140%] bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-20 animate-pulse"></div>

                <motion.div
                    initial={{ opacity: 0, x: -50 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.8 }}
                    className="relative z-10 max-w-md"
                >
                    <h2 className="text-5xl font-black mb-6 leading-tight">
                        Start your journey to <br />
                        <span className="text-primary italic">Financial Freedom.</span>
                    </h2>
                    <p className="text-xl text-gray-400">Zero hidden fees. Zero bullshit. Just pure clarity.</p>

                    <motion.div
                        initial={{ rotate: 10, scale: 0.9 }}
                        animate={{ rotate: 3, scale: 1 }}
                        transition={{ delay: 0.5, type: "spring" }}
                        className="mt-12 bg-background border border-white/10 rounded-3xl p-6 shadow-2xl"
                    >
                        <div className="h-4 bg-primary/20 rounded-full w-1/2 mb-6"></div>
                        <div className="space-y-4">
                            <div className="h-10 bg-white/5 rounded-xl w-full"></div>
                            <div className="h-10 bg-white/5 rounded-xl w-3/4"></div>
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
                    className="w-full max-w-sm"
                >
                    <div className="mb-10 text-center">
                        <div className="w-12 h-12 bg-primary rounded-xl flex items-center justify-center rotate-3 border-2 border-black shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] mx-auto mb-4">
                            <span className="text-white font-mono font-bold text-xl">S</span>
                        </div>
                        <h1 className="text-3xl font-bold">Create an account</h1>
                        <p className="text-gray-500 mt-2">Join SCALE today.</p>
                    </div>

                    {error && (
                        <div className="mb-6 p-4 bg-red-500/10 border border-red-500/50 rounded-xl text-red-500 text-sm">
                            {error}
                        </div>
                    )}

                    <form onSubmit={handleSignup} className="space-y-4">
                        <div>
                            <label className="block text-sm font-medium text-gray-400 mb-1">Full Name</label>
                            <input
                                required
                                value={name}
                                onChange={(e) => setName(e.target.value)}
                                type="text"
                                placeholder="John Doe"
                                className="w-full px-4 py-3 bg-secondary border border-white/10 rounded-xl focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary transition-all text-white placeholder-gray-600"
                            />
                        </div>
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
                            className="w-full rounded-2xl bg-gradient-to-r from-blue-600 to-indigo-600 px-4 py-3 text-sm font-bold text-white shadow-lg shadow-blue-500/25 transition-all hover:scale-[1.02] hover:shadow-blue-500/40 disabled:opacity-50"
                        >
                            {loading ? <Loader2 className="mx-auto h-5 w-5 animate-spin" /> : "Create Account"}
                        </button>

                        <div className="relative my-4">
                            <div className="absolute inset-0 flex items-center"><div className="w-full border-t border-white/10"></div></div>
                            <div className="relative flex justify-center text-xs uppercase"><span className="bg-[#0B1221] px-2 text-gray-500">Or continue with</span></div>
                        </div>

                        <button
                            type="button"
                            onClick={handleGoogleLogin}
                            className="w-full flex items-center justify-center gap-2 rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm font-bold text-white hover:bg-white/10 transition-all"
                        >
                            <svg className="h-5 w-5" viewBox="0 0 24 24"><path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4" /><path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" /><path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05" /><path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335" /></svg>
                            Google
                        </button>
                    </form>

                    <p className="mt-8 text-center text-sm text-gray-500">
                        Already have an account? <Link href="/login" className="text-primary hover:underline">Login</Link>
                    </p>
                </motion.div>
            </div>
        </div>
    );
}
