"""Render the study area three ways at zooms 11-13 and save the results.

  native   - render each zoom directly from full-resolution data with coverage AA
             (the Mapnik/CARTO behaviour we want to reproduce)
  pyramid  - render once at a high base zoom, then 2x2 box-average down
             (cheaper; same mean tone, but seams are thinner)
  aliased  - render each zoom with anti-aliasing off: a rough stand-in for a
             GPU vector renderer, where a sub-pixel triangle covers a pixel
             fully or not at all

Outputs transparent RGBA PNGs in out/, one per method and zoom.
"""
import argparse
import os
import time

import numpy as np
from PIL import Image

from area import BASE_SIZE, BASE_ZOOM, merc_window
from render import Layer, downsample, render

ZOOMS = [11, 12, 13]


def save(rgba, path):
    # PIL expects straight alpha; un-premultiply.
    a = rgba[..., 3:4].astype(np.float32)
    rgb = np.where(a > 0, rgba[..., :3].astype(np.float32) * 255.0 / np.maximum(a, 1), 0)
    Image.fromarray(np.dstack([np.clip(rgb + 0.5, 0, 255).astype(np.uint8), rgba[..., 3]]), "RGBA").save(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--layers", nargs="+", default=["buildings"], help="draw order, e.g. parcels buildings")
    ap.add_argument("--pyramid-base", type=int, default=15)
    ap.add_argument("--chunk", type=int, default=4096)
    ap.add_argument("--out", default="out")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    layers = [Layer(name, f"data/{name}.npz") for name in args.layers]
    x0, y0, x1, y1 = merc_window()

    def size_at(z):
        f = 2 ** (z - BASE_ZOOM)
        return BASE_SIZE[0] * f, BASE_SIZE[1] * f

    for method, aa in (("native", True), ("aliased", False)):
        for z in ZOOMS:
            t = time.time()
            w, h = size_at(z)
            img = render(layers, z, x0, y1, w, h, antialias=aa)
            save(img, f"{args.out}/{method}_z{z}.png")
            print(f"{method} z{z} {w}x{h}: {time.time() - t:.1f}s")

    # Pyramid: render the base zoom in chunks, downsample each chunk to every target zoom.
    t = time.time()
    bz = args.pyramid_base
    bw, bh = size_at(bz)
    outs = {z: np.zeros((size_at(z)[1], size_at(z)[0], 4), np.uint8) for z in ZOOMS}
    from area import meters_per_pixel
    mpp = meters_per_pixel(bz)
    for cy in range(0, bh, args.chunk):
        for cx in range(0, bw, args.chunk):
            cw, ch = min(args.chunk, bw - cx), min(args.chunk, bh - cy)
            tile = render(layers, bz, x0 + cx * mpp, y1 - cy * mpp, cw, ch)
            for z in ZOOMS:
                f = 2 ** (bz - z)
                small = downsample(tile, f)
                outs[z][cy // f: cy // f + small.shape[0], cx // f: cx // f + small.shape[1]] = small
    for z in ZOOMS:
        save(outs[z], f"{args.out}/pyramid_z{z}.png")
    print(f"pyramid from z{bz} ({bw}x{bh}): {time.time() - t:.1f}s")


if __name__ == "__main__":
    main()
