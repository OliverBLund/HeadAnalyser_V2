"""
HeadAnalyser V2 - PDF Report Generator Dialog
Collects options for a multi-page PDF report.

Modernized to match HeadAnalyser V2 design system.
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox,
    QGroupBox, QFormLayout, QSpinBox, QDoubleSpinBox, QComboBox,
    QPushButton, QWidget, QScrollArea
)
from PyQt5.QtCore import Qt

from styles.colors import Colors
from ui.common_widgets import SectionHeader
from ui.icons import Icons
from qt_chrome import FramelessDialogMixin


class ReportSettingsDialog(FramelessDialogMixin, QDialog):
    """Dialog for configuring PDF report export."""

    PLOT_TYPES = [
        "2D Hydraulic Head",
        "3D Surface",
        "Gradient Vectors",
        "Gradient Histogram",
        "Rose Diagram",
    ]

    def __init__(self, main_window, parent=None):
        super().__init__(parent or main_window)
        self.main_window = main_window

        self.setWindowTitle("PDF Report Generator")
        self.resize(580, 720)
        self.setModal(True)
        self.init_frameless_dialog_chrome(
            default_windows="frameless",
            default_other="native",
            resize_margin=10,
            top_resize_margin=10,
        )

        self._setup_ui()
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
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(24, 20, 24, 20)
        header_layout.setSpacing(12)

        title = QLabel("Generate PDF Report")
        title.setStyleSheet(f"""
            color: {Colors.TEXT_PRIMARY};
            font-size: 18px;
            font-weight: 700;
            letter-spacing: -0.3px;
            background: transparent;
            border: none;
        """)
        header_layout.addWidget(title)

        header_layout.addStretch()

        # Close button
        close_btn = QPushButton("×")
        close_btn.setObjectName("close_btn")
        close_btn.setFixedSize(32, 32)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self.reject)
        close_btn.setToolTip("Close")
        header_layout.addWidget(close_btn)

        root.addWidget(header)

        # ── Scroll Area for Content ──
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QScrollArea.NoFrame)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(24, 20, 24, 20)
        content_layout.setSpacing(24)

        # Info banner
        info_banner = QWidget()
        info_banner.setObjectName("info_banner")
        info_layout = QHBoxLayout(info_banner)
        info_layout.setContentsMargins(16, 12, 16, 12)
        info_layout.setSpacing(12)

        info_icon = QLabel("📄")
        info_icon.setStyleSheet(f"font-size: 18px; background: transparent; border: none;")
        info_layout.addWidget(info_icon)

        info_text = QLabel("Configure which plots, statistics, and tables to include in your PDF report.")
        info_text.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 12px; background: transparent; border: none;")
        info_text.setWordWrap(True)
        info_layout.addWidget(info_text, 1)

        content_layout.addWidget(info_banner)

        # ── Plots & Statistics Side-by-Side ──
        top_row = QHBoxLayout()
        top_row.setSpacing(20)

        # Left: Plots Section
        plots_section = SectionHeader("Plots to Include", Icons.CHART_LINE)
        top_row.addWidget(plots_section)

        self._plot_checks = {}
        for name in self.PLOT_TYPES:
            cb = QCheckBox(name)
            cb.setChecked(name == "2D Hydraulic Head")
            cb.setCursor(Qt.PointingHandCursor)
            self._plot_checks[name] = cb
            plots_section.contentLayout().addWidget(cb)

        # Right: Statistics & Tables Section
        stats_section = SectionHeader("Statistics & Tables", Icons.TABLE)
        top_row.addWidget(stats_section)

        self.include_general_stats = QCheckBox("Include general statistics")
        self.include_general_stats.setChecked(True)
        self.include_general_stats.setCursor(Qt.PointingHandCursor)
        stats_section.contentLayout().addWidget(self.include_general_stats)

        self.include_gradient_stats = QCheckBox("Include gradient statistics")
        self.include_gradient_stats.setChecked(True)
        self.include_gradient_stats.setCursor(Qt.PointingHandCursor)
        stats_section.contentLayout().addWidget(self.include_gradient_stats)

        self.include_valid_table = QCheckBox("Include valid results table")
        self.include_valid_table.setChecked(True)
        self.include_valid_table.setCursor(Qt.PointingHandCursor)
        stats_section.contentLayout().addWidget(self.include_valid_table)

        self.include_rejected_table = QCheckBox("Include rejected results table")
        self.include_rejected_table.setChecked(True)
        self.include_rejected_table.setCursor(Qt.PointingHandCursor)
        stats_section.contentLayout().addWidget(self.include_rejected_table)

        self.include_rejection_analysis = QCheckBox("Include rejected points analysis")
        self.include_rejection_analysis.setChecked(False)
        self.include_rejection_analysis.setCursor(Qt.PointingHandCursor)
        stats_section.contentLayout().addWidget(self.include_rejection_analysis)

        content_layout.addLayout(top_row)

        # ── Layout Section ──
        layout_section = SectionHeader("Layout & Quality", Icons.SETTINGS)
        content_layout.addWidget(layout_section)

        layout_grid = QFormLayout()
        layout_grid.setSpacing(12)
        layout_grid.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.dpi_spin = QSpinBox()
        self.dpi_spin.setRange(72, 600)
        self.dpi_spin.setValue(200)
        self.dpi_spin.setSuffix(" dpi")
        self.dpi_spin.setObjectName("styled_spinbox")
        layout_grid.addRow("Plot DPI:", self.dpi_spin)

        self.width_spin = QDoubleSpinBox()
        self.width_spin.setRange(3.0, 20.0)
        self.width_spin.setSingleStep(0.5)
        self.width_spin.setValue(8.0)
        self.width_spin.setSuffix(' "')
        self.width_spin.setObjectName("styled_spinbox")
        layout_grid.addRow("Plot Width:", self.width_spin)

        self.height_spin = QDoubleSpinBox()
        self.height_spin.setRange(3.0, 20.0)
        self.height_spin.setSingleStep(0.5)
        self.height_spin.setValue(5.5)
        self.height_spin.setSuffix(' "')
        self.height_spin.setObjectName("styled_spinbox")
        layout_grid.addRow("Plot Height:", self.height_spin)

        self.row_limit_combo = QComboBox()
        self.row_limit_combo.addItems(["All", "50", "100", "250", "500"])
        self.row_limit_combo.setCurrentText("100")
        self.row_limit_combo.setObjectName("styled_combo")
        self.row_limit_combo.setCursor(Qt.PointingHandCursor)
        layout_grid.addRow("Table Row Limit:", self.row_limit_combo)

        layout_section.contentLayout().addLayout(layout_grid)

        self.landscape_check = QCheckBox("Use landscape orientation for plots")
        self.landscape_check.setChecked(True)
        self.landscape_check.setCursor(Qt.PointingHandCursor)
        layout_section.contentLayout().addWidget(self.landscape_check)

        # ── Map Section ──
        map_section = SectionHeader("Location Map", "fa6s.map-location-dot")
        content_layout.addWidget(map_section)

        self.include_map_check = QCheckBox("Include interactive location map (Folium)")
        self.include_map_check.setChecked(False)
        self.include_map_check.setCursor(Qt.PointingHandCursor)
        map_section.contentLayout().addWidget(self.include_map_check)

        map_form = QFormLayout()
        map_form.setSpacing(12)
        map_form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.map_style_combo = QComboBox()
        self.map_style_combo.addItems(["OpenStreetMap"])
        self.map_style_combo.setObjectName("styled_combo")
        self.map_style_combo.setCursor(Qt.PointingHandCursor)
        map_form.addRow("Map Style:", self.map_style_combo)

        map_section.contentLayout().addLayout(map_form)

        map_note = QLabel("⚠ Note: Map export may require Selenium to render a PNG.")
        map_note.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: 11px; font-style: italic; background: transparent; border: none; padding: 4px 0;")
        map_note.setWordWrap(True)
        map_section.contentLayout().addWidget(map_note)

        content_layout.addStretch()

        scroll.setWidget(content)
        root.addWidget(scroll, 1)

        # ── Footer with Buttons ──
        footer = QWidget()
        footer.setObjectName("dialog_footer")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(24, 16, 24, 16)
        footer_layout.setSpacing(12)

        footer_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("btn_secondary")
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        footer_layout.addWidget(cancel_btn)

        export_btn = QPushButton("Generate PDF")
        export_btn.setObjectName("btn_primary")
        export_btn.setCursor(Qt.PointingHandCursor)
        export_btn.clicked.connect(self.accept)
        footer_layout.addWidget(export_btn)

        root.addWidget(footer)

    def _apply_styles(self):
        """Apply modern styling to the dialog."""
        self.setStyleSheet(f"""
            QDialog {{
                background: {Colors.BG_ELEVATED};
            }}

            /* Header */
            #dialog_header {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {Colors.BG_SURFACE}, stop:1 #18181d);
                border-bottom: 1px solid rgba(129, 140, 248, 0.08);
            }}

            /* Footer */
            #dialog_footer {{
                background: {Colors.BG_SURFACE};
                border-top: 1px solid {Colors.BORDER_SUBTLE};
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
                background: rgba(239, 68, 68, 0.15);
                border-color: rgba(239, 68, 68, 0.3);
                color: #fca5a5;
            }}
            #close_btn:pressed {{
                background: rgba(239, 68, 68, 0.25);
            }}

            /* Info banner */
            #info_banner {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(129, 140, 248, 0.08), stop:1 rgba(129, 140, 248, 0.04));
                border: 1px solid rgba(129, 140, 248, 0.2);
                border-left: 3px solid {Colors.ACCENT_PRIMARY};
                border-radius: 10px;
            }}

            /* Checkboxes */
            QCheckBox {{
                color: {Colors.TEXT_SECONDARY};
                font-size: 13px;
                font-weight: 500;
                spacing: 8px;
                padding: 6px 8px;
                border-radius: 6px;
            }}
            QCheckBox:hover {{
                background: rgba(129, 140, 248, 0.05);
                color: {Colors.TEXT_PRIMARY};
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border: 2px solid {Colors.BORDER_MEDIUM};
                border-radius: 5px;
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

            /* Form labels */
            QLabel {{
                color: {Colors.TEXT_SECONDARY};
                font-size: 12px;
                font-weight: 500;
            }}

            /* SpinBoxes */
            #styled_spinbox {{
                background: {Colors.BG_SURFACE};
                border: 1px solid {Colors.BORDER_MEDIUM};
                border-radius: 8px;
                padding: 6px 10px;
                color: {Colors.TEXT_PRIMARY};
                font-size: 12px;
                min-width: 120px;
            }}
            #styled_spinbox:focus {{
                border-color: {Colors.ACCENT_PRIMARY};
                background: {Colors.BG_ELEVATED};
            }}
            #styled_spinbox::up-button, #styled_spinbox::down-button {{
                background: {Colors.BG_HOVER};
                border: none;
                border-radius: 4px;
                width: 18px;
            }}
            #styled_spinbox::up-button:hover, #styled_spinbox::down-button:hover {{
                background: {Colors.BG_ELEVATED};
            }}
            #styled_spinbox::up-arrow {{
                image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTIiIGhlaWdodD0iMTIiIHZpZXdCb3g9IjAgMCAxMiAxMiIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZD0iTTYgNEw5IDhIMloiIGZpbGw9IiM4ZThlOTMiLz4KPC9zdmc+);
                width: 10px;
                height: 10px;
            }}
            #styled_spinbox::down-arrow {{
                image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTIiIGhlaWdodD0iMTIiIHZpZXdCb3g9IjAgMCAxMiAxMiIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZD0iTTYgOEwzIDRIOVoiIGZpbGw9IiM4ZThlOTMiLz4KPC9zdmc+);
                width: 10px;
                height: 10px;
            }}

            /* ComboBox */
            #styled_combo {{
                background: {Colors.BG_SURFACE};
                border: 1px solid {Colors.BORDER_MEDIUM};
                border-radius: 8px;
                padding: 6px 10px;
                color: {Colors.TEXT_PRIMARY};
                font-size: 12px;
                min-width: 120px;
            }}
            #styled_combo:focus {{
                border-color: {Colors.ACCENT_PRIMARY};
                background: {Colors.BG_ELEVATED};
            }}
            #styled_combo::drop-down {{
                border: none;
                background: {Colors.BG_HOVER};
                border-radius: 4px;
                width: 20px;
                margin: 2px;
            }}
            #styled_combo::down-arrow {{
                image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTIiIGhlaWdodD0iMTIiIHZpZXdCb3g9IjAgMCAxMiAxMiIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZD0iTTYgOEwzIDRIOVoiIGZpbGw9IiM4ZThlOTMiLz4KPC9zdmc+);
                width: 10px;
                height: 10px;
            }}
            QComboBox QAbstractItemView {{
                background: {Colors.BG_SURFACE};
                border: 1px solid {Colors.BORDER_MEDIUM};
                border-radius: 8px;
                color: {Colors.TEXT_PRIMARY};
                selection-background-color: {Colors.ACCENT_GHOST};
                selection-color: {Colors.TEXT_PRIMARY};
                padding: 4px;
            }}

            /* Buttons */
            QPushButton {{
                padding: 9px 20px;
                border-radius: 10px;
                font-size: 13px;
                font-weight: 600;
                border: 1px solid;
            }}
            #btn_primary {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {Colors.ACCENT_PRIMARY}, stop:1 {Colors.ACCENT_PRESSED});
                border-color: {Colors.ACCENT_PRIMARY};
                color: {Colors.TEXT_PRIMARY};
            }}
            #btn_primary:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {Colors.ACCENT_BRIGHT}, stop:1 {Colors.ACCENT_PRIMARY});
                border-color: {Colors.ACCENT_BRIGHT};
            }}
            #btn_primary:pressed {{
                background: {Colors.ACCENT_PRESSED};
            }}
            #btn_secondary {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {Colors.BG_HOVER}, stop:1 #242429);
                border-color: {Colors.BORDER_MEDIUM};
                color: {Colors.TEXT_SECONDARY};
            }}
            #btn_secondary:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {Colors.BG_ELEVATED}, stop:1 #2a2a30);
                border-color: {Colors.ACCENT_PRIMARY};
                color: {Colors.TEXT_PRIMARY};
            }}

            /* Scroll area */
            QScrollArea {{
                border: none;
                background: {Colors.BG_ELEVATED};
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 10px;
                margin: 0;
            }}
            QScrollBar::handle:vertical {{
                background: {Colors.BG_HOVER};
                border-radius: 5px;
                min-height: 30px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {Colors.BG_ELEVATED};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
        """)

    def get_settings(self):
        """Return the configured report settings."""
        return {
            "plots": [name for name, cb in self._plot_checks.items() if cb.isChecked()],
            "include_general_stats": self.include_general_stats.isChecked(),
            "include_gradient_stats": self.include_gradient_stats.isChecked(),
            "include_valid": self.include_valid_table.isChecked(),
            "include_rejected": self.include_rejected_table.isChecked(),
            "include_rejection_analysis": self.include_rejection_analysis.isChecked(),
            "dpi": int(self.dpi_spin.value()),
            "plot_width": float(self.width_spin.value()),
            "plot_height": float(self.height_spin.value()),
            "row_limit": self.row_limit_combo.currentText(),
            "use_landscape": bool(self.landscape_check.isChecked()),
            "include_map": bool(self.include_map_check.isChecked()),
            "map_style": self.map_style_combo.currentText(),
        }
