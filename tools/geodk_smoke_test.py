#!/usr/bin/env python3
"""
Headless smoke test for Geo.dk integration using the in-app client:
  token -> geomodel list -> pick model for path -> crosssection -> SVG stats.

Example:
  python3 tools/geodk_smoke_test.py \\
    --username "you@example.com" --password "..." --role "" \\
    --path '[[486406.903,6261887.022],[496204.85,6259164.59]]' \\
    --geomodelid auto \\
    --out-svg /tmp/section.svg \\
    --insecure-ssl
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow running from repo root (where HeadAnalyser_V2 is not necessarily on sys.path).
V2_ROOT = Path(__file__).resolve().parents[1]
if str(V2_ROOT) not in sys.path:
    sys.path.insert(0, str(V2_ROOT))

from core.geodk_api import (
    GeoDKClient,
    auto_linepointdistance,
    normalize_svg_for_display,
    path_length_m,
    svg_stats,
)


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
    ap.add_argument("--maxdepth", type=int, default=-40, help="Depth level (negative is down)")
    ap.add_argument("--linepointdistance", default="auto", help="int or 'auto'")
    ap.add_argument("--insecure-ssl", action="store_true")
    ap.add_argument("--out-svg", default="", help="Optional output SVG file path")
    args = ap.parse_args()

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

    models, cache_hit = client.geomodels_for_path(path)
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

    length_m = float(path_length_m(path))
    if str(args.linepointdistance).strip().lower() == "auto":
        lpd = auto_linepointdistance(length_m=length_m, width_px=int(args.width))
    else:
        try:
            lpd = max(1, int(args.linepointdistance))
        except Exception:
            lpd = 10

    section = client.crosssection(
        path_25832=path,
        geomodelid=int(chosen_id),
        width=int(args.width),
        height=int(args.height),
        maxdepth=int(args.maxdepth),
        linepointdistance=int(lpd),
    )

    model_name = None
    if isinstance(section.get("Model"), dict):
        model_name = section["Model"].get("Name")

    svg_raw = str(section.get("Svg") or "")
    layout = section.get("SvgLayout") if isinstance(section.get("SvgLayout"), dict) else {}
    svg_w = int(layout.get("Width") or args.width)
    svg_h = int(layout.get("Height") or args.height)
    svg = normalize_svg_for_display(svg_raw, width=svg_w, height=svg_h)
    st = svg_stats(svg)

    print(f"CacheHit: {bool(cache_hit)}")
    print(f"ModelId: {chosen_id}")
    print(f"Model: {model_name}")
    print(f"ZMin: {section.get('ZMin')}  ZMax: {section.get('ZMax')}")
    print(f"Length (m): {length_m:.2f}")
    print(f"LinePointDistance: {lpd}")
    print(f"SVG polygons: {st['polygons']}  polylines: {st['polylines']}")

    if args.out_svg:
        with open(args.out_svg, "w", encoding="utf-8") as f:
            f.write(svg)
        print(f"Wrote SVG: {args.out_svg}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
