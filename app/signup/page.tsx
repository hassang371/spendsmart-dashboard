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

        const { data, error: signupError } = await supabase.auth.signUp({
            email,
            password,
            options: {
                emailRedirectTo: `${window.location.origin}/auth/callback?next=/dashboard`,
                data: {
                    full_name: name,
                },
            },
        });

        if (signupError) {
            setError(signupError.message);
            setLoading(false);
        } else {
            if (data.user) {
                router.push("/login");
            }
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
                        <p className="text-gray-500 mt-2">Join SpendSmart today.</p>
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
                            className="w-full py-3 bg-white text-black font-bold rounded-xl hover:bg-gray-200 transition-colors mt-4 flex items-center justify-center gap-2 group disabled:opacity-50"
                        >
                            {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : "Sign Up"}
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
