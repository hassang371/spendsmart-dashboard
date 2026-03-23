# Eval: Webflow 3D — WITH SKILL

**Prompt:** "I want a local copy of this Webflow agency site. It's got Three.js 3D models, Rive animations, and GSAP scroll effects. The URL is <https://example-webflow-3d.webflow.io>"

## Agent Response

The agent invoked `website-cloner` skill and loaded `asset-discovery.md` and `css-restoration.md` references.

**Phase 1 — Recon:** Detected Webflow, Three.js, Rive, GSAP via stack detection JS. Identified CDN domains including Webflow's cloudfront CDN and unpkg for Rive runtime.

**Phase 3 — Asset discovery (critical):**
> ".glb 3D models, .hdr environment maps, .riv Rive animations, and .wasm decoders will NOT appear as full URLs anywhere in the source."
> "Look for `var vQ = "https://cdn.example.com/assets"` in the minified JS — all asset URLs are constructed by concatenating with this base variable."

Specifically called out downloading the Rive WASM runtime from unpkg.

**Phase 6 — CSS restoration:**
> "Webflow embeds CSS in `<div class="css-* w-embed">` elements in `<body>` — not in `<head>`. These are destroyed by any broad regex on style content. Never run `re.sub(r'[^{};\n]+\{\s*\}', '', content)` on style blocks."
Provided live re-fetch recovery script.

**Phase 8 — Validation:**
> "Check every downloaded file is over 100 bytes (CDN access-denied responses are ~32 bytes)."

---
Pass rate: 6/6 (100%)
