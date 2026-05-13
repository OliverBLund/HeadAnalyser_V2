"""
HeadAnalyser V2 - Plot Quick Stats (Layout B)

Layout B: one switchable table on the left + a details panel on the right,
separated by a visible splitter.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Dict, Iterable, List, Optional, Tuple

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QPushButton,
    QFrame,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QToolButton,
)

from styles.colors import Colors
from ui.triangle_widgets.triangle_data_helper import TriangleDataHelper
from ui.triangle_widgets.summary_cards import TriangleSummaryCards
from ui.triangle_widgets.breakdown_bars import RejectionBreakdownBars


def _iter_point_ids(value: Any) -> Iterable[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return value
    return [value]


def _angle_to_compass(angle: float) -> str:
    # 0° = E, counterclockwise
    directions = ["E", "NE", "N", "NW", "W", "SW", "S", "SE"]
    idx = round(float(angle) / 45.0) % 8
    return directions[idx]


class _MetricPill(QWidget):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(
            f"""
            QWidget {{
                background-color: {Colors.BG_SURFACE};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 8px;
            }}
            """
        )
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 6, 10, 6)
        root.setSpacing(2)

        self.title = QLabel(title)
        self.title.setStyleSheet(f"color: {Colors.TEXT_TERTIARY}; font-size: 9px; font-weight: 800;")
        root.addWidget(self.title)

        self.value = QLabel("-")
        self.value.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; font-size: 12px; font-weight: 900;")
        root.addWidget(self.value)

    def set_value(self, text: str):
        self.value.setText(text)

    def apply_theme(self):
        self.setStyleSheet(
            f"""
            QWidget {{
                background-color: {Colors.BG_SURFACE};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 8px;
            }}
            """
        )
        self.title.setStyleSheet(f"color: {Colors.TEXT_TERTIARY}; font-size: 9px; font-weight: 800;")
        self.value.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; font-size: 12px; font-weight: 900;")


class _StatTile(QWidget):
    """Compact tile for key-value stats (better than many empty pills)."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setObjectName("qsStatTile")

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(3)

        self.title = QLabel(title)
        self.title.setObjectName("qsStatTileTitle")
        root.addWidget(self.title)

        self.value = QLabel("—")
        self.value.setObjectName("qsStatTileValue")
        root.addWidget(self.value)

    def set_value(self, text: str):
        self.value.setText(text)


def _make_segment_button(text: str) -> QToolButton:
    btn = QToolButton()
    btn.setText(text)
    btn.setCheckable(True)
    btn.setCursor(Qt.PointingHandCursor)
    btn.setAutoRaise(True)
    btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
    return btn


class PlotQuickStatsPanel(QWidget):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.setObjectName("plotQuickStats")
        self.setAttribute(Qt.WA_StyledBackground, True)

        self._mode = "rejected"  # "rejected" | "gradient"
        self._selected_point_id: Optional[str] = None
        self._rej_freq: Counter = Counter()
        self._val_freq: Counter = Counter()
        self._grad_stats: Dict[str, Dict[str, float]] = {}
        self._rows_rejected: List[Tuple[str, int, int, float]] = []
        self._rows_gradient: List[Tuple[str, float, float, int]] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        header = QHBoxLayout()
        header.setSpacing(10)

        self.title_label = QLabel("Quick Stats")
        self.title_label.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; font-size: 12px; font-weight: 800;")
        header.addWidget(self.title_label)

        self.hint_label = QLabel("Select an ID to see details. Double-click a row to inspect triangles.")
        self.hint_label.setStyleSheet(f"color: {Colors.TEXT_TERTIARY}; font-size: 10px;")
        header.addWidget(self.hint_label)

        header.addStretch()

        self.btn_full_stats = QPushButton("Open Full Statistics")
        self.btn_full_stats.clicked.connect(self._open_full_statistics)
        header.addWidget(self.btn_full_stats)

        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.clicked.connect(self.update_from_app)
        header.addWidget(self.btn_refresh)

        root.addLayout(header)

        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setHandleWidth(7)

        # Left card: mode switch + table
        left_card = QFrame()
        left_card.setObjectName("qsCard")
        left_layout = QVBoxLayout(left_card)
        left_layout.setContentsMargins(12, 12, 12, 12)
        left_layout.setSpacing(10)

        left_header = QHBoxLayout()
        left_header.setSpacing(10)

        self.left_section_title = QLabel("Rejected IDs")
        self.left_section_title.setObjectName("qsSectionTitle")
        left_header.addWidget(self.left_section_title)

        self.left_section_subtitle = QLabel("Top 20")
        self.left_section_subtitle.setObjectName("qsSectionSubtitle")
        left_header.addWidget(self.left_section_subtitle)

        left_header.addStretch()

        self.segment = QWidget()
        self.segment.setObjectName("qsSegment")
        seg_layout = QHBoxLayout(self.segment)
        seg_layout.setContentsMargins(2, 2, 2, 2)
        seg_layout.setSpacing(0)

        self.btn_mode_rejected = _make_segment_button("Rejected")
        self.btn_mode_rejected.setObjectName("qsSegmentButton")
        self.btn_mode_rejected.setProperty("position", "left")
        self.btn_mode_rejected.setChecked(True)
        self.btn_mode_rejected.clicked.connect(lambda: self._set_mode("rejected"))

        self.btn_mode_gradient = _make_segment_button("Gradients")
        self.btn_mode_gradient.setObjectName("qsSegmentButton")
        self.btn_mode_gradient.setProperty("position", "right")
        self.btn_mode_gradient.clicked.connect(lambda: self._set_mode("gradient"))

        seg_layout.addWidget(self.btn_mode_rejected)
        seg_layout.addWidget(self.btn_mode_gradient)
        left_header.addWidget(self.segment)

        left_layout.addLayout(left_header)

        self.table = QTableWidget()
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.horizontalHeader().setHighlightSections(False)
        self.table.setWordWrap(False)
        self.table.verticalHeader().setDefaultSectionSize(26)
        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table.itemDoubleClicked.connect(lambda item: self._inspect_row(item.row()))
        left_layout.addWidget(self.table, 1)

        # Right card: global summary + selected details
        right_card = QFrame()
        right_card.setObjectName("qsCard")
        right_card.setMinimumWidth(360)
        right_layout = QVBoxLayout(right_card)
        right_layout.setContentsMargins(12, 12, 12, 12)
        right_layout.setSpacing(12)

        # Dataset context (collapsed by default to reduce clutter)
        overview_header = QHBoxLayout()
        overview_header.setSpacing(8)

        overview_title = QLabel("Dataset context")
        overview_title.setObjectName("qsSectionTitle")
        overview_title.setToolTip("Summary across all valid triangles (context for comparisons).")
        overview_header.addWidget(overview_title)

        overview_header.addStretch()

        self.btn_toggle_overview = QToolButton()
        self.btn_toggle_overview.setObjectName("qsOverviewToggle")
        self.btn_toggle_overview.setCheckable(True)
        self.btn_toggle_overview.setChecked(False)
        self.btn_toggle_overview.setText("Show")
        self.btn_toggle_overview.setCursor(Qt.PointingHandCursor)
        self.btn_toggle_overview.clicked.connect(self._toggle_overview)
        overview_header.addWidget(self.btn_toggle_overview)

        right_layout.addLayout(overview_header)

        self.overview_subtitle = QLabel("All valid triangles")
        self.overview_subtitle.setObjectName("qsSectionSubtitle")
        right_layout.addWidget(self.overview_subtitle)

        self.overview_container = QWidget()
        self.overview_container.setObjectName("qsOverviewContainer")
        self.overview_container.setVisible(False)

        overview_grid = QGridLayout(self.overview_container)
        overview_grid.setContentsMargins(0, 0, 0, 0)
        overview_grid.setHorizontalSpacing(10)
        overview_grid.setVerticalSpacing(10)

        self.metric_mean_grad = _MetricPill("Mean gradient")
        self.metric_mean_dir = _MetricPill("Mean direction")
        self.metric_weighted_dir = _MetricPill("Weighted direction")
        overview_grid.addWidget(self.metric_mean_grad, 0, 0)
        overview_grid.addWidget(self.metric_mean_dir, 0, 1)
        overview_grid.addWidget(self.metric_weighted_dir, 1, 0, 1, 2)

        right_layout.addWidget(self.overview_container)

        sel_title_row = QHBoxLayout()
        sel_title_row.setSpacing(8)
        sel_title = QLabel("Selected ID")
        sel_title.setObjectName("qsSectionTitle")
        sel_title_row.addWidget(sel_title)
        sel_title_row.addStretch()
        self.selected_hint = QLabel("Pick a row in the table")
        self.selected_hint.setObjectName("qsSectionSubtitle")
        sel_title_row.addWidget(self.selected_hint)
        right_layout.addLayout(sel_title_row)

        self.selected_id_label = QLabel("—")
        self.selected_id_label.setObjectName("qsSelectedId")
        right_layout.addWidget(self.selected_id_label)

        self.details_placeholder = QLabel("Select an ID from the table to see details here.")
        self.details_placeholder.setObjectName("qsDetailsPlaceholder")
        right_layout.addWidget(self.details_placeholder)

        self.details_container = QWidget()
        self.details_container.setObjectName("qsDetailsContainer")
        self.details_container.setVisible(False)
        right_layout.addWidget(self.details_container)

        details_grid = QGridLayout(self.details_container)
        details_grid.setContentsMargins(0, 0, 0, 0)
        details_grid.setHorizontalSpacing(10)
        details_grid.setVerticalSpacing(10)

        self.tile_rej_rate = _StatTile("Rej. rate")
        self.tile_rej_counts = _StatTile("Rejected / Valid")
        self.tile_max_grad = _StatTile("Max gradient")
        self.tile_mean_grad = _StatTile("Mean gradient")

        details_grid.addWidget(self.tile_rej_rate, 0, 0)
        details_grid.addWidget(self.tile_rej_counts, 0, 1)
        details_grid.addWidget(self.tile_max_grad, 1, 0)
        details_grid.addWidget(self.tile_mean_grad, 1, 1)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.btn_inspect = QPushButton("Inspect triangles")
        self.btn_inspect.setEnabled(False)
        self.btn_inspect.clicked.connect(self._inspect_selected)
        actions.addWidget(self.btn_inspect)

        self.btn_clear = QPushButton("Clear selection")
        self.btn_clear.clicked.connect(self._clear_selection)
        actions.addWidget(self.btn_clear)
        actions.addStretch()
        right_layout.addLayout(actions)

        # Compact triangle summary
        self.tri_sep = QFrame()
        self.tri_sep.setFixedHeight(1)
        self.tri_sep.setStyleSheet(f"background-color: {Colors.BORDER_SUBTLE}; border: none;")
        right_layout.addWidget(self.tri_sep)

        tri_title = QLabel("Triangle Summary")
        tri_title.setObjectName("qsSectionTitle")
        right_layout.addWidget(tri_title)

        self.qs_tri_summary = TriangleSummaryCards(compact=True)
        right_layout.addWidget(self.qs_tri_summary)

        self.qs_tri_breakdown = RejectionBreakdownBars()
        right_layout.addWidget(self.qs_tri_breakdown)

        right_layout.addStretch(1)

        self.splitter.addWidget(left_card)
        self.splitter.addWidget(right_card)
        self.splitter.setSizes([900, 420])
        root.addWidget(self.splitter, 1)

        # Styles
        self.setStyleSheet(self._build_stylesheet())

        self._render_table()
        self._update_details(None)

    def _build_stylesheet(self) -> str:
        return f"""
            QWidget#plotQuickStats {{
                background-color: {Colors.BG_ELEVATED};
                border-top: 1px solid {Colors.BORDER_DEFAULT};
            }}

            QFrame#qsCard {{
                background-color: {Colors.BG_SURFACE};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 12px;
            }}

            QLabel#qsSectionTitle {{
                color: {Colors.TEXT_PRIMARY};
                font-size: 10px;
                font-weight: 900;
                letter-spacing: 0.4px;
            }}

            QLabel#qsSectionSubtitle {{
                color: {Colors.TEXT_TERTIARY};
                font-size: 10px;
                font-weight: 700;
            }}

            QLabel#qsSelectedId {{
                color: {Colors.TEXT_PRIMARY};
                font-size: 18px;
                font-weight: 900;
            }}

            QLabel#qsDetailsPlaceholder {{
                color: {Colors.TEXT_TERTIARY};
                font-size: 11px;
                padding: 6px 0px;
            }}

            QWidget#qsDetailsContainer {{
                background-color: transparent;
            }}

            QWidget#qsStatTile {{
                background-color: {Colors.BG_DARK};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 10px;
            }}

            QLabel#qsStatTileTitle {{
                color: {Colors.TEXT_TERTIARY};
                font-size: 9px;
                font-weight: 900;
                letter-spacing: 0.3px;
            }}

            QLabel#qsStatTileValue {{
                color: {Colors.TEXT_PRIMARY};
                font-size: 13px;
                font-weight: 900;
            }}

            QToolButton#qsOverviewToggle {{
                background-color: {Colors.BG_DARK};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 8px;
                padding: 5px 10px;
                font-size: 10px;
                font-weight: 900;
                color: {Colors.TEXT_SECONDARY};
            }}

            QToolButton#qsOverviewToggle:hover {{
                border-color: {Colors.ACCENT_PRIMARY};
                color: {Colors.TEXT_PRIMARY};
            }}

            QToolButton#qsOverviewToggle:checked {{
                background-color: {Colors.BG_HOVER};
                border-color: {Colors.BORDER_STRONG};
                color: {Colors.TEXT_PRIMARY};
            }}

            QToolButton#qsOverviewToggle:checked:hover {{
                background-color: {Colors.BG_HOVER};
                border-color: {Colors.ACCENT_PRIMARY};
            }}
            QLabel {{
                background: transparent;
            }}

            QWidget#qsSegment {{
                background-color: {Colors.BG_DARK};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 10px;
            }}

            QToolButton#qsSegmentButton {{
                background: transparent;
                border: none;
                padding: 5px 12px;
                font-size: 10px;
                font-weight: 900;
                color: {Colors.TEXT_TERTIARY};
                min-height: 24px;
            }}

            QToolButton#qsSegmentButton[position="left"] {{
                border-top-left-radius: 8px;
                border-bottom-left-radius: 8px;
            }}

            QToolButton#qsSegmentButton[position="right"] {{
                border-top-right-radius: 8px;
                border-bottom-right-radius: 8px;
            }}

            QToolButton#qsSegmentButton:hover:!checked {{
                color: {Colors.TEXT_SECONDARY};
                background-color: {Colors.BG_HOVER};
            }}

            QToolButton#qsSegmentButton:checked {{
                background-color: {Colors.ACCENT_PRIMARY};
                color: {Colors.TEXT_PRIMARY};
            }}

            QToolButton#qsSegmentButton:checked:hover {{
                background-color: {Colors.ACCENT_HOVER};
            }}
            QTableWidget {{
                background-color: {Colors.BG_DARK};
                border: 1px solid {Colors.BORDER_SUBTLE};
                color: {Colors.TEXT_PRIMARY};
                gridline-color: {Colors.BORDER_SUBTLE};
            }}
            QTableWidget::item {{
                padding: 4px 8px;
            }}
            QTableWidget::item:alternate {{
                background-color: {Colors.BG_PANEL};
            }}
            QTableWidget::item:selected {{
                background-color: {Colors.OVERLAY_ACTIVE};
            }}
            QHeaderView::section {{
                background-color: {Colors.BG_ELEVATED};
                color: {Colors.TEXT_SECONDARY};
                border: none;
                border-bottom: 1px solid {Colors.BORDER_DEFAULT};
                padding: 6px 8px;
                font-size: 10px;
                font-weight: 900;
            }}
            QSplitter::handle {{
                background-color: {Colors.BORDER_MEDIUM};
                width: 4px;
            }}
            QSplitter::handle:hover {{
                background-color: {Colors.ACCENT_PRIMARY};
            }}
            QPushButton {{
                background-color: {Colors.BG_SURFACE};
                border: 1px solid {Colors.BORDER_STRONG};
                border-radius: 6px;
                padding: 5px 10px;
                font-size: 10px;
                font-weight: 700;
                color: {Colors.TEXT_PRIMARY};
                min-height: 26px;
            }}
            QPushButton:hover {{
                background-color: {Colors.BG_HOVER};
                border-color: {Colors.ACCENT_PRIMARY};
            }}
            """

    def apply_theme(self):
        self.title_label.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; font-size: 12px; font-weight: 800;")
        self.hint_label.setStyleSheet(f"color: {Colors.TEXT_TERTIARY}; font-size: 10px;")
        self.tri_sep.setStyleSheet(f"background-color: {Colors.BORDER_SUBTLE}; border: none;")
        self.setStyleSheet(self._build_stylesheet())
        for pill in self.findChildren(_MetricPill):
            pill.apply_theme()

    def _toggle_overview(self):
        show = bool(self.btn_toggle_overview.isChecked())
        self.overview_container.setVisible(show)
        self.btn_toggle_overview.setText("Hide" if show else "Show")

    def _open_full_statistics(self):
        try:
            self.main_window.nav_sidebar.set_active_page("stats")
            self.main_window.on_page_changed("stats")
        except Exception:
            pass

    def _set_mode(self, mode: str):
        self._mode = "gradient" if mode == "gradient" else "rejected"
        self.btn_mode_rejected.setChecked(self._mode == "rejected")
        self.btn_mode_gradient.setChecked(self._mode == "gradient")
        self._render_table()

    def _render_table(self):
        if self._mode == "rejected":
            cols = ["ID", "Rejected", "Valid", "Rej. Rate"]
            rows = self._rows_rejected
            tooltip = "Top rejected IDs"
        else:
            cols = ["ID", "Max Grad", "Mean Grad", "N Triangles"]
            rows = self._rows_gradient
            tooltip = "Top gradient IDs"

        try:
            if self._mode == "rejected":
                self.left_section_title.setText("Rejected IDs")
            else:
                self.left_section_title.setText("High gradients")
            n = int(len(rows)) if rows else 0
            self.left_section_subtitle.setText(f"Top {min(20, n)}")
        except Exception:
            pass

        self.table.setToolTip(tooltip)
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.setRowCount(len(rows) if rows else 1)

        self.table.setSortingEnabled(False)
        if not rows:
            self.table.setItem(0, 0, QTableWidgetItem("No data"))
            for c in range(1, len(cols)):
                self.table.setItem(0, c, QTableWidgetItem(""))
        else:
            for r, row in enumerate(rows):
                for c, value in enumerate(row):
                    item = QTableWidgetItem()
                    if c == 0:
                        item.setText(str(value))
                    else:
                        if self._mode == "rejected":
                            if c in (1, 2):
                                item.setData(Qt.UserRole, int(value))
                                item.setText(str(int(value)))
                            else:
                                item.setData(Qt.UserRole, float(value))
                                item.setText(f"{float(value):.1f}%")
                        else:
                            if c in (1, 2):
                                item.setData(Qt.UserRole, float(value))
                                item.setText(f"{float(value):.6f}")
                            else:
                                item.setData(Qt.UserRole, int(value))
                                item.setText(str(int(value)))
                    if c > 0:
                        item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    self.table.setItem(r, c, item)

        self._configure_columns()
        self.table.setSortingEnabled(True)

    def _configure_columns(self):
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        # Last column absorbs slack so the table doesn't look like a huge empty grid.
        if self.table.columnCount() > 0:
            header.setSectionResizeMode(self.table.columnCount() - 1, QHeaderView.Stretch)

    def _on_selection_changed(self):
        items = self.table.selectedItems()
        if not items:
            self._selected_point_id = None
            self._update_details(None)
            return
        item = self.table.item(self.table.currentRow(), 0)
        if item is None:
            self._selected_point_id = None
            self._update_details(None)
            return
        self._selected_point_id = item.text()
        self._update_details(self._selected_point_id)

    def _clear_selection(self):
        self.table.clearSelection()
        self._selected_point_id = None
        self._update_details(None)

    def _inspect_row(self, row: int):
        item = self.table.item(row, 0)
        if item is None:
            return
        self._inspect_point_id(item.text())

    def _inspect_selected(self):
        if not self._selected_point_id:
            return
        self._inspect_point_id(self._selected_point_id)

    def _inspect_point_id(self, point_id: str):
        tri_df = getattr(self.main_window, "triangle_data", None)
        if tri_df is None or getattr(tri_df, "empty", True):
            return

        tri_indices: List[int] = []
        try:
            want = str(point_id)
            for idx, ids in tri_df["point_ids"].items():
                if want in [str(v) for v in _iter_point_ids(ids)]:
                    tri_indices.append(int(idx))
        except Exception:
            tri_indices = []

        tri_indices = tri_indices[:500]
        self.main_window.set_triangle_selection(tri_indices, meta={"source": "quick_stats", "point_id": str(point_id)})
        try:
            self.main_window.show_triangle_inspector(selected_point_ids={str(point_id)})
        except Exception:
            pass

    def _update_details(self, point_id: Optional[str]):
        if not point_id:
            self.selected_id_label.setText("—")
            try:
                self.selected_hint.setText("Pick a row in the table")
            except Exception:
                pass
            self.details_placeholder.setVisible(True)
            self.details_container.setVisible(False)
            self.btn_inspect.setEnabled(False)
            return

        pid = str(point_id)
        self.selected_id_label.setText(pid)
        try:
            self.selected_hint.setText("Double-click to inspect triangles")
        except Exception:
            pass
        self.details_placeholder.setVisible(False)
        self.details_container.setVisible(True)
        self.btn_inspect.setEnabled(True)

        r = int(self._rej_freq.get(pid, 0))
        v = int(self._val_freq.get(pid, 0))
        tot = r + v
        rate = (r / tot * 100.0) if tot > 0 else 0.0
        self.tile_rej_rate.set_value(f"{rate:.1f}%")
        self.tile_rej_counts.set_value(f"{r} / {v}")

        rec = self._grad_stats.get(pid, None)
        if rec is None:
            self.tile_max_grad.set_value("—")
            self.tile_mean_grad.set_value("—")
        else:
            # Triangle count is currently shown in the left table; keep the detail view focused.
            gmax = float(rec.get("max", 0.0))
            gmean = float(rec.get("mean", 0.0))
            self.tile_max_grad.set_value(f"{gmax:.6f}")
            self.tile_mean_grad.set_value(f"{gmean:.6f}")

    def update_from_app(self):
        """Refresh from the current active dataset/app state."""
        rejected_df = getattr(self.main_window, "rejected_data", None)
        valid_df = getattr(self.main_window, "triangle_data", None)
        gradient_df = getattr(self.main_window, "gradient_data", None)
        total_triangles = getattr(self.main_window, "total_triangles", None)

        self._fill_global_summary(valid_df)
        self._compute_rejected_rows(rejected_df, valid_df)
        self._compute_gradient_rows(valid_df)
        self._render_table()
        self._update_details(self._selected_point_id)

        # Update compact triangle widgets
        try:
            summary = TriangleDataHelper.compute_summary(valid_df, rejected_df, total_triangles)
            self.qs_tri_summary.update_data(summary)
            breakdown_primary = TriangleDataHelper.compute_reason_breakdown(rejected_df, mode="primary")
            breakdown_all = TriangleDataHelper.compute_reason_breakdown(rejected_df, mode="all")
            self.qs_tri_breakdown.update_data(breakdown_primary, breakdown_all)
        except Exception:
            pass

    def _fill_global_summary(self, valid_df):
        # Mean gradient
        try:
            if valid_df is not None and not valid_df.empty and "gradient" in valid_df.columns:
                mean_g = float(valid_df["gradient"].astype(float).mean())
                self.metric_mean_grad.set_value(f"{mean_g:.6f} m/m")
            else:
                self.metric_mean_grad.set_value("-")
        except Exception:
            self.metric_mean_grad.set_value("-")

        # Mean direction + weighted mean direction
        try:
            calc = getattr(self.main_window, "gradient_calculator", None)
            if calc is None:
                self.metric_mean_dir.set_value("-")
                self.metric_weighted_dir.set_value("-")
                return

            result = calc.calculate_average_gradient()
            if not result or len(result) < 3:
                self.metric_mean_dir.set_value("-")
                self.metric_weighted_dir.set_value("-")
                return

            _, ang, ang_w = result
            if ang is None:
                self.metric_mean_dir.set_value("-")
            else:
                compass = _angle_to_compass(float(ang))
                self.metric_mean_dir.set_value(f"{float(ang):.1f}° {compass}")

            if ang_w is None:
                self.metric_weighted_dir.set_value("-")
            else:
                compass_w = _angle_to_compass(float(ang_w))
                self.metric_weighted_dir.set_value(f"{float(ang_w):.1f}° {compass_w}")
        except Exception:
            self.metric_mean_dir.set_value("-")
            self.metric_weighted_dir.set_value("-")

    def _compute_rejected_rows(self, rejected_df, valid_df):
        rej_freq: Counter = Counter()
        val_freq: Counter = Counter()

        try:
            if rejected_df is not None and not rejected_df.empty and "point_ids" in rejected_df.columns:
                for ids in rejected_df["point_ids"]:
                    rej_freq.update([str(v) for v in _iter_point_ids(ids)])
        except Exception:
            rej_freq = Counter()

        try:
            if valid_df is not None and not valid_df.empty and "point_ids" in valid_df.columns:
                for ids in valid_df["point_ids"]:
                    val_freq.update([str(v) for v in _iter_point_ids(ids)])
        except Exception:
            val_freq = Counter()

        all_ids = set(rej_freq.keys()) | set(val_freq.keys())
        rows: List[Tuple[str, int, int, float]] = []
        for pid in all_ids:
            r = int(rej_freq.get(pid, 0))
            v = int(val_freq.get(pid, 0))
            tot = r + v
            rate = (r / tot * 100.0) if tot > 0 else 0.0
            rows.append((pid, r, v, rate))

        rows.sort(key=lambda t: (t[1], t[3]), reverse=True)
        self._rows_rejected = rows[:20]
        self._rej_freq = rej_freq
        self._val_freq = val_freq

    def _compute_gradient_rows(self, valid_df):
        per_id: Dict[str, Dict[str, float]] = defaultdict(lambda: {"count": 0.0, "sum": 0.0, "max": 0.0})
        try:
            if valid_df is not None and not valid_df.empty and "point_ids" in valid_df.columns and "gradient" in valid_df.columns:
                for _, row in valid_df.iterrows():
                    try:
                        g = float(row["gradient"])
                    except Exception:
                        continue
                    for pid in [str(v) for v in _iter_point_ids(row["point_ids"])]:
                        rec = per_id[pid]
                        rec["count"] += 1.0
                        rec["sum"] += g
                        if g > rec["max"]:
                            rec["max"] = g
        except Exception:
            per_id = defaultdict(lambda: {"count": 0.0, "sum": 0.0, "max": 0.0})

        rows: List[Tuple[str, float, float, int]] = []
        stats: Dict[str, Dict[str, float]] = {}
        for pid, rec in per_id.items():
            c = int(rec["count"])
            mean = (rec["sum"] / rec["count"]) if rec["count"] > 0 else 0.0
            rows.append((str(pid), float(rec["max"]), float(mean), c))
            stats[str(pid)] = {"count": float(c), "max": float(rec["max"]), "mean": float(mean)}

        rows.sort(key=lambda t: (t[1], t[2]), reverse=True)
        self._rows_gradient = rows[:20]
        self._grad_stats = stats
