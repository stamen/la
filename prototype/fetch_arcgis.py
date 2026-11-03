"""Download LA County layers from the county's ArcGIS Online feature services.

  parcels   - Assessor parcels, 2025 roll (ASSR_PARCELS_25_View), ~2.43M countywide.
              Stored in EPSG:2229, so Shape__Area is square feet, the same unit as
              the original CARTO `shape_area`.
  buildings - LARIAC6 building outlines (2020), CODE = 'Building' (the original
              site filtered the 2008 LARIAC outlines the same way). AREA is sq ft.

Pages through the bbox with resultOffset and writes WKB geometry plus an
`area_ft2` column to Parquet, ready for prep.py / export_geojsonseq.py.

Usage:
    python fetch_arcgis.py parcels data/parcels.parquet [--bbox W,S,E,N]
"""
import argparse
import concurrent.futures as cf
import json
import os
import time

import pyarrow as pa
import pyarrow.parquet as pq
import requests
import shapely

from area import DEFAULT_BBOX

BASE = "https://services.arcgis.com/RmCCgQtiZLDCtblq/arcgis/rest/services"
LAYERS = {
    "parcels": dict(url=f"{BASE}/ASSR_PARCELS_25_View/FeatureServer/0", where="1=1",
                    fields=["AIN", "Shape__Area"], area="Shape__Area"),
    "buildings": dict(url=f"{BASE}/Countywide_Building_Outlines_(2020)/FeatureServer/0", where="CODE='Building'",
                      fields=["BLD_ID", "AREA"], area="AREA"),
}
PAGE = 2000

session = requests.Session()


def get(url, params, tries=6):
    for i in range(tries):
        try:
            r = session.get(url, params=params, timeout=120)
            r.raise_for_status()
            d = r.json()
            if "error" in d:
                raise RuntimeError(d["error"])
            return d
        except Exception as e:  # noqa: BLE001
            if i == tries - 1:
                raise
            time.sleep(2 ** i)
            print(f"  retry {i + 1}: {e}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("layer", choices=LAYERS)
    ap.add_argument("out")
    ap.add_argument("--bbox", default=",".join(map(str, DEFAULT_BBOX)))
    ap.add_argument("--workers", type=int, default=16)
    args = ap.parse_args()
    cfg = LAYERS[args.layer]

    spatial = dict(geometry=args.bbox, geometryType="esriGeometryEnvelope", inSR=4326,
                   spatialRel="esriSpatialRelIntersects")
    n = get(cfg["url"] + "/query", dict(spatial, where=cfg["where"], returnCountOnly="true", f="json"))["count"]
    stats = get(cfg["url"] + "/query", dict(where="1=1", f="json", outStatistics=json.dumps([
        {"statisticType": "min", "onStatisticField": "OBJECTID", "outStatisticFieldName": "lo"},
        {"statisticType": "max", "onStatisticField": "OBJECTID", "outStatisticFieldName": "hi"}])))
    lo, hi = (stats["features"][0]["attributes"][k] for k in ("lo", "hi"))
    print(f"{args.layer}: {n:,} features in bbox; OBJECTID {lo}..{hi}")

    # Page by fixed OBJECTID ranges rather than resultOffset: deep offsets get
    # slower and start failing on hosted feature services, while a range of
    # PAGE ids can never exceed the PAGE-record limit. Pages are cached so an
    # interrupted download resumes where it stopped.
    cache = os.path.join(os.path.dirname(os.path.abspath(args.out)), f"cache_{args.layer}")
    os.makedirs(cache, exist_ok=True)

    def page(start):
        path = os.path.join(cache, f"{start}.json")
        if os.path.exists(path):
            with open(path) as f:
                return json.load(f)
        d = get(cfg["url"] + "/query", dict(
            spatial, where=f"({cfg['where']}) AND OBJECTID >= {start} AND OBJECTID < {start + PAGE}",
            outFields=",".join(cfg["fields"]), outSR=4326, geometryPrecision=7, f="geojson"))
        if d.get("exceededTransferLimit") or d.get("properties", {}).get("exceededTransferLimit"):
            raise RuntimeError(f"page {start} exceeded the transfer limit")
        with open(path + ".tmp", "w") as f:
            json.dump(d["features"], f)
        os.replace(path + ".tmp", path)
        return d["features"]

    feats, t0 = [], time.time()
    starts = range(lo, hi + 1, PAGE)
    with cf.ThreadPoolExecutor(args.workers) as ex:
        for i, fs in enumerate(ex.map(page, starts)):
            feats.extend(fs)
            if i % 100 == 0:
                print(f"  page {i}/{len(starts)}: {len(feats):,}/{n:,}  {time.time() - t0:.0f}s", flush=True)
    if len(feats) != n:
        print(f"  warning: got {len(feats):,} features, server count was {n:,}")

    feats = [f for f in feats if f.get("geometry")]
    geoms = shapely.from_geojson([json.dumps(f["geometry"]) for f in feats])
    cols = {"geometry": shapely.to_wkb(geoms)}
    for k in cfg["fields"]:
        cols[k] = [f["properties"].get(k) for f in feats]
    cols["area_ft2"] = [float(f["properties"].get(cfg["area"]) or 0.0) for f in feats]
    pq.write_table(pa.table(cols), args.out, compression="zstd")
    print(f"wrote {len(feats):,} {args.layer} to {args.out}")


if __name__ == "__main__":
    main()
