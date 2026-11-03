"""Turn a footprint GeoParquet (WKB geometry) into flat numpy arrays for rendering.

Output .npz holds:
  xy        float64 (N, 2)  every exterior/interior ring vertex, Web Mercator meters
  ring_off  int64           start index of each ring in xy (+ final sentinel)
  poly_ring int64           start index of each polygon's rings in ring_off (+ sentinel)
  bbox      float64 (P, 4)  per-polygon mercator bbox, for culling
  area_ft2  float64 (P,)    ground area in square feet
  cls       uint8   (P,)    0..6 area class using the original la.stamen.com breaks

MultiPolygons are split into their parts; each part keeps the parent's area
class, matching how Mapnik styled a whole feature with one fill.
"""
import argparse

import numpy as np
import pyarrow.parquet as pq
import shapely

from palette import classify

R = 6378137.0
M2_TO_FT2 = 10.763910416709722


def to_merc(coords):
    lon = np.radians(coords[:, 0])
    lat = np.radians(np.clip(coords[:, 1], -85.05, 85.05))
    return np.column_stack([lon * R, np.log(np.tan(np.pi / 4 + lat / 2)) * R])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--layer", choices=["buildings", "parcels"], required=True)
    ap.add_argument("--area-field", help="use this attribute (sq ft) instead of computing area")
    args = ap.parse_args()

    cols = ["geometry"] + ([args.area_field] if args.area_field else [])
    t = pq.read_table(args.src, columns=cols)
    geoms = shapely.from_wkb(t.column("geometry").to_numpy(zero_copy_only=False))
    keep = shapely.get_type_id(geoms) >= 3  # Polygon (3) or MultiPolygon (6)
    geoms = geoms[keep]

    # Project to Web Mercator.
    merc = shapely.transform(geoms, to_merc)

    if args.area_field:
        area_ft2 = t.column(args.area_field).to_numpy()[keep].astype("float64")
    else:
        # Mercator inflates area by 1/cos^2(lat); undo it per feature at its centroid.
        # At LA's latitude this is within ~0.1% of an equal-area (EPSG:2229) result.
        lat = shapely.get_coordinates(shapely.centroid(geoms))[:, 1]
        area_ft2 = shapely.area(merc) * np.cos(np.radians(lat)) ** 2 * M2_TO_FT2
    cls = classify(area_ft2, args.layer)

    # Explode multipolygons into parts.
    parts, parent = shapely.get_parts(merc, return_index=True)
    rings, ring_parent = shapely.get_rings(parts, return_index=True)
    coords, coord_ring = shapely.get_coordinates(rings, return_index=True)

    ring_off = np.searchsorted(coord_ring, np.arange(len(rings) + 1))
    poly_ring = np.searchsorted(ring_parent, np.arange(len(parts) + 1))
    b = shapely.bounds(parts)

    np.savez(
        args.out,
        xy=coords,
        ring_off=ring_off,
        poly_ring=poly_ring,
        bbox=b,
        area_ft2=area_ft2[parent],
        cls=cls[parent],
    )
    counts = np.bincount(cls, minlength=7)
    print(f"{len(geoms):,} features -> {len(parts):,} polygons, {len(coords):,} vertices")
    print("class counts:", counts.tolist())


if __name__ == "__main__":
    main()
