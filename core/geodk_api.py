"""
Geo.dk API integration (token -> geomodel selection -> crosssection SVG).

This module is a direct-Python client (no local HTTP proxy needed), intended for
use from the PyQt application so browser-side JS never sees the token.
"""

from __future__ import annotations

import base64
import json
import math
import re
import ssl
import time
from dataclasses import dataclass
from html import escape as _html_escape
from pathlib import Path
from typing import Any, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


DATA_GEO_BASE = "https://data.geo.dk"


class GeoDKError(RuntimeError):
    """Raised for upstream or client errors when talking to data.geo.dk."""

    def __init__(
        self,
        message: str,
        *,
        url: str | None = None,
        status: int | None = None,
        detail: str | None = None,
    ) -> None:
        super().__init__(message)
        self.url = url
        self.status = status
        self.detail = detail

    def __str__(self) -> str:  # noqa: D105
        base = super().__str__()
        parts: list[str] = []
        if self.status:
            parts.append(f"status={int(self.status)}")
        if self.url:
            parts.append(f"url={self.url}")
        if self.detail:
            d = str(self.detail)
            d = d.strip().replace("\r", " ").replace("\n", " ")
            if len(d) > 240:
                d = d[:240] + "..."
            parts.append(f"detail={d}")
        if not parts:
            return base
        return f"{base} ({', '.join(parts)})"


def normalize_token(token_value: object) -> str:
    token = str(token_value or "").strip().strip('"')
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    return token


def svg_stats(svg_text: str) -> dict[str, int]:
    t = svg_text or ""
    low = t.lower()
    return {
        "polygons": low.count("<polygon"),
        "polylines": low.count("<polyline"),
    }


def has_geology(svg_text: str) -> bool:
    return int(svg_stats(svg_text).get("polygons", 0) or 0) > 0


def normalize_svg_for_display(svg_text: str, *, width: int | None = None, height: int | None = None) -> str:
    """
    Geo.dk SVG sometimes lacks viewBox/preserveAspectRatio, which makes embedded
    rendering awkward. This normalizes the SVG similarly to the PoC.
    """
    if not svg_text or not isinstance(svg_text, str):
        return ""

    out = re.sub(r"-webkit-font-smoothing:\s*antialiased;?", "", svg_text, flags=re.IGNORECASE)

    if width is None:
        m = re.search(r"<svg[^>]*\\bwidth=['\"]?([0-9.]+)", out, flags=re.IGNORECASE)
        if m:
            try:
                width = int(round(float(m.group(1))))
            except Exception:
                width = None
    if height is None:
        m = re.search(r"<svg[^>]*\\bheight=['\"]?([0-9.]+)", out, flags=re.IGNORECASE)
        if m:
            try:
                height = int(round(float(m.group(1))))
            except Exception:
                height = None

    width = int(width or 1000)
    height = int(height or 320)

    if not re.search(r"\\bviewBox\\s*=", out):
        out = re.sub(
            r"<svg\\b",
            f'<svg viewBox="0 0 {width} {height}" preserveAspectRatio="xMinYMin meet"',
            out,
            count=1,
            flags=re.IGNORECASE,
        )
    elif not re.search(r"\\bpreserveAspectRatio\\s*=", out):
        out = re.sub(
            r"<svg\\b",
            '<svg preserveAspectRatio="xMinYMin meet"',
            out,
            count=1,
            flags=re.IGNORECASE,
        )
    return out


def _safe_float(value: object) -> float | None:
    try:
        return float(value)  # type: ignore[arg-type]
    except Exception:
        return None


@dataclass(frozen=True)
class BBox:
    minx: float
    miny: float
    maxx: float
    maxy: float

    def intersects(self, other: "BBox") -> bool:
        # Inclusive intersection; bbox edges touching counts as overlap.
        return not (
            self.maxx < other.minx
            or self.minx > other.maxx
            or self.maxy < other.miny
            or self.miny > other.maxy
        )


def path_bbox(path: list[list[float]]) -> BBox | None:
    if not isinstance(path, list) or len(path) < 2:
        return None
    xs: list[float] = []
    ys: list[float] = []
    for pt in path:
        if not isinstance(pt, list) or len(pt) < 2:
            continue
        x = _safe_float(pt[0])
        y = _safe_float(pt[1])
        if x is None or y is None:
            continue
        xs.append(float(x))
        ys.append(float(y))
    if len(xs) < 2:
        return None
    return BBox(min(xs), min(ys), max(xs), max(ys))


def path_length_m(path: list[list[float]]) -> float:
    if not isinstance(path, list) or len(path) < 2:
        return 0.0
    total = 0.0
    prev = None
    for pt in path:
        if not isinstance(pt, list) or len(pt) < 2:
            continue
        x = _safe_float(pt[0])
        y = _safe_float(pt[1])
        if x is None or y is None:
            continue
        cur = (float(x), float(y))
        if prev is not None:
            total += math.hypot(cur[0] - prev[0], cur[1] - prev[1])
        prev = cur
    return float(total)


def auto_linepointdistance(*, length_m: float, width_px: int) -> int:
    """QGIS-like: ceil(pathLengthMeters / widthPx)."""
    try:
        lm = float(length_m)
    except Exception:
        lm = 0.0
    try:
        w = int(width_px)
    except Exception:
        w = 0
    if w <= 0:
        w = 1000
    if not math.isfinite(lm) or lm <= 0:
        return 1
    return max(1, int(math.ceil(lm / float(w))))


def project_point_to_path(
    *,
    point_xy: tuple[float, float],
    path_xy: list[list[float]],
) -> tuple[float, float] | None:
    """
    Project a point onto a polyline path.

    Returns (chainage_m, distance_m) where:
    - chainage_m is the distance along the path from the first vertex to the closest projected point.
    - distance_m is the perpendicular distance from the point to the path at that location.
    """
    try:
        px = float(point_xy[0])
        py = float(point_xy[1])
    except Exception:
        return None
    if not isinstance(path_xy, list) or len(path_xy) < 2:
        return None

    # Pre-parse vertices and cumulative lengths.
    verts: list[tuple[float, float]] = []
    for pt in path_xy:
        if not isinstance(pt, list) or len(pt) < 2:
            continue
        x = _safe_float(pt[0])
        y = _safe_float(pt[1])
        if x is None or y is None:
            continue
        verts.append((float(x), float(y)))
    if len(verts) < 2:
        return None

    best_dist2 = None
    best_chain = 0.0
    chain_at_start = 0.0

    for i in range(len(verts) - 1):
        x1, y1 = verts[i]
        x2, y2 = verts[i + 1]
        dx = x2 - x1
        dy = y2 - y1
        seg_len2 = dx * dx + dy * dy
        if seg_len2 <= 0:
            continue

        # Project onto segment [0,1].
        t = ((px - x1) * dx + (py - y1) * dy) / seg_len2
        if t < 0.0:
            t = 0.0
        elif t > 1.0:
            t = 1.0
        qx = x1 + t * dx
        qy = y1 + t * dy
        ddx = px - qx
        ddy = py - qy
        dist2 = ddx * ddx + ddy * ddy

        if best_dist2 is None or dist2 < best_dist2:
            seg_len = math.hypot(dx, dy)
            best_dist2 = dist2
            best_chain = chain_at_start + t * seg_len

        chain_at_start += math.hypot(dx, dy)

    if best_dist2 is None:
        return None
    return float(best_chain), float(math.sqrt(best_dist2))


def extract_geounit_colors(svg_text: str) -> dict[str, str]:
    """Extract geounit ID -> fill color mapping from SVG <style> CSS rules."""
    colors: dict[str, str] = {}
    if not svg_text or not isinstance(svg_text, str):
        return colors

    # Match CSS rules like: .geounit-447 { fill: #8b7355; }
    # or: .geoenhed-123 { fill: rgb(139, 115, 85); }
    regexes = [
        re.compile(r"\.geounit-(\d+)\s*\{[^}]*fill:\s*([^;}\s]+)", flags=re.IGNORECASE),
        re.compile(r"\.geoenhed-(\d+)\s*\{[^}]*fill:\s*([^;}\s]+)", flags=re.IGNORECASE),
    ]
    for rx in regexes:
        for m in rx.finditer(svg_text):
            gid = str(m.group(1))
            col = str(m.group(2) or "").strip()
            if gid and col:
                colors[gid] = col
    return colors


def build_geounit_legend_html(model: object, svg_text: str) -> str:
    """
    Return HTML compatible with the map concept classes:
    - geology-legend-item / geology-legend-color / geology-legend-text / geology-legend-code
    """
    if not isinstance(model, dict):
        return ""
    units = model.get("GeoUnits")
    if not isinstance(units, list) or not units:
        return ""

    color_map = extract_geounit_colors(svg_text)
    items: list[str] = []
    for u in units:
        if not isinstance(u, dict):
            continue
        uid = u.get("Id") if "Id" in u else u.get("ID")
        name = u.get("Name") or u.get("name") or ""
        try:
            uid_s = str(int(uid))
        except Exception:
            uid_s = str(uid or "").strip()
        if not uid_s:
            continue
        color = color_map.get(uid_s, "")
        style = ""
        if color:
            c = _html_escape(color)
            style = f' style="background:{c};border-color:{c};"'
        items.append(
            "<div class=\"geology-legend-item\">"
            f"<div class=\"geology-legend-color\"{style}></div>"
            f"<span class=\"geology-legend-text\">{_html_escape(str(name or f'Unit {uid_s}'))}</span>"
            f"<span class=\"geology-legend-code\">{_html_escape(uid_s)}</span>"
            "</div>"
        )
    if not items:
        return ""
    title = "<div class=\"geology-legend-title\">GeoUnits</div>"
    return title + "".join(items)


def write_repro_bundle(
    payload: dict[str, Any],
    *,
    svg_text: str | None = None,
    root_dir: Path | None = None,
    keep_last_n: int = 50,
    stamp: str | None = None,
) -> Path:
    """
    Write a minimal repro bundle for bug reports under `.recovery/geo_dk/`.

    Security note: callers should not include passwords or tokens in `payload`.
    """
    root = Path(root_dir) if root_dir is not None else Path(__file__).resolve().parents[1]
    out_dir = root / ".recovery" / "geo_dk"
    out_dir.mkdir(parents=True, exist_ok=True)

    if not stamp:
        now = time.time()
        stamp = time.strftime("%Y%m%d_%H%M%S", time.localtime(now))
        stamp = f"{stamp}_{int((now - int(now)) * 1000):03d}"
    repro_path = out_dir / f"geo_dk_repro_{stamp}.json"
    repro_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    if svg_text:
        svg_path = out_dir / f"geo_dk_crosssection_{stamp}.svg"
        svg_path.write_text(str(svg_text), encoding="utf-8")

    # Basic rotation to keep `.recovery/geo_dk` bounded.
    try:
        keep = int(keep_last_n)
    except Exception:
        keep = 50
    if keep > 0:
        try:
            # We rotate based on the repro JSON files, and delete any matching SVG with the same stamp.
            repro_rx = re.compile(r"^geo_dk_repro_(\\d{8}_\\d{6}_\\d{3})\\.json$", flags=re.IGNORECASE)
            svg_rx = re.compile(r"^geo_dk_crosssection_(\\d{8}_\\d{6}_\\d{3})\\.svg$", flags=re.IGNORECASE)
            repro_files: list[tuple[str, Path]] = []
            for p in out_dir.iterdir():
                if not p.is_file():
                    continue
                m = repro_rx.match(p.name)
                if m:
                    repro_files.append((str(m.group(1)), p))
            repro_files.sort(key=lambda t: t[0])  # stamp lexical order == chronological order
            keep_stamps = {s for (s, _) in repro_files[-keep:]} if keep > 0 else set()
            drop_stamps = [s for (s, _) in repro_files[:-keep]] if len(repro_files) > keep else []
            # Delete old repro JSON files.
            for s, p in repro_files:
                if s in keep_stamps:
                    continue
                try:
                    p.unlink(missing_ok=True)
                except Exception:
                    pass
            # Delete matching SVG files for dropped stamps.
            if drop_stamps:
                drop_set = set(drop_stamps)
                for p in out_dir.iterdir():
                    if not p.is_file():
                        continue
                    m = svg_rx.match(p.name)
                    if not m:
                        continue
                    if str(m.group(1)) not in drop_set:
                        continue
                    try:
                        p.unlink(missing_ok=True)
                    except Exception:
                        pass
        except Exception:
            pass

    return repro_path


def _build_ssl_context(*, insecure_ssl: bool) -> ssl.SSLContext:
    if insecure_ssl:
        return ssl._create_unverified_context()
    try:
        import certifi  # type: ignore

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def _http_get_text(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout_s: float = 60.0,
    ssl_context: ssl.SSLContext | None = None,
) -> str:
    req = Request(url, headers=headers or {}, method="GET")
    try:
        with urlopen(req, timeout=float(timeout_s), context=ssl_context) as resp:
            return resp.read().decode("utf-8")
    except HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        except Exception:
            detail = ""
        raise GeoDKError(
            f"Upstream HTTP error: {exc.code}",
            url=url,
            status=int(getattr(exc, "code", 0) or 0),
            detail=detail,
        ) from exc
    except URLError as exc:
        raise GeoDKError(f"Upstream URL error: {exc}", url=url) from exc


def _http_get_json(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout_s: float = 60.0,
    ssl_context: ssl.SSLContext | None = None,
) -> Any:
    raw = _http_get_text(url, headers=headers, timeout_s=timeout_s, ssl_context=ssl_context)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise GeoDKError("Upstream returned invalid JSON", url=url, detail=raw[:2000]) from exc


def _normalize_token_response(token_response: str) -> str:
    token_response = str(token_response or "").strip()
    try:
        parsed = json.loads(token_response)
        if isinstance(parsed, str):
            return normalize_token(parsed)
    except Exception:
        pass
    return normalize_token(token_response.strip('"'))


def _jwt_claims_unsafe(token: str) -> dict[str, Any] | None:
    """
    Best-effort decode of JWT payload without verifying signature.
    Used only for diagnostics (e.g. exp/profile claims), not for security decisions.
    """
    t = normalize_token(token)
    parts = t.split(".")
    if len(parts) < 2:
        return None
    payload_b64 = parts[1]
    # Base64url padding
    pad = "=" * ((4 - (len(payload_b64) % 4)) % 4)
    try:
        raw = base64.urlsafe_b64decode((payload_b64 + pad).encode("ascii", errors="ignore"))
        obj = json.loads(raw.decode("utf-8", errors="replace"))
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


class GeoDKClient:
    def __init__(
        self,
        *,
        username: str,
        password: str,
        role: str = "",
        geoareaid: int = 1,
        api_major_version: int = 3,
        insecure_ssl: bool = False,
        timeout_s: float = 60.0,
        geomodel_cache_ttl_s: int = 900,
        retry_attempts: int = 3,
        retry_backoff_s: float = 0.6,
    ) -> None:
        self.username = str(username or "").strip()
        self.password = str(password or "").strip()
        self.role = "" if role is None else str(role).strip()
        self.geoareaid = int(geoareaid)
        self.api_major_version = int(api_major_version)
        self.insecure_ssl = bool(insecure_ssl)
        self.timeout_s = float(timeout_s)
        self.geomodel_cache_ttl_s = int(geomodel_cache_ttl_s)
        self.retry_attempts = int(retry_attempts)
        self.retry_backoff_s = float(retry_backoff_s)

        self._ssl_context = _build_ssl_context(insecure_ssl=self.insecure_ssl)
        self._token: str | None = None
        self._token_claims: dict[str, Any] | None = None
        self._geomodel_cache: dict[str, Any] | None = None
        self._last_token_refresh_at: float | None = None
        self._last_token_refresh_reason: str = ""

    def token_claims(self) -> dict[str, Any] | None:
        return self._token_claims

    def refresh_token(self) -> str:
        if not self.username or not self.password:
            raise GeoDKError("Geo.dk username/password not configured")

        query = urlencode({"username": self.username, "password": self.password, "role": self.role})
        url = f"{DATA_GEO_BASE}/token?{query}"
        raw = _http_get_text(url, timeout_s=self.timeout_s, ssl_context=self._ssl_context)
        token = _normalize_token_response(raw)
        if not token:
            raise GeoDKError("Token response was empty", url=url, detail=str(raw)[:2000])
        self._token = token
        self._token_claims = _jwt_claims_unsafe(token)
        self._last_token_refresh_at = time.time()
        self._last_token_refresh_reason = "manual"
        return token

    def ensure_token(self) -> str:
        if self._token:
            return self._token
        return self.refresh_token()

    def _auth_headers(self) -> dict[str, str]:
        token = self.ensure_token()
        return {"Authorization": f"Bearer {normalize_token(token)}"}

    def _get_json_auth_retry_401(self, url: str) -> Any:
        """
        Authenticated GET with:
        - single token refresh on 401
        - retries with exponential backoff for transient errors (URLError, 5xx, 429)
        """
        attempts = max(1, int(self.retry_attempts or 1))
        backoff = max(0.05, float(self.retry_backoff_s or 0.6))
        refreshed = False
        last_exc: Exception | None = None

        for i in range(attempts):
            try:
                headers = self._auth_headers()
                return _http_get_json(url, headers=headers, timeout_s=self.timeout_s, ssl_context=self._ssl_context)
            except GeoDKError as exc:
                last_exc = exc
                st = int(exc.status or 0)
                if st == 401 and not refreshed:
                    # Token likely expired; refresh and retry once.
                    self.refresh_token()
                    self._last_token_refresh_reason = "401"
                    refreshed = True
                    continue
                is_transient = (st in (429,)) or (st >= 500 and st <= 599) or (st == 0)
                if (i + 1) >= attempts or not is_transient:
                    raise
            except Exception as exc:
                last_exc = exc
                if (i + 1) >= attempts:
                    raise
            # Backoff before retry.
            try:
                time.sleep(backoff * (2.0 ** float(i)))
            except Exception:
                pass

        if last_exc is not None:
            raise last_exc
        raise GeoDKError("Geo.dk request failed (unknown error)", url=url)

    def geomodels(self) -> tuple[list[dict[str, Any]], bool]:
        """Return (models, cache_hit)."""
        now = time.time()
        cache = self._geomodel_cache if isinstance(self._geomodel_cache, dict) else None
        if cache is not None:
            try:
                if cache.get("expires_at", 0) > now and isinstance(cache.get("models"), list):
                    return list(cache["models"]), True
            except Exception:
                pass

        url = f"{DATA_GEO_BASE}/api/v{int(self.api_major_version)}/geomodel?{urlencode({'geoareaid': int(self.geoareaid)})}"
        models = self._get_json_auth_retry_401(url)
        if not isinstance(models, list):
            raise GeoDKError("Unexpected /geomodel response shape", url=url, detail=str(type(models)))

        self._geomodel_cache = {
            "expires_at": now + float(self.geomodel_cache_ttl_s),
            "models": models,
        }
        return list(models), False

    def geomodels_for_path(self, path_25832: list[list[float]]) -> tuple[list[dict[str, Any]], bool]:
        """Return (matching_models + terrain_fallback, cache_hit)."""
        models, cache_hit = self.geomodels()
        pb = path_bbox(path_25832)
        matching: list[dict[str, Any]] = []
        if pb is not None:
            for m in models:
                if not isinstance(m, dict):
                    continue
                bbox_raw = m.get("BoundingBox")
                if not isinstance(bbox_raw, dict):
                    continue
                try:
                    mb = BBox(
                        float(bbox_raw["MinX"]),
                        float(bbox_raw["MinY"]),
                        float(bbox_raw["MaxX"]),
                        float(bbox_raw["MaxY"]),
                    )
                except Exception:
                    continue
                if mb.intersects(pb):
                    matching.append(m)

        # QGIS behavior: add terrain fallback at the end.
        matching.append({"ID": -1, "Name": "DHM/Terræn Model, 0.4m"})
        return matching, cache_hit

    def crosssection(
        self,
        *,
        path_25832: list[list[float]],
        geomodelid: int,
        width: int = 1000,
        height: int = 320,
        maxdepth: int = -40,
        linepointdistance: int = 10,
        srid: int = 25832,
    ) -> dict[str, Any]:
        if not isinstance(path_25832, list) or len(path_25832) < 2:
            raise GeoDKError("path_25832 must be a list of at least 2 [x,y] points")

        query = {
            "geoareaid": int(self.geoareaid),
            "path": json.dumps(path_25832, separators=(",", ":")),
            "geomodelid": int(geomodelid),
            "width": int(width),
            "height": int(height),
            "linepointdistance": int(linepointdistance),
            "maxdepth": int(maxdepth),
            "srid": int(srid),
            "format": "application/json",
        }
        url = f"{DATA_GEO_BASE}/api/v{int(self.api_major_version)}/crosssection?{urlencode(query)}"
        data = self._get_json_auth_retry_401(url)
        if not isinstance(data, dict):
            raise GeoDKError("Unexpected /crosssection response shape", url=url, detail=str(type(data)))
        return data
