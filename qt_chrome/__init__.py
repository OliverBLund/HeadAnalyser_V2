"""Reusable frameless window helpers for PyQt5/QGIS apps."""

from .frameless_main_window_mixin import FramelessMainWindowMixin
from .frameless_dialog_mixin import FramelessDialogMixin
from .mask import apply_frameless_round_mask
from .mode import resolve_window_chrome_mode
from .platform import enable_windows_soft_corners
from .window_helper import FramelessWindowChromeHelper

__all__ = [
    "FramelessMainWindowMixin",
    "FramelessDialogMixin",
    "FramelessWindowChromeHelper",
    "apply_frameless_round_mask",
    "enable_windows_soft_corners",
    "resolve_window_chrome_mode",
]
