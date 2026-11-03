# la.stamen.com modernization prototype

Experiments for rebuilding la.stamen.com on a static stack: MapLibre + PMTiles in cheap object
storage, with **pre-rendered raster tiles at low zoom** (to keep the dense sub-pixel texture the old
Mapnik/CARTO version had) and **vector tiles at high zoom**.

Status: buildings only (Overture Maps, which in LA mostly comes from OSM's LARIAC import).
Parcels are pending network access to LA County's GIS hosts.

## Pipeline

```sh
pip install skia-python shapely pyarrow numpy pillow pmtiles
python fetch_overture_buildings.py data/buildings.parquet     # ~2M footprints, central LA
python prep.py data/buildings.parquet data/buildings.npz --layer buildings
python experiment.py      # native / pyramid / aliased renders at z11-13 -> out/
python compare.py         # out/sheet_crops.png
python build_raster_tiles.py data/la-raster.pmtiles           # z9-14 @2x WebP tiles
python export_geojsonseq.py data/buildings.parquet --layer buildings > data/buildings.geojsonl
tippecanoe -o data/la-vector.pmtiles -l buildings -Z13 -z16 --drop-rate=1 \
  --no-feature-limit --no-tile-size-limit --no-tiny-polygon-reduction data/buildings.geojsonl
```

## Files

- `area.py` - study area (1024x640 px at z11 around Koreatown) and Web Mercator helpers
- `palette.py` - original 7-class Greys palette and `shape_area` breaks from the 2016 `index.html`
- `render.py` - Skia renderer: each polygon drawn separately with coverage anti-aliasing, transparent background
- `experiment.py`, `compare.py` - method comparison
- `build_raster_tiles.py` - low-zoom raster PMTiles
- `export_geojsonseq.py` - input for tippecanoe

## Findings so far (buildings only)

![comparison](docs/comparison_buildings_only.png)

- The 2008 class breaks still split today's ~2M buildings into seven nearly equal classes.
- Rendering each zoom natively and rendering at z15 then averaging down look nearly identical for
  buildings, which rarely share edges. Parcels share every edge, so that is where the two methods
  should diverge; needs parcel data to test.
- No anti-aliasing (a stand-in for GPU vector rendering) gives black speckle and holes: the effect
  the raster tiles are there to avoid.
- Python + skia-python manages ~19 us/polygon (~40 s per 2M-polygon pass). Fine for a prototype; use
  Rust/tiny-skia for the full county.
