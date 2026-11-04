"""Pre-render the low-zoom raster tiles into a PMTiles archive.

Tiles are 512x512 px images for each 256 px tile slot ("@2x"), so they stay
crisp on high-DPI screens; MapLibre loads them with tileSize 256.

Each zoom is supersampled (the "supersampled" method in experiment.py): the
full-resolution data is drawn WITHOUT anti-aliasing at SS x the tile
resolution, then box-averaged down. Every sample belongs to exactly one
polygon, so shared parcel edges leak no background and sub-pixel buildings
and parcels contribute exactly their area. Rendering each zoom with per-polygon
anti-aliasing instead (Mapnik's approach) leaks the background through every
parcel seam and adds ~10 points of extra turquoise at z11.

Rendering happens in tile-aligned chunks that are then sliced.

Output tiles are lossless WebP with transparency: the page's CSS background
color shows through streets and the gaps between shapes.
"""
import argparse
import io
import math
import multiprocessing as mp
import time

import numpy as np
from PIL import Image
from pmtiles.tile import Compression, TileType, zxy_to_tileid
from pmtiles.writer import Writer

from area import ORIGIN, lonlat_window
from render import Layer, downsample, render

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


LAYERS, SS = None, None


def render_chunk(job):
    """Render nx x ny tiles starting at (cx, cy) and return {tileid: webp bytes}."""
    z, cx, cy, nx, ny = job
    px = 256 * SCALE
    mx, my, size = tile_origin(cx, cy, z)
    big = render(LAYERS, z, mx, my, nx * px * SS, ny * px * SS,
                 antialias=False, scale_mpp=size / (px * SS))
    img = downsample(big, SS)
    del big
    out = {}
    for j in range(ny):
        for i in range(nx):
            t = img[j * px:(j + 1) * px, i * px:(i + 1) * px]
            if t[..., 3].any():
                out[zxy_to_tileid(z, cx + i, cy + j)] = encode(t)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--layers", nargs="+", default=["parcels", "buildings"], help="draw order")
    ap.add_argument("--minzoom", type=int, default=9)
    ap.add_argument("--maxzoom", type=int, default=15)
    ap.add_argument("--render-zooms", type=int, nargs="+",
                    help="render only these zooms; copy the rest from --keep")
    ap.add_argument("--keep", help="existing raster .pmtiles to copy non-rendered zooms from")
    ap.add_argument("--supersample", type=int, default=8, help="samples per output pixel, per axis")
    ap.add_argument("--chunk-px", type=int, default=4096, help="max rendered chunk width in pixels")
    ap.add_argument("--workers", type=int, default=mp.cpu_count())
    args = ap.parse_args()

    global LAYERS, SS
    LAYERS = [Layer(n, f"data/{n}.npz") for n in args.layers]  # inherited by forked workers
    SS = args.supersample
    w, s, e, n = lonlat_window()
    tiles = {}
    px = 256 * SCALE
    render_zooms = set(args.render_zooms or range(args.minzoom, args.maxzoom + 1))
    if args.keep:
        from pmtiles.reader import MmapSource, all_tiles
        with open(args.keep, "rb") as f:
            for (z, x, y), data in all_tiles(MmapSource(f)):
                if args.minzoom <= z <= args.maxzoom and z not in render_zooms:
                    tiles[zxy_to_tileid(z, x, y)] = data
        print(f"kept {len(tiles)} tiles from {args.keep}", flush=True)
    with mp.get_context("fork").Pool(args.workers) as pool:
        for z in sorted(render_zooms):
            t0 = time.time()
            tx0, ty0 = lonlat_to_tile(w, n, z)
            tx1, ty1 = lonlat_to_tile(e, s, z)
            chunk = max(1, args.chunk_px // (px * SS))
            jobs = [(z, cx, cy, min(chunk, tx1 + 1 - cx), min(chunk, ty1 + 1 - cy))
                    for cy in range(ty0, ty1 + 1, chunk) for cx in range(tx0, tx1 + 1, chunk)]
            for result in pool.imap_unordered(render_chunk, jobs):
                tiles.update(result)
            print(f"z{z}: tiles x {tx0}-{tx1}, y {ty0}-{ty1}  ({time.time() - t0:.0f}s)", flush=True)

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
            {"name": "la-stamen low-zoom raster", "attribution": "Stamen Design; parcels and buildings: County of Los Angeles (Assessor, LARIAC)"},
        )
    total = sum(len(v) for v in tiles.values())
    print(f"wrote {len(tiles)} tiles, {total / 1e6:.1f} MB to {args.out}")


if __name__ == "__main__":
    main()
