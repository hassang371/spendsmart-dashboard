import React from 'react';
import { motion, useScroll, useTransform } from 'framer-motion';
import { LayoutDashboard, Receipt, PieChart, Settings, Bot, MoreVertical } from 'lucide-react';

const AppPreview: React.FC = () => {
  const ref = React.useRef(null);
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ['start end', 'end start'],
  });

  const rotateX = useTransform(scrollYProgress, [0, 0.5], [30, 0]);
  const scale = useTransform(scrollYProgress, [0, 0.5], [0.9, 1]);
  const y = useTransform(scrollYProgress, [0, 0.5], [100, 0]);

  return (
    <div ref={ref} className="perspective-1000 w-full max-w-7xl mx-auto py-20">
      <motion.div
        style={{
          rotateX,
          scale,
          y,
          transformStyle: 'preserve-3d',
        }}
        className="relative aspect-[16/10] w-full rounded-[3rem] border-8 border-gray-900 bg-[#0A0C10] shadow-hard-xl overflow-hidden flex"
      >
        {/* Sidebar */}
        <div className="hidden md:flex w-64 flex-col border-r border-gray-800 bg-[#0F1116] p-6">
          <div className="flex items-center gap-3 mb-10 text-white font-display text-2xl tracking-tight">
            <div className="h-8 w-8 rounded-full bg-brand-blue flex items-center justify-center">
              S
            </div>
            SCALE
          </div>

          <nav className="flex flex-col gap-2">
            <div className="flex items-center gap-3 px-4 py-3 bg-brand-blue text-white rounded-xl font-medium shadow-lg shadow-brand-blue/20">
              <LayoutDashboard size={20} />
              Overview
            </div>
            <div className="flex items-center gap-3 px-4 py-3 text-gray-400 hover:text-white hover:bg-white/5 rounded-xl font-medium transition-colors">
              <Receipt size={20} />
              Transactions
            </div>
            <div className="flex items-center gap-3 px-4 py-3 text-gray-400 hover:text-white hover:bg-white/5 rounded-xl font-medium transition-colors">
              <PieChart size={20} />
              Analytics
            </div>
            <div className="flex items-center gap-3 px-4 py-3 text-gray-400 hover:text-white hover:bg-white/5 rounded-xl font-medium transition-colors">
              <Bot size={20} />
              AI Agent
            </div>
          </nav>

          <div className="mt-auto">
            <div className="flex items-center gap-3 px-4 py-3 text-gray-400 hover:text-white hover:bg-white/5 rounded-xl font-medium transition-colors">
              <Settings size={20} />
              Settings
            </div>
            <div className="mt-4 flex items-center gap-3 p-3 rounded-xl bg-gray-800/50 border border-gray-700">
              <div className="h-10 w-10 rounded-full bg-gradient-to-tr from-brand-violet to-brand-blue" />
              <div className="flex-1 overflow-hidden">
                <div className="text-sm font-bold text-white truncate">Hassan</div>
                <div className="text-xs text-gray-400 truncate">Pro Member</div>
              </div>
              <MoreVertical size={16} className="text-gray-400" />
            </div>
          </div>
        </div>

        {/* Main Content */}
        <div className="flex-1 p-4 md:p-8 overflow-hidden flex flex-col bg-[#0A0C10]">
          {/* Header */}
          <div className="flex justify-between items-center mb-8">
            <div>
              <h2 className="text-3xl font-display font-bold text-white">Hi, Hassan</h2>
              <p className="text-gray-400">Your financial prediction snapshot.</p>
            </div>
            <div className="hidden sm:flex bg-gray-800/50 rounded-full p-1 border border-gray-700">
              <button className="px-6 py-2 bg-brand-blue text-white rounded-full text-sm font-bold shadow-lg">
                Weekly
              </button>
              <button className="px-6 py-2 text-gray-400 hover:text-white rounded-full text-sm font-medium transition-colors">
                Monthly
              </button>
            </div>
          </div>

          {/* Dashboard Grid */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 flex-1">
            {/* Spend Card (Red/Orange) */}
            <div className="bg-gradient-to-br from-brand-coral to-red-600 rounded-3xl p-6 text-white relative overflow-hidden shadow-lg shadow-brand-coral/20 group">
              <div className="absolute top-0 right-0 p-4 opacity-50">
                <svg
                  width="60"
                  height="60"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  className="transform group-hover:scale-110 transition-transform duration-500"
                >
                  <path d="M7 17L17 7M17 7H7M17 7V17" />
                </svg>
              </div>
              <div className="flex flex-col h-full justify-between relative z-10">
                <div>
                  <div className="text-red-100 font-medium mb-1 flex items-center gap-2">
                    <span className="bg-white/20 p-1 rounded">📉</span> LAST 7 DAYS
                  </div>
                  <div className="text-5xl font-display font-bold tracking-tight">$3,846</div>
                </div>
                <div>
                  <div className="h-px w-full bg-white/20 mb-4" />
                  <div className="flex justify-between items-end">
                    <div>
                      <div className="text-red-100 text-sm mb-1">DAILY AVERAGE</div>
                      <div className="text-2xl font-bold">$769</div>
                    </div>
                    <div className="px-3 py-1 bg-white/20 backdrop-blur-md rounded-lg text-xs font-bold">
                      High Burn Rate
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Categories (Dark Blue) */}
            <div className="bg-[#13161C] border border-gray-800 rounded-3xl p-6 text-white shadow-lg flex flex-col relative overflow-hidden">
              <div className="flex items-center gap-2 mb-6">
                <div className="text-brand-green">▣</div>
                <h3 className="font-bold">Top Categories</h3>
              </div>

              <div className="flex items-center justify-between flex-1">
                <div className="space-y-4">
                  <div className="flex items-center gap-2">
                    <div className="w-3 h-3 rounded-full bg-brand-blue" />
                    <span className="text-sm text-gray-300">Subscriptions</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-3 h-3 rounded-full bg-brand-violet" />
                    <span className="text-sm text-gray-300">Entertainment</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-3 h-3 rounded-full bg-brand-coral" />
                    <span className="text-sm text-gray-300">Dining</span>
                  </div>
                </div>

                <div className="relative w-32 h-32 flex items-center justify-center">
                  <svg viewBox="0 0 100 100" className="w-full h-full transform -rotate-90">
                    <circle
                      cx="50"
                      cy="50"
                      r="40"
                      fill="transparent"
                      stroke="#1F2937"
                      strokeWidth="12"
                    />
                    <circle
                      cx="50"
                      cy="50"
                      r="40"
                      fill="transparent"
                      stroke="#4892FF"
                      strokeWidth="12"
                      strokeDasharray="150 251"
                      strokeLinecap="round"
                    />
                    <circle
                      cx="50"
                      cy="50"
                      r="40"
                      fill="transparent"
                      stroke="#9F8BFF"
                      strokeWidth="12"
                      strokeDasharray="70 251"
                      strokeDashoffset="-150"
                      strokeLinecap="round"
                    />
                    <circle
                      cx="50"
                      cy="50"
                      r="40"
                      fill="transparent"
                      stroke="#FF4D4D"
                      strokeWidth="12"
                      strokeDasharray="30 251"
                      strokeDashoffset="-220"
                      strokeLinecap="round"
                    />
                  </svg>
                </div>
              </div>
            </div>

            {/* Splurges (Dark) */}
            <div className="bg-[#13161C] border border-gray-800 rounded-3xl p-6 text-white shadow-lg flex flex-col">
              <div className="flex items-center gap-2 mb-6">
                <div className="text-brand-yellow">⚡</div>
                <h3 className="font-bold">Big Splurges</h3>
              </div>

              <div className="space-y-4">
                {[
                  { name: 'Apple One Premier', date: '2/3/2026', price: '$39.95' },
                  { name: 'Uber Eats', date: '2/3/2026', price: '$48.50' },
                  { name: 'Scale Pro', date: '2/7/2026', price: '$199.00' },
                ].map((item, i) => (
                  <div
                    key={i}
                    className="flex items-center justify-between p-3 rounded-xl bg-gray-800/30 border border-gray-700/50 hover:bg-gray-800/50 transition-colors"
                  >
                    <div className="flex items-center gap-3">
                      <div className="h-8 w-8 rounded-lg bg-gray-700 flex items-center justify-center text-xs font-bold text-gray-400">
                        {i + 1}
                      </div>
                      <div>
                        <div className="text-sm font-bold">{item.name}</div>
                        <div className="text-xs text-gray-500">{item.date}</div>
                      </div>
                    </div>
                    <div className="text-sm font-bold text-brand-coral">{item.price}</div>
                  </div>
                ))}
              </div>
            </div>

            {/* Trends (Bottom) */}
            <div className="lg:col-span-3 bg-[#13161C] border border-gray-800 rounded-3xl p-6 text-white shadow-lg relative overflow-hidden">
              <div className="flex justify-between items-center mb-8">
                <div>
                  <h3 className="font-bold text-xl flex items-center gap-2">
                    <span className="text-brand-green">~</span> Spending Trends & AI Prediction
                  </h3>
                  <p className="text-sm text-gray-400">
                    Projected spend based on recurring vectors.
                  </p>
                </div>
                <div className="px-3 py-1 rounded-full border border-brand-blue/30 bg-brand-blue/10 text-brand-blue text-xs font-bold animate-pulse">
                  ● AI LIVE
                </div>
              </div>

              <div className="flex items-end justify-between gap-4 h-48 w-full px-2">
                {[40, 65, 35, 80, 50, 90, 60].map((h, i) => (
                  <div key={i} className="flex-1 flex flex-col justify-end gap-2 group">
                    <motion.div
                      initial={{ height: 0 }}
                      whileInView={{ height: `${h}%` }}
                      transition={{ duration: 1, delay: i * 0.1, ease: 'backOut' }}
                      className={`w-full rounded-t-lg opacity-80 group-hover:opacity-100 transition-opacity ${
                        i === 5
                          ? 'bg-gradient-to-t from-brand-green to-emerald-400'
                          : 'bg-gradient-to-t from-brand-blue/50 to-brand-blue'
                      }`}
                    />
                    <div className="text-center text-xs text-gray-500 font-bold">
                      {['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][i]}
                    </div>
                  </div>
                ))}
              </div>

              {/* Prediction Line */}
              <svg
                className="absolute bottom-10 left-0 w-full h-48 pointer-events-none opacity-50"
                preserveAspectRatio="none"
              >
                <path
                  d="M0 100 Q 300 150, 600 50 T 1200 80"
                  fill="none"
                  stroke="#CCFF00"
                  strokeWidth="2"
                  strokeDasharray="5 5"
                />
              </svg>
            </div>
          </div>
        </div>

        {/* Reflection Overlay */}
        <div className="pointer-events-none absolute inset-0 bg-gradient-to-tr from-white/5 to-transparent z-30" />
      </motion.div>
    </div>
  );
};

export default AppPreview;
