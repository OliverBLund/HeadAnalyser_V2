"""
HeadAnalyser V2 - Plot Settings Dialog
Modern collapsible-section settings dialog with colored section icons.
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QWidget, QFormLayout, QSpinBox,
    QDoubleSpinBox, QLineEdit, QSlider, QColorDialog,
    QScrollArea, QFrame, QStackedWidget, QSizePolicy,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor

from styles.colors import Colors
from styles.stylesheet import StyleSheet
from ui.common_widgets import ToggleSwitch
from ui.icons import Icons, icon
from qt_chrome import FramelessDialogMixin


# ──────────────────────────────────────────────────
# Reusable settings section with colored icon + chevron
# ──────────────────────────────────────────────────

class _SettingsSection(QWidget):
    """Collapsible section with colored icon box, title, and chevron."""

    # Icon color presets: (icon_color, bg_color)
    BLUE = ("#60a5fa", "rgba(96, 165, 250, 0.10)")
    PURPLE = ("#a78bfa", "rgba(167, 139, 250, 0.12)")
    AMBER = ("#fbbf24", "rgba(251, 191, 36, 0.10)")
    RED = ("#f87171", "rgba(248, 113, 113, 0.10)")

    def __init__(self, title: str, icon_name: str, color_preset: tuple, parent=None):
        super().__init__(parent)
        self._expanded = True
        icon_color, icon_bg = color_preset

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Header row ──
        self._header = QPushButton()
        self._header.setCursor(Qt.PointingHandCursor)
        self._header.setFixedHeight(48)
        self._header.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                border-bottom: 1px solid {Colors.BORDER_SUBTLE};
                text-align: left;
                padding: 0;
            }}
            QPushButton:hover {{
                background-color: {Colors.BG_SURFACE};
            }}
        """)

        hl = QHBoxLayout()
        hl.setContentsMargins(24, 0, 24, 0)
        hl.setSpacing(12)
        self._header.setLayout(hl)

        # Icon box with FontAwesome icon
        icon_box = QLabel()
        icon_box.setFixedSize(28, 28)
        icon_box.setAlignment(Qt.AlignCenter)
        icon_box.setPixmap(icon(icon_name, icon_color, 13).pixmap(13, 13))
        icon_box.setStyleSheet(f"""
            background-color: {icon_bg};
            border-radius: 7px;
            border: none;
        """)
        hl.addWidget(icon_box)

        # Title
        title_label = QLabel(title)
        title_label.setStyleSheet(f"""
            color: {Colors.TEXT_PRIMARY};
            font-size: 13px;
            font-weight: 600;
            background: transparent;
            border: none;
        """)
        hl.addWidget(title_label, 1)

        # Chevron using FontAwesome
        self._chevron = QLabel()
        self._chevron.setFixedSize(16, 16)
        self._chevron.setAlignment(Qt.AlignCenter)
        self._chevron.setPixmap(icon(Icons.CHEVRON_DOWN, Colors.TEXT_MUTED, 9).pixmap(9, 9))
        self._chevron.setStyleSheet(f"""
            background: transparent;
            border: none;
        """)
        hl.addWidget(self._chevron)

        self._header.clicked.connect(self._toggle)
        layout.addWidget(self._header)

        # ── Body ──
        self._body = QWidget()
        self._body_layout = QVBoxLayout(self._body)
        self._body_layout.setContentsMargins(24, 20, 24, 20)
        self._body_layout.setSpacing(16)
        layout.addWidget(self._body)

    def _toggle(self):
        self._expanded = not self._expanded
        self._body.setVisible(self._expanded)
        chevron_icon = Icons.CHEVRON_DOWN if self._expanded else Icons.CHEVRON_RIGHT
        self._chevron.setPixmap(icon(chevron_icon, Colors.TEXT_MUTED, 9).pixmap(9, 9))

    def bodyLayout(self):
        return self._body_layout

    def addRow(self, label_text: str, widget):
        """Add a form row: label on left, widget on right."""
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(16)

        label = QLabel(label_text)
        label.setStyleSheet(f"""
            color: {Colors.TEXT_SECONDARY};
            font-size: 11px;
            font-weight: 500;
            line-height: 1.4;
            background: transparent;
            border: none;
        """)
        row.addWidget(label, 1, Qt.AlignVCenter)
        row.addWidget(widget, 0, Qt.AlignVCenter)

        self._body_layout.addLayout(row)

    def addFullWidget(self, widget):
        """Add a widget spanning the full width."""
        self._body_layout.addWidget(widget)

    def addDivider(self):
        """Add a subtle divider line between groups."""
        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setFixedHeight(1)
        divider.setStyleSheet(f"""
            background: {Colors.BORDER_SUBTLE};
            border: none;
            margin: 8px 0;
        """)
        self._body_layout.addWidget(divider)


# ──────────────────────────────────────────────────
# Shared inline styles for settings inputs
# ──────────────────────────────────────────────────

def _input_style():
    return f"""
        QLineEdit {{
            font-family: 'IBM Plex Mono', monospace;
            font-size: 11px;
            font-weight: 500;
            color: {Colors.TEXT_PRIMARY};
            background: {Colors.BG_SURFACE};
            border: 1px solid {Colors.BORDER_DEFAULT};
            border-radius: 6px;
            padding: 5px 10px;
            min-height: 18px;
        }}
        QLineEdit:hover {{
            border-color: {Colors.BORDER_MEDIUM};
        }}
        QLineEdit:focus {{
            border-color: {Colors.ACCENT_PRIMARY};
        }}
    """


def _spin_style():
    return f"""
        QSpinBox, QDoubleSpinBox {{
            font-family: 'IBM Plex Mono', monospace;
            font-size: 11px;
            font-weight: 500;
            color: {Colors.TEXT_PRIMARY};
            background: {Colors.BG_SURFACE};
            border: 1px solid {Colors.BORDER_DEFAULT};
            border-radius: 6px;
            padding: 5px 10px;
            min-height: 18px;
            min-width: 70px;
            max-width: 70px;
        }}
        QSpinBox:hover, QDoubleSpinBox:hover {{
            border-color: {Colors.BORDER_MEDIUM};
        }}
        QSpinBox:focus, QDoubleSpinBox:focus {{
            border-color: {Colors.ACCENT_PRIMARY};
        }}
        QSpinBox::up-button, QSpinBox::down-button,
        QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
            width: 0; border: none;
        }}
    """


def _row_height():
    """Minimum height style for setting rows to keep them consistent."""
    return 30


def _combo_style():
    """Shared combo box styling for settings."""
    return f"""
        QComboBox {{
            background-color: {Colors.BG_SURFACE};
            color: {Colors.TEXT_PRIMARY};
            border: 1px solid {Colors.BORDER_DEFAULT};
            border-radius: 6px;
            padding: 4px 24px 4px 8px;
            font-size: 11px;
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


# ──────────────────────────────────────────────────
# Main dialog
# ──────────────────────────────────────────────────

class PlotSettingsDialog(FramelessDialogMixin, QDialog):
    """Modal settings dialog with collapsible sections."""

    def __init__(self, main_window, plot_type: str, parent=None):
        super().__init__(parent or main_window)
        self.main_window = main_window
        self.plot_type = plot_type

        self.setWindowTitle("Plot Settings")
        self.setMinimumSize(480, 600)
        self.setModal(True)
        self.init_frameless_dialog_chrome(
            default_windows="frameless",
            default_other="native",
            resize_margin=10,
            top_resize_margin=10,
        )
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {Colors.BG_PANEL};
            }}
        """)

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

    def _make_input(self, text: str = "", width: int = 180) -> QLineEdit:
        e = QLineEdit(text)
        e.setStyleSheet(_input_style())
        e.setFixedWidth(width)
        return e

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Header ──
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
        hl.setSpacing(14)

        icon_box = QLabel()
        icon_box.setFixedSize(36, 36)
        icon_box.setAlignment(Qt.AlignCenter)
        icon_box.setPixmap(icon(Icons.SETTINGS, Colors.ACCENT_PRIMARY, 16).pixmap(16, 16))
        icon_box.setStyleSheet(f"""
            background-color: {Colors.ACCENT_GHOST};
            border: 1px solid {Colors.BORDER_ACCENT};
            border-radius: 8px;
        """)
        hl.addWidget(icon_box)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title_label = QLabel("Plot Settings")
        title_label.setStyleSheet(f"""
            color: {Colors.TEXT_PRIMARY}; font-size: 16px; font-weight: 700;
            background: transparent;
        """)
        title_col.addWidget(title_label)
        subtitle = QLabel(f"{self.plot_type} — Advanced Customization")
        subtitle.setStyleSheet(f"""
            color: {Colors.TEXT_TERTIARY}; font-size: 11px; font-weight: 500;
            background: transparent;
        """)
        title_col.addWidget(subtitle)
        hl.addLayout(title_col)
        hl.addStretch()

        close_btn = QPushButton()
        close_btn.setFixedSize(32, 32)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setIcon(icon(Icons.CLOSE, Colors.TEXT_MUTED, 14))
        close_btn.setIconSize(close_btn.size())
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: none; border-radius: 6px;
            }}
            QPushButton:hover {{
                background-color: {Colors.BG_HOVER};
            }}
        """)
        close_btn.clicked.connect(self.reject)
        hl.addWidget(close_btn)
        layout.addWidget(header)

        # ── Scrollable body ──
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"""
            QScrollArea {{ background: transparent; border: none; }}
            QScrollBar:vertical {{
                background: transparent; width: 6px; margin: 0;
            }}
            QScrollBar::handle:vertical {{
                background: {Colors.BORDER_STRONG}; border-radius: 3px; min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {Colors.TEXT_MUTED};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)

        body = QWidget()
        body.setStyleSheet("background: transparent;")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 6, 0, 6)
        body_layout.setSpacing(0)

        # ────────────────────────────
        # Section 1: Plot Titles
        # ────────────────────────────
        sec_titles = _SettingsSection(
            "Plot Titles", Icons.HEADING, _SettingsSection.BLUE)

        self.plot_title_edit = self._make_input(
            getattr(self.main_window, 'plot_title', ''), 220)
        self.plot_title_edit.setPlaceholderText("Optional plot title")
        sec_titles.addRow("Title", self.plot_title_edit)

        self.plot_subtitle_edit = self._make_input(
            getattr(self.main_window, 'plot_subtitle', ''), 220)
        self.plot_subtitle_edit.setPlaceholderText("Optional subtitle")
        sec_titles.addRow("Subtitle", self.plot_subtitle_edit)

        body_layout.addWidget(sec_titles)

        # ────────────────────────────
        # Section 2: Labels & Typography
        # ────────────────────────────
        sec_labels = _SettingsSection(
            "Labels & Typography", Icons.TEXT_HEIGHT, _SettingsSection.PURPLE)

        self.x_label_edit = self._make_input(
            getattr(self.main_window, 'x_axis_label', 'X Coordinate [m]'))
        sec_labels.addRow("X-Axis Label", self.x_label_edit)

        self.y_label_edit = self._make_input(
            getattr(self.main_window, 'y_axis_label', 'Y Coordinate [m]'))
        sec_labels.addRow("Y-Axis Label", self.y_label_edit)

        sec_labels.addDivider()

        self.axis_label_font_spin = self._make_spin()
        self.axis_label_font_spin.setRange(8, 20)
        self.axis_label_font_spin.setValue(getattr(self.main_window, 'axis_label_font_size', 11))
        sec_labels.addRow("Axis Label Font Size", self.axis_label_font_spin)

        self.axis_tick_font_spin = self._make_spin()
        self.axis_tick_font_spin.setRange(6, 18)
        self.axis_tick_font_spin.setValue(getattr(self.main_window, 'axis_tick_font_size', 9))
        sec_labels.addRow("Axis Tick Font Size", self.axis_tick_font_spin)

        sec_labels.addDivider()

        self.toggle_id_labels = ToggleSwitch("Show ID Labels")
        self.toggle_id_labels.setChecked(getattr(self.main_window, 'show_id_labels', True))
        sec_labels.addFullWidget(self.toggle_id_labels)

        self.id_font_spin = self._make_spin()
        self.id_font_spin.setRange(6, 24)
        self.id_font_spin.setValue(getattr(self.main_window, 'id_font_size', 9))
        sec_labels.addRow("ID Font Size", self.id_font_spin)

        self.toggle_head_labels = ToggleSwitch("Show Head Labels")
        self.toggle_head_labels.setChecked(getattr(self.main_window, 'show_head_labels', True))
        sec_labels.addFullWidget(self.toggle_head_labels)

        self.head_font_spin = self._make_spin()
        self.head_font_spin.setRange(6, 24)
        self.head_font_spin.setValue(getattr(self.main_window, 'head_font_size', 8))
        sec_labels.addRow("Head Font Size", self.head_font_spin)

        self.label_offset_spin = self._make_spin()
        self.label_offset_spin.setRange(0, 50)
        self.label_offset_spin.setValue(getattr(self.main_window, 'label_offset', 10))
        sec_labels.addRow("Label Offset (px)", self.label_offset_spin)

        body_layout.addWidget(sec_labels)

        # ────────────────────────────
        # Section 3: Spines & Grid
        # ────────────────────────────
        sec_spines = _SettingsSection(
            "Spines & Grid", Icons.BORDER_ALL, _SettingsSection.AMBER)

        self.show_left_spine_toggle = ToggleSwitch("Show Left Spine")
        self.show_left_spine_toggle.setChecked(
            bool(getattr(self.main_window, "show_left_spine", True))
        )
        sec_spines.addFullWidget(self.show_left_spine_toggle)

        self.show_bottom_spine_toggle = ToggleSwitch("Show Bottom Spine")
        self.show_bottom_spine_toggle.setChecked(
            bool(getattr(self.main_window, "show_bottom_spine", True))
        )
        sec_spines.addFullWidget(self.show_bottom_spine_toggle)

        self.show_top_spine_toggle = ToggleSwitch("Show Top Spine")
        self.show_top_spine_toggle.setChecked(
            bool(getattr(self.main_window, "show_top_spine", False))
        )
        sec_spines.addFullWidget(self.show_top_spine_toggle)

        self.show_right_spine_toggle = ToggleSwitch("Show Right Spine")
        self.show_right_spine_toggle.setChecked(
            bool(getattr(self.main_window, "show_right_spine", False))
        )
        sec_spines.addFullWidget(self.show_right_spine_toggle)

        sec_spines.addDivider()

        self.spine_width_spin = self._make_dspin()
        self.spine_width_spin.setRange(0.5, 5.0)
        self.spine_width_spin.setSingleStep(0.1)
        self.spine_width_spin.setValue(
            float(getattr(self.main_window, "spine_width", 1.0))
        )
        sec_spines.addRow("Spine Width", self.spine_width_spin)

        self.grid_line_width_spin = self._make_dspin()
        self.grid_line_width_spin.setRange(0.1, 3.0)
        self.grid_line_width_spin.setSingleStep(0.1)
        self.grid_line_width_spin.setValue(
            float(getattr(self.main_window, "grid_line_width", 0.5))
        )
        sec_spines.addRow("Grid Line Width", self.grid_line_width_spin)

        body_layout.addWidget(sec_spines)

        # ────────────────────────────
        # Section 4: Colors
        # ────────────────────────────
        sec_colors = _SettingsSection(
            "Colors", Icons.PALETTE, _SettingsSection.RED)

        self.id_color_btn = self._color_swatch(
            getattr(self.main_window, 'id_label_color', '#818cf8'))
        sec_colors.addRow("ID Label Color", self.id_color_btn)

        self.head_color_btn = self._color_swatch(
            getattr(self.main_window, 'head_label_color', '#a0a0a0'))
        sec_colors.addRow("Head Label Color", self.head_color_btn)

        self.arrow_color_btn = self._color_swatch(
            getattr(self.main_window, 'arrow_color', '#000000'))
        sec_colors.addRow("Arrow Color", self.arrow_color_btn)

        self.arrow_outline_color_btn = self._color_swatch(
            getattr(self.main_window, 'arrow_outline_color', '#ffffff'))
        sec_colors.addRow("Arrow Outline Color", self.arrow_outline_color_btn)

        body_layout.addWidget(sec_colors)

        # ────────────────────────────
        # Section 5: Plot-Specific
        # ────────────────────────────
        # Determine display name for plot type
        plot_display = {
            "2D": "2D Plot Options",
            "3D": "3D Plot Options",
            "Gradient Vectors": "Vector Options",
            "Histogram": "Histogram Options",
            "Rose Diagram": "Rose Diagram Options",
        }.get(self.plot_type, "Plot Options")

        sec_specific = _SettingsSection(
            plot_display, Icons.SLIDERS, _SettingsSection.AMBER)

        self._specific_stack = QStackedWidget()
        self._specific_stack.setStyleSheet("background: transparent;")

        # 2D options
        w_2d = QWidget()
        f_2d = QFormLayout(w_2d)
        f_2d.setSpacing(10)
        self.interp_combo = QComboBox()
        self.interp_combo.addItems(['cubic', 'linear', 'nearest'])
        self.interp_combo.setStyleSheet(_combo_style())
        f_2d.addRow("Interpolation:", self.interp_combo)

        # Point glow effect controls
        self.show_point_glow_toggle = ToggleSwitch("Point Glow Effect")
        self.show_point_glow_toggle.setChecked(
            bool(getattr(self.main_window, "show_point_glow", True))
        )
        f_2d.addRow(self.show_point_glow_toggle)

        self.point_glow_size_spin = self._make_dspin()
        self.point_glow_size_spin.setRange(1.5, 4.0)
        self.point_glow_size_spin.setSingleStep(0.1)
        self.point_glow_size_spin.setValue(
            float(getattr(self.main_window, "point_glow_size_multiplier", 2.2))
        )
        f_2d.addRow("Glow Size Multiplier:", self.point_glow_size_spin)

        self.point_glow_alpha_spin = self._make_spin()
        self.point_glow_alpha_spin.setRange(5, 30)
        self.point_glow_alpha_spin.setSuffix("%")
        try:
            glow_alpha_pct = int(round(float(getattr(self.main_window, "point_glow_alpha", 0.12)) * 100.0))
        except Exception:
            glow_alpha_pct = 12
        self.point_glow_alpha_spin.setValue(max(5, min(glow_alpha_pct, 30)))
        f_2d.addRow("Glow Opacity:", self.point_glow_alpha_spin)

        self.show_point_glow_toggle.toggled.connect(self._update_glow_controls)
        self._update_glow_controls()

        self.arrow_outline_width_spin = self._make_dspin()
        self.arrow_outline_width_spin.setRange(0.0, 5.0)
        self.arrow_outline_width_spin.setSingleStep(0.1)
        self.arrow_outline_width_spin.setValue(getattr(self.main_window, 'arrow_outline_width', 0.0))
        f_2d.addRow("Arrow Outline Width:", self.arrow_outline_width_spin)

        self.arrow_x_edit = self._make_input("", 100)
        self.arrow_x_edit.setPlaceholderText("Auto")
        f_2d.addRow("Arrow Start X:", self.arrow_x_edit)
        self.arrow_y_edit = self._make_input("", 100)
        self.arrow_y_edit.setPlaceholderText("Auto")
        f_2d.addRow("Arrow Start Y:", self.arrow_y_edit)
        # Contour styling (merged into 2D)
        self.contour_linewidth_spin = self._make_dspin()
        self.contour_linewidth_spin.setRange(0.1, 5.0)
        self.contour_linewidth_spin.setValue(getattr(self.main_window, 'contour_linewidth', 0.8))
        self.contour_linewidth_spin.setSingleStep(0.1)
        f_2d.addRow("Contour Line Width:", self.contour_linewidth_spin)
        self.contour_label_font_spin = self._make_spin()
        self.contour_label_font_spin.setRange(6, 16)
        self.contour_label_font_spin.setValue(getattr(self.main_window, 'contour_label_font_size', 9))
        f_2d.addRow("Contour Label Size:", self.contour_label_font_spin)
        self.contour_extent_spin = self._make_spin()
        self.contour_extent_spin.setRange(0, 30)
        self.contour_extent_spin.setValue(int(getattr(self.main_window, 'contour_extent_pct', 0)))
        f_2d.addRow("Contour Extent (%):", self.contour_extent_spin)
        self.contour_extrapolation_combo = QComboBox()
        self.contour_extrapolation_combo.addItems(["None", "Nearest", "IDW"])
        self.contour_extrapolation_combo.setStyleSheet(_combo_style())
        current_extrap = str(getattr(self.main_window, 'contour_extrapolation', 'none') or 'none').lower()
        extrap_label = {"none": "None", "nearest": "Nearest", "idw": "IDW"}.get(current_extrap, "None")
        self.contour_extrapolation_combo.setCurrentText(extrap_label)
        f_2d.addRow("Extrapolation:", self.contour_extrapolation_combo)
        contour_exp_note = QLabel(
            "Experimental: extent/extrapolation can introduce artifacts on sparse data."
        )
        contour_exp_note.setWordWrap(True)
        contour_exp_note.setStyleSheet(
            f"color: {Colors.TEXT_TERTIARY}; font-size: 10px; font-style: italic;"
        )
        f_2d.addRow(contour_exp_note)

        self.show_excluded_toggle = ToggleSwitch("Show Excluded Points")
        self.show_excluded_toggle.setChecked(bool(getattr(self.main_window, "show_excluded_points", True)))
        f_2d.addRow(self.show_excluded_toggle)

        self.custom_excluded_style_toggle = ToggleSwitch("Custom Excluded Style")
        self.custom_excluded_style_toggle.setChecked(bool(getattr(self.main_window, "custom_excluded_style", False)))
        f_2d.addRow(self.custom_excluded_style_toggle)

        self.excluded_marker_combo = QComboBox()
        self.excluded_marker_combo.setStyleSheet(_combo_style())
        self.excluded_marker_combo.addItems(["x", "o", "s", "^", "v", "D", "P", "*", "+"])
        current_excluded_marker = str(getattr(self.main_window, "excluded_marker", "x") or "x")
        idx_marker = self.excluded_marker_combo.findText(current_excluded_marker)
        if idx_marker >= 0:
            self.excluded_marker_combo.setCurrentIndex(idx_marker)
        f_2d.addRow("Excluded Marker:", self.excluded_marker_combo)

        self.excluded_color_btn = self._color_swatch(
            str(getattr(self.main_window, "excluded_color", "#6a6a6a") or "#6a6a6a")
        )
        f_2d.addRow("Excluded Color:", self.excluded_color_btn)

        self.excluded_opacity_spin = self._make_spin()
        self.excluded_opacity_spin.setRange(0, 100)
        self.excluded_opacity_spin.setSuffix("%")
        try:
            excluded_opacity_pct = int(round(float(getattr(self.main_window, "excluded_opacity", 0.3)) * 100.0))
        except Exception:
            excluded_opacity_pct = 30
        self.excluded_opacity_spin.setValue(max(0, min(excluded_opacity_pct, 100)))
        f_2d.addRow("Excluded Opacity:", self.excluded_opacity_spin)

        self.excluded_size_scale_spin = self._make_spin()
        self.excluded_size_scale_spin.setRange(10, 300)
        self.excluded_size_scale_spin.setSuffix("%")
        try:
            excluded_size_pct = int(round(float(getattr(self.main_window, "excluded_size_scale", 0.75)) * 100.0))
        except Exception:
            excluded_size_pct = 75
        self.excluded_size_scale_spin.setValue(max(10, min(excluded_size_pct, 300)))
        f_2d.addRow("Excluded Size Scale:", self.excluded_size_scale_spin)

        self.sync_xy_ticks_toggle_2d = ToggleSwitch("Sync X/Y Major Tick Step")
        self.sync_xy_ticks_toggle_2d.setChecked(bool(getattr(self.main_window, "sync_xy_major_ticks", False)))
        f_2d.addRow(self.sync_xy_ticks_toggle_2d)

        self.show_geology_strip_toggle = ToggleSwitch("Show Geology Strip (WIP / Experimental)")
        self.show_geology_strip_toggle.setChecked(
            bool(getattr(self.main_window, "show_geology_strip_experimental", False))
        )
        f_2d.addRow(self.show_geology_strip_toggle)
        geology_note = QLabel(
            "Cross-section only. Uses placeholder geology provider for concept validation."
        )
        geology_note.setWordWrap(True)
        geology_note.setStyleSheet(
            f"color: {Colors.TEXT_TERTIARY}; font-size: 10px; font-style: italic;"
        )
        f_2d.addRow(geology_note)

        self.show_stacked_points_toggle = ToggleSwitch("Stacked Points Explode (WIP / Experimental)")
        self.show_stacked_points_toggle.setChecked(
            bool(getattr(self.main_window, "show_stacked_points_experimental", True))
        )
        f_2d.addRow(self.show_stacked_points_toggle)
        stacked_note = QLabel(
            "2D only. Click stacked marker badge (xN) to explode and select a specific intake."
        )
        stacked_note.setWordWrap(True)
        stacked_note.setStyleSheet(
            f"color: {Colors.TEXT_TERTIARY}; font-size: 10px; font-style: italic;"
        )
        f_2d.addRow(stacked_note)

        self.show_excluded_toggle.toggled.connect(self._update_excluded_style_controls)
        self.custom_excluded_style_toggle.toggled.connect(self._update_excluded_style_controls)
        self._update_excluded_style_controls()
        self._specific_stack.addWidget(w_2d)

        # 3D options (wireframe and opacity moved to sidebar)
        w_3d = QWidget()
        f_3d = QFormLayout(w_3d)
        f_3d.setSpacing(10)

        placeholder_3d = QLabel("3D-specific cosmetic options will go here (currently all moved to sidebar).")
        placeholder_3d.setWordWrap(True)
        placeholder_3d.setStyleSheet(f"""
            color: {Colors.TEXT_TERTIARY};
            font-size: 10px;
            font-style: italic;
            padding: 10px;
        """)
        f_3d.addRow(placeholder_3d)

        self._specific_stack.addWidget(w_3d)

        # Vector options
        w_vec = QWidget()
        f_vec = QFormLayout(w_vec)
        f_vec.setSpacing(10)
        self.scale_spin = self._make_dspin()
        self.scale_spin.setRange(0.1, 100.0)
        self.scale_spin.setValue(50.0)
        self.scale_spin.setSingleStep(5.0)
        f_vec.addRow("Scale Factor:", self.scale_spin)
        self.alpha_slider = QSlider(Qt.Horizontal)
        self.alpha_slider.setRange(10, 100)
        self.alpha_slider.setValue(70)
        f_vec.addRow("Opacity:", self.alpha_slider)
        self.marker_size_spin = self._make_spin()
        self.marker_size_spin.setRange(10, 300)
        self.marker_size_spin.setValue(80)
        f_vec.addRow("Marker Size:", self.marker_size_spin)
        self.sync_xy_ticks_toggle_vec = ToggleSwitch("Sync X/Y Major Tick Step")
        self.sync_xy_ticks_toggle_vec.setChecked(bool(getattr(self.main_window, "sync_xy_major_ticks", False)))
        f_vec.addRow(self.sync_xy_ticks_toggle_vec)
        self._specific_stack.addWidget(w_vec)

        # Histogram options
        w_hist = QWidget()
        f_hist = QFormLayout(w_hist)
        f_hist.setSpacing(10)
        self.hist_x_label_edit = self._make_input(
            getattr(self.main_window, 'x_axis_label', 'Gradient Magnitude'), 160)
        f_hist.addRow("X Label:", self.hist_x_label_edit)
        self.hist_y_label_edit = self._make_input(
            getattr(self.main_window, 'y_axis_label', 'Frequency'), 160)
        f_hist.addRow("Y Label:", self.hist_y_label_edit)
        self._specific_stack.addWidget(w_hist)

        # Rose options
        w_rose = QWidget()
        f_rose = QFormLayout(w_rose)
        f_rose.setSpacing(10)
        self.rose_title_edit = self._make_input("Gradient Direction Distribution", 200)
        f_rose.addRow("Title:", self.rose_title_edit)
        self._specific_stack.addWidget(w_rose)

        type_to_idx = {
            "2D": 0, "3D": 1,
            "Gradient Vectors": 2, "Histogram": 3, "Rose Diagram": 4,
        }
        self._specific_stack.setCurrentIndex(type_to_idx.get(self.plot_type, 0))

        sec_specific.addFullWidget(self._specific_stack)
        body_layout.addWidget(sec_specific)

        # ────────────────────────────
        # Section 6: Calculation Parameters
        # ────────────────────────────
        sec_calc = _SettingsSection(
            "Calculation Parameters", Icons.WARNING, _SettingsSection.AMBER)

        warning = QLabel(
            "These control triangle rejection thresholds. "
            "Changing them recomputes gradients for the current dataset."
        )
        warning.setWordWrap(True)
        warning.setStyleSheet(f"""
            color: {Colors.TEXT_TERTIARY};
            font-size: 10px;
            font-style: italic;
            background-color: {Colors.BG_SURFACE};
            padding: 6px 10px;
            border-radius: 6px;
            border: 1px solid {Colors.BORDER_SUBTLE};
        """)
        sec_calc.addFullWidget(warning)

        self.head_uncertainty_spin = self._make_dspin()
        self.head_uncertainty_spin.setDecimals(4)
        self.head_uncertainty_spin.setRange(0.0, 10.0)
        self.head_uncertainty_spin.setSingleStep(0.005)
        self.head_uncertainty_spin.setFixedWidth(85)
        self.head_uncertainty_spin.setMaximumWidth(85)
        self.head_uncertainty_spin.setValue(
            float(getattr(self.main_window, "gradient_head_uncertainty", 0.01)))
        sec_calc.addRow("Head Uncertainty (L)", self.head_uncertainty_spin)

        self.confidence_spin = self._make_dspin()
        self.confidence_spin.setDecimals(1)
        self.confidence_spin.setRange(1.0, 99.9)
        self.confidence_spin.setSingleStep(1.0)
        self.confidence_spin.setSuffix(" %")
        self.confidence_spin.setFixedWidth(85)
        self.confidence_spin.setMaximumWidth(85)
        self.confidence_spin.setValue(
            float(getattr(self.main_window, "gradient_confidence_level", 0.66)) * 100.0)
        sec_calc.addRow("Confidence Level", self.confidence_spin)

        self.ratio_low_spin = self._make_dspin()
        self.ratio_low_spin.setDecimals(3)
        self.ratio_low_spin.setRange(0.0, 100.0)
        self.ratio_low_spin.setSingleStep(0.05)
        self.ratio_low_spin.setFixedWidth(85)
        self.ratio_low_spin.setMaximumWidth(85)
        self.ratio_low_spin.setValue(
            float(getattr(self.main_window, "gradient_base_height_low", 0.2)))
        sec_calc.addRow("Base:Height Low", self.ratio_low_spin)

        self.ratio_high_spin = self._make_dspin()
        self.ratio_high_spin.setDecimals(3)
        self.ratio_high_spin.setRange(0.0, 1e6)
        self.ratio_high_spin.setSingleStep(0.5)
        self.ratio_high_spin.setFixedWidth(85)
        self.ratio_high_spin.setMaximumWidth(85)
        self.ratio_high_spin.setValue(
            float(getattr(self.main_window, "gradient_base_height_high", 8.0)))
        sec_calc.addRow("Base:Height High", self.ratio_high_spin)

        self.max_base_height_spin = self._make_dspin()
        self.max_base_height_spin.setDecimals(0)
        self.max_base_height_spin.setRange(0.0, 1e12)
        self.max_base_height_spin.setSingleStep(1000.0)
        self.max_base_height_spin.setFixedWidth(110)
        self.max_base_height_spin.setMaximumWidth(110)
        self.max_base_height_spin.setValue(
            float(getattr(self.main_window, "gradient_max_base_or_height", 1e9)))
        sec_calc.addRow("Max Base or Height (L)", self.max_base_height_spin)

        self.stacked_epsilon_edit = self._make_input(
            str(getattr(self.main_window, "gradient_stacked_epsilon", 1e-10)), 100)
        self.stacked_epsilon_edit.setAlignment(Qt.AlignCenter)
        sec_calc.addRow("Stacked Point Epsilon", self.stacked_epsilon_edit)

        body_layout.addWidget(sec_calc)

        body_layout.addStretch()
        scroll.setWidget(body)
        layout.addWidget(scroll, 1)

        # ── Footer ──
        footer = QWidget()
        footer.setFixedHeight(64)
        footer.setStyleSheet(f"""
            QWidget {{
                background-color: {Colors.BG_PANEL};
                border-top: 1px solid {Colors.BORDER_DEFAULT};
            }}
        """)
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(24, 0, 24, 0)
        fl.setSpacing(10)

        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.setCursor(Qt.PointingHandCursor)
        reset_btn.setStyleSheet(f"""
            QPushButton {{
                color: {Colors.TEXT_SECONDARY};
                background: transparent;
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 8px;
                font-size: 11px; font-weight: 600;
                padding: 9px 18px;
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
                padding: 9px 18px;
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
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(129, 140, 248, 0.85),
                    stop:1 rgba(129, 140, 248, 0.95));
                border: 1px solid {Colors.ACCENT_PRIMARY};
                border-radius: 8px;
                font-size: 11px; font-weight: 700;
                padding: 9px 20px;
            }}
            QPushButton:hover {{
                background: {Colors.ACCENT_PRIMARY};
            }}
        """)
        apply_btn.clicked.connect(self._apply)
        fl.addWidget(apply_btn)

        layout.addWidget(footer)

    # ── Helpers ──

    def _set_swatch_color(self, button: QPushButton, hex_color: str):
        button.setProperty("color", hex_color)
        button.setStyleSheet(f"""
            QPushButton {{
                background-color: {hex_color};
                border: 2px solid {Colors.BORDER_MEDIUM};
                border-radius: 4px;
            }}
            QPushButton:hover {{
                border-color: {Colors.ACCENT_PRIMARY};
            }}
        """)

    def _color_swatch(self, hex_color: str) -> QPushButton:
        btn = QPushButton()
        btn.setFixedSize(28, 20)
        btn.setCursor(Qt.PointingHandCursor)
        self._set_swatch_color(btn, hex_color)
        btn.clicked.connect(lambda: self._pick_color(btn))
        return btn

    def _pick_color(self, button):
        current = QColor(button.property("color"))
        color = QColorDialog.getColor(current, self, "Select Color")
        if color.isValid():
            self._set_swatch_color(button, color.name())

    def _update_excluded_style_controls(self):
        show = bool(getattr(self, "show_excluded_toggle", None) and self.show_excluded_toggle.isChecked())
        custom = bool(getattr(self, "custom_excluded_style_toggle", None) and self.custom_excluded_style_toggle.isChecked())

        if hasattr(self, "custom_excluded_style_toggle"):
            self.custom_excluded_style_toggle.setEnabled(show)

        enabled = show and custom
        for attr_name in (
            "excluded_marker_combo",
            "excluded_color_btn",
            "excluded_opacity_spin",
            "excluded_size_scale_spin",
        ):
            widget = getattr(self, attr_name, None)
            if widget is not None:
                widget.setEnabled(enabled)

    def _update_glow_controls(self):
        """Enable/disable glow parameter controls based on toggle state."""
        enabled = bool(getattr(self, "show_point_glow_toggle", None) and self.show_point_glow_toggle.isChecked())
        for attr_name in ("point_glow_size_spin", "point_glow_alpha_spin"):
            widget = getattr(self, attr_name, None)
            if widget is not None:
                widget.setEnabled(enabled)

    # ── Reset ──

    def _reset_defaults(self):
        # Titles
        if hasattr(self, "plot_title_edit"):
            self.plot_title_edit.setText("")
        if hasattr(self, "plot_subtitle_edit"):
            self.plot_subtitle_edit.setText("")

        # Labels
        self.x_label_edit.setText("X Coordinate [m]")
        self.y_label_edit.setText("Y Coordinate [m]")
        self.axis_label_font_spin.setValue(11)
        self.axis_tick_font_spin.setValue(9)
        self.toggle_id_labels.setChecked(True)
        self.toggle_head_labels.setChecked(True)
        self.id_font_spin.setValue(9)
        self.head_font_spin.setValue(8)
        self.label_offset_spin.setValue(10)

        # Spines & Grid
        if hasattr(self, "show_left_spine_toggle"):
            self.show_left_spine_toggle.setChecked(True)
        if hasattr(self, "show_bottom_spine_toggle"):
            self.show_bottom_spine_toggle.setChecked(True)
        if hasattr(self, "show_top_spine_toggle"):
            self.show_top_spine_toggle.setChecked(False)
        if hasattr(self, "show_right_spine_toggle"):
            self.show_right_spine_toggle.setChecked(False)
        if hasattr(self, "spine_width_spin"):
            self.spine_width_spin.setValue(1.0)
        if hasattr(self, "grid_line_width_spin"):
            self.grid_line_width_spin.setValue(0.5)

        # Colors
        self._set_swatch_color(self.id_color_btn, "#818cf8")
        self._set_swatch_color(self.head_color_btn, "#a0a0a0")
        self._set_swatch_color(self.arrow_color_btn, "#000000")
        self._set_swatch_color(self.arrow_outline_color_btn, "#ffffff")
        if hasattr(self, "arrow_outline_width_spin"):
            self.arrow_outline_width_spin.setValue(0.0)
        if hasattr(self, "show_excluded_toggle"):
            self.show_excluded_toggle.setChecked(True)
        if hasattr(self, "custom_excluded_style_toggle"):
            self.custom_excluded_style_toggle.setChecked(False)
        if hasattr(self, "excluded_marker_combo"):
            self.excluded_marker_combo.setCurrentText("x")
        if hasattr(self, "excluded_color_btn"):
            self._set_swatch_color(self.excluded_color_btn, "#6a6a6a")
        if hasattr(self, "excluded_opacity_spin"):
            self.excluded_opacity_spin.setValue(30)
        if hasattr(self, "excluded_size_scale_spin"):
            self.excluded_size_scale_spin.setValue(75)
        if hasattr(self, "sync_xy_ticks_toggle_2d"):
            self.sync_xy_ticks_toggle_2d.setChecked(False)
        if hasattr(self, "show_point_glow_toggle"):
            self.show_point_glow_toggle.setChecked(True)
        if hasattr(self, "point_glow_size_spin"):
            self.point_glow_size_spin.setValue(2.2)
        if hasattr(self, "point_glow_alpha_spin"):
            self.point_glow_alpha_spin.setValue(12)
        self._update_glow_controls()
        if hasattr(self, "show_geology_strip_toggle"):
            self.show_geology_strip_toggle.setChecked(False)
        if hasattr(self, "show_stacked_points_toggle"):
            self.show_stacked_points_toggle.setChecked(True)
        if hasattr(self, "sync_xy_ticks_toggle_vec"):
            self.sync_xy_ticks_toggle_vec.setChecked(False)
        self._update_excluded_style_controls()

        self.head_uncertainty_spin.setValue(0.01)
        self.confidence_spin.setValue(66.0)
        self.ratio_low_spin.setValue(0.2)
        self.ratio_high_spin.setValue(8.0)
        self.max_base_height_spin.setValue(1e9)
        self.stacked_epsilon_edit.setText("1e-10")
        if hasattr(self, "contour_extent_spin"):
            self.contour_extent_spin.setValue(0)
        if hasattr(self, "contour_extrapolation_combo"):
            self.contour_extrapolation_combo.setCurrentText("None")

    # ── Apply ──

    def _apply(self):
        mw = self.main_window
        dataset = mw.get_active_dataset() if hasattr(mw, "get_active_dataset") else None

        # Titles
        if hasattr(self, "plot_title_edit"):
            mw.plot_title = self.plot_title_edit.text()
        if hasattr(self, "plot_subtitle_edit"):
            mw.plot_subtitle = self.plot_subtitle_edit.text()

        # Labels
        mw.x_axis_label = self.x_label_edit.text()
        mw.y_axis_label = self.y_label_edit.text()
        mw.axis_label_font_size = self.axis_label_font_spin.value()
        mw.axis_tick_font_size = self.axis_tick_font_spin.value()
        mw.show_id_labels = self.toggle_id_labels.isChecked()
        mw.show_head_labels = self.toggle_head_labels.isChecked()
        mw.id_font_size = self.id_font_spin.value()
        mw.head_font_size = self.head_font_spin.value()
        mw.label_offset = self.label_offset_spin.value()

        # Spines & Grid
        if hasattr(self, "show_left_spine_toggle"):
            mw.show_left_spine = bool(self.show_left_spine_toggle.isChecked())
        if hasattr(self, "show_bottom_spine_toggle"):
            mw.show_bottom_spine = bool(self.show_bottom_spine_toggle.isChecked())
        if hasattr(self, "show_top_spine_toggle"):
            mw.show_top_spine = bool(self.show_top_spine_toggle.isChecked())
        if hasattr(self, "show_right_spine_toggle"):
            mw.show_right_spine = bool(self.show_right_spine_toggle.isChecked())
        if hasattr(self, "spine_width_spin"):
            mw.spine_width = float(self.spine_width_spin.value())
        if hasattr(self, "grid_line_width_spin"):
            mw.grid_line_width = float(self.grid_line_width_spin.value())

        # Colors
        mw.id_label_color = self.id_color_btn.property("color")
        mw.head_label_color = self.head_color_btn.property("color")
        mw.arrow_color = self.arrow_color_btn.property("color")
        mw.arrow_outline_color = self.arrow_outline_color_btn.property("color")

        # Plot-specific
        idx = self._specific_stack.currentIndex()
        if idx == 0:  # 2D
            mw.interpolation_method = self.interp_combo.currentText()
            mw.arrow_outline_width = self.arrow_outline_width_spin.value()
            text_x = self.arrow_x_edit.text().strip()
            mw.arrow_start_x = float(text_x) if text_x else None
            text_y = self.arrow_y_edit.text().strip()
            mw.arrow_start_y = float(text_y) if text_y else None
            if hasattr(self, "contour_linewidth_spin"):
                mw.contour_linewidth = self.contour_linewidth_spin.value()
            if hasattr(self, "contour_label_font_spin"):
                mw.contour_label_font_size = self.contour_label_font_spin.value()
            if hasattr(self, "contour_extent_spin"):
                mw.contour_extent_pct = self.contour_extent_spin.value()
            if hasattr(self, "contour_extrapolation_combo"):
                mw.contour_extrapolation = self.contour_extrapolation_combo.currentText().lower()
            if hasattr(self, "show_excluded_toggle"):
                mw.show_excluded_points = bool(self.show_excluded_toggle.isChecked())
            if hasattr(self, "custom_excluded_style_toggle"):
                mw.custom_excluded_style = bool(self.custom_excluded_style_toggle.isChecked())
            if hasattr(self, "excluded_marker_combo"):
                mw.excluded_marker = str(self.excluded_marker_combo.currentText() or "x")
            if hasattr(self, "excluded_color_btn"):
                mw.excluded_color = str(self.excluded_color_btn.property("color") or "#6a6a6a")
            if hasattr(self, "excluded_opacity_spin"):
                mw.excluded_opacity = float(self.excluded_opacity_spin.value()) / 100.0
            if hasattr(self, "excluded_size_scale_spin"):
                mw.excluded_size_scale = float(self.excluded_size_scale_spin.value()) / 100.0
            if hasattr(self, "sync_xy_ticks_toggle_2d"):
                mw.sync_xy_major_ticks = bool(self.sync_xy_ticks_toggle_2d.isChecked())
            if hasattr(self, "show_point_glow_toggle"):
                mw.show_point_glow = bool(self.show_point_glow_toggle.isChecked())
            if hasattr(self, "point_glow_size_spin"):
                mw.point_glow_size_multiplier = float(self.point_glow_size_spin.value())
            if hasattr(self, "point_glow_alpha_spin"):
                mw.point_glow_alpha = float(self.point_glow_alpha_spin.value()) / 100.0
            if hasattr(self, "show_geology_strip_toggle"):
                mw.show_geology_strip_experimental = bool(self.show_geology_strip_toggle.isChecked())
            if hasattr(self, "show_stacked_points_toggle"):
                mw.show_stacked_points_experimental = bool(self.show_stacked_points_toggle.isChecked())
        elif idx == 1:  # 3D (wireframe and opacity moved to sidebar)
            pass
        elif idx == 2:  # Vectors
            mw.vector_scale = self.scale_spin.value()
            mw.vector_alpha = self.alpha_slider.value() / 100.0
            mw.marker_size = self.marker_size_spin.value()
            if hasattr(self, "sync_xy_ticks_toggle_vec"):
                mw.sync_xy_major_ticks = bool(self.sync_xy_ticks_toggle_vec.isChecked())

        # Calculation parameters
        mw.gradient_head_uncertainty = self.head_uncertainty_spin.value()
        mw.gradient_confidence_level = self.confidence_spin.value() / 100.0
        mw.gradient_base_height_low = self.ratio_low_spin.value()
        mw.gradient_base_height_high = self.ratio_high_spin.value()
        mw.gradient_max_base_or_height = self.max_base_height_spin.value()
        try:
            mw.gradient_stacked_epsilon = float(self.stacked_epsilon_edit.text())
        except ValueError:
            mw.gradient_stacked_epsilon = 1e-10

        if dataset is not None and hasattr(mw, "sync_to_dataset"):
            mw.sync_to_dataset(dataset)

        mw.update_plot()
        self.accept()
