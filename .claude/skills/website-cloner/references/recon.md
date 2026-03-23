# Phase 1: Reconnaissance

Spend time here before downloading anything. Understanding what you're dealing with saves hours of debugging later.

---

## Step 1: Technology Stack Detection

Navigate to the target site with Playwright and run this detection script via `browser_evaluate`. It tells you everything about the JS environment in one pass.

```javascript
() => ({
  // Page builders
  webflow: !!window.Webflow,
  wfDomain: document.documentElement.getAttribute('data-wf-domain'),
  wordpress: !!window.wp || document.body.classList.contains('wordpress'),
  squarespace: !!window.Squarespace,
  shopify: !!window.Shopify,

  // JS frameworks
  react: !!window.React || !!window.__REACT_DEVTOOLS_GLOBAL_HOOK__,
  nextjs: !!window.__NEXT_DATA__,
  nuxt: !!window.__NUXT__,
  vue: !!window.__VUE__ || !!window.__VUE_DEVTOOLS_GLOBAL_HOOK__,
  angular: !!window.ng || !!document.querySelector('[ng-version]'),
  svelte: !!window.__svelte,

  // Animation libraries
  gsap: !!window.gsap,
  gsapVersion: window.gsap?.version,
  scrollTrigger: !!window.ScrollTrigger,
  splitText: !!window.SplitText,
  lenis: !!window.lenis || !!window.Lenis,
  barba: !!window.barba,
  locomotive: !!window.LocomotiveScroll,

  // 3D / Graphics
  three: !!window.THREE,
  threeVersion: window.THREE?.REVISION,
  pixi: !!window.PIXI,
  babylon: !!window.BABYLON,

  // Rive
  rive: !!window.Rive,
  riveCanvases: document.querySelectorAll('canvas[data-rive-primary], canvas[data-rive-artboard]').length,

  // Other common libs
  jquery: !!window.jQuery,
  jqueryVersion: window.jQuery?.fn?.jquery,
  alpine: !!window.Alpine,

  // All external scripts loaded
  scripts: [...document.querySelectorAll('script[src]')].map(s => s.src),

  // All stylesheets
  stylesheets: [...document.querySelectorAll('link[rel="stylesheet"]')].map(l => l.href),

  // All font preloads
  fonts: [...document.querySelectorAll('link[rel="preload"][as="font"]')].map(l => l.href),

  // Images (first 20 to get CDN pattern)
  images: [...document.querySelectorAll('img[src]')].slice(0, 20).map(i => i.src),

  // Canvas elements (indicate 3D or animation)
  canvases: [...document.querySelectorAll('canvas')].map(c => ({
    id: c.id,
    class: c.className,
    attrs: [...c.attributes].map(a => `${a.name}="${a.value}"`).join(' ')
  })),
})
```

From this output, determine:
- Which frameworks are active → which reference files you may need
- Which script/stylesheet URLs are present → identifies CDN domains
- Whether Rive canvases exist → need .riv file discovery
- Whether 3D (Three.js, Babylon, PIXI) is active → need binary asset discovery

---

## Step 2: Identify CDN Domains and Referrer Protection

From the script and stylesheet URLs, extract all unique CDN domains. Build a table like this:

| Domain | Content type | Referrer required? |
|--------|-------------|-------------------|
| `cdn.prod.website-files.com` | Webflow CDN (CSS, fonts, images) | No |
| `*.cloudfront.net` | AWS CloudFront (varies) | Usually no |
| `unpkg.com`, `cdn.jsdelivr.net` | Public npm CDNs | No |
| `*.itsoffbrand.io`, `*.studioname.io` | Agency CDN | **Yes — always try Referer** |
| `d3e54v103j8qbb.cloudfront.net` | Webflow jQuery CDN | No |

**How to detect referrer protection:** Download one file from an unfamiliar CDN with and without a `Referer` header and compare file sizes:

```bash
# Without referrer
curl -sL "https://unknown-cdn.io/asset.js" -o /tmp/test-no-ref.js
wc -c /tmp/test-no-ref.js  # if < 100 bytes, referrer is required

# With referrer
curl -sL -H "Referer: https://targetsite.com/" "https://unknown-cdn.io/asset.js" -o /tmp/test-with-ref.js
wc -c /tmp/test-with-ref.js  # should be the real file size
```

The body of the denied response is usually something like `"Access denied - Invalid referrer"` — 32 bytes. Confirmed referrer-protected domains need `-H "Referer: https://targetsite.com/"` on every curl command for that domain.

---

## Step 3: Map All Pages and Routes

Find every URL on the site before downloading any of them.

**Method A: Check navigation links in DOM**

```javascript
() => [...new Set(
  [...document.querySelectorAll('a[href]')]
    .map(a => a.href)
    .filter(h => h.startsWith(window.location.origin))
    .map(h => new URL(h).pathname)
)].sort()
```

**Method B: Check sitemap.xml**

```
https://targetsite.com/sitemap.xml
https://targetsite.com/sitemap_index.xml
```

**Method C: Check robots.txt for hints**

```
https://targetsite.com/robots.txt
```

Build a route → filename mapping before starting HTML capture:

```
/                       → index.html
/about                  → about.html
/work                   → work.html
/work/project-name      → work/project-name.html  (note: nested)
/legal/privacy-policy   → privacy-policy.html
```

Nested routes (more than one level deep) require more careful path handling in Phase 7.

---

## Step 4: Identify Custom Framework Patterns

Inspect the DOM for data-attribute patterns that hint at framework-specific behavior you'll need to handle:

```javascript
() => ({
  // Page transitions (Taxi, Barba, custom)
  taxiViews: [...document.querySelectorAll('[data-taxi-view]')].length,
  barbaContainers: [...document.querySelectorAll('[data-barba]')].length,

  // Rive data-attribute bindings
  riveArtboards: [...document.querySelectorAll('[data-rive-artboard]')].map(el => el.getAttribute('data-rive-artboard')),
  riveStateMachines: [...document.querySelectorAll('[data-rive-state-machine]')].map(el => el.getAttribute('data-rive-state-machine')),

  // SplitText / text animation markers
  splitTextElements: document.querySelectorAll('[split-text]').length,
  screenReaderClones: document.querySelectorAll('[screen-reader]').length,

  // Navigation theming
  navTheme: document.querySelector('[data-nav-theme]')?.getAttribute('data-nav-theme'),

  // Custom animation attributes
  animElements: [...document.querySelectorAll('[data-anim]')].map(el => el.getAttribute('data-anim')),

  // Webflow-specific embed blocks (CSS in body)
  wEmbedBlocks: [...document.querySelectorAll('.w-embed')].map(el => el.className),
})
```

**What these tell you:**
- `data-taxi-view` / `data-barba` → page transition JS must be preserved carefully (see `references/routing.md`)
- `data-rive-artboard` → need the .riv binary and WASM runtime
- `[screen-reader]` elements → JS-generated accessibility clones that will cause duplicate text in DOM capture (fix in Phase 5)
- `.w-embed` blocks → CSS embedded in body divs, fragile to regex cleaning (handle in Phase 6)

---

## Reconnaissance Output

Before moving to Phase 2, document:

1. **Frameworks detected** (list from detection script)
2. **CDN domains** (table with referrer requirements)
3. **Page map** (routes → local filenames)
4. **Custom patterns** (split-text, Rive artboards, page transitions, etc.)
5. **Potential problem assets** (binary files: .glb, .riv, .wasm, .hdr)

This reconnaissance document becomes your guide for the rest of the cloning process.
