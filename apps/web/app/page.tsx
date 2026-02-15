'use client';
import React from 'react';
import Navbar from '@/components/landing/Navbar';
import Hero from '@/components/landing/Hero';
import Marquee from '@/components/landing/Marquee';

import TabsSection from '@/components/landing/TabsSection';
import Testimonials from '@/components/landing/Testimonials';
import Footer from '@/components/landing/Footer';
import CustomCursor from '@/components/landing/CustomCursor';

import ParallaxText from '@/components/landing/ParallaxText';
import FeatureSlider from '@/components/landing/FeatureSlider';
import ImpactCards from '@/components/landing/ImpactCards';

export default function Home() {
  // Auth check handled by middleware
  // Scroll behavior handled by globals.css

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
        <Navbar />

        <main>
          <Hero />
          <ParallaxText />
          <FeatureSlider />
          <ImpactCards />
          <TabsSection />
          <Marquee direction="right" />
          <Testimonials />
        </main>

        <Footer />
      </div>
    </div>
  );
}
