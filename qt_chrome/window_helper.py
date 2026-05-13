"""Frameless edge-resize controller for PyQt5 windows."""

from __future__ import annotations

from typing import Callable, Optional

from PyQt5.QtCore import QEvent, QObject, QPoint, QRect, Qt
from PyQt5.QtGui import QCursor
from PyQt5.QtWidgets import QApplication, QWidget


class FramelessWindowChromeHelper(QObject):
    """Provides edge-resize behavior and resize cursors for frameless windows."""

    def __init__(
        self,
        window: QWidget,
        margin: int = 8,
        top_margin: int = 6,
        is_effectively_maximized: Optional[Callable[[], bool]] = None,
    ):
        super().__init__(window)
        self.window = window
        self.margin = margin
        self.top_margin = top_margin
        self._is_effectively_maximized_cb = is_effectively_maximized
        self._resize_edges: set[str] = set()
        self._press_pos: Optional[QPoint] = None
        self._press_geom: Optional[QRect] = None
        self._cursor_shape = None

        app = QApplication.instance()
        self._installed_app = app
        if self._installed_app:
            self._installed_app.installEventFilter(self)
        window.destroyed.connect(self._cleanup)

    def _cleanup(self):
        if self._installed_app:
            self._installed_app.removeEventFilter(self)
            self._installed_app = None

    def _is_window_effectively_maximized(self) -> bool:
        if callable(self._is_effectively_maximized_cb):
            try:
                return bool(self._is_effectively_maximized_cb())
            except Exception:
                pass
        return bool(
            self.window.isMaximized()
            or getattr(self.window, "_frameless_is_maximized", False)
        )

    @staticmethod
    def _event_global_pos(event) -> QPoint:
        if hasattr(event, "globalPosition"):
            return event.globalPosition().toPoint()
        if hasattr(event, "globalPos"):
            return event.globalPos()
        return QPoint()

    def eventFilter(self, watched, event):
        if not isinstance(watched, QWidget):
            return False
        if watched.window() is not self.window or not self.window.isVisible():
            return False

        etype = event.type()
        if etype not in (
            QEvent.MouseButtonPress,
            QEvent.MouseMove,
            QEvent.MouseButtonRelease,
            QEvent.HoverMove,
            QEvent.Enter,
            QEvent.Leave,
            QEvent.WindowDeactivate,
        ):
            return False

        if etype == QEvent.MouseButtonPress:
            return self._handle_mouse_press(event)
        if etype == QEvent.MouseMove:
            if self._handle_mouse_move(event):
                return True
            self._update_cursor(self._event_global_pos(event))
            return False
        if etype == QEvent.HoverMove:
            self._update_cursor(QCursor.pos())
            return False
        if etype == QEvent.Enter:
            self._update_cursor(QCursor.pos())
            return False
        if etype == QEvent.MouseButtonRelease:
            return self._handle_mouse_release(event)
        if etype in (QEvent.Leave, QEvent.WindowDeactivate):
            self._maybe_reset_cursor()
        return False

    def _handle_mouse_press(self, event):
        if event.button() != Qt.LeftButton or self.window.isMinimized():
            return False

        global_pos = self._event_global_pos(event)
        local_pos = self.window.mapFromGlobal(global_pos)
        edges = self._edges_at(local_pos)
        if not edges:
            return False

        if self._start_system_resize(edges):
            event.accept()
            return True

        if self._is_window_effectively_maximized() or self.window.isFullScreen():
            self.window.showNormal()
            self._maybe_reset_cursor()
            event.accept()
            return True

        self._resize_edges = edges
        self._press_pos = global_pos
        self._press_geom = self.window.geometry()
        event.accept()
        return True

    def _handle_mouse_move(self, event):
        if not self._resize_edges:
            return False
        self._apply_resize(self._event_global_pos(event))
        event.accept()
        return True

    def _handle_mouse_release(self, event):
        if event.button() != Qt.LeftButton:
            return False
        if not self._resize_edges:
            return False
        self._resize_edges.clear()
        self._press_pos = None
        self._press_geom = None
        self._refresh_cursor()
        event.accept()
        return True

    def _apply_resize(self, global_pos: QPoint):
        if (
            not self._press_geom
            or not self._press_pos
            or self._is_window_effectively_maximized()
            or self.window.isFullScreen()
        ):
            return

        delta = global_pos - self._press_pos
        geom = QRect(self._press_geom)
        x, y, w, h = geom.x(), geom.y(), geom.width(), geom.height()
        min_w = max(200, self.window.minimumWidth())
        min_h = max(140, self.window.minimumHeight())

        if "left" in self._resize_edges:
            new_x = x + delta.x()
            new_w = w - delta.x()
            if new_w < min_w:
                new_x = x + (w - min_w)
                new_w = min_w
            x, w = new_x, new_w
        elif "right" in self._resize_edges:
            w = max(min_w, w + delta.x())

        if "top" in self._resize_edges:
            new_y = y + delta.y()
            new_h = h - delta.y()
            if new_h < min_h:
                new_y = y + (h - min_h)
                new_h = min_h
            y, h = new_y, new_h
        elif "bottom" in self._resize_edges:
            h = max(min_h, h + delta.y())

        self.window.setGeometry(x, y, w, h)

    def _edges_at(self, pos: QPoint) -> set[str]:
        rect = self.window.rect()
        edges = set()
        if pos.x() <= self.margin:
            edges.add("left")
        elif pos.x() >= rect.width() - self.margin:
            edges.add("right")

        if pos.y() <= self.top_margin:
            edges.add("top")
        elif pos.y() >= rect.height() - self.margin:
            edges.add("bottom")
        return edges

    def _cursor_for_edges(self, edges: set[str]):
        if not edges:
            return None
        if edges == {"left", "top"} or edges == {"right", "bottom"}:
            return Qt.SizeFDiagCursor
        if edges == {"left", "bottom"} or edges == {"right", "top"}:
            return Qt.SizeBDiagCursor
        if "left" in edges or "right" in edges:
            return Qt.SizeHorCursor
        if "top" in edges or "bottom" in edges:
            return Qt.SizeVerCursor
        return None

    def _update_cursor(self, global_pos: QPoint):
        if not self.window.isVisible() or self._is_window_effectively_maximized():
            self._maybe_reset_cursor()
            return

        geometry = self.window.geometry()
        if not geometry.contains(global_pos):
            self._maybe_reset_cursor()
            return

        # Fast reject for interior moves where resize cursors are never needed.
        if self._cursor_shape is None:
            left_dist = int(global_pos.x() - geometry.left())
            right_dist = int(geometry.right() - global_pos.x())
            top_dist = int(global_pos.y() - geometry.top())
            bottom_dist = int(geometry.bottom() - global_pos.y())
            if (
                left_dist > self.margin
                and right_dist > self.margin
                and top_dist > self.top_margin
                and bottom_dist > self.margin
            ):
                return

        local_pos = self.window.mapFromGlobal(global_pos)
        edges = self._edges_at(local_pos)
        cursor = self._cursor_for_edges(edges)
        if cursor is None:
            self._maybe_reset_cursor()
            return
        if self._cursor_shape != cursor:
            self.window.setCursor(cursor)
            self._cursor_shape = cursor

    def _refresh_cursor(self):
        self._update_cursor(QCursor.pos())

    def _maybe_reset_cursor(self):
        if self._cursor_shape is not None:
            self.window.unsetCursor()
            self._cursor_shape = None

    def _start_system_resize(self, edges: set[str]) -> bool:
        handle = self.window.windowHandle()
        if handle is None:
            return False

        try:
            edge_flag = 0
            if "left" in edges:
                edge_flag |= int(Qt.LeftEdge)
            if "right" in edges:
                edge_flag |= int(Qt.RightEdge)
            if "top" in edges:
                edge_flag |= int(Qt.TopEdge)
            if "bottom" in edges:
                edge_flag |= int(Qt.BottomEdge)
            if edge_flag == 0:
                return False
            return bool(handle.startSystemResize(Qt.Edges(edge_flag)))
        except Exception:
            return False
