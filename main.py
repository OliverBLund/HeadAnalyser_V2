"""
HeadAnalyser V2 - Hydraulic Gradient Analysis Tool
Main Application Entry Point
"""

import sys
import os
from pathlib import Path

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt, QSettings
from PyQt5.QtGui import QFont, QIcon, QPixmap, QPainter, QImage

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from ui.main_window import MainWindow
from styles.colors import Colors
from styles.stylesheet import StyleSheet
from styles.theme import build_qpalette
from core.runtime_cprofile import install_runtime_cprofile


def _resource_path(*parts: str) -> str:
    """Resolve resource path in both dev and PyInstaller bundle."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS)  # type: ignore[attr-defined]
    else:
        base = Path(__file__).resolve().parent
    return str(base.joinpath(*parts))


def _set_windows_app_id(app_id: str) -> None:
    """Set explicit AppUserModelID so taskbar icon/grouping is reliable on Windows."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except Exception:
        pass


def _resolve_app_icon() -> QIcon:
    """Find best available app icon."""
    icon_candidates = [
        _resource_path("assets", "headanalyser.ico"),
        _resource_path("assets", "app.ico"),
        _resource_path("assets", "logo_newest.png"),
        _resource_path("assets", "headanalyser_logo.svg"),
    ]
    for icon_path in icon_candidates:
        if not os.path.exists(icon_path):
            continue
        icon = QIcon(icon_path)
        if not icon.isNull():
            return _boost_icon_visual_size(icon)
    return QIcon()


def _trim_transparent_margins(pixmap: QPixmap) -> QPixmap:
    """Crop transparent margins so icon content can fill more of the target canvas."""
    if pixmap.isNull():
        return pixmap

    img = pixmap.toImage().convertToFormat(QImage.Format_ARGB32)
    width = img.width()
    height = img.height()
    left, top = width, height
    right, bottom = -1, -1

    for y in range(height):
        for x in range(width):
            if img.pixelColor(x, y).alpha() > 8:
                if x < left:
                    left = x
                if y < top:
                    top = y
                if x > right:
                    right = x
                if y > bottom:
                    bottom = y

    if right < left or bottom < top:
        return pixmap

    return pixmap.copy(left, top, right - left + 1, bottom - top + 1)


def _boost_icon_visual_size(icon: QIcon) -> QIcon:
    """Build a dense square icon variant so taskbar glyph appears much larger."""
    if icon.isNull():
        return icon

    boosted = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        base = icon.pixmap(size * 4, size * 4)
        if base.isNull():
            continue

        base = _trim_transparent_margins(base)
        if base.width() > int(base.height() * 1.2):
            # Wide logos look tiny in taskbar slots; use the upper center emblem region.
            side = min(base.width(), base.height())
            x = max(0, (base.width() - side) // 2)
            y = max(0, (base.height() - side) // 2)
            base = base.copy(x, y, side, side)

        target = QPixmap(size, size)
        target.fill(Qt.transparent)
        painter = QPainter(target)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

        # Keep a small margin so Windows taskbar does not visually clip the icon.
        scaled = base.scaled(
            int(round(size * 0.84)),
            int(round(size * 0.84)),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        x = (size - scaled.width()) // 2
        y = (size - scaled.height()) // 2
        painter.drawPixmap(x, y, scaled)
        painter.end()

        boosted.addPixmap(target)

    return boosted if not boosted.isNull() else icon


def main():
    # Enable high DPI scaling
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("HeadAnalyser")
    app.setApplicationVersion("2.0.0")
    app.setOrganizationName("DTU")
    _set_windows_app_id("DTU.HeadAnalyser.V2")

    settings = QSettings("DTU", "HeadAnalyser")
    Colors.apply_theme(settings.value("ui_theme", Colors.current_theme(), type=str))
    app.setPalette(build_qpalette())

    app_icon = _resolve_app_icon()
    if not app_icon.isNull():
        app.setWindowIcon(app_icon)

    # Set default font
    font = QFont("Segoe UI", 10)
    app.setFont(font)

    # Apply centralized stylesheet with clear panel boundaries
    app.setStyleSheet(StyleSheet.get_main_stylesheet())

    # Optional runtime cProfile hooks (env-gated).
    install_runtime_cprofile()

    # Create and show main window
    window = MainWindow()
    if not app_icon.isNull():
        window.setWindowIcon(app_icon)
    window.showMaximized()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
