import React, { useRef } from 'react';
import { motion, useScroll, useTransform } from 'framer-motion';
import Button from './Button';
import AppPreview from './AppPreview';

const Hero: React.FC = () => {
  const containerRef = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({
    target: containerRef,
    offset: ["start start", "end start"]
  });

  const y = useTransform(scrollYProgress, [0, 1], ["0%", "30%"]);
  const opacity = useTransform(scrollYProgress, [0, 0.8], [1, 0]);

  return (
    <>
      <section ref={containerRef} className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden pt-20">
        
        {/* Full Screen Animated Background */}
        <div className="absolute inset-0 z-0">
            {/* Mesh Gradient Animation */}
            <div className="absolute inset-0 bg-brand-light opacity-50"></div>
            <div className="absolute top-[-50%] left-[-50%] h-[200%] w-[200%] animate-spin-slow opacity-60">
                <div className="absolute top-[20%] left-[20%] h-[40vw] w-[40vw] rounded-full bg-brand-blue mix-blend-multiply blur-[128px] animate-blob"></div>
                <div className="absolute top-[20%] right-[20%] h-[40vw] w-[40vw] rounded-full bg-brand-violet mix-blend-multiply blur-[128px] animate-blob animation-delay-2000"></div>
                <div className="absolute bottom-[20%] left-[30%] h-[40vw] w-[40vw] rounded-full bg-brand-green mix-blend-multiply blur-[128px] animate-blob animation-delay-4000"></div>
                <div className="absolute bottom-[20%] right-[30%] h-[40vw] w-[40vw] rounded-full bg-brand-yellow mix-blend-multiply blur-[128px] animate-blob animation-delay-6000"></div>
            </div>
            {/* Grain Overlay */}
            <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-20 pointer-events-none mix-blend-overlay"></div>
        </div>

        {/* Content - Lower Z-Index than floaters */}
        <div className="container relative z-10 mx-auto flex h-full flex-col items-center justify-center px-4 text-center mt-10">
          <motion.div style={{ y, opacity }} className="relative flex flex-col items-center w-full max-w-6xl">
            
            {/* Floating 3D Elements - Positioned closer to center and overlapping text */}
            <motion.div 
              animate={{ y: [0, -20, 0], rotate: [0, 5, 0] }}
              transition={{ duration: 5, repeat: Infinity, ease: "easeInOut" }}
              className="absolute left-[15%] top-[10%] z-40 hidden lg:block"
            >
              <div className="flex h-24 w-24 items-center justify-center rounded-[2rem] border-4 border-black bg-brand-coral shadow-hard-lg text-5xl rotate-12 transform hover:scale-110 transition-transform">
                🚀
              </div>
            </motion.div>

            <motion.div 
              animate={{ y: [0, 30, 0], rotate: [0, -10, 0] }}
              transition={{ duration: 6, repeat: Infinity, ease: "easeInOut", delay: 1 }}
              className="absolute right-[18%] top-[15%] z-40 hidden lg:block"
            >
              <div className="flex h-32 w-32 items-center justify-center rounded-full border-4 border-black bg-brand-yellow shadow-hard-lg text-6xl -rotate-12 transform hover:scale-110 transition-transform">
                🤑
              </div>
            </motion.div>

            <motion.div 
              animate={{ y: [0, -15, 0], x: [0, 10, 0] }}
              transition={{ duration: 4, repeat: Infinity, ease: "easeInOut", delay: 0.5 }}
              className="absolute left-[20%] bottom-[25%] z-40 hidden lg:block"
            >
              <div className="flex h-20 w-20 items-center justify-center rounded-full border-4 border-black bg-brand-green shadow-hard text-4xl transform hover:scale-110 transition-transform">
                💎
              </div>
            </motion.div>

            <motion.div 
              animate={{ y: [0, 20, 0], x: [0, -10, 0] }}
              transition={{ duration: 7, repeat: Infinity, ease: "easeInOut", delay: 1.5 }}
              className="absolute right-[22%] bottom-[20%] z-40 hidden lg:block"
            >
              <div className="flex h-24 w-36 items-center justify-center rounded-[2rem] border-4 border-black bg-brand-violet shadow-hard text-4xl -rotate-6 transform hover:scale-110 transition-transform">
                👛
              </div>
            </motion.div>

            {/* Main Text */}
            <h1 className="font-display text-[25vw] font-bold leading-[0.75] tracking-tighter text-black lg:text-[400px] drop-shadow-sm select-none mix-blend-hard-light scale-y-125 z-10">
              SCALE
            </h1>

            <div className="relative -mt-4 md:-mt-8 flex flex-col items-center gap-4 z-30">
              <h2 className="font-display text-5xl font-semibold uppercase tracking-tight md:text-8xl bg-brand-white/80 backdrop-blur-sm px-6 py-2 rounded-xl border-2 border-black transform rotate-1 shadow-hard-sm">
                Finance, Leveled Up.
              </h2>
              <p className="font-sans text-xl font-medium uppercase tracking-widest text-gray-900 md:text-2xl max-w-2xl bg-brand-green px-6 py-2 border-2 border-black transform -rotate-1 shadow-hard-sm">
                Personal Financing Made Easy
              </p>
            </div>

            <div className="mt-16 flex flex-col gap-6 sm:flex-row z-30">
              <Button variant="dark" icon href="#" className="!text-xl !px-10 !py-5 shadow-hard hover:shadow-glow" glow>Launch Web App</Button>
              <Button variant="white" icon href="#" className="!text-xl !px-10 !py-5 shadow-hard hover:shadow-hard-sm">Download App</Button>
            </div>
          </motion.div>
        </div>
      </section>

      {/* App Interface Reveal Section */}
      <section className="relative z-30 -mt-32 pb-32">
        <div className="container mx-auto px-4">
          <AppPreview />
        </div>
      </section>
    </>
  );
};

export default Hero;