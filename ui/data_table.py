"""
HeadAnalyser V2 - Data Table Widget.

Responsibilities:
- Present tabular data for the active dataset.
- Drive row-level include/exclude actions.
- Keep selection and exclusion styling synchronized with plot/map state.

Data-flow rule:
- This module mutates exclusion state, then delegates recompute/refresh to
  `MainWindow.refilter_and_recalculate()` (the central pipeline).
"""

import pandas as pd
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableView, QHeaderView,
    QLabel, QStackedWidget, QLineEdit, QSizePolicy, QMenu,
    QAction, QApplication, QToolButton, QShortcut, QFrame,
    QStyledItemDelegate, QStyle, QPushButton
)
from PyQt5.QtCore import (
    Qt, QAbstractTableModel, QModelIndex, QVariant,
    pyqtSignal, QSortFilterProxyModel, QTimer, QRect
)
from PyQt5.QtGui import QFont, QColor, QKeySequence, QPainter, QPen, QBrush

from styles.colors import Colors
from styles.stylesheet import StyleSheet
from .theme_utils import reset_widget_layout


# ── Custom roles ──
ROLE_EXCLUDED = Qt.UserRole + 1
ROLE_FLASH = Qt.UserRole + 2


class PandasModel(QAbstractTableModel):
    """Qt model for pandas DataFrame with excluded-row awareness."""

    def __init__(self, data=None, parent=None):
        super().__init__(parent)
        self._data = data if data is not None else pd.DataFrame()
        self.main_window = None
        self._flash_rows = set()  # Source rows currently flashing

    def rowCount(self, parent=QModelIndex()):
        return len(self._data)

    def columnCount(self, parent=QModelIndex()):
        return len(self._data.columns)

    def _is_excluded(self, row):
        """Check if a row's ID is in the excluded set."""
        if self.main_window is None:
            return False
        excluded = getattr(self.main_window, 'excluded_ids', set())
        excluded_member_keys = {str(v) for v in getattr(self.main_window, "excluded_member_keys", set())}
        if (not excluded and not excluded_member_keys) or self._data.empty:
            return False
        try:
            id_col = self._get_id_column_name()
            row_id = self._data.iloc[row, 0] if id_col is None else self._data.iloc[row][id_col]
            member_key = f"{str(row_id)}::{str(self._data.index[row])}"
            return (row_id in excluded) or (str(row_id) in excluded) or (member_key in excluded_member_keys)
        except (IndexError, KeyError):
            return False

    def _get_id_column_name(self):
        """Resolve the logical ID column from mapping, fallback to first column."""
        if self._data is None or self._data.empty:
            return None
        try:
            col_map = getattr(self.main_window, "col_mapping", {}) if self.main_window is not None else {}
            id_col = col_map.get("ID") if isinstance(col_map, dict) else None
            if id_col and id_col in self._data.columns:
                return id_col
        except Exception:
            pass
        try:
            return self._data.columns[0]
        except Exception:
            return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return QVariant()

        row = index.row()
        col = index.column()

        if role == Qt.DisplayRole:
            value = self._data.iloc[row, col]
            if pd.isna(value):
                return ""
            if isinstance(value, float):
                return f"{value:.4f}"
            return str(value)

        if role == Qt.TextAlignmentRole:
            if col == 0:
                return Qt.AlignLeft | Qt.AlignVCenter
            return Qt.AlignRight | Qt.AlignVCenter

        if role == Qt.ForegroundRole:
            if self._is_excluded(row):
                return QColor(Colors.TEXT_MUTED)
            if col == 0:
                # ID column in accent color for visual pop
                return QColor(Colors.ACCENT_BRIGHT)
            return QColor(Colors.TEXT_SECONDARY)

        if role == Qt.FontRole:
            if self._is_excluded(row):
                font = QFont("Consolas, 'IBM Plex Mono', monospace" if col > 0 else "")
                font.setPixelSize(12)
                font.setItalic(True)
                if col == 0:
                    font.setStrikeOut(True)
                return font
            if col == 0:
                font = QFont()
                font.setPixelSize(12)
                font.setWeight(QFont.DemiBold)
                return font
            # Numeric columns: monospace (matches triangle table look)
            font = QFont("Consolas, 'IBM Plex Mono', monospace")
            font.setPixelSize(12)
            return font

        if role == Qt.BackgroundRole:
            if row in self._flash_rows:
                return QColor(129, 140, 248, 40)  # accent glow flash
            return QVariant()

        if role == ROLE_EXCLUDED:
            return self._is_excluded(row)

        if role == ROLE_FLASH:
            return row in self._flash_rows

        return QVariant()

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return QVariant()

        if orientation == Qt.Horizontal:
            return str(self._data.columns[section])
        return str(section + 1)

    def set_data(self, data):
        self.beginResetModel()
        self._data = data
        self._flash_rows.clear()
        self.endResetModel()

    def set_main_window(self, main_window):
        self.main_window = main_window

    def refresh_excluded_display(self):
        """Signal that excluded state may have changed - repaint all rows."""
        if self._data.empty:
            return
        top_left = self.index(0, 0)
        bottom_right = self.index(self.rowCount() - 1, self.columnCount() - 1)
        self.dataChanged.emit(top_left, bottom_right, [Qt.ForegroundRole, Qt.FontRole, ROLE_EXCLUDED])

    def flash_row(self, source_row):
        """Start a flash highlight for a row."""
        self._flash_rows.add(source_row)
        if self.columnCount() > 0:
            top_left = self.index(source_row, 0)
            bottom_right = self.index(source_row, self.columnCount() - 1)
            self.dataChanged.emit(top_left, bottom_right, [Qt.BackgroundRole])

    def clear_flash(self, source_row):
        """End flash highlight for a row."""
        self._flash_rows.discard(source_row)
        if source_row < self.rowCount() and self.columnCount() > 0:
            top_left = self.index(source_row, 0)
            bottom_right = self.index(source_row, self.columnCount() - 1)
            self.dataChanged.emit(top_left, bottom_right, [Qt.BackgroundRole])

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemIsEnabled
        if index.column() == 0:
            return Qt.ItemIsEnabled | Qt.ItemIsSelectable
        else:
            return Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable

    def setData(self, index, value, role=Qt.EditRole):
        if not index.isValid() or role != Qt.EditRole:
            return False

        row = index.row()
        col = index.column()

        if col == 0:
            return False

        try:
            col_name = self._data.columns[col]
            dtype = self._data[col_name].dtype

            if dtype in ['float64', 'float32']:
                new_value = float(value)
            elif dtype in ['int64', 'int32']:
                new_value = int(value)
            else:
                new_value = str(value)

            self._data.iat[row, col] = new_value
            self.dataChanged.emit(index, index, [Qt.EditRole])

            if self.main_window:
                self.main_window.on_table_data_change()

            return True
        except (ValueError, TypeError):
            return False

    def get_row_id(self, row):
        if row < 0 or row >= len(self._data):
            return None
        id_col = self._get_id_column_name()
        if id_col is None:
            return None
        try:
            return str(self._data.iloc[row][id_col])
        except Exception:
            return None

    def find_row_by_id(self, id_value):
        if self._data.empty:
            return -1
        id_col = self._get_id_column_name()
        if id_col is None:
            return -1
        matches = self._data.index[self._data[id_col].astype(str) == str(id_value)]
        if len(matches) > 0:
            return int(matches[0])
        return -1


class AccentBarDelegate(QStyledItemDelegate):
    """Delegate that draws a colored accent bar on the left edge of selected rows."""

    def paint(self, painter, option, index):
        super().paint(painter, option, index)

        # Draw accent bar on leftmost column of selected rows
        if index.column() == 0 and (option.state & QStyle.State_Selected):
            painter.save()
            painter.setRenderHint(QPainter.Antialiasing, False)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(Colors.ACCENT_PRIMARY))
            bar = QRect(option.rect.left(), option.rect.top(), 3, option.rect.height())
            painter.drawRect(bar)
            painter.restore()


class TableFilterProxyModel(QSortFilterProxyModel):
    """Proxy model that supports text search AND excluded-state filtering."""

    FILTER_ALL = 0
    FILTER_INCLUDED = 1
    FILTER_EXCLUDED = 2

    def __init__(self, parent=None):
        super().__init__(parent)
        self._exclude_filter = self.FILTER_ALL

    def set_exclude_filter(self, mode):
        self._exclude_filter = mode
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row, source_parent):
        if self._exclude_filter != self.FILTER_ALL:
            source_model = self.sourceModel()
            if source_model is not None:
                idx = source_model.index(source_row, 0, source_parent)
                is_excluded = source_model.data(idx, ROLE_EXCLUDED)
                if self._exclude_filter == self.FILTER_INCLUDED and is_excluded:
                    return False
                if self._exclude_filter == self.FILTER_EXCLUDED and not is_excluded:
                    return False
        return super().filterAcceptsRow(source_row, source_parent)


class DataTableWidget(QWidget):
    """Widget for displaying data in a table with search, selection sync,
    context menu, excluded-row styling, filter toggles, and summary footer."""

    # Signals
    row_selected = pyqtSignal(str)       # Emits first point ID (backwards compat)
    row_deselected = pyqtSignal()
    rows_selected = pyqtSignal(list)     # Emits all selected IDs as list of str
    rows_selected_member_keys = pyqtSignal(list)  # Emits selected member keys (`ID::row_index`)
    inspect_requested = pyqtSignal(list) # Emits selected point IDs for triangle inspection

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self._programmatic_select = False
        self._flash_timers = {}  # {source_row: QTimer}

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.stack = QStackedWidget()

        # ── Empty state ──
        self.empty_widget = QWidget()
        empty_layout = QVBoxLayout(self.empty_widget)
        empty_layout.setAlignment(Qt.AlignCenter)
        empty_label = QLabel("No Data Available\n\nLoad a file to view data table")
        empty_label.setAlignment(Qt.AlignCenter)
        empty_label.setStyleSheet(f"""
            color: {Colors.TEXT_MUTED};
            font-size: 15px;
            font-weight: 300;
            line-height: 1.8;
        """)
        empty_layout.addWidget(empty_label)
        self.stack.addWidget(self.empty_widget)

        # ── Table page ──
        table_page = QWidget()
        table_page_layout = QVBoxLayout(table_page)
        table_page_layout.setContentsMargins(0, 0, 0, 0)
        table_page_layout.setSpacing(0)

        # Search / filter toolbar
        search_bar = QWidget()
        search_bar.setStyleSheet(f"""
            QWidget {{
                background-color: {Colors.BG_PANEL};
                border-bottom: 1px solid {Colors.BORDER_DEFAULT};
            }}
        """)
        search_layout = QHBoxLayout(search_bar)
        search_layout.setContentsMargins(12, 6, 12, 6)
        search_layout.setSpacing(8)

        # Search input (no separate icon - use placeholder with unicode)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("\u2315  Filter rows...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {Colors.BG_SURFACE};
                color: {Colors.TEXT_PRIMARY};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 6px;
                padding: 5px 12px;
                font-size: 12px;
            }}
            QLineEdit:focus {{
                border-color: {Colors.ACCENT_PRIMARY};
            }}
        """)
        self.search_input.textChanged.connect(self._on_search_changed)
        search_layout.addWidget(self.search_input, 1)

        # Filter toggle pills: All | Included | Excluded
        self._filter_pills = []
        pill_container = QWidget()
        pill_container.setStyleSheet("border: none; background: transparent;")
        pill_layout = QHBoxLayout(pill_container)
        pill_layout.setContentsMargins(0, 0, 0, 0)
        pill_layout.setSpacing(2)

        for label, mode in [("All", TableFilterProxyModel.FILTER_ALL),
                            ("Included", TableFilterProxyModel.FILTER_INCLUDED),
                            ("Excluded", TableFilterProxyModel.FILTER_EXCLUDED)]:
            btn = QToolButton()
            btn.setText(label)
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setProperty("filter_mode", mode)
            if mode == TableFilterProxyModel.FILTER_ALL:
                btn.setChecked(True)
            btn.clicked.connect(self._on_filter_pill_clicked)
            self._filter_pills.append(btn)
            pill_layout.addWidget(btn)

        self._apply_pill_styles()
        search_layout.addWidget(pill_container)

        table_page_layout.addWidget(search_bar)

        # Table view — match triangle table structure
        self.table_view = QTableView()
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setSelectionBehavior(QTableView.SelectRows)
        self.table_view.setSelectionMode(QTableView.ExtendedSelection)
        self.table_view.setSortingEnabled(True)
        self.table_view.setShowGrid(False)
        self.table_view.setWordWrap(False)
        self.table_view.setMouseTracking(True)

        # Accent bar delegate for selected-row left stripe
        self._delegate = AccentBarDelegate(self.table_view)
        self.table_view.setItemDelegate(self._delegate)

        # Context menu
        self.table_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table_view.customContextMenuRequested.connect(self._show_context_menu)

        # Column resize: interactive with stretch last
        header = self.table_view.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(True)
        header.setHighlightSections(False)
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header.setSortIndicatorShown(True)
        header.setCursor(Qt.PointingHandCursor)
        header.setMinimumSectionSize(60)
        header.setDefaultSectionSize(110)

        # Hide vertical header (row numbers) — ID column is the identifier
        self.table_view.verticalHeader().setVisible(False)
        self.table_view.verticalHeader().setDefaultSectionSize(34)

        # Model + proxy
        self.model = PandasModel()
        self.proxy_model = TableFilterProxyModel()
        self.proxy_model.setSourceModel(self.model)
        self.proxy_model.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.proxy_model.setFilterKeyColumn(-1)

        self.table_view.setModel(self.proxy_model)

        # Apply polished table styling (matches triangle table look)
        self.table_view.setStyleSheet(
            StyleSheet.get_table_base_style()
            + f"""
            QScrollBar:horizontal {{
                background: transparent;
                height: 6px;
                margin: 0;
            }}
            QScrollBar::handle:horizontal {{
                background: {Colors.BG_HOVER};
                border-radius: 3px;
                min-width: 20px;
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                width: 0;
            }}
            """
        )

        # Enable editing
        self.table_view.setEditTriggers(QTableView.DoubleClicked | QTableView.EditKeyPressed)

        # Selection changed -> emit signal
        self.table_view.selectionModel().selectionChanged.connect(self._on_selection_changed)

        table_page_layout.addWidget(self.table_view, 1)

        # ── Summary footer ──
        self.footer = QWidget()
        self.footer.setFixedHeight(30)
        self.footer.setStyleSheet(f"""
            QWidget {{
                background-color: {Colors.BG_PANEL};
                border-top: 1px solid {Colors.BORDER_SUBTLE};
            }}
        """)
        footer_layout = QHBoxLayout(self.footer)
        footer_layout.setContentsMargins(16, 0, 16, 0)
        footer_layout.setSpacing(12)

        # Keyboard hints (left)
        hints = [("E", "Exclude"), ("I", "Include"), ("Esc", "Deselect")]
        for key, action in hints:
            hint = QLabel()
            hint.setTextFormat(Qt.RichText)
            hint.setText(
                f'<span style="font-family: monospace; font-size: 9px; color: {Colors.TEXT_TERTIARY}; '
                f'background: {Colors.BG_SURFACE}; padding: 1px 5px; border-radius: 3px;">{key}</span>'
                f'<span style="font-size: 10px; color: {Colors.TEXT_MUTED};"> {action}</span>'
            )
            hint.setStyleSheet("border: none; background: transparent;")
            footer_layout.addWidget(hint)

        dblclick = QLabel("Double-click to edit")
        dblclick.setStyleSheet(f"font-size: 10px; color: {Colors.TEXT_MUTED}; border: none; background: transparent;")
        footer_layout.addWidget(dblclick)

        footer_layout.addStretch()

        # Row count chip (in footer instead of duplicate in search bar)
        self.row_count_label = QLabel("0 rows")
        self.row_count_label.setStyleSheet(f"""
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
        footer_layout.addWidget(self.row_count_label)

        # Accent dot separator
        sep_dot = QLabel("\u2022")
        sep_dot.setStyleSheet(f"color: {Colors.BORDER_STRONG}; font-size: 8px; border: none; background: transparent;")
        footer_layout.addWidget(sep_dot)

        # Selection status (right)
        self.footer_selection_label = QLabel("")
        self.footer_selection_label.setStyleSheet(f"""
            font-size: 10px;
            font-weight: 600;
            color: {Colors.ACCENT_PRIMARY};
            border: none;
            background: transparent;
        """)
        footer_layout.addWidget(self.footer_selection_label)

        # Inspect Triangles button (hidden until selection)
        self.inspect_triangles_btn = QPushButton("Inspect Triangles")
        self.inspect_triangles_btn.setCursor(Qt.PointingHandCursor)
        self.inspect_triangles_btn.setVisible(False)
        self.inspect_triangles_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.ACCENT_GHOST};
                border: 1px solid rgba(129, 140, 248, 0.15);
                border-radius: 10px;
                color: {Colors.ACCENT_BRIGHT};
                font-size: 10px;
                font-weight: 600;
                padding: 3px 12px;
            }}
            QPushButton:hover {{
                border-color: {Colors.ACCENT_PRIMARY};
                color: {Colors.TEXT_PRIMARY};
            }}
        """)
        self.inspect_triangles_btn.clicked.connect(self._on_inspect_clicked)
        footer_layout.addWidget(self.inspect_triangles_btn)

        table_page_layout.addWidget(self.footer)

        self.stack.addWidget(table_page)
        self.stack.setCurrentIndex(0)
        layout.addWidget(self.stack)

        # Keyboard shortcuts
        QShortcut(QKeySequence("Ctrl+C"), self.table_view).activated.connect(self._copy_selected_row)
        QShortcut(QKeySequence("Escape"), self.table_view).activated.connect(self.clear_highlight)

    # ── Pill styling ──

    def _apply_pill_styles(self):
        for btn in self._filter_pills:
            if btn.isChecked():
                btn.setStyleSheet(f"""
                    QToolButton {{
                        background-color: {Colors.ACCENT_PRIMARY};
                        border: 1px solid {Colors.ACCENT_PRIMARY};
                        color: {Colors.TEXT_PRIMARY};
                        font-size: 10px; font-weight: 600;
                        padding: 3px 10px; border-radius: 10px;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QToolButton {{
                        background-color: {Colors.BG_SURFACE};
                        border: 1px solid {Colors.BORDER_DEFAULT};
                        color: {Colors.TEXT_TERTIARY};
                        font-size: 10px; font-weight: 500;
                        padding: 3px 10px; border-radius: 10px;
                    }}
                    QToolButton:hover {{
                        border-color: {Colors.ACCENT_PRIMARY};
                        color: {Colors.TEXT_PRIMARY};
                    }}
                """)

    def _on_filter_pill_clicked(self):
        sender = self.sender()
        mode = sender.property("filter_mode")
        for btn in self._filter_pills:
            btn.setChecked(btn is sender)
        self._apply_pill_styles()
        self.proxy_model.set_exclude_filter(mode)
        self._update_row_count()

    def _on_search_changed(self, text):
        self.proxy_model.setFilterFixedString(text)
        self._update_row_count()

    def _update_row_count(self):
        total = self.model.rowCount()
        shown = self.proxy_model.rowCount()
        if total == 0:
            self.row_count_label.setText("0 rows")
        elif shown == total:
            self.row_count_label.setText(f"{total} rows")
        else:
            self.row_count_label.setText(f"{shown} of {total}")

    def apply_theme(self):
        data = self.model._data.copy() if self.model._data is not None else None
        search_text = self.search_input.text() if hasattr(self, "search_input") else ""
        filter_mode = getattr(self.proxy_model, "_exclude_filter", TableFilterProxyModel.FILTER_ALL)
        selected_ids = self._get_selected_ids() if hasattr(self, "_get_selected_ids") else []

        reset_widget_layout(self)

        self._setup_ui()
        self.set_main_window(self.main_window)
        self.set_data(data)
        self.search_input.setText(search_text)
        self.proxy_model.set_exclude_filter(filter_mode)
        for btn in self._filter_pills:
            btn.setChecked(btn.property("filter_mode") == filter_mode)
        self._apply_pill_styles()
        if selected_ids:
            self.highlight_rows_by_ids(selected_ids)

    # ── Selection ──

    def _on_inspect_clicked(self):
        """Emit inspect_requested with currently selected point IDs."""
        ids = self._get_selected_ids()
        if ids:
            self.inspect_requested.emit(ids)

    def _on_selection_changed(self, selected, deselected):
        if self._programmatic_select:
            return

        indexes = self.table_view.selectionModel().selectedRows()
        if indexes:
            # Collect all selected IDs
            ids = []
            for proxy_idx in indexes:
                source_idx = self.proxy_model.mapToSource(proxy_idx)
                row_id = self.model.get_row_id(source_idx.row())
                if row_id is not None:
                    ids.append(row_id)

            if ids:
                member_keys = self._get_selected_member_keys()
                # Emit first ID for backwards compat (single-point highlight)
                self.row_selected.emit(ids[0])
                # Emit full list for multi-select features
                self.rows_selected.emit(ids)
                self.rows_selected_member_keys.emit(member_keys)

                if len(ids) == 1:
                    self.footer_selection_label.setText(
                        f"\u25CF  {ids[0]} selected \u2014 synced with plot")
                else:
                    self.footer_selection_label.setText(
                        f"\u25CF  {len(ids)} points selected \u2014 synced with plot")

                # Show inspect button
                self.inspect_triangles_btn.setText(f"Inspect Triangles ({len(ids)})")
                self.inspect_triangles_btn.setVisible(True)
            else:
                self.inspect_triangles_btn.setVisible(False)
        else:
            self.row_deselected.emit()
            self.rows_selected.emit([])
            self.rows_selected_member_keys.emit([])
            self.footer_selection_label.setText("")
            self.inspect_triangles_btn.setVisible(False)

    # ── Flash animation ──

    def _flash_source_row(self, source_row):
        """Briefly flash a row with accent glow."""
        # Cancel existing flash on this row
        if source_row in self._flash_timers:
            self._flash_timers[source_row].stop()

        self.model.flash_row(source_row)

        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda r=source_row: self._end_flash(r))
        timer.start(500)
        self._flash_timers[source_row] = timer

    def _end_flash(self, source_row):
        self.model.clear_flash(source_row)
        self._flash_timers.pop(source_row, None)

    # ── Context menu ──

    def _show_context_menu(self, pos):
        index = self.table_view.indexAt(pos)
        if not index.isValid():
            return

        source_index = self.proxy_model.mapToSource(index)
        row = source_index.row()
        row_id = self.model.get_row_id(row)
        if row_id is None:
            return

        menu = QMenu(self)

        # Exclude / Include for all selected rows
        selected_ids = self._get_selected_ids()
        selected_member_keys = self._get_selected_member_keys()
        if not selected_ids:
            selected_ids = [row_id]
            clicked_member_key = self._member_key_for_row(row, row_id=row_id)
            selected_member_keys = [clicked_member_key] if clicked_member_key else []

        is_excluded = self.model._is_excluded(row)
        if is_excluded:
            action_text = f"Include Point ({row_id})" if len(selected_ids) == 1 else f"Include {len(selected_ids)} Points"
            act = QAction(action_text, self)
            act.triggered.connect(lambda: self._include_points(selected_ids, selected_member_keys))
            menu.addAction(act)
        else:
            action_text = f"Exclude Point ({row_id})" if len(selected_ids) == 1 else f"Exclude {len(selected_ids)} Points"
            act = QAction(action_text, self)
            act.triggered.connect(lambda: self._exclude_points(selected_ids, selected_member_keys))
            menu.addAction(act)

        menu.addSeparator()

        copy_act = QAction("Copy Row(s)  (Ctrl+C)", self)
        copy_act.triggered.connect(self._copy_selected_row)
        menu.addAction(copy_act)

        copy_cell = QAction("Copy Cell", self)
        copy_cell.triggered.connect(lambda: self._copy_cell(index))
        menu.addAction(copy_cell)

        menu.exec_(self.table_view.viewport().mapToGlobal(pos))

    def _get_selected_ids(self):
        """Get all selected point IDs."""
        ids = []
        for proxy_idx in self.table_view.selectionModel().selectedRows():
            source_idx = self.proxy_model.mapToSource(proxy_idx)
            row_id = self.model.get_row_id(source_idx.row())
            if row_id is not None:
                ids.append(row_id)
        return ids

    def _member_key_for_row(self, source_row, row_id=None):
        """Build the row member key used for duplicate-ID exclusion targeting."""
        if source_row < 0 or source_row >= self.model.rowCount():
            return None
        rid = str(row_id) if row_id is not None else self.model.get_row_id(source_row)
        if not rid:
            return None
        try:
            row_index = str(self.model._data.index[source_row])
        except Exception:
            return None
        return f"{rid}::{row_index}"

    def _get_selected_member_keys(self):
        """Get member keys for selected rows (stable for duplicate IDs)."""
        member_keys = []
        for proxy_idx in self.table_view.selectionModel().selectedRows():
            source_idx = self.proxy_model.mapToSource(proxy_idx)
            row = source_idx.row()
            row_id = self.model.get_row_id(row)
            if row_id is None:
                continue
            mkey = self._member_key_for_row(row, row_id=row_id)
            if mkey:
                member_keys.append(mkey)
        return member_keys

    def _exclude_points(self, row_ids, member_keys=None):
        if self.main_window is None:
            return
        changed = False
        if member_keys:
            # Member-level exclusion: keep duplicate-ID members independent.
            for rid, mkey in zip(list(row_ids or []), list(member_keys or [])):
                try:
                    changed = bool(
                        self.main_window.apply_point_exclusion(
                            str(rid), member_key=str(mkey or ""), exclude=True
                        )
                    ) or changed
                except Exception:
                    pass
        else:
            for rid in row_ids:
                try:
                    changed = bool(
                        self.main_window.apply_point_exclusion(str(rid), member_key="", exclude=True)
                    ) or changed
                except Exception:
                    pass
        if changed:
            self.main_window.refilter_and_recalculate()
            self.model.refresh_excluded_display()

    def _include_points(self, row_ids, member_keys=None):
        if self.main_window is None:
            return
        changed = False
        if member_keys:
            for rid, mkey in zip(list(row_ids or []), list(member_keys or [])):
                try:
                    changed = bool(
                        self.main_window.apply_point_exclusion(
                            str(rid), member_key=str(mkey or ""), exclude=False
                        )
                    ) or changed
                except Exception:
                    pass
        else:
            for rid in row_ids:
                try:
                    changed = bool(
                        self.main_window.apply_point_exclusion(str(rid), member_key="", exclude=False)
                    ) or changed
                except Exception:
                    pass
                # Legacy include-by-ID behavior: if no explicit member keys were provided,
                # include all duplicate-ID members currently tracked.
                try:
                    prefix = f"{str(rid)}::"
                    stale = [mk for mk in self.main_window.excluded_member_keys if str(mk).startswith(prefix)]
                    if stale:
                        changed = True
                    for mk in stale:
                        self.main_window.excluded_member_keys.discard(mk)
                except Exception:
                    pass
        if changed:
            self.main_window.refilter_and_recalculate()
            self.model.refresh_excluded_display()

    # Keep old single-point methods for backwards compat
    def _exclude_point(self, row_id):
        self._exclude_points([row_id])

    def _include_point(self, row_id):
        self._include_points([row_id])

    def _copy_selected_row(self):
        indexes = self.table_view.selectionModel().selectedRows()
        if not indexes:
            return
        lines = []
        for proxy_idx in indexes:
            source_idx = self.proxy_model.mapToSource(proxy_idx)
            row = source_idx.row()
            cols = []
            for c in range(self.model.columnCount()):
                val = self.model.data(self.model.index(row, c), Qt.DisplayRole)
                cols.append(str(val) if val else "")
            lines.append("\t".join(cols))
        QApplication.clipboard().setText("\n".join(lines))

    def _copy_cell(self, proxy_index):
        source_index = self.proxy_model.mapToSource(proxy_index)
        val = self.model.data(source_index, Qt.DisplayRole)
        QApplication.clipboard().setText(str(val) if val else "")

    # ── Public API ──

    def highlight_row_by_id(self, id_value):
        """Scroll to and select the row matching the given point ID, with flash."""
        source_row = self.model.find_row_by_id(id_value)
        if source_row < 0:
            return

        source_index = self.model.index(source_row, 0)
        proxy_index = self.proxy_model.mapFromSource(source_index)
        if not proxy_index.isValid():
            return

        self._programmatic_select = True
        self.table_view.selectRow(proxy_index.row())
        self.table_view.scrollTo(proxy_index)
        self._programmatic_select = False

        # Flash the row
        self._flash_source_row(source_row)

        self.footer_selection_label.setText(f"\u25CF  {id_value} selected \u2014 synced with plot")

    def highlight_rows_by_ids(self, id_values):
        """Select multiple rows by ID list, with flash."""
        if not id_values:
            self.clear_highlight()
            return

        self._programmatic_select = True
        self.table_view.clearSelection()

        selection = self.table_view.selectionModel()
        first_proxy_index = None

        for id_val in id_values:
            source_row = self.model.find_row_by_id(id_val)
            if source_row < 0:
                continue
            source_index = self.model.index(source_row, 0)
            proxy_index = self.proxy_model.mapFromSource(source_index)
            if not proxy_index.isValid():
                continue

            # Select the whole row
            selection.select(
                self.proxy_model.index(proxy_index.row(), 0),
                selection.Select | selection.Rows
            )
            self._flash_source_row(source_row)

            if first_proxy_index is None:
                first_proxy_index = proxy_index

        if first_proxy_index is not None:
            self.table_view.scrollTo(first_proxy_index)

        self._programmatic_select = False

        if len(id_values) == 1:
            self.footer_selection_label.setText(
                f"\u25CF  {id_values[0]} selected \u2014 synced with plot")
        else:
            self.footer_selection_label.setText(
                f"\u25CF  {len(id_values)} points selected \u2014 synced with plot")

    def clear_highlight(self):
        self._programmatic_select = True
        self.table_view.clearSelection()
        self._programmatic_select = False
        # Programmatic clear bypasses _on_selection_changed; emit explicit deselection
        # so plot/map sync are cleared when user presses Esc in the table.
        try:
            self.row_deselected.emit()
            self.rows_selected.emit([])
            self.rows_selected_member_keys.emit([])
        except Exception:
            pass
        self.footer_selection_label.setText("")
        self.inspect_triangles_btn.setVisible(False)

    def set_main_window(self, main_window):
        self.model.set_main_window(main_window)

    def set_data(self, data):
        self.model.set_data(data)
        if data is not None and not data.empty:
            self.stack.setCurrentIndex(1)
            self._update_row_count()

            try:
                header = self.table_view.horizontalHeader()
                header.resizeSection(0, 80)
                for c in range(1, self.model.columnCount()):
                    header.resizeSection(c, 110)
            except Exception:
                pass

            try:
                self.table_view.selectionModel().selectionChanged.disconnect(self._on_selection_changed)
            except (TypeError, RuntimeError):
                pass
            self.table_view.selectionModel().selectionChanged.connect(self._on_selection_changed)
        else:
            self.stack.setCurrentIndex(0)

    def clear_data(self):
        self.model.set_data(pd.DataFrame())
        self.stack.setCurrentIndex(0)

    def refresh_excluded_styling(self):
        self.model.refresh_excluded_display()
