"""
HeadAnalyser V2 - Main Window (Application Orchestrator).

This module is the canonical coordinator for cross-view data flow:
- Filter/exclusion pipeline entrypoint: `_run_filter_pipeline(...)`.
- Map payload dispatch entrypoint: `_update_map_view(...)`.
- Legacy-state <-> Dataset synchronization: `sync_from_dataset(...)` / `sync_to_dataset(...)`.

Design rule:
- Feature modules should request refreshes through MainWindow centralizers instead of
  calling lower-level filter/render methods directly.
"""

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QSplitter, QStatusBar, QLabel, QMessageBox, QFileDialog,
    QStackedWidget, QShortcut, QToolButton, QDialog, QInputDialog,
    QTabWidget, QTabBar, QFrame
)
from PyQt5.QtCore import Qt, QSize, QTimer, QThread, QSettings
from PyQt5.QtGui import QIcon, QKeySequence

from .header_bar import HeaderBar
from .navigation_sidebar import NavigationSidebar
from .properties_panel import PropertiesPanel
from .plot_page import PlotPage
from .map_widget import MapWidget
from .statistics_panel import StatisticsPanel
from .welcome_widget import WelcomeWidget
from .plot_types import normalize_plot_type, to_toolbar_label

from core.dataset import Dataset
from core.exclusion_state import apply_point_exclusion as apply_point_exclusion_state
from core.file_handler import FileHandler
from core.data_processing import DataProcessing
from core.gradient_calculation import GradientCalculation
from core.sensitivity_analysis import SensitivityAnalysisEngine
from core.coordinate_transform import wgs84_to_utm32
from core.point_creation_service import build_point_record, append_point, suggest_point_id
import numpy as np
import numbers
import os
import time
from types import SimpleNamespace
from concurrent.futures import ThreadPoolExecutor
from ui.dialogs.selection_inspector import SelectionInspectorDialog
from ui.dialogs.triangle_inspector import TriangleInspectorDialog
from styles.colors import Colors
from styles.stylesheet import StyleSheet
from styles.theme import build_qpalette
from qt_chrome import FramelessMainWindowMixin
from ui.scaling import build_screen_metrics
from ui.workers import FunctionWorker


class MainWindow(FramelessMainWindowMixin, QMainWindow):
    """Main application window for HeadAnalyser."""

    _DATASET_EXTRA_OPTION_ATTRS = (
        "show_legend",
        "current_plot_style",
        "current_popup_style",
        "colormap_2d",
        "point_size",
        "contour_levels",
        "fill_contours",
        "contour_extent_pct",
        "contour_extrapolation",
        "elevation_3d",
        "azimuth_3d",
        "colormap_3d",
        "vector_scale",
        "vector_alpha",
        "colormap_vectors",
        "show_mean_vector",
        "normalize_vectors",
        "histogram_bins",
        "histogram_bar_color",
        "histogram_edge_color",
        "histogram_show_mean",
        "histogram_show_median",
        "histogram_show_ci",
        "histogram_ci_level",
        "histogram_ci_resamples",
        "histogram_show_kde",
        "rose_bins",
        "rose_show_mean",
        "rose_show_weighted_mean",
        "rose_show_ci",
        "rose_ci_level",
        "rose_ci_resamples",
        "rose_mode",
        "rose_color",
        "rose_show_mean_resultant",
        "rose_show_median",
        "marker_size",
        "id_font_size",
        "head_font_size",
        "label_offset",
        "axis_tick_font_size",
        "axis_label_font_size",
        "x_axis_label",
        "y_axis_label",
        "id_label_color",
        "head_label_color",
        "arrow_color",
        "arrow_start_x",
        "arrow_start_y",
        "show_arrow_label",
        "interpolation_method",
        "surface_alpha",
        "show_wireframe",
        "contour_linewidth",
        "contour_label_font_size",
        "show_vector_id_labels",
        "max_vector_count",
        "show_vector_points",
        "show_geology_strip_experimental",
        "show_stacked_points_experimental",
        "stacked_intake_choice_map",
        "show_point_glow",
        "point_glow_size_multiplier",
        "point_glow_alpha",
    )

    def __init__(self):
        super().__init__()
        self._ui_theme = Colors.current_theme()
        self._screen_metrics = build_screen_metrics()
        self._screen_metrics_signature = None
        self._tracked_window_handle = None
        self.init_frameless_window_chrome(
            default_windows="frameless",
            default_other="native",
            resize_margin=10,
            top_resize_margin=10,
            enable_edge_resize=True,
        )
        self.setWindowTitle("HeadAnalyser")
        self.setMinimumSize(self._screen_metrics.min_window_size)
        self.resize(self._screen_metrics.initial_window_size)

        # Multi-dataset support
        self.datasets = {}  # {dataset_id: Dataset}
        self.active_dataset_id = None
        self.dataset_counter = 0
        self._creating_tab = False  # Flag to prevent on_tab_changed during creation
        self._target_locations_by_dataset = {}  # {dataset_id: {"xy": (x, y), "source": str}}
        self._point_creation_mode_by_dataset = {}  # {dataset_id: bool}

        # Legacy compatibility attributes (for backwards compatibility with handlers)
        # These will proxy to the active dataset
        self.data = None
        self.filtered_data = None
        self.filtered_plot_data = None
        self.triangle_data = None
        self.gradient_data = None
        self.rejected_data = None
        self.col_mapping = {'ID': None, 'x': None, 'y': None, 'hydraulic head': None}
        self.top_column = None
        self.bottom_column = None
        self.depth_column = None
        self.excluded_ids = set()
        self.excluded_member_keys = set()
        self.current_plot_type = "2D"

        # Cross-plot selection (triangles)
        self.selected_triangle_indices = set()
        self.selection_meta = None
        self.show_triangle_selection_overlay = False
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
        self.show_arrow_label = True
        self.arrow_color = Colors.ACCENT_PRIMARY
        self.show_grid = False
        self.show_legend = False
        self.current_plot_style = "Default"
        self.current_popup_style = "Clean"

        # Plot-specific options
        # 2D plot options
        self.colormap_2d = 'viridis'
        self.point_size = 80
        # Point glow effect settings (2D plot)
        self.show_point_glow = True
        self.point_glow_size_multiplier = 2.2
        self.point_glow_alpha = 0.12
        # Contour plot options
        self.contour_levels = 10
        self.fill_contours = False
        self.contour_extent_pct = 0
        self.contour_extrapolation = 'none'
        # 3D plot options
        self.elevation_3d = 30
        self.azimuth_3d = 45
        self.colormap_3d = 'viridis'
        # Vector plot options
        # Note: Matplotlib quiver uses an inverse scale (smaller value => longer arrows).
        self.vector_scale = 5.0
        self.vector_alpha = 0.8
        self.colormap_vectors = 'viridis'
        self.show_mean_vector = True
        self.normalize_vectors = False
        # Histogram options
        self.histogram_bins = 30
        self.histogram_bar_color = 'grey'
        self.histogram_edge_color = 'black'
        self.histogram_show_mean = False
        self.histogram_show_median = False
        self.histogram_show_ci = False
        self.histogram_ci_level = 95
        self.histogram_ci_resamples = 200
        self.histogram_show_kde = False
        # Rose diagram options
        self.rose_bins = 16
        self.rose_show_mean = True
        self.rose_show_weighted_mean = True
        self.rose_show_ci = False
        self.rose_ci_level = 95
        self.rose_ci_resamples = 200
        self.rose_mode = 'count'
        self.rose_color = 'blue'
        self.rose_show_mean_resultant = True
        self.rose_show_median = False

        # Advanced customization options (from dialog)
        # General
        self.marker_size = 80

        # Labels
        self.id_font_size = 9
        self.head_font_size = 8
        self.label_offset = 10
        self.axis_tick_font_size = 9
        self.axis_label_font_size = 11
        self.x_axis_label = "X Coordinate [m]"
        self.y_axis_label = "Y Coordinate [m]"

        # Colors
        self.id_label_color = "#818cf8"
        self.head_label_color = "#a0a0a0"
        self.arrow_color = "#818cf8"

        # 2D advanced
        self.arrow_start_x = None
        self.arrow_start_y = None
        self.interpolation_method = 'cubic'

        # 3D advanced
        self.surface_alpha = 0.8
        self.show_wireframe = False

        # Contour advanced
        self.contour_linewidth = 0.8
        self.contour_label_font_size = 9

        # Vectors advanced
        self.show_vector_id_labels = False
        # Only downsample vector-plot rendering for very large triangle sets.
        # This keeps moderate datasets (e.g., ~1k triangles from ~30 points) faithful to V1 when
        # users chose not to downsample.
        self.max_vector_count = 5000
        self.vector_scale = 5.0
        self.vector_alpha = 0.7
        self.show_vector_points = True
        self.show_geology_strip_experimental = True
        self.show_stacked_points_experimental = True
        self.stacked_intake_choice_map = {}

        # Gradient calculation constraints (match Excel defaults)
        # Note: confidence level is currently informational; the algorithm uses `gradient_head_uncertainty` directly.
        self.gradient_head_uncertainty = 0.01
        self.gradient_confidence_level = 0.66
        self.gradient_base_height_low = 0.2
        self.gradient_base_height_high = 8.0
        self.gradient_max_base_or_height = 1e9
        self.gradient_stacked_epsilon = 1e-10

        # Defaults for new datasets (may be changed by user)
        self.default_gradient_settings = {
            "gradient_head_uncertainty": self.gradient_head_uncertainty,
            "gradient_confidence_level": self.gradient_confidence_level,
            "gradient_base_height_low": self.gradient_base_height_low,
            "gradient_base_height_high": self.gradient_base_height_high,
            "gradient_max_base_or_height": self.gradient_max_base_or_height,
            "gradient_stacked_epsilon": self.gradient_stacked_epsilon,
        }

        # Triangle stats (active dataset)
        self.total_triangles = None
        self.rejected_due_to_uncertainty = None
        self.rejected_due_to_triangle_quality = None
        self.rejected_due_to_calculation_failed = None


        # Initialize handlers
        self.gradient_calculator = GradientCalculation(self)
        self.data_processor = DataProcessing(self)
        self.file_handler = FileHandler(self)
        self._gradient_executor = ThreadPoolExecutor(max_workers=1)
        self._gradient_future = None
        self._gradient_future_meta = None
        self._gradient_recompute_version = 0
        self._gradient_pending_reason = None
        self._gradient_poll_timer = QTimer(self)
        self._gradient_poll_timer.setInterval(40)
        self._gradient_poll_timer.timeout.connect(self._poll_gradient_future)
        self._perf_enabled = str(os.getenv("HEADANALYSER_PERF_LOG", "1")).strip().lower() in {"1", "true", "yes", "on"}
        # Default OFF: thread-based async compute can still starve UI due Python GIL.
        # Enable only for experimentation.
        self._async_gradient_enabled = str(os.getenv("HEADANALYSER_ENABLE_ASYNC_GRADIENT", "0")).strip().lower() in {
            "1", "true", "yes", "on"
        }
        self._sensitivity_backend_enabled = str(os.getenv("HEADANALYSER_ENABLE_SENSITIVITY_BACKEND", "1")).strip().lower() in {
            "1", "true", "yes", "on"
        }
        self._sensitivity_engine = None
        self._latest_sensitivity_analysis_result = None

        # Setup UI
        self._setup_ui()
        self._setup_statusbar()
        self._connect_signals()
        self._setup_shortcuts()
        self._sync_window_controls()
        QTimer.singleShot(0, self._apply_screen_metrics)

    def get_current_filter_values(self):
        """Get current filter slider values from the properties panel (if available)."""
        try:
            if self.properties_panel.depth_range.isEnabled():
                depth_min, depth_max = self.properties_panel.depth_range.get_values()
            else:
                depth_min, depth_max = None, None
            head_min, head_max = self.properties_panel.head_range.get_values()
            return depth_min, depth_max, head_min, head_max
        except Exception:
            return None, None, None, None

    def _perf_log(self, message: str):
        if self._perf_enabled:
            print(message, flush=True)

    def _find_dataset_id(self, dataset: Dataset):
        for did, ds in self.datasets.items():
            if ds is dataset:
                return did
        return None

    def _get_or_create_dataset_calculator(self, dataset: Dataset):
        calc_ctx = getattr(dataset, "_gradient_calc_ctx", None)
        calc = getattr(dataset, "_gradient_calculator", None)
        if calc_ctx is None or calc is None:
            calc_ctx = SimpleNamespace()
            calc = GradientCalculation(calc_ctx)
            dataset._gradient_calc_ctx = calc_ctx
            dataset._gradient_calculator = calc
        return calc_ctx, calc

    @staticmethod
    def _run_gradient_compute_job(calc, calc_ctx, data_snapshot):
        prev_disable_progress = bool(getattr(calc, "_disable_progress", False))
        prev_progress_parent = getattr(calc_ctx, "progress_parent", None)
        calc._disable_progress = True
        calc_ctx.progress_parent = None
        t0 = time.perf_counter()
        try:
            triangle_df = calc.create_gradient_dataframe(data_snapshot)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            return {
                "triangle_df": triangle_df,
                "gradient_data": getattr(calc_ctx, "gradient_data", triangle_df),
                "rejected_data": getattr(calc_ctx, "rejected_data", None),
                "total_triangles": getattr(calc_ctx, "total_triangles", None),
                "rejected_due_to_uncertainty": getattr(calc_ctx, "rejected_due_to_uncertainty", None),
                "rejected_due_to_triangle_quality": getattr(calc_ctx, "rejected_due_to_triangle_quality", None),
                "rejected_due_to_calculation_failed": getattr(calc_ctx, "rejected_due_to_calculation_failed", None),
                "elapsed_ms": elapsed_ms,
                "cache_hit": bool(getattr(calc, "_last_cache_hit", False)),
            }
        finally:
            calc._disable_progress = prev_disable_progress
            calc_ctx.progress_parent = prev_progress_parent

    def _start_gradient_job(self, dataset: Dataset, version: int, reason: str):
        data = dataset.filtered_data if dataset.filtered_data is not None else dataset.data
        if data is None:
            return

        dataset_id = self._find_dataset_id(dataset)
        if dataset_id is None:
            return

        # Selection indices are tied to a specific triangle set.
        dataset.selected_triangle_indices = set()
        dataset.selection_meta = None
        if dataset is self.get_active_dataset():
            self.clear_triangle_selection()

        calc_ctx, calc = self._get_or_create_dataset_calculator(dataset)
        calc_ctx.col_mapping = dict(dataset.col_mapping) if isinstance(dataset.col_mapping, dict) else dataset.col_mapping
        calc_ctx.gradient_head_uncertainty = float(getattr(dataset, "gradient_head_uncertainty", 0.01))
        calc_ctx.gradient_confidence_level = float(getattr(dataset, "gradient_confidence_level", 0.66))
        calc_ctx.gradient_base_height_low = float(getattr(dataset, "gradient_base_height_low", 0.2))
        calc_ctx.gradient_base_height_high = float(getattr(dataset, "gradient_base_height_high", 8.0))
        calc_ctx.gradient_max_base_or_height = float(getattr(dataset, "gradient_max_base_or_height", 1e9))
        calc_ctx.gradient_stacked_epsilon = float(getattr(dataset, "gradient_stacked_epsilon", 1e-10))
        calc_ctx.progress_parent = None
        calc_ctx.dataset_name = str(getattr(dataset, "name", dataset_id))
        calc_ctx._calc_reason = str(reason or "async")

        data_snapshot = data.copy(deep=True)
        self._gradient_future = self._gradient_executor.submit(
            MainWindow._run_gradient_compute_job, calc, calc_ctx, data_snapshot
        )
        self._gradient_future_meta = {
            "dataset_id": dataset_id,
            "dataset_name": str(getattr(dataset, "name", dataset_id)),
            "reason": str(reason or "recompute"),
            "version": int(version),
            "started": time.perf_counter(),
            "point_count": int(len(data_snapshot)),
        }
        self._gradient_poll_timer.start()
        self._perf_log(
            f"[perf] gradient job start dataset={self._gradient_future_meta['dataset_name']} "
            f"reason={self._gradient_future_meta['reason']} points={self._gradient_future_meta['point_count']} "
            f"version={version}"
        )

    def request_active_gradient_recompute_async(self, reason: str = "recompute"):
        dataset = self.get_active_dataset()
        if dataset is None:
            return

        self._gradient_recompute_version += 1
        version = self._gradient_recompute_version

        if self._gradient_future is not None and not self._gradient_future.done():
            self._gradient_pending_reason = str(reason or "recompute")
            self._perf_log(
                f"[perf] gradient job queued dataset={getattr(dataset, 'name', 'unknown')} "
                f"reason={self._gradient_pending_reason} version={version}"
            )
            return

        self._start_gradient_job(dataset, version, reason)

    def _poll_gradient_future(self):
        future = self._gradient_future
        if future is None:
            self._gradient_poll_timer.stop()
            return
        if not future.done():
            return

        meta = self._gradient_future_meta or {}
        self._gradient_future = None
        self._gradient_future_meta = None
        self._gradient_poll_timer.stop()

        try:
            result = future.result()
        except Exception as exc:
            self._perf_log(
                f"[perf] gradient job failed dataset={meta.get('dataset_name', 'unknown')} "
                f"reason={meta.get('reason', 'unknown')} error={exc}"
            )
            result = None

        is_stale = int(meta.get("version", -1)) != int(self._gradient_recompute_version)
        if (result is not None) and (not is_stale):
            dataset = self.datasets.get(meta.get("dataset_id"))
            if dataset is not None:
                dataset.triangle_data = result.get("triangle_df")
                dataset.gradient_data = result.get("gradient_data")
                dataset.rejected_data = result.get("rejected_data")
                dataset.total_triangles = result.get("total_triangles")
                dataset.rejected_due_to_uncertainty = result.get("rejected_due_to_uncertainty")
                dataset.rejected_due_to_triangle_quality = result.get("rejected_due_to_triangle_quality")
                dataset.rejected_due_to_calculation_failed = result.get("rejected_due_to_calculation_failed")

                if dataset is self.get_active_dataset():
                    self.sync_from_dataset(dataset)
                    self.update_status(
                        num_points=len(self.filtered_data) if self.filtered_data is not None else 0,
                        num_triangles=len(self.triangle_data) if self.triangle_data is not None else 0,
                    )
                    self.update_plot()
                    self._update_map_view(force=False)
                    try:
                        if hasattr(dataset, "page_stack") and dataset.page_stack.currentIndex() == 2:
                            dataset.statistics_panel.update_statistics(self)
                    except Exception:
                        pass

                try:
                    dataset.plot_page.refresh_triangle_data()
                except Exception:
                    pass

                wall_ms = (time.perf_counter() - float(meta.get("started", time.perf_counter()))) * 1000.0
                self._perf_log(
                    f"[perf] gradient job done dataset={meta.get('dataset_name', 'unknown')} "
                    f"reason={meta.get('reason', 'unknown')} points={meta.get('point_count', 0)} "
                    f"worker={float(result.get('elapsed_ms', 0.0)):.1f}ms wall={wall_ms:.1f}ms "
                    f"cache={'hit' if result.get('cache_hit') else 'miss'} "
                    f"valid={len(dataset.triangle_data) if dataset.triangle_data is not None else 0} "
                    f"total={dataset.total_triangles if dataset.total_triangles is not None else 0}"
                )
        else:
            self._perf_log(
                f"[perf] gradient job dropped dataset={meta.get('dataset_name', 'unknown')} "
                f"reason={meta.get('reason', 'unknown')} stale={is_stale}"
            )

        if self._gradient_pending_reason:
            pending_reason = self._gradient_pending_reason
            self._gradient_pending_reason = None
            dataset = self.get_active_dataset()
            if dataset is not None:
                self._start_gradient_job(dataset, self._gradient_recompute_version, pending_reason)

    def refilter_and_recalculate(self):
        """Reapply current filters/exclusions and recompute triangle gradients."""
        if self.data is None:
            return
        depth_min, depth_max, head_min, head_max = self.get_current_filter_values()
        self._run_filter_pipeline(depth_min, depth_max, head_min, head_max, reason="refilter")

    def _run_filter_pipeline(self, depth_min, depth_max, head_min, head_max, *, reason="filters"):
        """Single centralized path for applying filters/exclusions and refreshing all views."""
        if self.data is None:
            return
        self.clear_triangle_selection()
        self.file_handler.filter_data(
            depth_min,
            depth_max,
            head_min,
            head_max,
            async_gradients=self._async_gradient_enabled,
        )
        self.update_plot()
        self.update_data_views()
        self.properties_panel.refresh_excluded_list()

    def recompute_gradients_for_dataset(self, dataset: Dataset):
        """Recompute triangle gradients for a dataset using its current filtered data and settings."""
        if dataset is None or dataset.data is None:
            return

        if (dataset is self.get_active_dataset()) and (self._gradient_future is not None) and (not self._gradient_future.done()):
            # Avoid touching the same calculator/cache from two threads.
            self.request_active_gradient_recompute_async(reason="sync-recompute-queued")
            return

        data = dataset.filtered_data if dataset.filtered_data is not None else dataset.data
        if data is None or getattr(data, "empty", False):
            return

        # Invalidate selection because triangle indices refer to a specific triangle set.
        dataset.selected_triangle_indices = set()
        dataset.selection_meta = None
        if dataset is self.get_active_dataset():
            self.clear_triangle_selection()

        # Run calculation in an isolated context to avoid mutating UI state.
        # Reuse calculator per dataset so cache can persist across recalculations.
        calc_ctx, calc = self._get_or_create_dataset_calculator(dataset)
        calc_ctx.col_mapping = dict(dataset.col_mapping) if isinstance(dataset.col_mapping, dict) else dataset.col_mapping
        calc_ctx.gradient_head_uncertainty = float(getattr(dataset, "gradient_head_uncertainty", 0.01))
        calc_ctx.gradient_confidence_level = float(getattr(dataset, "gradient_confidence_level", 0.66))
        calc_ctx.gradient_base_height_low = float(getattr(dataset, "gradient_base_height_low", 0.2))
        calc_ctx.gradient_base_height_high = float(getattr(dataset, "gradient_base_height_high", 8.0))
        calc_ctx.gradient_max_base_or_height = float(getattr(dataset, "gradient_max_base_or_height", 1e9))
        calc_ctx.gradient_stacked_epsilon = float(getattr(dataset, "gradient_stacked_epsilon", 1e-10))
        calc_ctx.progress_parent = self if dataset is self.get_active_dataset() else None
        calc_ctx.dataset_name = str(getattr(dataset, "name", "dataset"))
        calc_ctx._calc_reason = "sync-recompute"

        t0 = time.perf_counter()
        triangle_df = calc.create_gradient_dataframe(data)

        dataset.triangle_data = triangle_df
        dataset.gradient_data = getattr(calc_ctx, "gradient_data", triangle_df)
        dataset.rejected_data = getattr(calc_ctx, "rejected_data", None)
        dataset.total_triangles = getattr(calc_ctx, "total_triangles", None)
        dataset.rejected_due_to_uncertainty = getattr(calc_ctx, "rejected_due_to_uncertainty", None)
        dataset.rejected_due_to_triangle_quality = getattr(calc_ctx, "rejected_due_to_triangle_quality", None)
        dataset.rejected_due_to_calculation_failed = getattr(calc_ctx, "rejected_due_to_calculation_failed", None)

        if dataset is self.get_active_dataset():
            self.sync_from_dataset(dataset)

        # Refresh triangle table in drawer
        try:
            dataset.plot_page.refresh_triangle_data()
        except Exception:
            pass

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        self._perf_log(
            f"[perf] gradient recompute sync dataset={getattr(dataset, 'name', 'unknown')} "
            f"points={len(data)} elapsed={elapsed_ms:.1f}ms "
            f"cache={'hit' if getattr(calc, '_last_cache_hit', False) else 'miss'}"
        )

    def apply_calculation_settings(self, settings: dict, apply_globally: bool = False):
        """Apply triangle constraint settings to current dataset (or all datasets) and recompute."""
        keys = [
            "gradient_head_uncertainty",
            "gradient_confidence_level",
            "gradient_base_height_low",
            "gradient_base_height_high",
            "gradient_max_base_or_height",
            "gradient_stacked_epsilon",
        ]
        normalized = {}
        for k in keys:
            if k in settings:
                try:
                    normalized[k] = float(settings[k])
                except Exception:
                    pass

        if not normalized:
            return

        def _is_changed(current_value, new_value):
            try:
                return not np.isclose(float(current_value), float(new_value), rtol=0.0, atol=1e-12)
            except Exception:
                return True

        if apply_globally:
            self.default_gradient_settings.update(normalized)
            for ds in self.datasets.values():
                changed = False
                for k, v in normalized.items():
                    if _is_changed(getattr(ds, k, None), v):
                        changed = True
                    setattr(ds, k, v)
                if ds.has_data() and changed:
                    self.recompute_gradients_for_dataset(ds)
            active = self.get_active_dataset()
            if active is not None:
                self.sync_from_dataset(active)
            self.update_all_views()
        else:
            ds = self.get_active_dataset()
            if ds is None:
                return
            changed = False
            for k, v in normalized.items():
                if _is_changed(getattr(ds, k, None), v):
                    changed = True
                setattr(ds, k, v)
            if ds.has_data() and changed:
                self.recompute_gradients_for_dataset(ds)
            self.sync_from_dataset(ds)
            self.update_all_views()

    def run_sensitivity_analysis(
        self,
        config: dict,
        *,
        dataset: Dataset = None,
        selected_point_ids: set = None,
        progress_callback=None,
        cancel_check=None,
    ):
        """Run isolated sensitivity backend and store result on dataset.

        This method is intentionally thin so UI code can plug/unplug the feature
        by calling one function and consuming one result object.
        """
        if not self._sensitivity_backend_enabled:
            raise RuntimeError("Sensitivity backend is disabled (HEADANALYSER_ENABLE_SENSITIVITY_BACKEND=0).")

        ds = dataset or self.get_active_dataset()
        if ds is None:
            raise ValueError("No active dataset available for sensitivity analysis.")

        data = ds.filtered_data if ds.filtered_data is not None else ds.data
        if data is None or getattr(data, "empty", False):
            raise ValueError("Dataset has no data to analyze.")

        col_mapping = dict(ds.col_mapping) if isinstance(ds.col_mapping, dict) else {}
        required = ("ID", "x", "y", "hydraulic head")
        for key in required:
            if not col_mapping.get(key):
                raise ValueError(f"Missing column mapping for '{key}'.")

        base_settings = {
            "gradient_head_uncertainty": float(getattr(ds, "gradient_head_uncertainty", 0.01)),
            "gradient_confidence_level": float(getattr(ds, "gradient_confidence_level", 0.66)),
            "gradient_base_height_low": float(getattr(ds, "gradient_base_height_low", 0.2)),
            "gradient_base_height_high": float(getattr(ds, "gradient_base_height_high", 8.0)),
            "gradient_max_base_or_height": float(getattr(ds, "gradient_max_base_or_height", 1e9)),
            "gradient_stacked_epsilon": float(getattr(ds, "gradient_stacked_epsilon", 1e-10)),
        }

        if self._sensitivity_engine is None:
            self._sensitivity_engine = SensitivityAnalysisEngine()

        result = self._sensitivity_engine.run(
            filtered_data=data,
            col_mapping=col_mapping,
            base_settings=base_settings,
            config=config or {},
            selected_point_ids=set(selected_point_ids or []),
            progress_callback=progress_callback,
            cancel_check=cancel_check,
        )

        ds.sensitivity_analysis_result = result
        if ds is self.get_active_dataset():
            self._latest_sensitivity_analysis_result = result
        return result

    def set_triangle_selection(self, triangle_indices, meta=None):
        """Set selected triangles (by triangle_data index)."""
        try:
            self.selected_triangle_indices = set(int(v) for v in triangle_indices)
        except Exception:
            self.selected_triangle_indices = set()
        self.selection_meta = dict(meta) if isinstance(meta, dict) else None
        ds = self.get_active_dataset()
        if ds is not None:
            ds.selected_triangle_indices = set(self.selected_triangle_indices)
            ds.selection_meta = self.selection_meta
        try:
            self._update_selection_inspector()
        except Exception:
            pass
        try:
            dataset = self.get_active_dataset()
            if dataset is not None and hasattr(dataset, "map_widget") and self._is_map_sync_enabled(dataset):
                dataset.map_widget.apply_triangle_selection_overlay(list(self.selected_triangle_indices))
                point_ids = sorted(str(v) for v in self._get_selected_point_ids())
                if point_ids:
                    dataset.map_widget.set_selected_point(point_ids[0])
        except Exception:
            pass

    def clear_triangle_selection(self):
        """Clear any global triangle selection."""
        self.selected_triangle_indices = set()
        self.selection_meta = None
        ds = self.get_active_dataset()
        if ds is not None:
            ds.selected_triangle_indices = set()
            ds.selection_meta = None
        try:
            self._update_selection_inspector()
        except Exception:
            pass
        try:
            if ds is not None and hasattr(ds, "map_widget") and self._is_map_sync_enabled(ds):
                ds.map_widget.apply_triangle_selection_overlay([])
                ds.map_widget.clear_selected_point()
        except Exception:
            pass

    def show_selection_inspector(self):
        """Open (or focus) the selection inspector dialog for the active dataset."""
        ds = self.get_active_dataset()
        if ds is None:
            return
        dlg = getattr(ds, "_selection_inspector_dialog", None)
        if dlg is None:
            dlg = SelectionInspectorDialog(self, parent=self)
            ds._selection_inspector_dialog = dlg
        self._update_selection_inspector()
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

    def _update_selection_inspector(self):
        ds = self.get_active_dataset()
        if ds is None:
            return
        dlg = getattr(ds, "_selection_inspector_dialog", None)
        if dlg is None:
            return
        dlg.update_selection(self.selected_triangle_indices, meta=self.selection_meta)

    def show_triangle_inspector(self, selected_point_ids=None):
        """Open the Triangle Inspector dialog filtered to selected points."""
        ds = self.get_active_dataset()
        if ds is None:
            return

        # Collect selected point IDs from current triangle selection if not provided
        if selected_point_ids is None:
            selected_point_ids = self._get_selected_point_ids()

        dlg = getattr(ds, "_triangle_inspector_dialog", None)
        if dlg is None:
            dlg = TriangleInspectorDialog(self, parent=self)
            ds._triangle_inspector_dialog = dlg

        dlg.update_for_selection(
            selected_point_ids=selected_point_ids,
            triangle_data=self.triangle_data,
            rejected_data=self.rejected_data,
            gradient_data=self.gradient_data,
            filtered_data=self.filtered_data,
            col_mapping=self.col_mapping,
            total_triangles=getattr(self, "total_triangles", None),
        )
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

    def _get_selected_point_ids(self):
        """Extract point IDs from the current triangle selection."""
        if not self.selected_triangle_indices or self.triangle_data is None:
            return set()
        try:
            point_ids = set()
            for idx in self.selected_triangle_indices:
                if idx in self.triangle_data.index:
                    ids = self.triangle_data.loc[idx, "point_ids"]
                    if isinstance(ids, (list, tuple)):
                        point_ids.update(str(v) for v in ids)
                    else:
                        point_ids.add(str(ids))
            return point_ids
        except Exception:
            return set()

    def _on_stats_inspect_clicked(self, statistics_panel):
        """Open triangle inspector using frequency bar selection if available."""
        ids = statistics_panel.get_selected_point_ids()
        self.show_triangle_inspector(selected_point_ids=ids or None)

    def _on_stats_export_clicked(self, statistics_panel):
        """Export currently rejected triangle rows from the active dataset."""
        _ = statistics_panel  # UI sender context (currently unused).
        if self.rejected_data is None or getattr(self.rejected_data, "empty", True):
            QMessageBox.information(self, "No Rejected Triangles", "There is no rejected triangle data to export.")
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Export Rejected Triangles", "rejected_triangles.csv", "CSV Files (*.csv)"
        )
        if not path:
            return

        try:
            export_df = self.rejected_data.copy()
            for col in export_df.columns:
                export_df[col] = export_df[col].apply(
                    lambda v: ", ".join(str(x) for x in v)
                    if isinstance(v, (list, tuple, np.ndarray))
                    else (str(v) if isinstance(v, dict) else v)
                )
            export_df.to_csv(path, index=False)
            QMessageBox.information(self, "Export Complete", f"Rejected triangle data exported to:\n{path}")
        except Exception as exc:
            QMessageBox.critical(self, "Export Failed", f"Could not export rejected triangles.\n\n{exc}")

    def _update_triangle_inspector(self):
        """Refresh the triangle inspector if visible."""
        ds = self.get_active_dataset()
        if ds is None:
            return
        dlg = getattr(ds, "_triangle_inspector_dialog", None)
        if dlg is None or not dlg.isVisible():
            return
        selected_point_ids = self._get_selected_point_ids()
        dlg.update_for_selection(
            selected_point_ids=selected_point_ids,
            triangle_data=self.triangle_data,
            rejected_data=self.rejected_data,
            gradient_data=self.gradient_data,
            filtered_data=self.filtered_data,
            col_mapping=self.col_mapping,
            total_triangles=getattr(self, "total_triangles", None),
        )

    def _setup_ui(self):
        """Setup the main UI layout."""
        metrics = self._screen_metrics
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main vertical layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Header bar
        self.header_bar = HeaderBar(self)
        main_layout.addWidget(self.header_bar)

        # Content area
        content_widget = QWidget()
        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # Navigation sidebar
        self.nav_sidebar = NavigationSidebar(self)
        content_layout.addWidget(self.nav_sidebar)

        # Splitter for center content + properties
        self.splitter = QSplitter(Qt.Horizontal)

        # Stack for welcome screen vs dataset tabs
        self.content_stack = QStackedWidget()
        self.welcome_widget = None
        self._create_welcome_widget()

        # Tab widget for datasets (index 1)
        self.dataset_tabs = QTabWidget()
        self.dataset_tabs.setTabsClosable(True)
        self.dataset_tabs.setMovable(True)
        self.dataset_tabs.setDocumentMode(True)
        self.dataset_tabs.setElideMode(Qt.ElideRight)
        self.dataset_tabs.setUsesScrollButtons(True)
        self.dataset_tabs.tabBar().setDrawBase(False)
        self.dataset_tabs.tabCloseRequested.connect(self.close_dataset_tab)
        self.dataset_tabs.currentChanged.connect(self.on_tab_changed)

        self.content_stack.addWidget(self.dataset_tabs)

        # Start with welcome screen
        if self.welcome_widget is not None:
            self.content_stack.setCurrentWidget(self.welcome_widget)
        else:
            self.content_stack.setCurrentWidget(self.dataset_tabs)

        self.splitter.addWidget(self.content_stack)

        # Properties panel
        self.properties_panel = PropertiesPanel(self)
        self.splitter.addWidget(self.properties_panel)

        self.splitter.setSizes([
            max(640, metrics.initial_window_size.width() - metrics.properties_width),
            metrics.properties_width,
        ])
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)

        content_layout.addWidget(self.splitter)
        main_layout.addWidget(content_widget)

        # Initial state
        self._set_welcome_mode(True)

    def _connect_welcome_widget_signals(self, widget: WelcomeWidget):
        """Connect welcome widget bridge signals to main-window handlers."""
        if widget is None:
            return
        widget.open_file_requested.connect(self.on_open_file)
        widget.load_recent_requested.connect(self.on_open_recent)
        widget.open_recent_file_requested.connect(self.open_recent_file)
        widget.help_requested.connect(self.on_help)
        widget.contact_requested.connect(self.on_contact)

    def _create_welcome_widget(self):
        """Create and insert the welcome widget if it does not exist."""
        if self.welcome_widget is not None:
            return
        widget = WelcomeWidget(self)
        widget.update_recent_sessions(self.get_recent_sessions(limit=6))
        self.welcome_widget = widget
        self._connect_welcome_widget_signals(widget)
        self.content_stack.insertWidget(0, widget)

    def _recent_settings(self) -> QSettings:
        """Persistent settings store for lightweight app UI state."""
        return QSettings("DTU", "HeadAnalyser")

    def toggle_ui_theme(self):
        if Colors.is_dark():
            next_theme = self._recent_settings().value("last_non_dark_ui_theme", "porcelain_lab", type=str)
            next_theme = Colors.normalize_theme(next_theme)
            if Colors.theme_scheme(next_theme) == "dark":
                next_theme = "porcelain_lab"
        else:
            next_theme = "dark"
        self.apply_ui_theme(next_theme)

    def apply_ui_theme(self, theme_name: str, persist: bool = True):
        theme = Colors.apply_theme(theme_name)
        self._ui_theme = theme

        app = QApplication.instance()
        if app is not None:
            app.setPalette(build_qpalette())
            app.setStyleSheet(StyleSheet.get_main_stylesheet())

        if hasattr(self, "header_bar") and self.header_bar is not None:
            self.header_bar.apply_theme()
        if hasattr(self, "nav_sidebar") and self.nav_sidebar is not None:
            self.nav_sidebar.apply_theme()
        if hasattr(self, "properties_panel") and self.properties_panel is not None:
            self.properties_panel.apply_theme()
        if self.welcome_widget is not None:
            self.welcome_widget.apply_theme()

        self._apply_statusbar_theme()

        for dataset in self.datasets.values():
            page_stack = getattr(dataset, "page_stack", None)
            if page_stack is not None:
                page_stack.setStyleSheet(f"background-color: {Colors.BG_PANEL};")
            if hasattr(dataset, "plot_page"):
                dataset.plot_page.apply_theme()
            if hasattr(dataset, "map_widget"):
                dataset.map_widget.apply_theme()
            if hasattr(dataset, "statistics_panel"):
                dataset.statistics_panel.apply_theme()

        if persist:
            settings = self._recent_settings()
            settings.setValue("ui_theme", theme)
            if Colors.theme_scheme(theme) != "dark":
                settings.setValue("last_non_dark_ui_theme", theme)

        active_dataset = self.get_active_dataset()
        if active_dataset is not None:
            self._sync_active_sidebar_from_state()
            self.update_plot()
            self._update_map_view(force=True)
            try:
                current_page = int(active_dataset.page_stack.currentIndex())
            except Exception:
                current_page = 0
            if current_page == 2 and hasattr(active_dataset, "statistics_panel"):
                active_dataset.statistics_panel.update_statistics(self)

    @staticmethod
    def _normalize_recent_path(path: str) -> str:
        return os.path.normcase(os.path.normpath(str(path or "").strip()))

    def _load_recent_entries(self) -> list:
        try:
            entries = self._recent_settings().value("recent_sessions", [], type=list) or []
        except Exception:
            entries = []
        return entries if isinstance(entries, list) else []

    def get_recent_sessions(self, limit: int = 6) -> list:
        """Return normalized recent file sessions from settings."""
        sessions = self._load_recent_entries()
        normalized = []
        for item in sessions:
            if not isinstance(item, dict):
                continue
            files = item.get("files") if isinstance(item.get("files"), list) else []
            files = [str(p) for p in files if p]
            if not files:
                continue
            normalized.append(
                {
                    "name": str(item.get("name") or os.path.basename(files[0]) or "Session"),
                    "files": files,
                    "opened_at": str(item.get("opened_at") or ""),
                }
            )
        return normalized[: max(1, int(limit))]

    def add_recent_session(self, file_path: str, dataset_name: str = "", mapping: dict = None) -> None:
        """Persist one-file session for Welcome recent list."""
        path = str(file_path or "").strip()
        if not path:
            return
        try:
            from datetime import datetime

            now_iso = datetime.now().strftime("%Y-%m-%d %H:%M")
        except Exception:
            now_iso = ""

        cleaned_mapping = {}
        mapping_input = mapping if isinstance(mapping, dict) else {}
        for key in ("ID", "x", "y", "hydraulic head", "top", "bottom", "depth"):
            value = mapping_input.get(key)
            if value:
                cleaned_mapping[key] = str(value)

        new_entry = {
            "name": str(dataset_name or os.path.basename(path) or "Session"),
            "files": [path],
            "opened_at": now_iso,
            "mapping": cleaned_mapping,
        }

        sessions = self._load_recent_entries()
        normalized_new = self._normalize_recent_path(path)
        deduped = []
        for item in sessions:
            files = item.get("files") if isinstance(item.get("files"), list) else []
            first = str(files[0]) if files else ""
            if first and self._normalize_recent_path(first) == normalized_new:
                continue
            deduped.append(item)
        updated = [new_entry] + deduped[:15]
        try:
            self._recent_settings().setValue("recent_sessions", updated)
        except Exception:
            pass

    def get_recent_mapping_for_file(self, file_path: str, columns: list = None) -> dict:
        """Return saved mapping for a specific file path if still compatible."""
        normalized_path = self._normalize_recent_path(file_path)
        if not normalized_path:
            return {}
        available = {str(c) for c in (columns or [])}
        for item in self._load_recent_entries():
            if not isinstance(item, dict):
                continue
            files = item.get("files") if isinstance(item.get("files"), list) else []
            first = str(files[0]) if files else ""
            if not first or self._normalize_recent_path(first) != normalized_path:
                continue
            mapping = item.get("mapping")
            if not isinstance(mapping, dict):
                return {}
            required = ("ID", "x", "y", "hydraulic head")
            if not all(mapping.get(k) for k in required):
                return {}
            if available and not all(str(mapping.get(k)) in available for k in required):
                return {}
            for opt in ("top", "bottom", "depth"):
                value = mapping.get(opt)
                if value and available and str(value) not in available:
                    mapping = dict(mapping)
                    mapping.pop(opt, None)
            return {k: str(v) for k, v in mapping.items() if v}
        return {}

    def open_recent_file(self, file_path: str) -> None:
        """Open one recent file directly from welcome list."""
        path = str(file_path or "").strip()
        if not path:
            self.on_open_file()
            return
        if not os.path.exists(path):
            QMessageBox.warning(self, "Recent File Missing", f"File not found:\n{path}")
            return
        self.file_handler.load_file(path, use_recent_mapping=True)

    def on_open_recent(self) -> None:
        """Open newest recent file; fallback to open-file dialog."""
        sessions = self.get_recent_sessions(limit=1)
        if not sessions:
            self.on_open_file()
            return
        files = sessions[0].get("files") if isinstance(sessions[0], dict) else []
        first_path = str(files[0]) if files else ""
        if not first_path:
            self.on_open_file()
            return
        self.open_recent_file(first_path)

    def _destroy_welcome_widget(self):
        """Destroy the welcome widget to fully stop WebEngine animation/rendering."""
        widget = self.welcome_widget
        if widget is None:
            return
        try:
            if hasattr(widget, "shutdown"):
                widget.shutdown()
        except Exception:
            pass
        try:
            self.content_stack.removeWidget(widget)
        except Exception:
            pass
        widget.deleteLater()
        self.welcome_widget = None

    def _setup_statusbar(self):
        """Setup the status bar."""
        metrics = build_screen_metrics(self)
        self.statusbar = QStatusBar()
        self.statusbar.setFixedHeight(metrics.statusbar_height)
        self.setStatusBar(self.statusbar)
        self.statusbar.setStyleSheet(
            f"""
            QStatusBar {{
                background-color: {Colors.BG_PANEL};
                border-top: 1px solid {Colors.BORDER_DEFAULT};
            }}
            QStatusBar QLabel {{
                color: {Colors.TEXT_TERTIARY};
                font-size: 10px;
                padding: 0px 6px;
            }}
            """
        )

        # Ready indicator
        self.status_indicator = QLabel("\u25CF")
        self.status_indicator.setStyleSheet(f"color: {Colors.SUCCESS}; font-size: 10px;")
        self.statusbar.addWidget(self.status_indicator)

        self.status_file_label = QLabel("Ready")
        self.status_file_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 10px;")
        self.statusbar.addWidget(self.status_file_label)

        # Permanent widgets on right
        self.status_coords_label = QLabel("")
        # Keep fixed width so rapid coord updates don't trigger layout thrash.
        self.status_coords_label.setFixedWidth(metrics.status_coords_width)
        self.status_coords_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.statusbar.addPermanentWidget(self.status_coords_label)

        # Separator (plain styled frame — no VLine to avoid Qt border artifact)
        sep1 = QFrame()
        sep1.setFixedWidth(1)
        sep1.setFixedHeight(metrics.status_separator_height)
        sep1.setStyleSheet(f"background-color: {Colors.BORDER_MEDIUM}; border: none;")
        self.status_sep1 = sep1
        self.statusbar.addPermanentWidget(sep1)

        self.status_gradient_label = QLabel("")
        self.statusbar.addPermanentWidget(self.status_gradient_label)

        # Separator
        sep2 = QFrame()
        sep2.setFixedWidth(1)
        sep2.setFixedHeight(metrics.status_separator_height)
        sep2.setStyleSheet(f"background-color: {Colors.BORDER_MEDIUM}; border: none;")
        self.status_sep2 = sep2
        self.statusbar.addPermanentWidget(sep2)

        self.status_points_label = QLabel("")
        self.statusbar.addPermanentWidget(self.status_points_label)

        # Triangle counts (warm chips)
        self.status_triangles_widget = QWidget()
        tri_layout = QHBoxLayout(self.status_triangles_widget)
        tri_layout.setContentsMargins(0, 0, 0, 0)
        tri_layout.setSpacing(6)

        tri_prefix = QLabel("Triangles:")
        tri_prefix.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: 10px;")
        self.status_triangles_prefix = tri_prefix
        tri_layout.addWidget(tri_prefix)

        def _chip_style(text_color: str) -> str:
            return f"""
                QLabel {{
                    background-color: {Colors.BG_SURFACE};
                    border: 1px solid {Colors.BORDER_DEFAULT};
                    border-radius: {Colors.RADIUS_SM};
                    padding: 2px 10px;
                    color: {text_color};
                    font-size: 10px;
                    font-weight: 600;
                }}
            """

        self.status_triangles_total_chip = QLabel("Total: -")
        self.status_triangles_total_chip.setStyleSheet(_chip_style(Colors.TEXT_SECONDARY))
        tri_layout.addWidget(self.status_triangles_total_chip)

        self.status_triangles_valid_chip = QLabel("Valid: -")
        self.status_triangles_valid_chip.setStyleSheet(_chip_style(Colors.SUCCESS))
        tri_layout.addWidget(self.status_triangles_valid_chip)

        self.status_triangles_rejected_chip = QLabel("Rejected: -")
        self.status_triangles_rejected_chip.setStyleSheet(_chip_style(Colors.ERROR))
        tri_layout.addWidget(self.status_triangles_rejected_chip)

        self.statusbar.addPermanentWidget(self.status_triangles_widget)

    def _apply_statusbar_theme(self):
        if not hasattr(self, "statusbar") or self.statusbar is None:
            return
        metrics = build_screen_metrics(self)
        self.statusbar.setFixedHeight(metrics.statusbar_height)
        self.status_coords_label.setFixedWidth(metrics.status_coords_width)
        self.status_sep1.setFixedHeight(metrics.status_separator_height)
        self.status_sep2.setFixedHeight(metrics.status_separator_height)

        self.statusbar.setStyleSheet(
            f"""
            QStatusBar {{
                background-color: {Colors.BG_PANEL};
                border-top: 1px solid {Colors.BORDER_DEFAULT};
            }}
            QStatusBar QLabel {{
                color: {Colors.TEXT_TERTIARY};
                font-size: 10px;
                padding: 0px 6px;
            }}
            """
        )
        self.status_indicator.setStyleSheet(f"color: {Colors.SUCCESS}; font-size: 10px;")
        self.status_file_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 10px;")
        self.status_sep1.setStyleSheet(f"background-color: {Colors.BORDER_MEDIUM}; border: none;")
        self.status_sep2.setStyleSheet(f"background-color: {Colors.BORDER_MEDIUM}; border: none;")
        self.status_triangles_prefix.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: 10px;")

        def _chip_style(text_color: str) -> str:
            return f"""
                QLabel {{
                    background-color: {Colors.BG_SURFACE};
                    border: 1px solid {Colors.BORDER_DEFAULT};
                    border-radius: {Colors.RADIUS_SM};
                    padding: 2px 10px;
                    color: {text_color};
                    font-size: 10px;
                    font-weight: 600;
                }}
            """

        self.status_triangles_total_chip.setStyleSheet(_chip_style(Colors.TEXT_SECONDARY))
        self.status_triangles_valid_chip.setStyleSheet(_chip_style(Colors.SUCCESS))
        self.status_triangles_rejected_chip.setStyleSheet(_chip_style(Colors.ERROR))

    def _ensure_screen_metrics_tracking(self):
        handle = self.windowHandle()
        if handle is None or handle is self._tracked_window_handle:
            return
        if self._tracked_window_handle is not None:
            try:
                self._tracked_window_handle.screenChanged.disconnect(self._on_screen_changed)
            except Exception:
                pass
        self._tracked_window_handle = handle
        try:
            handle.screenChanged.connect(self._on_screen_changed)
        except Exception:
            pass

    def _on_screen_changed(self, _screen=None):
        QTimer.singleShot(0, self._apply_screen_metrics)

    def _apply_screen_metrics(self):
        metrics = build_screen_metrics(self)
        signature = (
            metrics.available_width,
            metrics.available_height,
            metrics.compact,
            metrics.scale,
        )
        if signature == self._screen_metrics_signature:
            return

        self._screen_metrics = metrics
        self._screen_metrics_signature = signature
        self.setMinimumSize(metrics.min_window_size)

        is_effectively_maximized = bool(
            self.is_window_effectively_maximized()
            if hasattr(self, "is_window_effectively_maximized")
            else self.isMaximized()
        )
        if not is_effectively_maximized:
            target_size = self.size().boundedTo(metrics.initial_window_size).expandedTo(metrics.min_window_size)
            self.resize(target_size)

        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(StyleSheet.get_main_stylesheet())

        if hasattr(self, "header_bar") and self.header_bar is not None:
            self.header_bar.apply_theme()
        if hasattr(self, "nav_sidebar") and self.nav_sidebar is not None:
            self.nav_sidebar.apply_theme()
        if hasattr(self, "properties_panel") and self.properties_panel is not None:
            self.properties_panel.apply_theme()
        if hasattr(self, "splitter") and self.splitter is not None:
            total_width = self.splitter.width() or max(960, metrics.initial_window_size.width() - metrics.nav_width)
            self.splitter.setSizes([max(640, total_width - metrics.properties_width), metrics.properties_width])

        self._apply_statusbar_theme()

        for dataset in self.datasets.values():
            if hasattr(dataset, "plot_page"):
                dataset.plot_page.apply_theme()

    def showEvent(self, event):
        super().showEvent(event)
        self._ensure_screen_metrics_tracking()
        QTimer.singleShot(0, self._apply_screen_metrics)

    def _connect_signals(self):
        """Connect signals between components."""
        # Header bar
        self.header_bar.open_clicked.connect(self.on_open_file)
        self.header_bar.save_clicked.connect(self.on_save)
        self.header_bar.export_clicked.connect(self.on_export)
        self.header_bar.report_clicked.connect(self.on_export_report)
        self.header_bar.calc_clicked.connect(self.on_calculation_settings)
        self.header_bar.table_clicked.connect(self.on_open_attribute_table)
        self.header_bar.sensitivity_clicked.connect(self._open_sensitivity_dialog)
        self.header_bar.reset_clicked.connect(self.on_reset)
        self.header_bar.help_clicked.connect(self.on_help)
        self.header_bar.theme_selected.connect(self.apply_ui_theme)
        self.header_bar.window_minimize_clicked.connect(self.showMinimized)
        self.header_bar.window_maximize_clicked.connect(self.toggle_window_maximize)
        self.header_bar.window_close_clicked.connect(self.close)

        # Navigation
        self.nav_sidebar.page_changed.connect(self.on_page_changed)

        # Properties (data filters only now)
        self.properties_panel.filters_changed.connect(self.on_filters_changed)

    def on_window_chrome_state_changed(self, is_frameless: bool, is_maximized: bool):
        if hasattr(self, "header_bar") and self.header_bar is not None:
            self.header_bar.set_frameless_mode(is_frameless)
            self.header_bar.set_maximized_state(is_maximized)

    def _setup_shortcuts(self):
        """Setup keyboard shortcuts."""
        QShortcut(QKeySequence("Ctrl+O"), self).activated.connect(self.on_open_file)
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self.on_save)
        QShortcut(QKeySequence("Ctrl+E"), self).activated.connect(self.on_export)
        QShortcut(QKeySequence("Ctrl+R"), self).activated.connect(self.on_export_report)
        QShortcut(QKeySequence("Ctrl+T"), self).activated.connect(self.on_open_attribute_table)
        # Experimental: isolated Geo.dk fence view (does not affect normal workflows).
        QShortcut(QKeySequence("Ctrl+Shift+F"), self).activated.connect(self._open_geodk_fence_dialog)

    def _update_map_view(self, force: bool = False):
        """
        Helper: Refresh the map widget with the current dataset state.
        Constructs the full MapPayload using the Phase 0 contract.
        Guarded against missing map_widget for safety.
        """
        # Guard: Check if map exists on dataset (Phase 0 constraint)
        dataset = self.get_active_dataset()
        if dataset is None or not hasattr(dataset, 'map_widget'):
            return

        # Avoid unnecessary full map rebuilds when map page is not visible.
        try:
            current_page = int(dataset.page_stack.currentIndex())
        except Exception:
            current_page = 0
        if (not force) and current_page != 1:
            setattr(dataset, "_map_dirty", True)
            return

        # Phase 0 Contract: Assemble MapPayload
        # Use filtered_plot_data if available (includes excluded points visually marked),
        # fallback to raw data if filtering hasn't run yet.
        data_source = dataset.filtered_plot_data if dataset.filtered_plot_data is not None else dataset.data

        payload = {
            'data': data_source,
            'col_mapping': dataset.col_mapping,
            'excluded_ids': dataset.excluded_ids,
            'triangle_data': dataset.triangle_data,
            'gradient_data': dataset.gradient_data,
            'rejected_data': dataset.rejected_data,
        }

        # Dispatch to map widget
        dataset.map_widget.update_map(**payload)
        setattr(dataset, "_map_dirty", False)

    def _on_map_point_selected(self, point_id: str):
        """Handle point selection emitted from map widget."""
        dataset = self.get_active_dataset()
        if dataset is None:
            return
        if self.is_point_creation_mode():
            xy = self._resolve_point_xy_by_id(dataset, str(point_id))
            if xy is not None:
                self._set_active_target_location(xy[0], xy[1], source="map-point-click")
                self._add_point_at_xy(xy)
                return
        self._on_plot_point_selected(str(point_id))
        try:
            dataset.plot_page.plot_widget.highlight_point_by_id(str(point_id))
        except Exception:
            pass
        try:
            dataset.plot_page.data_table.highlight_rows_by_ids([str(point_id)])
        except Exception:
            pass

    def _on_map_point_deselected(self):
        """Clear point highlights in plot and table when map selection is cleared."""
        dataset = self.get_active_dataset()
        if dataset is None:
            return
        try:
            dataset.plot_page.plot_widget.clear_point_highlight()
        except Exception:
            pass
        try:
            dataset.plot_page.data_table.clear_highlight()
        except Exception:
            pass

    def _on_map_exclude_requested(self, point_id: str):
        """Exclude the selected map point and refresh filters/gradients."""
        payload = str(point_id).strip()
        if not payload:
            return
        pid = payload
        member_key = ""
        try:
            if payload.startswith("{"):
                import json
                parsed = json.loads(payload)
                if isinstance(parsed, dict):
                    pid = str(parsed.get("id", "")).strip()
                    member_key = str(parsed.get("member_key", "")).strip()
        except Exception:
            pid = payload

        changed = self.apply_point_exclusion(pid, member_key=member_key, exclude=True)
        if changed:
            self.refilter_and_recalculate()

    def apply_point_exclusion(self, point_id: str, *, member_key: str = "", exclude: bool = True) -> bool:
        """
        Canonical exclusion mutator.

        Rules:
        - If member_key is provided: apply exclusion at member-level.
        - If member_key is missing: apply exclusion at ID-level (legacy fallback).
        - Member-level include also clears ID-level exclusion for that ID so selected row/member can be restored.
        """
        if not isinstance(getattr(self, "excluded_ids", None), set):
            self.excluded_ids = set()
        if not isinstance(getattr(self, "excluded_member_keys", None), set):
            self.excluded_member_keys = set()

        return bool(
            apply_point_exclusion_state(
                self.excluded_ids,
                self.excluded_member_keys,
                point_id=str(point_id or ""),
                member_key=str(member_key or ""),
                exclude=bool(exclude),
            )
        )

    def _on_map_show_in_plot_requested(self, point_id: str):
        """Navigate to plot page and highlight a selected map point."""
        pid = str(point_id).strip()
        if not pid:
            return
        try:
            self.nav_sidebar.set_active_page("plot")
        except Exception:
            pass
        dataset = self.get_active_dataset()
        if dataset is None:
            return
        try:
            dataset.plot_page.plot_widget.highlight_point_by_id(pid)
        except Exception:
            pass
        try:
            dataset.plot_page.data_table.highlight_rows_by_ids([pid])
        except Exception:
            pass

    def _on_map_contour_settings_requested(self):
        """Open advanced map contour settings dialog."""
        dataset = self.get_active_dataset()
        if dataset is None or not hasattr(dataset, "map_widget"):
            return
        from .dialogs.map_contour_settings import MapContourSettingsDialog
        dialog = MapContourSettingsDialog(self, dataset.map_widget, parent=self)
        try:
            dialog.exec_()
        finally:
            dialog.deleteLater()

    def _set_active_target_location(self, x: float, y: float, source: str):
        """Store active target location in dataset CRS (UTM32)."""
        ds_id = self.active_dataset_id
        if not ds_id:
            return
        self._target_locations_by_dataset[ds_id] = {
            "xy": (float(x), float(y)),
            "source": str(source),
        }

    def _get_active_target_location(self):
        """Return active target XY tuple in dataset CRS, or None."""
        ds_id = self.active_dataset_id
        if not ds_id:
            return None
        entry = self._target_locations_by_dataset.get(ds_id)
        if not isinstance(entry, dict):
            return None
        xy = entry.get("xy")
        if not isinstance(xy, (tuple, list)) or len(xy) != 2:
            return None
        try:
            return float(xy[0]), float(xy[1])
        except Exception:
            return None

    def is_point_creation_mode(self) -> bool:
        """Return whether point creation mode is enabled for the active dataset."""
        ds_id = self.active_dataset_id
        if not ds_id:
            return False
        return bool(self._point_creation_mode_by_dataset.get(ds_id, False))

    def set_point_creation_mode(self, enabled: bool):
        """Enable/disable point creation mode for active dataset and sync UI toggles."""
        ds_id = self.active_dataset_id
        if not ds_id:
            return
        self._point_creation_mode_by_dataset[ds_id] = bool(enabled)
        self._sync_point_creation_mode_ui()

    def _sync_point_creation_mode_ui(self):
        """Sync plot/map toggle buttons to active mode without recursive signals."""
        dataset = self.get_active_dataset()
        if dataset is None:
            return
        enabled = bool(self.is_point_creation_mode())
        try:
            btn = getattr(dataset.plot_page, "add_point_btn", None)
            if btn is not None and bool(btn.isChecked()) != enabled:
                btn.blockSignals(True)
                btn.setChecked(enabled)
                btn.blockSignals(False)
        except Exception:
            pass
        try:
            map_btn = getattr(dataset.map_widget.toolbar, "add_point_btn", None)
            if map_btn is not None and bool(map_btn.isChecked()) != enabled:
                map_btn.blockSignals(True)
                map_btn.setChecked(enabled)
                map_btn.blockSignals(False)
        except Exception:
            pass

    def _resolve_point_xy_by_id(self, dataset, point_id: str):
        """Resolve point XY from current dataset for a given point ID."""
        if dataset is None:
            return None
        data = dataset.filtered_plot_data if dataset.filtered_plot_data is not None else dataset.data
        if data is None or getattr(data, "empty", False):
            return None
        mapping = dataset.col_mapping if isinstance(dataset.col_mapping, dict) else {}
        id_col = mapping.get("ID")
        x_col = mapping.get("x")
        y_col = mapping.get("y")
        if not id_col or not x_col or not y_col:
            return None
        if id_col not in data.columns or x_col not in data.columns or y_col not in data.columns:
            return None
        pid = str(point_id).strip()
        if not pid:
            return None
        try:
            mask = data[id_col].astype(str) == pid
            if not bool(mask.any()):
                return None
            row = data.loc[mask].iloc[0]
            return float(row[x_col]), float(row[y_col])
        except Exception:
            return None

    def _on_plot_point_selected(self, point_id: str):
        """Update target location when a point is selected in plot/table/map sync."""
        dataset = self.get_active_dataset()
        xy = self._resolve_point_xy_by_id(dataset, point_id)
        if xy is None:
            return
        self._set_active_target_location(xy[0], xy[1], source="point-selection")

    def _on_plot_coordinate_clicked(self, x: float, y: float):
        """Handle direct click on plot canvas in dataset CRS."""
        self._set_active_target_location(x, y, source="plot-click")
        if not self.is_point_creation_mode():
            return
        self._add_point_at_xy((x, y))

    def _is_map_sync_enabled(self, dataset) -> bool:
        """Return whether map selection sync is enabled for this dataset."""
        try:
            return bool(getattr(dataset.map_widget, "_sync_selection", True))
        except Exception:
            return True

    def _on_table_row_selected(self, point_id: str):
        """Sync table single-row selection to map selection."""
        dataset = self.get_active_dataset()
        if dataset is None or not hasattr(dataset, "map_widget"):
            return
        if not self._is_map_sync_enabled(dataset):
            return
        pid = str(point_id).strip()
        if not pid:
            return
        try:
            dataset.map_widget.set_selected_point(pid)
        except Exception:
            pass
        self._on_plot_point_selected(pid)

    def _on_table_rows_selected(self, point_ids):
        """Sync table multi-row selection to map (first selected point)."""
        try:
            ids = [str(v).strip() for v in (point_ids or []) if str(v).strip()]
        except Exception:
            ids = []
        if not ids:
            return
        self._on_table_row_selected(ids[0])

    def _on_table_row_deselected(self):
        """Sync table deselection to map deselection."""
        dataset = self.get_active_dataset()
        if dataset is None or not hasattr(dataset, "map_widget"):
            return
        if not self._is_map_sync_enabled(dataset):
            return
        try:
            dataset.map_widget.clear_selected_point()
        except Exception:
            pass

    def _on_map_location_clicked(self, lat: float, lon: float):
        """Convert map click (WGS84) to UTM32 and store as current target."""
        try:
            x, y = wgs84_to_utm32(float(lon), float(lat))
        except Exception:
            return
        self._set_active_target_location(x, y, source="map-click")
        if not self.is_point_creation_mode():
            return
        self._add_point_at_xy((x, y))

    def _geodk_settings(self) -> dict:
        cfg = getattr(self, "_geodk_cfg", None)
        if isinstance(cfg, dict):
            return cfg
        cfg = {
            "username": "",
            "password": "",
            "role": "",
            "insecure_ssl": False,
            "geoareaid": 1,
            "api_major_version": 3,
            "default_maxdepth": -40,
            "default_width": 1000,
            "default_height": 320,
            "borehole_tolerance_m_default": 10.0,
            "repro_keep_last_n": 50,
        }
        setattr(self, "_geodk_cfg", cfg)
        return cfg

    def _track_geodk_qt_job(self, thread: QThread, worker: object) -> None:
        """
        Keep Python references to QThread/worker pairs so they don't get garbage-collected
        before finishing (common PyQt pitfall).
        """
        jobs = getattr(self, "_geodk_qt_jobs", None)
        if not isinstance(jobs, list):
            jobs = []
            setattr(self, "_geodk_qt_jobs", jobs)
        entry = {"thread": thread, "worker": worker}
        jobs.append(entry)

        def _cleanup():
            try:
                jobs.remove(entry)
            except Exception:
                pass

        try:
            thread.finished.connect(_cleanup)
        except Exception:
            pass

    def _prompt_geodk_credentials(self) -> bool:
        cfg = self._geodk_settings()
        from .dialogs.geodk_credentials import GeoDKCredentialsDialog

        dlg = GeoDKCredentialsDialog(
            parent=self,
            username=str(cfg.get("username") or ""),
            role=str(cfg.get("role") or ""),
            insecure_ssl=bool(cfg.get("insecure_ssl", False)),
        )
        try:
            if dlg.exec_() != QDialog.Accepted:
                return False
        finally:
            dlg.deleteLater()

        cfg["username"] = dlg.username()
        cfg["password"] = dlg.password()
        cfg["role"] = dlg.role()
        cfg["insecure_ssl"] = dlg.insecure_ssl()
        # Force client rebuild.
        setattr(self, "_geodk_client", None)
        setattr(self, "_geodk_client_sig", None)
        return bool(cfg["username"] and cfg["password"])

    def _get_geodk_client(self):
        cfg = self._geodk_settings()
        sig = (
            str(cfg.get("username") or ""),
            str(cfg.get("password") or ""),
            str(cfg.get("role") or ""),
            int(cfg.get("geoareaid") or 1),
            int(cfg.get("api_major_version") or 3),
            bool(cfg.get("insecure_ssl", False)),
        )
        existing = getattr(self, "_geodk_client", None)
        if existing is not None and getattr(self, "_geodk_client_sig", None) == sig:
            return existing
        from core.geodk_api import GeoDKClient

        client = GeoDKClient(
            username=sig[0],
            password=sig[1],
            role=sig[2],
            geoareaid=sig[3],
            api_major_version=sig[4],
            insecure_ssl=sig[5],
        )
        setattr(self, "_geodk_client", client)
        setattr(self, "_geodk_client_sig", sig)
        return client

    @staticmethod
    def _geodk_path_from_latlon(coords: list) -> tuple[list[list[float]], list[list[float]]]:
        """Return (path_wgs84_latlon, path_25832_xy)."""
        from core.coordinate_transform import wgs84_to_utm32

        path_latlon: list[list[float]] = []
        path_utm: list[list[float]] = []
        for item in coords or []:
            if not isinstance(item, (list, tuple)) or len(item) < 2:
                continue
            try:
                lat = float(item[0])
                lon = float(item[1])
            except Exception:
                continue
            if not np.isfinite(lat) or not np.isfinite(lon):
                continue
            try:
                x, y = wgs84_to_utm32(float(lon), float(lat))
            except Exception:
                continue
            path_latlon.append([float(lat), float(lon)])
            path_utm.append([float(x), float(y)])
        return path_latlon, path_utm

    @staticmethod
    def _remember_geodk_transect(dataset, *, source: str, path_latlon: list, path_utm: list, length_m: float) -> None:
        """
        Store transect in per-dataset history for experimental fence rendering.
        Isolated storage only; does not affect core fetch/display logic.
        """
        try:
            hist = getattr(dataset, "geodk_transect_history", None)
            if not isinstance(hist, list):
                hist = []
                setattr(dataset, "geodk_transect_history", hist)
            # Simple dedupe against most recent entry.
            if hist:
                prev = hist[-1] if isinstance(hist[-1], dict) else {}
                if list(prev.get("path_utm") or []) == list(path_utm or []):
                    return
            import time as _time
            tid = f"T{len(hist) + 1:03d}"
            hist.append(
                {
                    "id": tid,
                    "source": str(source or "map"),
                    "path_latlon": list(path_latlon or []),
                    "path_utm": list(path_utm or []),
                    "length_m": float(length_m or 0.0),
                    "created_at": float(_time.time()),
                }
            )
            # Keep bounded history.
            if len(hist) > 120:
                del hist[:-120]
        except Exception:
            pass

    def _open_sensitivity_dialog(self):
        """Open the sensitivity analysis dialog (cached, non-modal)."""
        dataset = self.get_active_dataset()
        if dataset is None:
            QMessageBox.information(self, "Sensitivity Analysis", "Load/select a dataset first.")
            return
        data = dataset.filtered_data if dataset.filtered_data is not None else dataset.data
        if data is None or getattr(data, "empty", False):
            QMessageBox.information(self, "Sensitivity Analysis", "Dataset has no data to analyze.")
            return
        dlg = getattr(self, "_sensitivity_dialog", None)
        if dlg is None:
            from .dialogs.sensitivity_dialog import SensitivityDialog
            dlg = SensitivityDialog(main_window=self, parent=self)
            self._sensitivity_dialog = dlg
            dlg.finished.connect(lambda *_: setattr(self, "_sensitivity_dialog", None))
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

    def _open_geodk_fence_dialog(self):
        """
        Open isolated experimental fence-view dialog.
        This does not change normal map/plot behavior.
        """
        dataset = self.get_active_dataset()
        if dataset is None:
            QMessageBox.information(self, "Geo.dk Fence", "Load/select a dataset first.")
            return
        hist = list(getattr(dataset, "geodk_transect_history", []) or [])
        if not hist:
            QMessageBox.information(
                self,
                "Geo.dk Fence",
                "No transects in history yet.\nDraw one or more transects in Map or 2D plot first.",
            )
            return
        dlg = getattr(self, "_geodk_fence_dialog", None)
        if dlg is None:
            from .dialogs.geodk_fence_dialog import GeoDKFenceDialog

            dlg = GeoDKFenceDialog(parent=self, main_window=self)
            self._geodk_fence_dialog = dlg
            dlg.finished.connect(lambda *_: setattr(self, "_geodk_fence_dialog", None))
        try:
            dlg.refresh_from_dataset(dataset)
        except Exception:
            pass
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

    def _on_map_transect_created(self, coords: list):
        """Fetch Geo.dk cross section for the drawn transect line (models first; fetch via panel)."""
        dataset = self.get_active_dataset()
        if dataset is None or not hasattr(dataset, "map_widget"):
            return

        dataset_id = self._find_dataset_id(dataset) or str(self.active_dataset_id or "")
        mapw = dataset.map_widget
        mapw.set_geology_panel_loading("Transect drawn. Preparing Geo.dk request...")

        cfg = self._geodk_settings()
        if not str(cfg.get("username") or "").strip() or not str(cfg.get("password") or "").strip():
            if not self._prompt_geodk_credentials():
                mapw.set_geology_panel_loading("Geo.dk credentials are required to fetch cross sections.")
                return

        path_latlon, path_utm = self._geodk_path_from_latlon(coords)
        if len(path_utm) < 2:
            mapw.set_geology_panel_loading("Transect line was invalid (need 2 points).")
            return

        from core.geodk_api import path_length_m

        length_m = float(path_length_m(path_utm))
        self._remember_geodk_transect(
            dataset,
            source="map",
            path_latlon=list(path_latlon),
            path_utm=list(path_utm),
            length_m=float(length_m),
        )
        self._start_geodk_models_for_path(
            dataset_id=str(dataset_id),
            path_latlon=list(path_latlon),
            path_utm=list(path_utm),
            length_m=float(length_m),
            auto_fetch=False,
        )

    def _on_plot_geodk_transect_requested(self, path_utm_obj: object):
        """
        Trigger Geo.dk cross-section fetch from a line drawn in the 2D plot.

        Contract: `path_utm_obj` is [[x,y], ...] in EPSG:25832 (UTM32).
        """
        dataset = self.get_active_dataset()
        if dataset is None:
            return
        dataset_id = self._find_dataset_id(dataset) or str(self.active_dataset_id or "")

        # Normalize path_utm
        path_utm: list[list[float]] = []
        try:
            for pt in list(path_utm_obj or []):  # type: ignore[arg-type]
                if not isinstance(pt, (list, tuple)) or len(pt) < 2:
                    continue
                try:
                    x = float(pt[0])
                    y = float(pt[1])
                except Exception:
                    continue
                if np.isfinite(x) and np.isfinite(y):
                    path_utm.append([float(x), float(y)])
        except Exception:
            path_utm = []
        if len(path_utm) < 2:
            return

        # Best-effort lat/lon for diagnostics / repro bundle.
        path_latlon: list[list[float]] = []
        try:
            from core.coordinate_transform import utm32_to_wgs84

            for x, y in path_utm:
                lon, lat = utm32_to_wgs84(float(x), float(y))
                path_latlon.append([float(lat), float(lon)])
        except Exception:
            path_latlon = []

        from core.geodk_api import path_length_m

        length_m = float(path_length_m(path_utm))
        self._remember_geodk_transect(
            dataset,
            source="plot",
            path_latlon=list(path_latlon),
            path_utm=list(path_utm),
            length_m=float(length_m),
        )

        # Store transect context so plot Geo.dk panel "Fetch" can reuse it.
        try:
            dataset._geodk_path_latlon = list(path_latlon)  # type: ignore[attr-defined]
            dataset._geodk_path_utm = list(path_utm)  # type: ignore[attr-defined]
            dataset._geodk_length_m = float(length_m)  # type: ignore[attr-defined]
        except Exception:
            pass
        # Prefer the plot Geo.dk panel as UI target if it exists.
        ui_target = None
        try:
            if hasattr(dataset, "plot_page") and hasattr(dataset.plot_page, "plot_widget"):
                dlg = getattr(dataset.plot_page.plot_widget, "_cross_section_dialog", None)
                ui_target = getattr(dlg, "_geodk_panel", None) if dlg is not None else None
        except Exception:
            ui_target = None

        self._start_geodk_models_for_path(
            dataset_id=str(dataset_id),
            path_latlon=list(path_latlon),
            path_utm=list(path_utm),
            length_m=float(length_m),
            auto_fetch=True,
            ui_target=ui_target,
        )

    def _start_geodk_models_for_path(
        self,
        *,
        dataset_id: str,
        path_latlon: list[list[float]],
        path_utm: list[list[float]],
        length_m: float,
        auto_fetch: bool,
        ui_target=None,
    ) -> None:
        ds = self.datasets.get(str(dataset_id))
        mapw = getattr(ds, "map_widget", None) if ds is not None else None
        target = ui_target if ui_target is not None else mapw

        cfg = self._geodk_settings()
        if not str(cfg.get("username") or "").strip() or not str(cfg.get("password") or "").strip():
            if not self._prompt_geodk_credentials():
                if target is not None:
                    target.set_geology_panel_loading("Geo.dk credentials are required to fetch cross sections.")
                return
        try:
            client = self._get_geodk_client()
        except Exception as exc:
            if target is not None:
                target.set_geology_panel_loading(f"Geo.dk setup failed: {exc}")
            return

        job_id = int(getattr(self, "_geodk_job_id", 0) or 0) + 1
        setattr(self, "_geodk_job_id", job_id)
        if target is not None:
            target.set_geology_panel_loading("Loading Geo.dk models for this transect...")

        thread = QThread(self)
        worker = FunctionWorker(client.geomodels_for_path, path_utm)
        worker.moveToThread(thread)
        worker._ha_geodk_job_id = int(job_id)  # type: ignore[attr-defined]
        worker._ha_geodk_dataset_id = str(dataset_id)  # type: ignore[attr-defined]
        worker._ha_geodk_path_latlon = list(path_latlon)  # type: ignore[attr-defined]
        worker._ha_geodk_path_utm = list(path_utm)  # type: ignore[attr-defined]
        worker._ha_geodk_length_m = float(length_m)  # type: ignore[attr-defined]
        worker._ha_geodk_client = client  # type: ignore[attr-defined]
        worker._ha_geodk_auto_fetch = bool(auto_fetch)  # type: ignore[attr-defined]
        worker._ha_geodk_ui_target = target  # type: ignore[attr-defined]

        worker.finished.connect(self._on_geodk_models_ready)
        worker.failed.connect(self._on_geodk_models_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.started.connect(worker.run)
        self._track_geodk_qt_job(thread, worker)
        thread.start()

    def _on_geodk_models_ready(self, result: object):
        worker = self.sender()
        job_id = getattr(worker, "_ha_geodk_job_id", None)
        dataset_id = getattr(worker, "_ha_geodk_dataset_id", None)
        if job_id is None or dataset_id is None:
            return
        if int(getattr(self, "_geodk_job_id", 0) or 0) != int(job_id):
            return

        ds = self.datasets.get(str(dataset_id))
        if ds is None:
            return
        target = getattr(worker, "_ha_geodk_ui_target", None)
        mapw = getattr(ds, "map_widget", None)
        if target is None:
            target = mapw

        try:
            models, cache_hit = result  # type: ignore[misc]
        except Exception:
            if target is not None:
                target.set_geology_panel_loading("Geo.dk model query returned an unexpected result.")
            return
        if not models:
            if target is not None:
                target.set_geology_panel_loading("No Geo.dk models matched this transect. Try another line.")
            return

        cfg = self._geodk_settings()
        length_m = float(getattr(worker, "_ha_geodk_length_m", 0.0) or 0.0)
        path_latlon = list(getattr(worker, "_ha_geodk_path_latlon", []) or [])
        path_utm = list(getattr(worker, "_ha_geodk_path_utm", []) or [])
        client = getattr(worker, "_ha_geodk_client", None)
        if client is None:
            if target is not None:
                target.set_geology_panel_loading("Geo.dk client was not available for cross section request.")
            return

        # Store transect context so panel-driven "Fetch" can reuse it.
        try:
            ds._geodk_models = list(models)  # type: ignore[attr-defined]
            ds._geodk_path_latlon = list(path_latlon)  # type: ignore[attr-defined]
            ds._geodk_path_utm = list(path_utm)  # type: ignore[attr-defined]
            ds._geodk_length_m = float(length_m)  # type: ignore[attr-defined]
            ds._geodk_cache_hit = bool(cache_hit)  # type: ignore[attr-defined]
        except Exception:
            pass

        # Populate the in-map Geo.dk panel; user can now fetch directly from there.
        try:
            if target is not None:
                target.set_geodk_panel_models(
                    models=list(models),
                    default_geomodelid=None,
                    default_maxdepth=int(cfg.get("default_maxdepth", -40) or -40),
                    default_width=int(cfg.get("default_width", 1000) or 1000),
                    default_height=int(cfg.get("default_height", 320) or 320),
                    default_borehole_tolerance_m=float(cfg.get("borehole_tolerance_m_default", 10.0) or 10.0),
                    path_m=float(length_m),
                    cache_hit=bool(cache_hit),
                )
        except Exception as exc:
            if target is not None:
                target.set_geology_panel_loading(f"Failed to populate Geo.dk panel: {exc}")

        # Auto-fetch (used by plot cross-section): pick a default model and fetch immediately.
        auto_fetch = bool(getattr(worker, "_ha_geodk_auto_fetch", False))
        if auto_fetch:
            try:
                # Prefer first non -1 model (terrain fallback is appended as -1).
                picked = None
                # Reuse last selection if possible.
                last_mid = getattr(ds, "_geodk_last_geomodelid", None)
                try:
                    last_mid = int(last_mid) if last_mid is not None else None
                except Exception:
                    last_mid = None
                if last_mid is not None:
                    for m in list(models):
                        if not isinstance(m, dict):
                            continue
                        mid = m.get("ID", m.get("Id", m.get("id", None)))
                        try:
                            if int(mid) == int(last_mid):
                                picked = int(last_mid)
                                break
                        except Exception:
                            continue
                for m in list(models):
                    if not isinstance(m, dict):
                        continue
                    mid = m.get("ID", m.get("Id", m.get("id", None)))
                    try:
                        mid_int = int(mid)
                    except Exception:
                        continue
                    if mid_int != -1:
                        picked = mid_int
                        break
                if picked is None:
                    picked = int(models[0].get("ID", -1)) if isinstance(models[0], dict) else -1

                from core.geodk_api import auto_linepointdistance
                from .dialogs.geodk_transect_settings import GeoDKTransectSettings

                maxdepth = int(cfg.get("default_maxdepth", -40) or -40)
                width = int(cfg.get("default_width", 1000) or 1000)
                height = int(cfg.get("default_height", 320) or 320)
                bore_tol = float(cfg.get("borehole_tolerance_m_default", 10.0) or 10.0)
                lpd = int(auto_linepointdistance(length_m=float(length_m or 0.0), width_px=int(width)))
                settings = GeoDKTransectSettings(
                    geomodelid=int(picked),
                    maxdepth=int(maxdepth),
                    width=int(width),
                    height=int(height),
                    linepointdistance=int(max(1, lpd)),
                    auto_linepointdistance=True,
                    borehole_tolerance_m=float(bore_tol),
                )
                self._start_geodk_crosssection_for_dataset(
                    dataset=ds,
                    dataset_id=str(dataset_id),
                    client=client,
                    path_latlon=list(path_latlon),
                    path_utm=list(path_utm),
                    length_m=float(length_m or 0.0),
                    settings=settings,
                    ui_target=target,
                )
            except Exception:
                pass

    def _on_geodk_models_failed(self, msg: str, tb: str):
        worker = self.sender()
        job_id = getattr(worker, "_ha_geodk_job_id", None)
        dataset_id = getattr(worker, "_ha_geodk_dataset_id", None)
        if job_id is None or dataset_id is None:
            return
        if int(getattr(self, "_geodk_job_id", 0) or 0) != int(job_id):
            return
        ds = self.datasets.get(str(dataset_id))
        if ds is None or not hasattr(ds, "map_widget"):
            return
        ds.map_widget.set_geology_panel_loading(f"Geo.dk model query failed: {msg}")
        print(f"[geo.dk] model_query_failed msg={msg}\n{tb}")

    def _on_map_geodk_credentials_requested(self):
        """Open Geo.dk credentials dialog from the in-panel button."""
        try:
            self._prompt_geodk_credentials()
        except Exception:
            pass

    def _on_map_geodk_copy_repro_requested(self):
        """Copy last Geo.dk repro bundle path to clipboard (best-effort)."""
        dataset = self.get_active_dataset()
        if dataset is None:
            return
        p = getattr(dataset, "_geodk_last", None)
        repro_path = str(p.get("repro_path") or "") if isinstance(p, dict) else ""
        repro_path = repro_path.strip()
        if not repro_path:
            try:
                self.status_bar.showMessage("No Geo.dk repro bundle available yet.", 4000)
            except Exception:
                pass
            return
        try:
            cb = QApplication.clipboard()
            cb.setText(repro_path)
            self.status_bar.showMessage("Copied Geo.dk repro bundle path to clipboard.", 4000)
        except Exception:
            try:
                self.status_bar.showMessage(repro_path, 6000)
            except Exception:
                pass

    def _on_plot_geodk_copy_repro_requested(self):
        # Same behavior as map button.
        self._on_map_geodk_copy_repro_requested()

    def _on_map_geodk_download_requested(self):
        """
        Open a Save dialog and copy the last Geo.dk cross-section SVG to disk.
        This uses the most recent in-memory SVG (not the `.recovery` file).
        """
        dataset = self.get_active_dataset()
        if dataset is None:
            return
        p = getattr(dataset, "_geodk_last", None)
        svg_text = str(p.get("svg") or "") if isinstance(p, dict) else ""
        if not svg_text.strip():
            try:
                self.status_bar.showMessage("No Geo.dk cross-section loaded yet.", 4000)
            except Exception:
                pass
            return
        try:
            default_name = "geo_dk_crosssection.svg"
            out_path, _ = QFileDialog.getSaveFileName(
                self,
                "Save Geo.dk Cross-Section SVG",
                default_name,
                "SVG (*.svg);;All Files (*)",
            )
            if not out_path:
                return
            Path(str(out_path)).write_text(svg_text, encoding="utf-8")
            self.status_bar.showMessage(f"Saved Geo.dk cross-section: {out_path}", 6000)
        except Exception as exc:
            try:
                self.status_bar.showMessage(f"Save failed: {exc}", 6000)
            except Exception:
                pass

    def _on_plot_geodk_download_requested(self):
        # Same behavior as map button.
        self._on_map_geodk_download_requested()

    def _on_plot_geodk_fetch_requested(self, payload_json: str):
        """Handle Fetch click from the plot Geo.dk panel."""
        sender = self.sender()
        dataset = self.get_active_dataset()
        if dataset is None:
            return

        ui_target = sender
        # Use the last plot-drawn transect if present, else fallback to map-stored transect.
        path_latlon = getattr(dataset, "_geodk_path_latlon", None)
        path_utm = getattr(dataset, "_geodk_path_utm", None)
        length_m = getattr(dataset, "_geodk_length_m", None)
        if not isinstance(path_latlon, list) or not isinstance(path_utm, list) or len(path_utm) < 2:
            if ui_target is not None:
                try:
                    ui_target.set_geology_panel_loading("No transect found. Draw a line in the plot first.")
                except Exception:
                    pass
            return

        cfg = self._geodk_settings()
        if not str(cfg.get("username") or "").strip() or not str(cfg.get("password") or "").strip():
            if not self._prompt_geodk_credentials():
                if ui_target is not None:
                    try:
                        ui_target.set_geology_panel_loading("Geo.dk credentials are required to fetch cross sections.")
                    except Exception:
                        pass
                return

        try:
            client = self._get_geodk_client()
        except Exception as exc:
            if ui_target is not None:
                try:
                    ui_target.set_geology_panel_loading(f"Geo.dk setup failed: {exc}")
                except Exception:
                    pass
            return

        import json as _json
        try:
            req = _json.loads(str(payload_json or "{}"))
            if not isinstance(req, dict):
                req = {}
        except Exception:
            req = {}

        try:
            geomodelid = int(req.get("geomodelid"))
        except Exception:
            geomodelid = -999999
        try:
            maxdepth = int(req.get("maxdepth", cfg.get("default_maxdepth", -40)))
        except Exception:
            maxdepth = int(cfg.get("default_maxdepth", -40) or -40)
        try:
            width = int(req.get("width", cfg.get("default_width", 1000)))
        except Exception:
            width = int(cfg.get("default_width", 1000) or 1000)
        try:
            height = int(req.get("height", cfg.get("default_height", 320)))
        except Exception:
            height = int(cfg.get("default_height", 320) or 320)
        auto_lpd = bool(req.get("auto_linepointdistance", True))
        try:
            lpd_manual = int(req.get("linepointdistance", 2))
        except Exception:
            lpd_manual = 2
        try:
            bore_tol_m = float(req.get("borehole_tolerance_m", cfg.get("borehole_tolerance_m_default", 10.0)))
        except Exception:
            bore_tol_m = float(cfg.get("borehole_tolerance_m_default", 10.0) or 10.0)
        if not np.isfinite(float(bore_tol_m)):
            bore_tol_m = 10.0
        bore_tol_m = float(max(0.0, min(500.0, bore_tol_m)))

        if geomodelid == -999999:
            if ui_target is not None:
                try:
                    ui_target.set_geology_panel_loading("Pick a Geo.dk model first.")
                except Exception:
                    pass
            return

        from core.geodk_api import auto_linepointdistance

        linepointdistance = (
            int(auto_linepointdistance(length_m=float(length_m or 0.0), width_px=int(width)))
            if auto_lpd
            else int(max(1, lpd_manual))
        )

        cfg["default_maxdepth"] = int(maxdepth)
        cfg["default_width"] = int(width)
        cfg["default_height"] = int(height)
        cfg["borehole_tolerance_m_default"] = float(bore_tol_m)

        from .dialogs.geodk_transect_settings import GeoDKTransectSettings

        settings = GeoDKTransectSettings(
            geomodelid=int(geomodelid),
            maxdepth=int(maxdepth),
            width=int(width),
            height=int(height),
            linepointdistance=int(linepointdistance),
            auto_linepointdistance=bool(auto_lpd),
            borehole_tolerance_m=float(bore_tol_m),
        )

        dataset_id = self._find_dataset_id(dataset) or str(self.active_dataset_id or "")
        self._start_geodk_crosssection_for_dataset(
            dataset=dataset,
            dataset_id=str(dataset_id),
            client=client,
            path_latlon=list(path_latlon),
            path_utm=list(path_utm),
            length_m=float(length_m or 0.0),
            settings=settings,
            ui_target=ui_target,
        )

    def _on_map_geodk_fetch_requested(self, payload_json: str):
        """Handle Fetch click from the in-map Geo.dk panel."""
        sender = self.sender()
        dataset = None
        dataset_id = None
        try:
            for did, ds in (self.datasets or {}).items():
                if getattr(ds, "map_widget", None) is sender:
                    dataset = ds
                    dataset_id = str(did)
                    break
        except Exception:
            dataset = None
            dataset_id = None
        if dataset is None or not hasattr(dataset, "map_widget"):
            return
        mapw = dataset.map_widget

        path_latlon = getattr(dataset, "_geodk_path_latlon", None)
        path_utm = getattr(dataset, "_geodk_path_utm", None)
        length_m = getattr(dataset, "_geodk_length_m", None)
        if not isinstance(path_latlon, list) or not isinstance(path_utm, list) or len(path_utm) < 2:
            coords = getattr(mapw, "_transect_coords", None)
            if isinstance(coords, list) and coords:
                path_latlon, path_utm = self._geodk_path_from_latlon(coords)
                from core.geodk_api import path_length_m

                length_m = float(path_length_m(path_utm))
            else:
                mapw.set_geology_panel_loading("No transect found. Draw a transect first.")
                return

        cfg = self._geodk_settings()
        if not str(cfg.get("username") or "").strip() or not str(cfg.get("password") or "").strip():
            if not self._prompt_geodk_credentials():
                mapw.set_geology_panel_loading("Geo.dk credentials are required to fetch cross sections.")
                return

        try:
            client = self._get_geodk_client()
        except Exception as exc:
            mapw.set_geology_panel_loading(f"Geo.dk setup failed: {exc}")
            return

        import json as _json
        try:
            req = _json.loads(str(payload_json or "{}"))
            if not isinstance(req, dict):
                req = {}
        except Exception:
            req = {}

        try:
            geomodelid = int(req.get("geomodelid"))
        except Exception:
            geomodelid = -999999
        try:
            maxdepth = int(req.get("maxdepth", cfg.get("default_maxdepth", -40)))
        except Exception:
            maxdepth = int(cfg.get("default_maxdepth", -40) or -40)
        try:
            width = int(req.get("width", cfg.get("default_width", 1000)))
        except Exception:
            width = int(cfg.get("default_width", 1000) or 1000)
        try:
            height = int(req.get("height", cfg.get("default_height", 320)))
        except Exception:
            height = int(cfg.get("default_height", 320) or 320)
        auto_lpd = bool(req.get("auto_linepointdistance", True))
        try:
            lpd_manual = int(req.get("linepointdistance", 2))
        except Exception:
            lpd_manual = 2
        try:
            bore_tol_m = float(req.get("borehole_tolerance_m", cfg.get("borehole_tolerance_m_default", 10.0)))
        except Exception:
            bore_tol_m = float(cfg.get("borehole_tolerance_m_default", 10.0) or 10.0)
        if not np.isfinite(float(bore_tol_m)):
            bore_tol_m = 10.0
        bore_tol_m = float(max(0.0, min(500.0, bore_tol_m)))

        if geomodelid == -999999:
            mapw.set_geology_panel_loading("Pick a Geo.dk model first.")
            return

        from core.geodk_api import auto_linepointdistance

        linepointdistance = (
            int(auto_linepointdistance(length_m=float(length_m or 0.0), width_px=int(width)))
            if auto_lpd
            else int(max(1, lpd_manual))
        )

        # Persist defaults for next fetch.
        cfg["default_maxdepth"] = int(maxdepth)
        cfg["default_width"] = int(width)
        cfg["default_height"] = int(height)
        cfg["borehole_tolerance_m_default"] = float(bore_tol_m)

        from .dialogs.geodk_transect_settings import GeoDKTransectSettings

        settings = GeoDKTransectSettings(
            geomodelid=int(geomodelid),
            maxdepth=int(maxdepth),
            width=int(width),
            height=int(height),
            linepointdistance=int(linepointdistance),
            auto_linepointdistance=bool(auto_lpd),
            borehole_tolerance_m=float(bore_tol_m),
        )

        self._start_geodk_crosssection_for_dataset(
            dataset=dataset,
            dataset_id=str(dataset_id or ""),
            client=client,
            path_latlon=list(path_latlon),
            path_utm=list(path_utm),
            length_m=float(length_m or 0.0),
            settings=settings,
            ui_target=mapw,
        )

    def _start_geodk_crosssection_for_dataset(
        self,
        *,
        dataset,
        dataset_id: str,
        client,
        path_latlon: list,
        path_utm: list,
        length_m: float,
        settings,
        ui_target=None,
    ) -> None:
        """Start cross-section fetch job (shared by map panel + plot-triggered transects)."""
        mapw = getattr(dataset, "map_widget", None)
        target = ui_target if ui_target is not None else mapw
        cfg = self._geodk_settings()

        # Prepare borehole overlay candidates from current dataset.
        boreholes: list[dict] = []
        try:
            data_source = dataset.filtered_plot_data if dataset.filtered_plot_data is not None else dataset.data
        except Exception:
            data_source = None
        mapping = dataset.col_mapping if isinstance(getattr(dataset, "col_mapping", None), dict) else {}
        id_col = mapping.get("ID")
        x_col = mapping.get("x")
        y_col = mapping.get("y")
        top_col = getattr(dataset, "top_column", None)
        bottom_col = getattr(dataset, "bottom_column", None)
        depth_col = getattr(dataset, "depth_column", None)
        excluded = set(getattr(dataset, "excluded_ids", set()) or set())

        try:
            bore_tol_m = float(getattr(settings, "borehole_tolerance_m", cfg.get("borehole_tolerance_m_default", 10.0)) or 10.0)
        except Exception:
            bore_tol_m = 10.0

        # Fast pre-filter: bbox of transect (+ tolerance margin).
        minx = miny = maxx = maxy = None
        try:
            xs = [float(p[0]) for p in (path_utm or []) if isinstance(p, list) and len(p) >= 2]
            ys = [float(p[1]) for p in (path_utm or []) if isinstance(p, list) and len(p) >= 2]
            if xs and ys:
                minx = min(xs) - float(bore_tol_m)
                maxx = max(xs) + float(bore_tol_m)
                miny = min(ys) - float(bore_tol_m)
                maxy = max(ys) + float(bore_tol_m)
        except Exception:
            minx = miny = maxx = maxy = None

        if data_source is not None and x_col and y_col and (x_col in data_source.columns) and (y_col in data_source.columns):
            try:
                import numpy as _np  # type: ignore
            except Exception:
                _np = None
            max_items = 6000
            try:
                it = data_source.itertuples(index=False)
            except Exception:
                it = None
            if it is not None:
                cols = list(getattr(data_source, "columns", []))
                idx = {c: i for i, c in enumerate(cols)}
                xi = idx.get(x_col)
                yi = idx.get(y_col)
                idi = idx.get(id_col) if id_col in idx else None
                ti = idx.get(top_col) if top_col in idx else None
                bi = idx.get(bottom_col) if bottom_col in idx else None
                di = idx.get(depth_col) if depth_col in idx else None
                for row in it:
                    if len(boreholes) >= max_items:
                        break
                    try:
                        x = float(row[xi]) if xi is not None else None
                        y = float(row[yi]) if yi is not None else None
                    except Exception:
                        continue
                    if x is None or y is None:
                        continue
                    if _np is not None:
                        try:
                            if not (_np.isfinite(x) and _np.isfinite(y)):
                                continue
                        except Exception:
                            pass
                    if minx is not None and maxx is not None and miny is not None and maxy is not None:
                        if x < float(minx) or x > float(maxx) or y < float(miny) or y > float(maxy):
                            continue
                    pid = ""
                    try:
                        if idi is not None:
                            pid = str(row[idi]).strip()
                    except Exception:
                        pid = ""
                    if pid and pid in excluded:
                        continue

                    def _f(i):
                        if i is None:
                            return None
                        try:
                            v = float(row[i])
                            return v if (v == v) else None
                        except Exception:
                            return None

                    boreholes.append(
                        {
                            "id": pid,
                            "x": float(x),
                            "y": float(y),
                            "top_m": _f(ti),
                            "bottom_m": _f(bi),
                            "depth_m": _f(di),
                        }
                    )

        # Remember last chosen model for auto-fetch reuse.
        try:
            setattr(dataset, "_geodk_last_geomodelid", int(getattr(settings, "geomodelid", -1)))
        except Exception:
            pass

        job_id = int(getattr(self, "_geodk_job_id", 0) or 0) + 1
        setattr(self, "_geodk_job_id", job_id)
        if target is not None:
            target.set_geology_panel_loading("Requesting Geo.dk cross section...")

        cs_thread = QThread(self)
        cs_worker = FunctionWorker(
            self._geodk_crosssection_job,
            client,
            path_latlon,
            path_utm,
            float(length_m or 0.0),
            settings,
            boreholes,
            int(cfg.get("repro_keep_last_n", 50) or 50),
        )
        cs_worker.moveToThread(cs_thread)
        cs_worker._ha_geodk_job_id = int(job_id)  # type: ignore[attr-defined]
        cs_worker._ha_geodk_dataset_id = str(dataset_id or "")  # type: ignore[attr-defined]
        cs_worker._ha_geodk_ui_target = target  # type: ignore[attr-defined]
        cs_worker.finished.connect(self._on_geodk_crosssection_ready)
        cs_worker.failed.connect(self._on_geodk_crosssection_failed)
        cs_worker.finished.connect(cs_thread.quit)
        cs_worker.failed.connect(cs_thread.quit)
        cs_worker.finished.connect(cs_worker.deleteLater)
        cs_worker.failed.connect(cs_worker.deleteLater)
        cs_thread.finished.connect(cs_thread.deleteLater)
        cs_thread.started.connect(cs_worker.run)
        self._track_geodk_qt_job(cs_thread, cs_worker)
        cs_thread.start()

    @staticmethod
    def _geodk_crosssection_job(
        client,
        path_latlon,
        path_utm,
        length_m: float,
        settings,
        boreholes: list | None = None,
        repro_keep_last_n: int = 50,
    ):
        from core.geodk_api import (
            build_geounit_legend_html,
            has_geology,
            normalize_svg_for_display,
            svg_stats,
            write_repro_bundle,
        )
        from core.geodk_overlay import compute_borehole_overlay

        data = client.crosssection(
            path_25832=path_utm,
            geomodelid=int(settings.geomodelid),
            width=int(settings.width),
            height=int(settings.height),
            maxdepth=int(settings.maxdepth),
            linepointdistance=int(settings.linepointdistance),
        )

        model_name = None
        if isinstance(data.get("Model"), dict):
            model_name = data["Model"].get("Name")

        svg_raw = str(data.get("Svg") or "")
        layout = data.get("SvgLayout") if isinstance(data.get("SvgLayout"), dict) else {}
        try:
            svg_w = int(layout.get("Width") or settings.width)
        except Exception:
            svg_w = int(settings.width)
        try:
            svg_h = int(layout.get("Height") or settings.height)
        except Exception:
            svg_h = int(settings.height)

        svg_norm = normalize_svg_for_display(svg_raw, width=svg_w, height=svg_h)
        stats = svg_stats(svg_norm)
        geo = bool(has_geology(svg_norm))
        legend_html = build_geounit_legend_html(data.get("Model"), svg_norm)

        resp_summary = {
            "ZMin": data.get("ZMin"),
            "ZMax": data.get("ZMax"),
            "PathLength": data.get("PathLength"),
        }
        try:
            tol_m = float(getattr(settings, "borehole_tolerance_m", 10.0) or 10.0)
        except Exception:
            tol_m = 10.0
        overlay = compute_borehole_overlay(
            svg_text=svg_norm,
            svg_w=int(svg_w),
            svg_h=int(svg_h),
            path_utm=path_utm,
            boreholes=list(boreholes or []),
            length_m=float(length_m),
            response_summary=resp_summary,
            tolerance_m=float(tol_m),
        )
        overlay_items = list(overlay.items)
        viewbox_w = float(overlay.viewbox_w)
        viewbox_h = float(overlay.viewbox_h)
        overlay_diag = dict(overlay.diag)

        info = (
            f"Model: {model_name or 'N/A'} | GeoModelId: {int(settings.geomodelid)} | "
            f"Length: {float(length_m):.0f} m | Depth: {int(settings.maxdepth)}"
        )
        if not geo:
            info = info + f" | SVG polygons: {int(stats.get('polygons', 0) or 0)} (terrain-only)"

        repro_payload = {
            "request": {
                "geoareaid": int(getattr(client, "geoareaid", 1) or 1),
                "api_major_version": int(getattr(client, "api_major_version", 3) or 3),
                "geomodelid": int(settings.geomodelid),
                "width": int(settings.width),
                "height": int(settings.height),
                "maxdepth": int(settings.maxdepth),
                "linepointdistance": int(settings.linepointdistance),
                "path_wgs84_latlon": path_latlon,
                "path_25832_xy": path_utm,
                "path_length_m": float(length_m),
            },
            "response_summary": {
                "ModelName": str(model_name or ""),
                "ZMin": data.get("ZMin"),
                "ZMax": data.get("ZMax"),
                "PathLength": data.get("PathLength"),
                "ProfileLayersCount": len(data.get("ProfileLayers") or []) if isinstance(data.get("ProfileLayers"), list) else None,
            },
            "client_diag": {
                "token_refresh_reason": str(getattr(client, "_last_token_refresh_reason", "") or ""),
                "token_claims": getattr(client, "token_claims", lambda: None)() or None,
            },
            "svg_stats": stats,
            "has_geology": bool(geo),
            "borehole_overlay": {
                **overlay_diag,
            },
        }
        repro_path = None
        try:
            repro_path = str(write_repro_bundle(repro_payload, svg_text=svg_norm, keep_last_n=int(repro_keep_last_n or 50)))
        except Exception:
            repro_path = None

        return {
            "svg": svg_norm,
            "legend_html": legend_html,
            "info": info,
            "stats": stats,
            "has_geology": geo,
            "repro_path": repro_path,
            "diag": repro_payload,
            "overlay_items": overlay_items,
            "viewbox_w": float(viewbox_w),
            "viewbox_h": float(viewbox_h),
        }

    def _on_geodk_crosssection_ready(self, payload: object):
        worker = self.sender()
        job_id = getattr(worker, "_ha_geodk_job_id", None)
        dataset_id = getattr(worker, "_ha_geodk_dataset_id", None)
        if job_id is None or dataset_id is None:
            return
        if int(getattr(self, "_geodk_job_id", 0) or 0) != int(job_id):
            return
        ds = self.datasets.get(str(dataset_id))
        if ds is None:
            return
        target = getattr(worker, "_ha_geodk_ui_target", None)
        mapw = getattr(ds, "map_widget", None)
        if target is None:
            target = mapw
        try:
            p = payload if isinstance(payload, dict) else {}
            svg = str(p.get("svg") or "")
            info = str(p.get("info") or "")
            legend_html = str(p.get("legend_html") or "")
            ds._geodk_last = p
            if target is not None:
                target.set_geology_panel_svg(svg_html=svg, info_text=info, legend_html=legend_html)
            # Push Geo.dk-derived geology strip into plot cross-section provider (if enabled).
            try:
                if hasattr(ds, "plot_page") and hasattr(ds.plot_page, "plot_widget"):
                    pw = ds.plot_page.plot_widget
                    prov = getattr(pw, "_geology_provider", None)
                    from core.geology_layers import GeoDkSvgSurfaceGeologyProvider

                    if isinstance(prov, GeoDkSvgSurfaceGeologyProvider):
                        prov.update_from_geodk_payload(dict(p))
            except Exception:
                pass
            # Update metrics + diagnostics tab.
            try:
                stats = p.get("stats") if isinstance(p.get("stats"), dict) else {}
                poly = None
                try:
                    poly = int(stats.get("polygons", None))
                except Exception:
                    poly = None
                if target is not None:
                    target.set_geodk_panel_metrics(polygons=poly)

                diag = p.get("diag") if isinstance(p.get("diag"), dict) else {}
                if diag:
                    diag = dict(diag)
                    diag["note"] = "SVG is displayed via <img> to isolate Geo.dk CSS from Leaflet."
                if target is not None:
                    target.set_geodk_panel_diag(diag)
            except Exception:
                pass
            # Borehole overlay (vertical lines on cross-section).
            try:
                items = p.get("overlay_items") if isinstance(p.get("overlay_items"), list) else []
                vw = float(p.get("viewbox_w") or 0.0)
                vh = float(p.get("viewbox_h") or 0.0)
                if items and vw > 0 and vh > 0:
                    if target is not None:
                        target.set_geodk_boreholes_overlay(items=list(items), viewbox_w=vw, viewbox_h=vh)
            except Exception:
                pass
            repro_path = p.get("repro_path")
            if repro_path:
                try:
                    self.status_bar.showMessage(f"Geo.dk repro bundle: {repro_path}", 8000)
                except Exception:
                    pass
        except Exception as exc:
            if target is not None:
                target.set_geology_panel_loading(f"Failed to render Geo.dk SVG: {exc}")

    def _on_geodk_crosssection_failed(self, msg: str, tb: str):
        worker = self.sender()
        job_id = getattr(worker, "_ha_geodk_job_id", None)
        dataset_id = getattr(worker, "_ha_geodk_dataset_id", None)
        if job_id is None or dataset_id is None:
            return
        if int(getattr(self, "_geodk_job_id", 0) or 0) != int(job_id):
            return
        ds = self.datasets.get(str(dataset_id))
        if ds is None or not hasattr(ds, "map_widget"):
            return
        ds.map_widget.set_geology_panel_loading(f"Geo.dk cross section failed: {msg}")
        print(f"[geo.dk] crosssection_failed msg={msg}\n{tb}")

    def _add_point_at_xy(self, target_xy):
        """Prompt for head value and append a new point at given UTM32 XY."""
        dataset = self.get_active_dataset()
        if dataset is None or self.data is None:
            QMessageBox.warning(self, "No Data", "Load a dataset before adding a point.")
            return

        mapping = self.col_mapping if isinstance(self.col_mapping, dict) else {}
        x_col = mapping.get("x")
        y_col = mapping.get("y")
        h_col = mapping.get("hydraulic head")
        id_col = mapping.get("ID")
        if not x_col or not y_col or not h_col:
            QMessageBox.warning(
                self,
                "Missing Mapping",
                "Point creation requires mapped x, y, and hydraulic head columns.",
            )
            return

        default_head = 0.0
        try:
            if h_col in self.data.columns and not self.data[h_col].dropna().empty:
                default_head = float(self.data[h_col].dropna().astype(float).median())
        except Exception:
            default_head = 0.0

        head_value, ok = QInputDialog.getDouble(
            self,
            "Add Point at Target",
            f"Hydraulic head value ({h_col}):",
            default_head,
            -1e9,
            1e9,
            6,
        )
        if not ok:
            return

        point_id_value = None
        if id_col:
            suggested_id = suggest_point_id(dataset.data, id_col)
            point_id_text, ok_id = QInputDialog.getText(
                self,
                "Add Point at Target",
                f"Point ID ({id_col}) [leave empty for auto]:",
                text=str(suggested_id),
            )
            if not ok_id:
                return
            point_id_value = str(point_id_text).strip() or None

        try:
            record = build_point_record(
                target_xy=target_xy,
                head_value=head_value,
                col_mapping=mapping,
                existing_data=dataset.data,
                point_id=point_id_value,
            )
            new_data = append_point(dataset.data, record)
        except Exception as exc:
            QMessageBox.critical(self, "Point Creation Failed", str(exc))
            return

        # Ensure active head filter range/selection includes the new value.
        try:
            if hasattr(self, "properties_panel") and h_col:
                head_bounds = self.properties_panel.head_range.get_bounds()
                head_values = self.properties_panel.head_range.get_values()
                hb_min, hb_max = float(head_bounds[0]), float(head_bounds[1])
                hv_min, hv_max = float(head_values[0]), float(head_values[1])
                v = float(head_value)
                new_bound_min = min(hb_min, v)
                new_bound_max = max(hb_max, v)
                new_value_min = min(hv_min, v)
                new_value_max = max(hv_max, v)
                self.properties_panel.update_filter_ranges(
                    head_range=(new_bound_min, new_bound_max),
                    head_values=(new_value_min, new_value_max),
                )
                ds = self.get_active_dataset()
                if ds is not None:
                    ds.head_bounds = (new_bound_min, new_bound_max)
                    ds.head_range = (new_value_min, new_value_max)
        except Exception:
            pass

        dataset.data = new_data
        self.data = new_data
        self.refilter_and_recalculate()

    def on_add_point_at_target(self):
        """Create a new point at stored active target location (UTM32)."""
        target_xy = self._get_active_target_location()
        if target_xy is None:
            dataset = self.get_active_dataset()
            selected = getattr(dataset.plot_page.plot_widget, "_selected_point", None) if dataset is not None else None
            if isinstance(selected, dict) and "x" in selected and "y" in selected:
                try:
                    target_xy = (float(selected["x"]), float(selected["y"]))
                    self._set_active_target_location(target_xy[0], target_xy[1], source="plot-selected")
                except Exception:
                    target_xy = None
        if target_xy is None:
            QMessageBox.information(
                self,
                "No Target Location",
                "Enable point creation mode and click in the plot/map, or select a point first.",
            )
            return
        self._add_point_at_xy(target_xy)

    def on_page_changed(self, page: str):
        """Handle navigation page change."""
        dataset = self.get_active_dataset()
        if dataset is None or not hasattr(dataset, 'page_stack'):
            return

        page_map = {"plot": 0, "map": 1, "stats": 2}
        dataset.page_stack.setCurrentIndex(page_map.get(page, 0))

        if page == "map":
            self._update_map_view(force=True)
        elif page == "stats":
            dataset.statistics_panel.update_statistics(self)

    def on_open_file(self):
        """Handle file open action."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Data File", "",
            "Data Files (*.csv *.xlsx *.json);;All Files (*.*)"
        )
        if file_path:
            self.file_handler.load_file(file_path)

    def on_save(self):
        if self.data is None:
            QMessageBox.warning(self, "No Data", "No data to save.")
            return
        QMessageBox.information(self, "Save", "Save functionality coming soon.")

    def on_export(self):
        dataset = self.get_active_dataset()
        if dataset is None or self.data is None:
            QMessageBox.warning(self, "No Data", "No data to export.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Plot", "", "PNG Image (*.png);;PDF Document (*.pdf)"
        )
        if file_path:
            dataset.plot_page.export_plot(file_path)
            QMessageBox.information(self, "Export", f"Plot exported to {file_path}")

    def on_export_report(self):
        dataset = self.get_active_dataset()
        if dataset is None or self.data is None:
            QMessageBox.warning(self, "No Data", "No data to include in report.")
            return

        from ui.dialogs.report_generator import ReportSettingsDialog
        from ui.report_generator import PdfReportGenerator
        from PyQt5.QtWidgets import QProgressDialog, QApplication

        dialog = ReportSettingsDialog(self, parent=self)
        try:
            if dialog.exec_() != QDialog.Accepted:
                return
            settings = dialog.get_settings()
        finally:
            dialog.deleteLater()

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export PDF Report", "", "PDF Document (*.pdf)"
        )
        if not file_path:
            return

        progress = QProgressDialog("Generating report...", "Cancel", 0, 100, self)
        progress.setWindowTitle("Generating Report")
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)

        def _progress_cb(fraction, message):
            if message:
                progress.setLabelText(message)
            progress.setValue(int(max(0, min(1, fraction)) * 100))
            QApplication.processEvents()
            if progress.wasCanceled():
                raise RuntimeError("Report generation canceled.")

        try:
            generator = PdfReportGenerator(self)
            generator.generate(settings, file_path, _progress_cb)
            progress.setValue(100)
            QMessageBox.information(self, "Report Export", f"Report exported to {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Report Export Error", str(e))
        finally:
            progress.close()

    def on_settings(self):
        from .dialogs.plot_settings import PlotSettingsDialog
        dialog = PlotSettingsDialog(self, self.current_plot_type)
        try:
            if dialog.exec_():
                self.update_plot()
        finally:
            dialog.deleteLater()

    def on_calculation_settings(self):
        from .dialogs.calculation_settings import CalculationSettingsDialog
        dialog = CalculationSettingsDialog(self, parent=self)
        try:
            dialog.exec_()
        finally:
            dialog.deleteLater()

    def on_open_attribute_table(self):
        """Toggle the embedded attribute table panel below the plot."""
        dataset = self.get_active_dataset()
        if dataset is None or self.data is None:
            QMessageBox.information(self, "No Data", "No data to display. Load a file first.")
            return
        try:
            current_page = int(dataset.page_stack.currentIndex())
        except Exception:
            current_page = 0
        if current_page == 1 and hasattr(dataset, "map_widget"):
            dataset.map_widget.toggle_table_panel()
            return
        if current_page == 0 and hasattr(dataset, "plot_page"):
            dataset.plot_page.toggle_table_panel()
            return
        QMessageBox.information(self, "Table Panel", "Table panel is available on Plot and Map pages.")

    def on_reset(self):
        reply = QMessageBox.question(
            self, "Reset Application",
            "Are you sure you want to reset? All loaded data will be cleared.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self._reset_application()

    def on_help(self):
        """Open the Help & Documentation dialog."""
        # Deferred via QTimer so modal exec_() doesn't block when called
        # from a QWebChannel callback (e.g. welcome screen Help button).
        QTimer.singleShot(0, self._show_help_dialog)

    def _show_help_dialog(self):
        from .dialogs.help_dialog import HelpDialog
        dialog = HelpDialog(parent=self)
        try:
            dialog.exec_()
        finally:
            dialog.deleteLater()

    def on_contact(self):
        """Show contact information popup."""
        QMessageBox.information(
            self, "Contact",
            "<h3>HeadAnalyser V2</h3>"
            "<p><b>Author:</b> Oliver Lund</p>"
            "<p><b>Affiliation:</b> DTU — Technical University of Denmark</p>"
            "<p><b>Email:</b> <a href='mailto:ollun@dtu.dk'>ollun@dtu.dk</a></p>"
            "<p>For bug reports, feature requests, or questions about the "
            "software, please reach out via email.</p>"
        )

    def _reset_application(self):
        # Clear all datasets and tabs
        while self.dataset_tabs.count() > 0:
            self.dataset_tabs.removeTab(0)

        self.datasets.clear()
        self.active_dataset_id = None
        self.dataset_counter = 0

        # Reset legacy attributes
        self.sync_from_dataset(None)

        # Reset status
        self.status_file_label.setText("Ready")
        self.status_points_label.setText("")
        try:
            self.status_triangles_total_chip.setText("Total: -")
            self.status_triangles_valid_chip.setText("Valid: -")
            self.status_triangles_rejected_chip.setText("Rejected: -")
        except Exception:
            pass

        # Reset navigation
        self.nav_sidebar.set_active_page("plot")

        # Initial welcome state
        self._set_welcome_mode(True)

    def _set_welcome_mode(self, enabled: bool):
        """Toggle between full welcome screen and normal workspace."""
        if enabled:
            if self.welcome_widget is None:
                self._create_welcome_widget()
            if self.welcome_widget is not None:
                self.content_stack.setCurrentWidget(self.welcome_widget)
            else:
                self.content_stack.setCurrentWidget(self.dataset_tabs)
            self.nav_sidebar.hide()
            self.properties_panel.hide()
        else:
            self.content_stack.setCurrentWidget(self.dataset_tabs)
            self.nav_sidebar.show()
            self.properties_panel.show()
            # Free welcome screen resources while working with datasets.
            if self.welcome_widget is not None:
                self._destroy_welcome_widget()

    def on_plot_type_changed(self, plot_type):
        self.current_plot_type = normalize_plot_type(plot_type)
        self.update_plot()

    def on_filters_changed(self, filters):
        if self.data is None:
            return
        t0 = time.perf_counter()
        self._run_filter_pipeline(
            filters.get('depth_min'), filters.get('depth_max'),
            filters.get('head_min'), filters.get('head_max'),
            reason="filters_changed",
        )
        self._perf_log(f"[perf] filters apply (pre-gradient) elapsed={(time.perf_counter() - t0) * 1000.0:.1f}ms")

    def on_visualization_changed(self, settings):
        self.show_contours = settings.get('contours', self.show_contours)
        self.show_colorbar = settings.get('colorbar', self.show_colorbar)
        self.show_id_labels = settings.get('id_labels', self.show_id_labels)
        self.show_head_labels = settings.get('head_labels', self.show_head_labels)
        self.show_compass = settings.get('compass', self.show_compass)
        self.show_arrow = settings.get('arrow', self.show_arrow)
        self.show_arrow_label = settings.get('arrow_label', self.show_arrow_label)
        self.show_grid = settings.get('grid', self.show_grid)
        self.update_plot()

    def on_plot_options_changed(self, options):
        """Handle plot-specific option changes from sidebar."""
        non_label_changed = False
        prev_label_mode = self.label_mode_2d

        # 2D plot options
        new_colormap_2d = options.get('colormap_2d', self.colormap_2d)
        non_label_changed = non_label_changed or (new_colormap_2d != self.colormap_2d)
        self.colormap_2d = new_colormap_2d

        new_point_size = options.get('point_size', self.point_size)
        non_label_changed = non_label_changed or (new_point_size != self.point_size)
        self.point_size = new_point_size

        new_label_mode = str(options.get('label_mode_2d', self.label_mode_2d) or self.label_mode_2d).lower()
        if new_label_mode not in {"all", "smart", "off", "pinned"}:
            new_label_mode = "all"
        self.label_mode_2d = new_label_mode
        label_mode_changed = (self.label_mode_2d != prev_label_mode)

        # Contour plot options (merged into 2D)
        new_contour_levels = options.get('contour_levels', self.contour_levels)
        non_label_changed = non_label_changed or (new_contour_levels != self.contour_levels)
        self.contour_levels = new_contour_levels

        new_fill_contours = options.get('fill_contours', self.fill_contours)
        non_label_changed = non_label_changed or (new_fill_contours != self.fill_contours)
        self.fill_contours = new_fill_contours

        new_contour_extent = options.get('contour_extent_pct', self.contour_extent_pct)
        non_label_changed = non_label_changed or (new_contour_extent != self.contour_extent_pct)
        self.contour_extent_pct = new_contour_extent

        new_contour_extrap = options.get('contour_extrapolation', self.contour_extrapolation)
        non_label_changed = non_label_changed or (new_contour_extrap != self.contour_extrapolation)
        self.contour_extrapolation = new_contour_extrap

        # 3D plot options
        new_elev = options.get('elevation', self.elevation_3d)
        non_label_changed = non_label_changed or (new_elev != self.elevation_3d)
        self.elevation_3d = new_elev

        new_azim = options.get('azimuth', self.azimuth_3d)
        non_label_changed = non_label_changed or (new_azim != self.azimuth_3d)
        self.azimuth_3d = new_azim

        new_colormap_3d = options.get('colormap_3d', self.colormap_3d)
        non_label_changed = non_label_changed or (new_colormap_3d != self.colormap_3d)
        self.colormap_3d = new_colormap_3d

        # Vector plot options
        new_vector_scale = options.get('vector_scale', self.vector_scale)
        non_label_changed = non_label_changed or (new_vector_scale != self.vector_scale)
        self.vector_scale = new_vector_scale

        new_vector_alpha = options.get('vector_alpha', self.vector_alpha)
        non_label_changed = non_label_changed or (new_vector_alpha != self.vector_alpha)
        self.vector_alpha = new_vector_alpha

        new_colormap_vectors = options.get('colormap_vectors', self.colormap_vectors)
        non_label_changed = non_label_changed or (new_colormap_vectors != self.colormap_vectors)
        self.colormap_vectors = new_colormap_vectors

        new_show_mean_vector = options.get('show_mean_vector', self.show_mean_vector)
        non_label_changed = non_label_changed or (new_show_mean_vector != self.show_mean_vector)
        self.show_mean_vector = new_show_mean_vector

        new_normalize_vectors = options.get('normalize_vectors', self.normalize_vectors)
        non_label_changed = non_label_changed or (new_normalize_vectors != self.normalize_vectors)
        self.normalize_vectors = new_normalize_vectors

        # Histogram options
        new_hist_bins = options.get('histogram_bins', self.histogram_bins)
        non_label_changed = non_label_changed or (new_hist_bins != self.histogram_bins)
        self.histogram_bins = new_hist_bins

        new_hist_bar = options.get('histogram_bar_color', self.histogram_bar_color)
        non_label_changed = non_label_changed or (new_hist_bar != self.histogram_bar_color)
        self.histogram_bar_color = new_hist_bar

        new_hist_edge = options.get('histogram_edge_color', self.histogram_edge_color)
        non_label_changed = non_label_changed or (new_hist_edge != self.histogram_edge_color)
        self.histogram_edge_color = new_hist_edge

        new_hist_mean = options.get('histogram_show_mean', self.histogram_show_mean)
        non_label_changed = non_label_changed or (new_hist_mean != self.histogram_show_mean)
        self.histogram_show_mean = new_hist_mean

        new_hist_median = options.get('histogram_show_median', self.histogram_show_median)
        non_label_changed = non_label_changed or (new_hist_median != self.histogram_show_median)
        self.histogram_show_median = new_hist_median

        new_hist_ci = options.get('histogram_show_ci', self.histogram_show_ci)
        non_label_changed = non_label_changed or (new_hist_ci != self.histogram_show_ci)
        self.histogram_show_ci = new_hist_ci

        new_hist_ci_level = options.get('histogram_ci_level', self.histogram_ci_level)
        non_label_changed = non_label_changed or (new_hist_ci_level != self.histogram_ci_level)
        self.histogram_ci_level = new_hist_ci_level

        # Rose diagram options
        new_rose_mode = options.get('rose_mode', self.rose_mode)
        non_label_changed = non_label_changed or (new_rose_mode != self.rose_mode)
        self.rose_mode = new_rose_mode

        new_rose_bins = options.get('rose_bins', self.rose_bins)
        non_label_changed = non_label_changed or (new_rose_bins != self.rose_bins)
        self.rose_bins = new_rose_bins

        new_rose_mean = options.get('rose_show_mean', self.rose_show_mean)
        non_label_changed = non_label_changed or (new_rose_mean != self.rose_show_mean)
        self.rose_show_mean = new_rose_mean

        new_rose_weighted = options.get('rose_show_weighted_mean', self.rose_show_weighted_mean)
        non_label_changed = non_label_changed or (new_rose_weighted != self.rose_show_weighted_mean)
        self.rose_show_weighted_mean = new_rose_weighted

        new_rose_ci = options.get('rose_show_ci', self.rose_show_ci)
        non_label_changed = non_label_changed or (new_rose_ci != self.rose_show_ci)
        self.rose_show_ci = new_rose_ci

        new_rose_ci_level = options.get('rose_ci_level', self.rose_ci_level)
        non_label_changed = non_label_changed or (new_rose_ci_level != self.rose_ci_level)
        self.rose_ci_level = new_rose_ci_level

        new_rose_color = options.get('rose_color', self.rose_color)
        non_label_changed = non_label_changed or (new_rose_color != self.rose_color)
        self.rose_color = new_rose_color

        new_hist_kde = options.get('histogram_show_kde', self.histogram_show_kde)
        non_label_changed = non_label_changed or (new_hist_kde != self.histogram_show_kde)
        self.histogram_show_kde = new_hist_kde

        new_rose_mean_resultant = options.get('rose_show_mean_resultant', self.rose_show_mean_resultant)
        non_label_changed = non_label_changed or (new_rose_mean_resultant != self.rose_show_mean_resultant)
        self.rose_show_mean_resultant = new_rose_mean_resultant

        new_rose_median = options.get('rose_show_median', self.rose_show_median)
        non_label_changed = non_label_changed or (new_rose_median != self.rose_show_median)
        self.rose_show_median = new_rose_median

        # Fast path: label-mode-only change on 2D plot.
        if label_mode_changed and not non_label_changed:
            if self._try_refresh_2d_labels_only():
                return

        # Fallback: full redraw.
        self.update_plot()

    def _try_refresh_2d_labels_only(self) -> bool:
        """Try a cheap label-only refresh for current 2D plot."""
        dataset = self.get_active_dataset()
        if dataset is None or not hasattr(dataset, "plot_page"):
            return False
        if self.current_plot_type != "2D":
            return False

        try:
            plot_widget = dataset.plot_page.plot_widget
        except Exception:
            return False

        if plot_widget is None or not hasattr(plot_widget, "refresh_2d_labels_only"):
            return False

        try:
            return bool(plot_widget.refresh_2d_labels_only())
        except Exception:
            return False

    def update_plot(self):
        dataset = self.get_active_dataset()
        if dataset is None or not hasattr(dataset, 'plot_page'):
            return
        if self.filtered_data is None and self.data is None:
            return
        if self.current_plot_type == "2D":
            data = self.filtered_plot_data if self.filtered_plot_data is not None else (
                self.filtered_data if self.filtered_data is not None else self.data
            )
        else:
            data = self.filtered_data if self.filtered_data is not None else self.data
        dataset.plot_page.update_plot(data, self.current_plot_type)

    @property
    def current_data(self):
        """Return the current raw data (before filtering)."""
        return self.data

    def update_status(self, file_name=None, num_points=None, num_triangles=None):
        if file_name:
            self.status_file_label.setText(f"Loaded: {file_name}")
        if num_points is not None:
            self.status_points_label.setText(f"Points: {num_points}")
        if num_triangles is not None:
            valid = int(num_triangles)
            total = getattr(self, "total_triangles", None)
            if not isinstance(total, numbers.Integral):
                # Fallback: compute total triangles from point count when possible.
                try:
                    n = int(num_points) if num_points is not None else 0
                    total = (n * (n - 1) * (n - 2)) // 6 if n >= 3 else 0
                except Exception:
                    total = None

            rejected = None
            try:
                if getattr(self, "rejected_data", None) is not None:
                    rejected = int(len(self.rejected_data))
            except Exception:
                rejected = None

            if rejected is None and isinstance(total, numbers.Integral):
                rejected = int(total) - int(valid)

            try:
                total_txt = str(int(total)) if isinstance(total, numbers.Integral) else "-"
                self.status_triangles_total_chip.setText(f"Total: {total_txt}")
                self.status_triangles_valid_chip.setText(f"Valid: {int(valid)}")
                self.status_triangles_rejected_chip.setText(
                    f"Rejected: {int(rejected)}" if rejected is not None else "Rejected: -"
                )
            except Exception:
                pass

        # Update gradient info
        if hasattr(self, 'status_gradient_label') and self.triangle_data is not None:
            try:
                gradients = self.triangle_data['gradient'].apply(
                    lambda g: g[0] if isinstance(g, (list, np.ndarray)) else g
                )
                avg_grad = gradients.mean()
                self.status_gradient_label.setText(f"Gradient: {avg_grad:.4f} m/m")
            except Exception:
                self.status_gradient_label.setText("")

    def update_data_views(self):
        dataset = self.get_active_dataset()
        if dataset is None or not hasattr(dataset, 'page_stack'):
            return
        if self.data is not None:
            table_bind_mode = "reset"
            # Avoid resetting table models on plain tab switches when data object is unchanged.
            # This prevents expensive downstream refreshes (notably triangle table rebuild/sort).
            table_data = None
            try:
                table_data = dataset.plot_page.data_table.model._data
            except Exception:
                table_data = None

            if table_data is self.data:
                table_bind_mode = "reuse"
                try:
                    dataset.plot_page._update_drawer_row_count()
                except Exception:
                    pass
            else:
                dataset.plot_page.set_data(self.data)
            current = dataset.page_stack.currentIndex()
            self._update_map_view(force=False)
            if current == 2:
                dataset.statistics_panel.update_statistics(self)
            try:
                self._perf_log(
                    f"[perf] data_views dataset={getattr(dataset, 'name', 'unknown')} "
                    f"table_bind={table_bind_mode} rows={len(self.data)} page={current}"
                )
            except Exception:
                pass

    # ========== Multi-Dataset Management ==========

    def get_active_dataset(self):
        """Get the currently active dataset object."""
        if self.active_dataset_id is not None and self.active_dataset_id in self.datasets:
            return self.datasets[self.active_dataset_id]
        return None

    def sync_from_dataset(self, dataset):
        """Load dataset state into legacy attributes for compatibility."""
        if dataset is None:
            # Clear legacy attributes
            self.data = None
            self.filtered_data = None
            self.filtered_plot_data = None
            self.triangle_data = None
            self.gradient_data = None
            self.rejected_data = None
            self.col_mapping = {'ID': None, 'x': None, 'y': None, 'hydraulic head': None}
            self.top_column = None
            self.bottom_column = None
            self.depth_column = None
            self.excluded_ids = set()
            self.excluded_member_keys = set()
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
            self.selected_triangle_indices = set()
            self.selection_meta = None
            self.show_triangle_selection_overlay = False
            self.total_triangles = None
            self.rejected_due_to_uncertainty = None
            self.rejected_due_to_triangle_quality = None
            self.rejected_due_to_calculation_failed = None
        else:
            # Load from dataset
            self.data = dataset.data
            self.filtered_data = dataset.filtered_data
            self.filtered_plot_data = getattr(dataset, "filtered_plot_data", dataset.filtered_data)
            self.triangle_data = dataset.triangle_data
            self.gradient_data = dataset.gradient_data
            self.rejected_data = dataset.rejected_data
            self.col_mapping = dataset.col_mapping
            self.top_column = dataset.top_column
            self.bottom_column = dataset.bottom_column
            self.depth_column = getattr(dataset, "depth_column", None)
            self.excluded_ids = dataset.excluded_ids
            self.excluded_member_keys = set(getattr(dataset, "excluded_member_keys", set()) or set())
            loaded_plot_type = getattr(dataset, "current_plot_type", "2D")
            self.current_plot_type = normalize_plot_type(loaded_plot_type)
            self.show_contours = dataset.show_contours
            self.show_colorbar = dataset.show_colorbar
            self.show_id_labels = dataset.show_id_labels
            self.show_head_labels = dataset.show_head_labels
            loaded_label_mode = str(getattr(dataset, "label_mode_2d", "all") or "all").lower()
            self.label_mode_2d = loaded_label_mode if loaded_label_mode in {"all", "smart", "off", "pinned"} else "all"
            self.show_excluded_points = bool(getattr(dataset, "show_excluded_points", True))
            self.custom_excluded_style = bool(getattr(dataset, "custom_excluded_style", False))
            self.excluded_marker = str(getattr(dataset, "excluded_marker", "x") or "x")
            self.excluded_color = str(getattr(dataset, "excluded_color", "#6a6a6a") or "#6a6a6a")
            try:
                self.excluded_opacity = float(getattr(dataset, "excluded_opacity", 0.3))
            except Exception:
                self.excluded_opacity = 0.3
            self.excluded_opacity = max(0.0, min(self.excluded_opacity, 1.0))
            try:
                self.excluded_size_scale = float(getattr(dataset, "excluded_size_scale", 0.75))
            except Exception:
                self.excluded_size_scale = 0.75
            if self.excluded_size_scale <= 0:
                self.excluded_size_scale = 0.75
            self.sync_xy_major_ticks = bool(getattr(dataset, "sync_xy_major_ticks", False))
            self.show_compass = dataset.show_compass
            self.show_arrow = dataset.show_arrow
            self.show_grid = dataset.show_grid
            self.selected_triangle_indices = set(getattr(dataset, "selected_triangle_indices", set()) or set())
            self.selection_meta = getattr(dataset, "selection_meta", None)
            self.show_triangle_selection_overlay = bool(getattr(dataset, "show_triangle_selection_overlay", False))
            self.gradient_head_uncertainty = getattr(dataset, "gradient_head_uncertainty", self.gradient_head_uncertainty)
            self.gradient_confidence_level = getattr(dataset, "gradient_confidence_level", self.gradient_confidence_level)
            self.gradient_base_height_low = getattr(dataset, "gradient_base_height_low", self.gradient_base_height_low)
            self.gradient_base_height_high = getattr(dataset, "gradient_base_height_high", self.gradient_base_height_high)
            self.gradient_max_base_or_height = getattr(dataset, "gradient_max_base_or_height", self.gradient_max_base_or_height)
            self.gradient_stacked_epsilon = getattr(dataset, "gradient_stacked_epsilon", self.gradient_stacked_epsilon)
            self.total_triangles = getattr(dataset, "total_triangles", None)
            self.rejected_due_to_uncertainty = getattr(dataset, "rejected_due_to_uncertainty", None)
            self.rejected_due_to_triangle_quality = getattr(dataset, "rejected_due_to_triangle_quality", None)
            self.rejected_due_to_calculation_failed = getattr(dataset, "rejected_due_to_calculation_failed", None)
            for attr in self._DATASET_EXTRA_OPTION_ATTRS:
                if hasattr(dataset, attr):
                    setattr(self, attr, getattr(dataset, attr))

        self._sync_point_creation_mode_ui()

    def sync_to_dataset(self, dataset):
        """Save current legacy attributes back to dataset."""
        if dataset is None:
            return
        dataset.data = self.data
        dataset.filtered_data = self.filtered_data
        dataset.filtered_plot_data = self.filtered_plot_data
        dataset.triangle_data = self.triangle_data
        dataset.gradient_data = self.gradient_data
        dataset.rejected_data = self.rejected_data
        dataset.col_mapping = self.col_mapping
        dataset.top_column = self.top_column
        dataset.bottom_column = self.bottom_column
        dataset.depth_column = getattr(self, "depth_column", None)
        dataset.excluded_ids = self.excluded_ids
        dataset.excluded_member_keys = set(getattr(self, "excluded_member_keys", set()) or set())
        dataset.current_plot_type = self.current_plot_type
        dataset.show_contours = self.show_contours
        dataset.show_colorbar = self.show_colorbar
        dataset.show_id_labels = self.show_id_labels
        dataset.show_head_labels = self.show_head_labels
        dataset.label_mode_2d = self.label_mode_2d
        dataset.show_excluded_points = bool(self.show_excluded_points)
        dataset.custom_excluded_style = bool(self.custom_excluded_style)
        dataset.excluded_marker = str(self.excluded_marker)
        dataset.excluded_color = str(self.excluded_color)
        dataset.excluded_opacity = float(self.excluded_opacity)
        dataset.excluded_size_scale = float(self.excluded_size_scale)
        dataset.sync_xy_major_ticks = bool(self.sync_xy_major_ticks)
        dataset.show_compass = self.show_compass
        dataset.show_arrow = self.show_arrow
        dataset.show_grid = self.show_grid
        dataset.selected_triangle_indices = set(self.selected_triangle_indices or set())
        dataset.selection_meta = self.selection_meta
        dataset.show_triangle_selection_overlay = bool(self.show_triangle_selection_overlay)
        dataset.gradient_head_uncertainty = self.gradient_head_uncertainty
        dataset.gradient_confidence_level = self.gradient_confidence_level
        dataset.gradient_base_height_low = self.gradient_base_height_low
        dataset.gradient_base_height_high = self.gradient_base_height_high
        dataset.gradient_max_base_or_height = self.gradient_max_base_or_height
        dataset.gradient_stacked_epsilon = self.gradient_stacked_epsilon
        dataset.total_triangles = getattr(self, "total_triangles", None)
        dataset.rejected_due_to_uncertainty = getattr(self, "rejected_due_to_uncertainty", None)
        dataset.rejected_due_to_triangle_quality = getattr(self, "rejected_due_to_triangle_quality", None)
        dataset.rejected_due_to_calculation_failed = getattr(self, "rejected_due_to_calculation_failed", None)
        for attr in self._DATASET_EXTRA_OPTION_ATTRS:
            setattr(dataset, attr, getattr(self, attr, None))

        # Persist active filter sliders per dataset so tab switches keep correct ranges and values.
        try:
            if dataset is self.get_active_dataset() and hasattr(self, "properties_panel"):
                depth_bounds = tuple(self.properties_panel.depth_range.get_bounds())
                head_bounds = tuple(self.properties_panel.head_range.get_bounds())
                depth_values = tuple(self.properties_panel.depth_range.get_values())
                head_values = tuple(self.properties_panel.head_range.get_values())
                dataset.depth_bounds = depth_bounds
                dataset.head_bounds = head_bounds
                dataset.depth_range = depth_values
                dataset.head_range = head_values
        except Exception:
            pass

    def _sidebar_settings_for_active_state(self) -> dict:
        return {
            'show_contours': bool(self.show_contours),
            'show_arrow': bool(self.show_arrow),
            'show_colorbar': bool(self.show_colorbar),
            'show_id_labels': bool(self.show_id_labels),
            'show_head_labels': bool(self.show_head_labels),
            'label_mode_2d': str(self.label_mode_2d),
            'colormap_2d': self.colormap_2d,
            'point_size': self.point_size,
            'contour_levels': self.contour_levels,
            'fill_contours': self.fill_contours,
            'elevation_3d': self.elevation_3d,
            'azimuth_3d': self.azimuth_3d,
            'colormap_3d': self.colormap_3d,
            'vector_scale': self.vector_scale,
            'vector_alpha': self.vector_alpha,
            'colormap_vectors': self.colormap_vectors,
            'show_mean_vector': self.show_mean_vector,
            'normalize_vectors': self.normalize_vectors,
            'histogram_bins': self.histogram_bins,
            'histogram_bar_color': self.histogram_bar_color,
            'histogram_edge_color': self.histogram_edge_color,
            'histogram_show_mean': self.histogram_show_mean,
            'histogram_show_median': self.histogram_show_median,
            'histogram_show_ci': self.histogram_show_ci,
            'histogram_ci_level': self.histogram_ci_level,
            'rose_mode': self.rose_mode,
            'rose_bins': self.rose_bins,
            'rose_show_mean': self.rose_show_mean,
            'rose_show_weighted_mean': self.rose_show_weighted_mean,
            'rose_show_ci': self.rose_show_ci,
            'rose_ci_level': self.rose_ci_level,
            'rose_color': self.rose_color,
        }

    def _sync_active_sidebar_from_state(self):
        dataset = self.get_active_dataset()
        if dataset is None or not hasattr(dataset, "plot_page"):
            return
        combo = getattr(dataset.plot_page, "plot_type_combo", None)
        try:
            if combo is not None:
                combo.blockSignals(True)
                combo.setCurrentText(to_toolbar_label(self.current_plot_type))
            dataset.plot_page.plot_sidebar.update_from_settings(self._sidebar_settings_for_active_state())
            dataset.plot_page.plot_sidebar.set_plot_type(self.current_plot_type)
            dataset.plot_page.plot_widget.set_hint_plot_type(self.current_plot_type)
        except Exception:
            pass
        finally:
            if combo is not None:
                try:
                    combo.blockSignals(False)
                except Exception:
                    pass

    def create_new_dataset_tab(self, dataset_name=None, file_path=None):
        """Create a new tab for a dataset."""
        # Prevent on_tab_changed from running during creation
        self._creating_tab = True

        # Generate dataset ID
        dataset_id = f"dataset_{self.dataset_counter}"
        self.dataset_counter += 1

        # Create dataset object
        if dataset_name is None:
            dataset_name = f"Dataset {self.dataset_counter}"
        dataset = Dataset(name=dataset_name)
        dataset.file_path = file_path
        for k, v in (self.default_gradient_settings or {}).items():
            if hasattr(dataset, k):
                setattr(dataset, k, v)
        self.datasets[dataset_id] = dataset

        # Create page stack for this dataset
        page_stack = QStackedWidget()
        page_stack.setStyleSheet(f"background-color: {Colors.BG_PANEL};")

        # Create pages for this dataset
        plot_page = PlotPage(self)
        map_widget = MapWidget(self)
        statistics_panel = StatisticsPanel(self)

        # Connect statistics panel buttons
        statistics_panel.open_inspector_requested.connect(
            lambda: self._on_stats_inspect_clicked(statistics_panel)
        )
        statistics_panel.export_requested.connect(
            lambda: self._on_stats_export_clicked(statistics_panel)
        )

        # Connect plot page signals
        plot_page.plot_type_changed.connect(self.on_plot_type_changed)
        plot_page.plot_sidebar.visualization_changed.connect(self.on_visualization_changed)
        plot_page.plot_sidebar.plot_options_changed.connect(self.on_plot_options_changed)
        plot_page.plot_widget.point_selected.connect(self._on_plot_point_selected)
        plot_page.plot_widget.point_coordinate_clicked.connect(self._on_plot_coordinate_clicked)
        plot_page.plot_widget.geodk_transect_requested.connect(self._on_plot_geodk_transect_requested)
        plot_page.data_table.row_selected.connect(self._on_table_row_selected)
        plot_page.data_table.rows_selected.connect(self._on_table_rows_selected)
        plot_page.data_table.row_deselected.connect(self._on_table_row_deselected)
        map_widget.pointSelected.connect(self._on_map_point_selected)
        map_widget.pointDeselected.connect(self._on_map_point_deselected)
        map_widget.pointExcludeRequested.connect(self._on_map_exclude_requested)
        map_widget.pointShowInPlotRequested.connect(self._on_map_show_in_plot_requested)
        map_widget.contourSettingsRequested.connect(self._on_map_contour_settings_requested)
        map_widget.mapLocationClicked.connect(self._on_map_location_clicked)
        map_widget.addPointModeChanged.connect(self.set_point_creation_mode)
        map_widget.transectCreated.connect(self._on_map_transect_created)
        map_widget.geodkFetchRequested.connect(self._on_map_geodk_fetch_requested)
        map_widget.geodkCredentialsRequested.connect(self._on_map_geodk_credentials_requested)
        map_widget.geodkDownloadRequested.connect(self._on_map_geodk_download_requested)
        map_widget.geodkCopyReproRequested.connect(self._on_map_geodk_copy_repro_requested)

        # Sync initial plot settings to sidebar from this dataset's defaults.
        initial_settings = {
            'show_contours': bool(dataset.show_contours),
            'show_arrow': bool(dataset.show_arrow),
            'show_colorbar': bool(dataset.show_colorbar),
            'show_id_labels': bool(dataset.show_id_labels),
            'show_head_labels': bool(dataset.show_head_labels),
            'label_mode_2d': str(dataset.label_mode_2d),
            'colormap_2d': dataset.colormap_2d,
            'point_size': dataset.point_size,
            'contour_levels': dataset.contour_levels,
            'fill_contours': dataset.fill_contours,
            'elevation_3d': dataset.elevation_3d,
            'azimuth_3d': dataset.azimuth_3d,
            'colormap_3d': dataset.colormap_3d,
            'vector_scale': dataset.vector_scale,
            'vector_alpha': dataset.vector_alpha,
            'colormap_vectors': dataset.colormap_vectors,
            'histogram_bins': dataset.histogram_bins,
            'histogram_bar_color': dataset.histogram_bar_color,
            'histogram_edge_color': dataset.histogram_edge_color,
            'histogram_show_mean': dataset.histogram_show_mean,
            'histogram_show_median': dataset.histogram_show_median,
            'histogram_show_ci': dataset.histogram_show_ci,
            'histogram_ci_level': dataset.histogram_ci_level,
            'rose_mode': dataset.rose_mode,
            'rose_bins': dataset.rose_bins,
            'rose_show_mean': dataset.rose_show_mean,
            'rose_show_weighted_mean': dataset.rose_show_weighted_mean,
            'rose_show_ci': dataset.rose_show_ci,
            'rose_ci_level': dataset.rose_ci_level,
            'rose_color': dataset.rose_color,
        }
        plot_page.plot_sidebar.update_from_settings(initial_settings)

        page_stack.addWidget(plot_page)
        page_stack.addWidget(map_widget)
        page_stack.addWidget(statistics_panel)

        # Store references in dataset for later access
        dataset.plot_page = plot_page
        dataset.map_widget = map_widget
        dataset.statistics_panel = statistics_panel
        dataset.page_stack = page_stack
        # Allow PlotWidget to tag emitted transects with this dataset context.
        try:
            plot_page.plot_widget._dataset_id = str(dataset_id)
        except Exception:
            pass

        # Add tab
        tab_index = self.dataset_tabs.addTab(page_stack, dataset_name)
        try:
            self.dataset_tabs.tabBar().setTabData(tab_index, dataset_id)
        except Exception:
            pass
        self.dataset_tabs.setCurrentIndex(tab_index)
        self._install_dataset_close_button(tab_index)

        # Switch stack to tabs view
        self._set_welcome_mode(False)

        # Set as active dataset (don't sync from dataset here - caller will set data)
        self.active_dataset_id = dataset_id

        # Re-enable on_tab_changed
        self._creating_tab = False

        return dataset_id

    def _install_dataset_close_button(self, tab_index: int):
        """Install a compact visible close button (×) for dataset tabs."""
        try:
            bar = self.dataset_tabs.tabBar()
            btn = QToolButton(self.dataset_tabs)
            btn.setObjectName("datasetTabCloseButton")
            btn.setText("\u00D7")
            btn.setCursor(Qt.PointingHandCursor)
            btn.setAutoRaise(True)
            btn.setToolTip("Close dataset")
            btn.setFixedSize(16, 16)
            btn.clicked.connect(self._close_dataset_from_button)
            bar.setTabButton(tab_index, QTabBar.RightSide, btn)
        except Exception:
            pass

    def _close_dataset_from_button(self):
        """Close the dataset tab associated with the clicked close button."""
        try:
            sender = self.sender()
            bar = self.dataset_tabs.tabBar()
            for i in range(bar.count()):
                if bar.tabButton(i, QTabBar.RightSide) is sender:
                    self.close_dataset_tab(i)
                    return
        except Exception:
            pass

    def close_dataset_tab(self, index):
        """Close a dataset tab."""
        if self.dataset_tabs.count() == 0:
            return

        # Find dataset_id for this tab
        dataset_id = None
        try:
            dataset_id = self.dataset_tabs.tabBar().tabData(index)
        except Exception:
            dataset_id = None
        if dataset_id is not None:
            dataset_id = str(dataset_id)

        if dataset_id is None:
            # Fallback for older tabs that may not have tab data.
            tab_count = 0
            for did, _dataset in self.datasets.items():
                if tab_count == index:
                    dataset_id = did
                    break
                tab_count += 1

        if dataset_id is None:
            return

        # Remove tab
        self.dataset_tabs.removeTab(index)

        # Remove dataset
        if dataset_id in self.datasets:
            del self.datasets[dataset_id]

        # Update active dataset
        if dataset_id == self.active_dataset_id:
            if self.dataset_tabs.count() > 0:
                # Switch to another tab
                self.active_dataset_id = list(self.datasets.keys())[0] if self.datasets else None
                self.sync_from_dataset(self.get_active_dataset())
            else:
                # No tabs left - show welcome screen
                self.active_dataset_id = None
                self.sync_from_dataset(None)
                self._set_welcome_mode(True)

        # Update UI
        self.update_all_views()

    def on_tab_changed(self, index):
        """Handle tab change - sync to new active dataset."""
        t0 = time.perf_counter()
        # Skip during tab creation to avoid overwriting data
        if self._creating_tab:
            return

        if index < 0 or self.dataset_tabs.count() == 0:
            self.active_dataset_id = None
            self.sync_from_dataset(None)
            return

        # Save current dataset state before switching
        current_dataset = self.get_active_dataset()
        if current_dataset is not None:
            self.sync_to_dataset(current_dataset)

        # Find new dataset_id
        dataset = None
        dataset_id = None
        try:
            dataset_id = self.dataset_tabs.tabBar().tabData(index)
        except Exception:
            dataset_id = None
        if dataset_id is not None:
            dataset_id = str(dataset_id)
            dataset = self.datasets.get(dataset_id)
        if dataset is None:
            # Fallback for older tabs that may not have tab data.
            tab_count = 0
            for did, ds in self.datasets.items():
                if tab_count == index:
                    dataset_id = did
                    dataset = ds
                    break
                tab_count += 1
        if dataset is None:
            return

        self.active_dataset_id = dataset_id
        self.sync_from_dataset(dataset)

        # Update navigation to show correct page for this dataset's view
        current_page = dataset.page_stack.currentIndex()
        self.nav_sidebar.set_active_page(["plot", "map", "stats"][current_page])

        # Update properties panel to reflect this dataset's settings
        self.properties_panel.update_from_main_window()
        self._sync_active_sidebar_from_state()

        # Update views
        self.update_all_views()
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        ds = self.get_active_dataset()
        self._perf_log(
            f"[perf] tab switch index={index} dataset={getattr(ds, 'name', 'none')} elapsed={elapsed_ms:.1f}ms"
        )

    def update_all_views(self):
        """Update all views for current dataset."""
        t0 = time.perf_counter()
        dataset = self.get_active_dataset()
        if dataset is None or not dataset.has_data():
            self.update_status(None, 0, 0)
            return

        # Update plot
        self.update_plot()

        # Update data views
        self.update_data_views()

        # Update status
        self.update_status(
            dataset.name,
            dataset.get_point_count(),
            dataset.get_triangle_count()
        )

        # Refresh Triangle Inspector if it is currently visible
        try:
            self._update_triangle_inspector()
        except Exception:
            pass
        self._perf_log(
            f"[perf] update_all_views dataset={getattr(dataset, 'name', 'unknown')} "
            f"elapsed={(time.perf_counter() - t0) * 1000.0:.1f}ms"
        )

    def on_table_data_change(self):
        """Handle data table edits - recalculate and update everything."""
        dataset = self.get_active_dataset()
        if dataset is None or self.data is None:
            return

        # Get updated data from table model
        if hasattr(dataset, 'plot_page') and hasattr(dataset.plot_page, 'data_table'):
            self.data = dataset.plot_page.data_table.model._data
            dataset.data = self.data

        # Reapply filters using the centralized pipeline.
        refilter_ok = False
        try:
            depth_min, depth_max, head_min, head_max = self.get_current_filter_values()
            self._run_filter_pipeline(
                depth_min, depth_max, head_min, head_max, reason="table_data_change"
            )
            refilter_ok = True
        except Exception:
            # If filters fail, just use the updated data as-is
            self.filtered_data = self.data
            self.filtered_plot_data = self.data
            dataset.filtered_data = self.data
            dataset.filtered_plot_data = self.data

        # Recalculate gradients only if the standard filter path failed.
        if (not refilter_ok) and hasattr(self, 'gradient_calculator') and self.filtered_data is not None:
            try:
                self.dataset_name = str(getattr(dataset, "name", "active"))
                self._calc_reason = "table_data_change"
                self.triangle_data = self.gradient_calculator.create_gradient_dataframe(self.filtered_data)
                dataset.triangle_data = self.triangle_data
            except Exception:
                pass

        # Sync back to dataset
        self.sync_to_dataset(dataset)

        # Update the plot and views
        self.update_plot()
        self.update_data_views()

        # Update statistics if on stats page
        if hasattr(dataset, 'page_stack'):
            current = dataset.page_stack.currentIndex()
            if current == 2:
                dataset.statistics_panel.update_statistics(self)

    def closeEvent(self, event):
        try:
            if self._gradient_poll_timer.isActive():
                self._gradient_poll_timer.stop()
        except Exception:
            pass
        try:
            self._gradient_executor.shutdown(wait=False, cancel_futures=True)
        except Exception:
            pass
        super().closeEvent(event)
