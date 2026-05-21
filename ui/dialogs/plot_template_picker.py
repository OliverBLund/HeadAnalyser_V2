"""
HeadAnalyser plot template picker.

This is a PyQt5-native adaptation of the concept/template_picker.py idea. It
keeps the gallery visual, but applies HeadAnalyser's own plot template registry.
"""

from __future__ import annotations

import math

from PyQt5.QtCore import QRectF, Qt, pyqtSignal
from PyQt5.QtGui import (
    QBrush,
    QColor,
    QCursor,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
)
from PyQt5.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from qt_chrome import FramelessDialogMixin
from styles.colors import Colors
from styles.plot_templates import (
    DEFAULT_TEMPLATE_KEY,
    PlotTemplate,
    available_templates,
    category_names,
    get_template,
)
from styles.plot_palettes import get_palette
from ui.icons import Icons, icon
from ui.plot_types import normalize_plot_type


_POINTS = (
    (0.18, 0.66),
    (0.31, 0.46),
    (0.46, 0.73),
    (0.60, 0.38),
    (0.73, 0.58),
    (0.84, 0.31),
)


def _color(value: str, fallback: str = "#64748b") -> QColor:
    if not value:
        return QColor(fallback)
    value = str(value).strip()
    if value.startswith("rgba("):
        try:
            parts = [p.strip() for p in value[5:-1].split(",")]
            rgba = [int(parts[0]), int(parts[1]), int(parts[2]), int(float(parts[3]) * 255)]
            return QColor(*rgba)
        except Exception:
            return QColor(fallback)
    if value.startswith("rgb("):
        try:
            parts = [p.strip() for p in value[4:-1].split(",")]
            return QColor(int(parts[0]), int(parts[1]), int(parts[2]))
        except Exception:
            return QColor(fallback)
    parsed = QColor(value)
    return parsed if parsed.isValid() else QColor(fallback)


class _MiniPreview(QWidget):
    """Custom-painted thumbnail showing the intent of a plot template."""

    def __init__(self, template: PlotTemplate, parent=None):
        super().__init__(parent)
        self._template = template
        self.setFixedHeight(104)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.rect().adjusted(1, 1, -1, -1)
        painter.fillRect(rect, _color(self._template.preview_background, "#ffffff"))
        painter.setClipRect(rect)

        self._draw_grid(painter, rect)

        mode = self._template.preview_mode
        if mode == "vector":
            self._draw_vectors(painter, rect)
        elif mode == "surface":
            self._draw_surface(painter, rect)
        elif mode == "stats":
            self._draw_stats(painter, rect)
        else:
            self._draw_contours(painter, rect)

        painter.setClipping(False)
        border = QColor(Colors.BORDER_SUBTLE)
        border.setAlpha(170)
        painter.setPen(QPen(border, 1.0))
        painter.drawRoundedRect(QRectF(rect), 11, 11)
        painter.end()

    def _palette(self):
        palette = list(self._template.palette or ())
        return palette or ["#2563eb", "#0ea5e9", "#64748b"]

    def _draw_grid(self, painter: QPainter, rect):
        grid = QColor("#dbeafe")
        grid.setAlpha(80)
        painter.setPen(QPen(grid, 0.7))
        for frac in (0.25, 0.50, 0.75):
            y = rect.top() + int(rect.height() * frac)
            painter.drawLine(rect.left(), y, rect.right(), y)
        for frac in (0.22, 0.44, 0.66, 0.88):
            x = rect.left() + int(rect.width() * frac)
            painter.drawLine(x, rect.top(), x, rect.bottom())

    def _draw_contours(self, painter: QPainter, rect):
        palette = self._palette()
        for i in range(7):
            color = _color(palette[i % len(palette)])
            color.setAlpha(54 if i % 2 else 76)
            painter.setPen(QPen(color, 1.2 if i % 2 else 1.7))
            path = QPainterPath()
            for step in range(36):
                x_frac = step / 35.0
                wave = math.sin((x_frac * 2.2 + i * 0.26) * math.pi)
                y_frac = 0.18 + i * 0.105 + wave * 0.055
                x = rect.left() + x_frac * rect.width()
                y = rect.top() + y_frac * rect.height()
                if step == 0:
                    path.moveTo(x, y)
                else:
                    path.lineTo(x, y)
            painter.drawPath(path)

        for idx, (x_frac, y_frac) in enumerate(_POINTS):
            color = _color(palette[idx % len(palette)])
            x = rect.left() + int(x_frac * rect.width())
            y = rect.top() + int(y_frac * rect.height())
            glow = QColor(color)
            glow.setAlpha(38)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(glow))
            painter.drawEllipse(x - 8, y - 8, 16, 16)
            painter.setBrush(QBrush(color))
            painter.drawEllipse(x - 4, y - 4, 8, 8)

    def _draw_surface(self, painter: QPainter, rect):
        palette = self._palette()
        gradient = QLinearGradient(rect.left(), rect.bottom(), rect.right(), rect.top())
        for idx, value in enumerate(palette):
            gradient.setColorAt(idx / max(1, len(palette) - 1), _color(value))
        painter.fillRect(rect, QBrush(gradient))

        ridge = QColor("#ffffff")
        ridge.setAlpha(130)
        painter.setPen(QPen(ridge, 1.2))
        for i in range(5):
            path = QPainterPath()
            for step in range(26):
                x_frac = step / 25.0
                y_frac = 0.28 + i * 0.12 + math.sin((x_frac + i * 0.18) * math.pi * 2.0) * 0.04
                x = rect.left() + x_frac * rect.width()
                y = rect.top() + y_frac * rect.height()
                if step == 0:
                    path.moveTo(x, y)
                else:
                    path.lineTo(x, y)
            painter.drawPath(path)

        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(255, 255, 255, 215)))
        for x_frac, y_frac in _POINTS[1::2]:
            x = rect.left() + int(x_frac * rect.width())
            y = rect.top() + int(y_frac * rect.height())
            painter.drawEllipse(x - 3, y - 3, 6, 6)

    def _draw_vectors(self, painter: QPainter, rect):
        palette = self._palette()
        for idx, (x_frac, y_frac) in enumerate(_POINTS):
            color = _color(palette[idx % len(palette)])
            color.setAlpha(220)
            start_x = rect.left() + int(x_frac * rect.width())
            start_y = rect.top() + int(y_frac * rect.height())
            length = int(rect.width() * (0.13 + idx * 0.01))
            angle = -0.65 + idx * 0.18
            end_x = start_x + int(math.cos(angle) * length)
            end_y = start_y + int(math.sin(angle) * length)
            painter.setPen(QPen(color, 2.0))
            painter.drawLine(start_x, start_y, end_x, end_y)
            painter.setBrush(QBrush(color))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(start_x - 3, start_y - 3, 6, 6)
            painter.drawEllipse(end_x - 2, end_y - 2, 4, 4)

        mean = _color(palette[-1])
        painter.setPen(QPen(mean, 3.0))
        y = rect.top() + int(rect.height() * 0.78)
        painter.drawLine(rect.left() + 24, y, rect.right() - 30, y - 18)

    def _draw_stats(self, painter: QPainter, rect):
        palette = self._palette()
        painter.setPen(Qt.NoPen)
        bar_width = max(7, rect.width() // 14)
        baseline = rect.bottom() - 16
        for idx, height_frac in enumerate((0.28, 0.46, 0.72, 0.86, 0.64, 0.38, 0.24)):
            color = _color(palette[idx % len(palette)])
            color.setAlpha(205)
            height = int(rect.height() * height_frac * 0.62)
            x = rect.left() + 24 + idx * (bar_width + 8)
            painter.setBrush(QBrush(color))
            painter.drawRoundedRect(QRectF(x, baseline - height, bar_width, height), 3, 3)

        rose_rect = QRectF(rect.right() - 86, rect.top() + 21, 58, 58)
        for idx, color_value in enumerate(palette):
            color = _color(color_value)
            color.setAlpha(170)
            painter.setBrush(QBrush(color))
            painter.setPen(Qt.NoPen)
            painter.drawPie(rose_rect, int((idx * 90 + 14) * 16), int(42 * 16))


class _TemplateCard(QFrame):
    clicked = pyqtSignal(str)
    double_clicked = pyqtSignal(str)

    def __init__(self, template: PlotTemplate, parent=None):
        super().__init__(parent)
        self.template = template
        self.setObjectName("plotTemplateCard")
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setProperty("selected", False)
        self.setMinimumHeight(198)
        self._build()
        self._apply_style()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(_MiniPreview(self.template, self))

        info = QWidget()
        info_layout = QVBoxLayout(info)
        info_layout.setContentsMargins(14, 11, 14, 13)
        info_layout.setSpacing(6)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(8)

        name = QLabel(self.template.name)
        name.setStyleSheet(f"""
            color: {Colors.TEXT_PRIMARY};
            font-size: 13px;
            font-weight: 700;
            background: transparent;
        """)
        top.addWidget(name, 1)

        badge = QLabel(self.template.category.upper())
        badge.setStyleSheet(f"""
            color: {Colors.ACCENT_PRIMARY};
            background: {Colors.ACCENT_GHOST};
            border: 1px solid {Colors.BORDER_ACCENT};
            border-radius: 5px;
            padding: 2px 6px;
            font-size: 8px;
            font-weight: 800;
            letter-spacing: 0.5px;
        """)
        top.addWidget(badge)
        info_layout.addLayout(top)

        desc = QLabel(self.template.description)
        desc.setWordWrap(True)
        desc.setStyleSheet(f"""
            color: {Colors.TEXT_TERTIARY};
            font-size: 10px;
            line-height: 1.35;
            background: transparent;
        """)
        info_layout.addWidget(desc)

        chips = QHBoxLayout()
        chips.setContentsMargins(0, 0, 0, 0)
        chips.setSpacing(6)
        for text in (
            self.template.format_key,
            get_palette(self.template.palette_key).name,
            ", ".join(self.template.plot_types),
        ):
            chip = QLabel(text)
            chip.setStyleSheet(f"""
                color: {Colors.TEXT_MUTED};
                background: {Colors.BG_SURFACE};
                border: 1px solid {Colors.BORDER_SUBTLE};
                border-radius: 5px;
                padding: 2px 6px;
                font-size: 9px;
                font-weight: 700;
            """)
            chips.addWidget(chip)
        chips.addStretch()
        info_layout.addLayout(chips)
        layout.addWidget(info)

    def _apply_style(self):
        self.setStyleSheet(f"""
            QFrame#plotTemplateCard {{
                background: {Colors.BG_ELEVATED};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 14px;
            }}
            QFrame#plotTemplateCard:hover {{
                background: {Colors.BG_SURFACE};
                border-color: {Colors.BORDER_MEDIUM};
            }}
            QFrame#plotTemplateCard[selected="true"] {{
                background: {Colors.ACCENT_GHOST};
                border: 1px solid {Colors.ACCENT_PRIMARY};
            }}
        """)

    def set_selected(self, selected: bool):
        self.setProperty("selected", bool(selected))
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.template.key)
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.double_clicked.emit(self.template.key)
        super().mouseDoubleClickEvent(event)


class PlotTemplatePickerDialog(FramelessDialogMixin, QDialog):
    """Modal gallery for selecting a HeadAnalyser plot template."""

    def __init__(self, plot_type: str = "2D", active_key: str | None = None, parent=None):
        super().__init__(parent)
        self.plot_type = normalize_plot_type(plot_type)
        self._templates = available_templates(self.plot_type)
        self._filter = "All"
        self._cards: list[_TemplateCard] = []
        self._selected_key = active_key or DEFAULT_TEMPLATE_KEY
        if self._selected_key not in {template.key for template in self._templates} and self._templates:
            self._selected_key = self._templates[0].key

        self.setWindowTitle("Plot Templates")
        self.setMinimumSize(760, 560)
        self.setModal(True)
        self.init_frameless_dialog_chrome(
            default_windows="frameless",
            default_other="native",
            resize_margin=10,
            top_resize_margin=10,
        )
        self._build()
        self.bind_frameless_drag_widget(self._chrome_header)

    def selected_template_key(self) -> str:
        return self._selected_key

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.setStyleSheet(f"QDialog {{ background: {Colors.BG_PANEL}; }}")

        root.addWidget(self._build_header())

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(22, 18, 22, 18)
        body_layout.setSpacing(14)

        body_layout.addLayout(self._build_filter_row())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"""
            QScrollArea {{ background: transparent; border: none; }}
            QScrollBar:vertical {{ background: transparent; width: 6px; }}
            QScrollBar::handle:vertical {{
                background: {Colors.BORDER_STRONG};
                border-radius: 3px;
                min-height: 20px;
            }}
        """)

        self._grid_host = QWidget()
        self._grid_host.setStyleSheet("background: transparent;")
        self._grid = QGridLayout(self._grid_host)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setHorizontalSpacing(14)
        self._grid.setVerticalSpacing(14)
        scroll.setWidget(self._grid_host)
        body_layout.addWidget(scroll, 1)

        self._summary = QLabel()
        self._summary.setWordWrap(True)
        self._summary.setStyleSheet(f"""
            color: {Colors.TEXT_TERTIARY};
            font-size: 11px;
            background: {Colors.BG_SURFACE};
            border: 1px solid {Colors.BORDER_SUBTLE};
            border-radius: 10px;
            padding: 9px 12px;
        """)
        body_layout.addWidget(self._summary)

        root.addWidget(body, 1)
        root.addWidget(self._build_footer())

        self._rebuild_cards()
        self._update_summary()

    def _build_header(self) -> QWidget:
        header = QWidget()
        header.setFixedHeight(72)
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
        icon_box.setFixedSize(38, 38)
        icon_box.setAlignment(Qt.AlignCenter)
        icon_box.setPixmap(icon(Icons.PALETTE, Colors.ACCENT_PRIMARY, 16).pixmap(16, 16))
        icon_box.setStyleSheet(f"""
            background: {Colors.ACCENT_GHOST};
            border: 1px solid {Colors.BORDER_ACCENT};
            border-radius: 10px;
        """)
        layout.addWidget(icon_box)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title = QLabel("Plot Templates")
        title.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; font-size: 18px; font-weight: 800; background: transparent;")
        title_col.addWidget(title)
        subtitle = QLabel(f"{self.plot_type} recipes: color style + format + plot defaults")
        subtitle.setStyleSheet(f"color: {Colors.TEXT_TERTIARY}; font-size: 11px; font-weight: 500; background: transparent;")
        title_col.addWidget(subtitle)
        layout.addLayout(title_col, 1)

        close_btn = QPushButton()
        close_btn.setFixedSize(32, 32)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setIcon(icon(Icons.CLOSE, Colors.TEXT_MUTED, 14))
        close_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; border: none; border-radius: 7px; }}
            QPushButton:hover {{ background: {Colors.BG_HOVER}; }}
        """)
        close_btn.clicked.connect(self.reject)
        layout.addWidget(close_btn)
        return header

    def _build_filter_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        self._filter_buttons: dict[str, QPushButton] = {}

        for category in ("All",) + category_names(self._templates):
            btn = QPushButton(category)
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedHeight(28)
            btn.setStyleSheet(f"""
                QPushButton {{
                    color: {Colors.TEXT_TERTIARY};
                    background: {Colors.BG_SURFACE};
                    border: 1px solid {Colors.BORDER_DEFAULT};
                    border-radius: 8px;
                    padding: 0 12px;
                    font-size: 10px;
                    font-weight: 700;
                }}
                QPushButton:hover {{
                    color: {Colors.TEXT_SECONDARY};
                    border-color: {Colors.BORDER_MEDIUM};
                }}
                QPushButton:checked {{
                    color: {Colors.TEXT_PRIMARY};
                    background: {Colors.ACCENT_GHOST};
                    border-color: {Colors.ACCENT_PRIMARY};
                }}
            """)
            btn.setChecked(category == self._filter)
            btn.clicked.connect(lambda _checked=False, c=category: self._set_filter(c))
            self._filter_buttons[category] = btn
            row.addWidget(btn)

        row.addStretch()
        return row

    def _build_footer(self) -> QWidget:
        footer = QWidget()
        footer.setFixedHeight(64)
        footer.setStyleSheet(f"""
            QWidget {{
                background: {Colors.BG_PANEL};
                border-top: 1px solid {Colors.BORDER_DEFAULT};
            }}
        """)
        layout = QHBoxLayout(footer)
        layout.setContentsMargins(22, 0, 22, 0)
        layout.setSpacing(10)

        hint = QLabel("Applies immediately when launched from the toolbar; inside Plot Settings it is applied with the dialog.")
        hint.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: 10px; background: transparent;")
        layout.addWidget(hint, 1)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setStyleSheet(self._secondary_button_style())
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(cancel_btn)

        apply_btn = QPushButton("Apply Template")
        apply_btn.setCursor(Qt.PointingHandCursor)
        apply_btn.setStyleSheet(self._primary_button_style())
        apply_btn.clicked.connect(self.accept)
        layout.addWidget(apply_btn)
        return footer

    def _set_filter(self, category: str):
        self._filter = category
        for key, button in self._filter_buttons.items():
            button.setChecked(key == category)
        self._rebuild_cards()

    def _rebuild_cards(self):
        while self._grid.count():
            item = self._grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._cards = []

        templates = [
            template for template in self._templates
            if self._filter == "All" or template.category == self._filter
        ]

        for idx, template in enumerate(templates):
            card = _TemplateCard(template, self._grid_host)
            card.clicked.connect(self._select_template)
            card.double_clicked.connect(self._accept_template)
            card.set_selected(template.key == self._selected_key)
            self._cards.append(card)
            self._grid.addWidget(card, idx // 2, idx % 2)

        self._grid.setRowStretch(max(0, (len(templates) + 1) // 2), 1)

    def _select_template(self, template_key: str):
        self._selected_key = template_key
        for card in self._cards:
            card.set_selected(card.template.key == template_key)
        self._update_summary()

    def _accept_template(self, template_key: str):
        self._select_template(template_key)
        self.accept()

    def _update_summary(self):
        template = get_template(self._selected_key)
        palette = get_palette(template.palette_key)
        self._summary.setText(
            f"Selected: {template.name}. Format: {template.format_key}. Color style: {palette.name}. {template.description}"
        )

    def _primary_button_style(self) -> str:
        return f"""
            QPushButton {{
                color: #ffffff;
                background: {Colors.ACCENT_PRIMARY};
                border: 1px solid {Colors.ACCENT_PRIMARY};
                border-radius: 8px;
                padding: 9px 18px;
                font-size: 11px;
                font-weight: 800;
            }}
            QPushButton:hover {{ background: {Colors.ACCENT_HOVER}; }}
        """

    def _secondary_button_style(self) -> str:
        return f"""
            QPushButton {{
                color: {Colors.TEXT_SECONDARY};
                background: transparent;
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 8px;
                padding: 9px 18px;
                font-size: 11px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                color: {Colors.TEXT_PRIMARY};
                background: {Colors.BG_SURFACE};
                border-color: {Colors.BORDER_MEDIUM};
            }}
        """
