"""Dominant colour of a detected object.

Only reached behind `--color`; nothing else in the pipeline imports it, so the
`scikit-learn` cost is paid only when the user asks for it.

Two decisions live here and nowhere else (spec, "Boundaries and seams"): the
clustering and the palette of names. The sample is taken from the central third
of the box because the edges of a box always touch background, which would
otherwise win the vote on thin objects.
"""

from __future__ import annotations

import cv2
import numpy as np
from sklearn.cluster import KMeans

Bbox = tuple[float, float, float, float]

# Clustering. Three clusters separate the object from the shading and the
# leftover background inside the crop without paying for more centroids.
_CLUSTERS = 3
_MAX_SAMPLE_PIXELS = 4096  # enough for a stable vote, cheap on a CPU-only box
_RANDOM_STATE = 0  # same crop must always give the same name
_KMEANS_RESTARTS = 4

# Where the sample comes from: the middle third of the box in both axes.
_CENTRAL_FRACTION = 1.0 / 3.0

# Palette. Hues are OpenCV's 0..179 half-degrees; each entry is the upper bound
# of the band, walked in order. Red wraps around, so it closes the list too.
_HUE_BANDS = (
    (8, "red"),
    (20, "orange"),
    (33, "yellow"),
    (78, "green"),
    (96, "cyan"),
    (130, "blue"),
    (150, "purple"),
    (170, "pink"),
    (180, "red"),
)

# Achromatic and dark cases, decided before the hue is consulted.
_GREY_SATURATION = 40  # below this a pixel carries no usable hue
_BLACK_VALUE = 55
_WHITE_VALUE = 200
_BROWN_MAX_HUE = 25  # a dark orange reads as brown, not orange
_BROWN_MAX_VALUE = 130


def dominant_color(image: np.ndarray, bbox: Bbox) -> str:
    """Return the dominant colour name inside `bbox` as a palette name.

    `image` is a BGR frame and `bbox` is (x1, y1, x2, y2) in its pixels. Raises
    `ValueError` when the box lies outside the image or is too small to sample.
    """
    crop = _central_third(image, bbox)
    pixels = _sample(crop)
    return _name(_dominant_bgr(pixels))


def _central_third(image: np.ndarray, bbox: Bbox) -> np.ndarray:
    """Crop the middle third of the box, clamped to the image."""
    height, width = image.shape[:2]
    x1, y1, x2, y2 = (float(value) for value in bbox)
    box_width = x2 - x1
    box_height = y2 - y1
    if box_width <= 0 or box_height <= 0:
        raise ValueError(f"bbox must have positive size, got {bbox!r}")

    inset_x = box_width * (1.0 - _CENTRAL_FRACTION) / 2.0
    inset_y = box_height * (1.0 - _CENTRAL_FRACTION) / 2.0
    left = max(int(round(x1 + inset_x)), 0)
    top = max(int(round(y1 + inset_y)), 0)
    right = min(int(round(x2 - inset_x)), width)
    bottom = min(int(round(y2 - inset_y)), height)

    if right <= left or bottom <= top:
        raise ValueError(f"bbox has no pixels inside the image, got {bbox!r}")
    return image[top:bottom, left:right]


def _sample(crop: np.ndarray) -> np.ndarray:
    """Flatten the crop to a pixel list, thinned to a size KMeans likes."""
    pixels = crop.reshape(-1, crop.shape[-1]).astype(np.float64)
    if pixels.shape[0] > _MAX_SAMPLE_PIXELS:
        step = pixels.shape[0] // _MAX_SAMPLE_PIXELS + 1
        pixels = pixels[::step]
    return pixels


def _dominant_bgr(pixels: np.ndarray) -> tuple[int, int, int]:
    """Cluster the pixels and return the centre of the most populated cluster.

    A flat crop holds fewer distinct colours than clusters, so the count is
    capped by what is actually there -- otherwise KMeans warns on every call.
    """
    distinct = np.unique(pixels, axis=0).shape[0]
    clusters = min(_CLUSTERS, distinct)
    model = KMeans(
        n_clusters=clusters,
        n_init=_KMEANS_RESTARTS,
        random_state=_RANDOM_STATE,
    ).fit(pixels)

    counts = np.bincount(model.labels_, minlength=clusters)
    centre = model.cluster_centers_[int(np.argmax(counts))]
    blue, green, red = (int(round(float(value))) for value in centre[:3])
    return blue, green, red


def _name(bgr: tuple[int, int, int]) -> str:
    """Map one BGR colour onto the palette.

    Saturation and value are read first: a grey pixel has a hue, but it means
    nothing, and a dark orange is what everyone calls brown.
    """
    patch = np.uint8([[list(bgr)]])
    hue, saturation, value = (
        int(channel) for channel in cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)[0][0]
    )

    if value <= _BLACK_VALUE:
        return "black"
    if saturation < _GREY_SATURATION:
        return "white" if value >= _WHITE_VALUE else "gray"
    if hue <= _BROWN_MAX_HUE and value <= _BROWN_MAX_VALUE:
        return "brown"

    for upper, name in _HUE_BANDS:
        if hue < upper:
            return name
    return "red"  # hue 179 wraps back onto red
