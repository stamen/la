"""Build the Mid-Wilshire demo page published as a claude.ai artifact.

Artifacts serve only web file types, each at most 15 MB, and allow stylesheets
only from Google Fonts. So this:
  1. cuts the Mid-Wilshire box out of both study-area PMTiles archives,
  2. base64-encodes each into one or more .txt parts under 15 MB that the page
     fetches, decodes and joins (the part list is written into the page),
  3. inlines MapLibre's CSS into page.html.

Usage (from prototype/):
    python artifact/build.py MAPLIBRE_CSS OUT_DIR
MAPLIBRE_CSS is https://unpkg.com/maplibre-gl@5.24.0/dist/maplibre-gl.css saved locally.
OUT_DIR gets index.html and tiles/*.b64.txt, ready to publish.
"""
import base64
import json
import os
import re
import subprocess
import sys

BBOX = "-118.373,34.0425,-118.297,34.0875"
PART_BYTES = 10_500_000  # raw bytes per part; base64 makes it 14 MB, under the 15 MB file limit
HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    css_path, out = sys.argv[1], sys.argv[2]
    tiles_dir = os.path.join(out, "tiles")
    os.makedirs(tiles_dir, exist_ok=True)
    for old in os.listdir(tiles_dir):
        os.remove(os.path.join(tiles_dir, old))
    parts, total = {}, 0
    for name, extra in (("raster", []), ("vector", [])):
        tmp = os.path.join(tiles_dir, f"{name}.pmtiles")
        subprocess.run([sys.executable, os.path.join(HERE, "..", "subset_pmtiles.py"),
                        f"data/la-{name}.pmtiles", tmp, f"--bbox={BBOX}", *extra], check=True)
        with open(tmp, "rb") as f:
            raw = f.read()
        os.remove(tmp)
        chunks = [raw[i:i + PART_BYTES] for i in range(0, len(raw), PART_BYTES)]
        parts[name] = []
        for i, chunk in enumerate(chunks):
            rel = f"tiles/{name}.pmtiles.b64.txt" if len(chunks) == 1 else f"tiles/{name}.pmtiles.part{i + 1}.b64.txt"
            data = base64.b64encode(chunk)
            with open(os.path.join(out, rel), "wb") as g:
                g.write(data)
            parts[name].append(rel)
            total += len(data)
    with open(os.path.join(HERE, "page.html")) as f, open(css_path) as c:
        page = f.read().replace("/*MAPLIBRE_CSS*/", c.read())
    page = re.sub(r"/\*TILE_PARTS\*/[^;]*", lambda m: json.dumps(parts), page)
    page = re.sub(r"/\*TILE_BYTES\*/[^;]*", str(total), page)
    with open(os.path.join(out, "index.html"), "w") as f:
        f.write(page)
    for root, _, files in os.walk(out):
        for n in files:
            p = os.path.join(root, n)
            print(f"{os.path.getsize(p) / 1e6:6.1f} MB  {os.path.relpath(p, out)}")


if __name__ == "__main__":
    main()
