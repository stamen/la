#!/bin/bash
# Build the countywide tiles from scratch: data/la-raster.pmtiles and data/la-vector.pmtiles.
# Takes ~1.5 hours on 4 cores (most of it the z15 raster level) and ~10 GB of disk.
#
#   bash prototype/build_all.sh          # from the repo root
#
# Then upload with prototype/upload_tiles.py.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p data

echo "== dependencies"
if ! python3 -c "import skia" 2>/dev/null; then
  (apt-get install -y -q libegl1 libgl1 >/dev/null 2>&1 || (apt-get update -q >/dev/null && apt-get install -y -q libegl1 libgl1 >/dev/null)) || true
fi
pip install -q skia-python shapely pyarrow numpy pillow pmtiles requests
TIPPECANOE="${TIPPECANOE:-$(command -v tippecanoe || true)}"
if [ -z "$TIPPECANOE" ]; then
  if [ ! -x build/tippecanoe/tippecanoe ]; then
    mkdir -p build && git clone -q --depth 1 https://github.com/felt/tippecanoe.git build/tippecanoe
    make -C build/tippecanoe -j"$(nproc)" >/dev/null
  fi
  TIPPECANOE="$PWD/build/tippecanoe/tippecanoe"
fi

echo "== fetch (LA County ArcGIS Online; resumable)"
[ -f data/parcels.parquet ] || python3 fetch_arcgis.py parcels data/parcels.parquet --bbox all
[ -f data/lariac_buildings.parquet ] || python3 fetch_arcgis.py buildings data/lariac_buildings.parquet --bbox all

echo "== prep"
python3 prep.py data/parcels.parquet data/parcels.npz --layer parcels --area-field area_ft2
python3 prep.py data/lariac_buildings.parquet data/buildings.npz --layer buildings --area-field area_ft2

echo "== vector tiles (z13-16)"
python3 export_geojsonseq.py data/parcels.parquet --layer parcels --area-field area_ft2 > data/parcels.geojsonl
python3 export_geojsonseq.py data/lariac_buildings.parquet --layer buildings --area-field area_ft2 > data/buildings.geojsonl
"$TIPPECANOE" -q -P -o data/la-vector.pmtiles --force -Z13 -z16 --drop-rate=1 --no-feature-limit \
  --no-tile-size-limit --no-tiny-polygon-reduction --detect-shared-borders \
  --attribution "County of Los Angeles: Assessor parcels (2025), LARIAC buildings (2020)" \
  -L parcels:data/parcels.geojsonl -L buildings:data/buildings.geojsonl
rm -f data/parcels.geojsonl data/buildings.geojsonl

echo "== raster tiles (z11-15 rendered, z0-10 averaged down)"
python3 build_raster_tiles.py data/la-raster-z11-15.pmtiles --bbox data --minzoom 11 --maxzoom 15
python3 build_overviews.py data/la-raster-z11-15.pmtiles data/la-raster.pmtiles --from-zoom 11 --to-zoom 0
rm -f data/la-raster-z11-15.pmtiles

ls -la data/la-raster.pmtiles data/la-vector.pmtiles
echo "== done"
