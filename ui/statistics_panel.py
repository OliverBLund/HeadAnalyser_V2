"""
HeadAnalyser V2 — Statistics Dashboard.

"Field Survey" cartographic-engineering aesthetic — deep ink + sodium-amber
accent, JetBrains Mono numerals, reticle-cornered panels, instrument-LED
indicators. See ``stats_dashboard_concept_v2.html`` for the design source.

Public API (unchanged across the redesign):
    StatisticsPanel(parent=None)
        .update_statistics(app)
        .clear_statistics()
        .apply_theme()
        .get_selected_point_ids() -> set
        open_inspector_requested  pyqtSignal()
        export_requested          pyqtSignal()
"""

from __future__ import annotations

import math
import time

import numpy as np
import pandas as pd

from PyQt5.QtCore import (
    Qt, pyqtSignal, QRect, QRectF, QSize, QPointF, QPoint,
)
from PyQt5.QtGui import (
    QPainter, QPainterPath, QColor, QPen, QBrush, QFont, QFontMetrics,
    QLinearGradient, QPolygonF, QFontDatabase,
)
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QScrollArea,
    QStackedWidget, QPushButton, QToolButton, QSizePolicy, QGridLayout,
    QSplitter, QButtonGroup, QSpacerItem, QMenu, QAction, QGraphicsOpacityEffect,
)

from styles.colors import Colors
from ui.head_gradient_statistics import HeadStatisticsWidget, GradientStatisticsWidget
from ui.theme_utils import reset_widget_layout
from ui.triangle_widgets.breakdown_bars import RejectionBreakdownBars
from ui.triangle_widgets.geometry_plot import TriangleGeometryPlot
from ui.triangle_widgets.point_frequency import PointFrequencyBars
from ui.triangle_widgets.summary_cards import TriangleSummaryCards
from ui.triangle_widgets.triangle_data_helper import TriangleDataHelper
from ui.triangle_widgets.triangle_table import TriangleTableWidget


# ════════════════════════════════════════════════════════════════════════
# Local "Field Survey" palette — kept scoped to this module until the rest
# of the app adopts the same direction (so we don't pollute the global
# Colors namespace with stats-only tokens).
# ════════════════════════════════════════════════════════════════════════

class FS:
    """Field-Survey palette.

    Surface tones + text colors are sourced from the app's global ``Colors``
    so the panel adapts to whichever theme the user has active at startup
    (dark / light / etc). Sodium-amber accent and state colors stay
    constant — that's the brand identity of this view.
    """
    # ── theme-adaptive surface tones (read at module load) ──
    INK         = Colors.BG_DARK
    INK_2       = Colors.BG_PANEL
    PANEL       = Colors.BG_SURFACE
    RAISED      = Colors.BG_ELEVATED
    HOVER       = Colors.BG_HOVER

    HAIR        = Colors.BORDER_SUBTLE
    LINE        = Colors.BORDER_DEFAULT
    LINE_STRONG = Colors.BORDER_MEDIUM
    LINE_BRIGHT = Colors.BORDER_STRONG

    TXT         = Colors.TEXT_PRIMARY
    TXT_DIM     = Colors.TEXT_SECONDARY
    TXT_FAINT   = Colors.TEXT_TERTIARY
    TXT_GHOST   = Colors.TEXT_MUTED

    # ── constant brand accents (never change with theme) ──
    AMBER         = "#d9a04e"
    AMBER_BRIGHT  = "#f0bd6a"
    AMBER_GLOW    = "rgba(217, 160, 78, 0.16)"
    AMBER_FAINT   = "rgba(217, 160, 78, 0.06)"

    SAGE = "#88b896"
    RUST = "#c4795f"
    CYAN = "#6ec1c9"

    @staticmethod
    def qc(value: str, alpha: int = 255) -> QColor:
        """Build a QColor from a hex/name/rgba/rgb CSS string.

        Without this, ``QColor("rgba(220,226,235,0.08)")`` silently returns
        an invalid colour (defaults to black on draw), which previously made
        every QPainter-rendered widget (rose card, panel borders, sparkline
        outlines, band brackets) look black-on-black.
        """
        s = value.strip() if isinstance(value, str) else ""
        c = None
        if s.startswith("rgba(") or s.startswith("rgb("):
            try:
                body = s[s.index("(") + 1 : s.rindex(")")]
                parts = [p.strip() for p in body.split(",")]
                r = int(float(parts[0]))
                g = int(float(parts[1]))
                b = int(float(parts[2]))
                if len(parts) >= 4:
                    af = float(parts[3])
                    a = int(round(af * 255 if af <= 1.0 else af))
                else:
                    a = 255
                c = QColor(max(0, min(255, r)),
                           max(0, min(255, g)),
                           max(0, min(255, b)),
                           max(0, min(255, a)))
            except Exception:
                c = None
        if c is None:
            c = QColor(s)
            if not c.isValid():
                # Last-resort default — won't render as cursed black.
                c = QColor(128, 128, 128)
        if alpha != 255:
            c.setAlpha(alpha)
        return c


# Font fallbacks — JetBrains Mono / IBM Plex Sans Condensed / Bitter aren't
# usually shipped on Windows by default; if they're missing we fall back to
# the next-best system mono / condensed sans / serif. Bundling these as
# QFontDatabase resources is a future task.
FF_MONO  = '"JetBrains Mono", "Cascadia Mono", Consolas, "Courier New", monospace'
FF_LABEL = '"IBM Plex Sans Condensed", "Segoe UI", system-ui, sans-serif'
FF_PROSE = '"Bitter", Georgia, "Times New Roman", serif'


# ════════════════════════════════════════════════════════════════════════
# PRIMITIVES
# ════════════════════════════════════════════════════════════════════════


class ReticlePanel(QFrame):
    """Panel with sodium-amber reticle marks in all four corners.

    Reticles are painted via ``paintEvent`` so they stay 1-px regardless
    of the panel's background colour. Children attach via the standard
    layout — the reticle ticks are decoration only.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(
            f"ReticlePanel {{ background-color: {FS.PANEL};"
            f" border: 1px solid {FS.LINE}; }}"
        )

    def paintEvent(self, ev):
        super().paintEvent(ev)
        p = QPainter(self)
        try:
            p.setRenderHint(QPainter.Antialiasing, False)
            pen = QPen(FS.qc("AMBER"))
            pen.setWidth(1)
            pen.setCosmetic(True)
            p.setPen(pen)
            arm = 10
            w, h = self.width(), self.height()
            # Top-left
            p.drawLine(0, 0, arm, 0)
            p.drawLine(0, 0, 0, arm)
            # Top-right
            p.drawLine(w - arm, 0, w - 1, 0)
            p.drawLine(w - 1, 0, w - 1, arm)
            # Bottom-left
            p.drawLine(0, h - 1, arm, h - 1)
            p.drawLine(0, h - arm, 0, h - 1)
            # Bottom-right
            p.drawLine(w - arm, h - 1, w - 1, h - 1)
            p.drawLine(w - 1, h - arm, w - 1, h - 1)
        finally:
            p.end()


class BrandGlyph(QLabel):
    """22x22 amber-bordered glyph showing a single letter (the app initial)."""

    def __init__(self, letter: str = "H", parent=None):
        super().__init__(letter, parent)
        self.setFixedSize(22, 22)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet(
            f"background-color: {FS.AMBER_GLOW};"
            f" border: 1px solid {FS.AMBER};"
            f" color: {FS.AMBER_BRIGHT};"
            f" font-family: {FF_MONO};"
            f" font-size: 11px; font-weight: 700; letter-spacing: -0.5px;"
        )


class SegmentedTabs(QWidget):
    """Topbar segmented tabs with numbered indices ("01 OVERVIEW")."""

    tab_changed = pyqtSignal(int)  # emits the new active index

    def __init__(self, items, parent=None):
        super().__init__(parent)
        self._buttons = []
        self._active = 0
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        for i, label in enumerate(items):
            btn = QToolButton()
            btn.setCheckable(True)
            btn.setText(f"  {i+1:02d}  {label}")
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedHeight(44)
            btn.setStyleSheet(self._btn_style())
            btn.clicked.connect(lambda _checked, idx=i: self._select(idx))
            self._group.addButton(btn, i)
            self._buttons.append(btn)
            lay.addWidget(btn)
        # Default selection
        if self._buttons:
            self._buttons[0].setChecked(True)

    @staticmethod
    def _btn_style() -> str:
        return (
            f"QToolButton {{"
            f"  background: transparent;"
            f"  border: 0px;"
            f"  border-bottom: 2px solid transparent;"
            f"  color: {FS.TXT_FAINT};"
            f"  font-family: {FF_MONO};"
            f"  font-size: 10px;"
            f"  font-weight: 500;"
            f"  letter-spacing: 1.6px;"
            f"  padding: 0 16px;"
            f"  text-transform: uppercase;"
            f"}}"
            f"QToolButton:hover {{ color: {FS.TXT}; }}"
            f"QToolButton:checked {{"
            f"  color: {FS.AMBER_BRIGHT};"
            f"  border-bottom: 2px solid {FS.AMBER};"
            f"}}"
        )

    def _select(self, idx: int):
        if idx != self._active:
            self._active = idx
            self.tab_changed.emit(idx)

    def set_active(self, idx: int):
        if 0 <= idx < len(self._buttons):
            self._buttons[idx].setChecked(True)
            self._select(idx)


class ScopeChip(QPushButton):
    """Reticle-bracketed scope indicator showing the active cell / filter."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setText("SCOPE  ·  —")
        self.setStyleSheet(
            f"QPushButton {{"
            f"  background-color: {FS.AMBER_FAINT};"
            f"  border: 1px solid {FS.AMBER};"
            f"  color: {FS.AMBER_BRIGHT};"
            f"  font-family: {FF_MONO};"
            f"  font-size: 10px;"
            f"  font-weight: 500;"
            f"  letter-spacing: 0.8px;"
            f"  padding: 4px 14px;"
            f"  text-align: left;"
            f"}}"
            f"QPushButton:hover {{ background-color: {FS.AMBER_GLOW}; }}"
        )

    def paintEvent(self, ev):
        super().paintEvent(ev)
        p = QPainter(self)
        try:
            p.setRenderHint(QPainter.Antialiasing, False)
            pen = QPen(FS.qc("AMBER"))
            pen.setWidth(1)
            pen.setCosmetic(True)
            p.setPen(pen)
            w, h = self.width(), self.height()
            arm = 6
            # Top-left exterior bracket
            p.drawLine(-2, -2, -2 + arm, -2)
            p.drawLine(-2, -2, -2, -2 + arm)
            # Bottom-right exterior bracket
            p.drawLine(w + 1 - arm, h + 1, w + 1, h + 1)
            p.drawLine(w + 1, h + 1 - arm, w + 1, h + 1)
        finally:
            p.end()

    def set_scope(self, text: str):
        self.setText("●  SCOPE  ·  " + text)


class TopBar(QWidget):
    """Title block + segmented tabs + scope chip + actions.

    Sodium tick marks live along the bottom edge (drawn in paintEvent).
    """

    pin_baseline_requested = pyqtSignal()
    export_requested = pyqtSignal()
    tab_changed = pyqtSignal(int)
    scope_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(45)  # 44 + 1 for the tick scale
        self.setStyleSheet(
            f"TopBar {{ background-color: {FS.INK_2};"
            f" border-bottom: 1px solid {FS.LINE_STRONG}; }}"
        )

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── main row ──
        row = QWidget()
        row.setFixedHeight(44)
        rl = QHBoxLayout(row)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(0)

        # Brand block
        brand = QWidget()
        brand.setStyleSheet(f"background: transparent; border-right: 1px solid {FS.LINE};")
        bl = QHBoxLayout(brand)
        bl.setContentsMargins(18, 0, 18, 0)
        bl.setSpacing(10)
        bl.addWidget(BrandGlyph("H"))
        bname = QLabel(
            f'<span style="color:{FS.TXT_DIM};">HEADANALYSER</span>'
            f' <span style="color:{FS.AMBER};font-weight:700;">·</span> '
            f'<span style="color:{FS.TXT};font-weight:700;">STATISTICS</span>'
        )
        bname.setStyleSheet(
            f"background: transparent; font-family: {FF_MONO}; font-size: 10px;"
            f" font-weight: 500; letter-spacing: 2.5px;"
        )
        bl.addWidget(bname)
        rl.addWidget(brand)

        # Segmented tabs
        tabs_wrap = QWidget()
        tabs_wrap.setStyleSheet(f"background: transparent; border-right: 1px solid {FS.LINE};")
        twl = QHBoxLayout(tabs_wrap)
        twl.setContentsMargins(8, 0, 8, 0)
        twl.setSpacing(0)
        self.tabs = SegmentedTabs(["OVERVIEW", "HEAD", "GRADIENT", "TRIANGLES", "SNAPSHOTS", "RAW"])
        self.tabs.tab_changed.connect(self.tab_changed.emit)
        twl.addWidget(self.tabs)
        rl.addWidget(tabs_wrap)

        rl.addStretch()

        # Right-side cluster: scope chip + actions
        rcluster = QWidget()
        rcluster.setStyleSheet("background: transparent;")
        rcl = QHBoxLayout(rcluster)
        rcl.setContentsMargins(0, 0, 14, 0)
        rcl.setSpacing(14)

        self.scope_chip = ScopeChip()
        self.scope_chip.clicked.connect(self.scope_clicked.emit)
        rcl.addWidget(self.scope_chip)

        self.pin_btn = self._make_action_button("PIN BASELINE")
        self.pin_btn.clicked.connect(self.pin_baseline_requested.emit)
        rcl.addWidget(self.pin_btn)

        self.export_btn = self._make_action_button("EXPORT  ▾", primary=True)
        self.export_btn.clicked.connect(self.export_requested.emit)
        rcl.addWidget(self.export_btn)

        rl.addWidget(rcluster)
        outer.addWidget(row)

        # Tick scale (1-px high)
        ticks = QWidget()
        ticks.setFixedHeight(1)
        ticks.setStyleSheet("background: transparent;")
        ticks.paintEvent = self._paint_ticks_for(ticks)
        outer.addWidget(ticks)

    @staticmethod
    def _make_action_button(label: str, primary: bool = False) -> QPushButton:
        btn = QPushButton(label)
        btn.setCursor(Qt.PointingHandCursor)
        if primary:
            btn.setStyleSheet(
                f"QPushButton {{ background-color: {FS.AMBER};"
                f" border: 1px solid {FS.AMBER}; color: {FS.INK};"
                f" font-family: {FF_MONO}; font-size: 10px;"
                f" font-weight: 700; letter-spacing: 1.2px;"
                f" padding: 5px 12px; }}"
                f"QPushButton:hover {{ background-color: {FS.AMBER_BRIGHT};"
                f" border-color: {FS.AMBER_BRIGHT}; }}"
            )
        else:
            btn.setStyleSheet(
                f"QPushButton {{ background: transparent;"
                f" border: 1px solid {FS.LINE_STRONG}; color: {FS.TXT_DIM};"
                f" font-family: {FF_MONO}; font-size: 10px;"
                f" font-weight: 500; letter-spacing: 1.2px;"
                f" padding: 5px 12px; }}"
                f"QPushButton:hover {{ border-color: {FS.AMBER};"
                f" color: {FS.AMBER_BRIGHT};"
                f" background-color: {FS.AMBER_FAINT}; }}"
            )
        return btn

    @staticmethod
    def _paint_ticks_for(w: QWidget):
        # Returns a paintEvent closure that draws sodium tick marks along
        # the strip's width — 1-px tall amber pips every 24px.
        def _paint(ev):
            p = QPainter(w)
            try:
                p.setRenderHint(QPainter.Antialiasing, False)
                pen = QPen(FS.qc("AMBER", 115))
                pen.setWidth(1)
                pen.setCosmetic(True)
                p.setPen(pen)
                x = 0
                while x < w.width():
                    p.drawLine(x, 0, x, 0)
                    x += 24
            finally:
                p.end()
        return _paint


class HealthGauge(QWidget):
    """A single instrument-gauge card in the health strip.

    Layout: numbered index + label + status LED on top, big mono value below,
    optional meta line at the bottom. Borders only on the left (visual
    separator between gauges); first gauge gets no left border.
    """

    def __init__(self, idx: int, label: str, led_color: str = "amber",
                 *, sparkline: bool = False, parent=None):
        super().__init__(parent)
        self._led_color = led_color
        self._sparkline_points: list[float] | None = None
        self.setMinimumHeight(84)
        self.setStyleSheet("HealthGauge { background: transparent; }")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 12, 18, 12)
        lay.setSpacing(4)

        # Header row: index, label, LED
        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        head.setSpacing(8)
        idx_lbl = QLabel(f"{idx:02d}")
        idx_lbl.setStyleSheet(
            f"color: {FS.TXT_GHOST}; background: transparent;"
            f" font-family: {FF_MONO}; font-size: 9px; font-weight: 400;"
            f" letter-spacing: 0.5px;"
        )
        head.addWidget(idx_lbl)
        lbl = QLabel(label.upper())
        lbl.setStyleSheet(
            f"color: {FS.TXT_DIM}; background: transparent;"
            f" font-family: {FF_MONO}; font-size: 9px; font-weight: 500;"
            f" letter-spacing: 1.8px;"
        )
        head.addWidget(lbl)
        head.addStretch()
        self._led = QLabel("●")
        self._set_led_style()
        head.addWidget(self._led)
        lay.addLayout(head)

        # Value (mono, large)
        self.value_label = QLabel("—")
        self.value_label.setTextFormat(Qt.RichText)
        self.value_label.setStyleSheet(
            f"color: {FS.TXT}; background: transparent;"
            f" font-family: {FF_MONO}; font-size: 26px; font-weight: 300;"
            f" letter-spacing: -0.5px;"
        )
        lay.addWidget(self.value_label)

        # Sparkline (optional) — sized to match the visual weight of the
        # large mono numeric value used in other gauges.
        self._sparkline = None
        if sparkline:
            self._sparkline = _SparkPath(self._led_color_qc())
            self._sparkline.setFixedHeight(34)
            lay.addWidget(self._sparkline)

        # Meta (small subtext)
        self.meta_label = QLabel("")
        self.meta_label.setTextFormat(Qt.RichText)
        self.meta_label.setStyleSheet(
            f"color: {FS.TXT_FAINT}; background: transparent;"
            f" font-family: {FF_MONO}; font-size: 9px; letter-spacing: 0.6px;"
        )
        lay.addWidget(self.meta_label)

    def _led_color_qc(self) -> QColor:
        return {
            "amber": FS.qc("AMBER"),
            "sage":  FS.qc("SAGE"),
            "rust":  FS.qc("RUST"),
            "cyan":  FS.qc("CYAN"),
        }.get(self._led_color, FS.qc("AMBER"))

    def _set_led_style(self):
        c = {"amber": FS.AMBER, "sage": FS.SAGE, "rust": FS.RUST, "cyan": FS.CYAN}\
            .get(self._led_color, FS.AMBER)
        self._led.setStyleSheet(
            f"color: {c}; background: transparent; font-size: 10px;"
        )

    def set_led(self, color: str):
        self._led_color = color
        self._set_led_style()
        if self._sparkline is not None:
            self._sparkline.set_color(self._led_color_qc())

    def set_value(self, html_value: str):
        self.value_label.setText(html_value)

    def set_meta(self, html_meta: str):
        self.meta_label.setText(html_meta)

    def set_spark(self, values: list[float]):
        if self._sparkline is not None:
            self._sparkline.set_values(values)


class _SparkPath(QWidget):
    """22-px tall path-style sparkline rendered via QPainter."""

    def __init__(self, color: QColor, parent=None):
        super().__init__(parent)
        self._color = color
        self._values: list[float] = []

    def set_color(self, c: QColor):
        self._color = c
        self.update()

    def set_values(self, values: list[float]):
        self._values = list(values) if values else []
        self.update()

    def paintEvent(self, ev):
        if not self._values or len(self._values) < 2:
            return
        p = QPainter(self)
        try:
            p.setRenderHint(QPainter.Antialiasing, True)
            vmin, vmax = min(self._values), max(self._values)
            if vmax == vmin:
                vmax = vmin + 1.0
            w, h = self.width(), self.height()
            n = len(self._values)
            pts = []
            for i, v in enumerate(self._values):
                x = i * (w - 2) / (n - 1) + 1
                y = h - 2 - (v - vmin) / (vmax - vmin) * (h - 4)
                pts.append(QPointF(x, y))
            # Filled area below the line — gradient for depth
            fill_path = QPainterPath()
            fill_path.moveTo(QPointF(pts[0].x(), h))
            for pt in pts:
                fill_path.lineTo(pt)
            fill_path.lineTo(QPointF(pts[-1].x(), h))
            fill_path.closeSubpath()
            grad = QLinearGradient(0, 0, 0, h)
            c_top = QColor(self._color); c_top.setAlphaF(0.42)
            c_bot = QColor(self._color); c_bot.setAlphaF(0.04)
            grad.setColorAt(0.0, c_top)
            grad.setColorAt(1.0, c_bot)
            p.fillPath(fill_path, grad)
            # Line — slightly thicker for visibility
            pen = QPen(self._color)
            pen.setWidthF(1.5)
            pen.setCapStyle(Qt.RoundCap)
            pen.setJoinStyle(Qt.RoundJoin)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            line_path = QPainterPath()
            line_path.moveTo(pts[0])
            for pt in pts[1:]:
                line_path.lineTo(pt)
            p.drawPath(line_path)
            # Dot at peak
            peak_idx = max(range(len(self._values)), key=lambda i: self._values[i])
            peak_pt = pts[peak_idx]
            p.setBrush(self._color)
            p.setPen(Qt.NoPen)
            p.drawEllipse(peak_pt, 2.0, 2.0)
        finally:
            p.end()


class HealthStrip(QWidget):
    """Five-gauge instrument strip below the topbar."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            f"HealthStrip {{ background: transparent;"
            f" border-bottom: 1px solid {FS.LINE}; }}"
        )
        lay = QHBoxLayout(self)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(0)

        self.gauge_points    = HealthGauge(1, "Data Points", "cyan")
        self.gauge_triangles = HealthGauge(2, "Triangles Kept", "sage")
        self.gauge_rejected  = HealthGauge(3, "Rejected", "amber")
        self.gauge_head      = HealthGauge(4, "Head Profile", "cyan", sparkline=True)
        self.gauge_direction = HealthGauge(5, "Direction R", "sage")

        gauges = [
            self.gauge_points, self.gauge_triangles, self.gauge_rejected,
            self.gauge_head, self.gauge_direction,
        ]
        # Use TXT_GHOST (solid mid-tone) rather than LINE_STRONG (rgba at
        # low alpha) so the separator hair is visible on light themes too.
        # On dark themes TXT_GHOST is a dark grey — still visible against
        # the deep ink panel.
        for i, g in enumerate(gauges):
            border_rule = (
                f" border-left: 1px solid {FS.TXT_GHOST};"
                if i > 0 else ""
            )
            g.setStyleSheet(
                f"HealthGauge {{ background: transparent;{border_rule} }}"
            )
            lay.addWidget(g, 1)


class PanelHeader(QWidget):
    """The header bar of a ReticlePanel — section number + title + meta."""

    def __init__(self, section_num: str, title: str, parent=None):
        super().__init__(parent)
        self.setFixedHeight(38)
        self.setStyleSheet(
            f"PanelHeader {{ background: transparent;"
            f" border-bottom: 1px solid {FS.LINE}; }}"
        )
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 0, 16, 0)
        lay.setSpacing(12)

        num = QLabel(section_num)
        num.setStyleSheet(
            f"color: {FS.AMBER}; background: transparent;"
            f" font-family: {FF_MONO}; font-size: 10px; font-weight: 400;"
            f" letter-spacing: 0.5px;"
            f" padding-right: 12px; border-right: 1px solid {FS.LINE};"
        )
        lay.addWidget(num)

        ttl = QLabel(title.upper())
        ttl.setStyleSheet(
            f"color: {FS.TXT}; background: transparent;"
            f" font-family: {FF_LABEL}; font-size: 11px; font-weight: 600;"
            f" letter-spacing: 2.4px;"
        )
        lay.addWidget(ttl)
        lay.addStretch()

        self.meta = QLabel("")
        self.meta.setTextFormat(Qt.RichText)
        self.meta.setStyleSheet(
            f"color: {FS.TXT_FAINT}; background: transparent;"
            f" font-family: {FF_MONO}; font-size: 9px; letter-spacing: 0.6px;"
        )
        lay.addWidget(self.meta)

    def set_meta(self, html: str):
        self.meta.setText(html)


class SubHeader(QLabel):
    """Amber dash + label + optional right-aligned count."""

    def __init__(self, label: str, count: str = "", parent=None):
        super().__init__(parent)
        self.setTextFormat(Qt.RichText)
        self._label = label
        self.set_count(count)
        self.setStyleSheet(
            f"background: transparent; color: {FS.AMBER};"
            f" font-family: {FF_MONO}; font-size: 9px; font-weight: 600;"
            f" letter-spacing: 2.4px;"
        )

    def set_count(self, count: str):
        dash = (
            f'<span style="background-color:{FS.AMBER};"'
            f' >&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</span>'
        )
        # We approximate the leading dash via a short underline-styled span;
        # actual horizontal rule is drawn via a QFrame in compositions where
        # the dash needs to be perfectly aligned.
        right = ""
        if count:
            right = (
                f' &nbsp;<span style="color:{FS.TXT_FAINT}; letter-spacing:0.8px;'
                f' font-weight:400;">— {count}</span>'
            )
        self.setText(f"{self._label.upper()}{right}")


class ReadoutGrid(QWidget):
    """3-column dense stat grid with key / value / delta per cell.

    Cells have no per-cell borders — instead, a 1-px grid spacing reveals
    the parent's INK background as hair-line separators, giving subtle
    structure without the noisy interior grid that per-cell borders create.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: list[tuple[str, QLabel, QLabel, QLabel]] = []
        self.setStyleSheet(
            f"ReadoutGrid {{ background-color: {FS.LINE};"
            f" border: 1px solid {FS.LINE}; }}"
        )
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(1)

    def add_row(self, key: str, key_id: str, *, wide: bool = False):
        """Add a stat row. ``key_id`` is the lookup name used by ``set``."""
        col_count = 3
        idx = len(self._rows)
        row = idx // col_count
        col = idx % col_count
        cell = self._build_cell(key, wide=wide)
        if wide:
            # Place wide row on its own row spanning 3 columns; bump idx so
            # the next row starts cleanly.
            self._grid.addWidget(cell["widget"], row, 0, 1, col_count)
            # Pad accounting — push next index to start of next row.
            self._rows.append((key_id, cell["v"], cell["delta"], None))
            # Fill the remainder of this row index slots
            for _ in range(col_count - 1):
                self._rows.append((None, None, None, None))
        else:
            self._grid.addWidget(cell["widget"], row, col, 1, 1)
            self._rows.append((key_id, cell["v"], cell["delta"], cell["widget"]))

    def _build_cell(self, key: str, *, wide: bool) -> dict:
        cell = QFrame()
        cell.setStyleSheet(
            f"QFrame {{ background-color: {FS.PANEL}; border: 0; }}"
        )
        v = QVBoxLayout(cell)
        v.setContentsMargins(12, 9, 12, 9)
        v.setSpacing(3)

        k_lbl = QLabel(key.upper())
        k_lbl.setStyleSheet(
            f"color: {FS.TXT_FAINT}; background: transparent;"
            f" font-family: {FF_MONO}; font-size: 8.5px; font-weight: 500;"
            f" letter-spacing: 1.4px;"
        )
        v.addWidget(k_lbl)

        val = QLabel("—")
        val.setTextFormat(Qt.RichText)
        val.setStyleSheet(
            f"color: {FS.TXT}; background: transparent;"
            f" font-family: {FF_MONO}; font-size: 13px; font-weight: 400;"
            f" letter-spacing: -0.2px;"
        )
        v.addWidget(val)

        delta = QLabel("")
        delta.setTextFormat(Qt.RichText)
        delta.setStyleSheet(
            f"color: {FS.TXT_GHOST}; background: transparent;"
            f" font-family: {FF_MONO}; font-size: 9px; letter-spacing: 0.4px;"
        )
        v.addWidget(delta)

        return {"widget": cell, "v": val, "delta": delta}

    def set(self, key_id: str, value_html: str, delta_html: str = "",
            delta_class: str = "flat"):
        for kid, v, d, _ in self._rows:
            if kid == key_id and v is not None:
                v.setText(value_html)
                if d is not None:
                    color = {
                        "warn": FS.RUST,
                        "gain": FS.SAGE,
                        "flat": FS.TXT_GHOST,
                    }.get(delta_class, FS.TXT_GHOST)
                    d.setStyleSheet(
                        f"color: {color}; background: transparent;"
                        f" font-family: {FF_MONO}; font-size: 9px; letter-spacing: 0.4px;"
                    )
                    d.setText(delta_html)
                return

    def clear_all(self):
        for kid, v, d, _ in self._rows:
            if v is not None:
                v.setText("—")
            if d is not None:
                d.setText("")


class FieldNote(QFrame):
    """Italic serif note block with a leading amber rule + 'NOTE' label.

    Uses a real ``QVBoxLayout`` rather than a single QLabel with HTML so
    the NOTE caption reliably sits on its own line — Qt's QLabel rich-text
    rendering doesn't honour ``<div>``'s block-level behaviour, which
    previously caused the caption to inline with the body text
    ("NOTERejected triangles…").
    """

    def __init__(self, text: str = "", parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            f"FieldNote {{ background-color: {FS.INK_2};"
            f" border-left: 2px solid {FS.AMBER};"
            f" border-top: 0; border-right: 0; border-bottom: 0; }}"
        )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 14, 12)
        lay.setSpacing(4)

        self._cap = QLabel("NOTE")
        self._cap.setStyleSheet(
            f"background: transparent; color: {FS.AMBER};"
            f" font-family: {FF_MONO}; font-size: 9px; font-weight: 600;"
            f" letter-spacing: 2px;"
        )
        lay.addWidget(self._cap)

        self._body = QLabel("")
        self._body.setWordWrap(True)
        self._body.setTextFormat(Qt.RichText)
        self._body.setStyleSheet(
            f"background: transparent; color: {FS.TXT_DIM};"
            f" font-family: {FF_PROSE}; font-style: italic; font-size: 12px;"
        )
        lay.addWidget(self._body)

        self.set_note(text)

    def set_note(self, text: str):
        if not text:
            self.setVisible(False)
            return
        self.setVisible(True)
        self._body.setText(text)


class PillRow(QWidget):
    """Horizontal flow of clickable ID pills."""

    pill_clicked = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(4)
        self._layout.addStretch()
        self._pills: list[QPushButton] = []

    def set_ids(self, ids: list[str], max_show: int = 7, warn: bool = True):
        # Clear
        while self._pills:
            btn = self._pills.pop()
            btn.setParent(None)
            btn.deleteLater()
        # Add new
        warn_color = FS.RUST if warn else FS.LINE_STRONG
        warn_text = FS.RUST if warn else FS.TXT_DIM
        show = ids[:max_show]
        more = max(0, len(ids) - max_show)
        # Insert before the stretch
        insert_idx = self._layout.count() - 1
        for pid in show:
            btn = QPushButton(str(pid))
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(
                f"QPushButton {{ background: transparent;"
                f" border: 1px solid {warn_color}; color: {warn_text};"
                f" font-family: {FF_MONO}; font-size: 9.5px;"
                f" padding: 3px 8px; letter-spacing: 0.3px; }}"
                f"QPushButton:hover {{ border-color: {FS.AMBER};"
                f" color: {FS.AMBER_BRIGHT}; }}"
            )
            btn.clicked.connect(lambda _checked, p=pid: self.pill_clicked.emit(str(p)))
            self._layout.insertWidget(insert_idx, btn)
            self._pills.append(btn)
            insert_idx += 1
        if more > 0:
            more_btn = QLabel(f"+ {more} more")
            more_btn.setStyleSheet(
                f"background: transparent; color: {FS.TXT_FAINT};"
                f" border: 1px dashed {FS.LINE_STRONG};"
                f" font-family: {FF_MONO}; font-size: 9.5px;"
                f" padding: 3px 8px;"
            )
            self._layout.insertWidget(insert_idx, more_btn)
            self._pills.append(more_btn)


class ProfileDistribution(QWidget):
    """Topographic-style distribution profile.

    Renders a filled amber curve representing a histogram with smooth path
    + dashed median line + Q1/Q3 hairs. Axes annotated in the corners.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(108)
        self.setStyleSheet(
            f"ProfileDistribution {{ background-color: {FS.INK_2};"
            f" border: 1px solid {FS.LINE}; }}"
        )
        self._values: np.ndarray | None = None
        self._meta = {"min": None, "max": None, "mean": None, "std": None,
                      "median": None, "q1": None, "q3": None}

    def set_data(self, values, meta: dict | None = None):
        if values is None or len(values) == 0:
            self._values = None
        else:
            arr = np.asarray(values, dtype=float)
            arr = arr[np.isfinite(arr)]
            self._values = arr if arr.size else None
        if meta:
            self._meta.update(meta)
        self.update()

    def paintEvent(self, ev):
        super().paintEvent(ev)
        p = QPainter(self)
        try:
            p.setRenderHint(QPainter.Antialiasing, True)
            w, h = self.width(), self.height()
            # Corner annotations
            self._draw_corner_label(p, "min", "tl", 8, 6)
            self._draw_corner_label(p, "max", "tr", 8, 6)
            self._draw_corner_label(p, "mean", "bl", 8, 6)
            self._draw_corner_label(p, "std", "br", 8, 6)

            if self._values is None or self._values.size < 4:
                return
            # Inner draw region
            top, bot = 22, h - 22
            left, right = 12, w - 12
            iw = right - left
            ih = bot - top
            if iw <= 4 or ih <= 4:
                return
            # Histogram bins — square-root rule, but clamp aggressively low
            # so small datasets (e.g. 7 points) don't get a comb-shaped chart
            # with mostly-empty bins.
            n = int(self._values.size)
            if n < 16:
                nbins = max(4, min(8, n // 2))
            else:
                nbins = max(8, min(36, int(math.sqrt(n) * 1.4)))
            counts, edges = np.histogram(self._values, bins=nbins)
            if counts.max() == 0:
                return
            xs = (edges[:-1] + edges[1:]) / 2.0
            cmin, cmax = float(edges[0]), float(edges[-1])
            if cmax == cmin:
                cmax = cmin + 1.0

            # Build path
            path = QPainterPath()
            for i, x_val in enumerate(xs):
                x_px = left + (x_val - cmin) / (cmax - cmin) * iw
                y_px = bot - counts[i] / counts.max() * ih
                if i == 0:
                    path.moveTo(QPointF(left, bot))
                    path.lineTo(QPointF(x_px, y_px))
                else:
                    path.lineTo(QPointF(x_px, y_px))
            path.lineTo(QPointF(right, bot))
            path.closeSubpath()

            # Gradient fill
            grad = QLinearGradient(0, top, 0, bot)
            grad.setColorAt(0.0, FS.qc("AMBER", 115))
            grad.setColorAt(1.0, FS.qc("AMBER", 0))
            p.fillPath(path, grad)
            # Outline
            outline = QPainterPath()
            for i, x_val in enumerate(xs):
                x_px = left + (x_val - cmin) / (cmax - cmin) * iw
                y_px = bot - counts[i] / counts.max() * ih
                if i == 0:
                    outline.moveTo(QPointF(x_px, y_px))
                else:
                    outline.lineTo(QPointF(x_px, y_px))
            pen = QPen(FS.qc("AMBER"))
            pen.setWidthF(1.2)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawPath(outline)

            # Median dashed
            med = self._meta.get("median")
            if med is not None and cmin <= med <= cmax:
                x_med = left + (med - cmin) / (cmax - cmin) * iw
                med_pen = QPen(FS.qc("AMBER_BRIGHT", 200))
                med_pen.setWidthF(0.8)
                med_pen.setDashPattern([2, 2])
                p.setPen(med_pen)
                p.drawLine(QPointF(x_med, top), QPointF(x_med, bot))

            # Q1/Q3
            for q in ("q1", "q3"):
                v = self._meta.get(q)
                if v is not None and cmin <= v <= cmax:
                    x_q = left + (v - cmin) / (cmax - cmin) * iw
                    qpen = QPen(FS.qc("AMBER_BRIGHT", 110))
                    qpen.setWidthF(0.6)
                    p.setPen(qpen)
                    p.drawLine(QPointF(x_q, bot - ih * 0.45), QPointF(x_q, bot))
        finally:
            p.end()

    def _draw_corner_label(self, p: QPainter, key: str, corner: str, dx: int, dy: int):
        v = self._meta.get(key)
        if v is None:
            text = key
        else:
            text = f"{key} {v:.2f}" if isinstance(v, (int, float)) else f"{key} {v}"
        font = QFont()
        font.setFamily("JetBrains Mono")
        font.setPointSize(7)
        p.setFont(font)
        p.setPen(FS.qc("TXT_FAINT"))
        fm = QFontMetrics(font)
        tw = fm.horizontalAdvance(text)
        th = fm.height()
        w, h = self.width(), self.height()
        x, y = dx, dy + th - 2
        if corner == "tr":
            x = w - dx - tw
        elif corner == "bl":
            y = h - dy
        elif corner == "br":
            x = w - dx - tw
            y = h - dy
        p.drawText(int(x), int(y), text)


class MiniRoseCard(QWidget):
    """Compact compass card: SVG-style rose + bearing readout to the right."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(140)
        self.setStyleSheet(
            f"MiniRoseCard {{ background-color: {FS.INK_2};"
            f" border: 1px solid {FS.LINE}; }}"
        )
        outer = QHBoxLayout(self)
        outer.setContentsMargins(14, 14, 14, 14)
        outer.setSpacing(14)

        self._rose = _RoseWidget()
        self._rose.setFixedSize(110, 110)
        outer.addWidget(self._rose)

        info = QVBoxLayout()
        info.setContentsMargins(0, 0, 0, 0)
        info.setSpacing(6)

        self.bearing_lbl = QLabel("—")
        self.bearing_lbl.setTextFormat(Qt.RichText)
        self.bearing_lbl.setStyleSheet(
            f"background: transparent; color: {FS.AMBER_BRIGHT};"
            f" font-family: {FF_MONO}; font-size: 28px; font-weight: 300;"
            f" letter-spacing: -1px;"
        )
        info.addWidget(self.bearing_lbl)

        self.caption_lbl = QLabel("avg bearing (gradient-weighted)".upper())
        self.caption_lbl.setStyleSheet(
            f"background: transparent; color: {FS.TXT_FAINT};"
            f" font-family: {FF_MONO}; font-size: 9px; letter-spacing: 0.8px;"
        )
        info.addWidget(self.caption_lbl)

        self.coh_lbl = QLabel("")
        self.coh_lbl.setTextFormat(Qt.RichText)
        self.coh_lbl.setStyleSheet(
            f"background: transparent; color: {FS.SAGE};"
            f" font-family: {FF_MONO}; font-size: 9.5px; letter-spacing: 0.4px;"
        )
        info.addWidget(self.coh_lbl)
        info.addStretch()
        outer.addLayout(info, 1)

    def set_state(self, bearing_deg, coherence, angle_hist=None):
        """Update rose state. ``angle_hist`` is an optional iterable of
        bin weights (most useful: 16 bins of 22.5° each starting at N)."""
        if bearing_deg is None or not math.isfinite(bearing_deg):
            self.bearing_lbl.setText("—")
            self._rose.set_bearing(None)
        else:
            compass = self._compass_letter(bearing_deg)
            self.bearing_lbl.setText(
                f"{bearing_deg:.0f}°"
                f"<span style='color:{FS.TXT_FAINT}; font-size:13px;"
                f" margin-left:6px; letter-spacing:1px;'> {compass}</span>"
            )
            self._rose.set_bearing(bearing_deg)
        self._rose.set_histogram(angle_hist)
        if coherence is None or not math.isfinite(coherence):
            self.coh_lbl.setText("")
        else:
            strength = (
                "strong" if coherence > 0.7
                else "moderate" if coherence > 0.4
                else "weak"
            )
            self.coh_lbl.setText(
                f"●  R = {coherence:.2f} — {strength} directional signal"
            )

    @staticmethod
    def _compass_letter(deg: float) -> str:
        # 8-point compass
        idx = int(((deg + 22.5) % 360) // 45)
        return ["N", "NE", "E", "SE", "S", "SW", "W", "NW"][idx]


class _RoseWidget(QWidget):
    """Painted compass rose with reticle rings, cardinals, amber wedges + mean bearing arrow.

    Rendered as a "recessed instrument glass" — a darker tone than the
    surrounding card (using ``INK``) for visible contrast on both dark and
    light themes. If an angle histogram is provided, draws proportional
    amber wedges showing the bin density of gradient directions.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._bearing = None
        self._hist = None  # optional list/array of weights per direction-bin

    def set_bearing(self, deg):
        self._bearing = deg
        self.update()

    def set_histogram(self, hist):
        self._hist = list(hist) if hist is not None else None
        self.update()

    # The rose deliberately uses always-dark "instrument glass" colours
    # regardless of the active app theme. Theme-adaptive contrast in light
    # mode left every internal detail (reticles, ticks, arrow) invisibly
    # faint; keeping the rose dark makes the amber wedges + bearing arrow
    # always pop, like the gauges on a real surveying instrument.
    _INSTRUMENT_BG = QColor("#1a1f2c")
    _INSTRUMENT_RIM = QColor("#3d4452")
    _INSTRUMENT_RING = QColor("#5d6577")
    _INSTRUMENT_TICK = QColor("#8a94a8")
    _INSTRUMENT_LABEL = QColor("#c4ccd3")

    def paintEvent(self, ev):
        p = QPainter(self)
        try:
            p.setRenderHint(QPainter.Antialiasing, True)
            w, h = self.width(), self.height()
            cx, cy = w / 2.0, h / 2.0
            r = min(w, h) / 2.0 - 5
            if r <= 0:
                return

            # ── 1. Background instrument circle ──
            try:
                p.setBrush(self._INSTRUMENT_BG)
                p.setPen(QPen(self._INSTRUMENT_RIM, 1))
                p.drawEllipse(QPointF(cx, cy), r, r)
            except Exception:
                pass

            # ── 2. Amber direction wedges (if histogram present) ──
            try:
                if self._hist:
                    valid = [float(v) for v in self._hist
                             if v is not None and math.isfinite(float(v))]
                    if valid:
                        hmax = max(valid)
                        if hmax > 0:
                            nbins = len(self._hist)
                            bin_span = 360.0 / nbins
                            for i, raw in enumerate(self._hist):
                                try:
                                    count = float(raw)
                                except Exception:
                                    count = 0.0
                                if count <= 0 or not math.isfinite(count):
                                    continue
                                norm = count / hmax
                                outer_r = (r - 6) * (0.30 + 0.70 * norm)
                                if outer_r < 4:
                                    continue
                                # Use drawPie (16ths-of-a-degree) instead of
                                # QPainterPath.arcTo — simpler API, fewer
                                # ways to silently fail.
                                compass_start = i * bin_span
                                qt_start_16 = int((90.0 - compass_start) * 16)
                                qt_sweep_16 = int(-bin_span * 16)
                                alpha = int(95 + 145 * norm)  # 95..240
                                amber = QColor("#d9a04e")
                                amber.setAlpha(alpha)
                                p.setBrush(amber)
                                p.setPen(Qt.NoPen)
                                rect = QRectF(cx - outer_r, cy - outer_r,
                                              2 * outer_r, 2 * outer_r)
                                p.drawPie(rect, qt_start_16, qt_sweep_16)
            except Exception:
                pass

            # ── 3. Concentric reticles (always-visible mid-grey) ──
            try:
                p.setBrush(Qt.NoBrush)
                p.setPen(QPen(self._INSTRUMENT_RING, 0.8))
                p.drawEllipse(QPointF(cx, cy), r * 0.66, r * 0.66)
                p.drawEllipse(QPointF(cx, cy), r * 0.33, r * 0.33)
            except Exception:
                pass

            # ── 4. Cardinal ticks + intercardinal hairs ──
            try:
                p.setPen(QPen(self._INSTRUMENT_TICK, 1.2))
                for ang_deg in (0, 90, 180, 270):
                    a = math.radians(ang_deg - 90)
                    x1 = cx + math.cos(a) * (r - 8)
                    y1 = cy + math.sin(a) * (r - 8)
                    x2 = cx + math.cos(a) * r
                    y2 = cy + math.sin(a) * r
                    p.drawLine(QPointF(x1, y1), QPointF(x2, y2))
                p.setPen(QPen(self._INSTRUMENT_RING, 0.8))
                for ang_deg in (45, 135, 225, 315):
                    a = math.radians(ang_deg - 90)
                    x1 = cx + math.cos(a) * (r - 4)
                    y1 = cy + math.sin(a) * (r - 4)
                    x2 = cx + math.cos(a) * r
                    y2 = cy + math.sin(a) * r
                    p.drawLine(QPointF(x1, y1), QPointF(x2, y2))
            except Exception:
                pass

            # ── 5. Mean bearing arrow ──
            try:
                if self._bearing is not None and math.isfinite(self._bearing):
                    a = math.radians(self._bearing - 90)
                    tip_x = cx + math.cos(a) * (r * 0.82)
                    tip_y = cy + math.sin(a) * (r * 0.82)
                    amber_bright = QColor("#f0bd6a")
                    pen = QPen(amber_bright)
                    pen.setWidthF(2.4)
                    pen.setCapStyle(Qt.RoundCap)
                    p.setPen(pen)
                    p.setBrush(Qt.NoBrush)
                    p.drawLine(QPointF(cx, cy), QPointF(tip_x, tip_y))
                    # Arrowhead
                    ah = 7.5
                    a1 = a + math.radians(150)
                    a2 = a - math.radians(150)
                    p.setPen(Qt.NoPen)
                    p.setBrush(amber_bright)
                    tri = QPolygonF([
                        QPointF(tip_x, tip_y),
                        QPointF(tip_x + math.cos(a1) * ah, tip_y + math.sin(a1) * ah),
                        QPointF(tip_x + math.cos(a2) * ah, tip_y + math.sin(a2) * ah),
                    ])
                    p.drawPolygon(tri)
                    # Center pip
                    p.drawEllipse(QPointF(cx, cy), 2.0, 2.0)
            except Exception:
                pass

            # ── 6. Compass letters (drawn inside the dark circle, mid-grey) ──
            try:
                font = QFont()
                font.setFamily("JetBrains Mono")
                font.setPointSize(7)
                font.setBold(True)
                p.setFont(font)
                p.setPen(self._INSTRUMENT_LABEL)
                # Position the letters just inside the rim so they don't
                # collide with the cardinal tick.
                inset = 12
                p.drawText(QRectF(cx - 7, inset - 4, 14, 12), Qt.AlignCenter, "N")
                p.drawText(QRectF(cx - 7, h - inset - 8, 14, 12), Qt.AlignCenter, "S")
                p.drawText(QRectF(inset - 4, cy - 6, 14, 12), Qt.AlignCenter, "W")
                p.drawText(QRectF(w - inset - 10, cy - 6, 14, 12), Qt.AlignCenter, "E")
            except Exception:
                pass
        finally:
            p.end()


class BandComparison(QWidget):
    """Two-band overlay showing Kept vs Rejected gradient distributions."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            f"BandComparison {{ background-color: {FS.INK_2};"
            f" border: 1px solid {FS.LINE}; }}"
        )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(4)

        self.kept_row = self._make_row("KEPT", FS.SAGE)
        self.rej_row  = self._make_row("REJ", FS.RUST)
        lay.addLayout(self.kept_row["row"])
        lay.addLayout(self.rej_row["row"])
        # Defaults
        self.set_data(None, None, None, None, None, None)

    def _make_row(self, name: str, color: str) -> dict:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)

        name_lbl = QLabel(name)
        name_lbl.setFixedWidth(50)
        name_lbl.setStyleSheet(
            f"background: transparent; color: {color};"
            f" font-family: {FF_MONO}; font-size: 9.5px;"
            f" letter-spacing: 1px;"
        )
        row.addWidget(name_lbl)

        track = _BandTrack(QColor(color))
        track.setMinimumHeight(14)
        track.setMaximumHeight(14)
        row.addWidget(track, 1)

        stat_lbl = QLabel("—")
        stat_lbl.setFixedWidth(110)
        stat_lbl.setStyleSheet(
            f"background: transparent; color: {FS.TXT_DIM};"
            f" font-family: {FF_MONO}; font-size: 9.5px;"
        )
        stat_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        row.addWidget(stat_lbl)

        return {"row": row, "track": track, "stat": stat_lbl}

    def set_stats(self, kept: dict | None, rej: dict | None):
        """Accept full distribution stats for each population.

        Each dict (when present) holds keys ``vmin / vmax / p25 / p75 /
        median / mean``. The track widget renders a box-and-whisker on a
        shared global axis so the two populations can be visually compared.
        """
        # Combined axis bounds = global min..max across both populations.
        candidates = []
        for s in (kept, rej):
            if not s:
                continue
            for k in ("vmin", "vmax", "p25", "p75", "median", "mean"):
                v = s.get(k)
                if v is not None and math.isfinite(v):
                    candidates.append(v)
        if not candidates:
            self.kept_row["track"].set_stats(None, 0.0, 1.0)
            self.rej_row["track"].set_stats(None, 0.0, 1.0)
            self.kept_row["stat"].setText("—")
            self.rej_row["stat"].setText("—")
            return
        gmin, gmax = min(candidates), max(candidates)
        if gmax == gmin:
            gmax = gmin + 1.0
        # Pad slightly so the whisker end caps don't touch the track edges.
        pad = (gmax - gmin) * 0.04
        gmin -= pad
        gmax += pad

        def fmt(v):
            return f"{v:.4f}" if (v is not None and math.isfinite(v)) else "—"

        self.kept_row["track"].set_stats(kept, gmin, gmax)
        self.rej_row["track"].set_stats(rej, gmin, gmax)
        self.kept_row["stat"].setText(
            f"μ {fmt(kept.get('mean')) if kept else '—'}"
        )
        self.rej_row["stat"].setText(
            f"μ {fmt(rej.get('mean')) if rej else '—'}"
        )

    # Back-compat — old call sites passed P10/P90; map to a stats dict
    # so they keep working until the refactor is complete.
    def set_data(self, kept_lo, kept_hi, kept_mean,
                 rej_lo, rej_hi, rej_mean):
        kept = None
        if kept_lo is not None and kept_hi is not None:
            kept = {
                "vmin": kept_lo, "vmax": kept_hi,
                "p25": kept_lo, "p75": kept_hi,
                "median": kept_mean, "mean": kept_mean,
            }
        rej = None
        if rej_lo is not None and rej_hi is not None:
            rej = {
                "vmin": rej_lo, "vmax": rej_hi,
                "p25": rej_lo, "p75": rej_hi,
                "median": rej_mean, "mean": rej_mean,
            }
        self.set_stats(kept, rej)


class _BandTrack(QWidget):
    """Horizontal box-and-whisker strip for one distribution.

    Renders on a shared global axis so two strips above/below each other
    can be compared visually:
      - Thin horizontal whisker line from MIN to MAX (full range)
      - Solid filled box from P25 to P75 (IQR)
      - Median tick across the box (slightly brighter)
      - Mean marker as a filled circle outside the box

    Replaces the previous P10-P90 gradient-bracket approach, which read as
    "everything is filled" when one population dominated the combined
    range.
    """

    def __init__(self, color: QColor, parent=None):
        super().__init__(parent)
        self._color = color
        self._stats = None  # dict: vmin/vmax/p25/p75/median/mean
        self._range_min = 0.0
        self._range_max = 1.0

    def set_stats(self, stats: dict | None, gmin: float, gmax: float):
        """Accept a stats dict and the SHARED global axis bounds."""
        self._stats = stats
        self._range_min = float(gmin) if gmin is not None else 0.0
        self._range_max = float(gmax) if gmax is not None and gmax > gmin else self._range_min + 1.0
        self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        try:
            w, h = self.width(), self.height()
            # ── track background (subtle ground) ──
            p.setRenderHint(QPainter.Antialiasing, False)
            p.fillRect(0, 0, w, h, FS.qc("INK_2"))
            p.setPen(QPen(FS.qc("LINE"), 1))
            p.setBrush(Qt.NoBrush)
            p.drawRect(0, 0, w - 1, h - 1)

            if not self._stats:
                return
            span = self._range_max - self._range_min
            if span <= 0:
                return

            def _x(v):
                if v is None or not math.isfinite(v):
                    return None
                return int((v - self._range_min) / span * (w - 2)) + 1

            vmin = _x(self._stats.get("vmin"))
            vmax = _x(self._stats.get("vmax"))
            p25 = _x(self._stats.get("p25"))
            p75 = _x(self._stats.get("p75"))
            med = _x(self._stats.get("median"))
            mean = _x(self._stats.get("mean"))

            color = QColor(self._color)
            mid_y = h / 2.0

            # ── whisker (min → max) ──
            p.setRenderHint(QPainter.Antialiasing, True)
            if vmin is not None and vmax is not None and vmax > vmin:
                whisker_pen = QPen(color)
                whisker_pen.setWidthF(1.2)
                p.setPen(whisker_pen)
                p.drawLine(QPointF(vmin, mid_y), QPointF(vmax, mid_y))
                # End caps (small vertical ticks at the ends of the whisker)
                cap_h = h * 0.4
                p.drawLine(QPointF(vmin, mid_y - cap_h / 2),
                           QPointF(vmin, mid_y + cap_h / 2))
                p.drawLine(QPointF(vmax, mid_y - cap_h / 2),
                           QPointF(vmax, mid_y + cap_h / 2))

            # ── IQR box (P25 → P75) ──
            if p25 is not None and p75 is not None and p75 > p25:
                box_fill = QColor(color)
                box_fill.setAlphaF(0.65)
                box_y = h * 0.18
                box_h = h * 0.64
                p.setBrush(box_fill)
                p.setPen(QPen(color, 1.0))
                p.drawRect(QRectF(p25, box_y, p75 - p25, box_h))

            # ── median tick inside the box ──
            if med is not None:
                med_pen = QPen(color.lighter(145))
                med_pen.setWidthF(1.6)
                p.setPen(med_pen)
                p.drawLine(QPointF(med, h * 0.18),
                           QPointF(med, h * 0.82))

            # ── mean marker (filled circle) ──
            if mean is not None:
                p.setPen(Qt.NoPen)
                p.setBrush(color.lighter(135))
                p.drawEllipse(QPointF(mean, mid_y), 3.0, 3.0)
                # White-ish ring around the mean dot to lift it off the box
                p.setBrush(Qt.NoBrush)
                p.setPen(QPen(QColor("#ffffff"), 0.8))
                p.drawEllipse(QPointF(mean, mid_y), 3.0, 3.0)
        finally:
            p.end()


# ════════════════════════════════════════════════════════════════════════
# DOMAIN-SPECIFIC COMPOSITES — Head + Gradient + Triangle panels
# ════════════════════════════════════════════════════════════════════════


class HeadPanel(ReticlePanel):
    """The 'Hydraulic Head' panel — profile distribution + readouts + note."""

    outlier_clicked = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.header = PanelHeader("§ 02", "Hydraulic Head")
        outer.addWidget(self.header)

        body = QWidget()
        body.setStyleSheet("background: transparent;")
        body_l = QVBoxLayout(body)
        body_l.setContentsMargins(16, 16, 16, 16)
        body_l.setSpacing(14)

        # Distribution profile
        self.profile = ProfileDistribution()
        body_l.addWidget(self.profile)

        # Distribution stat grid
        self.dist_grid = ReadoutGrid()
        for k_id, lbl in [
            ("mean", "Mean"), ("median", "Median"), ("std", "Std"),
            ("range", "Range"), ("iqr", "IQR Q1–Q3"), ("mad", "MAD"),
        ]:
            self.dist_grid.add_row(lbl, k_id)
        body_l.addWidget(self.dist_grid)

        # Coverage sub-section
        body_l.addWidget(SubHeader("DATA COVERAGE", "3 metrics"))
        self.cov_grid = ReadoutGrid()
        for k_id, lbl in [
            ("used", "Used / Total"), ("missing", "Missing Head"),
            ("dup_ids", "Dup IDs"),
        ]:
            self.cov_grid.add_row(lbl, k_id)
        body_l.addWidget(self.cov_grid)

        # Outlier IDs sub-section
        body_l.addWidget(SubHeader("OUTLIER IDS", "click to focus"))
        self.outlier_pills = PillRow()
        self.outlier_pills.pill_clicked.connect(self.outlier_clicked)
        body_l.addWidget(self.outlier_pills)

        # Spatial trend sub-section
        body_l.addWidget(SubHeader("SPATIAL TREND", "least-squares plane"))
        self.spatial_grid = ReadoutGrid()
        for k_id, lbl in [
            ("ew", "E–W Slope"), ("ns", "N–S Slope"), ("dom", "Dominant"),
        ]:
            self.spatial_grid.add_row(lbl, k_id)
        body_l.addWidget(self.spatial_grid)

        # Field note
        self.note = FieldNote("")
        body_l.addWidget(self.note)
        body_l.addStretch()

        outer.addWidget(body, 1)

    def clear(self):
        for grid in (self.dist_grid, self.cov_grid, self.spatial_grid):
            grid.clear_all()
        self.outlier_pills.set_ids([])
        self.note.set_note("")
        self.profile.set_data(None)
        self.header.set_meta("")

    def update_from_app(self, app):
        try:
            fdata = getattr(app, "filtered_data", None)
            cmap = getattr(app, "col_mapping", {}) or {}
            if fdata is None or getattr(fdata, "empty", True):
                self.clear()
                return
            h_col = cmap.get("hydraulic head")
            id_col = cmap.get("ID")
            x_col = cmap.get("x")
            y_col = cmap.get("y")
            if not h_col or h_col not in fdata.columns:
                self.clear()
                return
            heads = pd.to_numeric(fdata[h_col], errors="coerce")
            valid = heads.notna()
            heads_v = heads[valid].values
            if heads_v.size == 0:
                self.clear()
                return

            mean = float(np.mean(heads_v))
            median = float(np.median(heads_v))
            std = float(np.std(heads_v, ddof=1)) if heads_v.size > 1 else 0.0
            q1 = float(np.quantile(heads_v, 0.25))
            q3 = float(np.quantile(heads_v, 0.75))
            iqr = q3 - q1
            mad = float(np.median(np.abs(heads_v - median)))
            vmin = float(np.min(heads_v))
            vmax = float(np.max(heads_v))

            self.profile.set_data(
                heads_v,
                meta={"min": vmin, "max": vmax, "mean": mean, "std": std,
                      "median": median, "q1": q1, "q3": q3},
            )

            def m(v): return f"{v:.2f}<span style='color:{FS.TXT_FAINT};font-size:10px;'> m</span>"
            self.dist_grid.set("mean", m(mean))
            self.dist_grid.set("median", m(median))
            self.dist_grid.set("std", m(std))
            self.dist_grid.set("range", f"{vmin:.1f} – {vmax:.1f}",
                               f"{vmax - vmin:.1f} m span", "flat")
            self.dist_grid.set("iqr", f"{q1:.1f} – {q3:.1f}",
                               f"{iqr:.2f} m span", "flat")
            self.dist_grid.set("mad", m(mad))

            # Coverage
            total = int(len(fdata))
            used = int(valid.sum())
            missing = int(total - used)
            dup_ids = 0
            if id_col and id_col in fdata.columns:
                try:
                    dup_ids = int(fdata[id_col].duplicated().sum())
                except Exception:
                    dup_ids = 0
            self.cov_grid.set("used", f"{used:,} / {total:,}",
                              f"{(used/total*100 if total else 0):.1f}%", "flat")
            self.cov_grid.set("missing", str(missing),
                              "flag" if missing > 0 else "ok",
                              "warn" if missing > 0 else "flat")
            self.cov_grid.set("dup_ids", str(dup_ids),
                              "flag" if dup_ids > 0 else "ok",
                              "warn" if dup_ids > 0 else "flat")

            # Outliers via IQR fence (1.5×)
            lo_fence = q1 - 1.5 * iqr
            hi_fence = q3 + 1.5 * iqr
            out_mask = (heads_v < lo_fence) | (heads_v > hi_fence)
            n_lo = int(np.sum(heads_v < lo_fence))
            n_hi = int(np.sum(heads_v > hi_fence))
            self.outlier_pills.set_ids([])
            if id_col and id_col in fdata.columns:
                ids = fdata.loc[valid, id_col].values
                if ids.size == heads_v.size:
                    out_ids = [str(i) for i, m in zip(ids, out_mask) if m]
                    self.outlier_pills.set_ids(out_ids)

            # Spatial trend (least-squares plane on filtered data)
            ew_slope = ns_slope = None
            if (x_col and y_col and x_col in fdata.columns and y_col in fdata.columns):
                xs = pd.to_numeric(fdata.loc[valid, x_col], errors="coerce").values
                ys = pd.to_numeric(fdata.loc[valid, y_col], errors="coerce").values
                ok = np.isfinite(xs) & np.isfinite(ys) & np.isfinite(heads_v)
                if ok.sum() >= 3:
                    X = np.column_stack([xs[ok], ys[ok], np.ones(ok.sum())])
                    try:
                        coeffs, *_ = np.linalg.lstsq(X, heads_v[ok], rcond=None)
                        ew_slope, ns_slope = float(coeffs[0]), float(coeffs[1])
                    except Exception:
                        pass
            if ew_slope is None:
                self.spatial_grid.set("ew", "—")
                self.spatial_grid.set("ns", "—")
                self.spatial_grid.set("dom", "—")
            else:
                self.spatial_grid.set(
                    "ew", f"{ew_slope:+.4f}",
                    "m / m E to W" if ew_slope < 0 else "m / m W to E", "flat")
                self.spatial_grid.set(
                    "ns", f"{ns_slope:+.4f}",
                    "m / m N to S" if ns_slope < 0 else "m / m S to N", "flat")
                dom = "E → W" if abs(ew_slope) >= abs(ns_slope) else "N → S"
                if abs(ew_slope) > 0 and abs(ns_slope) > 0:
                    ratio = max(abs(ew_slope), abs(ns_slope)) / min(abs(ew_slope), abs(ns_slope))
                    self.spatial_grid.set("dom", f"<span style='color:{FS.AMBER_BRIGHT};'>{dom}</span>",
                                          f"{ratio:.1f}× stronger", "flat")
                else:
                    self.spatial_grid.set("dom", f"<span style='color:{FS.AMBER_BRIGHT};'>{dom}</span>")

            # Header meta
            self.header.set_meta(
                f"N <b style='color:{FS.AMBER_BRIGHT};'>{used:,}/{total:,}</b>"
                f" · clean rate <b style='color:{FS.AMBER_BRIGHT};'>{(used/total*100 if total else 0):.1f}%</b>"
            )

            # Field note
            note_bits = []
            if ew_slope is not None and ns_slope is not None:
                dom_lower = "eastward" if ew_slope > 0 else "westward"
                note_bits.append(f"Head rises {dom_lower} with a shallow plane.")
            if n_hi > n_lo + 5:
                note_bits.append(
                    f"Outlier population is biased toward the upper IQR fence "
                    f"({n_hi} high vs {n_lo} low) — investigate possible sensor drift "
                    f"at the high-side wells."
                )
            elif n_hi + n_lo > 0:
                note_bits.append(f"{n_hi + n_lo} points flagged as IQR outliers ({n_lo} low / {n_hi} high).")
            self.note.set_note(" ".join(note_bits) if note_bits else "")
        except Exception:
            # Defensive — keep the panel usable even if a stat fails to compute.
            pass


class GradientPanel(ReticlePanel):
    """The 'Gradient Field' panel — rose card + readouts + kept-vs-rej bands."""

    def __init__(self, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.header = PanelHeader("§ 03", "Gradient Field")
        outer.addWidget(self.header)

        body = QWidget()
        body.setStyleSheet("background: transparent;")
        body_l = QVBoxLayout(body)
        body_l.setContentsMargins(16, 16, 16, 16)
        body_l.setSpacing(14)

        self.rose = MiniRoseCard()
        body_l.addWidget(self.rose)

        self.core_grid = ReadoutGrid()
        for k_id, lbl in [
            ("avg", "Avg ∇"), ("ci", "CI 95%"), ("med", "Median"),
            ("std", "Std"), ("p10p90", "P10 / P90"), ("cv", "CV"),
        ]:
            self.core_grid.add_row(lbl, k_id)
        body_l.addWidget(self.core_grid)

        body_l.addWidget(SubHeader("KEPT vs REJECTED", "distribution overlay"))
        self.bands = BandComparison()
        body_l.addWidget(self.bands)

        self.ratio_grid = ReadoutGrid()
        for k_id, lbl in [
            ("mean_kr", "Mean K / R"), ("med_kr", "Median K / R"),
            ("iqr_ratio", "IQR Ratio"),
        ]:
            self.ratio_grid.add_row(lbl, k_id)
        body_l.addWidget(self.ratio_grid)

        self.note = FieldNote("")
        body_l.addWidget(self.note)
        body_l.addStretch()

        outer.addWidget(body, 1)

    def clear(self):
        self.core_grid.clear_all()
        self.ratio_grid.clear_all()
        self.bands.set_data(None, None, None, None, None, None)
        self.rose.set_state(None, None)
        self.note.set_note("")
        self.header.set_meta("")

    def update_from_app(self, app):
        try:
            tri = getattr(app, "triangle_data", None)
            rej = getattr(app, "rejected_data", None)
            if tri is None or getattr(tri, "empty", True):
                self.clear()
                return

            grad_col = self._find_col(tri, ["gradient_magnitude", "gradient", "grad_mag"])
            ang_col = self._find_col(tri, ["gradient_angle", "angle_deg", "angle", "direction"])
            grad_vals = self._numeric_or_none(tri, grad_col)
            if grad_vals is None or grad_vals.size == 0:
                self.clear()
                return

            mean = float(np.mean(grad_vals))
            median = float(np.median(grad_vals))
            std = float(np.std(grad_vals, ddof=1)) if grad_vals.size > 1 else 0.0
            p10 = float(np.quantile(grad_vals, 0.10))
            p90 = float(np.quantile(grad_vals, 0.90))
            cv = (std / mean) if mean else 0.0
            # 95% CI on the mean via normal approx
            ci_half = 1.96 * (std / math.sqrt(grad_vals.size)) if grad_vals.size > 1 else 0.0
            ci_lo, ci_hi = mean - ci_half, mean + ci_half

            def f(v): return f"{v:.5f}"
            self.core_grid.set("avg", f(mean),
                               f"<span style='color:{FS.TXT_FAINT}'>m/m</span>", "flat")
            self.core_grid.set("ci", f"{ci_lo:.5f} – {ci_hi:.5f}",
                               f"95% interval", "flat")
            self.core_grid.set("med", f(median),
                               f"<span style='color:{FS.TXT_FAINT}'>m/m</span>", "flat")
            self.core_grid.set("std", f(std))
            self.core_grid.set("p10p90", f"{p10:.5f} / {p90:.5f}",
                               (f"{p90 / p10:.1f}× ratio" if p10 > 0 else ""), "flat")
            self.core_grid.set("cv", f"{cv:.3f}")

            # Direction + coherence
            bearing, coherence = self._direction_stats(tri, ang_col, grad_vals)
            # Direction histogram (16 wedges, 22.5° each, weighted by ∇ magnitude)
            angle_hist = self._direction_histogram(tri, ang_col, grad_vals)
            self.rose.set_state(bearing, coherence, angle_hist=angle_hist)

            # Kept vs Rejected — pass full distribution stats so the
            # box-and-whisker tracks render correctly.
            rej_vals = None
            if rej is not None and not getattr(rej, "empty", True):
                rej_grad_col = self._find_col(rej, ["gradient_magnitude", "gradient", "grad_mag"])
                rej_vals = self._numeric_or_none(rej, rej_grad_col)

            kept_stats = self._distribution_stats(grad_vals)
            rej_stats = self._distribution_stats(rej_vals) if rej_vals is not None else None
            self.bands.set_stats(kept_stats, rej_stats)

            if rej_stats is not None:
                rej_mean_v = rej_stats["mean"]
                rej_median_v = rej_stats["median"]
                kept_iqr = kept_stats["p75"] - kept_stats["p25"]
                rej_iqr = rej_stats["p75"] - rej_stats["p25"]
                ratio_mean = (rej_mean_v / mean) if mean else 0.0
                ratio_med = (rej_median_v / median) if median else 0.0
                ratio_iqr = (rej_iqr / kept_iqr) if kept_iqr else 0.0
                self.ratio_grid.set("mean_kr",
                                    f"{mean:.5f}<span style='color:{FS.TXT_FAINT};'> · </span>{rej_mean_v:.5f}",
                                    f"1 : {ratio_mean:.2f}", "flat")
                self.ratio_grid.set("med_kr",
                                    f"{median:.5f}<span style='color:{FS.TXT_FAINT};'> · </span>{rej_median_v:.5f}",
                                    f"1 : {ratio_med:.2f}", "flat")
                self.ratio_grid.set("iqr_ratio",
                                    f"1 : {ratio_iqr:.2f}",
                                    "rej / kept", "flat")
            else:
                self.ratio_grid.set("mean_kr", f"{mean:.5f}", "no rej", "flat")
                self.ratio_grid.set("med_kr", f"{median:.5f}", "no rej", "flat")
                self.ratio_grid.set("iqr_ratio", "—", "no rej", "flat")

            # Header meta
            coh_str = f"<b style='color:{FS.SAGE};'>{coherence:.2f}</b>" if coherence is not None else "—"
            self.header.set_meta(
                f"N <b style='color:{FS.AMBER_BRIGHT};'>{grad_vals.size:,}</b>"
                f" · CV <b style='color:{FS.AMBER_BRIGHT};'>{cv:.3f}</b>"
                f" · R {coh_str}"
            )

            # Field note
            note = ""
            if rej_vals is not None and rej_vals.size > 0 and mean:
                ratio = rej_mean / mean
                note += (
                    f"Rejected triangles carry ~{ratio:.1f}× the gradient magnitude of kept ones — "
                    f"the rejection filter is removing the high-gradient tail as designed. "
                )
            if coherence is not None:
                if coherence > 0.7:
                    note += f"Coherence holds at <code>R = {coherence:.2f}</code>; flow direction is well-constrained."
                elif coherence > 0.4:
                    note += f"Coherence <code>R = {coherence:.2f}</code> — moderate directional signal."
                else:
                    note += f"Coherence <code>R = {coherence:.2f}</code> — weak directional signal; treat bearing with care."
            self.note.set_note(note)
        except Exception:
            pass

    @staticmethod
    def _find_col(df, names):
        for n in names:
            if n in df.columns:
                return n
        return None

    @staticmethod
    def _unwrap_scalar_series(series):
        """Some columns in triangle_data store scalars as single-element
        lists/arrays (e.g. ``[145.0]`` instead of ``145.0``). Flatten those
        so ``pd.to_numeric`` works without losing data.
        """
        try:
            first = series.dropna().iloc[0] if not series.empty else None
        except Exception:
            first = None
        if isinstance(first, (list, np.ndarray, tuple)):
            return series.apply(
                lambda v: (v[0] if isinstance(v, (list, np.ndarray, tuple)) and len(v) > 0 else v)
            )
        return series

    @staticmethod
    def _numeric_or_none(df, col):
        if col is None or col not in df.columns:
            return None
        s = GradientPanel._unwrap_scalar_series(df[col])
        s = pd.to_numeric(s, errors="coerce")
        arr = s.dropna().values
        return arr if arr.size else None

    @staticmethod
    def _distribution_stats(values):
        """Return {vmin, vmax, p25, p75, median, mean} for an array of values.

        Used by ``BandComparison`` to render box-and-whisker strips. Returns
        ``None`` if the values are empty / unusable.
        """
        if values is None:
            return None
        arr = np.asarray(values, dtype=float)
        arr = arr[np.isfinite(arr)]
        if arr.size == 0:
            return None
        return {
            "vmin": float(np.min(arr)),
            "vmax": float(np.max(arr)),
            "p25": float(np.quantile(arr, 0.25)),
            "p75": float(np.quantile(arr, 0.75)),
            "median": float(np.median(arr)),
            "mean": float(np.mean(arr)),
        }

    # NOTE on angle convention:
    # ``triangle_data['angle']`` stores values in MATH convention
    # (0° = East, CCW positive — see core/gradient_calculation.py:546 and
    # the existing rose diagram which renders with set_theta_zero_location('E')
    # + set_theta_direction(1)). The stats-panel rose card displays in
    # COMPASS convention (0° = North, CW positive — N at top). Conversion:
    #     compass = (90 - math) % 360
    # All public outputs of _direction_stats / _direction_histogram are in
    # compass convention so the rose card's geometry just works.

    @staticmethod
    def _direction_histogram(df, ang_col, weights, nbins: int = 16):
        """Weighted compass-bin histogram for the rose's wedges.

        Input angles are math convention; output bin ``i`` covers compass
        bearings ``[i * (360/nbins), (i + 1) * (360/nbins))`` starting at
        N. Weights are gradient magnitudes when available, else counts.
        """
        if ang_col is None or ang_col not in df.columns:
            return None
        s = GradientPanel._unwrap_scalar_series(df[ang_col])
        a = pd.to_numeric(s, errors="coerce")
        ok = a.notna()
        if not ok.any():
            return None
        math_deg = a[ok].values
        # Math → compass conversion.
        compass_deg = (90.0 - math_deg) % 360.0
        # Align weights to the valid angle rows. If lengths don't match
        # (because weights came from a different filter pass) fall back
        # to unit weights to keep the histogram meaningful.
        if weights is not None and weights.size == compass_deg.size:
            w_arr = np.abs(weights)
        else:
            w_arr = np.ones_like(compass_deg)
        bin_span = 360.0 / nbins
        bin_idx = np.floor(compass_deg / bin_span).astype(int)
        bin_idx = np.clip(bin_idx, 0, nbins - 1)
        hist = np.zeros(nbins)
        for i, w in zip(bin_idx, w_arr):
            hist[i] += float(w)
        return hist.tolist()

    @staticmethod
    def _direction_stats(df, ang_col, weights):
        """Return ``(mean_compass_deg, coherence_R)``.

        Input angles are math convention; output bearing is compass
        convention (0° = N, clockwise) so it can be passed directly to
        ``MiniRoseCard.set_state``.
        """
        if ang_col is None or ang_col not in df.columns:
            return None, None
        s = GradientPanel._unwrap_scalar_series(df[ang_col])
        angles_math = pd.to_numeric(s, errors="coerce").dropna().values
        if angles_math.size == 0:
            return None, None
        # Convert math (0°=E, CCW) → compass (0°=N, CW) BEFORE the circular
        # mean. Doing it before/after is mathematically equivalent — doing
        # it before keeps the sin/cos terms aligned with their geographic
        # meaning (sin = east component, cos = north component when input
        # is compass).
        compass = (90.0 - angles_math) % 360.0
        rad = np.radians(compass)
        if weights is not None and weights.size == compass.size:
            w = np.abs(weights)
        else:
            w = np.ones_like(compass)
        # In compass space: sin(b) = east component, cos(b) = north component.
        east_sum = np.sum(w * np.sin(rad))
        north_sum = np.sum(w * np.cos(rad))
        total_w = np.sum(w)
        if total_w == 0:
            return None, None
        mean_rad = math.atan2(east_sum, north_sum)
        mean_compass = math.degrees(mean_rad) % 360.0
        R = math.hypot(east_sum, north_sum) / total_w
        return mean_compass, R


class TrianglePanel(ReticlePanel):
    """Full-width Triangle Analysis panel — embeds existing widgets in new chrome."""

    open_inspector_requested = pyqtSignal()
    export_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.header = PanelHeader("§ 04", "Triangle Analysis")
        outer.addWidget(self.header)

        body = QWidget()
        body.setStyleSheet("background: transparent;")
        body_l = QVBoxLayout(body)
        body_l.setContentsMargins(16, 16, 16, 16)
        body_l.setSpacing(14)

        # Summary cards (existing widget — already an inline strip)
        self.tri_summary = TriangleSummaryCards()
        body_l.addWidget(self.tri_summary)

        # Splitter: left (geometry + frequency) / right (table + breakdown)
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(4)
        splitter.setChildrenCollapsible(False)
        splitter.setStyleSheet(
            f"QSplitter::handle {{ background-color: {FS.LINE_STRONG}; width: 4px; }}"
            f"QSplitter::handle:hover {{ background-color: {FS.AMBER}; }}"
        )

        # Left side
        left = QWidget()
        left.setStyleSheet("background: transparent;")
        left_l = QVBoxLayout(left)
        left_l.setContentsMargins(0, 0, 6, 0)
        left_l.setSpacing(10)
        left_l.addWidget(SubHeader("GEOMETRY HEATMAP", "colored by ∇ magnitude"))
        self.tri_geometry = TriangleGeometryPlot()
        self.tri_geometry.setMinimumHeight(220)
        left_l.addWidget(self.tri_geometry, 3)
        left_l.addWidget(SubHeader("POINT FREQUENCY IN REJECTIONS", "top wells"))
        self.tri_frequency = PointFrequencyBars()
        left_l.addWidget(self.tri_frequency, 2)
        splitter.addWidget(left)

        # Right side
        right = QWidget()
        right.setStyleSheet("background: transparent;")
        right_l = QVBoxLayout(right)
        right_l.setContentsMargins(6, 0, 0, 0)
        right_l.setSpacing(10)
        right_l.addWidget(SubHeader("TRIANGLE TABLE", "click row to inspect"))
        self.tri_table = TriangleTableWidget()
        right_l.addWidget(self.tri_table, 1)
        right_l.addWidget(SubHeader("REJECTION BREAKDOWN", "by primary cause"))
        self.tri_breakdown = RejectionBreakdownBars()
        right_l.addWidget(self.tri_breakdown)
        splitter.addWidget(right)
        splitter.setSizes([500, 500])
        splitter.setMinimumHeight(520)

        body_l.addWidget(splitter, 1)

        # Connect hover sync + filter sync
        self.tri_table.triangle_hovered.connect(self.tri_geometry.highlight_triangle)
        self.tri_table.filter_changed.connect(self.tri_geometry.set_filter_mode)

        # Action bar (replaces the old buttons-at-bottom)
        action_row = QHBoxLayout()
        action_row.setContentsMargins(0, 8, 0, 0)
        action_row.setSpacing(10)

        self.export_btn = QPushButton("EXPORT REJECTED · CSV")
        self.export_btn.setEnabled(False)
        self.export_btn.setCursor(Qt.PointingHandCursor)
        self.export_btn.setStyleSheet(
            f"QPushButton {{ background: transparent;"
            f" border: 1px solid {FS.LINE_STRONG}; color: {FS.TXT_DIM};"
            f" font-family: {FF_MONO}; font-size: 10px;"
            f" font-weight: 500; letter-spacing: 1.2px;"
            f" padding: 7px 14px; }}"
            f"QPushButton:hover:enabled {{ border-color: {FS.AMBER};"
            f" color: {FS.AMBER_BRIGHT};"
            f" background-color: {FS.AMBER_FAINT}; }}"
            f"QPushButton:disabled {{ color: {FS.TXT_GHOST};"
            f" border-color: {FS.LINE}; }}"
        )
        self.export_btn.clicked.connect(self.export_requested.emit)
        action_row.addWidget(self.export_btn)

        action_row.addStretch()

        self.selection_hint = QLabel("")
        self.selection_hint.setStyleSheet(
            f"color: {FS.TXT_FAINT}; background: transparent;"
            f" font-family: {FF_MONO}; font-size: 9.5px; letter-spacing: 0.6px;"
        )
        action_row.addWidget(self.selection_hint)

        self.open_inspector_btn = QPushButton("INSPECT SELECTED →")
        self.open_inspector_btn.setEnabled(False)
        self.open_inspector_btn.setCursor(Qt.PointingHandCursor)
        self.open_inspector_btn.setStyleSheet(
            f"QPushButton {{ background-color: {FS.AMBER};"
            f" border: 1px solid {FS.AMBER}; color: {FS.INK};"
            f" font-family: {FF_MONO}; font-size: 10px;"
            f" font-weight: 700; letter-spacing: 1.2px;"
            f" padding: 7px 14px; }}"
            f"QPushButton:hover:enabled {{ background-color: {FS.AMBER_BRIGHT};"
            f" border-color: {FS.AMBER_BRIGHT}; }}"
            f"QPushButton:disabled {{ background-color: transparent;"
            f" color: {FS.TXT_GHOST}; border-color: {FS.LINE}; }}"
        )
        self.open_inspector_btn.clicked.connect(self.open_inspector_requested.emit)
        action_row.addWidget(self.open_inspector_btn)

        body_l.addLayout(action_row)

        outer.addWidget(body, 1)

        # Wire frequency-selection sync to the action bar hint + button label
        self._selected_ids: set = set()
        self.tri_frequency.selection_changed.connect(self._on_frequency_selection_changed)

    def _on_frequency_selection_changed(self, ids):
        self._selected_ids = set(ids) if ids else set()
        n = len(self._selected_ids)
        if n > 0:
            self.open_inspector_btn.setText(f"INSPECT {n} SELECTED →")
            self.selection_hint.setText(f"{n} POINT{'S' if n != 1 else ''} SELECTED")
        else:
            self.open_inspector_btn.setText("INSPECT SELECTED →")
            self.selection_hint.setText("")

    def selected_ids(self) -> set:
        return set(self._selected_ids)

    def clear(self):
        self.tri_summary.clear()
        self.tri_breakdown.clear()
        self.tri_frequency.clear()
        self.tri_table.clear()
        self.tri_geometry.clear()
        self.export_btn.setEnabled(False)
        self.open_inspector_btn.setEnabled(False)
        self.selection_hint.setText("")
        self.header.set_meta("")


# ════════════════════════════════════════════════════════════════════════
# RAW READOUT VIEW (placeholder stub — full implementation pending)
# ════════════════════════════════════════════════════════════════════════


class RawReadoutView(QWidget):
    """Placeholder for the dense raw-readout view (tab 06).

    Real implementation will be a sortable / searchable QTreeView with
    section grouping and inline sparkline / LED-pip / delta-vs-baseline
    columns. For now, shows a styled placeholder so the tab works.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background-color: {FS.INK};")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(40, 60, 40, 60)
        lay.setSpacing(14)
        lay.addStretch()

        head = QLabel("RAW · DENSE READOUT")
        head.setAlignment(Qt.AlignCenter)
        head.setStyleSheet(
            f"color: {FS.AMBER}; background: transparent;"
            f" font-family: {FF_MONO}; font-size: 11px; letter-spacing: 3px;"
        )
        lay.addWidget(head)

        body = QLabel(
            "<div style='text-align:center;'>"
            "Implementation pending — see <code>stats_dashboard_concept_v2_raw.html</code> for the target view."
            "<br/><br/>Will render all metrics as a sortable / searchable table with section grouping, "
            "inline trend sparklines, and per-row baseline-delta annotations."
            "</div>"
        )
        body.setAlignment(Qt.AlignCenter)
        body.setWordWrap(True)
        body.setStyleSheet(
            f"color: {FS.TXT_DIM}; background: transparent;"
            f" font-family: {FF_PROSE}; font-size: 13px;"
            f" font-style: italic; line-height: 1.6;"
        )
        lay.addWidget(body)
        lay.addStretch()


# ════════════════════════════════════════════════════════════════════════
# Other tab placeholders (Head / Gradient / Triangles / Snapshots)
# ════════════════════════════════════════════════════════════════════════


def _make_placeholder(title: str, message: str) -> QWidget:
    """Build a centred-text placeholder widget for stubbed tabs."""
    w = QWidget()
    w.setStyleSheet(f"background-color: {FS.INK};")
    lay = QVBoxLayout(w)
    lay.setContentsMargins(40, 60, 40, 60)
    lay.setSpacing(14)
    lay.addStretch()
    head = QLabel(title.upper())
    head.setAlignment(Qt.AlignCenter)
    head.setStyleSheet(
        f"color: {FS.AMBER}; background: transparent;"
        f" font-family: {FF_MONO}; font-size: 11px; letter-spacing: 3px;"
    )
    lay.addWidget(head)
    body = QLabel(message)
    body.setAlignment(Qt.AlignCenter)
    body.setWordWrap(True)
    body.setStyleSheet(
        f"color: {FS.TXT_DIM}; background: transparent;"
        f" font-family: {FF_PROSE}; font-size: 13px;"
        f" font-style: italic;"
    )
    lay.addWidget(body)
    lay.addStretch()
    return w


# ════════════════════════════════════════════════════════════════════════
# MAIN PANEL
# ════════════════════════════════════════════════════════════════════════


class StatisticsPanel(QWidget):
    """Statistics Dashboard — Field Survey redesign.

    Composed of:
      - TopBar (brand + segmented tabs + scope chip + actions)
      - HealthStrip (5 instrument gauges)
      - QStackedWidget routing each tab to its content view:
          0 Overview · Head + Gradient (side-by-side) + Triangle Analysis
          1 Head     · placeholder (use Overview's panel for now)
          2 Gradient · placeholder
          3 Triangles· placeholder
          4 Snapshots· placeholder
          5 Raw      · placeholder (will become the dense readout table)
    """

    # Signals — preserve names/signatures used by main_window.
    open_inspector_requested = pyqtSignal()
    export_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"StatisticsPanel {{ background-color: {FS.INK}; }}")
        self.setAttribute(Qt.WA_StyledBackground, True)

        # Derived-stats cache layer (kept for parity with old impl).
        self._derived_cache_key = None
        self._derived_cache: dict = {}
        self._bound_table_key = None
        self._bound_geometry_key = None
        self._last_app_context = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Topbar ──
        self.topbar = TopBar()
        self.topbar.export_requested.connect(self._on_topbar_export)
        self.topbar.pin_baseline_requested.connect(self._on_pin_baseline)
        self.topbar.tab_changed.connect(self._on_tab_changed)
        self.topbar.scope_clicked.connect(self._on_scope_clicked)
        outer.addWidget(self.topbar)

        # ── Health Strip ──
        self.health = HealthStrip()
        outer.addWidget(self.health)

        # ── Stacked content ──
        self.stack = QStackedWidget()
        self.stack.setStyleSheet(f"QStackedWidget {{ background-color: {FS.INK}; }}")
        outer.addWidget(self.stack, 1)

        # Page 0 — Overview
        self._overview_page = self._build_overview_page()
        self.stack.addWidget(self._overview_page)
        # Page 1 — Head deep dive (placeholder reusing existing widget)
        self._head_detail_page = self._build_detail_page(
            "§ 02 · HYDRAULIC HEAD · DETAIL",
            HeadStatisticsWidget(),
        )
        self.stack.addWidget(self._head_detail_page)
        # Page 2 — Gradient deep dive (placeholder reusing existing widget)
        self._grad_detail_page = self._build_detail_page(
            "§ 03 · GRADIENT FIELD · DETAIL",
            GradientStatisticsWidget(),
        )
        self.stack.addWidget(self._grad_detail_page)
        # Page 3 — Triangles tab is identical to Overview's panel for now
        # (most users come here from Overview's full-width panel anyway).
        self.stack.addWidget(_make_placeholder(
            "Triangles · Detail",
            "Use the Triangle Analysis panel on the Overview tab — "
            "a dedicated full-width detail view is on the roadmap.",
        ))
        # Page 4 — Snapshots placeholder
        self.stack.addWidget(_make_placeholder(
            "Snapshots",
            "Save a baseline snapshot via PIN BASELINE in the topbar. "
            "Snapshots and side-by-side comparison are on the roadmap.",
        ))
        # Page 5 — Raw placeholder
        self._raw_view = RawReadoutView()
        self.stack.addWidget(self._raw_view)

        # Default to Overview
        self.stack.setCurrentIndex(0)

        # Hook deep-dive widgets so they refresh on update_statistics.
        # Store refs for the update path.
        self._head_detail_widget = self._head_detail_page.findChild(HeadStatisticsWidget)
        self._grad_detail_widget = self._grad_detail_page.findChild(GradientStatisticsWidget)

        # Default scope chip text — will be overwritten on first update.
        self.topbar.scope_chip.set_scope("—")

    # ──────────────────────────────────────────────────────────────────
    # Layout builders
    # ──────────────────────────────────────────────────────────────────

    def _build_overview_page(self) -> QWidget:
        """Overview tab: head + gradient panels + full-width triangle panel."""
        page = QScrollArea()
        page.setWidgetResizable(True)
        page.setFrameShape(QFrame.NoFrame)
        page.setStyleSheet(
            f"QScrollArea {{ background-color: {FS.INK}; border: 0; }}"
            f"QScrollBar:vertical {{ background: transparent; width: 6px; }}"
            f"QScrollBar::handle:vertical {{ background: {FS.LINE_STRONG}; border-radius: 3px; }}"
            f"QScrollBar::handle:vertical:hover {{ background: {FS.AMBER}; }}"
        )

        content = QWidget()
        content.setStyleSheet(f"background-color: {FS.INK};")
        v = QVBoxLayout(content)
        v.setContentsMargins(18, 14, 18, 28)
        v.setSpacing(14)

        # Top row: head + gradient side-by-side
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(14)
        self.head_panel = HeadPanel()
        self.grad_panel = GradientPanel()
        row.addWidget(self.head_panel, 1)
        row.addWidget(self.grad_panel, 1)
        v.addLayout(row)

        # Triangle Analysis full-width
        self.tri_panel = TrianglePanel()
        self.tri_panel.open_inspector_requested.connect(self.open_inspector_requested)
        self.tri_panel.export_requested.connect(self.export_requested)
        v.addWidget(self.tri_panel)

        v.addStretch()

        page.setWidget(content)
        return page

    def _build_detail_page(self, title: str, inner_widget: QWidget) -> QWidget:
        """Wrap an existing detail widget in a styled scroll container."""
        page = QScrollArea()
        page.setWidgetResizable(True)
        page.setFrameShape(QFrame.NoFrame)
        page.setStyleSheet(
            f"QScrollArea {{ background-color: {FS.INK}; border: 0; }}"
            f"QScrollBar:vertical {{ background: transparent; width: 6px; }}"
            f"QScrollBar::handle:vertical {{ background: {FS.LINE_STRONG}; border-radius: 3px; }}"
            f"QScrollBar::handle:vertical:hover {{ background: {FS.AMBER}; }}"
        )
        content = QWidget()
        content.setStyleSheet(f"background-color: {FS.INK};")
        v = QVBoxLayout(content)
        v.setContentsMargins(18, 14, 18, 28)
        v.setSpacing(12)

        title_label = QLabel(title)
        title_label.setStyleSheet(
            f"color: {FS.AMBER}; background: transparent;"
            f" font-family: {FF_MONO}; font-size: 11px; letter-spacing: 3px;"
            f" padding-bottom: 4px; border-bottom: 1px solid {FS.LINE};"
        )
        v.addWidget(title_label)
        v.addWidget(inner_widget)
        v.addStretch()
        page.setWidget(content)
        return page

    # ──────────────────────────────────────────────────────────────────
    # Topbar signal handlers
    # ──────────────────────────────────────────────────────────────────

    def _on_tab_changed(self, idx: int):
        self.stack.setCurrentIndex(idx)

    def _on_topbar_export(self):
        # Open a small menu — for now, route to the Triangle export action.
        menu = QMenu(self)
        menu.setStyleSheet(
            f"QMenu {{ background-color: {FS.PANEL}; color: {FS.TXT};"
            f" border: 1px solid {FS.LINE_STRONG}; padding: 4px; }}"
            f"QMenu::item {{ padding: 6px 16px; font-family: {FF_MONO};"
            f" font-size: 10px; letter-spacing: 0.8px; }}"
            f"QMenu::item:selected {{ background-color: {FS.AMBER_FAINT};"
            f" color: {FS.AMBER_BRIGHT}; }}"
        )
        a_csv = QAction("EXPORT REJECTED · CSV", self)
        a_csv.triggered.connect(self.export_requested.emit)
        menu.addAction(a_csv)
        a_report = QAction("FULL REPORT · PDF  (soon)", self)
        a_report.setEnabled(False)
        menu.addAction(a_report)
        # Position below the button
        btn = self.topbar.export_btn
        menu.exec_(btn.mapToGlobal(QPoint(0, btn.height())))

    def _on_pin_baseline(self):
        # Placeholder — baseline-snapshot persistence pending.
        self.topbar.scope_chip.set_scope(
            self.topbar.scope_chip.text().replace("●  ", "✓  ", 1)
            if not self.topbar.scope_chip.text().startswith("✓  ")
            else self.topbar.scope_chip.text()
        )

    def _on_scope_clicked(self):
        # In a real impl this opens a cell selector menu (clone of the
        # status-bar chip). For now, no-op.
        pass

    # ──────────────────────────────────────────────────────────────────
    # Data binding
    # ──────────────────────────────────────────────────────────────────

    @staticmethod
    def _safe_len(df) -> int:
        try:
            return int(len(df)) if df is not None else 0
        except Exception:
            return 0

    def _build_derived_cache_key(self, app, total_triangles):
        tri = getattr(app, "triangle_data", None)
        rej = getattr(app, "rejected_data", None)
        grad = getattr(app, "gradient_data", None)
        fdata = getattr(app, "filtered_data", None)
        cmap = getattr(app, "col_mapping", {}) or {}
        try:
            cmap_key = tuple(sorted((str(k), str(v)) for k, v in cmap.items()))
        except Exception:
            cmap_key = tuple()
        return (
            id(tri), self._safe_len(tri),
            id(rej), self._safe_len(rej),
            id(grad), self._safe_len(grad),
            id(fdata), self._safe_len(fdata),
            int(total_triangles) if isinstance(total_triangles, (int, np.integer)) else -1,
            cmap_key,
        )

    @staticmethod
    def _stats_perf_log(app, message: str):
        logger = getattr(app, "_perf_log", None)
        if callable(logger):
            logger(message)
        else:
            print(message, flush=True)

    def get_selected_point_ids(self) -> set:
        """Currently selected point IDs from the Triangle panel's frequency bars."""
        try:
            return self.tri_panel.selected_ids()
        except Exception:
            return set()

    def update_statistics(self, app):
        """Update every panel + the health strip + the scope chip."""
        self._last_app_context = app
        t0_total = time.perf_counter()

        # ── Health strip ──
        fdata = getattr(app, "filtered_data", None)
        raw = getattr(app, "data", None)
        n_filtered = self._safe_len(fdata)
        n_raw = self._safe_len(raw)
        # Data points gauge
        self.health.gauge_points.set_value(f"{n_filtered:,}")
        pct_raw = (n_filtered / n_raw * 100.0) if n_raw else 0.0
        self.health.gauge_points.set_meta(
            f"FILTERED · <b style='color:{FS.TXT};'>{pct_raw:.1f}%</b> OF RAW"
        )

        total_triangles = getattr(app, "total_triangles", None)
        n_tri = self._safe_len(getattr(app, "triangle_data", None))
        n_rej = self._safe_len(getattr(app, "rejected_data", None))
        # Triangle keep
        if isinstance(total_triangles, (int, np.integer)) and int(total_triangles) > 0:
            keep_pct = n_tri / int(total_triangles) * 100.0
            self.health.gauge_triangles.set_value(
                f"{n_tri:,}<span style='color:{FS.TXT_FAINT};font-size:13px;'>/{int(total_triangles):,}</span>"
            )
            self.health.gauge_triangles.set_meta(
                f"KEPT RATE · <b style='color:{FS.SAGE};'>{keep_pct:.1f}%</b>"
            )
            if keep_pct >= 90:
                self.health.gauge_triangles.set_led("sage")
            elif keep_pct >= 75:
                self.health.gauge_triangles.set_led("amber")
            else:
                self.health.gauge_triangles.set_led("rust")
        else:
            self.health.gauge_triangles.set_value(f"{n_tri:,}")
            self.health.gauge_triangles.set_meta("")
            self.health.gauge_triangles.set_led("sage")

        # Rejected
        self.health.gauge_rejected.set_value(f"{n_rej:,}")
        if n_tri + n_rej > 0:
            rej_pct = n_rej / (n_tri + n_rej) * 100.0
            self.health.gauge_rejected.set_meta(
                f"OF TOTAL · <b style='color:{FS.AMBER_BRIGHT};'>{rej_pct:.1f}%</b>"
            )
            self.health.gauge_rejected.set_led(
                "sage" if rej_pct < 5 else "amber" if rej_pct < 15 else "rust"
            )
        else:
            self.health.gauge_rejected.set_meta("")

        # Head profile gauge — set sparkline values from head distribution
        cmap = getattr(app, "col_mapping", {}) or {}
        h_col = cmap.get("hydraulic head")
        if fdata is not None and not getattr(fdata, "empty", True) and h_col and h_col in fdata.columns:
            heads = pd.to_numeric(fdata[h_col], errors="coerce").dropna().values
            if heads.size > 4:
                hist, _ = np.histogram(heads, bins=min(16, max(6, int(math.sqrt(heads.size)))))
                self.health.gauge_head.set_spark(list(hist.astype(float)))
                mean = float(np.mean(heads))
                std = float(np.std(heads, ddof=1)) if heads.size > 1 else 0.0
                self.health.gauge_head.set_value("")  # value is the sparkline itself
                self.health.gauge_head.set_meta(
                    f"μ <b style='color:{FS.TXT};'>{mean:.2f} m</b>"
                    f" · σ <b style='color:{FS.TXT};'>{std:.2f}</b>"
                )
            else:
                self.health.gauge_head.set_spark([])
                self.health.gauge_head.set_meta("INSUFFICIENT POINTS")
        else:
            self.health.gauge_head.set_spark([])
            self.health.gauge_head.set_meta("")

        # Direction R gauge
        tri = getattr(app, "triangle_data", None)
        coherence = bearing = None
        if tri is not None and not getattr(tri, "empty", True):
            ang_col = GradientPanel._find_col(tri, ["gradient_angle", "angle_deg", "angle", "direction"])
            grad_col = GradientPanel._find_col(tri, ["gradient_magnitude", "gradient", "grad_mag"])
            weights = GradientPanel._numeric_or_none(tri, grad_col)
            bearing, coherence = GradientPanel._direction_stats(tri, ang_col, weights)
        if coherence is not None:
            self.health.gauge_direction.set_value(f"{coherence:.2f}")
            bearing_txt = f"{bearing:.0f}°" if bearing is not None else "—"
            self.health.gauge_direction.set_meta(
                f"BEARING · <b style='color:{FS.AMBER};'>{bearing_txt}</b>"
                f" · {'STRONG' if coherence > 0.7 else 'MODERATE' if coherence > 0.4 else 'WEAK'}"
            )
            self.health.gauge_direction.set_led(
                "sage" if coherence > 0.7 else "amber" if coherence > 0.4 else "rust"
            )
        else:
            self.health.gauge_direction.set_value("—")
            self.health.gauge_direction.set_meta("NO TRIANGLE DATA")
            self.health.gauge_direction.set_led("sage")

        # ── Scope chip ──
        # Determine the active cell context, if any (mirror of the
        # status-bar chip logic from main_window). Falls back to "—".
        scope_text = "—"
        try:
            mw = self._find_main_window()
            if mw is not None:
                ds = getattr(mw, "get_active_dataset", lambda: None)()
                if ds is not None and hasattr(ds, "plot_page"):
                    grid = ds.plot_page._grid_area
                    cells = grid.cells
                    active_idx = next((i for i, c in enumerate(cells) if c is grid.active_cell), 0)
                    if len(cells) > 1:
                        scope_text = f"CELL {active_idx + 1}/{len(cells)}"
                    else:
                        scope_text = "FULL DATASET"
        except Exception:
            pass
        self.topbar.scope_chip.set_scope(scope_text)

        # ── Head + Gradient panels ──
        self.head_panel.update_from_app(app)
        self.grad_panel.update_from_app(app)
        if self._head_detail_widget is not None:
            try: self._head_detail_widget.update_from_app(app)
            except Exception: pass
        if self._grad_detail_widget is not None:
            try: self._grad_detail_widget.update_from_app(app)
            except Exception: pass

        # ── Triangle Analysis (cached derived data) ──
        derived_key = self._build_derived_cache_key(app, total_triangles)
        cache_hit = (derived_key == self._derived_cache_key) and bool(self._derived_cache)

        t0_derived = time.perf_counter()
        if not cache_hit:
            summary = TriangleDataHelper.compute_summary(
                app.triangle_data, app.rejected_data, total_triangles
            )
            breakdown_primary = TriangleDataHelper.compute_reason_breakdown(
                app.rejected_data, mode="primary"
            )
            breakdown_all = TriangleDataHelper.compute_reason_breakdown(
                app.rejected_data, mode="all"
            )
            freq_df = TriangleDataHelper.compute_point_frequency(
                app.rejected_data, app.gradient_data
            )
            combined_df = TriangleDataHelper.build_combined_triangle_df(
                app.triangle_data, app.rejected_data
            )
            col_mapping = getattr(app, 'col_mapping', {}) or {}
            filtered_data = getattr(app, 'filtered_data', None)
            heatmap_df = TriangleDataHelper.compute_heatmap_data(
                freq_df, filtered_data, col_mapping
            )
            self._derived_cache = {
                "summary": summary,
                "breakdown_primary": breakdown_primary,
                "breakdown_all": breakdown_all,
                "freq_df": freq_df,
                "combined_df": combined_df,
                "filtered_data": filtered_data,
                "col_mapping": col_mapping,
                "heatmap_df": heatmap_df,
            }
            self._derived_cache_key = derived_key
        else:
            summary = self._derived_cache.get("summary", {})
            breakdown_primary = self._derived_cache.get("breakdown_primary", [])
            breakdown_all = self._derived_cache.get("breakdown_all", [])
            freq_df = self._derived_cache.get("freq_df", pd.DataFrame())
            combined_df = self._derived_cache.get("combined_df", pd.DataFrame())
            filtered_data = self._derived_cache.get("filtered_data", None)
            col_mapping = self._derived_cache.get("col_mapping", {})
            heatmap_df = self._derived_cache.get("heatmap_df", pd.DataFrame())
        derived_ms = (time.perf_counter() - t0_derived) * 1000.0
        self._stats_perf_log(
            app,
            f"[perf][stats] cache={'hit' if cache_hit else 'miss'} "
            f"tri={self._safe_len(getattr(app, 'triangle_data', None))} "
            f"rej={self._safe_len(getattr(app, 'rejected_data', None))} "
            f"derive={derived_ms:.1f}ms",
        )

        self.tri_panel.tri_summary.update_data(summary)
        self.tri_panel.tri_breakdown.update_data(breakdown_primary, breakdown_all)
        self.tri_panel.tri_frequency.update_data(freq_df)

        # Update the heavy widgets only when the derived key changed.
        table_ms = 0.0
        if self._bound_table_key != self._derived_cache_key:
            t0_t = time.perf_counter()
            self.tri_panel.tri_table.update_data(combined_df)
            table_ms = (time.perf_counter() - t0_t) * 1000.0
            self._bound_table_key = self._derived_cache_key

        geometry_ms = 0.0
        if self._bound_geometry_key != self._derived_cache_key:
            t0_g = time.perf_counter()
            self.tri_panel.tri_geometry.update_data(
                combined_df, filtered_data, col_mapping, heatmap_df
            )
            geometry_ms = (time.perf_counter() - t0_g) * 1000.0
            self._bound_geometry_key = self._derived_cache_key

        # Triangle panel header meta
        rejected_count = summary.get("rejected", 0)
        self.tri_panel.header.set_meta(
            f"{n_tri:,} valid · "
            f"<b style='color:{FS.RUST};'>{rejected_count:,} rejected</b> · "
            f"click row to inspect"
        )

        has_rejected = app.rejected_data is not None and not app.rejected_data.empty
        has_data = app.triangle_data is not None and not app.triangle_data.empty
        self.tri_panel.export_btn.setEnabled(has_rejected)
        self.tri_panel.open_inspector_btn.setEnabled(has_rejected or has_data)

        total_ms = (time.perf_counter() - t0_total) * 1000.0
        self._stats_perf_log(
            app,
            f"[perf][stats] update total={total_ms:.1f}ms table={table_ms:.1f}ms "
            f"geometry={geometry_ms:.1f}ms cache={'hit' if cache_hit else 'miss'}",
        )

    def clear_statistics(self):
        """Reset every panel back to its empty state."""
        self._derived_cache_key = None
        self._derived_cache = {}
        self._bound_table_key = None
        self._bound_geometry_key = None
        # Health strip
        for g in (self.health.gauge_points, self.health.gauge_triangles,
                  self.health.gauge_rejected, self.health.gauge_head,
                  self.health.gauge_direction):
            g.set_value("—")
            g.set_meta("")
            g.set_spark([])
        # Panels
        self.head_panel.clear()
        self.grad_panel.clear()
        self.tri_panel.clear()
        if self._head_detail_widget is not None:
            try: self._head_detail_widget.clear()
            except Exception: pass
        if self._grad_detail_widget is not None:
            try: self._grad_detail_widget.clear()
            except Exception: pass
        self.topbar.scope_chip.set_scope("—")

    def apply_theme(self):
        """Hook called by theme cycling.

        The Field-Survey design uses a fixed palette (no light/dark
        variant yet) so the previous implementation's
        ``reset_widget_layout(self)`` was actively harmful — it
        ``deleteLater``-ed every child widget while our Python refs
        (``self.health.gauge_points.value_label`` etc.) still pointed at
        the destroyed C++ objects, blowing up the next call to
        ``update_statistics``. We deliberately no-op here until the
        panel grows real theme variants.
        """
        return

    # ──────────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────────

    def _find_main_window(self):
        """Walk parents until we find a widget with ``get_active_dataset``."""
        w = self.parentWidget()
        while w is not None:
            if hasattr(w, "get_active_dataset"):
                return w
            w = w.parentWidget()
        return None
