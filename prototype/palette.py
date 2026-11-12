"""The la.stamen.com palette and class breaks.

Seven ColorBrewer Greys (the 2016 palette), classed on area in square feet.
Buildings: small = dark, large = light.  Parcels: the reverse.

Breaks are round numbers chosen in 2026 to read cleanly in a legend while
staying close to the 2016 quantiles (which are kept below for reference).
Each break is an inclusive upper bound: class k holds areas "up to" BREAKS[k].

Parcels get 1% of slack on each break. LA lots cluster at standard surveyed
sizes (2-3% of parcels sit within 0.5% of exactly 5,000, 6,000 or 7,500 sq ft),
and their computed areas wobble around the nominal value; without the slack a
break at 5,000 would split identical lots on one block between two grays.
Buildings have no such clustering, so they get none.
"""
import numpy as np

GREYS = ["#252525", "#525252", "#737373", "#969696", "#BDBDBD", "#D9D9D9", "#F7F7F7"]

# Upper bounds of classes 0..5 (sq ft); anything larger is class 6.
BREAKS = {
    "buildings": [400, 800, 1400, 1800, 2400, 3000],
    "parcels": [5000, 6000, 7000, 8000, 10000, 20000],
}
SLACK = {"buildings": 0.0, "parcels": 0.01}

# The 2016 CARTO quantile breaks, for reference and comparisons.
BREAKS_2016 = {
    "buildings": [437.62214556, 830.578055424, 1424.7760669, 1904.96072563, 2379.88198146, 3074.36767757],
    "parcels": [5043.57735, 5924.23825, 6661.9965, 7550.60995, 9615.76605, 18749.2191],
}

# Class index (small -> large) to gray.
COLORS = {
    "buildings": GREYS,            # small buildings dark
    "parcels": GREYS[::-1],        # small parcels light
}


def classify(area_ft2, layer, breaks=None, slack=None):
    br = np.asarray(BREAKS[layer] if breaks is None else breaks, dtype="float64")
    s = SLACK[layer] if slack is None else slack
    return np.searchsorted(br * (1 + s), area_ft2, side="left").astype("uint8")


def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
