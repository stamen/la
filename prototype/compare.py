"""Build side-by-side comparison sheets from experiment.py output.

  out/sheet_crops.png   rows = zoom 11..13, columns = native / pyramid / aliased,
                        each a same-pixel-size crop at the window center
  out/full_z11_<bg>.png the whole native z11 window over a background color
"""
import argparse

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from render import composite

METHODS = ["native", "pyramid", "aliased"]
LABELS = {
    "native": "native coverage AA (Mapnik-like)",
    "pyramid": "rendered at z15, averaged down",
    "aliased": "no AA (GPU-like approximation)",
}


def load_premul(path):
    im = np.asarray(Image.open(path).convert("RGBA")).astype(np.float32)
    a = im[..., 3:4] / 255.0
    return np.dstack([im[..., :3] * a, im[..., 3:4]]).clip(0, 255).astype(np.uint8)


def font(size):
    for f in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",):
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            pass
    return ImageFont.load_default()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out")
    ap.add_argument("--bg", default="#40E0D0")  # CSS turquoise
    ap.add_argument("--crop", type=int, nargs=2, default=[480, 360])
    args = ap.parse_args()
    cw, ch = args.crop
    pad, head, side = 12, 30, 70
    zooms = [11, 12, 13]

    W = side + len(METHODS) * (cw + pad)
    H = head + len(zooms) * (ch + pad)
    sheet = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(sheet)
    f = font(15)
    for j, m in enumerate(METHODS):
        d.text((side + j * (cw + pad), 8), LABELS[m], fill="black", font=f)
    for i, z in enumerate(zooms):
        d.text((8, head + i * (ch + pad) + ch // 2 - 8), f"z{z}", fill="black", font=font(20))
        for j, m in enumerate(METHODS):
            im = load_premul(f"{args.out}/{m}_z{z}.png")
            h, w, _ = im.shape
            crop = im[(h - ch) // 2:(h + ch) // 2, (w - cw) // 2:(w + cw) // 2]
            sheet.paste(Image.fromarray(composite(crop, args.bg)), (side + j * (cw + pad), head + i * (ch + pad)))
    sheet.save(f"{args.out}/sheet_crops.png")

    for m in METHODS:
        im = load_premul(f"{args.out}/{m}_z11.png")
        Image.fromarray(composite(im, args.bg)).save(f"{args.out}/full_z11_{m}.png")
    print("wrote", f"{args.out}/sheet_crops.png")


if __name__ == "__main__":
    main()
