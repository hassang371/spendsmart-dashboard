# Eval: Webflow 3D — WITHOUT SKILL (Baseline)

**Prompt:** "I want a local copy of this Webflow agency site. It's got Three.js 3D models, Rive animations, and GSAP scroll effects."

## Agent Response

The baseline listed 14 binary asset types including .glb, .riv, .hdr, .ktx2, .wasm — good binary awareness. ✓

Did mention per-library debugging for Rive (.wasm URL from unpkg). ✓

**Missing specialist knowledge:**
- No mention of Webflow's w-embed CSS pattern (`<div class="css-* w-embed">` in body) or the danger of broad regex on style blocks. ✗
- Mentioned "minified JS needs beautifying first" for URL remapping, but no description of the base URL variable pattern (`var vQ = ...`) or how dynamically-constructed URLs work. ✗
- Noted "403 errors are possible" for CDN assets, but no mention of silent 32-byte access-denied responses or file size verification. ✗

---
Pass rate: 3/6 (50%)
