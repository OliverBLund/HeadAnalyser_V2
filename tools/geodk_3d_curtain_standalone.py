#!/usr/bin/env python3
"""
Standalone experimental 3D curtain viewer for Geo.dk cross-sections.

This reuses the in-app backend client (`core/geodk_api.py`) for real data fetches:
  token -> model lookup -> crosssection -> SVG normalize -> derive GeoUnit segments
  -> render an interactive 3D curtain with pyqtgraph.opengl.

Example:
  python3 tools/geodk_3d_curtain_standalone.py \
    --username "Geoatlas@dtu.dk" --password "Th9#tB2" --role "" \
    --path '[[486406.903,6261887.022],[496204.85,6259164.59]]' \
    --geomodelid auto \
    --insecure-ssl
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

# Allow running from repo root.
V2_ROOT = Path(__file__).resolve().parents[1]
if str(V2_ROOT) not in sys.path:
    sys.path.insert(0, str(V2_ROOT))

from core.geodk_api import GeoDKClient, auto_linepointdistance, normalize_svg_for_display, path_length_m, svg_stats

np = None  # lazy-loaded in main()


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


def _build_segment_mesh(segments, *, depth_m: float):
    """
    Build a vertical curtain mesh from 1D segments.

    Coordinates:
      x -> distance along transect (m)
      y -> 0 at surface, negative down
      z -> 0 (single vertical plane)
    """
    depth = float(max(1.0, depth_m))
    verts = []
    faces = []
    colors = []

    for seg in segments:
        x0 = float(seg.start_m)
        x1 = float(seg.end_m)
        if not (math.isfinite(x0) and math.isfinite(x1)) or x1 <= x0:
            continue
        base = len(verts)
        # Quad (top-left, bottom-left, top-right, bottom-right)
        verts.extend(
            [
                [x0, 0.0, 0.0],
                [x0, -depth, 0.0],
                [x1, 0.0, 0.0],
                [x1, -depth, 0.0],
            ]
        )
        # Two triangles
        faces.append([base + 0, base + 1, base + 2])
        faces.append([base + 2, base + 1, base + 3])
        col = _hex_to_rgba(getattr(seg, "color", "#8899aa"))
        colors.append(col)
        colors.append(col)

    if not verts:
        return None, None, None
    return np.array(verts, dtype=float), np.array(faces, dtype=np.int32), np.array(colors, dtype=float)


def _normalize_vertices(
    verts: np.ndarray,
    *,
    length_m: float,
    depth_m: float,
    target_len: float = 900.0,
    vertical_exag: float = 4.0,
) -> np.ndarray:
    """Normalize large world coordinates into a viewer-friendly local frame."""
    out = np.array(verts, dtype=float, copy=True)
    lm = float(max(1.0, length_m))
    dm = float(max(1.0, depth_m))
    sx = float(target_len) / lm
    sy = float(vertical_exag)
    # Center x around zero so camera targets the middle of curtain.
    out[:, 0] = (out[:, 0] - 0.5 * lm) * sx
    out[:, 1] = out[:, 1] * sy
    # Keep z at 0 (single curtain plane).
    return out


def _rasterize_svg_rgba(svg_text: str, width: int, height: int):
    """
    Render SVG text to an RGBA numpy array using QtSvg.
    Returns None if QtSvg is unavailable.
    """
    try:
        from PyQt5.QtCore import QByteArray
        from PyQt5.QtGui import QImage, QPainter
        from PyQt5.QtSvg import QSvgRenderer
    except Exception:
        return None
    try:
        w = int(max(64, width))
        h = int(max(64, height))
        img = QImage(w, h, QImage.Format_RGBA8888)
        img.fill(0)
        renderer = QSvgRenderer(QByteArray(svg_text.encode("utf-8")))
        if not renderer.isValid():
            return None
        painter = QPainter(img)
        renderer.render(painter)
        painter.end()
        ptr = img.bits()
        ptr.setsize(img.byteCount())
        arr = np.frombuffer(ptr, dtype=np.uint8).reshape((h, w, 4)).copy()
        return arr
    except Exception:
        return None


def _print_summary(*, chosen_id: int, section: dict, length_m_val: float, lpd: int, svg: str):
    model_name = None
    if isinstance(section.get("Model"), dict):
        model_name = section["Model"].get("Name")
    st = svg_stats(svg)
    print(f"ModelId: {int(chosen_id)}")
    print(f"Model: {model_name}")
    print(f"ZMin: {section.get('ZMin')}  ZMax: {section.get('ZMax')}")
    print(f"Length (m): {length_m_val:.2f}")
    print(f"LinePointDistance: {int(lpd)}")
    print(f"SVG polygons: {st['polygons']}  polylines: {st['polylines']}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--username", required=True)
    ap.add_argument("--password", required=True)
    ap.add_argument("--role", default="")
    ap.add_argument("--geoareaid", type=int, default=1)
    ap.add_argument("--api-major-version", type=int, default=3, choices=[2, 3])
    ap.add_argument("--geomodelid", default="auto", help="Model ID or 'auto'")
    ap.add_argument("--path", required=True, help="JSON list of [x,y] points in EPSG:25832")
    ap.add_argument("--width", type=int, default=1000)
    ap.add_argument("--height", type=int, default=320)
    ap.add_argument("--maxdepth", type=int, default=-40)
    ap.add_argument("--linepointdistance", default="auto", help="int or 'auto'")
    ap.add_argument("--insecure-ssl", action="store_true")
    ap.add_argument("--window-title", default="Geo.dk 3D Curtain (Experimental)")
    ap.add_argument("--vertical-exag", type=float, default=4.0, help="Vertical exaggeration factor")
    ap.add_argument("--target-length", type=float, default=900.0, help="Rendered curtain length in local scene units")
    args = ap.parse_args()

    global np
    try:
        import numpy as _np  # type: ignore
        np = _np
    except Exception as exc:
        print(
            "numpy is required for this standalone viewer.\n"
            "Install: pip install numpy\n"
            f"Import error: {exc}",
            file=sys.stderr,
        )
        return 11

    from core.geology_layers import GeoDkSvgSurfaceGeologyProvider

    try:
        path = json.loads(args.path)
    except json.JSONDecodeError as exc:
        print(f"Invalid --path JSON: {exc}", file=sys.stderr)
        return 2
    if not isinstance(path, list) or len(path) < 2:
        print("--path must be a list of at least 2 points", file=sys.stderr)
        return 2

    client = GeoDKClient(
        username=args.username,
        password=args.password,
        role=args.role,
        geoareaid=int(args.geoareaid),
        api_major_version=int(args.api_major_version),
        insecure_ssl=bool(args.insecure_ssl),
    )

    models, _cache_hit = client.geomodels_for_path(path)
    chosen_id = None
    if str(args.geomodelid).strip().lower() != "auto":
        try:
            chosen_id = int(args.geomodelid)
        except ValueError:
            print("--geomodelid must be int or 'auto'", file=sys.stderr)
            return 2
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
        print("No matching geomodel found for this path; try another line", file=sys.stderr)
        return 5

    length_m_val = float(path_length_m(path))
    if str(args.linepointdistance).strip().lower() == "auto":
        lpd = auto_linepointdistance(length_m=length_m_val, width_px=int(args.width))
    else:
        try:
            lpd = max(1, int(args.linepointdistance))
        except Exception:
            lpd = 1

    section = client.crosssection(
        path_25832=path,
        geomodelid=int(chosen_id),
        width=int(args.width),
        height=int(args.height),
        maxdepth=int(args.maxdepth),
        linepointdistance=int(lpd),
    )

    svg_raw = str(section.get("Svg") or "")
    layout = section.get("SvgLayout") if isinstance(section.get("SvgLayout"), dict) else {}
    svg_w = int(layout.get("Width") or args.width)
    svg_h = int(layout.get("Height") or args.height)
    svg = normalize_svg_for_display(svg_raw, width=svg_w, height=svg_h)
    _print_summary(chosen_id=int(chosen_id), section=section, length_m_val=length_m_val, lpd=int(lpd), svg=svg)

    # Derive 1D geology segments from SVG polygons.
    provider = GeoDkSvgSurfaceGeologyProvider()
    provider.update_from_svg(svg_text=svg, path_length_m=length_m_val)
    geo = provider.sample_transect(distances_m=np.array([0.0, length_m_val], dtype=float))
    segments = list(geo.get("segments", []))
    if not segments:
        print("No GeoUnit segments derived from SVG; using one fallback segment.", file=sys.stderr)

        class _FallbackSeg:
            start_m = 0.0
            end_m = float(max(1.0, length_m_val))
            color = "#8f99a6"

        segments = [_FallbackSeg()]

    # Depth extent (meters down)
    depth_m = abs(float(args.maxdepth))
    try:
        zmin = float(section.get("ZMin"))
        if math.isfinite(zmin) and zmin < 0:
            depth_m = max(depth_m, abs(zmin))
    except Exception:
        pass
    depth_m = float(max(5.0, depth_m))

    verts, faces, face_colors = _build_segment_mesh(segments, depth_m=depth_m)
    if verts is None:
        print("Failed to build curtain mesh.", file=sys.stderr)
        return 9
    verts = _normalize_vertices(
        verts,
        length_m=float(length_m_val),
        depth_m=float(depth_m),
        target_len=float(max(200.0, args.target_length)),
        vertical_exag=float(max(0.5, args.vertical_exag)),
    )

    try:
        from PyQt5.QtWidgets import QApplication
        from PyQt5.QtGui import QVector3D
    except Exception as exc:
        print(
            "PyQt5 is required for this standalone viewer.\n"
            "Install: pip install PyQt5\n"
            f"Import error: {exc}",
            file=sys.stderr,
        )
        return 10

    app = QApplication.instance() or QApplication(sys.argv)

    try:
        import pyqtgraph as pg
        import pyqtgraph.opengl as gl
    except Exception as exc:
        print(
            "pyqtgraph.opengl is required for this standalone viewer.\n"
            "Install: pip install pyqtgraph PyOpenGL\n"
            f"Import error: {exc}",
            file=sys.stderr,
        )
        return 10

    view = gl.GLViewWidget()
    view.setWindowTitle(str(args.window_title))
    view.setBackgroundColor((8, 18, 28))
    local_len = float(max(200.0, args.target_length))
    local_depth = float(max(5.0, depth_m * max(0.5, args.vertical_exag)))
    view.opts["center"] = QVector3D(0.0, float(-0.45 * local_depth), 0.0)
    view.setCameraPosition(distance=max(500.0, local_len * 1.35), elevation=14, azimuth=-32)

    # Grid for orientation
    grid = gl.GLGridItem()
    grid.setSize(x=max(100.0, local_len * 1.05), y=max(80.0, local_depth * 1.1))
    grid.setSpacing(x=max(20.0, local_len / 16.0), y=max(10.0, local_depth / 10.0))
    grid.rotate(90, 1, 0, 0)  # make it vertical-ish frame
    grid.translate(0.0, float(-0.5 * local_depth), -8.0)
    view.addItem(grid)

    # Preferred: real SVG texture mapped onto curtain plane.
    tex = _rasterize_svg_rgba(svg, width=svg_w, height=svg_h)
    if tex is not None:
        img_item = gl.GLImageItem(tex)
        # GLImageItem draws in x/y pixel space. Map to local curtain dimensions.
        sx = float(local_len) / float(tex.shape[1])
        sy = float(local_depth) / float(tex.shape[0])
        img_item.scale(sx, -sy, 1.0)  # negative y => depth goes downward
        img_item.translate(-0.5 * float(tex.shape[1]), 0.0, 0.0)
        img_item.rotate(8.0, 0, 1, 0)
        view.addItem(img_item)
    else:
        # Fallback: segmented color mesh if QtSvg isn't available.
        mesh_data = gl.MeshData(vertexes=verts, faces=faces, faceColors=face_colors)
        curtain = gl.GLMeshItem(
            meshdata=mesh_data,
            smooth=False,
            drawEdges=True,
            edgeColor=(0.96, 0.97, 0.99, 0.28),
            shader="shaded",
        )
        curtain.rotate(8.0, 0, 1, 0)
        view.addItem(curtain)

    # Surface/top line
    top_line = gl.GLLinePlotItem(
        pos=np.array([[-0.5 * local_len, 0.0, 0.6], [0.5 * local_len, 0.0, 0.6]], dtype=float),
        color=(0.35, 0.78, 1.0, 1.0),
        width=2.0,
        antialias=True,
    )
    view.addItem(top_line)

    # Borehole placeholders can be added later by passing projected points.
    view.resize(1180, 760)
    view.show()
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
