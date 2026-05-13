"""Reusable PyQt5 frameless-window mixin for QDialog-based apps."""

from __future__ import annotations

from typing import Optional

from PyQt5.QtCore import QEvent, QObject, QPoint, Qt
from PyQt5.QtWidgets import (
    QAbstractButton,
    QAbstractItemView,
    QAbstractSlider,
    QAbstractSpinBox,
    QComboBox,
    QLineEdit,
    QPlainTextEdit,
    QTextEdit,
    QWidget,
)

try:
    from PyQt5.QtWebEngineWidgets import QWebEngineView
except Exception:  # pragma: no cover - optional module in some environments
    QWebEngineView = None

from .mask import apply_frameless_round_mask
from .mode import resolve_window_chrome_mode
from .platform import enable_windows_soft_corners
from .window_helper import FramelessWindowChromeHelper


class _FramelessDragWidgetFilter(QObject):
    """Adds click-drag move behavior to a custom dialog header widget."""

    def __init__(
        self,
        dialog: "FramelessDialogMixin",
        widget: QWidget,
        *,
        allow_double_click_maximize: bool,
    ):
        super().__init__(widget)
        self._dialog = dialog
        self._widget = widget
        self._allow_double_click_maximize = bool(allow_double_click_maximize)
        self._manual_drag_active = True
        self._manual_drag_offset: Optional[QPoint] = None

    @staticmethod
    def _event_global_pos(event) -> QPoint:
        if hasattr(event, "globalPosition"):
            return event.globalPosition().toPoint()
        if hasattr(event, "globalPos"):
            return event.globalPos()
        return QPoint()

    @staticmethod
    def _event_local_pos(event) -> QPoint:
        if hasattr(event, "position"):
            return event.position().toPoint()
        if hasattr(event, "pos"):
            return event.pos()
        return QPoint()

    def _is_drag_region(self, local_pos: QPoint) -> bool:
        interactive_types = (
            QAbstractButton,
            QAbstractItemView,
            QAbstractSlider,
            QAbstractSpinBox,
            QComboBox,
            QLineEdit,
            QTextEdit,
            QPlainTextEdit,
        )
        if QWebEngineView is not None:
            interactive_types = interactive_types + (QWebEngineView,)
        child = self._widget.childAt(local_pos)
        while child is not None and child is not self._widget:
            if isinstance(child, interactive_types):
                return False
            child = child.parentWidget()
        return True

    def _is_in_resize_margin(self, local_pos: QPoint) -> bool:
        global_pos = self._widget.mapToGlobal(local_pos)
        win_pos = self._dialog.mapFromGlobal(global_pos)
        rect = self._dialog.rect()

        margin = max(2, int(getattr(self._dialog, "_dialog_resize_margin", 8)))
        top_margin = max(2, int(getattr(self._dialog, "_dialog_top_resize_margin", margin)))
        return (
            win_pos.x() <= margin
            or win_pos.x() >= rect.width() - margin
            or win_pos.y() <= top_margin
            or win_pos.y() >= rect.height() - margin
        )

    def _start_system_move(self) -> bool:
        handle = self._dialog.windowHandle()
        if handle is None:
            return False
        try:
            return bool(handle.startSystemMove())
        except Exception:
            return False

    def eventFilter(self, watched, event):
        if watched is not self._widget:
            return False
        if not self._dialog._is_frameless_mode():
            return False

        etype = event.type()
        if etype == QEvent.MouseButtonPress:
            if event.button() != Qt.LeftButton:
                return False
            local_pos = self._event_local_pos(event)
            if self._is_in_resize_margin(local_pos) or not self._is_drag_region(local_pos):
                return False
            if self._start_system_move():
                event.accept()
                return True
            if self._dialog.isMaximized() or self._dialog.isFullScreen():
                return False
            self._manual_drag_active = True
            self._manual_drag_offset = self._event_global_pos(event) - self._dialog.pos()
            event.accept()
            return True

        if etype == QEvent.MouseMove:
            if not self._manual_drag_active:
                return False
            if not (event.buttons() & Qt.LeftButton):
                self._manual_drag_active = False
                self._manual_drag_offset = None
                return False
            if self._manual_drag_offset is None:
                return False
            self._dialog.move(self._event_global_pos(event) - self._manual_drag_offset)
            event.accept()
            return True

        if etype == QEvent.MouseButtonRelease:
            if event.button() != Qt.LeftButton:
                return False
            if not self._manual_drag_active:
                return False
            self._manual_drag_active = False
            self._manual_drag_offset = None
            event.accept()
            return True

        if etype == QEvent.MouseButtonDblClick and self._allow_double_click_maximize:
            if event.button() != Qt.LeftButton:
                return False
            local_pos = self._event_local_pos(event)
            if self._is_in_resize_margin(local_pos) or not self._is_drag_region(local_pos):
                return False
            if self._dialog.isMaximized():
                self._dialog.showNormal()
            else:
                self._dialog.showMaximized()
            event.accept()
            return True

        return False


class FramelessDialogMixin:
    """Drop-in frameless chrome behavior for PyQt5 QDialog classes."""

    def init_frameless_dialog_chrome(
        self,
        *,
        default_windows: str = "frameless",
        default_other: str = "native",
        enable_edge_resize: bool = False,
        resize_margin: int = 8,
        top_resize_margin: int = 6,
        corner_radius_px: int = 10,
    ) -> None:
        self._dialog_chrome_mode = "native"
        self._dialog_window_chrome = None
        self._dialog_drag_filters = []
        self._dialog_enable_edge_resize = bool(enable_edge_resize)
        self._dialog_resize_margin = int(resize_margin)
        self._dialog_top_resize_margin = int(top_resize_margin)
        self._dialog_corner_radius_px = int(corner_radius_px)
        self._dialog_default_windows = default_windows
        self._dialog_default_other = default_other
        self._init_dialog_chrome()
        self._notify_dialog_chrome_state()

    def bind_frameless_drag_widget(
        self,
        widget: Optional[QWidget],
        *,
        allow_double_click_maximize: bool = False,
        include_children: Optional[bool] = None,
    ) -> None:
        if widget is None:
            return
        if include_children is None:
            # Performance default:
            # - Binding on the full dialog should not recurse through every child.
            # - Binding on a dedicated header should recurse for better drag UX.
            include_children = widget is not self

        interactive_types = (
            QAbstractButton,
            QAbstractItemView,
            QAbstractSlider,
            QAbstractSpinBox,
            QComboBox,
            QLineEdit,
            QTextEdit,
            QPlainTextEdit,
        )
        if QWebEngineView is not None:
            interactive_types = interactive_types + (QWebEngineView,)

        def _under_interactive_parent(target: QWidget) -> bool:
            current = target
            while current is not None and current is not widget:
                if isinstance(current, interactive_types):
                    return True
                current = current.parentWidget()
            return isinstance(widget, interactive_types)

        targets = [widget]
        if include_children:
            targets.extend(widget.findChildren(QWidget))
        for target in targets:
            if _under_interactive_parent(target):
                continue
            drag_filter = _FramelessDragWidgetFilter(
                self,
                target,
                allow_double_click_maximize=allow_double_click_maximize,
            )
            target.installEventFilter(drag_filter)
            self._dialog_drag_filters.append(drag_filter)

    def _is_frameless_mode(self) -> bool:
        return getattr(self, "_dialog_chrome_mode", "native") == "frameless"

    def _apply_frameless_round_mask(self) -> None:
        apply_frameless_round_mask(
            self,
            enabled=self._is_frameless_mode(),
            is_effectively_maximized=bool(self.isMaximized()),
            corner_radius_px=max(2, int(getattr(self, "_dialog_corner_radius_px", 10))),
        )

    def _notify_dialog_chrome_state(self) -> None:
        hook = getattr(self, "on_dialog_chrome_state_changed", None)
        if callable(hook):
            try:
                hook(self._is_frameless_mode(), bool(self.isMaximized()))
            except Exception:
                pass

    def _release_dialog_window_chrome(self) -> None:
        helper = getattr(self, "_dialog_window_chrome", None)
        if helper is None:
            return
        try:
            cleanup = getattr(helper, "_cleanup", None)
            if callable(cleanup):
                cleanup()
        except Exception:
            pass
        try:
            helper.deleteLater()
        except Exception:
            pass
        self._dialog_window_chrome = None

    def _ensure_dialog_window_chrome(self) -> None:
        if not self._is_frameless_mode():
            self._release_dialog_window_chrome()
            return
        if not bool(getattr(self, "_dialog_enable_edge_resize", False)):
            self._release_dialog_window_chrome()
            return
        if getattr(self, "_dialog_window_chrome", None) is not None:
            return
        self._dialog_window_chrome = FramelessWindowChromeHelper(
            self,
            margin=max(2, int(getattr(self, "_dialog_resize_margin", 8))),
            top_margin=max(2, int(getattr(self, "_dialog_top_resize_margin", 6))),
            is_effectively_maximized=lambda: bool(self.isMaximized()),
        )

    def _init_dialog_chrome(self) -> None:
        from PyQt5.QtCore import Qt

        self._release_dialog_window_chrome()
        chrome_mode = resolve_window_chrome_mode(
            default_windows=getattr(self, "_dialog_default_windows", "frameless"),
            default_other=getattr(self, "_dialog_default_other", "native"),
        )
        self._dialog_chrome_mode = chrome_mode

        if chrome_mode == "frameless":
            try:
                flags = self.windowFlags() | Qt.FramelessWindowHint
                flags &= ~Qt.WindowTitleHint
                self.setWindowFlags(flags)
                self.setAttribute(Qt.WA_TranslucentBackground, False)
                self.setMouseTracking(bool(getattr(self, "_dialog_enable_edge_resize", False)))
                self._ensure_dialog_window_chrome()
                enable_windows_soft_corners(self)
                return
            except Exception:
                self._dialog_window_chrome = None
                self._dialog_chrome_mode = "native"

        flags = self.windowFlags()
        flags &= ~Qt.FramelessWindowHint
        flags |= Qt.WindowTitleHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setMouseTracking(False)
        enable_windows_soft_corners(self)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_frameless_round_mask()

    def showEvent(self, event):
        super().showEvent(event)
        self._ensure_dialog_window_chrome()
        self._apply_frameless_round_mask()
        self._notify_dialog_chrome_state()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.WindowStateChange:
            self._apply_frameless_round_mask()
            self._notify_dialog_chrome_state()

    def hideEvent(self, event):
        super().hideEvent(event)
        # QDialog.accept()/reject() hides the dialog without guaranteed destruction.
        # Release app-level frameless helpers immediately to avoid lingering global filters.
        self._release_dialog_window_chrome()

    def closeEvent(self, event):
        super().closeEvent(event)
        self._release_dialog_window_chrome()
