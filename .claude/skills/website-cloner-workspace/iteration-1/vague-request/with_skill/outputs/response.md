# Eval: Vague Request — WITH SKILL

**Prompt:** "can you download this website for me so i can have it locally" (no URL given)

## Agent Response

The agent invoked `website-cloner` skill even on this minimal prompt.

**Engaged fully** — did not say "I can't help" or recommend a simple download tool.

**Explained DOM capture rationale:**
> "Modern websites are built with JavaScript frameworks — React, Next.js, Vue, Webflow. Traditional tools like wget or HTTrack download the server-delivered HTML but miss everything rendered by JavaScript. A Playwright-based DOM capture approach is needed."

**Asked for URL** and simultaneously outlined all 8 phases as a preview of what the process will involve:
1. Reconnaissance — detect tech stack and CDN domains
2. HTML Capture — Playwright DOM snapshot
3. Asset Discovery — JS base URL analysis + binary asset download
4. URL Rewriting — local path substitution
5. Corruption Repair — fix Playwright pipeline artifacts
6. CSS Restoration — recover w-embed CSS blocks
7. Routing — subdirectory index.html, absolute paths
8. Validation — file size checks, sub-page testing

**Explicitly warned against wget/HTTrack** as primary tools.

---
Pass rate: 5/5 (100%)
