"""
Compact toolbar flyout for plot appearance selection.

This is the lightweight counterpart to the full template gallery. It uses the
same AppearancePreviewCard/PlotAppearancePreview renderer as the gallery.
"""

from __future__ import annotations

from typing import Dict

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from styles.colors import Colors
from styles.plot_palettes import all_palettes, get_palette
from styles.plot_styles import PlotStyles
from styles.plot_templates import available_templates, get_template
from ui.icons import Icons, icon
from ui.plot_appearance_preview import AppearancePreviewCard, settings_from_target


class PlotAppearanceFlyout(QFrame):
    template_selected = pyqtSignal(str)
    palette_selected = pyqtSignal(str)
    format_selected = pyqtSignal(str)
    gallery_requested = pyqtSignal()

    def __init__(self, main_window, plot_type: str = "2D", parent=None):
        super().__init__(parent, Qt.Popup | Qt.FramelessWindowHint)
        self.main_window = main_window
        self.plot_type = plot_type or "2D"
        self._tab = "presets"
        self._tab_buttons: Dict[str, QPushButton] = {}
        self._cards: list[AppearancePreviewCard] = []
        self.setObjectName("plotAppearanceFlyout")
        self.setFixedSize(540, 470)
        self._build()
        self._rebuild_cards()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.setStyleSheet(f"""
            QFrame#plotAppearanceFlyout {{
                background: {Colors.BG_PANEL};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 14px;
            }}
        """)

        header = QWidget(self)
        header.setFixedHeight(58)
        header.setStyleSheet(f"background: {Colors.BG_ELEVATED}; border-bottom: 1px solid {Colors.BORDER_DEFAULT};")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 0, 14, 0)
        header_layout.setSpacing(10)
        icon_box = QLabel()
        icon_box.setFixedSize(28, 28)
        icon_box.setAlignment(Qt.AlignCenter)
        icon_box.setPixmap(icon(Icons.PALETTE, Colors.ACCENT_PRIMARY, 13).pixmap(13, 13))
        icon_box.setStyleSheet(f"background: {Colors.ACCENT_GHOST}; border: 1px solid {Colors.BORDER_ACCENT}; border-radius: 8px;")
        header_layout.addWidget(icon_box)
        title_col = QVBoxLayout()
        title_col.setSpacing(1)
        title = QLabel("Plot Templates")
        title.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; font-size: 13px; font-weight: 900; background: transparent;")
        title_col.addWidget(title)
        subtitle = QLabel(f"{self.plot_type} preview - Active Cell")
        subtitle.setStyleSheet(f"color: {Colors.TEXT_TERTIARY}; font-size: 10px; font-weight: 600; background: transparent;")
        title_col.addWidget(subtitle)
        header_layout.addLayout(title_col, 1)
        root.addWidget(header)

        tab_row = QHBoxLayout()
        tab_row.setContentsMargins(14, 12, 14, 8)
        tab_row.setSpacing(6)
        for key, label in (("presets", "Presets"), ("palettes", "Color Styles"), ("formats", "Formats")):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedHeight(28)
            btn.clicked.connect(lambda _checked=False, tab=key: self._set_tab(tab))
            self._tab_buttons[key] = btn
            tab_row.addWidget(btn)
        root.addLayout(tab_row)
        self._sync_tabs()

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
        self._grid.setContentsMargins(14, 0, 14, 10)
        self._grid.setHorizontalSpacing(10)
        self._grid.setVerticalSpacing(10)
        scroll.setWidget(self._grid_host)
        root.addWidget(scroll, 1)

        footer = QWidget(self)
        footer.setFixedHeight(52)
        footer.setStyleSheet(f"background: {Colors.BG_PANEL}; border-top: 1px solid {Colors.BORDER_DEFAULT};")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(14, 0, 14, 0)
        footer_layout.addStretch()
        gallery_btn = QPushButton("Template Gallery...")
        gallery_btn.setCursor(Qt.PointingHandCursor)
        gallery_btn.setStyleSheet(self._button_style(primary=True))
        gallery_btn.clicked.connect(self._on_gallery)
        footer_layout.addWidget(gallery_btn)
        root.addWidget(footer)

    def _button_style(self, *, primary: bool = False) -> str:
        if primary:
            return f"""
                QPushButton {{
                    color: #ffffff;
                    background: {Colors.ACCENT_PRIMARY};
                    border: 1px solid {Colors.ACCENT_PRIMARY};
                    border-radius: 8px;
                    padding: 7px 14px;
                    font-size: 11px;
                    font-weight: 800;
                }}
                QPushButton:hover {{ background: {Colors.ACCENT_HOVER}; }}
            """
        return f"""
            QPushButton {{
                color: {Colors.TEXT_TERTIARY};
                background: {Colors.BG_SURFACE};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 8px;
                font-size: 10px;
                font-weight: 800;
            }}
            QPushButton:hover {{ color: {Colors.TEXT_SECONDARY}; border-color: {Colors.BORDER_MEDIUM}; }}
            QPushButton:checked {{
                color: {Colors.TEXT_PRIMARY};
                background: {Colors.ACCENT_GHOST};
                border-color: {Colors.ACCENT_PRIMARY};
            }}
        """

    def _sync_tabs(self) -> None:
        for key, btn in self._tab_buttons.items():
            btn.setChecked(key == self._tab)
            btn.setStyleSheet(self._button_style(primary=False))

    def _set_tab(self, tab: str) -> None:
        self._tab = tab
        self._sync_tabs()
        self._rebuild_cards()

    def _base_settings(self) -> Dict:
        return settings_from_target(self.main_window, self.plot_type)

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
        elif self._tab == "formats":
            self._build_format_cards()
        else:
            self._build_template_cards()

    def _add_card(self, card: AppearancePreviewCard, index: int) -> None:
        self._cards.append(card)
        self._grid.addWidget(card, index // 2, index % 2)

    def _build_template_cards(self) -> None:
        active = str(getattr(self.main_window, "current_plot_template", "hydraulic_field"))
        for idx, template in enumerate(available_templates(self.plot_type)):
            settings = template.settings_for(self.plot_type)
            card = AppearancePreviewCard(
                template.key,
                template.name,
                f"{template.format_key} / {get_palette(template.palette_key).name}",
                self.plot_type,
                settings,
                badge=template.category,
                compact=True,
                parent=self._grid_host,
            )
            card.set_selected(template.key == active)
            card.clicked.connect(self._choose_template)
            self._add_card(card, idx)

    def _build_palette_cards(self) -> None:
        active = str(getattr(self.main_window, "current_color_style", "hydraulic"))
        base = self._base_settings()
        for idx, palette in enumerate(all_palettes(include_custom=False)):
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
                compact=True,
                parent=self._grid_host,
            )
            card.set_selected(palette.key == active)
            card.clicked.connect(self._choose_palette)
            self._add_card(card, idx)

    def _build_format_cards(self) -> None:
        active = str(getattr(self.main_window, "current_plot_format", getattr(self.main_window, "current_plot_style", "Default")))
        base = self._base_settings()
        descriptions = {
            "Default": "Balanced workspace formatting.",
            "Minimal": "Reduced chrome for dense views.",
            "Scientific": "Technical axes, ticks, and grid.",
            "Publication": "Crisp report/export formatting.",
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
                compact=True,
                parent=self._grid_host,
            )
            card.set_selected(format_key == active)
            card.clicked.connect(self._choose_format)
            self._add_card(card, idx)

    def _choose_template(self, key: str) -> None:
        self.template_selected.emit(key)
        self.close()

    def _choose_palette(self, key: str) -> None:
        self.palette_selected.emit(key)
        self.close()

    def _choose_format(self, key: str) -> None:
        self.format_selected.emit(key)
        self.close()

    def _on_gallery(self) -> None:
        self.gallery_requested.emit()
        self.close()
