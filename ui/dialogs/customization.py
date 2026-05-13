"""
HeadAnalyser V2 - Customization Dialog
Dialog for plot customization settings.
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QTabWidget, QWidget, QFormLayout, QSpinBox,
    QDoubleSpinBox, QCheckBox, QLineEdit, QSlider, QColorDialog
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor

from styles.colors import Colors
from qt_chrome import FramelessDialogMixin


class CustomizationDialog(FramelessDialogMixin, QDialog):
    """Dialog for customizing plot appearance."""
    
    def __init__(self, main_window, plot_type: str, parent=None):
        super().__init__(parent or main_window)
        self.main_window = main_window
        self.plot_type = "2D" if plot_type == "Contour & Gradient" else plot_type
        
        self.setWindowTitle("Plot Customization")
        self.setMinimumSize(500, 400)
        self.setModal(True)
        self.init_frameless_dialog_chrome(
            default_windows="native",
            default_other="native",
            resize_margin=10,
            top_resize_margin=10,
        )

        self._setup_ui()
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Title
        title = QLabel(f"Customize {self.plot_type} Plot")
        title.setStyleSheet(f"color: {Colors.ACCENT_PRIMARY}; font-size: 16px; font-weight: bold;")
        layout.addWidget(title)
        
        # Tab widget for different settings categories
        tabs = QTabWidget()
        
        # Determine which tabs to show based on plot type
        # General/Labels/Colors tabs don't apply well to Histogram and Rose Diagram
        show_styling_tabs = self.plot_type not in ["Histogram", "Rose Diagram"]
        
        # General tab - only for plots with markers, grid, compass, colormap
        if show_styling_tabs:
            general_tab = self._create_general_tab()
            tabs.addTab(general_tab, "General")
        
            # Labels tab
            labels_tab = self._create_labels_tab()
            tabs.addTab(labels_tab, "Labels")
        
            # Colors tab
            colors_tab = self._create_colors_tab()
            tabs.addTab(colors_tab, "Colors")
        
        # Plot-specific tabs
        if self.plot_type == "2D":
            specific_tab = self._create_2d_tab()
            tabs.addTab(specific_tab, "2D Options")
        elif self.plot_type == "3D":
            specific_tab = self._create_3d_tab()
            tabs.addTab(specific_tab, "3D Options")
        elif self.plot_type == "Gradient Vectors":
            specific_tab = self._create_vectors_tab()
            tabs.addTab(specific_tab, "Vector Options")
        elif self.plot_type == "Histogram":
            # Histogram - show a simplified options tab
            specific_tab = self._create_histogram_tab()
            tabs.addTab(specific_tab, "Histogram Options")
        elif self.plot_type == "Rose Diagram":
            # Rose diagram - show a simplified options tab
            specific_tab = self._create_rose_tab()
            tabs.addTab(specific_tab, "Rose Options")

        layout.addWidget(tabs)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.clicked.connect(self._reset_defaults)
        button_layout.addWidget(reset_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        apply_btn = QPushButton("Apply")
        apply_btn.setStyleSheet(f"background-color: {Colors.ACCENT_PRIMARY};")
        apply_btn.clicked.connect(self._apply)
        button_layout.addWidget(apply_btn)
        
        layout.addLayout(button_layout)
        
    def _create_general_tab(self):
        widget = QWidget()
        layout = QFormLayout(widget)
        layout.setSpacing(12)
        
        # Marker size
        self.marker_size_spin = QSpinBox()
        self.marker_size_spin.setRange(10, 300)
        self.marker_size_spin.setValue(80)
        layout.addRow("Marker Size:", self.marker_size_spin)
        
        # Show grid
        self.show_grid_check = QCheckBox()
        self.show_grid_check.setChecked(self.main_window.show_grid)
        layout.addRow("Show Grid:", self.show_grid_check)
        
        # Show compass
        self.show_compass_check = QCheckBox()
        self.show_compass_check.setChecked(self.main_window.show_compass)
        layout.addRow("Show Compass:", self.show_compass_check)
        
        # Colormap
        self.colormap_combo = QComboBox()
        self.colormap_combo.addItems(['viridis', 'plasma', 'inferno', 'magma', 'cividis', 'coolwarm'])
        layout.addRow("Colormap:", self.colormap_combo)

        # Tooltip style
        from styles.plot_styles import PopupStyles
        self.popup_style_combo = QComboBox()
        self.popup_style_combo.addItems(list(PopupStyles.STYLES.keys()))
        self.popup_style_combo.setCurrentText(getattr(self.main_window, 'current_popup_style', 'Clean'))
        layout.addRow("Tooltip Style:", self.popup_style_combo)

        return widget
        
    def _create_labels_tab(self):
        widget = QWidget()
        layout = QFormLayout(widget)
        layout.setSpacing(12)
        
        # Show ID labels
        self.show_id_check = QCheckBox()
        self.show_id_check.setChecked(self.main_window.show_id_labels)
        layout.addRow("Show ID Labels:", self.show_id_check)
        
        # ID font size
        self.id_font_spin = QSpinBox()
        self.id_font_spin.setRange(6, 24)
        self.id_font_spin.setValue(9)
        layout.addRow("ID Font Size:", self.id_font_spin)
        
        # Show head labels
        self.show_head_check = QCheckBox()
        self.show_head_check.setChecked(self.main_window.show_head_labels)
        layout.addRow("Show Head Labels:", self.show_head_check)
        
        # Head font size
        self.head_font_spin = QSpinBox()
        self.head_font_spin.setRange(6, 24)
        self.head_font_spin.setValue(8)
        layout.addRow("Head Font Size:", self.head_font_spin)
        
        # X-axis label
        self.x_label_edit = QLineEdit("X Coordinate [m]")
        layout.addRow("X-Axis Label:", self.x_label_edit)
        
        # Y-axis label
        self.y_label_edit = QLineEdit("Y Coordinate [m]")
        layout.addRow("Y-Axis Label:", self.y_label_edit)

        # Label offset
        self.label_offset_spin = QSpinBox()
        self.label_offset_spin.setRange(0, 50)
        self.label_offset_spin.setValue(10)
        layout.addRow("Label Offset:", self.label_offset_spin)

        # Axis tick label font size
        self.axis_tick_font_spin = QSpinBox()
        self.axis_tick_font_spin.setRange(6, 18)
        self.axis_tick_font_spin.setValue(9)
        layout.addRow("Axis Tick Font Size:", self.axis_tick_font_spin)

        # Axis label font size
        self.axis_label_font_spin = QSpinBox()
        self.axis_label_font_spin.setRange(8, 20)
        self.axis_label_font_spin.setValue(11)
        layout.addRow("Axis Label Font Size:", self.axis_label_font_spin)

        return widget
        
    def _create_colors_tab(self):
        widget = QWidget()
        layout = QFormLayout(widget)
        layout.setSpacing(12)
        
        # ID label color
        self.id_color_btn = QPushButton("Select Color")
        self.id_color_btn.setProperty("color", "#818cf8")
        self.id_color_btn.clicked.connect(lambda: self._pick_color(self.id_color_btn))
        layout.addRow("ID Label Color:", self.id_color_btn)
        
        # Head label color
        self.head_color_btn = QPushButton("Select Color")
        self.head_color_btn.setProperty("color", "#a0a0a0")
        self.head_color_btn.clicked.connect(lambda: self._pick_color(self.head_color_btn))
        layout.addRow("Head Label Color:", self.head_color_btn)
        
        # Arrow color
        self.arrow_color_btn = QPushButton("Select Color")
        self.arrow_color_btn.setProperty("color", "#818cf8")
        self.arrow_color_btn.clicked.connect(lambda: self._pick_color(self.arrow_color_btn))
        layout.addRow("Arrow Color:", self.arrow_color_btn)
        
        return widget
        
    def _create_2d_tab(self):
        widget = QWidget()
        layout = QFormLayout(widget)
        layout.setSpacing(12)
        
        # Show contours
        self.show_contours_check = QCheckBox()
        self.show_contours_check.setChecked(self.main_window.show_contours)
        layout.addRow("Show Contours:", self.show_contours_check)
        
        # Interpolation method
        self.interp_combo = QComboBox()
        self.interp_combo.addItems(['cubic', 'linear', 'nearest'])
        layout.addRow("Interpolation:", self.interp_combo)
        
        # Show colorbar
        self.show_colorbar_check = QCheckBox()
        self.show_colorbar_check.setChecked(self.main_window.show_colorbar)
        layout.addRow("Show Colorbar:", self.show_colorbar_check)
        
        # Show arrow
        self.show_arrow_check = QCheckBox()
        self.show_arrow_check.setChecked(self.main_window.show_arrow)
        layout.addRow("Show Gradient Arrow:", self.show_arrow_check)

        # Show arrow label
        self.show_arrow_label_check = QCheckBox()
        self.show_arrow_label_check.setChecked(getattr(self.main_window, 'show_arrow_label', True))
        layout.addRow("Show Arrow Label:", self.show_arrow_label_check)

        # Arrow start X position
        self.arrow_x_edit = QLineEdit()
        self.arrow_x_edit.setPlaceholderText("Auto (leave empty)")
        layout.addRow("Arrow Start X:", self.arrow_x_edit)

        # Arrow start Y position
        self.arrow_y_edit = QLineEdit()
        self.arrow_y_edit.setPlaceholderText("Auto (leave empty)")
        layout.addRow("Arrow Start Y:", self.arrow_y_edit)

        return widget

    def _create_3d_tab(self):
        widget = QWidget()
        layout = QFormLayout(widget)
        layout.setSpacing(12)

        # Surface opacity/alpha
        self.surface_alpha_slider = QSlider(Qt.Horizontal)
        self.surface_alpha_slider.setRange(10, 100)
        self.surface_alpha_slider.setValue(80)
        layout.addRow("Surface Opacity:", self.surface_alpha_slider)

        # Show wireframe overlay
        self.show_wireframe_check = QCheckBox()
        self.show_wireframe_check.setChecked(False)
        layout.addRow("Wireframe Overlay:", self.show_wireframe_check)

        return widget

    def _create_vectors_tab(self):
        widget = QWidget()
        layout = QFormLayout(widget)
        layout.setSpacing(12)
        
        # Scale factor
        self.scale_spin = QDoubleSpinBox()
        self.scale_spin.setRange(0.1, 100.0)
        self.scale_spin.setValue(50.0)
        self.scale_spin.setSingleStep(5.0)
        layout.addRow("Scale Factor:", self.scale_spin)
        
        # Alpha
        self.alpha_slider = QSlider(Qt.Horizontal)
        self.alpha_slider.setRange(10, 100)
        self.alpha_slider.setValue(70)
        layout.addRow("Opacity:", self.alpha_slider)
        
        # Show points
        self.show_points_check = QCheckBox()
        self.show_points_check.setChecked(True)
        layout.addRow("Show Points:", self.show_points_check)

        # Show vector ID labels
        self.show_vector_id_check = QCheckBox()
        self.show_vector_id_check.setChecked(False)
        layout.addRow("Show ID Labels:", self.show_vector_id_check)

        # Max vector count for downsampling
        self.vector_count_spin = QSpinBox()
        self.vector_count_spin.setRange(10, 10000)
        self.vector_count_spin.setValue(500)
        layout.addRow("Max Vectors:", self.vector_count_spin)

        return widget

    def _create_histogram_tab(self):
        """Create histogram-specific options tab."""
        widget = QWidget()
        layout = QFormLayout(widget)
        layout.setSpacing(12)

        # X-axis label
        self.hist_x_label_edit = QLineEdit()
        self.hist_x_label_edit.setText(getattr(self.main_window, 'x_axis_label', 'Gradient Magnitude'))
        layout.addRow("X-Axis Label:", self.hist_x_label_edit)

        # Y-axis label
        self.hist_y_label_edit = QLineEdit()
        self.hist_y_label_edit.setText(getattr(self.main_window, 'y_axis_label', 'Frequency'))
        layout.addRow("Y-Axis Label:", self.hist_y_label_edit)

        # Axis label font size
        self.hist_axis_label_font_spin = QSpinBox()
        self.hist_axis_label_font_spin.setRange(8, 20)
        self.hist_axis_label_font_spin.setValue(getattr(self.main_window, 'axis_label_font_size', 11))
        layout.addRow("Axis Label Font Size:", self.hist_axis_label_font_spin)

        # Axis tick font size
        self.hist_axis_tick_font_spin = QSpinBox()
        self.hist_axis_tick_font_spin.setRange(6, 18)
        self.hist_axis_tick_font_spin.setValue(getattr(self.main_window, 'axis_tick_font_size', 9))
        layout.addRow("Tick Font Size:", self.hist_axis_tick_font_spin)

        # Tooltip style
        from styles.plot_styles import PopupStyles
        self.popup_style_combo = QComboBox()
        self.popup_style_combo.addItems(list(PopupStyles.STYLES.keys()))
        self.popup_style_combo.setCurrentText(getattr(self.main_window, 'current_popup_style', 'Clean'))
        layout.addRow("Tooltip Style:", self.popup_style_combo)

        return widget

    def _create_rose_tab(self):
        """Create rose diagram-specific options tab."""
        widget = QWidget()
        layout = QFormLayout(widget)
        layout.setSpacing(12)

        # Title label
        self.rose_title_edit = QLineEdit()
        self.rose_title_edit.setText("Gradient Direction Distribution")
        layout.addRow("Title:", self.rose_title_edit)

        # Axis label font size
        self.rose_axis_label_font_spin = QSpinBox()
        self.rose_axis_label_font_spin.setRange(8, 20)
        self.rose_axis_label_font_spin.setValue(getattr(self.main_window, 'axis_label_font_size', 11))
        layout.addRow("Label Font Size:", self.rose_axis_label_font_spin)

        # Axis tick font size
        self.rose_axis_tick_font_spin = QSpinBox()
        self.rose_axis_tick_font_spin.setRange(6, 18)
        self.rose_axis_tick_font_spin.setValue(getattr(self.main_window, 'axis_tick_font_size', 9))
        layout.addRow("Tick Font Size:", self.rose_axis_tick_font_spin)

        # Tooltip style
        from styles.plot_styles import PopupStyles
        self.popup_style_combo = QComboBox()
        self.popup_style_combo.addItems(list(PopupStyles.STYLES.keys()))
        self.popup_style_combo.setCurrentText(getattr(self.main_window, 'current_popup_style', 'Clean'))
        layout.addRow("Tooltip Style:", self.popup_style_combo)

        return widget
        
    def _pick_color(self, button):
        """Open color picker dialog."""
        current = QColor(button.property("color"))
        color = QColorDialog.getColor(current, self, "Select Color")
        if color.isValid():
            button.setProperty("color", color.name())
            button.setStyleSheet(f"background-color: {color.name()};")
            
    def _reset_defaults(self):
        """Reset all settings to defaults."""
        # General tab
        if hasattr(self, 'marker_size_spin'):
            self.marker_size_spin.setValue(80)
        if hasattr(self, 'show_grid_check'):
            self.show_grid_check.setChecked(False)
        if hasattr(self, 'show_compass_check'):
            self.show_compass_check.setChecked(True)
        if hasattr(self, 'colormap_combo'):
            self.colormap_combo.setCurrentText('viridis')
        if hasattr(self, 'popup_style_combo'):
            self.popup_style_combo.setCurrentText('Clean')

        # Labels tab
        if hasattr(self, 'show_id_check'):
            self.show_id_check.setChecked(True)
        if hasattr(self, 'id_font_spin'):
            self.id_font_spin.setValue(9)
        if hasattr(self, 'show_head_check'):
            self.show_head_check.setChecked(True)
        if hasattr(self, 'head_font_spin'):
            self.head_font_spin.setValue(8)
        if hasattr(self, 'x_label_edit'):
            self.x_label_edit.setText("X Coordinate [m]")
        if hasattr(self, 'y_label_edit'):
            self.y_label_edit.setText("Y Coordinate [m]")
        if hasattr(self, 'label_offset_spin'):
            self.label_offset_spin.setValue(10)
        if hasattr(self, 'axis_tick_font_spin'):
            self.axis_tick_font_spin.setValue(9)
        if hasattr(self, 'axis_label_font_spin'):
            self.axis_label_font_spin.setValue(11)

        # Colors tab
        if hasattr(self, 'id_color_btn'):
            self.id_color_btn.setProperty("color", "#818cf8")
            self.id_color_btn.setStyleSheet("background-color: #818cf8;")
        if hasattr(self, 'head_color_btn'):
            self.head_color_btn.setProperty("color", "#a0a0a0")
            self.head_color_btn.setStyleSheet("background-color: #a0a0a0;")
        if hasattr(self, 'arrow_color_btn'):
            self.arrow_color_btn.setProperty("color", "#818cf8")
            self.arrow_color_btn.setStyleSheet("background-color: #818cf8;")

        # 2D tab
        if hasattr(self, 'show_contours_check'):
            self.show_contours_check.setChecked(False)
        if hasattr(self, 'show_colorbar_check'):
            self.show_colorbar_check.setChecked(True)
        if hasattr(self, 'show_arrow_check'):
            self.show_arrow_check.setChecked(True)
        if hasattr(self, 'show_arrow_label_check'):
            self.show_arrow_label_check.setChecked(True)
        if hasattr(self, 'interp_combo'):
            self.interp_combo.setCurrentText('cubic')
        if hasattr(self, 'arrow_x_edit'):
            self.arrow_x_edit.setText("")
        if hasattr(self, 'arrow_y_edit'):
            self.arrow_y_edit.setText("")

        # 3D tab
        if hasattr(self, 'surface_alpha_slider'):
            self.surface_alpha_slider.setValue(80)
        if hasattr(self, 'show_wireframe_check'):
            self.show_wireframe_check.setChecked(False)

        # Contour tab
        if hasattr(self, 'contour_linewidth_spin'):
            self.contour_linewidth_spin.setValue(0.8)
        if hasattr(self, 'contour_label_font_spin'):
            self.contour_label_font_spin.setValue(9)

        # Vectors tab
        if hasattr(self, 'show_vector_id_check'):
            self.show_vector_id_check.setChecked(False)
        if hasattr(self, 'vector_count_spin'):
            self.vector_count_spin.setValue(500)
        if hasattr(self, 'scale_spin'):
            self.scale_spin.setValue(50.0)
        if hasattr(self, 'alpha_slider'):
            self.alpha_slider.setValue(70)
        if hasattr(self, 'show_points_check'):
            self.show_points_check.setChecked(True)

        # Advanced calculation defaults (Excel)
        if hasattr(self, 'head_uncertainty_spin'):
            self.head_uncertainty_spin.setValue(0.01)
        if hasattr(self, 'confidence_spin'):
            self.confidence_spin.setValue(66.0)
        if hasattr(self, 'ratio_low_spin'):
            self.ratio_low_spin.setValue(0.2)
        if hasattr(self, 'ratio_high_spin'):
            self.ratio_high_spin.setValue(8.0)
        if hasattr(self, 'max_base_height_spin'):
            self.max_base_height_spin.setValue(1e9)
        if hasattr(self, 'stacked_epsilon_spin'):
            self.stacked_epsilon_spin.setValue(1e-10)

        
    def _apply(self):
        """Apply the settings."""
        dataset = self.main_window.get_active_dataset() if hasattr(self.main_window, "get_active_dataset") else None

        # General settings
        if hasattr(self, 'show_grid_check'):
            self.main_window.show_grid = self.show_grid_check.isChecked()
        if hasattr(self, 'show_compass_check'):
            self.main_window.show_compass = self.show_compass_check.isChecked()
        if hasattr(self, 'marker_size_spin'):
            self.main_window.marker_size = self.marker_size_spin.value()
        if hasattr(self, 'popup_style_combo'):
            self.main_window.current_popup_style = self.popup_style_combo.currentText()

        # Label settings
        if hasattr(self, 'show_id_check'):
            self.main_window.show_id_labels = self.show_id_check.isChecked()
        if hasattr(self, 'show_head_check'):
            self.main_window.show_head_labels = self.show_head_check.isChecked()
        if hasattr(self, 'id_font_spin'):
            self.main_window.id_font_size = self.id_font_spin.value()
        if hasattr(self, 'head_font_spin'):
            self.main_window.head_font_size = self.head_font_spin.value()
        if hasattr(self, 'x_label_edit'):
            self.main_window.x_axis_label = self.x_label_edit.text()
        if hasattr(self, 'y_label_edit'):
            self.main_window.y_axis_label = self.y_label_edit.text()
        if hasattr(self, 'label_offset_spin'):
            self.main_window.label_offset = self.label_offset_spin.value()
        if hasattr(self, 'axis_tick_font_spin'):
            self.main_window.axis_tick_font_size = self.axis_tick_font_spin.value()
        if hasattr(self, 'axis_label_font_spin'):
            self.main_window.axis_label_font_size = self.axis_label_font_spin.value()

        # Color settings
        if hasattr(self, 'id_color_btn'):
            self.main_window.id_label_color = self.id_color_btn.property("color")
        if hasattr(self, 'head_color_btn'):
            self.main_window.head_label_color = self.head_color_btn.property("color")
        if hasattr(self, 'arrow_color_btn'):
            self.main_window.arrow_color = self.arrow_color_btn.property("color")

        # 2D-specific settings
        if hasattr(self, 'show_contours_check'):
            self.main_window.show_contours = self.show_contours_check.isChecked()
        if hasattr(self, 'show_colorbar_check'):
            self.main_window.show_colorbar = self.show_colorbar_check.isChecked()
        if hasattr(self, 'show_arrow_check'):
            self.main_window.show_arrow = self.show_arrow_check.isChecked()
        if hasattr(self, 'show_arrow_label_check'):
            self.main_window.show_arrow_label = self.show_arrow_label_check.isChecked()
        if hasattr(self, 'arrow_x_edit'):
            text = self.arrow_x_edit.text().strip()
            self.main_window.arrow_start_x = float(text) if text else None
        if hasattr(self, 'arrow_y_edit'):
            text = self.arrow_y_edit.text().strip()
            self.main_window.arrow_start_y = float(text) if text else None
        if hasattr(self, 'interp_combo'):
            self.main_window.interpolation_method = self.interp_combo.currentText()

        # 3D-specific settings
        if hasattr(self, 'surface_alpha_slider'):
            self.main_window.surface_alpha = self.surface_alpha_slider.value() / 100.0
        if hasattr(self, 'show_wireframe_check'):
            self.main_window.show_wireframe = self.show_wireframe_check.isChecked()

        # Contour-specific settings
        if hasattr(self, 'contour_linewidth_spin'):
            self.main_window.contour_linewidth = self.contour_linewidth_spin.value()
        if hasattr(self, 'contour_label_font_spin'):
            self.main_window.contour_label_font_size = self.contour_label_font_spin.value()

        # Vector-specific settings
        if hasattr(self, 'show_vector_id_check'):
            self.main_window.show_vector_id_labels = self.show_vector_id_check.isChecked()
        if hasattr(self, 'vector_count_spin'):
            self.main_window.max_vector_count = self.vector_count_spin.value()
        if hasattr(self, 'scale_spin'):
            self.main_window.vector_scale = self.scale_spin.value()
        if hasattr(self, 'alpha_slider'):
            self.main_window.vector_alpha = self.alpha_slider.value() / 100.0
        if hasattr(self, 'show_points_check'):
            self.main_window.show_vector_points = self.show_points_check.isChecked()

        if dataset is not None and hasattr(self.main_window, "sync_to_dataset"):
            self.main_window.sync_to_dataset(dataset)

        self.main_window.update_plot()

        self.accept()

    def _create_advanced_calculation_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)

        info = QLabel(
            "These settings control which triangles are rejected during gradient calculation.\n"
            "Changing them recomputes gradients for the current dataset."
        )
        info.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 10px;")
        info.setWordWrap(True)
        layout.addWidget(info)

        form = QFormLayout()
        form.setSpacing(10)
        layout.addLayout(form)

        self.head_uncertainty_spin = QDoubleSpinBox()
        self.head_uncertainty_spin.setDecimals(4)
        self.head_uncertainty_spin.setRange(0.0, 10.0)
        self.head_uncertainty_spin.setSingleStep(0.005)
        self.head_uncertainty_spin.setValue(float(getattr(self.main_window, "gradient_head_uncertainty", 0.01)))
        form.addRow("± on head (L):", self.head_uncertainty_spin)

        self.confidence_spin = QDoubleSpinBox()
        self.confidence_spin.setDecimals(1)
        self.confidence_spin.setRange(1.0, 99.9)
        self.confidence_spin.setSingleStep(1.0)
        self.confidence_spin.setSuffix(" %")
        self.confidence_spin.setValue(float(getattr(self.main_window, "gradient_confidence_level", 0.66)) * 100.0)
        form.addRow("Confidence level:", self.confidence_spin)

        self.ratio_low_spin = QDoubleSpinBox()
        self.ratio_low_spin.setDecimals(3)
        self.ratio_low_spin.setRange(0.0, 100.0)
        self.ratio_low_spin.setSingleStep(0.05)
        self.ratio_low_spin.setValue(float(getattr(self.main_window, "gradient_base_height_low", 0.2)))
        form.addRow("Base:Height low:", self.ratio_low_spin)

        self.ratio_high_spin = QDoubleSpinBox()
        self.ratio_high_spin.setDecimals(3)
        self.ratio_high_spin.setRange(0.0, 1e6)
        self.ratio_high_spin.setSingleStep(0.5)
        self.ratio_high_spin.setValue(float(getattr(self.main_window, "gradient_base_height_high", 8.0)))
        form.addRow("Base:Height high:", self.ratio_high_spin)

        self.max_base_height_spin = QDoubleSpinBox()
        self.max_base_height_spin.setDecimals(0)
        self.max_base_height_spin.setRange(0.0, 1e12)
        self.max_base_height_spin.setSingleStep(1000.0)
        self.max_base_height_spin.setValue(float(getattr(self.main_window, "gradient_max_base_or_height", 1e9)))
        form.addRow("Max base or height (L):", self.max_base_height_spin)

        self.stacked_epsilon_spin = QDoubleSpinBox()
        self.stacked_epsilon_spin.setDecimals(12)
        self.stacked_epsilon_spin.setRange(0.0, 1.0)
        self.stacked_epsilon_spin.setSingleStep(1e-10)
        self.stacked_epsilon_spin.setValue(float(getattr(self.main_window, "gradient_stacked_epsilon", 1e-10)))
        form.addRow("Stacked point epsilon:", self.stacked_epsilon_spin)

        note = QLabel("Note: Confidence level is stored but not currently used in the calculation.")
        note.setStyleSheet(f"color: {Colors.TEXT_TERTIARY}; font-size: 9px; font-style: italic;")
        note.setWordWrap(True)
        layout.addWidget(note)

        layout.addStretch(1)
        return widget
