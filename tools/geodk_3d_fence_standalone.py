#!/usr/bin/env python3
"""
Standalone experimental Geo.dk fence-diagram viewer.

Purpose:
  Quickly evaluate whether multiple Geo.dk transects in a 3D scene provide
  meaningful user value before integrating into the main app UI.

What it does:
  - Reuses core/geodk_api.py for real Geo.dk fetches.
  - Supports either:
      A) explicit --paths JSON (list of transect paths), or
      B) one --path plus --count/--spacing-m to generate parallel transects.
  - Derives GeoUnit segments from each returned SVG and builds colored 3D
    curtain panels (fence diagram).

Example:
  python tools/geodk_3d_fence_standalone.py \
    --username "you@example.com" --password "..." \
    --path "[[486406.903,6261887.022],[496204.85,6259164.59]]" \
    --count 5 --spacing-m 120 \
    --geomodelid auto --insecure-ssl
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

# Repo-root import support.
V2_ROOT = Path(__file__).resolve().parents[1]
if str(V2_ROOT) not in sys.path:
    sys.path.insert(0, str(V2_ROOT))

from core.geodk_api import GeoDKClient, auto_linepointdistance, normalize_svg_for_display, path_length_m, svg_stats


def _parse_path_json(text: str) -> list[list[float]]:
    obj = json.loads(text)
    if not isinstance(obj, list) or len(obj) < 2:
        raise ValueError("path must be list of at least 2 points")
    out: list[list[float]] = []
    for pt in obj:
        if not isinstance(pt, list) or len(pt) < 2:
            continue
        x = float(pt[0])
        y = float(pt[1])
        if math.isfinite(x) and math.isfinite(y):
            out.append([x, y])
    if len(out) < 2:
        raise ValueError("path had fewer than 2 valid points")
    return out


def _offset_path_parallel(path: list[list[float]], offset_m: float) -> list[list[float]]:
    if len(path) < 2:
        return list(path)
    x0, y0 = float(path[0][0]), float(path[0][1])
    x1, y1 = float(path[-1][0]), float(path[-1][1])
    dx = x1 - x0
    dy = y1 - y0
    ll = math.hypot(dx, dy)
    if not math.isfinite(ll) or ll <= 1e-9:
        return list(path)
    nx = -dy / ll
    ny = dx / ll
    d = float(offset_m)
    return [[float(px + nx * d), float(py + ny * d)] for px, py in path]


def _hex_to_rgba(color: str, alpha: float = 0.92) -> tuple[float, float, float, float]:
    c = str(color or "").strip()
    if c.startswith("#") and len(c) in {4, 7}:
        if len(c) == 4:
            c = "#" + c[1] * 2 + c[2] * 2 + c[3] * 2
        try:
            r = int(c[1:3], 16) / 255.0
            g = int(c[3:5], 16) / 255.0
            b = int(c[5:7], 16) / 255.0
            return float(r), float(g), float(b), float(alpha)
        except Exception:
            pass
    return 0.58, 0.62, 0.68, float(alpha)


def _build_curtain_mesh_from_segments(
    segments,
    *,
    length_m: float,
    depth_m: float,
    z_offset: float,
    target_len_scene: float,
    vertical_exag: float,
):
    lm = float(max(1.0, length_m))
    dm = float(max(1.0, depth_m))
    sx = float(target_len_scene) / lm
    sy = float(max(0.1, vertical_exag))

    verts = []
    faces = []
    colors = []

    for seg in segments:
        x0m = float(getattr(seg, "start_m", 0.0))
        x1m = float(getattr(seg, "end_m", lm))
        if not (math.isfinite(x0m) and math.isfinite(x1m)) or x1m <= x0m:
            continue

        # Center x at 0.
        x0 = (x0m - 0.5 * lm) * sx
        x1 = (x1m - 0.5 * lm) * sx
        y_top = 0.0
        y_bot = -dm * sy
        z = float(z_offset)

        b = len(verts)
        verts.extend(
            [
                [x0, y_top, z],
                [x0, y_bot, z],
                [x1, y_top, z],
                [x1, y_bot, z],
            ]
        )
        faces.append([b + 0, b + 1, b + 2])
        faces.append([b + 2, b + 1, b + 3])
        col = _hex_to_rgba(getattr(seg, "color", "#8f99a6"), alpha=0.90)
        colors.append(col)
        colors.append(col)

    if not verts:
        return None, None, None

    import numpy as np  # local import for cleaner startup failures

    return np.array(verts, dtype=float), np.array(faces, dtype=np.int32), np.array(colors, dtype=float)


def _fetch_one_transect(
    *,
    client: GeoDKClient,
    path: list[list[float]],
    geomodelid_arg: str,
    width: int,
    height: int,
    maxdepth: int,
    linepointdistance_arg: str,
):
    from core.geology_layers import GeoDkSvgSurfaceGeologyProvider

    models, _cache_hit = client.geomodels_for_path(path)

    chosen_id = None
    if str(geomodelid_arg).strip().lower() != "auto":
        chosen_id = int(geomodelid_arg)
    else:
        for m in models:
            if not isinstance(m, dict):
                continue
            mid = m.get("ID") if "ID" in m else m.get("Id")
            try:
                mid_int = int(mid)
            except Exception:
                continue
            if mid_int > 0:
                chosen_id = mid_int
                break
    if chosen_id is None:
        raise RuntimeError("No matching geomodel for transect")

    length_m_val = float(path_length_m(path))
    if str(linepointdistance_arg).strip().lower() == "auto":
        lpd = int(auto_linepointdistance(length_m=length_m_val, width_px=int(width)))
    else:
        lpd = int(max(1, int(linepointdistance_arg)))

    section = client.crosssection(
        path_25832=path,
        geomodelid=int(chosen_id),
        width=int(width),
        height=int(height),
        maxdepth=int(maxdepth),
        linepointdistance=int(lpd),
    )

    svg_raw = str(section.get("Svg") or "")
    layout = section.get("SvgLayout") if isinstance(section.get("SvgLayout"), dict) else {}
    svg_w = int(layout.get("Width") or width)
    svg_h = int(layout.get("Height") or height)
    svg = normalize_svg_for_display(svg_raw, width=svg_w, height=svg_h)
    st = svg_stats(svg)

    provider = GeoDkSvgSurfaceGeologyProvider()
    provider.update_from_svg(svg_text=svg, path_length_m=length_m_val)
    geo = provider.sample_transect(distances_m=[0.0, length_m_val])
    segments = list(geo.get("segments", []))
    if not segments:
        # fallback neutral block
        class _FallbackSeg:
            start_m = 0.0
            end_m = float(max(1.0, length_m_val))
            color = "#8f99a6"

        segments = [_FallbackSeg()]

    model_name = None
    if isinstance(section.get("Model"), dict):
        model_name = section["Model"].get("Name")

    return {
        "length_m": float(length_m_val),
        "chosen_id": int(chosen_id),
        "model_name": model_name,
        "section": section,
        "svg_stats": st,
        "segments": segments,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--username", required=True)
    ap.add_argument("--password", required=True)
    ap.add_argument("--role", default="")
    ap.add_argument("--geoareaid", type=int, default=1)
    ap.add_argument("--api-major-version", type=int, default=3, choices=[2, 3])
    ap.add_argument("--geomodelid", default="auto", help="Model ID or 'auto'")

    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--path", help="One path JSON: [[x,y],[x,y],...] in EPSG:25832")
    src.add_argument("--paths", help="List of path JSONs: [[[x,y],...], [[x,y],...], ...]")

    ap.add_argument("--count", type=int, default=5, help="When using --path: number of parallel transects")
    ap.add_argument("--spacing-m", type=float, default=120.0, help="When using --path: offset spacing in meters")

    ap.add_argument("--width", type=int, default=1000)
    ap.add_argument("--height", type=int, default=320)
    ap.add_argument("--maxdepth", type=int, default=-40)
    ap.add_argument("--linepointdistance", default="auto", help="int or 'auto'")
    ap.add_argument("--insecure-ssl", action="store_true")

    ap.add_argument("--target-length", type=float, default=950.0, help="Rendered curtain length in scene units")
    ap.add_argument("--vertical-exag", type=float, default=5.0, help="Vertical exaggeration factor")
    ap.add_argument("--fence-spacing", type=float, default=170.0, help="Spacing between curtain planes in scene units")
    ap.add_argument("--window-title", default="Geo.dk 3D Fence (Experimental)")
    args = ap.parse_args()

    # Runtime deps (lazy imports for clearer CLI failures).
    try:
        import numpy as np  # noqa: F401
    except Exception as exc:
        print(f"numpy is required: {exc}", file=sys.stderr)
        return 11
    try:
        from PyQt5.QtWidgets import QApplication
        from PyQt5.QtGui import QVector3D
        import pyqtgraph.opengl as gl
    except Exception as exc:
        print(
            "PyQt5 + pyqtgraph.opengl are required.\n"
            "Install: pip install PyQt5 pyqtgraph PyOpenGL\n"
            f"Import error: {exc}",
            file=sys.stderr,
        )
        return 12

    # Build transect set.
    if args.paths:
        try:
            raw = json.loads(args.paths)
            if not isinstance(raw, list) or not raw:
                raise ValueError("paths must be a non-empty list")
            paths = []
            for p in raw:
                paths.append(_parse_path_json(json.dumps(p)))
        except Exception as exc:
            print(f"Invalid --paths JSON: {exc}", file=sys.stderr)
            return 2
    else:
        try:
            base = _parse_path_json(str(args.path))
        except Exception as exc:
            print(f"Invalid --path JSON: {exc}", file=sys.stderr)
            return 2
        n = int(max(1, args.count))
        center = 0.5 * (n - 1)
        paths = []
        for i in range(n):
            off = (float(i) - center) * float(args.spacing_m)
            paths.append(_offset_path_parallel(base, off))

    client = GeoDKClient(
        username=args.username,
        password=args.password,
        role=args.role,
        geoareaid=int(args.geoareaid),
        api_major_version=int(args.api_major_version),
        insecure_ssl=bool(args.insecure_ssl),
    )

    results = []
    for idx, path in enumerate(paths):
        try:
            r = _fetch_one_transect(
                client=client,
                path=path,
                geomodelid_arg=str(args.geomodelid),
                width=int(args.width),
                height=int(args.height),
                maxdepth=int(args.maxdepth),
                linepointdistance_arg=str(args.linepointdistance),
            )
            results.append(r)
            print(
                f"[{idx+1}/{len(paths)}] model={r['chosen_id']} len={r['length_m']:.1f}m "
                f"poly={r['svg_stats']['polygons']} name={r['model_name']}"
            )
        except Exception as exc:
            print(f"[{idx+1}/{len(paths)}] fetch failed: {exc}", file=sys.stderr)

    if not results:
        print("No transects could be fetched.", file=sys.stderr)
        return 20

    # Scene setup.
    app = QApplication.instance() or QApplication(sys.argv)
    view = gl.GLViewWidget()
    view.setWindowTitle(str(args.window_title))
    view.setBackgroundColor((8, 18, 28))

    max_len = max(float(r["length_m"]) for r in results)
    max_depth = float(max(abs(float(args.maxdepth)), 8.0))
    local_len = float(max(250.0, args.target_length))
    local_depth = float(max(30.0, max_depth * max(0.1, args.vertical_exag)))
    n = len(results)
    total_z_span = float(max(10.0, (n - 1) * float(args.fence_spacing)))

    view.opts["center"] = QVector3D(0.0, float(-0.45 * local_depth), 0.0)
    view.setCameraPosition(distance=max(700.0, local_len * 1.4 + total_z_span * 0.7), elevation=18, azimuth=-34)

    grid = gl.GLGridItem()
    grid.setSize(x=max(120.0, local_len * 1.15), y=max(120.0, total_z_span * 1.25))
    grid.setSpacing(x=max(25.0, local_len / 16.0), y=max(25.0, total_z_span / max(2.0, n - 1)))
    grid.translate(0.0, float(-local_depth), 0.0)
    view.addItem(grid)

    # Render curtain per transect.
    center_idx = 0.5 * (n - 1)
    for i, r in enumerate(results):
        z = (float(i) - center_idx) * float(args.fence_spacing)
        verts, faces, cols = _build_curtain_mesh_from_segments(
            r["segments"],
            length_m=float(r["length_m"]),
            depth_m=float(max_depth),
            z_offset=float(z),
            target_len_scene=float(local_len),
            vertical_exag=float(args.vertical_exag),
        )
        if verts is None:
            continue
        md = gl.MeshData(vertexes=verts, faces=faces, faceColors=cols)
        item = gl.GLMeshItem(
            meshdata=md,
            smooth=False,
            drawEdges=True,
            edgeColor=(0.95, 0.98, 1.0, 0.22),
            shader="shaded",
        )
        item.rotate(8.0, 0, 1, 0)
        view.addItem(item)

        # Top line for each transect
        top = gl.GLLinePlotItem(
            pos=np.array([[-0.5 * local_len, 0.0, z], [0.5 * local_len, 0.0, z]], dtype=float),
            color=(0.39, 0.80, 1.0, 0.95 if i == int(round(center_idx)) else 0.45),
            width=2.0 if i == int(round(center_idx)) else 1.2,
            antialias=True,
        )
        view.addItem(top)

    view.resize(1260, 820)
    view.show()
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())

