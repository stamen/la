"""Write a footprint GeoParquet as newline-delimited GeoJSON for tippecanoe.

Each feature carries only {"c": area class 0..6}, keeping vector tiles small;
colors are applied in the MapLibre style.
"""
import argparse
import sys

import numpy as np
import pyarrow.parquet as pq
import shapely

from palette import classify
from prep import M2_TO_FT2, to_merc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("--layer", choices=["buildings", "parcels"], required=True)
    ap.add_argument("--area-field")
    args = ap.parse_args()

    cols = ["geometry"] + ([args.area_field] if args.area_field else [])
    t = pq.read_table(args.src, columns=cols)
    geoms = shapely.from_wkb(t.column("geometry").to_numpy(zero_copy_only=False))
    keep = shapely.get_type_id(geoms) >= 3
    geoms = geoms[keep]
    if args.area_field:
        area = t.column(args.area_field).to_numpy()[keep].astype("float64")
    else:
        lat = shapely.get_coordinates(shapely.centroid(geoms))[:, 1]
        area = shapely.area(shapely.transform(geoms, to_merc)) * np.cos(np.radians(lat)) ** 2 * M2_TO_FT2
    cls = classify(area, args.layer)
    out = sys.stdout
    for g, c in zip(shapely.to_geojson(geoms), cls):
        out.write(f'{{"type":"Feature","properties":{{"c":{int(c)}}},"geometry":{g}}}\n')


if __name__ == "__main__":
    main()
