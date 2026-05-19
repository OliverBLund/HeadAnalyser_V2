"""
GridPlotArea — resizable multi-cell plot grid for HeadAnalyser V2.

Provides a QWidget that tiles multiple PlotWidget instances in a
splitter-based grid.  Each cell stores its own plot-type and sidebar
settings; clicking a cell makes it "active" and the PlotPage routes
all sidebar/toolbar changes to that cell only.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from PyQt5.QtCore import Qt, QEvent, pyqtSignal
from PyQt5.QtGui import QColor, QPainter
from PyQt5.QtWidgets import QSplitter, QVBoxLayout, QWidget

from styles.colors import Colors

# (rows, cols) for each layout preset key 1-5
_PRESET_GRID: Dict[int, tuple] = {
    1: (1, 1),
    2: (1, 2),
    3: (2, 1),
    4: (2, 2),
    5: (1, 3),
}

_SPLITTER_HANDLE_CSS = "QSplitter::handle { background: #0f0f12; }"


class GridCellContainer(QWidget):
    """
    Wraps one PlotWidget with an active-state accent border and click capture.

    The border is painted inside the widget bounds (no layout shift).
    An event-filter on the wrapped PlotWidget (and its canvas child) emits
    ``activated`` on any mouse-press so the parent grid can focus the cell
    without blocking matplotlib pan/zoom interactions.
    """

    activated = pyqtSignal(int)  # cell index (0-based)

    _BORDER_PX = 2

    def __init__(self, index: int, plot_widget: QWidget, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._index = index
        self._pw = plot_widget
        self._active = False

        # Per-cell saved state
        self._plot_type: str = "2D"
        self._settings: dict = {}

        lay = QVBoxLayout(self)
        lay.setContentsMargins(
            self._BORDER_PX, self._BORDER_PX,
            self._BORDER_PX, self._BORDER_PX,
        )
        lay.setSpacing(0)
        lay.addWidget(plot_widget)

        # Capture clicks anywhere inside the cell (including deep in the canvas)
        self._install_click_capture(plot_widget)

    # ── properties ──────────────────────────────────────────────────────────

    @property
    def plot_widget(self) -> QWidget:
        return self._pw

    @property
    def index(self) -> int:
        return self._index

    @property
    def is_active(self) -> bool:
        return self._active

    @property
    def plot_type(self) -> str:
        return self._plot_type

    @property
    def settings(self) -> dict:
        return dict(self._settings)

    # ── state ────────────────────────────────────────────────────────────────

    def set_active(self, active: bool) -> None:
        if self._active != active:
            self._active = active
            self.update()

    def save_state(self, plot_type: str, settings: dict) -> None:
        self._plot_type = str(plot_type)
        self._settings = dict(settings)

    # ── click capture ────────────────────────────────────────────────────────

    def _install_click_capture(self, w: QWidget) -> None:
        w.installEventFilter(self)
        # Also capture on the matplotlib canvas widget directly
        canvas = getattr(w, "canvas", None)
        if canvas is not None and isinstance(canvas, QWidget) and canvas is not w:
            canvas.installEventFilter(self)

    def eventFilter(self, obj, event) -> bool:  # type: ignore[override]
        if event.type() == QEvent.MouseButtonPress:
            self.activated.emit(self._index)
        return False  # always pass through so pan/zoom still works

    # ── border paint ─────────────────────────────────────────────────────────

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if not self._active:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, False)
        try:
            col = QColor(Colors.ACCENT_PRIMARY)
        except Exception:
            col = QColor(129, 140, 248)
        b = self._BORDER_PX
        r = self.rect()
        p.fillRect(r.x(), r.y(), r.width(), b, col)                 # top
        p.fillRect(r.x(), r.height() - b, r.width(), b, col)        # bottom
        p.fillRect(r.x(), r.y(), b, r.height(), col)                 # left
        p.fillRect(r.width() - b, r.y(), b, r.height(), col)        # right
        p.end()


class GridPlotArea(QWidget):
    """
    Displays 1–4 PlotWidget instances arranged in a resizable splitter grid.

    Layout presets:
        1 → 1×1   (single cell, no splitters)
        2 → 1×2   (side-by-side)
        3 → 2×1   (stacked)
        4 → 2×2   (quad)
        5 → 1×3   (three columns)

    ``save_active_cell_state`` is emitted *before* the active cell changes so
    that the caller can snapshot the current sidebar settings into the
    departing cell.  ``active_cell_changed`` is emitted *after* the switch.
    """

    save_active_cell_state = pyqtSignal()
    active_cell_changed = pyqtSignal(int)  # new active cell index

    def __init__(
        self,
        main_window,
        primary_plot_widget: QWidget,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._mw = main_window
        self._preset: int = 1
        self._active_idx: int = 0
        self._containers: List[GridCellContainer] = []
        # All PlotWidget instances ever created; index 0 = primary (pre-existing)
        self._plot_widgets: List[QWidget] = [primary_plot_widget]
        self._root: Optional[QWidget] = None

        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(0, 0, 0, 0)
        self._lay.setSpacing(0)

        self._build()

    # ── public API ───────────────────────────────────────────────────────────

    @property
    def active_cell(self) -> GridCellContainer:
        return self._containers[self._active_idx]

    @property
    def active_plot_widget(self) -> QWidget:
        return self.active_cell.plot_widget

    @property
    def cells(self) -> List[GridCellContainer]:
        return list(self._containers)

    def current_preset(self) -> int:
        return self._preset

    def set_layout_preset(self, preset: int) -> None:
        if preset not in _PRESET_GRID or preset == self._preset:
            return
        self._preset = preset
        self._build()

    # ── layout construction ──────────────────────────────────────────────────

    def _build(self) -> None:
        rows, cols = _PRESET_GRID[self._preset]
        n = rows * cols

        self._ensure_widgets(n)

        # Reparent plot widgets out to self (GridPlotArea) and hide them so
        # they survive teardown of their old containers. Without this, when
        # the old root splitter loses its only Python ref below, PyQt deletes
        # it — Qt then cascades and deletes the containers AND the plot
        # widgets nested inside them, leaving stale Python wrappers.
        for pw in self._plot_widgets:
            try:
                pw.setParent(self)
                pw.hide()
            except RuntimeError:
                pass

        # Tear down the old splitter tree. With plot widgets safely detached,
        # we can let Qt cascade-delete the splitter and its old containers.
        if self._root is not None:
            try:
                self._lay.removeWidget(self._root)
                self._root.setParent(None)
                self._root.deleteLater()
            except RuntimeError:
                pass
            self._root = None
        # Drop stale Python refs to the (now-deleted) old containers.
        self._containers = []

        # (Re)create containers around the surviving plot widgets.
        for i in range(n):
            pw = self._plot_widgets[i]
            pw.show()
            c = GridCellContainer(i, pw, self)
            c.activated.connect(self._on_activated)
            self._containers.append(c)

        self._active_idx = min(self._active_idx, n - 1)
        self._containers[self._active_idx].set_active(True)

        root = self._build_splitter_tree(rows, cols)
        self._root = root
        self._lay.addWidget(root)

    def _build_splitter_tree(self, rows: int, cols: int) -> QWidget:
        """Construct nested QSplitters for the given grid dimensions."""
        if rows == 1 and cols == 1:
            return self._containers[0]

        if rows == 1:
            sp = self._make_splitter(Qt.Horizontal)
            for c in self._containers:
                sp.addWidget(c)
            self._equalize_sizes(sp, len(self._containers))
            return sp

        if cols == 1:
            sp = self._make_splitter(Qt.Vertical)
            for c in self._containers:
                sp.addWidget(c)
            self._equalize_sizes(sp, len(self._containers))
            return sp

        # Both dimensions > 1 (currently only 2×2 reaches here)
        vsp = self._make_splitter(Qt.Vertical)
        for r in range(rows):
            hsp = self._make_splitter(Qt.Horizontal)
            for c in range(cols):
                hsp.addWidget(self._containers[r * cols + c])
            self._equalize_sizes(hsp, cols)
            vsp.addWidget(hsp)
        self._equalize_sizes(vsp, rows)
        return vsp

    @staticmethod
    def _make_splitter(orientation) -> QSplitter:
        """Build a configured QSplitter — no collapsing, no opaque drag (avoids
        matplotlib re-rendering at every drag step which causes the visual
        glitches seen on vertical drags)."""
        sp = QSplitter(orientation)
        sp.setHandleWidth(4)
        sp.setStyleSheet(_SPLITTER_HANDLE_CSS)
        sp.setChildrenCollapsible(False)
        # Non-opaque resize: cell only redraws once when the handle is released.
        # Matplotlib canvases can be slow to repaint and create visible artifacts
        # if redrawn at every mouse-move during the drag.
        sp.setOpaqueResize(False)
        return sp

    @staticmethod
    def _equalize_sizes(sp: QSplitter, n: int) -> None:
        """Distribute the splitter's available extent evenly across n panes."""
        try:
            extent = sp.width() if sp.orientation() == Qt.Horizontal else sp.height()
            if extent <= 0:
                extent = 1000  # placeholder before first show; Qt will rebalance later
            base = max(50, extent // max(1, n))
            sp.setSizes([base] * n)
        except Exception:
            pass

    def _ensure_widgets(self, n: int) -> None:
        """Lazily create additional PlotWidget instances as needed."""
        from ui.plot_widget import PlotWidget  # local import avoids circular dep
        while len(self._plot_widgets) < n:
            pw = PlotWidget(self._mw)
            self._plot_widgets.append(pw)

    # ── activation ───────────────────────────────────────────────────────────

    def _on_activated(self, idx: int) -> None:
        if idx == self._active_idx:
            return
        # Let PlotPage snapshot the sidebar state for the departing cell
        self.save_active_cell_state.emit()
        # Switch
        self._containers[self._active_idx].set_active(False)
        self._active_idx = idx
        self._containers[self._active_idx].set_active(True)
        self.active_cell_changed.emit(idx)
