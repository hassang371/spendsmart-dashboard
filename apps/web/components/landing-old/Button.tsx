import React from 'react';
import { ArrowRight } from 'lucide-react';

interface ButtonProps {
  children: React.ReactNode;
  variant?:
    | 'yellow'
    | 'blue'
    | 'green'
    | 'violet'
    | 'orange'
    | 'dark'
    | 'white'
    | 'glass'
    | 'brand'
    | 'outline';
  onClick?: () => void;
  className?: string; // Allow additional classes to override
  icon?: boolean;
  href?: LinkProps['href']; // Use Next.js LinkProps if possible, but string is fine for now
  glow?: boolean;
  'aria-label'?: string;
}

import Link, { LinkProps } from 'next/link';

const Button: React.FC<ButtonProps> = ({
  children,
  variant = 'yellow',
  onClick,
  className = '',
  icon = false,
  href,
  glow = false,
  'aria-label': ariaLabel,
}) => {
  const colors = {
    yellow: 'bg-brand-yellow text-black',
    blue: 'bg-brand-blue text-white',
    green: 'bg-brand-green text-black',
    violet: 'bg-brand-violet text-black',
    orange: 'bg-brand-orange text-black',
    dark: 'bg-brand-dark text-white',
    white: 'bg-white text-black',
    glass: 'bg-white/20 backdrop-blur-md border-white/50 text-white',
    brand: 'bg-black text-white hover:bg-brand-blue border-black',
    outline: 'bg-white text-black border-black hover:bg-brand-yellow',
  };

  const glowStyles = glow ? 'hover:shadow-glow hover:border-brand-blue/50' : '';
  const baseStyles = `inline-flex items-center justify-center rounded-full border-2 font-display font-bold uppercase tracking-wider active:scale-95 text-lg ${glowStyles}`;

  const colorStyle = colors[variant] || colors['yellow'];
  const borderStyle = variant === 'glass' ? 'border-white/30' : 'border-black';

  // 3D Flip Animation Styles
  const flipContainer = 'relative overflow-hidden group';
  const frontFace =
    'block transition-all duration-500 ease-[cubic-bezier(0.65,0.05,0,1)] group-hover:-translate-y-[150%] group-hover:rotate-x-90';
  const backFace =
    'absolute inset-0 flex items-center justify-center transition-all duration-500 ease-[cubic-bezier(0.65,0.05,0,1)] translate-y-[150%] rotate-x-[-90deg] group-hover:translate-y-0 group-hover:rotate-x-0';

  // Dynamic Back Face Color
  let backFaceColor = 'bg-brand-dark text-white'; // default
  if (variant === 'brand') backFaceColor = 'bg-brand-blue text-white';
  if (variant === 'outline') backFaceColor = 'bg-brand-yellow text-black';
  if (variant === 'white') backFaceColor = 'bg-brand-yellow text-black'; // White flips to Yellow
  if (variant === 'dark') backFaceColor = 'bg-brand-blue text-white'; // Dark flips to Blue

  const content = (
    <>
      <span className={`${frontFace} flex items-center gap-2 px-8 py-4`}>
        {children}
        {icon && <ArrowRight className="h-5 w-5" />}
      </span>
      <span className={`${backFace} px-8 py-4 w-full h-full ${backFaceColor}`}>
        {children}
        {icon && <ArrowRight className="h-5 w-5" />}
      </span>
    </>
  );

  const buttonClasses = `${flipContainer} ${baseStyles} ${colorStyle} ${borderStyle} ${className} !p-0`;

  if (href) {
    return (
      <Link href={href} className={buttonClasses} onClick={onClick} aria-label={ariaLabel}>
        {content}
      </Link>
    );
  }

  return (
    <button onClick={onClick} className={buttonClasses} aria-label={ariaLabel}>
      {content}
    </button>
  );
};

export default Button;
