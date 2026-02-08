import type { Metadata } from "next";
import { Inter, Oswald } from "next/font/google";
import "./globals.css";

const inter = Inter({
    subsets: ["latin"],
    variable: "--font-inter",
    display: "swap",
});

const oswald = Oswald({
    subsets: ["latin"],
    variable: "--font-oswald",
    display: "swap",
});

export const metadata: Metadata = {
    title: "SCALE — Finance, Leveled Up.",
    description: "Finance. Leveled Up.",
};

import { ThemeProvider } from "../components/theme-provider";

export default function RootLayout({
    children,
}: Readonly<{
    children: React.ReactNode;
}>) {
    return (
        <html lang="en" suppressHydrationWarning>
            <body className={`${inter.variable} ${oswald.variable} font-sans antialiased bg-background text-foreground`}>
                <ThemeProvider
                    attribute="class"
                    defaultTheme="dark"
                    enableSystem
                    disableTransitionOnChange
                >
                    {children}
                </ThemeProvider>
            </body>
        </html>
    );
}
