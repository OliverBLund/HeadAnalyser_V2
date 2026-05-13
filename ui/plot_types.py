"""Canonical plot-type mappings and normalization helpers."""

from __future__ import annotations

from typing import Optional


INTERNAL_PLOT_TYPES = (
    "2D",
    "3D",
    "Gradient Vectors",
    "Histogram",
    "Rose Diagram",
)

DEFAULT_INTERNAL_PLOT_TYPE = "2D"

# Labels shown in the plot toolbar combo box.
TOOLBAR_LABEL_TO_INTERNAL = {
    "2D Hydraulic Head": "2D",
    "3D Surface": "3D",
    "Gradient Vectors": "Gradient Vectors",
    "Gradient Histogram": "Histogram",
    "Rose Diagram": "Rose Diagram",
}

INTERNAL_TO_TOOLBAR_LABEL = {v: k for k, v in TOOLBAR_LABEL_TO_INTERNAL.items()}
TOOLBAR_PLOT_LABELS = tuple(TOOLBAR_LABEL_TO_INTERNAL.keys())

# Legacy aliases observed in persisted state.
LEGACY_PLOT_TYPE_ALIASES = {
    "Contour & Gradient": "2D",
}


def normalize_plot_type(value: Optional[str]) -> str:
    """Normalize internal/display/legacy plot type names to canonical internal names."""
    raw = str(value or "").strip()
    if not raw:
        return DEFAULT_INTERNAL_PLOT_TYPE

    # Canonical internal value.
    if raw in INTERNAL_PLOT_TYPES:
        return raw

    # Toolbar/display label -> internal.
    mapped = TOOLBAR_LABEL_TO_INTERNAL.get(raw)
    if mapped:
        return mapped

    # Legacy aliases.
    mapped = LEGACY_PLOT_TYPE_ALIASES.get(raw)
    if mapped:
        return mapped

    # Case-insensitive fallback.
    low = raw.lower()
    for candidate in INTERNAL_PLOT_TYPES:
        if candidate.lower() == low:
            return candidate
    for label, candidate in TOOLBAR_LABEL_TO_INTERNAL.items():
        if label.lower() == low:
            return candidate
    for label, candidate in LEGACY_PLOT_TYPE_ALIASES.items():
        if label.lower() == low:
            return candidate

    return DEFAULT_INTERNAL_PLOT_TYPE


def to_toolbar_label(internal_plot_type: Optional[str]) -> str:
    """Return toolbar label for canonical internal type."""
    canonical = normalize_plot_type(internal_plot_type)
    return INTERNAL_TO_TOOLBAR_LABEL.get(canonical, INTERNAL_TO_TOOLBAR_LABEL[DEFAULT_INTERNAL_PLOT_TYPE])

