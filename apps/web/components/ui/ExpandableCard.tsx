'use client';

import { useState, type ReactNode } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Maximize2, X } from 'lucide-react';

interface ExpandableCardProps {
  id: string;
  title: string;
  children: ReactNode | ((props: { isExpanded: boolean }) => ReactNode);
  className?: string; // Additional classes for the grid item
}

export function ExpandableCard({ id, title, children, className = '' }: ExpandableCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <>
      {/* The Compact Grid Card */}
      <motion.div
        layoutId={`card-container-${id}`}
        onClick={() => setIsExpanded(true)}
        className={`relative group flex flex-col overflow-hidden rounded-3xl border border-border bg-card shadow-lg transition-colors hover:border-primary/30 cursor-pointer ${className}`}
        style={{ willChange: 'transform, opacity' }}
      >
        {/* Header */}
        <motion.div
          layoutId={`card-header-${id}`}
          className="flex items-center justify-between px-6 py-4 border-b border-border/50"
        >
          <motion.h3
            layoutId={`card-title-${id}`}
            className="text-lg font-semibold text-foreground tracking-tight"
          >
            {title}
          </motion.h3>
          <button
            className="rounded-full bg-accent p-1.5 text-muted-foreground opacity-0 transition-all hover:bg-accent hover:text-foreground group-hover:opacity-100"
            aria-label="Expand chart"
          >
            <Maximize2 className="h-4 w-4" />
          </button>
        </motion.div>

        {/* Content (Compact) */}
        <motion.div
          layoutId={`card-content-${id}`}
          className="flex-1 p-6 relative w-full h-full min-h-0"
        >
          {typeof children === 'function' ? children({ isExpanded: false }) : children}
        </motion.div>
      </motion.div>

      {/* The Expanded Overlay */}
      <AnimatePresence>
        {isExpanded && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 md:p-12">
            {/* Dark Backdrop */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setIsExpanded(false)}
              className="absolute inset-0 bg-black/60 backdrop-blur-sm"
              style={{ willChange: 'opacity' }}
            />

            {/* Expanded Card */}
            <motion.div
              layoutId={`card-container-${id}`}
              className="relative z-10 flex h-full w-full max-w-7xl flex-col overflow-hidden rounded-3xl border border-border bg-background shadow-2xl"
              style={{ willChange: 'transform, opacity' }}
            >
              {/* Header */}
              <motion.div
                layoutId={`card-header-${id}`}
                className="flex items-center justify-between px-8 py-6 border-b border-border/50 bg-card/80 backdrop-blur-md"
              >
                <motion.h3
                  layoutId={`card-title-${id}`}
                  className="text-2xl font-bold text-foreground tracking-tight"
                >
                  {title}
                </motion.h3>
                <button
                  onClick={() => setIsExpanded(false)}
                  className="rounded-full bg-accent p-2 text-muted-foreground transition-colors hover:bg-accent/80 hover:text-foreground"
                  aria-label="Close expanded view"
                >
                  <X className="h-6 w-6" />
                </button>
              </motion.div>

              {/* Content (Expanded) */}
              <motion.div
                layoutId={`card-content-${id}`}
                className="flex-1 p-8 relative w-full h-full min-h-0 overflow-y-auto custom-scrollbar"
              >
                {typeof children === 'function' ? children({ isExpanded: true }) : children}
              </motion.div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </>
  );
}
