"use client";
import React, { useEffect, useState } from "react";
import Navbar from "../components/landing/Navbar";
import Hero from "../components/landing/Hero";
import Marquee from "../components/landing/Marquee";
import Features from "../components/landing/Features";
import TabsSection from "../components/landing/TabsSection";
import Testimonials from "../components/landing/Testimonials";
import Footer from "../components/landing/Footer";
import CustomCursor from "../components/landing/CustomCursor";
import { supabase } from "../lib/supabase/client";
import { useRouter } from "next/navigation";
import { type AuthChangeEvent, type Session } from "@supabase/supabase-js";

export default function Home() {
    const router = useRouter();

    useEffect(() => {
        // Smooth scroll behavior hack
        document.documentElement.style.scrollBehavior = 'smooth';

        // Auth Check
        const checkSession = async () => {
            const { data: { user } } = await supabase.auth.getUser();
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
        <div className="relative min-h-screen w-full bg-brand-light font-sans selection:bg-brand-orange selection:text-white overflow-x-hidden">
            {/* Fixed Sticky Gradient Background */}
            <div className="fixed inset-0 z-0 bg-gradient-to-br from-brand-light via-[#E0EAFF] to-[#D6E4FF] pointer-events-none" />
            <div className="fixed inset-0 z-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-20 pointer-events-none mix-blend-overlay"></div>

            <div className="relative z-10">
                {/* Custom Cursor might conflict with strict content policies or pointer events, keeping it but ensuring pointer-events-none */}
                <div className="pointer-events-none hidden md:block">
                    <CustomCursor />
                </div>

                {/* Main App Content */}
                <Navbar onLoginClick={() => router.push("/login")} />

                <main>
                    <Hero />
                    <Marquee direction="left" />
                    <Features />
                    <TabsSection />
                    <Marquee direction="right" />
                    <Testimonials />
                </main>

                <Footer />
            </div>
        </div>
    );
}
