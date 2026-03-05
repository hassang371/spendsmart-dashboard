/**
 * Returns the appropriate Storage object based on the environment.
 * - Development: sessionStorage (clears when the tab closes, easy for debugging)
 * - Production (Vercel): localStorage (persists across sessions for better UX)
 */
export function getAppStorage(): Storage | null {
  // Prevent SSR errors in Next.js
  if (typeof window === 'undefined') return null;

  // Next.js automatically sets NODE_ENV to 'development' when running `next dev`
  if (process.env.NODE_ENV === 'development') {
    return window.sessionStorage;
  }

  // Next.js sets NODE_ENV to 'production' on Vercel
  return window.localStorage;
}
