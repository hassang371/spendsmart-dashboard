import React from 'react';
import AnimatedSection from './AnimatedSection';
import dynamic from 'next/dynamic';

const Lottie = dynamic(() => import('lottie-react'), { ssr: false });
import smileyAnimation from '@/public/slush/icon-smiley.json';

const testimonials = [
  {
    text: "Scale replaced my accountant. The AI predictions are freakishly accurate.",
    author: "Freelancer",
    color: "bg-brand-light",
    rotation: "rotate-2"
  },
  {
    text: "I used to drown in spreadsheets. Now I just ask Scale's LLM and get instant answers.",
    author: "Small Business Owner",
    color: "bg-brand-blue",
    rotation: "-rotate-1"
  },
  {
    text: "The spending visualization is beautiful. Finally, I understand my cash flow.",
    author: "Esther Johnson",
    color: "bg-white",
    rotation: "rotate-3"
  },
  {
    text: "As a data nerd, the analytics dashboard is pure gold. Complex math made simple.",
    author: "@zachpumpit",
    color: "bg-brand-violet",
    rotation: "-rotate-2"
  },
  {
    text: "The budget forecasting saved me from going into the red last month. Lifesaver.",
    author: "Beta Tester",
    color: "bg-brand-green",
    rotation: "rotate-1"
  }
];

const Testimonials: React.FC = () => {
  return (
    <section className="overflow-hidden py-32 bg-brand-light">
      <div className="container mx-auto px-4">
        <div className="mb-20 flex flex-col items-center text-center">
          <AnimatedSection>
            <div className="relative inline-block mb-8">
               <div className="flex flex-col items-center">
                   <h2 className="font-display text-8xl font-bold uppercase tracking-tighter md:text-[10rem] leading-[0.8] z-10 relative text-black transform -rotate-2 italic">
                       DON&apos;T <br/>
                       BELIEVE US?
                   </h2>
                   <div className="absolute top-0 -right-20 w-32 h-32 md:w-48 md:h-48 z-20 transform rotate-12">
                       <Lottie animationData={smileyAnimation} loop={true} />
                   </div>
               </div>
            </div>
            <p className="font-display text-4xl font-bold uppercase md:text-5xl text-black">See for yourself.</p>
          </AnimatedSection>
        </div>

        <div className="relative -mx-4">
          {/* Horizontal scroll container with hidden scrollbar */}
          <div className="flex gap-8 overflow-x-auto pb-20 pt-10 px-8 snap-x no-scrollbar">
            <div className="flex-none w-[350px] md:w-[500px] flex flex-col items-center justify-center rounded-[2.5rem] border-4 border-black bg-brand-yellow p-12 shadow-hard-lg text-center snap-center transform transition-transform hover:scale-105 hover:-rotate-2">
               <h3 className="font-display text-6xl font-bold uppercase italic leading-none">Trusted By<br/>Millions</h3>
               <div className="mt-8 text-8xl animate-pulse">🤝</div>
            </div>

            {testimonials.map((t, i) => (
              <div key={i} className={`flex-none w-[350px] md:w-[500px] flex flex-col justify-between rounded-[2.5rem] border-4 border-black ${t.color} p-12 shadow-hard-lg snap-center transition-all duration-300 hover:-translate-y-4 hover:shadow-hard-xl ${t.rotation}`}>
                <p className="font-display text-4xl font-bold leading-[0.9] uppercase text-black">&quot;{t.text}&quot;</p>
                <div className="mt-12 flex items-center gap-4">
                  <div className="h-16 w-16 rounded-full border-2 border-black bg-gray-900 text-white flex items-center justify-center font-display text-2xl">
                    {t.author[0]}
                  </div>
                  <p className="font-sans font-bold uppercase tracking-wide text-xl text-black">{t.author}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
};

export default Testimonials;