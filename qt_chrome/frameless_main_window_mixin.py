"""Reusable PyQt5 frameless-window mixin for QMainWindow-based apps.

Usage:
    class MainWindow(FramelessMainWindowMixin, QMainWindow):
        def __init__(self):
            super().__init__()
            self.init_frameless_window_chrome()
            ...
"""

from __future__ import annotations

from typing import Optional

from PyQt5.QtCore import QEvent, QRect
from PyQt5.QtWidgets import QApplication

from .mask import apply_frameless_round_mask
from .mode import resolve_window_chrome_mode
from .platform import enable_windows_frameless_snap_styles, enable_windows_soft_corners
from .window_helper import FramelessWindowChromeHelper


class FramelessMainWindowMixin:
    """Drop-in frameless chrome behavior for PyQt5 QMainWindow classes."""

    def init_frameless_window_chrome(
        self,
        *,
        default_windows: str = "frameless",
        default_other: str = "native",
        resize_margin: int = 8,
        top_resize_margin: int = 6,
        corner_radius_px: int = 10,
        taskbar_gap_px: int = 0,
        maximize_inset_px: int = 0,
        enable_edge_resize: bool = True,
    ) -> None:
        """Initialize chrome state and apply initial mode."""
        self._window_chrome_mode = "native"
        self._frameless_is_maximized = False
        self._frameless_restore_geometry = None
        self._frameless_saved_minimum_size = None

        self._frameless_taskbar_gap_px = int(taskbar_gap_px)
        self._frameless_maximize_inset_px = int(maximize_inset_px)
        self._frameless_corner_radius_px = int(corner_radius_px)

        self._chrome_default_windows = default_windows
        self._chrome_default_other = default_other
        self._chrome_resize_margin = int(resize_margin)
        self._chrome_top_resize_margin = int(top_resize_margin)
        self._chrome_enable_edge_resize = bool(enable_edge_resize)
        self._chrome_enable_windows_snap_styles = True

        self.window_chrome = None
        self._init_window_chrome()

    def _is_frameless_mode(self) -> bool:
        return getattr(self, "_window_chrome_mode", "native") == "frameless"

    def is_window_effectively_maximized(self) -> bool:
        return bool(self.isMaximized() or getattr(self, "_frameless_is_maximized", False))

    def _apply_frameless_round_mask(self) -> None:
        apply_frameless_round_mask(
            self,
            enabled=self._is_frameless_mode(),
            is_effectively_maximized=self.is_window_effectively_maximized(),
            corner_radius_px=max(2, int(getattr(self, "_frameless_corner_radius_px", 10))),
        )

    def _current_window_screen(self):
        handle = self.windowHandle()
        if handle and handle.screen():
            return handle.screen()
        if hasattr(self, "screen"):
            screen = self.screen()
            if screen:
                return screen
        return QApplication.primaryScreen()

    def _frameless_maximized_geometry(self) -> Optional[QRect]:
        screen = self._current_window_screen()
        if not screen:
            return None

        available = QRect(screen.availableGeometry())
        target = QRect(available)
        if not target.isValid():
            return None

        inset = max(0, int(getattr(self, "_frameless_maximize_inset_px", 0)))
        if inset > 0 and target.width() > (2 * inset + 220) and target.height() > (2 * inset + 180):
            target.adjust(inset, inset, -inset, -inset)

        gap = max(0, int(getattr(self, "_frameless_taskbar_gap_px", 0)))
        if gap > 0 and target.height() > gap + max(140, self.minimumHeight()):
            target.adjust(0, 0, 0, -gap)

        if target.bottom() > available.bottom():
            target.moveBottom(available.bottom())
        if target.top() < available.top():
            target.moveTop(available.top())
        if target.left() < available.left():
            target.moveLeft(available.left())
        if target.right() > available.right():
            target.moveRight(available.right())

        return target

    def _set_frameless_maximized(self) -> None:
        if self._frameless_is_maximized:
            target = self._frameless_maximized_geometry()
            if target and self.geometry() != target:
                self.setGeometry(target)
            self._sync_window_controls()
            return

        current = self.normalGeometry() if self.isMaximized() else self.geometry()
        if not current.isValid():
            current = self.geometry()
        if current.isValid():
            self._frameless_restore_geometry = QRect(current)

        target = self._frameless_maximized_geometry()
        if target and target.isValid():
            if self._frameless_saved_minimum_size is None:
                self._frameless_saved_minimum_size = self.minimumSize()

            required_w = max(self.minimumWidth(), self.minimumSizeHint().width())
            required_h = max(self.minimumHeight(), self.minimumSizeHint().height())
            if required_w > target.width() or required_h > target.height():
                self.setMinimumSize(
                    min(max(320, self.minimumWidth()), target.width()),
                    min(max(240, self.minimumHeight()), target.height()),
                )

            super().showNormal()
            self.setGeometry(target)
            self._frameless_is_maximized = True
            self.setProperty("_frameless_maximized", True)
            self._apply_frameless_round_mask()
            self._sync_window_controls()
            return

        super().showMaximized()
        self._apply_frameless_round_mask()
        self._sync_window_controls()

    def _restore_from_frameless_maximized(self) -> None:
        if not self._frameless_is_maximized:
            return

        restore = self._frameless_restore_geometry
        self._frameless_is_maximized = False
        self.setProperty("_frameless_maximized", False)

        if self._frameless_saved_minimum_size is not None:
            try:
                self.setMinimumSize(self._frameless_saved_minimum_size)
            except Exception:
                pass
            self._frameless_saved_minimum_size = None

        if restore and restore.isValid():
            super().showNormal()
            self.setGeometry(restore)
        else:
            super().showNormal()

        self._apply_frameless_round_mask()
        self._sync_window_controls()

    def showMaximized(self):
        if self._is_frameless_mode():
            self._set_frameless_maximized()
            return
        self._frameless_is_maximized = False
        self.setProperty("_frameless_maximized", False)
        super().showMaximized()
        self._apply_frameless_round_mask()
        self._sync_window_controls()

    def showNormal(self):
        if self._is_frameless_mode() and self._frameless_is_maximized:
            self._restore_from_frameless_maximized()
            return
        self._frameless_is_maximized = False
        self.setProperty("_frameless_maximized", False)
        super().showNormal()
        self._apply_frameless_round_mask()
        self._sync_window_controls()

    def toggle_window_maximize(self) -> None:
        if self.isFullScreen():
            super().showNormal()
            if self._is_frameless_mode():
                self._set_frameless_maximized()
            else:
                super().showMaximized()
            self._apply_frameless_round_mask()
            self._sync_window_controls()
            return

        if self._is_frameless_mode():
            if self.is_window_effectively_maximized():
                if self._frameless_is_maximized:
                    self._restore_from_frameless_maximized()
                else:
                    super().showNormal()
                    self._frameless_is_maximized = False
                    self.setProperty("_frameless_maximized", False)
            else:
                self._set_frameless_maximized()
            self._sync_window_controls()
            return

        if self.isMaximized():
            super().showNormal()
        else:
            super().showMaximized()
        self._apply_frameless_round_mask()
        self._sync_window_controls()

    def _sync_window_controls(self) -> None:
        """Sync common custom titlebars/ribbons and optional app hook."""
        is_frameless = self._is_frameless_mode()
        is_maximized = self.is_window_effectively_maximized()

        for attr_name in ("ribbon_toolbar", "html_toolbar"):
            toolbar = getattr(self, attr_name, None)
            if toolbar is None:
                continue
            if hasattr(toolbar, "set_frameless_mode"):
                toolbar.set_frameless_mode(is_frameless)
            if hasattr(toolbar, "set_maximized_state"):
                toolbar.set_maximized_state(is_maximized)
            title_bar = getattr(toolbar, "title_bar", None)
            if title_bar is not None and hasattr(title_bar, "set_maximized_state"):
                title_bar.set_maximized_state(is_maximized)

        hook = getattr(self, "on_window_chrome_state_changed", None)
        if callable(hook):
            try:
                hook(is_frameless, is_maximized)
            except Exception:
                pass

    def _init_window_chrome(self) -> None:
        """Apply frameless/native flags with safe fallback."""
        from PyQt5.QtCore import Qt

        self.window_chrome = None
        chrome_mode = resolve_window_chrome_mode(
            default_windows=getattr(self, "_chrome_default_windows", "frameless"),
            default_other=getattr(self, "_chrome_default_other", "native"),
        )
        self._window_chrome_mode = chrome_mode

        if chrome_mode == "frameless":
            try:
                self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
                self.setAttribute(Qt.WA_TranslucentBackground, False)

                enable_edge_resize = bool(getattr(self, "_chrome_enable_edge_resize", True))
                self.setMouseTracking(enable_edge_resize)
                if enable_edge_resize:
                    self.window_chrome = FramelessWindowChromeHelper(
                        self,
                        margin=max(2, int(getattr(self, "_chrome_resize_margin", 8))),
                        top_margin=max(2, int(getattr(self, "_chrome_top_resize_margin", 6))),
                        is_effectively_maximized=self.is_window_effectively_maximized,
                    )
                else:
                    self.window_chrome = None
                return
            except Exception:
                self.window_chrome = None
                self._window_chrome_mode = "native"

        self.setWindowFlags(Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setMouseTracking(False)

    def _enable_windows_soft_corners(self) -> None:
        enable_windows_soft_corners(self)

    def _enable_windows_snap_styles(self) -> None:
        enable_windows_frameless_snap_styles(self)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_frameless_round_mask()

    def showEvent(self, event):
        super().showEvent(event)
        if not getattr(self, "_first_show_done", False):
            self._first_show_done = True
            from PyQt5.QtCore import QTimer

            QTimer.singleShot(0, self._post_first_show)
        else:
            self._apply_frameless_round_mask()

    def _post_first_show(self) -> None:
        self._apply_frameless_round_mask()
        if (
            self._is_frameless_mode()
            and getattr(self, "_chrome_enable_windows_snap_styles", True)
            and not getattr(self, "_windows_snap_styles_applied", False)
        ):
            self._enable_windows_snap_styles()
            self._windows_snap_styles_applied = True
        if not getattr(self, "_soft_corners_applied", False):
            self._enable_windows_soft_corners()
            self._soft_corners_applied = True

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.WindowStateChange:
            if self._is_frameless_mode() and self.isMaximized() and not self._frameless_is_maximized:
                from PyQt5.QtCore import QTimer

                QTimer.singleShot(0, self._set_frameless_maximized)
            self._apply_frameless_round_mask()
            self._sync_window_controls()
