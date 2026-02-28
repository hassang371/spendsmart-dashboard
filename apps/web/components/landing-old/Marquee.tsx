import React from 'react';

interface MarqueeProps {
  direction?: 'left' | 'right';
  text?: string;
}

const Marquee: React.FC<MarqueeProps> = ({
  direction = 'left',
  text = 'SCALE IS HERE. STRATEGIES. LIVE NOW. ',
}) => {
  const animationClass = direction === 'left' ? 'animate-marquee' : 'animate-marquee-reverse';

  // Repeat text to fill width
  const content = Array(10).fill(text).join(' • ');

  return (
    <div className="relative flex w-full overflow-hidden border-y-2 border-black bg-brand-yellow py-4">
      <div
        className={`whitespace-nowrap font-display text-2xl font-bold uppercase tracking-wide md:text-4xl ${animationClass}`}
      >
        {content}
      </div>
      <div
        className={`absolute top-4 whitespace-nowrap font-display text-2xl font-bold uppercase tracking-wide md:text-4xl ${animationClass}`}
        aria-hidden="true"
      >
        {content}
      </div>
    </div>
  );
};

export default Marquee;
