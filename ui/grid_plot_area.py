"""
GridPlotArea — resizable multi-cell plot grid for HeadAnalyser V2.

Provides a QWidget that tiles multiple PlotWidget instances in a
splitter-based grid.  Each cell stores its own plot-type and sidebar
settings; clicking a cell makes it "active" and the PlotPage routes
all sidebar/toolbar changes to that cell only.
"""

from __future__ import annotations

from typing import Callable, Dict, List, Optional

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

    # Main-window attributes whose values this cell owns. When the cell is
    # active, ``main_window.<attr>`` mirrors ``self._mw_state[attr]``.
    # NOTE: depth_min/max and head_min/max are NOT actual attributes on
    # main_window — they live exclusively in the properties_panel sliders.
    # We still store them in ``_mw_state`` (so we can restore the slider on
    # cell switch), but we do NOT include them in the snapshot-from-mw path
    # below (otherwise getattr(mw, "head_min", None) would return None and
    # clobber the value just written by _persist_filter_inputs_to_active_cell).
    MW_FILTER_INPUTS_CELL_ONLY = (
        "depth_min", "depth_max", "head_min", "head_max",
    )
    MW_FILTER_INPUTS_MIRRORED = (
        "excluded_ids", "excluded_member_keys",
    )
    MW_FILTER_OUTPUTS = (
        "filtered_data", "filtered_plot_data",
        "triangle_data", "gradient_data", "rejected_data",
        "total_triangles",
        "rejected_due_to_uncertainty",
        "rejected_due_to_triangle_quality",
        "rejected_due_to_calculation_failed",
    )
    # Dark canvas isn't a main_window attribute — it's stored on each
    # PlotWidget (``_dark_canvas``), so it's already per-cell by construction.
    MW_PILLS = (
        "show_legend", "show_grid", "show_compass",
    )
    MW_VISUAL_COMPOSITION = (
        "current_plot_template",
        "current_color_style",
        "current_plot_format",
        "current_plot_style",
        "current_popup_style",
        "colormap_2d",
        "colormap_3d",
        "colormap_vectors",
        "histogram_bar_color",
        "histogram_edge_color",
        "rose_color",
        "id_label_color",
        "head_label_color",
        "arrow_color",
    )
    # Keys captured by ``snapshot_mw_state`` (i.e. genuinely live on mw).
    MW_SNAPSHOT_KEYS = MW_FILTER_INPUTS_MIRRORED + MW_FILTER_OUTPUTS + MW_PILLS + MW_VISUAL_COMPOSITION
    # Keys restored by ``apply_to_mw`` (mirrored + cell-only). The cell-only
    # ones are also written to mw — harmless, since nothing reads them there.
    MW_KEYS = MW_FILTER_INPUTS_CELL_ONLY + MW_SNAPSHOT_KEYS

    def __init__(self, index: int, plot_widget: QWidget, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._index = index
        self._pw = plot_widget
        self._active = False

        # Per-cell saved state
        self._plot_type: str = "2D"
        self._settings: dict = {}
        # Per-cell mirror of main_window attributes (see MW_KEYS).
        # Populated by ``snapshot_mw_state`` and restored via ``apply_to_mw``.
        self._mw_state: dict = {}

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

    # ── per-cell mirror of main_window attributes ───────────────────────────

    @property
    def mw_state(self) -> dict:
        return self._mw_state

    @staticmethod
    def _dup(value):
        """Defensive copy for mutable containers; pass-through for scalars/DataFrames."""
        if isinstance(value, set):
            return set(value)
        return value

    def snapshot_mw_state(self, mw) -> None:
        """Capture ``mw``'s per-cell attributes into this cell.

        Preserves any existing cell-only filter inputs (depth/head slider
        values), since those don't live on mw — they're managed directly via
        ``_persist_filter_inputs_to_active_cell``.
        """
        snap = dict(self._mw_state)  # preserve existing (esp. cell-only keys)
        for key in self.MW_SNAPSHOT_KEYS:
            snap[key] = self._dup(getattr(mw, key, None))
        self._mw_state = snap

    def apply_to_mw(self, mw) -> None:
        """Push this cell's stored state back onto ``mw``."""
        for key in self.MW_KEYS:
            if key not in self._mw_state:
                continue
            try:
                setattr(mw, key, self._dup(self._mw_state[key]))
            except Exception:
                pass

    def inherit_from(self, other: "GridCellContainer") -> None:
        """Copy another cell's mw_state (used when a fresh cell is added to the grid)."""
        snap = {}
        for key in self.MW_KEYS:
            snap[key] = self._dup(other._mw_state.get(key))
        self._mw_state = snap
        # Also copy plot type + sidebar settings so the new cell starts as a clone.
        self._plot_type = str(other._plot_type)
        self._settings = dict(other._settings)
        # Carry over the dark-canvas pill which lives on the PlotWidget itself.
        try:
            other_dark = bool(getattr(other.plot_widget, "_dark_canvas", False))
            self._pw.set_dark_canvas(other_dark)
        except Exception:
            pass

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
        # Hook the owner (PlotPage) can install to initialize freshly-created
        # plot widgets (e.g., stamp `_dataset_id`, apply page-wide flags).
        self._on_new_plot_widget: Optional[Callable[[QWidget], None]] = None

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

        # Hold a reference to the old containers (their _mw_state) for the
        # rebuild — newly-added cells inherit from the active one.
        self._old_cells_for_inherit = list(self._containers)

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

        # Capture the soon-to-be-replaced active cell's state so we can copy it
        # onto any *newly-introduced* cells (those past the prior length).
        seed_cells = list(self._old_cells_for_inherit) if hasattr(self, "_old_cells_for_inherit") else []
        prior_len = len(seed_cells)
        prior_active_idx = self._active_idx if 0 <= self._active_idx < prior_len else 0
        seed_cell = seed_cells[prior_active_idx] if seed_cells else None

        # (Re)create containers around the surviving plot widgets.
        for i in range(n):
            pw = self._plot_widgets[i]
            pw.show()
            c = GridCellContainer(i, pw, self)
            c.activated.connect(self._on_activated)
            # Preserve state for indices that existed before; newly-introduced
            # indices inherit from the previously-active cell so the grid
            # starts as N clones of the user's current view.
            if i < prior_len:
                try:
                    c.inherit_from(seed_cells[i])
                except Exception:
                    pass
            elif seed_cell is not None:
                try:
                    c.inherit_from(seed_cell)
                except Exception:
                    pass
            self._containers.append(c)

        self._active_idx = min(self._active_idx, n - 1)
        self._containers[self._active_idx].set_active(True)

        root = self._build_splitter_tree(rows, cols)
        self._root = root
        self._lay.addWidget(root)
        # Drop the seed snapshot now that all new containers have inherited.
        self._old_cells_for_inherit = []

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
        """Lazily create additional PlotWidget instances as needed.

        Each freshly created widget is passed through ``_on_new_plot_widget``
        (if set) so the owning PlotPage can stamp dataset_id and any other
        page-wide state onto it before it is wrapped in a container.
        """
        from ui.plot_widget import PlotWidget  # local import avoids circular dep
        while len(self._plot_widgets) < n:
            pw = PlotWidget(self._mw)
            if self._on_new_plot_widget is not None:
                try:
                    self._on_new_plot_widget(pw)
                except Exception:
                    pass
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
