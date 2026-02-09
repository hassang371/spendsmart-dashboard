import React, { useRef } from 'react';
import { motion, useScroll, useTransform } from 'framer-motion';
import Button from './Button';
import { ChevronDown } from 'lucide-react';
import Image from 'next/image';
import dynamic from 'next/dynamic';

// Dynamic import for Lottie to avoid SSR issues
const Lottie = dynamic(() => import('lottie-react'), { ssr: false });

import rocketAnimation from '@/public/slush/rocket.json';
import walletAnimation from '@/public/slush/wallet.json';
import goldCoinAnimation from '@/public/slush/67fec9c205180e5c013941f7_GetStashed - Onboarding - Icon Coin - V01.json';
import smileyAnimation from '@/public/slush/icon-smiley.json';

const Hero: React.FC = () => {
  const containerRef = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({
    target: containerRef,
    offset: ["start start", "end start"]
  });

  const y = useTransform(scrollYProgress, [0, 1], ["0%", "50%"]);
  const textY = useTransform(scrollYProgress, [0, 1], ["0%", "20%"]);
  const logoY = useTransform(scrollYProgress, [0, 1], ["0%", "30%"]);

  return (
    <section ref={containerRef} className="relative min-h-[100vh] w-full overflow-hidden bg-brand-bg pt-20">

      {/* Parallax Background 'S' */}
      <motion.div
        style={{ y: logoY }}
        className="absolute top-0 left-0 w-full h-full z-0 flex items-center justify-center opacity-80 pointer-events-none"
      >
        <Image
          src="/slush/bg-s-logo.avif"
          alt="Slush S Logo Background"
          width={1200}
          height={1200}
          className="w-[120%] max-w-none md:w-[80%] h-auto object-contain mix-blend-multiply"
          priority
        />
      </motion.div>


      {/* Main Content Container */}
      <div className="relative z-10 container mx-auto flex flex-col items-center justify-center h-full px-4 min-h-[80vh]">

        {/* Massive Typography Layer - Compacted */}
        <motion.div style={{ y: textY }} className="relative z-20 text-center w-full flex flex-col items-center justify-center -space-y-4 md:-space-y-8">
          <h1
            className="font-display font-black text-[22vw] md:text-[25vw] leading-[0.8] tracking-tighter text-black select-none z-10 scale-y-125"
          >
            SCALE
          </h1>
        </motion.div>

        {/* 3D Floating Lottie Elements - Restored Positions & Smiley Added */}
        <div className="absolute inset-0 z-30 pointer-events-none">
          {/* Element 1: Rocket - Top Left (Restored) */}
          <motion.div
            animate={{ y: [0, -20, 0], rotate: [0, 5, -5, 0] }}
            transition={{ duration: 6, repeat: Infinity, ease: "easeInOut" }}
            className="absolute top-[10%] left-[5%] md:left-[10%] w-32 h-32 md:w-56 md:h-56 lg:w-72 lg:h-72"
          >
            <Lottie animationData={rocketAnimation} loop={true} />
          </motion.div>

          {/* Element 2: Smiley - Top Right (Added as requested) */}
          <motion.div
            animate={{ y: [0, 30, 0], rotate: [0, -10, 0] }}
            transition={{ duration: 7, repeat: Infinity, ease: "easeInOut", delay: 1 }}
            className="absolute top-[15%] right-[5%] md:right-[10%] w-28 h-28 md:w-40 md:h-40"
          >
            <Lottie animationData={smileyAnimation} loop={true} />
          </motion.div>

          {/* Element 3: Wallet - Bottom Right (Restored position concept) */}
          <motion.div
            animate={{ y: [0, -25, 0], x: [0, 10, 0] }}
            transition={{ duration: 5, repeat: Infinity, ease: "easeInOut", delay: 2 }}
            className="absolute bottom-[20%] right-[10%] md:right-[15%] w-24 h-24 md:w-36 md:h-36"
          >
            <Lottie animationData={walletAnimation} loop={true} />
          </motion.div>

          {/* Element 4: Gold Coin - Bottom Left (Restored position concept) */}
          <motion.div
            animate={{ y: [0, 20, 0], rotate: [0, 10, -5, 0] }}
            transition={{ duration: 8, repeat: Infinity, ease: "easeInOut", delay: 1.5 }}
            className="absolute bottom-[20%] left-[10%] md:left-[20%] w-20 h-20 md:w-32 md:h-32"
          >
            <Lottie animationData={goldCoinAnimation} loop={true} />
          </motion.div>
        </div>

        {/* CTAs - Compact & Overlapping */}
        <motion.div
          style={{ y }}
          className="relative z-40 mt-24 md:mt-32 flex flex-col sm:flex-row gap-6 pointer-events-auto"
        >
          <Button
            variant="brand"
            href="/login"
            className="!text-base !px-8 !py-3 !rounded-full !bg-black !text-white hover:!bg-brand-blue shadow-slush hover:shadow-xl transition-all"
          >
            Launch App
          </Button>
          <Button
            variant="outline"
            href="/dashboard"
            className="!text-base !px-8 !py-3 !rounded-full !bg-white !text-black !border-black hover:!bg-brand-yellow shadow-slush"
          >
            Learn More
          </Button>
        </motion.div>

      </div>

      {/* Scroll Indicator */}
      <motion.div
        animate={{ y: [0, 10, 0] }}
        transition={{ duration: 2, repeat: Infinity }}
        className="absolute bottom-8 left-1/2 -translate-x-1/2 z-40 text-black/50"
      >
        <ChevronDown className="w-10 h-10" />
      </motion.div>

    </section>
  );
};

export default Hero;