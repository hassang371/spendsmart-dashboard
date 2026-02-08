import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence, useScroll, useMotionValueEvent } from 'framer-motion';
import Button from './Button';
import { Plus, X } from 'lucide-react';
import ScaleLogo from './ScaleLogo';

interface NavbarProps {
  onLoginClick: () => void;
}

const Navbar: React.FC<NavbarProps> = ({ onLoginClick }) => {
  const [menuOpen, setMenuOpen] = useState(false);
  const [showLoginButton, setShowLoginButton] = useState(true);
  const { scrollY } = useScroll();

  useEffect(() => {
    if (menuOpen) {
      document.body.classList.add('scroll-locked');
    } else {
      document.body.classList.remove('scroll-locked');
    }
    return () => document.body.classList.remove('scroll-locked');
  }, [menuOpen]);

  useMotionValueEvent(scrollY, "change", (latest) => {
    // Hide login button after scrolling past roughly the Hero section (e.g., 700px)
    if (latest > 700) {
      setShowLoginButton(false);
    } else {
      setShowLoginButton(true);
    }
  });

  return (
    <>
      <nav className="fixed top-0 left-0 right-0 z-50 flex items-center justify-between p-6 md:p-8 pointer-events-none">
        {/* Logo Icon Only - Top Left */}
        <a href="#" className="pointer-events-auto flex items-center justify-center transition-transform hover:scale-110 active:scale-95">
          <ScaleLogo className="h-14 w-14" />
        </a>

        {/* Right Side: Login + Menu Trigger */}
        <div className="pointer-events-auto flex items-center gap-4">
          <AnimatePresence>
            {showLoginButton && (
              <motion.div
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.8 }}
                transition={{ duration: 0.2 }}
              >
                <Button 
                  variant="dark" 
                  onClick={onLoginClick} 
                  className="hidden md:flex !py-3 !px-8 text-lg hover:bg-brand-coral"
                >
                  Login
                </Button>
              </motion.div>
            )}
          </AnimatePresence>
          
          <button 
            onClick={() => setMenuOpen(true)}
            className="group flex h-14 w-14 items-center justify-center rounded-full border-2 border-black bg-white shadow-hard-sm transition-all hover:bg-brand-green hover:shadow-hard active:scale-95 active:shadow-none"
          >
            <Plus className="h-8 w-8 transition-transform group-hover:rotate-90" />
          </button>
        </div>
      </nav>

      {/* Full Screen Menu Overlay */}
      <AnimatePresence>
        {menuOpen && (
          <motion.div
            initial={{ opacity: 0, y: "-100%" }}
            animate={{ opacity: 1, y: "0%" }}
            exit={{ opacity: 0, y: "-100%" }}
            transition={{ type: "spring", damping: 25, stiffness: 120 }}
            className="fixed inset-0 z-[60] flex flex-col bg-brand-light"
          >
            {/* Menu Header */}
            <div className="flex items-center justify-between p-6 md:p-8">
              <ScaleLogo className="h-14 w-14" />
              
              <button 
                onClick={() => setMenuOpen(false)}
                className="flex h-14 w-14 items-center justify-center rounded-full border-2 border-black bg-brand-coral shadow-hard-sm transition-transform active:scale-95 hover:rotate-90"
              >
                <X className="h-8 w-8 text-black" />
              </button>
            </div>

            {/* Menu Links */}
            <div className="flex flex-1 flex-col items-center justify-center gap-4 p-6">
               {['Get Started', 'DeFi', 'Security', 'Guides', 'Download'].map((item, i) => (
                 <motion.a 
                   key={item}
                   initial={{ opacity: 0, y: 40 }}
                   animate={{ opacity: 1, y: 0 }}
                   transition={{ delay: i * 0.05 + 0.2 }}
                   href={`#${item.toLowerCase().replace(' ', '-')}`}
                   className="font-display text-7xl font-bold uppercase tracking-tight text-black transition-colors hover:text-brand-blue md:text-9xl hover:italic"
                   onClick={() => setMenuOpen(false)}
                 >
                   {item}
                 </motion.a>
               ))}
               
               <motion.div 
                 initial={{ opacity: 0, y: 20 }}
                 animate={{ opacity: 1, y: 0 }}
                 transition={{ delay: 0.5 }}
                 className="mt-12 md:hidden"
               >
                 <Button variant="dark" onClick={() => { setMenuOpen(false); onLoginClick(); }} className="!text-xl !px-10 !py-4">Login</Button>
               </motion.div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
};

export default Navbar;