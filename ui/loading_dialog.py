"""
HeadAnalyser V2 - reusable loading/progress dialog.

Hydraulic-contour themed progress surface for report generation, data loading,
and future long-running operations.
"""

from __future__ import annotations

import math
import sys
import time
from pathlib import Path

from PyQt5.QtCore import QPointF, QRectF, QTimer, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QBrush, QPixmap
from PyQt5.QtWidgets import QDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from qt_chrome import FramelessDialogMixin
from styles.colors import Colors


def _rgba(color: QColor, alpha: int) -> str:
    return f"rgba({color.red()}, {color.green()}, {color.blue()}, {max(0, min(255, int(alpha)))})"


def _resource_path(*parts: str) -> str:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS)  # type: ignore[attr-defined]
    else:
        base = Path(__file__).resolve().parents[1]
    return str(base.joinpath(*parts))


def _with_alpha(color: QColor, alpha: int) -> QColor:
    out = QColor(color)
    out.setAlpha(max(0, min(255, int(alpha))))
    return out


class _HeaderMark(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(34, 34)
        self._logo = QPixmap(_resource_path("assets", "logo_newest.png"))

    def paintEvent(self, event):
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(1.0, 1.0, -1.0, -1.0)
        grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
        grad.setColorAt(0.0, QColor(30, 64, 175, 120))
        grad.setColorAt(1.0, QColor(14, 165, 233, 68))
        painter.setPen(QPen(QColor(125, 211, 252, 88), 1.0))
        painter.setBrush(QBrush(grad))
        painter.drawRoundedRect(rect, 10, 10)

        if not self._logo.isNull():
            logo = self._logo.scaled(28, 28, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            painter.drawPixmap((self.width() - logo.width()) // 2, (self.height() - logo.height()) // 2, logo)
        else:
            painter.setFont(QFont("Segoe UI", 10, QFont.DemiBold))
            painter.setPen(QColor(224, 242, 254))
            painter.drawText(rect, Qt.AlignCenter, "HA")
        painter.end()


class _LoadingSpinner(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._angle = 0
        self._phase = 0.0
        self._logo = QPixmap(_resource_path("assets", "logo_newest.png"))
        self.setFixedWidth(178)
        self.setMinimumHeight(214)
        self._timer = QTimer(self)
        self._timer.setInterval(58)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def stop(self):
        self._timer.stop()
        self.update()

    def _tick(self):
        self._angle = (self._angle + 7) % 360
        self._phase = (self._phase + 0.035) % 1000.0
        self.update()

    def _field_value(self, x: float, y: float, rect: QRectF) -> float:
        """Small-panel version of the splash contour field."""
        width = max(1.0, float(rect.width()))
        height = max(1.0, float(rect.height()))
        nx = (x - rect.left()) / width
        ny = (y - rect.top()) / height
        phase = self._phase * 0.035

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

    def _draw_contours(self, painter: QPainter, rect: QRectF) -> None:
        step = 9.0
        cols = int(math.ceil(rect.width() / step)) + 2
        rows = int(math.ceil(rect.height() / step)) + 2
        values: list[list[float]] = []
        min_value = float("inf")
        max_value = float("-inf")

        for row in range(rows):
            row_values = []
            y = rect.top() + (row - 1) * step
            for col in range(cols):
                x = rect.left() + (col - 1) * step
                value = self._field_value(x, y, rect)
                row_values.append(value)
                min_value = min(min_value, value)
                max_value = max(max_value, value)
            values.append(row_values)

        span = max(0.001, max_value - min_value)
        threshold_count = 11
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
                    x = rect.left() + (col - 1) * step
                    y = rect.top() + (row - 1) * step
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
                painter.setPen(QPen(QColor(125, 211, 252, 28), 3.0))
                painter.drawPath(path)
                painter.setPen(QPen(QColor(186, 230, 253, 86), 1.15))
            else:
                painter.setPen(QPen(QColor(129, 140, 248, 48), 0.72))
            painter.drawPath(path)

    def paintEvent(self, event):
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)

        panel = QPainterPath()
        panel.addRoundedRect(rect, 18, 18)
        background = QLinearGradient(rect.topLeft(), rect.bottomRight())
        if Colors.is_dark():
            background.setColorAt(0.0, QColor(7, 18, 32))
            background.setColorAt(0.55, QColor(8, 28, 48))
            background.setColorAt(1.0, QColor(11, 38, 61))
            border = QColor(125, 211, 252, 48)
            grid = QColor(148, 163, 184, 22)
            label = QColor(203, 213, 225)
        else:
            background.setColorAt(0.0, QColor(248, 250, 252))
            background.setColorAt(0.55, QColor(232, 241, 250))
            background.setColorAt(1.0, QColor(216, 231, 245))
            border = QColor(37, 99, 235, 46)
            grid = QColor(37, 99, 235, 20)
            label = QColor(71, 85, 105)

        painter.setPen(QPen(border, 1.0))
        painter.setBrush(QBrush(background))
        painter.drawPath(panel)

        painter.save()
        painter.setClipPath(panel)
        painter.setPen(QPen(grid, 1.0))
        for x in range(20, self.width(), 28):
            painter.drawLine(x, 0, x, self.height())
        for y in range(20, self.height(), 28):
            painter.drawLine(0, y, self.width(), y)

        contour_rect = rect.adjusted(10, 8, -10, -44)
        self._draw_contours(painter, contour_rect)

        wash = QLinearGradient(rect.topLeft(), rect.bottomRight())
        wash.setColorAt(0.0, QColor(56, 189, 248, 42 if Colors.is_dark() else 28))
        wash.setColorAt(0.58, QColor(37, 99, 235, 18 if Colors.is_dark() else 10))
        wash.setColorAt(1.0, QColor(15, 23, 42, 0))
        painter.fillPath(panel, QBrush(wash))
        painter.restore()

        center = QPointF(rect.center().x(), rect.top() + 98.0)
        outer = QRectF(center.x() - 42, center.y() - 42, 84, 84)
        inner = QRectF(center.x() - 31, center.y() - 31, 62, 62)

        glow = QLinearGradient(outer.topLeft(), outer.bottomRight())
        glow.setColorAt(0.0, QColor(37, 99, 235, 78))
        glow.setColorAt(0.54, QColor(14, 165, 233, 84))
        glow.setColorAt(1.0, QColor(125, 211, 252, 28))
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(glow))
        painter.drawEllipse(outer)

        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor(125, 211, 252, 54), 3.0, Qt.SolidLine, Qt.RoundCap))
        painter.drawArc(outer.adjusted(5, 5, -5, -5), 0, 360 * 16)
        painter.setPen(QPen(QColor(56, 189, 248, 230), 3.8, Qt.SolidLine, Qt.RoundCap))
        painter.drawArc(outer.adjusted(5, 5, -5, -5), int(-self._angle * 16), -106 * 16)
        painter.setPen(QPen(QColor(129, 140, 248, 170), 2.2, Qt.SolidLine, Qt.RoundCap))
        painter.drawArc(inner, int((self._angle + 170) * 16), 72 * 16)

        if not self._logo.isNull():
            logo = self._logo.scaled(48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            painter.drawPixmap(int(center.x() - logo.width() / 2), int(center.y() - logo.height() / 2), logo)
        else:
            painter.setFont(QFont("Segoe UI", 12, QFont.DemiBold))
            painter.setPen(QColor(224, 242, 254))
            painter.drawText(QRectF(center.x() - 24, center.y() - 16, 48, 32), Qt.AlignCenter, "HA")

        painter.setPen(QPen(QColor(56, 189, 248, 96), 1.2))
        painter.drawLine(24, self.height() - 52, self.width() - 24, self.height() - 52)
        painter.setFont(QFont("Segoe UI", 8, QFont.DemiBold))
        painter.setPen(label)
        painter.drawText(QRectF(14, self.height() - 43, self.width() - 28, 18), Qt.AlignCenter, "HYDRAULIC FIELD")
        painter.end()


class _ProgressRail(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._current = 0
        self._total = 1
        self._ratio = 0.0
        self._phase = 0.0
        self.setFixedHeight(20)
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def set_progress(self, current: int, total: int):
        self._total = max(1, int(total))
        self._current = max(0, min(int(current), self._total))
        incoming = self._current / self._total
        self._ratio = max(self._ratio, incoming)
        self.update()

    def stop(self):
        self._timer.stop()
        self.update()

    def _tick(self):
        self._phase = (self._phase + 0.026) % 1.0
        self.update()

    def paintEvent(self, event):
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(0, 7, self.width(), 6)
        radius = rect.height() / 2.0

        track = QPainterPath()
        track.addRoundedRect(rect, radius, radius)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(148, 163, 184, 54))
        painter.drawPath(track)

        ratio = self._ratio if self._ratio > 0 else 0.04
        fill_rect = QRectF(rect)
        fill_rect.setWidth(max(rect.height(), rect.width() * ratio))
        fill = QPainterPath()
        fill.addRoundedRect(fill_rect, radius, radius)
        grad = QLinearGradient(fill_rect.topLeft(), fill_rect.topRight())
        grad.setColorAt(0.0, QColor(37, 99, 235))
        grad.setColorAt(0.55, QColor(14, 165, 233))
        grad.setColorAt(1.0, QColor(125, 211, 252))
        painter.setBrush(QBrush(grad))
        painter.drawPath(fill)

        painter.save()
        painter.setClipPath(fill)
        shimmer_w = max(70.0, rect.width() * 0.18)
        shimmer_x = rect.x() + (rect.width() + shimmer_w) * self._phase - shimmer_w
        shimmer = QRectF(shimmer_x, rect.y(), shimmer_w, rect.height())
        shimmer_grad = QLinearGradient(shimmer.topLeft(), shimmer.topRight())
        shimmer_grad.setColorAt(0.0, QColor(255, 255, 255, 0))
        shimmer_grad.setColorAt(0.5, QColor(255, 255, 255, 150))
        shimmer_grad.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.setBrush(QBrush(shimmer_grad))
        painter.drawRoundedRect(shimmer, radius, radius)
        painter.restore()

        cap_x = rect.x() + rect.width() * ratio
        cap = QColor(224, 242, 254)
        painter.setBrush(_with_alpha(cap, 220))
        painter.drawEllipse(QPointF(cap_x, rect.center().y()), 3.2, 3.2)
        painter.end()


class LoadingDialog(FramelessDialogMixin, QDialog):
    """Reusable modal progress dialog with cancellation support."""

    cancellation_requested = pyqtSignal()

    def __init__(self, title: str, subtitle: str, parent=None, *, cancellable: bool = True):
        super().__init__(parent)
        self._cancellable = bool(cancellable)
        self._cancel_pending = False
        self._finished = False
        self._live_frame = 0
        self._status_base = "Working"
        self._started_at = time.monotonic()

        self.setWindowTitle(title)
        self.setMinimumWidth(620)
        self.setMaximumWidth(740)
        self.setModal(True)
        self.setWindowModality(Qt.WindowModal if parent is not None else Qt.ApplicationModal)
        self.init_frameless_dialog_chrome(
            default_windows="frameless",
            default_other="native",
            enable_edge_resize=False,
            corner_radius_px=16,
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._header = self._build_header(title, subtitle)
        root.addWidget(self._header)

        body = QWidget()
        body.setObjectName("loadingBody")
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(18, 18, 18, 16)
        body_layout.setSpacing(18)

        self._spinner = _LoadingSpinner()
        body_layout.addWidget(self._spinner, 0)

        info_panel = QWidget()
        info_panel.setObjectName("loadingInfoPanel")
        info_layout = QVBoxLayout(info_panel)
        info_layout.setContentsMargins(0, 2, 0, 0)
        info_layout.setSpacing(10)

        self._stage_label = QLabel("Preparing operation")
        self._stage_label.setObjectName("loadingStage")
        info_layout.addWidget(self._stage_label)

        self._detail_label = QLabel("Waiting for work to start.")
        self._detail_label.setObjectName("loadingDetail")
        self._detail_label.setWordWrap(True)
        info_layout.addWidget(self._detail_label)

        chips = QHBoxLayout()
        chips.setSpacing(6)
        self._count_chip = QLabel("0 of 0")
        self._count_chip.setObjectName("loadingChip")
        chips.addWidget(self._count_chip, 0, Qt.AlignLeft)
        self._elapsed_chip = QLabel("00:00 elapsed")
        self._elapsed_chip.setObjectName("loadingChipMuted")
        chips.addWidget(self._elapsed_chip, 0, Qt.AlignLeft)
        chips.addStretch(1)
        info_layout.addLayout(chips)

        self._progress = _ProgressRail()
        info_layout.addWidget(self._progress)

        self._note_label = QLabel("This dialog will update as the current operation progresses.")
        self._note_label.setObjectName("loadingNote")
        self._note_label.setWordWrap(True)
        info_layout.addWidget(self._note_label)

        activity_panel = QFrame()
        activity_panel.setObjectName("loadingActivityPanel")
        activity_layout = QHBoxLayout(activity_panel)
        activity_layout.setContentsMargins(12, 10, 12, 10)
        activity_layout.setSpacing(10)
        self._activity_dot = QLabel()
        self._activity_dot.setFixedSize(8, 8)
        activity_layout.addWidget(self._activity_dot, 0, Qt.AlignTop)
        self._activity_label = QLabel("Operation queued.")
        self._activity_label.setWordWrap(True)
        self._activity_label.setObjectName("loadingActivity")
        activity_layout.addWidget(self._activity_label, 1)
        info_layout.addWidget(activity_panel)
        info_layout.addStretch(1)

        body_layout.addWidget(info_panel, 1)

        root.addWidget(body, 1)

        footer = QWidget()
        footer.setObjectName("loadingFooter")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(18, 12, 18, 12)
        footer_layout.setSpacing(10)
        self._footer_status = QLabel("Working")
        self._footer_status.setObjectName("loadingFooterStatus")
        footer_layout.addWidget(self._footer_status, 1)
        self._footer_button = QPushButton("Cancel" if cancellable else "Close")
        self._footer_button.setObjectName("loadingCancelButton")
        self._footer_button.setCursor(Qt.PointingHandCursor)
        self._footer_button.clicked.connect(self._request_cancel)
        self._footer_button.setEnabled(cancellable)
        footer_layout.addWidget(self._footer_button)
        root.addWidget(footer)

        self.bind_frameless_drag_widget(self._header)
        self._apply_styles()

        self._live_timer = QTimer(self)
        self._live_timer.setInterval(180)
        self._live_timer.timeout.connect(self._tick_live_state)
        self._live_timer.start()

        self._elapsed_timer = QTimer(self)
        self._elapsed_timer.setInterval(1000)
        self._elapsed_timer.timeout.connect(self._update_elapsed_chip)
        self._elapsed_timer.start()
        self._update_elapsed_chip()
        self._tick_live_state()

    @property
    def cancel_requested(self) -> bool:
        return self._cancel_pending

    def _build_header(self, title: str, subtitle: str) -> QWidget:
        header = QWidget()
        header.setObjectName("loadingHeader")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(20, 16, 16, 16)
        layout.setSpacing(13)

        mark = _HeaderMark()
        mark.setObjectName("loadingHeaderMark")
        layout.addWidget(mark)

        text = QVBoxLayout()
        text.setSpacing(1)
        title_label = QLabel(title)
        title_label.setObjectName("loadingTitle")
        text.addWidget(title_label)
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("loadingSubtitle")
        subtitle_label.setWordWrap(True)
        text.addWidget(subtitle_label)
        layout.addLayout(text, 1)

        close = QPushButton("x")
        close.setObjectName("loadingCloseButton")
        close.setCursor(Qt.PointingHandCursor)
        close.setFixedSize(30, 30)
        close.clicked.connect(self._request_cancel)
        layout.addWidget(close)
        return header

    def _apply_styles(self):
        dark = Colors.is_dark()
        surface = "#0b1220" if dark else Colors.BG_ELEVATED
        header = "#0d1321" if dark else Colors.BG_ELEVATED
        footer = "#11131a" if dark else Colors.BG_PANEL
        body_bg = "#07111f" if dark else "#eef5fb"
        body_border = "rgba(125, 211, 252, 0.18)" if dark else Colors.BORDER_DEFAULT
        text = "#f8fafc" if dark else Colors.TEXT_PRIMARY
        secondary = "#cbd5e1" if dark else Colors.TEXT_SECONDARY
        muted = "#94a3b8" if dark else Colors.TEXT_TERTIARY
        accent = "#38bdf8" if dark else Colors.ACCENT_PRIMARY
        accent_qc = QColor(accent)
        chip_bg = "rgba(56, 189, 248, 0.10)" if dark else Colors.ACCENT_GHOST
        chip_muted_bg = "rgba(15, 23, 42, 0.38)" if dark else Colors.BG_WELL
        activity_bg = "rgba(15, 23, 42, 0.44)" if dark else "rgba(255, 255, 255, 0.58)"
        activity_border = "rgba(125, 211, 252, 0.17)" if dark else Colors.BORDER_DEFAULT
        self.setStyleSheet(f"""
            QDialog {{
                background: {surface};
                border: 1px solid {body_border};
                border-radius: 16px;
            }}
            #loadingHeader {{
                background: {header};
                border-bottom: 1px solid {body_border};
                min-height: 58px;
            }}
            #loadingBody {{
                background: {body_bg};
                border: none;
            }}
            #loadingInfoPanel {{
                background: transparent;
                border: none;
            }}
            #loadingHeaderMark {{
                background: transparent;
                border: none;
            }}
            #loadingTitle {{
                color: {text};
                font-size: 15px;
                font-weight: 800;
                letter-spacing: -0.2px;
                background: transparent;
                border: none;
            }}
            #loadingSubtitle {{
                color: {muted};
                font-size: 10px;
                background: transparent;
                border: none;
            }}
            #loadingCloseButton {{
                background: transparent;
                border: 1px solid transparent;
                border-radius: 8px;
                color: {muted};
                font-size: 16px;
                font-weight: 700;
            }}
            #loadingCloseButton:hover {{
                background: {"rgba(248, 113, 113, 0.13)" if dark else Colors.ERROR_BG};
                color: {Colors.ERROR};
            }}
            #loadingStage {{
                color: {text};
                font-size: 17px;
                font-weight: 800;
                letter-spacing: -0.2px;
                background: transparent;
                border: none;
            }}
            #loadingDetail, #loadingActivity {{
                color: {secondary};
                font-size: 11px;
                background: transparent;
                border: none;
            }}
            #loadingNote {{
                color: {muted};
                font-size: 10px;
                background: transparent;
                border: none;
            }}
            #loadingChip, #loadingChipMuted {{
                border-radius: 99px;
                padding: 3px 9px;
                font-family: Cascadia Mono, Consolas, monospace;
                font-size: 9px;
                font-weight: 700;
                background: {chip_bg};
                border: 1px solid {_rgba(accent_qc, 76)};
            }}
            #loadingChip {{
                color: {accent};
            }}
            #loadingChipMuted {{
                color: {muted};
                background: {chip_muted_bg};
                border-color: {activity_border};
            }}
            #loadingActivityPanel {{
                background: {activity_bg};
                border: 1px solid {activity_border};
                border-radius: 10px;
            }}
            #loadingFooter {{
                background: {footer};
                border-top: 1px solid {body_border};
                min-height: 46px;
            }}
            #loadingFooterStatus {{
                color: {muted};
                font-family: Cascadia Mono, Consolas, monospace;
                font-size: 9px;
                background: transparent;
                border: none;
            }}
            #loadingCancelButton {{
                background: {"rgba(255, 255, 255, 0.045)" if dark else Colors.BG_SURFACE};
                border: 1px solid {activity_border};
                border-radius: 10px;
                color: {secondary};
                padding: 7px 15px;
                font-weight: 700;
            }}
            #loadingCancelButton:hover {{
                background: {"rgba(56, 189, 248, 0.12)" if dark else Colors.BG_HOVER};
                color: {text};
                border-color: {_rgba(accent_qc, 112)};
            }}
            #loadingCancelButton:disabled {{
                color: {Colors.TEXT_DISABLED};
            }}
        """)

    def update_progress(
        self,
        current: int,
        total: int,
        stage: str,
        detail: str,
        *,
        count_label: str | None = None,
        activity_label: str | None = None,
    ):
        total = max(1, int(total))
        current = max(0, min(int(current), total))
        self._progress.set_progress(current, total)
        self._stage_label.setText(stage or "Working")
        self._detail_label.setText(detail or " ")
        self._count_chip.setText(count_label or f"{current} of {total}")
        self._activity_label.setText(activity_label or f"Processing step {current} of {total}.")
        self._status_base = "Working"
        self._tick_live_state()

    def set_activity(self, text: str):
        self._note_label.setText(text or " ")

    def mark_finished(self, headline: str, detail: str = "", *, ok: bool = True):
        self._finished = True
        self._spinner.stop()
        self._progress.set_progress(1, 1)
        self._progress.stop()
        self._live_timer.stop()
        self._elapsed_timer.stop()
        self._stage_label.setText(headline)
        self._detail_label.setText(detail or " ")
        self._activity_label.setText("Completed successfully." if ok else "Completed with warnings.")
        self._footer_status.setText("Done" if ok else "Needs review")
        self._note_label.setText("This dialog can be closed.")
        self._activity_dot.setStyleSheet(
            f"background: {Colors.SUCCESS if ok else Colors.WARNING}; border-radius: 4px;"
        )
        if self._footer_button is not None:
            self._footer_button.setEnabled(True)
            self._footer_button.setText("Close")

    def mark_cancel_pending(self):
        if self._cancel_pending or self._finished:
            return
        self._cancel_pending = True
        self._detail_label.setText("Stopping after the current step.")
        self._activity_label.setText("Cancellation requested.")
        self._status_base = "Stopping"
        if self._footer_button is not None:
            self._footer_button.setEnabled(False)
        self._tick_live_state()

    def _request_cancel(self):
        if self._finished:
            self.accept()
            return
        if not self._cancellable or self._cancel_pending:
            return
        self.mark_cancel_pending()
        self.cancellation_requested.emit()

    def _update_elapsed_chip(self):
        elapsed = max(0, int(time.monotonic() - self._started_at))
        minutes, seconds = divmod(elapsed, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            text = f"{hours:02d}:{minutes:02d}:{seconds:02d} elapsed"
        else:
            text = f"{minutes:02d}:{seconds:02d} elapsed"
        self._elapsed_chip.setText(text)

    def _tick_live_state(self):
        if self._finished:
            return
        self._live_frame = (self._live_frame + 1) % 24
        suffix = "." * ((self._live_frame // 6) % 4)
        self._footer_status.setText(f"{self._status_base}{suffix}")
        opacity = (0.35, 0.55, 0.75, 1.0, 0.75, 0.55)[self._live_frame % 6]
        dot = QColor(Colors.ACCENT_PRIMARY)
        self._activity_dot.setStyleSheet(
            f"background: rgba({dot.red()}, {dot.green()}, {dot.blue()}, {int(opacity * 255)}); border-radius: 4px;"
        )
