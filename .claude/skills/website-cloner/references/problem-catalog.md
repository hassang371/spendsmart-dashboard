# Problem Catalog

A reference for debugging unexpected issues during cloning. Problems are organized by category with symptom → root cause → solution.

---

## Category 1: CDN & Network

### P-01 — Referrer Protection (Silent Access Denial)
**Symptom:** Downloaded files are tiny (< 100 bytes). Assets show as broken in browser. Running `head -c 50 file.glb` shows `"Access denied - Invalid referrer"`.
**Root cause:** The CDN requires a `Referer` header matching the target site's origin. Without it, it returns a denial string instead of the actual file.
**Solution:** Add `-H "Referer: https://targetsite.com/"` to every curl command for that domain. Also add a `User-Agent` header to avoid bot blocking.

### P-02 — Wrong Asset URLs (Guessed Filenames)
**Symptom:** 404s for CSS/JS files. Assets have names that don't match what you expected (e.g., looking for `main.css` but file is `landonorris.webflow.css`).
**Root cause:** Guessing filenames based on site name or convention instead of extracting actual URLs from the DOM.
**Solution:** Use `browser_evaluate` to query the live DOM for actual URLs: `[...document.querySelectorAll('link[rel="stylesheet"]')].map(l => l.href)`

### P-03 — Dynamic URL Construction (JS Variables)
**Symptom:** Some assets still loading from CDN after URL rewriting. Certain file types (GLB, WASM, HDR) 404 locally.
**Root cause:** Asset URLs built from minified JS base variables (`var vQ = "https://cdn..."`) — the full URL never appears in source.
**Solution:** Search JS files for CDN domain, find the variable assignment, replace it with the local absolute path. See `asset-discovery.md`.

### P-04 — Multiple CDN Domains
**Symptom:** Some assets load, others still 403. Different file types fail from different domains.
**Root cause:** Different JS files use different base URL variables pointing to different CDN domains.
**Solution:** Check ALL JS files for CDN references. Each may have its own variable name and domain.

### P-05 — CORS Errors for Local Assets
**Symptom:** Browser console shows CORS errors for assets you've downloaded locally.
**Root cause:** Serving files from the filesystem (`file:///`) rather than a local HTTP server.
**Solution:** Always serve with a local HTTP server: `python -m http.server 8080`

---

## Category 2: HTML Corruption

### P-06 — JSON Wrapper Artifacts
**Symptom:** HTML file starts with `### Result` or `"<!DOCTYPE` (with leading quote). Page doesn't parse correctly.
**Root cause:** Playwright MCP JSON serialization wraps the result in debug markers.
**Solution:** Strip prefix with `re.sub(r'^.*?(?=<!DOCTYPE|<html)', '', content, flags=re.DOTALL)`, then truncate at `</html>`.

### P-07 — Escaped Quotes Throughout HTML
**Symptom:** HTML attributes contain `\"` instead of `"`. Styles and scripts may be malformed.
**Root cause:** JSON string encoding inside the Playwright pipeline.
**Solution:** `content = content.replace('\\"', '"')`

### P-08 — Literal `\t` Sequences in CSS
**Symptom:** Browser shows CSS errors. Properties like `display: flex` broken as `\tdisplay: flex`. Page looks unstyled in specific sections.
**Root cause:** Tab characters in `<style>` blocks get JSON-encoded as literal `\t` two-character sequences.
**Solution:** `re.sub(r'\\t([a-z-])', r'\1', content)` — or the specific targeted replacements in `capture-and-repair.md`.

### P-09 — Debug Text Appended After `</html>`
**Symptom:** Raw text appears at the bottom of the page. Contains "Ran Playwright code", tab names, console output.
**Root cause:** Playwright MCP appends status output after returning the HTML string.
**Solution:** Truncate content at the end of `</html>`: `content = content[:re.search(r'</html>', content).end()]`

### P-10 — Broken `</@media` Tags
**Symptom:** CSS parse error. `@media` queries not applying. Browser console shows unexpected token errors.
**Root cause:** DOM serialization corrupts `@media` rules inside `<style>` blocks.
**Solution:** `content = content.replace('</@media', '@media')`

### P-11 — Doubled `<style>` Tags
**Symptom:** Empty nested style tags: `<style><style></style>`. CSS doesn't apply.
**Root cause:** Aggressive regex cleaning that moved content out of style tags but left both tags.
**Solution:** `re.sub(r'<style>\s*<style>', '<style>', content)` — and audit your cleaning regexes.

---

## Category 3: CSS

### P-12 — Empty w-embed CSS Divs (Destroyed CSS)
**Symptom:** Page is completely unstyled. CSS variables undefined. All custom styling gone. Running the block inventory shows `0 chars` for all CSS blocks.
**Root cause:** A broad regex cleaning operation matched and emptied `<div class="css-* w-embed">` blocks containing critical inline CSS.
**Solution:** Re-fetch CSS blocks from the live site. See `css-restoration.md` for the full recovery script.

### P-13 — CSS Specificity Override Failure
**Symptom:** An injected `<style>` override doesn't take effect. The linked stylesheet's rule wins.
**Root cause:** A `<style>` block placed before a `<link>` stylesheet loses on specificity tie (later source wins).
**Solution:** Move injected `<style>` after the `<link>` tag, or add `!important` to the override rule.

### P-14 — SRI Hash Mismatch
**Symptom:** Browser refuses to load CSS or JS files. Console shows `Failed to find a valid digest in the 'integrity' attribute for resource`.
**Root cause:** You modified the file (changed URLs) but the original SRI hash still validates against the unmodified original.
**Solution:** Remove all `integrity="sha*"` and `crossorigin="anonymous"` attributes from `<link>` and `<script>` tags.

### P-15 — CSS Source Map Reference
**Symptom:** Browser makes requests for a `.css.map` file that doesn't exist locally.
**Root cause:** CSS file ends with `/*# sourceMappingURL=main.css.map */` — the source map file wasn't downloaded.
**Solution:** Remove the last line from the CSS file, or download the source map too.

---

## Category 4: DOM & JavaScript

### P-16 — Screen-Reader Duplicate Text
**Symptom:** All text on the page appears twice. Headings, navigation, body text all doubled.
**Root cause:** JS-generated accessibility clones (elements with `screen-reader=""` attribute) were captured in the DOM snapshot. No CSS hides them.
**Solution:** Inject hiding CSS for `[screen-reader]`. See `capture-and-repair.md`.

### P-17 — Transition Overlay Stuck (Colored Screen)
**Symptom:** A solid-color (lime, black, white) overlay covers the entire page. The site is beneath it but inaccessible.
**Root cause:** The transition overlay `display: flex !important` override is being defeated by the main stylesheet (CSS source order issue), or the JS initialization chain isn't completing.
**Solution:** Add `!important` to the transition overlay's `display: flex` rule. Check console for JS errors. Check that `.riv` file and WASM are loading.

### P-18 — `require is not defined` Error
**Symptom:** Console error: `ReferenceError: require is not defined`. Script fails to run.
**Root cause:** Trying to run Node.js code (using CommonJS `require()`) in the browser context via `browser_evaluate`. Only browser APIs are available there.
**Solution:** Use `browser_evaluate` for browser JS only. Run Node.js/Python scripts via Bash for server-side processing.

### P-19 — Dev Server References in DOM
**Symptom:** 404 requests in console for `localhost:PORT/some-script.js`. Hot-reload script loaded when dev server was running.
**Root cause:** Site was captured while a development server was running — dev scripts appear in the DOM.
**Solution:** Remove localhost script tags: `re.sub(r'<script[^>]*(?:localhost|127\.0\.0\.1)[^>]*></script>', '', content)`

### P-20 — Rive Canvas Not Rendering
**Symptom:** Blank canvas where Rive animation should be. No errors in console.
**Root cause:** One or more of the three required Rive components is missing: (a) the `.riv` binary file, (b) the Rive WASM runtime, or (c) the JS initialization code.
**Solution:** Verify all three: the `.riv` file exists and is > 1KB, the `rive.wasm` is present, and the canvas element has the correct `data-rive-artboard` and `data-rive-state-machine` attributes.

---

## Category 5: Paths & Routing

### P-21 — Assets 404 on Subdirectory Pages Only
**Symptom:** Root page (`/`) works fine. Subdirectory pages (`/about/`) show 404s for CSS, JS, fonts.
**Root cause:** Relative paths like `css/main.css` resolve correctly from root but incorrectly from subdirectories.
**Solution:** Use absolute paths everywhere: `/css/main.css`, `/js/main.js`, `/fonts/font.woff2`.

### P-22 — Font Preload Path Mismatch
**Symptom:** Console warning about unused preload for fonts on subdirectory pages. Fonts flash/FOUT.
**Root cause:** `<link rel="preload" href="../fonts/font.woff2">` path is correct for one depth level but wrong for pages nested deeper.
**Solution:** Switch font preload hrefs to absolute paths: `href="/fonts/font.woff2"`.

### P-23 — Navigation Links Break (`.html` extensions)
**Symptom:** Clicking navigation links goes to `about.html` (404 with your static server setup expecting clean URLs).
**Root cause:** Captured DOM contains `href="about.html"` instead of `href="/about"`.
**Solution:** Rewrite: `re.sub(r'href="([a-z-]+)\.html"', r'href="/\1"', content)`.
