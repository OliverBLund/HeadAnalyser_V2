"""
HeadAnalyser plot template registry.

Templates are intentionally data-only. They map a named visual intent to the
same MainWindow attributes already consumed by PlotWidget and PlotSidebar.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Tuple


ALL_PLOT_TYPES = (
    "2D",
    "3D",
    "Gradient Vectors",
    "Histogram",
    "Rose Diagram",
)

DEFAULT_TEMPLATE_KEY = "hydraulic_field"


@dataclass(frozen=True)
class PlotTemplate:
    key: str
    name: str
    category: str
    description: str
    plot_types: Tuple[str, ...]
    settings: Dict[str, Any]
    palette: Tuple[str, ...]
    preview_mode: str = "contour"
    preview_background: str = "#ffffff"
    is_built_in: bool = True

    def applies_to(self, plot_type: str | None) -> bool:
        if not plot_type:
            return True
        return "All" in self.plot_types or plot_type in self.plot_types

    def settings_for(self, plot_type: str | None = None) -> Dict[str, Any]:
        # The current templates are shared dictionaries, but this hook keeps the
        # registry ready for future plot-type-specific overrides.
        return dict(self.settings)


def _settings(**kwargs: Any) -> Dict[str, Any]:
    return dict(kwargs)


_TEMPLATES: Tuple[PlotTemplate, ...] = (
    PlotTemplate(
        key="hydraulic_field",
        name="Hydraulic Field",
        category="Hydraulic",
        description="Working template for head surfaces with filled contours, readable points, and a compact label mode.",
        plot_types=("2D", "3D"),
        preview_mode="contour",
        preview_background="#f8fbff",
        palette=("#0ea5e9", "#2563eb", "#22c55e", "#f59e0b"),
        settings=_settings(
            current_plot_style="Default",
            current_popup_style="Clean",
            colormap_2d="turbo",
            colormap_3d="turbo",
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
        preview_mode="contour",
        preview_background="#ffffff",
        palette=("#2563eb", "#38bdf8", "#94a3b8", "#111827"),
        settings=_settings(
            current_plot_style="Publication",
            current_popup_style="Compact",
            colormap_2d="viridis",
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
        preview_mode="contour",
        preview_background="#fbfbfd",
        palette=("#4f46e5", "#06b6d4", "#64748b", "#22c55e"),
        settings=_settings(
            current_plot_style="Minimal",
            current_popup_style="Compact",
            colormap_2d="viridis",
            colormap_3d="viridis",
            colormap_vectors="viridis",
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
        description="High-contrast visuals for screen sharing, with larger typography and saturated gradients.",
        plot_types=("All",),
        preview_mode="contour",
        preview_background="#f8fafc",
        palette=("#7c3aed", "#0ea5e9", "#f97316", "#22c55e"),
        settings=_settings(
            current_plot_style="Scientific",
            current_popup_style="Accent",
            colormap_2d="turbo",
            colormap_3d="turbo",
            colormap_vectors="plasma",
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
            histogram_bar_color="purple",
            histogram_edge_color="white",
            rose_color="purple",
        ),
    ),
    PlotTemplate(
        key="vector_audit",
        name="Vector Audit",
        category="Diagnostics",
        description="Gradient-vector inspection with mean vector, strong contrast, and uncluttered labels.",
        plot_types=("Gradient Vectors",),
        preview_mode="vector",
        preview_background="#f8fafc",
        palette=("#2563eb", "#0ea5e9", "#f97316", "#111827"),
        settings=_settings(
            current_plot_style="Scientific",
            current_popup_style="Clean",
            colormap_vectors="plasma",
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
        description="3D surface view with contextual points and a smooth color ramp for terrain-like head variation.",
        plot_types=("3D",),
        preview_mode="surface",
        preview_background="#f8fbff",
        palette=("#1d4ed8", "#38bdf8", "#facc15", "#f97316"),
        settings=_settings(
            current_plot_style="Default",
            current_popup_style="Clean",
            colormap_3d="RdYlBu",
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
        description="Readable histogram and rose diagram defaults for reports, with central tendency overlays enabled.",
        plot_types=("Histogram", "Rose Diagram"),
        preview_mode="stats",
        preview_background="#ffffff",
        palette=("#0f766e", "#14b8a6", "#94a3b8", "#111827"),
        settings=_settings(
            current_plot_style="Publication",
            current_popup_style="Compact",
            show_grid=True,
            histogram_bins=32,
            histogram_bar_color="teal",
            histogram_edge_color="black",
            histogram_show_mean=True,
            histogram_show_median=True,
            histogram_show_ci=True,
            histogram_ci_level=95,
            histogram_show_kde=True,
            rose_mode="gradient_weighted",
            rose_bins=24,
            rose_color="teal",
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
        preview_mode="stats",
        preview_background="#ffffff",
        palette=("#111827", "#64748b", "#cbd5e1", "#f8fafc"),
        settings=_settings(
            current_plot_style="Publication",
            current_popup_style="Compact",
            colormap_2d="Blues",
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
            histogram_bar_color="grey",
            histogram_edge_color="black",
            histogram_show_mean=True,
            histogram_show_median=True,
            rose_color="blue",
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
