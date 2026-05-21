"""
HeadAnalyser plot template registry.

Templates are recipes composed from three layers:
- color style: data colors and colormaps from styles.plot_palettes
- format: typography, spines, ticks, and grid from styles.plot_styles
- plot defaults: overlays, labels, contour density, statistics options, etc.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Tuple

from .plot_palettes import DEFAULT_PALETTE_KEY, get_palette, palette_settings


ALL_PLOT_TYPES = (
    "2D",
    "3D",
    "Gradient Vectors",
    "Histogram",
    "Rose Diagram",
)

DEFAULT_TEMPLATE_KEY = "hydraulic_field"
DEFAULT_FORMAT_KEY = "Default"


@dataclass(frozen=True)
class PlotTemplate:
    key: str
    name: str
    category: str
    description: str
    plot_types: Tuple[str, ...]
    format_key: str
    palette_key: str
    settings: Dict[str, Any]
    preview_mode: str = "contour"
    preview_background: str = "#ffffff"
    is_built_in: bool = True

    @property
    def palette(self) -> Tuple[str, ...]:
        return get_palette(self.palette_key).swatches

    def applies_to(self, plot_type: str | None) -> bool:
        if not plot_type:
            return True
        return "All" in self.plot_types or plot_type in self.plot_types

    def settings_for(self, plot_type: str | None = None) -> Dict[str, Any]:
        """Return the composed target settings for this template."""
        format_key = self.format_key or DEFAULT_FORMAT_KEY
        palette_key = self.palette_key or DEFAULT_PALETTE_KEY

        composed = {
            "current_plot_template": self.key,
            "current_plot_format": format_key,
            # Compatibility alias used by existing PlotWidget rendering code.
            "current_plot_style": format_key,
            "current_color_style": palette_key,
        }
        composed.update(palette_settings(palette_key, plot_type))
        composed.update(self.settings)
        return composed


def _settings(**kwargs: Any) -> Dict[str, Any]:
    return dict(kwargs)


_TEMPLATES: Tuple[PlotTemplate, ...] = (
    PlotTemplate(
        key="hydraulic_field",
        name="Hydraulic Field",
        category="Hydraulic",
        description="Working view for head surfaces with filled contours, readable points, and compact labels.",
        plot_types=("2D", "3D"),
        format_key="Default",
        palette_key="hydraulic",
        preview_mode="contour",
        preview_background="#f8fbff",
        settings=_settings(
            current_popup_style="Clean",
            show_points=True,
            show_contours=True,
            fill_contours=True,
            contour_levels=12,
            contour_linewidth=0.75,
            contour_label_font_size=8,
            show_colorbar=True,
            show_id_labels=True,
            show_head_labels=False,
            label_mode_2d="smart",
            id_font_size=8,
            head_font_size=7,
            point_size=74,
            marker_size=74,
            show_point_glow=True,
            point_glow_size_multiplier=2.0,
            point_glow_alpha=0.11,
            show_arrow=True,
            show_arrow_label=True,
            show_grid=False,
            interpolation_method="cubic",
        ),
    ),
    PlotTemplate(
        key="contour_report",
        name="Contour Report",
        category="Report",
        description="Clean report-ready contour map with restrained labels and publication axes.",
        plot_types=("2D",),
        format_key="Publication",
        palette_key="blue_report",
        preview_mode="contour",
        preview_background="#ffffff",
        settings=_settings(
            current_popup_style="Compact",
            show_points=True,
            show_contours=True,
            fill_contours=False,
            contour_levels=10,
            contour_linewidth=0.65,
            contour_label_font_size=8,
            show_colorbar=True,
            show_id_labels=True,
            show_head_labels=False,
            label_mode_2d="smart",
            id_font_size=8,
            head_font_size=7,
            point_size=58,
            marker_size=58,
            show_point_glow=False,
            show_arrow=True,
            show_arrow_label=False,
            show_grid=True,
        ),
    ),
    PlotTemplate(
        key="compact_review",
        name="Compact Review",
        category="Review",
        description="Dense inspection view for smaller screens: reduced point size, fewer labels, and minimal axes.",
        plot_types=("All",),
        format_key="Minimal",
        palette_key="blue_report",
        preview_mode="contour",
        preview_background="#fbfbfd",
        settings=_settings(
            current_popup_style="Compact",
            show_points=True,
            show_contours=True,
            fill_contours=False,
            contour_levels=8,
            show_colorbar=True,
            show_id_labels=True,
            show_head_labels=False,
            label_mode_2d="smart",
            id_font_size=7,
            head_font_size=7,
            point_size=52,
            marker_size=52,
            show_point_glow=False,
            show_arrow=True,
            show_arrow_label=False,
            show_grid=False,
            vector_alpha=0.72,
            histogram_bins=24,
            rose_bins=16,
        ),
    ),
    PlotTemplate(
        key="presentation_gradient",
        name="Presentation Gradient",
        category="Presentation",
        description="High-contrast screen-sharing defaults with larger typography and saturated gradients.",
        plot_types=("All",),
        format_key="Scientific",
        palette_key="thermal_gradient",
        preview_mode="contour",
        preview_background="#f8fafc",
        settings=_settings(
            current_popup_style="Accent",
            show_points=True,
            show_contours=True,
            fill_contours=True,
            contour_levels=14,
            show_colorbar=True,
            show_id_labels=False,
            show_head_labels=False,
            label_mode_2d="off",
            axis_label_font_size=13,
            axis_tick_font_size=11,
            point_size=90,
            marker_size=90,
            show_point_glow=True,
            point_glow_size_multiplier=2.25,
            point_glow_alpha=0.14,
            show_arrow=True,
            show_arrow_label=True,
            show_grid=False,
            histogram_bins=28,
        ),
    ),
    PlotTemplate(
        key="vector_audit",
        name="Vector Audit",
        category="Diagnostics",
        description="Gradient-vector inspection with mean vector, strong contrast, and uncluttered labels.",
        plot_types=("Gradient Vectors",),
        format_key="Scientific",
        palette_key="thermal_gradient",
        preview_mode="vector",
        preview_background="#f8fafc",
        settings=_settings(
            current_popup_style="Clean",
            show_points=True,
            show_vector_points=True,
            show_id_labels=False,
            show_head_labels=False,
            show_arrow=True,
            show_colorbar=True,
            show_grid=True,
            vector_scale=5.0,
            vector_alpha=0.85,
            show_mean_vector=True,
            normalize_vectors=False,
            marker_size=64,
            max_vector_count=8000,
        ),
    ),
    PlotTemplate(
        key="surface_context",
        name="Surface Context",
        category="Hydraulic",
        description="3D surface view with contextual points and a smooth terrain-like ramp.",
        plot_types=("3D",),
        format_key="Default",
        palette_key="surface_context",
        preview_mode="surface",
        preview_background="#f8fbff",
        settings=_settings(
            current_popup_style="Clean",
            show_points=True,
            show_colorbar=True,
            elevation_3d=32,
            azimuth_3d=45,
            surface_alpha=0.9,
            show_wireframe=False,
        ),
    ),
    PlotTemplate(
        key="statistics_report",
        name="Statistics Report",
        category="Statistics",
        description="Readable histogram and rose diagram defaults with central tendency overlays enabled.",
        plot_types=("Histogram", "Rose Diagram"),
        format_key="Publication",
        palette_key="statistical_teal",
        preview_mode="stats",
        preview_background="#ffffff",
        settings=_settings(
            current_popup_style="Compact",
            show_grid=True,
            histogram_bins=32,
            histogram_show_mean=True,
            histogram_show_median=True,
            histogram_show_ci=True,
            histogram_ci_level=95,
            histogram_show_kde=True,
            rose_mode="gradient_weighted",
            rose_bins=24,
            rose_show_mean=True,
            rose_show_weighted_mean=True,
            rose_show_ci=True,
            rose_ci_level=95,
            rose_show_mean_resultant=True,
            rose_show_median=True,
        ),
    ),
    PlotTemplate(
        key="print_grayscale",
        name="Print Grayscale",
        category="Report",
        description="Low-color figure setup for printouts and appendix exports.",
        plot_types=("2D", "Histogram", "Rose Diagram"),
        format_key="Publication",
        palette_key="grayscale",
        preview_mode="stats",
        preview_background="#ffffff",
        settings=_settings(
            current_popup_style="Compact",
            show_points=True,
            show_contours=True,
            fill_contours=False,
            contour_levels=9,
            show_colorbar=True,
            show_id_labels=False,
            show_head_labels=False,
            label_mode_2d="off",
            point_size=54,
            marker_size=54,
            show_point_glow=False,
            show_arrow=True,
            show_arrow_label=False,
            show_grid=True,
            histogram_bins=24,
            histogram_show_mean=True,
            histogram_show_median=True,
            rose_show_mean=True,
            rose_show_weighted_mean=False,
        ),
    ),
)


def all_templates() -> Tuple[PlotTemplate, ...]:
    return _TEMPLATES


def available_templates(plot_type: str | None = None) -> Tuple[PlotTemplate, ...]:
    return tuple(t for t in _TEMPLATES if t.applies_to(plot_type))


def get_template(template_key: str | None) -> PlotTemplate:
    key = template_key or DEFAULT_TEMPLATE_KEY
    for template in _TEMPLATES:
        if template.key == key:
            return template
    for template in _TEMPLATES:
        if template.key == DEFAULT_TEMPLATE_KEY:
            return template
    return _TEMPLATES[0]


def category_names(templates: Iterable[PlotTemplate] | None = None) -> Tuple[str, ...]:
    templates = tuple(templates or _TEMPLATES)
    preferred = ("Hydraulic", "Report", "Review", "Presentation", "Diagnostics", "Statistics")
    present = {t.category for t in templates}
    ordered = [name for name in preferred if name in present]
    ordered.extend(sorted(present - set(ordered)))
    return tuple(ordered)


def template_settings(template_key: str | None, plot_type: str | None = None) -> Dict[str, Any]:
    return get_template(template_key).settings_for(plot_type)


def apply_template_to_target(target: Any, template_key: str | None, plot_type: str | None = None) -> PlotTemplate:
    template = get_template(template_key)
    for attr, value in template.settings_for(plot_type).items():
        setattr(target, attr, value)
    setattr(target, "current_plot_template", template.key)
    return template

