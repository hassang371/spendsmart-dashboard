# Eval: Stripe SPA — WITH SKILL

**Prompt:** "I want to clone the Stripe homepage so I can run it locally for design reference. I've got Playwright MCP set up. How should I approach this?"

## Agent Response

The agent invoked `website-cloner` skill and delivered a complete 8-phase guide.

**Explicitly rejected wget/HTTrack** — stated traditional tools fail on JS-heavy SPAs.

**DOM capture approach** — used `document.documentElement.outerHTML` via Playwright `browser_evaluate`, waiting for full JS render before capture.

**JS base URL variable (Phase 3):**
> "The real CDN base URL is never written out in full in the HTML. Look for a pattern like `var vQ = "https://cdn.stripe.com/v3/fingerprinted/assets"` in the minified JS bundles. You must download the JS bundles, grep for the CDN domain to find the base variable, then find all concatenations."

**Referrer protection (Phase 1):**
> "Test with and without Referer header using `curl -I`. Then verify every downloaded file with `wc -c` — a 32-byte file is a silent access-denied response."

**Absolute paths:**
> "Use absolute paths (/assets/...), not relative ones. This is critical for subdirectory pages — relative paths break when you're at /pricing/ vs the root."

**Corruption repair (Phase 5):** Complete Python repair script covering JSON wrapper stripping, escaped quote unescaping, literal `\t` removal, broken `</@media>` tag fix.

**All 8 phases covered in order** — Recon → Capture → Asset Discovery → URL Rewriting → Corruption Repair → CSS Restoration → Routing → Validation.

---
Pass rate: 6/6 (100%)
