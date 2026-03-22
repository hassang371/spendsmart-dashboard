# Phase 4: URL Rewriting

Replace every remote CDN/origin URL with local absolute paths. Do this systematically — start with JS (the base variable), then HTML, then CSS.

---

## Step 1: Rewrite JS Base URL Variables (Most Important)

Don't try to replace individual asset URLs in JS. Change the base variable assignment and every asset path downstream updates automatically:

```python
content = open('js/main.js', 'r').read()

# Replace CDN base with local absolute path
content = content.replace(
    'var vQ="https://cdn.example.com/assets"',
    'var vQ="/assets"'
)

# Also replace any separate Rive base path
content = content.replace(
    'var mj="https://cdn.example.com/rive/"',
    'var mj="/rive/"'
)

open('js/main.js', 'w').write(content)
```

**Always use absolute paths starting with `/`** — not relative paths like `assets` or `../assets`. Relative paths break on subdirectory pages. See `references/routing.md` for why.

If you have multiple JS files with different variable names and different CDN domains, rewrite each one:

```python
rewrites = [
    ('js/main.js',       'var vQ="https://cdn1.example.com/gl"',      'var vQ="/gl"'),
    ('js/alternate.js',  'var dQ="https://cdn1.example.com/gl"',      'var dQ="/gl"'),
    ('js/third.js',      'var Z8="https://cdn2.example.com/prod/gl"', 'var Z8="/gl"'),
]

for filepath, old, new in rewrites:
    content = open(filepath, 'r').read()
    if old in content:
        content = content.replace(old, new)
        open(filepath, 'w').write(content)
        print(f"Rewrote {filepath}")
    else:
        print(f"WARNING: pattern not found in {filepath}: {old[:60]}")
```

---

## Step 2: Rewrite HTML Script and Stylesheet References

Replace CDN URLs in `<script src>` and `<link href>` tags with local paths:

```python
import re

content = open('index.html', 'r').read()

# External JS → local
content = re.sub(
    r'src="https://cdn\.example\.com/js/[^"]*\.js"',
    'src="/js/main.js"',
    content
)

# jQuery or other known libraries → local copy
content = re.sub(
    r'src="https://[^"]*jquery[^"]*\.js"',
    'src="/js/jquery.min.js"',
    content
)

# External CSS → local
content = re.sub(
    r'href="https://cdn\.example\.com/[^"]*\.css"',
    'href="/css/main.css"',
    content
)

open('index.html', 'w').write(content)
```

For sites with multiple pages, apply to all HTML files:

```python
import os

for fname in os.listdir('.'):
    if fname.endswith('.html'):
        content = open(fname, 'r').read()
        # apply rewrites
        open(fname, 'w').write(content)
```

---

## Step 3: Rewrite Font Preload Links

Font preload `<link>` tags in `<head>` need their `href` updated:

```python
content = re.sub(
    r'href="https://cdn\.example\.com/[^"]*MonaSans[^"]*\.woff2"',
    'href="/fonts/MonaSans-Variable.woff2"',
    content
)
content = re.sub(
    r'href="https://cdn\.example\.com/[^"]*([A-Za-z-]+)\.woff2"',
    lambda m: f'href="/fonts/{m.group(1)}.woff2"',
    content
)
```

---

## Step 4: Remove SRI Integrity Hashes

If you modified any file (which you did — changing URL variables), the Subresource Integrity hash will no longer match and the browser will refuse to load it:

```python
# Remove integrity attributes
content = re.sub(r'\s+integrity="sha(256|384|512)-[^"]+"', '', content)

# Remove crossorigin attributes that accompany integrity checks
content = re.sub(r'\s+crossorigin="anonymous"', '', content)
```

Apply this to all HTML files.

---

## Step 5: Remove Webflow / Page Builder Metadata (Optional)

Webflow embeds domain-specific attributes that may cause issues or unnecessary network requests:

```python
# Remove Webflow beacon
content = re.sub(r'<script[^>]*webflow\.com[^>]*>.*?</script>', '', content, flags=re.DOTALL)
content = re.sub(r'<script[^>]*webflow\.com[^>]*></script>', '', content)

# Remove data-wf-* attributes (Webflow tracking)
content = re.sub(r'\s+data-wf-[a-z-]+="[^"]*"', '', content)
```

---

## Step 6: Remove Dev Artifact References

```python
# Remove dev server hot-reload references (captured when dev server was running)
content = re.sub(r'<script[^>]*(?:localhost|127\.0\.0\.1)[^>]*></script>', '', content)
content = re.sub(r'<script[^>]*(?:localhost|127\.0\.0\.1)[^>]*>.*?</script>', '', content, flags=re.DOTALL)

# Remove dat.gui debug panels (common in Three.js dev environments)
content = re.sub(r'<div class="dg[^"]*"[^>]*>.*?</div>', '', content, flags=re.DOTALL)
```

---

## Step 7: Rewrite CSS `url()` References

The main CSS file likely references fonts via relative paths (which should still work), but any absolute CDN references need updating:

```python
css = open('css/main.css', 'r').read()

# Replace any absolute CDN URLs in url() with local paths
css = re.sub(
    r'url\(["\']?https://cdn\.example\.com/fonts/([^"\')\s]+)["\']?\)',
    lambda m: f'url("../fonts/{m.group(1)}")',
    css
)

open('css/main.css', 'w').write(css)
```

Note: CSS `@font-face` `url()` paths are relative to the CSS file location, not the HTML file. If your CSS is at `/css/main.css`, then `../fonts/` correctly resolves to `/fonts/`.

---

## Verification After URL Rewriting

Search for any remaining remote URLs to make sure nothing was missed:

```bash
# Check all HTML files for remaining external asset URLs
grep -rn "https://" *.html | grep -v '<!-- ' | grep -E '\.(js|css|woff2|glb|riv|wasm|jpg|png|webp|svg)' | head -30

# Check JS files for remaining CDN references
grep -n "https://" js/main.js | grep -v "//\s" | head -20
```

Any remaining remote URLs that should be local are download gaps from Phase 3. Either download the missing file and update the reference, or note it as a known gap.
