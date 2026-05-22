"""
HeadAnalyser V2 - Plot Sidebar
Collapsible sidebar with plot visualization controls and plot-type-specific options.
"""

from PyQt5.QtWidgets import (
    QFrame, QVBoxLayout, QLabel, QWidget, QStackedWidget, QScrollArea,
    QComboBox, QSlider, QSpinBox, QCheckBox, QHBoxLayout, QToolButton,
    QLineEdit, QMessageBox
)
from PyQt5.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve, QSize
from PyQt5.QtGui import QIcon, QPixmap, QImage

from .common_widgets import ToggleSwitch, CollapsibleSection, SectionHeader, CardSection, ToggleRow, SubOptionsContainer


class PlaceholderToggleRow(ToggleRow):
    """A ToggleRow that shows a placeholder message when toggled."""

    def __init__(self, label: str, feature_name: str, icon_name: str = None, is_sub: bool = False, parent=None):
        super().__init__(label, icon_name=icon_name, is_sub=is_sub, parent=parent)
        self._feature_name = feature_name
        self._placeholder_style()
        # Override toggle behavior
        self._toggle.setEnabled(False)
        self._toggle.setToolTip(f"Coming soon: {feature_name}")

    def _placeholder_style(self):
        """Apply muted styling to indicate placeholder status."""
        self.setStyleSheet(self.styleSheet() + f"""
            QWidget {{
                opacity: 0.6;
            }}
        """)
        # Add "(Planned)" suffix to label
        self._label.setText(self._label.text() + " (Planned)")
        self._label.setStyleSheet(f"""
            color: {Colors.TEXT_MUTED};
            font-size: {build_screen_metrics(self).font_md}px;
            font-weight: 500;
            font-style: italic;
            background: transparent;
        """)


class PlaceholderComboBox(QComboBox):
    """A ComboBox that shows a placeholder message when interacted with."""

    def __init__(self, feature_name: str, items: list = None, parent=None):
        super().__init__(parent)
        self._feature_name = feature_name
        if items:
            self.addItems(items)
        self.setEnabled(False)
        self.setToolTip(f"Coming soon: {feature_name}")


class PlaceholderCheckBox(QCheckBox):
    """A CheckBox that shows a placeholder message when toggled."""

    def __init__(self, label: str, feature_name: str, parent=None):
        super().__init__(label + " (Planned)", parent)
        self._feature_name = feature_name
        self.setEnabled(False)
        self.setToolTip(f"Coming soon: {feature_name}")
from .plot_types import normalize_plot_type
from .icons import Icons, icon
from styles.colors import Colors
from styles.stylesheet import StyleSheet
from ui.scaling import build_screen_metrics
from .theme_utils import reset_widget_layout


class PlotSidebar(QFrame):
    """Collapsible sidebar with plot controls."""

    # Signals
    visualization_changed = pyqtSignal(dict)
    plot_options_changed = pyqtSignal(dict)

    def __init__(self, plot_page_ref=None, parent=None):
        super().__init__(parent)
        metrics = build_screen_metrics(parent)
        self.plot_page_ref = plot_page_ref  # Reference to PlotPage for toolbar access
        self.setObjectName("plotSidebar")
        self.setMinimumWidth(metrics.plot_sidebar_width)
        self.setMaximumWidth(metrics.plot_sidebar_width)
        self.setStyleSheet(f"""
            QWidget#plotSidebar {{
                background-color: {Colors.BG_PANEL};
                border-right: 1px solid {Colors.BORDER_DEFAULT};
            }}
        """)

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        """Setup the sidebar UI."""
        metrics = build_screen_metrics(self)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── Title header ──
        title_widget = QWidget()
        title_widget.setFixedHeight(metrics.title_header_height)
        title_widget.setStyleSheet(f"""
            background-color: {Colors.BG_ELEVATED};
            border-bottom: 1px solid {Colors.BORDER_DEFAULT};
        """)
        title_layout = QVBoxLayout(title_widget)
        title_layout.setContentsMargins(14 if metrics.compact else 16, 8 if metrics.compact else 10, 14 if metrics.compact else 16, 8 if metrics.compact else 10)
        title_layout.setSpacing(2)

        title_label = QLabel("Plot Controls")
        title_label.setStyleSheet(f"""
            color: {Colors.TEXT_PRIMARY};
            font-size: {metrics.font_title}px;
            font-weight: 700;
            background-color: transparent;
        """)
        title_layout.addWidget(title_label)

        subtitle_label = QLabel("Visualization & Options")
        subtitle_label.setStyleSheet(f"""
            color: {Colors.TEXT_TERTIARY};
            font-size: {metrics.font_sm}px;
            font-weight: 500;
            background-color: transparent;
        """)
        title_layout.addWidget(subtitle_label)

        main_layout.addWidget(title_widget)

        # ── Scroll area ──
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet(f"""
            QScrollArea {{ background: transparent; border: none; }}
            QScrollBar:vertical {{
                background: transparent;
                width: 5px;
                margin: 0;
            }}
            QScrollBar::handle:vertical {{
                background: {Colors.BORDER_STRONG};
                border-radius: 2px;
                min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {Colors.TEXT_MUTED};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
        """)

        # Content widget
        content_widget = QWidget()
        content_widget.setStyleSheet("QWidget { background-color: transparent; }")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(8 if metrics.compact else 10, 6 if metrics.compact else 8, 8 if metrics.compact else 10, 6 if metrics.compact else 8)
        content_layout.setSpacing(3 if metrics.compact else 4)

        # ── VISUALIZATION section (card style) ──
        viz_section = CardSection("Visualization", icon_name=Icons.EYE, icon_color=Colors.ACCENT_PRIMARY)

        # Contours toggle with sub-option
        self.toggle_contours = ToggleRow("Contours", icon_name="fa6s.circle-nodes")
        viz_section.addWidget(self.toggle_contours)

        # Sub-options container for Fill Contours
        self._contour_suboptions = SubOptionsContainer()
        self.toggle_fill_contours = ToggleRow("Fill Contours", icon_name="fa6s.fill", is_sub=True)
        self._contour_suboptions.addWidget(self.toggle_fill_contours)
        viz_section.addWidget(self._contour_suboptions)
        self.toggle_contours.setSubOptionsWidget(self._contour_suboptions)

        # Other visualization toggles
        self.toggle_arrows = ToggleRow("Gradient Arrows", icon_name="fa6s.arrows-up-down")
        viz_section.addWidget(self.toggle_arrows)

        self.toggle_arrow_label = ToggleRow("Arrow Label", icon_name="fa6s.tag")
        self.toggle_arrow_label.setChecked(True)
        viz_section.addWidget(self.toggle_arrow_label)

        self.toggle_points = ToggleRow("Data Points", icon_name="fa6s.circle")
        self.toggle_points.setChecked(True)  # Default ON
        viz_section.addWidget(self.toggle_points)

        self.toggle_labels = ToggleRow("Labels", icon_name="fa6s.tag")
        self.toggle_labels.setChecked(True)  # Default ON
        viz_section.addWidget(self.toggle_labels)

        self.toggle_colorbar = ToggleRow("Colorbar", icon_name="fa6s.palette")
        self.toggle_colorbar.setChecked(True)  # Default ON
        viz_section.addWidget(self.toggle_colorbar)

        content_layout.addWidget(viz_section)

        # ── PLOT OPTIONS section (card style) ──
        opts_section = CardSection("Plot Options", icon_name=Icons.SLIDERS, icon_color=Colors.WARNING)

        # Stacked widget for plot-type-specific controls
        self.options_stack = QStackedWidget()
        self.options_stack.setStyleSheet("background-color: transparent;")

        # ── 2D options (index 0) ──
        self.options_2d = QWidget()
        self.options_2d_layout = QVBoxLayout(self.options_2d)
        self.options_2d_layout.setContentsMargins(0, 0, 0, 0)
        self.options_2d_layout.setSpacing(3)

        colormap_label = QLabel("Colormap:")
        colormap_label.setStyleSheet(self._get_option_label_style())
        self.colormap_2d_combo = self._create_colormap_combo(
            ['viridis', 'plasma', 'turbo', 'coolwarm', 'RdYlBu', 'YlOrRd', 'Blues', 'Greys'])
        self.options_2d_layout.addWidget(colormap_label)
        self.options_2d_layout.addWidget(self.colormap_2d_combo)

        point_size_label = QLabel("Point Size:")
        point_size_label.setStyleSheet(self._get_option_label_style())
        self.point_size_slider = QSlider(Qt.Horizontal)
        self.point_size_slider.setRange(20, 200)
        self.point_size_slider.setValue(80)
        self.point_size_slider.setStyleSheet(StyleSheet.get_range_slider_style())
        self.point_size_value_label = QLabel("80")
        self.point_size_value_label.setStyleSheet(self._get_value_label_style())
        point_size_row = QHBoxLayout()
        point_size_row.addWidget(self.point_size_slider)
        point_size_row.addWidget(self.point_size_value_label)
        self.options_2d_layout.addWidget(point_size_label)
        self.options_2d_layout.addLayout(point_size_row)

        label_mode_label = QLabel("Label Mode:")
        label_mode_label.setStyleSheet(self._get_option_label_style())
        self.label_mode_2d_combo = QComboBox()
        self.label_mode_2d_combo.addItems(["All", "Smart", "Off", "Pinned"])
        self.label_mode_2d_combo.setCurrentText("All")
        self.label_mode_2d_combo.setStyleSheet(self._get_option_widget_style())
        self.options_2d_layout.addWidget(label_mode_label)
        self.options_2d_layout.addWidget(self.label_mode_2d_combo)

        # Contour options (merged into 2D)
        levels_label = QLabel("Contour Levels:")
        levels_label.setStyleSheet(self._get_option_label_style())
        self.contour_levels_spinbox = QSpinBox()
        self.contour_levels_spinbox.setRange(5, 50)
        self.contour_levels_spinbox.setValue(10)
        self.contour_levels_spinbox.setStyleSheet(self._get_option_widget_style())
        self.options_2d_layout.addWidget(levels_label)
        self.options_2d_layout.addWidget(self.contour_levels_spinbox)

        # ── Planned Features (2D) ──
        planned_header = QLabel("PLANNED FEATURES")
        planned_header.setStyleSheet(f"""
            color: {Colors.TEXT_MUTED};
            font-size: 9px;
            font-weight: 700;
            letter-spacing: 0.5px;
            padding: 6px 0 3px 0;
            border-top: 1px solid {Colors.BORDER_SUBTLE};
            margin-top: 4px;
        """)
        self.options_2d_layout.addWidget(planned_header)

        # Stacked Points Mode (Planned)
        stacked_mode_label = QLabel("Stacked Points Mode:")
        stacked_mode_label.setStyleSheet(self._get_placeholder_label_style())
        self.stacked_mode_combo = PlaceholderComboBox(
            "Stacked Points Mode",
            ["Collapse", "Exclude", "Depth Band", "Choose Intake"]
        )
        self.stacked_mode_combo.setStyleSheet(self._get_option_widget_style())
        self.options_2d_layout.addWidget(stacked_mode_label)
        self.options_2d_layout.addWidget(self.stacked_mode_combo)

        self.options_2d_layout.addStretch()

        # ── 3D options (index 1) ──
        self.options_3d = QWidget()
        self.options_3d_layout = QVBoxLayout(self.options_3d)
        self.options_3d_layout.setContentsMargins(0, 0, 0, 0)
        self.options_3d_layout.setSpacing(3)

        elev_label = QLabel("Elevation:")
        elev_label.setStyleSheet(self._get_option_label_style())
        self.elev_slider = QSlider(Qt.Horizontal)
        self.elev_slider.setRange(0, 90)
        self.elev_slider.setValue(30)
        self.elev_slider.setStyleSheet(StyleSheet.get_range_slider_style())
        self.elev_value_label = QLabel("30\u00b0")
        self.elev_value_label.setStyleSheet(self._get_value_label_style())
        elev_row = QHBoxLayout()
        elev_row.addWidget(self.elev_slider)
        elev_row.addWidget(self.elev_value_label)
        self.options_3d_layout.addWidget(elev_label)
        self.options_3d_layout.addLayout(elev_row)

        azim_label = QLabel("Azimuth:")
        azim_label.setStyleSheet(self._get_option_label_style())
        self.azim_slider = QSlider(Qt.Horizontal)
        self.azim_slider.setRange(0, 360)
        self.azim_slider.setValue(45)
        self.azim_slider.setStyleSheet(StyleSheet.get_range_slider_style())
        self.azim_value_label = QLabel("45\u00b0")
        self.azim_value_label.setStyleSheet(self._get_value_label_style())
        azim_row = QHBoxLayout()
        azim_row.addWidget(self.azim_slider)
        azim_row.addWidget(self.azim_value_label)
        self.options_3d_layout.addWidget(azim_label)
        self.options_3d_layout.addLayout(azim_row)

        colormap_3d_label = QLabel("Colormap:")
        colormap_3d_label.setStyleSheet(self._get_option_label_style())
        self.colormap_3d_combo = self._create_colormap_combo(
            ['viridis', 'plasma', 'turbo', 'coolwarm', 'RdYlBu', 'YlOrRd', 'Blues', 'Greys'])
        self.options_3d_layout.addWidget(colormap_3d_label)
        self.options_3d_layout.addWidget(self.colormap_3d_combo)

        # Surface opacity slider
        opacity_label = QLabel("Surface Opacity:")
        opacity_label.setStyleSheet(self._get_option_label_style())
        self.surface_opacity_slider = QSlider(Qt.Horizontal)
        self.surface_opacity_slider.setRange(10, 100)
        self.surface_opacity_slider.setValue(80)
        self.surface_opacity_slider.setStyleSheet(StyleSheet.get_range_slider_style())
        self.surface_opacity_value_label = QLabel("80%")
        self.surface_opacity_value_label.setStyleSheet(self._get_value_label_style())
        opacity_row = QHBoxLayout()
        opacity_row.addWidget(self.surface_opacity_slider)
        opacity_row.addWidget(self.surface_opacity_value_label)
        self.options_3d_layout.addWidget(opacity_label)
        self.options_3d_layout.addLayout(opacity_row)

        # Wireframe toggle (moved from Settings)
        self.wireframe_checkbox = QCheckBox("Wireframe Overlay")
        self.wireframe_checkbox.setChecked(False)
        self.wireframe_checkbox.setStyleSheet(self._get_checkbox_style())
        self.options_3d_layout.addWidget(self.wireframe_checkbox)

        # ── Planned Features (3D) ──
        planned_header_3d = QLabel("PLANNED FEATURES")
        planned_header_3d.setStyleSheet(f"""
            color: {Colors.TEXT_MUTED};
            font-size: 9px;
            font-weight: 700;
            letter-spacing: 0.5px;
            padding: 6px 0 3px 0;
            border-top: 1px solid {Colors.BORDER_SUBTLE};
            margin-top: 4px;
        """)
        self.options_3d_layout.addWidget(planned_header_3d)

        # Z Exaggeration (Planned)
        z_exag_label = QLabel("Z Exaggeration:")
        z_exag_label.setStyleSheet(self._get_placeholder_label_style())
        self.z_exag_slider = QSlider(Qt.Horizontal)
        self.z_exag_slider.setRange(1, 50)
        self.z_exag_slider.setValue(10)
        self.z_exag_slider.setEnabled(False)
        self.z_exag_slider.setToolTip("Coming soon: Z Exaggeration for vertical scale emphasis")
        self.z_exag_slider.setStyleSheet(StyleSheet.get_range_slider_style())
        self.options_3d_layout.addWidget(z_exag_label)
        self.options_3d_layout.addWidget(self.z_exag_slider)

        # Base-plane Contours (Planned)
        self.baseplane_contours_checkbox = PlaceholderCheckBox(
            "Base-plane Contours", "Base-plane Contours")
        self.baseplane_contours_checkbox.setStyleSheet(self._get_checkbox_style())
        self.options_3d_layout.addWidget(self.baseplane_contours_checkbox)

        # Lighting (Planned)
        self.lighting_checkbox = PlaceholderCheckBox("Lighting Effect", "Lighting Effect")
        self.lighting_checkbox.setStyleSheet(self._get_checkbox_style())
        self.options_3d_layout.addWidget(self.lighting_checkbox)

        self.options_3d_layout.addStretch()

        # ── Vectors options (index 2) ──
        self.options_vectors = QWidget()
        self.options_vectors_layout = QVBoxLayout(self.options_vectors)
        self.options_vectors_layout.setContentsMargins(0, 0, 0, 0)
        self.options_vectors_layout.setSpacing(3)

        scale_label = QLabel("Arrow Scale:")
        scale_label.setStyleSheet(self._get_option_label_style())
        self.vector_scale_slider = QSlider(Qt.Horizontal)
        self.vector_scale_slider.setRange(1, 100)
        self.vector_scale_slider.setValue(5)
        self.vector_scale_slider.setStyleSheet(StyleSheet.get_range_slider_style())
        self.vector_scale_value_label = QLabel("5")
        self.vector_scale_value_label.setStyleSheet(self._get_value_label_style())
        scale_row = QHBoxLayout()
        scale_row.addWidget(self.vector_scale_slider)
        scale_row.addWidget(self.vector_scale_value_label)
        self.options_vectors_layout.addWidget(scale_label)
        self.options_vectors_layout.addLayout(scale_row)

        alpha_label = QLabel("Alpha:")
        alpha_label.setStyleSheet(self._get_option_label_style())
        self.vector_alpha_slider = QSlider(Qt.Horizontal)
        self.vector_alpha_slider.setRange(0, 100)
        self.vector_alpha_slider.setValue(80)
        self.vector_alpha_slider.setStyleSheet(StyleSheet.get_range_slider_style())
        self.vector_alpha_value_label = QLabel("0.80")
        self.vector_alpha_value_label.setStyleSheet(self._get_value_label_style())
        alpha_row = QHBoxLayout()
        alpha_row.addWidget(self.vector_alpha_slider)
        alpha_row.addWidget(self.vector_alpha_value_label)
        self.options_vectors_layout.addWidget(alpha_label)
        self.options_vectors_layout.addLayout(alpha_row)

        colormap_vectors_label = QLabel("Colormap:")
        colormap_vectors_label.setStyleSheet(self._get_option_label_style())
        self.colormap_vectors_combo = self._create_colormap_combo(
            ['viridis', 'plasma', 'turbo', 'coolwarm', 'RdYlBu', 'YlOrRd', 'Blues', 'Greys'])
        self.options_vectors_layout.addWidget(colormap_vectors_label)
        self.options_vectors_layout.addWidget(self.colormap_vectors_combo)

        # Mean Vector overlay (active)
        self.mean_vector_checkbox = QCheckBox("Show Mean Vector")
        self.mean_vector_checkbox.setChecked(True)
        self.mean_vector_checkbox.setStyleSheet(self._get_checkbox_style())
        self.options_vectors_layout.addWidget(self.mean_vector_checkbox)

        # ── Planned Features (Vectors) ──
        planned_header_vec = QLabel("PLANNED FEATURES")
        planned_header_vec.setStyleSheet(f"""
            color: {Colors.TEXT_MUTED};
            font-size: 9px;
            font-weight: 700;
            letter-spacing: 0.5px;
            padding: 6px 0 3px 0;
            border-top: 1px solid {Colors.BORDER_SUBTLE};
            margin-top: 4px;
        """)
        self.options_vectors_layout.addWidget(planned_header_vec)

        # Normalize Vectors (active)
        self.normalize_vectors_checkbox = QCheckBox("Normalize Vectors")
        self.normalize_vectors_checkbox.setChecked(False)
        self.normalize_vectors_checkbox.setToolTip("All arrows same length — shows direction field only")
        self.normalize_vectors_checkbox.setStyleSheet(self._get_checkbox_style())
        self.options_vectors_layout.addWidget(self.normalize_vectors_checkbox)

        # Show Rejected (Planned)
        self.show_rejected_checkbox = PlaceholderCheckBox(
            "Show Rejected Vectors", "Rejected Vectors Display")
        self.show_rejected_checkbox.setStyleSheet(self._get_checkbox_style())
        self.options_vectors_layout.addWidget(self.show_rejected_checkbox)

        # Background Points (Planned)
        self.background_points_checkbox = PlaceholderCheckBox(
            "Background Points", "Background Point Layer")
        self.background_points_checkbox.setStyleSheet(self._get_checkbox_style())
        self.options_vectors_layout.addWidget(self.background_points_checkbox)

        self.options_vectors_layout.addStretch()

        # ── Histogram options (index 3) ──
        self.options_histogram = QWidget()
        self.options_histogram_layout = QVBoxLayout(self.options_histogram)
        self.options_histogram_layout.setContentsMargins(0, 0, 0, 0)
        self.options_histogram_layout.setSpacing(3)

        bins_label = QLabel("Number of Bins:")
        bins_label.setStyleSheet(self._get_option_label_style())
        self.bins_spinbox = QSpinBox()
        self.bins_spinbox.setRange(5, 100)
        self.bins_spinbox.setValue(30)
        self.bins_spinbox.setStyleSheet(self._get_option_widget_style())
        self.options_histogram_layout.addWidget(bins_label)
        self.options_histogram_layout.addWidget(self.bins_spinbox)

        bar_color_label = QLabel("Bar Color:")
        bar_color_label.setStyleSheet(self._get_option_label_style())
        self.bar_color_combo = QComboBox()
        self.bar_color_combo.addItems(['grey', 'blue', 'green', 'red', 'orange', 'purple', 'teal'])
        self.bar_color_combo.setStyleSheet(self._get_option_widget_style())
        self.options_histogram_layout.addWidget(bar_color_label)
        self.options_histogram_layout.addWidget(self.bar_color_combo)

        edge_color_label = QLabel("Edge Color:")
        edge_color_label.setStyleSheet(self._get_option_label_style())
        self.edge_color_combo = QComboBox()
        self.edge_color_combo.addItems(['black', 'white', 'grey', 'none'])
        self.edge_color_combo.setStyleSheet(self._get_option_widget_style())
        self.options_histogram_layout.addWidget(edge_color_label)
        self.options_histogram_layout.addWidget(self.edge_color_combo)

        self.show_mean_checkbox = QCheckBox("Show Mean Line")
        self.show_mean_checkbox.setChecked(False)
        self.show_mean_checkbox.setStyleSheet(self._get_checkbox_style())
        self.options_histogram_layout.addWidget(self.show_mean_checkbox)

        self.show_median_checkbox = QCheckBox("Show Median Line")
        self.show_median_checkbox.setChecked(False)
        self.show_median_checkbox.setStyleSheet(self._get_checkbox_style())
        self.options_histogram_layout.addWidget(self.show_median_checkbox)

        self.show_ci_checkbox = QCheckBox("Show Confidence Interval (CI)")
        self.show_ci_checkbox.setChecked(False)
        self.show_ci_checkbox.setStyleSheet(self._get_checkbox_style())
        self.show_ci_checkbox.setToolTip(
            "WARNING: CI is a heuristic/diagnostic estimate.\n"
            "Triangles are not independent (they share points), so this CI can be misleading."
        )
        self.options_histogram_layout.addWidget(self.show_ci_checkbox)

        ci_level_label = QLabel("CI Level (%):")
        ci_level_label.setStyleSheet(self._get_option_label_style())
        self.ci_level_spinbox = QSpinBox()
        self.ci_level_spinbox.setRange(50, 99)
        self.ci_level_spinbox.setValue(95)
        self.ci_level_spinbox.setStyleSheet(self._get_option_widget_style())
        self.options_histogram_layout.addWidget(ci_level_label)
        self.options_histogram_layout.addWidget(self.ci_level_spinbox)

        hist_ci_warning = QLabel(
            "WARNING: CI is heuristic/diagnostic only. Triangles are not independent (shared points),\n"
            "so the interval may be inaccurate or misleading."
        )
        hist_ci_warning.setStyleSheet(
            f"color: {Colors.WARNING}; font-size: 9px; font-weight: 600; background: transparent;"
        )
        hist_ci_warning.setWordWrap(True)
        self.options_histogram_layout.addWidget(hist_ci_warning)

        # ── Planned Features (Histogram) ──
        planned_header_hist = QLabel("PLANNED FEATURES")
        planned_header_hist.setStyleSheet(f"""
            color: {Colors.TEXT_MUTED};
            font-size: 9px;
            font-weight: 700;
            letter-spacing: 0.5px;
            padding: 6px 0 3px 0;
            border-top: 1px solid {Colors.BORDER_SUBTLE};
            margin-top: 4px;
        """)
        self.options_histogram_layout.addWidget(planned_header_hist)

        # Binning Rule Selector (Planned)
        binning_rule_label = QLabel("Binning Rule:")
        binning_rule_label.setStyleSheet(self._get_placeholder_label_style())
        self.binning_rule_combo = PlaceholderComboBox(
            "Binning Rule Selector",
            ["Fixed", "Freedman-Diaconis", "Scott"]
        )
        self.binning_rule_combo.setStyleSheet(self._get_option_widget_style())
        self.options_histogram_layout.addWidget(binning_rule_label)
        self.options_histogram_layout.addWidget(self.binning_rule_combo)

        # Stack Kept/Rejected (Planned)
        self.stack_kept_rejected_checkbox = PlaceholderCheckBox(
            "Stack Kept/Rejected", "Kept vs Rejected Stacked Bars")
        self.stack_kept_rejected_checkbox.setStyleSheet(self._get_checkbox_style())
        self.options_histogram_layout.addWidget(self.stack_kept_rejected_checkbox)

        # KDE Curve (active)
        self.kde_curve_checkbox = QCheckBox("KDE Curve Overlay")
        self.kde_curve_checkbox.setChecked(False)
        self.kde_curve_checkbox.setStyleSheet(self._get_checkbox_style())
        self.options_histogram_layout.addWidget(self.kde_curve_checkbox)

        # CDF Overlay (Planned)
        self.cdf_overlay_checkbox = PlaceholderCheckBox(
            "CDF Overlay", "Cumulative Distribution Function")
        self.cdf_overlay_checkbox.setStyleSheet(self._get_checkbox_style())
        self.options_histogram_layout.addWidget(self.cdf_overlay_checkbox)

        self.options_histogram_layout.addStretch()

        # ── Rose diagram options (index 4) ──
        self.options_rose = QWidget()
        self.options_rose_layout = QVBoxLayout(self.options_rose)
        self.options_rose_layout.setContentsMargins(0, 0, 0, 0)
        self.options_rose_layout.setSpacing(3)

        # ── Data ──
        rose_mode_label = QLabel("Bar Mode:")
        rose_mode_label.setStyleSheet(self._get_option_label_style())
        self.rose_mode_combo = QComboBox()
        self.rose_mode_combo.addItems(['Triangle Count', 'Gradient Sum'])
        self.rose_mode_combo.setStyleSheet(self._get_option_widget_style())
        self.options_rose_layout.addWidget(rose_mode_label)
        self.options_rose_layout.addWidget(self.rose_mode_combo)

        rose_bins_label = QLabel("Number of Bins:")
        rose_bins_label.setStyleSheet(self._get_option_label_style())
        self.rose_bins_spinbox = QSpinBox()
        self.rose_bins_spinbox.setRange(4, 36)
        self.rose_bins_spinbox.setValue(16)
        self.rose_bins_spinbox.setStyleSheet(self._get_option_widget_style())
        self.options_rose_layout.addWidget(rose_bins_label)
        self.options_rose_layout.addWidget(self.rose_bins_spinbox)

        # ── Appearance ──
        _rose_sep_appearance = QLabel("Appearance")
        _rose_sep_appearance.setStyleSheet(
            f"color: {Colors.TEXT_MUTED}; font-size: 9px; font-weight: 700;"
            f" letter-spacing: 0.4px; padding-top: 3px;"
            f" border-top: 1px solid {Colors.BORDER_SUBTLE}; margin-top: 2px;"
        )
        self.options_rose_layout.addWidget(_rose_sep_appearance)

        rose_color_label = QLabel("Color:")
        rose_color_label.setStyleSheet(self._get_option_label_style())
        self.rose_color_combo = QComboBox()
        self.rose_color_combo.addItems(['blue', 'red', 'green', 'purple', 'orange', 'teal', 'grey', 'black'])
        self.rose_color_combo.setStyleSheet(self._get_option_widget_style())
        self.options_rose_layout.addWidget(rose_color_label)
        self.options_rose_layout.addWidget(self.rose_color_combo)

        # ── Overlays ──
        _rose_sep_overlays = QLabel("Overlays")
        _rose_sep_overlays.setStyleSheet(
            f"color: {Colors.TEXT_MUTED}; font-size: 9px; font-weight: 700;"
            f" letter-spacing: 0.4px; padding-top: 3px;"
            f" border-top: 1px solid {Colors.BORDER_SUBTLE}; margin-top: 2px;"
        )
        self.options_rose_layout.addWidget(_rose_sep_overlays)

        self.show_mean_direction_checkbox = QCheckBox("Mean Angle (unweighted)")
        self.show_mean_direction_checkbox.setChecked(True)
        self.show_mean_direction_checkbox.setStyleSheet(self._get_checkbox_style())
        self.options_rose_layout.addWidget(self.show_mean_direction_checkbox)

        self.show_weighted_mean_checkbox = QCheckBox("Weighted Mean (by gradient)")
        self.show_weighted_mean_checkbox.setChecked(True)
        self.show_weighted_mean_checkbox.setStyleSheet(self._get_checkbox_style())
        self.options_rose_layout.addWidget(self.show_weighted_mean_checkbox)

        self.rose_show_median_checkbox = QCheckBox("Median Angle")
        self.rose_show_median_checkbox.setChecked(False)
        self.rose_show_median_checkbox.setStyleSheet(self._get_checkbox_style())
        self.rose_show_median_checkbox.setToolTip("Show the circular (L1) median direction line.")
        self.options_rose_layout.addWidget(self.rose_show_median_checkbox)

        self.rose_show_ci_checkbox = QCheckBox("Confidence Interval (heuristic)")
        self.rose_show_ci_checkbox.setChecked(False)
        self.rose_show_ci_checkbox.setStyleSheet(self._get_checkbox_style())
        self.rose_show_ci_checkbox.setToolTip(
            "WARNING: CI is a heuristic/diagnostic estimate.\n"
            "Triangles are not independent (they share points), so this CI can be misleading."
        )
        self.options_rose_layout.addWidget(self.rose_show_ci_checkbox)

        rose_ci_level_label = QLabel("CI Level (%):")
        rose_ci_level_label.setStyleSheet(self._get_option_label_style())
        self.rose_ci_level_spinbox = QSpinBox()
        self.rose_ci_level_spinbox.setRange(50, 99)
        self.rose_ci_level_spinbox.setValue(95)
        self.rose_ci_level_spinbox.setStyleSheet(self._get_option_widget_style())
        self.options_rose_layout.addWidget(rose_ci_level_label)
        self.options_rose_layout.addWidget(self.rose_ci_level_spinbox)

        # ── Statistics ──
        _rose_sep_stats = QLabel("Statistics")
        _rose_sep_stats.setStyleSheet(
            f"color: {Colors.TEXT_MUTED}; font-size: 9px; font-weight: 700;"
            f" letter-spacing: 0.4px; padding-top: 3px;"
            f" border-top: 1px solid {Colors.BORDER_SUBTLE}; margin-top: 2px;"
        )
        self.options_rose_layout.addWidget(_rose_sep_stats)

        self.mean_resultant_checkbox = QCheckBox("Mean Resultant & Circ. Variance")
        self.mean_resultant_checkbox.setChecked(True)
        self.mean_resultant_checkbox.setStyleSheet(self._get_checkbox_style())
        self.options_rose_layout.addWidget(self.mean_resultant_checkbox)

        # ── Planned Features (Rose) ──
        planned_header_rose = QLabel("PLANNED FEATURES")
        planned_header_rose.setStyleSheet(f"""
            color: {Colors.TEXT_MUTED};
            font-size: 9px;
            font-weight: 700;
            letter-spacing: 0.5px;
            padding: 6px 0 3px 0;
            border-top: 1px solid {Colors.BORDER_SUBTLE};
            margin-top: 4px;
        """)
        self.options_rose_layout.addWidget(planned_header_rose)

        self.axial_symmetry_checkbox = PlaceholderCheckBox(
            "Axial Symmetry (0-180°)", "Axial Symmetry Mode")
        self.axial_symmetry_checkbox.setStyleSheet(self._get_checkbox_style())
        self.options_rose_layout.addWidget(self.axial_symmetry_checkbox)

        self.ring_grid_checkbox = PlaceholderCheckBox(
            "Concentric Ring Grid", "Ring Grid Overlay")
        self.ring_grid_checkbox.setStyleSheet(self._get_checkbox_style())
        self.options_rose_layout.addWidget(self.ring_grid_checkbox)

        self.options_rose_layout.addStretch()

        # Add all option widgets to stack
        self.options_stack.addWidget(self.options_2d)         # Index 0
        self.options_stack.addWidget(self.options_3d)         # Index 1
        self.options_stack.addWidget(self.options_vectors)    # Index 2
        self.options_stack.addWidget(self.options_histogram)  # Index 3
        self.options_stack.addWidget(self.options_rose)       # Index 4

        opts_section.addWidget(self.options_stack)
        content_layout.addWidget(opts_section)

        # Stretch at bottom
        content_layout.addStretch()

        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)

    def _connect_signals(self):
        """Connect toggle signals to emit visualization_changed."""
        self.toggle_contours.toggled.connect(self._emit_visualization_changed)
        self.toggle_contours.toggled.connect(self.contour_levels_spinbox.setEnabled)
        self.toggle_fill_contours.toggled.connect(self._emit_plot_options)
        self.toggle_arrows.toggled.connect(self._emit_visualization_changed)
        self.toggle_arrow_label.toggled.connect(self._emit_visualization_changed)
        self.toggle_points.toggled.connect(self._emit_visualization_changed)
        self.toggle_labels.toggled.connect(self._emit_visualization_changed)
        self.toggle_colorbar.toggled.connect(self._emit_visualization_changed)

        # Connect slider value label updates
        self.point_size_slider.valueChanged.connect(
            lambda v: self.point_size_value_label.setText(str(v))
        )
        self.elev_slider.valueChanged.connect(
            lambda v: self.elev_value_label.setText(f"{v}\u00b0")
        )
        self.azim_slider.valueChanged.connect(
            lambda v: self.azim_value_label.setText(f"{v}\u00b0")
        )
        self.surface_opacity_slider.valueChanged.connect(
            lambda v: self.surface_opacity_value_label.setText(f"{v}%")
        )
        self.vector_scale_slider.valueChanged.connect(
            lambda v: self.vector_scale_value_label.setText(str(v))
        )
        self.vector_alpha_slider.valueChanged.connect(
            lambda v: self.vector_alpha_value_label.setText(f"{v/100:.2f}")
        )
        # Connect plot option widgets to emit plot_options_changed
        # 2D plot options
        self.colormap_2d_combo.currentTextChanged.connect(self._emit_plot_options)
        self.point_size_slider.valueChanged.connect(self._emit_plot_options)
        self.label_mode_2d_combo.currentTextChanged.connect(self._emit_plot_options)

        # Contour plot options
        self.contour_levels_spinbox.valueChanged.connect(self._emit_plot_options)

        # 3D plot options
        self.elev_slider.valueChanged.connect(self._emit_plot_options)
        self.azim_slider.valueChanged.connect(self._emit_plot_options)
        self.colormap_3d_combo.currentTextChanged.connect(self._emit_plot_options)
        self.surface_opacity_slider.valueChanged.connect(self._emit_plot_options)
        self.wireframe_checkbox.toggled.connect(self._emit_plot_options)

        # Vector plot options
        self.vector_scale_slider.valueChanged.connect(self._emit_plot_options)
        self.vector_alpha_slider.valueChanged.connect(self._emit_plot_options)
        self.colormap_vectors_combo.currentTextChanged.connect(self._emit_plot_options)
        self.mean_vector_checkbox.toggled.connect(self._emit_plot_options)
        self.normalize_vectors_checkbox.toggled.connect(self._emit_plot_options)

        # Histogram options
        self.bins_spinbox.valueChanged.connect(self._emit_plot_options)
        self.bar_color_combo.currentTextChanged.connect(self._emit_plot_options)
        self.edge_color_combo.currentTextChanged.connect(self._emit_plot_options)
        self.show_mean_checkbox.toggled.connect(self._emit_plot_options)
        self.show_median_checkbox.toggled.connect(self._emit_plot_options)
        self.show_ci_checkbox.toggled.connect(self._emit_plot_options)
        self.ci_level_spinbox.valueChanged.connect(self._emit_plot_options)
        self.kde_curve_checkbox.toggled.connect(self._emit_plot_options)

        # Rose diagram options
        self.rose_mode_combo.currentTextChanged.connect(self._emit_plot_options)
        self.rose_bins_spinbox.valueChanged.connect(self._emit_plot_options)
        self.show_mean_direction_checkbox.toggled.connect(self._emit_plot_options)
        self.show_weighted_mean_checkbox.toggled.connect(self._emit_plot_options)
        self.rose_show_ci_checkbox.toggled.connect(self._emit_plot_options)
        self.rose_ci_level_spinbox.valueChanged.connect(self._emit_plot_options)
        self.rose_color_combo.currentTextChanged.connect(self._emit_plot_options)
        self.rose_show_median_checkbox.toggled.connect(self._emit_plot_options)
        self.mean_resultant_checkbox.toggled.connect(self._emit_plot_options)

        # Initialize contour sub-option state
        self.contour_levels_spinbox.setEnabled(self.toggle_contours.isChecked())

    def _emit_visualization_changed(self):
        """Emit visualization_changed signal with current state."""
        # Get compass and grid state from toolbar if available
        compass_state = True  # Default
        grid_state = False  # Default

        if self.plot_page_ref:
            compass_state = self.plot_page_ref.compass_checkbox.isChecked()
            grid_state = self.plot_page_ref.grid_checkbox.isChecked()

        viz_dict = {
            'contours': self.toggle_contours.isChecked(),
            'arrow': self.toggle_arrows.isChecked(),
            'arrow_label': self.toggle_arrow_label.isChecked(),
            'points': self.toggle_points.isChecked(),
            'colorbar': self.toggle_colorbar.isChecked(),
            'id_labels': self.toggle_labels.isChecked(),
            'head_labels': self.toggle_labels.isChecked(),
            'compass': compass_state,  # Read from toolbar
            'grid': grid_state  # Read from toolbar
        }
        self.visualization_changed.emit(viz_dict)

    def _emit_plot_options(self):
        """Emit plot_options_changed signal with current options based on active plot type."""
        current_index = self.options_stack.currentIndex()

        options = {
            'plot_type_index': current_index,
            # 2D options (index 0)
            'colormap_2d': self.colormap_2d_combo.currentText(),
            'point_size': self.point_size_slider.value(),
            'label_mode_2d': self.label_mode_2d_combo.currentText().lower(),
            # Contour options (merged into 2D)
            'contour_levels': self.contour_levels_spinbox.value(),
            'fill_contours': self.toggle_fill_contours.isChecked(),
            # 3D options (index 1)
            'elevation': self.elev_slider.value(),
            'azimuth': self.azim_slider.value(),
            'colormap_3d': self.colormap_3d_combo.currentText(),
            'surface_opacity': self.surface_opacity_slider.value() / 100.0,
            'wireframe_overlay': self.wireframe_checkbox.isChecked(),
            # Vector options (index 2)
            'vector_scale': self.vector_scale_slider.value(),
            'vector_alpha': self.vector_alpha_slider.value() / 100.0,
            'colormap_vectors': self.colormap_vectors_combo.currentText(),
            'show_mean_vector': self.mean_vector_checkbox.isChecked(),
            'normalize_vectors': self.normalize_vectors_checkbox.isChecked(),
            # Histogram options (index 3)
            'histogram_bins': self.bins_spinbox.value(),
            'histogram_bar_color': self.bar_color_combo.currentText(),
            'histogram_edge_color': self.edge_color_combo.currentText(),
            'histogram_show_mean': self.show_mean_checkbox.isChecked(),
            'histogram_show_median': self.show_median_checkbox.isChecked(),
            'histogram_show_ci': self.show_ci_checkbox.isChecked(),
            'histogram_ci_level': self.ci_level_spinbox.value(),
            'histogram_show_kde': self.kde_curve_checkbox.isChecked(),
            # Rose diagram options (index 4)
            'rose_mode': 'gradient_weighted' if self.rose_mode_combo.currentText() == 'Gradient Sum' else 'count',
            'rose_bins': self.rose_bins_spinbox.value(),
            'rose_show_mean': self.show_mean_direction_checkbox.isChecked(),
            'rose_show_weighted_mean': self.show_weighted_mean_checkbox.isChecked(),
            'rose_show_ci': self.rose_show_ci_checkbox.isChecked(),
            'rose_ci_level': self.rose_ci_level_spinbox.value(),
            'rose_color': self.rose_color_combo.currentText(),
            'rose_show_median': self.rose_show_median_checkbox.isChecked(),
            'rose_show_mean_resultant': self.mean_resultant_checkbox.isChecked(),
        }

        self.plot_options_changed.emit(options)

    def set_plot_type(self, plot_type: str):
        """Switch to appropriate options panel based on plot type."""
        plot_type = normalize_plot_type(plot_type)
        type_map = {
            "2D": 0,
            "3D": 1,
            "Gradient Vectors": 2,
            "Histogram": 3,
            "Rose Diagram": 4,
            # "Map" reuses the 2D options panel — colormap, point size and
            # colorbar toggle all apply identically to the lat/lon scatter
            # drawn over the OSM basemap.
            "Map": 0,
        }
        index = type_map.get(plot_type, 0)
        self.options_stack.setCurrentIndex(index)

        # Define which toggles are relevant for each plot type
        toggle_visibility = {
            "2D": {"contours": True, "arrows": True, "arrow_label": True, "points": True, "labels": True, "colorbar": True},
            "3D": {"contours": False, "arrows": False, "arrow_label": False, "points": True, "labels": False, "colorbar": True},
            "Gradient Vectors": {"contours": False, "arrows": True, "arrow_label": False, "points": True, "labels": True, "colorbar": True},
            "Histogram": {"contours": False, "arrows": False, "arrow_label": False, "points": False, "labels": False, "colorbar": False},
            "Rose Diagram": {"contours": False, "arrows": False, "arrow_label": False, "points": False, "labels": False, "colorbar": False},
            # Map: colormap + colorbar are the only meaningful toggles here.
            # Contour / arrow / label overlays are conceptually 2-D-only.
            "Map": {"contours": False, "arrows": False, "arrow_label": False, "points": False, "labels": False, "colorbar": True},
        }

        visibility = toggle_visibility.get(plot_type, toggle_visibility["2D"])

        # Show/hide toggles based on plot type
        self.toggle_contours.setVisible(visibility["contours"])
        self._contour_suboptions.setVisible(visibility["contours"])
        self.toggle_arrows.setVisible(visibility["arrows"])
        self.toggle_arrow_label.setVisible(visibility.get("arrow_label", False))
        self.toggle_points.setVisible(visibility["points"])
        self.toggle_labels.setVisible(visibility["labels"])
        self.toggle_colorbar.setVisible(visibility["colorbar"])

    def update_from_settings(self, settings: dict):
        """Update toggle states from settings dict."""
        # Block signals while updating to avoid loops
        self.toggle_contours.blockSignals(True)
        self.toggle_arrows.blockSignals(True)
        self.toggle_arrow_label.blockSignals(True)
        self.toggle_points.blockSignals(True)
        self.toggle_labels.blockSignals(True)
        self.toggle_colorbar.blockSignals(True)
        self.label_mode_2d_combo.blockSignals(True)
        self.colormap_2d_combo.blockSignals(True)
        self.point_size_slider.blockSignals(True)
        self.contour_levels_spinbox.blockSignals(True)
        self.toggle_fill_contours.blockSignals(True)
        self.elev_slider.blockSignals(True)
        self.azim_slider.blockSignals(True)
        self.colormap_3d_combo.blockSignals(True)
        self.surface_opacity_slider.blockSignals(True)
        self.wireframe_checkbox.blockSignals(True)
        self.vector_scale_slider.blockSignals(True)
        self.vector_alpha_slider.blockSignals(True)
        self.colormap_vectors_combo.blockSignals(True)
        self.mean_vector_checkbox.blockSignals(True)
        self.normalize_vectors_checkbox.blockSignals(True)
        self.bins_spinbox.blockSignals(True)
        self.bar_color_combo.blockSignals(True)
        self.edge_color_combo.blockSignals(True)
        self.show_mean_checkbox.blockSignals(True)
        self.show_median_checkbox.blockSignals(True)
        self.show_ci_checkbox.blockSignals(True)
        self.ci_level_spinbox.blockSignals(True)
        self.kde_curve_checkbox.blockSignals(True)
        self.rose_mode_combo.blockSignals(True)
        self.rose_bins_spinbox.blockSignals(True)
        self.show_mean_direction_checkbox.blockSignals(True)
        self.show_weighted_mean_checkbox.blockSignals(True)
        self.rose_show_ci_checkbox.blockSignals(True)
        self.rose_ci_level_spinbox.blockSignals(True)
        self.rose_color_combo.blockSignals(True)
        self.rose_show_median_checkbox.blockSignals(True)
        self.mean_resultant_checkbox.blockSignals(True)

        # Update states
        self.toggle_contours.setChecked(settings.get('show_contours', False))
        self.toggle_arrows.setChecked(settings.get('show_arrow', True))
        self.toggle_arrow_label.setChecked(settings.get('show_arrow_label', True))
        self.toggle_points.setChecked(settings.get('show_points', True))
        self.toggle_colorbar.setChecked(settings.get('show_colorbar', True))
        self.toggle_labels.setChecked(settings.get('show_id_labels', True))
        label_mode = str(settings.get('label_mode_2d', 'all') or 'all').lower()
        label_mode_text = {
            'all': 'All',
            'smart': 'Smart',
            'off': 'Off',
            'pinned': 'Pinned',
        }.get(label_mode, 'All')
        self.label_mode_2d_combo.setCurrentText(label_mode_text)
        self.colormap_2d_combo.setCurrentText(str(settings.get('colormap_2d', self.colormap_2d_combo.currentText())))
        self.point_size_slider.setValue(int(settings.get('point_size', self.point_size_slider.value())))
        self.contour_levels_spinbox.setValue(int(settings.get('contour_levels', self.contour_levels_spinbox.value())))
        self.toggle_fill_contours.setChecked(bool(settings.get('fill_contours', self.toggle_fill_contours.isChecked())))
        self.elev_slider.setValue(int(settings.get('elevation_3d', settings.get('elevation', self.elev_slider.value()))))
        self.azim_slider.setValue(int(settings.get('azimuth_3d', settings.get('azimuth', self.azim_slider.value()))))
        self.colormap_3d_combo.setCurrentText(str(settings.get('colormap_3d', self.colormap_3d_combo.currentText())))
        self.surface_opacity_slider.setValue(int(round(100.0 * float(settings.get('surface_opacity', settings.get('surface_alpha', 0.8))))))
        self.wireframe_checkbox.setChecked(bool(settings.get('wireframe_overlay', settings.get('show_wireframe', False))))
        self.vector_scale_slider.setValue(int(settings.get('vector_scale', self.vector_scale_slider.value())))
        self.vector_alpha_slider.setValue(int(round(100.0 * float(settings.get('vector_alpha', self.vector_alpha_slider.value() / 100.0)))))
        self.colormap_vectors_combo.setCurrentText(str(settings.get('colormap_vectors', self.colormap_vectors_combo.currentText())))
        self.mean_vector_checkbox.setChecked(bool(settings.get('show_mean_vector', self.mean_vector_checkbox.isChecked())))
        self.normalize_vectors_checkbox.setChecked(bool(settings.get('normalize_vectors', self.normalize_vectors_checkbox.isChecked())))
        self.bins_spinbox.setValue(int(settings.get('histogram_bins', self.bins_spinbox.value())))
        self.bar_color_combo.setCurrentText(str(settings.get('histogram_bar_color', self.bar_color_combo.currentText())))
        self.edge_color_combo.setCurrentText(str(settings.get('histogram_edge_color', self.edge_color_combo.currentText())))
        self.show_mean_checkbox.setChecked(bool(settings.get('histogram_show_mean', self.show_mean_checkbox.isChecked())))
        self.show_median_checkbox.setChecked(bool(settings.get('histogram_show_median', self.show_median_checkbox.isChecked())))
        self.show_ci_checkbox.setChecked(bool(settings.get('histogram_show_ci', self.show_ci_checkbox.isChecked())))
        self.ci_level_spinbox.setValue(int(settings.get('histogram_ci_level', self.ci_level_spinbox.value())))
        self.kde_curve_checkbox.setChecked(bool(settings.get('histogram_show_kde', self.kde_curve_checkbox.isChecked())))
        self.rose_mode_combo.setCurrentText('Gradient Sum' if str(settings.get('rose_mode', 'count')) == 'gradient_weighted' else 'Count')
        self.rose_bins_spinbox.setValue(int(settings.get('rose_bins', self.rose_bins_spinbox.value())))
        self.show_mean_direction_checkbox.setChecked(bool(settings.get('rose_show_mean', self.show_mean_direction_checkbox.isChecked())))
        self.show_weighted_mean_checkbox.setChecked(bool(settings.get('rose_show_weighted_mean', self.show_weighted_mean_checkbox.isChecked())))
        self.rose_show_ci_checkbox.setChecked(bool(settings.get('rose_show_ci', self.rose_show_ci_checkbox.isChecked())))
        self.rose_ci_level_spinbox.setValue(int(settings.get('rose_ci_level', self.rose_ci_level_spinbox.value())))
        self.rose_color_combo.setCurrentText(str(settings.get('rose_color', self.rose_color_combo.currentText())))
        self.rose_show_median_checkbox.setChecked(bool(settings.get('rose_show_median', self.rose_show_median_checkbox.isChecked())))
        self.mean_resultant_checkbox.setChecked(bool(settings.get('rose_show_mean_resultant', self.mean_resultant_checkbox.isChecked())))

        # Keep contour sub-option in sync (visibility controlled by setSubOptionsWidget)
        self._contour_suboptions.setVisible(self.toggle_contours.isChecked())
        self.contour_levels_spinbox.setEnabled(self.toggle_contours.isChecked())

        # Unblock signals
        self.toggle_contours.blockSignals(False)
        self.toggle_arrows.blockSignals(False)
        self.toggle_arrow_label.blockSignals(False)
        self.toggle_points.blockSignals(False)
        self.toggle_labels.blockSignals(False)
        self.toggle_colorbar.blockSignals(False)
        self.label_mode_2d_combo.blockSignals(False)
        self.colormap_2d_combo.blockSignals(False)
        self.point_size_slider.blockSignals(False)
        self.contour_levels_spinbox.blockSignals(False)
        self.toggle_fill_contours.blockSignals(False)
        self.elev_slider.blockSignals(False)
        self.azim_slider.blockSignals(False)
        self.colormap_3d_combo.blockSignals(False)
        self.surface_opacity_slider.blockSignals(False)
        self.wireframe_checkbox.blockSignals(False)
        self.vector_scale_slider.blockSignals(False)
        self.vector_alpha_slider.blockSignals(False)
        self.colormap_vectors_combo.blockSignals(False)
        self.mean_vector_checkbox.blockSignals(False)
        self.normalize_vectors_checkbox.blockSignals(False)
        self.bins_spinbox.blockSignals(False)
        self.bar_color_combo.blockSignals(False)
        self.edge_color_combo.blockSignals(False)
        self.show_mean_checkbox.blockSignals(False)
        self.show_median_checkbox.blockSignals(False)
        self.show_ci_checkbox.blockSignals(False)
        self.ci_level_spinbox.blockSignals(False)
        self.kde_curve_checkbox.blockSignals(False)
        self.rose_mode_combo.blockSignals(False)
        self.rose_bins_spinbox.blockSignals(False)
        self.show_mean_direction_checkbox.blockSignals(False)
        self.show_weighted_mean_checkbox.blockSignals(False)
        self.rose_show_ci_checkbox.blockSignals(False)
        self.rose_ci_level_spinbox.blockSignals(False)
        self.rose_color_combo.blockSignals(False)
        self.rose_show_median_checkbox.blockSignals(False)
        self.mean_resultant_checkbox.blockSignals(False)

    def get_settings_snapshot(self) -> dict:
        """Return a settings dict that can be fed back into update_from_settings()."""
        return {
            # Viz toggles
            'show_contours':      self.toggle_contours.isChecked(),
            'show_arrow':         self.toggle_arrows.isChecked(),
            'show_arrow_label':   self.toggle_arrow_label.isChecked(),
            'show_points':        self.toggle_points.isChecked(),
            'show_colorbar':      self.toggle_colorbar.isChecked(),
            'show_id_labels':     self.toggle_labels.isChecked(),
            'fill_contours':      self.toggle_fill_contours.isChecked(),
            # 2D
            'colormap_2d':        self.colormap_2d_combo.currentText(),
            'point_size':         self.point_size_slider.value(),
            'label_mode_2d':      self.label_mode_2d_combo.currentText().lower(),
            'contour_levels':     self.contour_levels_spinbox.value(),
            # 3D
            'elevation_3d':       self.elev_slider.value(),
            'azimuth_3d':         self.azim_slider.value(),
            'colormap_3d':        self.colormap_3d_combo.currentText(),
            'surface_opacity':    self.surface_opacity_slider.value() / 100.0,
            'wireframe_overlay':  self.wireframe_checkbox.isChecked(),
            # Vectors
            'vector_scale':       self.vector_scale_slider.value(),
            'vector_alpha':       self.vector_alpha_slider.value() / 100.0,
            'colormap_vectors':   self.colormap_vectors_combo.currentText(),
            'show_mean_vector':   self.mean_vector_checkbox.isChecked(),
            'normalize_vectors':  self.normalize_vectors_checkbox.isChecked(),
            # Histogram
            'histogram_bins':         self.bins_spinbox.value(),
            'histogram_bar_color':    self.bar_color_combo.currentText(),
            'histogram_edge_color':   self.edge_color_combo.currentText(),
            'histogram_show_mean':    self.show_mean_checkbox.isChecked(),
            'histogram_show_median':  self.show_median_checkbox.isChecked(),
            'histogram_show_ci':      self.show_ci_checkbox.isChecked(),
            'histogram_ci_level':     self.ci_level_spinbox.value(),
            'histogram_show_kde':     self.kde_curve_checkbox.isChecked(),
            # Rose diagram
            'rose_mode':              'gradient_weighted' if self.rose_mode_combo.currentText() == 'Gradient Sum' else 'count',
            'rose_bins':              self.rose_bins_spinbox.value(),
            'rose_show_mean':         self.show_mean_direction_checkbox.isChecked(),
            'rose_show_weighted_mean':self.show_weighted_mean_checkbox.isChecked(),
            'rose_show_ci':           self.rose_show_ci_checkbox.isChecked(),
            'rose_ci_level':          self.rose_ci_level_spinbox.value(),
            'rose_color':             self.rose_color_combo.currentText(),
            'rose_show_median':       self.rose_show_median_checkbox.isChecked(),
            'rose_show_mean_resultant':self.mean_resultant_checkbox.isChecked(),
        }

    def apply_theme(self):
        metrics = build_screen_metrics(self)
        settings = {}
        if self.plot_page_ref is not None and getattr(self.plot_page_ref, "main_window", None) is not None:
            try:
                settings = self.plot_page_ref.main_window._sidebar_settings_for_active_state()
            except Exception:
                settings = {}
        plot_type = "2D"
        if self.plot_page_ref is not None and getattr(self.plot_page_ref, "main_window", None) is not None:
            plot_type = str(getattr(self.plot_page_ref.main_window, "current_plot_type", "2D"))

        reset_widget_layout(self)
        self.setMinimumWidth(metrics.plot_sidebar_width)
        self.setMaximumWidth(metrics.plot_sidebar_width)
        self.setStyleSheet(f"""
            QWidget#plotSidebar {{
                background-color: {Colors.BG_PANEL};
                border-right: 1px solid {Colors.BORDER_DEFAULT};
            }}
        """)
        self._setup_ui()
        self._connect_signals()
        self.update_from_settings(settings)
        self.set_plot_type(plot_type)

    def _create_colormap_combo(self, colormaps: list) -> QComboBox:
        """Create a QComboBox with colormap gradient preview icons."""
        import numpy as np
        import matplotlib.cm as cm

        combo = QComboBox()
        combo.setIconSize(QSize(80, 14))
        combo.addItems(colormaps)
        combo.setStyleSheet(self._get_option_widget_style())

        for i, name in enumerate(colormaps):
            try:
                cmap = cm.get_cmap(name)
                gradient = np.linspace(0, 1, 80)
                rgba = (cmap(gradient) * 255).astype(np.uint8)
                # Tile single row to icon height
                data = np.tile(rgba, (14, 1, 1)).copy()
                img = QImage(data.data, 80, 14, 80 * 4, QImage.Format_RGBA8888)
                combo.setItemIcon(i, QIcon(QPixmap.fromImage(img.copy())))
            except Exception:
                pass

        return combo

    def _get_option_label_style(self):
        """Get styling for option labels."""
        return f"""
            QLabel {{
                color: {Colors.TEXT_SECONDARY};
                font-size: 10px;
                font-weight: 600;
                padding: 0px 0px;
            }}
        """

    def _get_placeholder_label_style(self):
        """Get styling for placeholder/planned feature labels."""
        return f"""
            QLabel {{
                color: {Colors.TEXT_MUTED};
                font-size: 10px;
                font-weight: 500;
                font-style: italic;
                padding: 0px 0px;
            }}
        """

    def _get_option_widget_style(self):
        """Get styling for option widgets (combo boxes, spin boxes).

        Uses BG_ELEVATED + a stronger border so the input fields stand out
        from the BG_PANEL surface they sit on. Padding kept tight so the
        sidebar stays compact in a 2×2 grid layout.
        """
        return f"""
            QComboBox {{
                background-color: {Colors.BG_ELEVATED};
                color: {Colors.TEXT_PRIMARY};
                border: 1px solid {Colors.BORDER_STRONG};
                border-radius: 5px;
                padding: 3px 10px;
                padding-right: 24px;
                font-size: 11px;
                min-height: 18px;
            }}
            QComboBox:hover {{
                background-color: {Colors.BG_HOVER};
                border-color: {Colors.ACCENT_PRIMARY};
            }}
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: center right;
                width: 22px;
                border: none;
                background: transparent;
            }}
            QComboBox::down-arrow {{
                width: 0px;
                height: 0px;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid {Colors.TEXT_MUTED};
            }}
            QComboBox::down-arrow:hover {{
                border-top-color: {Colors.ACCENT_PRIMARY};
            }}
            QComboBox QAbstractItemView {{
                background-color: {Colors.BG_ELEVATED};
                color: {Colors.TEXT_PRIMARY};
                border: 1px solid {Colors.BORDER_STRONG};
                border-radius: 6px;
                padding: 4px;
                selection-background-color: {Colors.ACCENT_PRIMARY};
                selection-color: white;
                outline: none;
            }}
            QComboBox QAbstractItemView::item {{
                background-color: {Colors.BG_ELEVATED};
                padding: 5px 10px;
                min-height: 20px;
            }}
            QComboBox QAbstractItemView::item:hover {{
                background-color: {Colors.BG_HOVER};
            }}
            QComboBox QAbstractItemView::item:selected {{
                background-color: {Colors.ACCENT_PRIMARY};
            }}
            QSpinBox {{
                background-color: {Colors.BG_ELEVATED};
                color: {Colors.TEXT_PRIMARY};
                border: 1px solid {Colors.BORDER_STRONG};
                border-radius: 5px;
                padding: 3px 8px;
                padding-right: 20px;
                font-size: 11px;
                min-height: 18px;
            }}
            QSpinBox:hover {{
                background-color: {Colors.BG_HOVER};
                border-color: {Colors.ACCENT_PRIMARY};
            }}
            QSpinBox::up-button, QSpinBox::down-button {{
                subcontrol-origin: border;
                background: transparent;
                border: none;
                width: 18px;
            }}
            QSpinBox::up-button {{
                subcontrol-position: top right;
            }}
            QSpinBox::down-button {{
                subcontrol-position: bottom right;
            }}
            QSpinBox::up-arrow {{
                width: 0; height: 0;
                border-left: 3px solid transparent;
                border-right: 3px solid transparent;
                border-bottom: 4px solid {Colors.TEXT_MUTED};
            }}
            QSpinBox::down-arrow {{
                width: 0; height: 0;
                border-left: 3px solid transparent;
                border-right: 3px solid transparent;
                border-top: 4px solid {Colors.TEXT_MUTED};
            }}
            QSpinBox::up-arrow:hover {{
                border-bottom-color: {Colors.ACCENT_PRIMARY};
            }}
            QSpinBox::down-arrow:hover {{
                border-top-color: {Colors.ACCENT_PRIMARY};
            }}
        """

    def _get_value_label_style(self):
        """Get styling for value labels next to sliders."""
        return f"""
            QLabel {{
                color: {Colors.ACCENT_BRIGHT};
                font-family: 'IBM Plex Mono', monospace;
                font-size: 10px;
                font-weight: 500;
                background-color: {Colors.ACCENT_GHOST};
                border: 1px solid {Colors.BORDER_ACCENT};
                padding: 1px 7px;
                border-radius: 6px;
                min-width: 35px;
            }}
        """

    def _get_checkbox_style(self):
        """Get styling for checkboxes."""
        return f"""
            QCheckBox {{
                color: {Colors.TEXT_SECONDARY};
                font-size: 10px;
                font-weight: 500;
                spacing: 6px;
                padding: 4px 0px;
                border-radius: 4px;
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
                background-color: {Colors.BG_SURFACE};
            }}
            QCheckBox::indicator:hover {{
                border-color: {Colors.ACCENT_PRIMARY};
                background-color: {Colors.BG_HOVER};
            }}
            QCheckBox::indicator:checked {{
                background-color: {Colors.ACCENT_PRIMARY};
                border-color: {Colors.ACCENT_PRIMARY};
                image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTIiIGhlaWdodD0iMTIiIHZpZXdCb3g9IjAgMCAxMiAxMiIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZD0iTTEwIDNMNC41IDguNUwyIDYiIHN0cm9rZT0id2hpdGUiIHN0cm9rZS13aWR0aD0iMiIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIi8+Cjwvc3ZnPgo=);
            }}
            QCheckBox::indicator:checked:hover {{
                background-color: {Colors.ACCENT_HOVER};
                border-color: {Colors.ACCENT_HOVER};
            }}
            QCheckBox:disabled {{
                color: {Colors.TEXT_MUTED};
            }}
            QCheckBox::indicator:disabled {{
                background-color: {Colors.BG_WELL};
                border-color: {Colors.BORDER_SUBTLE};
            }}
        """
