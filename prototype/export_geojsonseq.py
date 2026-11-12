"""Write a footprint GeoParquet as newline-delimited GeoJSON for tippecanoe.

Each feature carries a numeric "id" (its row number, the same in every tile, so the map can
outline a hovered shape across tile edges) and the properties
  c    area class 0..6 (colors are applied in the MapLibre style)
  a    area in square feet, rounded
  ain  the Assessor ID Number (parcels only, when the source has one)
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

    names = pq.read_schema(args.src).names
    ain_field = "AIN" if args.layer == "parcels" and "AIN" in names else None
    cols = ["geometry"] + ([args.area_field] if args.area_field else []) + ([ain_field] if ain_field else [])
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
    ains = (np.asarray(t.column(ain_field).to_pylist(), dtype=object)[keep] if ain_field
            else np.full(len(geoms), None, dtype=object))
    out = sys.stdout
    for i, (g, c, a, ain) in enumerate(zip(shapely.to_geojson(geoms), cls, area, ains)):
        ain = (ain or "").strip()
        extra = f',"ain":"{ain}"' if ain.isdigit() else ""
        out.write(f'{{"type":"Feature","id":{i},"properties":{{"c":{int(c)},"a":{round(float(a))}{extra}}},"geometry":{g}}}\n')


if __name__ == "__main__":
    main()
