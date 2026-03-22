# Phase 7: Routing & Paths + Phase 8: Page Transitions

---

## Phase 7: Subdirectory Routing & Path Management

### Clean URL Routing with Static Files

The original site uses clean URLs (`/about`, `/work/project-name`) without `.html` extensions. A plain static file server needs `index.html` files in subdirectories to serve these:

```
/about         → about/index.html
/work          → work/index.html
/work/project  → work/project/index.html
/legal/privacy → legal/privacy/index.html
```

Create these from your flat `.html` files:

```bash
# Create directory and copy HTML file
mkdir -p about && cp about.html about/index.html
mkdir -p work && cp work.html work/index.html
mkdir -p legal/privacy && cp privacy.html legal/privacy/index.html

# For pages that should redirect (e.g., /partnerships → /)
mkdir -p partnerships
cat > partnerships/index.html << 'EOF'
<!DOCTYPE html>
<html>
<head><meta http-equiv="refresh" content="0;url=/"></head>
<body><a href="/">Redirecting...</a></body>
</html>
EOF
```

Or in Python for bulk creation:

```python
import os
import shutil

routes = [
    ('about.html',    'about/index.html'),
    ('work.html',     'work/index.html'),
    ('calendar.html', 'calendar/index.html'),
    ('privacy.html',  'legal/privacy/index.html'),
    ('terms.html',    'legal/terms/index.html'),
]

for src, dst in routes:
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)
    print(f"Created {dst}")
```

---

### The Path Depth Problem

This is why absolute paths are mandatory. With relative paths:

```
Root page (index.html):         css/main.css  → resolves to /css/main.css  ✓
Subdirectory (about/index.html): css/main.css → resolves to /about/css/main.css ✗ (404)
Deeper (legal/privacy/index.html): css/main.css → resolves to /legal/privacy/css/main.css ✗
```

With absolute paths:

```
Root page:                /css/main.css → /css/main.css  ✓
Subdirectory:             /css/main.css → /css/main.css  ✓
Deeper nested:            /css/main.css → /css/main.css  ✓
```

**Fix: Rewrite all relative references to absolute** in the subdirectory copies:

```python
import re
import os

def make_paths_absolute(content, depth=1):
    """Convert relative paths to absolute paths for subdirectory pages."""
    prefix = '../' * depth

    # Convert relative src/href to absolute
    content = re.sub(
        rf'(src|href)="{prefix}([^"]+)"',
        r'\1="/\2"',
        content
    )

    # Simpler: just ensure all asset references start with /
    # Replace common relative patterns
    for pattern in ['css/', 'js/', 'fonts/', 'images/', 'assets/', 'gl/', 'rive/']:
        content = content.replace(f'src="{pattern}', f'src="/{pattern}')
        content = content.replace(f'href="{pattern}', f'href="/{pattern}')

    return content

# For each subdirectory page, rewrite paths
for dst_path in ['about/index.html', 'work/index.html']:
    depth = dst_path.count('/') - 1  # how deep from root
    content = open(dst_path, 'r').read()
    content = make_paths_absolute(content, depth)
    open(dst_path, 'w').write(content)
```

**Better approach:** Start with absolute paths from the beginning (during URL rewriting in Phase 4) so subdirectory copies don't need adjustment.

---

### Font Preload Paths in Subdirectory Pages

`<link rel="preload">` for fonts in `<head>` uses the `href` attribute, which resolves relative to the HTML file's location:

```html
<!-- In about/index.html, this needs a path up one level: -->
<link rel="preload" href="../fonts/MonaSans-Variable.woff2" as="font" type="font/woff2" crossorigin>

<!-- Or just use absolute: -->
<link rel="preload" href="/fonts/MonaSans-Variable.woff2" as="font" type="font/woff2" crossorigin>
```

Absolute paths are preferred here too.

---

### Internal Navigation Links

Update `<a href>` links that reference other pages using the original clean URL format:

```python
# /about → /about (works as-is with subdirectory routing)
# about.html → /about (needs fixing)
content = re.sub(r'href="([a-z-]+)\.html"', r'href="/\1"', content)
content = re.sub(r'href="([a-z-]+)/([a-z-]+)\.html"', r'href="/\1/\2"', content)
```

---

## Phase 8: Page Transition Restoration

Sites with animated page transitions (Rive, GSAP, Barba.js, Taxi.js) require special handling. The transition overlay must be visible during the loading phase and then hidden by JS.

### How Page Transitions Typically Work

```
1. Page loads → transition overlay is VISIBLE (covers the page)
2. JS initializes → transition animation plays (e.g., "transition-in" wipes away)
3. User navigates → transition animation plays in reverse ("transition-out")
4. New page loads → cycle repeats
```

### The CSS Specificity Problem for Transitions

The main stylesheet typically sets the transition overlay to hidden by default:

```css
/* In main.css, line 6620: */
.transition-overlay { display: none; }
```

The site's custom CSS (injected `<style>` block, placed after the `<link>` in the original site) overrides this:

```css
.transition-overlay { display: flex; }  /* needs to be visible on load */
```

In your clone, if the injected `<style>` lands before the `<link>` tag, the main CSS wins and the overlay stays hidden — the transition never shows. The JS's ability to **hide** the overlay uses `visibility: hidden` (not `display: none`), so it doesn't conflict.

**Fix:** Ensure the transition override uses `!important` and is placed after the main CSS link:

```html
<head>
  <link rel="stylesheet" href="/css/main.css">
  <!-- This must come AFTER the <link>, or use !important -->
  <style>
    .transition-overlay { display: flex !important; }
  </style>
</head>
```

### Rive-Based Transitions

If the site uses Rive for transitions, you need:
1. The `.riv` binary file (downloaded in Phase 3)
2. The Rive JS runtime (the `.js` file referenced in HTML)
3. The Rive WASM file (`rive.wasm`) — often loaded from the same directory as the runtime
4. A `<canvas>` element with the correct data attributes
5. The JS initialization function (part of the site's main JS bundle)

The transition JS typically looks for a canvas with specific data attributes:

```html
<canvas data-rive-primary=""
        data-rive-artboard="page-transition"
        data-rive-state-machine="page-transition"></canvas>
```

If the canvas element is missing from your DOM capture, check: the transition overlay div may be injected by JS on the first page load and captured in the DOM, but subsequent pages may not have it. Copy the full transition HTML from index.html into all page files.

### Typical Transition Lifecycle (JS perspective)

```
allriveloaded event fired
  → initPageModules()
  → hideTransition()       ← triggers "transition-in" animation
    → 100ms: button fades
    → 500ms: overlay.style.visibility = "hidden"

user clicks link
  → showTransition()       ← triggers "transition-out" animation
    → overlay becomes visible
    → animation plays
    → navigate to new page
```

### Debugging Transition Issues

If the overlay stays stuck (lime/colored screen covering everything):
1. Check: is `.transition-overlay { display: flex }` being overridden by the main CSS? → Add `!important`
2. Check: is the Rive WASM loading? Check Network tab for `rive.wasm` (should be 200, not 404)
3. Check: is the JS initialization running? Check Console for errors
4. Check: is `allriveloaded` firing? The transition hide is often gated on all Rive files loading

If the overlay is invisible (no transition at all):
1. Check: is `display: flex !important` in a `<style>` after the `<link>`?
2. Check: is the `.riv` file present and > 1KB?

### Non-Rive Transitions (CSS + GSAP)

If transitions use pure CSS/GSAP:

```javascript
// Common pattern: a full-screen overlay div toggled by JS
gsap.to('.page-transition', { opacity: 1, duration: 0.3, onComplete: navigateTo });
gsap.to('.page-transition', { opacity: 0, duration: 0.3, delay: 0.5 });
```

These usually work without special handling if the JS is intact and paths are correct. The most common issue is the overlay CSS (same specificity problem above).

---

## Serving the Clone Locally

```bash
cd clone/
python -m http.server 8080
# or
npx serve .
# or
npx http-server . -p 8080
```

Always test:
1. Root page: `http://localhost:8080/`
2. A subdirectory page: `http://localhost:8080/about/`
3. A nested page: `http://localhost:8080/legal/privacy/`
4. Navigation between pages (if page transitions exist)
