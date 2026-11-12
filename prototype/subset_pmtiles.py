"""Copy the tiles of a PMTiles archive that fall inside a bbox into a new archive.

Used to cut a small demo area (e.g. Mid-Wilshire) out of the study-area tiles,
small enough to publish as a single static file.

Usage:
    python subset_pmtiles.py IN.pmtiles OUT.pmtiles --bbox W,S,E,N [--minzoom Z] [--maxzoom Z]
"""
import argparse
import math

from pmtiles.reader import MmapSource, Reader, all_tiles
from pmtiles.tile import zxy_to_tileid
from pmtiles.writer import Writer


def lonlat_to_tile(lon, lat, z):
    n = 2 ** z
    x = int((lon + 180) / 360 * n)
    r = math.radians(lat)
    y = int((1 - math.log(math.tan(r) + 1 / math.cos(r)) / math.pi) / 2 * n)
    return x, y


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--bbox", required=True)
    ap.add_argument("--minzoom", type=int)
    ap.add_argument("--maxzoom", type=int)
    args = ap.parse_args()
    w, s, e, n = (float(v) for v in args.bbox.split(","))

    with open(args.src, "rb") as f:
        src = MmapSource(f)
        reader = Reader(src)
        header, metadata = reader.header(), reader.metadata()
        zmin = max(header["min_zoom"], args.minzoom if args.minzoom is not None else 0)
        zmax = min(header["max_zoom"], args.maxzoom if args.maxzoom is not None else 99)
        ranges = {z: (lonlat_to_tile(w, n, z), lonlat_to_tile(e, s, z)) for z in range(zmin, zmax + 1)}

        keep = {}
        for (z, x, y), data in all_tiles(src):
            if z in ranges:
                (x0, y0), (x1, y1) = ranges[z]
                if x0 <= x <= x1 and y0 <= y <= y1:
                    keep[zxy_to_tileid(z, x, y)] = data

    with open(args.out, "wb") as f:
        wr = Writer(f)
        for tid in sorted(keep):
            wr.write_tile(tid, keep[tid])
        h = dict(header)
        h.update(min_zoom=zmin, max_zoom=zmax,
                 min_lon_e7=int(w * 1e7), min_lat_e7=int(s * 1e7),
                 max_lon_e7=int(e * 1e7), max_lat_e7=int(n * 1e7),
                 center_zoom=max(zmin, min(zmax, 14)),
                 center_lon_e7=int((w + e) / 2 * 1e7), center_lat_e7=int((s + n) / 2 * 1e7))
        wr.finalize(h, metadata)
    print(f"{len(keep)} tiles, {sum(map(len, keep.values())) / 1e6:.1f} MB -> {args.out}")


if __name__ == "__main__":
    main()
