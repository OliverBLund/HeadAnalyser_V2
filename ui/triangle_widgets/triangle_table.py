"""
Triangle table widget with filter pills (All/Kept/Rejected) and text search.
Pill-style badges for Status and Reason columns via QStyledItemDelegate.
"""

from __future__ import annotations

import os
import time
from typing import Optional

import numpy as np
import pandas as pd
from PyQt5.QtCore import (
    QAbstractTableModel, QModelIndex, QRect, QSortFilterProxyModel, Qt,
    QVariant, pyqtSignal, QSize,
)
from PyQt5.QtGui import QBrush, QColor, QFont, QFontMetrics, QPainter, QPen, QKeySequence
from PyQt5.QtWidgets import (
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QPushButton,
    QSizePolicy, QStyledItemDelegate, QStyle, QStyleOptionViewItem,
    QTableView, QVBoxLayout, QWidget, QFrame, QShortcut,
)

from styles.colors import Colors
from styles.stylesheet import StyleSheet
from ui.icons import icon, Icons


FILTER_ALL = 0
FILTER_KEPT = 1
FILTER_REJECTED = 2

_COLUMNS = ["#", "POINTS", "STATUS", "GRADIENT", "ANGLE", "REASON"]

# Reason → display label
_REASON_DISPLAY = {
    "thin_triangle": "thin_triangle",
    "stacked_points": "stacked_points",
    "uncertainty": "uncertainty",
    "max_base_or_height": "base/height",
    "mixed": "mixed",
    "calculation_failed": "calc_failed",
}

# Reason → color
_REASON_COLORS = {
    "thin_triangle": Colors.REJECTION_THIN,
    "stacked_points": Colors.REJECTION_STACKED,
    "uncertainty": Colors.REJECTION_UNCERTAINTY,
    "max_base_or_height": Colors.REJECTION_BASE_HEIGHT,
    "mixed": Colors.REJECTION_THIN,
    "calculation_failed": Colors.REJECTION_CALC_FAILED,
}


# ──────────────────────────────────────────────────────────
# Custom Delegates
# ──────────────────────────────────────────────────────────

class _PillDelegate(QStyledItemDelegate):
    """Draws a colored pill badge (dot + text) for Status and Reason columns."""

    # Column type constants
    COL_STATUS = "status"
    COL_REASON = "reason"

    def __init__(self, col_type: str, parent=None):
        super().__init__(parent)
        self._col_type = col_type

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        # Draw base (selection highlight, alternating bg)
        self.initStyleOption(option, index)
        style = option.widget.style() if option.widget else None

        # Draw background only (no text)
        opt = QStyleOptionViewItem(option)
        opt.text = ""
        if style:
            style.drawControl(QStyle.CE_ItemViewItem, opt, painter, option.widget)

        text = str(index.data(Qt.DisplayRole) or "")
        if not text:
            # For empty reason on kept rows, draw "—"
            if self._col_type == self.COL_REASON:
                painter.save()
                painter.setPen(QPen(QColor(Colors.TEXT_MUTED)))
                font = QFont()
                font.setPixelSize(11)
                painter.setFont(font)
                painter.drawText(option.rect, Qt.AlignCenter, "\u2014")
                painter.restore()
            return

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        if self._col_type == self.COL_STATUS:
            self._draw_status_pill(painter, option.rect, text)
        elif self._col_type == self.COL_REASON:
            self._draw_reason_pill(painter, option.rect, text)

        painter.restore()

    def _draw_status_pill(self, painter: QPainter, rect: QRect, status: str):
        is_kept = status.lower() == "kept"
        dot_color = QColor(Colors.SUCCESS if is_kept else Colors.ERROR)
        text_color = QColor(Colors.SUCCESS if is_kept else Colors.ERROR)
        bg_color = QColor(Colors.SUCCESS if is_kept else Colors.ERROR)
        bg_color.setAlpha(20)
        label = "Kept" if is_kept else "Rejected"

        font = QFont()
        font.setPixelSize(11)
        font.setWeight(QFont.DemiBold)
        fm = QFontMetrics(font)
        text_w = fm.horizontalAdvance(label)

        # Pill dimensions
        dot_r = 5
        dot_gap = 5
        h_pad = 10
        pill_w = h_pad + dot_r * 2 + dot_gap + text_w + h_pad
        pill_h = 22

        # Center in cell
        x = rect.x() + (rect.width() - pill_w) // 2
        y = rect.y() + (rect.height() - pill_h) // 2

        # Draw pill background
        painter.setPen(Qt.NoPen)
        painter.setBrush(bg_color)
        painter.drawRoundedRect(x, y, pill_w, pill_h, pill_h / 2, pill_h / 2)

        # Draw dot
        dot_x = x + h_pad
        dot_y = y + (pill_h - dot_r * 2) // 2
        painter.setBrush(dot_color)
        painter.drawEllipse(dot_x, dot_y, dot_r * 2, dot_r * 2)

        # Draw text
        painter.setPen(QPen(text_color))
        painter.setFont(font)
        text_x = dot_x + dot_r * 2 + dot_gap
        text_rect = QRect(text_x, y, pill_w - (text_x - x) - h_pad, pill_h)
        painter.drawText(text_rect, Qt.AlignLeft | Qt.AlignVCenter, label)

    def _draw_reason_pill(self, painter: QPainter, rect: QRect, reason: str):
        color_hex = _REASON_COLORS.get(reason, Colors.REJECTION_CALC_FAILED)
        text_color = QColor(color_hex)
        bg_color = QColor(color_hex)
        bg_color.setAlpha(18)
        border_color = QColor(color_hex)
        border_color.setAlpha(40)

        label = _REASON_DISPLAY.get(reason, reason)

        font = QFont()
        font.setPixelSize(10)
        font.setWeight(QFont.DemiBold)
        fm = QFontMetrics(font)
        text_w = fm.horizontalAdvance(label)

        h_pad = 8
        pill_w = text_w + h_pad * 2
        pill_h = 20

        x = rect.x() + (rect.width() - pill_w) // 2
        y = rect.y() + (rect.height() - pill_h) // 2

        # Draw pill bg + border
        painter.setPen(QPen(border_color, 1.0))
        painter.setBrush(bg_color)
        painter.drawRoundedRect(x, y, pill_w, pill_h, pill_h / 2, pill_h / 2)

        # Draw text
        painter.setPen(QPen(text_color))
        painter.setFont(font)
        painter.drawText(QRect(x, y, pill_w, pill_h), Qt.AlignCenter, label)

    def sizeHint(self, option, index):
        hint = super().sizeHint(option, index)
        hint.setHeight(max(hint.height(), 34))
        return hint


class _MonoDelegate(QStyledItemDelegate):
    """Renders numeric cells in monospace font, right-aligned."""

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        self.initStyleOption(option, index)
        style = option.widget.style() if option.widget else None

        # Draw background only
        opt = QStyleOptionViewItem(option)
        opt.text = ""
        if style:
            style.drawControl(QStyle.CE_ItemViewItem, opt, painter, option.widget)

        text = str(index.data(Qt.DisplayRole) or "")
        if not text or text == "-":
            painter.save()
            painter.setPen(QPen(QColor(Colors.TEXT_MUTED)))
            font = QFont()
            font.setPixelSize(11)
            painter.setFont(font)
            painter.drawText(option.rect.adjusted(0, 0, -8, 0), Qt.AlignRight | Qt.AlignVCenter, "\u2014")
            painter.restore()
            return

        painter.save()
        font = QFont("Consolas, 'IBM Plex Mono', monospace")
        font.setPixelSize(12)
        font.setWeight(QFont.Normal)

        # Color: accent for gradient, secondary for angle
        col = index.column()
        if col == 3:
            painter.setPen(QPen(QColor(Colors.TEXT_PRIMARY)))
        else:
            painter.setPen(QPen(QColor(Colors.TEXT_SECONDARY)))

        painter.setFont(font)
        painter.drawText(option.rect.adjusted(0, 0, -8, 0), Qt.AlignRight | Qt.AlignVCenter, text)
        painter.restore()


# ──────────────────────────────────────────────────────────
# Table Model
# ──────────────────────────────────────────────────────────

class TriangleTableModel(QAbstractTableModel):
    """Table model backed by a combined triangle DataFrame."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._df: pd.DataFrame = pd.DataFrame()  # Full backing DataFrame (compat alias)
        self._loaded_rows = 0
        try:
            self._initial_rows = max(
                200, int(os.getenv("HEADANALYSER_TRIANGLE_TABLE_INITIAL_ROWS", "2000"))
            )
        except Exception:
            self._initial_rows = 2000
        try:
            self._fetch_chunk_rows = max(
                200, int(os.getenv("HEADANALYSER_TRIANGLE_TABLE_FETCH_CHUNK_ROWS", "2000"))
            )
        except Exception:
            self._fetch_chunk_rows = 2000
        self._kept_count = 0
        self._rejected_count = 0
        self._sort_col = -1
        self._sort_order = Qt.AscendingOrder

    @property
    def kept_count(self) -> int:
        return self._kept_count

    @property
    def rejected_count(self) -> int:
        return self._rejected_count

    @property
    def total_count(self) -> int:
        return int(len(self._df))

    @property
    def loaded_count(self) -> int:
        return int(self._loaded_rows)

    def rowCount(self, parent=QModelIndex()):
        return int(self._loaded_rows)

    def columnCount(self, parent=QModelIndex()):
        return len(_COLUMNS)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or index.row() >= int(self._loaded_rows):
            return QVariant()

        row = self._df.iloc[index.row()]
        col = index.column()

        if role == Qt.DisplayRole:
            if col == 0:  # #
                return str(index.row() + 1)
            elif col == 1:  # Points
                ids = row.get("point_ids", "")
                if isinstance(ids, (list, tuple, np.ndarray)):
                    return " \u2013 ".join(str(v) for v in ids)
                return str(ids) if not pd.isna(ids) else ""
            elif col == 2:  # Status
                return str(row.get("status", ""))
            elif col == 3:  # Gradient
                g = row.get("gradient")
                if pd.isna(g) if not isinstance(g, (list, tuple, np.ndarray)) else False:
                    return ""
                if isinstance(g, (list, np.ndarray)):
                    g = g[0] if len(g) > 0 else np.nan
                try:
                    return f"{float(g):.5f}"
                except (ValueError, TypeError):
                    return ""
            elif col == 4:  # Angle
                a = row.get("angle")
                if pd.isna(a) if isinstance(a, (float, int, np.floating, np.integer)) else a is None:
                    return ""
                try:
                    return f"{float(a):.1f}\u00b0"
                except (ValueError, TypeError):
                    return ""
            elif col == 5:  # Reason
                r = row.get("reason", "")
                return str(r) if r and not (isinstance(r, float) and np.isnan(r)) else ""

        elif role == Qt.ForegroundRole:
            # Default text colors (delegates override for special columns)
            if col == 0:
                return QColor(Colors.TEXT_MUTED)
            elif col == 1:
                return QColor(Colors.TEXT_PRIMARY)

        elif role == Qt.FontRole:
            if col == 1:
                font = QFont()
                font.setPixelSize(12)
                font.setWeight(QFont.DemiBold)
                return font

        elif role == Qt.TextAlignmentRole:
            if col == 0:
                return Qt.AlignCenter
            if col in (3, 4):
                return Qt.AlignRight | Qt.AlignVCenter

        elif role == Qt.UserRole:
            if col == 2:
                return str(row.get("status", ""))

        # Sort role: return raw numeric for gradient/angle
        elif role == Qt.UserRole + 1:
            if col == 3:
                g = row.get("gradient")
                if isinstance(g, (list, np.ndarray)):
                    g = g[0] if len(g) > 0 else np.nan
                try:
                    return float(g)
                except (ValueError, TypeError):
                    return -1.0
            elif col == 4:
                a = row.get("angle")
                try:
                    return float(a)
                except (ValueError, TypeError):
                    return -1.0
            elif col == 0:
                return index.row()
            return str(self.data(index, Qt.DisplayRole) or "")

        return QVariant()

    def set_sort_indicator(self, col: int, order):
        self._sort_col = col
        self._sort_order = order
        self.headerDataChanged.emit(Qt.Horizontal, 0, len(_COLUMNS) - 1)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal and section < len(_COLUMNS):
            text = _COLUMNS[section]
            if section == self._sort_col:
                arrow = " \u25b2" if self._sort_order == Qt.AscendingOrder else " \u25bc"
                text += arrow
            return text
        if role == Qt.FontRole and orientation == Qt.Horizontal:
            font = QFont()
            font.setPixelSize(10)
            font.setWeight(QFont.Bold)
            font.setLetterSpacing(QFont.AbsoluteSpacing, 0.8)
            return font
        return QVariant()

    def flags(self, index):
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable

    def set_df(self, df: pd.DataFrame):
        self.beginResetModel()
        self._df = df if df is not None else pd.DataFrame()
        self._loaded_rows = min(int(self._initial_rows), int(len(self._df)))
        if not self._df.empty and "status" in self._df.columns:
            statuses = self._df["status"]
            self._kept_count = int((statuses == "kept").sum())
            self._rejected_count = int((statuses == "rejected").sum())
        else:
            self._kept_count = 0
            self._rejected_count = 0
        self.endResetModel()

    def canFetchMore(self, parent=QModelIndex()):
        return int(self._loaded_rows) < int(len(self._df))

    def fetchMore(self, parent=QModelIndex()):
        if not self.canFetchMore(parent):
            return
        remaining = int(len(self._df)) - int(self._loaded_rows)
        add_rows = min(int(self._fetch_chunk_rows), remaining)
        if add_rows <= 0:
            return
        first = int(self._loaded_rows)
        last = int(self._loaded_rows + add_rows - 1)
        self.beginInsertRows(QModelIndex(), first, last)
        self._loaded_rows += add_rows
        self.endInsertRows()


class TriangleFilterProxy(QSortFilterProxyModel):
    """Proxy that filters by status and text search."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._filter_mode = FILTER_ALL
        self._search_text = ""
        self._search_tokens = []
        self.setSortRole(Qt.UserRole + 1)

    def set_filter_mode(self, mode: int):
        self._filter_mode = mode
        self.invalidateFilter()

    def set_search_text(self, text: str):
        self._search_text = text.lower().strip()
        self._search_tokens = self._search_text.split() if self._search_text else []
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        model = self.sourceModel()
        if model is None:
            return True

        # Status filter
        if self._filter_mode != FILTER_ALL:
            status_idx = model.index(source_row, 2, source_parent)
            status = model.data(status_idx, Qt.UserRole)
            if self._filter_mode == FILTER_KEPT and status != "kept":
                return False
            if self._filter_mode == FILTER_REJECTED and status != "rejected":
                return False

        # Text search
        if self._search_tokens:
            if len(self._search_tokens) == 1:
                # Single token: match against ANY column (current behavior)
                token = self._search_tokens[0]
                for col in range(model.columnCount()):
                    idx = model.index(source_row, col, source_parent)
                    text = str(model.data(idx, Qt.DisplayRole) or "").lower()
                    if token in text:
                        return True
                return False
            else:
                # Multi-token: ALL tokens must appear in the POINTS column (col 1)
                points_idx = model.index(source_row, 1, source_parent)
                points_text = str(model.data(points_idx, Qt.DisplayRole) or "").lower()
                return all(tok in points_text for tok in self._search_tokens)

        return True


# ──────────────────────────────────────────────────────────
# Table Widget
# ──────────────────────────────────────────────────────────

class TriangleTableWidget(QWidget):
    """Complete triangle table with toolbar, filter pills, and search."""

    triangle_hovered = pyqtSignal(int)
    triangle_selected = pyqtSignal(list)
    filter_changed = pyqtSignal(str)  # "all", "kept", or "rejected"
    triangle_double_clicked = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        try:
            self._large_mode_row_threshold = max(
                1000, int(os.getenv("HEADANALYSER_TRIANGLE_TABLE_LARGE_MODE_ROWS", "10000"))
            )
        except Exception:
            self._large_mode_row_threshold = 10000
        self._large_mode_active = False
        self._perf_enabled = str(os.getenv("HEADANALYSER_PERF_LOG", "1")).strip().lower() in {
            "1", "true", "yes", "on"
        }
        self._selected_source_rows = set()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(4)

        # Filter pills with icons
        self._pill_all = self._make_pill("All", "fa6s.list", checked=True)
        self._pill_kept = self._make_pill("Kept", "fa6s.circle-check")
        self._pill_rejected = self._make_pill("Rejected", "fa6s.circle-xmark")

        self._pill_all.clicked.connect(lambda: self._set_filter(FILTER_ALL))
        self._pill_kept.clicked.connect(lambda: self._set_filter(FILTER_KEPT))
        self._pill_rejected.clicked.connect(lambda: self._set_filter(FILTER_REJECTED))

        toolbar.addWidget(self._pill_all)
        toolbar.addWidget(self._pill_kept)
        toolbar.addWidget(self._pill_rejected)
        toolbar.addStretch()

        # Search input with icon
        self._search = QLineEdit()
        self._search.setPlaceholderText("⌕  Search... (space = AND)")
        self._search.setFixedWidth(180)
        self._search.setFixedHeight(28)
        self._search.setStyleSheet(f"""
            QLineEdit {{
                background-color: {Colors.BG_SURFACE};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 8px;
                color: {Colors.TEXT_SECONDARY};
                font-size: 11px;
                padding: 4px 10px 4px 12px;
            }}
            QLineEdit:focus {{
                border-color: {Colors.ACCENT_PRIMARY};
                background-color: {Colors.BG_ELEVATED};
            }}
        """)
        self._search.textChanged.connect(self._on_search_changed)
        toolbar.addWidget(self._search)

        # Row count chip
        self._count_label = QLabel("0 rows")
        self._count_label.setStyleSheet(f"""
            color: {Colors.TEXT_MUTED};
            font-size: 10px;
            font-weight: 600;
            background: transparent;
            padding-left: 6px;
        """)
        toolbar.addWidget(self._count_label)
        self._perf_mode_label = QLabel("")
        self._perf_mode_label.setVisible(False)
        self._perf_mode_label.setStyleSheet(f"""
            color: {Colors.WARNING};
            font-size: 10px;
            font-weight: 700;
            background: transparent;
            padding-left: 6px;
        """)
        toolbar.addWidget(self._perf_mode_label)
        layout.addLayout(toolbar)

        # Table view
        self._model = TriangleTableModel()
        self._proxy = TriangleFilterProxy()
        self._proxy.setSourceModel(self._model)

        self._table = QTableView()
        self._table.setModel(self._proxy)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QTableView.SelectRows)
        self._table.setSelectionMode(QTableView.ExtendedSelection)
        self._table.setSortingEnabled(True)
        self._table.setShowGrid(False)
        self._table.setEditTriggers(QTableView.NoEditTriggers)
        self._table.setWordWrap(False)
        self._table.horizontalHeader().setHighlightSections(False)
        self._table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._table.verticalHeader().setDefaultSectionSize(34)
        self._table.verticalHeader().setVisible(False)

        # Column sizing
        h = self._table.horizontalHeader()
        h.setSectionResizeMode(QHeaderView.Stretch)
        h.setSectionResizeMode(0, QHeaderView.Fixed)       # #
        h.setSectionResizeMode(2, QHeaderView.Fixed)       # Status
        h.setSectionResizeMode(3, QHeaderView.Fixed)       # Gradient
        h.setSectionResizeMode(4, QHeaderView.Fixed)       # Angle
        h.setSectionResizeMode(5, QHeaderView.Fixed)       # Reason
        self._table.setColumnWidth(0, 36)
        self._table.setColumnWidth(2, 100)
        self._table.setColumnWidth(3, 100)
        self._table.setColumnWidth(4, 76)
        self._table.setColumnWidth(5, 120)

        # Assign custom delegates
        self._status_delegate = _PillDelegate(_PillDelegate.COL_STATUS, self._table)
        self._table.setItemDelegateForColumn(2, self._status_delegate)

        self._reason_delegate = _PillDelegate(_PillDelegate.COL_REASON, self._table)
        self._table.setItemDelegateForColumn(5, self._reason_delegate)

        self._grad_delegate = _MonoDelegate(self._table)
        self._table.setItemDelegateForColumn(3, self._grad_delegate)

        self._angle_delegate = _MonoDelegate(self._table)
        self._table.setItemDelegateForColumn(4, self._angle_delegate)

        self._table.setStyleSheet(StyleSheet.get_table_base_style())

        # Connect hover signal
        # Changed from entered (hover) to clicked for performance
        self._table.clicked.connect(self._on_row_entered)
        self._table.setMouseTracking(True)
        self._table.doubleClicked.connect(self._on_row_double_clicked)
        self._table.verticalScrollBar().valueChanged.connect(self._on_table_scrolled)

        # Selection changed -> emit triangle_selected with source row indices
        self._table.selectionModel().selectionChanged.connect(self._on_selection_changed)
        QShortcut(QKeySequence("Escape"), self._table).activated.connect(self._clear_selection_shortcut)

        # Track sort state for header indicator
        self._sort_column = -1
        self._sort_order = Qt.AscendingOrder
        self._table.horizontalHeader().sortIndicatorChanged.connect(self._on_sort_changed)

        # Built-in compact details popup (works in both stats panel and inspector).
        self._detail_popup = self._create_detail_popup()
        self._detail_popup.hide()

        layout.addWidget(self._table, 1)

    def _perf_log(self, message: str):
        if self._perf_enabled:
            print(message, flush=True)

    def _set_large_mode(self, enabled: bool):
        enabled = bool(enabled)
        if enabled == self._large_mode_active:
            return
        self._large_mode_active = enabled

        # Sorting on very large models can freeze the UI.
        self._table.setSortingEnabled(not enabled)
        try:
            self._proxy.setDynamicSortFilter(not enabled)
            if enabled:
                self._proxy.sort(-1, Qt.AscendingOrder)
        except Exception:
            pass
        if enabled:
            self._perf_mode_label.setText(
                f"Perf mode: sort off (>{self._large_mode_row_threshold:,})"
            )
            self._perf_mode_label.setToolTip(
                "Automatic table sorting is disabled for large datasets to keep UI responsive."
            )
            self._perf_mode_label.setVisible(True)
        else:
            self._perf_mode_label.setVisible(False)
            self._perf_mode_label.setText("")
            self._perf_mode_label.setToolTip("")

    def _create_detail_popup(self):
        popup = QFrame(self)
        popup.setObjectName("triangleRowDetailPopup")
        popup.setFixedWidth(320)
        popup.setStyleSheet(f"""
            QFrame#triangleRowDetailPopup {{
                background-color: {Colors.BG_ELEVATED};
                border: 1px solid {Colors.BORDER_MEDIUM};
                border-radius: 8px;
            }}
        """)

        layout = QVBoxLayout(popup)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(5)

        header = QHBoxLayout()
        header.setSpacing(8)
        title = QLabel("Triangle Details")
        title.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; font-size: 11px; font-weight: 700;")
        header.addWidget(title)
        header.addStretch()
        close_btn = QPushButton("\u2715")
        close_btn.setFixedSize(20, 20)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                border-radius: 5px;
                color: {Colors.TEXT_TERTIARY};
                font-size: 11px;
            }}
            QPushButton:hover {{
                background-color: {Colors.BG_HOVER};
                color: {Colors.TEXT_PRIMARY};
            }}
        """)
        close_btn.clicked.connect(popup.hide)
        header.addWidget(close_btn)
        layout.addLayout(header)

        self._detail_title = QLabel("\u2014")
        self._detail_title.setStyleSheet(f"color: {Colors.TEXT_TERTIARY}; font-size: 10px;")
        layout.addWidget(self._detail_title)

        self._detail_reasons = QLabel("\u2014")
        self._detail_reasons.setWordWrap(True)
        self._detail_reasons.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 10px;")
        layout.addWidget(self._detail_reasons)

        def _row(label_text):
            row = QHBoxLayout()
            row.setSpacing(6)
            label = QLabel(label_text)
            label.setFixedWidth(88)
            label.setStyleSheet(f"color: {Colors.TEXT_TERTIARY}; font-size: 9px;")
            value = QLabel("\u2014")
            value.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 10px;")
            value.setWordWrap(True)
            row.addWidget(label)
            row.addWidget(value, 1)
            layout.addLayout(row)
            return value

        self._detail_sides = _row("Sides")
        self._detail_heights = _row("Heights")
        self._detail_ratios = _row("Ratios")
        self._detail_hrange = _row("Head range")
        self._detail_area = _row("Area")
        self._detail_thresholds = _row("Thresholds")

        return popup

    def _fmt_detail_value(self, value):
        if value is None:
            return "\u2014"
        if isinstance(value, (list, tuple, np.ndarray)):
            return ", ".join(str(v) for v in value) if len(value) else "\u2014"
        try:
            if pd.isna(value):
                return "\u2014"
        except Exception:
            pass
        if isinstance(value, dict):
            return ", ".join(f"{k}={v}" for k, v in value.items())
        return str(value)

    def _show_detail_popup(self, source_row: int, proxy_index: QModelIndex):
        if source_row is None or source_row < 0 or source_row >= self._model.rowCount():
            return
        try:
            row = self._model._df.iloc[int(source_row)]
        except Exception:
            return

        ids = row.get("point_ids", None)
        if isinstance(ids, (list, tuple, np.ndarray)):
            title = " \u2013 ".join(str(v) for v in ids)
        else:
            title = self._fmt_detail_value(ids)
        self._detail_title.setText(f"Triangle: {title}")

        flags = row.get("reason_flags", None)
        if isinstance(flags, (list, tuple, np.ndarray)) and len(flags) > 0:
            reasons_text = ", ".join(str(v) for v in flags)
        else:
            reasons_text = self._fmt_detail_value(row.get("reason", None))
        checks = []
        if bool(row.get("quality_is_stacked_points", False)):
            checks.append("stacked_points")
        if bool(row.get("quality_is_thin_triangle", False)):
            checks.append("thin_triangle")
        if bool(row.get("quality_is_uncertainty", False)):
            checks.append("uncertainty")
        if bool(row.get("quality_is_max_base_or_height", False)):
            checks.append("max_base_or_height")
        if bool(row.get("quality_is_calculation_failed", False)):
            checks.append("calculation_failed")
        if len(checks) > 0:
            reasons_text = f"{reasons_text} | checks: {', '.join(checks)}"
        self._detail_reasons.setText(f"Reasons: {reasons_text}")

        self._detail_sides.setText(self._fmt_detail_value(row.get("quality_side_lengths", None)))
        self._detail_heights.setText(self._fmt_detail_value(row.get("quality_heights", None)))
        self._detail_ratios.setText(self._fmt_detail_value(row.get("quality_base_height_ratio", None)))
        self._detail_hrange.setText(self._fmt_detail_value(row.get("quality_h_range", None)))
        self._detail_area.setText(self._fmt_detail_value(row.get("quality_area", None)))
        self._detail_thresholds.setText(self._fmt_detail_value(row.get("quality_thresholds", None)))

        self._detail_popup.adjustSize()

        # Anchor vertically to the clicked row and keep the popup in-bounds.
        rect = self._table.visualRect(proxy_index)
        anchor = self._table.viewport().mapToGlobal(rect.topRight())
        local_anchor = self.mapFromGlobal(anchor)
        x = min(max(local_anchor.x() + 8, 8), max(8, self.width() - self._detail_popup.width() - 8))
        y = int(local_anchor.y() + rect.height() / 2 - self._detail_popup.height() / 2)
        y = min(max(y, 8), max(8, self.height() - self._detail_popup.height() - 8))
        self._detail_popup.move(x, y)
        self._detail_popup.raise_()
        self._detail_popup.show()

    def _make_pill(self, text: str, icon_name: str, checked: bool = False) -> QPushButton:
        """Create a filter pill button with FontAwesome icon."""
        btn = QPushButton(f" {text}")
        btn.setIcon(icon(icon_name, color=Colors.TEXT_MUTED))
        btn.setIconSize(QSize(12, 12))
        btn.setCheckable(True)
        btn.setChecked(checked)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFixedHeight(28)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.BG_SURFACE};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 14px;
                color: {Colors.TEXT_MUTED};
                font-size: 11px; font-weight: 600;
                padding: 0 14px 0 12px;
                text-align: left;
            }}
            QPushButton:hover {{
                color: {Colors.TEXT_SECONDARY};
                border-color: {Colors.BORDER_MEDIUM};
            }}
            QPushButton:checked {{
                background-color: {Colors.ACCENT_GHOST};
                color: {Colors.ACCENT_BRIGHT};
                border-color: rgba(129, 140, 248, 0.25);
            }}
        """)
        return btn

    def _set_filter(self, mode: int):
        self._pill_all.setChecked(mode == FILTER_ALL)
        self._pill_kept.setChecked(mode == FILTER_KEPT)
        self._pill_rejected.setChecked(mode == FILTER_REJECTED)
        self._proxy.set_filter_mode(mode)
        self._update_count()
        mode_name = {FILTER_ALL: "all", FILTER_KEPT: "kept", FILTER_REJECTED: "rejected"}.get(mode, "all")
        self.filter_changed.emit(mode_name)

    def _on_search_changed(self, text: str):
        self._proxy.set_search_text(text)
        self._update_count()

    def _on_sort_changed(self, logical_index: int, order):
        self._sort_column = logical_index
        self._sort_order = order
        self._model.set_sort_indicator(logical_index, order)

    def _update_count(self):
        visible = self._proxy.rowCount()
        total_loaded = self._model.rowCount()
        total_all = getattr(self._model, "total_count", total_loaded)
        if total_all > total_loaded:
            self._count_label.setText(f"{visible} shown of {total_all} total")
        elif visible < total_loaded:
            self._count_label.setText(f"{visible} of {total_loaded} rows")
        else:
            self._count_label.setText(f"{total_loaded} rows")

    def _update_pill_counts(self):
        """Update filter pill labels with counts."""
        total = getattr(self._model, "total_count", self._model.rowCount())
        kept = self._model.kept_count
        rejected = self._model.rejected_count
        self._pill_all.setText(f"All ({total})")
        self._pill_kept.setText(f"Kept ({kept})")
        self._pill_rejected.setText(f"Rejected ({rejected})")

    def _on_table_scrolled(self, value: int):
        """Lazy-load additional rows when scrolling near the bottom."""
        try:
            sb = self._table.verticalScrollBar()
            max_val = int(sb.maximum())
            if max_val <= 0:
                return
            near_bottom = int(value) >= max_val - max(8, int(sb.pageStep() * 0.25))
            if not near_bottom:
                return
            if self._model.canFetchMore(QModelIndex()):
                t0 = time.perf_counter()
                self._model.fetchMore(QModelIndex())
                self._update_count()
                self._perf_log(
                    f"[perf][triangle-table] fetch_more loaded={self._model.loaded_count} "
                    f"total={self._model.total_count} dt={(time.perf_counter() - t0) * 1000.0:.1f}ms"
                )
        except Exception:
            pass

    def _on_selection_changed(self, selected, deselected):
        """Emit triangle_selected with selected source row indices (incremental update)."""
        try:
            # Apply only changed selections to avoid rescanning all selected rows each click.
            for proxy_idx in selected.indexes():
                if proxy_idx.column() != 0:
                    continue
                source_idx = self._proxy.mapToSource(proxy_idx)
                if source_idx.isValid():
                    self._selected_source_rows.add(int(source_idx.row()))

            for proxy_idx in deselected.indexes():
                if proxy_idx.column() != 0:
                    continue
                source_idx = self._proxy.mapToSource(proxy_idx)
                if source_idx.isValid():
                    self._selected_source_rows.discard(int(source_idx.row()))

            indices = sorted(self._selected_source_rows)
            self.triangle_selected.emit(indices)
        except Exception:
            self._selected_source_rows = set()
            self.triangle_selected.emit([])

    def _clear_selection_shortcut(self):
        """Clear table selection and emit deselection for overlay sync."""
        try:
            self._table.clearSelection()
        except Exception:
            pass
        self._selected_source_rows = set()
        self.triangle_selected.emit([])
        try:
            self._detail_popup.hide()
        except Exception:
            pass

    def _on_row_entered(self, index):
        if index.isValid():
            source_index = self._proxy.mapToSource(index)
            if source_index.isValid():
                self.triangle_hovered.emit(source_index.row())

    def _on_row_double_clicked(self, index):
        if index.isValid():
            source_index = self._proxy.mapToSource(index)
            if source_index.isValid():
                source_row = source_index.row()
                self.triangle_double_clicked.emit(source_row)
                self._show_detail_popup(source_row, index)

    def get_row_rect_global(self, source_row: int):
        if source_row is None or source_row < 0:
            return None
        try:
            source_index = self._model.index(int(source_row), 0)
            proxy_index = self._proxy.mapFromSource(source_index)
            if not proxy_index.isValid():
                return None
            rect = self._table.visualRect(proxy_index)
            if rect.isNull():
                return None
            top_left = self._table.viewport().mapToGlobal(rect.topLeft())
            return QRect(top_left, rect.size())
        except Exception:
            return None

    def update_data(self, combined_df: pd.DataFrame):
        t0 = time.perf_counter()
        row_count = len(combined_df)
        large_mode = row_count >= int(self._large_mode_row_threshold)
        # Apply large-mode before model reset to avoid expensive proxy sort work.
        self._set_large_mode(large_mode)
        self._perf_log(
            f"[perf][triangle-table] start rows={row_count} "
            f"threshold={self._large_mode_row_threshold} large_mode={large_mode}"
        )
        # Reset filter pills to "All" on new data
        self._detail_popup.hide()
        self._set_filter(FILTER_ALL)
        self._selected_source_rows = set()
        t_set0 = time.perf_counter()
        self._model.set_df(combined_df)
        set_df_ms = (time.perf_counter() - t_set0) * 1000.0
        self._update_pill_counts()
        self._update_count()
        # Auto-size # column based on row count (36px min, grows for 1000+ rows)
        if row_count > 0:
            digits = len(str(row_count))
            col_width = max(36, digits * 10 + 16)  # ~10px per digit + padding
            self._table.setColumnWidth(0, col_width)

        sort_ms = 0.0
        # Default sort by gradient descending only when not in large mode.
        if (not large_mode) and (not combined_df.empty):
            t_sort0 = time.perf_counter()
            self._table.sortByColumn(3, Qt.DescendingOrder)
            sort_ms = (time.perf_counter() - t_sort0) * 1000.0

        total_ms = (time.perf_counter() - t0) * 1000.0
        self._perf_log(
            f"[perf][triangle-table] rows={row_count} large_mode={large_mode} "
            f"threshold={self._large_mode_row_threshold} set_df={set_df_ms:.1f}ms "
            f"sort={sort_ms:.1f}ms total={total_ms:.1f}ms"
        )

    def clear(self):
        self._detail_popup.hide()
        self._selected_source_rows = set()
        self._model.set_df(pd.DataFrame())
        self._update_pill_counts()
        self._update_count()
