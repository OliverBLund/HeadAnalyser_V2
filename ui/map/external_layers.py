"""External GIS layer loading helpers for map overlays."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


_GEOJSON_GEOMETRY_TYPES = {
    "Point",
    "MultiPoint",
    "LineString",
    "MultiLineString",
    "Polygon",
    "MultiPolygon",
    "GeometryCollection",
}

_EXTERNAL_LAYER_COLOR_PALETTE = (
    "#22c55e",
    "#0ea5e9",
    "#f59e0b",
    "#ef4444",
    "#a855f7",
    "#14b8a6",
)


class ExternalLayerError(RuntimeError):
    """Raised when an external GIS layer cannot be loaded or normalized."""


def build_external_layer_style(index: int) -> Dict[str, Any]:
    """Return a deterministic style dict for an external overlay layer."""
    color = _EXTERNAL_LAYER_COLOR_PALETTE[index % len(_EXTERNAL_LAYER_COLOR_PALETTE)]
    return {
        "color": color,
        "line_width": 2.0,
        "line_opacity": 0.9,
        "fill_opacity": 0.12,
        "point_size": 8.0,
    }


def load_external_layer_payload(file_path: str) -> Dict[str, Any]:
    """
    Load GeoJSON or Shapefile into a normalized FeatureCollection payload.

    Supported formats:
    - `.geojson`, `.json`
    - `.shp` (requires optional `geopandas`)
    """
    path = Path(str(file_path)).expanduser()
    if not path.exists():
        raise ExternalLayerError(f"Layer file does not exist: {path}")

    suffix = path.suffix.lower()
    if suffix in {".geojson", ".json"}:
        raw = _load_geojson_file(path)
    elif suffix == ".shp":
        raw = _load_shapefile(path)
    else:
        raise ExternalLayerError(
            f"Unsupported layer format '{suffix}'. Use .geojson/.json or .shp."
        )

    feature_collection = _normalize_geojson(raw)
    feature_count = len(feature_collection.get("features", []))
    if feature_count <= 0:
        raise ExternalLayerError("Layer contains no renderable features.")

    return {
        # Default layer label should match the actual file name (incl. extension).
        "name": path.name,
        "source_path": str(path),
        "feature_collection": feature_collection,
        "feature_count": int(feature_count),
        "source_suffix": suffix,
        "geometry_kind": infer_feature_collection_geometry_kind(feature_collection),
        "geometry_types": sorted(list(_collect_geometry_types(feature_collection))),
    }


def normalize_external_layer_style(style: Any, fallback_color: str = "#22c55e") -> Dict[str, Any]:
    """Normalize style payload from Python/JS into stable map-layer style keys."""
    src = style if isinstance(style, dict) else {}
    color = str(src.get("color") or src.get("stroke_color") or fallback_color)
    line_width = _clamp_float(src.get("line_width", src.get("weight", 2.0)), 1.0, 8.0, 2.0)
    line_opacity = _clamp_float(src.get("line_opacity", src.get("opacity", 0.9)), 0.05, 1.0, 0.9)
    fill_opacity = _clamp_float(src.get("fill_opacity", src.get("fillOpacity", 0.12)), 0.0, 1.0, 0.12)
    point_size = _clamp_float(src.get("point_size", src.get("radius", 8.0)), 2.0, 24.0, 8.0)
    return {
        "color": color,
        "line_width": float(line_width),
        "line_opacity": float(line_opacity),
        "fill_opacity": float(fill_opacity),
        "point_size": float(point_size),
    }


def infer_feature_collection_geometry_kind(feature_collection: Dict[str, Any]) -> str:
    """Return dominant geometry kind: point|line|polygon|mixed|other."""
    kinds = _collect_geometry_types(feature_collection)
    grouped = set()
    for g in kinds:
        if g in {"Point", "MultiPoint"}:
            grouped.add("point")
        elif g in {"LineString", "MultiLineString"}:
            grouped.add("line")
        elif g in {"Polygon", "MultiPolygon"}:
            grouped.add("polygon")
        elif g == "GeometryCollection":
            grouped.add("mixed")
        else:
            grouped.add("other")

    if not grouped:
        return "other"
    if len(grouped) == 1:
        return next(iter(grouped))
    if grouped.issubset({"point", "line", "polygon"}):
        return "mixed"
    if "mixed" in grouped:
        return "mixed"
    return "other"


def _load_geojson_file(path: Path) -> Dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = path.read_text(encoding="latin-1")
    except Exception as exc:
        raise ExternalLayerError(f"Failed to read GeoJSON file: {path}") from exc

    try:
        return json.loads(text)
    except Exception as exc:
        raise ExternalLayerError(f"Invalid JSON in file: {path}") from exc


def _load_shapefile(path: Path) -> Dict[str, Any]:
    try:
        import geopandas as gpd
    except Exception as exc:
        raise ExternalLayerError(
            "Loading .shp requires optional dependency 'geopandas'. "
            "Install it to enable shapefile loading."
        ) from exc

    try:
        gdf = gpd.read_file(str(path))
    except Exception as exc:
        raise ExternalLayerError(f"Failed to read shapefile: {path}") from exc

    if gdf is None or gdf.empty:
        raise ExternalLayerError(f"Shapefile has no rows: {path}")

    try:
        if getattr(gdf, "crs", None):
            gdf = gdf.to_crs(epsg=4326)
    except Exception as exc:
        raise ExternalLayerError(
            "Failed to reproject shapefile to EPSG:4326."
        ) from exc

    try:
        return json.loads(gdf.to_json())
    except Exception as exc:
        raise ExternalLayerError("Failed to convert shapefile to GeoJSON.") from exc


def _normalize_geojson(raw: Any) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        raise ExternalLayerError("Layer payload must be a JSON object.")

    obj_type = str(raw.get("type", "")).strip()
    if obj_type == "FeatureCollection":
        features = _coerce_feature_list(raw.get("features", []))
    elif obj_type == "Feature":
        features = _coerce_feature_list([raw])
    elif obj_type in _GEOJSON_GEOMETRY_TYPES:
        features = _coerce_feature_list(
            [{"type": "Feature", "properties": {}, "geometry": raw}]
        )
    else:
        raise ExternalLayerError(
            "Unsupported GeoJSON object type. Expected FeatureCollection, Feature, or geometry."
        )

    if not features:
        raise ExternalLayerError("No valid features found in layer.")

    return {
        "type": "FeatureCollection",
        "features": features,
    }


def _coerce_feature_list(features: Any) -> List[Dict[str, Any]]:
    if not isinstance(features, list):
        raise ExternalLayerError("GeoJSON features must be a list.")

    out: List[Dict[str, Any]] = []
    for item in features:
        if not isinstance(item, dict):
            continue
        if str(item.get("type", "")).strip() != "Feature":
            continue
        geometry = item.get("geometry")
        if not isinstance(geometry, dict):
            continue
        if str(geometry.get("type", "")).strip() not in _GEOJSON_GEOMETRY_TYPES:
            continue
        out.append(
            {
                "type": "Feature",
                "properties": item.get("properties") if isinstance(item.get("properties"), dict) else {},
                "geometry": geometry,
            }
        )
    return out


def _collect_geometry_types(feature_collection: Any) -> set:
    kinds = set()
    if not isinstance(feature_collection, dict):
        return kinds
    features = feature_collection.get("features")
    if not isinstance(features, list):
        return kinds
    for feat in features:
        if not isinstance(feat, dict):
            continue
        geom = feat.get("geometry")
        if not isinstance(geom, dict):
            continue
        gtype = str(geom.get("type", "")).strip()
        if gtype:
            kinds.add(gtype)
    return kinds


def _clamp_float(value: Any, lo: float, hi: float, default: float) -> float:
    try:
        val = float(value)
    except Exception:
        val = float(default)
    if val < lo:
        return float(lo)
    if val > hi:
        return float(hi)
    return float(val)
