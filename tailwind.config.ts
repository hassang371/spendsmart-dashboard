import type { Config } from "tailwindcss";

const config: Config = {
    content: [
        "./pages/**/*.{js,ts,jsx,tsx,mdx}",
        "./components/**/*.{js,ts,jsx,tsx,mdx}",
        "./app/**/*.{js,ts,jsx,tsx,mdx}",
    ],
    theme: {
        extend: {
            colors: {
                background: "#020617", // Slate 950
                foreground: "#F8FAFC", // Slate 50
                primary: {
                    DEFAULT: "#3B82F6", // Electric Blue
                    foreground: "#FFFFFF",
                },
                secondary: {
                    DEFAULT: "#1E293B", // Slate 800
                    foreground: "#F8FAFC",
                },
                accent: {
                    DEFAULT: "#F59E0B", // Amber/Orange
                    foreground: "#000000",
                },
                success: "#22C55E", // Green
                card: {
                    DEFAULT: "#0F172A", // Slate 900
                    foreground: "#F8FAFC",
                },
            },
            fontFamily: {
                sans: ["var(--font-outfit)", "sans-serif"],
                mono: ["var(--font-space-grotesk)", "monospace"],
            },
            borderRadius: {
                lg: "var(--radius)",
                md: "calc(var(--radius) - 2px)",
                sm: "calc(var(--radius) - 4px)",
                xl: "1rem",
                "2xl": "1.5rem",
                "3xl": "2rem", // Slush style large roundness
            },
            backgroundImage: {
                "gradient-radial": "radial-gradient(var(--tw-gradient-stops))",
                "slush-gradient": "linear-gradient(135deg, #3B82F6 0%, #8B5CF6 100%)",
            },
            keyframes: {
                "fade-in-up": {
                    "0%": { opacity: "0", transform: "translateY(20px)" },
                    "100%": { opacity: "1", transform: "translateY(0)" },
                },
                float: {
                    "0%, 100%": { transform: "translateY(0)" },
                    "50%": { transform: "translateY(-10px)" },
                },
                "blur-in": {
                    "0%": { filter: "blur(10px)", opacity: "0" },
                    "100%": { filter: "blur(0)", opacity: "1" },
                },
            },
            animation: {
                "fade-in-up": "fade-in-up 0.5s ease-out forwards",
                float: "float 3s ease-in-out infinite",
                "blur-in": "blur-in 0.8s ease-out forwards",
            },
        },
    },
    plugins: [],
};
export default config;
