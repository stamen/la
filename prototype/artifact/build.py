"""Build the Mid-Wilshire demo page published as a claude.ai artifact.

Artifacts serve only web file types, each at most 15 MB, and allow stylesheets
only from Google Fonts. So this:
  1. cuts the Mid-Wilshire box out of both study-area PMTiles archives,
  2. base64-encodes each into a .txt file the page fetches and decodes,
  3. inlines MapLibre's CSS into page.html.

Usage (from prototype/):
    python artifact/build.py MAPLIBRE_CSS OUT_DIR
MAPLIBRE_CSS is https://unpkg.com/maplibre-gl@5.24.0/dist/maplibre-gl.css saved locally.
OUT_DIR gets index.html and tiles/*.pmtiles.b64.txt, ready to publish.
"""
import base64
import os
import subprocess
import sys

BBOX = "-118.373,34.0425,-118.297,34.0875"
HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    css_path, out = sys.argv[1], sys.argv[2]
    os.makedirs(os.path.join(out, "tiles"), exist_ok=True)
    for name, extra in (("raster", ["--minzoom", "11"]), ("vector", [])):
        tmp = os.path.join(out, "tiles", f"{name}.pmtiles")
        subprocess.run([sys.executable, os.path.join(HERE, "..", "subset_pmtiles.py"),
                        f"data/la-{name}.pmtiles", tmp, f"--bbox={BBOX}", *extra], check=True)
        with open(tmp, "rb") as f, open(tmp + ".b64.txt", "wb") as g:
            g.write(base64.b64encode(f.read()))
        os.remove(tmp)
    with open(os.path.join(HERE, "page.html")) as f, open(css_path) as c:
        page = f.read().replace("/*MAPLIBRE_CSS*/", c.read())
    with open(os.path.join(out, "index.html"), "w") as f:
        f.write(page)
    for root, _, files in os.walk(out):
        for n in files:
            p = os.path.join(root, n)
            print(f"{os.path.getsize(p) / 1e6:6.1f} MB  {os.path.relpath(p, out)}")


if __name__ == "__main__":
    main()
