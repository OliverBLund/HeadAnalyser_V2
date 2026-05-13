"""
HeadAnalyser V2 - Base Styled Table
Shared base class providing the dark-surface table visual design
(rounded corners, alternating rows, clean header, search bar, row count chip)
that both the raw-data table and the triangle table extend.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableView, QHeaderView,
    QLabel, QLineEdit, QSizePolicy, QFrame,
)
from PyQt5.QtCore import Qt

from styles.colors import Colors
from styles.stylesheet import StyleSheet


class BaseStyledTable(QWidget):
    """Base widget providing a styled QTableView with search bar and row count chip.

    Subclasses should:
      - Set ``self.table_view.setModel(...)`` with their own model/proxy
      - Populate ``self.filter_bar`` layout with filter pills
      - Override ``_on_search_changed`` if custom search logic is needed
      - Call ``update_row_count(filtered, total)`` to keep the chip current
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_base_ui()

    def _setup_base_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Toolbar row: filter pills + search + row count ──
        toolbar = QWidget()
        toolbar.setStyleSheet(f"""
            QWidget {{
                background-color: transparent;
            }}
        """)
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 4, 0, 4)
        toolbar_layout.setSpacing(4)

        # Filter bar (subclasses populate with pills)
        self.filter_bar = QHBoxLayout()
        self.filter_bar.setSpacing(4)
        toolbar_layout.addLayout(self.filter_bar)

        toolbar_layout.addStretch()

        # Search input
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search...")
        self.search_bar.setFixedWidth(170)
        self.search_bar.setFixedHeight(28)
        self.search_bar.setStyleSheet(f"""
            QLineEdit {{
                background-color: {Colors.BG_SURFACE};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 6px;
                color: {Colors.TEXT_SECONDARY};
                font-size: 11px;
                padding: 4px 10px;
            }}
            QLineEdit:focus {{
                border-color: {Colors.ACCENT_PRIMARY};
            }}
        """)
        self.search_bar.textChanged.connect(self._on_search_changed)
        toolbar_layout.addWidget(self.search_bar)

        # Row count chip
        self.row_count_label = QLabel("0 rows")
        self.row_count_label.setStyleSheet(f"""
            color: {Colors.TEXT_MUTED};
            font-size: 10px;
            font-weight: 600;
            background: transparent;
            padding-left: 6px;
        """)
        toolbar_layout.addWidget(self.row_count_label)

        layout.addWidget(toolbar)

        # ── Table view ──
        self.table_view = QTableView()
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setSelectionBehavior(QTableView.SelectRows)
        self.table_view.setSelectionMode(QTableView.SingleSelection)
        self.table_view.setSortingEnabled(True)
        self.table_view.setShowGrid(False)
        self.table_view.setEditTriggers(QTableView.NoEditTriggers)
        self.table_view.setWordWrap(False)
        self.table_view.horizontalHeader().setHighlightSections(False)
        self.table_view.horizontalHeader().setDefaultAlignment(
            Qt.AlignLeft | Qt.AlignVCenter
        )
        self.table_view.verticalHeader().setDefaultSectionSize(34)
        self.table_view.verticalHeader().setVisible(False)

        # Apply shared table style
        self.table_view.setStyleSheet(StyleSheet.get_table_base_style())

        layout.addWidget(self.table_view, 1)

    # ── Overridable hooks ──

    def _on_search_changed(self, text: str):
        """Override in subclasses to implement search filtering."""
        pass

    def update_row_count(self, filtered: int, total: int):
        """Update the row count chip label."""
        if total == 0:
            self.row_count_label.setText("0 rows")
        elif filtered == total:
            self.row_count_label.setText(f"{total} rows")
        else:
            self.row_count_label.setText(f"{filtered} of {total}")
