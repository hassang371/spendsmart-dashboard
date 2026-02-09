import React from 'react';
import { ArrowRight } from 'lucide-react';

interface ButtonProps {
  children: React.ReactNode;
  variant?: 'yellow' | 'blue' | 'green' | 'violet' | 'orange' | 'dark' | 'white' | 'glass' | 'brand' | 'outline';
  onClick?: () => void;
  className?: string; // Allow additional classes to override
  icon?: boolean;
  href?: LinkProps['href']; // Use Next.js LinkProps if possible, but string is fine for now
  glow?: boolean;
  "aria-label"?: string;
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
  "aria-label": ariaLabel,
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

  const glowStyles = glow ? "hover:shadow-glow hover:border-brand-blue/50" : "";
  const baseStyles = `relative group inline-flex items-center justify-center overflow-hidden rounded-full border-2 px-8 py-4 font-display font-bold uppercase tracking-wider transition-all duration-200 active:scale-95 text-lg ${glowStyles}`;

  const colorStyle = colors[variant] || colors['yellow'];
  const borderStyle = variant === 'glass' ? 'border-white/30' : 'border-black';

  const content = (
    <>
      <span className="relative z-10 flex items-center gap-2 transition-all duration-300 ease-out group-hover:-translate-y-[150%] group-hover:opacity-0">
        {children}
        {icon && <ArrowRight className="h-5 w-5" />}
      </span>
      <span className="absolute inset-0 z-10 flex items-center justify-center gap-2 translate-y-[150%] transition-all duration-300 ease-out group-hover:translate-y-0">
        {children}
        {icon && <ArrowRight className="h-5 w-5" />}
      </span>
    </>
  );

  if (href) {
    return (
      <Link href={href} className={`${baseStyles} ${colorStyle} ${borderStyle} ${className}`} onClick={onClick} aria-label={ariaLabel}>
        {content}
      </Link>
    );
  }

  return (
    <button onClick={onClick} className={`${baseStyles} ${colorStyle} ${borderStyle} ${className}`} aria-label={ariaLabel}>
      {content}
    </button>
  );
};

export default Button;