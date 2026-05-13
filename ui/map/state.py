"""State defaults/constants for MapWidget."""

MAP_COLORS = {
    "points": "#60a5fa",
    "excluded": "#6e6e7a",
    "external": "#22c55e",
    "selected": "#60a5fa",
    "rejection": "#f87171",
    "coverage": "#4ade80",
    "contours": "#a78bfa",
    "vectors": "#fbbf24",
    "transect": "#f472b6",
}

# Transect naming: A-A', B-B', ... J-J' (10 max)
TRANSECT_NAMES = ["A-A'", "B-B'", "C-C'", "D-D'", "E-E'", "F-F'", "G-G'", "H-H'", "I-I'", "J-J'"]

# Transect line colors (cycling through for visual distinction)
TRANSECT_COLORS = [
    "#f472b6",  # Pink
    "#60a5fa",  # Blue
    "#4ade80",  # Green
    "#fbbf24",  # Yellow
    "#a78bfa",  # Purple
    "#f87171",  # Red
    "#22d3ee",  # Cyan
    "#fb923c",  # Orange
    "#c084fc",  # Violet
    "#34d399",  # Emerald
]

MAP_TILE_PROVIDERS = {
    "OpenStreetMap": "OpenStreetMap",
    "CartoDB Positron": "CartoDB positron",
    "CartoDB Dark Matter": "CartoDB dark_matter",
    "Esri World Imagery": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
}


def initialize_map_widget_state(widget):
    """Populate MapWidget instance state with canonical defaults."""
    widget._transformer = None
    widget._current_tile = "OpenStreetMap"
    widget._current_data = None
    widget._current_col_mapping = None
    widget._current_triangle_data = None
    widget._current_gradient_data = None
    widget._current_rejected_data = None
    widget._excluded_ids = set()
    widget._selected_id = None
    widget._selected_point_data = None
    widget._point_data_map = {}
    widget._point_data_by_id = {}
    widget._show_labels = False
    widget._show_heatmap = True
    widget._heatmap_opacity = 0.5
    widget._heatmap_mode = "smooth"
    widget._point_size = 8
    widget._render_point_size = 8
    widget._show_scale_bar = True
    widget._sync_selection = True
    widget._show_points = True
    widget._show_excluded = True
    widget._show_external = True
    widget._color_points_by_head = False
    widget._show_vectors = False
    widget._show_main_arrow = False
    widget._show_contours = True
    widget._show_contour_labels = True
    widget._contour_label_precision = 2
    widget._contour_major_interval = 2
    widget._contour_fill_opacity = 0.22
    widget._contour_label_font_size = 12
    widget._contour_legend = {"enabled": False, "gradient": "", "min_label": "-", "max_label": "-"}
    widget._point_legend = {"available": False, "gradient": "", "min_label": "-", "max_label": "-"}
    widget._show_coverage = False
    widget._transect_mode = False
    widget._transect_coords = None
    # Multi-transect storage: list of dicts with {id, name, coords, svg_data, legend_html}
    widget._transects = []
    widget._active_transect_id = None
    widget._next_transect_num = 1
    widget._restoring_transect = False  # Flag to prevent re-storing data when restoring
    widget._external_layers = []
    widget._last_bounds_signature = None
    widget._last_render_signature = None
    widget._last_render_kind = "empty"
    widget._last_view_state = None
