"""
Shared visual previews for plot templates, color styles, and formats.

The widgets in this module intentionally use synthetic canonical data rather
than live project data. That keeps the selector fast and makes each preview
show only the visual change being selected.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Tuple

from PyQt5.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QPolygonF
from PyQt5.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from styles.colors import Colors
from styles.plot_palettes import DEFAULT_PALETTE_KEY, get_palette
from styles.plot_styles import PlotStyles


_POINTS = (
    (0.16, 0.70),
    (0.29, 0.44),
    (0.43, 0.66),
    (0.58, 0.33),
    (0.72, 0.56),
    (0.85, 0.28),
)


def _qcolor(value: Any, fallback: str = "#64748b") -> QColor:
    color = QColor(str(value or fallback))
    return color if color.isValid() else QColor(fallback)


def _blend(a: QColor, b: QColor, t: float) -> QColor:
    t = max(0.0, min(1.0, float(t)))
    return QColor(
        int(a.red() + (b.red() - a.red()) * t),
        int(a.green() + (b.green() - a.green()) * t),
        int(a.blue() + (b.blue() - a.blue()) * t),
        int(a.alpha() + (b.alpha() - a.alpha()) * t),
    )


def settings_from_target(target: Any, plot_type: str = "2D") -> Dict[str, Any]:
    """Collect the preview-relevant settings from a MainWindow-like object."""
    keys = (
        "current_plot_template",
        "current_color_style",
        "current_plot_format",
        "current_plot_style",
        "show_grid",
        "show_colorbar",
        "show_points",
        "show_contours",
        "fill_contours",
        "show_id_labels",
        "show_arrow",
        "show_arrow_label",
        "colormap_2d",
        "colormap_3d",
        "colormap_vectors",
        "histogram_bar_color",
        "histogram_edge_color",
        "rose_color",
        "id_label_color",
        "head_label_color",
        "arrow_color",
    )
    settings = {key: getattr(target, key, None) for key in keys if hasattr(target, key)}
    settings.setdefault("current_color_style", DEFAULT_PALETTE_KEY)
    settings.setdefault("current_plot_format", getattr(target, "current_plot_style", "Default"))
    settings.setdefault("current_plot_style", settings["current_plot_format"])
    settings.setdefault("show_grid", plot_type in {"Histogram", "Rose Diagram", "Gradient Vectors"})
    settings.setdefault("show_points", plot_type in {"2D", "3D", "Gradient Vectors"})
    settings.setdefault("show_contours", plot_type == "2D")
    settings.setdefault("show_colorbar", plot_type in {"2D", "3D", "Gradient Vectors"})
    return settings


class PlotAppearancePreview(QWidget):
    """Painter-based preview for one plot appearance choice."""

    def __init__(self, plot_type: str = "2D", settings: Dict[str, Any] | None = None, parent=None):
        super().__init__(parent)
        self.plot_type = plot_type or "2D"
        self.settings = dict(settings or {})
        self.setMinimumHeight(86)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_settings(self, settings: Dict[str, Any]) -> None:
        self.settings = dict(settings or {})
        self.update()

    def set_plot_type(self, plot_type: str) -> None:
        self.plot_type = plot_type or "2D"
        self.update()

    def _format_key(self) -> str:
        return str(self.settings.get("current_plot_format") or self.settings.get("current_plot_style") or "Default")

    def _palette(self) -> Tuple[QColor, QColor, QColor, QColor]:
        palette_key = str(self.settings.get("current_color_style") or DEFAULT_PALETTE_KEY)
        swatches = list(get_palette(palette_key).swatches)
        if len(swatches) < 4:
            swatches.extend(["#2563eb", "#38bdf8", "#94a3b8", "#111827"])
        return tuple(_qcolor(v) for v in swatches[:4])  # type: ignore[return-value]

    def _style(self) -> Dict[str, Any]:
        return PlotStyles.get_style(self._format_key())

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(1.0, 1.0, -1.0, -1.0)
        painter.fillRect(rect, QColor("#f8fafc"))
        painter.setClipRect(rect)

        plot_rect = rect.adjusted(22, 13, -18, -22)
        if self.plot_type == "3D":
            self._draw_surface(painter, plot_rect)
        elif self.plot_type == "Gradient Vectors":
            self._draw_vectors(painter, plot_rect)
        elif self.plot_type == "Histogram":
            self._draw_histogram(painter, plot_rect)
        elif self.plot_type == "Rose Diagram":
            self._draw_rose(painter, plot_rect)
        else:
            self._draw_contours(painter, plot_rect)

        if self.plot_type != "3D":
            self._draw_axes(painter, plot_rect)
        if bool(self.settings.get("show_colorbar", self.plot_type in {"2D", "3D", "Gradient Vectors"})):
            self._draw_colorbar(painter, rect.adjusted(rect.width() - 14, 16, -7, -26))

        painter.setClipping(False)
        border = QColor(Colors.BORDER_SUBTLE)
        border.setAlpha(160)
        painter.setPen(QPen(border, 1))
        painter.drawRoundedRect(rect, 10, 10)
        painter.end()

    def _draw_axes(self, painter: QPainter, rect: QRectF) -> None:
        style = self._style()
        text = _qcolor(style.get("text_color"), "#334155")
        spine = _qcolor(style.get("spine_color"), "#475569")
        grid = _qcolor(style.get("grid_color"), "#cbd5e1")
        grid.setAlphaF(float(style.get("grid_alpha", 0.35)))
        fmt = self._format_key()
        show_grid = bool(self.settings.get("show_grid", fmt in {"Scientific", "Publication"}))

        if show_grid:
            painter.setPen(QPen(grid, float(style.get("grid_linewidth", 0.6)), Qt.DashLine if style.get("grid_linestyle") == "--" else Qt.SolidLine))
            for frac in (0.25, 0.5, 0.75):
                if style.get("grid_axis", "both") in {"both", "y"}:
                    y = rect.top() + rect.height() * frac
                    painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
                if style.get("grid_axis", "both") in {"both", "x"}:
                    x = rect.left() + rect.width() * frac
                    painter.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))

        painter.setPen(QPen(spine, float(style.get("spine_width", style.get("line_width", 1.0)))))
        hide = set(style.get("hide_spines", []))
        if "bottom" not in hide:
            painter.drawLine(rect.bottomLeft(), rect.bottomRight())
        if "left" not in hide:
            painter.drawLine(rect.bottomLeft(), rect.topLeft())
        if "top" not in hide:
            painter.drawLine(rect.topLeft(), rect.topRight())
        if "right" not in hide:
            painter.drawLine(rect.topRight(), rect.bottomRight())

        font = QFont(str(style.get("font_family", "sans-serif")), 6 if fmt == "Minimal" else 7)
        font.setBold(bool(style.get("label_weight") == "bold"))
        painter.setFont(font)
        painter.setPen(text)
        painter.drawText(QRectF(rect.left() - 18, rect.bottom() - 8, 16, 10), Qt.AlignRight | Qt.AlignVCenter, "0")
        painter.drawText(QRectF(rect.right() - 10, rect.bottom() + 3, 22, 10), Qt.AlignLeft | Qt.AlignVCenter, "x")
        painter.drawText(QRectF(rect.left() - 18, rect.top() - 4, 16, 10), Qt.AlignRight | Qt.AlignVCenter, "h")

    def _draw_colorbar(self, painter: QPainter, rect: QRectF) -> None:
        p0, p1, p2, p3 = self._palette()
        gradient = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        for idx, color in enumerate((p3, p2, p1, p0)):
            gradient.setColorAt(idx / 3.0, color)
        painter.fillRect(rect, gradient)
        painter.setPen(QPen(QColor("#94a3b8"), 0.8))
        painter.drawRoundedRect(rect, 2, 2)

    def _draw_contours(self, painter: QPainter, rect: QRectF) -> None:
        p0, p1, p2, p3 = self._palette()
        if bool(self.settings.get("fill_contours", False)):
            gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
            for idx, color in enumerate((p0, p1, p2, p3)):
                c = QColor(color)
                c.setAlpha(125)
                gradient.setColorAt(idx / 3.0, c)
            painter.fillRect(rect, gradient)
        for i in range(7):
            color = _blend(p0, p2, i / 6.0)
            color.setAlpha(165)
            painter.setPen(QPen(color, 1.5 if i % 2 == 0 else 0.9))
            path = QPainterPath()
            for step in range(42):
                x_frac = step / 41.0
                wave = math.sin((x_frac * 2.4 + i * 0.24) * math.pi)
                y_frac = 0.14 + i * 0.115 + wave * 0.050
                pt = QPointF(rect.left() + x_frac * rect.width(), rect.top() + y_frac * rect.height())
                if step == 0:
                    path.moveTo(pt)
                else:
                    path.lineTo(pt)
            painter.drawPath(path)

        if bool(self.settings.get("show_points", True)):
            label_color = _qcolor(self.settings.get("id_label_color"), "#334155")
            for idx, (x_frac, y_frac) in enumerate(_POINTS):
                x = rect.left() + x_frac * rect.width()
                y = rect.top() + y_frac * rect.height()
                point = _blend(p0, p3, idx / max(1, len(_POINTS) - 1))
                painter.setPen(Qt.NoPen)
                glow = QColor(point)
                glow.setAlpha(42)
                painter.setBrush(glow)
                painter.drawEllipse(QPointF(x, y), 8.0, 8.0)
                painter.setBrush(point)
                painter.drawEllipse(QPointF(x, y), 3.6, 3.6)
                if bool(self.settings.get("show_id_labels", True)) and idx < 3:
                    painter.setPen(label_color)
                    painter.setFont(QFont("Arial", 6))
                    painter.drawText(QPointF(x + 5, y - 5), f"P{idx + 1}")

        if bool(self.settings.get("show_arrow", True)):
            arrow = _qcolor(self.settings.get("arrow_color"), "#2563eb")
            arrow.setAlpha(210)
            painter.setPen(QPen(arrow, 2.0))
            start = QPointF(rect.left() + rect.width() * 0.62, rect.top() + rect.height() * 0.76)
            end = QPointF(rect.left() + rect.width() * 0.83, rect.top() + rect.height() * 0.34)
            painter.drawLine(start, end)
            painter.setBrush(arrow)
            painter.setPen(Qt.NoPen)
            painter.drawPolygon(QPolygonF([
                QPointF(end.x(), end.y()),
                QPointF(end.x() - 8, end.y() + 2),
                QPointF(end.x() - 2, end.y() + 8),
            ]))

    def _draw_vectors(self, painter: QPainter, rect: QRectF) -> None:
        p0, p1, p2, p3 = self._palette()
        painter.fillRect(rect, QColor("#f8fafc"))
        for idx, (x_frac, y_frac) in enumerate(_POINTS):
            color = _blend(p0, p3, idx / max(1, len(_POINTS) - 1))
            color.setAlpha(225)
            x = rect.left() + x_frac * rect.width()
            y = rect.top() + y_frac * rect.height()
            length = rect.width() * (0.13 + idx * 0.012)
            angle = -0.72 + idx * 0.16
            end = QPointF(x + math.cos(angle) * length, y + math.sin(angle) * length)
            painter.setPen(QPen(color, 2.0))
            painter.drawLine(QPointF(x, y), end)
            painter.setBrush(color)
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QPointF(x, y), 3.2, 3.2)
        painter.setPen(QPen(p2, 3.0))
        painter.drawLine(
            QPointF(rect.left() + rect.width() * 0.18, rect.bottom() - 12),
            QPointF(rect.right() - 18, rect.bottom() - 28),
        )

    def _draw_surface(self, painter: QPainter, rect: QRectF) -> None:
        p0, p1, p2, p3 = self._palette()
        base = QPainterPath()
        base.moveTo(rect.left() + 12, rect.bottom() - 8)
        base.lineTo(rect.left() + rect.width() * 0.38, rect.top() + 12)
        base.lineTo(rect.right() - 12, rect.top() + rect.height() * 0.34)
        base.lineTo(rect.right() - 34, rect.bottom() - 8)
        base.closeSubpath()
        gradient = QLinearGradient(rect.bottomLeft(), rect.topRight())
        for idx, color in enumerate((p0, p1, p2, p3)):
            gradient.setColorAt(idx / 3.0, color)
        painter.fillPath(base, gradient)
        ridge = QColor("#ffffff")
        ridge.setAlpha(125)
        painter.setPen(QPen(ridge, 1.0))
        for i in range(5):
            y = rect.top() + 18 + i * rect.height() * 0.13
            painter.drawLine(QPointF(rect.left() + 24 + i * 7, y), QPointF(rect.right() - 24, y + 10))
        painter.setPen(QPen(QColor("#475569"), 1.2))
        painter.drawPath(base)

    def _draw_histogram(self, painter: QPainter, rect: QRectF) -> None:
        p0, p1, p2, _p3 = self._palette()
        bar = _qcolor(self.settings.get("histogram_bar_color"), p1.name())
        if not bar.isValid():
            bar = p1
        heights = (0.24, 0.42, 0.68, 0.86, 0.72, 0.45, 0.26)
        gap = 4.0
        width = (rect.width() - gap * (len(heights) - 1)) / len(heights)
        for idx, frac in enumerate(heights):
            h = rect.height() * frac
            x = rect.left() + idx * (width + gap)
            color = _blend(p0, bar, idx / max(1, len(heights) - 1))
            color.setAlpha(215)
            painter.fillRect(QRectF(x, rect.bottom() - h, width, h), color)
        painter.setPen(QPen(p2, 1.8))
        mean_x = rect.left() + rect.width() * 0.54
        painter.drawLine(QPointF(mean_x, rect.top() + 6), QPointF(mean_x, rect.bottom()))

    def _draw_rose(self, painter: QPainter, rect: QRectF) -> None:
        p0, p1, p2, p3 = self._palette()
        size = min(rect.width(), rect.height())
        rose = QRectF(rect.center().x() - size * 0.42, rect.center().y() - size * 0.42, size * 0.84, size * 0.84)
        painter.setPen(QPen(QColor("#cbd5e1"), 0.8))
        painter.drawEllipse(rose)
        painter.drawEllipse(rose.adjusted(size * 0.16, size * 0.16, -size * 0.16, -size * 0.16))
        for idx, (start, span, color) in enumerate(
            ((16, 38, p0), (70, 28, p1), (138, 48, p2), (230, 36, p3), (300, 30, p1))
        ):
            c = QColor(color)
            c.setAlpha(190)
            painter.setBrush(c)
            painter.setPen(Qt.NoPen)
            painter.drawPie(rose, start * 16, span * 16)
        painter.setPen(QPen(p3, 2.2))
        center = rose.center()
        painter.drawLine(center, QPointF(center.x() + size * 0.26, center.y() - size * 0.22))


class AppearancePreviewCard(QFrame):
    clicked = pyqtSignal(str)
    double_clicked = pyqtSignal(str)

    def __init__(
        self,
        key: str,
        title: str,
        subtitle: str,
        plot_type: str,
        settings: Dict[str, Any],
        *,
        badge: str = "",
        compact: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self.key = key
        self.title = title
        self.subtitle = subtitle
        self.badge = badge
        self.setObjectName("appearancePreviewCard")
        self.setCursor(Qt.PointingHandCursor)
        self.setProperty("selected", False)
        self.setMinimumHeight(136 if compact else 226)
        self._build(plot_type, settings, compact)
        self._apply_style()

    def _build(self, plot_type: str, settings: Dict[str, Any], compact: bool) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        preview = PlotAppearancePreview(plot_type, settings, self)
        preview.setFixedHeight(82 if compact else 132)
        layout.addWidget(preview)

        info = QWidget(self)
        info_layout = QVBoxLayout(info)
        info_layout.setContentsMargins(10 if compact else 14, 8, 10 if compact else 14, 10)
        info_layout.setSpacing(4)
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        title = QLabel(self.title)
        title.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; font-size: {11 if compact else 13}px; font-weight: 800; background: transparent;")
        top.addWidget(title, 1)
        if self.badge:
            badge = QLabel(self.badge.upper())
            badge.setStyleSheet(f"""
                color: {Colors.ACCENT_PRIMARY};
                background: {Colors.ACCENT_GHOST};
                border: 1px solid {Colors.BORDER_ACCENT};
                border-radius: 5px;
                padding: 1px 5px;
                font-size: 8px;
                font-weight: 800;
            """)
            top.addWidget(badge)
        info_layout.addLayout(top)
        subtitle = QLabel(self.subtitle)
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(f"color: {Colors.TEXT_TERTIARY}; font-size: {9 if compact else 10}px; background: transparent;")
        info_layout.addWidget(subtitle)
        layout.addWidget(info)

    def _apply_style(self) -> None:
        self.setStyleSheet(f"""
            QFrame#appearancePreviewCard {{
                background: {Colors.BG_ELEVATED};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 13px;
            }}
            QFrame#appearancePreviewCard:hover {{
                background: {Colors.BG_SURFACE};
                border-color: {Colors.BORDER_MEDIUM};
            }}
            QFrame#appearancePreviewCard[selected="true"] {{
                background: {Colors.ACCENT_GHOST};
                border: 1px solid {Colors.ACCENT_PRIMARY};
            }}
        """)

    def set_selected(self, selected: bool) -> None:
        self.setProperty("selected", bool(selected))
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.key)
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.double_clicked.emit(self.key)
        super().mouseDoubleClickEvent(event)
