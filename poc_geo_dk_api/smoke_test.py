#!/usr/bin/env python3
"""
Headless smoke test for the Geo.dk API pipeline:
  token -> geomodel list -> pick model for path -> crosssection -> SVG stats.

This is meant to validate the backend/features without relying on the browser UI.

Usage example (EPSG:25832 path):
  python3 poc_geo_dk_api/smoke_test.py \
    --username "you@example.com" --password "..." --role "" \
    --geomodelid auto \
    --path '[[486406.903,6261887.022],[496204.85,6259164.59]]' \
    --insecure-ssl
"""

from __future__ import annotations

import argparse
import json
import ssl
import sys
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

try:
    import certifi  # type: ignore
except Exception:  # noqa: BLE001
    certifi = None


DATA_GEO_BASE = "https://data.geo.dk"


def http_get_json(url: str, headers: dict[str, str] | None = None, ssl_context: ssl.SSLContext | None = None) -> Any:
    req = Request(url, headers=headers or {}, method="GET")
    with urlopen(req, timeout=60, context=ssl_context) as resp:
        raw = resp.read().decode("utf-8")
    return json.loads(raw)


def http_get_text(url: str, headers: dict[str, str] | None = None, ssl_context: ssl.SSLContext | None = None) -> str:
    req = Request(url, headers=headers or {}, method="GET")
    with urlopen(req, timeout=60, context=ssl_context) as resp:
        return resp.read().decode("utf-8")


def normalize_token(token_value: object) -> str:
    token = str(token_value or "").strip().strip('"')
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    return token


def svg_stats(svg_text: str) -> dict[str, int]:
    t = svg_text or ""
    return {
        "polygons": t.lower().count("<polygon"),
        "polylines": t.lower().count("<polyline"),
    }


@dataclass
class BBox:
    minx: float
    miny: float
    maxx: float
    maxy: float

    def contains(self, x: float, y: float) -> bool:
        return self.minx <= x <= self.maxx and self.miny <= y <= self.maxy


def models_for_path(models: list[dict[str, Any]], path: list[list[float]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for m in models:
        bbox_raw = m.get("BoundingBox")
        if not isinstance(bbox_raw, dict):
            continue
        try:
            bbox = BBox(
                float(bbox_raw["MinX"]),
                float(bbox_raw["MinY"]),
                float(bbox_raw["MaxX"]),
                float(bbox_raw["MaxY"]),
            )
        except Exception:
            continue
        if any(bbox.contains(pt[0], pt[1]) for pt in path):
            out.append(m)
    return out


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
    ap.add_argument("--linepointdistance", type=int, default=10)
    ap.add_argument("--insecure-ssl", action="store_true")
    ap.add_argument("--out-svg", default="", help="Optional output SVG file path")
    args = ap.parse_args()

    if args.insecure_ssl:
        ssl_context = ssl._create_unverified_context()
    else:
        if certifi is not None:
            ssl_context = ssl.create_default_context(cafile=certifi.where())
        else:
            ssl_context = ssl.create_default_context()

    try:
        path = json.loads(args.path)
    except json.JSONDecodeError as exc:
        print(f"Invalid --path JSON: {exc}", file=sys.stderr)
        return 2

    if not isinstance(path, list) or len(path) < 2:
        print("--path must be a list of at least 2 points", file=sys.stderr)
        return 2

    # Token
    token_url = f"{DATA_GEO_BASE}/token?{urlencode({'username': args.username, 'password': args.password, 'role': args.role})}"
    token_raw = http_get_text(token_url, ssl_context=ssl_context)
    token = normalize_token(token_raw)
    if not token:
        print("Token was empty", file=sys.stderr)
        return 3

    auth = {"authorization": f"Bearer {token}"}

    # Models
    geomodel_url = f"{DATA_GEO_BASE}/api/v{args.api_major_version}/geomodel?{urlencode({'geoareaid': args.geoareaid})}"
    models = http_get_json(geomodel_url, headers=auth, ssl_context=ssl_context)
    if not isinstance(models, list):
        print("Unexpected /geomodel response shape", file=sys.stderr)
        return 4

    candidates = models_for_path(models, path)
    chosen_id: int | None = None
    if args.geomodelid.strip().lower() != "auto":
        try:
            chosen_id = int(args.geomodelid)
        except ValueError:
            print("--geomodelid must be int or 'auto'", file=sys.stderr)
            return 2
    else:
        for m in candidates:
            mid = m.get("ID") or m.get("Id")
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

    # Crosssection
    qs = {
        "geoareaid": args.geoareaid,
        "path": json.dumps(path, separators=(",", ":")),
        "geomodelid": chosen_id,
        "width": args.width,
        "height": args.height,
        "maxdepth": args.maxdepth,
        "linepointdistance": args.linepointdistance,
        "srid": 25832,
        "format": "application/json",
    }
    cross_url = f"{DATA_GEO_BASE}/api/v{args.api_major_version}/crosssection?{urlencode(qs)}"
    section = http_get_json(cross_url, headers=auth, ssl_context=ssl_context)
    if not isinstance(section, dict):
        print("Unexpected /crosssection response shape", file=sys.stderr)
        return 6

    model_name = None
    if isinstance(section.get("Model"), dict):
        model_name = section["Model"].get("Name")
    svg = section.get("Svg") or ""
    st = svg_stats(str(svg))

    print(f"ModelId: {chosen_id}")
    print(f"Model: {model_name}")
    print(f"ZMin: {section.get('ZMin')}  ZMax: {section.get('ZMax')}")
    print(f"SVG polygons: {st['polygons']}  polylines: {st['polylines']}")
    print(f"PathLength: {section.get('PathLength')}")

    if args.out_svg:
        with open(args.out_svg, "w", encoding="utf-8") as f:
            f.write(str(svg))
        print(f"Wrote SVG: {args.out_svg}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

