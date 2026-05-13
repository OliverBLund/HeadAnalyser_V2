"""
Shared contour interpolation utilities for PlotWidget and MapWidget.
"""

from __future__ import annotations

from typing import Optional, Tuple

import numpy as np


def _normalize_method(method: str) -> str:
    m = str(method or "cubic").strip().lower()
    return m if m in {"nearest", "linear", "cubic"} else "cubic"


def _normalize_extrapolation(extrapolation: str) -> str:
    e = str(extrapolation or "none").strip().lower()
    return e if e in {"none", "nearest", "idw"} else "none"


def fill_idw(
    zi: np.ndarray,
    xi: np.ndarray,
    yi: np.ndarray,
    x_pts: np.ndarray,
    y_pts: np.ndarray,
    v_pts: np.ndarray,
    power: float = 2.0,
) -> np.ndarray:
    """Fill NaNs in an interpolated grid using inverse-distance weighting."""
    try:
        flat = zi.reshape(-1)
        xi_flat = xi.reshape(-1)
        yi_flat = yi.reshape(-1)
        nan_idx = np.where(np.isnan(flat))[0]
        if nan_idx.size == 0:
            return zi

        x_pts = np.asarray(x_pts, dtype=float)
        y_pts = np.asarray(y_pts, dtype=float)
        v_pts = np.asarray(v_pts, dtype=float)

        for i in nan_idx:
            xg = float(xi_flat[i])
            yg = float(yi_flat[i])
            dx = x_pts - xg
            dy = y_pts - yg
            dist2 = dx * dx + dy * dy
            if dist2.size == 0:
                continue
            if np.any(dist2 == 0):
                flat[i] = float(v_pts[np.argmin(dist2)])
                continue
            w = 1.0 / np.power(dist2, power / 2.0)
            w_sum = float(np.sum(w))
            if w_sum > 0.0:
                flat[i] = float(np.sum(w * v_pts) / w_sum)
        return flat.reshape(zi.shape)
    except Exception:
        return zi


def compute_contour_grid(
    x: np.ndarray,
    y: np.ndarray,
    h: np.ndarray,
    interpolation_method: str = "cubic",
    contour_extent_pct: float = 0.0,
    contour_extrapolation: str = "none",
    grid_resolution: int = 100,
) -> Optional[Tuple[np.ndarray, np.ndarray, np.ndarray]]:
    """
    Compute contour interpolation grid using the same pathway for map and plot.

    Returns (xi, yi, zi) or None when the input is insufficient/invalid.
    """
    try:
        from scipy.interpolate import griddata
    except Exception:
        return None

    try:
        x = np.asarray(x, dtype=float)
        y = np.asarray(y, dtype=float)
        h = np.asarray(h, dtype=float)
        valid = np.isfinite(x) & np.isfinite(y) & np.isfinite(h)
        x = x[valid]
        y = y[valid]
        h = h[valid]
        if x.size < 4:
            return None

        extent_pct = float(contour_extent_pct or 0.0)
        extent_pct = max(0.0, min(extent_pct, 50.0))
        x_min, x_max = float(np.min(x)), float(np.max(x))
        y_min, y_max = float(np.min(y)), float(np.max(y))
        pad_x = (x_max - x_min) * (extent_pct / 100.0)
        pad_y = (y_max - y_min) * (extent_pct / 100.0)

        n = int(max(25, min(int(grid_resolution or 100), 300)))
        xi = np.linspace(x_min - pad_x, x_max + pad_x, n)
        yi = np.linspace(y_min - pad_y, y_max + pad_y, n)
        xi, yi = np.meshgrid(xi, yi)

        method = _normalize_method(interpolation_method)
        zi = griddata((x, y), h, (xi, yi), method=method)
        if zi is None:
            zi = griddata((x, y), h, (xi, yi), method="linear")
        if zi is None:
            return None

        extrap = _normalize_extrapolation(contour_extrapolation)
        if extrap in {"nearest", "idw"} and np.isnan(zi).any():
            if extrap == "nearest":
                zi_near = griddata((x, y), h, (xi, yi), method="nearest")
                zi = np.where(np.isnan(zi), zi_near, zi)
            else:
                zi = fill_idw(zi, xi, yi, x, y, h)

        return xi, yi, zi
    except Exception:
        return None

