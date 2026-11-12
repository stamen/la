"""Prototype study area and Web Mercator helpers."""
import math

R = 6378137.0
ORIGIN = math.pi * R          # half the Web Mercator world width, in meters
TILE = 256

# Study area: a 1024 x 640 px window at zoom 11, centered near Koreatown.
# That is ~65 x 40 km on the ground and covers most of the central LA basin.
CENTER = (-118.30, 34.06)
BASE_ZOOM = 11
BASE_SIZE = (1024, 640)


def lonlat_to_merc(lon, lat):
    x = math.radians(lon) * R
    y = math.log(math.tan(math.pi / 4 + math.radians(lat) / 2)) * R
    return x, y


def merc_to_lonlat(x, y):
    return math.degrees(x / R), math.degrees(2 * math.atan(math.exp(y / R)) - math.pi / 2)


def meters_per_pixel(z):
    return 2 * ORIGIN / (TILE * 2 ** z)


def merc_window(center=CENTER, zoom=BASE_ZOOM, size=BASE_SIZE):
    """(xmin, ymin, xmax, ymax) in Web Mercator meters."""
    cx, cy = lonlat_to_merc(*center)
    hw = size[0] / 2 * meters_per_pixel(zoom)
    hh = size[1] / 2 * meters_per_pixel(zoom)
    return cx - hw, cy - hh, cx + hw, cy + hh


def lonlat_window(**kw):
    x0, y0, x1, y1 = merc_window(**kw)
    w, s = merc_to_lonlat(x0, y0)
    e, n = merc_to_lonlat(x1, y1)
    return w, s, e, n


DEFAULT_BBOX = tuple(round(v, 5) for v in lonlat_window())
