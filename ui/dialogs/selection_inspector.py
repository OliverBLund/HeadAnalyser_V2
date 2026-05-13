"""
Selection Inspector dialog

Shows the triangles/points that make up a histogram bin or rose wedge selection,
and supports basic A/B comparison.

Modernized to match HeadAnalyser V2 design system with polished UI components.
"""

from __future__ import annotations

from typing import Iterable, Optional, Set

import numpy as np
import pandas as pd
from PyQt5.QtCore import Qt, QAbstractTableModel, QModelIndex, QVariant, QSize
from PyQt5.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTabWidget,
    QTableView,
    QVBoxLayout,
    QWidget,
    QHeaderView,
    QLineEdit,
    QFrame,
)
from PyQt5.QtGui import QFont, QColor

from styles.colors import Colors
from styles.stylesheet import StyleSheet
from qt_chrome import FramelessDialogMixin


def _danger_text() -> str:
    return Colors.ERROR_LIGHT if Colors.is_dark() else Colors.ERROR_DARK


def _badge_style(color: str) -> str:
    return f"""
        color: {color};
        font-size: 10px;
        font-weight: 700;
        background: {Colors.rgba(color, 0.15)};
        border: 1px solid {Colors.rgba(color, 0.30)};
        border-radius: 8px;
        padding: 4px 10px;
    """


class _ReadOnlyPandasModel(QAbstractTableModel):
    """Read-only Qt model for pandas DataFrame."""

    def __init__(self, df: Optional[pd.DataFrame] = None, parent=None):
        super().__init__(parent)
        self._df = df if df is not None else pd.DataFrame()

    def rowCount(self, parent=QModelIndex()):
        return int(len(self._df))

    def columnCount(self, parent=QModelIndex()):
        return int(len(self._df.columns))

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return QVariant()

        row = index.row()
        col = index.column()

        if role == Qt.DisplayRole:
            value = self._df.iloc[row, col]
            if pd.isna(value):
                return ""
            if isinstance(value, float):
                return f"{value:.6f}"
            return str(value)

        if role == Qt.TextAlignmentRole:
            if col == 0:
                return Qt.AlignLeft | Qt.AlignVCenter
            return Qt.AlignRight | Qt.AlignVCenter

        if role == Qt.ForegroundRole:
            if col == 0:
                return QColor(Colors.ACCENT_BRIGHT)
            return QColor(Colors.TEXT_SECONDARY)

        if role == Qt.FontRole:
            if col == 0:
                font = QFont()
                font.setPixelSize(12)
                font.setWeight(QFont.DemiBold)
                return font
            # Monospace for numeric columns
            font = QFont("Consolas, 'IBM Plex Mono', monospace")
            font.setPixelSize(12)
            return font

        return QVariant()

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return QVariant()
        if orientation == Qt.Horizontal:
            return str(self._df.columns[section])
        return str(section + 1)

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemIsEnabled
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable

    def set_df(self, df: pd.DataFrame):
        self.beginResetModel()
        self._df = df if df is not None else pd.DataFrame()
        self.endResetModel()


def _make_stat_card(label: str, value: str, badge_text: str = "", badge_color: str = Colors.ACCENT_PRIMARY):
    """Create a modern stat card widget."""
    card = QWidget()
    card.setStyleSheet(f"""
        QWidget {{
            background: {Colors.GRADIENT_SURFACE};
            border: 1px solid {Colors.BORDER_DEFAULT};
            border-radius: 12px;
            padding: 18px;
        }}
        QWidget:hover {{
            border-color: {Colors.BORDER_MEDIUM};
        }}
    """)

    layout = QVBoxLayout(card)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)

    # Label
    label_widget = QLabel(label.upper())
    label_widget.setStyleSheet(f"""
        color: {Colors.TEXT_TERTIARY};
        font-size: 10px;
        font-weight: 700;
        letter-spacing: 1px;
        background: transparent;
        border: none;
        padding: 0;
    """)
    layout.addWidget(label_widget)

    # Value row (value + badge)
    value_row = QHBoxLayout()
    value_row.setSpacing(10)

    value_label = QLabel(value)
    value_label.setStyleSheet(f"""
        color: {Colors.TEXT_PRIMARY};
        font-size: 32px;
        font-weight: 700;
        background: transparent;
        border: none;
        padding: 0;
    """)
    value_row.addWidget(value_label)

    if badge_text:
        badge = QLabel(badge_text)
        badge.setStyleSheet(_badge_style(badge_color))
        badge.setAlignment(Qt.AlignCenter)
        value_row.addWidget(badge)

    value_row.addStretch()
    layout.addLayout(value_row)

    return card


class SelectionInspectorDialog(FramelessDialogMixin, QDialog):
    def __init__(self, main_window, parent=None):
        super().__init__(parent or main_window)
        self.main_window = main_window
        self.setWindowTitle("Selection Inspector")
        self.resize(1000, 680)
        self.init_frameless_dialog_chrome(
            default_windows="frameless",
            default_other="native",
            resize_margin=10,
            top_resize_margin=10,
        )

        self._compare_a: Set[int] = set()
        self._compare_b: Set[int] = set()
        self._compare_a_meta = None
        self._compare_b_meta = None

        self._setup_ui()
        self._current_selection: Set[int] = set()
        self._current_meta = None
        self.bind_frameless_drag_widget(self._chrome_header)
        self._apply_styles()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header ──
        header = QWidget()
        self._chrome_header = header
        header.setObjectName("dialog_header")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(24, 20, 24, 20)
        header_layout.setSpacing(8)

        # Title row (title + badge)
        title_row = QHBoxLayout()
        title_row.setSpacing(12)

        self.title_label = QLabel("Selection Inspector")
        self.title_label.setStyleSheet(f"""
            color: {Colors.TEXT_PRIMARY};
            font-size: 18px;
            font-weight: 700;
            letter-spacing: -0.3px;
            background: transparent;
            border: none;
        """)
        title_row.addWidget(self.title_label)

        self.source_badge = QLabel()
        self.source_badge.setVisible(False)
        self.source_badge.setAlignment(Qt.AlignCenter)
        title_row.addWidget(self.source_badge)

        title_row.addStretch()

        # Close button
        close_btn = QPushButton("×")
        close_btn.setObjectName("close_btn")
        close_btn.setFixedSize(32, 32)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self.close)
        close_btn.setToolTip("Close")
        title_row.addWidget(close_btn)

        header_layout.addLayout(title_row)

        # Subtitle
        self.subtitle_label = QLabel()
        self.subtitle_label.setStyleSheet(f"""
            color: {Colors.TEXT_TERTIARY};
            font-size: 13px;
            font-weight: 500;
            background: transparent;
            border: none;
        """)
        header_layout.addWidget(self.subtitle_label)

        root.addWidget(header)

        # ── Controls Bar ──
        controls = QWidget()
        controls.setObjectName("controls_bar")
        controls_layout = QHBoxLayout(controls)
        controls_layout.setContentsMargins(24, 16, 24, 16)
        controls_layout.setSpacing(16)

        # Overlay checkbox
        self.overlay_checkbox = QCheckBox("Show selection overlay in Gradient Vectors")
        self.overlay_checkbox.setChecked(bool(getattr(self.main_window, "show_triangle_selection_overlay", False)))
        self.overlay_checkbox.stateChanged.connect(self._on_overlay_changed)
        self.overlay_checkbox.setCursor(Qt.PointingHandCursor)
        controls_layout.addWidget(self.overlay_checkbox)

        controls_layout.addStretch()

        # A/B comparison buttons
        self.btn_set_a = QPushButton("Set as A")
        self.btn_set_a.setCursor(Qt.PointingHandCursor)
        self.btn_set_a.setObjectName("btn_accent")
        self.btn_set_a.clicked.connect(self._set_as_a)
        controls_layout.addWidget(self.btn_set_a)

        self.btn_set_b = QPushButton("Set as B")
        self.btn_set_b.setCursor(Qt.PointingHandCursor)
        self.btn_set_b.setObjectName("btn_secondary")
        self.btn_set_b.clicked.connect(self._set_as_b)
        controls_layout.addWidget(self.btn_set_b)

        self.btn_clear_compare = QPushButton("Clear A/B")
        self.btn_clear_compare.setCursor(Qt.PointingHandCursor)
        self.btn_clear_compare.setObjectName("btn_danger")
        self.btn_clear_compare.clicked.connect(self._clear_compare)
        controls_layout.addWidget(self.btn_clear_compare)

        root.addWidget(controls)

        # ── Tabs ──
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setTabPosition(QTabWidget.North)

        # Triangles tab
        tri_tab = QWidget()
        tri_layout = QVBoxLayout(tri_tab)
        tri_layout.setContentsMargins(24, 20, 24, 24)
        tri_layout.setSpacing(16)

        # Info banner
        info_banner = QWidget()
        info_banner.setObjectName("info_banner")
        info_layout = QHBoxLayout(info_banner)
        info_layout.setContentsMargins(16, 12, 16, 12)
        info_layout.setSpacing(12)

        info_icon = QLabel("ℹ")
        info_icon.setStyleSheet(f"color: {Colors.ACCENT_PRIMARY}; font-size: 18px; background: transparent; border: none;")
        info_layout.addWidget(info_icon)

        info_text = QLabel("<b>Tip:</b> Click table headers to sort. Use Ctrl+C to copy selected rows.")
        info_text.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 12px; background: transparent; border: none;")
        info_text.setWordWrap(True)
        info_layout.addWidget(info_text, 1)

        tri_layout.addWidget(info_banner)

        # Search bar
        self.tri_search = QLineEdit()
        self.tri_search.setPlaceholderText("⌕  Filter triangles...")
        self.tri_search.setClearButtonEnabled(True)
        self.tri_search.setObjectName("search_input")
        tri_layout.addWidget(self.tri_search)

        # Table
        self.tri_table = self._make_table()
        self.tri_model = _ReadOnlyPandasModel()
        self.tri_table.setModel(self.tri_model)
        tri_layout.addWidget(self.tri_table)

        self.tabs.addTab(tri_tab, "Triangles")

        # Points tab
        pt_tab = QWidget()
        pt_layout = QVBoxLayout(pt_tab)
        pt_layout.setContentsMargins(24, 20, 24, 24)
        pt_layout.setSpacing(16)

        # Search bar
        self.pt_search = QLineEdit()
        self.pt_search.setPlaceholderText("⌕  Filter points...")
        self.pt_search.setClearButtonEnabled(True)
        self.pt_search.setObjectName("search_input")
        pt_layout.addWidget(self.pt_search)

        # Table
        self.pt_table = self._make_table()
        self.pt_model = _ReadOnlyPandasModel()
        self.pt_table.setModel(self.pt_model)
        pt_layout.addWidget(self.pt_table)

        self.tabs.addTab(pt_tab, "Points")

        # Compare tab
        cmp_tab = QWidget()
        cmp_layout = QVBoxLayout(cmp_tab)
        cmp_layout.setContentsMargins(24, 20, 24, 24)
        cmp_layout.setSpacing(20)

        # Empty state (shown when no A/B)
        self.compare_empty = QWidget()
        empty_layout = QVBoxLayout(self.compare_empty)
        empty_layout.setAlignment(Qt.AlignCenter)
        empty_icon = QLabel("⊗")
        empty_icon.setAlignment(Qt.AlignCenter)
        empty_icon.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: 64px; opacity: 0.15; background: transparent; border: none;")
        empty_layout.addWidget(empty_icon)
        empty_title = QLabel("No Comparison Set")
        empty_title.setAlignment(Qt.AlignCenter)
        empty_title.setStyleSheet(f"color: {Colors.TEXT_TERTIARY}; font-size: 16px; font-weight: 700; background: transparent; border: none;")
        empty_layout.addWidget(empty_title)
        empty_text = QLabel("Double-click a histogram bin or rose wedge, then use 'Set as A'.<br>Repeat with another selection and 'Set as B' to compare.")
        empty_text.setAlignment(Qt.AlignCenter)
        empty_text.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: 13px; line-height: 1.7; background: transparent; border: none;")
        empty_text.setWordWrap(True)
        empty_layout.addWidget(empty_text)

        cmp_layout.addWidget(self.compare_empty)

        # Stats area (hidden initially)
        self.compare_stats = QWidget()
        self.compare_stats.setVisible(False)
        stats_layout = QVBoxLayout(self.compare_stats)
        stats_layout.setContentsMargins(0, 0, 0, 0)
        stats_layout.setSpacing(20)

        # Label
        self.compare_label = QLabel()
        self.compare_label.setStyleSheet(f"""
            color: {Colors.TEXT_SECONDARY};
            font-size: 13px;
            font-weight: 500;
            background: transparent;
            border: none;
        """)
        stats_layout.addWidget(self.compare_label)

        # Stats grid
        self.stats_grid = QHBoxLayout()
        self.stats_grid.setSpacing(16)
        stats_layout.addLayout(self.stats_grid)

        cmp_layout.addWidget(self.compare_stats)
        cmp_layout.addStretch()

        self.tabs.addTab(cmp_tab, "Compare")

        root.addWidget(self.tabs, 1)

    def _make_table(self) -> QTableView:
        """Create a styled table view."""
        tv = QTableView()
        tv.setAlternatingRowColors(True)
        tv.setSelectionBehavior(QTableView.SelectRows)
        tv.setSelectionMode(QTableView.SingleSelection)
        tv.setSortingEnabled(True)
        tv.setShowGrid(False)
        tv.setEditTriggers(QTableView.NoEditTriggers)
        tv.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        tv.horizontalHeader().setHighlightSections(False)
        tv.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        tv.verticalHeader().setVisible(False)
        tv.verticalHeader().setDefaultSectionSize(34)
        tv.setWordWrap(False)
        return tv

    def _apply_styles(self):
        """Apply modern styling to the dialog."""
        self.setStyleSheet(f"""
            QDialog {{
                background: {Colors.BG_MODAL};
            }}

            /* Header */
            #dialog_header {{
                background: {Colors.GRADIENT_HEADER};
                border-bottom: 1px solid {Colors.BORDER_ACCENT};
            }}

            /* Controls bar */
            #controls_bar {{
                background: {Colors.BG_DARK};
                border-bottom: 1px solid {Colors.BORDER_SUBTLE};
            }}

            /* Checkbox */
            QCheckBox {{
                color: {Colors.TEXT_SECONDARY};
                font-size: 13px;
                font-weight: 500;
                spacing: 8px;
                padding: 6px 8px;
                border-radius: 8px;
            }}
            QCheckBox:hover {{
                background: {Colors.ACCENT_GHOST};
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border: 2px solid {Colors.BORDER_MEDIUM};
                border-radius: 6px;
                background: {Colors.BG_SURFACE};
            }}
            QCheckBox::indicator:checked {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {Colors.ACCENT_PRIMARY}, stop:1 {Colors.ACCENT_PRESSED});
                border-color: {Colors.ACCENT_PRIMARY};
                image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTIiIGhlaWdodD0iMTIiIHZpZXdCb3g9IjAgMCAxMiAxMiIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZD0iTTEwIDNMNC41IDguNUwyIDYiIHN0cm9rZT0id2hpdGUiIHN0cm9rZS13aWR0aD0iMiIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIi8+Cjwvc3ZnPgo=);
            }}
            QCheckBox::indicator:hover {{
                border-color: {Colors.ACCENT_PRIMARY};
            }}

            /* Buttons */
            QPushButton {{
                padding: 8px 18px;
                border-radius: 10px;
                font-size: 12px;
                font-weight: 600;
                border: 1px solid;
            }}
            #btn_accent {{
                background: {Colors.ACCENT_GHOST};
                border-color: {Colors.BORDER_ACCENT};
                color: {Colors.TEXT_ACCENT};
            }}
            #btn_accent:hover {{
                background: {Colors.rgba(Colors.ACCENT_PRIMARY, 0.18)};
                border-color: {Colors.ACCENT_PRIMARY};
                color: {Colors.TEXT_PRIMARY};
            }}
            #btn_secondary {{
                background: {Colors.GRADIENT_BUTTON};
                border-color: {Colors.BORDER_MEDIUM};
                color: {Colors.TEXT_SECONDARY};
            }}
            #btn_secondary:hover {{
                background: {Colors.GRADIENT_SURFACE};
                border-color: {Colors.ACCENT_PRIMARY};
                color: {Colors.TEXT_PRIMARY};
            }}
            #btn_danger {{
                background: {Colors.ERROR_BG};
                border-color: {Colors.rgba(Colors.ERROR, 0.35)};
                color: {_danger_text()};
            }}
            #btn_danger:hover {{
                background: {Colors.rgba(Colors.ERROR, 0.20)};
                border-color: {Colors.ERROR};
                color: {Colors.TEXT_PRIMARY};
            }}
            /* Close button */
            #close_btn {{
                background: transparent;
                border: 1px solid transparent;
                border-radius: 8px;
                color: {Colors.TEXT_TERTIARY};
                font-size: 24px;
                font-weight: 400;
                padding: 0;
            }}
            #close_btn:hover {{
                background: {Colors.rgba(Colors.ERROR, 0.15)};
                border-color: {Colors.rgba(Colors.ERROR, 0.30)};
                color: {_danger_text()};
            }}
            #close_btn:pressed {{
                background: {Colors.rgba(Colors.ERROR, 0.25)};
            }}

            /* Search input */
            #search_input {{
                padding: 10px 16px 10px 36px;
                background: {Colors.GRADIENT_SURFACE};
                border: 1px solid {Colors.BORDER_MEDIUM};
                border-radius: 10px;
                font-size: 13px;
                color: {Colors.TEXT_PRIMARY};
                selection-background-color: {Colors.ACCENT_PRIMARY};
            }}
            #search_input:focus {{
                border-color: {Colors.ACCENT_PRIMARY};
                background: {Colors.BG_ELEVATED};
            }}

            /* Info banner */
            #info_banner {{
                background: {Colors.ACCENT_GHOST};
                border: 1px solid {Colors.BORDER_ACCENT};
                border-left: 3px solid {Colors.ACCENT_PRIMARY};
                border-radius: 12px;
            }}

            /* Tabs */
            QTabWidget::pane {{
                border: none;
                background: {Colors.BG_ELEVATED};
            }}
            QTabBar::tab {{
                padding: 12px 24px;
                font-size: 13px;
                font-weight: 600;
                color: {Colors.TEXT_TERTIARY};
                background: transparent;
                border: none;
                border-bottom: 2px solid transparent;
            }}
            QTabBar::tab:hover {{
                color: {Colors.TEXT_SECONDARY};
                background: {Colors.ACCENT_GHOST};
            }}
            QTabBar::tab:selected {{
                color: {Colors.TEXT_ACCENT};
                background: {Colors.STATE_SELECTED_BG};
                border-bottom: 2px solid {Colors.ACCENT_PRIMARY};
            }}

            /* Tables */
            QTableView {{
                {StyleSheet.get_table_base_style()}
            }}
        """)

    def _on_overlay_changed(self, state):
        self.main_window.show_triangle_selection_overlay = (state == Qt.Checked)
        try:
            ds = self.main_window.get_active_dataset()
            if ds is not None:
                ds.show_triangle_selection_overlay = self.main_window.show_triangle_selection_overlay
        except Exception:
            pass
        self.main_window.update_plot()

    def _set_as_a(self):
        self._compare_a = set(self._current_selection)
        self._compare_a_meta = self._current_meta
        self._update_compare()

    def _set_as_b(self):
        self._compare_b = set(self._current_selection)
        self._compare_b_meta = self._current_meta
        self._update_compare()

    def _clear_compare(self):
        self._compare_a = set()
        self._compare_b = set()
        self._compare_a_meta = None
        self._compare_b_meta = None
        self._update_compare()

    def update_selection(self, triangle_indices: Iterable[int], meta=None):
        """Update the dialog with a new selection."""
        self._current_selection = set(int(v) for v in (triangle_indices or []))
        self._current_meta = meta

        # Update title and badge based on source
        title = "Selection Inspector"
        badge_text = ""
        badge_color = Colors.ACCENT_PRIMARY
        subtitle_parts = []

        if isinstance(meta, dict):
            src = meta.get("source")
            if src == "histogram":
                badge_text = "HISTOGRAM"
                badge_color = Colors.INFO
                r = meta.get("range")
                if isinstance(r, (list, tuple)) and len(r) == 2:
                    title = f"Histogram Bin {meta.get('bin', '?')}"
                    subtitle_parts.append(f"Range: {r[0]:.6f} – {r[1]:.6f}")
            elif src == "rose":
                badge_text = "ROSE"
                badge_color = Colors.WARNING
                r = meta.get("range_deg")
                mode = meta.get("mode", "count")
                if isinstance(r, (list, tuple)) and len(r) == 2:
                    title = f"Rose Wedge {meta.get('bin', '?')}"
                    subtitle_parts.append(f"{r[0]:.1f}° – {r[1]:.1f}° • Mode: {mode}")
            elif src == "vector":
                badge_text = "VECTOR"
                badge_color = Colors.ACCENT_PRIMARY
                tri_id = meta.get("triangle")
                if tri_id is not None:
                    title = f"Vector Triangle {tri_id}"

        self.title_label.setText(title)

        if badge_text:
            self.source_badge.setText(badge_text)
            self.source_badge.setStyleSheet(f"""
                color: {badge_color};
                font-size: 10px;
                font-weight: 700;
                background: {Colors.rgba(badge_color, 0.15)};
                border: 1px solid {Colors.rgba(badge_color, 0.30)};
                border-radius: 10px;
                padding: 5px 12px;
                letter-spacing: 0.8px;
            """)
            self.source_badge.setVisible(True)
        else:
            self.source_badge.setVisible(False)

        # Subtitle
        tri_count = len(self._current_selection)
        subtitle_parts.append(f"{tri_count} triangle{'s' if tri_count != 1 else ''}")

        tri_df, pt_df = self._build_tables(self._current_selection)
        pt_count = len(pt_df)
        subtitle_parts.append(f"{pt_count} point{'s' if pt_count != 1 else ''}")

        self.subtitle_label.setText(" • ".join(subtitle_parts))

        # Update tables
        self.tri_model.set_df(tri_df)
        self.pt_model.set_df(pt_df)

        # Update tab labels
        self.tabs.setTabText(0, f"Triangles ({tri_count})")
        self.tabs.setTabText(1, f"Points ({pt_count})")

        self._update_compare()

    def _build_tables(self, triangle_indices: Set[int]):
        """Build triangle and point DataFrames from selection."""
        tri = getattr(self.main_window, "triangle_data", None)
        data = getattr(self.main_window, "filtered_data", None)
        if data is None:
            data = getattr(self.main_window, "data", None)
        if tri is None or tri.empty or data is None or len(triangle_indices) == 0:
            return pd.DataFrame(), pd.DataFrame()

        want = set()
        try:
            want = set(int(v) for v in triangle_indices)
        except Exception:
            want = set(triangle_indices)

        try:
            idx = tri.index
            if hasattr(idx, "dtype") and str(getattr(idx, "dtype", "")).startswith(("int", "uint")):
                take = idx.intersection(list(want))
                subset = tri.loc[take].copy()
            else:
                subset = tri.loc[idx.isin(list(want))].copy()
        except Exception:
            subset = pd.DataFrame()

        if subset.empty:
            return pd.DataFrame(), pd.DataFrame()

        subset = subset.assign(triangle_row=subset.index.astype(int))
        if "point_ids" in subset.columns:
            subset["point_ids"] = subset["point_ids"].apply(
                lambda v: ", ".join([str(x) for x in v]) if isinstance(v, (list, tuple, np.ndarray)) else str(v)
            )
        if "point_row_labels" in subset.columns:
            subset["point_row_labels"] = subset["point_row_labels"].apply(
                lambda v: ", ".join([str(x) for x in v]) if isinstance(v, (list, tuple, np.ndarray)) else str(v)
            )

        tri_cols = ["triangle_row", "gradient", "angle", "centroid_x", "centroid_y", "point_ids", "point_row_labels"]
        tri_cols = [c for c in tri_cols if c in subset.columns]
        tri_df = subset[tri_cols].sort_values(by="triangle_row", ascending=True)

        # Build points table
        point_rows = set()
        subset_orig = tri.loc[subset.index]
        if "point_row_labels" in subset_orig.columns:
            for v in subset_orig["point_row_labels"].to_list():
                if isinstance(v, (list, tuple, np.ndarray)):
                    point_rows.update(v)
                else:
                    point_rows.add(v)

        pt_df = pd.DataFrame()
        try:
            pts = None
            if point_rows:
                available = data.index.intersection(list(point_rows))
                pts = data.loc[available].copy()

            if (pts is None or pts.empty) and "point_ids" in subset_orig.columns:
                cm = getattr(self.main_window, "col_mapping", {}) or {}
                id_col = cm.get("ID")
                if id_col and id_col in data.columns:
                    want_ids = set()
                    for v in subset_orig["point_ids"].to_list():
                        if isinstance(v, (list, tuple, np.ndarray)):
                            want_ids.update([str(x) for x in v])
                        else:
                            want_ids.add(str(v))
                    if want_ids:
                        pts = data[data[id_col].astype(str).isin(sorted(want_ids))].copy()

            if pts is not None and not pts.empty:
                pts.insert(0, "row_label", pts.index.astype(str))
                cm = getattr(self.main_window, "col_mapping", {}) or {}
                preferred = []
                for k in ("ID", "x", "y", "hydraulic head"):
                    c = cm.get(k)
                    if c and c in pts.columns:
                        preferred.append(c)
                ordered = ["row_label"] + preferred + [c for c in pts.columns if c not in (["row_label"] + preferred)]
                pt_df = pts[ordered].reset_index(drop=True)
        except Exception:
            pt_df = pd.DataFrame()

        return tri_df.reset_index(drop=True), pt_df

    def _update_compare(self):
        """Update the compare tab with A/B stats."""
        if not self._compare_a or not self._compare_b:
            self.compare_empty.setVisible(True)
            self.compare_stats.setVisible(False)
            self.tabs.setTabText(2, "Compare")
            return

        tri = getattr(self.main_window, "triangle_data", None)
        if tri is None or tri.empty:
            self.compare_empty.setVisible(True)
            self.compare_stats.setVisible(False)
            return

        self.compare_empty.setVisible(False)
        self.compare_stats.setVisible(True)

        a = set(int(v) for v in self._compare_a)
        b = set(int(v) for v in self._compare_b)
        tri_inter = sorted(a.intersection(b))
        tri_union = sorted(a.union(b))

        def points_for(tri_set: Set[int]) -> Set[str]:
            if "point_row_labels" not in tri.columns or not tri_set:
                return set()
            try:
                sub = tri.loc[tri.index.astype(int).isin(list(tri_set))]
            except Exception:
                return set()
            out = set()
            for v in sub["point_row_labels"].to_list():
                if isinstance(v, (list, tuple, np.ndarray)):
                    out.update([str(x) for x in v])
                else:
                    out.add(str(v))
            return out

        pts_a = points_for(a)
        pts_b = points_for(b)
        pts_inter = sorted(pts_a.intersection(pts_b))

        # Update label
        self.compare_label.setText(
            f"Triangles: |A|={len(a)} |B|={len(b)} |A∩B|={len(tri_inter)} |A∪B|={len(tri_union)}   •   "
            f"Points (row labels): |A∩B|={len(pts_inter)}"
        )

        # Clear and rebuild stats grid
        while self.stats_grid.count():
            item = self.stats_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Create stat cards
        card_a = _make_stat_card("Set A Triangles", str(len(a)), "A", Colors.INFO)
        self.stats_grid.addWidget(card_a)

        card_b = _make_stat_card("Set B Triangles", str(len(b)), "B", Colors.WARNING)
        self.stats_grid.addWidget(card_b)

        card_inter = _make_stat_card("Intersection (A∩B)", str(len(tri_inter)), "A∩B", Colors.SUCCESS)
        self.stats_grid.addWidget(card_inter)

        card_union = _make_stat_card("Union (A∪B)", str(len(tri_union)))
        self.stats_grid.addWidget(card_union)

        # Update tab label
        self.tabs.setTabText(2, f"Compare (A∩B={len(tri_inter)})")
