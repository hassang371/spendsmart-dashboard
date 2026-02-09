
import React, { useRef } from 'react';
import { motion, useScroll, useTransform } from 'framer-motion';
import dynamic from 'next/dynamic';

const Lottie = dynamic(() => import('lottie-react'), { ssr: false });
import smileAnimation from '@/public/slush/icon-smiley.json';
import coinAnimation from '@/public/slush/coin.json';
import walletAnimation from '@/public/slush/wallet.json';

const ParallaxText: React.FC = () => {
    const containerRef = useRef<HTMLDivElement>(null);
    const { scrollYProgress } = useScroll({
        target: containerRef,
        offset: ["start end", "end start"]
    });

    // Parallax effects
    const y1 = useTransform(scrollYProgress, [0, 1], [100, -100]);
    const y2 = useTransform(scrollYProgress, [0, 1], [0, 0]); // Stationary
    const y3 = useTransform(scrollYProgress, [0, 1], [-100, 100]);

    return (
        <section ref={containerRef} className="py-32 bg-white overflow-hidden relative">
            <div className="container mx-auto px-4 relative z-10">
                <div className="flex flex-col gap-12 md:gap-24">
                    
                    {/* Row 1 */}
                    <motion.div style={{ y: y1 }} className="flex items-center gap-4 md:gap-8 opacity-80">
                        <h2 className="font-display text-7xl md:text-9xl font-bold uppercase tracking-tighter leading-none text-black">
                            ALL
                        </h2>
                        <div className="w-24 h-24 md:w-32 md:h-32">
                             <Lottie animationData={coinAnimation} loop={true} />
                        </div>
                         <h2 className="font-display text-7xl md:text-9xl font-bold uppercase italic tracking-tighter leading-none text-gray-400">
                            THINGS
                        </h2>
                    </motion.div>

                    {/* Row 2 */}
                    <motion.div style={{ y: y2 }} className="flex items-center justify-center gap-4 md:gap-8 z-20">
                         <h2 className="font-display text-8xl md:text-[12rem] font-black uppercase tracking-tighter leading-none text-brand-blue text-outline" style={{WebkitTextStroke: "3px black"}}>
                            MONEY
                        </h2>
                         <div className="w-32 h-32 md:w-48 md:h-48 -mt-8">
                             <Lottie animationData={smileAnimation} loop={true} />
                        </div>
                    </motion.div>

                     {/* Row 3 */}
                    <motion.div style={{ y: y3 }} className="flex items-center justify-end gap-4 md:gap-8 opacity-80">
                         <div className="w-24 h-24 md:w-32 md:h-32">
                             <Lottie animationData={walletAnimation} loop={true} />
                        </div>
                        <h2 className="font-display text-7xl md:text-9xl font-bold uppercase tracking-tighter leading-none text-black">
                           SIMPLIFIED.
                        </h2>
                    </motion.div>

                </div>
            </div>
            
             {/* Decorative Background Elements */}
             <div className="absolute top-1/2 left-0 w-full h-[1px] bg-black/10 -z-0"></div>
        </section>
    );
};

export default ParallaxText;
