# la.stamen.com

Every parcel and building in Los Angeles County, shaded by area. Small buildings are dark and large
ones light; parcels run the other way. The streets are the space between parcels.

Originally made in 2016 on CARTO
([about](https://stamen.com/using-open-data-to-learn-about-los-angeles-5b30192a68b0/)). Rebuilt in
2026 as a static site: MapLibre GL JS reading two PMTiles archives from object storage, with no map
server.

- **Below z14.5** the map shows pre-rendered raster tiles. Every parcel and building is drawn at
  full resolution and supersampled, so features smaller than a pixel still shade it by their area.
  That keeps the dense low-zoom texture the 2016 Mapnik rendering had, which vector tiles cannot
  reproduce.
- **From z14.5** it shows vector tiles, with buildings/parcels toggles. Hovering (or tapping) a
  building or parcel outlines it in the page color and shows its area, and a parcel's AIN
  (Assessor ID Number).
- **Color scale.** *Fixed breaks* (the default) uses the same round-number classes everywhere,
  matching the raster tiles. At the vector zooms, *this view* switches to seven equal-count
  classes (quantiles) of the shapes on screen, recomputed when the map stops moving; *lock* keeps
  the current breaks while panning, to compare places on one scale. In that mode the legend keeps
  the fixed breaks as its axis and resizes the swatches to where the view's breaks fall on it, so
  the scale visibly squashes toward one end.
- Labels are the vector Stamen Toner labels from [Stadia Maps](https://stadiamaps.com/)
  (domain-authenticated for `*.stamen.com`), loaded the first time they are turned on. Search uses
  [Photon](https://photon.komoot.io/). The background color is selectable, as in 2016.

Data: County of Los Angeles Assessor parcels (2025 roll) and LARIAC building outlines (2020), from
the county's ArcGIS Online services.

## Files

- `index.html` - the whole site, one file (GitHub Pages from `main`, `CNAME` -> la.stamen.com)
- `social.jpg` - the social card
- `prototype/` - the data pipeline (`build_all.sh`, `upload_tiles.py`), experiments and the
  Mid-Wilshire demo; see [prototype/README.md](prototype/README.md)

URL parameters: `?background=<css color or hex>` (as in 2016), `?labels=true`, `?scale=view`,
`?tiles=<base url of the .pmtiles files>`; the hash holds `#zoom/lat/lon`.

### Tiles

- `la-raster.pmtiles` - 512 px WebP, z0-15. z11-15 are rendered from the polygons; z0-10 are box
  averages of z11.
- `la-vector-v2.pmtiles` - z13-16 (overzoomed beyond), layers `parcels` and `buildings`. Every
  feature has an `id` that is the same in every tile (the hover outline uses it) and the
  properties `c` (fixed area class, 0-6), `a` (area in sq ft, rounded) and, on parcels, `ain`.

## Running locally

No build is needed to work on the page: serve the repo root with any static server and point it
at the published tiles (on localhost the page otherwise looks for them in `./tiles/`):

```sh
python3 -m http.server 8000
open "http://localhost:8000/?tiles=https://d2a8fp87hzkuh6.cloudfront.net/#15/34.0615/-118.3005"
```

With tiles built locally (see below), `node prototype/web/serve.mjs 8080` serves the page and
`/tiles/*` from `prototype/data`, with the HTTP range requests PMTiles needs.

The social card (`social.jpg`, referenced by the Open Graph tags in `index.html`) is rendered from
the map: `node prototype/web/social-card.mjs` (uses the live site; pass `http://localhost:8080/` to
render from a local checkout).

## Hosting the tiles on AWS (S3 + CloudFront)

The page loads `la-raster.pmtiles` (~320 MB) and `la-vector-v2.pmtiles` (~715 MB) with HTTP range requests.

1. **S3 bucket** (any region), private, e.g. `la-stamen-tiles`.
2. **CloudFront distribution** with that bucket as origin, using Origin Access Control.
   - Cache policy: `CachingOptimized` (range requests are cached per range automatically).
   - Response headers policy: `CORS-With-Preflight` (or a custom one allowing
     `https://la.stamen.com` with `GET, HEAD` and exposing `ETag, Content-Range, Accept-Ranges`).
   - Optional custom domain such as `tiles.stamen.com`, with a certificate from ACM in `us-east-1`.
3. **Build and upload** (in a session or machine with the AWS variables set; see below):
   ```sh
   bash prototype/build_all.sh            # ~1.5 h: fetch, prep, vector + raster tiles
   python prototype/upload_tiles.py       # uploads both archives to $LA_TILES_BUCKET
   ```
   CloudFront caches each file for a day. When a rebuild changes what the page expects (new
   properties, say), upload it under a new name (`la-vector-v2` -> `v3`) and point `index.html` at
   it, so the live site keeps working until the change is merged; otherwise invalidate the path.
4. The site reads tiles from `TILES_HOST` in `index.html` (currently
   `https://d2a8fp87hzkuh6.cloudfront.net/`), and from `./tiles/` on localhost.

Environment variables for the upload: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`,
`AWS_DEFAULT_REGION` (the bucket's region) and `LA_TILES_BUCKET` (the bucket name).

An IAM policy for an upload-only key limited to the bucket:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": ["s3:PutObject", "s3:GetObject", "s3:ListBucket", "s3:AbortMultipartUpload"],
    "Resource": ["arn:aws:s3:::la-stamen-tiles", "arn:aws:s3:::la-stamen-tiles/*"]
  }]
}
```

Cost at this size is a few cents a month for storage; CloudFront's free tier includes 1 TB of
transfer a month.
