"""Tiny OSM (slippy-map) tile fetcher with on-disk cache.

Used by the in-cell "Map" plot type — fetches a small mosaic of tiles
covering the data's lat/lon bounding box, stitches them into a single
PIL image, and returns it alongside the geographic extent so matplotlib
``imshow`` can place it on a lat/lon axes.

Design intentionally minimal — no projection, no async, no rate limiting
beyond a User-Agent header. Tiles cached to disk so repeat renders are
instant. Acceptable Mercator-on-equirect distortion in Denmark
latitudes (~56°N); we trade pixel-perfect tile alignment for
implementation simplicity.
"""

from __future__ import annotations

import math
import os
from io import BytesIO
from typing import Optional, Tuple

_TILE_SIZE = 256
_USER_AGENT = "HeadAnalyser/2.0 (https://github.com/headanalyser)"
# OSM tile usage policy allows light tile use with proper User-Agent; for
# heavier use a different tile provider should be substituted.
_OSM_TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
# Half the world width in meters at the equator in EPSG:3857 (Web Mercator).
_MERC_HALF = 20037508.342789244


def _tile_to_mercator(x: float, y: float, z: int):
    """Web Mercator coordinates (meters) of the NW corner of tile (x, y) at zoom z."""
    n = 2.0 ** z
    span = 2.0 * _MERC_HALF / n
    mx = x * span - _MERC_HALF
    # Slippy-map y grows southward (y=0 is north). Mercator y grows northward,
    # so invert to convert.
    my = _MERC_HALF - y * span
    return mx, my


def _lat_lon_to_tile(lat: float, lon: float, z: int) -> Tuple[float, float]:
    """Slippy-map tile coordinates (floats) for a lat/lon at zoom z."""
    lat_rad = math.radians(lat)
    n = 2.0 ** z
    x = (lon + 180.0) / 360.0 * n
    y = (1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n
    return x, y


def _tile_to_lat_lon(x: float, y: float, z: int) -> Tuple[float, float]:
    """Lat/lon of the NW corner of tile (x, y) at zoom z."""
    n = 2.0 ** z
    lon = x / n * 360.0 - 180.0
    lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
    return lat, lon


def _pick_zoom(lon_span: float, target_px: int) -> int:
    """Highest zoom where the longitude span fits in ``target_px`` pixels.

    At zoom z the world is ``256 * 2**z`` pixels wide in longitude, so a
    span of ``span`` degrees covers ``span / 360 * 256 * 2**z`` pixels.
    We pick the largest z keeping that under target_px.
    """
    if lon_span <= 0:
        return 12
    for z in range(18, 0, -1):
        bbox_px = (lon_span / 360.0) * _TILE_SIZE * (2 ** z)
        if bbox_px <= target_px:
            return z
    return 1


def fetch_basemap(
    lat_min: float, lat_max: float,
    lon_min: float, lon_max: float,
    cache_dir: str,
    target_px: int = 800,
    timeout: float = 5.0,
) -> Tuple[Optional[object], Optional[Tuple[float, float, float, float]]]:
    """Fetch + stitch OSM tiles covering the bbox.

    Returns ``(PIL.Image, extent)`` where extent is
    ``(lon_min_extent, lon_max_extent, lat_min_extent, lat_max_extent)``
    matching matplotlib's ``imshow(extent=...)`` format. Returns
    ``(None, None)`` on any failure that prevents producing a usable
    mosaic — callers should fall back to plotting points without a
    basemap.

    Tiles are cached per-zoom in ``cache_dir`` so repeated views of the
    same area incur no network cost.
    """
    try:
        import requests
        from PIL import Image
    except Exception:
        return None, None

    if lat_min >= lat_max or lon_min >= lon_max:
        return None, None

    z = _pick_zoom(lon_max - lon_min, target_px)
    x0_f, y1_f = _lat_lon_to_tile(lat_min, lon_min, z)  # lat_min → larger y
    x1_f, y0_f = _lat_lon_to_tile(lat_max, lon_max, z)  # lat_max → smaller y
    x0, x1 = int(math.floor(x0_f)), int(math.ceil(x1_f))
    y0, y1 = int(math.floor(y0_f)), int(math.ceil(y1_f))
    n_x, n_y = x1 - x0, y1 - y0
    if n_x <= 0 or n_y <= 0 or n_x * n_y > 64:
        # Bail on absurd tile counts (likely zoom miscalculation).
        return None, None

    try:
        os.makedirs(cache_dir, exist_ok=True)
    except Exception:
        return None, None

    mosaic = Image.new("RGBA", (n_x * _TILE_SIZE, n_y * _TILE_SIZE))
    fetched_any = False
    session = requests.Session()
    session.headers.update({"User-Agent": _USER_AGENT})
    for ix in range(n_x):
        for iy in range(n_y):
            tx, ty = x0 + ix, y0 + iy
            cache_path = os.path.join(cache_dir, f"{z}_{tx}_{ty}.png")
            tile_img = None
            if os.path.exists(cache_path):
                try:
                    tile_img = Image.open(cache_path).convert("RGBA")
                except Exception:
                    tile_img = None
            if tile_img is None:
                try:
                    r = session.get(
                        _OSM_TILE_URL.format(z=z, x=tx, y=ty),
                        timeout=timeout,
                    )
                    r.raise_for_status()
                    tile_img = Image.open(BytesIO(r.content)).convert("RGBA")
                    try:
                        tile_img.save(cache_path)
                    except Exception:
                        pass
                except Exception:
                    continue
            if tile_img is not None:
                mosaic.paste(tile_img, (ix * _TILE_SIZE, iy * _TILE_SIZE))
                fetched_any = True

    if not fetched_any:
        return None, None

    # Mercator extent of the stitched mosaic — NW corner of tile (x0, y0)
    # is (mx_min, my_max), SE corner is (mx_max, my_min) in EPSG:3857.
    mx_min, my_max = _tile_to_mercator(x0, y0, z)
    mx_max, my_min = _tile_to_mercator(x1, y1, z)
    # matplotlib imshow extent = (xmin, xmax, ymin, ymax) with origin='upper'.
    extent = (mx_min, mx_max, my_min, my_max)
    return mosaic, extent
