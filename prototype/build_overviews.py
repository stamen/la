"""Rebuild the low zooms of a raster PMTiles archive by averaging down from one level.

Each parent tile is the 2x2 box average (in premultiplied RGBA) of its four
children, so every level shows exactly the coverage of the level it came from.
That matches how the supersampled levels relate to each other, and it is more
accurate at low zooms than rendering them directly: at z9 a direct render's 8x8
samples per pixel land ~19 m apart, coarser than a house.

Usage:
    python build_overviews.py IN.pmtiles OUT.pmtiles [--from-zoom 11] [--to-zoom 0]
Levels below --from-zoom are replaced; --from-zoom and above are copied as-is.
"""
import argparse
import io
from collections import defaultdict

import numpy as np
from PIL import Image
from pmtiles.reader import MmapSource, Reader, all_tiles
from pmtiles.tile import zxy_to_tileid
from pmtiles.writer import Writer


def decode(data):
    a = np.asarray(Image.open(io.BytesIO(data)).convert("RGBA")).astype(np.float32)
    a[..., :3] *= a[..., 3:4] / 255.0  # premultiply
    return a


def encode(premul):
    a = premul[..., 3:4]
    rgb = np.where(a > 0, premul[..., :3] * 255.0 / np.maximum(a, 1e-6), 0)
    out = np.dstack([rgb, a]).clip(0, 255) + 0.5
    buf = io.BytesIO()
    Image.fromarray(out.astype(np.uint8), "RGBA").save(buf, "WEBP", lossless=True, quality=100, method=4)
    return buf.getvalue()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--from-zoom", type=int, default=11)
    ap.add_argument("--to-zoom", type=int, default=0)
    args = ap.parse_args()

    with open(args.src, "rb") as f:
        src = MmapSource(f)
        reader = Reader(src)
        header, metadata = reader.header(), reader.metadata()
        kept, level = {}, {}
        for (z, x, y), data in all_tiles(src):
            if z >= args.from_zoom:
                kept[zxy_to_tileid(z, x, y)] = data
            if z == args.from_zoom:
                level[(x, y)] = decode(data)
    size = next(iter(level.values())).shape[0]
    print(f"z{args.from_zoom}: {len(level)} tiles of {size}px", flush=True)

    made = {}
    for z in range(args.from_zoom - 1, args.to_zoom - 1, -1):
        parents = defaultdict(dict)
        for (x, y), img in level.items():
            parents[(x // 2, y // 2)][(x % 2, y % 2)] = img
        nxt = {}
        for (px, py), kids in parents.items():
            mosaic = np.zeros((size * 2, size * 2, 4), np.float32)
            for (dx, dy), img in kids.items():
                mosaic[dy * size:(dy + 1) * size, dx * size:(dx + 1) * size] = img
            parent = mosaic.reshape(size, 2, size, 2, 4).mean(axis=(1, 3))
            # Round through 8 bits like a stored tile, so each level is built from what is shipped.
            parent = np.floor(parent + 0.5)
            nxt[(px, py)] = parent
            made[zxy_to_tileid(z, px, py)] = encode(parent)
        level = nxt
        print(f"z{z}: {len(level)} tiles", flush=True)

    tiles = {**kept, **made}
    with open(args.out, "wb") as f:
        wr = Writer(f)
        for tid in sorted(tiles):
            wr.write_tile(tid, tiles[tid])
        wr.finalize({**header, "min_zoom": args.to_zoom}, metadata)
    print(f"wrote {len(tiles)} tiles, {sum(map(len, tiles.values())) / 1e6:.1f} MB to {args.out}")


if __name__ == "__main__":
    main()
