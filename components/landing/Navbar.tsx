import Link from 'next/link';
import React, { useState } from 'react';
import { motion, AnimatePresence, useScroll, useMotionValueEvent } from 'framer-motion';
import Button from './Button';
import { Plus, X } from 'lucide-react';

const Navbar: React.FC = () => {
  const [menuOpen, setMenuOpen] = useState(false);
  const [isScrolled, setIsScrolled] = useState(false);
  const { scrollY } = useScroll();

  useMotionValueEvent(scrollY, "change", (latest) => {
    setIsScrolled(latest > 50);
  });

  return (
    <>
      <nav className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 py-6`}>
        <div className="container mx-auto px-6 flex items-center justify-between">

          {/* Logo (Top Left) */}
          <Link href="/" className="relative z-50 group" aria-label="Go to Homepage">
            <div className="h-12 w-12 bg-white rounded-full border-2 border-black flex items-center justify-center shadow-slush transition-transform group-hover:scale-105 active:scale-95">
              <span className="font-display font-bold text-xl text-black">S</span>
            </div>
          </Link>

          {/* Right Side: Login + Menu Trigger */}
          <div className="flex items-center gap-4">
            <Link
              href="/login"
              className="flex h-12 items-center justify-center rounded-full border-2 border-black bg-white px-6 shadow-slush transition-all hover:bg-brand-yellow active:scale-95 font-display font-bold text-sm uppercase"
            >
              Login
            </Link>

            <button
              onClick={() => setMenuOpen(true)}
              className="group flex h-12 w-12 items-center justify-center rounded-full border-2 border-black bg-white shadow-slush transition-all hover:bg-brand-yellow active:scale-95"
              aria-label="Open Menu"
            >
              <Plus className="h-6 w-6 text-black transition-transform group-hover:rotate-90" />
            </button>
          </div>
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
            className="fixed inset-0 z-[60] flex flex-col bg-brand-bg"
          >
            {/* Menu Header */}
            <div className="flex items-center justify-between p-6 container mx-auto">
              <Link href="/" onClick={() => setMenuOpen(false)} aria-label="Go to Homepage">
                <div className="h-12 w-12 bg-white rounded-full border-2 border-black flex items-center justify-center shadow-slush">
                  <span className="font-display font-bold text-xl text-black">S</span>
                </div>
              </Link>

              <button
                onClick={() => setMenuOpen(false)}
                className="flex h-12 w-12 items-center justify-center rounded-full border-2 border-black bg-white shadow-slush transition-transform active:scale-95 hover:rotate-90 hover:bg-brand-coral"
                aria-label="Close Menu"
              >
                <X className="h-6 w-6 text-black" />
              </button>
            </div>

            {/* Menu Links */}
            <div className="flex flex-1 flex-col items-center justify-center gap-6 p-6">
              {['Get Started', 'Defi', 'Security', 'Guides', 'Download'].map((item, i) => (
                <motion.div
                  key={item}
                  initial={{ opacity: 0, y: 40 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.05 + 0.2 }}
                >
                  <Link
                    href={`#${item.toLowerCase().replace(' ', '-')}`}
                    onClick={() => setMenuOpen(false)}
                    className="font-display text-4xl md:text-6xl font-black uppercase tracking-tight text-black transition-colors hover:text-brand-blue hover:italic"
                    style={{ transform: "scaleY(1.2)" }}
                  >
                    {item}
                  </Link>
                </motion.div>
              ))}

              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.5 }}
                className="mt-12"
              >
                <Button href="/login" variant="brand" className="!px-10 !py-5 !text-xl !rounded-full !bg-brand-dark !text-white hover:!bg-brand-violet shadow-slush">
                  Launch App
                </Button>
              </motion.div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
};

export default Navbar;