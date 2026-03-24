# Website Cloning: An Exhaustive Guide

## From landonorris.com to a Near-Exact Local Clone

**Status:** Complete
**Date:** 2026-03-16
**Target site:** landonorris.com
**Technologies encountered:** Webflow, Three.js r174, Rive, GSAP 3.13.0, SplitText, Lenis, ScrollTrigger
**Purpose:** This document captures every step, problem, and solution from cloning a complex production website. It will be used as the foundation for a reusable website-cloning skill.

---

## Table of Contents

1. [Philosophy & Strategy](#1-philosophy--strategy)
2. [Phase 1: Reconnaissance](#2-phase-1-reconnaissance)
3. [Phase 2: HTML Capture](#3-phase-2-html-capture)
4. [Phase 3: Asset Discovery & Download](#4-phase-3-asset-discovery--download)
5. [Phase 4: URL Rewriting](#5-phase-4-url-rewriting)
6. [Phase 5: HTML Corruption Repair](#6-phase-5-html-corruption-repair)
7. [Phase 6: CSS Restoration](#7-phase-6-css-restoration)
8. [Phase 7: Subdirectory Routing & Path Fixes](#8-phase-7-subdirectory-routing--path-fixes)
9. [Phase 8: Page Transition Restoration](#9-phase-8-page-transition-restoration)
10. [Problem Catalog](#10-problem-catalog)
11. [Key Patterns & Anti-Patterns](#11-key-patterns--anti-patterns)
12. [Final File Structure](#12-final-file-structure)
13. [Lessons Learned](#13-lessons-learned)

---

## 1. Philosophy & Strategy

### Why Not HTTrack/wget?

Traditional mirroring tools (HTTrack, wget --mirror) fail on modern JavaScript-heavy sites because:

- They only download what the server sends as static HTML
- They miss JS-rendered content (Three.js scenes, Rive canvases, GSAP-animated DOM)
- They don't execute JavaScript, so dynamically constructed asset URLs are invisible
- They often break on SPAs, Webflow sites, and sites with complex routing

### The Chosen Strategy: DOM Snapshot + Manual Asset Download

The approach that works for complex sites:

1. **Playwright DOM capture** — Navigate to each page, wait for JS to render, capture `document.documentElement.outerHTML`. This gives you the fully-rendered DOM including JS-generated elements.
2. **Manual asset download** — Identify all asset URLs (JS, CSS, fonts, 3D models, textures, animations) through source analysis, then download with appropriate headers.
3. **URL rewriting** — Replace all CDN/remote URLs with local relative/absolute paths.
4. **Post-processing** — Fix HTML corruption from the capture pipeline, restore stripped CSS, repair broken paths.

### Why This Works

- You get the page as the browser sees it, not as the server sends it
- You can handle referrer-protected CDNs by setting custom headers
- You can trace JS variable patterns to find dynamically-constructed URLs
- You control every transformation step, so you can debug when things break

---

## 2. Phase 1: Reconnaissance

### Step 1: Technology Stack Detection

Before downloading anything, run a comprehensive stack detection script in the browser. This tells you what you're dealing with.

**Tool:** Playwright `browser_evaluate` on the target site.

```javascript
() => {
  return {
    // Page builder
    webflow: !!window.Webflow,
    wfDomain: document.documentElement.getAttribute('data-wf-domain'),

    // JS frameworks
    react: !!window.React || !!window.__REACT_DEVTOOLS_GLOBAL_HOOK__,
    nextjs: !!window.__NEXT_DATA__,
    nuxt: !!window.__NUXT__,
    vue: !!window.__VUE__,

    // Animation libraries
    gsap: !!window.gsap,
    gsapVersion: window.gsap?.version,
    scrollTrigger: !!window.ScrollTrigger,
    splitText: !!window.SplitText,
    lenis: !!window.lenis,
    barba: !!window.barba,

    // 3D / Graphics
    three: !!window.THREE,
    threeVersion: window.THREE?.REVISION,

    // Rive
    riveCanvases: document.querySelectorAll('canvas[data-rive-primary], canvas[data-rive-nav-hamburger]').length,

    // jQuery
    jquery: !!window.jQuery,
    jqueryVersion: window.jQuery?.fn?.jquery,

    // All external scripts
    scripts: [...document.querySelectorAll('script[src]')].map(s => s.src),

    // All stylesheets
    stylesheets: [...document.querySelectorAll('link[rel="stylesheet"]')].map(l => l.href),

    // All font preloads
    fonts: [...document.querySelectorAll('link[rel="preload"][as="font"]')].map(l => l.href),
  };
}
```

### Step 2: Identify CDN Domains

From the script/stylesheet URLs, identify all CDN domains:

| Domain | Purpose | Auth Required? |
|---|---|---|
| `cdn.prod.website-files.com` | Webflow CDN (images, fonts) | No |
| `lando.itsoffbrand.io` | OFF BRAND agency (3D, Rive) | Yes — Referer header |
| `assets.itsoffbrand.io` | OFF BRAND alternate CDN | Yes — Referer header |
| `d3e54v103j8qbb.cloudfront.net` | jQuery (Webflow default) | No |
| `unpkg.com` | Rive WASM runtime | No |

**Critical discovery:** The OFF BRAND CDNs return `"Access denied - Invalid referrer"` (32-byte response) without the header `Referer: https://landonorris.com/`. This is the single most common failure mode when cloning sites with agency-hosted assets.

### Step 3: Map All Pages

Identify every page/route on the site:

```
/                    -> index.html (home)
/on-track            -> on-track.html (F1 results)
/off-track           -> off-track.html (lifestyle)
/calendar            -> calendar.html (F1 calendar)
/legal/privacy-policy -> privacy-policy.html
/legal/terms-conditions -> terms-conditions.html
/partnerships        -> redirect to /
```

### Step 4: Identify Custom Frameworks

Inspect the DOM for custom data-attribute patterns:

- `data-rive-primary=""` — Rive canvas elements
- `data-rive-artboard="..."` — Rive artboard binding
- `data-rive-state-machine="..."` — Rive state machine binding
- `split-text="chars"` / `split-text="lines"` — GSAP SplitText markers
- `screen-reader=""` — Accessibility clone elements (JS-managed)
- `data-nav-wrap=""`, `data-nav-theme="light"` — Navigation system
- `data-taxi=""`, `data-taxi-view=""` — Page transition system
- `data-anim="text-hover"` — Hover animation triggers

---

## 3. Phase 2: HTML Capture

### Step 1: Navigate and Capture Each Page

For each page, use Playwright to:

1. Navigate to the URL
2. Wait for the page to fully render (network idle + JS execution)
3. Capture the rendered DOM

```javascript
// Via mcp__playwright__browser_evaluate
() => document.documentElement.outerHTML
```

This returns the **rendered DOM**, which includes:
- All JS-generated elements (SplitText character wrappers, screen-reader clones, GSAP inline styles)
- Resolved attribute values
- Computed inline styles from animation libraries

### Step 2: Save to Files

Save each page's HTML to the local folder structure:

```
lando/index.html          <- from /
lando/on-track.html       <- from /on-track
lando/off-track.html      <- from /off-track
lando/calendar.html       <- from /calendar
lando/privacy-policy.html <- from /legal/privacy-policy
lando/terms-conditions.html <- from /legal/terms-conditions
```

### Known Issue: Playwright JSON Pipeline Corruption

**CRITICAL:** When Playwright returns HTML via `browser_evaluate`, the result passes through a JSON serialization pipeline. This causes:

1. **JSON wrapper artifacts** — The HTML gets wrapped in `### Result\n"...\n"` markers
2. **Quote escaping** — All `"` inside the HTML become `\"`
3. **Tab escaping** — Actual tab characters become literal two-character `\t` sequences
4. **Debug text appended** — Playwright appends `### Ran Playwright code`, `### Open tabs`, console logs after `</html>`

These must ALL be cleaned in Phase 5.

---

## 4. Phase 3: Asset Discovery & Download

### Step 1: Download CSS and Fonts

Extract actual CSS URLs from the live DOM (don't guess filenames):

```javascript
// Get actual stylesheet URLs
[...document.querySelectorAll('link[rel="stylesheet"]')].map(l => l.href)
```

Download with curl:

```bash
curl -sL "https://cdn.prod.website-files.com/.../landonorris.css" -o css/landonorris.css
```

For web fonts referenced in CSS `@font-face` rules:

```bash
curl -sL "https://cdn.prod.website-files.com/.../MonaSans-Variable.woff2" -o fonts/MonaSans-Variable.woff2
curl -sL "https://cdn.prod.website-files.com/.../Brier-Bold.woff2" -o fonts/Brier-Bold.woff2
```

### Step 2: Download JavaScript Files

Download all `<script src="...">` references. For this site:

```bash
# OFF BRAND main JS (the big one — 1.3MB)
curl -sL -H "Referer: https://landonorris.com/" \
  "https://lando.itsoffbrand.io/js/lando.OFF+BRAND.gold-android-fix-03.js" \
  -o js/custom-main.js

# jQuery
curl -sL "https://d3e54v103j8qbb.cloudfront.net/js/jquery-3.5.1.min.js" \
  -o js/jquery-3.5.1.min.js

# Webflow runtime
curl -sL "https://cdn.prod.website-files.com/.../webflow.js" \
  -o js/webflow-chunk.js
```

### Step 3: Analyze JS for Asset URLs (The Critical Step)

**This is the most important and most missed step.** Modern sites construct asset URLs dynamically in JavaScript using base URL variables. You cannot find these URLs by grepping for full paths.

**Method: Search for CDN domain references in JS source**

```python
import re
content = open('js/custom-main.js', 'r').read()

# Find all CDN URL references
for m in re.finditer(r'https?://[a-z]+\.itsoffbrand\.io[^\s"\'`,;)}]*', content):
    print(f"pos {m.start()}: {m.group()}")
```

**What you find:**

```
pos 1197044: var vQ="https://lando.itsoffbrand.io/gl"
```

This is a **base URL variable**. ALL 3D assets are constructed from it:

```javascript
var vQ = "https://lando.itsoffbrand.io/gl";
// ...later in code...
helmet: vQ + "/models/helmet-21.glb",
hdri: vQ + "/hdri/studio_small_08_1k--light.hdr",
textures: vQ + `/textures/head/${iQ}/diffuse.${iQ}`,
```

**Method: Trace all concatenations from the base variable**

```python
# Find all paths built from vQ
for m in re.finditer(r'vQ\+["\'/]([^"\']+)', content):
    print(m.group(1))
```

This reveals the complete asset manifest:
- `/models/helmet-21.glb`, `/models/disco-02.glb`, `/models/sotd.glb`
- `/models/tracks/tracks-05.glb`
- `/hdri/studio_small_08_1k--light.hdr`, `--faded.hdr`, `--dark.hdr`
- `/textures/head/webp/{diffuse,depth,normal,alpha,shadow,shadow-softer-edit}.webp`
- `/textures/helmet/webp/{Metallic,Normal,Roughness}.webp`
- `/textures/helmet/webp/gold/BaseColor.webp`
- `/textures/helmet/webp/disco/{BaseColor,lens-flare-15,mask-01,matcap-01}.webp`
- `/textures/glass/webp/{BaseColor,Metallic,Normal,Roughness}.webp`
- `/textures/tracks/lando__matcap-02.webp`
- `/textures/noise/noise-03.webp`
- `/textures/plastic/plastic__matcap-02.webp`
- `/fonts/Brier-Bold-msdf.json`, `/fonts/MonaSans-Bold-msdf.json`
- `/draco/draco_decoder.js`, `/draco/draco_decoder.wasm`, `/draco/draco_wasm_wrapper.js`
- `/basis/basis_transcoder.js`, `/basis/basis_transcoder.wasm`

**Also check other JS files for different variable names:**

```python
# lando-offbrand.js uses dQ
content2 = open('js/lando-offbrand.js', 'r').read()
re.findall(r'var dQ="[^"]+"', content2)  # var dQ="https://lando.itsoffbrand.io/gl"

# lando-by-offbrand.js uses Z8 with DIFFERENT CDN domain
content3 = open('js/lando-by-offbrand.js', 'r').read()
re.findall(r'var Z8="[^"]+"', content3)  # var Z8="https://assets.itsoffbrand.io/lando/gl"
```

### Step 4: Download All Assets

**Always include the Referer header for protected CDNs:**

```bash
REF="-H 'Referer: https://landonorris.com/'"
UA="-H 'User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'"

# 3D Models
curl -sL $REF $UA "https://lando.itsoffbrand.io/gl/models/helmet-21.glb" -o gl/models/helmet-21.glb

# Verify file isn't the 32-byte "Access denied" response
wc -c gl/models/helmet-21.glb  # Should be >1KB
```

**Verify EVERY downloaded file:**

```bash
# Check for the "Access denied" response
for f in $(find gl/ -type f); do
  size=$(wc -c < "$f")
  if [ "$size" -lt 100 ]; then
    echo "SUSPICIOUS: $f ($size bytes)"
    head -c 50 "$f"
  fi
done
```

### Step 5: Download Rive Animation Files

Rive files (`.riv`) are binary animation files. Find them by searching JS for `.riv`:

```python
for m in re.finditer(r'["\']([^"\']*\.riv)["\']', content):
    print(m.group(1))
```

Download each:

```bash
curl -sL -H "Referer: https://landonorris.com/" \
  "https://lando.itsoffbrand.io/rive/page-transition.riv" -o rive/page-transition.riv
```

Also download the Rive WASM runtime:

```bash
curl -sL "https://unpkg.com/@rive-app/canvas-lite@2.26.4/rive.wasm" -o rive/rive.wasm
```

### Step 6: Download Images

Extract image URLs from HTML `src`/`srcset` attributes and CSS `url()` references:

```python
# From HTML
for m in re.finditer(r'src="(https://cdn\.prod\.website-files\.com/[^"]+)"', html):
    print(m.group(1))

# From srcset
for m in re.finditer(r'(https://cdn\.prod\.website-files\.com/[^\s]+)', html):
    print(m.group(1))
```

### Step 7: Format-Responsive Textures

Some sites load different texture formats based on device:

```javascript
var iQ = window.innerWidth > 991 ? "webp" : "ktx2";
// Used as: vQ + `/textures/head/${iQ}/diffuse.${iQ}`
```

For the clone, download the WebP versions (desktop) since that's the common case. You can also download KTX2 if you want mobile support, but WebP works everywhere.

---

## 5. Phase 4: URL Rewriting

### Step 1: Rewrite JS Base URL Variables

**This is the most important rewrite.** Don't try to find-and-replace every full URL — change the base variable assignment.

```python
content = open('js/custom-main.js', 'r').read()

# Change CDN base to local absolute path
content = content.replace(
    'var vQ="https://lando.itsoffbrand.io/gl"',
    'var vQ="/gl"'
)

# Also fix Rive base path
content = content.replace(
    'var mj="https://lando.itsoffbrand.io/rive/"',
    'var mj="/rive/"'
)

open('js/custom-main.js', 'w').write(content)
```

**Use absolute paths (`/gl`) not relative (`gl`)** — relative paths break on subdirectory pages like `/on-track/index.html` where `gl/` would resolve to `/on-track/gl/`.

**Repeat for every JS file with a different variable name:**

| File | Variable | Original Value | New Value |
|---|---|---|---|
| `custom-main.js` | `vQ` | `"https://lando.itsoffbrand.io/gl"` | `"/gl"` |
| `lando-offbrand.js` | `dQ` | `"https://lando.itsoffbrand.io/gl"` | `"/gl"` |
| `lando-by-offbrand.js` | `Z8` | `"https://assets.itsoffbrand.io/lando/gl"` | `"/gl"` |

### Step 2: Rewrite HTML Script/CSS References

Replace CDN URLs with local paths in HTML:

```python
# Script tags
content = re.sub(
    r'src="https://lando\.itsoffbrand\.io/js/[^"]*\.js"',
    'src="js/custom-main.js"',
    content
)

# CSS links
content = re.sub(
    r'href="https://cdn\.prod\.website-files\.com/[^"]*\.css"',
    'href="css/landonorris.css"',
    content
)

# Font preloads
content = re.sub(
    r'href="https://cdn\.prod\.website-files\.com/[^"]*MonaSans[^"]*\.woff2"',
    'href="fonts/MonaSans-Variable.woff2"',
    content
)
```

### Step 3: Remove SRI Integrity Hashes

If you modified any CSS/JS files (which you did by changing URLs), the SRI hashes will fail:

```python
content = re.sub(r' integrity="sha384-[^"]+"', '', content)
content = re.sub(r' crossorigin="anonymous"', '', content)
```

### Step 4: Remove Development Artifacts

Playwright DOM snapshots may include development tools:

```python
# Remove localhost dev server scripts
content = re.sub(r'<script[^>]*localhost[^>]*></script>', '', content)

# Remove dat.gui debug panels (Webflow dev tools)
content = re.sub(r'<div class="dg[^"]*"[^>]*>.*?</div>', '', content)
```

---

## 6. Phase 5: HTML Corruption Repair

The Playwright DOM capture pipeline introduces several forms of corruption that must be repaired.

### Fix 1: JSON Wrapper Artifacts

The HTML may start with `### Result\n"` and end with `"\n`:

```python
# Strip leading artifact
if '### Result' in content[:100]:
    content = re.sub(r'^.*?<!DOCTYPE', '<!DOCTYPE', content, flags=re.DOTALL)

# Strip trailing artifact
content = re.sub(r'</html>.*$', '</html>', content, flags=re.DOTALL)
```

### Fix 2: Escaped Quotes

```python
content = content.replace('\\"', '"')
```

### Fix 3: Literal `\t` Sequences

The JSON pipeline converts tab characters to literal two-character `\t` strings. This creates invalid CSS properties like `\tdisplay: flex`:

```python
# Fix CSS property corruption
content = content.replace('\\tdisplay', 'display')
content = content.replace('\\tpadding-bottom', 'padding-bottom')
content = content.replace('\\tposition', 'position')
content = content.replace('\\tpadding', 'padding')
content = content.replace('\\tmargin', 'margin')

# Generic: fix any remaining \t before lowercase letters in CSS context
content = re.sub(r'\\t([a-z])', r'\1', content)
```

### Fix 4: Playwright Debug Text After `</html>`

Every captured file has Playwright status output appended:

```python
match = re.search(r'</html>', content)
if match:
    content = content[:match.end()]
```

### Fix 5: Screen-Reader Duplicate Text

Playwright captures JS-generated accessibility clones. These have `screen-reader=""` attribute and create visible duplicate text.

**Two-part fix:**

**Part A: CSS hiding rule** — Inject into `<head>`:

```css
[screen-reader] {
    position: absolute !important;
    width: 1px !important;
    height: 1px !important;
    overflow: hidden !important;
    clip: rect(0, 0, 0, 0) !important;
    white-space: nowrap !important;
    border: 0 !important;
    padding: 0 !important;
    margin: -1px !important;
}
```

**Part B: DOM element removal** (optional, reduces file size):

```python
content = re.sub(r'<div screen-reader=""[^>]*>.*?</div>', '', content)
```

### Fix 6: Broken `</@media` Tags

DOM capture can corrupt `@media` queries inside `<style>` blocks:

```python
content = content.replace('</@media', '@media')
```

### Fix 7: Webflow Badge Removal

```css
.w-webflow-badge { display: none !important; }
```

---

## 7. Phase 6: CSS Restoration

### The Problem

The most catastrophic error in the cloning process was an aggressive CSS cleaning regex that emptied all Webflow CSS embed blocks:

```python
# THIS REGEX DESTROYED ALL CSS CONTENT:
re.sub(r'[^{};\n]+\{\s*\}', '', style_content)
```

This turned `<div class="css-root w-embed"><style>:root { --color: #fff; ... }</style></div>` into `<div class="css-root w-embed"></div>`.

The site uses **14 CSS embed blocks** containing critical styles for: root variables, utilities, split-text animations, Lenis smooth scroll, navigation theming, button styles, page-specific layouts, responsive breakpoints, edit mode, and Safari fixes.

### The Solution: Re-fetch CSS from Live Site

When local CSS is destroyed and can't be recovered from git (untracked files), re-fetch from the live site:

```python
import urllib.request
import re
import json

pages = {
    'home': 'https://landonorris.com/',
    'on-track': 'https://landonorris.com/on-track',
    'off-track': 'https://landonorris.com/off-track',
    'calendar': 'https://landonorris.com/calendar',
}

all_css = {}

for page_name, url in pages.items():
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 ...',
        'Referer': 'https://landonorris.com/'
    })
    resp = urllib.request.urlopen(req, timeout=30)
    html = resp.read().decode('utf-8')

    # Extract CSS from w-embed divs
    pattern = r'<div class="(css-[a-z-]+) w-embed"><style>(.*?)</style></div>'
    for cls, css in re.findall(pattern, html, re.DOTALL):
        if cls not in all_css or len(css) > len(all_css[cls]):
            all_css[cls] = css

# Restore into local HTML files
for html_file in html_files:
    content = open(html_file, 'r').read()
    for css_class, css_content in all_css.items():
        empty = f'<div class="{css_class} w-embed"></div>'
        full = f'<div class="{css_class} w-embed"><style>{css_content}</style></div>'
        content = content.replace(empty, full)
    open(html_file, 'w').write(content)
```

### Key Learning

**NEVER run aggressive regex cleaning on `<style>` blocks inside HTML.** The Webflow w-embed pattern puts CSS inside `<div>` containers, and any regex that strips empty rules or "cleans" CSS will destroy critical styling. If you must clean CSS, do it surgically on specific known-broken patterns, not blanket regex.

### CSS Block Inventory

| Block | Purpose | Size |
|---|---|---|
| `css-root` | CSS custom properties (colors, spacing, timing) | 2160 chars |
| `css-utils` | Selection colors, utility classes, focus styles | 3501 chars |
| `css-split-type` | SplitText line/char wrapper positioning | 1560 chars |
| `css-lenis` | Smooth scroll engine integration | 462 chars |
| `css-nav` | Navigation theming (light/dark), brand colors | 2450 chars |
| `css-buttons` | Rive button rotation/inversion overrides | 234 chars |
| `css-home` | Home page helmet section masks, hero layout | 3032 chars |
| `css-on-track` | On-track page hero stats, masks | 2840 chars |
| `css-off-track` | Off-track page layouts, galleries | 2470 chars |
| `css-partnerships` | Partner grid, campaign layouts | 1818 chars |
| `css-breakpoints` | Responsive overrides (tablet, mobile) | 576 chars |
| `css-editmode` | Webflow editor mode visibility toggles | 2344 chars |
| `css-safari` | Safari-specific workarounds (empty rules for `.is-safari`, `.is-iphone`) | 600 chars |
| `css-tracks` | Track/circuit page layouts (only on on-track, calendar) | 1766 chars |

---

## 8. Phase 7: Subdirectory Routing & Path Fixes

### Clean URL Routing

The original site uses clean URLs (`/on-track` not `/on-track.html`). For a static file server, create subdirectory `index.html` files:

```
on-track/index.html      <- copy of on-track.html with adjusted paths
off-track/index.html     <- copy of off-track.html
calendar/index.html      <- copy of calendar.html
legal/privacy-policy/index.html
legal/terms-conditions/index.html
partnerships/index.html  <- redirect: <meta http-equiv="refresh" content="0;url=/">
```

### The Relative Path Problem

When a page lives at `/on-track/index.html`, relative paths like `css/landonorris.css` resolve to `/on-track/css/landonorris.css` (wrong).

**Two approaches:**

**Approach A: Depth-based relative prefixes**

```
on-track/index.html:     ../css/landonorris.css
legal/privacy-policy/:   ../../css/landonorris.css
```

**Approach B: Absolute paths from root (recommended)**

```
/css/landonorris.css     <- works from any depth
/js/custom-main.js
/fonts/MonaSans-Variable.woff2
```

We used Approach B for JS asset paths (`/gl`, `/rive/`) and Approach A for HTML references initially, then standardized on absolute paths to avoid depth-counting bugs.

### Font Path Fix in CSS

CSS `@font-face` rules use `url("../fonts/...")` which is relative to the CSS file location. Since our CSS is at `/css/landonorris.css`, the `../fonts/` path correctly resolves to `/fonts/`. This doesn't need changing.

But subdirectory `index.html` files that inline font preloads need adjusted paths:

```html
<!-- In on-track/index.html -->
<link rel="preload" href="../fonts/MonaSans-Variable.woff2" as="font" type="font/woff2" crossorigin>

<!-- In legal/privacy-policy/index.html -->
<link rel="preload" href="../../fonts/MonaSans-Variable.woff2" as="font" type="font/woff2" crossorigin>
```

---

## 9. Phase 8: Page Transition Restoration

### How the Original Transition Works

The site has a Rive-based page transition:

1. `.transition-w` — Full-screen overlay (z-index 9999, lime background)
2. `page-transition.riv` — Rive animation with state machine inputs: `initial`, `transition-out`, `transition-in`
3. `BL()` — JS function that initializes the Rive instance on the canvas
4. `EL()` — Shows overlay, triggers transition-out animation
5. `H$()` — Triggers transition-in animation, hides overlay after 500ms

### The CSS Specificity Problem

The main CSS file (`landonorris.css`) has:

```css
.transition-w { display: none; }  /* line 6620 */
```

The original site overrides this with a `<style>` block placed **after** the CSS link (right before `</head>`):

```css
.transition-w { display: flex; }
```

**Source order matters.** If the override `<style>` is placed **before** the CSS `<link>`, the CSS file wins and the overlay stays hidden.

### The Fix

In our clone, the injected `<style>` block was at the top of `<head>` (before the CSS link), so it was overridden. The fix: use `!important` to ensure priority regardless of source order:

```css
.transition-w { display: flex !important; }
```

### The Transition Lifecycle

```
Page load → .transition-w visible (display: flex, lime bg)
         → BL() loads page-transition.riv
         → Rive "initial" state plays
         → All Rive files load (allriveloaded event)
         → Page modules initialize
         → H$() called → triggers "transition-in" animation
         → 100ms: button fades out
         → 500ms: overlay hidden (visibility: hidden, pointer-events: none)
```

The JS uses `visibility: hidden` (not `display: none`) to hide the overlay, so `display: flex !important` doesn't conflict with the hide mechanism.

---

## 10. Problem Catalog

A complete reference of every problem encountered, ordered by frequency/impact.

### Category: CDN & Network

| # | Problem | Symptom | Root Cause | Solution |
|---|---|---|---|---|
| 1 | **Referrer protection** | 32-byte files, "Access denied" | CDN requires `Referer` header | Add `-H "Referer: https://targetsite.com/"` to curl |
| 2 | **Wrong asset URLs** | 404s on local server | Guessed filenames instead of extracting from DOM | Use `browser_evaluate` to get actual URLs |
| 3 | **Dynamic URL construction** | Assets still loading from CDN | URLs built from JS variables, not hardcoded | Find and replace base URL variable assignments |
| 4 | **Multiple CDN domains** | Some assets 403, others work | Different JS files use different CDN domains | Check ALL JS files for CDN references |

### Category: HTML Corruption

| # | Problem | Symptom | Root Cause | Solution |
|---|---|---|---|---|
| 5 | **JSON wrapper artifacts** | Invalid HTML start/end | Playwright JSON serialization | Strip `### Result` prefix, truncate after `</html>` |
| 6 | **Escaped quotes** | `\"` throughout HTML | JSON string escaping | `content.replace('\\"', '"')` |
| 7 | **Literal `\t` in CSS** | Unknown properties `\tdisplay` | Tab chars → `\t` in JSON | Regex: `re.sub(r'\\t([a-z])', r'\1', content)` |
| 8 | **Debug text after `</html>`** | Raw text at page bottom | Playwright status output captured | Truncate at `</html>` |
| 9 | **Broken `</@media`** | CSS parse errors | DOM capture corruption | `content.replace('</@media', '@media')` |
| 10 | **Doubled `<style>` tags** | Empty nested tags | Aggressive CSS cleaning regex | Targeted removal of empty `<style><style></style>` |

### Category: CSS

| # | Problem | Symptom | Root Cause | Solution |
|---|---|---|---|---|
| 11 | **Empty w-embed CSS divs** | ALL custom styling gone | `clean_style_block` regex destroyed content | Re-fetch CSS from live site, restore into empty divs |
| 12 | **CSS specificity override** | Transition overlay hidden | Injected style before CSS link | Add `!important` to critical overrides |
| 13 | **SRI hash mismatch** | CSS/JS blocked from loading | Modified files don't match integrity hash | Remove `integrity` and `crossorigin` attributes |
| 14 | **VS Code false positives** | 14 warnings in CSS | Vendor prefixes, deprecated properties | Ignore — severity 4 hints from original site's CSS |

### Category: DOM & JavaScript

| # | Problem | Symptom | Root Cause | Solution |
|---|---|---|---|---|
| 15 | **Screen-reader duplicates** | All text appears twice | Playwright captures JS-generated clones | CSS hiding + optional DOM removal |
| 16 | **Transition overlay stuck** | Lime screen covers page | `display: flex` without JS completing | Fix CSS specificity so JS can control visibility |
| 17 | **`require is not defined`** | Script error in Playwright | `run_code` executes in browser, not Node | Use `browser_evaluate` instead |
| 18 | **Dev server references** | 404 for localhost:6645 | Dev tool captured in DOM snapshot | Regex removal of localhost script tags |

### Category: Paths & Routing

| # | Problem | Symptom | Root Cause | Solution |
|---|---|---|---|---|
| 19 | **Relative path depth** | Assets 404 on sub-pages | `css/foo.css` resolves relative to subdir | Use absolute paths (`/css/`, `/js/`, `/gl/`) |
| 20 | **Font preload paths** | Font warnings on sub-pages | Preload href relative to wrong base | Depth-appropriate prefixes (`../`, `../../`) |

---

## 11. Key Patterns & Anti-Patterns

### Pattern: Base URL Variable in Minified JS

**What it looks like:**

```javascript
var vQ="https://cdn.example.com/assets";
// ...thousands of lines later...
model: vQ+"/models/thing.glb",
texture: vQ+`/textures/${format}/diffuse.${format}`,
```

**Why sed/grep fails:** The full URL never appears in the source. Only the base variable assignment does.

**How to handle:**
1. Search for CDN domain: `grep -n 'cdn.example.com' file.js`
2. Find the variable assignment: `var vQ="https://cdn.example.com/assets"`
3. Replace the assignment value: `var vQ="/assets"`
4. Search for all concatenations: `grep 'vQ+' file.js` to build the full asset list

### Pattern: Webflow CSS Embed (w-embed)

**What it looks like:**

```html
<div class="css-root w-embed"><style>:root { ... }</style></div>
<div class="css-nav w-embed"><style>.nav { ... }</style></div>
```

**Why it's fragile:** CSS lives inside `<div>` containers in `<body>`, not in `<head>`. Any DOM manipulation or cleaning regex can destroy these blocks.

**How to handle:** Treat w-embed divs as sacred. Never run regex cleaning on their content. If damaged, re-fetch from the live site using the extraction pattern: `r'<div class="(css-[a-z-]+) w-embed"><style>(.*?)</style></div>'`

### Pattern: Screen-Reader Accessibility Clones

**What it looks like:**

```html
<div split-text="chars" class="text-nav-link">Home</div>
<div screen-reader="">Home</div>  <!-- JS-created clone -->
```

**Why it causes problems:** DOM capture includes both elements. No CSS rule hides the clone. Browser shows double text.

**How to handle:** Inject `[screen-reader] { position: absolute; clip: rect(0,0,0,0); ... }` CSS.

### Pattern: Rive Data-Attribute Framework

**What it looks like:**

```html
<canvas data-rive-primary=""
        data-rive-artboard="page-transition"
        data-rive-state-machine="page-transition"></canvas>
```

**Why it matters:** Rive canvases don't render from HTML alone — they need: (a) the `.riv` binary file, (b) the Rive WASM runtime, (c) JS initialization code. All three must be present.

### Pattern: Format-Responsive Texture Loading

**What it looks like:**

```javascript
var iQ = window.innerWidth > 991 ? "webp" : "ktx2";
url: vQ + `/textures/head/${iQ}/diffuse.${iQ}`
```

**How to handle:** Download both format directories, or just the desktop format (webp) if you're targeting desktop only.

### Anti-Pattern: Aggressive CSS Regex Cleaning

**NEVER DO THIS:**

```python
re.sub(r'[^{};\n]+\{\s*\}', '', style_content)  # Removes "empty" rules
```

This regex matches much more than you think in minified CSS and will destroy valid rules. If you must clean CSS, target specific known-broken patterns with exact string matches, not broad regex.

### Anti-Pattern: Relative Paths for JS-Loaded Assets

**DON'T:**

```javascript
var vQ = "gl";  // Relative — breaks on sub-pages
```

**DO:**

```javascript
var vQ = "/gl";  // Absolute — works from any page depth
```

### Anti-Pattern: Guessing Asset Filenames

**DON'T:** Assume `landonorris.css` or `main.js` based on site name.

**DO:** Extract actual URLs from the live DOM using `browser_evaluate` to query `<link>`, `<script>`, and `@font-face` sources.

---

## 12. Final File Structure

```
lando/                                    (~155 files, ~19MB total)
│
├── index.html                            Home page (233KB)
├── on-track.html                         F1 results page (433KB)
├── off-track.html                        Lifestyle page (204KB)
├── calendar.html                         F1 calendar (946KB)
├── privacy-policy.html                   Legal
├── terms-conditions.html                 Legal
│
├── on-track/index.html                   Clean URL routing copies
├── off-track/index.html
├── calendar/index.html
├── legal/privacy-policy/index.html
├── legal/terms-conditions/index.html
├── partnerships/index.html               Redirect to /
│
├── css/
│   ├── landonorris.css                   Main stylesheet (184KB)
│   └── landonorris-2.css                 Alternate hash variant (182KB)
│
├── fonts/
│   ├── MonaSans-Variable.woff2           Variable font (164KB)
│   └── Brier-Bold.woff2                  Display font (24KB)
│
├── js/
│   ├── custom-main.js                    OFF BRAND main (1.3MB)
│   ├── custom-main-pretty.js             Prettified version (2.0MB)
│   ├── lando-offbrand.js                 Variant JS (1.3MB)
│   ├── lando-by-offbrand.js              Variant JS (1.4MB)
│   ├── transitions-rive-isolate.js       Transition handler (104KB)
│   ├── jquery-3.5.1.min.js              jQuery (87KB)
│   ├── rive-canvas-lite.js              Rive runtime (197KB)
│   ├── webflow-chunk.js                 Webflow runtime (35KB)
│   └── webflow-main.js                  Webflow init (1KB)
│
├── rive/
│   ├── page-transition.riv              Page transition animation (5.5KB)
│   ├── signature.riv                    Signature animation (31KB)
│   ├── btn-ui.riv                       Button hover animation (4KB)
│   ├── circuits.riv                     Circuit map animation (37KB)
│   ├── ln4.riv                          LN4 logo animation (3.8KB)
│   ├── mob-landscape.riv               Mobile landscape (53KB)
│   ├── phrases.riv                      Text phrases animation (69KB)
│   ├── reef.riv                         Reef animation (73KB)
│   └── rive.wasm                        Rive WASM runtime (529KB)
│
├── gl/
│   ├── models/
│   │   ├── helmet-21.glb                Racing helmet (136KB)
│   │   ├── disco-02.glb                 Disco helmet (351KB)
│   │   ├── sotd.glb                     Site of the Day model (29KB)
│   │   └── tracks/
│   │       └── tracks-05.glb            F1 track model (453KB)
│   │
│   ├── hdri/
│   │   ├── studio_small_08_1k--light.hdr  Light env map (172KB)
│   │   ├── studio_small_08_1k--faded.hdr  Faded env map (378KB)
│   │   └── studio_small_08_1k--dark.hdr   Dark env map (383KB)
│   │
│   ├── textures/
│   │   ├── head/webp/                    Head PBR maps (6 files)
│   │   ├── helmet/webp/                  Helmet PBR + variants (9 files)
│   │   ├── glass/webp/                   Glass PBR maps (4 files)
│   │   ├── tracks/                       Track matcap (1 file)
│   │   ├── noise/                        Noise texture (1 file)
│   │   ├── not-found/webp/              404 page texture (1 file)
│   │   └── plastic/                      Plastic matcap (1 file)
│   │
│   ├── fonts/
│   │   ├── Brier-Bold-msdf.json         MSDF font data (90KB)
│   │   ├── Brier-Bold-02.webp           MSDF font atlas
│   │   ├── MonaSans-Bold-msdf.json      MSDF font data (5KB)
│   │   └── MonaSans-Bold-02.webp        MSDF font atlas
│   │
│   ├── draco/
│   │   ├── draco_decoder.js             Geometry decoder (719KB)
│   │   ├── draco_decoder.wasm           WASM decoder (286KB)
│   │   └── draco_wasm_wrapper.js        WASM wrapper (59KB)
│   │
│   └── basis/
│       ├── basis_transcoder.js          Texture transcoder (58KB)
│       └── basis_transcoder.wasm        WASM transcoder (527KB)
│
└── images/
    ├── webflow/                          SVG logos, masks (26 files)
    ├── helmets/                          Helmet gallery (32 WebPs)
    └── [photo WebPs]                     Gallery images (35+ files)
```

---

## 13. Lessons Learned

### 1. Reconnaissance Before Everything
Spend 30 minutes analyzing the site before downloading a single file. Identify CDN domains, referrer protection, JS frameworks, and custom patterns. This saves hours of debugging later.

### 2. The Base URL Variable Is King
On agency-built sites, 80% of asset loading bugs come from one thing: the JS base URL variable pointing to a CDN. Find it, replace it, and most assets will load.

### 3. DOM Capture Is Powerful But Messy
`document.documentElement.outerHTML` gives you the rendered page, but it also captures JS-generated elements (screen-reader clones, animation state, debug tools). Plan for post-processing cleanup.

### 4. Always Use Absolute Paths
Relative paths (`gl/`, `css/`) are a trap. They work for root-level pages but break on subdirectory routing. Always use absolute paths from root (`/gl/`, `/css/`).

### 5. Verify Every Downloaded File
A 32-byte file that says "Access denied" looks like a successful download. Always check file sizes and content. `wc -c` every file.

### 6. CSS Source Order Matters
A `<style>` block before a `<link>` tag loses to the linked stylesheet (same specificity, later wins). Match the original site's source order, or use `!important` for critical overrides.

### 7. Never Run Broad Regex on CSS
The single most destructive mistake was running `re.sub(r'[^{};\n]+\{\s*\}', '', style_content)` on Webflow embed blocks. Use surgical string replacements, never broad patterns.

### 8. The Live Site Is Your Backup
When local content is destroyed and git history isn't available, you can always re-fetch from the live site. Keep the original URLs documented.

### 9. Test on Subdirectory Pages
Most bugs only appear on `/on-track/` or deeper paths, not on the root `/`. Always test at least one sub-page after any URL rewriting.

### 10. Transitions Are the Last Mile
Page transitions involve CSS, JS, Rive, and timing. They're the hardest thing to get right because they depend on the full initialization chain completing successfully. Fix everything else first, then tackle transitions last.

---

## Appendix: Tool Chain Used

| Tool | Purpose |
|---|---|
| Playwright (MCP) | Browser automation, DOM capture, JS evaluation |
| curl | Asset downloading with custom headers |
| Python (inline scripts) | HTML parsing, regex processing, bulk file operations |
| Bash | File management, verification |
| VS Code | Error/warning identification |
| Live site (WebFetch/urllib) | CSS re-extraction when local content was destroyed |

---

*This document captures the complete process of cloning landonorris.com — a Webflow site with Three.js 3D rendering, Rive animations, GSAP scroll effects, and custom agency JavaScript. It is intended as the foundation for a reusable website-cloning skill.*
