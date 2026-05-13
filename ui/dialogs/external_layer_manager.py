"""
External GIS layer manager dialog.

This is a real Qt dialog (like other app dialogs), not an in-map HTML overlay.
It edits MapWidget's external-layer catalog and pushes updates to the webview.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from PyQt5.QtCore import Qt, QByteArray
from PyQt5.QtGui import QColor, QIcon, QPixmap, QPainter
from PyQt5.QtSvg import QSvgRenderer
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
    QColorDialog,
)


# SVG icons for External Layer Manager
ELM_ICONS = {
    "layers": """<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
        <path d="M10 2L2 7l8 5 8-5-8-5z"/>
        <path d="M2 12l8 5 8-5"/>
        <path d="M2 17l8 5 8-5"/>
    </svg>""",
}


def _svg_to_pixmap(svg_str: str, size: int = 24, color: str = None) -> QPixmap:
    """Convert an SVG string to a QPixmap with optional color replacement."""
    svg = svg_str.strip()
    if color:
        svg = svg.replace('currentColor', color)
    else:
        svg = svg.replace('currentColor', Colors.ACCENT_PRIMARY)

    data = QByteArray(svg.encode('utf-8'))
    renderer = QSvgRenderer(data)

    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()

    return pixmap

from qt_chrome import FramelessDialogMixin
from styles.colors import Colors
from ui.dialogs.plot_settings import _spin_style


def _btn_style(kind: str = "ghost") -> str:
    if kind == "primary":
        return f"""
            QPushButton {{
                color: #fff;
                background: {Colors.ACCENT_MUTED};
                border: 1px solid {Colors.ACCENT_PRIMARY};
                border-radius: 8px;
                font-size: 11px;
                font-weight: 700;
                padding: 7px 14px;
            }}
            QPushButton:hover {{
                background: {Colors.ACCENT_PRIMARY};
            }}
        """
    if kind == "danger":
        return f"""
            QPushButton {{
                color: {Colors.TEXT_SECONDARY};
                background: transparent;
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 8px;
                font-size: 11px;
                font-weight: 600;
                padding: 7px 14px;
            }}
            QPushButton:hover {{
                color: {Colors.ERROR};
                border-color: rgba(248, 113, 113, 0.3);
                background: rgba(248, 113, 113, 0.08);
            }}
        """
    return f"""
        QPushButton {{
            color: {Colors.TEXT_SECONDARY};
            background: transparent;
            border: 1px solid {Colors.BORDER_DEFAULT};
            border-radius: 8px;
            font-size: 11px;
            font-weight: 600;
            padding: 7px 14px;
        }}
        QPushButton:hover {{
            color: {Colors.TEXT_PRIMARY};
            border-color: {Colors.BORDER_MEDIUM};
            background: {Colors.BG_SURFACE};
        }}
    """


class ExternalLayerManagerDialog(FramelessDialogMixin, QDialog):
    """Manage loaded external GIS overlays (visibility + simple styling)."""

    def __init__(self, main_window, map_widget, parent=None):
        super().__init__(parent or main_window)
        self.main_window = main_window
        self.map_widget = map_widget
        self._block_item_signals = False
        self._current_layer_id: Optional[str] = None

        self.setWindowTitle("External Layers")
        self.resize(920, 620)
        self.setMinimumSize(760, 520)
        self.setModal(False)
        self.init_frameless_dialog_chrome(
            default_windows="frameless",
            default_other="native",
            resize_margin=10,
            top_resize_margin=10,
        )
        self.setStyleSheet(f"QDialog {{ background-color: {Colors.BG_MODAL}; }}")

        self._setup_ui()
        self.bind_frameless_drag_widget(self._chrome_header)
        self.refresh_from_map()

    # ---- UI helpers ---------------------------------------------------------

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

    def _set_swatch_color(self, button: QPushButton, hex_color: str):
        button.setProperty("color", hex_color)
        button.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {hex_color};
                border: 2px solid {Colors.BORDER_MEDIUM};
                border-radius: 4px;
            }}
            QPushButton:hover {{
                border-color: {Colors.ACCENT_PRIMARY};
            }}
            """
        )

    def _set_geometry_badge(self, geom_kind: str):
        """Set the geometry badge color and text based on geometry type."""
        kind = str(geom_kind or "other").lower().strip()
        colors = {
            "polygon": ("#22c55e", "rgba(34, 197, 94, 0.15)", "Polygon"),
            "line": ("#3b82f6", "rgba(59, 130, 246, 0.15)", "Line"),
            "point": ("#f59e0b", "rgba(245, 158, 11, 0.15)", "Point"),
            "mixed": ("#a855f7", "rgba(168, 85, 247, 0.15)", "Mixed"),
        }
        fg, bg, text = colors.get(kind, (Colors.TEXT_TERTIARY, "transparent", kind.title() or "Unknown"))
        self.geometry_badge.setText(text)
        self.geometry_badge.setStyleSheet(
            f"""
            QLabel {{
                background: {bg};
                color: {fg};
                border: 1px solid {fg}40;
                border-radius: 6px;
                padding: 2px 10px;
                font-size: 10px;
                font-weight: 700;
            }}
            """
        )

    def _make_slider_row(self, label: str, min_val: int, max_val: int, initial: int, suffix: str = "") -> tuple:
        """Create a styled slider row with label and value display."""
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        lbl = QLabel(label)
        lbl.setMinimumWidth(70)
        layout.addWidget(lbl)

        slider = QSlider(Qt.Horizontal)
        slider.setRange(min_val, max_val)
        slider.setValue(initial)
        slider.setStyleSheet(
            f"""
            QSlider::groove:horizontal {{
                height: 6px;
                background: {Colors.BG_WELL};
                border: 1px solid {Colors.BORDER_SUBTLE};
                border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                width: 14px;
                height: 14px;
                margin: -5px 0;
                background: {Colors.ACCENT_PRIMARY};
                border: 2px solid {Colors.BG_SURFACE};
                border-radius: 7px;
            }}
            QSlider::handle:horizontal:hover {{
                background: {Colors.ACCENT_MUTED};
            }}
            QSlider::sub-page:horizontal {{
                background: {Colors.ACCENT_GHOST};
                border-radius: 3px;
            }}
            """
        )
        layout.addWidget(slider, 1)

        value_label = QLabel(f"{initial}{suffix}")
        value_label.setFixedWidth(50)
        value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        value_label.setStyleSheet(
            f"""
            QLabel {{
                background: {Colors.BG_WELL};
                border: 1px solid {Colors.BORDER_SUBTLE};
                border-radius: 4px;
                padding: 2px 6px;
                font-family: 'Consolas', monospace;
                font-size: 10px;
                font-weight: 600;
                color: {Colors.TEXT_SECONDARY};
            }}
            """
        )
        layout.addWidget(value_label)

        return row, slider, value_label

    def _pick_color(self):
        current = QColor(str(self.color_btn.property("color") or "#22c55e"))
        color = QColorDialog.getColor(current, self, "Select Layer Color")
        if not color.isValid():
            return
        self._set_swatch_color(self.color_btn, color.name())
        self._commit_style()

    # ---- Layout -------------------------------------------------------------

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QWidget()
        header.setFixedHeight(64)
        header.setStyleSheet(
            f"""
            QWidget {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {Colors.BG_ELEVATED}, stop:1 {Colors.BG_SURFACE});
                border-bottom: 1px solid {Colors.BORDER_DEFAULT};
            }}
            """
        )
        self._chrome_header = header
        hl = QHBoxLayout(header)
        hl.setContentsMargins(20, 0, 20, 0)
        hl.setSpacing(12)

        icon_box = QLabel()
        icon_box.setFixedSize(32, 32)
        icon_box.setAlignment(Qt.AlignCenter)
        icon_box.setPixmap(_svg_to_pixmap(ELM_ICONS["layers"], 20, Colors.ACCENT_PRIMARY))
        icon_box.setStyleSheet(
            f"""
            background-color: {Colors.ACCENT_GHOST};
            border: 1px solid {Colors.BORDER_ACCENT};
            border-radius: 8px;
            """
        )
        hl.addWidget(icon_box)

        title_col = QVBoxLayout()
        title_col.setSpacing(1)
        title_label = QLabel("External Layers")
        title_label.setStyleSheet(
            f"color: {Colors.TEXT_PRIMARY}; font-size: 15px; font-weight: 700; background: transparent;"
        )
        title_col.addWidget(title_label)
        subtitle = QLabel("Visibility and styling for loaded GeoJSON / Shapefile overlays")
        subtitle.setStyleSheet(
            f"color: {Colors.TEXT_TERTIARY}; font-size: 10px; font-weight: 500; background: transparent;"
        )
        title_col.addWidget(subtitle)
        hl.addLayout(title_col)
        hl.addStretch()

        close_btn = QPushButton("x")
        close_btn.setFixedSize(28, 28)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet(
            f"""
            QPushButton {{
                background: transparent;
                border: none;
                border-radius: 6px;
                color: {Colors.TEXT_MUTED};
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {Colors.BG_HOVER};
                color: {Colors.TEXT_PRIMARY};
            }}
            """
        )
        close_btn.clicked.connect(self.close)
        hl.addWidget(close_btn)
        root.addWidget(header)

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(14, 14, 14, 14)
        body_layout.setSpacing(12)
        root.addWidget(body, 1)

        # Left: list + actions
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)

        self.layer_tree = QTreeWidget()
        self.layer_tree.setColumnCount(2)
        self.layer_tree.setHeaderHidden(True)
        self.layer_tree.setIndentation(0)
        self.layer_tree.setRootIsDecorated(False)
        self.layer_tree.setUniformRowHeights(True)
        self.layer_tree.setSelectionMode(QTreeWidget.SingleSelection)
        self.layer_tree.setAnimated(False)
        # We only allow editing the name column (0) via explicit double-click handler.
        self.layer_tree.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.layer_tree.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.layer_tree.setStyleSheet(
            f"""
            QTreeWidget {{
                background: {Colors.BG_SURFACE};
                color: {Colors.TEXT_PRIMARY};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 10px;
                padding: 6px;
            }}
            QTreeWidget::item {{
                padding: 6px;
                border-radius: 8px;
            }}
            QTreeWidget::item:selected {{
                background: {Colors.ACCENT_GHOST};
                border: 1px solid {Colors.BORDER_ACCENT};
            }}
            """
        )
        self.layer_tree.itemSelectionChanged.connect(self._on_layer_selected)
        self.layer_tree.itemChanged.connect(self._on_layer_item_changed)
        self.layer_tree.itemDoubleClicked.connect(self._on_layer_item_double_clicked)
        left_layout.addWidget(self.layer_tree, 1)

        left_actions = QHBoxLayout()
        left_actions.setSpacing(8)
        self.btn_load = QPushButton("Load...")
        self.btn_load.setCursor(Qt.PointingHandCursor)
        self.btn_load.setStyleSheet(_btn_style("ghost"))
        self.btn_load.clicked.connect(self._on_load_clicked)
        left_actions.addWidget(self.btn_load)

        self.btn_remove = QPushButton("Remove")
        self.btn_remove.setCursor(Qt.PointingHandCursor)
        self.btn_remove.setStyleSheet(_btn_style("danger"))
        self.btn_remove.clicked.connect(self._on_remove_clicked)
        left_actions.addWidget(self.btn_remove)

        self.btn_clear = QPushButton("Clear All")
        self.btn_clear.setCursor(Qt.PointingHandCursor)
        self.btn_clear.setStyleSheet(_btn_style("danger"))
        self.btn_clear.clicked.connect(self._on_clear_clicked)
        left_actions.addWidget(self.btn_clear)

        left_layout.addLayout(left_actions)

        # Right: details + style
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)

        # Title row with geometry badge
        title_row = QHBoxLayout()
        title_row.setSpacing(10)
        self.detail_title = QLabel("-")
        self.detail_title.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; font-size: 14px; font-weight: 700;")
        title_row.addWidget(self.detail_title)

        self.geometry_badge = QLabel("-")
        self.geometry_badge.setFixedHeight(22)
        self.geometry_badge.setAlignment(Qt.AlignCenter)
        self._set_geometry_badge("other")
        title_row.addWidget(self.geometry_badge)
        title_row.addStretch()
        right_layout.addLayout(title_row)

        self.detail_meta = QLabel("-")
        self.detail_meta.setStyleSheet(f"color: {Colors.TEXT_TERTIARY}; font-size: 11px;")
        self.detail_meta.setWordWrap(True)
        right_layout.addWidget(self.detail_meta)

        style_box = QWidget()
        style_box.setStyleSheet(
            f"""
            QWidget {{
                background: {Colors.BG_SURFACE};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 10px;
            }}
            """
        )
        sb = QVBoxLayout(style_box)
        sb.setContentsMargins(12, 12, 12, 12)
        sb.setSpacing(10)

        # Color
        row_color = QHBoxLayout()
        row_color.addWidget(QLabel("Color"))
        row_color.addStretch()
        self.color_btn = QPushButton()
        self.color_btn.setFixedSize(34, 22)
        self.color_btn.setCursor(Qt.PointingHandCursor)
        self.color_btn.clicked.connect(self._pick_color)
        self._set_swatch_color(self.color_btn, "#22c55e")
        row_color.addWidget(self.color_btn)
        sb.addLayout(row_color)

        # Line width (slider)
        self.row_line_width, self.slider_line_width, self.val_line_width = self._make_slider_row(
            "Line Width", 1, 8, 2, " px"
        )
        self.slider_line_width.valueChanged.connect(self._on_line_width_changed)
        sb.addWidget(self.row_line_width)

        # Line opacity (slider)
        self.row_line_opacity, self.slider_line_opacity, self.val_line_opacity = self._make_slider_row(
            "Line Opacity", 5, 100, 90, "%"
        )
        self.slider_line_opacity.valueChanged.connect(self._on_line_opacity_changed)
        sb.addWidget(self.row_line_opacity)

        # Fill opacity (slider)
        self.row_fill_opacity, self.slider_fill_opacity, self.val_fill_opacity = self._make_slider_row(
            "Fill Opacity", 0, 100, 12, "%"
        )
        self.slider_fill_opacity.valueChanged.connect(self._on_fill_opacity_changed)
        sb.addWidget(self.row_fill_opacity)

        # Point size (slider)
        self.row_point_size, self.slider_point_size, self.val_point_size = self._make_slider_row(
            "Point Size", 2, 24, 8, " px"
        )
        self.slider_point_size.valueChanged.connect(self._on_point_size_changed)
        sb.addWidget(self.row_point_size)

        right_layout.addWidget(style_box)
        right_layout.addStretch()

        body_layout.addWidget(left, 1)
        body_layout.addWidget(right, 2)

        # Footer with Done button
        footer = QWidget()
        footer.setFixedHeight(56)
        footer.setStyleSheet(
            f"""
            QWidget {{
                background: {Colors.BG_ELEVATED};
                border-top: 1px solid {Colors.BORDER_DEFAULT};
            }}
            """
        )
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(20, 0, 20, 0)
        footer_layout.setSpacing(12)

        footer_note = QLabel("Geometry-specific controls shown based on layer type.")
        footer_note.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: 10px; background: transparent;")
        footer_layout.addWidget(footer_note)
        footer_layout.addStretch()

        self.btn_done = QPushButton("Done")
        self.btn_done.setCursor(Qt.PointingHandCursor)
        self.btn_done.setStyleSheet(_btn_style("primary"))
        self.btn_done.clicked.connect(self.close)
        footer_layout.addWidget(self.btn_done)

        root.addWidget(footer)

    # ---- Data sync ----------------------------------------------------------

    def refresh_from_map(self):
        self._block_item_signals = True
        try:
            self.layer_tree.clear()
            layers = self.map_widget._external_layer_catalog_payload() if self.map_widget else []
            # Show topmost layer first (Leaflet draws later layers on top).
            for layer in reversed(layers):
                layer_id = str(layer.get("id") or "")
                name = str(layer.get("name") or "External Layer")
                geom = str(layer.get("geometry") or layer.get("geometry_kind") or "Geometry")
                features = int(layer.get("feature_count") or 0)

                item = QTreeWidgetItem()
                item.setText(0, name)
                item.setText(1, f"{geom} - {features} features")
                item.setData(0, Qt.UserRole, layer_id)
                item.setFlags(
                    item.flags()
                    | Qt.ItemIsUserCheckable
                    | Qt.ItemIsSelectable
                    | Qt.ItemIsEnabled
                    | Qt.ItemIsEditable
                )
                item.setCheckState(0, Qt.Checked if bool(layer.get("visible", True)) else Qt.Unchecked)
                self.layer_tree.addTopLevelItem(item)

            self.layer_tree.resizeColumnToContents(0)
            if self.layer_tree.topLevelItemCount() > 0:
                first = self.layer_tree.topLevelItem(0)
                self.layer_tree.setCurrentItem(first)
        finally:
            self._block_item_signals = False

        self._sync_detail_from_selection()

    def _get_selected_layer_id(self) -> Optional[str]:
        item = self.layer_tree.currentItem()
        if item is None:
            return None
        return str(item.data(0, Qt.UserRole) or "")

    def _layer_by_id(self, layer_id: str) -> Optional[Dict[str, Any]]:
        if not self.map_widget:
            return None
        for layer in self.map_widget._external_layers:
            if str(layer.get("layer_id", "")) == str(layer_id or ""):
                return layer
        return None

    def _sync_detail_from_selection(self):
        layer_id = self._get_selected_layer_id()
        self._current_layer_id = layer_id
        layer = self._layer_by_id(layer_id) if layer_id else None
        if not layer:
            self.detail_title.setText("-")
            self.detail_meta.setText("No layer selected.")
            self._set_geometry_badge("other")
            self._set_controls_enabled(False)
            return

        name = str(layer.get("name") or "External Layer")
        geom_kind = str(layer.get("geometry_kind") or "other").lower().strip()
        source = str(layer.get("source_path") or "-")
        features = int(layer.get("feature_count") or 0)
        self.detail_title.setText(name)
        self.detail_meta.setText(f"{features} features\n{source}")
        self._set_geometry_badge(geom_kind)

        style = layer.get("style") if isinstance(layer.get("style"), dict) else {}
        color = str(style.get("color") or self.map_widget.COLORS.get("external", "#22c55e"))
        self._set_swatch_color(self.color_btn, color)

        # Block signals while updating sliders
        self.slider_line_width.blockSignals(True)
        self.slider_line_opacity.blockSignals(True)
        self.slider_fill_opacity.blockSignals(True)
        self.slider_point_size.blockSignals(True)
        try:
            line_width = int(round(float(style.get("line_width") or 2.0)))
            line_opacity = int(round(float(style.get("line_opacity") or 0.9) * 100.0))
            fill_opacity = int(round(float(style.get("fill_opacity") or 0.12) * 100.0))
            point_size = int(round(float(style.get("point_size") or 8.0)))

            self.slider_line_width.setValue(line_width)
            self.val_line_width.setText(f"{line_width} px")
            self.slider_line_opacity.setValue(line_opacity)
            self.val_line_opacity.setText(f"{line_opacity}%")
            self.slider_fill_opacity.setValue(fill_opacity)
            self.val_fill_opacity.setText(f"{fill_opacity}%")
            self.slider_point_size.setValue(point_size)
            self.val_point_size.setText(f"{point_size} px")
        finally:
            self.slider_line_width.blockSignals(False)
            self.slider_line_opacity.blockSignals(False)
            self.slider_fill_opacity.blockSignals(False)
            self.slider_point_size.blockSignals(False)

        # Geometry-aware controls
        is_point = geom_kind == "point"
        is_line = geom_kind == "line"
        is_polygon = geom_kind == "polygon"
        is_mixed = geom_kind == "mixed"

        self.row_line_width.setVisible(is_line or is_polygon or is_mixed)
        self.row_fill_opacity.setVisible(is_polygon or is_mixed)
        self.row_point_size.setVisible(is_point or is_mixed)
        self._set_controls_enabled(True)

    def _set_controls_enabled(self, enabled: bool):
        self.color_btn.setEnabled(enabled)
        self.slider_line_width.setEnabled(enabled)
        self.slider_line_opacity.setEnabled(enabled)
        self.slider_fill_opacity.setEnabled(enabled)
        self.slider_point_size.setEnabled(enabled)
        self.btn_remove.setEnabled(bool(enabled and self._current_layer_id))

    # ---- Events -------------------------------------------------------------

    def _on_layer_selected(self):
        if self._block_item_signals:
            return
        self._sync_detail_from_selection()

    def _on_layer_item_double_clicked(self, item: QTreeWidgetItem, column: int):
        if self._block_item_signals:
            return
        if item is None or int(column) != 0:
            return
        try:
            self.layer_tree.editItem(item, 0)
        except Exception:
            pass

    def _on_layer_item_changed(self, item: QTreeWidgetItem, column: int):
        if self._block_item_signals or column != 0:
            return
        layer_id = str(item.data(0, Qt.UserRole) or "")
        if not layer_id or not self.map_widget:
            return
        layer = self._layer_by_id(layer_id)
        if not layer:
            return

        visible = item.checkState(0) == Qt.Checked
        if bool(layer.get("visible", True)) != bool(visible):
            self.map_widget.set_external_layer_visible(layer_id, visible)

        new_name = str(item.text(0) or "").strip()
        if not new_name:
            self._block_item_signals = True
            try:
                item.setText(0, str(layer.get("name") or "External Layer"))
            finally:
                self._block_item_signals = False
            return

        if str(layer.get("name") or "").strip() != new_name:
            self.map_widget.rename_external_layer(layer_id, new_name)
            if self._current_layer_id == layer_id:
                self.detail_title.setText(new_name)

    def _commit_style(self):
        layer_id = self._current_layer_id
        layer = self._layer_by_id(layer_id) if layer_id else None
        if not layer or not self.map_widget:
            return
        style = {
            "color": str(self.color_btn.property("color") or "#22c55e"),
            "line_width": float(self.slider_line_width.value()),
            "line_opacity": float(self.slider_line_opacity.value()) / 100.0,
            "fill_opacity": float(self.slider_fill_opacity.value()) / 100.0,
            "point_size": float(self.slider_point_size.value()),
        }
        self.map_widget.set_external_layer_style(str(layer_id), style)

    def _on_line_width_changed(self, value: int):
        self.val_line_width.setText(f"{value} px")
        self._commit_style()

    def _on_line_opacity_changed(self, value: int):
        self.val_line_opacity.setText(f"{value}%")
        self._commit_style()

    def _on_fill_opacity_changed(self, value: int):
        self.val_fill_opacity.setText(f"{value}%")
        self._commit_style()

    def _on_point_size_changed(self, value: int):
        self.val_point_size.setText(f"{value} px")
        self._commit_style()

    def _on_load_clicked(self):
        if not self.map_widget:
            return
        self.map_widget._prompt_external_layer_file()
        self.refresh_from_map()

    def _on_remove_clicked(self):
        if not self.map_widget:
            return
        layer_id = self._current_layer_id
        if not layer_id:
            return
        self.map_widget.remove_external_layer(str(layer_id))
        self.refresh_from_map()

    def _on_clear_clicked(self):
        if not self.map_widget:
            return
        self.map_widget.clear_external_layers()
        self.refresh_from_map()
