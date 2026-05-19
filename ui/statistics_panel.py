"""
HeadAnalyser V2 - Statistics Panel
Premium dashboard-style statistics display with rejection analysis and comparison placeholder.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QScrollArea, QGridLayout, QPushButton, QSizePolicy,
    QSpacerItem, QGroupBox, QSplitter,
)
from PyQt5.QtCore import Qt, pyqtSignal, QRect
from PyQt5.QtGui import QFont, QPainter, QColor, QPainterPath, QPen
import time
import numpy as np
import pandas as pd

from styles.colors import Colors
from ui.triangle_widgets.triangle_data_helper import TriangleDataHelper
from ui.triangle_widgets.summary_cards import TriangleSummaryCards
from ui.triangle_widgets.breakdown_bars import RejectionBreakdownBars
from ui.triangle_widgets.point_frequency import PointFrequencyBars
from ui.triangle_widgets.triangle_table import TriangleTableWidget
from ui.triangle_widgets.geometry_plot import TriangleGeometryPlot
from ui.head_gradient_statistics import HeadStatisticsWidget, GradientStatisticsWidget
from ui.theme_utils import reset_widget_layout


class MetricCard(QWidget):
    """Compact metric display card with colored left-edge bar."""

    def __init__(self, label: str, color: str = Colors.ACCENT_PRIMARY, parent=None):
        super().__init__(parent)
        self._bar_color = QColor(color)
        self.setMinimumWidth(120)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setAttribute(Qt.WA_StyledBackground, True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        # Label
        title = QLabel(label)
        title.setStyleSheet(f"""
            color: {Colors.TEXT_TERTIARY};
            font-size: 9px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.8px;
            background: transparent;
            border: none;
        """)
        layout.addWidget(title)

        # Value
        self.value_label = QLabel("-")
        self.value_label.setStyleSheet(f"""
            color: {Colors.TEXT_PRIMARY};
            font-size: 18px;
            font-weight: 600;
            background: transparent;
            border: none;
        """)
        layout.addWidget(self.value_label)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw card background with rounded corners
        rect = self.rect()
        path = QPainterPath()
        path.addRoundedRect(float(rect.x()), float(rect.y()),
                            float(rect.width()), float(rect.height()), 6.0, 6.0)

        # Fill background
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(Colors.BG_PANEL))
        painter.drawPath(path)

        # Draw subtle border
        border_color = QColor(255, 255, 255, 18)  # ~7% white
        painter.setPen(QPen(border_color, 1.0))
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(path)

        # Draw full-height colored left bar
        painter.setPen(Qt.NoPen)
        painter.setBrush(self._bar_color)
        painter.drawRoundedRect(QRect(0, 0, 3, self.height()), 1.5, 1.5)

        painter.end()

    def set_value(self, value: str):
        self.value_label.setText(value)


class ProgressBar(QWidget):
    """Simple horizontal progress bar for visualizing proportions."""

    def __init__(self, label: str, color: str, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        self.color = color
        self._percentage = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(4)

        # Label row
        label_row = QHBoxLayout()
        label_row.setSpacing(8)

        self.title = QLabel(label)
        self.title.setStyleSheet(f"""
            color: {Colors.TEXT_SECONDARY};
            font-size: 10px;
            background: transparent;
        """)
        label_row.addWidget(self.title)

        label_row.addStretch()

        self.count_label = QLabel("0")
        self.count_label.setStyleSheet(f"""
            color: {Colors.TEXT_PRIMARY};
            font-size: 10px;
            font-weight: 600;
            background: transparent;
        """)
        label_row.addWidget(self.count_label)

        layout.addLayout(label_row)

        # Progress bar container
        bar_container = QWidget()
        bar_container.setFixedHeight(6)
        bar_container.setStyleSheet(f"""
            background-color: {Colors.BG_SURFACE};
            border-radius: 3px;
        """)

        bar_layout = QHBoxLayout(bar_container)
        bar_layout.setContentsMargins(0, 0, 0, 0)
        bar_layout.setSpacing(0)

        self.bar = QWidget()
        self.bar.setFixedHeight(6)
        self.bar.setStyleSheet(f"""
            background-color: {color};
            border-radius: 3px;
        """)
        bar_layout.addWidget(self.bar)
        bar_layout.addStretch()

        layout.addWidget(bar_container)

    def set_value(self, count: int, total: int):
        self.count_label.setText(str(count))
        if total > 0:
            pct = (count / total) * 100
            # Set width as percentage (minimum 2% when > 0 for visibility)
            width_pct = max(2, pct) if count > 0 else 0
            self.bar.setFixedWidth(int(self.width() * width_pct / 100))
        else:
            self.bar.setFixedWidth(0)


class SectionIconBox(QWidget):
    """Small colored icon indicator for collapsible section headers."""

    def __init__(self, color: str, parent=None):
        super().__init__(parent)
        self.setFixedSize(20, 20)
        self._color = QColor(color)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        bg = QColor(self._color)
        bg.setAlpha(25)
        painter.setPen(Qt.NoPen)
        painter.setBrush(bg)
        painter.drawRoundedRect(0, 0, 20, 20, 5, 5)
        painter.setBrush(self._color)
        painter.drawEllipse(6, 6, 8, 8)
        painter.end()


class CollapsibleSection(QWidget):
    """Collapsible section as a unified card with colored icon indicator."""

    def __init__(self, title: str, icon_color: str = None, parent=None):
        super().__init__(parent)
        self._expanded = True
        self._title_text = title
        self.setAttribute(Qt.WA_StyledBackground, True)

        # Card container styling
        self.setStyleSheet(f"""
            CollapsibleSection {{
                background-color: {Colors.BG_PANEL};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 6px;
            }}
            CollapsibleSection:hover {{
                border-color: {Colors.BORDER_MEDIUM};
            }}
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # --- Header row (clickable) ---
        self.header_widget = QWidget()
        self.header_widget.setCursor(Qt.PointingHandCursor)
        self.header_widget.setStyleSheet("background: transparent;")
        header_layout = QHBoxLayout(self.header_widget)
        header_layout.setContentsMargins(14, 9, 14, 9)
        header_layout.setSpacing(8)

        # Colored icon box
        if icon_color:
            self._icon_box = SectionIconBox(icon_color)
            header_layout.addWidget(self._icon_box)

        # Title label
        self._title_label = QLabel(title)
        self._title_label.setStyleSheet(f"""
            color: {Colors.TEXT_PRIMARY};
            font-size: 11px;
            font-weight: 600;
            background: transparent;
        """)
        header_layout.addWidget(self._title_label)
        header_layout.addStretch()

        # Chevron
        self._chevron = QLabel("\u25bc")
        self._chevron.setStyleSheet(f"""
            color: {Colors.TEXT_MUTED};
            font-size: 10px;
            background: transparent;
        """)
        header_layout.addWidget(self._chevron)

        main_layout.addWidget(self.header_widget)

        # --- Separator ---
        self._separator = QFrame()
        self._separator.setFixedHeight(1)
        self._separator.setStyleSheet(f"background-color: {Colors.BORDER_SUBTLE}; border: none; margin: 0;")
        main_layout.addWidget(self._separator)

        # --- Content area ---
        self.content = QWidget()
        self.content.setStyleSheet("background: transparent;")
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(12, 10, 12, 12)
        self.content_layout.setSpacing(8)

        main_layout.addWidget(self.content)

        # Connect click
        self.header_widget.mousePressEvent = lambda e: self._toggle()

    def _toggle(self):
        self._expanded = not self._expanded
        self.content.setVisible(self._expanded)
        self._separator.setVisible(self._expanded)
        self._chevron.setText("\u25bc" if self._expanded else "\u25b6")

    def add_widget(self, widget):
        self.content_layout.addWidget(widget)


class StatisticsPanel(QWidget):
    """Premium statistics dashboard with responsive layout."""

    open_inspector_requested = pyqtSignal()
    export_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background-color: {Colors.BG_DARK};")
        self._derived_cache_key = None
        self._derived_cache = {}
        self._bound_table_key = None
        self._bound_geometry_key = None
        self._last_app_context = None
        self._setup_ui()

    @staticmethod
    def _stats_perf_log(app, message: str):
        logger = getattr(app, "_perf_log", None)
        if callable(logger):
            logger(message)
        else:
            print(message, flush=True)

    @staticmethod
    def _safe_len(df) -> int:
        try:
            return int(len(df)) if df is not None else 0
        except Exception:
            return 0

    def _build_derived_cache_key(self, app, total_triangles):
        tri = getattr(app, "triangle_data", None)
        rej = getattr(app, "rejected_data", None)
        grad = getattr(app, "gradient_data", None)
        fdata = getattr(app, "filtered_data", None)
        cmap = getattr(app, "col_mapping", {}) or {}
        try:
            cmap_key = tuple(sorted((str(k), str(v)) for k, v in cmap.items()))
        except Exception:
            cmap_key = tuple()
        return (
            id(tri), self._safe_len(tri),
            id(rej), self._safe_len(rej),
            id(grad), self._safe_len(grad),
            id(fdata), self._safe_len(fdata),
            int(total_triangles) if isinstance(total_triangles, (int, np.integer)) else -1,
            cmap_key,
        )

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Header
        header = QWidget()
        header.setFixedHeight(42)
        header.setStyleSheet(f"""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 {Colors.BG_ELEVATED},
                stop:1 {Colors.BG_SURFACE});
            border-bottom: 1px solid {Colors.BORDER_DEFAULT};
        """)

        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(14, 0, 14, 0)

        title = QLabel("Statistics Dashboard")
        title.setStyleSheet(f"""
            color: {Colors.TEXT_PRIMARY};
            font-size: 13px;
            font-weight: 700;
            background: transparent;
        """)
        header_layout.addWidget(title)

        header_layout.addStretch()

        # Compare dropdown placeholder
        self.compare_btn = QPushButton("Compare \u25be")
        self.compare_btn.setEnabled(False)
        self.compare_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.BG_SURFACE};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: {Colors.RADIUS_XS};
                color: {Colors.TEXT_TERTIARY};
                font-size: 11px;
                padding: 6px 12px;
            }}
            QPushButton:disabled {{
                color: {Colors.TEXT_TERTIARY};
            }}
        """)
        self.compare_btn.setToolTip("Comparison feature coming soon")
        header_layout.addWidget(self.compare_btn)

        main_layout.addWidget(header)

        # Scroll area for content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet(f"background-color: {Colors.BG_DARK};")

        scroll_content = QWidget()
        scroll_content.setStyleSheet(f"background-color: {Colors.BG_DARK};")
        content_layout = QVBoxLayout(scroll_content)
        content_layout.setContentsMargins(14, 14, 14, 14)
        content_layout.setSpacing(10)

        # KEY METRICS BAR
        metrics_row = QHBoxLayout()
        metrics_row.setSpacing(12)

        self.metric_points = MetricCard("Data Points", color=Colors.INFO)
        metrics_row.addWidget(self.metric_points)

        self.metric_triangles = MetricCard("Triangles (valid/total)", color=Colors.SUCCESS)
        metrics_row.addWidget(self.metric_triangles)

        self.metric_rejected = MetricCard("Rejected", color=Colors.ERROR)
        metrics_row.addWidget(self.metric_rejected)

        content_layout.addLayout(metrics_row)

        # HEAD STATISTICS SECTION
        head_section = CollapsibleSection("Head Statistics", icon_color=Colors.INFO)
        self.head_stats_widget = HeadStatisticsWidget()
        head_section.add_widget(self.head_stats_widget)

        content_layout.addWidget(head_section)

        # GRADIENT STATISTICS SECTION
        gradient_section = CollapsibleSection("Gradient Statistics", icon_color=Colors.SUCCESS)
        self.gradient_stats_widget = GradientStatisticsWidget()
        gradient_section.add_widget(self.gradient_stats_widget)

        content_layout.addWidget(gradient_section)

        # TRIANGLE ANALYSIS SECTION (full two-column layout)
        triangle_section = CollapsibleSection("Triangle Analysis", icon_color=Colors.ERROR)

        # Summary cards row
        self.tri_summary = TriangleSummaryCards()
        triangle_section.add_widget(self.tri_summary)

        # Two-column body: left = plot + frequency, right = table + rejection breakdown
        body_splitter = QSplitter(Qt.Horizontal)
        body_splitter.setHandleWidth(4)
        body_splitter.setChildrenCollapsible(False)
        body_splitter.setStyleSheet(f"""
            QSplitter::handle {{
                background-color: {Colors.BORDER_MEDIUM};
                width: 4px;
            }}
            QSplitter::handle:hover {{
                background-color: {Colors.ACCENT_PRIMARY};
            }}
        """)

        # --- Left column ---
        left_col = QWidget()
        left_col.setStyleSheet("background: transparent;")
        left_col.setMinimumWidth(300)
        left_layout = QVBoxLayout(left_col)
        left_layout.setContentsMargins(0, 8, 6, 0)
        left_layout.setSpacing(12)

        self.tri_geometry = TriangleGeometryPlot()
        self.tri_geometry.setMinimumHeight(250)
        left_layout.addWidget(self.tri_geometry, 3)

        self.tri_frequency = PointFrequencyBars()
        left_layout.addWidget(self.tri_frequency, 2)

        body_splitter.addWidget(left_col)

        # --- Right column ---
        right_col = QWidget()
        right_col.setStyleSheet("background: transparent;")
        right_col.setMinimumWidth(320)
        right_layout = QVBoxLayout(right_col)
        right_layout.setContentsMargins(6, 8, 0, 0)
        right_layout.setSpacing(8)

        table_title = QLabel("TRIANGLE TABLE")
        table_title.setStyleSheet(f"""
            color: {Colors.TEXT_TERTIARY};
            font-size: 10px; font-weight: 700;
            text-transform: uppercase; letter-spacing: 0.7px;
            background: transparent;
        """)
        right_layout.addWidget(table_title)

        self.tri_table = TriangleTableWidget()
        right_layout.addWidget(self.tri_table, 1)

        self.tri_breakdown = RejectionBreakdownBars()
        right_layout.addWidget(self.tri_breakdown)

        body_splitter.addWidget(right_col)
        body_splitter.setSizes([400, 500])

        # Set a minimum height for the body so it's usable (enough room for frequency bars)
        body_splitter.setMinimumHeight(560)
        triangle_section.add_widget(body_splitter)

        # Connect hover sync: table row → geometry highlight
        self.tri_table.triangle_hovered.connect(self.tri_geometry.highlight_triangle)

        # Connect filter sync: table filter pills → geometry plot
        self.tri_table.filter_changed.connect(self.tri_geometry.set_filter_mode)

        # Connect frequency bar selection → inspector button label
        self._frequency_selected_ids = set()
        self.tri_frequency.selection_changed.connect(self._on_frequency_selection_changed)

        # Buttons row
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 8, 0, 0)
        btn_row.setSpacing(10)

        self.export_btn = QPushButton("Export Rejected Data")
        self.export_btn.setEnabled(False)
        self.export_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.BG_ELEVATED};
                border: 2px solid {Colors.BORDER_DEFAULT};
                border-radius: {Colors.RADIUS_XS};
                color: {Colors.TEXT_SECONDARY};
                font-size: 11px;
                font-weight: 600;
                padding: 8px 16px;
            }}
            QPushButton:hover:enabled {{
                border-color: {Colors.ACCENT_PRIMARY};
                color: {Colors.ACCENT_PRIMARY};
            }}
            QPushButton:disabled {{
                color: {Colors.TEXT_TERTIARY};
            }}
        """)
        self.export_btn.setToolTip("Export rejected triangles to CSV")
        self.export_btn.clicked.connect(self.export_requested.emit)
        btn_row.addWidget(self.export_btn)

        self.open_inspector_btn = QPushButton("Inspect Selected Points")
        self.open_inspector_btn.setEnabled(False)
        self.open_inspector_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.ACCENT_GHOST};
                border: 1px solid {Colors.BORDER_ACCENT};
                border-radius: {Colors.RADIUS_XS};
                color: {Colors.TEXT_ACCENT};
                font-size: 11px;
                font-weight: 600;
                padding: 8px 16px;
            }}
            QPushButton:hover:enabled {{
                border-color: {Colors.ACCENT_PRIMARY};
                color: {Colors.TEXT_PRIMARY};
            }}
            QPushButton:disabled {{
                color: {Colors.TEXT_TERTIARY};
            }}
        """)
        self.open_inspector_btn.setToolTip("Open Triangle Inspector filtered to selected points")
        self.open_inspector_btn.clicked.connect(self.open_inspector_requested.emit)
        btn_row.addWidget(self.open_inspector_btn)
        btn_row.addStretch()

        triangle_section.content_layout.addLayout(btn_row)

        content_layout.addWidget(triangle_section)

        # SNAPSHOT & COMPARISON SECTION (Placeholder)
        snapshot_section = CollapsibleSection("Snapshot & Comparison", icon_color=Colors.WARNING)

        info_label = QLabel(
            "Save snapshots of current statistics to compare against "
            "filtered data or other loaded datasets."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet(f"""
            color: {Colors.TEXT_TERTIARY};
            font-size: 11px;
            line-height: 1.4;
            padding: 8px;
            background-color: {Colors.BG_ELEVATED};
            border-radius: {Colors.RADIUS_XS};
            border: 1px dashed {Colors.BORDER_DEFAULT};
        """)
        snapshot_section.add_widget(info_label)

        # Placeholder buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.save_snapshot_btn = QPushButton("Save Snapshot")
        self.save_snapshot_btn.setEnabled(False)
        self.save_snapshot_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.BG_ELEVATED};
                border: 2px solid {Colors.BORDER_DEFAULT};
                border-radius: {Colors.RADIUS_XS};
                color: {Colors.TEXT_TERTIARY};
                font-size: 11px;
                font-weight: 600;
                padding: 10px 16px;
            }}
        """)
        self.save_snapshot_btn.setToolTip("Coming soon")
        btn_row.addWidget(self.save_snapshot_btn)

        self.compare_snapshots_btn = QPushButton("Compare Snapshots")
        self.compare_snapshots_btn.setEnabled(False)
        self.compare_snapshots_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.BG_ELEVATED};
                border: 2px solid {Colors.BORDER_DEFAULT};
                border-radius: {Colors.RADIUS_XS};
                color: {Colors.TEXT_TERTIARY};
                font-size: 11px;
                font-weight: 600;
                padding: 10px 16px;
            }}
        """)
        self.compare_snapshots_btn.setToolTip("Coming soon")
        btn_row.addWidget(self.compare_snapshots_btn)

        btn_row.addStretch()

        snapshot_section.content_layout.addLayout(btn_row)

        content_layout.addWidget(snapshot_section)

        # Add stretch at bottom
        content_layout.addStretch()

        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)

    def _on_frequency_selection_changed(self, selected_ids):
        """Handle frequency bar selection changes."""
        self._frequency_selected_ids = set(selected_ids) if selected_ids else set()
        n = len(self._frequency_selected_ids)
        if n > 0:
            self.open_inspector_btn.setText(f"Inspect Selected Points ({n})")
        else:
            self.open_inspector_btn.setText("Inspect Selected Points")

    def get_selected_point_ids(self) -> set:
        """Return currently selected point IDs from frequency bars."""
        return set(self._frequency_selected_ids)

    def update_statistics(self, app):
        """Update all statistics from application data."""
        self._last_app_context = app
        t0_total = time.perf_counter()
        # Key metrics
        if app.filtered_data is not None and not app.filtered_data.empty:
            self.metric_points.set_value(str(len(app.filtered_data)))
        else:
            self.metric_points.set_value("0")

        total_triangles = getattr(app, "total_triangles", None)
        rejected_count = 0
        try:
            if app.rejected_data is not None:
                rejected_count = int(len(app.rejected_data))
        except Exception:
            rejected_count = 0

        if app.triangle_data is not None and not app.triangle_data.empty:
            valid_count = int(len(app.triangle_data))
        else:
            valid_count = 0

        if isinstance(total_triangles, (int, np.integer)) and int(total_triangles) > 0:
            self.metric_triangles.set_value(f"{valid_count}/{int(total_triangles)}")
        else:
            self.metric_triangles.set_value(str(valid_count))

        # Head/gradient statistics widgets
        self.head_stats_widget.update_from_app(app)
        self.gradient_stats_widget.update_from_app(app)

        # Triangle analysis (cached derived data for fast repeated opens/tab switches)
        derived_key = self._build_derived_cache_key(app, total_triangles)
        cache_hit = (derived_key == self._derived_cache_key) and bool(self._derived_cache)

        t0_derived = time.perf_counter()
        if not cache_hit:
            summary = TriangleDataHelper.compute_summary(
                app.triangle_data, app.rejected_data, total_triangles
            )
            breakdown_primary = TriangleDataHelper.compute_reason_breakdown(app.rejected_data, mode="primary")
            breakdown_all = TriangleDataHelper.compute_reason_breakdown(app.rejected_data, mode="all")
            freq_df = TriangleDataHelper.compute_point_frequency(app.rejected_data, app.gradient_data)
            combined_df = TriangleDataHelper.build_combined_triangle_df(
                app.triangle_data, app.rejected_data
            )
            col_mapping = getattr(app, 'col_mapping', {}) or {}
            filtered_data = getattr(app, 'filtered_data', None)
            heatmap_df = TriangleDataHelper.compute_heatmap_data(freq_df, filtered_data, col_mapping)
            self._derived_cache = {
                "summary": summary,
                "breakdown_primary": breakdown_primary,
                "breakdown_all": breakdown_all,
                "freq_df": freq_df,
                "combined_df": combined_df,
                "filtered_data": filtered_data,
                "col_mapping": col_mapping,
                "heatmap_df": heatmap_df,
            }
            self._derived_cache_key = derived_key
        else:
            summary = self._derived_cache.get("summary", {})
            breakdown_primary = self._derived_cache.get("breakdown_primary", [])
            breakdown_all = self._derived_cache.get("breakdown_all", [])
            freq_df = self._derived_cache.get("freq_df", pd.DataFrame())
            combined_df = self._derived_cache.get("combined_df", pd.DataFrame())
            filtered_data = self._derived_cache.get("filtered_data", None)
            col_mapping = self._derived_cache.get("col_mapping", {})
            heatmap_df = self._derived_cache.get("heatmap_df", pd.DataFrame())
        derived_ms = (time.perf_counter() - t0_derived) * 1000.0

        self._stats_perf_log(
            app,
            f"[perf][stats] cache={'hit' if cache_hit else 'miss'} "
            f"tri={self._safe_len(getattr(app, 'triangle_data', None))} "
            f"rej={self._safe_len(getattr(app, 'rejected_data', None))} "
            f"derive={derived_ms:.1f}ms",
        )

        self.tri_summary.update_data(summary)

        rejected_count = summary.get("rejected", 0)
        if isinstance(total_triangles, (int, np.integer)) and int(total_triangles) > 0:
            self.metric_rejected.set_value(f"{rejected_count}/{int(total_triangles)}")
        else:
            self.metric_rejected.set_value(str(rejected_count))

        self.tri_breakdown.update_data(breakdown_primary, breakdown_all)
        self.tri_frequency.update_data(freq_df)

        # Update heavy widgets only when underlying derived key changed.
        table_ms = 0.0
        if self._bound_table_key != self._derived_cache_key:
            t0_table = time.perf_counter()
            self.tri_table.update_data(combined_df)
            table_ms = (time.perf_counter() - t0_table) * 1000.0
            self._bound_table_key = self._derived_cache_key

        geometry_ms = 0.0
        if self._bound_geometry_key != self._derived_cache_key:
            t0_geom = time.perf_counter()
            self.tri_geometry.update_data(combined_df, filtered_data, col_mapping, heatmap_df)
            geometry_ms = (time.perf_counter() - t0_geom) * 1000.0
            self._bound_geometry_key = self._derived_cache_key

        has_rejected = app.rejected_data is not None and not app.rejected_data.empty
        has_data = app.triangle_data is not None and not app.triangle_data.empty
        self.export_btn.setEnabled(has_rejected)
        self.open_inspector_btn.setEnabled(has_rejected or has_data)
        total_ms = (time.perf_counter() - t0_total) * 1000.0
        self._stats_perf_log(
            app,
            f"[perf][stats] update total={total_ms:.1f}ms table={table_ms:.1f}ms "
            f"geometry={geometry_ms:.1f}ms cache={'hit' if cache_hit else 'miss'}",
        )

    def _clear_head_stats(self):
        self.head_stats_widget.clear()

    def _clear_gradient_stats(self):
        self.gradient_stats_widget.clear()

    def clear_statistics(self):
        """Clear all statistics."""
        self._derived_cache_key = None
        self._derived_cache = {}
        self._bound_table_key = None
        self._bound_geometry_key = None
        self.metric_points.set_value("0")
        self.metric_triangles.set_value("0")
        self.metric_rejected.set_value("0")
        self._clear_head_stats()
        self._clear_gradient_stats()
        self.tri_summary.clear()
        self.tri_breakdown.clear()
        self.tri_frequency.clear()
        self.tri_table.clear()
        self.tri_geometry.clear()
        self.export_btn.setEnabled(False)
        self.open_inspector_btn.setEnabled(False)

    def apply_theme(self):
        reset_widget_layout(self)
        self._setup_ui()
