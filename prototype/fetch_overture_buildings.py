"""Fetch Overture Maps building footprints for a bounding box.

Stand-in for the LARIAC building outlines while LA County's own GIS hosts are
unreachable from the build environment. In Los Angeles, Overture's buildings
come largely from OpenStreetMap, whose LA buildings were themselves imported
from LARIAC, so the shapes are a close match to the original data.

Reads only the Parquet row groups whose bbox statistics intersect the area of
interest, so it downloads a few hundred MB rather than the global dataset.

Usage:
    python fetch_overture_buildings.py OUT.parquet [--bbox W,S,E,N] [--release R]
"""
import argparse
import concurrent.futures as cf

import pyarrow as pa
import pyarrow.fs as pafs
import pyarrow.parquet as pq
import pyarrow.compute as pc

from area import DEFAULT_BBOX

BUCKET = "overturemaps-us-west-2"
DEFAULT_RELEASE = "2026-10-21.0"


def rg_intersects(md, rg_idx, names, bbox):
    w, s, e, n = bbox
    rg = md.row_group(rg_idx)
    stats = {}
    for i in range(rg.num_columns):
        col = rg.column(i)
        if col.path_in_schema in names and col.statistics is not None and col.statistics.has_min_max:
            stats[col.path_in_schema] = col.statistics
    try:
        xmin = stats["bbox.xmin"].min
        xmax = stats["bbox.xmax"].max
        ymin = stats["bbox.ymin"].min
        ymax = stats["bbox.ymax"].max
    except KeyError:
        return True  # no stats: be conservative
    return not (xmin > e or xmax < w or ymin > n or ymax < s)


def scan_file(s3, path, bbox):
    f = pq.ParquetFile(path, filesystem=s3)
    md = f.metadata
    names = {"bbox.xmin", "bbox.xmax", "bbox.ymin", "bbox.ymax"}
    hits = [i for i in range(md.num_row_groups) if rg_intersects(md, i, names, bbox)]
    if not hits:
        return None
    w, s, e, n = bbox
    t = f.read_row_groups(hits, columns=["id", "geometry", "bbox"])
    b = t.column("bbox")
    mask = pc.and_(
        pc.and_(pc.less_equal(pc.struct_field(b, "xmin"), e), pc.greater_equal(pc.struct_field(b, "xmax"), w)),
        pc.and_(pc.less_equal(pc.struct_field(b, "ymin"), n), pc.greater_equal(pc.struct_field(b, "ymax"), s)),
    )
    t = t.filter(mask).select(["id", "geometry"])
    return t if t.num_rows else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--bbox", default=",".join(map(str, DEFAULT_BBOX)))
    ap.add_argument("--release", default=DEFAULT_RELEASE)
    args = ap.parse_args()
    bbox = tuple(float(v) for v in args.bbox.split(","))

    s3 = pafs.S3FileSystem(anonymous=True, region="us-west-2")
    prefix = f"{BUCKET}/release/{args.release}/theme=buildings/type=building/"
    files = [i.path for i in s3.get_file_info(pafs.FileSelector(prefix)) if i.path.endswith(".parquet")]
    print(f"{len(files)} files in release {args.release}; scanning footers for bbox {bbox}")

    tables = []
    with cf.ThreadPoolExecutor(32) as ex:
        for path, t in zip(files, ex.map(lambda p: scan_file(s3, p, bbox), files)):
            if t is not None:
                print(f"  {path.rsplit('/', 1)[-1]}: {t.num_rows:,} buildings")
                tables.append(t)
    out = pa.concat_tables(tables)
    pq.write_table(out, args.out, compression="zstd")
    print(f"wrote {out.num_rows:,} buildings to {args.out}")


if __name__ == "__main__":
    main()
