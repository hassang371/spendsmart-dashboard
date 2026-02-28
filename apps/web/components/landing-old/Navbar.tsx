import Link from 'next/link';
import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import Button from './Button';
import { Plus, X } from 'lucide-react';

const Navbar: React.FC = () => {
  const [menuOpen, setMenuOpen] = useState(false);
  // const [isScrolled, setIsScrolled] = useState(false);
  // const { scrollY } = useScroll();

  // useMotionValueEvent(scrollY, "change", (latest) => {
  //   setIsScrolled(latest > 50);
  // });

  // Lock body scroll when menu is open
  useEffect(() => {
    if (menuOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = 'unset';
    }
    return () => {
      document.body.style.overflow = 'unset';
    };
  }, [menuOpen]);

  const menuLinks = ['Features', 'Testimonials', 'Pricing', 'FAQ'];

  return (
    <>
      <nav className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 py-6`}>
        <div className="container mx-auto px-6 flex items-center justify-between">
          {/* Logo (Top Left) */}
          <Link
            href="/"
            className="relative z-50 group"
            aria-label="Go to Homepage"
            onClick={() => setMenuOpen(false)}
          >
            <div className="h-12 w-12 bg-white rounded-full border-2 border-black flex items-center justify-center shadow-slush transition-transform group-hover:scale-105 active:scale-95">
              <span className="font-display font-bold text-xl text-black">S</span>
            </div>
          </Link>

          {/* Right Side: Login + Menu Trigger */}
          <div className="flex items-center gap-4">
            <Button
              href="/login"
              variant="brand"
              className="!h-12 !px-4 !w-32 !text-sm !bg-white !text-black !border-black hover:!bg-brand-yellow"
            >
              Login
            </Button>

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
            initial={{ opacity: 0, y: '-100%' }}
            animate={{ opacity: 1, y: '0%' }}
            exit={{ opacity: 0, y: '-100%' }}
            transition={{ type: 'spring', damping: 25, stiffness: 120 }}
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
            <div className="flex flex-1 flex-col items-center justify-center gap-2 p-6 overflow-hidden">
              {menuLinks.map((item, i) => (
                <motion.div
                  key={item}
                  initial={{ opacity: 0, y: 40 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.05 + 0.2 }}
                >
                  <Link
                    href={`#${item.toLowerCase()}`}
                    onClick={() => setMenuOpen(false)}
                    className="font-display font-black uppercase tracking-tighter text-black transition-colors hover:text-brand-blue hover:italic leading-[0.9]"
                    style={{ fontSize: '13vw' }} // HUGE text
                  >
                    {item}
                  </Link>
                </motion.div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
};

export default Navbar;
