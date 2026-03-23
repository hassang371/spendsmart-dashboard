# Phase 3: Asset Discovery & Download

The goal of this phase is to find and download every asset the site needs — including those whose URLs are never written out in full anywhere in the source code.

---

## Step 1: Extract Explicit Asset URLs from HTML

Start with what's directly visible in the captured HTML:

```python
import re

html = open('index.html', 'r').read()

# CSS stylesheets
css_urls = re.findall(r'<link[^>]*rel=["\']stylesheet["\'][^>]*href=["\']([^"\']+)["\']', html)
css_urls += re.findall(r'<link[^>]*href=["\']([^"\']+)["\'][^>]*rel=["\']stylesheet["\']', html)

# Scripts
js_urls = re.findall(r'<script[^>]*src=["\']([^"\']+)["\']', html)

# Font preloads
font_urls = re.findall(r'<link[^>]*rel=["\']preload["\'][^>]*as=["\']font["\'][^>]*href=["\']([^"\']+)["\']', html)
font_urls += re.findall(r'<link[^>]*href=["\']([^"\']+)["\'][^>]*as=["\']font["\']', html)

# Images (src and srcset)
img_srcs = re.findall(r'<img[^>]*src=["\']([^"\']+)["\']', html)
srcset_urls = re.findall(r'srcset=["\']([^"\']+)["\']', html)
# srcset values are comma-separated "url descriptor" pairs
for srcset in srcset_urls:
    for part in srcset.split(','):
        url = part.strip().split()[0]
        if url.startswith('http'):
            img_srcs.append(url)

# All URLs (deduplicated)
all_urls = list(set(css_urls + js_urls + font_urls + img_srcs))
print(f"Found {len(all_urls)} explicit asset URLs")
```

---

## Step 2: The Critical Step — Analyze JS for Base URL Variables

This is the most important and most missed step. Modern sites construct asset URLs dynamically:

```javascript
var vQ = "https://cdn.example.com/assets"; // the only thing that appears in source
// ...2000 lines of minified code...
model: vQ + "/models/hero.glb",
texture: vQ + `/textures/${format}/diffuse.${format}`,
```

The full URL `https://cdn.example.com/assets/models/hero.glb` **never appears anywhere**. You must find the base variable, then trace all concatenations from it.

### Finding the Base Variable

```python
content = open('js/main.js', 'r').read()

# Find all CDN domain references — these will be the base variable assignments
for m in re.finditer(r'var\s+\w+\s*=\s*["\']https?://[^"\']+["\']', content):
    print(f"pos {m.start()}: {m.group()}")
```

You're looking for something like:

```
pos 1197044: var vQ="https://cdn.example.com/assets"
pos 1197089: var mj="https://cdn.example.com/rive/"
```

### Extracting All Concatenated Paths

Once you have the variable name(s), find every path appended to it:

```python
var_name = 'vQ'  # replace with the actual variable name found above

# Find all string concatenations
for m in re.finditer(rf'{var_name}\s*\+\s*["`\']([^"`\']+)', content):
    print(m.group(1))

# Find template literal concatenations: vQ + `/path/${var}`
for m in re.finditer(rf'{var_name}\s*\+\s*`([^`]+)`', content):
    print(m.group(1))
```

This reveals the full asset manifest — 3D models, textures, HDR environment maps, WASM decoders, Rive animation files, MSDF font atlases, and more.

### Multiple JS Files, Multiple Variables

Check **all** JS files, not just the main bundle — different JS files may use different variable names pointing to different CDN domains:

```python
import os

for js_file in os.listdir('js/'):
    content = open(f'js/{js_file}', 'r').read()
    matches = re.findall(r'var\s+(\w+)\s*=\s*["\']https?://[^"\']+cdn[^"\']*["\']', content)
    if matches:
        print(f"{js_file}: found CDN variables: {matches}")
```

---

## Step 3: Find Rive Animation Files

Rive `.riv` files are binary animations. Find them by searching JS source:

```python
for m in re.finditer(r'["\']([^"\']*\.riv)["\']', content):
    print(m.group(1))

# Also check for relative paths that get appended to a Rive base URL
for m in re.finditer(r'["\']([^"\']*rive[^"\']*)["\']', content, re.IGNORECASE):
    print(m.group(1))
```

Also download the Rive WASM runtime — it's always hosted publicly on unpkg:

```bash
curl -sL "https://unpkg.com/@rive-app/canvas-lite@<version>/rive.wasm" -o rive/rive.wasm
```

Get the version number from the script URL in your HTML: `rive-canvas-lite@2.26.4/rive.js`

---

## Step 4: Find Binary Assets (3D, WASM, HDR)

Common binary asset patterns to search for in JS:

```python
patterns = [
    r'["\']([^"\']+\.glb)["\']',       # GLTF 3D models
    r'["\']([^"\']+\.gltf)["\']',      # GLTF JSON
    r'["\']([^"\']+\.hdr)["\']',       # HDR environment maps
    r'["\']([^"\']+\.exr)["\']',       # EXR environment maps
    r'["\']([^"\']+\.wasm)["\']',      # WebAssembly modules
    r'["\']([^"\']+\.ktx2?)["\']',     # KTX/KTX2 compressed textures
    r'["\']([^"\']+\.basis)["\']',     # Basis universal textures
    r'["\']([^"\']+\.webp)["\']',      # WebP images (may be textures)
    r'["\']([^"\']+draco[^"\']*)["\']', # Draco decoder files
    r'["\']([^"\']+\.json)["\']',      # JSON (may include MSDF font data)
    r'["\']([^"\']+\.mp4)["\']',       # Video backgrounds
    r'["\']([^"\']+\.webm)["\']',      # WebM video
]

all_binary_assets = set()
for pattern in patterns:
    for m in re.finditer(pattern, content):
        path = m.group(1)
        if not path.startswith('data:'):  # skip data URIs
            all_binary_assets.add(path)
```

---

## Step 5: Download All Assets

### Referrer-Protected CDN Downloads

For any CDN domain you identified as referrer-protected in Phase 1:

```bash
TARGET_SITE="https://targetsite.com"
REF="-H 'Referer: ${TARGET_SITE}/'"
UA="-H 'User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'"

curl -sL $REF $UA "https://cdn.example.com/assets/models/hero.glb" -o gl/models/hero.glb
```

In Python for bulk downloads:

```python
import urllib.request
import os

def download(url, local_path, referer=None):
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    req = urllib.request.Request(url)
    req.add_header('User-Agent', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36')
    if referer:
        req.add_header('Referer', referer)
    with urllib.request.urlopen(req, timeout=30) as resp:
        with open(local_path, 'wb') as f:
            f.write(resp.read())
    size = os.path.getsize(local_path)
    print(f"{'OK' if size > 100 else 'SUSPICIOUS'}: {local_path} ({size} bytes)")
```

### File Size Verification

**Always verify every downloaded file.** CDN access-denied responses are typically 32–64 bytes. Any file under 100 bytes that should be an asset is a failed download:

```bash
for f in $(find output/ -type f ! -name "*.html"); do
    size=$(wc -c < "$f")
    if [ "$size" -lt 100 ]; then
        echo "SUSPICIOUS: $f ($size bytes)"
        head -c 80 "$f"
        echo ""
    fi
done
```

Retry suspicious files with the correct `Referer` header.

---

## Step 6: CSS-Referenced Assets

CSS files may reference additional assets via `url()` — fonts, background images, SVG masks:

```python
css_content = open('css/main.css', 'r').read()

# Extract url() references
for m in re.finditer(r'url\(["\']?(https?://[^"\')\s]+)["\']?\)', css_content):
    print(m.group(1))
```

Also check `@font-face` rules in CSS for font file URLs.

---

## Format-Responsive Assets

Some sites load different asset formats based on device/browser:

```javascript
var format = window.innerWidth > 991 ? "webp" : "ktx2";
url: baseUrl + `/textures/head/${format}/diffuse.${format}`
```

Download both format directories if you want both desktop and mobile support, or just the desktop format (webp/jpg) if targeting desktop only.
