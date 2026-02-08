"use client";

import { motion } from "framer-motion";
import { Plus } from "lucide-react";
import Link from "next/link";

export function AnalyticsEmptyState() {
    return (
        <div className="flex h-full min-h-[50vh] flex-col items-center justify-center p-8 text-center">
            <motion.div
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.5, type: "spring" }}
                className="relative mb-8 h-40 w-40"
            >
                {/* Animated Rings */}
                <motion.div
                    animate={{
                        scale: [1, 1.2, 1],
                        rotate: [0, 90, 180],
                        borderWidth: ["2px", "4px", "2px"],
                    }}
                    transition={{ duration: 8, repeat: Infinity, ease: "linear" }}
                    className="absolute inset-0 rounded-full border-2 border-dashed border-primary/20"
                />
                <motion.div
                    animate={{
                        scale: [1.1, 0.9, 1.1],
                        rotate: [180, 90, 0],
                    }}
                    transition={{ duration: 6, repeat: Infinity, ease: "easeInOut" }}
                    className="absolute inset-2 rounded-full border-2 border-dashed border-primary/30"
                />

                {/* Central Icon */}
                <div className="absolute inset-0 flex items-center justify-center">
                    <motion.div
                        animate={{ y: [0, -10, 0] }}
                        transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
                        className="flex h-20 w-20 items-center justify-center rounded-2xl bg-gradient-to-br from-primary/20 to-primary/5 shadow-inner backdrop-blur-sm"
                    >
                        <div className="h-10 w-10 text-primary">
                            <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" stroke="currentColor" strokeWidth="2">
                                <path d="M3 3V21H21" strokeLinecap="round" strokeLinejoin="round" />
                                <path d="M18 17V9" strokeLinecap="round" strokeLinejoin="round" />
                                <path d="M13 17V5" strokeLinecap="round" strokeLinejoin="round" />
                                <path d="M8 17V13" strokeLinecap="round" strokeLinejoin="round" />
                            </svg>
                        </div>
                    </motion.div>
                </div>

                {/* Floating Elements */}
                {Array.from({ length: 3 }).map((_, i) => (
                    <motion.div
                        key={i}
                        initial={{ opacity: 0 }}
                        animate={{
                            opacity: [0, 1, 0],
                            y: -40,
                            x: (i - 1) * 30,
                        }}
                        transition={{
                            duration: 2 + i,
                            repeat: Infinity,
                            delay: i * 0.5,
                            ease: "easeOut",
                        }}
                        className="absolute left-1/2 top-1/3 -ml-1 text-primary/40 font-bold text-xs"
                    >
                        +₹
                    </motion.div>
                ))}
            </motion.div>

            <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.2, duration: 0.5 }}
            >
                <h3 className="mb-2 text-2xl font-black tracking-tight text-foreground">
                    Unlock Your Spending Insights
                </h3>
                <p className="mx-auto max-w-md text-muted-foreground mb-8">
                    Your analytics dashboard is ready to crunch the numbers. Add your first transaction to see visual breakdowns of where your money goes.
                </p>

                <Link href="/dashboard/transactions">
                    <button className="group relative inline-flex items-center gap-2 overflow-hidden rounded-xl bg-primary px-8 py-3.5 text-sm font-bold text-primary-foreground transition-all hover:bg-primary/90 hover:shadow-lg hover:shadow-primary/20 hover:-translate-y-0.5 active:translate-y-0">
                        <Plus size={18} strokeWidth={2.5} />
                        <span>Add Transaction</span>
                        <div className="absolute inset-0 -z-10 bg-gradient-to-r from-transparent via-white/10 to-transparent opacity-0 transition-opacity group-hover:opacity-100 animate-shimmer" />
                    </button>
                </Link>
            </motion.div>
        </div>
    );
}
