"""
HeadAnalyser V2 - Report Composer View.

Dataset-scoped report workspace inspired by the Kornstoerrelse reporting tab,
implemented natively for the HeadAnalyser PyQt5 UI and existing PDF generator.
"""

from __future__ import annotations

import os
import re
from html import escape
from typing import Dict, List

from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from styles.colors import Colors
from ui.icons import Icons, icon
from ui.loading_dialog import LoadingDialog
from ui.report_html_builder import HeadReportHtmlBuilder
from ui.scaling import build_screen_metrics

try:
    from PyQt5.QtWebEngineWidgets import QWebEngineView
    HAS_WEBENGINE = True
    WEBENGINE_IMPORT_ERROR = ""
except Exception as exc:
    QWebEngineView = None
    HAS_WEBENGINE = False
    WEBENGINE_IMPORT_ERROR = str(exc)


class _ReportSection(QFrame):
    """Compact collapsible section used by the report composer."""

    def __init__(self, title: str, icon_name: str, parent=None, expanded: bool = True):
        super().__init__(parent)
        self.icon_name = icon_name
        self.setObjectName("reportSection")
        self.setAttribute(Qt.WA_StyledBackground, True)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.header = QWidget()
        self.header.setObjectName("reportSectionHeader")
        self.header.setCursor(Qt.PointingHandCursor)
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(12, 8, 12, 8)
        header_layout.setSpacing(9)

        self.icon_label = QLabel()
        self.icon_label.setFixedSize(16, 16)
        self.icon_label.setObjectName("reportSectionIcon")
        header_layout.addWidget(self.icon_label)

        title_label = QLabel(title)
        title_label.setObjectName("reportSectionTitle")
        header_layout.addWidget(title_label, 1)

        self.toggle = QToolButton()
        self.toggle.setObjectName("reportSectionToggle")
        self.toggle.setCheckable(True)
        self.toggle.setChecked(expanded)
        self.toggle.setCursor(Qt.PointingHandCursor)
        self.toggle.clicked.connect(self._sync_state)
        header_layout.addWidget(self.toggle)

        self.body = QWidget()
        self.body.setObjectName("reportSectionBody")
        self._body_layout = QVBoxLayout(self.body)
        self._body_layout.setContentsMargins(12, 4, 12, 12)
        self._body_layout.setSpacing(8)

        root.addWidget(self.header)
        root.addWidget(self.body)

        self.header.mousePressEvent = self._on_header_pressed  # type: ignore[assignment]
        self._sync_state()
        self.apply_theme()

    def content_layout(self) -> QVBoxLayout:
        return self._body_layout

    def _on_header_pressed(self, event):
        if event.button() == Qt.LeftButton:
            self.toggle.setChecked(not self.toggle.isChecked())
            self._sync_state()
            event.accept()
            return
        super().mousePressEvent(event)

    def _sync_state(self, *_args):
        is_open = self.toggle.isChecked()
        self.body.setVisible(is_open)
        self.toggle.setArrowType(Qt.DownArrow if is_open else Qt.RightArrow)

    def apply_theme(self):
        self.icon_label.setPixmap(icon(self.icon_name, color=Colors.ACCENT_PRIMARY).pixmap(16, 16))


class ReportView(QWidget):
    """Dataset-level PDF report composer."""

    PLOT_TYPES = [
        "2D Hydraulic Head",
        "3D Surface",
        "Gradient Vectors",
        "Gradient Histogram",
        "Rose Diagram",
    ]

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self._plot_checks: Dict[str, QCheckBox] = {}
        self._sections: List[_ReportSection] = []
        self._outline_rows: List[QLabel] = []
        self.current_report_html = ""
        self._pending_pdf_path = ""
        self._preview_loaded = False
        self._pdf_export_dialog = None

        self.setObjectName("reportView")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._setup_ui()
        self._connect_setting_signals()
        self.apply_theme()
        self.refresh_from_main_window()

    def _setup_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setObjectName("reportSplitter")
        root.addWidget(self.splitter)

        self.composer_panel = self._build_composer_panel()
        self.preview_panel = self._build_preview_panel()
        self.splitter.addWidget(self.composer_panel)
        self.splitter.addWidget(self.preview_panel)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)

    def _build_composer_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("reportComposer")
        panel.setMinimumWidth(320)
        panel.setMaximumWidth(430)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 18, 18, 16)
        layout.setSpacing(12)

        title_row = QHBoxLayout()
        title_row.setSpacing(10)

        icon_label = QLabel()
        icon_label.setObjectName("reportTitleIcon")
        icon_label.setFixedSize(22, 22)
        self.title_icon_label = icon_label
        title_row.addWidget(icon_label)

        title_col = QVBoxLayout()
        title_col.setSpacing(1)
        title = QLabel("Report Composer")
        title.setObjectName("reportComposerTitle")
        title_col.addWidget(title)
        subtitle = QLabel("Configure the PDF contents for the active dataset.")
        subtitle.setObjectName("reportComposerSubtitle")
        subtitle.setWordWrap(True)
        title_col.addWidget(subtitle)
        title_row.addLayout(title_col, 1)
        layout.addLayout(title_row)

        scroll = QScrollArea()
        scroll.setObjectName("reportComposerScroll")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.NoFrame)

        content = QWidget()
        content.setObjectName("reportComposerContent")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(10)

        details = self._add_section(content_layout, "Document Details", Icons.REPORT, expanded=True)
        details_form = QFormLayout()
        details_form.setContentsMargins(0, 0, 0, 0)
        details_form.setSpacing(8)
        details_form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self.project_title_edit = self._line_edit("Hydraulic Gradient Analysis Report")
        self.project_number_edit = self._line_edit("Optional project number")
        self.analyst_edit = self._line_edit("Optional analyst")
        self.client_edit = self._line_edit("Optional client")
        details_form.addRow("Title", self.project_title_edit)
        details_form.addRow("Project", self.project_number_edit)
        details_form.addRow("Analyst", self.analyst_edit)
        details_form.addRow("Client", self.client_edit)
        details.content_layout().addLayout(details_form)

        self.notes_edit = QTextEdit()
        self.notes_edit.setObjectName("reportTextEdit")
        self.notes_edit.setPlaceholderText("Optional report note for the title page")
        self.notes_edit.setAcceptRichText(False)
        self.notes_edit.setFixedHeight(68)
        details.content_layout().addWidget(self.notes_edit)

        plots = self._add_section(content_layout, "Plots", Icons.CHART_LINE, expanded=True)
        for plot_name in self.PLOT_TYPES:
            checked = plot_name == "2D Hydraulic Head"
            checkbox = self._check(plot_name, checked=checked)
            self._plot_checks[plot_name] = checkbox
            plots.content_layout().addWidget(checkbox)

        sections = self._add_section(content_layout, "Statistics And Tables", Icons.TABLE, expanded=True)
        self.include_general_stats = self._check("General point statistics", checked=True)
        self.include_gradient_stats = self._check("Gradient statistics", checked=True)
        self.include_valid_table = self._check("Valid results table", checked=True)
        self.include_rejected_table = self._check("Rejected results table", checked=True)
        self.include_rejection_analysis = self._check("Rejected points analysis", checked=False)
        for checkbox in (
            self.include_general_stats,
            self.include_gradient_stats,
            self.include_valid_table,
            self.include_rejected_table,
            self.include_rejection_analysis,
        ):
            sections.content_layout().addWidget(checkbox)

        layout_section = self._add_section(content_layout, "Layout And Quality", Icons.SETTINGS, expanded=True)
        layout_form = QFormLayout()
        layout_form.setContentsMargins(0, 0, 0, 0)
        layout_form.setSpacing(8)
        layout_form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self.dpi_spin = QSpinBox()
        self.dpi_spin.setObjectName("reportSpinBox")
        self.dpi_spin.setRange(72, 600)
        self.dpi_spin.setValue(200)
        self.dpi_spin.setSuffix(" dpi")

        self.width_spin = QDoubleSpinBox()
        self.width_spin.setObjectName("reportSpinBox")
        self.width_spin.setRange(3.0, 20.0)
        self.width_spin.setSingleStep(0.5)
        self.width_spin.setValue(8.0)
        self.width_spin.setSuffix(' "')

        self.height_spin = QDoubleSpinBox()
        self.height_spin.setObjectName("reportSpinBox")
        self.height_spin.setRange(3.0, 20.0)
        self.height_spin.setSingleStep(0.5)
        self.height_spin.setValue(5.5)
        self.height_spin.setSuffix(' "')

        self.row_limit_combo = QComboBox()
        self.row_limit_combo.setObjectName("reportCombo")
        self.row_limit_combo.addItems(["All", "50", "100", "250", "500"])
        self.row_limit_combo.setCurrentText("100")
        self.row_limit_combo.setCursor(Qt.PointingHandCursor)

        layout_form.addRow("DPI", self.dpi_spin)
        layout_form.addRow("Width", self.width_spin)
        layout_form.addRow("Height", self.height_spin)
        layout_form.addRow("Rows", self.row_limit_combo)
        layout_section.content_layout().addLayout(layout_form)

        self.landscape_check = self._check("Use landscape orientation for plots", checked=True)
        layout_section.content_layout().addWidget(self.landscape_check)

        map_section = self._add_section(content_layout, "Location Map", "fa6s.map-location-dot", expanded=False)
        self.include_map_check = self._check("Include location map if coordinates are available", checked=False)
        map_section.content_layout().addWidget(self.include_map_check)
        self.map_style_combo = QComboBox()
        self.map_style_combo.setObjectName("reportCombo")
        self.map_style_combo.addItems(["OpenStreetMap"])
        self.map_style_combo.setCursor(Qt.PointingHandCursor)
        map_section.content_layout().addWidget(self.map_style_combo)
        map_note = QLabel("Map image export depends on optional map rendering dependencies.")
        map_note.setObjectName("reportNote")
        map_note.setWordWrap(True)
        map_section.content_layout().addWidget(map_note)

        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

        footer = QWidget()
        footer.setObjectName("reportComposerFooter")
        footer_layout = QVBoxLayout(footer)
        footer_layout.setContentsMargins(0, 12, 0, 0)
        footer_layout.setSpacing(8)

        self.generate_button = QPushButton("Generate Preview")
        self.generate_button.setObjectName("reportGenerateButton")
        self.generate_button.setCursor(Qt.PointingHandCursor)
        self.generate_button.clicked.connect(self.generate_preview)
        footer_layout.addWidget(self.generate_button)

        self.status_hint = QLabel("")
        self.status_hint.setObjectName("reportStatusHint")
        self.status_hint.setWordWrap(True)
        footer_layout.addWidget(self.status_hint)

        layout.addWidget(footer)
        return panel

    def _build_preview_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("reportPreview")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        topbar = QWidget()
        topbar.setObjectName("reportPreviewTopbar")
        top = QHBoxLayout()
        topbar.setLayout(top)
        top.setContentsMargins(16, 0, 16, 0)
        top.setSpacing(8)
        title_col = QVBoxLayout()
        title_col.setSpacing(0)
        title = QLabel("Document Preview")
        title.setObjectName("reportPreviewTitle")
        title_col.addWidget(title)
        self.preview_subtitle = QLabel("Generate a preview, then save the exact rendered document as PDF.")
        self.preview_subtitle.setObjectName("reportPreviewSubtitle")
        self.preview_subtitle.setWordWrap(True)
        title_col.addWidget(self.preview_subtitle)
        top.addLayout(title_col, 1)

        refresh = QPushButton("Refresh")
        refresh.setObjectName("reportSecondaryButton")
        refresh.setCursor(Qt.PointingHandCursor)
        refresh.clicked.connect(self.generate_preview)
        self.refresh_button = refresh
        top.addWidget(refresh)

        self.save_pdf_button = QPushButton("Save PDF")
        self.save_pdf_button.setObjectName("reportPrimaryPreviewButton")
        self.save_pdf_button.setCursor(Qt.PointingHandCursor)
        self.save_pdf_button.clicked.connect(self.save_preview_pdf)
        top.addWidget(self.save_pdf_button)

        self.save_html_button = QPushButton("Save HTML")
        self.save_html_button.setObjectName("reportSecondaryButton")
        self.save_html_button.setCursor(Qt.PointingHandCursor)
        self.save_html_button.clicked.connect(self.save_preview_html)
        top.addWidget(self.save_html_button)

        layout.addWidget(topbar)

        canvas = QWidget()
        canvas.setObjectName("reportPreviewCanvas")
        canvas_layout = QVBoxLayout(canvas)
        canvas_layout.setContentsMargins(22, 22, 22, 22)
        canvas_layout.setSpacing(0)

        if HAS_WEBENGINE:
            self.web_view = QWebEngineView()
            self.web_view.setObjectName("reportWebPreview")
            self.web_view.setHtml(self._empty_preview_html())
            try:
                self.web_view.loadFinished.connect(self._on_preview_load_finished)
                self.web_view.page().pdfPrintingFinished.connect(self._on_pdf_done)
            except Exception:
                pass
        else:
            self.web_view = QTextEdit()
            self.web_view.setObjectName("reportWebPreviewFallback")
            self.web_view.setReadOnly(True)
            self.web_view.setHtml(self._empty_preview_html(
                "WebEngine preview unavailable",
                WEBENGINE_IMPORT_ERROR or "PyQtWebEngine could not be imported.",
            ))
        canvas_layout.addWidget(self.web_view)
        layout.addWidget(canvas, 1)

        return panel

    def _add_section(
        self,
        parent_layout: QVBoxLayout,
        title: str,
        icon_name: str,
        expanded: bool = True,
    ) -> _ReportSection:
        section = _ReportSection(title, icon_name, self, expanded=expanded)
        self._sections.append(section)
        parent_layout.addWidget(section)
        return section

    def _line_edit(self, placeholder: str) -> QLineEdit:
        widget = QLineEdit()
        widget.setObjectName("reportLineEdit")
        widget.setPlaceholderText(placeholder)
        return widget

    def _check(self, label: str, checked: bool = False) -> QCheckBox:
        checkbox = QCheckBox(label)
        checkbox.setChecked(checked)
        checkbox.setCursor(Qt.PointingHandCursor)
        checkbox.setObjectName("reportCheck")
        return checkbox

    def _connect_setting_signals(self):
        for checkbox in list(self._plot_checks.values()) + [
            self.include_general_stats,
            self.include_gradient_stats,
            self.include_valid_table,
            self.include_rejected_table,
            self.include_rejection_analysis,
            self.landscape_check,
            self.include_map_check,
        ]:
            checkbox.toggled.connect(self._on_settings_changed)

        for widget in (
            self.project_title_edit,
            self.project_number_edit,
            self.analyst_edit,
            self.client_edit,
        ):
            widget.textChanged.connect(self._on_settings_changed)
        self.notes_edit.textChanged.connect(self._on_settings_changed)
        self.dpi_spin.valueChanged.connect(self._on_settings_changed)
        self.width_spin.valueChanged.connect(self._on_settings_changed)
        self.height_spin.valueChanged.connect(self._on_settings_changed)
        self.row_limit_combo.currentTextChanged.connect(self._on_settings_changed)
        self.map_style_combo.currentTextChanged.connect(self._on_settings_changed)

    def refresh_from_main_window(self):
        self._update_preview()

    def apply_theme(self):
        metrics = build_screen_metrics(self)
        composer_width = 340 if metrics.density == "dense" else 370
        self.composer_panel.setMinimumWidth(max(310, composer_width - 35))
        self.composer_panel.setMaximumWidth(composer_width + 50)
        self.generate_button.setMinimumHeight(max(32, metrics.toolbar_control_height + 4))
        self.refresh_button.setMinimumHeight(max(28, metrics.toolbar_control_height))
        self.save_pdf_button.setMinimumHeight(max(28, metrics.toolbar_control_height))
        self.save_html_button.setMinimumHeight(max(28, metrics.toolbar_control_height))
        self.title_icon_label.setPixmap(icon(Icons.REPORT, color=Colors.ACCENT_PRIMARY).pixmap(22, 22))
        self.generate_button.setIcon(icon(Icons.REPORT, color=Colors.TEXT_INVERSE))
        self.refresh_button.setIcon(icon(Icons.RESET, color=Colors.TEXT_SECONDARY))
        self.save_pdf_button.setIcon(icon(Icons.EXPORT, color=Colors.TEXT_INVERSE))
        self.save_html_button.setIcon(icon(Icons.SAVE, color=Colors.TEXT_SECONDARY))
        for section in self._sections:
            section.apply_theme()

        border = Colors.BORDER_DEFAULT
        self.setStyleSheet(f"""
            #reportView {{
                background: {Colors.BG_PANEL};
            }}
            #reportComposer {{
                background: {Colors.BG_ELEVATED};
                border-right: 1px solid {border};
            }}
            #reportPreview {{
                background: {Colors.BG_PANEL};
            }}
            #reportPreviewTopbar {{
                background: {Colors.BG_ELEVATED};
                border-bottom: 1px solid {Colors.BORDER_DEFAULT};
                min-height: 58px;
            }}
            #reportPreviewCanvas {{
                background: {Colors.BG_SURFACE};
            }}
            #reportWebPreview {{
                background: #ffffff;
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: {Colors.RADIUS_LG};
            }}
            #reportWebPreviewFallback {{
                background: #ffffff;
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: {Colors.RADIUS_LG};
                color: #1f2937;
                padding: 12px;
            }}
            #reportComposerScroll {{
                background: transparent;
                border: none;
            }}
            #reportComposerContent {{
                background: transparent;
            }}
            #reportComposerTitle {{
                color: {Colors.TEXT_PRIMARY};
                font-size: {metrics.font_title}px;
                font-weight: 700;
                letter-spacing: -0.2px;
                background: transparent;
                border: none;
            }}
            #reportComposerSubtitle,
            #reportPreviewSubtitle,
            #reportStatusHint,
            #reportPreviewFootnote,
            #reportNote {{
                color: {Colors.TEXT_TERTIARY};
                font-size: {metrics.font_sm}px;
                background: transparent;
                border: none;
            }}
            #reportPreviewTitle {{
                color: {Colors.TEXT_PRIMARY};
                font-size: {metrics.font_xl}px;
                font-weight: 700;
                letter-spacing: -0.3px;
                background: transparent;
                border: none;
            }}
            #reportSection {{
                background: {Colors.BG_PANEL};
                border: 1px solid {border};
                border-radius: {Colors.RADIUS_LG};
            }}
            #reportSectionHeader {{
                background: transparent;
                border: none;
            }}
            #reportSectionTitle,
            #reportPanelTitle {{
                color: {Colors.TEXT_PRIMARY};
                font-size: {metrics.font_base}px;
                font-weight: 700;
                letter-spacing: 0.2px;
                background: transparent;
                border: none;
            }}
            #reportSectionToggle {{
                background: transparent;
                border: none;
                color: {Colors.TEXT_TERTIARY};
                width: 18px;
            }}
            QLineEdit#reportLineEdit,
            QTextEdit#reportTextEdit,
            QComboBox#reportCombo,
            QSpinBox#reportSpinBox,
            QDoubleSpinBox#reportSpinBox {{
                background: {Colors.BG_SURFACE};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: {Colors.RADIUS_SM};
                color: {Colors.TEXT_PRIMARY};
                min-height: {max(25, metrics.toolbar_control_height - 3)}px;
                padding: 4px 8px;
                font-size: {metrics.font_base}px;
                selection-background-color: {Colors.ACCENT_PRIMARY};
            }}
            QTextEdit#reportTextEdit {{
                padding: 8px;
            }}
            QLineEdit#reportLineEdit:focus,
            QTextEdit#reportTextEdit:focus,
            QComboBox#reportCombo:focus,
            QSpinBox#reportSpinBox:focus,
            QDoubleSpinBox#reportSpinBox:focus {{
                border-color: {Colors.BORDER_FOCUS};
            }}
            QLabel {{
                color: {Colors.TEXT_SECONDARY};
                background: transparent;
                border: none;
                font-size: {metrics.font_base}px;
            }}
            QCheckBox#reportCheck {{
                color: {Colors.TEXT_SECONDARY};
                spacing: 8px;
                padding: 4px 2px;
                font-size: {metrics.font_base}px;
                background: transparent;
                border: none;
            }}
            QCheckBox#reportCheck:hover {{
                color: {Colors.TEXT_PRIMARY};
            }}
            QCheckBox#reportCheck::indicator {{
                width: 15px;
                height: 15px;
                border: 1px solid {Colors.BORDER_MEDIUM};
                border-radius: 4px;
                background: {Colors.BG_SURFACE};
            }}
            QCheckBox#reportCheck::indicator:checked {{
                background: {Colors.ACCENT_PRIMARY};
                border-color: {Colors.ACCENT_PRIMARY};
            }}
            #reportGenerateButton {{
                background: {Colors.ACCENT_PRIMARY};
                color: {Colors.TEXT_INVERSE};
                border: none;
                border-radius: {Colors.RADIUS_MD};
                padding: 7px 12px;
                font-size: {metrics.font_md}px;
                font-weight: 700;
            }}
            #reportGenerateButton:hover {{
                background: {Colors.ACCENT_HOVER};
            }}
            #reportGenerateButton:disabled {{
                background: {Colors.STATE_DISABLED_BG};
                color: {Colors.STATE_DISABLED_TEXT};
            }}
            #reportSecondaryButton {{
                background: {Colors.BG_SURFACE};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: {Colors.RADIUS_MD};
                color: {Colors.TEXT_SECONDARY};
                padding: 5px 12px;
                font-size: {metrics.font_base}px;
                font-weight: 600;
            }}
            #reportSecondaryButton:hover {{
                background: {Colors.BG_HOVER};
                color: {Colors.TEXT_PRIMARY};
            }}
            #reportPrimaryPreviewButton {{
                background: {Colors.ACCENT_PRIMARY};
                border: 1px solid {Colors.ACCENT_PRIMARY};
                border-radius: {Colors.RADIUS_MD};
                color: {Colors.TEXT_INVERSE};
                padding: 5px 12px;
                font-size: {metrics.font_base}px;
                font-weight: 700;
            }}
            #reportPrimaryPreviewButton:hover {{
                background: {Colors.ACCENT_HOVER};
                border-color: {Colors.ACCENT_HOVER};
            }}
            #reportPrimaryPreviewButton:disabled,
            #reportSecondaryButton:disabled {{
                background: {Colors.STATE_DISABLED_BG};
                color: {Colors.STATE_DISABLED_TEXT};
                border-color: {Colors.BORDER_SUBTLE};
            }}
        """)
        self._update_preview()

    def _collect_settings(self) -> Dict[str, object]:
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
            "project_title": self.project_title_edit.text().strip(),
            "project_number": self.project_number_edit.text().strip(),
            "analyst": self.analyst_edit.text().strip(),
            "client": self.client_edit.text().strip(),
            "notes": self.notes_edit.toPlainText().strip(),
        }

    def _active_data(self):
        filtered = getattr(self.main_window, "filtered_data", None)
        if filtered is not None:
            return filtered
        return getattr(self.main_window, "data", None)

    def _update_preview(self, *_args):
        dataset = self.main_window.get_active_dataset() if self.main_window is not None else None
        data = self._active_data()
        has_data = data is not None and not getattr(data, "empty", True)

        if dataset is None:
            dataset_name = "No active dataset"
        else:
            dataset_name = getattr(dataset, "name", "Untitled")

        self.generate_button.setEnabled(has_data)
        self.refresh_button.setEnabled(has_data)
        self.save_pdf_button.setEnabled(bool(self.current_report_html) and HAS_WEBENGINE and self._preview_loaded)
        self.save_html_button.setEnabled(bool(self.current_report_html))
        self.status_hint.setText(
            f"Active dataset: {dataset_name}. Generate a preview before exporting."
            if has_data
            else "Open a dataset before generating a report."
        )

    def _on_settings_changed(self, *_args):
        self.current_report_html = ""
        self._set_preview_html(self._empty_preview_html(
            "Preview Not Generated",
            "Report settings changed. Click Generate Preview to refresh the document.",
        ))
        self._update_preview()

    def _default_report_path(self) -> str:
        dataset = self.main_window.get_active_dataset() if self.main_window is not None else None
        raw_name = getattr(dataset, "name", "HeadAnalyser_Report") if dataset is not None else "HeadAnalyser_Report"
        safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(raw_name)).strip("_") or "HeadAnalyser_Report"
        base_dir = ""
        if dataset is not None:
            source_path = getattr(dataset, "file_path", "") or ""
            if source_path:
                base_dir = os.path.dirname(source_path)
        return os.path.join(base_dir or os.getcwd(), f"{safe_name}_report.pdf")

    def _set_preview_html(self, html: str):
        if HAS_WEBENGINE:
            self._preview_loaded = False
            if hasattr(self, "save_pdf_button"):
                self.save_pdf_button.setEnabled(False)
            self.web_view.setHtml(html)
        else:
            self._preview_loaded = True
            self.web_view.setHtml(html)

    def _on_preview_load_finished(self, _ok: bool):
        self._preview_loaded = True
        self._update_preview()

    @staticmethod
    def _empty_preview_html(
        title: str = "No Report Generated",
        message: str = "Configure options on the left, then click Generate Preview.",
    ) -> str:
        safe_title = escape(str(title))
        safe_message = escape(str(message))
        return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
body {{
  margin: 0;
  min-height: 100vh;
  display: grid;
  place-items: center;
  background: #eef2f7;
  color: #1f2937;
  font-family: "Segoe UI", Arial, sans-serif;
}}
.empty {{
  width: min(560px, calc(100vw - 80px));
  padding: 42px;
  background: white;
  border: 1px solid #d8dee9;
  box-shadow: 0 18px 50px rgba(20,31,50,0.14);
}}
h2 {{
  margin: 0 0 10px;
  font-size: 24px;
  letter-spacing: -0.4px;
}}
p {{
  margin: 0;
  color: #667085;
  line-height: 1.5;
}}
</style>
</head>
<body>
  <div class="empty">
    <h2>{safe_title}</h2>
    <p>{safe_message}</p>
  </div>
</body>
</html>"""

    @staticmethod
    def _error_preview_html(message: str) -> str:
        return ReportView._empty_preview_html(
            "Report Generation Failed",
            f"The preview was cleared so stale content cannot be exported. Error: {message}",
        )

    def generate_preview(self):
        dataset = self.main_window.get_active_dataset() if self.main_window is not None else None
        data = self._active_data()
        if dataset is None or data is None or getattr(data, "empty", True):
            QMessageBox.warning(self, "No Data", "Open a dataset before generating a report.")
            return

        progress = LoadingDialog(
            "Generating Report Preview",
            "Rendering plots, statistics, and report sections",
            self,
            cancellable=True,
        )
        progress.update_progress(
            0,
            100,
            "Preparing preview",
            "Collecting active dataset state and report settings.",
            count_label="0%",
            activity_label="Starting report builder.",
        )
        progress.set_activity("The preview uses the same plot renderer as the main workspace.")
        progress.open()

        def _progress_cb(fraction: float, message: str):
            percent = int(max(0.0, min(1.0, float(fraction))) * 100)
            progress.update_progress(
                percent,
                100,
                message or "Generating preview",
                "Rendering the preview document from current HeadAnalyser state.",
                count_label=f"{percent}%",
                activity_label=message or "Working.",
            )
            QApplication.processEvents()
            if progress.cancel_requested:
                raise RuntimeError("Report generation canceled.")

        try:
            builder = HeadReportHtmlBuilder(self.main_window)
            self.current_report_html = builder.build(self._collect_settings(), _progress_cb)
            self._set_preview_html(self.current_report_html)
            progress.mark_finished("Preview ready", "The rendered report preview is available.", ok=True)
            QTimer.singleShot(420, progress.accept)
            self._update_preview()
        except Exception as exc:
            self.current_report_html = ""
            self._set_preview_html(self._error_preview_html(str(exc)))
            self._update_preview()
            progress.mark_finished("Preview failed", str(exc), ok=False)
            QMessageBox.critical(self, "Report Preview Error", str(exc))
        finally:
            QTimer.singleShot(650, progress.deleteLater)

    def save_preview_pdf(self):
        if not self.current_report_html:
            QMessageBox.information(self, "No Preview", "Generate a report preview before saving PDF.")
            return
        if not HAS_WEBENGINE:
            QMessageBox.warning(
                self,
                "Preview Export Unavailable",
                "PyQtWebEngine is required to export the rendered preview to PDF.",
            )
            return
        if not self._preview_loaded:
            QMessageBox.information(self, "Preview Loading", "Wait for the preview to finish loading before saving PDF.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Report PDF",
            self._default_report_path(),
            "PDF Document (*.pdf)",
        )
        if not file_path:
            return
        if not file_path.lower().endswith(".pdf"):
            file_path += ".pdf"

        self._pending_pdf_path = file_path
        self.save_pdf_button.setEnabled(False)
        self.status_hint.setText("Saving rendered preview to PDF...")
        self._pdf_export_dialog = LoadingDialog(
            "Saving Report PDF",
            "Printing the rendered preview to a PDF file",
            self,
            cancellable=False,
        )
        self._pdf_export_dialog.update_progress(
            0,
            1,
            "Saving PDF",
            "Qt WebEngine is writing the rendered document.",
            count_label="PDF",
            activity_label="Waiting for PDF writer to finish.",
        )
        self._pdf_export_dialog.open()
        try:
            self.web_view.page().printToPdf(file_path)
        except Exception as exc:
            self._pending_pdf_path = ""
            self._update_preview()
            if self._pdf_export_dialog is not None:
                self._pdf_export_dialog.mark_finished("PDF export failed", str(exc), ok=False)
                QTimer.singleShot(700, self._pdf_export_dialog.deleteLater)
                self._pdf_export_dialog = None
            QMessageBox.critical(self, "PDF Export Error", str(exc))

    def _on_pdf_done(self, path: str, success: bool):
        saved_path = path or self._pending_pdf_path
        self._pending_pdf_path = ""
        self._update_preview()
        if self._pdf_export_dialog is not None:
            if success:
                self._pdf_export_dialog.mark_finished("PDF saved", saved_path, ok=True)
            else:
                self._pdf_export_dialog.mark_finished("PDF export failed", "The WebEngine PDF writer reported failure.", ok=False)
            dialog = self._pdf_export_dialog
            self._pdf_export_dialog = None
            QTimer.singleShot(650, dialog.accept if success else dialog.deleteLater)
        if success:
            QMessageBox.information(self, "Report Export", f"Report exported to {saved_path}")
        else:
            QMessageBox.critical(self, "Report Export Error", "PDF export failed.")

    def save_preview_html(self):
        if not self.current_report_html:
            QMessageBox.information(self, "No Preview", "Generate a report preview before saving HTML.")
            return
        default_path = self._default_report_path()
        default_path = re.sub(r"\.pdf$", ".html", default_path, flags=re.IGNORECASE)
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Report HTML",
            default_path,
            "HTML Document (*.html)",
        )
        if not file_path:
            return
        if not file_path.lower().endswith(".html"):
            file_path += ".html"
        try:
            with open(file_path, "w", encoding="utf-8") as handle:
                handle.write(self.current_report_html)
            QMessageBox.information(self, "Report Export", f"Report HTML exported to {file_path}")
        except Exception as exc:
            QMessageBox.critical(self, "HTML Export Error", str(exc))
