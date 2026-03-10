import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'lh3.googleusercontent.com',
      },
      {
        protocol: 'https',
        hostname: 'nbtowufbthavewruaicc.supabase.co',
      },
      {
        protocol: 'https',
        hostname: 'avatars.githubusercontent.com',
      },
      {
        protocol: 'https',
        hostname: 'cdn.prod.website-files.com',
      },
      {
        protocol: 'https',
        hostname: 'sui-dev.b-cdn.net',
      },
    ],
  },
  async headers() {
    const isProd = process.env.NODE_ENV === 'production';

    // Strict CSP for authenticated app routes
    const appCsp = `
      default-src 'self';
      script-src 'self' https://js.sentry-cdn.com https://browser.sentry-cdn.com https://va.vercel-scripts.com;
      style-src 'self';
      img-src 'self' blob: data: https://lh3.googleusercontent.com https://nbtowufbthavewruaicc.supabase.co https://avatars.githubusercontent.com https://cdn.prod.website-files.com https://sui-dev.b-cdn.net;
      font-src 'self' data:;
      object-src 'none';
      base-uri 'self';
      form-action 'self';
      frame-ancestors 'none';
      connect-src 'self' http://localhost:8000 https://scale-api.vercel.app https://nbtowufbthavewruaicc.supabase.co https://*.sentry.io;
      worker-src 'self' blob:;
      upgrade-insecure-requests;
    `
      .replace(/\s{2,}/g, ' ')
      .trim();

    // Permissive CSP for the landing page (needs Webflow, GSAP, Slater, HubSpot CDNs)
    const landingCsp = `
      default-src 'self';
      script-src 'self'
        https://js.sentry-cdn.com https://browser.sentry-cdn.com https://va.vercel-scripts.com
        https://d3e54v103j8qbb.cloudfront.net
        https://cdn.jsdelivr.net
        https://assets.greensock.com
        https://unpkg.com
        https://cdn.prod.website-files.com
        https://assets.slater.app
        https://js.hsforms.net;
      style-src 'self' 'unsafe-inline' https://cdn.prod.website-files.com;
      img-src 'self' blob: data: https://lh3.googleusercontent.com https://nbtowufbthavewruaicc.supabase.co https://avatars.githubusercontent.com https://cdn.prod.website-files.com https://sui-dev.b-cdn.net;
      font-src 'self' data: https://cdn.prod.website-files.com;
      object-src 'none';
      base-uri 'self';
      form-action 'self';
      frame-ancestors 'none';
      connect-src 'self' http://localhost:8000 https://scale-api.vercel.app https://nbtowufbthavewruaicc.supabase.co https://*.sentry.io https://cdn.prod.website-files.com;
      worker-src 'self' blob:;
      upgrade-insecure-requests;
    `
      .replace(/\s{2,}/g, ' ')
      .trim();

    const securityHeaders = [
      { key: 'X-Content-Type-Options', value: 'nosniff' },
      { key: 'X-Frame-Options', value: 'DENY' },
      { key: 'X-XSS-Protection', value: '1; mode=block' },
      { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
    ];

    const hsts = isProd
      ? { key: 'Strict-Transport-Security', value: 'max-age=31536000; includeSubDomains; preload' }
      : { key: 'Strict-Transport-Security', value: 'max-age=0' };

    return [
      // Landing page: permissive CSP for third-party Webflow/GSAP/Slater scripts
      {
        source: '/',
        headers: [
          { key: 'Content-Security-Policy', value: landingCsp },
          ...securityHeaders,
          hsts,
        ],
      },
      // All other routes: strict CSP
      {
        source: '/((?!$).*)',
        headers: [
          { key: 'Content-Security-Policy', value: appCsp },
          ...securityHeaders,
          hsts,
        ],
      },
    ];
  },
};

import { withSentryConfig } from '@sentry/nextjs';

export default withSentryConfig(nextConfig, {
  // For all available options, see:
  // https://www.npmjs.com/package/@sentry/webpack-plugin#options

  org: 'scale-13',

  project: 'javascript-nextjs',

  // Only print logs for uploading source maps in CI
  silent: !process.env.CI,

  // For all available options, see:
  // https://docs.sentry.io/platforms/javascript/guides/nextjs/manual-setup/

  // Upload a larger set of source maps for prettier stack traces (increases build time)
  widenClientFileUpload: true,

  // Route browser requests to Sentry through a Next.js rewrite to circumvent ad-blockers.
  // This can increase your server load as well as your hosting bill.
  // Note: Check that the configured route will not match with your Next.js middleware, otherwise reporting of client-
  // side errors will fail.
  tunnelRoute: '/monitoring',

  webpack: {
    // Enables automatic instrumentation of Vercel Cron Monitors. (Does not yet work with App Router route handlers.)
    // See the following for more information:
    // https://docs.sentry.io/product/crons/
    // https://vercel.com/docs/cron-jobs
    automaticVercelMonitors: true,

    // Tree-shaking options for reducing bundle size
    treeshake: {
      // Automatically tree-shake Sentry logger statements to reduce bundle size
      removeDebugLogging: true,
    },
  },
});
