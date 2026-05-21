"""
HeadAnalyser plot appearance gallery.

Full-size counterpart to the compact toolbar flyout. It exposes the same three
layers with shared visual previews:
- Presets: full recipes
- Color Styles: color-only palettes
- Formats: typography/axis/grid formatting
"""

from __future__ import annotations

from typing import Dict, Iterable

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from qt_chrome import FramelessDialogMixin
from styles.colors import Colors
from styles.plot_palettes import all_palettes, category_names as palette_category_names, get_palette
from styles.plot_styles import PlotStyles
from styles.plot_templates import (
    DEFAULT_TEMPLATE_KEY,
    available_templates,
    category_names as template_category_names,
    get_template,
)
from ui.icons import Icons, icon
from ui.plot_appearance_preview import AppearancePreviewCard, PlotAppearancePreview, settings_from_target
from ui.plot_types import normalize_plot_type


class PlotTemplatePickerDialog(FramelessDialogMixin, QDialog):
    """Modal gallery for selecting a template, color style, or plot format."""

    def __init__(
        self,
        plot_type: str = "2D",
        active_key: str | None = None,
        active_palette_key: str | None = None,
        active_format_key: str | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.plot_type = normalize_plot_type(plot_type)
        self._target = getattr(parent, "main_window", parent)
        self._tab = "presets"
        self._filter = "All"
        self._cards: list[AppearancePreviewCard] = []
        self._selected_kind = "template"
        self._selected_key = active_key or DEFAULT_TEMPLATE_KEY
        self._active_template_key = active_key or DEFAULT_TEMPLATE_KEY
        self._active_palette_key = active_palette_key or getattr(self._target, "current_color_style", "hydraulic")
        self._active_format_key = active_format_key or getattr(
            self._target,
            "current_plot_format",
            getattr(self._target, "current_plot_style", "Default"),
        )

        available = tuple(available_templates(self.plot_type))
        available_keys = {template.key for template in available}
        if self._selected_key not in available_keys and available:
            self._selected_key = available[0].key
            self._active_template_key = self._selected_key

        self.setWindowTitle("Template Gallery")
        self.setMinimumSize(960, 650)
        self.setModal(True)
        self.init_frameless_dialog_chrome(
            default_windows="frameless",
            default_other="native",
            resize_margin=10,
            top_resize_margin=10,
        )
        self._build()
        self.bind_frameless_drag_widget(self._chrome_header)

    def selected_kind(self) -> str:
        return self._selected_kind

    def selected_key(self) -> str:
        return self._selected_key

    def selected_template_key(self) -> str:
        """Compatibility for callers that only expect presets."""
        return self._selected_key if self._selected_kind == "template" else self._active_template_key

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.setStyleSheet(f"QDialog {{ background: {Colors.BG_PANEL}; }}")

        root.addWidget(self._build_header())

        body = QWidget(self)
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(22, 18, 22, 18)
        body_layout.setSpacing(18)

        left = QVBoxLayout()
        left.setSpacing(12)
        left.addLayout(self._build_tab_row())
        left.addLayout(self._build_filter_row())
        left.addWidget(self._build_scroll(), 1)
        body_layout.addLayout(left, 1)

        self._inspector = self._build_inspector()
        body_layout.addWidget(self._inspector)

        root.addWidget(body, 1)
        root.addWidget(self._build_footer())

        self._sync_tabs()
        self._sync_filters()
        self._rebuild_cards()
        self._update_inspector()

    def _build_header(self) -> QWidget:
        header = QWidget(self)
        header.setFixedHeight(76)
        header.setStyleSheet(f"""
            QWidget {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {Colors.BG_ELEVATED}, stop:1 {Colors.BG_SURFACE});
                border-bottom: 1px solid {Colors.BORDER_DEFAULT};
            }}
        """)
        self._chrome_header = header
        layout = QHBoxLayout(header)
        layout.setContentsMargins(22, 0, 22, 0)
        layout.setSpacing(14)

        icon_box = QLabel()
        icon_box.setFixedSize(40, 40)
        icon_box.setAlignment(Qt.AlignCenter)
        icon_box.setPixmap(icon(Icons.PALETTE, Colors.ACCENT_PRIMARY, 17).pixmap(17, 17))
        icon_box.setStyleSheet(f"background: {Colors.ACCENT_GHOST}; border: 1px solid {Colors.BORDER_ACCENT}; border-radius: 11px;")
        layout.addWidget(icon_box)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title = QLabel("Template Gallery")
        title.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; font-size: 18px; font-weight: 900; background: transparent;")
        title_col.addWidget(title)
        subtitle = QLabel(f"{self.plot_type} previews - Presets, Color Styles, and Formats")
        subtitle.setStyleSheet(f"color: {Colors.TEXT_TERTIARY}; font-size: 11px; font-weight: 600; background: transparent;")
        title_col.addWidget(subtitle)
        layout.addLayout(title_col, 1)

        scope = QLabel("Active Cell")
        scope.setStyleSheet(f"""
            color: {Colors.ACCENT_PRIMARY};
            background: {Colors.ACCENT_GHOST};
            border: 1px solid {Colors.BORDER_ACCENT};
            border-radius: 8px;
            padding: 6px 10px;
            font-size: 10px;
            font-weight: 800;
        """)
        layout.addWidget(scope)

        close_btn = QPushButton()
        close_btn.setFixedSize(32, 32)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setIcon(icon(Icons.CLOSE, Colors.TEXT_MUTED, 14))
        close_btn.setStyleSheet(f"QPushButton {{ background: transparent; border: none; border-radius: 7px; }} QPushButton:hover {{ background: {Colors.BG_HOVER}; }}")
        close_btn.clicked.connect(self.reject)
        layout.addWidget(close_btn)
        return header

    def _build_tab_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        self._tab_buttons: Dict[str, QPushButton] = {}
        for key, label in (("presets", "Presets"), ("palettes", "Color Styles"), ("formats", "Formats")):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedHeight(32)
            btn.clicked.connect(lambda _checked=False, tab=key: self._set_tab(tab))
            self._tab_buttons[key] = btn
            row.addWidget(btn)
        row.addStretch()
        return row

    def _build_filter_row(self) -> QHBoxLayout:
        self._filter_row = QHBoxLayout()
        self._filter_row.setContentsMargins(0, 0, 0, 0)
        self._filter_row.setSpacing(7)
        self._filter_buttons: Dict[str, QPushButton] = {}
        return self._filter_row

    def _build_scroll(self) -> QScrollArea:
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"""
            QScrollArea {{ background: transparent; border: none; }}
            QScrollBar:vertical {{ background: transparent; width: 6px; }}
            QScrollBar::handle:vertical {{ background: {Colors.BORDER_STRONG}; border-radius: 3px; min-height: 20px; }}
        """)
        self._grid_host = QWidget()
        self._grid_host.setStyleSheet("background: transparent;")
        self._grid = QGridLayout(self._grid_host)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setHorizontalSpacing(14)
        self._grid.setVerticalSpacing(14)
        scroll.setWidget(self._grid_host)
        return scroll

    def _build_inspector(self) -> QWidget:
        panel = QFrame(self)
        panel.setFixedWidth(270)
        panel.setObjectName("templateInspector")
        panel.setStyleSheet(f"""
            QFrame#templateInspector {{
                background: {Colors.BG_ELEVATED};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 14px;
            }}
        """)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        self._inspector_preview_host = QWidget(panel)
        self._inspector_preview_layout = QVBoxLayout(self._inspector_preview_host)
        self._inspector_preview_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._inspector_preview_host)
        self._inspector_title = QLabel()
        self._inspector_title.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; font-size: 15px; font-weight: 900; background: transparent;")
        layout.addWidget(self._inspector_title)
        self._inspector_meta = QLabel()
        self._inspector_meta.setWordWrap(True)
        self._inspector_meta.setStyleSheet(f"color: {Colors.TEXT_TERTIARY}; font-size: 10px; line-height: 1.35; background: transparent;")
        layout.addWidget(self._inspector_meta)
        layout.addStretch()
        scope = QLabel("Scope: Active Cell")
        scope.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: 10px; font-weight: 800; background: transparent;")
        layout.addWidget(scope)
        return panel

    def _build_footer(self) -> QWidget:
        footer = QWidget(self)
        footer.setFixedHeight(66)
        footer.setStyleSheet(f"background: {Colors.BG_PANEL}; border-top: 1px solid {Colors.BORDER_DEFAULT};")
        layout = QHBoxLayout(footer)
        layout.setContentsMargins(22, 0, 22, 0)
        layout.setSpacing(10)
        hint = QLabel("Preview cards use canonical synthetic data for the active plot type.")
        hint.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: 10px; background: transparent;")
        layout.addWidget(hint, 1)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setStyleSheet(self._button_style(primary=False))
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(cancel_btn)
        self._apply_btn = QPushButton("Apply Template")
        self._apply_btn.setCursor(Qt.PointingHandCursor)
        self._apply_btn.setStyleSheet(self._button_style(primary=True))
        self._apply_btn.clicked.connect(self.accept)
        layout.addWidget(self._apply_btn)
        return footer

    def _button_style(self, *, primary: bool = False) -> str:
        if primary:
            return f"""
                QPushButton {{
                    color: #ffffff;
                    background: {Colors.ACCENT_PRIMARY};
                    border: 1px solid {Colors.ACCENT_PRIMARY};
                    border-radius: 8px;
                    padding: 9px 18px;
                    font-size: 11px;
                    font-weight: 900;
                }}
                QPushButton:hover {{ background: {Colors.ACCENT_HOVER}; }}
            """
        return f"""
            QPushButton {{
                color: {Colors.TEXT_SECONDARY};
                background: transparent;
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 8px;
                padding: 8px 14px;
                font-size: 11px;
                font-weight: 800;
            }}
            QPushButton:hover {{ color: {Colors.TEXT_PRIMARY}; background: {Colors.BG_SURFACE}; border-color: {Colors.BORDER_MEDIUM}; }}
        """

    def _chip_style(self) -> str:
        return f"""
            QPushButton {{
                color: {Colors.TEXT_TERTIARY};
                background: {Colors.BG_SURFACE};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 8px;
                padding: 0 12px;
                font-size: 10px;
                font-weight: 800;
            }}
            QPushButton:hover {{ color: {Colors.TEXT_SECONDARY}; border-color: {Colors.BORDER_MEDIUM}; }}
            QPushButton:checked {{ color: {Colors.TEXT_PRIMARY}; background: {Colors.ACCENT_GHOST}; border-color: {Colors.ACCENT_PRIMARY}; }}
        """

    def _sync_tabs(self) -> None:
        for key, btn in self._tab_buttons.items():
            btn.setChecked(key == self._tab)
            btn.setStyleSheet(self._chip_style())

    def _filter_values(self) -> Iterable[str]:
        if self._tab == "presets":
            return ("All",) + template_category_names(available_templates(self.plot_type))
        if self._tab == "palettes":
            return ("All",) + palette_category_names(all_palettes(include_custom=False))
        return ("All",)

    def _sync_filters(self) -> None:
        while self._filter_row.count():
            item = self._filter_row.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._filter_buttons = {}
        values = tuple(self._filter_values())
        if self._filter not in values:
            self._filter = "All"
        for value in values:
            btn = QPushButton(value)
            btn.setCheckable(True)
            btn.setChecked(value == self._filter)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedHeight(28)
            btn.setStyleSheet(self._chip_style())
            btn.clicked.connect(lambda _checked=False, v=value: self._set_filter(v))
            self._filter_buttons[value] = btn
            self._filter_row.addWidget(btn)
        self._filter_row.addStretch()

    def _set_tab(self, tab: str) -> None:
        self._tab = tab
        self._filter = "All"
        if tab == "presets":
            self._selected_kind = "template"
            self._selected_key = self._active_template_key
        elif tab == "palettes":
            self._selected_kind = "palette"
            self._selected_key = self._active_palette_key
        else:
            self._selected_kind = "format"
            self._selected_key = self._active_format_key
        self._sync_tabs()
        self._sync_filters()
        self._rebuild_cards()
        self._update_inspector()

    def _set_filter(self, value: str) -> None:
        self._filter = value
        self._sync_filters()
        self._rebuild_cards()

    def _base_settings(self) -> Dict:
        return settings_from_target(self._target, self.plot_type)

    def _clear_cards(self) -> None:
        while self._grid.count():
            item = self._grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._cards = []

    def _rebuild_cards(self) -> None:
        self._clear_cards()
        if self._tab == "palettes":
            self._build_palette_cards()
            self._apply_btn.setText("Apply Color Style")
        elif self._tab == "formats":
            self._build_format_cards()
            self._apply_btn.setText("Apply Format")
        else:
            self._build_template_cards()
            self._apply_btn.setText("Apply Template")

    def _add_card(self, card: AppearancePreviewCard, index: int) -> None:
        self._cards.append(card)
        self._grid.addWidget(card, index // 2, index % 2)

    def _build_template_cards(self) -> None:
        templates = [
            template for template in available_templates(self.plot_type)
            if self._filter == "All" or template.category == self._filter
        ]
        for idx, template in enumerate(templates):
            card = AppearancePreviewCard(
                template.key,
                template.name,
                f"{template.format_key} / {get_palette(template.palette_key).name}",
                self.plot_type,
                template.settings_for(self.plot_type),
                badge=template.category,
                parent=self._grid_host,
            )
            card.set_selected(self._selected_kind == "template" and template.key == self._selected_key)
            card.clicked.connect(lambda key, kind="template": self._select(kind, key))
            card.double_clicked.connect(lambda key, kind="template": self._accept(kind, key))
            self._add_card(card, idx)

    def _build_palette_cards(self) -> None:
        palettes = [
            palette for palette in all_palettes(include_custom=False)
            if self._filter == "All" or palette.category == self._filter
        ]
        base = self._base_settings()
        for idx, palette in enumerate(palettes):
            settings = dict(base)
            settings.update(palette.settings_for(self.plot_type))
            settings["current_color_style"] = palette.key
            card = AppearancePreviewCard(
                palette.key,
                palette.name,
                palette.description,
                self.plot_type,
                settings,
                badge=palette.category,
                parent=self._grid_host,
            )
            card.set_selected(self._selected_kind == "palette" and palette.key == self._selected_key)
            card.clicked.connect(lambda key, kind="palette": self._select(kind, key))
            card.double_clicked.connect(lambda key, kind="palette": self._accept(kind, key))
            self._add_card(card, idx)

    def _build_format_cards(self) -> None:
        base = self._base_settings()
        descriptions = {
            "Default": "Balanced workspace formatting.",
            "Minimal": "Reduced chrome for dense multi-cell views.",
            "Scientific": "Technical ticks, stronger grid, and serif labels.",
            "Publication": "Clean report/export axes and emphasized labels.",
        }
        for idx, format_key in enumerate(PlotStyles.format_names()):
            settings = dict(base)
            settings["current_plot_format"] = format_key
            settings["current_plot_style"] = format_key
            settings["show_grid"] = True
            card = AppearancePreviewCard(
                format_key,
                format_key,
                descriptions.get(format_key, "Plot formatting preset."),
                self.plot_type,
                settings,
                badge="Format",
                parent=self._grid_host,
            )
            card.set_selected(self._selected_kind == "format" and format_key == self._selected_key)
            card.clicked.connect(lambda key, kind="format": self._select(kind, key))
            card.double_clicked.connect(lambda key, kind="format": self._accept(kind, key))
            self._add_card(card, idx)

    def _select(self, kind: str, key: str) -> None:
        self._selected_kind = kind
        self._selected_key = key
        for card in self._cards:
            card.set_selected(card.key == key)
        self._update_inspector()

    def _accept(self, kind: str, key: str) -> None:
        self._select(kind, key)
        self.accept()

    def _selected_settings(self) -> Dict:
        if self._selected_kind == "template":
            return get_template(self._selected_key).settings_for(self.plot_type)
        base = self._base_settings()
        if self._selected_kind == "palette":
            palette = get_palette(self._selected_key)
            base.update(palette.settings_for(self.plot_type))
            base["current_color_style"] = palette.key
            return base
        base["current_plot_format"] = self._selected_key
        base["current_plot_style"] = self._selected_key
        base["show_grid"] = True
        return base

    def _update_inspector(self) -> None:
        while self._inspector_preview_layout.count():
            item = self._inspector_preview_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        preview = PlotAppearancePreview(self.plot_type, self._selected_settings(), self._inspector_preview_host)
        preview.setFixedHeight(150)
        self._inspector_preview_layout.addWidget(preview)

        if self._selected_kind == "template":
            template = get_template(self._selected_key)
            palette = get_palette(template.palette_key)
            self._inspector_title.setText(template.name)
            self._inspector_meta.setText(
                f"Preset\nFormat: {template.format_key}\nColor Style: {palette.name}\nApplies to: {', '.join(template.plot_types)}\n\n{template.description}"
            )
        elif self._selected_kind == "palette":
            palette = get_palette(self._selected_key)
            self._inspector_title.setText(palette.name)
            self._inspector_meta.setText(f"Color Style\nCategory: {palette.category}\n\n{palette.description}")
        else:
            self._inspector_title.setText(self._selected_key)
            self._inspector_meta.setText("Format\nChanges typography, axes, ticks, spines, and grid behavior while preserving the selected color style.")
