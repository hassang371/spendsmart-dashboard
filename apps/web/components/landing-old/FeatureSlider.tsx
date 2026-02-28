import React from 'react';
import dynamic from 'next/dynamic';

const Lottie = dynamic(() => import('lottie-react'), { ssr: false });
import devicesAnimation from '@/public/slush/icon-devices.json';
import rocketAnimation from '@/public/slush/rocket.json';
import cardsAnimation from '@/public/slush/icon-cards.json';
import coinAnimation from '@/public/slush/coin.json';

const cards = [
  {
    title: 'Automated Accounting',
    description: 'Scale uses Agentic AI to categorize every transaction automatically.',
    color: 'bg-brand-light',
    animation: devicesAnimation,
    align: 'top',
  },
  {
    title: 'Predict Future Spend',
    description: 'Stop guessing. See your financial future with 98% accuracy.',
    color: 'bg-brand-blue',
    animation: rocketAnimation,
    align: 'bottom',
  },
  {
    title: 'Agentic Infrastructure',
    description: 'Your AI accountant works 24/7. It never sleeps, so you can.',
    color: 'bg-brand-violet',
    animation: cardsAnimation,
    align: 'top',
  },
  {
    title: 'AI-Driven Insights',
    description: 'Deep dive into your data. Ask questions. Get answers. Instantly.',
    color: 'bg-brand-orange',
    animation: coinAnimation,
    align: 'bottom',
  },
];

const FeatureSlider: React.FC = () => {
  return (
    <section className="py-24 bg-white overflow-hidden">
      <div className="container mx-auto px-4 mb-12">
        <h2 className="font-display text-5xl md:text-7xl font-bold uppercase tracking-tighter leading-none text-center mb-16">
          <span className="italic text-gray-400">Why Scale?</span> <br />
          <span className="text-black">Because Math Wins.</span>
        </h2>
      </div>

      <div className="relative w-full overflow-x-auto pb-12 px-4 md:px-0 no-scrollbar snap-x snap-mandatory pt-10">
        <div className="flex gap-6 md:gap-12 w-max mx-auto px-4 md:px-24">
          {cards.map((card, index) => (
            <div
              key={index}
              className={`flex-none w-[300px] md:w-[400px] h-[400px] md:h-[500px] rounded-[2.5rem] border-4 border-black p-8 md:p-12 shadow-hard-lg snap-center flex flex-col justify-between transition-transform hover:scale-105 ${
                card.title === 'Automated Accounting' ? 'bg-[#F5F5F7]' : card.color
              }`}
            >
              {card.align === 'top' ? (
                <>
                  <div className="w-full h-40 md:h-56">
                    <Lottie
                      animationData={card.animation}
                      loop={true}
                      className="w-full h-full object-contain"
                    />
                  </div>
                  <div>
                    <h3 className="font-display text-3xl md:text-4xl font-bold uppercase leading-none mb-4 text-black">
                      {card.title}
                    </h3>
                    <p className="font-sans text-lg font-bold opacity-80 text-black">
                      {card.description}
                    </p>
                  </div>
                </>
              ) : (
                <>
                  <div>
                    <h3 className="font-display text-3xl md:text-4xl font-bold uppercase leading-none mb-4 text-black">
                      {card.title}
                    </h3>
                    <p className="font-sans text-lg font-bold opacity-80 text-black">
                      {card.description}
                    </p>
                  </div>
                  <div className="w-full h-40 md:h-56">
                    <Lottie
                      animationData={card.animation}
                      loop={true}
                      className="w-full h-full object-contain"
                    />
                  </div>
                </>
              )}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};

export default FeatureSlider;
