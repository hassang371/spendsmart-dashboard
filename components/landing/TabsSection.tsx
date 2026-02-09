import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import AnimatedSection from './AnimatedSection';
import Button from './Button';

const tabs = [
  {
    id: 'mobile',
    label: 'Mobile App',
    color: 'bg-brand-violet',
    title: 'Mobile App',
    description: 'Track your spending on the fly. Snap receipts, categorize transactions, and get real-time AI alerts on your budget limits.',
    buttonText: 'Get Scale Mobile',
    illustration: 'phones'
  },
  {
    id: 'web',
    label: 'Web Dashboard',
    color: 'bg-brand-yellow',
    title: 'Web Dashboard',
    description: 'A powerful command center for your finances. Deep dive into analytics, export reports, and manage your prediction settings.',
    buttonText: 'Launch Dashboard',
    illustration: 'browser'
  },
  {
    id: 'ai',
    label: 'AI Accountant',
    color: 'bg-brand-green',
    title: 'AI Agent',
    description: 'Your personal accountant, available 24/7. Ask questions, get tax advice, and let the AI model optimize your cash flow automatically.',
    buttonText: 'Chat with AI',
    illustration: 'brain'
  }
];

const PhoneIllustration = () => (
  <div className="relative h-full w-full flex items-center justify-center p-8">
    <motion.div 
        animate={{ y: [-10, 10, -10] }} 
        transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
        className="absolute left-1/4 z-10 w-48 h-80 rounded-[2.5rem] border-4 border-black bg-black p-2 shadow-hard-lg -rotate-12"
    >
        <div className="h-full w-full rounded-[2rem] bg-gray-900 overflow-hidden relative">
            <div className="absolute top-4 left-1/2 -translate-x-1/2 w-20 h-6 bg-black rounded-b-xl z-20"/>
            <div className="p-4 pt-12 grid gap-2">
                <div className="h-8 bg-brand-blue rounded-lg"/>
                <div className="h-24 bg-brand-yellow rounded-lg"/>
                <div className="grid grid-cols-2 gap-2">
                    <div className="h-24 bg-brand-green rounded-lg"/>
                    <div className="h-24 bg-brand-coral rounded-lg"/>
                </div>
            </div>
        </div>
    </motion.div>
    <motion.div 
        animate={{ y: [10, -10, 10] }} 
        transition={{ duration: 5, repeat: Infinity, ease: "easeInOut", delay: 0.5 }}
        className="absolute right-1/4 z-0 w-48 h-80 rounded-[2.5rem] border-4 border-black bg-black p-2 shadow-hard-lg rotate-6"
    >
        <div className="h-full w-full rounded-[2rem] bg-gray-800 overflow-hidden relative">
             <div className="absolute top-4 left-1/2 -translate-x-1/2 w-20 h-6 bg-black rounded-b-xl z-20"/>
             <div className="p-4 pt-12 flex flex-col gap-3">
                <div className="h-10 w-10 bg-brand-violet rounded-full self-center mb-2"/>
                <div className="h-4 w-3/4 bg-gray-600 rounded-full self-center"/>
                <div className="h-4 w-1/2 bg-gray-600 rounded-full self-center"/>
                <div className="mt-4 h-32 bg-gray-700 rounded-xl"/>
             </div>
        </div>
    </motion.div>
  </div>
);

const BrowserIllustration = () => (
    <div className="relative h-full w-full flex items-center justify-center p-12">
        <motion.div 
            initial={{ scale: 0.9 }}
            animate={{ scale: 1 }}
            transition={{ duration: 2, repeat: Infinity, repeatType: "reverse", ease: "easeInOut" }}
            className="w-full h-full bg-white border-4 border-black rounded-xl shadow-hard overflow-hidden flex flex-col"
        >
            <div className="h-10 bg-brand-light border-b-4 border-black flex items-center px-4 gap-2">
                <div className="w-4 h-4 rounded-full bg-brand-coral border-2 border-black"/>
                <div className="w-4 h-4 rounded-full bg-brand-yellow border-2 border-black"/>
                <div className="w-4 h-4 rounded-full bg-brand-green border-2 border-black"/>
                <div className="flex-1 ml-4 h-6 bg-white border-2 border-black rounded-full"/>
            </div>
            <div className="flex-1 p-6 flex gap-6">
                <div className="w-1/4 h-full bg-gray-100 border-2 border-black rounded-lg"></div>
                <div className="w-3/4 h-full flex flex-col gap-4">
                    <div className="h-32 bg-brand-blue border-2 border-black rounded-lg w-full"></div>
                    <div className="flex gap-4 h-full">
                        <div className="flex-1 bg-brand-violet border-2 border-black rounded-lg"></div>
                        <div className="flex-1 bg-brand-orange border-2 border-black rounded-lg"></div>
                    </div>
                </div>
            </div>
        </motion.div>
    </div>
);

const BrainIllustration = () => (
    <div className="relative h-full w-full flex items-center justify-center">
        <div className="relative w-64 h-64 flex items-center justify-center">
            <motion.div 
                animate={{ scale: [1, 1.1, 1], rotate: [0, 5, -5, 0] }}
                transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
                className="w-40 h-40 bg-brand-green border-4 border-black rounded-full shadow-hard-lg flex items-center justify-center z-10"
            >
                <span className="text-7xl">🧠</span>
            </motion.div>
            
            {/* Orbiting nodes */}
            <motion.div 
                animate={{ rotate: 360 }}
                transition={{ duration: 8, repeat: Infinity, ease: "linear" }}
                className="absolute w-full h-full"
            >
                <div className="absolute top-0 left-1/2 -translate-x-1/2 w-12 h-12 bg-brand-blue border-4 border-black rounded-full shadow-hard" />
            </motion.div>
            <motion.div 
                animate={{ rotate: -360 }}
                transition={{ duration: 12, repeat: Infinity, ease: "linear" }}
                className="absolute w-52 h-52"
            >
                <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-10 h-10 bg-brand-coral border-4 border-black rounded-full shadow-hard" />
            </motion.div>
        </div>
    </div>
);

const TabsSection: React.FC = () => {
  const [activeTab, setActiveTab] = useState(tabs[0]);

  return (
    <section className="bg-white py-24">
      <div className="container mx-auto px-4">
        <AnimatedSection>
          <div className="mb-16 flex flex-col items-start justify-between gap-8 md:flex-row md:items-center">
            <h2 className="font-display text-6xl font-bold uppercase tracking-tighter md:text-8xl leading-none text-black">
                SCALE IS ALWAYS <br />
                <span className="text-outline text-brand-blue" style={{ WebkitTextStroke: "2px black" }}>WITHIN REACH</span>
            </h2>
            
            <div className="flex flex-wrap gap-2 rounded-full border-2 border-black bg-brand-light p-2">
              {tabs.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab)}
                  className={`rounded-full px-8 py-3 font-display text-xl font-bold uppercase transition-all ${
                    activeTab.id === tab.id 
                      ? 'bg-black text-white shadow-md' 
                      : 'hover:bg-gray-200'
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          </div>
        </AnimatedSection>

        <div className="overflow-hidden rounded-[3rem] border-4 border-black shadow-hard-lg">
          <AnimatePresence mode="wait">
            <motion.div
              key={activeTab.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              transition={{ duration: 0.4 }}
              className={`flex flex-col gap-12 p-8 md:flex-row md:items-center md:p-16 ${activeTab.color}`}
            >
              <div className="flex-1 order-2 md:order-1">
                <div className="mb-8 flex h-[500px] w-full items-center justify-center rounded-[2.5rem] border-4 border-black bg-white/20 backdrop-blur-sm shadow-hard overflow-hidden relative">
                   {activeTab.illustration === 'phones' && <PhoneIllustration />}
                   {activeTab.illustration === 'browser' && <BrowserIllustration />}
                   {activeTab.illustration === 'brain' && <BrainIllustration />}
                </div>
              </div>
              <div className="flex-1 space-y-8 order-1 md:order-2">
                <h3 className="font-display text-8xl font-bold uppercase italic tracking-tight md:text-[8rem] leading-[0.8] text-black">{activeTab.title}</h3>
                <p className="font-sans text-2xl font-bold leading-relaxed max-w-lg text-black">{activeTab.description}</p>
                <Button variant="dark" icon className="text-xl px-8 py-4">{activeTab.buttonText}</Button>
              </div>
            </motion.div>
          </AnimatePresence>
        </div>
      </div>
    </section>
  );
};

export default TabsSection;