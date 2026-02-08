import React from 'react';
import Button from './Button';
import { Twitter, Instagram, Youtube, Disc } from 'lucide-react';

const Footer: React.FC = () => {
  const currentYear = new Date().getFullYear();

  return (
    <footer className="bg-brand-dark pt-24 pb-12 text-white">
      <div className="container mx-auto px-4">
        
        {/* Big Blocky Sections */}
        <div className="grid gap-6 md:grid-cols-2">
            {/* Left Block - Brand */}
            <div className="flex flex-col justify-between rounded-[2.5rem] bg-brand-orange p-10 text-brand-dark min-h-[400px] relative overflow-hidden group">
                <div className="absolute top-0 right-0 p-4 transition-transform group-hover:scale-150 duration-700">
                    <div className="w-32 h-32 bg-black rounded-full mix-blend-overlay opacity-20 blur-2xl"/>
                </div>
                <div>
                    <h2 className="font-display text-[12vw] md:text-[10rem] font-bold leading-[0.8] tracking-tighter uppercase">
                        SCALE
                    </h2>
                </div>
                <div className="mt-auto">
                    <p className="font-display text-5xl font-bold uppercase leading-none">
                        Money, <br/> Measured.
                    </p>
                </div>
            </div>

            {/* Right Block - CTA */}
            <div className="flex flex-col justify-center items-center text-center rounded-[2.5rem] bg-brand-blue p-10 text-brand-dark min-h-[400px]">
                <h2 className="font-display text-6xl md:text-8xl font-bold leading-[0.85] tracking-tighter uppercase mb-8">
                    GET SCALE <br/> <span className="text-outline-white">NOW.</span>
                </h2>
                <div className="flex flex-wrap gap-4 justify-center">
                    <Button variant="white" className="!px-10 !py-4 text-xl shadow-hard hover:-translate-y-1">Download App</Button>
                    <Button variant="dark" className="!px-10 !py-4 text-xl shadow-hard hover:-translate-y-1">Web Dashboard</Button>
                </div>
            </div>
        </div>

        {/* Large Green Download Banner */}
        <div className="mt-6 rounded-[2.5rem] bg-brand-green p-10 md:p-16 text-brand-dark flex flex-col md:flex-row items-center justify-between gap-10">
            <div className="max-w-3xl">
                <h2 className="font-display text-5xl md:text-7xl font-bold uppercase leading-[0.9] tracking-tighter italic">
                    DOWNLOAD SCALE. <br/>
                    THEN MAKE IT ALL HAPPEN.
                </h2>
            </div>
            <div className="grid grid-cols-2 gap-x-12 gap-y-4 font-display text-xl md:text-2xl font-bold uppercase text-right">
                <a href="#" className="hover:underline decoration-4 underline-offset-4">Home</a>
                <a href="#" className="hover:underline decoration-4 underline-offset-4">Security</a>
                <a href="#" className="hover:underline decoration-4 underline-offset-4">Features</a>
                <a href="#" className="hover:underline decoration-4 underline-offset-4">Download</a>
                <a href="#" className="hover:underline decoration-4 underline-offset-4">Get Started</a>
                <a href="#" className="hover:underline decoration-4 underline-offset-4">Guides</a>
            </div>
        </div>

        {/* Bottom Socials & Copyright */}
        <div className="mt-6 grid gap-6 md:grid-cols-4">
            <div className="bg-white rounded-[2rem] aspect-square flex items-center justify-center text-black hover:bg-brand-yellow transition-colors group cursor-pointer border-2 border-transparent hover:border-black">
                <Disc className="w-20 h-20 group-hover:rotate-180 transition-transform duration-500" />
            </div>
            <div className="bg-white rounded-[2rem] aspect-square flex items-center justify-center text-black hover:bg-brand-violet transition-colors group cursor-pointer border-2 border-transparent hover:border-black">
                <Twitter className="w-20 h-20 group-hover:scale-110 transition-transform" />
            </div>
            <div className="bg-white rounded-[2rem] aspect-square flex items-center justify-center text-black hover:bg-brand-coral transition-colors group cursor-pointer border-2 border-transparent hover:border-black">
                <Instagram className="w-20 h-20 group-hover:scale-110 transition-transform" />
            </div>
            <div className="bg-white rounded-[2rem] aspect-square flex items-center justify-center text-black hover:bg-brand-blue transition-colors group cursor-pointer border-2 border-transparent hover:border-black">
                <Youtube className="w-20 h-20 group-hover:scale-110 transition-transform" />
            </div>
        </div>

        <div className="mt-12 flex flex-col md:flex-row justify-between items-end gap-6 text-gray-400 font-sans text-sm font-bold uppercase">
            <div className="flex gap-6">
                <a href="#" className="hover:text-white">Privacy Notice</a>
                <a href="#" className="hover:text-white">Terms of Service</a>
                <a href="#" className="hover:text-white">Brand Assets</a>
            </div>
            <p>© {currentYear} SCALE LABS, INC.</p>
        </div>
      </div>
    </footer>
  );
};

export default Footer;