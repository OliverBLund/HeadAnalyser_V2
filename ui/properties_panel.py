"""
HeadAnalyser V2 - Properties Panel.

Responsibilities:
- Present filter controls and exclusion management UI.
- Infer and communicate active depth-source mode (top+bottom / single / none).
- Emit filter changes to MainWindow; does not own filtering logic.

Data-flow rule:
- User actions here should feed MainWindow central handlers, which execute the
  canonical filter->recompute->refresh pipeline.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QCheckBox, QSlider, QDoubleSpinBox, QFrame, QScrollArea,
    QSizePolicy, QPushButton, QSpinBox, QGridLayout, QListWidget,
    QListWidgetItem, QGroupBox
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QPainter, QColor, QPixmap, QFont, QPen
import numpy as np
import pandas as pd

from styles.colors import Colors
from styles.stylesheet import StyleSheet
from ui.scaling import build_screen_metrics
from .point_selection_dialog import PointSelectionDialog
from .common_widgets import SectionHeader, ToggleSwitch, _TogglePill, CardSection
from .icons import Icons
from .theme_utils import reset_widget_layout


class PanelHeader(QWidget):
    """Section header widget with professional styling."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        metrics = build_screen_metrics(parent)
        self.setFixedHeight(36 if metrics.compact else 40)
        # Updated gradient: from BG_ELEVATED (#28282f) to BG_SURFACE (#212127)
        # with 1px border-bottom using BORDER_DEFAULT
        self.setStyleSheet(f"""
            background-color: {Colors.BG_ELEVATED};
            border: none;
            border-bottom: 1px solid {Colors.BORDER_DEFAULT};
            border-radius: 4px 4px 0px 0px;
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)

        label = QLabel(title)
        label.setStyleSheet(f"""
            background-color: transparent;
            color: {Colors.ACCENT_PRIMARY};
            font-size: {metrics.font_sm}px;
            font-weight: 700;
            letter-spacing: 1.2px;
        """)
        layout.addWidget(label)
        layout.addStretch()


class GroupBoxSection(QGroupBox):
    """Professional group box for clear visual grouping.

    Kept for backward-compatibility with sections that still use it
    (e.g. _create_rejected_triangles_section).
    """

    def __init__(self, title: str, parent=None):
        super().__init__(title, parent)
        self.setStyleSheet(f"""
            QGroupBox {{
                background-color: {Colors.BG_ELEVATED};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: {Colors.RADIUS_SM};
                margin-top: 12px;
                padding-top: 16px;
                font-size: 11px;
                font-weight: 700;
                color: {Colors.TEXT_PRIMARY};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 4px 12px;
                background-color: {Colors.BG_SURFACE};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 4px;
                color: {Colors.ACCENT_PRIMARY};
                left: 10px;
            }}
        """)


class RangeSliderWidget(QWidget):
    """Dual range slider with fixed-width labels."""

    value_changed = pyqtSignal(float, float)
    value_committed = pyqtSignal(float, float)

    def __init__(self, label: str, unit: str = "", parent=None):
        super().__init__(parent)
        metrics = build_screen_metrics(parent)
        self.unit = unit
        self._min_val = 0
        self._max_val = 100

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Label row with values - FIXED WIDTH for value label
        label_row = QHBoxLayout()

        self.label = QLabel(label)
        self.label.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY}; font-size: {metrics.font_md}px; font-weight: 500;"
        )
        label_row.addWidget(self.label)

        label_row.addStretch()

        # Fixed width value label to prevent cutoff
        # Softer border using BORDER_ACCENT and ACCENT_GHOST background
        self.value_label = QLabel("0.0 - 100.0")
        self.value_label.setFixedWidth(metrics.value_label_width)
        self.value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.value_label.setStyleSheet(f"""
            color: {Colors.ACCENT_PRIMARY};
            font-size: {metrics.font_sm}px;
            font-weight: 700;
            background-color: {Colors.ACCENT_GHOST};
            padding: 2px 7px;
            border-radius: 3px;
            border: 1px solid {Colors.BORDER_ACCENT};
        """)
        label_row.addWidget(self.value_label)

        layout.addLayout(label_row)

        # Sliders
        slider_layout = QHBoxLayout()
        slider_layout.setSpacing(8)

        self.min_slider = QSlider(Qt.Horizontal)
        self.min_slider.setRange(0, 100)
        self.min_slider.setValue(0)
        self.min_slider.setStyleSheet(StyleSheet.get_range_slider_style())
        self.min_slider.valueChanged.connect(self._on_min_changed)
        slider_layout.addWidget(self.min_slider)

        self.max_slider = QSlider(Qt.Horizontal)
        self.max_slider.setRange(0, 100)
        self.max_slider.setValue(100)
        self.max_slider.setStyleSheet(StyleSheet.get_range_slider_style())
        self.max_slider.valueChanged.connect(self._on_max_changed)
        slider_layout.addWidget(self.max_slider)

        self.min_slider.sliderReleased.connect(self._emit_value_committed)
        self.max_slider.sliderReleased.connect(self._emit_value_committed)

        self._commit_timer = QTimer(self)
        self._commit_timer.setSingleShot(True)
        self._commit_timer.setInterval(180)
        self._commit_timer.timeout.connect(self._emit_committed_if_idle)

        layout.addLayout(slider_layout)

        # Range labels
        range_layout = QHBoxLayout()
        self.min_label = QLabel("0.0")
        self.min_label.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: {metrics.font_sm}px;")
        range_layout.addWidget(self.min_label)

        range_layout.addStretch()

        self.max_label = QLabel("100.0")
        self.max_label.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: {metrics.font_sm}px;")
        range_layout.addWidget(self.max_label)

        layout.addLayout(range_layout)

    def _on_min_changed(self, value):
        self._update_value_label()
        self.value_changed.emit(self.get_min_value(), self.get_max_value())
        self._commit_timer.start()

    def _on_max_changed(self, value):
        self._update_value_label()
        self.value_changed.emit(self.get_min_value(), self.get_max_value())
        self._commit_timer.start()

    def _emit_committed_if_idle(self):
        if self.min_slider.isSliderDown() or self.max_slider.isSliderDown():
            self._commit_timer.start()
            return
        self._emit_value_committed()

    def _emit_value_committed(self):
        self.value_committed.emit(self.get_min_value(), self.get_max_value())

    def _update_value_label(self):
        min_v = self.get_min_value()
        max_v = self.get_max_value()
        self.value_label.setText(f"{min_v:.1f}-{max_v:.1f}")  # Compact format

    def set_range(self, min_val: float, max_val: float):
        self._min_val = min_val
        self._max_val = max_val
        self.min_label.setText(f"{min_val:.1f}")
        self.max_label.setText(f"{max_val:.1f}")
        self._commit_timer.stop()
        self.min_slider.blockSignals(True)
        self.max_slider.blockSignals(True)
        self.min_slider.setValue(0)
        self.max_slider.setValue(100)
        self.min_slider.blockSignals(False)
        self.max_slider.blockSignals(False)
        self._update_value_label()

    def get_min_value(self):
        pct = self.min_slider.value() / 100.0
        return self._min_val + pct * (self._max_val - self._min_val)

    def get_max_value(self):
        pct = self.max_slider.value() / 100.0
        return self._min_val + pct * (self._max_val - self._min_val)

    def get_values(self):
        return self.get_min_value(), self.get_max_value()

    def get_bounds(self):
        return float(self._min_val), float(self._max_val)

    def set_values(self, min_val: float, max_val: float):
        span = float(self._max_val - self._min_val)
        if not np.isfinite(span) or span <= 0:
            self._update_value_label()
            return

        vmin = float(min_val)
        vmax = float(max_val)
        if not np.isfinite(vmin):
            vmin = float(self._min_val)
        if not np.isfinite(vmax):
            vmax = float(self._max_val)

        lo = float(max(self._min_val, min(vmin, vmax)))
        hi = float(min(self._max_val, max(vmin, vmax)))
        if hi < lo:
            lo, hi = hi, lo

        lo_pct = int(round(100.0 * (lo - self._min_val) / span))
        hi_pct = int(round(100.0 * (hi - self._min_val) / span))
        lo_pct = max(0, min(100, lo_pct))
        hi_pct = max(0, min(100, hi_pct))

        self._commit_timer.stop()
        self.min_slider.blockSignals(True)
        self.max_slider.blockSignals(True)
        self.min_slider.setValue(lo_pct)
        self.max_slider.setValue(hi_pct)
        self.min_slider.blockSignals(False)
        self.max_slider.blockSignals(False)
        self._update_value_label()


class PropertiesPanel(QWidget):
    """Right-side properties panel with complete feature set."""

    # Signals
    filters_changed = pyqtSignal(dict)
    point_excluded = pyqtSignal(str)  # point_id
    point_included = pyqtSignal(str)  # point_id

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        metrics = build_screen_metrics(parent)
        self.main_window = main_window
        self.setObjectName("propertiesPanel")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setMinimumWidth(metrics.properties_width)
        self.setMaximumWidth(metrics.properties_width)

        self._setup_ui()

    def _setup_ui(self):
        metrics = build_screen_metrics(self)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # TITLE - gradient from BG_ELEVATED to BG_SURFACE, no bottom border
        title_widget = QWidget()
        title_widget.setFixedHeight(metrics.title_header_height)
        title_widget.setStyleSheet(f"""
            background-color: {Colors.BG_ELEVATED};
            border-bottom: 1px solid {Colors.BORDER_DEFAULT};
        """)
        title_layout = QVBoxLayout(title_widget)
        title_layout.setContentsMargins(14 if metrics.compact else 16, 8 if metrics.compact else 10, 14 if metrics.compact else 16, 8 if metrics.compact else 10)
        title_layout.setSpacing(2)

        # Main title: 15px, weight 700, TEXT_PRIMARY
        title_label = QLabel("Properties")
        title_label.setStyleSheet(f"""
            color: {Colors.TEXT_PRIMARY};
            font-size: {metrics.font_title}px;
            font-weight: 700;
            background-color: transparent;
        """)
        title_layout.addWidget(title_label)

        # Subtitle: 10px, weight 500, TEXT_TERTIARY
        subtitle_label = QLabel("Dataset Configuration")
        subtitle_label.setStyleSheet(f"""
            color: {Colors.TEXT_TERTIARY};
            font-size: {metrics.font_sm}px;
            font-weight: 500;
            background-color: transparent;
        """)
        title_layout.addWidget(subtitle_label)

        main_layout.addWidget(title_widget)

        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setFrameShape(QFrame.NoFrame)

        scroll_content = QWidget()
        self.content_layout = QVBoxLayout(scroll_content)
        self.content_layout.setContentsMargins(10 if metrics.compact else 12, 10 if metrics.compact else 12, 10 if metrics.compact else 12, 10 if metrics.compact else 12)
        self.content_layout.setSpacing(10 if metrics.compact else 12)

        # Create all sections
        self._create_filters_section()
        self._create_point_selection_section()
        # Rejected triangles section moved to Statistics view
        self._create_about_section()

        self.content_layout.addStretch()

        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)

    def _create_filters_section(self):
        """Data filters with range sliders."""
        section = CardSection("Data Filters", icon_name=Icons.FILTER, icon_color=Colors.ACCENT_PRIMARY)

        # Depth range slider
        self.depth_filter_card = QFrame()
        self.depth_filter_card.setObjectName("depthFilterCard")
        self.depth_filter_card.setStyleSheet(f"""
            QFrame#depthFilterCard {{
                background-color: transparent;
                border: none;
            }}
        """)
        depth_card_layout = QVBoxLayout(self.depth_filter_card)
        depth_card_layout.setContentsMargins(0, 0, 0, 0)
        depth_card_layout.setSpacing(6)

        self.depth_range = RangeSliderWidget("Depth Range (m)")
        self.depth_range.value_committed.connect(self._on_filters_changed)
        depth_card_layout.addWidget(self.depth_range)
        self.depth_mode_hint = QLabel("Depth source: Not configured")
        self.depth_mode_hint.setWordWrap(True)
        self.depth_mode_hint.setStyleSheet(f"""
            color: {Colors.TEXT_TERTIARY};
            font-size: 10px;
            font-style: italic;
            background-color: {Colors.BG_SURFACE};
            padding: 6px 8px;
            border-radius: 4px;
            border: 1px solid {Colors.BORDER_SUBTLE};
        """)
        depth_card_layout.addWidget(self.depth_mode_hint)
        section.addWidget(self.depth_filter_card)
        from PyQt5.QtWidgets import QGraphicsOpacityEffect
        self._depth_card_opacity = QGraphicsOpacityEffect(self.depth_filter_card)
        self.depth_filter_card.setGraphicsEffect(self._depth_card_opacity)
        self.depth_filter_card.setEnabled(False)
        self._depth_card_opacity.setOpacity(0.45)
        self.depth_mode_hint.setText("Depth source: No dataset loaded")

        # Hydraulic head range slider
        self.head_range = RangeSliderWidget("Hydraulic Head (m)")
        self.head_range.value_committed.connect(self._on_filters_changed)
        section.addWidget(self.head_range)

        self.content_layout.addWidget(section)

    def apply_theme(self):
        metrics = build_screen_metrics(self)
        self.setMinimumWidth(metrics.properties_width)
        self.setMaximumWidth(metrics.properties_width)
        reset_widget_layout(self)
        self._setup_ui()
        self.update_from_main_window()

    def _create_point_selection_section(self):
        """Point selection/exclusion controls."""
        section = CardSection("Point Selection", icon_name="fa6s.hand-pointer", icon_color=Colors.WARNING)

        # Select Points button - softer 1px border, BORDER_MEDIUM
        select_points_btn = QPushButton("Select Points to Exclude")
        select_points_btn.setStyleSheet(f"""
            QPushButton {{
                font-size: 11px;
                font-weight: 600;
                padding: 6px 12px;
                background-color: {Colors.BG_SURFACE};
                border: 1px solid {Colors.BORDER_MEDIUM};
                border-radius: 4px;
                color: {Colors.TEXT_PRIMARY};
            }}
            QPushButton:hover {{
                border-color: {Colors.BORDER_ACCENT};
                color: {Colors.ACCENT_PRIMARY};
                background-color: {Colors.ACCENT_GHOST};
            }}
            QPushButton:pressed {{
                background-color: {Colors.ACCENT_PRESSED};
                border-color: {Colors.ACCENT_PRESSED};
                color: {Colors.TEXT_PRIMARY};
            }}
        """)
        select_points_btn.clicked.connect(self._open_point_selection_dialog)
        section.addWidget(select_points_btn)

        info_label = QLabel("Or click points on the plot to exclude / include")
        info_label.setWordWrap(True)
        info_label.setStyleSheet(f"""
            color: {Colors.TEXT_MUTED};
            font-size: 9px;
            font-style: italic;
            background-color: transparent;
        """)
        section.addWidget(info_label)

        list_label = QLabel("Excluded Points")
        list_label.setStyleSheet(
            f"color: {Colors.TEXT_TERTIARY}; font-size: 9px; font-weight: 700; letter-spacing: 0.5px;"
        )
        section.addWidget(list_label)

        self.excluded_points_list = QListWidget()
        self.excluded_points_list.setMaximumHeight(100)
        self.excluded_points_list.setStyleSheet(f"""
            QListWidget {{
                background-color: {Colors.BG_SURFACE};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 4px;
                font-size: 10px;
            }}
            QListWidget::item {{
                padding: 4px;
                border-bottom: 1px solid {Colors.BORDER_SUBTLE};
            }}
            QListWidget::item:selected {{
                background-color: {Colors.ACCENT_PRIMARY};
            }}
        """)
        section.addWidget(self.excluded_points_list)

        # Action buttons - softer 1px borders, BORDER_MEDIUM
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(6)

        clear_btn = QPushButton("Clear All")
        clear_btn.setStyleSheet(f"""
            QPushButton {{
                font-size: 10px;
                padding: 4px 8px;
                background-color: {Colors.BG_SURFACE};
                border: 1px solid {Colors.BORDER_MEDIUM};
                border-radius: 3px;
            }}
            QPushButton:hover {{
                border-color: {Colors.ERROR};
                color: {Colors.ERROR};
                background-color: {Colors.ERROR_BG};
            }}
        """)
        clear_btn.clicked.connect(self._clear_excluded_points)
        btn_layout.addWidget(clear_btn)

        restore_btn = QPushButton("Restore Selected")
        restore_btn.setStyleSheet(f"""
            QPushButton {{
                font-size: 10px;
                padding: 4px 8px;
                background-color: {Colors.BG_SURFACE};
                border: 1px solid {Colors.BORDER_MEDIUM};
                border-radius: 3px;
            }}
            QPushButton:hover {{
                border-color: {Colors.BORDER_ACCENT};
                color: {Colors.ACCENT_PRIMARY};
                background-color: {Colors.ACCENT_GHOST};
            }}
        """)
        restore_btn.clicked.connect(self._restore_selected_point)
        btn_layout.addWidget(restore_btn)

        section.addLayout(btn_layout)

        self.content_layout.addWidget(section)

    def _create_rejected_triangles_section(self):
        """Display rejected triangles information."""
        section = SectionHeader("Rejected Triangles")
        layout = section.contentLayout()

        # Stats display
        stats_layout = QGridLayout()
        stats_layout.setSpacing(8)

        # Total triangles
        stats_layout.addWidget(QLabel("Total:"), 0, 0)
        self.total_triangles_label = QLabel("0")
        self.total_triangles_label.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; font-weight: 600;")
        stats_layout.addWidget(self.total_triangles_label, 0, 1)

        # Rejected count
        stats_layout.addWidget(QLabel("Rejected:"), 1, 0)
        self.rejected_triangles_label = QLabel("0")
        self.rejected_triangles_label.setStyleSheet(f"color: {Colors.ERROR}; font-weight: 600;")
        stats_layout.addWidget(self.rejected_triangles_label, 1, 1)

        # Accepted count
        stats_layout.addWidget(QLabel("Accepted:"), 2, 0)
        self.accepted_triangles_label = QLabel("0")
        self.accepted_triangles_label.setStyleSheet(f"color: {Colors.SUCCESS}; font-weight: 600;")
        stats_layout.addWidget(self.accepted_triangles_label, 2, 1)

        for i in range(3):
            label = stats_layout.itemAtPosition(i, 0).widget()
            label.setStyleSheet(f"color: {Colors.TEXT_TERTIARY}; font-size: 10px;")

        layout.addLayout(stats_layout)

        # Show/hide rejected checkbox
        self.show_rejected_checkbox = QCheckBox("Show Rejected on Plot")
        self.show_rejected_checkbox.setStyleSheet(f"""
            QCheckBox {{
                color: {Colors.TEXT_SECONDARY};
                font-size: 10px;
                font-weight: 500;
                spacing: 8px;
                padding: 4px 0;
                background: transparent;
            }}
            QCheckBox:hover {{
                color: {Colors.TEXT_PRIMARY};
            }}
            QCheckBox::indicator {{
                width: 14px;
                height: 14px;
                border: 1.5px solid {Colors.BORDER_MEDIUM};
                border-radius: 4px;
                background: {Colors.BG_SURFACE};
            }}
            QCheckBox::indicator:hover {{
                border-color: {Colors.ACCENT_PRIMARY};
                background: {Colors.BG_HOVER};
            }}
            QCheckBox::indicator:checked {{
                background: {Colors.ACCENT_PRIMARY};
                border-color: {Colors.ACCENT_PRIMARY};
                image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTIiIGhlaWdodD0iMTIiIHZpZXdCb3g9IjAgMCAxMiAxMiIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZD0iTTEwIDNMNC41IDguNUwyIDYiIHN0cm9rZT0id2hpdGUiIHN0cm9rZS13aWR0aD0iMiIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIi8+Cjwvc3ZnPgo=);
            }}
            QCheckBox::indicator:checked:hover {{
                background: {Colors.ACCENT_HOVER};
                border-color: {Colors.ACCENT_HOVER};
            }}
        """)
        self.show_rejected_checkbox.setChecked(False)
        layout.addWidget(self.show_rejected_checkbox)

        self.content_layout.addWidget(section)

    def _create_about_section(self):
        """DTU logo, version, author, and acknowledgements — compact identity layout."""
        import os
        section = CardSection("About", icon_name=Icons.INFO, icon_color=Colors.ACCENT_PRIMARY)

        # ── Identity row: logo square + name / version / author ──
        identity_row = QWidget()
        id_layout = QHBoxLayout(identity_row)
        id_layout.setContentsMargins(0, 2, 0, 4)
        id_layout.setSpacing(10)

        logo_label = QLabel()
        logo_label.setFixedSize(38, 38)
        logo_label.setAlignment(Qt.AlignCenter)
        logo_label.setStyleSheet(f"""
            background-color: {Colors.ACCENT_GHOST};
            border: 1px solid {Colors.BORDER_ACCENT};
            border-radius: 3px;
        """)
        logo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "DTU_logo.png")
        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path)
            logo_label.setPixmap(pixmap.scaledToHeight(30, Qt.SmoothTransformation))
        else:
            logo_label.setText("DTU")
            logo_label.setStyleSheet(f"""
                font-size: 10px; font-weight: 800; color: {Colors.ACCENT_PRIMARY};
                background-color: {Colors.ACCENT_GHOST};
                border: 1px solid {Colors.BORDER_ACCENT};
                border-radius: 3px;
            """)
        id_layout.addWidget(logo_label)

        text_col = QWidget()
        text_layout = QVBoxLayout(text_col)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(3)

        app_name = QLabel("HeadAnalyser")
        app_name.setStyleSheet(f"""
            color: {Colors.TEXT_PRIMARY};
            font-size: 13px;
            font-weight: 700;
            background: transparent;
        """)
        text_layout.addWidget(app_name)

        meta_row = QWidget()
        meta_layout = QHBoxLayout(meta_row)
        meta_layout.setContentsMargins(0, 0, 0, 0)
        meta_layout.setSpacing(6)
        version_badge = QLabel("v2.0.0")
        version_badge.setStyleSheet(f"""
            color: {Colors.ACCENT_PRIMARY};
            font-size: 9px;
            font-weight: 600;
            background-color: {Colors.ACCENT_GHOST};
            border: 1px solid {Colors.BORDER_ACCENT};
            padding: 1px 6px;
            border-radius: 3px;
        """)
        meta_layout.addWidget(version_badge)
        author_label = QLabel("Oliver B. Lund")
        author_label.setStyleSheet(
            f"color: {Colors.TEXT_TERTIARY}; font-size: 10px; background: transparent;"
        )
        meta_layout.addWidget(author_label)
        meta_layout.addStretch()
        text_layout.addWidget(meta_row)
        id_layout.addWidget(text_col)
        section.addWidget(identity_row)

        # ── Separator ──
        section.addSeparator()

        # ── Credits key→value table ──
        credits_widget = QWidget()
        credits_layout = QVBoxLayout(credits_widget)
        credits_layout.setContentsMargins(0, 4, 0, 0)
        credits_layout.setSpacing(4)

        def _cred_row(key: str, val: str) -> QWidget:
            row = QWidget()
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 0, 0, 0)
            rl.setSpacing(8)
            k = QLabel(key.upper())
            k.setFixedWidth(64)
            k.setAlignment(Qt.AlignTop)
            k.setStyleSheet(f"""
                color: {Colors.TEXT_MUTED};
                font-size: 9px;
                font-weight: 700;
                letter-spacing: 0.5px;
                background: transparent;
            """)
            rl.addWidget(k)
            v = QLabel(val)
            v.setWordWrap(True)
            v.setStyleSheet(
                f"color: {Colors.TEXT_TERTIARY}; font-size: 9px; background: transparent;"
            )
            rl.addWidget(v, 1)
            return row

        credits_layout.addWidget(_cred_row("Calcs by", "A. Bøllingtoft & G. Lemaire, DTU Sustain"))
        credits_layout.addWidget(_cred_row("Based on", "Dr. J.F. Devlin, Kansas University"))
        credits_layout.addWidget(_cred_row("Released", "February 2025"))
        section.addWidget(credits_widget)

        # ── DTU badge ──
        dtu_badge = QLabel("Technical University of Denmark")
        dtu_badge.setStyleSheet(f"""
            color: {Colors.TEXT_SECONDARY};
            font-size: 9px;
            font-weight: 600;
            background-color: rgba(153, 0, 0, 0.10);
            border: 1px solid rgba(153, 0, 0, 0.20);
            padding: 3px 8px;
            border-radius: 3px;
        """)
        section.addWidget(dtu_badge)

        self.content_layout.addWidget(section)

    def _on_filters_changed(self, *_):
        """Handle filter changes."""
        if self.depth_filter_card.isEnabled():
            depth_min, depth_max = self.depth_range.get_values()
        else:
            depth_min, depth_max = None, None
        head_min, head_max = self.head_range.get_values()

        self.filters_changed.emit({
            'depth_min': depth_min,
            'depth_max': depth_max,
            'head_min': head_min,
            'head_max': head_max
        })

    def _clear_excluded_points(self):
        """Clear all excluded points."""
        self.excluded_points_list.clear()
        self.main_window.excluded_ids.clear()
        if hasattr(self.main_window, "excluded_member_keys"):
            self.main_window.excluded_member_keys.clear()
        self.main_window.refilter_and_recalculate()

    def _restore_selected_point(self):
        """Restore selected excluded point."""
        selected_items = self.excluded_points_list.selectedItems()
        if not selected_items:
            return

        # Remove selected points from excluded set
        for item in selected_items:
            point_id_str = item.text()
            # Try to convert to the correct type (could be int or str)
            try:
                # Try parsing as int first (most common for point IDs)
                point_id = int(point_id_str)
            except ValueError:
                # Keep as string if not an int
                point_id = point_id_str

            # Remove from excluded set
            self.main_window.excluded_ids.discard(point_id)
            self.main_window.excluded_ids.discard(str(point_id))
            try:
                self.main_window.excluded_ids.discard(int(point_id))
            except Exception:
                pass
            if hasattr(self.main_window, "excluded_member_keys"):
                pstr = str(point_id)
                self.main_window.excluded_member_keys = {
                    mk for mk in set(getattr(self.main_window, "excluded_member_keys", set()) or set())
                    if not str(mk).startswith(pstr + "::")
                }

            # Remove from list widget
            self.excluded_points_list.takeItem(self.excluded_points_list.row(item))

        self.main_window.refilter_and_recalculate()

    def _open_point_selection_dialog(self):
        """Open the point selection dialog."""
        # Check if data is loaded
        if not hasattr(self.main_window, 'current_data') or self.main_window.current_data is None:
            # Show info message (could add QMessageBox here)
            return

        # Get current data and excluded IDs
        current_data = self.main_window.current_data
        excluded_ids = getattr(self.main_window, 'excluded_ids', set())

        # Create and show dialog
        dialog = PointSelectionDialog(current_data, excluded_ids, self)
        dialog.points_excluded.connect(self._on_points_excluded)
        dialog.exec_()

    def _on_points_excluded(self, excluded_ids: set):
        """Handle points exclusion from dialog."""
        # Update main window state
        self.main_window.excluded_ids = excluded_ids
        if hasattr(self.main_window, "excluded_member_keys"):
            self.main_window.excluded_member_keys = set()

        # Update excluded points list display
        self.excluded_points_list.clear()
        for point_id in sorted(excluded_ids, key=lambda x: str(x)):
            self.excluded_points_list.addItem(QListWidgetItem(str(point_id)))

        self.main_window.refilter_and_recalculate()

    def add_excluded_point(self, point_id: str):
        """Add a point to the excluded list."""
        item = QListWidgetItem(point_id)
        self.excluded_points_list.addItem(item)

    def update_triangle_stats(self, total: int, rejected: int):
        """Update rejected triangles statistics."""
        accepted = total - rejected
        self.total_triangles_label.setText(str(total))
        self.rejected_triangles_label.setText(str(rejected))
        self.accepted_triangles_label.setText(str(accepted))

    def update_filter_ranges(self, depth_range=None, head_range=None, depth_values=None, head_values=None):
        """Update filter slider ranges/values without emitting filter-change signals."""
        if depth_range:
            self.depth_range.set_range(*depth_range)
            self.depth_filter_card.setEnabled(True)
        else:
            self.depth_filter_card.setEnabled(False)
        if depth_values:
            self.depth_range.set_values(*depth_values)
        if head_range:
            self.head_range.set_range(*head_range)
        if head_values:
            self.head_range.set_values(*head_values)

    def refresh_excluded_list(self):
        """Refresh the excluded points list from main_window.excluded_ids."""
        self.excluded_points_list.clear()
        for pid in sorted(self.main_window.excluded_ids, key=lambda x: str(x)):
            self.excluded_points_list.addItem(QListWidgetItem(str(pid)))

    @staticmethod
    def _coerce_range_tuple(value):
        if not isinstance(value, (tuple, list)) or len(value) != 2:
            return None
        try:
            lo = float(value[0])
            hi = float(value[1])
        except Exception:
            return None
        if not (np.isfinite(lo) and np.isfinite(hi)):
            return None
        if hi < lo:
            lo, hi = hi, lo
        return (lo, hi)

    def _infer_depth_bounds(self, dataset):
        data = getattr(dataset, "data", None)
        if data is None or getattr(data, "empty", True):
            return None
        top_col = getattr(dataset, "top_column", None)
        bottom_col = getattr(dataset, "bottom_column", None)
        depth_col = getattr(dataset, "depth_column", None)
        cols = set(data.columns)
        top_ok = bool(top_col and top_col in cols)
        bottom_ok = bool(bottom_col and bottom_col in cols)
        depth_ok = bool(depth_col and depth_col in cols)
        try:
            if top_ok and bottom_ok:
                top_vals = pd.to_numeric(data[top_col], errors="coerce").to_numpy(dtype=float)
                bot_vals = pd.to_numeric(data[bottom_col], errors="coerce").to_numpy(dtype=float)
                if not (np.isfinite(top_vals).any() or np.isfinite(bot_vals).any()):
                    return None
                dmin = float(np.nanmin([np.nanmin(top_vals), np.nanmin(bot_vals)]))
                dmax = float(np.nanmax([np.nanmax(top_vals), np.nanmax(bot_vals)]))
            elif top_ok:
                vals = pd.to_numeric(data[top_col], errors="coerce").to_numpy(dtype=float)
                if not np.isfinite(vals).any():
                    return None
                dmin = float(np.nanmin(vals))
                dmax = float(np.nanmax(vals))
            elif bottom_ok:
                vals = pd.to_numeric(data[bottom_col], errors="coerce").to_numpy(dtype=float)
                if not np.isfinite(vals).any():
                    return None
                dmin = float(np.nanmin(vals))
                dmax = float(np.nanmax(vals))
            elif depth_ok:
                vals = pd.to_numeric(data[depth_col], errors="coerce").to_numpy(dtype=float)
                if not np.isfinite(vals).any():
                    return None
                dmin = float(np.nanmin(vals))
                dmax = float(np.nanmax(vals))
            else:
                return None
        except Exception:
            return None
        if not (np.isfinite(dmin) and np.isfinite(dmax)):
            return None
        if dmax < dmin:
            dmin, dmax = dmax, dmin
        return (dmin, dmax)

    def _infer_depth_mode(self, dataset):
        """Return a mode key + human-readable depth source description."""
        data = getattr(dataset, "data", None)
        if data is None or getattr(data, "empty", True):
            return "none", "Depth source: No dataset loaded"

        top_col = getattr(dataset, "top_column", None)
        bottom_col = getattr(dataset, "bottom_column", None)
        depth_col = getattr(dataset, "depth_column", None)
        cols = set(data.columns)
        top_ok = bool(top_col and top_col in cols)
        bottom_ok = bool(bottom_col and bottom_col in cols)
        depth_ok = bool(depth_col and depth_col in cols)

        if top_ok and bottom_ok:
            return "top_bottom", f"Depth source: Top+Bottom ({top_col}, {bottom_col})"
        if top_ok:
            return "top_only", f"Depth source: Top only ({top_col})"
        if bottom_ok:
            return "bottom_only", f"Depth source: Bottom only ({bottom_col})"
        if depth_ok:
            return "single", f"Depth source: Single depth ({depth_col})"
        return "none", "Depth source: No depth columns selected"

    def _apply_depth_mode_hint(self, mode_key: str, mode_text: str):
        self.depth_mode_hint.setText(mode_text)
        if mode_key == "none":
            self.depth_mode_hint.setStyleSheet(f"""
                color: {Colors.WARNING};
                font-size: 10px;
                font-style: italic;
                background-color: {Colors.BG_SURFACE};
                padding: 6px 8px;
                border-radius: 4px;
                border: 1px solid rgba(251, 191, 36, 0.35);
            """)
            self.depth_filter_card.setEnabled(False)
            if hasattr(self, "_depth_card_opacity") and self._depth_card_opacity is not None:
                self._depth_card_opacity.setOpacity(0.45)
        else:
            self.depth_mode_hint.setStyleSheet(f"""
                color: {Colors.TEXT_TERTIARY};
                font-size: 10px;
                font-style: italic;
                background-color: {Colors.BG_SURFACE};
                padding: 6px 8px;
                border-radius: 4px;
                border: 1px solid {Colors.BORDER_SUBTLE};
            """)
            self.depth_filter_card.setEnabled(True)
            if hasattr(self, "_depth_card_opacity") and self._depth_card_opacity is not None:
                self._depth_card_opacity.setOpacity(1.0)

    def _infer_head_bounds(self, dataset):
        data = getattr(dataset, "data", None)
        if data is None or getattr(data, "empty", True):
            return None
        col_map = getattr(dataset, "col_mapping", {}) or {}
        h_col = col_map.get("hydraulic head")
        if not h_col or h_col not in data.columns:
            return None
        try:
            hmin = float(data[h_col].min())
            hmax = float(data[h_col].max())
        except Exception:
            return None
        if not (np.isfinite(hmin) and np.isfinite(hmax)):
            return None
        if hmax < hmin:
            hmin, hmax = hmax, hmin
        return (hmin, hmax)

    def update_from_main_window(self):
        """Update properties panel to reflect active dataset's settings."""
        self.refresh_excluded_list()
        dataset = self.main_window.get_active_dataset() if hasattr(self.main_window, "get_active_dataset") else None
        if dataset is None:
            self._apply_depth_mode_hint("none", "Depth source: No dataset loaded")
            return

        depth_bounds = self._coerce_range_tuple(getattr(dataset, "depth_bounds", None))
        head_bounds = self._coerce_range_tuple(getattr(dataset, "head_bounds", None))
        if depth_bounds is None:
            depth_bounds = self._infer_depth_bounds(dataset)
        if head_bounds is None:
            head_bounds = self._infer_head_bounds(dataset)

        depth_values = self._coerce_range_tuple(getattr(dataset, "depth_range", None))
        head_values = self._coerce_range_tuple(getattr(dataset, "head_range", None))

        if depth_bounds is None:
            depth_values = None
        if head_bounds is None:
            head_values = None
        if depth_bounds is not None and depth_values is None:
            depth_values = depth_bounds
        if head_bounds is not None and head_values is None:
            head_values = head_bounds

        self.update_filter_ranges(
            depth_range=depth_bounds,
            head_range=head_bounds,
            depth_values=depth_values,
            head_values=head_values,
        )
        mode_key, mode_text = self._infer_depth_mode(dataset)
        self._apply_depth_mode_hint(mode_key, mode_text)
