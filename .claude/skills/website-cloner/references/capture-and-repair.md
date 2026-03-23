# Phase 2: HTML Capture + Phase 5: Corruption Repair

These two phases are documented together because the corruption introduced in Phase 2 is repaired in Phase 5.

---

## Phase 2: HTML Capture

### The Capture Pattern

For each page, navigate with Playwright and wait for full JS execution before capturing:

```javascript
// Step 1: Navigate and wait for network idle
// Use mcp__playwright__browser_navigate with the page URL

// Step 2: Give JS time to finish (animations, data fetches, deferred init)
// Use mcp__playwright__browser_wait_for with state: "networkidle"
// or add a small pause if the site has deferred initialization

// Step 3: Capture the fully-rendered DOM
// Use mcp__playwright__browser_evaluate with:
() => document.documentElement.outerHTML
```

This gives you the **rendered DOM**, which includes:
- All JS-generated elements (SplitText character wrappers, accessibility clones, GSAP inline styles)
- Webflow's dynamically-applied class states
- Rive canvas elements with their data attributes resolved
- Any lazy-loaded content that JS has already triggered

### What to Save

Save each page's HTML to your local folder structure immediately after capture:

```
clone/
├── index.html          ← from /
├── about.html          ← from /about
├── work.html           ← from /work
├── privacy.html        ← from /legal/privacy-policy
```

Use flat filenames for now. You'll create the subdirectory routing structure in Phase 7.

### Per-Page Capture Checklist

For each page:
1. Navigate to the page URL
2. Wait for `networkidle` state
3. Evaluate `() => document.documentElement.outerHTML`
4. Save the raw output to a .html file
5. Note the file size (should be > 50KB for most real pages)

---

## Phase 5: HTML Corruption Repair

The Playwright capture pipeline introduces several predictable corruption patterns. Apply all 7 fixes to every captured HTML file.

### Fix 1: JSON Wrapper Artifacts

The Playwright MCP returns results through a JSON serialization pipeline. Sometimes the HTML gets wrapped with debug markers:

```
### Result
"<!DOCTYPE html>..."
"
```

**Fix:**

```python
import re

content = open('index.html', 'r').read()

# Strip leading JSON wrapper (keeps everything from <!DOCTYPE or <html onward)
if '### Result' in content[:200]:
    content = re.sub(r'^.*?(?=<!DOCTYPE|<html)', '', content, flags=re.DOTALL)

# Strip anything after </html>
match = re.search(r'</html>', content, re.IGNORECASE)
if match:
    content = content[:match.end()]
```

### Fix 2: Escaped Quotes

JSON string encoding turns every `"` inside the HTML into `\"`:

```python
content = content.replace('\\"', '"')
```

Apply this after Fix 1 (order matters — stripping the wrapper first means fewer escapes to process).

### Fix 3: Literal `\t` Sequences in CSS

Tab characters inside `<style>` blocks get JSON-encoded as literal two-character `\t` sequences. This creates invalid CSS properties like `\tdisplay: flex` and `\tpadding: 0`:

```python
# Generic fix: replace \t before any lowercase letter (CSS property names start lowercase)
content = re.sub(r'\\t([a-z-])', r'\1', content)

# Targeted fixes for common cases (use if generic isn't enough):
content = content.replace('\\tdisplay', 'display')
content = content.replace('\\tpadding', 'padding')
content = content.replace('\\tmargin', 'margin')
content = content.replace('\\tposition', 'position')
content = content.replace('\\tbackground', 'background')
content = content.replace('\\ttransform', 'transform')
content = content.replace('\\tcolor', 'color')
```

### Fix 4: Playwright Debug Text After `</html>`

Every captured file may have Playwright status text appended after `</html>`:

```
</html>

### Ran Playwright code
### Open tabs: ...
Console output: ...
```

This is already handled by Fix 1 (truncating at `</html>`), but double-check by reading the last 200 characters of each file.

### Fix 5: Screen-Reader Accessibility Clones

Many sites use JS to generate hidden accessibility clones of animated text elements. Playwright captures both the original and the clone, producing doubled visible text:

```html
<!-- Original element (animated) -->
<div split-text="chars" class="heading">Hello World</div>
<!-- JS-generated clone (should be visually hidden) -->
<div screen-reader="">Hello World</div>
```

**Fix A — Inject CSS (recommended, preserves accessibility intent):**

```python
sr_css = '''<style>
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
</style>'''

# Inject before </head>
content = content.replace('</head>', sr_css + '\n</head>')
```

**Fix B — Remove elements (optional, reduces file size):**

```python
# Only use if you don't care about screen reader accessibility
content = re.sub(r'<[a-z]+[^>]*\sscreen-reader=""[^>]*>.*?</[a-z]+>', '', content, flags=re.DOTALL)
```

### Fix 6: Broken `</@media` Tags

DOM capture can corrupt `@media` queries inside `<style>` blocks, producing `</@media` as a closing tag:

```python
content = content.replace('</@media', '@media')
```

### Fix 7: Development Tool Artifacts

DOM capture includes whatever the browser had loaded at the time, including dev server scripts and debug panels:

```python
# Remove dev server hot-reload scripts (localhost references)
content = re.sub(r'<script[^>]*(?:localhost|127\.0\.0\.1)[^>]*></script>', '', content)
content = re.sub(r'<script[^>]*(?:localhost|127\.0\.0\.1)[^>]*>.*?</script>', '', content, flags=re.DOTALL)

# Remove Webflow/dat.gui debug panels
content = re.sub(r'<div class="dg[^"]*"[^>]*>.*?</div>', '', content, flags=re.DOTALL)

# Remove Webflow badge
# (Better handled via CSS: .w-webflow-badge { display: none !important; })
```

---

## Applying All Fixes

Put all fixes in a single Python script and run it over every HTML file:

```python
import re
import os

def repair_html(content):
    # Fix 1: Strip JSON wrapper artifacts
    if '### Result' in content[:200]:
        content = re.sub(r'^.*?(?=<!DOCTYPE|<html)', '', content, flags=re.DOTALL)
    match = re.search(r'</html>', content, re.IGNORECASE)
    if match:
        content = content[:match.end()]

    # Fix 2: Unescape quotes
    content = content.replace('\\"', '"')

    # Fix 3: Literal \t sequences in CSS
    content = re.sub(r'\\t([a-z-])', r'\1', content)

    # Fix 5: Screen-reader CSS injection
    if 'screen-reader' in content and '[screen-reader]' not in content:
        sr_css = '<style>[screen-reader]{position:absolute!important;width:1px!important;height:1px!important;overflow:hidden!important;clip:rect(0,0,0,0)!important;white-space:nowrap!important;border:0!important;margin:-1px!important;}</style>'
        content = content.replace('</head>', sr_css + '\n</head>')

    # Fix 6: Broken @media tags
    content = content.replace('</@media', '@media')

    # Fix 7: Dev tool artifacts
    content = re.sub(r'<script[^>]*(?:localhost|127\.0\.0\.1)[^>]*></script>', '', content)

    return content

html_files = [f for f in os.listdir('.') if f.endswith('.html')]
for fname in html_files:
    content = open(fname, 'r', encoding='utf-8').read()
    content = repair_html(content)
    open(fname, 'w', encoding='utf-8').write(content)
    print(f"Repaired: {fname} ({len(content)} chars)")
```

Run this script from your clone directory after capturing all pages.
