"""
HeadAnalyser V2 - Calculation Settings Dialog
Dialog for triangle constraint settings used during gradient calculation.

Modernized to match HeadAnalyser V2 design system.
"""

from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFormLayout,
    QDoubleSpinBox,
    QCheckBox,
    QPushButton,
    QWidget,
)
from PyQt5.QtCore import Qt

from styles.colors import Colors
from ui.common_widgets import SectionHeader
from ui.icons import Icons
from qt_chrome import FramelessDialogMixin


def _danger_text() -> str:
    return Colors.ERROR_LIGHT if Colors.is_dark() else Colors.ERROR_DARK


class CalculationSettingsDialog(FramelessDialogMixin, QDialog):
    """Dialog for editing triangle constraint settings (per dataset, optionally global)."""

    def __init__(self, main_window, parent=None):
        super().__init__(parent or main_window)
        self.main_window = main_window

        self.setWindowTitle("Calculation Settings")
        self.resize(640, 580)
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

        title = QLabel("Calculation Settings")
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

        # ── Content ──
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

        info_icon = QLabel("⚙️")
        info_icon.setStyleSheet(f"font-size: 18px; background: transparent; border: none;")
        info_layout.addWidget(info_icon)

        info_text = QLabel(
            "These settings control which triangles are rejected during gradient calculation. "
            "They apply per dataset unless you choose to apply them globally."
        )
        info_text.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 12px; background: transparent; border: none;")
        info_text.setWordWrap(True)
        info_layout.addWidget(info_text, 1)

        content_layout.addWidget(info_banner)

        # ── Triangle Constraints Section ──
        constraints_section = SectionHeader("Triangle Constraints", Icons.SLIDERS)
        content_layout.addWidget(constraints_section)

        form = QFormLayout()
        form.setSpacing(14)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        # Head uncertainty
        self.head_uncertainty_spin = QDoubleSpinBox()
        self.head_uncertainty_spin.setDecimals(4)
        self.head_uncertainty_spin.setRange(0.0, 10.0)
        self.head_uncertainty_spin.setSingleStep(0.005)
        self.head_uncertainty_spin.setValue(float(getattr(self.main_window, "gradient_head_uncertainty", 0.01)))
        self.head_uncertainty_spin.setObjectName("styled_spinbox")
        form.addRow("σₙ on head (L):", self.head_uncertainty_spin)

        # Confidence level
        self.confidence_spin = QDoubleSpinBox()
        self.confidence_spin.setDecimals(1)
        self.confidence_spin.setRange(1.0, 99.9)
        self.confidence_spin.setSingleStep(1.0)
        self.confidence_spin.setSuffix(" %")
        self.confidence_spin.setValue(float(getattr(self.main_window, "gradient_confidence_level", 0.66)) * 100.0)
        self.confidence_spin.setObjectName("styled_spinbox")
        form.addRow("Confidence level:", self.confidence_spin)

        # Base:Height low
        self.ratio_low_spin = QDoubleSpinBox()
        self.ratio_low_spin.setDecimals(3)
        self.ratio_low_spin.setRange(0.0, 100.0)
        self.ratio_low_spin.setSingleStep(0.05)
        self.ratio_low_spin.setValue(float(getattr(self.main_window, "gradient_base_height_low", 0.2)))
        self.ratio_low_spin.setObjectName("styled_spinbox")
        form.addRow("Base:Height (min):", self.ratio_low_spin)

        # Base:Height high
        self.ratio_high_spin = QDoubleSpinBox()
        self.ratio_high_spin.setDecimals(3)
        self.ratio_high_spin.setRange(0.0, 1e6)
        self.ratio_high_spin.setSingleStep(0.5)
        self.ratio_high_spin.setValue(float(getattr(self.main_window, "gradient_base_height_high", 8.0)))
        self.ratio_high_spin.setObjectName("styled_spinbox")
        form.addRow("Base:Height (max):", self.ratio_high_spin)

        # Max base or height
        self.max_base_height_spin = QDoubleSpinBox()
        self.max_base_height_spin.setDecimals(0)
        self.max_base_height_spin.setRange(0.0, 1e12)
        self.max_base_height_spin.setSingleStep(1000.0)
        self.max_base_height_spin.setValue(float(getattr(self.main_window, "gradient_max_base_or_height", 1e9)))
        self.max_base_height_spin.setObjectName("styled_spinbox")
        form.addRow("Max base or height (L):", self.max_base_height_spin)

        # Stacked point epsilon
        self.stacked_epsilon_spin = QDoubleSpinBox()
        self.stacked_epsilon_spin.setDecimals(12)
        self.stacked_epsilon_spin.setRange(0.0, 1.0)
        self.stacked_epsilon_spin.setSingleStep(1e-10)
        self.stacked_epsilon_spin.setValue(float(getattr(self.main_window, "gradient_stacked_epsilon", 1e-10)))
        self.stacked_epsilon_spin.setObjectName("styled_spinbox")
        form.addRow("Stacked point epsilon:", self.stacked_epsilon_spin)

        constraints_section.contentLayout().addLayout(form)

        # Apply globally checkbox
        self.apply_global_check = QCheckBox("Apply to all datasets (and set as default)")
        self.apply_global_check.setCursor(Qt.PointingHandCursor)
        constraints_section.contentLayout().addWidget(self.apply_global_check)

        # Note about confidence level
        note = QLabel("⚠ Note: Confidence level is stored but not currently used in the calculation.")
        note.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: 11px; font-style: italic; background: transparent; border: none; padding: 4px 0;")
        note.setWordWrap(True)
        constraints_section.contentLayout().addWidget(note)

        content_layout.addStretch()

        root.addWidget(content, 1)

        # ── Footer with Buttons ──
        footer = QWidget()
        footer.setObjectName("dialog_footer")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(24, 16, 24, 16)
        footer_layout.setSpacing(12)

        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.setObjectName("btn_secondary")
        reset_btn.setCursor(Qt.PointingHandCursor)
        reset_btn.clicked.connect(self._reset_to_defaults)
        footer_layout.addWidget(reset_btn)

        footer_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("btn_secondary")
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        footer_layout.addWidget(cancel_btn)

        apply_btn = QPushButton("Apply")
        apply_btn.setObjectName("btn_primary")
        apply_btn.setCursor(Qt.PointingHandCursor)
        apply_btn.clicked.connect(self._apply)
        footer_layout.addWidget(apply_btn)

        root.addWidget(footer)

    def _apply_styles(self):
        """Apply modern styling to the dialog."""
        self.setStyleSheet(f"""
            QDialog {{
                background: {Colors.BG_MODAL};
            }}

            /* Header */
            #dialog_header {{
                background: {Colors.GRADIENT_HEADER};
                border-bottom: 1px solid {Colors.BORDER_ACCENT};
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
                background: {Colors.rgba(Colors.ERROR, 0.15)};
                border-color: {Colors.rgba(Colors.ERROR, 0.30)};
                color: {_danger_text()};
            }}
            #close_btn:pressed {{
                background: {Colors.rgba(Colors.ERROR, 0.25)};
            }}

            /* Info banner */
            #info_banner {{
                background: {Colors.ACCENT_GHOST};
                border: 1px solid {Colors.BORDER_ACCENT};
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
                background: {Colors.ACCENT_GHOST};
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
                padding: 8px 12px;
                color: {Colors.TEXT_PRIMARY};
                font-size: 13px;
                min-width: 160px;
            }}
            #styled_spinbox:focus {{
                border-color: {Colors.ACCENT_PRIMARY};
                background: {Colors.BG_ELEVATED};
            }}
            #styled_spinbox::up-button, #styled_spinbox::down-button {{
                background: {Colors.BG_HOVER};
                border: none;
                border-radius: 4px;
                width: 20px;
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
                color: {Colors.TEXT_INVERSE};
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
                background: {Colors.GRADIENT_BUTTON};
                border-color: {Colors.BORDER_MEDIUM};
                color: {Colors.TEXT_SECONDARY};
            }}
            #btn_secondary:hover {{
                background: {Colors.GRADIENT_SURFACE};
                border-color: {Colors.ACCENT_PRIMARY};
                color: {Colors.TEXT_PRIMARY};
            }}
        """)

    def _reset_to_defaults(self):
        """Reset all values to defaults."""
        defaults = getattr(self.main_window, "default_gradient_settings", {}) or {}
        self.head_uncertainty_spin.setValue(float(defaults.get("gradient_head_uncertainty", 0.01)))
        self.confidence_spin.setValue(float(defaults.get("gradient_confidence_level", 0.66)) * 100.0)
        self.ratio_low_spin.setValue(float(defaults.get("gradient_base_height_low", 0.2)))
        self.ratio_high_spin.setValue(float(defaults.get("gradient_base_height_high", 8.0)))
        self.max_base_height_spin.setValue(float(defaults.get("gradient_max_base_or_height", 1e9)))
        self.stacked_epsilon_spin.setValue(float(defaults.get("gradient_stacked_epsilon", 1e-10)))

    def _apply(self):
        """Apply the settings and close the dialog."""
        settings = {
            "gradient_head_uncertainty": float(self.head_uncertainty_spin.value()),
            "gradient_confidence_level": float(self.confidence_spin.value()) / 100.0,
            "gradient_base_height_low": float(self.ratio_low_spin.value()),
            "gradient_base_height_high": float(self.ratio_high_spin.value()),
            "gradient_max_base_or_height": float(self.max_base_height_spin.value()),
            "gradient_stacked_epsilon": float(self.stacked_epsilon_spin.value()),
        }
        self.main_window.apply_calculation_settings(settings, apply_globally=bool(self.apply_global_check.isChecked()))
        self.accept()
