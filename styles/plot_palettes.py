"""
HeadAnalyser plot color-style registry.

Color styles own data colors only: colormaps, marker/label accent colors, and
statistics colors. Plot formats own typography, ticks, grid, and spines.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Tuple


DEFAULT_PALETTE_KEY = "hydraulic"
CUSTOM_PALETTE_KEY = "custom"


COLOR_SETTING_KEYS = frozenset(
    {
        "colormap_2d",
        "colormap_3d",
        "colormap_vectors",
        "histogram_bar_color",
        "histogram_edge_color",
        "rose_color",
        "id_label_color",
        "head_label_color",
        "arrow_color",
    }
)


@dataclass(frozen=True)
class PlotPalette:
    key: str
    name: str
    category: str
    description: str
    settings: Dict[str, Any]
    swatches: Tuple[str, ...]
    is_built_in: bool = True

    def settings_for(self, _plot_type: str | None = None) -> Dict[str, Any]:
        return dict(self.settings)


def _settings(**kwargs: Any) -> Dict[str, Any]:
    return dict(kwargs)


_PALETTES: Tuple[PlotPalette, ...] = (
    PlotPalette(
        key="hydraulic",
        name="Hydraulic",
        category="Field",
        description="HeadAnalyser default with saturated hydraulic gradients and blue-violet labels.",
        swatches=("#0ea5e9", "#2563eb", "#22c55e", "#f59e0b"),
        settings=_settings(
            colormap_2d="turbo",
            colormap_3d="turbo",
            colormap_vectors="viridis",
            histogram_bar_color="teal",
            histogram_edge_color="black",
            rose_color="teal",
            id_label_color="#818cf8",
            head_label_color="#64748b",
            arrow_color="#818cf8",
        ),
    ),
    PlotPalette(
        key="blue_report",
        name="Blue Report",
        category="Report",
        description="Restrained blue scale for reports, appendices, and PDF export.",
        swatches=("#1d4ed8", "#38bdf8", "#94a3b8", "#111827"),
        settings=_settings(
            colormap_2d="Blues",
            colormap_3d="Blues",
            colormap_vectors="viridis",
            histogram_bar_color="blue",
            histogram_edge_color="black",
            rose_color="blue",
            id_label_color="#2563eb",
            head_label_color="#475569",
            arrow_color="#2563eb",
        ),
    ),
    PlotPalette(
        key="grayscale",
        name="Grayscale",
        category="Print",
        description="Low-color print style for papers, appendices, and photocopied figures.",
        swatches=("#111827", "#64748b", "#cbd5e1", "#f8fafc"),
        settings=_settings(
            colormap_2d="Greys",
            colormap_3d="Greys",
            colormap_vectors="Greys",
            histogram_bar_color="grey",
            histogram_edge_color="black",
            rose_color="grey",
            id_label_color="#111827",
            head_label_color="#6b7280",
            arrow_color="#111827",
        ),
    ),
    PlotPalette(
        key="thermal_gradient",
        name="Thermal Gradient",
        category="Diagnostics",
        description="High separation palette for gradient diagnostics and presentations.",
        swatches=("#7c3aed", "#0ea5e9", "#f97316", "#22c55e"),
        settings=_settings(
            colormap_2d="turbo",
            colormap_3d="turbo",
            colormap_vectors="plasma",
            histogram_bar_color="purple",
            histogram_edge_color="white",
            rose_color="purple",
            id_label_color="#7c3aed",
            head_label_color="#64748b",
            arrow_color="#f97316",
        ),
    ),
    PlotPalette(
        key="surface_context",
        name="Surface Context",
        category="Field",
        description="Terrain-like ramp for 3D surfaces and contextual head variation.",
        swatches=("#1d4ed8", "#38bdf8", "#facc15", "#f97316"),
        settings=_settings(
            colormap_2d="RdYlBu",
            colormap_3d="RdYlBu",
            colormap_vectors="viridis",
            histogram_bar_color="blue",
            histogram_edge_color="black",
            rose_color="blue",
            id_label_color="#2563eb",
            head_label_color="#64748b",
            arrow_color="#2563eb",
        ),
    ),
    PlotPalette(
        key="statistical_teal",
        name="Statistical Teal",
        category="Statistics",
        description="Teal-forward statistics palette for histogram and rose outputs.",
        swatches=("#0f766e", "#14b8a6", "#94a3b8", "#111827"),
        settings=_settings(
            colormap_2d="viridis",
            colormap_3d="viridis",
            colormap_vectors="viridis",
            histogram_bar_color="teal",
            histogram_edge_color="black",
            rose_color="teal",
            id_label_color="#0f766e",
            head_label_color="#64748b",
            arrow_color="#0f766e",
        ),
    ),
    PlotPalette(
        key=CUSTOM_PALETTE_KEY,
        name="Custom",
        category="Custom",
        description="Manual color choices from the sidebar or settings dialog.",
        swatches=("#64748b", "#94a3b8", "#cbd5e1", "#f8fafc"),
        settings=_settings(),
        is_built_in=False,
    ),
)


def all_palettes(*, include_custom: bool = True) -> Tuple[PlotPalette, ...]:
    if include_custom:
        return _PALETTES
    return tuple(p for p in _PALETTES if p.is_built_in)


def get_palette(palette_key: str | None) -> PlotPalette:
    key = palette_key or DEFAULT_PALETTE_KEY
    for palette in _PALETTES:
        if palette.key == key:
            return palette
    for palette in _PALETTES:
        if palette.key == DEFAULT_PALETTE_KEY:
            return palette
    return _PALETTES[0]


def palette_settings(palette_key: str | None, plot_type: str | None = None) -> Dict[str, Any]:
    return get_palette(palette_key).settings_for(plot_type)


def category_names(palettes: Iterable[PlotPalette] | None = None) -> Tuple[str, ...]:
    palettes = tuple(palettes or _PALETTES)
    preferred = ("Field", "Report", "Print", "Diagnostics", "Statistics", "Custom")
    present = {p.category for p in palettes}
    ordered = [name for name in preferred if name in present]
    ordered.extend(sorted(present - set(ordered)))
    return tuple(ordered)


def apply_palette_to_target(target: Any, palette_key: str | None, plot_type: str | None = None) -> PlotPalette:
    palette = get_palette(palette_key)
    for attr, value in palette.settings_for(plot_type).items():
        setattr(target, attr, value)
    setattr(target, "current_color_style", palette.key)
    return palette

