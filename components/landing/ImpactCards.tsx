
import React from 'react';
import Button from './Button';
import dynamic from 'next/dynamic';

const Lottie = dynamic(() => import('lottie-react'), { ssr: false });
import devicesAnimation from '@/public/slush/icon-devices.json';
import keysAnimation from '@/public/slush/wallet.json'; // Reusing generic wallet for now if keys not found
import codeAnimation from '@/public/slush/icon-cards.json'; // Reusing for placeholder


const ImpactCards: React.FC = () => {
    return (
        <section className="py-24 bg-brand-light">
             <div className="container mx-auto px-4 text-center mb-16">
                <h2 className="font-display text-5xl md:text-7xl font-bold uppercase tracking-tighter leading-none mb-4">
                    Finance for Humans.
                </h2>
                <h2 className="font-display text-5xl md:text-7xl font-bold uppercase tracking-tighter leading-none text-brand-blue italic">
                    Powered by Agents.
                </h2>
            </div>

            <div className="container mx-auto px-4 grid gap-8 md:grid-cols-3">
                {/* Card 1 */}
                <div className="bg-white rounded-[2.5rem] border-4 border-black p-8 shadow-hard relative overflow-hidden group hover:-translate-y-2 transition-transform">
                     <h3 className="font-display text-4xl font-bold uppercase italic mb-8 relative z-10">
                        For Savers
                    </h3>
                     <Button variant="dark" href="/signup" className="relative z-10">Start Saving</Button>
                     <div className="absolute bottom-[-20%] right-[-20%] w-64 h-64 opacity-50 group-hover:opacity-100 transition-opacity">
                         <Lottie animationData={devicesAnimation} loop={true} />
                     </div>
                </div>

                 {/* Card 2 */}
                <div className="bg-brand-violet rounded-[2.5rem] border-4 border-black p-8 shadow-hard relative overflow-hidden group hover:-translate-y-2 transition-transform">
                     <h3 className="font-display text-4xl font-bold uppercase italic mb-8 relative z-10 text-white">
                        For Spenders
                    </h3>
                     <Button variant="outline" href="/signup" className="bg-white text-black relative z-10">Optimize Spend</Button>
                      <div className="absolute bottom-[-10%] right-[-10%] w-56 h-56 opacity-80 group-hover:scale-110 transition-transform">
                         <Lottie animationData={keysAnimation} loop={true} />
                     </div>
                </div>

                 {/* Card 3 */}
                <div className="bg-brand-blue rounded-[2.5rem] border-4 border-black p-8 shadow-hard relative overflow-hidden group hover:-translate-y-2 transition-transform">
                     <h3 className="font-display text-4xl font-bold uppercase italic mb-8 relative z-10 text-white">
                        For Planners
                    </h3>
                     <Button variant="outline" href="/signup" className="bg-white text-black relative z-10">Build Wealth</Button>
                      <div className="absolute bottom-[-10%] right-[-10%] w-56 h-56 opacity-80 group-hover:rotate-12 transition-transform">
                         <Lottie animationData={codeAnimation} loop={true} />
                     </div>
                </div>
            </div>
        </section>
    );
};

export default ImpactCards;
