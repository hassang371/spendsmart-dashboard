import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';

const CustomCursor: React.FC = () => {
  const [mousePosition, setMousePosition] = useState({ x: 0, y: 0 });
  const [isPointer, setIsPointer] = useState(false);

  useEffect(() => {
    const mouseMove = (e: MouseEvent) => {
      setMousePosition({ x: e.clientX, y: e.clientY });

      const target = e.target as HTMLElement;
      setIsPointer(window.getComputedStyle(target).cursor === 'pointer');
    };

    window.addEventListener('mousemove', mouseMove);
    return () => window.removeEventListener('mousemove', mouseMove);
  }, []);

  return (
    <motion.div
      className="pointer-events-none fixed left-0 top-0 z-[9999] hidden md:block"
      animate={{
        x: mousePosition.x - 16,
        y: mousePosition.y - 16,
        scale: isPointer ? 1.5 : 1,
      }}
      transition={{ type: 'spring', stiffness: 500, damping: 28 }}
    >
      <div
        className={`h-8 w-8 rounded-full border-2 border-black bg-brand-yellow/80 backdrop-blur-sm transition-colors duration-300 ${
          isPointer ? 'bg-brand-violet/80' : ''
        }`}
      />
    </motion.div>
  );
};

export default CustomCursor;
