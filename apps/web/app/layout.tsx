import type { Metadata } from 'next';
import { Inter, Oswald, Space_Grotesk } from 'next/font/google';
import './globals.css';

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-inter',
  display: 'swap',
});

const oswald = Oswald({
  subsets: ['latin'],
  variable: '--font-oswald',
  display: 'swap',
});

const spaceGrotesk = Space_Grotesk({
  subsets: ['latin'],
  variable: '--font-space-grotesk',
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'SCALE — Personal Financing Made Easy',
  description: 'Real-time financial analytics, AI-powered spending predictions, and agentic AI accountants to manage your money.',
  openGraph: {
    title: 'SCALE — Personal Financing Made Easy',
    description: 'Real-time financial analytics, AI-powered spending predictions, and agentic AI accountants to manage your money.',
    images: ['/slush/6870e4e53832c8115a855885_slush_opengraph.jpg'],
    type: 'website',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'SCALE — Personal Financing Made Easy',
    description: 'Real-time financial analytics, AI-powered spending predictions, and agentic AI accountants to manage your money.',
    images: ['/slush/6870e4e53832c8115a855885_slush_opengraph.jpg'],
  },
  icons: {
    icon: '/slush/680905cfdc45073838364973_favicon.svg',
    shortcut: '/slush/680905cfdc45073838364973_favicon.svg',
    apple: '/slush/680905cfdc45073838364974_webclip.svg',
  },
};

import { ThemeProvider } from '../components/theme-provider';

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body
        className={`${inter.variable} ${oswald.variable} ${spaceGrotesk.variable} font-sans antialiased bg-background text-foreground`}
      >
        <ThemeProvider attribute="class" defaultTheme="dark" enableSystem disableTransitionOnChange>
          {children}
        </ThemeProvider>
      </body>
    </html>
  );
}
