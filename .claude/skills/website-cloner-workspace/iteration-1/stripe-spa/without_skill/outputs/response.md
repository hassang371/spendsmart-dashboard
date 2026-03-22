# Eval: Stripe SPA — WITHOUT SKILL (Baseline)

**Prompt:** "I want to clone the Stripe homepage so I can run it locally for design reference. I've got Playwright MCP set up. How should I approach this?"

## Agent Response

The baseline agent (no skill) independently used Playwright's `browser_evaluate` with `document.documentElement.outerHTML` — it correctly identified DOM capture as the right approach for a JS-heavy site.

**Phase 1 — Capture:** Used `browser_evaluate` to capture the rendered DOM. ✓

**Phase 2 — Assets:** Used `browser_network_requests` to enumerate loaded resources. Did NOT search for base URL variables in minified JS. ✗

**Phase 3 — Path rewriting:** Recommended *"replace absolute CDN URLs with relative local paths"* — this is the anti-pattern that breaks subdirectory pages. ✗

**Phase 4 — Serve:** Suggested `python -m http.server`.

**CDN protection:** Mentioned *"some CDN assets may 403"* as a limitation note, but did not detail referrer protection mechanics or the silent 32-byte denial pattern. ✗

**Corruption repair:** No mention of JSON pipeline corruption, escaped quotes, literal `\t` sequences, or any post-capture repair steps. ✗

Overall: caught the DOM capture pattern independently, missed the specialist knowledge the skill provides.

---
Pass rate: 2/6 (33%)
