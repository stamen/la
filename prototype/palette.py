"""The original la.stamen.com palette and class breaks (from index.html, 2016).

Seven ColorBrewer Greys, quantile breaks on shape_area in square feet.
Buildings: small = dark, large = light.  Parcels: the reverse.
"""
import numpy as np

GREYS = ["#252525", "#525252", "#737373", "#969696", "#BDBDBD", "#D9D9D9", "#F7F7F7"]

# Upper bounds of classes 0..5; anything larger is class 6.
BREAKS = {
    "buildings": [437.62214556, 830.578055424, 1424.7760669, 1904.96072563, 2379.88198146, 3074.36767757],
    "parcels": [5043.57735, 5924.23825, 6661.9965, 7550.60995, 9615.76605, 18749.2191],
}

# Class index (small -> large) to gray.
COLORS = {
    "buildings": GREYS,            # small buildings dark
    "parcels": GREYS[::-1],        # small parcels light
}


def classify(area_ft2, layer):
    return np.searchsorted(BREAKS[layer], area_ft2, side="left").astype("uint8")


def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
