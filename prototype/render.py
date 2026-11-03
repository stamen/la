"""Coverage-anti-aliased polygon renderer, imitating Mapnik/AGG's look.

Every polygon is drawn as its own path with analytic (coverage) anti-aliasing
and source-over blending in sRGB space, the way Mapnik drew CARTO tiles.
Consequences we want to keep:
  * sub-pixel features still shade their pixel in proportion to their area;
  * neighbouring polygons each anti-alias their shared edge, so a little of
    the background leaks through every boundary ("conflation" seams).  At low
    zoom the density of those seams is part of the texture.

The output is transparent RGBA (premultiplied), so the page's CSS background
(turquoise by default) shows through streets and seams, as it did originally.
"""
import numpy as np
import skia

from palette import COLORS, hex_to_rgb
from area import meters_per_pixel


class Layer:
    def __init__(self, name, npz_path):
        d = np.load(npz_path)
        self.name = name
        self.xy = d["xy"]
        self.ring_off = d["ring_off"]
        self.poly_ring = d["poly_ring"]
        self.bbox = d["bbox"]
        self.cls = d["cls"]
        self.paints = []
        for hexcol in COLORS[name]:
            r, g, b = hex_to_rgb(hexcol)
            self.paints.append(skia.Paint(Color=skia.Color(r, g, b), Style=skia.Paint.kFill_Style))


def render(layers, zoom, x0, y1, width, height, antialias=True, scale_mpp=None):
    """Render a window whose top-left corner is mercator (x0, y1).

    Returns an (height, width, 4) uint8 premultiplied RGBA array.
    """
    mpp = scale_mpp or meters_per_pixel(zoom)
    info = skia.ImageInfo.Make(width, height, skia.kRGBA_8888_ColorType, skia.kPremul_AlphaType)
    surf = skia.Surface.MakeRaster(info)
    canvas = surf.getCanvas()
    canvas.clear(skia.ColorTRANSPARENT)

    wx1 = x0 + width * mpp
    wy0 = y1 - height * mpp
    for layer in layers:
        for p in layer.paints:
            p.setAntiAlias(antialias)
        b = layer.bbox
        visible = np.nonzero((b[:, 0] <= wx1) & (b[:, 2] >= x0) & (b[:, 1] <= y1) & (b[:, 3] >= wy0))[0]
        xy, ro, pr, cls, paints = layer.xy, layer.ring_off, layer.poly_ring, layer.cls, layer.paints
        for p in visible:
            path = skia.Path()
            for r in range(pr[p], pr[p + 1]):
                pts = (xy[ro[r]:ro[r + 1]] - (x0, y1)) * (1.0 / mpp, -1.0 / mpp)
                path.addPoly([skia.Point(px, py) for px, py in pts.tolist()], True)
            canvas.drawPath(path, paints[cls[p]])
    # skia-python's toarray() hands back *unpremultiplied* RGBA; premultiply so
    # downsample() and composite() can average and blend correctly.
    a = surf.toarray().astype(np.float32)
    a[..., :3] *= a[..., 3:4] / 255.0
    return np.clip(a + 0.5, 0, 255).astype(np.uint8)


def downsample(rgba, factor):
    """Box-filter a premultiplied RGBA image by an integer factor (sRGB-space average)."""
    h, w, _ = rgba.shape
    a = rgba[: h - h % factor, : w - w % factor].astype(np.float32)
    a = a.reshape(h // factor, factor, w // factor, factor, 4).mean(axis=(1, 3))
    return np.clip(a + 0.5, 0, 255).astype(np.uint8)


def composite(rgba, background):
    """Flatten premultiplied RGBA over a solid background color, returning RGB."""
    bg = np.array(hex_to_rgb(background) if isinstance(background, str) else background, np.float32)
    a = rgba[..., 3:4].astype(np.float32) / 255.0
    out = rgba[..., :3].astype(np.float32) + bg * (1 - a)
    return np.clip(out + 0.5, 0, 255).astype(np.uint8)
