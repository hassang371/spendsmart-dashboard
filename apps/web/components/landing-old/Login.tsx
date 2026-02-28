import React from 'react';
import { motion } from 'framer-motion';
import { ArrowLeft, Apple } from 'lucide-react';

interface LoginProps {
  onBack: () => void;
}

const Login: React.FC<LoginProps> = ({ onBack }) => {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-[100] flex flex-col bg-brand-slushBlue text-white overflow-hidden font-display"
    >
      {/* Top Bar */}
      <div className="absolute top-0 left-0 w-full p-8 flex justify-center z-20">
        <h1 className="text-4xl font-bold tracking-tighter uppercase">SCALE</h1>
      </div>

      <button
        onClick={onBack}
        className="absolute top-8 left-8 flex items-center gap-2 text-white/50 hover:text-white transition-colors z-30 font-sans font-bold uppercase tracking-widest text-sm"
      >
        <ArrowLeft className="w-5 h-5" /> Back
      </button>

      {/* Main Content */}
      <div className="relative flex-1 flex flex-col items-center justify-center w-full max-w-[1600px] mx-auto">
        {/* Floating Elements */}
        <motion.div
          animate={{ y: [-10, 10, -10], rotate: [0, 5, 0] }}
          transition={{ duration: 6, repeat: Infinity, ease: 'easeInOut' }}
          className="absolute top-[20%] left-[10%] z-10 w-24 md:w-40"
        >
          {/* Rocket */}
          <svg
            viewBox="0 0 100 100"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            className="w-full drop-shadow-2xl"
          >
            <path d="M50 5L65 30H35L50 5Z" fill="#FF7D45" stroke="black" strokeWidth="3" />
            <rect
              x="35"
              y="30"
              width="30"
              height="40"
              fill="white"
              stroke="black"
              strokeWidth="3"
            />
            <circle cx="50" cy="50" r="8" fill="#4892FF" stroke="black" strokeWidth="3" />
            <path d="M35 60L20 80H40L35 60Z" fill="#FF7D45" stroke="black" strokeWidth="3" />
            <path d="M65 60L80 80H60L65 60Z" fill="#FF7D45" stroke="black" strokeWidth="3" />
          </svg>
        </motion.div>

        <motion.div
          animate={{ y: [10, -10, 10], rotate: [0, -10, 0] }}
          transition={{ duration: 7, repeat: Infinity, ease: 'easeInOut' }}
          className="absolute top-[15%] right-[5%] z-10 w-32 md:w-48"
        >
          {/* Coin */}
          <div className="w-full aspect-square rounded-full bg-brand-yellow border-4 border-black flex items-center justify-center shadow-[8px_8px_0px_0px_rgba(0,0,0,1)]">
            <div className="text-black text-6xl font-bold">:)</div>
          </div>
        </motion.div>

        <motion.div
          animate={{ y: [0, 20, 0] }}
          transition={{ duration: 5, repeat: Infinity, ease: 'easeInOut' }}
          className="absolute bottom-[20%] left-[-2%] z-10 w-32 md:w-56"
        >
          {/* Wallet */}
          <div className="w-full aspect-[4/3] bg-brand-violet border-4 border-black rounded-3xl relative shadow-[8px_8px_0px_0px_rgba(0,0,0,1)] transform rotate-12">
            <div className="absolute right-4 top-1/2 -translate-y-1/2 w-8 h-12 bg-black/20 rounded-md border-2 border-black"></div>
          </div>
        </motion.div>

        <motion.div
          animate={{ y: [0, -15, 0], rotate: [0, 5, 0] }}
          transition={{ duration: 8, repeat: Infinity, ease: 'easeInOut' }}
          className="absolute bottom-[15%] right-[10%] z-10 flex gap-4"
        >
          {/* Cards */}
          <div className="w-24 h-32 bg-brand-blue border-4 border-black rounded-xl shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] transform -rotate-12"></div>
          <div className="w-24 h-32 bg-brand-violet border-4 border-black rounded-xl shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] transform rotate-6 -ml-12 mt-8"></div>
        </motion.div>

        {/* Central Text */}
        <div className="relative z-20 text-center">
          <h1 className="text-[12vw] leading-[0.85] font-bold uppercase tracking-tighter text-white drop-shadow-lg">
            <span className="block">Finance.</span>
            <span className="block">Leveled Up.</span>
          </h1>
        </div>

        {/* Bottom Actions */}
        <div className="absolute bottom-24 left-0 w-full flex flex-col items-center gap-4 z-30 px-4">
          <div className="flex flex-col sm:flex-row gap-4 w-full max-w-md">
            <button className="flex-1 flex items-center justify-center gap-2 bg-[#4285F4] hover:bg-[#3367D6] text-white font-sans font-bold py-4 px-6 rounded-full transition-all hover:scale-105">
              <span className="font-bold text-lg">G</span>
              <span>Google</span>
            </button>
            <button className="flex-1 flex items-center justify-center gap-2 bg-[#333333] hover:bg-black text-white font-sans font-bold py-4 px-6 rounded-full transition-all hover:scale-105">
              <Apple className="w-5 h-5 fill-current" />
              <span>Apple</span>
            </button>
          </div>

          <button className="w-full max-w-md bg-white/20 hover:bg-white/30 backdrop-blur-md border border-white/30 text-white font-sans font-medium py-4 px-6 rounded-full transition-all">
            More options
          </button>
        </div>

        {/* Footer Legal */}
        <div className="absolute bottom-8 left-0 w-full text-center text-white/40 text-xs font-sans">
          By continuing, you agree to our{' '}
          <a href="#" className="underline hover:text-white">
            Terms of Service
          </a>{' '}
          and{' '}
          <a href="#" className="underline hover:text-white">
            Privacy Policy
          </a>
        </div>
      </div>
    </motion.div>
  );
};

export default Login;
