"""
Map contour settings dialog with plot-settings visual style.
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget, QScrollArea, QFrame,
    QComboBox, QSpinBox, QDoubleSpinBox
)
from PyQt5.QtCore import Qt

from styles.colors import Colors
from ui.common_widgets import ToggleSwitch
from qt_chrome import FramelessDialogMixin
from .plot_settings import _SettingsSection, _spin_style


def _combo_style() -> str:
    return f"""
        QComboBox {{
            background-color: {Colors.BG_SURFACE};
            color: {Colors.TEXT_PRIMARY};
            border: 1px solid {Colors.BORDER_DEFAULT};
            border-radius: 6px;
            padding: 4px 24px 4px 8px;
            font-size: 11px;
            min-width: 120px;
        }}
        QComboBox:hover {{ border-color: {Colors.BORDER_MEDIUM}; }}
        QComboBox:focus {{ border-color: {Colors.ACCENT_PRIMARY}; }}
        QComboBox::drop-down {{ border: none; width: 18px; }}
        QComboBox::down-arrow {{
            image: none;
            border-left: 3px solid transparent;
            border-right: 3px solid transparent;
            border-top: 5px solid {Colors.TEXT_TERTIARY};
            margin-right: 8px;
        }}
        QComboBox QAbstractItemView {{
            background: {Colors.BG_ELEVATED};
            color: {Colors.TEXT_PRIMARY};
            border: 1px solid {Colors.BORDER_DEFAULT};
            selection-background-color: {Colors.BG_HOVER};
        }}
    """


class MapContourSettingsDialog(FramelessDialogMixin, QDialog):
    """Advanced map contour configuration dialog."""

    def __init__(self, main_window, map_widget, parent=None):
        super().__init__(parent or main_window)
        self.main_window = main_window
        self.map_widget = map_widget

        self.setWindowTitle("Map Contour Settings")
        self.setMinimumSize(480, 560)
        self.setModal(True)
        self.init_frameless_dialog_chrome(
            default_windows="frameless",
            default_other="native",
            resize_margin=10,
            top_resize_margin=10,
        )
        self.setStyleSheet(f"QDialog {{ background-color: {Colors.BG_PANEL}; }}")

        self._setup_ui()
        self.bind_frameless_drag_widget(self._chrome_header)

    def _make_spin(self) -> QSpinBox:
        s = QSpinBox()
        s.setStyleSheet(_spin_style())
        s.setAlignment(Qt.AlignCenter)
        s.setButtonSymbols(QSpinBox.NoButtons)
        return s

    def _make_dspin(self) -> QDoubleSpinBox:
        s = QDoubleSpinBox()
        s.setStyleSheet(_spin_style())
        s.setAlignment(Qt.AlignCenter)
        s.setButtonSymbols(QDoubleSpinBox.NoButtons)
        return s

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QWidget()
        header.setFixedHeight(64)
        header.setStyleSheet(f"""
            QWidget {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {Colors.BG_ELEVATED}, stop:1 {Colors.BG_SURFACE});
                border-bottom: 1px solid {Colors.BORDER_DEFAULT};
            }}
        """)
        self._chrome_header = header
        hl = QHBoxLayout(header)
        hl.setContentsMargins(20, 0, 20, 0)
        hl.setSpacing(12)

        icon_box = QLabel("~")
        icon_box.setFixedSize(32, 32)
        icon_box.setAlignment(Qt.AlignCenter)
        icon_box.setStyleSheet(f"""
            background-color: {Colors.ACCENT_GHOST};
            border: 1px solid {Colors.BORDER_ACCENT};
            border-radius: 8px;
            color: {Colors.ACCENT_PRIMARY};
            font-size: 16px;
            font-weight: 700;
        """)
        hl.addWidget(icon_box)

        title_col = QVBoxLayout()
        title_col.setSpacing(1)
        title_label = QLabel("Map Contour Settings")
        title_label.setStyleSheet(
            f"color: {Colors.TEXT_PRIMARY}; font-size: 15px; font-weight: 700; background: transparent;"
        )
        title_col.addWidget(title_label)
        subtitle = QLabel("Shared contour math + map display tuning")
        subtitle.setStyleSheet(
            f"color: {Colors.TEXT_TERTIARY}; font-size: 10px; font-weight: 500; background: transparent;"
        )
        title_col.addWidget(subtitle)
        hl.addLayout(title_col)
        hl.addStretch()

        close_btn = QPushButton("x")
        close_btn.setFixedSize(28, 28)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: none; border-radius: 6px;
                color: {Colors.TEXT_MUTED}; font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {Colors.BG_HOVER}; color: {Colors.TEXT_PRIMARY};
            }}
        """)
        close_btn.clicked.connect(self.reject)
        hl.addWidget(close_btn)
        layout.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"""
            QScrollArea {{ background: transparent; border: none; }}
            QScrollBar:vertical {{ background: transparent; width: 5px; margin: 0; }}
            QScrollBar::handle:vertical {{ background: {Colors.BORDER_STRONG}; border-radius: 2px; min-height: 20px; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)

        body = QWidget()
        body.setStyleSheet("background: transparent;")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 6, 0, 6)
        body_layout.setSpacing(0)

        sec_surface = _SettingsSection("Contour Surface", "~", _SettingsSection.PURPLE)

        self.fill_contours_toggle = ToggleSwitch("Fill Contours")
        self.fill_contours_toggle.setChecked(bool(getattr(self.main_window, "fill_contours", False)))
        sec_surface.addFullWidget(self.fill_contours_toggle)

        self.fill_opacity_spin = self._make_spin()
        self.fill_opacity_spin.setRange(0, 100)
        self.fill_opacity_spin.setSuffix("%")
        try:
            fill_pct = int(round(float(getattr(self.map_widget, "_contour_fill_opacity", 0.22)) * 100.0))
        except Exception:
            fill_pct = 22
        self.fill_opacity_spin.setValue(max(0, min(fill_pct, 100)))
        sec_surface.addRow("Fill Opacity", self.fill_opacity_spin)

        self.interp_combo = QComboBox()
        self.interp_combo.addItems(["cubic", "linear", "nearest"])
        self.interp_combo.setStyleSheet(_combo_style())
        self.interp_combo.setCurrentText(str(getattr(self.main_window, "interpolation_method", "cubic") or "cubic"))
        sec_surface.addRow("Interpolation", self.interp_combo)

        self.levels_spin = self._make_spin()
        self.levels_spin.setRange(2, 50)
        self.levels_spin.setValue(int(getattr(self.main_window, "contour_levels", 10) or 10))
        sec_surface.addRow("Contour Levels", self.levels_spin)

        self.extent_spin = self._make_spin()
        self.extent_spin.setRange(0, 30)
        self.extent_spin.setValue(int(getattr(self.main_window, "contour_extent_pct", 0) or 0))
        sec_surface.addRow("Contour Extent (%)", self.extent_spin)

        self.extrap_combo = QComboBox()
        self.extrap_combo.addItems(["none", "nearest", "idw"])
        self.extrap_combo.setStyleSheet(_combo_style())
        self.extrap_combo.setCurrentText(str(getattr(self.main_window, "contour_extrapolation", "none") or "none").lower())
        sec_surface.addRow("Extrapolation", self.extrap_combo)

        body_layout.addWidget(sec_surface)

        sec_lines = _SettingsSection("Line & Labels", "T", _SettingsSection.BLUE)

        self.line_width_spin = self._make_dspin()
        self.line_width_spin.setRange(0.2, 5.0)
        self.line_width_spin.setSingleStep(0.1)
        self.line_width_spin.setValue(float(getattr(self.main_window, "contour_linewidth", 0.8) or 0.8))
        sec_lines.addRow("Line Width", self.line_width_spin)

        self.show_labels_toggle = ToggleSwitch("Show Contour Labels")
        self.show_labels_toggle.setChecked(bool(getattr(self.map_widget, "_show_contour_labels", True)))
        sec_lines.addFullWidget(self.show_labels_toggle)

        self.precision_spin = self._make_spin()
        self.precision_spin.setRange(0, 3)
        self.precision_spin.setValue(int(getattr(self.map_widget, "_contour_label_precision", 2) or 2))
        sec_lines.addRow("Label Precision", self.precision_spin)

        self.label_font_spin = self._make_spin()
        self.label_font_spin.setRange(8, 24)
        self.label_font_spin.setValue(int(getattr(self.map_widget, "_contour_label_font_size", 12) or 12))
        sec_lines.addRow("Label Font Size", self.label_font_spin)

        self.major_interval_spin = self._make_spin()
        self.major_interval_spin.setRange(1, 8)
        self.major_interval_spin.setValue(int(getattr(self.map_widget, "_contour_major_interval", 2) or 2))
        sec_lines.addRow("Major Line Interval", self.major_interval_spin)

        body_layout.addWidget(sec_lines)
        body_layout.addStretch()

        scroll.setWidget(body)
        layout.addWidget(scroll, 1)

        footer = QWidget()
        footer.setFixedHeight(56)
        footer.setStyleSheet(f"""
            QWidget {{
                background-color: {Colors.BG_PANEL};
                border-top: 1px solid {Colors.BORDER_DEFAULT};
            }}
        """)
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(20, 0, 20, 0)
        fl.setSpacing(8)

        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.setCursor(Qt.PointingHandCursor)
        reset_btn.setStyleSheet(f"""
            QPushButton {{
                color: {Colors.TEXT_SECONDARY};
                background: transparent;
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 8px;
                font-size: 11px; font-weight: 600;
                padding: 7px 16px;
            }}
            QPushButton:hover {{
                color: {Colors.ERROR};
                border-color: rgba(248, 113, 113, 0.3);
                background: rgba(248, 113, 113, 0.08);
            }}
        """)
        reset_btn.clicked.connect(self._reset_defaults)
        fl.addWidget(reset_btn)
        fl.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                color: {Colors.TEXT_SECONDARY};
                background: transparent;
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 8px;
                font-size: 11px; font-weight: 600;
                padding: 7px 16px;
            }}
            QPushButton:hover {{
                color: {Colors.TEXT_PRIMARY};
                border-color: {Colors.BORDER_MEDIUM};
                background: {Colors.BG_SURFACE};
            }}
        """)
        cancel_btn.clicked.connect(self.reject)
        fl.addWidget(cancel_btn)

        apply_btn = QPushButton("Apply")
        apply_btn.setCursor(Qt.PointingHandCursor)
        apply_btn.setStyleSheet(f"""
            QPushButton {{
                color: #fff;
                background: {Colors.ACCENT_MUTED};
                border: 1px solid {Colors.ACCENT_PRIMARY};
                border-radius: 8px;
                font-size: 11px; font-weight: 700;
                padding: 7px 20px;
            }}
            QPushButton:hover {{
                background: {Colors.ACCENT_PRIMARY};
            }}
        """)
        apply_btn.clicked.connect(self._apply)
        fl.addWidget(apply_btn)

        layout.addWidget(footer)

    def _reset_defaults(self):
        self.fill_contours_toggle.setChecked(False)
        self.fill_opacity_spin.setValue(22)
        self.interp_combo.setCurrentText("cubic")
        self.levels_spin.setValue(10)
        self.extent_spin.setValue(0)
        self.extrap_combo.setCurrentText("none")
        self.line_width_spin.setValue(0.8)
        self.show_labels_toggle.setChecked(True)
        self.precision_spin.setValue(2)
        self.label_font_spin.setValue(12)
        self.major_interval_spin.setValue(2)

    def _apply(self):
        mw = self.main_window
        mapw = self.map_widget
        dataset = mw.get_active_dataset() if hasattr(mw, "get_active_dataset") else None

        mw.fill_contours = bool(self.fill_contours_toggle.isChecked())
        mw.interpolation_method = str(self.interp_combo.currentText() or "cubic")
        mw.contour_levels = int(self.levels_spin.value())
        mw.contour_extent_pct = int(self.extent_spin.value())
        mw.contour_extrapolation = str(self.extrap_combo.currentText() or "none").lower()
        mw.contour_linewidth = float(self.line_width_spin.value())

        if mapw is not None:
            mapw.apply_contour_visual_settings(
                show_labels=bool(self.show_labels_toggle.isChecked()),
                label_precision=int(self.precision_spin.value()),
                major_interval=int(self.major_interval_spin.value()),
                label_font_size=int(self.label_font_spin.value()),
                fill_opacity=float(self.fill_opacity_spin.value()) / 100.0,
            )

        if dataset is not None and hasattr(mw, "sync_to_dataset"):
            mw.sync_to_dataset(dataset)

        mw.update_plot()
        self.accept()

