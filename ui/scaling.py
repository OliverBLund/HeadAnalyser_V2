"""Screen-aware UI sizing helpers for the primary application shell."""

from __future__ import annotations

from dataclasses import dataclass
import re

from PyQt5.QtCore import QSize
from PyQt5.QtWidgets import QApplication, QWidget


_BASE_SCREEN_WIDTH = 1600
_BASE_SCREEN_HEIGHT = 900
_PX_RE = re.compile(r"(?P<value>-?\d+(?:\.\d+)?)px")


def _clamp_int(value: float, low: int, high: int) -> int:
    return max(int(low), min(int(high), int(round(value))))


def _clamp_float(value: float, low: float, high: float) -> float:
    return max(float(low), min(float(high), float(value)))


def _screen_bound(preferred_min: int, preferred_max: int, available: int) -> int:
    upper = max(480, int(available) - 48)
    lower = min(int(preferred_min), upper)
    return max(lower, min(int(preferred_max), upper))


def _screen_for(widget: QWidget | None = None):
    if widget is not None:
        try:
            handle = widget.window().windowHandle() if widget.window() is not None else None
            if handle is not None and handle.screen() is not None:
                return handle.screen()
        except Exception:
            pass
        try:
            screen = widget.screen()
            if screen is not None:
                return screen
        except Exception:
            pass

    app = QApplication.instance()
    if app is None:
        return None
    try:
        return app.primaryScreen()
    except Exception:
        return None


@dataclass(frozen=True)
class ScreenMetrics:
    available_width: int
    available_height: int
    compact: bool
    scale: float
    nav_width: int
    nav_button_width: int
    nav_button_height: int
    header_height: int
    header_button_width: int
    header_button_height: int
    header_icon_size: int
    header_group_height: int
    header_logo_box_size: int
    header_logo_pixmap_size: int
    header_separator_height: int
    toolbar_height: int
    toolbar_button_size: int
    toolbar_control_height: int
    toolbar_pill_height: int
    toolbar_small_button_width: int
    toolbar_small_button_height: int
    drawer_header_height: int
    properties_width: int
    plot_sidebar_width: int
    statusbar_height: int
    status_coords_width: int
    status_separator_height: int
    value_label_width: int
    title_header_height: int
    about_badge_width: int
    min_window_size: QSize
    initial_window_size: QSize


def build_screen_metrics(widget: QWidget | None = None) -> ScreenMetrics:
    screen = _screen_for(widget)
    if screen is None:
        width = _BASE_SCREEN_WIDTH
        height = _BASE_SCREEN_HEIGHT
    else:
        geo = screen.availableGeometry()
        width = int(geo.width())
        height = int(geo.height())

    compact = width < 1440 or height < 840
    scale = 1.0 if compact else _clamp_float(
        min(width / _BASE_SCREEN_WIDTH, height / _BASE_SCREEN_HEIGHT), 1.0, 1.08
    )

    nav_width = 60 if compact else _clamp_int(68 * scale, 68, 76)
    nav_button_width = 48 if compact else _clamp_int(52 * scale, 52, 58)
    nav_button_height = 44 if compact else _clamp_int(48 * scale, 48, 54)

    header_height = 44 if compact else _clamp_int(48 * scale, 48, 56)
    header_button_width = 26 if compact else _clamp_int(28 * scale, 28, 32)
    header_button_height = 24 if compact else _clamp_int(26 * scale, 26, 30)
    header_icon_size = 12 if compact else _clamp_int(13 * scale, 13, 16)
    header_group_height = 26 if compact else _clamp_int(28 * scale, 28, 32)
    header_logo_box_size = 34 if compact else _clamp_int(38 * scale, 38, 44)
    header_logo_pixmap_size = 30 if compact else _clamp_int(34 * scale, 34, 40)
    header_separator_height = 18 if compact else _clamp_int(20 * scale, 20, 24)

    toolbar_height = 42 if compact else _clamp_int(46 * scale, 46, 52)
    toolbar_button_size = 30 if compact else _clamp_int(32 * scale, 32, 36)
    toolbar_control_height = 30 if compact else _clamp_int(32 * scale, 32, 36)
    toolbar_pill_height = 24 if compact else _clamp_int(26 * scale, 26, 30)
    toolbar_small_button_width = 26 if compact else _clamp_int(28 * scale, 28, 32)
    toolbar_small_button_height = 24 if compact else _clamp_int(26 * scale, 26, 30)
    drawer_header_height = 30 if compact else _clamp_int(32 * scale, 32, 36)

    properties_width = _clamp_int(width * 0.22, 260 if compact else 280, 340)
    plot_sidebar_width = _clamp_int(width * 0.24, 260 if compact else 280, 360)

    statusbar_height = 28 if compact else _clamp_int(32 * scale, 32, 36)
    status_coords_width = 120 if compact else _clamp_int(140 * scale, 140, 180)
    status_separator_height = 12 if compact else _clamp_int(14 * scale, 14, 18)

    value_label_width = 92 if compact else _clamp_int(100 * scale, 100, 128)
    title_header_height = 48 if compact else _clamp_int(52 * scale, 52, 60)
    about_badge_width = 64 if compact else _clamp_int(70 * scale, 70, 86)

    min_window_width = _screen_bound(960, 1180, width)
    min_window_height = _screen_bound(640, 760, height)
    initial_window_width = max(min_window_width, min(1500, int(round(width * 0.92))))
    initial_window_height = max(min_window_height, min(940, int(round(height * 0.92))))

    return ScreenMetrics(
        available_width=width,
        available_height=height,
        compact=compact,
        scale=scale,
        nav_width=nav_width,
        nav_button_width=nav_button_width,
        nav_button_height=nav_button_height,
        header_height=header_height,
        header_button_width=header_button_width,
        header_button_height=header_button_height,
        header_icon_size=header_icon_size,
        header_group_height=header_group_height,
        header_logo_box_size=header_logo_box_size,
        header_logo_pixmap_size=header_logo_pixmap_size,
        header_separator_height=header_separator_height,
        toolbar_height=toolbar_height,
        toolbar_button_size=toolbar_button_size,
        toolbar_control_height=toolbar_control_height,
        toolbar_pill_height=toolbar_pill_height,
        toolbar_small_button_width=toolbar_small_button_width,
        toolbar_small_button_height=toolbar_small_button_height,
        drawer_header_height=drawer_header_height,
        properties_width=properties_width,
        plot_sidebar_width=plot_sidebar_width,
        statusbar_height=statusbar_height,
        status_coords_width=status_coords_width,
        status_separator_height=status_separator_height,
        value_label_width=value_label_width,
        title_header_height=title_header_height,
        about_badge_width=about_badge_width,
        min_window_size=QSize(min_window_width, min_window_height),
        initial_window_size=QSize(initial_window_width, initial_window_height),
    )


def scale_qss(css: str, factor: float) -> str:
    if not css or abs(float(factor) - 1.0) < 0.001:
        return css

    def _replace(match: re.Match[str]) -> str:
        raw_value = float(match.group("value"))
        if raw_value == 0 or abs(raw_value) < 2.0:
            return match.group(0)

        scaled = raw_value * factor
        if abs(scaled - round(scaled)) < 0.01:
            value_text = str(int(round(scaled)))
        else:
            value_text = f"{scaled:.2f}".rstrip("0").rstrip(".")
        return f"{value_text}px"

    return _PX_RE.sub(_replace, css)
