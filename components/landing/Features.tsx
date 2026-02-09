import React from 'react';
import AnimatedSection from './AnimatedSection';
import { ArrowUpRight, Bot, LineChart, BrainCircuit } from 'lucide-react';

const Features: React.FC = () => {
  return (
    <section className="py-24 lg:py-32 bg-brand-white">
      <div className="container mx-auto px-4">
        <AnimatedSection className="mb-16 md:mb-24">
          <h2 className="max-w-4xl font-display text-6xl font-black leading-[0.85] tracking-tighter uppercase md:text-8xl lg:text-9xl text-black">
            YOUR POCKET <br />
            <span className="text-brand-orange text-outline" style={{ WebkitTextStroke: "2px black" }}>AI ACCOUNTANT.</span>
          </h2>
        </AnimatedSection>

        <div className="grid gap-8 lg:grid-cols-12">
          {/* Large Card */}
          <div className="lg:col-span-7">
            <AnimatedSection>
              <div className="group relative flex min-h-[500px] flex-col justify-between overflow-hidden rounded-[2.5rem] border-2 border-black bg-brand-light p-8 shadow-hard transition-all hover:shadow-hard-lg lg:p-12 hover:-translate-y-2">
                <div className="relative z-10 max-w-lg">
                  <h3 className="mb-6 font-display text-5xl font-bold uppercase leading-none md:text-7xl tracking-tight text-black">AI Prediction Engine</h3>
                  <p className="mb-8 text-xl font-medium leading-relaxed text-black md:text-2xl font-sans">
                    Scale uses advanced prediction vectors to analyze your transactional data. See exactly where your finances are heading before you even spend a dime.
                  </p>
                  <button className="flex items-center gap-2 rounded-full border-2 border-black bg-brand-yellow px-8 py-4 text-xl font-bold uppercase font-display tracking-wider transition-transform group-hover:scale-105 text-black hover:bg-brand-orange">
                    Start Analyzing <ArrowUpRight />
                  </button>
                </div>

                {/* Abstract Visual */}
                <div className="absolute bottom-0 right-0 h-64 w-64 translate-x-12 translate-y-12 rounded-full border-4 border-black bg-brand-blue flex items-center justify-center">
                  <BrainCircuit className="text-white w-32 h-32" />
                </div>
                <div className="absolute bottom-12 right-12 h-32 w-32 rounded-full border-4 border-black bg-brand-orange" />
              </div>
            </AnimatedSection>
          </div>

          {/* Right Column Stack */}
          <div className="flex flex-col gap-8 lg:col-span-5">
            <AnimatedSection delay={0.2}>
              <div className="group relative flex min-h-[300px] flex-col justify-center overflow-hidden rounded-[2.5rem] border-2 border-black bg-brand-violet p-8 shadow-hard transition-all hover:shadow-hard-lg hover:-translate-y-2">
                <h3 className="mb-4 font-display text-4xl font-bold uppercase md:text-5xl tracking-tight text-black">Ask the LLM</h3>
                <p className="text-xl font-medium text-black font-sans">Have a complex tax question or budgeting issue? Our trained LLM solves user financial problems instantly.</p>
                <div className="absolute -right-4 -top-4 h-24 w-24 rounded-full border-4 border-black bg-brand-green flex items-center justify-center">
                  <Bot className="w-12 h-12 text-black" />
                </div>
              </div>
            </AnimatedSection>

            <AnimatedSection delay={0.4}>
              <div className="group relative flex min-h-[300px] flex-col justify-center overflow-hidden rounded-[2.5rem] border-2 border-black bg-brand-green p-8 shadow-hard transition-all hover:shadow-hard-lg hover:-translate-y-2">
                <h3 className="mb-4 font-display text-4xl font-bold uppercase md:text-5xl tracking-tight text-black">Data Analytics</h3>
                <p className="text-xl font-medium text-black font-sans">Replace your accountant with AI agents. Visualise your cash flow with complex math made simple.</p>
                <div className="absolute -bottom-4 -left-4 h-24 w-24 rounded-full border-4 border-black bg-brand-yellow flex items-center justify-center">
                  <LineChart className="w-12 h-12 text-black" />
                </div>
              </div>
            </AnimatedSection>
          </div>
        </div>
      </div>
    </section>
  );
};

export default Features;