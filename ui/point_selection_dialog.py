"""
HeadAnalyser V2 - Point Selection Dialog
Dialog for selecting/excluding points from the dataset.
Premium design with header icon, unified search, stats bar, and status badges.
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QScrollArea, QWidget, QFrame, QSizePolicy
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont

from styles.colors import Colors
from qt_chrome import FramelessDialogMixin
from ui.icons import icon, Icons


class PointCheckboxItem(QFrame):
    """Custom checkbox item with premium styling and status badge."""

    toggled = pyqtSignal(bool)

    def __init__(self, point_id: str, is_checked: bool = True, parent=None):
        super().__init__(parent)
        self.point_id = point_id
        self._checked = is_checked
        self._setup_ui()
        self._update_state()

    def _setup_ui(self):
        """Setup the checkbox item UI."""
        self.setFixedHeight(40)
        self.setCursor(Qt.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(12)

        # Checkbox indicator
        self.check_box = QLabel()
        self.check_box.setFixedSize(18, 18)
        self.check_box.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.check_box)

        # Point label
        self.label = QLabel("Point")
        self.label.setStyleSheet(f"""
            font-size: 12px;
            font-weight: 500;
            color: {Colors.TEXT_PRIMARY};
        """)
        layout.addWidget(self.label)

        layout.addStretch()

        # Point ID badge
        self.id_badge = QLabel(str(self.point_id))
        self.id_badge.setStyleSheet(f"""
            font-family: 'Consolas', 'Monaco', monospace;
            font-size: 10px;
            font-weight: 600;
            color: {Colors.TEXT_SECONDARY};
            background-color: {Colors.BG_SURFACE};
            padding: 1px 6px;
            border-radius: 3px;
        """)
        layout.addWidget(self.id_badge)

        # Status badge
        self.status_badge = QLabel()
        self.status_badge.setFixedWidth(58)
        self.status_badge.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_badge)

    def _update_state(self):
        """Update visual state based on checked status."""
        if self._checked:
            # Checked state - included
            self.check_box.setStyleSheet(f"""
                background-color: {Colors.ACCENT_PRIMARY};
                border: 1.5px solid {Colors.ACCENT_PRIMARY};
                border-radius: 5px;
            """)
            self.check_box.setPixmap(icon(Icons.CHECK, color=Colors.TEXT_INVERSE).pixmap(10, 10))

            self.status_badge.setText("Included")
            self.status_badge.setStyleSheet(f"""
                font-size: 9px;
                font-weight: 500;
                color: {Colors.SUCCESS};
                background-color: {Colors.SUCCESS_BG};
                padding: 1px 5px;
                border-radius: 3px;
            """)

            self.setStyleSheet(f"""
                PointCheckboxItem {{
                    background-color: transparent;
                    border-radius: 0px;
                }}
                PointCheckboxItem:hover {{
                    background-color: {Colors.OVERLAY_HOVER};
                }}
            """)
            self.label.setStyleSheet(f"""
                font-size: 12px;
                font-weight: 500;
                color: {Colors.TEXT_PRIMARY};
            """)
        else:
            # Unchecked state - excluded
            self.check_box.setStyleSheet(f"""
                background-color: transparent;
                border: 1.5px solid {Colors.BORDER_MEDIUM};
                border-radius: 5px;
            """)
            self.check_box.clear()

            self.status_badge.setText("Excluded")
            self.status_badge.setStyleSheet(f"""
                font-size: 9px;
                font-weight: 500;
                color: {Colors.ERROR};
                background-color: {Colors.ERROR_BG};
                padding: 1px 5px;
                border-radius: 3px;
            """)

            self.setStyleSheet(f"""
                PointCheckboxItem {{
                    background-color: transparent;
                    border-radius: 0px;
                    opacity: 0.5;
                }}
                PointCheckboxItem:hover {{
                    background-color: {Colors.OVERLAY_HOVER};
                }}
            """)
            self.label.setStyleSheet(f"""
                font-size: 12px;
                font-weight: 500;
                color: {Colors.TEXT_MUTED};
            """)

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, checked: bool):
        if self._checked != checked:
            self._checked = checked
            self._update_state()
            self.toggled.emit(checked)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.setChecked(not self._checked)
        super().mousePressEvent(event)


class PointSelectionDialog(FramelessDialogMixin, QDialog):
    """Dialog for selecting points to exclude from analysis."""

    points_excluded = pyqtSignal(set)

    def __init__(self, current_data, currently_excluded, parent=None):
        super().__init__(parent)
        self.current_data = current_data
        self.currently_excluded = currently_excluded.copy() if currently_excluded else set()
        self.checkbox_items = {}
        self.all_point_ids = []

        self.setWindowTitle("Point Selection")
        self.setModal(True)
        self.setFixedSize(420, 650)
        self.init_frameless_dialog_chrome(
            default_windows="frameless",
            default_other="native",
            resize_margin=10,
            top_resize_margin=10,
        )

        # Apply dialog styling
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {Colors.BG_PANEL};
                border: 1px solid {Colors.BORDER_MEDIUM};
                border-radius: 12px;
            }}
        """)

        self._setup_ui()
        self._load_point_ids()
        self._populate_checkboxes()
        self._update_stats()
        self.bind_frameless_drag_widget(self.header_widget)

    def _setup_ui(self):
        """Setup the dialog UI with premium styling."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ═══════════════════════════════════════════
        # HEADER
        # ═══════════════════════════════════════════
        self.header_widget = QWidget()
        self.header_widget.setStyleSheet(f"""
            QWidget {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {Colors.BG_ELEVATED}, stop:1 {Colors.BG_SURFACE});
                border-bottom: 1px solid {Colors.BORDER_DEFAULT};
            }}
        """)
        header_layout = QHBoxLayout(self.header_widget)
        header_layout.setContentsMargins(20, 20, 20, 20)
        header_layout.setSpacing(14)

        # Icon box
        icon_box = QLabel()
        icon_box.setFixedSize(40, 40)
        icon_box.setAlignment(Qt.AlignCenter)
        icon_box.setStyleSheet(f"""
            background-color: {Colors.tint_surface(Colors.ACCENT_PRIMARY, dark_alpha=0.12, light_alpha=0.10)};
            border: 1px solid {Colors.BORDER_ACCENT};
            border-radius: 10px;
        """)
        icon_box.setPixmap(icon(Icons.FILTER, color=Colors.ACCENT_PRIMARY).pixmap(18, 18))
        header_layout.addWidget(icon_box)

        # Title section
        title_widget = QWidget()
        title_layout = QVBoxLayout(title_widget)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(3)

        title = QLabel("Point Selection")
        title.setStyleSheet(f"""
            font-size: 16px;
            font-weight: 700;
            color: {Colors.TEXT_PRIMARY};
        """)
        title_layout.addWidget(title)

        subtitle = QLabel("Select points to include in analysis")
        subtitle.setStyleSheet(f"""
            font-size: 11px;
            font-weight: 500;
            color: {Colors.TEXT_TERTIARY};
        """)
        title_layout.addWidget(subtitle)

        header_layout.addWidget(title_widget)
        header_layout.addStretch()

        # Close button
        close_btn = QPushButton()
        close_btn.setFixedSize(32, 32)
        close_btn.setIcon(icon(Icons.CLOSE, color=Colors.TEXT_MUTED))
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background-color: {Colors.OVERLAY_HOVER};
            }}
        """)
        close_btn.clicked.connect(self.reject)
        header_layout.addWidget(close_btn)

        main_layout.addWidget(self.header_widget)

        # ═══════════════════════════════════════════
        # SEARCH SECTION
        # ═══════════════════════════════════════════
        search_section = QWidget()
        search_section.setStyleSheet(f"border-bottom: 1px solid {Colors.BORDER_DEFAULT};")
        search_layout = QHBoxLayout(search_section)
        search_layout.setContentsMargins(24, 16, 24, 16)

        # Search wrapper
        search_wrapper = QFrame()
        search_wrapper.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.BG_SURFACE};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 8px;
            }}
            QFrame:focus-within {{
                border-color: {Colors.ACCENT_PRIMARY};
            }}
        """)
        search_wrapper_layout = QHBoxLayout(search_wrapper)
        search_wrapper_layout.setContentsMargins(14, 10, 14, 10)
        search_wrapper_layout.setSpacing(10)

        # Search icon
        search_icon = QLabel()
        search_icon.setPixmap(icon(Icons.SEARCH, color=Colors.TEXT_MUTED).pixmap(13, 13))
        search_wrapper_layout.addWidget(search_icon)

        # Search input
        self.search_field = QLineEdit()
        self.search_field.setPlaceholderText("Search by point ID...")
        self.search_field.setStyleSheet(f"""
            QLineEdit {{
                background: transparent;
                border: none;
                color: {Colors.TEXT_PRIMARY};
                font-size: 12px;
            }}
            QLineEdit::placeholder {{
                color: {Colors.TEXT_TERTIARY};
            }}
        """)
        self.search_field.textChanged.connect(self._filter_checkboxes)
        search_wrapper_layout.addWidget(self.search_field)

        # Clear button
        self.clear_search_btn = QPushButton()
        self.clear_search_btn.setFixedSize(20, 20)
        self.clear_search_btn.setIcon(icon(Icons.CLOSE, color=Colors.TEXT_MUTED))
        self.clear_search_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.OVERLAY_HOVER};
                border: none;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: {Colors.BORDER_MEDIUM};
            }}
        """)
        self.clear_search_btn.clicked.connect(lambda: self.search_field.clear())
        search_wrapper_layout.addWidget(self.clear_search_btn)

        search_layout.addWidget(search_wrapper)
        main_layout.addWidget(search_section)

        # ═══════════════════════════════════════════
        # STATS BAR
        # ═══════════════════════════════════════════
        stats_bar = QWidget()
        stats_bar.setStyleSheet(f"""
            background-color: {Colors.BG_SURFACE};
            border-bottom: 1px solid {Colors.BORDER_DEFAULT};
        """)
        stats_layout = QHBoxLayout(stats_bar)
        stats_layout.setContentsMargins(24, 10, 24, 10)

        # Stats text
        self.stats_label = QLabel()
        self.stats_label.setStyleSheet(f"""
            font-size: 10px;
            font-weight: 500;
            color: {Colors.TEXT_MUTED};
        """)
        stats_layout.addWidget(self.stats_label)

        stats_layout.addStretch()

        # Quick action buttons
        quick_actions = QWidget()
        quick_layout = QHBoxLayout(quick_actions)
        quick_layout.setContentsMargins(0, 0, 0, 0)
        quick_layout.setSpacing(6)

        select_all_btn = QPushButton("Select All")
        select_all_btn.setStyleSheet(self._get_quick_btn_style())
        select_all_btn.clicked.connect(self._select_all)
        quick_layout.addWidget(select_all_btn)

        deselect_all_btn = QPushButton("Deselect All")
        deselect_all_btn.setStyleSheet(self._get_quick_btn_style())
        deselect_all_btn.clicked.connect(self._deselect_all)
        quick_layout.addWidget(deselect_all_btn)

        stats_layout.addWidget(quick_actions)
        main_layout.addWidget(stats_bar)

        # ═══════════════════════════════════════════
        # CHECKBOX LIST
        # ═══════════════════════════════════════════
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet(f"""
            QScrollArea {{
                background-color: {Colors.BG_PANEL};
                border: none;
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 6px;
                margin: 0;
            }}
            QScrollBar::handle:vertical {{
                background: {Colors.BORDER_STRONG};
                border-radius: 3px;
                min-height: 30px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {Colors.TEXT_MUTED};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: transparent;
            }}
        """)

        self.checkbox_widget = QWidget()
        self.checkbox_widget.setStyleSheet(f"background-color: {Colors.BG_PANEL};")
        self.checkbox_layout = QVBoxLayout(self.checkbox_widget)
        self.checkbox_layout.setContentsMargins(0, 8, 0, 8)
        self.checkbox_layout.setSpacing(0)
        self.checkbox_layout.setAlignment(Qt.AlignTop)

        scroll.setWidget(self.checkbox_widget)
        main_layout.addWidget(scroll, 1)

        # ═══════════════════════════════════════════
        # FOOTER
        # ═══════════════════════════════════════════
        footer = QWidget()
        footer.setStyleSheet(f"""
            background-color: {Colors.BG_PANEL};
            border-top: 1px solid {Colors.BORDER_DEFAULT};
        """)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(24, 16, 24, 16)
        footer_layout.setSpacing(10)

        # Footer info
        self.footer_info = QLabel()
        self.footer_info.setStyleSheet(f"""
            font-size: 10px;
            color: {Colors.TEXT_MUTED};
        """)
        footer_layout.addWidget(self.footer_info)

        footer_layout.addStretch()

        # Cancel button
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(self._get_secondary_btn_style())
        cancel_btn.clicked.connect(self.reject)
        footer_layout.addWidget(cancel_btn)

        # Apply button
        apply_btn = QPushButton("Apply Changes")
        apply_btn.setStyleSheet(self._get_primary_btn_style())
        apply_btn.clicked.connect(self._apply_selection)
        footer_layout.addWidget(apply_btn)

        main_layout.addWidget(footer)

    def _get_quick_btn_style(self):
        """Style for quick action buttons in stats bar."""
        return f"""
            QPushButton {{
                padding: 4px 10px;
                border-radius: 4px;
                font-size: 10px;
                font-weight: 600;
                background: transparent;
                border: 1px solid {Colors.BORDER_DEFAULT};
                color: {Colors.TEXT_SECONDARY};
            }}
            QPushButton:hover {{
                border-color: {Colors.BORDER_ACCENT};
                color: {Colors.ACCENT_PRIMARY};
                background: {Colors.ACCENT_GHOST};
            }}
        """

    def _get_secondary_btn_style(self):
        """Style for secondary buttons."""
        return f"""
            QPushButton {{
                padding: 10px 20px;
                border-radius: 8px;
                font-size: 11px;
                font-weight: 600;
                color: {Colors.TEXT_SECONDARY};
                background: transparent;
                border: 1px solid {Colors.BORDER_DEFAULT};
            }}
            QPushButton:hover {{
                color: {Colors.TEXT_PRIMARY};
                border-color: {Colors.BORDER_MEDIUM};
                background: {Colors.BG_SURFACE};
            }}
        """

    def _get_primary_btn_style(self):
        """Style for primary buttons."""
        return f"""
            QPushButton {{
                padding: 8px 16px;
                border-radius: 6px;
                font-size: 11px;
                font-weight: 700;
                color: {Colors.TEXT_INVERSE};
                background: {Colors.GRADIENT_ACCENT};
                border: none;
            }}
            QPushButton:hover {{
                background: {Colors.ACCENT_HOVER};
            }}
        """

    def _load_point_ids(self):
        """Load all point IDs from the data."""
        self.all_point_ids = []

        if self.current_data is None or self.current_data.empty:
            return

        # Get all point IDs from data
        try:
            self.all_point_ids = list(self.current_data['ID'].unique())
        except KeyError:
            # If 'ID' column doesn't exist, try other common names
            for col in ['id', 'Id', 'Point_ID', 'PointID']:
                if col in self.current_data.columns:
                    self.all_point_ids = list(self.current_data[col].unique())
                    break

        # Sort IDs
        self.all_point_ids = sorted(self.all_point_ids, key=lambda x: str(x))

    def _populate_checkboxes(self, filter_text=""):
        """Populate checkboxes for all point IDs."""
        # Clear existing items
        for item in self.checkbox_items.values():
            item.setParent(None)
            item.deleteLater()
        self.checkbox_items.clear()

        # Clear layout
        while self.checkbox_layout.count():
            item = self.checkbox_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self.all_point_ids:
            self._show_empty_state("No data loaded")
            return

        # Create checkbox items
        filter_lower = filter_text.lower()
        visible_count = 0

        for point_id in self.all_point_ids:
            point_id_str = str(point_id)

            # Apply filter
            if filter_text and filter_lower not in point_id_str.lower():
                continue

            is_checked = point_id not in self.currently_excluded
            item = PointCheckboxItem(point_id_str, is_checked)
            item.toggled.connect(lambda checked, pid=point_id: self._on_item_toggled(pid, checked))

            self.checkbox_items[point_id] = item
            self.checkbox_layout.addWidget(item)
            visible_count += 1

        # Add stretch at bottom
        self.checkbox_layout.addStretch()

        # Show empty state if no results
        if visible_count == 0 and filter_text:
            self._show_empty_state(f"No points matching '{filter_text}'")

    def _show_empty_state(self, message: str):
        """Show empty state message."""
        empty_widget = QWidget()
        empty_layout = QVBoxLayout(empty_widget)
        empty_layout.setContentsMargins(40, 40, 40, 40)
        empty_layout.setAlignment(Qt.AlignCenter)

        empty_icon = QLabel()
        empty_icon.setPixmap(icon(Icons.SEARCH, color=Colors.TEXT_TERTIARY).pixmap(32, 32))
        empty_icon.setAlignment(Qt.AlignCenter)
        empty_layout.addWidget(empty_icon)

        empty_text = QLabel(message)
        empty_text.setStyleSheet(f"""
            font-size: 12px;
            color: {Colors.TEXT_MUTED};
        """)
        empty_text.setAlignment(Qt.AlignCenter)
        empty_layout.addWidget(empty_text)

        self.checkbox_layout.addWidget(empty_widget)

    def _on_item_toggled(self, point_id, checked):
        """Handle checkbox item toggle."""
        if checked:
            self.currently_excluded.discard(point_id)
        else:
            self.currently_excluded.add(point_id)
        self._update_stats()

    def _update_stats(self):
        """Update the stats bar and footer info."""
        total = len(self.all_point_ids)
        excluded = len(self.currently_excluded)
        included = total - excluded

        # Stats bar - highlight numbers with accent color
        self.stats_label.setText(
            f"<span style='color: {Colors.ACCENT_PRIMARY}; font-weight: 600;'>{included}</span> "
            f"of <span style='color: {Colors.ACCENT_PRIMARY}; font-weight: 600;'>{total}</span> points included"
        )

        # Footer info
        if excluded > 0:
            self.footer_info.setText(
                f"<span style='color: {Colors.WARNING}; font-weight: 600;'>{excluded}</span> "
                f"point{'s' if excluded != 1 else ''} will be excluded"
            )
        else:
            self.footer_info.setText("All points will be included")

    def _filter_checkboxes(self):
        """Filter checkboxes based on search text."""
        filter_text = self.search_field.text()
        self._populate_checkboxes(filter_text)

    def _select_all(self):
        """Check all visible checkbox items."""
        for item in self.checkbox_items.values():
            item.setChecked(True)
        self._update_stats()

    def _deselect_all(self):
        """Uncheck all visible checkbox items."""
        for item in self.checkbox_items.values():
            item.setChecked(False)
        self._update_stats()

    def _apply_selection(self):
        """Apply selection and emit signal with excluded IDs."""
        # Collect excluded IDs (unchecked items)
        excluded_ids = set()
        for point_id, item in self.checkbox_items.items():
            if not item.isChecked():
                excluded_ids.add(point_id)

        # Emit signal
        self.points_excluded.emit(excluded_ids)

        # Close dialog
        self.accept()

    def keyPressEvent(self, event):
        """Handle key press events."""
        if event.key() == Qt.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(event)
