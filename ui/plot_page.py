"""
HeadAnalyser V2 - Plot Page
Contains the main plot widget with optional data table below,
redesigned compact 40px toolbar, animated sidebar, and Data/Triangles
toggle in the drawer.
"""

import os
import time
from collections import Counter
import numpy as np

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QComboBox, QPushButton, QToolButton, QSizePolicy, QStackedWidget,
    QButtonGroup,
)
from PyQt5.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve, QEvent, QTimer, QAbstractAnimation, QPoint, QRectF, QSize
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QColor, QPen

from .plot_widget import PlotWidget
from .grid_plot_area import GridPlotArea
from .data_table import DataTableWidget
from .plot_sidebar import PlotSidebar
from .plot_quick_stats_b import PlotQuickStatsPanel
from .plot_types import TOOLBAR_PLOT_LABELS, normalize_plot_type, to_toolbar_label
from .icons import Icons, icon
from styles.colors import Colors
from styles.stylesheet import StyleSheet
from ui.scaling import build_screen_metrics


class PlotPage(QWidget):
    """Page containing the plot and optional data table below."""

    # Signals
    plot_type_changed = pyqtSignal(str)

    _PROFILE_EVENTS = {
        QEvent.Paint: "Paint",
        QEvent.Resize: "Resize",
        QEvent.LayoutRequest: "LayoutRequest",
        QEvent.UpdateRequest: "UpdateRequest",
        QEvent.HoverMove: "HoverMove",
        QEvent.MouseMove: "MouseMove",
        QEvent.Wheel: "Wheel",
        QEvent.Enter: "Enter",
        QEvent.Leave: "Leave",
    }

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        metrics = build_screen_metrics(main_window)
        self.main_window = main_window
        self.setStyleSheet(f"background-color: {Colors.BG_PANEL};")
        self.sidebar_visible = False
        self._sidebar_anim = None
        self._triangle_table = None  # Lazy-created
        self._toolbar = None
        self._sidebar_anim_started_at = None
        self._sidebar_anim_target = None
        self._sidebar_width = metrics.plot_sidebar_width
        self._plot_column = None
        self._plot_column_layout = None
        self._table_drawer_open = False
        self._quick_stats_drawer_open = False
        self._table_drawer_height = 0
        self._quick_stats_drawer_height = 0
        self._table_anim_target_open = False
        self._quick_stats_anim_target_open = False
        self._triangle_table_loading = False
        try:
            self._triangle_table_max_rows = int(os.getenv("HEADANALYSER_TRIANGLE_TABLE_MAX_ROWS", "0"))
            if self._triangle_table_max_rows < 0:
                self._triangle_table_max_rows = 0
        except Exception:
            self._triangle_table_max_rows = 0
        try:
            self._triangle_overlay_cap = max(
                1, int(os.getenv("HEADANALYSER_TRIANGLE_OVERLAY_CAP", "300"))
            )
        except Exception:
            self._triangle_overlay_cap = 300
        try:
            self._triangle_overlay_debounce_ms = max(
                0, int(os.getenv("HEADANALYSER_TRIANGLE_OVERLAY_DEBOUNCE_MS", "35"))
            )
        except Exception:
            self._triangle_overlay_debounce_ms = 35
        self._pending_triangle_indices = []
        self._triangle_overlay_timer = None

        # Optional lightweight profiler for plot page responsiveness debugging.
        self._perf_enabled = str(os.getenv("HEADANALYSER_PROFILE_PLOT_PAGE", "")).strip().lower() in {
            "1", "true", "yes", "on"
        }
        self._perf_started = time.perf_counter()
        self._perf_event_counts = Counter()
        self._perf_method_stats = {}
        self._perf_watch_alias = {}
        self._perf_dump_timer = None
        self._perf_log_path = os.getenv("HEADANALYSER_PROFILE_PLOT_PAGE_LOG", "plot_page_profile.log")

        self._setup_ui()
        self._connect_selection_sync()
        self._init_plot_profiler()

    def _setup_ui(self):
        metrics = build_screen_metrics(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Add compact toolbar
        toolbar = self._create_plot_toolbar()
        self._toolbar = toolbar
        layout.addWidget(toolbar)

        # Horizontal layout for plot area
        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # Plot column (plot + optional bottom drawers)
        plot_column = QWidget()
        self._plot_column = plot_column
        plot_column_layout = QVBoxLayout(plot_column)
        self._plot_column_layout = plot_column_layout
        plot_column_layout.setContentsMargins(0, 0, 0, 0)
        plot_column_layout.setSpacing(0)

        # Grid plot area — wraps primary PlotWidget; supports 1-4 cell layouts
        _primary_pw = PlotWidget(self.main_window)
        self._grid_area = GridPlotArea(self.main_window, _primary_pw)
        # Lazily-created cells inherit page-level state (dataset_id, etc.).
        self._grid_area._on_new_plot_widget = self._init_new_plot_widget
        self._grid_area.save_active_cell_state.connect(self._on_save_cell_state)
        self._grid_area.active_cell_changed.connect(self._on_active_cell_changed)
        plot_column_layout.addWidget(self._grid_area, 1)

        # Bottom quick stats drawer (collapsed by default)
        self.quick_stats_panel = PlotQuickStatsPanel(self.main_window)
        self.quick_stats_container = QWidget(plot_column)
        self.quick_stats_container.setObjectName("quickStatsContainer")
        self.quick_stats_container.setAttribute(Qt.WA_StyledBackground, True)
        self.quick_stats_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.quick_stats_container.hide()

        qs_layout = QVBoxLayout(self.quick_stats_container)
        qs_layout.setContentsMargins(0, 0, 0, 0)
        qs_layout.setSpacing(0)
        qs_layout.addWidget(self.quick_stats_panel)

        # Bottom data table drawer (collapsed by default)
        self.data_table = DataTableWidget(self.main_window)
        self.data_table.set_main_window(self.main_window)

        self.table_container = QWidget(plot_column)
        self.table_container.setObjectName("tableContainer")
        self.table_container.setAttribute(Qt.WA_StyledBackground, True)
        self.table_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.table_container.hide()
        self.table_container.setStyleSheet(f"""
            QWidget#tableContainer {{
                border-top: 1px solid {Colors.BORDER_DEFAULT};
            }}
        """)

        tc_layout = QVBoxLayout(self.table_container)
        tc_layout.setContentsMargins(0, 0, 0, 0)
        tc_layout.setSpacing(0)

        # ── Drawer header bar ──
        drawer_header = QWidget()
        drawer_header.setObjectName("drawerHeader")
        drawer_header.setFixedHeight(metrics.drawer_header_height)
        drawer_header.setStyleSheet(StyleSheet.get_drawer_header_style())
        self.drawer_header = drawer_header
        dh_layout = QHBoxLayout(drawer_header)
        dh_layout.setContentsMargins(10 if metrics.compact else 12, 0, 10 if metrics.compact else 12, 0)
        dh_layout.setSpacing(5 if metrics.compact else 6)

        # Data / Triangles toggle
        self._drawer_mode_group = QButtonGroup(self)
        self._drawer_mode_group.setExclusive(True)

        self._data_mode_btn = QPushButton("Data")
        self._data_mode_btn.setCheckable(True)
        self._data_mode_btn.setChecked(True)
        self._data_mode_btn.setCursor(Qt.PointingHandCursor)
        self._data_mode_btn.setFixedHeight(max(20, metrics.toolbar_pill_height - 2))

        self._tri_mode_btn = QPushButton("Triangles")
        self._tri_mode_btn.setCheckable(True)
        self._tri_mode_btn.setCursor(Qt.PointingHandCursor)
        self._tri_mode_btn.setFixedHeight(max(20, metrics.toolbar_pill_height - 2))

        for btn in (self._data_mode_btn, self._tri_mode_btn):
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    border: 1px solid transparent;
                    border-radius: 4px;
                    padding: 0 10px;
                    font-size: 10px;
                    font-weight: 600;
                    color: {Colors.TEXT_TERTIARY};
                }}
                QPushButton:hover {{
                    color: {Colors.TEXT_SECONDARY};
                    background-color: {Colors.BG_HOVER};
                }}
                QPushButton:checked {{
                    background-color: {Colors.BG_SURFACE};
                    color: {Colors.TEXT_PRIMARY};
                    border-color: {Colors.BORDER_MEDIUM};
                }}
            """)

        self._drawer_mode_group.addButton(self._data_mode_btn, 0)
        self._drawer_mode_group.addButton(self._tri_mode_btn, 1)
        self._drawer_mode_group.idClicked.connect(self._on_drawer_mode_changed)

        dh_layout.addWidget(self._data_mode_btn)
        dh_layout.addWidget(self._tri_mode_btn)

        # Centered drag pill (cosmetic)
        dh_layout.addStretch()

        drag_pill = QFrame()
        drag_pill.setFixedSize(28 if metrics.compact else 32, 4)
        drag_pill.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.BORDER_STRONG};
                border-radius: 2px;
                border: none;
            }}
        """)
        self.drawer_drag_pill = drag_pill
        dh_layout.addWidget(drag_pill)

        dh_layout.addStretch()

        # Row count chip in drawer header
        self.drawer_row_count = QLabel("0 rows")
        self.drawer_row_count.setStyleSheet(f"""
            QLabel {{
                color: {Colors.TEXT_TERTIARY};
                font-size: 10px;
                font-weight: 600;
                padding: 2px 9px;
                background-color: {Colors.BG_SURFACE};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 100px;
                letter-spacing: 0.2px;
            }}
        """)
        dh_layout.addWidget(self.drawer_row_count)

        # Performance notice chip for large triangle overlay selections.
        self.drawer_perf_notice = QLabel("")
        self.drawer_perf_notice.setVisible(False)
        self.drawer_perf_notice.setStyleSheet(f"""
            QLabel {{
                color: {Colors.WARNING};
                font-size: 10px;
                font-weight: 700;
                padding: 2px 8px;
                background-color: {Colors.BG_SURFACE};
                border: 1px solid {Colors.WARNING};
                border-radius: 100px;
            }}
        """)
        dh_layout.addWidget(self.drawer_perf_notice)

        tc_layout.addWidget(drawer_header)

        # Stacked widget for Data / Triangles
        self._drawer_stack = QStackedWidget()
        self._drawer_stack.addWidget(self.data_table)  # index 0
        # Triangle table added lazily in _ensure_triangle_table()
        tc_layout.addWidget(self._drawer_stack)

        content_layout.addWidget(plot_column, 1)

        layout.addLayout(content_layout, 1)

        self._quick_stats_anim = None
        self._table_anim = None
        self._sync_bottom_drawer_overlay_geometry(force_targets=False)

        # Overlay sidebar: animate position instead of width so the heavy plot
        # area does not relayout on every frame.
        self.plot_sidebar = PlotSidebar(plot_page_ref=self, parent=plot_column)
        self.plot_sidebar.setFixedWidth(int(self._sidebar_width))
        self.plot_sidebar.hide()
        self._sync_sidebar_overlay_geometry(x=-int(self._sidebar_width))
        self.plot_sidebar.raise_()

        self._triangle_overlay_timer = QTimer(self)
        self._triangle_overlay_timer.setSingleShot(True)
        self._triangle_overlay_timer.setInterval(self._triangle_overlay_debounce_ms)
        self._triangle_overlay_timer.timeout.connect(self._flush_triangle_selection_overlay)

        # Connect Sidebar -> Page
        self.plot_sidebar.visualization_changed.connect(self._on_visualization_changed)

    # Names of plot-widget signals that need to follow the active cell.
    # Routed to main_window handlers (set up by create_new_dataset_tab).
    _MW_FORWARDED_SIGNALS = (
        ("point_selected",            "_on_plot_point_selected"),
        ("point_coordinate_clicked",  "_on_plot_coordinate_clicked"),
        ("geodk_transect_requested",  "_on_plot_geodk_transect_requested"),
    )

    def _connect_selection_sync(self):
        """Wire bidirectional selection between the active plot cell and the table/main window."""
        self._sync_bound_pw = None
        self._mw_bound_pw = None
        self._rebind_table_to_active_cell()
        # Triangle inspector binding lives on the page, not the plot widget — once.
        self.data_table.inspect_requested.connect(self._on_inspect_requested)

    def _rebind_table_to_active_cell(self):
        """Move data_table↔plot AND main_window↔plot connections to the current active cell."""
        new_pw = self.plot_widget
        mw = self.main_window

        # ── Table ↔ plot ──────────────────────────────────────────────
        old_pw = getattr(self, "_sync_bound_pw", None)
        if old_pw is not new_pw:
            if old_pw is not None:
                try: old_pw.points_selected.disconnect(self.data_table.highlight_rows_by_ids)
                except (TypeError, RuntimeError): pass
                try: old_pw.point_deselected.disconnect(self.data_table.clear_highlight)
                except (TypeError, RuntimeError): pass
                try: self.data_table.row_selected.disconnect(old_pw.highlight_point_by_id)
                except (TypeError, RuntimeError): pass
                try: self.data_table.row_deselected.disconnect(old_pw.clear_point_highlight)
                except (TypeError, RuntimeError): pass
                try: self.data_table.rows_selected_member_keys.disconnect(old_pw.highlight_points_by_ids)
                except (TypeError, RuntimeError): pass
            new_pw.points_selected.connect(self.data_table.highlight_rows_by_ids)
            new_pw.point_deselected.connect(self.data_table.clear_highlight)
            self.data_table.row_selected.connect(new_pw.highlight_point_by_id)
            self.data_table.row_deselected.connect(new_pw.clear_point_highlight)
            self.data_table.rows_selected_member_keys.connect(new_pw.highlight_points_by_ids)
            self._sync_bound_pw = new_pw

        # ── main_window ↔ plot ───────────────────────────────────────
        # main_window connects these signals only once (in create_new_dataset_tab)
        # to whatever plot_widget returns at that moment (cell 0). We rebind here
        # so clicking points in any cell routes through main_window's handlers.
        old_mw_pw = getattr(self, "_mw_bound_pw", None)
        if old_mw_pw is not new_pw:
            for sig_name, handler_name in self._MW_FORWARDED_SIGNALS:
                handler = getattr(mw, handler_name, None)
                if handler is None:
                    continue
                if old_mw_pw is not None:
                    sig = getattr(old_mw_pw, sig_name, None)
                    if sig is not None:
                        try: sig.disconnect(handler)
                        except (TypeError, RuntimeError): pass
                sig = getattr(new_pw, sig_name, None)
                if sig is not None:
                    try: sig.connect(handler)
                    except (TypeError, RuntimeError): pass
            # Carry over the dataset_id tag so GeoDK transects emit with the right dataset.
            if old_mw_pw is not None and hasattr(old_mw_pw, "_dataset_id"):
                try: new_pw._dataset_id = old_mw_pw._dataset_id
                except Exception: pass
            self._mw_bound_pw = new_pw

    def _init_plot_profiler(self):
        if not self._perf_enabled:
            return

        self._register_perf_widget(self, "plot_page")
        self._register_perf_widget(self._toolbar, "toolbar")
        self._register_perf_widget(self.plot_sidebar, "sidebar")
        self._register_perf_widget(self.table_container, "table_drawer")
        self._register_perf_widget(self.quick_stats_container, "stats_drawer")
        self._register_perf_widget(self.plot_widget, "plot_widget")

        try:
            self._register_perf_widget(self.plot_widget.canvas_frame, "canvas_frame")
            self._register_perf_widget(self.plot_widget.canvas, "canvas")
        except Exception:
            pass

        try:
            self._register_perf_widget(self.data_table.table_view, "data_table_view")
        except Exception:
            pass

        interval = 1000
        try:
            interval = max(250, int(os.getenv("HEADANALYSER_PROFILE_PLOT_PAGE_INTERVAL_MS", "1000")))
        except Exception:
            interval = 1000

        self._perf_dump_timer = QTimer(self)
        self._perf_dump_timer.setInterval(interval)
        self._perf_dump_timer.timeout.connect(self._dump_plot_profiler_stats)
        self._perf_dump_timer.start()

        header = f"[plot-profiler] enabled, logging to {self._perf_log_path}"
        print(header)
        self._append_profiler_log(header)

    def _register_perf_widget(self, widget, alias: str):
        if widget is None:
            return
        try:
            widget.installEventFilter(self)
            self._perf_watch_alias[id(widget)] = str(alias)
        except Exception:
            pass

    def _perf_tic(self, key: str):
        if not self._perf_enabled:
            return None
        return key, time.perf_counter()

    def _perf_toc(self, token):
        if token is None:
            return
        key, started = token
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        stats = self._perf_method_stats.get(key)
        if stats is None:
            stats = {"count": 0, "total_ms": 0.0, "max_ms": 0.0}
            self._perf_method_stats[key] = stats
        stats["count"] += 1
        stats["total_ms"] += elapsed_ms
        if elapsed_ms > stats["max_ms"]:
            stats["max_ms"] = elapsed_ms

    def _append_profiler_log(self, text: str):
        try:
            with open(self._perf_log_path, "a", encoding="utf-8") as f:
                f.write(text + "\n")
        except Exception:
            pass

    def _perf_log(self, message: str):
        logger = getattr(self.main_window, "_perf_log", None)
        if callable(logger):
            logger(message)
        else:
            print(message, flush=True)

    def _set_overlay_perf_notice(self, text: str):
        try:
            text = str(text or "").strip()
            if text:
                self.drawer_perf_notice.setText(text)
                self.drawer_perf_notice.setToolTip(
                    f"Large selection optimization active. Overlay is capped at "
                    f"{self._triangle_overlay_cap} triangles. "
                    f"Set HEADANALYSER_TRIANGLE_OVERLAY_CAP to adjust."
                )
                self.drawer_perf_notice.setVisible(True)
            else:
                self.drawer_perf_notice.setVisible(False)
                self.drawer_perf_notice.setText("")
                self.drawer_perf_notice.setToolTip("")
        except Exception:
            pass

    def _dump_plot_profiler_stats(self):
        if not self._perf_enabled:
            return

        if not self._perf_event_counts and not self._perf_method_stats:
            return

        elapsed = time.perf_counter() - self._perf_started
        event_parts = [f"{name}={count}" for name, count in self._perf_event_counts.most_common(12)]
        method_parts = []
        sorted_methods = sorted(
            self._perf_method_stats.items(),
            key=lambda kv: kv[1]["total_ms"],
            reverse=True,
        )
        for name, s in sorted_methods[:8]:
            avg = s["total_ms"] / s["count"] if s["count"] else 0.0
            method_parts.append(
                f"{name}: n={s['count']} total={s['total_ms']:.1f}ms avg={avg:.2f}ms max={s['max_ms']:.2f}ms"
            )

        lines = [f"[plot-profiler +{elapsed:.1f}s]"]
        if event_parts:
            lines.append("events: " + " | ".join(event_parts))
        if method_parts:
            lines.append("methods: " + " | ".join(method_parts))
        message = "\n".join(lines)
        print(message)
        self._append_profiler_log(message)

        self._perf_event_counts.clear()
        self._perf_method_stats.clear()

    def eventFilter(self, watched, event):
        if self._perf_enabled:
            event_name = self._PROFILE_EVENTS.get(event.type())
            if event_name is not None:
                alias = self._perf_watch_alias.get(id(watched))
                if alias:
                    self._perf_event_counts[f"{alias}.{event_name}"] += 1
        return super().eventFilter(watched, event)

    def _on_inspect_requested(self, ids: list):
        """Open Triangle Inspector filtered to selected point IDs from data table."""
        self.main_window.show_triangle_inspector(
            selected_point_ids=set(str(v) for v in ids)
        )

    # ──────────────────────────────────────────────────
    #  GRID AREA — property + cell-switch handlers
    # ──────────────────────────────────────────────────

    @property
    def plot_widget(self) -> PlotWidget:
        """Always returns the active grid cell's PlotWidget."""
        return self._grid_area.active_plot_widget

    def _on_save_cell_state(self) -> None:
        """Called just before the active cell changes.

        Captures the current sidebar/plot-type state AND main_window's per-cell
        filter/pill state into the cell that's about to lose focus.
        """
        try:
            cell = self._grid_area.active_cell
            plot_type = normalize_plot_type(self.plot_type_combo.currentText())
            settings = self.plot_sidebar.get_settings_snapshot()
            cell.save_state(plot_type, settings)
            cell.snapshot_mw_state(self.main_window)
        except Exception:
            pass

    # ── per-cell main_window state plumbing ───────────────────────────────
    #
    # The cell owns its own filter inputs (depth/head sliders, exclusions),
    # filter outputs (filtered_data, triangle_data, gradient_data, etc.) and
    # pill state. We restore these onto ``main_window`` whenever the cell
    # becomes active, and snapshot them back to the cell after a pipeline
    # run. This means every existing consumer (stats panel, report generator,
    # map, etc.) keeps reading ``main_window.*`` unchanged — they just see
    # the active cell's view automatically.

    # Maps keys produced by ``PlotSidebar.get_settings_snapshot`` onto the
    # main_window attributes that ``PlotWidget`` reads at draw time. Some keys
    # rename across the boundary (sidebar "surface_opacity" → mw "surface_alpha",
    # "wireframe_overlay" → "show_wireframe", "elevation_3d" → "elevation_3d"
    # which matches in this snapshot variant). Every entry should correspond to
    # a real mw attribute — extra keys are harmless (silently skipped).
    _SETTINGS_TO_MW = {
        # Viz toggles (Q: not in MW_PILLS because they live in cell.settings)
        "show_contours":    "show_contours",
        "show_arrow":       "show_arrow",
        "show_arrow_label": "show_arrow_label",
        "show_points":      "show_points",
        "show_colorbar":    "show_colorbar",
        "show_id_labels":   "show_id_labels",
        "fill_contours":    "fill_contours",
        # 2D
        "colormap_2d":      "colormap_2d",
        "point_size":       "point_size",
        "label_mode_2d":    "label_mode_2d",
        "contour_levels":   "contour_levels",
        # 3D
        "elevation_3d":     "elevation_3d",
        "azimuth_3d":       "azimuth_3d",
        "colormap_3d":      "colormap_3d",
        "surface_opacity":  "surface_alpha",
        "wireframe_overlay":"show_wireframe",
        # Vectors
        "vector_scale":     "vector_scale",
        "vector_alpha":     "vector_alpha",
        "colormap_vectors": "colormap_vectors",
        "show_mean_vector": "show_mean_vector",
        "normalize_vectors":"normalize_vectors",
        # Histogram
        "histogram_bins":         "histogram_bins",
        "histogram_bar_color":    "histogram_bar_color",
        "histogram_edge_color":   "histogram_edge_color",
        "histogram_show_mean":    "histogram_show_mean",
        "histogram_show_median":  "histogram_show_median",
        "histogram_show_ci":      "histogram_show_ci",
        "histogram_ci_level":     "histogram_ci_level",
        "histogram_show_kde":     "histogram_show_kde",
        # Rose diagram
        "rose_mode":               "rose_mode",
        "rose_bins":               "rose_bins",
        "rose_show_mean":          "rose_show_mean",
        "rose_show_weighted_mean": "rose_show_weighted_mean",
        "rose_show_ci":            "rose_show_ci",
        "rose_ci_level":           "rose_ci_level",
        "rose_color":              "rose_color",
        "rose_show_median":        "rose_show_median",
        "rose_show_mean_resultant":"rose_show_mean_resultant",
    }

    def _apply_settings_to_mw(self, settings: dict) -> None:
        """Push a cell.settings dict onto main_window's sidebar-driven attrs."""
        if not settings:
            return
        mw = self.main_window
        for sk, mk in self._SETTINGS_TO_MW.items():
            if sk not in settings:
                continue
            try:
                setattr(mw, mk, settings[sk])
            except Exception:
                pass

    def snapshot_mw_to_active_cell(self) -> None:
        """Capture main_window's current filter state into the active cell."""
        try:
            self._grid_area.active_cell.snapshot_mw_state(self.main_window)
        except Exception:
            pass

    def apply_active_cell_to_mw(self, *, sync_ui: bool = True) -> None:
        """Push the active cell's stored state onto main_window and (optionally) the filter UI.

        ``sync_ui=True`` also moves the depth/head sliders and the excluded list
        to match the cell's filter inputs — silently, so the user's switch
        does not trigger a pipeline run.
        """
        try:
            cell = self._grid_area.active_cell
        except Exception:
            return
        cell.apply_to_mw(self.main_window)
        if not sync_ui:
            return
        # Properties panel sliders — silent set so we don't trigger filters_changed
        try:
            pp = getattr(self.main_window, "properties_panel", None)
            if pp is not None:
                ms = cell.mw_state
                def _resolve(v_lo, v_hi, slider):
                    """Map (depth/head)_min/max to slider values, falling back to slider bounds."""
                    try:
                        bmin, bmax = slider.get_bounds()
                    except Exception:
                        return None, None
                    lo = float(v_lo) if v_lo is not None else float(bmin)
                    hi = float(v_hi) if v_hi is not None else float(bmax)
                    return lo, hi
                # Depth range may be disabled (no depth column) — guard the set call.
                try:
                    if pp.depth_range.isEnabled():
                        lo, hi = _resolve(ms.get("depth_min"), ms.get("depth_max"), pp.depth_range)
                        if lo is not None:
                            pp.depth_range.blockSignals(True)
                            pp.depth_range.set_values(lo, hi)
                            pp.depth_range.blockSignals(False)
                except Exception:
                    pass
                try:
                    lo, hi = _resolve(ms.get("head_min"), ms.get("head_max"), pp.head_range)
                    if lo is not None:
                        pp.head_range.blockSignals(True)
                        pp.head_range.set_values(lo, hi)
                        pp.head_range.blockSignals(False)
                except Exception:
                    pass
                # Excluded-points list reflects main_window.excluded_ids, which
                # we just rewrote — refresh the visible list.
                try:
                    pp.refresh_excluded_list()
                except Exception:
                    pass
        except Exception:
            pass

    def _seed_cell_state_if_empty(self, cell) -> None:
        """For the very first activation, populate the cell from main_window.

        Without this the cell's `_mw_state` is empty and `apply_to_mw` would
        scribble Nones over a freshly-loaded dataset.
        """
        if not cell.mw_state:
            try:
                cell.snapshot_mw_state(self.main_window)
            except Exception:
                pass

    def _on_active_cell_changed(self, idx: int) -> None:
        """Load the newly-active cell's settings into the sidebar and re-render."""
        try:
            cell = self._grid_area.cells[idx]
            mw = self.main_window
            # First activation of this cell: seed its mw_state from main_window
            # so apply_to_mw below doesn't clobber a freshly-loaded dataset.
            self._seed_cell_state_if_empty(cell)
            # Push cell's filter inputs/outputs + pills onto main_window and
            # sync the depth/head sliders + excluded list silently.
            self.apply_active_cell_to_mw(sync_ui=True)
            # Sync main_window.current_plot_type so any subsequent global
            # re-render (legend/grid/compass toggle, etc.) uses the active
            # cell's plot type — not whatever type was last set on the toolbar.
            try:
                mw.current_plot_type = cell.plot_type
            except Exception:
                pass
            # Sync toolbar plot type combo (silent — don't trigger a re-render yet)
            label = to_toolbar_label(cell.plot_type)
            self.plot_type_combo.blockSignals(True)
            self.plot_type_combo.setCurrentText(label)
            self.plot_type_combo.blockSignals(False)
            self._sync_visual_composition_controls_from_mw()
            # Sync sidebar controls + the matching main_window attributes.
            # update_from_settings blocks signals (so mw isn't touched), so
            # we also have to push the values manually — otherwise the active
            # cell renders below with stale sidebar-driven attrs (colormaps,
            # point size, etc.) inherited from the cell we just left.
            if cell.settings:
                self.plot_sidebar.update_from_settings(cell.settings)
                self._apply_settings_to_mw(cell.settings)
            self.plot_sidebar.set_plot_type(cell.plot_type)
            # Sync toolbar pill checkboxes (silent) to the cell's stored pill state
            self._sync_pill_checkboxes_from_mw()
            # Sync per-plot-widget state
            pw = cell.plot_widget
            pw.set_hint_plot_type(cell.plot_type)
            # Re-render the newly-active cell using its now-active filter state
            data = (
                getattr(mw, "filtered_plot_data", None)
                if getattr(mw, "filtered_plot_data", None) is not None else (
                    getattr(mw, "filtered_data", None)
                    if getattr(mw, "filtered_data", None) is not None
                    else getattr(mw, "data", None)
                )
            )
            if data is not None and not data.empty:
                pw.update_plot(data, cell.plot_type)
            # Rewire table↔plot selection sync to the new active cell
            self._rebind_table_to_active_cell()
            # Refresh stats panel + map. update_data_views handles both: it
            # calls _update_map_view internally AND refreshes stats/report
            # if the user is currently on that page. Avoid the double-call
            # so map isn't rebuilt twice on a single chip-driven cell switch.
            try:
                if hasattr(mw, "update_data_views"):
                    mw.update_data_views()
            except Exception:
                pass
            # Sync layout preset button highlight
            self._sync_layout_btn_state()
            # Refresh the status-bar "Showing: Cell N of M" chip so views know
            # which cell's filter is driving Stats / Map / Report.
            try:
                if hasattr(mw, "update_cell_scope_chip"):
                    mw.update_cell_scope_chip()
            except Exception:
                pass
        except Exception:
            pass

    def _sync_pill_checkboxes_from_mw(self) -> None:
        """Silently push the active cell's pill flags onto the toolbar checkboxes.

        Grid/Legend/Compass live on ``main_window`` (just rewritten by
        ``apply_active_cell_to_mw``). Dark canvas is a per-PlotWidget flag
        (``_dark_canvas``), so we read it directly off the active cell's widget.
        """
        mw = self.main_window
        pairs = (
            (getattr(self, "grid_checkbox", None),    "show_grid"),
            (getattr(self, "legend_checkbox", None),  "show_legend"),
            (getattr(self, "compass_checkbox", None), "show_compass"),
        )
        for cb, attr in pairs:
            if cb is None:
                continue
            try:
                cb.blockSignals(True)
                cb.setChecked(bool(getattr(mw, attr, False)))
                cb.blockSignals(False)
            except Exception:
                pass
        dark_cb = getattr(self, "dark_canvas_checkbox", None)
        if dark_cb is not None:
            try:
                dark_cb.blockSignals(True)
                dark_cb.setChecked(bool(getattr(self.plot_widget, "_dark_canvas", False)))
                dark_cb.blockSignals(False)
            except Exception:
                pass

    def _sync_visual_composition_controls_from_mw(self) -> None:
        """Silently sync format/palette toolbar controls from main_window."""
        mw = self.main_window
        pairs = (
            (
                getattr(self, "format_combo", None),
                str(getattr(mw, "current_plot_format", getattr(mw, "current_plot_style", "Default"))),
            ),
            (
                getattr(self, "palette_combo", None),
                str(getattr(mw, "current_color_style", "hydraulic")),
            ),
        )
        for combo, key in pairs:
            if combo is None:
                continue
            try:
                combo.blockSignals(True)
                self._set_combo_current_data(combo, key)
            except Exception:
                pass
            finally:
                try:
                    combo.blockSignals(False)
                except Exception:
                    pass
        self._refresh_appearance_button()

    def _sync_layout_btn_state(self) -> None:
        """Highlight the correct layout preset button for the current grid preset."""
        try:
            preset = self._grid_area.current_preset()
            for i, btn in enumerate(self._layout_btns, 1):
                btn.setChecked(i == preset)
        except Exception:
            pass

    # ──────────────────────────────────────────────────
    #  TOOLBAR (redesigned: 40px, compact, pill group)
    # ──────────────────────────────────────────────────

    def _create_plot_toolbar(self):
        """Create a compact toolbar for plot controls.

        Uses a FlowLayout (instead of QHBoxLayout) so controls wrap to a
        second row when the window is too narrow to fit them on one line —
        keeps everything reachable without horizontal clipping.
        """
        from .common_widgets import FlowLayout
        metrics = build_screen_metrics(self)
        toolbar = QWidget()
        toolbar.setObjectName("plotToolbar")
        # Allow the toolbar to grow vertically when items wrap; minimum is one
        # row, but heightForWidth lets it expand when content needs two rows.
        toolbar.setMinimumHeight(metrics.toolbar_height)
        toolbar.setStyleSheet(StyleSheet.get_toolbar_compact_style())
        _sp = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        # Tell the parent layout that our height depends on our width — this
        # is what makes a parent QVBoxLayout actually consult heightForWidth
        # when the toolbar is narrow enough that FlowLayout wraps to 2 rows.
        _sp.setHeightForWidth(True)
        toolbar.setSizePolicy(_sp)

        tl = FlowLayout(
            toolbar,
            hSpacing=5 if metrics.compact else 6,
            vSpacing=4,
        )
        tl.setContentsMargins(8 if metrics.compact else 10, 4, 8 if metrics.compact else 10, 4)

        # ── Sidebar toggle (hamburger icon) ──
        self.sidebar_toggle_btn = QToolButton()
        self.sidebar_toggle_btn.setToolTip("Toggle Sidebar")
        self.sidebar_toggle_btn.setIcon(icon(Icons.BARS, color=Colors.TEXT_SECONDARY))
        self.sidebar_toggle_btn.setFixedSize(metrics.toolbar_button_size, metrics.toolbar_button_size)
        self.sidebar_toggle_btn.clicked.connect(self._toggle_sidebar)
        tl.addWidget(self.sidebar_toggle_btn)

        # ── Divider ──
        tl.addWidget(self._make_divider())

        # ── Grid layout preset buttons ──
        # Use mini-grid icons instead of "1×1"/"1×2" text — more compact,
        # visually self-explanatory, and matches the toolbar's iconic style.
        self._layout_btns = []
        # (label, rows, cols, preset_idx) — label kept for tooltip only.
        _preset_specs = [
            ("1×1", 1, 1, 1),
            ("1×2", 1, 2, 2),
            ("2×1", 2, 1, 3),
            ("2×2", 2, 2, 4),
            ("1×3", 1, 3, 5),
        ]
        _current_preset = self._grid_area.current_preset() if hasattr(self, '_grid_area') else 1
        layout_grp = QWidget()
        layout_grp.setObjectName("layoutBtnGroup")
        layout_grp.setStyleSheet(StyleSheet.get_toggle_pill_group_style())
        layout_grp.setFixedHeight(metrics.toolbar_control_height)
        _lg = QHBoxLayout(layout_grp)
        _lg.setContentsMargins(3, 0, 3, 0)
        _lg.setSpacing(2)
        _icon_px = max(12, metrics.toolbar_pill_height - 8)
        for _label, _rows, _cols, _n in _preset_specs:
            _btn = QToolButton()
            _btn.setIcon(self._make_grid_icon(_rows, _cols, _icon_px))
            _btn.setIconSize(QSize(_icon_px, _icon_px))
            _btn.setToolTip(f"Layout {_label}")
            _btn.setCheckable(True)
            _btn.setChecked(_n == _current_preset)
            _btn.setCursor(Qt.PointingHandCursor)
            _btn.setFixedHeight(metrics.toolbar_pill_height)
            _btn.setFixedWidth(metrics.toolbar_pill_height + 4)  # square-ish
            _btn.clicked.connect(
                lambda _checked=False, _preset=_n: self._on_layout_preset_clicked(_preset)
            )
            _lg.addWidget(_btn)
            self._layout_btns.append(_btn)
        tl.addWidget(layout_grp)

        # ── Divider ──
        tl.addWidget(self._make_divider())

        # ── Plot type combo ──
        self.plot_type_combo = QComboBox()
        self.plot_type_combo.addItems(list(TOOLBAR_PLOT_LABELS))
        self.plot_type_combo.setCurrentText(to_toolbar_label(getattr(self.main_window, "current_plot_type", "2D")))
        self.plot_type_combo.setFixedHeight(metrics.toolbar_pill_height)
        self.plot_type_combo.setMinimumWidth(100)
        self.plot_type_combo.currentTextChanged.connect(self._on_plot_type_changed)
        tl.addWidget(self.plot_type_combo)

        # Appearance menu: template gallery plus compact format/color-style selectors.
        self.format_combo = None
        self.palette_combo = None
        self.style_combo = None
        self.appearance_btn = QToolButton()
        self.appearance_btn.setIcon(icon(Icons.PALETTE, color=Colors.TEXT_SECONDARY))
        self.appearance_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.appearance_btn.setCursor(Qt.PointingHandCursor)
        self.appearance_btn.setFixedHeight(metrics.toolbar_control_height)
        self.appearance_btn.setToolTip("Templates, color style, and plot format")
        self.appearance_btn.clicked.connect(self._show_appearance_flyout)
        self._appearance_flyout = None
        self._refresh_appearance_button()
        tl.addWidget(self.appearance_btn)

        # ── Divider ──
        tl.addWidget(self._make_divider())

        # ── Toggle pill group (Grid / Legend / Compass) ──
        pill_group = QWidget()
        pill_group.setObjectName("togglePillGroup")
        pill_group.setFixedHeight(metrics.toolbar_control_height)
        pill_group.setStyleSheet(StyleSheet.get_toggle_pill_group_style())
        pg_layout = QHBoxLayout(pill_group)
        pg_layout.setContentsMargins(3, 0, 3, 0)
        pg_layout.setSpacing(2)

        self.grid_checkbox = self._make_pill_toggle("Grid", "Toggle grid", False, Icons.GRID)
        self.legend_checkbox = self._make_pill_toggle("Legend", "Toggle legend", True, Icons.LIST)
        self.compass_checkbox = self._make_pill_toggle("Compass", "Toggle compass", True, Icons.PLOT_ROSE)
        self.dark_canvas_checkbox = self._make_pill_toggle("Dark", "Toggle dark plot canvas", False, Icons.MOON)
        self.grid_checkbox.setChecked(bool(getattr(self.main_window, "show_grid", False)))
        self.legend_checkbox.setChecked(bool(getattr(self.main_window, "show_legend", True)))
        self.compass_checkbox.setChecked(bool(getattr(self.main_window, "show_compass", True)))

        pg_layout.addWidget(self.grid_checkbox)
        pg_layout.addWidget(self.legend_checkbox)
        pg_layout.addWidget(self.compass_checkbox)
        pg_layout.addWidget(self.dark_canvas_checkbox)

        tl.addWidget(pill_group)

        # Connect toggle signals
        self.grid_checkbox.toggled.connect(
            lambda checked: self._on_grid_changed(Qt.Checked if checked else Qt.Unchecked))
        self.legend_checkbox.toggled.connect(
            lambda checked: self._on_legend_changed(Qt.Checked if checked else Qt.Unchecked))
        self.compass_checkbox.toggled.connect(
            lambda checked: self._on_compass_changed(Qt.Checked if checked else Qt.Unchecked))
        self.dark_canvas_checkbox.toggled.connect(self._on_dark_canvas_changed)

        # FlowLayout can't honor addStretch (no concept of "expanding spacer"
        # when items wrap). Use a visual divider instead to separate primary
        # controls from secondary actions; items just flow left-to-right.
        tl.addWidget(self._make_divider())

        # ── Drawer toggles ──
        self.table_toggle_btn = QToolButton()
        self.table_toggle_btn.setText("Table")
        self.table_toggle_btn.setIcon(icon(Icons.TABLE, color=Colors.TEXT_SECONDARY))
        self.table_toggle_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.table_toggle_btn.setToolTip("Toggle attribute table (Ctrl+T)")
        self.table_toggle_btn.setCheckable(True)
        self.table_toggle_btn.setCursor(Qt.PointingHandCursor)
        self.table_toggle_btn.setFixedHeight(metrics.toolbar_control_height)
        self.table_toggle_btn.toggled.connect(self._toggle_table)
        tl.addWidget(self.table_toggle_btn)

        self.quick_stats_btn = QToolButton()
        self.quick_stats_btn.setText("Stats")
        self.quick_stats_btn.setIcon(icon(Icons.CHART_LINE, color=Colors.TEXT_SECONDARY))
        self.quick_stats_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.quick_stats_btn.setToolTip("Toggle quick stats drawer")
        self.quick_stats_btn.setCheckable(True)
        self.quick_stats_btn.setCursor(Qt.PointingHandCursor)
        self.quick_stats_btn.setFixedHeight(metrics.toolbar_control_height)
        self.quick_stats_btn.toggled.connect(self._toggle_quick_stats)
        tl.addWidget(self.quick_stats_btn)

        # ── Divider ──
        tl.addWidget(self._make_divider())

        # ── Action group (Export + Settings in well container) ──
        self.add_point_btn = QToolButton()
        self.add_point_btn.setText("Add")
        self.add_point_btn.setIcon(icon(Icons.ADD_POINT, color=Colors.TEXT_SECONDARY))
        self.add_point_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.add_point_btn.setToolTip("Toggle point creation mode")
        self.add_point_btn.setCheckable(True)
        self.add_point_btn.setCursor(Qt.PointingHandCursor)
        self.add_point_btn.setFixedHeight(metrics.toolbar_control_height)
        self.add_point_btn.toggled.connect(self.main_window.set_point_creation_mode)
        tl.addWidget(self.add_point_btn)

        tl.addWidget(self._make_divider())

        action_group = QWidget()
        action_group.setObjectName("tbActionGroup")
        action_group.setFixedHeight(metrics.toolbar_control_height)
        ag_layout = QHBoxLayout(action_group)
        ag_layout.setContentsMargins(3, 0, 3, 0)
        ag_layout.setSpacing(2)

        export_btn = QToolButton()
        export_btn.setIcon(icon(Icons.DOWNLOAD, color=Colors.TEXT_SECONDARY))
        export_btn.setToolTip("Export plot")
        export_btn.setFixedSize(metrics.toolbar_small_button_width, metrics.toolbar_small_button_height)
        export_btn.clicked.connect(self.main_window.on_export)
        ag_layout.addWidget(export_btn)

        self.settings_btn = QToolButton()
        self.settings_btn.setIcon(icon(Icons.SETTINGS, color=Colors.TEXT_SECONDARY))
        self.settings_btn.setToolTip("Plot settings")
        self.settings_btn.setFixedSize(metrics.toolbar_small_button_width, metrics.toolbar_small_button_height)
        self.settings_btn.clicked.connect(self.main_window.on_settings)
        ag_layout.addWidget(self.settings_btn)

        tl.addWidget(action_group)

        return toolbar

    def _rebuild_toolbar(self):
        root_layout = self.layout()
        if root_layout is None:
            return

        table_open = bool(self._table_drawer_open)
        quick_stats_open = bool(self._quick_stats_drawer_open)
        dark_canvas = bool(getattr(self.plot_widget, "_dark_canvas", False)) if hasattr(self, "plot_widget") else False
        add_point_mode = bool(self.main_window.is_point_creation_mode()) if hasattr(self.main_window, "is_point_creation_mode") else False

        if self._toolbar is not None:
            root_layout.removeWidget(self._toolbar)
            self._toolbar.deleteLater()

        self._toolbar = self._create_plot_toolbar()
        root_layout.insertWidget(0, self._toolbar)

        for btn, checked in (
            (self.table_toggle_btn, table_open),
            (self.quick_stats_btn, quick_stats_open),
            (self.add_point_btn, add_point_mode),
            (self.dark_canvas_checkbox, dark_canvas),
        ):
            btn.blockSignals(True)
            btn.setChecked(bool(checked))
            btn.blockSignals(False)

        self.sidebar_toggle_btn.setText("\u276E" if self.sidebar_visible else "\u2630")

    def _make_divider(self):
        """Create a thin vertical divider for the toolbar."""
        metrics = build_screen_metrics(self)
        d = QFrame()
        d.setFrameShape(QFrame.VLine)
        d.setFixedHeight(max(16, metrics.toolbar_control_height - 12))
        d.setStyleSheet(f"background-color: {Colors.BORDER_MEDIUM}; max-width: 1px; border: none;")
        return d

    @staticmethod
    def _make_grid_icon(rows: int, cols: int, size: int = 14) -> QIcon:
        """Render a tiny ``rows × cols`` grid pattern as a QIcon for toolbar use.

        Used by the layout preset buttons (1×1, 1×2, 2×1, 2×2, 1×3) to visually
        represent each layout without needing text. Outline rectangles draw
        cleanly at small sizes; the inner gap separates cells.
        """
        size = int(max(10, size))
        pix = QPixmap(size, size)
        pix.fill(Qt.transparent)
        painter = QPainter(pix)
        try:
            painter.setRenderHint(QPainter.Antialiasing, False)
            pen = QPen(QColor(Colors.TEXT_PRIMARY))
            pen.setWidth(1)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            # 1-px margin so the outline doesn't clip on the pixmap edge,
            # 1-px gap between cells.
            margin = 1.0
            gap = 1.0
            inner_w = size - 2 * margin
            inner_h = size - 2 * margin
            cell_w = (inner_w - gap * (cols - 1)) / cols
            cell_h = (inner_h - gap * (rows - 1)) / rows
            for r in range(rows):
                for c in range(cols):
                    x = margin + c * (cell_w + gap)
                    y = margin + r * (cell_h + gap)
                    painter.drawRect(QRectF(x, y, cell_w, cell_h))
        finally:
            painter.end()
        return QIcon(pix)

    @staticmethod
    def _set_combo_current_data(combo: QComboBox, key: str) -> None:
        idx = combo.findData(key)
        if idx < 0:
            idx = combo.findText(str(key))
        if idx >= 0:
            combo.setCurrentIndex(idx)

    @staticmethod
    def _combo_data(combo: QComboBox, fallback: str = "") -> str:
        data = combo.currentData()
        return str(data if data is not None else (combo.currentText() or fallback))

    def _refresh_appearance_button(self) -> None:
        btn = getattr(self, "appearance_btn", None)
        if btn is None:
            return
        try:
            from styles.plot_palettes import get_palette
            fmt = str(getattr(
                self.main_window,
                "current_plot_format",
                getattr(self.main_window, "current_plot_style", "Default"),
            ))
            palette = get_palette(getattr(self.main_window, "current_color_style", "hydraulic"))
            btn.setText(f"Templates  {palette.name} / {fmt}")
        except Exception:
            btn.setText("Templates")

    def _show_appearance_flyout(self) -> None:
        from .dialogs.plot_appearance_flyout import PlotAppearanceFlyout

        if self._appearance_flyout is not None:
            try:
                self._appearance_flyout.close()
            except Exception:
                pass
        self._appearance_flyout = PlotAppearanceFlyout(
            self.main_window,
            plot_type=getattr(self.main_window, "current_plot_type", "2D"),
            parent=self,
        )
        self._appearance_flyout.template_selected.connect(self._apply_template_key)
        self._appearance_flyout.palette_selected.connect(self._apply_palette_key)
        self._appearance_flyout.format_selected.connect(self._on_style_changed)
        self._appearance_flyout.gallery_requested.connect(self.main_window.on_plot_template_picker)
        pos = self.appearance_btn.mapToGlobal(self.appearance_btn.rect().bottomLeft())
        self._appearance_flyout.move(pos)
        self._appearance_flyout.show()

    def _apply_template_key(self, template_key: str) -> None:
        if hasattr(self.main_window, "apply_plot_template"):
            self.main_window.apply_plot_template(template_key)
        self._refresh_appearance_button()

    def _make_pill_toggle(self, text: str, tooltip: str, checked: bool, icon_name: str = None):
        """Create a pill-style toggle button for the pill group."""
        metrics = build_screen_metrics(self)
        btn = QToolButton()
        btn.setText(text)
        btn.setToolTip(tooltip)
        btn.setCheckable(True)
        btn.setChecked(bool(checked))
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFixedHeight(metrics.toolbar_pill_height)
        if icon_name:
            btn.setIcon(icon(icon_name, color=Colors.TEXT_SECONDARY))
            btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        return btn

    # ──────────────────────────────────────────────────
    #  SIDEBAR (animated collapse)
    # ──────────────────────────────────────────────────

    def _toggle_sidebar(self):
        """Toggle the sidebar using overlay slide animation (no layout resize)."""
        _perf = self._perf_tic("PlotPage._toggle_sidebar")
        if self._sidebar_anim is None:
            self._sidebar_anim = QPropertyAnimation(self.plot_sidebar, b"pos")
            self._sidebar_anim.setDuration(300)
            self._sidebar_anim.setEasingCurve(QEasingCurve.InOutCubic)
            self._sidebar_anim.finished.connect(self._on_sidebar_animation_finished)

        sidebar_w = int(self._sidebar_width)
        if self._sidebar_anim.state() == QAbstractAnimation.Running:
            self._sidebar_anim.stop()

        if not self.sidebar_visible:
            self.plot_sidebar.show()
            self.plot_sidebar.raise_()
            self._sync_sidebar_overlay_geometry(x=-sidebar_w)
            self._sidebar_anim.setStartValue(QPoint(-sidebar_w, 0))
            self._sidebar_anim.setEndValue(QPoint(0, 0))
            self._sidebar_anim_started_at = time.perf_counter()
            self._sidebar_anim_target = "open"
            self._sidebar_anim.start()
            self.sidebar_toggle_btn.setText("\u276E")
            self.sidebar_visible = True
        else:
            self.plot_sidebar.show()
            self.plot_sidebar.raise_()
            self._sync_sidebar_overlay_geometry(x=0)
            self._sidebar_anim.setStartValue(QPoint(0, 0))
            self._sidebar_anim.setEndValue(QPoint(-sidebar_w, 0))
            self._sidebar_anim_started_at = time.perf_counter()
            self._sidebar_anim_target = "close"
            self._sidebar_anim.start()
            self.sidebar_toggle_btn.setText("\u2630")
            self.sidebar_visible = False
        self._perf_toc(_perf)

    def _on_sidebar_animation_finished(self):
        started = self._sidebar_anim_started_at
        target = self._sidebar_anim_target or "unknown"
        self._sidebar_anim_started_at = None
        self._sidebar_anim_target = None

        # Hybrid mode:
        # - animate overlay for smoothness (no per-frame plot relayout),
        # - then do one final layout snap so the plot width reflects sidebar state.
        self._apply_sidebar_layout_snap()
        # Keep bottom drawer overlays aligned with the visible plotting area.
        self._sync_bottom_drawer_overlay_geometry(force_targets=True)

        if not self.sidebar_visible:
            self.plot_sidebar.hide()

        if started is None:
            return
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        self._perf_log(
            f"[perf][sidebar-anim] target={target} elapsed={elapsed_ms:.1f}ms "
            f"end_x={int(self.plot_sidebar.pos().x())}"
        )

    def _sync_sidebar_overlay_geometry(self, x=None):
        host = self._plot_column
        sidebar = getattr(self, "plot_sidebar", None)
        if host is None or sidebar is None:
            return
        sidebar_w = int(self._sidebar_width)
        if x is None:
            try:
                x = int(sidebar.x())
            except Exception:
                x = 0 if self.sidebar_visible else -sidebar_w
        sidebar.setGeometry(int(x), 0, sidebar_w, max(0, int(host.height())))

    def _drawer_overlay_left_offset(self) -> int:
        """Return left inset for drawer overlays based on visible sidebar width."""
        try:
            sidebar = getattr(self, "plot_sidebar", None)
            if sidebar is None:
                return 0
            sidebar_w = int(self._sidebar_width)
            sx = int(sidebar.x())
            # sidebar x in [-sidebar_w, 0] while animating.
            exposed = max(0, min(sidebar_w, sidebar_w + sx))
            return int(exposed)
        except Exception:
            return int(self._sidebar_width) if self.sidebar_visible else 0

    def _apply_sidebar_layout_snap(self):
        layout = self._plot_column_layout
        if layout is None:
            return
        left = int(self._sidebar_width) if self.sidebar_visible else 0
        try:
            cur = layout.contentsMargins()
            if int(cur.left()) == left:
                return
            layout.setContentsMargins(left, 0, 0, 0)
            self._perf_log(f"[perf][sidebar-layout-snap] visible={int(self.sidebar_visible)} left_margin={left}")
        except Exception:
            pass

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._sync_sidebar_overlay_geometry()
        # On host resize we must reflow open drawer overlay geometry immediately,
        # otherwise stale heights/positions can drift off-screen.
        self._sync_bottom_drawer_overlay_geometry(force_targets=True)

    # ──────────────────────────────────────────────────
    #  DRAWER TOGGLES
    # ──────────────────────────────────────────────────

    def _toggle_table(self, checked: bool):
        """Toggle the bottom data table drawer (overlay-slide + end snap)."""
        _perf = self._perf_tic("PlotPage._toggle_table")
        self._table_drawer_open = bool(checked)
        self._animate_bottom_drawers()
        self._perf_toc(_perf)

    def toggle_table_panel(self):
        """Public method to toggle the table panel (used by Ctrl+T shortcut)."""
        self.table_toggle_btn.setChecked(not self.table_toggle_btn.isChecked())

    def ensure_table_panel_visible(self):
        """Ensure the data table drawer is open."""
        if not self.table_toggle_btn.isChecked():
            self.table_toggle_btn.setChecked(True)

    def _toggle_quick_stats(self, checked: bool):
        """Toggle the bottom quick stats drawer (overlay-slide + end snap)."""
        _perf = self._perf_tic("PlotPage._toggle_quick_stats")
        self._quick_stats_drawer_open = bool(checked)
        if checked:
            try:
                self.quick_stats_panel.update_from_app()
            except Exception:
                pass
        self._animate_bottom_drawers()
        self._perf_toc(_perf)

    def _on_table_animation_finished(self):
        self._finalize_bottom_drawers_if_idle()

    def _on_quick_stats_animation_finished(self):
        self._finalize_bottom_drawers_if_idle()

    def _calc_table_drawer_height(self) -> int:
        target = 280
        try:
            target = max(200, min(420, int(self.height() * 0.38)))
        except Exception:
            target = 280
        return int(target)

    def _calc_quick_stats_drawer_height(self) -> int:
        target = 360
        try:
            target = max(260, min(460, int(self.height() * 0.42)))
        except Exception:
            target = 360
        return int(target)

    def _ensure_bottom_drawer_animations(self):
        if self._table_anim is None:
            self._table_anim = QPropertyAnimation(self.table_container, b"pos")
            self._table_anim.setDuration(300)
            self._table_anim.setEasingCurve(QEasingCurve.InOutCubic)
            self._table_anim.finished.connect(self._on_table_animation_finished)
        if self._quick_stats_anim is None:
            self._quick_stats_anim = QPropertyAnimation(self.quick_stats_container, b"pos")
            self._quick_stats_anim.setDuration(300)
            self._quick_stats_anim.setEasingCurve(QEasingCurve.InOutCubic)
            self._quick_stats_anim.finished.connect(self._on_quick_stats_animation_finished)

    def _animate_bottom_drawers(self):
        self._ensure_bottom_drawer_animations()

        if self._table_anim.state() == QAbstractAnimation.Running:
            self._table_anim.stop()
        if self._quick_stats_anim.state() == QAbstractAnimation.Running:
            self._quick_stats_anim.stop()

        host = self._plot_column
        if host is None:
            return
        host_h = max(0, int(host.height()))
        host_w = max(0, int(host.width()))
        drawer_x = int(self._drawer_overlay_left_offset())
        drawer_w = max(0, host_w - drawer_x)

        self._table_drawer_height = self._calc_table_drawer_height() if self._table_drawer_open else 0
        self._quick_stats_drawer_height = self._calc_quick_stats_drawer_height() if self._quick_stats_drawer_open else 0

        if self._table_drawer_height > 0:
            self.table_container.setFixedHeight(int(self._table_drawer_height))
        if self._quick_stats_drawer_height > 0:
            self.quick_stats_container.setFixedHeight(int(self._quick_stats_drawer_height))

        table_target_y = host_h - int(self._table_drawer_height) if self._table_drawer_open else host_h
        quick_target_y = (
            host_h - int(self._table_drawer_height) - int(self._quick_stats_drawer_height)
            if self._quick_stats_drawer_open
            else host_h
        )

        for widget in (self.table_container, self.quick_stats_container):
            try:
                widget.setFixedWidth(int(drawer_w))
            except Exception:
                pass

        if self._table_drawer_open or self.table_container.isVisible():
            if not self.table_container.isVisible():
                self.table_container.move(int(drawer_x), host_h)
                self.table_container.show()
            self._table_anim.setStartValue(QPoint(int(self.table_container.x()), int(self.table_container.y())))
            self._table_anim.setEndValue(QPoint(int(drawer_x), int(table_target_y)))
            self._table_anim_target_open = bool(self._table_drawer_open)
            self._table_anim.start()

        if self._quick_stats_drawer_open or self.quick_stats_container.isVisible():
            if not self.quick_stats_container.isVisible():
                self.quick_stats_container.move(int(drawer_x), host_h)
                self.quick_stats_container.show()
            self._quick_stats_anim.setStartValue(QPoint(int(self.quick_stats_container.x()), int(self.quick_stats_container.y())))
            self._quick_stats_anim.setEndValue(QPoint(int(drawer_x), int(quick_target_y)))
            self._quick_stats_anim_target_open = bool(self._quick_stats_drawer_open)
            self._quick_stats_anim.start()

        self._finalize_bottom_drawers_if_idle()

    def _finalize_bottom_drawers_if_idle(self):
        table_running = self._table_anim is not None and self._table_anim.state() == QAbstractAnimation.Running
        quick_running = self._quick_stats_anim is not None and self._quick_stats_anim.state() == QAbstractAnimation.Running
        if table_running or quick_running:
            return

        if not self._table_drawer_open:
            self.table_container.hide()
        if not self._quick_stats_drawer_open:
            self.quick_stats_container.hide()

        self._apply_bottom_drawers_layout_snap()
        self._sync_bottom_drawer_overlay_geometry(force_targets=True)

    def _apply_bottom_drawers_layout_snap(self):
        layout = self._plot_column_layout
        if layout is None:
            return
        bottom = int(self._table_drawer_height if self._table_drawer_open else 0) + int(
            self._quick_stats_drawer_height if self._quick_stats_drawer_open else 0
        )
        try:
            cur = layout.contentsMargins()
            if int(cur.bottom()) == int(bottom):
                return
            layout.setContentsMargins(int(cur.left()), int(cur.top()), int(cur.right()), int(bottom))
            self._perf_log(
                f"[perf][drawer-layout-snap] table={int(self._table_drawer_open)} "
                f"quick={int(self._quick_stats_drawer_open)} bottom_margin={int(bottom)}"
            )
        except Exception:
            pass

    def _sync_bottom_drawer_overlay_geometry(self, *, force_targets: bool):
        host = self._plot_column
        if host is None:
            return
        host_h = max(0, int(host.height()))
        host_w = max(0, int(host.width()))
        drawer_x = int(self._drawer_overlay_left_offset())
        drawer_w = max(0, host_w - drawer_x)

        # Recompute open drawer heights against current size.
        table_h_req = int(self._calc_table_drawer_height()) if self._table_drawer_open else 0
        quick_h_req = int(self._calc_quick_stats_drawer_height()) if self._quick_stats_drawer_open else 0

        # Keep some plot area visible; clamp drawer stack to available height.
        min_plot_visible = 120
        max_stack_h = max(0, host_h - int(min_plot_visible))
        stack_req = max(0, table_h_req) + max(0, quick_h_req)
        if stack_req > max_stack_h and stack_req > 0:
            scale = float(max_stack_h) / float(stack_req)
            table_h = int(max(0, round(table_h_req * scale)))
            quick_h = int(max(0, round(quick_h_req * scale)))
        else:
            table_h = int(max(0, table_h_req))
            quick_h = int(max(0, quick_h_req))

        self._table_drawer_height = int(table_h if self._table_drawer_open else 0)
        self._quick_stats_drawer_height = int(quick_h if self._quick_stats_drawer_open else 0)

        table_target_y = host_h - int(self._table_drawer_height) if self._table_drawer_open else host_h
        quick_target_y = (
            host_h - int(self._table_drawer_height) - int(self._quick_stats_drawer_height)
            if self._quick_stats_drawer_open
            else host_h
        )
        table_target_y = int(max(0, min(host_h, table_target_y)))
        quick_target_y = int(max(0, min(host_h, quick_target_y)))

        try:
            self.table_container.setFixedWidth(int(drawer_w))
            self.quick_stats_container.setFixedWidth(int(drawer_w))
            if self._table_drawer_open:
                self.table_container.setFixedHeight(int(self._table_drawer_height))
            if self._quick_stats_drawer_open:
                self.quick_stats_container.setFixedHeight(int(self._quick_stats_drawer_height))
        except Exception:
            pass

        # Keep layout margins in sync with recalculated heights.
        self._apply_bottom_drawers_layout_snap()

        table_running = self._table_anim is not None and self._table_anim.state() == QAbstractAnimation.Running
        quick_running = self._quick_stats_anim is not None and self._quick_stats_anim.state() == QAbstractAnimation.Running
        if force_targets or (not table_running and not quick_running):
            try:
                self.table_container.move(int(drawer_x), int(table_target_y))
            except Exception:
                pass
            try:
                self.quick_stats_container.move(int(drawer_x), int(quick_target_y))
            except Exception:
                pass

    # ──────────────────────────────────────────────────
    #  DRAWER MODE (Data / Triangles)
    # ──────────────────────────────────────────────────

    def _on_drawer_mode_changed(self, button_id: int):
        """Switch between Data (0) and Triangles (1) in the drawer."""
        if button_id == 1:
            self._ensure_triangle_table()
            # Clear triangle overlay when switching TO triangle view is harmless
            # (overlay is driven by selection)
        else:
            # Switching to Data mode: clear any triangle overlay
            self.plot_widget.clear_triangle_overlay()
            self._set_overlay_perf_notice("")

        self._drawer_stack.setCurrentIndex(button_id)
        self._update_drawer_row_count()

    def _ensure_triangle_table(self):
        """Lazily create and wire the triangle table widget."""
        if self._triangle_table is not None:
            return

        from .triangle_widgets.triangle_table import TriangleTableWidget
        self._triangle_table = TriangleTableWidget()
        self._drawer_stack.addWidget(self._triangle_table)  # index 1

        # Wire triangle selection -> plot overlay
        self._triangle_table.triangle_selected.connect(
            self._on_triangle_selection_changed
        )

        # Populate if data already available (deferred so UI can paint first).
        self.drawer_row_count.setText("Loading triangles...")
        self._set_overlay_perf_notice("Loading triangles...")
        QTimer.singleShot(0, self._refresh_triangle_table_data)

    def _refresh_triangle_table_data(self):
        """Push combined (kept + rejected) triangle data into the triangle table."""
        if self._triangle_table is None:
            return
        if self._triangle_table_loading:
            return
        self._triangle_table_loading = True
        try:
            from .triangle_widgets.triangle_data_helper import TriangleDataHelper

            mw = self.main_window
            triangle_data = getattr(mw, 'triangle_data', None)
            rejected_data = getattr(mw, 'rejected_data', None)
            kept_n = int(len(triangle_data)) if triangle_data is not None else 0
            rej_n = int(len(rejected_data)) if rejected_data is not None else 0
            self._perf_log(
                f"[perf][triangle-table-refresh] start kept={kept_n} rejected={rej_n}"
            )

            # Need at least one source of triangles
            has_kept = triangle_data is not None and not triangle_data.empty
            has_rejected = rejected_data is not None and not rejected_data.empty
            if not has_kept and not has_rejected:
                self._set_overlay_perf_notice("")
                return

            t0 = time.perf_counter()
            t_build0 = time.perf_counter()
            combined = TriangleDataHelper.build_combined_triangle_df(
                triangle_data, rejected_data
            )
            build_ms = (time.perf_counter() - t_build0) * 1000.0
            if combined.empty:
                self._set_overlay_perf_notice("")
                return

            total_rows = int(len(combined))
            shown_rows = total_rows
            if int(self._triangle_table_max_rows) > 0 and total_rows > int(self._triangle_table_max_rows):
                shown_rows = int(self._triangle_table_max_rows)
                combined = combined.iloc[:shown_rows]
                self._set_overlay_perf_notice(f"Triangles shown: {shown_rows}/{total_rows}")
            else:
                self._set_overlay_perf_notice("")

            self._perf_log(
                f"[perf][triangle-table-refresh] built combined={total_rows} shown={shown_rows} build={build_ms:.1f}ms"
            )
            try:
                from PyQt5.QtWidgets import QApplication
                app = QApplication.instance()
                if app is not None:
                    app.processEvents()
            except Exception:
                pass
            t_update0 = time.perf_counter()
            self._triangle_table.update_data(combined)
            update_ms = (time.perf_counter() - t_update0) * 1000.0
            self._update_drawer_row_count()
            total_ms = (time.perf_counter() - t0) * 1000.0
            self._perf_log(
                f"[perf][triangle-table-refresh] kept={kept_n} rejected={rej_n} "
                f"combined={total_rows} shown={shown_rows} build={build_ms:.1f}ms update={update_ms:.1f}ms total={total_ms:.1f}ms"
            )
        except Exception:
            pass
        finally:
            self._triangle_table_loading = False

    def refresh_triangle_data(self):
        """Public method — called after gradient recalculation to update triangle table."""
        self._refresh_triangle_table_data()

    def _on_triangle_selection_changed(self, triangle_indices: list):
        """Handle triangle selection from the drawer triangle table (debounced)."""
        self._pending_triangle_indices = list(triangle_indices or [])
        try:
            # Triangle table selection indices are table source rows (combined kept+rejected).
            # Global selection should track only canonical kept-triangle IDs.
            selected_kept_triangle_ids = []
            combined = None
            try:
                combined = self._triangle_table._model._df if self._triangle_table is not None else None
            except Exception:
                combined = None
            if combined is not None and not combined.empty:
                for idx in self._pending_triangle_indices:
                    try:
                        i = int(idx)
                    except Exception:
                        continue
                    if i < 0 or i >= len(combined):
                        continue
                    row = combined.iloc[i]
                    if str(row.get("status", "")).strip().lower() != "kept":
                        continue
                    tri_id = row.get("triangle_index", None)
                    try:
                        if tri_id is not None and np.isfinite(float(tri_id)):
                            selected_kept_triangle_ids.append(int(tri_id))
                    except Exception:
                        continue
            self.main_window.set_triangle_selection(
                selected_kept_triangle_ids,
                meta={
                    "source": "triangle_table",
                    "table_rows": list(self._pending_triangle_indices),
                    "kept_triangles": int(len(selected_kept_triangle_ids)),
                },
            )
        except Exception:
            pass
        if self._triangle_overlay_timer is not None:
            self._triangle_overlay_timer.start()
        else:
            self._flush_triangle_selection_overlay()

    def _flush_triangle_selection_overlay(self):
        t0 = time.perf_counter()
        triangle_indices = list(self._pending_triangle_indices or [])

        if not triangle_indices:
            self.plot_widget.clear_triangle_overlay()
            self._set_overlay_perf_notice("")
            return

        try:
            mw = self.main_window
            fdata = getattr(mw, 'filtered_data', None)
            if fdata is None or fdata.empty:
                self.plot_widget.clear_triangle_overlay()
                self._set_overlay_perf_notice("")
                return

            # The table model holds the combined DataFrame we passed in.
            combined = self._triangle_table._model._df
            if combined is None or combined.empty:
                self.plot_widget.clear_triangle_overlay()
                self._set_overlay_perf_notice("")
                return

            # Resolve columns from col_mapping.
            col_map = getattr(mw, 'col_mapping', {}) if hasattr(mw, "col_mapping") else {}
            id_col = col_map.get("ID")
            x_col = col_map.get("x")
            y_col = col_map.get("y")
            if not id_col or id_col not in fdata.columns:
                id_col = fdata.columns[0] if len(fdata.columns) > 0 else None
            if not id_col or x_col not in fdata.columns or y_col not in fdata.columns:
                self.plot_widget.clear_triangle_overlay()
                self._set_overlay_perf_notice("")
                return

            cap = max(1, int(self._triangle_overlay_cap))
            selected_total = len(triangle_indices)
            selected_for_render = triangle_indices[:cap]
            capped = selected_total > len(selected_for_render)

            t_map0 = time.perf_counter()
            coord_map_by_id = {}
            coord_map_by_member = {}
            try:
                id_vals = fdata[id_col].astype(str).to_numpy()
                row_keys = fdata.index.astype(str).to_numpy()
                x_vals = fdata[x_col].to_numpy()
                y_vals = fdata[y_col].to_numpy()
                for pid, rkey, x, y in zip(id_vals, row_keys, x_vals, y_vals):
                    try:
                        xy = (float(x), float(y))
                        mkey = f"{str(pid)}::{str(rkey)}"
                        coord_map_by_member[mkey] = xy
                        # First-seen fallback by ID for cases without row labels.
                        coord_map_by_id.setdefault(str(pid), xy)
                    except Exception:
                        continue
            except Exception:
                coord_map_by_id = {}
                coord_map_by_member = {}
            map_ms = (time.perf_counter() - t_map0) * 1000.0

            overlay_data = []
            unresolved = 0
            for idx in selected_for_render:
                if idx < 0 or idx >= len(combined):
                    continue
                tri = combined.iloc[idx]

                point_ids = tri.get("point_ids", None)
                if point_ids is None:
                    continue
                if not isinstance(point_ids, (list, tuple)):
                    try:
                        import numpy as _np
                        if isinstance(point_ids, _np.ndarray):
                            point_ids = list(point_ids)
                        else:
                            continue
                    except Exception:
                        continue

                row_labels = tri.get("point_row_labels", None)
                row_labels_seq = (
                    list(row_labels)
                    if isinstance(row_labels, (list, tuple, np.ndarray)) and len(row_labels) == len(point_ids)
                    else None
                )
                coords = []
                for j, pt_id in enumerate(point_ids):
                    xy = None
                    if row_labels_seq is not None:
                        mkey = f"{str(pt_id)}::{str(row_labels_seq[j])}"
                        xy = coord_map_by_member.get(mkey)
                    if xy is None:
                        xy = coord_map_by_id.get(str(pt_id))
                    if xy is not None:
                        coords.append(xy)
                if len(coords) == 3:
                    status = str(tri.get('status', 'kept')).lower()
                    overlay_data.append({
                        'point_coords': coords,
                        'point_ids': point_ids,
                        'status': status,
                        'gradient': tri.get('gradient', None),
                        'angle': tri.get('angle', None),
                        'centroid_x': tri.get('centroid_x', None),
                        'centroid_y': tri.get('centroid_y', None),
                    })
                else:
                    unresolved += 1

            t_draw0 = time.perf_counter()
            if overlay_data:
                self.plot_widget.highlight_triangles(overlay_data)
            else:
                self.plot_widget.clear_triangle_overlay()
            draw_call_ms = (time.perf_counter() - t_draw0) * 1000.0

            if capped:
                self._set_overlay_perf_notice(
                    f"Overlay limited: {len(overlay_data)}/{selected_total}"
                )
            else:
                self._set_overlay_perf_notice("")

            total_ms = (time.perf_counter() - t0) * 1000.0
            prep_ms = max(0.0, total_ms - map_ms - draw_call_ms)
            self._perf_log(
                f"[perf][triangle-overlay] selected={selected_total} rendered={len(overlay_data)} "
                f"cap={cap} capped={capped} unresolved={unresolved} points={len(coord_map_by_member)} "
                f"map={map_ms:.1f}ms prep={prep_ms:.1f}ms draw_call={draw_call_ms:.1f}ms total={total_ms:.1f}ms"
            )
        except Exception:
            self.plot_widget.clear_triangle_overlay()
            self._set_overlay_perf_notice("")

    def _update_drawer_row_count(self):
        """Update the drawer header row count chip based on current mode."""
        try:
            if self._drawer_stack.currentIndex() == 0:
                # Data mode
                total = self.data_table.model.rowCount()
                shown = self.data_table.proxy_model.rowCount()
                if total == 0:
                    self.drawer_row_count.setText("0 rows")
                elif shown == total:
                    self.drawer_row_count.setText(f"{total} rows")
                else:
                    self.drawer_row_count.setText(f"{shown} of {total}")
            else:
                # Triangle mode
                if self._triangle_table is not None:
                    visible = self._triangle_table._proxy.rowCount()
                    loaded = self._triangle_table._model.rowCount()
                    total = getattr(self._triangle_table._model, "total_count", loaded)
                    if total > loaded:
                        self.drawer_row_count.setText(f"{visible} of {total} triangles")
                    else:
                        self.drawer_row_count.setText(f"{visible} triangles")
                else:
                    self.drawer_row_count.setText("0 triangles")
        except Exception:
            pass

    # ──────────────────────────────────────────────────
    #  HANDLERS
    # ──────────────────────────────────────────────────

    def _on_plot_type_changed(self, text: str):
        """Handle plot type change from toolbar."""
        internal_type = normalize_plot_type(text)

        # Record the new type on the active cell so it persists across cell switches
        try:
            self._grid_area.active_cell.save_state(
                internal_type,
                self._grid_area.active_cell.settings,
            )
        except Exception:
            pass

        # Update sidebar to show appropriate options
        self.plot_sidebar.set_plot_type(internal_type)

        # Update hint bar for the new plot type
        self.plot_widget.set_hint_plot_type(internal_type)

        # Clear triangle overlay on plot type change
        self.plot_widget.clear_triangle_overlay()
        self._set_overlay_perf_notice("")

        # Rose Diagram looks best with the radial grid on — auto-activate the
        # Grid pill when entering Rose so the toolbar reflects what gets drawn.
        if internal_type == "Rose Diagram":
            self.grid_checkbox.blockSignals(True)
            self.grid_checkbox.setChecked(True)
            self.grid_checkbox.blockSignals(False)
            self.main_window.show_grid = True

        # Emit signal for main window
        self.plot_type_changed.emit(internal_type)

    def _on_visualization_changed(self, options: dict):
        """Handle signal from sidebar toggles: points, contours, grid, etc."""
        # Update main window state
        self.main_window.show_points = bool(options.get("points", True))
        self.main_window.show_vector_points = self.main_window.show_points
        self.main_window.show_contours = bool(options.get("contours", False))
        self.main_window.show_grid = bool(options.get("grid", False))
        self.main_window.show_id_labels = bool(options.get("labels", True))
        self.main_window.show_head_labels = bool(options.get("head_labels", True))
        self.main_window.show_compass = bool(options.get("compass", True))
        self.main_window.show_legend = bool(options.get("legend", False))

        # Check existing data
        data = getattr(self.main_window, "filtered_plot_data", None)
        if data is None:
            data = getattr(self.main_window, "filtered_data", None)
        if data is None:
            data = getattr(self.main_window, "data", None)

        if data is not None and not data.empty:
            current_type = self._grid_area.active_cell.plot_type
            self.plot_widget.update_plot(data, current_type)

    def _save_active_cell_pill(self, attr: str, value: bool) -> None:
        """Persist a single pill flag onto the active cell's stored mw_state."""
        try:
            cell = self._grid_area.active_cell
            if not cell.mw_state:
                cell.snapshot_mw_state(self.main_window)
            cell.mw_state[attr] = bool(value)
        except Exception:
            pass

    def _on_grid_changed(self, state):
        v = (state == Qt.Checked)
        self.main_window.show_grid = v
        self._save_active_cell_pill("show_grid", v)
        self.main_window.update_plot()

    def _on_legend_changed(self, state):
        v = (state == Qt.Checked)
        self.main_window.show_legend = v
        self._save_active_cell_pill("show_legend", v)
        self.main_window.update_plot()

    def _on_compass_changed(self, state):
        v = (state == Qt.Checked)
        self.main_window.show_compass = v
        self._save_active_cell_pill("show_compass", v)
        self.main_window.update_plot()

    def _on_dark_canvas_changed(self, checked: bool):
        # Dark canvas lives on each PlotWidget (``_dark_canvas``) — per-cell by
        # construction. Just flip the active cell's widget; other cells keep
        # whatever dark state they had.
        self.plot_widget.set_dark_canvas(bool(checked))
        self.main_window.update_plot()

    def _save_active_cell_visual_composition(self) -> None:
        try:
            cell = self._grid_area.active_cell
            if not cell.mw_state:
                cell.snapshot_mw_state(self.main_window)
            for key in (
                "current_plot_template",
                "current_color_style",
                "current_plot_format",
                "current_plot_style",
                "current_popup_style",
                "colormap_2d",
                "colormap_3d",
                "colormap_vectors",
                "histogram_bar_color",
                "histogram_edge_color",
                "rose_color",
                "id_label_color",
                "head_label_color",
                "arrow_color",
            ):
                cell.mw_state[key] = getattr(self.main_window, key, None)
            cell.save_state(cell.plot_type, self.plot_sidebar.get_settings_snapshot())
        except Exception:
            pass

    def _persist_visual_composition_to_dataset(self) -> None:
        try:
            dataset = self.main_window.get_active_dataset()
            if dataset is not None:
                self.main_window.sync_to_dataset(dataset)
        except Exception:
            pass

    def _on_format_combo_changed(self, _idx: int):
        format_key = self._combo_data(getattr(self, "format_combo", None), "Default")
        self._on_style_changed(format_key)

    def _on_palette_combo_changed(self, _idx: int):
        combo = getattr(self, "palette_combo", None)
        if combo is None:
            return
        self._apply_palette_key(self._combo_data(combo, "hydraulic"))

    def _apply_palette_key(self, palette_key: str):
        from styles.plot_palettes import apply_palette_to_target

        settings = apply_palette_to_target(self.main_window, palette_key, self.main_window.current_plot_type).settings_for(
            self.main_window.current_plot_type
        )
        self.plot_sidebar.update_from_settings(settings)
        self._save_active_cell_visual_composition()
        self._persist_visual_composition_to_dataset()
        self._refresh_appearance_button()
        self.main_window.update_plot()

    def _on_style_changed(self, style_name):
        # Compatibility handler: "style" now means plot format.
        self.main_window.current_plot_format = style_name
        self.main_window.current_plot_style = style_name
        self._save_active_cell_visual_composition()
        self._persist_visual_composition_to_dataset()
        self._refresh_appearance_button()
        self.main_window.update_plot()

    def _on_layout_preset_clicked(self, preset: int) -> None:
        """Switch the grid to a new layout preset and update button state."""
        # Snapshot the current sidebar AND mw_state into the active cell before
        # the rebuild — set_layout_preset will use this as the inheritance seed
        # for any newly-introduced cells.
        self._on_save_cell_state()
        self._grid_area.set_layout_preset(preset)
        # Process pending layout / resize events so reparented widgets (cell 0
        # from the previous layout) report their NEW canvas size by the time
        # update_plot reads it. Without this flush, font scaling computes
        # against the cell's pre-rebuild width and the active cell renders
        # with the wrong (too-large or too-small) font set.
        try:
            from PyQt5.QtWidgets import QApplication
            from PyQt5.QtCore import QEventLoop
            QApplication.processEvents(QEventLoop.ExcludeUserInputEvents)
        except Exception:
            pass
        # Route through main_window.update_plot so the multi-cell render swap
        # fires; each cell renders with its own (just-inherited) mw_state.
        try:
            self.main_window.update_plot()
        except Exception:
            pass
        # Layout count changed — refresh the cell scope chip (it hides itself
        # for 1×1 layouts and shows "of M" with the new total otherwise).
        try:
            if hasattr(self.main_window, "update_cell_scope_chip"):
                self.main_window.update_cell_scope_chip()
        except Exception:
            pass
        self._sync_layout_btn_state()

    # ──────────────────────────────────────────────────
    #  PUBLIC API
    # ──────────────────────────────────────────────────

    def update_plot(self, data, plot_type):
        """Render every grid cell using its own filter + pill state.

        For each cell we temporarily swap main_window's per-cell attributes
        (filter inputs/outputs + Legend/Grid/Compass/Dark flags) to that
        cell's stored values, render, then restore the active cell's state.
        This keeps every existing draw-time consumer (PlotWidget reads
        ``main_window.show_legend``, ``filtered_plot_data``, etc.) correct
        per cell without any changes to those consumers.

        The active cell adopts the incoming ``plot_type`` argument so the
        toolbar "switch to X" path keeps working.
        """
        _perf = self._perf_tic("PlotPage.update_plot")
        mw = self.main_window
        # Persist the requested type on the active cell so the next cell-switch
        # / repaint uses it (matches how _on_plot_type_changed normally records it).
        try:
            active = self._grid_area.active_cell
            active.save_state(plot_type, active.settings)
        except Exception:
            pass
        # Capture mw's current per-cell state. After we render each cell we'll
        # restore from this snapshot so any consumer that runs after update_plot
        # (stats, map, etc.) sees the active cell's view.
        active_snapshot = {}
        try:
            for key in self._grid_area.active_cell.MW_KEYS:
                v = getattr(mw, key, None)
                if isinstance(v, set):
                    v = set(v)
                active_snapshot[key] = v
        except Exception:
            active_snapshot = {}
        # Render each cell in its own plot_type with its own mw_state swapped in.
        try:
            cells = self._grid_area.cells
        except Exception:
            cells = []
        # Snapshot the *sidebar-driven* mw attributes too (colormaps, point
        # size, contour levels, etc.) so we can restore them after the loop.
        active_settings_snapshot = {}
        try:
            for sk, mk in self._SETTINGS_TO_MW.items():
                if hasattr(mw, mk):
                    active_settings_snapshot[mk] = getattr(mw, mk)
        except Exception:
            active_settings_snapshot = {}
        # Render INACTIVE cells first, swapping mw to each cell's stored state.
        # Then restore active state and render the active cell LAST. This avoids
        # overwriting mw with stale ``cell.settings`` for the active cell — its
        # settings dict is only refreshed on switch-away, so user edits made
        # since the last switch live ONLY on ``mw``, not in ``cell.settings``.
        active_cell = None
        try:
            active_cell = self._grid_area.active_cell
        except Exception:
            active_cell = None
        for cell in cells:
            if cell is active_cell:
                continue
            try:
                if cell.mw_state:
                    cell.apply_to_mw(mw)
                if cell.settings:
                    self._apply_settings_to_mw(cell.settings)
                cell_data = getattr(mw, "filtered_plot_data", None)
                if cell_data is None or getattr(cell_data, "empty", True):
                    cell_data = getattr(mw, "filtered_data", None)
                if cell_data is None or getattr(cell_data, "empty", True):
                    cell_data = data
                cell.plot_widget.update_plot(cell_data, cell.plot_type)
            except Exception:
                pass
        # Restore mw to active cell's working state (the snapshot taken at the
        # top of update_plot — i.e. what the user sees in the sidebar/sliders
        # right now). All subsequent reads of mw will see this.
        for key, v in active_snapshot.items():
            try: setattr(mw, key, v)
            except Exception: pass
        for key, v in active_settings_snapshot.items():
            try: setattr(mw, key, v)
            except Exception: pass
        # Render the active cell last, using mw's current (live-edited) state.
        if active_cell is not None:
            try:
                cell_data = getattr(mw, "filtered_plot_data", None)
                if cell_data is None or getattr(cell_data, "empty", True):
                    cell_data = getattr(mw, "filtered_data", None)
                if cell_data is None or getattr(cell_data, "empty", True):
                    cell_data = data
                active_cell.plot_widget.update_plot(cell_data, active_cell.plot_type)
            except Exception:
                pass
        if getattr(self, "quick_stats_btn", None) is not None and self.quick_stats_btn.isChecked():
            try:
                self.quick_stats_panel.update_from_app()
            except Exception:
                pass
        self._perf_toc(_perf)

    def clear_plot(self):
        # Clear every cell so a "new dataset" wipes the whole grid.
        try:
            for cell in self._grid_area.cells:
                try:
                    cell.plot_widget.clear_plot()
                except Exception:
                    pass
        except Exception:
            # Fallback if grid area not yet built
            self.plot_widget.clear_plot()

    # ──────────────────────────────────────────────────
    #  Cross-cell helpers — broadcast to every cell so that
    #  cross-widget interactions (map clicks, table row selection
    #  from main_window, exclusion-filter refresh) update every
    #  visible plot, not just the one currently focused.
    # ──────────────────────────────────────────────────

    def highlight_point_by_id_all(self, point_id) -> None:
        """Highlight `point_id` on every grid cell."""
        try:
            for cell in self._grid_area.cells:
                try:
                    cell.plot_widget.highlight_point_by_id(str(point_id))
                except Exception:
                    pass
        except Exception:
            try:
                self.plot_widget.highlight_point_by_id(str(point_id))
            except Exception:
                pass

    def clear_point_highlight_all(self) -> None:
        """Clear point highlight on every grid cell."""
        try:
            for cell in self._grid_area.cells:
                try:
                    cell.plot_widget.clear_point_highlight()
                except Exception:
                    pass
        except Exception:
            try:
                self.plot_widget.clear_point_highlight()
            except Exception:
                pass

    def set_dataset_id(self, dataset_id) -> None:
        """Tag every current and future plot widget with this dataset_id.

        ``_dataset_id`` is read by ``PlotWidget`` when constructing the
        GeoDK panel (so the dataset context is correct regardless of which
        cell triggers the action). main_window calls this once per dataset
        tab creation; subsequent ``GridPlotArea._ensure_widgets`` re-applies
        it to lazily-created cells via the ``_on_new_plot_widget`` hook.
        """
        sid = str(dataset_id)
        self._dataset_id = sid
        try:
            for pw in getattr(self._grid_area, "_plot_widgets", []):
                try:
                    pw._dataset_id = sid
                except Exception:
                    pass
        except Exception:
            try:
                self.plot_widget._dataset_id = sid
            except Exception:
                pass

    def _init_new_plot_widget(self, pw) -> None:
        """Hook for GridPlotArea — apply page-level state to a fresh PlotWidget."""
        sid = getattr(self, "_dataset_id", None)
        if sid is not None:
            try:
                pw._dataset_id = sid
            except Exception:
                pass

    def refresh_2d_labels_only_all(self) -> bool:
        """Refresh 2-D labels on every cell. Returns True if *any* cell handled it."""
        ok_any = False
        try:
            for cell in self._grid_area.cells:
                try:
                    if cell.plot_type == "2D" and bool(cell.plot_widget.refresh_2d_labels_only()):
                        ok_any = True
                except Exception:
                    pass
        except Exception:
            try:
                ok_any = bool(self.plot_widget.refresh_2d_labels_only())
            except Exception:
                ok_any = False
        return ok_any

    def export_plot(self, file_path):
        """Export the current view.

        For a multi-cell grid, captures the full splitter tree (composite of
        all visible plots, splitter handles included) using ``QWidget.grab()``.
        For a 1×1 layout, defers to the active cell's matplotlib ``savefig``
        path so the report generator's high-DPI behavior is preserved.
        """
        try:
            preset = self._grid_area.current_preset()
        except Exception:
            preset = 1
        if preset == 1:
            self.plot_widget.export_plot(file_path)
            return
        try:
            pix = self._grid_area.grab()
            if not pix.isNull():
                pix.save(str(file_path))
                return
        except Exception:
            pass
        # Fallback: active cell only
        self.plot_widget.export_plot(file_path)

    def set_data(self, data):
        """Set data in the table."""
        self.data_table.set_data(data)
        # Update drawer header row count
        try:
            count = len(data) if data is not None and not data.empty else 0
            self.drawer_row_count.setText(f"{count} rows")
        except Exception:
            pass
        # Refresh triangle table data if it exists
        self._refresh_triangle_table_data()

    def clear_data(self):
        self.data_table.clear_data()
        self._set_overlay_perf_notice("")

    def apply_theme(self):
        metrics = build_screen_metrics(self)
        self._sidebar_width = metrics.plot_sidebar_width
        self.setStyleSheet(f"background-color: {Colors.BG_PANEL};")
        self._rebuild_toolbar()
        self.table_container.setStyleSheet(f"""
            QWidget#tableContainer {{
                border-top: 1px solid {Colors.BORDER_DEFAULT};
            }}
        """)

        for btn in (self._data_mode_btn, self._tri_mode_btn):
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    border: 1px solid transparent;
                    border-radius: 4px;
                    padding: 0 10px;
                    font-size: 10px;
                    font-weight: 600;
                    color: {Colors.TEXT_TERTIARY};
                }}
                QPushButton:hover {{
                    color: {Colors.TEXT_SECONDARY};
                    background-color: {Colors.BG_HOVER};
                }}
                QPushButton:checked {{
                    background-color: {Colors.BG_SURFACE};
                    color: {Colors.TEXT_PRIMARY};
                    border-color: {Colors.BORDER_MEDIUM};
                }}
            """)

        self.drawer_header.setStyleSheet(StyleSheet.get_drawer_header_style())
        self.drawer_drag_pill.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.BORDER_STRONG};
                border-radius: 2px;
                border: none;
            }}
        """)
        self.drawer_row_count.setStyleSheet(f"""
            QLabel {{
                color: {Colors.TEXT_TERTIARY};
                font-size: 10px;
                font-weight: 600;
                padding: 2px 9px;
                background-color: {Colors.BG_SURFACE};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 100px;
                letter-spacing: 0.2px;
            }}
        """)
        self.drawer_perf_notice.setStyleSheet(f"""
            QLabel {{
                color: {Colors.WARNING};
                font-size: 10px;
                font-weight: 700;
                padding: 2px 8px;
                background-color: {Colors.BG_SURFACE};
                border: 1px solid {Colors.WARNING};
                border-radius: 100px;
            }}
        """)

        self.plot_widget.apply_theme()
        self.plot_sidebar.apply_theme()
        self.plot_sidebar.setMinimumWidth(self._sidebar_width)
        self.plot_sidebar.setMaximumWidth(self._sidebar_width)
        self._sync_sidebar_overlay_geometry(x=0 if self.sidebar_visible else -int(self._sidebar_width))
        self.data_table.apply_theme()
        self.quick_stats_panel.apply_theme()
