import React from 'react';
import { ArrowRight } from 'lucide-react';

interface ButtonProps {
  children: React.ReactNode;
  variant?: 'yellow' | 'blue' | 'green' | 'violet' | 'orange' | 'dark' | 'white' | 'glass';
  onClick?: () => void;
  className?: string;
  icon?: boolean;
  href?: string;
  glow?: boolean;
}

const Button: React.FC<ButtonProps> = ({ 
  children, 
  variant = 'yellow', 
  onClick, 
  className = '', 
  icon = false,
  href,
  glow = false
}) => {
  const colors = {
    yellow: 'bg-brand-yellow',
    blue: 'bg-brand-blue',
    green: 'bg-brand-green',
    violet: 'bg-brand-violet',
    orange: 'bg-brand-orange',
    dark: 'bg-brand-dark text-white',
    white: 'bg-white',
    glass: 'bg-white/20 backdrop-blur-md border-white/50 text-white',
  };

  const glowStyles = glow ? "hover:shadow-glow hover:border-brand-blue/50" : "";
  const baseStyles = `relative group overflow-hidden rounded-full border-2 border-black px-6 py-3 font-display font-bold uppercase tracking-wider transition-all duration-300 active:scale-95 ${glowStyles}`;
  const colorStyle = colors[variant];

  // Adjust border color for glass/dark variants if needed
  const borderStyle = variant === 'glass' ? 'border-white/30' : 'border-black';

  const content = (
    <>
      <span className="relative z-10 flex items-center gap-2 transition-transform duration-300 group-hover:-translate-y-[150%]">
        {children}
        {icon && <ArrowRight className="h-4 w-4" />}
      </span>
      <span className="absolute inset-0 z-10 flex items-center justify-center gap-2 translate-y-[150%] transition-transform duration-300 group-hover:translate-y-0">
        {children}
        {icon && <ArrowRight className="h-4 w-4" />}
      </span>
      {/* Background Hover Effect */}
      <div className={`absolute inset-0 z-0 translate-y-full transition-transform duration-300 group-hover:translate-y-0 ${variant === 'dark' ? 'bg-brand-blue' : 'bg-white'}`} />
    </>
  );

  if (href) {
    return (
      <a href={href} className={`${baseStyles} ${colorStyle} ${borderStyle} ${className}`}>
        {content}
      </a>
    );
  }

  return (
    <button onClick={onClick} className={`${baseStyles} ${colorStyle} ${borderStyle} ${className}`}>
      {content}
    </button>
  );
};

export default Button;