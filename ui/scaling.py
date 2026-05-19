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
    density: str
    compact: bool
    scale: float
    font_xs: int
    font_sm: int
    font_base: int
    font_md: int
    font_lg: int
    font_xl: int
    font_title: int
    font_display: int
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

    size_ratio = min(width / _BASE_SCREEN_WIDTH, height / _BASE_SCREEN_HEIGHT)
    compact = width < 1440 or height < 840
    density = "dense" if width < 1280 or height < 760 else ("compact" if compact else "regular")

    # Shared UI scale used for QSS px values. Unlike the previous logic, this
    # also scales smaller screens down instead of freezing them at desktop size.
    scale = _clamp_float(size_ratio, 0.90, 1.06)
    text_scale = _clamp_float(size_ratio, 0.92, 1.03)
    chrome_scale = _clamp_float(size_ratio, 0.88, 1.04)

    font_xs = _clamp_int(8.5 * text_scale, 8, 9)
    font_sm = _clamp_int(9.5 * text_scale, 9, 10)
    font_base = _clamp_int(10.5 * text_scale, 10, 11)
    font_md = _clamp_int(11.25 * text_scale, 10, 12)
    font_lg = _clamp_int(12.0 * text_scale, 11, 13)
    font_xl = _clamp_int(13.0 * text_scale, 11, 14)
    font_title = _clamp_int(15.0 * text_scale, 13, 16)
    font_display = _clamp_int(18.0 * text_scale, 15, 18)

    nav_width = _clamp_int(64 * chrome_scale, 56, 72)
    nav_button_width = _clamp_int(50 * chrome_scale, 44, 56)
    nav_button_height = _clamp_int(46 * chrome_scale, 40, 52)

    header_height = _clamp_int(46 * chrome_scale, 40, 52)
    header_button_width = _clamp_int(27 * chrome_scale, 24, 31)
    header_button_height = _clamp_int(25 * chrome_scale, 22, 29)
    header_icon_size = _clamp_int(12.5 * chrome_scale, 11, 15)
    header_group_height = _clamp_int(27 * chrome_scale, 24, 31)
    header_logo_box_size = _clamp_int(36 * chrome_scale, 30, 42)
    header_logo_pixmap_size = _clamp_int(32 * chrome_scale, 27, 38)
    header_separator_height = _clamp_int(19 * chrome_scale, 15, 23)

    toolbar_height = _clamp_int(44 * chrome_scale, 38, 50)
    toolbar_button_size = _clamp_int(31 * chrome_scale, 26, 35)
    toolbar_control_height = _clamp_int(31 * chrome_scale, 26, 35)
    toolbar_pill_height = _clamp_int(25 * chrome_scale, 21, 29)
    toolbar_small_button_width = _clamp_int(27 * chrome_scale, 23, 31)
    toolbar_small_button_height = _clamp_int(25 * chrome_scale, 21, 29)
    drawer_header_height = _clamp_int(31 * chrome_scale, 26, 35)

    properties_width = _clamp_int(width * 0.22, 250, 340)
    plot_sidebar_width = _clamp_int(width * 0.24, 248, 360)

    statusbar_height = _clamp_int(30 * chrome_scale, 24, 34)
    status_coords_width = _clamp_int(128 * chrome_scale, 112, 176)
    status_separator_height = _clamp_int(13 * chrome_scale, 10, 17)

    value_label_width = _clamp_int(96 * chrome_scale, 84, 124)
    title_header_height = _clamp_int(44 * chrome_scale, 42, 52)
    about_badge_width = _clamp_int(68 * chrome_scale, 58, 84)

    min_window_width = _screen_bound(960, 1180, width)
    min_window_height = _screen_bound(640, 760, height)
    initial_window_width = max(min_window_width, min(1500, int(round(width * 0.92))))
    initial_window_height = max(min_window_height, min(940, int(round(height * 0.92))))

    return ScreenMetrics(
        available_width=width,
        available_height=height,
        density=density,
        compact=compact,
        scale=scale,
        font_xs=font_xs,
        font_sm=font_sm,
        font_base=font_base,
        font_md=font_md,
        font_lg=font_lg,
        font_xl=font_xl,
        font_title=font_title,
        font_display=font_display,
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
