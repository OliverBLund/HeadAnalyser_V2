"""
Map-side table drawer.

Holds data/triangle table widgets and exposes a small API so MapWidget can
delegate drawer UI concerns without owning drawer internals.
"""

from PyQt5.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve, QTimer
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSizePolicy,
    QButtonGroup,
    QStackedWidget,
    QToolButton,
    QLabel,
)

from styles.colors import Colors
from ..data_table import DataTableWidget


class MapTableDrawer(QWidget):
    """Bottom drawer with Data/Triangles modes for map interactions."""

    tableRowSelected = pyqtSignal(str)
    tableRowsSelected = pyqtSignal(list)
    tableRowDeselected = pyqtSignal()
    triangleSelectionChanged = pyqtSignal(list)

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self._main_window = main_window
        self._table_anim = None
        self._triangle_table = None
        self._triangle_table_loading = False
        self._triangle_data = None
        self._rejected_data = None

        self.setObjectName("tableContainer")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMaximumHeight(0)
        self.setStyleSheet(
            f"""
            #tableContainer {{
                background-color: {Colors.BG_PANEL};
                border-top: 1px solid {Colors.BORDER_DEFAULT};
            }}
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QWidget()
        header.setFixedHeight(34)
        header.setStyleSheet(
            f"background-color: {Colors.BG_SURFACE}; border-bottom: 1px solid {Colors.BORDER_DEFAULT};"
        )
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(10, 0, 10, 0)
        header_layout.setSpacing(6)

        self._drawer_mode_group = QButtonGroup(self)
        self._drawer_mode_group.setExclusive(True)

        self._data_mode_btn = QToolButton()
        self._data_mode_btn.setText("Data")
        self._data_mode_btn.setCheckable(True)
        self._data_mode_btn.setChecked(True)
        self._drawer_mode_group.addButton(self._data_mode_btn, 0)
        header_layout.addWidget(self._data_mode_btn)

        self._tri_mode_btn = QToolButton()
        self._tri_mode_btn.setText("Triangles")
        self._tri_mode_btn.setCheckable(True)
        self._drawer_mode_group.addButton(self._tri_mode_btn, 1)
        header_layout.addWidget(self._tri_mode_btn)

        self._drawer_mode_group.idClicked.connect(self._on_drawer_mode_changed)
        header_layout.addStretch()

        self._row_count = QLabel("0 rows")
        self._row_count.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 10px;")
        header_layout.addWidget(self._row_count)
        layout.addWidget(header)

        self.data_table = DataTableWidget(self._main_window)
        self.data_table.row_selected.connect(self.tableRowSelected.emit)
        self.data_table.rows_selected.connect(self.tableRowsSelected.emit)
        self.data_table.row_deselected.connect(self.tableRowDeselected.emit)

        self._drawer_stack = QStackedWidget()
        self._drawer_stack.addWidget(self.data_table)  # index 0
        layout.addWidget(self._drawer_stack)

    def toggle_panel(self):
        self._toggle_table(not self.is_open())

    def ensure_visible(self):
        if not self.is_open():
            self._toggle_table(True)

    def is_open(self):
        return bool(int(self.maximumHeight()) > 0)

    def current_mode(self):
        return int(self._drawer_stack.currentIndex())

    def switch_to_data_mode_if_open(self):
        if self.is_open() and self.current_mode() != 0:
            self._data_mode_btn.setChecked(True)
            self._drawer_stack.setCurrentIndex(0)
            self._update_row_count()

    def set_data(self, data):
        self.data_table.set_data(data)
        self._update_row_count()

    def refresh_triangle_data(self, triangle_data, rejected_data):
        self._triangle_data = triangle_data
        self._rejected_data = rejected_data
        if self._triangle_table is None:
            return
        if self._triangle_table_loading:
            return
        self._triangle_table_loading = True
        try:
            from ..triangle_widgets.triangle_data_helper import TriangleDataHelper

            combined = TriangleDataHelper.build_combined_triangle_df(self._triangle_data, self._rejected_data)
            self._triangle_table.update_data(combined)
        except Exception:
            pass
        finally:
            self._triangle_table_loading = False
            self._update_row_count()

    def current_triangle_combined_df(self):
        try:
            if self._triangle_table is not None:
                return self._triangle_table._model._df
        except Exception:
            return None
        return None

    def highlight_rows_by_ids(self, point_ids):
        self.data_table.highlight_rows_by_ids(point_ids)

    def clear_highlight(self):
        self.data_table.clear_highlight()

    def _toggle_table(self, checked):
        if self._table_anim is None:
            self._table_anim = QPropertyAnimation(self, b"maximumHeight")
            self._table_anim.setDuration(300)
            self._table_anim.setEasingCurve(QEasingCurve.InOutCubic)
        if checked:
            target = 280
            try:
                target = max(200, min(420, int(self.parent().height() * 0.38)))
            except Exception:
                target = 280
            self._table_anim.setStartValue(0)
            self._table_anim.setEndValue(int(target))
            self._table_anim.start()
            return
        self._table_anim.setStartValue(int(self.maximumHeight()))
        self._table_anim.setEndValue(0)
        self._table_anim.start()

    def _on_drawer_mode_changed(self, button_id):
        if int(button_id) == 1:
            self._ensure_triangle_table()
        self._drawer_stack.setCurrentIndex(int(button_id))
        self._update_row_count()

    def _ensure_triangle_table(self):
        if self._triangle_table is not None:
            return
        from ..triangle_widgets.triangle_table import TriangleTableWidget

        self._triangle_table = TriangleTableWidget()
        self._triangle_table.triangle_selected.connect(self.triangleSelectionChanged.emit)
        self._drawer_stack.addWidget(self._triangle_table)  # index 1
        self._row_count.setText("Loading triangles...")
        QTimer.singleShot(0, lambda: self.refresh_triangle_data(self._triangle_data, self._rejected_data))

    def _update_row_count(self):
        try:
            if self._drawer_stack.currentIndex() == 0:
                total = self.data_table.model.rowCount()
                shown = self.data_table.proxy_model.rowCount()
                if total == 0:
                    self._row_count.setText("0 rows")
                elif shown == total:
                    self._row_count.setText(f"{total} rows")
                else:
                    self._row_count.setText(f"{shown} of {total}")
                return
            if self._triangle_table is None:
                self._row_count.setText("0 triangles")
                return
            visible = self._triangle_table._proxy.rowCount()
            loaded = self._triangle_table._model.rowCount()
            total = getattr(self._triangle_table._model, "total_count", loaded)
            if total > loaded:
                self._row_count.setText(f"{visible} of {total} triangles")
            else:
                self._row_count.setText(f"{visible} triangles")
        except Exception:
            pass
