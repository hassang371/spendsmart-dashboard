"use client";
import React, { useState } from "react";
import Link from "next/link";
import { ArrowLeft, Loader2 } from "lucide-react";
import { supabase } from "../../lib/supabase/client";
import { motion } from "framer-motion";
import { useRouter } from "next/navigation";
import dynamic from 'next/dynamic';

const Lottie = dynamic(() => import('lottie-react'), { ssr: false });
import rocketAnimation from '@/public/slush/rocket.json';
import coinAnimation from '@/public/slush/coin.json';
import walletAnimation from '@/public/slush/wallet.json';

export default function SignupPage() {
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [name, setName] = useState("");
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [confirmationSent, setConfirmationSent] = useState(false);
    const router = useRouter();

    const handleSignup = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        setError(null);

        const { data, error: signupError } = await supabase.auth.signUp({
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
        } else if (data.session) {
            // Direct redirect if session exists (e.g. auto confirm enabled or existing session)
            router.push("/dashboard");
        } else {
            setConfirmationSent(true);
        }
        setLoading(false);
    };

    const handleGoogleLogin = async () => {
        setLoading(true);
        const { error } = await supabase.auth.signInWithOAuth({
            provider: "google",
            options: {
                redirectTo: `${window.location.origin}/auth/callback?next=/dashboard`,
            },
        });

        if (error) {
            setError(error.message);
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen bg-brand-light flex flex-col md:flex-row font-display selection:bg-brand-yellow selection:text-black">
            {/* Visual Side (Left) - Brand Blue Theme with Assets */}
            <div className="hidden md:flex w-1/2 bg-brand-blue items-center justify-center p-12 relative overflow-hidden">
                <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-20 mix-blend-overlay pointer-events-none"></div>
                
                {/* Floating Assets */}
                <motion.div
                    animate={{ y: [-10, 10, -10], rotate: [0, 5, 0] }}
                    transition={{ duration: 6, repeat: Infinity, ease: "easeInOut" }}
                    className="absolute top-[10%] left-[10%] w-48 pointer-events-none opacity-90"
                >
                    <Lottie animationData={rocketAnimation} loop={true} />
                </motion.div>

                <motion.div
                    animate={{ y: [10, -10, 10], rotate: [0, -10, 0] }}
                    transition={{ duration: 7, repeat: Infinity, ease: "easeInOut" }}
                    className="absolute bottom-[15%] right-[10%] w-48 pointer-events-none opacity-90"
                >
                    <Lottie animationData={coinAnimation} loop={true} />
                </motion.div>

                 <motion.div
                    animate={{ y: [0, 20, 0] }}
                    transition={{ duration: 5, repeat: Infinity, ease: "easeInOut" }}
                    className="absolute top-[40%] right-[15%] w-32 pointer-events-none opacity-80"
                >
                    <Lottie animationData={walletAnimation} loop={true} />
                </motion.div>


                <motion.div
                    initial={{ opacity: 0, x: -50 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.8 }}
                    className="relative z-10 max-w-lg text-left"
                >
                    <h2 className="text-6xl font-black mb-6 leading-[0.9] text-white tracking-tighter uppercase">
                        Join the <br />
                        <span className="text-brand-yellow italic">Revolution.</span>
                    </h2>
                    <p className="text-2xl text-white/90 font-bold uppercase tracking-wide">
                        Stop guessing. Start measuring.
                    </p>
                </motion.div>
            </div>

            {/* Form Side (Right) - Light Theme High Contrast */}
            <div className="flex-1 flex flex-col justify-center items-center p-8 bg-brand-light relative">
                <Link href="/" className="absolute top-8 left-8 flex items-center gap-2 text-black/40 hover:text-black transition-colors font-sans font-bold uppercase tracking-widest text-xs">
                    <ArrowLeft className="w-4 h-4" /> Back
                </Link>

                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="w-full max-w-sm"
                >
                    <div className="mb-10 text-center">
                        <div className="w-16 h-16 bg-black text-white rounded-2xl flex items-center justify-center rotate-3 mx-auto mb-6 shadow-hard">
                            <span className="font-display font-black text-3xl">S</span>
                        </div>
                        <h1 className="text-4xl font-black uppercase tracking-tighter text-black">Create Account</h1>
                        <p className="text-black/50 mt-2 font-bold font-sans">Join SCALE today.</p>
                    </div>

                    {error && (
                        <div className="mb-6 p-4 bg-brand-coral/20 border-2 border-brand-coral rounded-xl text-brand-coral text-sm font-bold font-sans">
                            {error}
                        </div>
                    )}

                    {confirmationSent ? (
                        <div className="space-y-4 text-center">
                            <div className="p-6 bg-brand-green/20 border-2 border-brand-green rounded-xl">
                                <h2 className="text-lg font-bold text-brand-green mb-2 font-display uppercase">Check your email</h2>
                                <p className="text-sm text-black/70 font-sans font-medium">
                                    We&apos;ve sent a confirmation link to <strong className="text-black">{email}</strong>. Please check your inbox.
                                </p>
                            </div>
                            <Link href="/login" className="inline-block text-black hover:underline font-bold uppercase tracking-wide text-sm">
                                Back to Login
                            </Link>
                        </div>
                    ) : (
                    <form onSubmit={handleSignup} className="space-y-4 font-sans">
                        <div>
                            <input
                                required
                                value={name}
                                onChange={(e) => setName(e.target.value)}
                                type="text"
                                placeholder="Full Name"
                                className="w-full px-6 py-4 bg-white border-2 border-black/10 rounded-full focus:outline-none focus:shadow-hard-sm focus:border-brand-blue transition-all text-black placeholder-black/40 font-bold"
                            />
                        </div>
                        <div>
                            <input
                                required
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                                type="email"
                                placeholder="name@example.com"
                                className="w-full px-6 py-4 bg-white border-2 border-black/10 rounded-full focus:outline-none focus:shadow-hard-sm focus:border-brand-blue transition-all text-black placeholder-black/40 font-bold"
                            />
                        </div>
                        <div>
                            <input
                                required
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                type="password"
                                placeholder="Password"
                                className="w-full px-6 py-4 bg-white border-2 border-black/10 rounded-full focus:outline-none focus:shadow-hard-sm focus:border-brand-blue transition-all text-black placeholder-black/40 font-bold"
                            />
                        </div>

                        <button
                            disabled={loading}
                            type="submit"
                            className="w-full py-4 bg-black text-white font-bold uppercase tracking-widest rounded-full hover:bg-brand-blue hover:text-white transition-all shadow-hard active:translate-y-1 active:shadow-none disabled:opacity-50 disabled:cursor-not-allowed border-2 border-black mt-4"
                        >
                            {loading ? <Loader2 className="mx-auto h-5 w-5 animate-spin" /> : "Create Account"}
                        </button>

                        <div className="relative my-8">
                            <div className="absolute inset-0 flex items-center"><div className="w-full border-t-2 border-black/5"></div></div>
                            <div className="relative flex justify-center text-xs uppercase font-bold tracking-widest"><span className="bg-brand-light px-2 text-black/40">Or continue with</span></div>
                        </div>

                        <button
                            type="button"
                            onClick={handleGoogleLogin}
                            className="w-full flex items-center justify-center gap-2 rounded-full border-2 border-black/10 bg-white px-4 py-3 text-sm font-bold text-black hover:shadow-hard active:translate-y-1 transition-all group"
                        >
                            <svg className="h-5 w-5 group-hover:scale-110 transition-transform" viewBox="0 0 24 24"><path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4" /><path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" /><path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05" /><path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335" /></svg>
                            Google
                        </button>
                    </form>
                    )}

                    <p className="mt-8 text-center text-sm font-bold font-sans text-black/50">
                        Already have an account? <Link href="/login" className="text-black hover:underline underline-offset-4 decoration-2">Login</Link>
                    </p>
                </motion.div>
            </div>
        </div>
    );
}
