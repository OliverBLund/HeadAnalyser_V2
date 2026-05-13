"""Coordinate transformation helpers for HeadAnalyser."""

import pyproj


_UTM32_TO_WGS84 = pyproj.Transformer.from_crs(
    "epsg:25832",
    "epsg:4326",
    always_xy=True,
)

_WGS84_TO_UTM32 = pyproj.Transformer.from_crs(
    "epsg:4326",
    "epsg:25832",
    always_xy=True,
)


def utm32_to_wgs84(x, y):
    """Convert UTM32 EUREF89 (EPSG:25832) to WGS84 (lon, lat)."""
    lon, lat = _UTM32_TO_WGS84.transform(float(x), float(y))
    return float(lon), float(lat)


def wgs84_to_utm32(lon, lat):
    """Convert WGS84 (lon, lat) to UTM32 EUREF89 (x, y)."""
    x, y = _WGS84_TO_UTM32.transform(float(lon), float(lat))
    return float(x), float(y)
