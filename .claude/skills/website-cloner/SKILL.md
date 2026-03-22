---
name: website-cloner
description: |
  Use when the user wants a local copy of an existing website — to clone, download, mirror, capture, or get it working offline.
  Trigger on: "clone [site]", "download [url] locally", "get a local copy of", "mirror [site]", "replicate the look of [site]",
  "capture before the rebrand", "get [site] working locally", "want [site] offline", "grab this site", "poke around in the DOM locally".
  This looks simple but isn't — wget silently fails on JS-rendered sites, CDN assets need Referer headers, and asset URLs hide in minified JS variables. Use this skill rather than suggesting wget/curl.
  Works on: React/Next.js SPAs, Webflow, Vue/Nuxt, Three.js/GSAP/Rive animation sites, any modern website.
  Do NOT trigger for: building a new site from scratch, data scraping to CSV, screenshot analysis, E2E test setup, or debugging existing code.
license: MIT
metadata:
  version: "1.0.0"
  domain: browser-automation
  triggers: clone, mirror, replicate, copy, capture, download, website, local copy, static version, scrape
  role: specialist
  scope: browser-automation
  output-format: files
  related-skills: playwright-expert, cli-developer, python-pro
---

# Website Cloner

A specialist skill for creating faithful local copies of any modern website — from simple landing pages to complex SPAs with 3D rendering, animations, and custom JS frameworks.

## Core Philosophy

Traditional tools like `wget --mirror` and HTTrack fail on modern sites because they only capture what the server sends as static HTML. They cannot execute JavaScript, so JS-rendered content (React trees, Three.js scenes, GSAP-animated DOM, Webflow's inline CSS) is invisible to them. They also miss dynamically-constructed asset URLs buried inside minified JS.

The approach that works: **Playwright DOM capture + manual asset download**.

1. Use Playwright to navigate each page, wait for JS to fully render, then capture `document.documentElement.outerHTML` — the page as the browser sees it, not what the server sent.
2. Analyze JS source files to find dynamically-constructed asset URLs (CDN base URL variables).
3. Download all assets with appropriate headers — many CDNs require a `Referer` header.
4. Rewrite all remote URLs to local absolute paths.
5. Repair HTML/CSS corruption introduced by the Playwright capture pipeline.

## Prerequisites

Before starting, confirm:
- Playwright MCP is active and can reach the target URL
- `curl` is available (for asset downloads with custom headers)
- Python is available (for inline HTML/JS processing scripts)
- You have a local output directory in mind (e.g., `./clone/`)

## The 8 Phases

Work through phases in order. Read the linked reference when you reach each phase — don't preload all of them.

| # | Phase | What it accomplishes | Reference |
|---|-------|---------------------|-----------|
| 1 | **Reconnaissance** | Detect JS frameworks, find CDN domains, spot referrer-protected assets, map all pages/routes | `references/recon.md` |
| 2 | **HTML Capture** | Playwright DOM snapshot — the fully-rendered page, not the server HTML | `references/capture-and-repair.md` |
| 3 | **Asset Discovery** | Find all assets, including those constructed from JS base URL variables | `references/asset-discovery.md` |
| 4 | **URL Rewriting** | Replace CDN/remote URLs with local absolute paths; strip SRI integrity hashes | `references/url-rewriting.md` |
| 5 | **Corruption Repair** | Fix artifacts introduced by the Playwright JSON serialization pipeline | `references/capture-and-repair.md` |
| 6 | **CSS Restoration** | Recover CSS that lives inside `<div>` containers (common in Webflow and other page builders) | `references/css-restoration.md` |
| 7 | **Routing & Paths** | Create subdirectory `index.html` files for clean URLs; ensure all paths are absolute | `references/routing.md` |
| 8 | **Validation** | Verify every file downloaded correctly; test root and subdirectory pages | (inline below) |

## Top 5 Gotchas

Know these before you start — they account for most of the wasted debugging time.

### 1. Silent CDN Referrer Protection

Many CDNs silently return a 32-byte "Access denied" string with no HTTP error — the download looks successful but produces a broken binary. Always verify file sizes after downloading:

```bash
for f in $(find output/ -type f); do
  size=$(wc -c < "$f")
  if [ "$size" -lt 100 ]; then echo "SUSPICIOUS: $f ($size bytes)"; fi
done
```

Fix: add `-H "Referer: https://targetsite.com/"` to every curl command for that CDN.

### 2. The JS Base URL Variable Trap

On most agency-built and modern sites, asset URLs are never hardcoded — they're constructed at runtime from a minified base variable:

```javascript
var vQ = "https://cdn.example.com/assets"; // only THIS appears in source
// ...1000 lines of minified code later...
model: vQ + "/models/hero.glb"  // the full URL never appears anywhere
```

You must find and replace the variable assignment, not search for full URLs. Grepping for the CDN domain will find the variable; from there, grep for all concatenations. See `references/asset-discovery.md`.

### 3. Never Run Broad Regex on `<style>` Blocks

The most destructive mistake: running any kind of "clean empty rules" regex on style content. Webflow, WordPress, and other page builders embed CSS inside `<div>` containers in `<body>`. Minified CSS has patterns that look like empty rules but aren't. Any broad regex like `re.sub(r'[^{};\n]+\{\s*\}', '', content)` will silently destroy critical styling. Use only surgical string replacements targeting known-broken patterns.

### 4. Always Use Absolute Paths

Relative paths like `css/main.css` work from the root page but resolve to `/on-track/css/main.css` on a subdirectory page. Use `/css/main.css` everywhere — in HTML attributes, JS variable assignments, and any injected `<style>` or `<link>` tags.

### 5. CSS Source Order

A `<style>` block injected at the top of `<head>` loses to a `<link>` stylesheet loaded after it — same specificity, later source wins. When you need an override to stick regardless of injection point, use `!important`.

## Reference Guide

Load these files when you reach the corresponding phase. Do not preload all of them upfront.

| Topic | Reference | Load When |
|-------|-----------|-----------|
| Tech stack detection JS, CDN identification, page mapping | `references/recon.md` | Starting Phase 1 |
| DOM capture + all 7 corruption repair patterns | `references/capture-and-repair.md` | Starting Phase 2 or Phase 5 |
| JS base URL variable analysis, asset extraction, referrer-curl | `references/asset-discovery.md` | Starting Phase 3 |
| URL variable replacement, SRI removal, dev artifact cleanup | `references/url-rewriting.md` | Starting Phase 4 |
| CSS embed block recovery, live re-fetch recovery script | `references/css-restoration.md` | Phase 6 or whenever CSS looks wrong |
| Subdirectory routing, absolute paths, page transition lifecycle | `references/routing.md` | Starting Phase 7 |
| Full 20-problem catalog indexed by symptom | `references/problem-catalog.md` | When debugging an unexpected issue |

## Validation Checklist

Run this after completing all phases. Don't claim done until every item passes.

- [ ] Every downloaded file is > 100 bytes (run the size check above)
- [ ] Root page (`/`) renders with correct styles and fonts
- [ ] At least one subdirectory page (e.g., `/about/`, `/products/`) renders correctly
- [ ] No `localhost:` or `127.0.0.1` references remain in any HTML file
- [ ] No CDN or remote URLs remain in HTML/CSS/JS pointing to undownloaded assets
- [ ] Browser console shows no 404s for local assets
- [ ] Fonts load (visible in Network tab)
- [ ] If the site has animations or page transitions: they initialize and complete

## Delivering the Output

1. Serve locally: `cd clone/ && python -m http.server 8080`
2. Provide a summary: frameworks detected, CDN domains handled, total files, any known gaps
3. Note content that couldn't be replicated: server-side API calls, CMS-driven data, auth-gated pages, CORS-restricted endpoints
