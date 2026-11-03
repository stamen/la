"""Pre-render the low-zoom raster tiles into a PMTiles archive.

Tiles are 512x512 px images for each 256 px tile slot ("@2x"), so they stay
crisp on high-DPI screens; MapLibre loads them with tileSize 256.  Each zoom is
rendered natively from the full data (the "native" method in experiment.py),
in large tile-aligned chunks that are then sliced, so each polygon is drawn
about once per zoom instead of once per tile.

Output tiles are lossless WebP with transparency: the page's CSS background
color shows through streets and the gaps between shapes.
"""
import argparse
import io
import math
import time

import numpy as np
from PIL import Image
from pmtiles.tile import Compression, TileType, zxy_to_tileid
from pmtiles.writer import Writer

from area import ORIGIN, lonlat_window
from render import Layer, render

SCALE = 2  # pixels per CSS pixel


def lonlat_to_tile(lon, lat, z):
    n = 2 ** z
    x = int((lon + 180) / 360 * n)
    lat_r = math.radians(lat)
    y = int((1 - math.log(math.tan(lat_r) + 1 / math.cos(lat_r)) / math.pi) / 2 * n)
    return x, y


def tile_origin(x, y, z):
    size = 2 * ORIGIN / 2 ** z
    return -ORIGIN + x * size, ORIGIN - y * size, size


def encode(rgba_premul):
    a = rgba_premul[..., 3:4].astype(np.float32)
    rgb = np.where(a > 0, rgba_premul[..., :3] * 255.0 / np.maximum(a, 1), 0)
    im = Image.fromarray(np.dstack([np.clip(rgb + 0.5, 0, 255).astype(np.uint8), rgba_premul[..., 3]]), "RGBA")
    buf = io.BytesIO()
    im.save(buf, "WEBP", lossless=True, quality=100, method=4)
    return buf.getvalue()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--layers", nargs="+", default=["buildings"])
    ap.add_argument("--minzoom", type=int, default=9)
    ap.add_argument("--maxzoom", type=int, default=14)
    ap.add_argument("--chunk", type=int, default=8, help="chunk width in tiles")
    args = ap.parse_args()

    layers = [Layer(n, f"data/{n}.npz") for n in args.layers]
    w, s, e, n = lonlat_window()
    tiles = {}
    for z in range(args.minzoom, args.maxzoom + 1):
        t0 = time.time()
        tx0, ty0 = lonlat_to_tile(w, n, z)
        tx1, ty1 = lonlat_to_tile(e, s, z)
        px = 256 * SCALE
        for cy in range(ty0, ty1 + 1, args.chunk):
            for cx in range(tx0, tx1 + 1, args.chunk):
                nx, ny = min(args.chunk, tx1 + 1 - cx), min(args.chunk, ty1 + 1 - cy)
                mx, my, size = tile_origin(cx, cy, z)
                img = render(layers, z, mx, my, nx * px, ny * px, scale_mpp=size / px)
                for j in range(ny):
                    for i in range(nx):
                        t = img[j * px:(j + 1) * px, i * px:(i + 1) * px]
                        if t[..., 3].any():
                            tiles[zxy_to_tileid(z, cx + i, cy + j)] = encode(t)
        print(f"z{z}: tiles x {tx0}-{tx1}, y {ty0}-{ty1}  ({time.time() - t0:.0f}s)")

    with open(args.out, "wb") as f:
        wr = Writer(f)
        for tid in sorted(tiles):
            wr.write_tile(tid, tiles[tid])
        wr.finalize(
            {
                "tile_type": TileType.WEBP,
                "tile_compression": Compression.NONE,
                "min_zoom": args.minzoom,
                "max_zoom": args.maxzoom,
                "min_lon_e7": int(w * 1e7), "min_lat_e7": int(s * 1e7),
                "max_lon_e7": int(e * 1e7), "max_lat_e7": int(n * 1e7),
                "center_zoom": 12,
                "center_lon_e7": int(-118.30 * 1e7), "center_lat_e7": int(34.06 * 1e7),
            },
            {"name": "la-stamen low-zoom raster", "attribution": "Stamen Design; buildings © Overture Maps / OpenStreetMap"},
        )
    total = sum(len(v) for v in tiles.values())
    print(f"wrote {len(tiles)} tiles, {total / 1e6:.1f} MB to {args.out}")


if __name__ == "__main__":
    main()
