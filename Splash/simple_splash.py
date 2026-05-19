"""
HeadAnalyser V2 - startup splash screen.

Poster-style PyQt5 splash with animated hydraulic contours and a progress API
compatible with the Kornstoerrelse startup shell.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Optional

from PyQt5.QtCore import QEasingCurve, QPointF, QPropertyAnimation, QRectF, QTimer, Qt, QVariantAnimation
from PyQt5.QtGui import QBrush, QColor, QFont, QFontMetricsF, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QRegion
from PyQt5.QtWidgets import QApplication, QWidget


def _blend(c1: QColor, c2: QColor, amount: float) -> QColor:
    amount = max(0.0, min(1.0, amount))
    return QColor(
        round(c1.red() + (c2.red() - c1.red()) * amount),
        round(c1.green() + (c2.green() - c1.green()) * amount),
        round(c1.blue() + (c2.blue() - c1.blue()) * amount),
        round(c1.alpha() + (c2.alpha() - c1.alpha()) * amount),
    )


def _with_alpha(color: QColor, alpha: int) -> QColor:
    out = QColor(color)
    out.setAlpha(max(0, min(255, int(alpha))))
    return out


def _resource_path(*parts: str) -> str:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS)  # type: ignore[attr-defined]
    else:
        base = Path(__file__).resolve().parents[1]
    return str(base.joinpath(*parts))


class SimpleSplash(QWidget):
    """Hydraulic-gradient splash with animated contours and progress state."""

    _CONTOUR_COLORS = (
        QColor(146, 197, 253, 62),
        QColor(96, 165, 250, 54),
        QColor(56, 189, 248, 46),
        QColor(129, 140, 248, 42),
    )

    def __init__(self, backdrop_path: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.SplashScreen | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setFixedSize(700, 420)
        self._corner_radius = 20
        self._backdrop_path = backdrop_path
        self._logo_pixmap = QPixmap(_resource_path("assets", "logo_newest.png"))
        self._dtu_pixmap = QPixmap(_resource_path("assets", "DTU_logo.png"))

        self._display_progress = 0.0
        self._target_progress = 0
        self._motion_phase = 0.0
        self._status_mix = 1.0
        self._stage_text = "Starting HeadAnalyser"
        self._stage_previous = ""
        self._detail_text = "Preparing the hydraulic-gradient workspace."
        self._detail_previous = ""
        self.fade_animation: Optional[QPropertyAnimation] = None

        self._progress_animation = QVariantAnimation(self)
        self._progress_animation.setDuration(420)
        self._progress_animation.setEasingCurve(QEasingCurve.OutCubic)
        self._progress_animation.valueChanged.connect(self._on_progress_value)

        self._status_animation = QVariantAnimation(self)
        self._status_animation.setDuration(220)
        self._status_animation.setEasingCurve(QEasingCurve.InOutQuad)
        self._status_animation.valueChanged.connect(self._on_status_mix)

        self._motion_timer = QTimer(self)
        self._motion_timer.setInterval(33)
        self._motion_timer.timeout.connect(self._tick)
        self._motion_timer.start()

        self.setWindowOpacity(1.0)
        self._center_on_screen()

    def _center_on_screen(self) -> None:
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            self.move(geo.center().x() - self.width() // 2, geo.center().y() - self.height() // 2)

    def _tick(self) -> None:
        self._motion_phase = (self._motion_phase + 0.028) % 1000.0
        self.update()

    def _on_progress_value(self, value) -> None:
        self._display_progress = float(value)
        self.update()

    def _on_status_mix(self, value) -> None:
        self._status_mix = float(value)
        self.update()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), self._corner_radius, self._corner_radius)
        self.setMask(QRegion(path.toFillPolygon().toPolygon()))

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.raise_()
        self.activateWindow()

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        clip = QPainterPath()
        clip.addRoundedRect(QRectF(self.rect()), self._corner_radius, self._corner_radius)
        painter.setClipPath(clip)

        self._draw_background(painter)
        self._draw_contours(painter)
        self._draw_depth_panel(painter)
        self._draw_gradient_instrument(painter)
        self._draw_text_block(painter)
        self._draw_progress_rail(painter)
        self._draw_footer(painter)
        self._draw_frame(painter)
        painter.end()

    def _draw_background(self, painter: QPainter) -> None:
        rect = self.rect()
        base = QLinearGradient(0, 0, rect.width(), rect.height())
        base.setColorAt(0.0, QColor(6, 12, 24))
        base.setColorAt(0.45, QColor(11, 25, 44))
        base.setColorAt(1.0, QColor(20, 39, 66))
        painter.fillRect(rect, base)

        glow = QLinearGradient(rect.width() * 0.24, 0, rect.width(), rect.height())
        glow.setColorAt(0.0, QColor(56, 189, 248, 42))
        glow.setColorAt(0.48, QColor(37, 99, 235, 20))
        glow.setColorAt(1.0, QColor(15, 23, 42, 0))
        painter.fillRect(rect, glow)

        left_wash = QLinearGradient(0, 0, rect.width() * 0.55, 0)
        left_wash.setColorAt(0.0, QColor(2, 6, 23, 118))
        left_wash.setColorAt(0.62, QColor(2, 6, 23, 56))
        left_wash.setColorAt(1.0, QColor(2, 6, 23, 0))
        painter.fillRect(rect, left_wash)

        grid_pen = QPen(QColor(147, 197, 253, 20), 1.0)
        painter.setPen(grid_pen)
        for x in range(0, self.width() + 1, 32):
            painter.drawLine(x, 0, x, self.height())
        for y in range(0, self.height() + 1, 32):
            painter.drawLine(0, y, self.width(), y)

        painter.setPen(QPen(QColor(191, 219, 254, 70), 1.2))
        painter.drawLine(44, 34, 118, 34)
        painter.drawLine(self.width() - 118, 34, self.width() - 44, 34)

        panel = QRectF(28, 28, self.width() - 56, self.height() - 56)
        painter.setPen(QPen(QColor(147, 197, 253, 24), 1.0))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(panel, 16, 16)

    def _field_value(self, x: float, y: float) -> float:
        """Smooth scalar field used by the marching-squares contour renderer."""
        width = max(1.0, float(self.width()))
        height = max(1.0, float(self.height()))
        nx = x / width
        ny = y / height
        phase = self._motion_phase * 0.035

        value = (
            math.sin((nx * 2.35 + phase) * math.tau) * 0.42
            + math.cos((ny * 2.05 - phase * 0.72) * math.tau) * 0.35
            + math.sin((nx * 1.55 + ny * 2.15 + phase * 0.48) * math.tau) * 0.32
            + math.cos((nx * 3.40 - ny * 1.35 - phase * 0.36) * math.tau) * 0.18
        )

        for idx, (cx, cy, weight, stretch_x, stretch_y) in enumerate((
            (0.28, 0.28, 0.72, 0.060, 0.035),
            (0.70, 0.34, 0.58, 0.050, 0.045),
            (0.47, 0.72, 0.50, 0.075, 0.042),
            (0.82, 0.76, 0.38, 0.060, 0.055),
        )):
            drift_x = math.sin(phase * 2.2 + idx) * 0.018
            drift_y = math.cos(phase * 1.8 + idx * 0.7) * 0.016
            dx = nx - (cx + drift_x)
            dy = ny - (cy + drift_y)
            value += weight * math.exp(-((dx * dx) / stretch_x + (dy * dy) / stretch_y))

        return value

    @staticmethod
    def _interpolate(a: QPointF, b: QPointF, va: float, vb: float, threshold: float) -> QPointF:
        if abs(vb - va) < 1e-9:
            factor = 0.5
        else:
            factor = max(0.0, min(1.0, (threshold - va) / (vb - va)))
        return QPointF(a.x() + (b.x() - a.x()) * factor, a.y() + (b.y() - a.y()) * factor)

    def _contour_segments_for_cell(
        self,
        points: tuple[QPointF, QPointF, QPointF, QPointF],
        values: tuple[float, float, float, float],
        threshold: float,
    ) -> tuple[tuple[QPointF, QPointF], ...]:
        nw, ne, se, sw = values
        p_nw, p_ne, p_se, p_sw = points
        top = self._interpolate(p_nw, p_ne, nw, ne, threshold)
        right = self._interpolate(p_ne, p_se, ne, se, threshold)
        bottom = self._interpolate(p_sw, p_se, sw, se, threshold)
        left = self._interpolate(p_nw, p_sw, nw, sw, threshold)
        case = (
            (1 if nw > threshold else 0) << 3
            | (1 if ne > threshold else 0) << 2
            | (1 if se > threshold else 0) << 1
            | (1 if sw > threshold else 0)
        )
        return {
            1: ((left, bottom),),
            2: ((right, bottom),),
            3: ((left, right),),
            4: ((top, right),),
            5: ((left, top), (bottom, right)),
            6: ((top, bottom),),
            7: ((left, top),),
            8: ((left, top),),
            9: ((top, bottom),),
            10: ((top, right), (bottom, left)),
            11: ((top, right),),
            12: ((left, right),),
            13: ((right, bottom),),
            14: ((left, bottom),),
        }.get(case, tuple())

    def _draw_contours(self, painter: QPainter) -> None:
        step = 10.0
        cols = int(math.ceil(self.width() / step)) + 2
        rows = int(math.ceil(self.height() / step)) + 2
        values: list[list[float]] = []
        min_value = float("inf")
        max_value = float("-inf")

        for row in range(rows):
            row_values = []
            y = (row - 1) * step
            for col in range(cols):
                x = (col - 1) * step
                value = self._field_value(x, y)
                row_values.append(value)
                min_value = min(min_value, value)
                max_value = max(max_value, value)
            values.append(row_values)

        span = max(0.001, max_value - min_value)
        threshold_count = 15
        for idx in range(1, threshold_count + 1):
            threshold = min_value + span * (idx / float(threshold_count + 1))
            path = QPainterPath()
            for row in range(rows - 1):
                for col in range(cols - 1):
                    cell_values = (
                        values[row][col],
                        values[row][col + 1],
                        values[row + 1][col + 1],
                        values[row + 1][col],
                    )
                    if all(value > threshold for value in cell_values) or all(value <= threshold for value in cell_values):
                        continue
                    x = (col - 1) * step
                    y = (row - 1) * step
                    points = (
                        QPointF(x, y),
                        QPointF(x + step, y),
                        QPointF(x + step, y + step),
                        QPointF(x, y + step),
                    )
                    for start, end in self._contour_segments_for_cell(points, cell_values, threshold):
                        path.moveTo(start)
                        path.lineTo(end)

            is_major = idx % 4 == 0
            if is_major:
                painter.setPen(QPen(QColor(125, 211, 252, 26), 3.2))
                painter.drawPath(path)
                painter.setPen(QPen(QColor(186, 230, 253, 82), 1.25))
            else:
                painter.setPen(QPen(QColor(129, 140, 248, 42), 0.75))
            painter.drawPath(path)

    def _draw_depth_panel(self, painter: QPainter) -> None:
        panel_rect = QRectF(42, 264, 318, 58)
        panel_grad = QLinearGradient(panel_rect.topLeft(), panel_rect.bottomRight())
        panel_grad.setColorAt(0.0, QColor(15, 23, 42, 122))
        panel_grad.setColorAt(1.0, QColor(8, 47, 73, 82))
        painter.setPen(QPen(QColor(125, 211, 252, 50), 1.0))
        painter.setBrush(QBrush(panel_grad))
        painter.drawRoundedRect(panel_rect, 14, 14)

        progress_ratio = max(0.0, min(1.0, self._display_progress / 100.0))
        left = panel_rect.left() + 18
        top = panel_rect.top() + 9
        painter.setFont(QFont("Segoe UI", 8, QFont.DemiBold))
        painter.setPen(QColor(125, 211, 252, 190))
        painter.drawText(QRectF(left, top, 120, 14), Qt.AlignLeft | Qt.AlignVCenter, "SYSTEM CHECK")

        chips = (
            ("DATA", 0.24),
            ("MESH", 0.52),
            ("GRADIENT", 0.78),
        )
        for idx, (label, threshold) in enumerate(chips):
            x = left + idx * 88
            chip = QRectF(x, top + 25, 74, 22)
            active = progress_ratio >= threshold
            fill = QColor(56, 189, 248, 46 if active else 18)
            border = QColor(125, 211, 252, 94 if active else 34)
            painter.setPen(QPen(border, 1.0))
            painter.setBrush(fill)
            painter.drawRoundedRect(chip, 12, 12)
            painter.setFont(QFont("Cascadia Mono", 7, QFont.DemiBold))
            painter.setPen(QColor(224, 242, 254, 230 if active else 130))
            painter.drawText(chip, Qt.AlignCenter, label)

    def _draw_gradient_instrument(self, painter: QPainter) -> None:
        field_rect = QRectF(self.width() - 286, 82, 218, 204)
        field_grad = QLinearGradient(field_rect.topLeft(), field_rect.bottomRight())
        field_grad.setColorAt(0.0, QColor(15, 23, 42, 104))
        field_grad.setColorAt(0.58, QColor(14, 116, 144, 36))
        field_grad.setColorAt(1.0, QColor(30, 41, 59, 92))
        painter.setPen(QPen(QColor(125, 211, 252, 46), 1.0))
        painter.setBrush(field_grad)
        painter.drawRoundedRect(field_rect, 24, 24)

        center = field_rect.center()
        progress_ratio = max(0.0, min(1.0, self._display_progress / 100.0))
        pulse = 0.5 + 0.5 * math.sin(self._motion_phase * 2.3)

        glow_rect = QRectF(center.x() - 70, center.y() - 66, 140, 132)
        glow = QLinearGradient(glow_rect.topLeft(), glow_rect.bottomRight())
        glow.setColorAt(0.0, QColor(59, 130, 246, 28 + int(progress_ratio * 24)))
        glow.setColorAt(0.52, QColor(14, 165, 233, 46 + int(pulse * 18)))
        glow.setColorAt(1.0, QColor(129, 140, 248, 28))
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(glow))
        painter.drawEllipse(glow_rect)

        for ring_idx, radius in enumerate((82, 58)):
            alpha = 22 + ring_idx * 20 + int(progress_ratio * 18)
            painter.setPen(QPen(QColor(125, 211, 252, alpha), 1.0))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(center, radius, radius * 0.68)

        if not self._logo_pixmap.isNull():
            painter.save()
            logo_size = 152
            logo = self._logo_pixmap.scaled(logo_size, logo_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            shadow_rect = QRectF(
                center.x() - logo.width() / 2 + 4,
                center.y() - logo.height() / 2 + 10,
                logo.width(),
                logo.height(),
            )
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(0, 0, 0, 42))
            painter.drawEllipse(shadow_rect.adjusted(12, 22, -12, -18))
            painter.setOpacity(0.98)
            painter.drawPixmap(
                int(center.x() - logo.width() / 2),
                int(center.y() - logo.height() / 2),
                logo,
            )
            painter.restore()
        else:
            painter.setFont(QFont("Segoe UI", 34, QFont.DemiBold))
            painter.setPen(QColor(224, 242, 254))
            painter.drawText(field_rect, Qt.AlignCenter, "HA")

        caption_rect = QRectF(field_rect.left() + 28, field_rect.bottom() - 36, field_rect.width() - 56, 24)
        painter.setPen(QPen(QColor(125, 211, 252, 62), 1.0))
        painter.setBrush(QColor(8, 47, 73, 112))
        painter.drawRoundedRect(caption_rect, 12, 12)
        painter.setFont(QFont("Cascadia Mono", 7, QFont.DemiBold))
        painter.setPen(QColor(224, 242, 254, 220))
        painter.drawText(caption_rect, Qt.AlignCenter, "HEADANALYSER")

    def _title_font(self) -> QFont:
        font = QFont("Segoe UI", 34, QFont.DemiBold)
        font.setLetterSpacing(QFont.AbsoluteSpacing, -0.8)
        return font

    def _draw_text_block(self, painter: QPainter) -> None:
        left = 42.0
        top = 50.0

        title_font = self._title_font()
        metrics = QFontMetricsF(title_font)
        painter.setFont(title_font)
        title_baseline = top + metrics.ascent()
        painter.setPen(QColor(248, 250, 252))
        painter.drawText(QPointF(left, title_baseline), "Head")
        head_width = metrics.horizontalAdvance("Head")
        painter.setPen(QColor(129, 140, 248))
        painter.drawText(QPointF(left + head_width - 1.0, title_baseline), "Analyser")

        pill_rect = QRectF(left + metrics.horizontalAdvance("HeadAnalyser") + 15.0, top + 15.0, 78.0, 24.0)
        painter.setPen(QPen(QColor(129, 140, 248, 122), 1.0))
        painter.setBrush(QColor(67, 56, 202, 72))
        painter.drawRoundedRect(pill_rect, 12, 12)
        painter.setFont(QFont("Cascadia Mono", 7, QFont.DemiBold))
        painter.setPen(QColor(224, 231, 255, 228))
        painter.drawText(pill_rect, Qt.AlignCenter, "V2.0 BETA")

        subtitle_top = top + metrics.height() + 11.0
        subtitle_font = QFont("Segoe UI", 10, QFont.Medium)
        subtitle_font.setLetterSpacing(QFont.AbsoluteSpacing, 0.55)
        painter.setFont(subtitle_font)
        painter.setPen(QColor(186, 230, 253))
        painter.drawText(
            QRectF(left, subtitle_top, 390, 20),
            Qt.AlignLeft | Qt.AlignVCenter,
            "Hydraulic head analysis and gradient computation",
        )

        label_top = subtitle_top + 43.0
        label_font = QFont("Segoe UI", 8, QFont.DemiBold)
        label_font.setLetterSpacing(QFont.AbsoluteSpacing, 1.2)
        painter.setFont(label_font)
        painter.setPen(QColor(125, 211, 252))
        painter.drawText(QRectF(left, label_top, 180, 16), Qt.AlignLeft | Qt.AlignVCenter, "STARTUP STATUS")

        painter.setPen(QPen(QColor(56, 189, 248, 150), 1.6))
        painter.drawLine(QPointF(left, label_top - 7.0), QPointF(left + 30.0, label_top - 7.0))

        stage_rect = QRectF(left, label_top + 21.0, 352, 22)
        detail_rect = QRectF(left, label_top + 45.0, 352, 18)
        self._draw_transition_text(
            painter,
            stage_rect,
            self._stage_previous,
            self._stage_text,
            QFont("Cascadia Mono", 10, QFont.Medium),
            QColor(226, 232, 240),
        )
        self._draw_transition_text(
            painter,
            detail_rect,
            self._detail_previous,
            self._detail_text,
            QFont("Segoe UI", 9),
            QColor(148, 163, 184),
        )

    def _draw_transition_text(
        self,
        painter: QPainter,
        rect: QRectF,
        previous: str,
        current: str,
        font: QFont,
        color: QColor,
    ) -> None:
        painter.setFont(font)
        del previous
        painter.setPen(_with_alpha(color, round(color.alpha() * self._status_mix)))
        text = QFontMetricsF(font).elidedText(str(current), Qt.ElideRight, rect.width())
        painter.drawText(rect, Qt.AlignLeft | Qt.AlignVCenter, text)

    def _draw_progress_rail(self, painter: QPainter) -> None:
        rail_x = 42.0
        rail_y = self.height() - 58.0
        rail_width = self.width() - 128.0
        progress_ratio = max(0.0, min(1.0, self._display_progress / 100.0))
        progress_x = rail_x + rail_width * progress_ratio

        track_pen = QPen(QColor(148, 163, 184, 84), 2.0)
        track_pen.setCapStyle(Qt.RoundCap)
        painter.setPen(track_pen)
        painter.drawLine(QPointF(rail_x, rail_y), QPointF(rail_x + rail_width, rail_y))

        for marker in range(1, 4):
            tick_x = rail_x + rail_width * (marker / 4.0)
            painter.setPen(QPen(QColor(147, 197, 253, 90), 1.0))
            painter.drawLine(QPointF(tick_x, rail_y - 6.0), QPointF(tick_x, rail_y + 6.0))

        fill_gradient = QLinearGradient(rail_x, rail_y, rail_x + rail_width, rail_y)
        fill_gradient.setColorAt(0.0, QColor(37, 99, 235))
        fill_gradient.setColorAt(0.55, QColor(14, 165, 233))
        fill_gradient.setColorAt(1.0, QColor(125, 211, 252))
        fill_pen = QPen(QBrush(fill_gradient), 3.2)
        fill_pen.setCapStyle(Qt.RoundCap)
        painter.setPen(fill_pen)
        painter.drawLine(QPointF(rail_x, rail_y), QPointF(progress_x, rail_y))

        cap_color = _blend(QColor(14, 165, 233), QColor(224, 242, 254), progress_ratio * 0.45)
        painter.setPen(Qt.NoPen)
        painter.setBrush(_with_alpha(cap_color, 235))
        painter.drawEllipse(QPointF(progress_x, rail_y), 4.0, 4.0)

        painter.setFont(QFont("Cascadia Mono", 10, QFont.Medium))
        painter.setPen(QColor(219, 234, 254))
        painter.drawText(
            QRectF(self.width() - 76.0, rail_y - 12.0, 38.0, 20.0),
            Qt.AlignRight | Qt.AlignVCenter,
            f"{int(round(self._display_progress)):>3d}%",
        )

    def _draw_footer(self, painter: QPainter) -> None:
        footer_y = self.height() - 25.0
        left = 42.0

        if not self._dtu_pixmap.isNull():
            painter.save()
            painter.setOpacity(0.9)
            logo = self._dtu_pixmap.scaled(24, 24, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            painter.drawPixmap(int(left), int(footer_y - 17.0), logo)
            painter.restore()

        painter.setFont(QFont("Segoe UI", 9, QFont.DemiBold))
        painter.setPen(QColor(226, 232, 240, 204))
        painter.drawText(
            QRectF(left + 34.0, footer_y - 15.0, 260.0, 20.0),
            Qt.AlignLeft | Qt.AlignVCenter,
            "Created by Oliver Brincks Lund",
        )

        painter.setFont(QFont("Segoe UI", 9, QFont.DemiBold))
        painter.setPen(QColor(125, 211, 252, 190))
        painter.drawText(
            QRectF(self.width() - 170.0, footer_y - 15.0, 128.0, 20.0),
            Qt.AlignRight | Qt.AlignVCenter,
            "DTU Sustain",
        )

    def _draw_frame(self, painter: QPainter) -> None:
        frame_rect = QRectF(self.rect()).adjusted(1.0, 1.0, -1.0, -1.0)
        painter.setPen(QPen(QColor(147, 197, 253, 92), 1.1))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(frame_rect, self._corner_radius, self._corner_radius)

    def _set_status_text(self, stage: str, detail: Optional[str] = None, *, immediate: bool = False) -> None:
        next_stage = (stage or "").strip() or "Initializing..."
        next_detail = self._detail_text if detail is None else (detail or "").strip()
        if next_stage == self._stage_text and next_detail == self._detail_text:
            return

        self._stage_previous = self._stage_text
        self._detail_previous = self._detail_text
        self._stage_text = next_stage
        self._detail_text = next_detail

        self._status_animation.stop()
        if immediate:
            self._status_mix = 1.0
        else:
            self._status_mix = 0.0
            self._status_animation.setStartValue(0.0)
            self._status_animation.setEndValue(1.0)
            self._status_animation.start()
        self.update()

    def _animate_progress(self, value: int, *, immediate: bool = False) -> None:
        incoming = max(0, min(100, int(value)))
        self._target_progress = max(self._target_progress, incoming)
        self._progress_animation.stop()
        if immediate:
            self._display_progress = float(self._target_progress)
            self.update()
            return
        self._progress_animation.setStartValue(self._display_progress)
        self._progress_animation.setEndValue(float(self._target_progress))
        self._progress_animation.start()

    def set_backdrop(self, image_path: str) -> None:
        """Retained for compatibility; the HeadAnalyser splash is painted."""
        self._backdrop_path = image_path

    def set_message(self, message: str) -> None:
        self._set_status_text(message)

    def set_progress(
        self,
        value: int,
        message: str = "",
        detail: Optional[str] = None,
        *,
        immediate: bool = False,
    ) -> None:
        self._animate_progress(value, immediate=immediate)
        self._set_status_text(message or self._stage_text, detail, immediate=immediate)

    def finish_with_fade(self, message: str = "Ready") -> None:
        self.set_message(message)
        QTimer.singleShot(260, self._start_fade_out)

    def _start_fade_out(self) -> None:
        if self.fade_animation:
            self.fade_animation.stop()
        self.fade_animation = QPropertyAnimation(self, b"windowOpacity")
        self.fade_animation.setDuration(240)
        self.fade_animation.setStartValue(self.windowOpacity())
        self.fade_animation.setEndValue(0.0)
        self.fade_animation.setEasingCurve(QEasingCurve.InQuad)
        self.fade_animation.finished.connect(self.close)
        self.fade_animation.start()
