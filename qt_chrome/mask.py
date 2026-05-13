"""Rounded-mask helper for frameless windows."""

from __future__ import annotations

from PyQt5.QtCore import QRectF
from PyQt5.QtGui import QPainterPath, QRegion


def apply_frameless_round_mask(
    window,
    *,
    enabled: bool,
    is_effectively_maximized: bool,
    corner_radius_px: int = 10,
) -> None:
    """Apply a rounded mask when frameless and not maximized/fullscreen."""
    if window is None:
        return
    if not enabled or is_effectively_maximized or window.isFullScreen():
        window.clearMask()
        return

    rect = window.rect()
    if rect.width() < 4 or rect.height() < 4:
        return

    radius = max(2, int(corner_radius_px))
    path = QPainterPath()
    path.addRoundedRect(QRectF(rect), radius, radius)
    window.setMask(QRegion(path.toFillPolygon().toPolygon()))

