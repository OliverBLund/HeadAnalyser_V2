#!/usr/bin/env python3
"""
Local proof-of-concept server for data.geo.dk cross sections.

Provides:
  - Static UI (Leaflet draw + transect viewer)
  - /api/token proxy
  - /api/crosssection proxy
"""

from __future__ import annotations

import argparse
import json
import ssl
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

try:
    import certifi  # type: ignore
except Exception:  # noqa: BLE001
    certifi = None


BASE_DIR = Path(__file__).resolve().parent
DATA_GEO_TOKEN_URL = "https://data.geo.dk/token"
DATA_GEO_CROSSSECTION_URL = "https://data.geo.dk/api/v3/crosssection"
DATA_GEO_CROSSSECTION_V2_URL = "https://data.geo.dk/api/v2/crosssection"
DATA_GEO_GEOMODEL_URL = "https://data.geo.dk/api/v3/geomodel"
DATA_GEO_GEOMODEL_V2_URL = "https://data.geo.dk/api/v2/geomodel"

DEFAULT_GEOMODEL_CACHE_TTL_SECONDS = 900


def _read_json_body(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length", "0"))
    if length <= 0:
        return {}
    raw = handler.rfile.read(length).decode("utf-8")
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON body: {exc}") from exc


def _http_get_text(
    url: str,
    headers: dict | None = None,
    ssl_context: ssl.SSLContext | None = None,
) -> str:
    req = Request(url, headers=headers or {}, method="GET")
    with urlopen(req, timeout=60, context=ssl_context) as resp:
        return resp.read().decode("utf-8")


def _normalize_token(token_response: str) -> str:
    token_response = token_response.strip()
    try:
        # token endpoint returns JSON string: "eyJ..."
        parsed = json.loads(token_response)
        if isinstance(parsed, str):
            return parsed
    except json.JSONDecodeError:
        pass
    return token_response.strip('"')


def _normalize_auth_token(token_value: object) -> str:
    token = str(token_value or "").strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    return token


def _safe_float(value: object) -> float | None:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _point_in_bbox(point: list[float], bbox: dict) -> bool:
    x = _safe_float(point[0] if len(point) > 0 else None)
    y = _safe_float(point[1] if len(point) > 1 else None)
    min_x = _safe_float(bbox.get("MinX"))
    min_y = _safe_float(bbox.get("MinY"))
    max_x = _safe_float(bbox.get("MaxX"))
    max_y = _safe_float(bbox.get("MaxY"))
    if None in (x, y, min_x, min_y, max_x, max_y):
        return False
    return bool(min_x <= x <= max_x and min_y <= y <= max_y)


class Handler(BaseHTTPRequestHandler):
    server_version = "GeoDKPoC/1.0"

    def do_GET(self) -> None:
        path = urlparse(self.path).path

        if path == "/api/health":
            self._write_json(HTTPStatus.OK, {"ok": True})
            return

        static_map = {
            "/": "index.html",
            "/index.html": "index.html",
            "/app.js": "app.js",
            "/styles.css": "styles.css",
        }
        file_name = static_map.get(path)
        if file_name is None:
            self._write_json(HTTPStatus.NOT_FOUND, {"error": f"Not found: {path}"})
            return

        file_path = BASE_DIR / file_name
        if not file_path.exists():
            self._write_json(HTTPStatus.NOT_FOUND, {"error": f"Missing file: {file_name}"})
            return

        mime = "text/plain"
        if file_name.endswith(".html"):
            mime = "text/html; charset=utf-8"
        elif file_name.endswith(".js"):
            mime = "application/javascript; charset=utf-8"
        elif file_name.endswith(".css"):
            mime = "text/css; charset=utf-8"

        content = file_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            payload = _read_json_body(self)
        except ValueError as exc:
            self._write_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return

        try:
            if path == "/api/token":
                self._handle_token(payload)
                return
            if path == "/api/crosssection":
                self._handle_crosssection(payload)
                return
            if path == "/api/geomodels_for_path":
                self._handle_geomodels_for_path(payload)
                return
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
            self._write_json(
                HTTPStatus.BAD_GATEWAY,
                {"error": f"Upstream HTTP error: {exc.code}", "detail": detail},
            )
            return
        except URLError as exc:
            self._write_json(HTTPStatus.BAD_GATEWAY, {"error": f"Upstream URL error: {exc}"})
            return
        except Exception as exc:  # noqa: BLE001
            self._write_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})
            return

        self._write_json(HTTPStatus.NOT_FOUND, {"error": f"Not found: {path}"})

    def _handle_token(self, payload: dict) -> None:
        username = str(payload.get("username", "")).strip()
        password = str(payload.get("password", "")).strip()
        role_raw = payload.get("role", "")
        role = "" if role_raw is None else str(role_raw).strip()
        if not username or not password:
            self._write_json(
                HTTPStatus.BAD_REQUEST,
                {"error": "username and password are required; role may be empty"},
            )
            return

        query = urlencode({"username": username, "password": password, "role": role})
        response_text = _http_get_text(
            f"{DATA_GEO_TOKEN_URL}?{query}",
            ssl_context=getattr(self.server, "ssl_context", None),
        )
        token = _normalize_token(response_text)
        if not token:
            self._write_json(HTTPStatus.BAD_GATEWAY, {"error": "Token response was empty"})
            return
        self._write_json(HTTPStatus.OK, {"token": token})

    def _handle_crosssection(self, payload: dict) -> None:
        token = _normalize_auth_token(payload.get("token", ""))
        if not token:
            self._write_json(HTTPStatus.BAD_REQUEST, {"error": "token is required"})
            return

        raw_path = payload.get("path")
        if not isinstance(raw_path, list) or len(raw_path) < 2:
            self._write_json(
                HTTPStatus.BAD_REQUEST,
                {"error": "path must be a list of at least two [x, y] points"},
            )
            return

        # Keep compact JSON form expected by API (e.g. [[x1,y1],[x2,y2]]).
        path_param = json.dumps(raw_path, separators=(",", ":"))

        query = {
            "geoareaid": payload.get("geoareaid", 1),
            "path": path_param,
            "srid": payload.get("srid", 4326),
            "linepointdistance": payload.get("linepointdistance", 10),
            "maxdepth": payload.get("maxdepth", -40),
            "xresolution": payload.get("xresolution", 2),
            "height": payload.get("height", 320),
            "format": "application/json",
        }

        if payload.get("api_version") not in (None, "", 0):
            query["api-version"] = payload["api_version"]

        if payload.get("width") not in (None, "", 0):
            query["width"] = payload["width"]

        if payload.get("geomodelid") not in (None, "", 0):
            query["geomodelid"] = payload["geomodelid"]

        api_major_version = int(payload.get("api_major_version", 3))
        base_url = DATA_GEO_CROSSSECTION_URL
        if api_major_version == 2:
            base_url = DATA_GEO_CROSSSECTION_V2_URL

        url = f"{base_url}?{urlencode(query)}"
        headers = {"Authorization": f"Bearer {token}"}
        response_text = _http_get_text(
            url,
            headers=headers,
            ssl_context=getattr(self.server, "ssl_context", None),
        )
        data = json.loads(response_text)
        self._write_json(HTTPStatus.OK, data)

    def _handle_geomodels_for_path(self, payload: dict) -> None:
        token = _normalize_auth_token(payload.get("token", ""))
        if not token:
            self._write_json(HTTPStatus.BAD_REQUEST, {"error": "token is required"})
            return

        raw_path = payload.get("path")
        if not isinstance(raw_path, list) or len(raw_path) < 1:
            self._write_json(
                HTTPStatus.BAD_REQUEST,
                {"error": "path must be a list of [x, y] points"},
            )
            return

        # Validate a compact list of [x, y] point pairs.
        path: list[list[float]] = []
        for item in raw_path:
            if not isinstance(item, list) or len(item) < 2:
                continue
            x = _safe_float(item[0])
            y = _safe_float(item[1])
            if x is None or y is None:
                continue
            path.append([x, y])
        if not path:
            self._write_json(HTTPStatus.BAD_REQUEST, {"error": "path has no valid [x, y] points"})
            return

        geoareaid = payload.get("geoareaid", 1)
        api_major_version = int(payload.get("api_major_version", 3))
        base_url = DATA_GEO_GEOMODEL_URL if api_major_version != 2 else DATA_GEO_GEOMODEL_V2_URL
        url = f"{base_url}?{urlencode({'geoareaid': geoareaid})}"
        headers = {"Authorization": f"Bearer {token}"}

        cache_hit = False
        models = None
        cache = getattr(self.server, "geomodel_cache", None)
        ttl = int(getattr(self.server, "geomodel_cache_ttl_seconds", DEFAULT_GEOMODEL_CACHE_TTL_SECONDS))
        cache_key = (token, api_major_version, int(geoareaid))
        now = time.time()
        if isinstance(cache, dict):
            entry = cache.get(cache_key)
            if isinstance(entry, dict) and entry.get("expires_at", 0) > now:
                models = entry.get("models")
                cache_hit = True

        if models is None:
            response_text = _http_get_text(
                url,
                headers=headers,
                ssl_context=getattr(self.server, "ssl_context", None),
            )
            models = json.loads(response_text)
            if isinstance(cache, dict):
                cache[cache_key] = {"expires_at": now + ttl, "models": models}
        if not isinstance(models, list):
            self._write_json(HTTPStatus.BAD_GATEWAY, {"error": "Unexpected geomodel response"})
            return

        matching_models = []
        for model in models:
            if not isinstance(model, dict):
                continue
            bbox = model.get("BoundingBox")
            if not isinstance(bbox, dict):
                continue
            if any(_point_in_bbox(point, bbox) for point in path):
                matching_models.append(model)

        # Keep QGIS behavior: add terrain fallback at the end.
        matching_models.append({"ID": -1, "Name": "DHM/Terræn Model, 0.4m"})
        self._write_json(
            HTTPStatus.OK,
            {
                "models": matching_models,
                "count": len(matching_models),
                "cache_hit": cache_hit,
            },
        )

    def _write_json(self, status: HTTPStatus, payload: dict) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, fmt: str, *args) -> None:  # noqa: A003
        # Keep output compact for this PoC server.
        print(f"[{self.log_date_time_string()}] {self.address_string()} - {fmt % args}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run local PoC server for data.geo.dk")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8765, help="Port to bind (default: 8765)")
    parser.add_argument(
        "--insecure-ssl",
        action="store_true",
        help="Disable TLS certificate verification for upstream calls (PoC/debug only).",
    )
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    server.geomodel_cache = {}  # type: ignore[attr-defined]
    server.geomodel_cache_ttl_seconds = DEFAULT_GEOMODEL_CACHE_TTL_SECONDS  # type: ignore[attr-defined]
    if args.insecure_ssl:
        ssl_context = ssl._create_unverified_context()
        ssl_mode = "INSECURE (verification disabled)"
    else:
        if certifi is not None:
            ssl_context = ssl.create_default_context(cafile=certifi.where())
            ssl_mode = f"verified (certifi: {certifi.where()})"
        else:
            ssl_context = ssl.create_default_context()
            ssl_mode = "verified (system CA store)"

    server.ssl_context = ssl_context  # type: ignore[attr-defined]
    print(f"Serving PoC at http://{args.host}:{args.port}")
    print(f"Upstream TLS mode: {ssl_mode}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
