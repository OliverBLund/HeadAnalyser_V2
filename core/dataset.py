"""
HeadAnalyser V2 - Dataset State Container.

Each Dataset instance is the persistent source of truth for one tab:
- raw and filtered dataframes,
- exclusion/selection state,
- plot + map settings,
- derived analysis outputs (triangles/gradients/rejections),
- per-dataset filter bounds/ranges.

MainWindow syncs this state into legacy compatibility attributes when a tab is active.
"""

import pandas as pd


class Dataset:
    """Container for a single dataset with all associated data and settings."""

    def __init__(self, name: str = "Untitled"):
        """Initialize a new dataset."""
        self.name = name  # Dataset display name
        self.file_path = None  # Source file path

        # Data
        self.data = None  # Original data
        self.filtered_data = None  # Filtered data
        self.filtered_plot_data = None  # Filtered for plotting (before exclusion removal)
        self.triangle_data = None  # Gradient triangle data
        self.gradient_data = None  # Gradient data
        self.rejected_data = None  # Rejected triangles
        self.sensitivity_analysis_result = None  # Optional diagnostic output

        # Column mapping
        self.col_mapping = {
            'ID': None,
            'x': None,
            'y': None,
            'hydraulic head': None
        }
        self.top_column = None
        self.bottom_column = None
        self.depth_column = None

        # Exclusions
        self.excluded_ids = set()
        self.excluded_member_keys = set()

        # Selection (persisted across plot switches; cleared on recompute)
        self.selected_triangle_indices = set()  # triangle_data index values
        self.selection_meta = None  # dict describing selection source/range
        self.show_triangle_selection_overlay = False

        # Plot settings
        self.current_plot_type = "2D"
        self.show_contours = False
        self.show_colorbar = True
        self.show_id_labels = True
        self.show_head_labels = True
        self.label_mode_2d = "all"
        self.show_excluded_points = True
        self.custom_excluded_style = False
        self.excluded_marker = "x"
        self.excluded_color = "#6a6a6a"
        self.excluded_opacity = 0.3
        self.excluded_size_scale = 0.75
        self.sync_xy_major_ticks = False
        self.show_compass = True
        self.show_arrow = True
        self.show_grid = False
        self.show_legend = False
        self.current_plot_style = "Default"

        # Plot-specific options
        self.colormap_2d = "viridis"
        self.point_size = 80
        # Point glow effect
        self.show_point_glow = True
        self.point_glow_size_multiplier = 2.2
        self.point_glow_alpha = 0.12
        self.contour_levels = 10
        self.fill_contours = False
        self.contour_extent_pct = 0
        self.contour_extrapolation = "none"
        self.elevation_3d = 30
        self.azimuth_3d = 45
        self.colormap_3d = "viridis"
        self.vector_scale = 5.0
        self.vector_alpha = 0.7
        self.colormap_vectors = "viridis"
        self.histogram_bins = 30
        self.histogram_bar_color = "grey"
        self.histogram_edge_color = "black"
        self.histogram_show_mean = False
        self.histogram_show_median = False
        self.histogram_show_ci = False
        self.histogram_ci_level = 95
        self.histogram_ci_resamples = 200
        self.rose_bins = 16
        self.rose_show_mean = True
        self.rose_show_weighted_mean = True
        self.rose_show_ci = False
        self.rose_ci_level = 95
        self.rose_ci_resamples = 200
        self.rose_mode = "count"
        self.rose_color = "blue"

        # Advanced customization options
        self.marker_size = 80
        self.id_font_size = 9
        self.head_font_size = 8
        self.label_offset = 10
        self.axis_tick_font_size = 9
        self.axis_label_font_size = 11
        self.x_axis_label = "X Coordinate [m]"
        self.y_axis_label = "Y Coordinate [m]"
        self.id_label_color = "#818cf8"
        self.head_label_color = "#a0a0a0"
        self.arrow_color = "#818cf8"
        self.arrow_start_x = None
        self.arrow_start_y = None
        self.interpolation_method = "cubic"
        self.surface_alpha = 0.8
        self.show_wireframe = False
        self.contour_linewidth = 0.8
        self.contour_label_font_size = 9
        self.show_vector_id_labels = False
        self.max_vector_count = 5000
        self.show_vector_points = True
        self.show_geology_strip_experimental = True
        self.show_stacked_points_experimental = True
        self.stacked_intake_choice_map = {}

        # Map display settings (persisted per-dataset, consumed by MapWidget)
        # These correspond to the Display Settings and Sync sections in the concept UI.
        self.map_heatmap_opacity = 0.5       # 0.0–1.0
        self.map_point_size = 8              # pixels
        self.map_show_labels = False
        self.map_show_scale_bar = True
        self.map_sync_selection_with_plot = True

        # Geo.dk transect history (for experimental multi-transect/fence rendering).
        # Item shape:
        # {
        #   "id": str,
        #   "source": "map" | "plot",
        #   "path_utm": [[x,y], ...],
        #   "path_latlon": [[lat,lon], ...],
        #   "length_m": float,
        #   "created_at": float (epoch seconds),
        # }
        self.geodk_transect_history = []

        # Filter ranges
        self.depth_range = (0, 100)
        self.head_range = (0, 100)
        self.depth_bounds = None
        self.head_bounds = None

        # Gradient calculation constraints (match Excel defaults)
        # Note: confidence level is currently informational; the algorithm uses `head_uncertainty` directly.
        self.gradient_head_uncertainty = 0.01
        self.gradient_confidence_level = 0.66
        self.gradient_base_height_low = 0.2
        self.gradient_base_height_high = 8.0
        self.gradient_max_base_or_height = 1e9
        self.gradient_stacked_epsilon = 1e-10

        # Triangle stats (derived from current filtered dataset + constraints)
        self.total_triangles = None
        self.rejected_due_to_uncertainty = None
        self.rejected_due_to_triangle_quality = None
        self.rejected_due_to_calculation_failed = None


    def has_data(self):
        """Check if dataset has loaded data."""
        return self.data is not None and not self.data.empty

    def get_point_count(self):
        """Get number of data points."""
        if self.filtered_data is not None:
            return len(self.filtered_data)
        elif self.data is not None:
            return len(self.data)
        return 0

    def get_triangle_count(self):
        """Get number of triangles."""
        if self.triangle_data is not None:
            return len(self.triangle_data)
        return 0

    def clear(self):
        """Clear all data."""
        self.data = None
        self.filtered_data = None
        self.filtered_plot_data = None
        self.triangle_data = None
        self.gradient_data = None
        self.rejected_data = None
        self.sensitivity_analysis_result = None
        self.excluded_ids = set()
        self.excluded_member_keys = set()
        self.selected_triangle_indices = set()
        self.selection_meta = None
        self.show_triangle_selection_overlay = False
