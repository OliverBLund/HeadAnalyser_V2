"""
Placeholder geology layer provider interfaces for cross-section and map overlays.

This module is intentionally lightweight so the UI can integrate against a stable
API before a real Denmark geology backend is connected.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional
import re
import numpy as np


@dataclass
class GeologySegment:
    """One geology unit along a transect distance interval."""

    start_m: float
    end_m: float
    layer_code: str
    layer_name: str
    color: str


class GeologyLayerProvider:
    """Base interface for soil/geology providers."""

    provider_name = "base"

    def sample_transect(self, distances_m: np.ndarray, context: Optional[Dict] = None) -> Dict:
        """Return geology segments over the transect.

        Response format:
            {
                "provider": str,
                "available": bool,
                "segments": List[GeologySegment],
                "notes": List[str],
            }
        """
        return {
            "provider": self.provider_name,
            "available": False,
            "segments": [],
            "notes": ["No geology provider configured."],
        }


class PlaceholderDenmarkGeologyProvider(GeologyLayerProvider):
    """Mock provider for UI prototyping until real Denmark data integration."""

    provider_name = "placeholder-denmark"

    _LAYER_PALETTE = [
        ("QH", "Quaternary sand", "#d4b483"),
        ("QC", "Glacial clay", "#9a7b6f"),
        ("TS", "Till / mixed sediments", "#7f9aa3"),
        ("LS", "Limestone/chalk", "#b7bfd1"),
    ]

    def sample_transect(self, distances_m: np.ndarray, context: Optional[Dict] = None) -> Dict:
        notes: List[str] = [
            "Placeholder geology strip (not from a real database yet).",
        ]
        context = context or {}
        if bool(context.get("has_depth_data", False)):
            notes.append("Depth columns detected in dataset.")
        else:
            notes.append("No depth columns detected; showing conceptual layers only.")

        d = np.asarray(distances_m, dtype=float)
        if d.size < 2 or not np.isfinite(d).any():
            return {
                "provider": self.provider_name,
                "available": False,
                "segments": [],
                "notes": notes + ["Transect distances were invalid."],
            }

        start = float(np.nanmin(d))
        end = float(np.nanmax(d))
        total = max(1e-9, end - start)

        # Build deterministic pseudo-geology zones across distance.
        cuts = np.array([0.0, 0.22, 0.48, 0.73, 1.0], dtype=float) * total + start
        segments: List[GeologySegment] = []
        for i in range(len(cuts) - 1):
            code, name, color = self._LAYER_PALETTE[i % len(self._LAYER_PALETTE)]
            segments.append(
                GeologySegment(
                    start_m=float(cuts[i]),
                    end_m=float(cuts[i + 1]),
                    layer_code=code,
                    layer_name=name,
                    color=color,
                )
            )

        return {
            "provider": self.provider_name,
            "available": True,
            "segments": segments,
            "notes": notes,
        }


def get_default_geology_provider() -> GeologyLayerProvider:
    """Return the current default provider (placeholder for now)."""
    return PlaceholderDenmarkGeologyProvider()


class GeoDkSvgSurfaceGeologyProvider(GeologyLayerProvider):
    """
    Extract a 1D geology strip from the latest Geo.dk SVG.

    This is deliberately a "good enough" backend wiring for plot integration:
    - parse SVG polygons and their GeoUnit class (geounit-<id>/geoenhed-<id>)
    - determine the shallowest polygon at each x-bin (smallest minY) as "surface unit"
    - compress bins into GeologySegments over distance [m]
    """

    provider_name = "geo.dk-svg-surface"

    def __init__(self) -> None:
        self._segments: List[GeologySegment] = []
        self._available: bool = False
        self._notes: List[str] = ["Geo.dk provider not populated yet."]
        self._path_length_m: float = 0.0

    def update_from_geodk_payload(self, payload: Dict) -> None:
        svg = str(payload.get("svg") or "")
        diag = payload.get("diag") if isinstance(payload.get("diag"), dict) else {}
        req = diag.get("request") if isinstance(diag, dict) else {}
        try:
            path_len = float(req.get("path_length_m") or 0.0) if isinstance(req, dict) else 0.0
        except Exception:
            path_len = 0.0
        self.update_from_svg(svg_text=svg, path_length_m=float(path_len), model_obj=None)

    def update_from_svg(self, *, svg_text: str, path_length_m: float, model_obj: object = None) -> None:
        from core.geodk_api import extract_geounit_colors

        svg = str(svg_text or "")
        self._path_length_m = float(path_length_m or 0.0)
        if not svg.strip() or not np.isfinite(self._path_length_m) or self._path_length_m <= 0.0:
            self._segments = []
            self._available = False
            self._notes = ["Geo.dk SVG or path length missing."]
            return

        # viewBox width for x->distance mapping
        vbw = None
        try:
            m = re.search(r"viewBox=['\\\"]\\s*0\\s+0\\s+([0-9.]+)\\s+([0-9.]+)", svg, flags=re.I)
            if m:
                vbw = float(m.group(1))
        except Exception:
            vbw = None
        if vbw is None or not np.isfinite(vbw) or vbw <= 0:
            vbw = 1000.0

        # Color map by GeoUnit class.
        color_map = extract_geounit_colors(svg)

        # Parse polygons with class + points. Attribute order varies in Geo.dk SVG,
        # so we parse full polygon tags first and then extract class/points from tag text.
        poly_tag_rx = re.compile(r"<polygon\\b[^>]*>", flags=re.I)
        points_rx = re.compile(r"\\bpoints=['\\\"]([^'\\\"]+)['\\\"]", flags=re.I)
        class_rx = re.compile(r"\\bclass=['\\\"]([^'\\\"]+)['\\\"]", flags=re.I)
        geounit_rx = re.compile(r"\\b(?:geounit|geoenhed)-(\\d+)\\b", flags=re.I)

        polys = []
        for m in poly_tag_rx.finditer(svg):
            tag = str(m.group(0) or "")
            pm = points_rx.search(tag)
            if not pm:
                continue
            pts_raw = str(pm.group(1) or "")
            cm = class_rx.search(tag)
            cls = str(cm.group(1) or "") if cm else ""
            gm = geounit_rx.search(cls)
            if not gm:
                continue
            gid = str(gm.group(1))
            xs = []
            ys = []
            for part in pts_raw.split():
                if "," not in part:
                    continue
                a, b = part.split(",", 1)
                try:
                    x = float(a)
                    y = float(b)
                except Exception:
                    continue
                if np.isfinite(x) and np.isfinite(y):
                    xs.append(float(x))
                    ys.append(float(y))
            if len(xs) < 3 or len(ys) < 3:
                continue
            polys.append(
                {
                    "gid": gid,
                    "minx": float(min(xs)),
                    "maxx": float(max(xs)),
                    "miny": float(min(ys)),
                }
            )

        if not polys:
            self._segments = []
            self._available = False
            self._notes = ["Geo.dk SVG contained no geounit polygons."]
            return

        # Surface unit by binning along x (shallowest polygon at x).
        bins = 320
        xs = np.linspace(0.0, float(vbw), int(max(80, bins)))
        gids = []
        for x in xs:
            best = None
            best_miny = None
            for p in polys:
                if x < p["minx"] or x > p["maxx"]:
                    continue
                my = float(p["miny"])
                if best_miny is None or my < best_miny:
                    best_miny = my
                    best = p
            gids.append(str(best["gid"]) if best is not None else "")

        # Compress into segments and map to distance.
        segs: List[GeologySegment] = []
        last = None
        run_start = 0
        for i, gid in enumerate(gids + ["__END__"]):
            if last is None:
                last = gid
                run_start = i
                continue
            if gid == last:
                continue
            if last and last != "__END__":
                x0 = float(xs[run_start])
                x1 = float(xs[min(i, len(xs) - 1)])
                d0 = (x0 / float(vbw)) * float(self._path_length_m)
                d1 = (x1 / float(vbw)) * float(self._path_length_m)
                col = str(color_map.get(str(last), "#8b8b93"))
                segs.append(
                    GeologySegment(
                        start_m=float(min(d0, d1)),
                        end_m=float(max(d0, d1)),
                        layer_code=str(last),
                        layer_name=f"GeoUnit {last}",
                        color=col,
                    )
                )
            last = gid
            run_start = i

        self._segments = segs
        self._available = bool(segs)
        self._notes = ["Geo.dk SVG-derived surface geology strip (approximate)."]

    def sample_transect(self, distances_m: np.ndarray, context: Optional[Dict] = None) -> Dict:
        if not self._available or not self._segments:
            return {
                "provider": self.provider_name,
                "available": False,
                "segments": [],
                "notes": list(self._notes),
            }
        return {
            "provider": self.provider_name,
            "available": True,
            "segments": list(self._segments),
            "notes": list(self._notes),
        }
