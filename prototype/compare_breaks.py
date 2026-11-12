"""Render candidate class breaks side by side (supersampled, like the tiles) and print class shares.

Usage (from prototype/): python compare_breaks.py docs/class_breaks_options.png
"""
import sys, numpy as np
sys.path.insert(0, ".")  # run from prototype/
from PIL import Image, ImageDraw, ImageFont
from palette import BREAKS_2016 as BREAKS  # the 2016 quantiles, for the "Original" column
from render import Layer, render, downsample, composite
from area import lonlat_to_merc, meters_per_pixel

TOL = 1.01
def classify(a, br, tol=1.0):
    return np.searchsorted(np.array(br) * tol, a, side="left").astype("uint8")
def shares(a, br, tol):
    c = np.bincount(classify(a, br, tol), minlength=7) / len(a) * 100
    return " ".join(f"{x:4.1f}" for x in c)

OPTIONS = [
    ("Original 2016 quantiles", BREAKS["buildings"], BREAKS["parcels"], 1.0),
    ("Recommended: 500s / thousands", [500, 1000, 1500, 2000, 2500, 3000], [5000, 6000, 7000, 8000, 10000, 20000], TOL),
    ("Alternative: rounded / one acre", [400, 800, 1400, 1900, 2400, 3000], [5000, 6000, 7500, 10000, 20000, 43560], TOL),
]
P = Layer("parcels", "data/parcels.npz"); B = Layer("buildings", "data/buildings.npz")
pa = np.load("data/parcels.npz")["area_ft2"]; ba = np.load("data/buildings.npz")["area_ft2"]
for name, bb, pb, tol in OPTIONS:
    print(f"{name}\n  buildings % {shares(ba, bb, 1.0)}\n  parcels   % {shares(pa, pb, tol)}")

# Same view at two zooms, supersampled 8x like the tile builder.
VIEWS = [(13, (-118.335, 34.068), (640, 420)), (15, (-118.343, 34.0715), (640, 420))]
SS = 8
font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
cols, pad, head = len(OPTIONS), 10, 28
W = cols * 640 + (cols - 1) * pad; H = head + len(VIEWS) * 420 + (len(VIEWS) - 1) * pad
sheet = Image.new("RGB", (W, H), "white"); d = ImageDraw.Draw(sheet)
for j, (name, bb, pb, tol) in enumerate(OPTIONS):
    d.text((j * (640 + pad), 5), name, fill="black", font=font)
    P.cls = classify(np.load("data/parcels.npz")["area_ft2"], pb, tol)
    B.cls = classify(np.load("data/buildings.npz")["area_ft2"], bb, 1.0)
    for i, (z, c, (w, h)) in enumerate(VIEWS):
        cx, cy = lonlat_to_merc(*c); mpp = meters_per_pixel(z) / SS
        img = render([P, B], z, cx - w * SS / 2 * mpp, cy + h * SS / 2 * mpp, w * SS, h * SS, antialias=False, scale_mpp=mpp)
        rgb = composite(downsample(img, SS), "#40E0D0")
        sheet.paste(Image.fromarray(rgb), (j * (640 + pad), head + i * (420 + pad)))
sheet.save(sys.argv[1])
print("wrote", sys.argv[1])
