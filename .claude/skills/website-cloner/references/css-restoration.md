# Phase 6: CSS Restoration

This phase addresses a pattern that affects Webflow sites and many other page builders: CSS that lives inside `<div>` elements in `<body>`, not in `<head>` stylesheets. If anything destroyed this CSS during processing, this phase recovers it.

---

## The w-embed Pattern

In Webflow and similar tools, custom CSS is injected as "embed" blocks — `<div>` elements inside `<body>` containing inline `<style>` tags:

```html
<body>
  <!-- Regular content -->
  <div class="css-root w-embed">
    <style>
      :root {
        --color-primary: #ff6b00;
        --spacing-lg: 2rem;
        /* ... all CSS custom properties ... */
      }
    </style>
  </div>
  <div class="css-nav w-embed">
    <style>
      /* Navigation theming, brand colors */
      [data-nav-theme="dark"] { ... }
    </style>
  </div>
  <!-- ... more embed blocks ... -->
  <!-- Then the actual page content -->
</body>
```

A site might have 10–20 such blocks covering: root CSS variables, utility classes, animation styles, navigation theming, page-specific layouts, responsive breakpoints, and browser-specific fixes.

**Why this matters:** Any regex cleaning that touches `<style>` content, or any DOM manipulation that strips "empty-looking" elements, will silently destroy all of this CSS. The page will appear completely unstyled.

---

## How to Detect Destroyed CSS Blocks

If your page looks unstyled or wrong, check for empty w-embed blocks:

```python
import re

content = open('index.html', 'r').read()

# Find all w-embed divs
embed_blocks = re.findall(r'<div class="([^"]+w-embed[^"]*)">(.*?)</div>', content, re.DOTALL)

print(f"Found {len(embed_blocks)} embed blocks:")
for cls, inner in embed_blocks:
    style_content = re.findall(r'<style>(.*?)</style>', inner, re.DOTALL)
    css_chars = sum(len(s) for s in style_content)
    print(f"  {cls}: {css_chars} chars of CSS {'(EMPTY - DESTROYED)' if css_chars == 0 else ''}")
```

Empty w-embed blocks indicate destroyed CSS. Proceed to recovery below.

---

## The Destructive Pattern to Never Use

The single most common way to destroy w-embed CSS:

```python
# NEVER DO THIS — it matches and destroys minified CSS rules
re.sub(r'[^{};\n]+\{\s*\}', '', style_content)

# ALSO AVOID — too broad for minified CSS
re.sub(r'\s+', ' ', style_block)  # can collapse meaningful whitespace
```

Minified CSS has patterns that look like "empty rules" but contain valid content. There is no safe broad regex for CSS cleaning. If you must clean, target only specific known-broken patterns with exact string matches.

---

## Recovery: Re-fetch CSS from the Live Site

When local CSS blocks are empty and the originals can't be recovered, fetch them from the live site using Python's standard library (no dependencies):

```python
import urllib.request
import re

TARGET = 'https://targetsite.com'
pages_to_fetch = [TARGET + '/', TARGET + '/about', TARGET + '/work']

all_css = {}

for url in pages_to_fetch:
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Referer': TARGET + '/',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    })
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        html = resp.read().decode('utf-8')

        # Extract all w-embed CSS blocks
        # Pattern: <div class="css-NAME w-embed"><style>CONTENT</style></div>
        pattern = r'<div class="(css-[a-z-]+) w-embed"><style>(.*?)</style></div>'
        for cls, css in re.findall(pattern, html, re.DOTALL):
            # Keep the longest version of each block (some pages have more CSS than others)
            if cls not in all_css or len(css) > len(all_css[cls]):
                all_css[cls] = css

        print(f"Fetched from {url}: found {len(re.findall(pattern, html, re.DOTALL))} blocks")
    except Exception as e:
        print(f"Error fetching {url}: {e}")

print(f"\nTotal CSS blocks found: {len(all_css)}")
for cls, css in all_css.items():
    print(f"  {cls}: {len(css)} chars")
```

---

## Restoring the CSS Into Local HTML Files

Once you have the CSS content, inject it back into the empty blocks:

```python
import os

html_files = [f for f in os.listdir('.') if f.endswith('.html')]

for html_file in html_files:
    content = open(html_file, 'r').read()
    restored = 0

    for css_class, css_content in all_css.items():
        # Match the empty block
        empty_pattern = f'<div class="{css_class} w-embed"></div>'
        full_block = f'<div class="{css_class} w-embed"><style>{css_content}</style></div>'

        if empty_pattern in content:
            content = content.replace(empty_pattern, full_block)
            restored += 1

    open(html_file, 'w').write(content)
    print(f"{html_file}: restored {restored} CSS blocks")
```

---

## CSS Specificity Issues

After restoration, you may have styling conflicts. The most common case:

### Injected `<style>` Before `<link>` Loses

If you need a style to override the main linked stylesheet, source order matters. A `<style>` block placed before the `<link>` tag has lower priority than the stylesheet (same specificity, later source wins):

```html
<!-- This loses to the linked CSS: -->
<head>
  <style>.transition-w { display: flex; }</style>
  <link rel="stylesheet" href="/css/main.css">  <!-- wins -->
</head>

<!-- This wins: -->
<head>
  <link rel="stylesheet" href="/css/main.css">
  <style>.transition-w { display: flex; }</style>  <!-- wins -->
</head>
```

**Fix option A:** Move injected `<style>` after the `<link>` tag.

**Fix option B:** Use `!important` for critical overrides when you can't control position:

```css
.transition-w { display: flex !important; }
```

### Webflow Badge

Add this to hide the Webflow badge that appears on cloned Webflow sites:

```css
.w-webflow-badge { display: none !important; }
```

---

## CSS File Scope

If the site uses a CSS file (not just w-embed blocks), also check:

1. Does the CSS file reference fonts via relative paths? `../fonts/font.woff2` is relative to the CSS file location, not the HTML file — this is usually correct.
2. Does the CSS file have any `@import` rules pointing to CDN sources? Those need to be downloaded and the imports updated to local paths.
3. Is there a source map reference at the bottom? (`/*# sourceMappingURL=...`)  You can remove this line — source maps aren't needed for the clone.
