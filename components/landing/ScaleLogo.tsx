import React from 'react';

interface ScaleLogoProps {
  className?: string;
  dark?: boolean;
}

const ScaleLogo: React.FC<ScaleLogoProps> = ({ className = "h-12 w-12", dark = false }) => {
  const fg = dark ? "white" : "black";
  const bg = dark ? "#050505" : "white";
  const border = dark ? "white" : "black";

  return (
    <div className={`flex items-center justify-center rounded-xl border-2 border-${border} bg-[${bg}] shadow-hard-sm overflow-hidden ${className}`}>
      <svg width="100%" height="100%" viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg" className="p-2">
        {/* Ruler Marks increasing in height */}
        <line x1="8" y1="32" x2="8" y2="24" stroke={fg} strokeWidth="3" strokeLinecap="round"/>
        <line x1="16" y1="32" x2="16" y2="18" stroke={fg} strokeWidth="3" strokeLinecap="round"/>
        <line x1="24" y1="32" x2="24" y2="12" stroke={fg} strokeWidth="3" strokeLinecap="round"/>
        <line x1="32" y1="32" x2="32" y2="6" stroke={fg} strokeWidth="3" strokeLinecap="round"/>
        
        {/* Growth Arrow Overlay */}
        <path d="M8 20L32 4" stroke={fg} strokeWidth="2" strokeLinecap="round" className="opacity-0 hover:opacity-100 transition-opacity duration-300" />
      </svg>
    </div>
  );
};

export default ScaleLogo;