"""
Pure functions for mapping borehole positions (UTM32) onto Geo.dk cross-section SVG coordinates.

The Geo.dk SVG is treated as an opaque blob; we extract a few signals:
- SVG viewBox (for overlay SVG sizing)
- axis tick labels (best mapping)
- surface polyline (best surface Y at a given X)
- fallback mapping from surface span and ZMin/ZMax
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any

from .geodk_api import project_point_to_path


@dataclass(frozen=True)
class GeoDkOverlayResult:
    items: list[dict]
    viewbox_w: float
    viewbox_h: float
    diag: dict[str, Any]


def _parse_viewbox_wh(svg_text: str) -> tuple[float, float] | None:
    m = re.search(r"viewBox=['\"]\s*0\s+0\s+([0-9.]+)\s+([0-9.]+)\s*['\"]", svg_text or "", flags=re.I)
    if not m:
        m = re.search(
            r"viewBox=['\"]\s*([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s*['\"]",
            svg_text or "",
            flags=re.I,
        )
        if not m:
            return None
        try:
            return float(m.group(3)), float(m.group(4))
        except Exception:
            return None
    try:
        return float(m.group(1)), float(m.group(2))
    except Exception:
        return None


def _linfit(pairs: list[tuple[float, float]]) -> tuple[float, float] | None:
    # Fit y = a*x + b.
    if len(pairs) < 2:
        return None
    sx = sy = sxx = sxy = 0.0
    n = 0
    for x, y in pairs:
        if not math.isfinite(x) or not math.isfinite(y):
            continue
        sx += x
        sy += y
        sxx += x * x
        sxy += x * y
        n += 1
    if n < 2:
        return None
    denom = (n * sxx - sx * sx)
    if abs(denom) < 1e-12:
        return None
    a = (n * sxy - sx * sy) / denom
    b = (sy - a * sx) / float(n)
    return float(a), float(b)


def _cluster_by_axis(items: list[tuple[float, float, float]], *, axis: str, tol: float) -> list[list[tuple[float, float, float]]]:
    """Cluster label triplets by near-equal x or y (single-link)."""
    if axis not in {"x", "y"}:
        return []
    if not items:
        return []
    idx = 0 if axis == "x" else 1
    arr = sorted(items, key=lambda t: float(t[idx]))
    groups: list[list[tuple[float, float, float]]] = []
    cur: list[tuple[float, float, float]] = [arr[0]]
    for it in arr[1:]:
        if abs(float(it[idx]) - float(cur[-1][idx])) <= float(tol):
            cur.append(it)
        else:
            groups.append(cur)
            cur = [it]
    groups.append(cur)
    return groups


def _axis_fits(svg_text: str) -> tuple[tuple[float, float] | None, tuple[float, float] | None]:
    """
    Returns (x_from_dist, y_from_z):
    - x_from_dist: x = ax*d + bx
    - y_from_z: y = ay*z + by
    """
    rx = re.compile(
        r"<text\b[^>]*\bx=['\"]?([0-9.]+)['\"]?[^>]*\by=['\"]?([0-9.]+)['\"]?[^>]*>(-?\d+(?:\.\d+)?)</text>",
        re.I,
    )
    labels: list[tuple[float, float, float]] = []
    for m in rx.finditer(svg_text or ""):
        try:
            tx = float(m.group(1))
            ty = float(m.group(2))
            val = float(m.group(3))
        except Exception:
            continue
        labels.append((float(tx), float(ty), float(val)))

    x_pairs: list[tuple[float, float]] = []
    y_pairs: list[tuple[float, float]] = []

    # Legacy value-size heuristic (works for long transects).
    for tx, ty, val in labels:
        if abs(val) >= 200.0:
            x_pairs.append((float(val), float(tx)))
        else:
            y_pairs.append((float(val), float(ty)))

    x_fit = _linfit(x_pairs)
    y_fit = _linfit(y_pairs)

    # Fallback for short transects: infer x-axis from rows with similar y.
    if x_fit is None and len(labels) >= 2:
        best_row = None
        best_score = None
        for row in _cluster_by_axis(labels, axis="y", tol=4.0):
            if len(row) < 2:
                continue
            pairs = [(float(v), float(x)) for x, _, v in row]
            fit = _linfit(pairs)
            if fit is None:
                continue
            xs = [float(x) for x, _, _ in row]
            spread = max(xs) - min(xs) if xs else 0.0
            if spread <= 1e-9:
                continue
            # Prefer rows that look like a horizontal axis near the bottom.
            row_mean_y = sum(float(y) for _, y, _ in row) / float(len(row))
            score = (len(row), row_mean_y, spread)
            if best_score is None or score > best_score:
                best_score = score
                best_row = row
        if best_row is not None:
            x_fit = _linfit([(float(v), float(x)) for x, _, v in best_row])

    # Fallback: infer y-axis from vertical-ish columns (usually left side labels).
    if y_fit is None and len(labels) >= 2:
        best_col = None
        best_score = None
        for col in _cluster_by_axis(labels, axis="x", tol=6.0):
            if len(col) < 2:
                continue
            pairs = [(float(v), float(y)) for _, y, v in col]
            fit = _linfit(pairs)
            if fit is None:
                continue
            ys = [float(y) for _, y, _ in col]
            spread = max(ys) - min(ys) if ys else 0.0
            if spread <= 1e-9:
                continue
            col_mean_x = sum(float(x) for x, _, _ in col) / float(len(col))
            # Prefer columns with many labels close to left side (smaller x).
            score = (len(col), -col_mean_x, spread)
            if best_score is None or score > best_score:
                best_score = score
                best_col = col
        if best_col is not None:
            y_fit = _linfit([(float(v), float(y)) for _, y, v in best_col])

    return x_fit, y_fit


def _surface_polyline(svg_text: str) -> list[tuple[float, float]]:
    tag_rx = re.compile(r"<polyline\b[^>]*>", flags=re.I)
    points_rx = re.compile(r"\bpoints=['\"]([^'\"]+)['\"]", flags=re.I)
    id_rx = re.compile(r"\bid=['\"]([^'\"]+)['\"]", flags=re.I)
    class_rx = re.compile(r"\bclass=['\"]([^'\"]+)['\"]", flags=re.I)

    def _parse_points(tag: str) -> list[tuple[float, float]]:
        pm = points_rx.search(tag)
        if not pm:
            return []
        pts_raw = str(pm.group(1) or "").strip()
        out: list[tuple[float, float]] = []
        for part in pts_raw.split():
            if "," not in part:
                continue
            a, b = part.split(",", 1)
            try:
                x = float(a)
                y = float(b)
            except Exception:
                continue
            if math.isfinite(x) and math.isfinite(y):
                out.append((x, y))
        out.sort(key=lambda t: t[0])
        return out

    explicit_surface: list[tuple[float, float]] = []
    fallback_best: list[tuple[float, float]] = []
    fallback_score: tuple[float, float] | None = None
    for m in tag_rx.finditer(svg_text or ""):
        tag = str(m.group(0) or "")
        pts = _parse_points(tag)
        if len(pts) < 2:
            continue
        im = id_rx.search(tag)
        cm = class_rx.search(tag)
        ident = str(im.group(1) if im else "").lower()
        klass = str(cm.group(1) if cm else "").lower()
        if "surface" in ident or "surface" in klass:
            explicit_surface = pts
            break
        xs = [float(p[0]) for p in pts]
        ys = [float(p[1]) for p in pts]
        span = max(xs) - min(xs)
        mean_y = sum(ys) / float(len(ys))
        score = (float(span), -float(mean_y))
        if fallback_score is None or score > fallback_score:
            fallback_score = score
            fallback_best = pts
    return explicit_surface or fallback_best


def _interp_y(points: list[tuple[float, float]], x: float) -> float | None:
    if not points or not math.isfinite(x):
        return None
    if x <= points[0][0]:
        return float(points[0][1])
    if x >= points[-1][0]:
        return float(points[-1][1])
    prev = points[0]
    for cur in points[1:]:
        if prev[0] <= x <= cur[0]:
            x1, y1 = prev
            x2, y2 = cur
            if x2 == x1:
                return float(y1)
            t = (x - x1) / (x2 - x1)
            return float(y1 + t * (y2 - y1))
        prev = cur
    return float(points[-1][1])


def compute_borehole_overlay(
    *,
    svg_text: str,
    svg_w: int,
    svg_h: int,
    path_utm: list[list[float]],
    boreholes: list[dict],
    length_m: float,
    response_summary: dict[str, Any],
    tolerance_m: float,
) -> GeoDkOverlayResult:
    """
    Map boreholes to overlay primitives.

    Borehole dict contract (UTM32):
      - x, y required (float)
      - depth_m OR bottom_m required (meters below surface, positive down)
      - optional top_m for screen interval (meters below surface, positive down)
      - optional id for labels
    """
    vb = _parse_viewbox_wh(svg_text) or (float(svg_w), float(svg_h))
    viewbox_w, viewbox_h = float(vb[0]), float(vb[1])

    x_fit0, y_fit0 = _axis_fits(svg_text)
    x_fit = x_fit0
    y_fit = y_fit0
    x_method = "axis_text" if x_fit0 is not None else "none"
    y_method = "axis_text" if y_fit0 is not None else "none"
    surface_pts = _surface_polyline(svg_text)
    surface_method = "surface_polyline" if surface_pts else "none"

    # Fallback x mapping using surface polyline span.
    if x_fit is None and surface_pts:
        minx = float(surface_pts[0][0])
        maxx = float(surface_pts[-1][0])
        path_len = float(response_summary.get("PathLength") or length_m or 0.0)
        if path_len > 0 and maxx > minx:
            x_fit = ((maxx - minx) / path_len, minx)
            x_method = "surface_span"
    # Last-resort x mapping: full viewBox span.
    if x_fit is None:
        path_len = float(response_summary.get("PathLength") or length_m or 0.0)
        if path_len > 0 and viewbox_w > 0:
            x_fit = (float(viewbox_w) / path_len, 0.0)
            x_method = "viewbox_span"

    # Fallback y mapping using ZMin/ZMax and viewBox span.
    if y_fit is None:
        try:
            zmin = float(response_summary.get("ZMin"))
            zmax = float(response_summary.get("ZMax"))
        except Exception:
            zmin = None
            zmax = None
        if (
            zmin is not None
            and zmax is not None
            and math.isfinite(zmin)
            and math.isfinite(zmax)
            and abs(zmax - zmin) > 1e-9
        ):
            a = viewbox_h / (zmin - zmax)  # negative slope
            b = -a * zmax
            y_fit = (float(a), float(b))
            y_method = "zmin_zmax"

    ppm = abs(float(y_fit[0])) if y_fit is not None else None  # svg units per meter

    tol = float(tolerance_m)
    if not math.isfinite(tol) or tol < 0:
        tol = 10.0

    try:
        zmax = float(response_summary.get("ZMax"))
    except Exception:
        zmax = None
    if zmax is not None and not math.isfinite(zmax):
        zmax = None

    synthetic_surface_y = None
    if not surface_pts and y_fit is not None:
        ay, by = float(y_fit[0]), float(y_fit[1])
        ref_z = float(zmax) if zmax is not None else 0.0
        synthetic_surface_y = ay * ref_z + by
        if math.isfinite(synthetic_surface_y):
            surface_method = "synthetic_from_yfit"
        else:
            synthetic_surface_y = None

    counts = {
        "boreholes_input": 0,
        "boreholes_xy_valid": 0,
        "boreholes_projected": 0,
        "boreholes_in_tolerance": 0,
        "boreholes_with_depth": 0,
    }
    drop_reasons: dict[str, int] = {}

    def _drop(reason: str) -> None:
        drop_reasons[str(reason)] = int(drop_reasons.get(str(reason), 0) or 0) + 1

    items: list[dict] = []
    if x_fit is not None and ppm is not None and (surface_pts or synthetic_surface_y is not None):
        ax, bx = float(x_fit[0]), float(x_fit[1])
        for bh in boreholes or []:
            if not isinstance(bh, dict):
                continue
            counts["boreholes_input"] += 1
            try:
                bxm = float(bh.get("x"))
                bym = float(bh.get("y"))
            except Exception:
                _drop("invalid_xy")
                continue
            if not math.isfinite(bxm) or not math.isfinite(bym):
                _drop("invalid_xy")
                continue
            counts["boreholes_xy_valid"] += 1
            proj = project_point_to_path(point_xy=(bxm, bym), path_xy=path_utm)
            if proj is None:
                _drop("projection_failed")
                continue
            chain_m, dist_m = proj
            if not math.isfinite(chain_m) or not math.isfinite(dist_m):
                _drop("projection_failed")
                continue
            counts["boreholes_projected"] += 1
            if dist_m > tol:
                _drop("out_of_tolerance")
                continue
            counts["boreholes_in_tolerance"] += 1
            x_svg = ax * float(chain_m) + bx
            if not math.isfinite(x_svg):
                _drop("x_map_invalid")
                continue
            y_surface = _interp_y(surface_pts, float(x_svg)) if surface_pts else synthetic_surface_y
            if y_surface is None:
                _drop("surface_unavailable")
                continue

            label = str(bh.get("id") or "").strip()

            top_val = None
            bot_val = None
            try:
                v = bh.get("top_m", None)
                if v is not None:
                    vv = float(v)
                    if math.isfinite(vv):
                        top_val = abs(vv)
            except Exception:
                top_val = None
            try:
                v = bh.get("bottom_m", None)
                if v is not None:
                    vv = float(v)
                    if math.isfinite(vv):
                        bot_val = abs(vv)
            except Exception:
                bot_val = None
            if bot_val is None:
                try:
                    v = bh.get("depth_m", None)
                    if v is not None:
                        vv = float(v)
                        if math.isfinite(vv):
                            bot_val = abs(vv)
                except Exception:
                    bot_val = None
            if bot_val is None:
                _drop("missing_depth")
                continue
            counts["boreholes_with_depth"] += 1

            y1 = float(y_surface)
            y2 = float(y_surface) + float(bot_val) * float(ppm)
            item: dict[str, Any] = {"x": float(x_svg), "y1": float(y1), "y2": float(y2), "label": label}
            if top_val is not None and bot_val is not None:
                ys1 = float(y_surface) + float(top_val) * float(ppm)
                ys2 = float(y_surface) + float(bot_val) * float(ppm)
                item["screen"] = {"y1": float(ys1), "y2": float(ys2)}
            items.append(item)
    else:
        for bh in boreholes or []:
            if isinstance(bh, dict):
                counts["boreholes_input"] += 1
        if x_fit is None:
            _drop("x_mapping_unavailable")
        if ppm is None:
            _drop("y_mapping_unavailable")
        if not surface_pts and synthetic_surface_y is None:
            _drop("surface_unavailable")

    diag = {
        "count": int(len(items)),
        "tolerance_m": float(tol),
        "x_mapping": str(x_method),
        "y_mapping": str(y_method),
        "surface": str(surface_method),
        "boreholes_rendered": int(len(items)),
        **counts,
        "drop_reasons": drop_reasons,
    }
    return GeoDkOverlayResult(items=items, viewbox_w=float(viewbox_w), viewbox_h=float(viewbox_h), diag=diag)
