'use client';
import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ArrowLeft, Loader2, Apple } from 'lucide-react';
import { supabase } from '../../lib/supabase/client';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import dynamic from 'next/dynamic';

const Lottie = dynamic(() => import('lottie-react'), { ssr: false });
import rocketAnimation from '@/public/slush/rocket.json';
import coinAnimation from '@/public/slush/coin.json';
import walletAnimation from '@/public/slush/wallet.json';
import smileyAnimation from '@/public/slush/icon-smiley.json';

function LoginContent() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);
  const [sessionCheckSlow, setSessionCheckSlow] = useState(false);
  const router = useRouter();

  const searchParams = useSearchParams();
  const errorParam = searchParams.get('error');
  const [error, setError] = useState<string | null>(errorParam);

  useEffect(() => {
    const checkSession = async () => {
      const {
        data: { user },
      } = await supabase.auth.getUser();

      if (user) {
        router.replace('/dashboard');
      }
    };

    const timeout = setTimeout(() => {
      setSessionCheckSlow(true);
    }, 10000);

    checkSession().finally(() => clearTimeout(timeout));
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
      router.push('/dashboard');
    }
  };

  const handleGoogleLogin = async () => {
    setGoogleLoading(true);
    setError(null);

    const redirectTo = `${window.location.origin}/auth/callback?next=/dashboard`;
    const { error: googleError } = await supabase.auth.signInWithOAuth({
      provider: 'google',
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
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-[100] flex flex-col bg-brand-light text-black overflow-hidden font-display selection:bg-brand-yellow selection:text-black"
      >
        {/* Background Details */}
        <div className="absolute inset-0 z-0 opacity-30 pointer-events-none bg-[url('https://grainy-gradients.vercel.app/noise.svg')] mix-blend-multiply"></div>

        {/* Top Bar */}
        <div className="absolute top-0 left-0 w-full p-8 flex justify-center z-20">
          <h1
            className="text-4xl font-black tracking-tighter uppercase text-black"
            style={{ transform: 'scaleY(1.2)' }}
          >
            SCALE
          </h1>
        </div>

        <Link
          href="/"
          className="absolute top-8 left-8 flex items-center gap-2 text-black/50 hover:text-black transition-colors z-30 font-sans font-bold uppercase tracking-widest text-sm"
        >
          <ArrowLeft className="w-5 h-5" /> Back
        </Link>

        {/* Main Content */}
        <div className="relative flex-1 flex flex-col items-center justify-center w-full max-w-[1600px] mx-auto">
          {/* Floating Lottie Elements */}
          <motion.div
            animate={{ y: [-10, 10, -10], rotate: [0, 5, 0] }}
            transition={{ duration: 6, repeat: Infinity, ease: 'easeInOut' }}
            className="absolute top-[15%] left-[5%] md:left-[10%] z-10 w-32 md:w-56 pointer-events-none opacity-90"
          >
            <Lottie animationData={rocketAnimation} loop={true} />
          </motion.div>

          <motion.div
            animate={{ y: [10, -10, 10], rotate: [0, -10, 0] }}
            transition={{ duration: 7, repeat: Infinity, ease: 'easeInOut' }}
            className="absolute top-[20%] right-[5%] md:right-[15%] z-10 w-32 md:w-48 pointer-events-none opacity-90"
          >
            <Lottie animationData={coinAnimation} loop={true} />
          </motion.div>

          <motion.div
            animate={{ y: [0, 20, 0] }}
            transition={{ duration: 5, repeat: Infinity, ease: 'easeInOut' }}
            className="absolute bottom-[15%] left-[10%] z-10 w-28 md:w-40 pointer-events-none opacity-90"
          >
            <Lottie animationData={walletAnimation} loop={true} />
          </motion.div>

          {/* Smiley - Added as requested */}
          <motion.div
            animate={{ y: [0, -15, 0], rotate: [0, 10, 0] }}
            transition={{ duration: 6, repeat: Infinity, ease: 'easeInOut', delay: 1 }}
            className="absolute bottom-[20%] right-[10%] z-10 w-28 md:w-40 pointer-events-none opacity-90"
          >
            <Lottie animationData={smileyAnimation} loop={true} />
          </motion.div>

          {/* Central Form Card */}
          <div className="relative z-20 text-center w-full max-w-md px-4">
            <div className="bg-white border-2 border-black p-8 md:p-12 rounded-[2.5rem] shadow-hard relative overflow-hidden text-black">
              <h1
                className="text-6xl md:text-7xl font-black uppercase tracking-tighter mb-8 text-black"
                style={{ transform: 'scaleY(1.1)' }}
              >
                Login
              </h1>

              {sessionCheckSlow && !error && (
                <div className="mb-6 p-4 bg-brand-yellow/20 border-2 border-brand-yellow rounded-xl text-black/70 text-sm font-bold font-sans">
                  This is taking longer than usual. Please check your connection.
                </div>
              )}

              {error && (
                <div className="mb-6 p-4 bg-brand-coral/20 border-2 border-brand-coral rounded-xl text-brand-coral text-sm font-bold font-sans">
                  {error}
                </div>
              )}

              <form
                onSubmit={handleLogin}
                className="flex flex-col gap-4 font-sans text-left relative z-10"
              >
                <input
                  required
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  type="email"
                  placeholder="Email"
                  className="w-full px-6 py-4 bg-brand-light border-2 border-black/10 rounded-full focus:outline-none focus:shadow-hard-sm focus:border-brand-blue transition-all text-black placeholder-black/40 font-bold"
                />
                <input
                  required
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  type="password"
                  placeholder="Password"
                  className="w-full px-6 py-4 bg-brand-light border-2 border-black/10 rounded-full focus:outline-none focus:shadow-hard-sm focus:border-brand-blue transition-all text-black placeholder-black/40 font-bold"
                />
                <button
                  disabled={loading}
                  type="submit"
                  className="w-full py-4 bg-black text-white font-bold uppercase tracking-widest rounded-full hover:bg-brand-blue hover:text-white transition-all shadow-hard active:translate-y-1 active:shadow-none disabled:opacity-50 disabled:cursor-not-allowed border-2 border-black"
                >
                  {loading ? <Loader2 className="w-5 h-5 animate-spin mx-auto" /> : 'Continue'}
                </button>
              </form>
              {/* Actions embedded in card or below? Slush has Google/Apple buttons below form usually or inside. Putting inside for cleaner unit. */}
              <div className="flex flex-col gap-3 mt-6">
                <div className="flex gap-3">
                  <button
                    onClick={handleGoogleLogin}
                    disabled={googleLoading}
                    className="flex-1 flex items-center justify-center gap-2 bg-brand-light hover:bg-white text-black border-2 border-black/10 font-sans font-bold py-3 px-4 rounded-full transition-all hover:shadow-hard active:translate-y-1 active:shadow-none disabled:opacity-70 group"
                  >
                    {googleLoading ? (
                      <Loader2 className="w-5 h-5 animate-spin" />
                    ) : (
                      <>
                        <span className="font-bold text-lg group-hover:text-blue-500 transition-colors">
                          G
                        </span>
                      </>
                    )}
                  </button>
                  <button
                    disabled
                    className="flex-1 flex items-center justify-center gap-2 bg-brand-light text-black/40 border-2 border-black/5 font-sans font-bold py-3 px-4 rounded-full cursor-not-allowed"
                  >
                    <Apple className="w-5 h-5 fill-current" />
                  </button>
                </div>
              </div>

              <div className="mt-8 pt-6 border-t border-black/10">
                <p className="font-sans font-bold text-sm text-black/60">
                  Don&apos;t have an account?{' '}
                  <Link
                    href="/signup"
                    className="text-black hover:underline underline-offset-4 decoration-2"
                  >
                    Sign up
                  </Link>
                </p>
              </div>
            </div>
          </div>
        </div>
      </motion.div>
    </AnimatePresence>
  );
}

export default function LoginPage() {
  return (
    <React.Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center bg-brand-light">
          <Loader2 className="w-8 h-8 animate-spin text-black" />
        </div>
      }
    >
      <LoginContent />
    </React.Suspense>
  );
}
