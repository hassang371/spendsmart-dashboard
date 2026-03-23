---
id: BUG-013
title: CSP blocks Vercel preview toolbar and noise image; API calls hit localhost in production
status: Verified
severity: High
affected: apps/web/next.config.ts, Vercel environment variables
reported: 2026-03-23
---

## Summary

Three errors appear in the Vercel preview deployment at `/dashboard`:

1. **CSP blocks Vercel preview script** — `https://vercel.live/_next-live/feedback/feedback.js` blocked because `vercel.live` is absent from `script-src`.
2. **CSP blocks noise texture** — `https://grainy-gradients.vercel.app/noise.svg` blocked because the domain is absent from `img-src`.
3. **API calls hit `localhost:8000`** — `NEXT_PUBLIC_API_URL` was not set in Vercel, so the build baked in the `.env.local` default `http://localhost:8000/api/v1`, causing all API fetches to fail with CORS/ERR_FAILED in the deployed environment.

## Root Cause

- `next.config.ts` `appCsp` was written before the Vercel preview toolbar and grainy-gradients texture were introduced.
- `NEXT_PUBLIC_API_URL` was never added as a Vercel environment variable; only the local `.env.local` value was present.
- `connect-src` still referenced the old `https://scale-api.vercel.app` placeholder instead of the Railway URLs.

## Fix

- Added `https://vercel.live` to `script-src` in `appCsp` and `landingCsp`.
- Added `https://grainy-gradients.vercel.app` to `img-src` in both CSP blocks.
- Replaced `https://scale-api.vercel.app` with Railway URLs in `connect-src`.
- Set `NEXT_PUBLIC_API_URL` in Vercel:
  - Production → `https://scale-api-production-4373.up.railway.app/api/v1`
  - Preview → `https://scale-api-staging.up.railway.app/api/v1`

## Status

Implementation complete. Verified by commit on `main`.
