"""
HeadAnalyser V2 - Plot Widget
Matplotlib canvas embedded in PyQt with dark styling.
"""

import time
import os
import inspect
from collections import Counter
import numpy as np
import pandas as pd
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QSizePolicy, QLabel, QFrame, QDialog, QPushButton, QButtonGroup, QRadioButton, QTabWidget
from PyQt5.QtCore import Qt, pyqtSignal, QSize, QRectF, QTimer
from PyQt5.QtGui import QPainterPath, QRegion
import matplotlib
matplotlib.use('Qt5Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle, FancyArrow
from matplotlib.ticker import MultipleLocator
from mpl_toolkits.axes_grid1 import make_axes_locatable
from mpl_toolkits.axes_grid1 import make_axes_locatable
from mpl_toolkits.axes_grid1.inset_locator import inset_axes
import matplotlib.patheffects as pe

from styles.colors import Colors
from core.geology_layers import GeoDkSvgSurfaceGeologyProvider, get_default_geology_provider
from core.contour_engine import compute_contour_grid
from ui.geodk_panel_widget import GeoDKPanelWidget
from ui.plot_types import normalize_plot_type


class PlotCanvas(FigureCanvas):
    """Matplotlib canvas with white background styling."""

    def __init__(self, parent=None, coords_callback=None, interaction_callback=None, click_callback=None):
        # Use default matplotlib style (white background)
        plt.style.use('default')

        self._dark = False
        self.fig = Figure(dpi=110, facecolor=Colors.PLOT_BG)
        self.ax = self.fig.add_subplot(111)
        self._style_axes()

        super().__init__(self.fig)
        self.setParent(parent)

        # Ensure the canvas can receive keyboard focus (needed for key bindings like E/I).
        self.setFocusPolicy(Qt.ClickFocus)
        self.setFocus()

        # Callback for coordinate updates
        self.coords_callback = coords_callback
        # Optional callback for pan-interaction state changes (True on pan start, False on pan end).
        self.interaction_callback = interaction_callback
        # Optional callback for left-click in data coordinates.
        self.click_callback = click_callback

        # Set size policy to expand in both directions
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(300, 300)
        self.updateGeometry()

        # Enable mouse interaction
        self._setup_interactions()

        # Throttle expensive redraws during resize
        self._pending_resize = False
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self._apply_deferred_resize)

        # Keep high-frequency interaction redraws bounded to avoid UI backlog.
        self._last_interaction_draw_time = 0.0
        # Typical draw time is often ~30-45ms on contour plots; target stable responsiveness.
        try:
            interaction_fps = float(os.getenv("HEADANALYSER_INTERACTION_DRAW_FPS", "24"))
        except Exception:
            interaction_fps = 24.0
        if interaction_fps <= 0:
            interaction_fps = 24.0
        self._interaction_draw_interval_s = 1.0 / interaction_fps
        self._interaction_draw_pending = False
        self._interaction_draw_timer = QTimer(self)
        self._interaction_draw_timer.setSingleShot(True)
        self._interaction_draw_timer.timeout.connect(self._flush_deferred_interaction_draw)
        self._disable_tight_layout = self._env_flag("HEADANALYSER_DISABLE_TIGHT_LAYOUT")
        try:
            self._tight_layout_min_interval_s = max(
                0.0, float(os.getenv("HEADANALYSER_TIGHT_LAYOUT_MIN_INTERVAL_S", "0.0"))
            )
        except Exception:
            self._tight_layout_min_interval_s = 0.0
        self._last_tight_layout_time = 0.0
        self._last_coords_emit_time = 0.0
        self._coords_emit_interval_s = 1.0 / 45.0

        # Optional canvas-level profiler (disabled by default).
        self._perf_enabled = self._env_flag("HEADANALYSER_PROFILE_PLOT_CANVAS")
        self._perf_started = time.perf_counter()
        self._perf_last_dump = self._perf_started
        self._perf_counts = Counter()
        self._perf_stats = {}
        self._perf_log_path = os.getenv("HEADANALYSER_PROFILE_PLOT_CANVAS_LOG", "plot_canvas_profile.log")
        try:
            self._perf_dump_interval_s = max(
                0.25,
                float(os.getenv("HEADANALYSER_PROFILE_PLOT_CANVAS_INTERVAL_S", "1.0")),
            )
        except Exception:
            self._perf_dump_interval_s = 1.0
        if self._perf_enabled:
            msg = f"[canvas-profiler] enabled, logging to {self._perf_log_path}"
            print(msg)
            self._perf_append_log(msg)

    @staticmethod
    def _env_flag(name: str) -> bool:
        return str(os.getenv(name, "")).strip().lower() in {"1", "true", "yes", "on"}

    def _perf_append_log(self, text: str):
        if not self._perf_enabled:
            return
        try:
            with open(self._perf_log_path, "a", encoding="utf-8") as f:
                f.write(text + "\n")
        except Exception:
            pass

    def _perf_record_duration(self, key: str, elapsed_ms: float):
        stats = self._perf_stats.get(key)
        if stats is None:
            stats = {"count": 0, "total_ms": 0.0, "max_ms": 0.0}
            self._perf_stats[key] = stats
        stats["count"] += 1
        stats["total_ms"] += float(elapsed_ms)
        if elapsed_ms > stats["max_ms"]:
            stats["max_ms"] = float(elapsed_ms)

    def _perf_maybe_dump(self):
        if not self._perf_enabled:
            return
        now = time.perf_counter()
        if (now - self._perf_last_dump) < self._perf_dump_interval_s:
            return
        self._perf_last_dump = now
        if not self._perf_counts and not self._perf_stats:
            return

        elapsed = now - self._perf_started
        counts = [f"{k}={v}" for k, v in self._perf_counts.most_common(12)]
        methods = []
        for name, s in sorted(self._perf_stats.items(), key=lambda kv: kv[1]["total_ms"], reverse=True)[:8]:
            avg = s["total_ms"] / s["count"] if s["count"] else 0.0
            methods.append(
                f"{name}: n={s['count']} total={s['total_ms']:.1f}ms avg={avg:.2f}ms max={s['max_ms']:.2f}ms"
            )
        lines = [f"[canvas-profiler +{elapsed:.1f}s]"]
        if counts:
            lines.append("counts: " + " | ".join(counts))
        if methods:
            lines.append("timings: " + " | ".join(methods))
        scene = self._perf_scene_snapshot()
        if scene:
            lines.append("scene: " + scene)
        msg = "\n".join(lines)
        print(msg)
        self._perf_append_log(msg)
        self._perf_counts.clear()
        self._perf_stats.clear()

    def _perf_scene_snapshot(self) -> str:
        if not self._perf_enabled:
            return ""
        try:
            fig = getattr(self, "fig", None)
            if fig is None:
                return ""
            axes = list(getattr(fig, "axes", []) or [])
            parts = [f"axes={len(axes)}"]
            if axes:
                ax = axes[0]
                parts.append(f"texts={len(getattr(ax, 'texts', []))}")
                parts.append(f"collections={len(getattr(ax, 'collections', []))}")
                parts.append(f"lines={len(getattr(ax, 'lines', []))}")
                parts.append(f"patches={len(getattr(ax, 'patches', []))}")
                parts.append(f"images={len(getattr(ax, 'images', []))}")
            return " | ".join(parts)
        except Exception:
            return ""

    def draw_idle(self, *args, **kwargs):
        if self._perf_enabled:
            self._perf_counts["draw_idle_called"] += 1
            caller = None
            frame = None
            try:
                frame = inspect.currentframe()
                if frame is not None and frame.f_back is not None:
                    caller = str(frame.f_back.f_code.co_name)
            except Exception:
                caller = None
            finally:
                del frame
            if caller:
                self._perf_counts[f"draw_idle_from.{caller}"] += 1
        result = super().draw_idle(*args, **kwargs)
        self._perf_maybe_dump()
        return result

    def draw(self, *args, **kwargs):
        if not self._perf_enabled:
            return super().draw(*args, **kwargs)
        t0 = time.perf_counter()
        try:
            return super().draw(*args, **kwargs)
        finally:
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            self._perf_counts["draw_called"] += 1
            self._perf_record_duration("draw", elapsed_ms)
            self._perf_maybe_dump()

    def paintEvent(self, event):
        if not self._perf_enabled:
            return super().paintEvent(event)
        t0 = time.perf_counter()
        try:
            return super().paintEvent(event)
        finally:
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            self._perf_counts["paint_event_called"] += 1
            self._perf_record_duration("paint_event", elapsed_ms)
            self._perf_maybe_dump()

    def sizeHint(self):
        """Suggest using maximum available space."""
        # Return a very large size hint so it expands to fill space
        return QSize(2000, 2000)

    def minimumSizeHint(self):
        """Minimum size hint."""
        return QSize(300, 300)

    def hasHeightForWidth(self):
        """Height does not depend on width - allow free expansion."""
        return False

    def resizeEvent(self, event):
        """Schedule a debounced tight_layout so the plot re-fits its new canvas size.

        Without this, matplotlib propagates the size internally but doesn't
        recompute the axes layout — so labels, legends, colorbars, and 3-D
        bounding boxes can run off the cell when the user drags a splitter
        or switches grid presets, and stay clipped until the next full
        update_plot. Coalesce via timer so a resize storm (e.g. during a
        window drag) doesn't fire tight_layout on every event.
        """
        super().resizeEvent(event)
        try:
            self._pending_resize = True
            # 80ms is short enough to feel instant, long enough to coalesce
            # the burst of events Qt fires while a splitter handle is moving.
            self._resize_timer.start(80)
        except Exception:
            pass

    def _apply_deferred_resize(self):
        """Recompute the plot's layout once the resize burst has settled."""
        self._pending_resize = False
        # request_tight_layout already handles its own min-interval throttling
        # and draw_idle scheduling — just call it.
        try:
            self.request_tight_layout()
        except Exception:
            try:
                self.draw_idle()
            except Exception:
                pass

    def _flush_deferred_interaction_draw(self):
        self._interaction_draw_pending = False
        self._last_interaction_draw_time = time.monotonic()
        if self._perf_enabled:
            self._perf_counts["interaction_draw_flushed"] += 1
        self.draw_idle()

    def request_interaction_draw(self, *, force: bool = False):
        if self._perf_enabled:
            self._perf_counts["interaction_draw_requested"] += 1
            caller = None
            frame = None
            try:
                frame = inspect.currentframe()
                if frame is not None and frame.f_back is not None:
                    caller = str(frame.f_back.f_code.co_name)
                    if caller == "_request_interaction_draw" and frame.f_back.f_back is not None:
                        caller = str(frame.f_back.f_back.f_code.co_name)
            except Exception:
                caller = None
            finally:
                del frame
            if caller:
                self._perf_counts[f"interaction_draw_from.{caller}"] += 1

        now = time.monotonic()
        if force or self._interaction_draw_interval_s <= 0.0:
            self._last_interaction_draw_time = now
            self._interaction_draw_pending = False
            try:
                self._interaction_draw_timer.stop()
            except Exception:
                pass
            self.draw_idle()
            return

        elapsed = now - self._last_interaction_draw_time
        if elapsed >= self._interaction_draw_interval_s:
            self._last_interaction_draw_time = now
            self._interaction_draw_pending = False
            try:
                self._interaction_draw_timer.stop()
            except Exception:
                pass
            self.draw_idle()
            return

        if self._interaction_draw_pending:
            if self._perf_enabled:
                self._perf_counts["interaction_draw_throttled"] += 1
            return

        remaining_ms = max(1, int((self._interaction_draw_interval_s - elapsed) * 1000.0))
        self._interaction_draw_pending = True
        self._interaction_draw_timer.start(remaining_ms)
        if self._perf_enabled:
            self._perf_counts["interaction_draw_deferred"] += 1

    def request_tight_layout(self):
        """Apply layout that fits the current plot content into the canvas.

        Strategy varies by axes type — tight_layout misbehaves with 3-D
        projections (its math assumes 2-D axes) and clips radial tick labels
        on polar axes. We pick a layout strategy that suits the active
        primary axes so plots don't run off the cell on small layouts or
        after settings changes.
        """
        if self._disable_tight_layout:
            try:
                self.draw_idle()
            except Exception:
                pass
            return

        if self._tight_layout_min_interval_s > 0.0:
            now = time.monotonic()
            if (now - self._last_tight_layout_time) < self._tight_layout_min_interval_s:
                try:
                    self.draw_idle()
                except Exception:
                    pass
                return
            self._last_tight_layout_time = now

        # Detect axes type so we can pick a layout that doesn't clip content
        # in small / narrow cells (2-D side-by-side, 3-D in a quad grid, etc.).
        is_3d = False
        is_polar = False
        try:
            for a in self.fig.axes:
                if getattr(a, "name", "") == "3d" or hasattr(a, "get_proj"):
                    is_3d = True
                    break
                if getattr(a, "name", "") == "polar":
                    is_polar = True
                    break
        except Exception:
            pass

        try:
            import warnings
            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore",
                    message=r".*not compatible with tight_layout.*",
                    category=UserWarning,
                )
                if is_3d:
                    # tight_layout warps 3-D bounding boxes — use subplots_adjust
                    # with generous margins so labels + bbox stay inside the cell.
                    self.fig.subplots_adjust(
                        left=0.06, right=0.94, top=0.95, bottom=0.06
                    )
                elif is_polar:
                    # Rose / polar: radial tick labels sit OUTSIDE the axes
                    # circle — give them breathing room.
                    self.fig.tight_layout(pad=1.5)
                else:
                    # Standard 2-D — drop the prior rect=[0.06,0.06,0.98,0.98]
                    # constraint so tight_layout can use the full figure area
                    # when a legend/colorbar/etc. needs more room.
                    self.fig.tight_layout(pad=0.8)
        except Exception:
            pass
        try:
            self.draw_idle()
        except Exception:
            pass

    def _style_axes(self):
        """Apply styling to axes, respecting dark/light canvas mode."""
        dark = self._dark
        face = Colors.PLOT_DARK_FACE if dark else Colors.PLOT_FACE
        text = Colors.PLOT_DARK_TEXT if dark else Colors.PLOT_TEXT
        spine = Colors.PLOT_DARK_SPINE if dark else Colors.PLOT_SPINE
        grid = Colors.PLOT_DARK_GRID if dark else Colors.PLOT_GRID
        grid_alpha = 0.15 if dark else 0.12

        self.ax.set_facecolor(face)

        # Enhanced tick styling with better contrast
        self.ax.tick_params(
            colors=text,
            labelsize=11,
            width=1.2,
            length=5,
            direction='out',
            pad=6,
            labelcolor=text
        )

        # Axis labels with enhanced styling
        self.ax.xaxis.label.set_color(text)
        self.ax.yaxis.label.set_color(text)
        self.ax.xaxis.label.set_fontsize(12)
        self.ax.yaxis.label.set_fontsize(12)
        self.ax.xaxis.label.set_fontweight('600')
        self.ax.yaxis.label.set_fontweight('600')

        # Spine styling with refined appearance
        for sp in self.ax.spines.values():
            sp.set_color(spine)
            sp.set_linewidth(1.2)

        # Grid styling with subtle appearance
        self.ax.grid(
            True,
            alpha=grid_alpha,
            linestyle=':',
            linewidth=0.8,
            color=grid
        )

    def _apply_axis_theme(self, ax, fig=None, *, polar: bool = False, is_3d: bool = False):
        """Apply the active plot-surface theme to axes immediately after creation.

        Call this right after fig.clear() + add_subplot() in every draw method.
        This is the single source of truth for plot presentation quality — typography,
        grid, spines, tick params, and figure background.

        Args:
            ax:     The newly-created matplotlib Axes.
            fig:    The Figure (optional). When provided its face colour is also set.
            polar:  True for polar subplots — skips spine/grid manipulation.
            is_3d:  True for 3D subplots — minimal styling only (mpl limits control).
        """
        C_FACE = Colors.PLOT_FACE
        C_TEXT = Colors.PLOT_TEXT
        C_LABEL = Colors.PLOT_AXIS
        C_SPINE = Colors.PLOT_SPINE
        C_GRID = Colors.PLOT_GRID

        # Figure background
        if fig is not None:
            fig.patch.set_facecolor(C_FACE)

        # ── 3-D axes: pane colours + labels only (mpl limits control here) ───
        if is_3d:
            ax.set_facecolor(C_FACE)
            try:
                for pane in (ax.xaxis.pane, ax.yaxis.pane, ax.zaxis.pane):
                    pane.fill = False
                    pane.set_edgecolor(C_GRID)
            except Exception:
                pass
            for lbl in (ax.xaxis.label, ax.yaxis.label, ax.zaxis.label):
                lbl.set_color(C_TEXT)
                lbl.set_fontsize(11)
                lbl.set_fontweight("600")
            ax.tick_params(labelsize=9, colors=C_LABEL)
            return

        # ── Polar axes: background + ring + tick labels ───────────────────────
        if polar:
            ax.set_facecolor(C_FACE)
            ax.grid(False)   # let per-plot show_grid logic control this
            try:
                ax.spines["polar"].set_color(C_SPINE)
                ax.spines["polar"].set_linewidth(0.8)
            except Exception:
                pass
            ax.tick_params(labelsize=9, colors=C_LABEL, pad=6)
            ax.title.set_color(C_TEXT)
            ax.title.set_fontsize(13)
            ax.title.set_fontweight("600")
            return

        # ── Standard 2-D axes ────────────────────────────────────────────────
        ax.set_facecolor(C_FACE)

        # Spines: style all 4 with the baseline colour/width.
        # Visibility (hide top/right etc.) is a style decision — handled by PlotStyles.apply_to_axes.
        for spine in ax.spines.values():
            spine.set_visible(True)
            spine.set_color(C_SPINE)
            spine.set_linewidth(1.0)

        # Grid position: always behind data. State (on/off) is controlled by per-plot show_grid logic.
        ax.set_axisbelow(True)
        ax.grid(False)   # clean slate — per-plot logic turns it on if needed

        # Ticks: outward, compact, muted
        ax.tick_params(
            which="major",
            labelsize=10,
            colors=C_LABEL,
            labelcolor=C_LABEL,
            width=0.8,
            length=4,
            direction="out",
            pad=5,
        )
        ax.tick_params(which="minor", bottom=False, left=False, top=False, right=False)

        # Axis labels (pre-applied if already set; safe to call before set_xlabel/ylabel too)
        for axis_obj in (ax.xaxis, ax.yaxis):
            axis_obj.label.set_color(C_TEXT)
            axis_obj.label.set_fontsize(12)
            axis_obj.label.set_fontweight("600")

        # Title
        ax.title.set_color(C_TEXT)
        ax.title.set_fontsize(13)
        ax.title.set_fontweight("600")

    def _setup_interactions(self):
        """Setup mouse interactions for zoom and pan."""
        self.mpl_connect('scroll_event', self._on_scroll)
        self._press = None
        self._press_px = None
        self._drag_threshold_px = 4
        self._moved = False
        self._dragged_last = False
        self._pan_interaction_active = False
        self.mpl_connect('button_press_event', self._on_press)
        self.mpl_connect('button_release_event', self._on_release)
        self.mpl_connect('motion_notify_event', self._on_motion)

    def _on_scroll(self, event):
        """Handle scroll for zoom."""
        if event.inaxes != self.ax:
            return

        scale = 1.2 if event.button == 'down' else 1/1.2

        xlim = self.ax.get_xlim()
        ylim = self.ax.get_ylim()

        xdata = event.xdata
        ydata = event.ydata

        new_xlim = [xdata - (xdata - xlim[0]) * scale,
                    xdata + (xlim[1] - xdata) * scale]
        new_ylim = [ydata - (ydata - ylim[0]) * scale,
                    ydata + (ylim[1] - ydata) * scale]

        self.ax.set_xlim(new_xlim)
        self.ax.set_ylim(new_ylim)
        self._draw_idle_throttled()

    def _on_press(self, event):
        """Handle mouse press for pan."""
        if event.inaxes != self.ax or event.button != 1:
            return
        # Give keyboard focus to the canvas so Matplotlib key_press_event works.
        try:
            self.setFocus()
        except Exception:
            pass
        # Ctrl+drag is reserved for box selection in the plot widget.
        if self._event_has_modifier(event, Qt.ControlModifier, "control"):
            self._press = None
            self._press_px = None
            self._moved = False
            return
        self._press = (event.xdata, event.ydata)
        self._press_px = (event.x, event.y)
        self._moved = False

    def _on_release(self, event):
        """Handle mouse release."""
        self._dragged_last = bool(self._moved)
        if self._pan_interaction_active:
            self._pan_interaction_active = False
            if callable(self.interaction_callback):
                try:
                    self.interaction_callback(False)
                except Exception:
                    pass
        if self._dragged_last:
            self._draw_idle_throttled(force=True)
        elif (
            callable(self.click_callback)
            and event.inaxes == self.ax
            and event.button == 1
            and self._press is not None
        ):
            try:
                self.click_callback(float(self._press[0]), float(self._press[1]))
            except Exception:
                pass
        self._press = None
        self._press_px = None
        self._moved = False

    def _on_motion(self, event):
        """Handle mouse motion for pan and coordinate display."""
        # Always update coordinates if callback exists and mouse is in axes
        if self.coords_callback and event.inaxes == self.ax:
            if event.xdata is not None and event.ydata is not None:
                now = time.monotonic()
                if (now - self._last_coords_emit_time) >= self._coords_emit_interval_s:
                    self._last_coords_emit_time = now
                    self.coords_callback(event.xdata, event.ydata)

        # Handle panning
        if self._press is None or event.inaxes != self.ax:
            return

        # Only start panning after a small movement threshold so clicks can be used for selection.
        if not self._moved and self._press_px is not None:
            dx_px = abs(event.x - self._press_px[0])
            dy_px = abs(event.y - self._press_px[1])
            if max(dx_px, dy_px) >= self._drag_threshold_px:
                self._moved = True
                if not self._pan_interaction_active:
                    self._pan_interaction_active = True
                    if callable(self.interaction_callback):
                        try:
                            self.interaction_callback(True)
                        except Exception:
                            pass

        if not self._moved:
            return

        xpress, ypress = self._press
        dx = event.xdata - xpress
        dy = event.ydata - ypress

        xlim = self.ax.get_xlim()
        ylim = self.ax.get_ylim()

        self.ax.set_xlim(xlim[0] - dx, xlim[1] - dx)
        self.ax.set_ylim(ylim[0] - dy, ylim[1] - dy)
        self._draw_idle_throttled()

    def _draw_idle_throttled(self, *, force: bool = False):
        self.request_interaction_draw(force=force)

    @staticmethod
    def _event_has_modifier(event, qt_modifier, key_name: str) -> bool:
        key = str(getattr(event, "key", "") or "").lower()
        if key_name in key:
            return True
        gui_event = getattr(event, "guiEvent", None)
        if gui_event is not None and hasattr(gui_event, "modifiers"):
            try:
                return bool(gui_event.modifiers() & qt_modifier)
            except Exception:
                return False
        return False

    def clear(self):
        """Clear the plot."""
        self.ax.clear()
        self._style_axes()
        text_color = Colors.PLOT_DARK_TEXT if self._dark else Colors.PLOT_AXIS
        # Add empty state message
        self.ax.text(0.5, 0.5, 'No Data Loaded\n\nOpen a file to begin\n(Ctrl+O)',
                    transform=self.ax.transAxes,
                    ha='center', va='center',
                    fontsize=16, color=text_color,
                    fontweight='300',
                    linespacing=1.8)
        self.ax.set_xlim(0, 1)
        self.ax.set_ylim(0, 1)
        self.ax.axis('off')
        self.draw_idle()


class HintBar(QWidget):
    """Interaction hint strip below the plot canvas.
    Shows context-sensitive hints per plot type. Dismissable per session."""

    HINTS = {
        "2D": [("Scroll", "Zoom"), ("Drag", "Pan"), ("Click", "Select point"), ("Shift+Click", "Toggle select"), ("Ctrl+Drag", "Box select"), ("E / I", "Exclude / Include"), ("X", "Cross-section")],
        "3D": [("Scroll", "Zoom"), ("Drag", "Rotate")],
        "Gradient Vectors": [("Scroll", "Zoom"), ("Drag", "Pan"), ("Click", "Select arrow"), ("Dbl-click", "Inspect"), ("E / I", "Exclude / Include")],
        "Histogram": [("Hover", "Show value"), ("Click", "Select bin"), ("Dbl-click", "Inspect")],
        "Rose Diagram": [("Hover", "Show sector"), ("Click", "Select sector"), ("Dbl-click", "Inspect")],
    }

    dismissed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("hintBar")
        self.setFixedHeight(28)
        self._is_dismissed = False
        self._current_type = None

        # Outer layout to center the pill
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        outer.addStretch(1)

        # The pill container
        self._pill = QFrame(self)
        self._pill.setObjectName("hintPill")
        self._pill_layout = QHBoxLayout(self._pill)
        self._pill_layout.setContentsMargins(14, 0, 6, 0)
        self._pill_layout.setSpacing(0)

        self._hint_widgets = []  # all created children (labels + dots)

        # Close button
        from PyQt5.QtWidgets import QToolButton
        self._close_btn = QToolButton()
        self._close_btn.setObjectName("hintClose")
        self._close_btn.setText("\u2715")
        self._close_btn.setFixedSize(20, 20)
        self._close_btn.setCursor(Qt.PointingHandCursor)
        self._close_btn.clicked.connect(self._dismiss)

        outer.addWidget(self._pill)
        outer.addStretch(1)
        self.apply_theme()

    def _pill_stylesheet(self) -> str:
        return f"""
            QFrame#hintPill {{
                background-color: {Colors.floating_surface(light_base=Colors.BG_ELEVATED)};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 14px;
                padding: 0 4px;
            }}
        """

    def _close_button_stylesheet(self) -> str:
        return f"""
            QToolButton#hintClose {{
                background: transparent;
                border: none;
                color: {Colors.TEXT_MUTED};
                font-size: 11px;
                border-radius: 10px;
            }}
            QToolButton#hintClose:hover {{
                background-color: {Colors.BG_HOVER};
                color: {Colors.TEXT_PRIMARY};
            }}
        """

    def set_plot_type(self, plot_type: str, force: bool = False):
        """Rebuild hint content for the given plot type."""
        if self._is_dismissed or (not force and plot_type == self._current_type):
            return
        self._current_type = plot_type

        # Remove old widgets
        for w in self._hint_widgets:
            self._pill_layout.removeWidget(w)
            w.deleteLater()
        self._hint_widgets.clear()
        self._pill_layout.removeWidget(self._close_btn)

        hints = self.HINTS.get(plot_type, self.HINTS["2D"])
        for i, (key, action) in enumerate(hints):
            if i > 0:
                dot = QLabel("\u00b7")
                dot.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: 14px; background: transparent; border: none; padding: 0 3px;")
                dot.setFixedWidth(12)
                dot.setAlignment(Qt.AlignCenter)
                self._pill_layout.addWidget(dot)
                self._hint_widgets.append(dot)

            lbl = QLabel(f"<b>{key}</b> {action}")
            lbl.setStyleSheet(f"color: {Colors.TEXT_TERTIARY}; font-size: 10px; background: transparent; border: none;")
            self._pill_layout.addWidget(lbl)
            self._hint_widgets.append(lbl)

        self._pill_layout.addWidget(self._close_btn)
        self.setVisible(True)

    def apply_theme(self):
        self._pill.setStyleSheet(self._pill_stylesheet())
        self._close_btn.setStyleSheet(self._close_button_stylesheet())
        if self._current_type is not None:
            self.set_plot_type(self._current_type, force=True)

    def _dismiss(self):
        self._is_dismissed = True
        self.setVisible(False)
        self.dismissed.emit()


class PlotWidget(QWidget):
    """Widget containing the matplotlib plot and minimal toolbar."""

    # Signals for bidirectional selection sync with the data table
    point_selected = pyqtSignal(str)    # Emits point ID when a point is selected
    points_selected = pyqtSignal(list)  # Emits all selected point IDs for multi-select sync
    point_deselected = pyqtSignal()     # Emits when selection is cleared
    point_coordinate_clicked = pyqtSignal(float, float)  # Emits clicked data XY in plot CRS
    geodk_transect_requested = pyqtSignal(object)  # Emits [[x,y], ...] in plot/data CRS (UTM32)

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self._disable_hover_redraws = str(os.getenv("HEADANALYSER_DISABLE_HOVER_REDRAWS", "")).strip().lower() in {
            "1", "true", "yes", "on"
        }
        # Keep canvas clipped to the rounded frame to avoid square corner bleed-through.
        # Can be disabled for profiling/perf experiments.
        self._use_canvas_mask = str(os.getenv("HEADANALYSER_ENABLE_CANVAS_MASK", "1")).strip().lower() in {
            "1", "true", "yes", "on"
        }
        self._mplcursors = []
        self._mpl_cids = []
        self._selection_marker = None
        self._pinned_annotation = None
        self._hover_annotation = None
        self._hover_key = None
        self._mean_arrow_artist = None
        self._mean_arrow_info = None
        self._arrow_pinned_annotation = None
        self._highlight_artists = []
        self._selected_point = None  # dict with x,y,id,head,excluded
        self._2d_data_ref = None     # stored for highlight_point_by_id
        self._2d_set_selected_fn = None
        self._2d_set_selected_ids_fn = None
        self._2d_clear_selected_fn = None
        self._vector_data_ref = None  # stored for highlight_points_by_ids on vector plot
        self._vector_highlight_artists = []  # extra artists for multi-point vector highlight
        self._triangle_overlay_artists = []  # triangle polygon overlay
        self._static_label_artists = []  # static ID/head text artists on 2D plot
        self._compass_ax = None
        self._compass_parent_ax = None
        self._compass_xlim_cid = None
        self._compass_ylim_cid = None
        self._compass_view_text = None
        self._compass_show_center = False
        self._pan_hidden_texts = []
        self._last_coords_text = ""
        self._pending_mask_update = False
        self._last_mask_size = QSize(-1, -1)
        self._cross_section_mode = False
        self._cross_section_points = []
        self._cross_section_start_artist = None
        self._cross_section_end_artist = None
        self._cross_section_line_artist = None
        self._cross_section_dialog = None
        # Still used for the optional 1D strip under head-profile plot; the Geo.dk SVG viewer is separate.
        self._geology_provider = GeoDkSvgSurfaceGeologyProvider()
        self._stacked_panel_cluster = None
        self._stacked_panel_pending_id = None
        self._stacked_panel_select_cb = None
        self._stacked_panel_apply_cb = None
        self._stacked_panel_collapse_cb = None
        self._stacked_panel_radio_by_id = {}
        self._stacked_panel_row_by_id = {}
        self._stacked_panel_pill_by_id = {}

        # Ensure widget expands to fill available space
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self._setup_ui()

    def _setup_ui(self):
        self._dark_canvas = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(0)

        content_row = QHBoxLayout()
        content_row.setContentsMargins(0, 0, 0, 0)
        content_row.setSpacing(10)

        # Rounded canvas frame (provides border + rounded corners)
        self.canvas_frame = QFrame()
        self.canvas_frame.setObjectName("canvasFrame")
        self._apply_canvas_frame_style()

        frame_layout = QVBoxLayout(self.canvas_frame)
        frame_layout.setContentsMargins(1, 1, 1, 1)
        frame_layout.setSpacing(0)

        # Canvas fills all available space inside the rounded frame
        self.canvas = PlotCanvas(
            self,
            coords_callback=self._on_coords_changed,
            interaction_callback=self._on_canvas_pan_state_changed,
            click_callback=self._on_canvas_clicked,
        )
        frame_layout.addWidget(self.canvas, 1)

        content_row.addWidget(self.canvas_frame, 1)

        self._stacked_panel = self._create_stacked_intake_panel()
        self._stacked_panel.hide()
        content_row.addWidget(self._stacked_panel, 0)
        layout.addLayout(content_row, 1)

        # Allow keyboard shortcuts to work after interacting with the plot area.
        self.setFocusPolicy(Qt.StrongFocus)
        self.setFocusProxy(self.canvas)

        # Minimal toolbar (hidden by default, can be shown if needed)
        self.toolbar = NavigationToolbar(self.canvas, self)
        self.toolbar.setVisible(False)  # Hidden - using custom zoom/pan

        # Hint bar (layout-managed, sits below canvas_frame)
        self._hint_bar = HintBar()
        self._hint_bar.set_plot_type("2D")
        layout.addWidget(self._hint_bar, 0)

        self._mask_update_timer = QTimer(self)
        self._mask_update_timer.setSingleShot(True)
        self._mask_update_timer.timeout.connect(self._apply_deferred_canvas_mask)

        # Initialize with empty state
        self.clear_plot()
        if self._use_canvas_mask:
            self._schedule_canvas_mask_update()

    def _stacked_panel_stylesheet(self) -> str:
        header_glow = Colors.rgba(Colors.TEXT_INVERSE if Colors.is_dark() else Colors.TEXT_PRIMARY, 0.03 if Colors.is_dark() else 0.02)
        header_fade = Colors.rgba(Colors.TEXT_INVERSE if Colors.is_dark() else Colors.TEXT_PRIMARY, 0.0)
        radio_border = Colors.PLOT_AXIS if Colors.is_dark() else Colors.TEXT_TERTIARY
        return f"""
            QFrame#stackedIntakePanel {{
                background-color: {Colors.BG_PANEL};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 14px;
            }}
            QFrame#stackedPanelHeader {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {header_glow}, stop:1 {header_fade});
                border-bottom: 1px solid {Colors.BORDER_DEFAULT};
                border-top-left-radius: 14px;
                border-top-right-radius: 14px;
            }}
            QLabel#stackedPanelTitle {{
                color: {Colors.TEXT_SECONDARY};
                font-size: 12px;
                font-weight: 700;
                letter-spacing: 0.6px;
                text-transform: uppercase;
                background: transparent;
            }}
            QLabel#stackedPanelBadge {{
                background-color: {Colors.ACCENT_PRIMARY};
                color: {Colors.TEXT_INVERSE};
                font-size: 10px;
                font-weight: 700;
                padding: 3px 8px;
                border-radius: 9px;
            }}
            QLabel#stackedPanelInstr {{
                color: {Colors.TEXT_SECONDARY};
                font-size: 12px;
                font-weight: 700;
                letter-spacing: 0.4px;
                text-transform: uppercase;
                margin-bottom: 6px;
            }}
            QFrame#intakeRow {{
                background-color: {Colors.BG_SURFACE};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 10px;
            }}
            QFrame#intakeRow:hover {{
                border: 1px solid {Colors.BORDER_STRONG};
            }}
            QFrame#intakeRow[selected="true"] {{
                border: 1px solid {Colors.BORDER_ACCENT};
                background-color: {Colors.BG_SURFACE};
            }}
            QLabel#intakeTitle {{
                color: {Colors.TEXT_PRIMARY};
                font-size: 12px;
                font-weight: 700;
            }}
            QLabel#intakeMeta {{
                color: {Colors.TEXT_TERTIARY};
                font-size: 11px;
            }}
            QLabel#intakePill {{
                font-size: 10px;
                font-weight: 700;
                padding: 2px 8px;
                border-radius: 10px;
                min-width: 0px;
            }}
            QLabel#intakePill[state="selected"] {{
                background: {Colors.tint_surface(Colors.ACCENT_PRIMARY, dark_alpha=0.18, light_alpha=0.10)};
                color: {Colors.ACCENT_PRIMARY};
                border: 1px solid {Colors.BORDER_ACCENT};
            }}
            QLabel#intakePill[state="available"] {{
                background-color: transparent;
                color: {Colors.TEXT_TERTIARY};
                border: 1px solid {Colors.BORDER_DEFAULT};
            }}
            QRadioButton {{
                background: transparent;
            }}
            QRadioButton::indicator {{
                width: 14px;
                height: 14px;
                border-radius: 8px;
                border: 2px solid {radio_border};
                background: transparent;
            }}
            QRadioButton::indicator:checked {{
                border: 2px solid {Colors.ACCENT_PRIMARY};
                background: {Colors.ACCENT_PRIMARY};
                image: none;
            }}
            QPushButton {{
                background-color: {Colors.BG_ELEVATED};
                border: 1px solid {Colors.BORDER_STRONG};
                color: {Colors.TEXT_PRIMARY};
                font-size: 11px;
                font-weight: 700;
                border-radius: 8px;
                padding: 8px 12px;
            }}
            QPushButton:hover {{
                background-color: {Colors.BG_HOVER};
            }}
            QPushButton[primary="true"] {{
                background-color: {Colors.ACCENT_PRIMARY};
                color: {Colors.TEXT_INVERSE};
                border: 1px solid {Colors.ACCENT_PRIMARY};
            }}
            QPushButton[primary="true"]:hover {{
                background-color: {Colors.ACCENT_HOVER};
            }}
            QLabel#stackedPanelHint {{
                color: {Colors.TEXT_MUTED};
                font-size: 10px;
                background: transparent;
            }}
        """

    def _apply_stacked_panel_theme(self):
        if hasattr(self, "_stacked_panel") and self._stacked_panel is not None:
            self._stacked_panel.setStyleSheet(self._stacked_panel_stylesheet())
        if hasattr(self, "_stacked_panel_note") and self._stacked_panel_note is not None:
            self._stacked_panel_note.setStyleSheet(
                f"color: {Colors.TEXT_TERTIARY}; font-size: 11px; line-height: 1.4; margin-top: 4px;"
            )

    def _create_stacked_intake_panel(self):
        panel = QFrame()
        panel.setObjectName("stackedIntakePanel")
        panel.setFixedWidth(336)
        panel.setStyleSheet(self._stacked_panel_stylesheet())
        
        main_layout = QVBoxLayout(panel)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 1. Card Header
        header_frame = QFrame()
        header_frame.setObjectName("stackedPanelHeader")
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(16, 12, 16, 12)
        header_layout.setSpacing(10)
        
        self._stacked_panel_title = QLabel("STACKED INTAKE SELECTION")
        self._stacked_panel_title.setObjectName("stackedPanelTitle")
        
        self._stacked_panel_badge = QLabel("Calculation Target")
        self._stacked_panel_badge.setObjectName("stackedPanelBadge")
        
        header_layout.addWidget(self._stacked_panel_title)
        header_layout.addStretch(1)
        header_layout.addWidget(self._stacked_panel_badge)
        
        main_layout.addWidget(header_frame, 0)
        
        # 2. Body Content
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(16, 16, 16, 16)
        body_layout.setSpacing(12)
        
        # Subtitle / Instruction (Uppercase per concept)
        self._stacked_panel_subtitle = QLabel("CHOOSE INTAKE FOR CALCULATION")
        self._stacked_panel_subtitle.setObjectName("stackedPanelInstr")
        body_layout.addWidget(self._stacked_panel_subtitle)
        
        # List Container
        self._stacked_panel_list_wrap = QWidget()
        self._stacked_panel_list_layout = QVBoxLayout(self._stacked_panel_list_wrap)
        self._stacked_panel_list_layout.setContentsMargins(0, 0, 0, 0)
        self._stacked_panel_list_layout.setSpacing(8)
        body_layout.addWidget(self._stacked_panel_list_wrap, 1)
        
        # Action Buttons
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 8, 0, 0)
        btn_row.setSpacing(10)
        
        self._stacked_panel_apply_btn = QPushButton("Use Selected Intake")
        self._stacked_panel_apply_btn.setProperty("primary", True)
        self._stacked_panel_apply_btn.setCursor(Qt.PointingHandCursor)
        self._stacked_panel_apply_btn.setMinimumHeight(32)
        
        self._stacked_panel_collapse_btn = QPushButton("Collapse")
        self._stacked_panel_collapse_btn.setCursor(Qt.PointingHandCursor)
        self._stacked_panel_collapse_btn.setMinimumHeight(32)
        
        self._stacked_panel_collapse_btn.clicked.connect(self._on_stacked_panel_collapse)
        self._stacked_panel_apply_btn.clicked.connect(self._on_stacked_panel_apply)
        
        btn_row.addWidget(self._stacked_panel_apply_btn, 1)
        btn_row.addWidget(self._stacked_panel_collapse_btn, 0)
        
        body_layout.addLayout(btn_row)
        
        # Note / Hint
        self._stacked_panel_note = QLabel(
            "Selection changes gradient calculation target only. Stacked marker remains visually collapsed by default to keep the map clean."
        )
        self._stacked_panel_note.setWordWrap(True)
        body_layout.addWidget(self._stacked_panel_note)
    
        self._stacked_panel_hint = QLabel("Tip: click a displaced marker to select the intake directly.")
        self._stacked_panel_hint.setObjectName("stackedPanelHint")
        body_layout.addWidget(self._stacked_panel_hint)
        
        main_layout.addWidget(body, 1)
        self._apply_stacked_panel_theme()

        return panel

    def _clear_stacked_panel_list(self):
        lay = getattr(self, "_stacked_panel_list_layout", None)
        if lay is None:
            return
        while lay.count():
            item = lay.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _set_stacked_panel_selection(self, intake_key: str):
        self._stacked_panel_pending_id = str(intake_key or "").strip() or None
        self._refresh_stacked_panel_row_states()
        if callable(self._stacked_panel_select_cb) and self._stacked_panel_pending_id:
            try:
                self._stacked_panel_select_cb(self._stacked_panel_pending_id)
            except Exception:
                pass

    def _set_stacked_panel_pending_visual(self, intake_key: str):
        key = str(intake_key or "").strip()
        self._stacked_panel_pending_id = key or None
        rb = self._stacked_panel_radio_by_id.get(key)
        if rb is None:
            return
        try:
            rb.blockSignals(True)
            rb.setChecked(True)
        except Exception:
            pass
        finally:
            try:
                rb.blockSignals(False)
            except Exception:
                pass
        self._refresh_stacked_panel_row_states()

    def _refresh_stacked_panel_row_states(self):
        selected = str(self._stacked_panel_pending_id or "").strip()
        for pid, row in (self._stacked_panel_row_by_id or {}).items():
            is_sel = (str(pid) == selected)
            try:
                row.setProperty("selected", bool(is_sel))
                row.style().unpolish(row)
                row.style().polish(row)
            except Exception:
                pass
            pill = self._stacked_panel_pill_by_id.get(pid)
            if pill is not None:
                pill.setText("Selected" if is_sel else "Available")
                pill.setProperty("state", "selected" if is_sel else "available")
                pill.style().unpolish(pill)
                pill.style().polish(pill)

    def _show_stacked_intake_panel(self, cluster: dict, pending_id: str, on_select=None, on_apply=None, on_collapse=None):
        self._stacked_panel_cluster = dict(cluster or {})
        self._stacked_panel_pending_id = str(pending_id or "").strip() or None
        self._stacked_panel_select_cb = on_select
        self._stacked_panel_apply_cb = on_apply
        self._stacked_panel_collapse_cb = on_collapse

        self._clear_stacked_panel_list()
        self._stacked_panel_radio_by_id = {}
        self._stacked_panel_row_by_id = {}
        self._stacked_panel_pill_by_id = {}
        
        members = list((cluster or {}).get("members", []))
        
        # Subtitle update forced to CAPS as per concept
        self._stacked_panel_subtitle.setText("CHOOSE INTAKE FOR CALCULATION")

        group = QButtonGroup(self._stacked_panel)
        group.setExclusive(True)
        self._stacked_panel_radio_group = group
        
        id_seen = {}
        for i, p in enumerate(members):
            pid = str(p.get("id", ""))
            member_key = str(p.get("member_key", pid))
            top_v = p.get("top", None)
            bot_v = p.get("bottom", None)
            
            meta_parts = []
            if top_v is not None and np.isfinite(float(top_v)):
                meta_parts.append(f"Top {float(top_v):.2f} m")
            if bot_v is not None and np.isfinite(float(bot_v)):
                meta_parts.append(f"Bottom {float(bot_v):.2f} m")
            h_val = p.get('h', np.nan)
            if np.isfinite(h_val):
                meta_parts.append(f"Head {float(h_val):.3f} m")
            
            meta_txt = " • ".join(meta_parts)
            
            row = QFrame()
            row.setObjectName("intakeRow")
            row.setFixedHeight(52)  # Force compact height
            row.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(12, 0, 12, 0) # Zero vertical padding, rely on centering
            row_layout.setSpacing(10)
            row.setCursor(Qt.PointingHandCursor)

            rb = QRadioButton("")
            group.addButton(rb, i)
            row_layout.addWidget(rb, 0, Qt.AlignVCenter)

            text_col = QVBoxLayout()
            text_col.setContentsMargins(0, 11, 0, 11) # Center text within 52px height
            text_col.setSpacing(1) # Tight spacing
            id_seen[pid] = int(id_seen.get(pid, 0)) + 1
            intake_title = f"Intake {pid}"
            if id_seen[pid] > 1:
                intake_title = f"{intake_title} ({id_seen[pid]})"
            t1 = QLabel(intake_title)
            t1.setObjectName("intakeTitle")
            t2 = QLabel(meta_txt)
            t2.setObjectName("intakeMeta")
            text_col.addWidget(t1)
            text_col.addWidget(t2)
            row_layout.addLayout(text_col, 1)

            pill = QLabel("Available")
            pill.setObjectName("intakePill")
            pill.setAlignment(Qt.AlignCenter)
            pill.setFixedSize(60, 22) # Force pill size
            row_layout.addWidget(pill, 0, Qt.AlignVCenter)

            self._stacked_panel_list_layout.addWidget(row)
            self._stacked_panel_radio_by_id[member_key] = rb
            self._stacked_panel_row_by_id[member_key] = row
            self._stacked_panel_pill_by_id[member_key] = pill
            
            if member_key == self._stacked_panel_pending_id:
                rb.setChecked(True)
            
            rb.toggled.connect(lambda checked, _mkey=member_key: self._set_stacked_panel_selection(_mkey) if checked else None)
            row.mousePressEvent = lambda _evt, _rb=rb: _rb.setChecked(True)

        self._stacked_panel_list_layout.addStretch(1)
        self._refresh_stacked_panel_row_states()
        self._stacked_panel.show()

    def _hide_stacked_intake_panel(self):
        self._stacked_panel_cluster = None
        self._stacked_panel_pending_id = None
        self._stacked_panel_select_cb = None
        self._stacked_panel_apply_cb = None
        self._stacked_panel_collapse_cb = None
        self._stacked_panel_radio_by_id = {}
        self._stacked_panel_row_by_id = {}
        self._stacked_panel_pill_by_id = {}
        self._clear_stacked_panel_list()
        if hasattr(self, "_stacked_panel"):
            self._stacked_panel.hide()

    def _on_stacked_panel_apply(self):
        if callable(self._stacked_panel_apply_cb) and self._stacked_panel_pending_id:
            try:
                self._stacked_panel_apply_cb(self._stacked_panel_pending_id)
            except Exception:
                pass

    def _on_stacked_panel_collapse(self):
        if callable(self._stacked_panel_collapse_cb):
            try:
                self._stacked_panel_collapse_cb()
            except Exception:
                pass
        self._hide_stacked_intake_panel()

    def _request_interaction_draw(self, *, force: bool = False):
        canvas = getattr(self, "canvas", None)
        if canvas is None:
            return
        request_draw = getattr(canvas, "request_interaction_draw", None)
        if callable(request_draw):
            request_draw(force=force)
            return
        try:
            canvas.draw_idle()
        except Exception:
            pass

    def _apply_canvas_frame_style(self):
        """Style the rounded canvas frame based on current dark/light mode."""
        if self._dark_canvas:
            bg = Colors.PLOT_DARK_BG
            border = Colors.PLOT_DARK_BORDER
        else:
            bg = Colors.PLOT_BG
            border = Colors.PLOT_BORDER
        self.canvas_frame.setStyleSheet(f"""
            QFrame#canvasFrame {{
                background-color: {bg};
                border: 1px solid {border};
                border-radius: 10px;
            }}
        """)

    def set_dark_canvas(self, dark: bool):
        """Switch between dark and light plot canvas."""
        self._dark_canvas = dark
        self.canvas._dark = dark
        self.canvas._style_axes()
        self._apply_canvas_frame_style()

        # Update the figure facecolor (area around axes)
        if dark:
            self.canvas.fig.set_facecolor(Colors.PLOT_DARK_BG)
        else:
            self.canvas.fig.set_facecolor(Colors.PLOT_BG)
        self.canvas.draw_idle()

    def apply_theme(self):
        self._apply_canvas_frame_style()
        self._apply_stacked_panel_theme()
        self._hint_bar.apply_theme()
        self.set_dark_canvas(self._dark_canvas)

    def _on_coords_changed(self, x, y):
        """Handle coordinate updates from canvas."""
        if hasattr(self.main_window, 'status_coords_label'):
            text = f"X: {x:.1f}, Y: {y:.1f}"
            if text != self._last_coords_text:
                self._last_coords_text = text
                self.main_window.status_coords_label.setText(text)

    def _on_canvas_pan_state_changed(self, active: bool):
        """Temporarily hide expensive text artists during pan for smoother interaction."""
        ax = getattr(self.canvas, "ax", None)
        if ax is None:
            return

        if active:
            self._pan_hidden_texts = [t for t in getattr(ax, "texts", []) if t.get_visible()]
            if not self._pan_hidden_texts:
                return
            for t in self._pan_hidden_texts:
                try:
                    t.set_visible(False)
                except Exception:
                    pass
            self._request_interaction_draw(force=True)
            return

        if not self._pan_hidden_texts:
            return
        for t in self._pan_hidden_texts:
            try:
                t.set_visible(True)
            except Exception:
                pass
        self._pan_hidden_texts = []
        self._request_interaction_draw(force=True)

    def _on_canvas_clicked(self, x, y):
        """Emit clicked data coordinate from plot canvas."""
        try:
            self.point_coordinate_clicked.emit(float(x), float(y))
        except Exception:
            return

    def _schedule_canvas_mask_update(self):
        if not self._use_canvas_mask:
            return
        self._pending_mask_update = True
        self._mask_update_timer.start(90)

    def _apply_deferred_canvas_mask(self):
        if not self._pending_mask_update:
            return
        self._pending_mask_update = False
        self._update_canvas_mask()

    def _update_canvas_mask(self):
        """Clip the canvas to a rounded rect matching the frame's inner radius."""
        if not self._use_canvas_mask:
            return
        r = self.canvas.rect()
        if r.width() < 1 or r.height() < 1:
            return
        size = r.size()
        if size == self._last_mask_size:
            return
        self._last_mask_size = QSize(size)
        path = QPainterPath()
        # Inner radius = frame border-radius (10) minus border width (1) = 9
        path.addRoundedRect(QRectF(r), 9, 9)
        self.canvas.setMask(QRegion(path.toFillPolygon().toPolygon()))

    def resizeEvent(self, event):
        """Handle parent resize and reposition canvas overlays."""
        super().resizeEvent(event)
        # Clip canvas to match frame's rounded corners
        if self._use_canvas_mask and hasattr(self, 'canvas'):
            self._schedule_canvas_mask_update()

    @property
    def figure(self):
        return self.canvas.fig

    @property
    def ax(self):
        return self.canvas.ax

    def clear_plot(self):
        """Clear the current plot."""
        self.canvas.clear()

    def update_plot(self, data, plot_type):
        """Update the plot based on data and type."""
        plot_type = normalize_plot_type(plot_type)
        self._clear_plot_interactivity()
        self.canvas.ax.clear()
        self.canvas._style_axes()

        # Update hint bar for this plot type
        self.set_hint_plot_type(plot_type)

        if data is None or data.empty:
            self._sync_compass_overlay()
            self.canvas.request_tight_layout()
            return

        # Get column mappings
        col_map = self.main_window.col_mapping
        x_col = col_map.get('x')
        y_col = col_map.get('y')
        h_col = col_map.get('hydraulic head')
        id_col = col_map.get('ID')

        if not all([x_col, y_col, h_col]):
            self._sync_compass_overlay()
            self.canvas.request_tight_layout()
            return

        # Draw based on plot type
        if plot_type == "2D":
            self._draw_2d_plot(data, x_col, y_col, h_col, id_col)
        elif plot_type == "3D":
            self._draw_3d_plot(data, x_col, y_col, h_col)
        elif plot_type == "Gradient Vectors":
            self._draw_gradient_vectors(data, x_col, y_col)
        elif plot_type == "Histogram":
            self._draw_histogram()
        elif plot_type == "Rose Diagram":
            self._draw_rose_diagram()

        self._sync_compass_overlay()
        self.canvas.request_tight_layout()

    def _clear_plot_interactivity(self):
        for cid in self._mpl_cids:
            try:
                self.canvas.mpl_disconnect(cid)
            except Exception:
                pass
        self._mpl_cids = []

        for cursor in self._mplcursors:
            try:
                cursor.remove()
            except Exception:
                pass
        self._mplcursors = []

        for artist in self._highlight_artists:
            try:
                artist.remove()
            except Exception:
                pass
        self._highlight_artists = []
        self._clear_static_labels()
        self._clear_compass_overlay()

        self._selection_marker = None
        self._pinned_annotation = None
        self._hover_annotation = None
        self._hover_key = None
        self._mean_arrow_artist = None
        self._mean_arrow_info = None
        self._arrow_pinned_annotation = None
        self._selected_point = None
        self._2d_data_ref = None
        self._2d_set_selected_fn = None
        self._2d_set_selected_ids_fn = None
        self._2d_clear_selected_fn = None
        self._vector_data_ref = None
        self._cross_section_mode = False
        self._cross_section_points = []
        self._clear_cross_section_artists()
        self._hide_stacked_intake_panel()
        for a in getattr(self, '_vector_highlight_artists', []):
            try:
                a.remove()
            except Exception:
                pass
        self._vector_highlight_artists = []

    def _popup_bbox(self):
        from styles.plot_styles import PopupStyles
        popup_style = getattr(self.main_window, 'current_popup_style', 'Clean')
        return PopupStyles.get_bbox(popup_style)

    def _popup_create(self, ax, *, zorder: int = 30, xytext=(12, 12), va: str = "bottom"):
        from styles.plot_styles import PopupStyles
        popup_style = getattr(self.main_window, 'current_popup_style', 'Clean')
        ann = ax.annotate(
            "",
            xy=(0, 0),
            xytext=xytext,
            textcoords="offset points",
            ha="left",
            va=va,
            fontsize=PopupStyles.get_fontsize(popup_style),
            color=PopupStyles.get_text_color(popup_style),
            bbox=self._popup_bbox(),
            zorder=zorder,
        )
        ann.set_visible(False)
        return ann

    @staticmethod
    def _popup_compose(title: str, lines=None) -> str:
        out = [str(title or "").strip() or "Details"]
        for raw in (lines or []):
            txt = str(raw).strip()
            if txt:
                out.append(txt)
        return "\n".join(out)

    @staticmethod
    def _angle_to_cardinal(angle_deg: float) -> str:
        """Convert angle in degrees CCW from East (+X) to compass abbreviation."""
        a = float(angle_deg) % 360
        dirs = ['E', 'NE', 'N', 'NW', 'W', 'SW', 'S', 'SE']
        return dirs[int((a + 22.5) / 45) % 8]

    def _bootstrap_ci(self, values, stat_fn, level_pct: float = 95.0, resamples: int = 200, max_points: int = 5000):
        try:
            arr = np.asarray(values, dtype=float)
        except Exception:
            return None

        arr = arr[np.isfinite(arr)]
        if arr.size < 2:
            return None

        try:
            level_pct = float(level_pct)
        except Exception:
            level_pct = 95.0
        level_pct = float(np.clip(level_pct, 50.0, 99.9))

        try:
            resamples = int(resamples)
        except Exception:
            resamples = 200
        resamples = int(np.clip(resamples, 50, 2000))

        if arr.size > int(max_points):
            rng = np.random.default_rng(12345)
            arr = rng.choice(arr, size=int(max_points), replace=False)

        rng = np.random.default_rng(12345)
        n = arr.size
        stats = np.empty(resamples, dtype=float)
        for i in range(resamples):
            sample = rng.choice(arr, size=n, replace=True)
            try:
                stats[i] = float(stat_fn(sample))
            except Exception:
                stats[i] = np.nan

        stats = stats[np.isfinite(stats)]
        if stats.size < 2:
            return None

        alpha = 1.0 - (level_pct / 100.0)
        lo_q = 100.0 * (alpha / 2.0)
        hi_q = 100.0 * (1.0 - alpha / 2.0)
        lo = float(np.percentile(stats, lo_q))
        hi = float(np.percentile(stats, hi_q))
        return lo, hi

    def _circular_diff_deg(self, a_deg: float, b_deg: float) -> float:
        return float(((a_deg - b_deg + 180.0) % 360.0) - 180.0)

    def _circular_mean_deg(self, angles_deg, weights=None):
        angles = np.asarray(angles_deg, dtype=float) % 360.0
        rad = np.deg2rad(angles)

        if weights is None:
            sin_mean = float(np.mean(np.sin(rad)))
            cos_mean = float(np.mean(np.cos(rad)))
        else:
            w = np.asarray(weights, dtype=float)
            mask = np.isfinite(angles) & np.isfinite(w)
            angles = angles[mask]
            rad = np.deg2rad(angles)
            w = w[mask]
            if w.size == 0:
                return None
            w_sum = float(np.sum(w))
            if not np.isfinite(w_sum) or w_sum <= 0:
                w = np.ones_like(w, dtype=float) / float(w.size)
            else:
                w = w / w_sum
            sin_mean = float(np.sum(w * np.sin(rad)))
            cos_mean = float(np.sum(w * np.cos(rad)))

        if not np.isfinite(sin_mean) or not np.isfinite(cos_mean):
            return None
        return float(np.degrees(np.arctan2(sin_mean, cos_mean)) % 360.0)

    def _bootstrap_circular_ci(self, angles_deg, point_estimate_deg: float, level_pct: float = 95.0, resamples: int = 200, weights=None, max_points: int = 5000):
        try:
            ang = np.asarray(angles_deg, dtype=float)
        except Exception:
            return None

        if weights is None:
            mask = np.isfinite(ang)
            ang = ang[mask]
            w = None
        else:
            w = np.asarray(weights, dtype=float)
            mask = np.isfinite(ang) & np.isfinite(w)
            ang = ang[mask]
            w = w[mask]

        if ang.size < 3:
            return None

        try:
            level_pct = float(level_pct)
        except Exception:
            level_pct = 95.0
        level_pct = float(np.clip(level_pct, 50.0, 99.9))

        try:
            resamples = int(resamples)
        except Exception:
            resamples = 200
        resamples = int(np.clip(resamples, 50, 2000))

        if ang.size > int(max_points):
            rng = np.random.default_rng(12345)
            idx = rng.choice(np.arange(ang.size), size=int(max_points), replace=False)
            ang = ang[idx]
            if w is not None:
                w = w[idx]

        rng = np.random.default_rng(12345)
        n = ang.size
        diffs = np.empty(resamples, dtype=float)
        for i in range(resamples):
            sample_idx = rng.integers(0, n, size=n)
            if w is None:
                m = self._circular_mean_deg(ang[sample_idx])
            else:
                m = self._circular_mean_deg(ang[sample_idx], weights=w[sample_idx])
            if m is None:
                diffs[i] = np.nan
            else:
                diffs[i] = self._circular_diff_deg(float(m), float(point_estimate_deg))

        diffs = diffs[np.isfinite(diffs)]
        if diffs.size < 3:
            return None

        alpha = 1.0 - (level_pct / 100.0)
        lo_q = 100.0 * (alpha / 2.0)
        hi_q = 100.0 * (1.0 - alpha / 2.0)
        lo_d = float(np.percentile(diffs, lo_q))
        hi_d = float(np.percentile(diffs, hi_q))
        lo = float((float(point_estimate_deg) + lo_d) % 360.0)
        hi = float((float(point_estimate_deg) + hi_d) % 360.0)
        return lo, hi

    def _apply_square_geo_axes(self, ax):
        """Keep geospatial plots visually square while preserving 1:1 data scaling."""
        try:
            # Preferred behavior: fixed square axes box + equal data units.
            if hasattr(ax, "set_box_aspect"):
                ax.set_box_aspect(1.0)
                ax.set_aspect("equal", adjustable="datalim")
            else:
                # Fallback for older Matplotlib.
                ax.set_aspect("equal", adjustable="box")
            ax.set_anchor("C")
        except Exception:
            try:
                ax.set_aspect("equal")
            except Exception:
                pass

    @staticmethod
    def _nice_125_step(value: float) -> float:
        """Round a positive value to a 1-2-5 engineering step."""
        if not np.isfinite(value) or value <= 0:
            return 1.0
        exponent = float(np.floor(np.log10(value)))
        base = 10.0 ** exponent
        scaled = value / base
        if scaled <= 1.0:
            nice = 1.0
        elif scaled <= 2.0:
            nice = 2.0
        elif scaled <= 5.0:
            nice = 5.0
        else:
            nice = 10.0
        return float(nice * base)

    def _apply_synced_geo_major_ticks(self, ax):
        """Optional engineering-style tick consistency for geospatial axes."""
        if not bool(getattr(self.main_window, "sync_xy_major_ticks", False)):
            return

        def infer_step(ticks):
            arr = np.asarray(ticks, dtype=float)
            if arr.size < 2:
                return None
            diffs = np.diff(np.sort(arr))
            diffs = diffs[np.isfinite(diffs) & (diffs > 0)]
            if diffs.size == 0:
                return None
            return float(np.median(diffs))

        try:
            x_step = infer_step(ax.get_xticks())
            y_step = infer_step(ax.get_yticks())
            candidates = [v for v in (x_step, y_step) if v is not None and np.isfinite(v) and v > 0]
            if not candidates:
                return

            step = self._nice_125_step(max(candidates))
            if not np.isfinite(step) or step <= 0:
                return

            ax.xaxis.set_major_locator(MultipleLocator(base=step))
            ax.yaxis.set_major_locator(MultipleLocator(base=step))
        except Exception:
            pass

    def _clear_cross_section_artists(self):
        for artist_name in (
            "_cross_section_start_artist",
            "_cross_section_end_artist",
            "_cross_section_line_artist",
        ):
            artist = getattr(self, artist_name, None)
            if artist is not None:
                try:
                    artist.remove()
                except Exception:
                    pass
            setattr(self, artist_name, None)

    def _update_cross_section_artists(self, ax, preview_xy=None):
        self._clear_cross_section_artists()
        points = list(getattr(self, "_cross_section_points", []) or [])
        if not points:
            self._request_interaction_draw(force=True)
            return

        p0 = points[0]
        self._cross_section_start_artist = ax.scatter(
            [p0[0]],
            [p0[1]],
            s=70,
            c=Colors.ACCENT_PRIMARY,
            edgecolors="white",
            linewidths=1.1,
            zorder=24,
        )

        if len(points) >= 2:
            p1 = points[1]
            self._cross_section_end_artist = ax.scatter(
                [p1[0]],
                [p1[1]],
                s=70,
                c=Colors.ACCENT_BRIGHT,
                edgecolors="white",
                linewidths=1.1,
                zorder=24,
            )
            self._cross_section_line_artist, = ax.plot(
                [p0[0], p1[0]],
                [p0[1], p1[1]],
                linestyle="-",
                color=Colors.ACCENT_PRIMARY,
                linewidth=1.8,
                alpha=0.95,
                zorder=23,
            )
        elif preview_xy is not None:
            self._cross_section_line_artist, = ax.plot(
                [p0[0], float(preview_xy[0])],
                [p0[1], float(preview_xy[1])],
                linestyle="--",
                color=Colors.ACCENT_PRIMARY,
                linewidth=1.4,
                alpha=0.9,
                zorder=23,
            )

        self._request_interaction_draw(force=True)

    def _compute_cross_section_profile(self, data, x_col, y_col, h_col, p0, p1, samples=180):
        x = pd.to_numeric(data[x_col], errors="coerce").to_numpy(dtype=float)
        y = pd.to_numeric(data[y_col], errors="coerce").to_numpy(dtype=float)
        h = pd.to_numeric(data[h_col], errors="coerce").to_numpy(dtype=float)
        valid = np.isfinite(x) & np.isfinite(y) & np.isfinite(h)
        x = x[valid]
        y = y[valid]
        h = h[valid]
        if x.size < 3:
            return None

        p0 = (float(p0[0]), float(p0[1]))
        p1 = (float(p1[0]), float(p1[1]))
        line_len = float(np.hypot(p1[0] - p0[0], p1[1] - p0[1]))
        if not np.isfinite(line_len) or line_len <= 0.0:
            return None

        t = np.linspace(0.0, 1.0, int(max(40, samples)))
        xs = p0[0] + (p1[0] - p0[0]) * t
        ys = p0[1] + (p1[1] - p0[1]) * t
        dist = t * line_len

        heads = None
        try:
            from scipy.interpolate import griddata

            method = str(getattr(self.main_window, "interpolation_method", "linear") or "linear").lower()
            if method not in {"nearest", "linear", "cubic"}:
                method = "linear"

            heads = griddata((x, y), h, (xs, ys), method=method)
            if heads is None:
                heads = griddata((x, y), h, (xs, ys), method="linear")
            if heads is not None and np.isnan(heads).any():
                near = griddata((x, y), h, (xs, ys), method="nearest")
                heads = np.where(np.isnan(heads), near, heads)
        except Exception:
            heads = None

        if heads is None or not np.isfinite(heads).any():
            try:
                dx = xs[:, None] - x[None, :]
                dy = ys[:, None] - y[None, :]
                d2 = dx * dx + dy * dy
                d2 = np.maximum(d2, 1e-12)
                w = 1.0 / d2
                heads = (w @ h) / np.sum(w, axis=1)
            except Exception:
                return None

        heads = np.asarray(heads, dtype=float)
        if heads.size != dist.size:
            return None
        return {
            "distance": dist,
            "head": heads,
            "p0": p0,
            "p1": p1,
            "length": line_len,
        }

    def _compute_stacked_clusters(self, data, x_col, y_col, h_col, id_col):
        """Group points sharing the same (or near-same) XY for stacked-point UX."""
        if data is None or getattr(data, "empty", True):
            return []
        if not all(c in data.columns for c in (x_col, y_col, h_col, id_col)):
            return []

        try:
            eps = float(getattr(self.main_window, "gradient_stacked_epsilon", 1e-10))
        except Exception:
            eps = 1e-10
        if not np.isfinite(eps) or eps <= 0:
            eps = 1e-10

        try:
            x = pd.to_numeric(data[x_col], errors="coerce").to_numpy(dtype=float)
            y = pd.to_numeric(data[y_col], errors="coerce").to_numpy(dtype=float)
            h = pd.to_numeric(data[h_col], errors="coerce").to_numpy(dtype=float)
            ids = data[id_col].astype(str).to_numpy()
        except Exception:
            return []
        top_col = getattr(self.main_window, "top_column", None)
        bottom_col = getattr(self.main_window, "bottom_column", None)
        top_vals = None
        bot_vals = None
        if top_col and top_col in data.columns:
            top_vals = pd.to_numeric(data[top_col], errors="coerce").to_numpy(dtype=float)
        if bottom_col and bottom_col in data.columns:
            bot_vals = pd.to_numeric(data[bottom_col], errors="coerce").to_numpy(dtype=float)

        valid = np.isfinite(x) & np.isfinite(y) & np.isfinite(h)
        if not np.any(valid):
            return []

        row_keys = data.index.astype(str).to_numpy()
        x = x[valid]
        y = y[valid]
        h = h[valid]
        ids = ids[valid]
        row_keys = row_keys[valid]
        if top_vals is not None:
            top_vals = top_vals[valid]
        if bot_vals is not None:
            bot_vals = bot_vals[valid]

        qx = np.round(x / eps).astype(np.int64)
        qy = np.round(y / eps).astype(np.int64)

        groups = {}
        for i in range(x.size):
            key = (int(qx[i]), int(qy[i]))
            groups.setdefault(key, []).append(i)

        clusters = []
        for grp_key, idxs in groups.items():
            if len(idxs) < 2:
                continue
            member_points = []
            for i in idxs:
                top_v = float(top_vals[i]) if top_vals is not None and np.isfinite(top_vals[i]) else None
                bot_v = float(bot_vals[i]) if bot_vals is not None and np.isfinite(bot_vals[i]) else None
                member_points.append(
                    {
                        "id": str(ids[i]),
                        "member_key": f"{str(ids[i])}::{str(row_keys[i])}",
                        "x": float(x[i]),
                        "y": float(y[i]),
                        "h": float(h[i]),
                        "top": top_v,
                        "bottom": bot_v,
                    }
                )
            cx = float(np.mean([p["x"] for p in member_points]))
            cy = float(np.mean([p["y"] for p in member_points]))
            clusters.append(
                {
                    "key": (int(grp_key[0]), int(grp_key[1])),
                    "center_x": cx,
                    "center_y": cy,
                    "members": member_points,
                    "count": len(member_points),
                }
            )
        return clusters

    def _choose_stacked_intake_dialog(self, members):
        """Prompt user to choose which intake in a stacked cluster should drive calculations."""
        if not members:
            return None
        dlg = QDialog(self.main_window)
        dlg.setWindowTitle("Choose Intake For Calculation")
        dlg.setModal(True)
        dlg.resize(430, 220)
        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title = QLabel("Stacked point detected. Select one intake to keep active for calculations:")
        title.setWordWrap(True)
        title.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; font-size: 12px;")
        layout.addWidget(title)

        group = QButtonGroup(dlg)
        excluded_ids = {str(v) for v in getattr(self.main_window, "excluded_ids", set())}
        default_btn = None
        for i, p in enumerate(members):
            pid = str(p.get("id", ""))
            depth_bits = []
            top_v = p.get("top", None)
            bot_v = p.get("bottom", None)
            if top_v is not None:
                depth_bits.append(f"top={top_v:.2f}")
            if bot_v is not None:
                depth_bits.append(f"bottom={bot_v:.2f}")
            depth_txt = f" | {' , '.join(depth_bits)}" if depth_bits else ""
            txt = f"Intake {pid} | head={float(p.get('h', np.nan)):.3f}{depth_txt}"
            rb = QRadioButton(txt)
            rb.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 11px;")
            group.addButton(rb, i)
            layout.addWidget(rb)
            if default_btn is None and pid not in excluded_ids:
                default_btn = rb
        if default_btn is None:
            default_btn = group.buttons()[0] if group.buttons() else None
        if default_btn is not None:
            default_btn.setChecked(True)

        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 6, 0, 0)
        btn_row.addStretch(1)
        cancel_btn = QPushButton("Cancel")
        apply_btn = QPushButton("Use Selected Intake")
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(apply_btn)
        layout.addLayout(btn_row)

        selected = {"id": None}

        def on_apply():
            idx = group.checkedId()
            if idx < 0 or idx >= len(members):
                dlg.reject()
                return
            selected["id"] = str(members[idx].get("id", ""))
            dlg.accept()

        cancel_btn.clicked.connect(dlg.reject)
        apply_btn.clicked.connect(on_apply)

        try:
            if dlg.exec_() == QDialog.Accepted:
                return selected["id"]
            return None
        finally:
            dlg.deleteLater()

    def _cross_section_depth_context(self, data):
        top_col = getattr(self.main_window, "top_column", None)
        bottom_col = getattr(self.main_window, "bottom_column", None)
        has_top = bool(top_col and top_col in data.columns)
        has_bottom = bool(bottom_col and bottom_col in data.columns)
        has_depth = bool(has_top or has_bottom)
        info = {
            "has_depth_data": has_depth,
            "top_column": top_col if has_top else None,
            "bottom_column": bottom_col if has_bottom else None,
        }
        if has_depth:
            bounds = []
            for col in (top_col, bottom_col):
                if col and col in data.columns:
                    vals = pd.to_numeric(data[col], errors="coerce").to_numpy(dtype=float)
                    vals = vals[np.isfinite(vals)]
                    if vals.size:
                        bounds.extend([float(np.min(vals)), float(np.max(vals))])
            if bounds:
                info["depth_min"] = float(np.min(bounds))
                info["depth_max"] = float(np.max(bounds))
        return info

    def _sample_cross_section_geology(self, profile, data):
        if not bool(getattr(self.main_window, "show_geology_strip_experimental", False)):
            return None
        provider = getattr(self, "_geology_provider", None)
        if provider is None:
            return None
        dist = np.asarray(profile.get("distance", []), dtype=float)
        if dist.size < 2:
            return None
        ctx = self._cross_section_depth_context(data)
        try:
            return provider.sample_transect(distances_m=dist, context=ctx)
        except Exception:
            return {
                "provider": "error",
                "available": False,
                "segments": [],
                "notes": ["Geology provider call failed."],
            }

    def _show_cross_section_dialog(self, profile, geology=None):
        if not isinstance(profile, dict):
            return

        if self._cross_section_dialog is None:
            self._cross_section_dialog = QDialog(self.main_window)
            self._cross_section_dialog.setWindowTitle("Cross-Section Profile")
            self._cross_section_dialog.resize(980, 640)
            self._cross_section_dialog.setModal(False)

            layout = QVBoxLayout(self._cross_section_dialog)
            layout.setContentsMargins(10, 10, 10, 10)
            layout.setSpacing(8)

            tabs = QTabWidget(self._cross_section_dialog)
            layout.addWidget(tabs, 1)

            # Head profile tab (existing behavior)
            head_tab = QWidget(tabs)
            head_layout = QVBoxLayout(head_tab)
            head_layout.setContentsMargins(0, 0, 0, 0)
            head_layout.setSpacing(8)
            fig = Figure(dpi=110, facecolor="white")
            canvas = FigureCanvas(fig)
            head_layout.addWidget(canvas, 1)
            tabs.addTab(head_tab, "Head Profile")

            # Geo.dk tab (same panel logic as map geology panel)
            geodk_tab = QWidget(tabs)
            geodk_layout = QVBoxLayout(geodk_tab)
            geodk_layout.setContentsMargins(0, 0, 0, 0)
            geodk_layout.setSpacing(0)
            geodk_panel = GeoDKPanelWidget(parent=geodk_tab, dataset_id=str(getattr(self, "_dataset_id", "") or ""))
            geodk_layout.addWidget(geodk_panel, 1)
            tabs.addTab(geodk_tab, "Geo.dk")

            footer = QHBoxLayout()
            footer.setContentsMargins(0, 0, 0, 0)
            footer.setSpacing(8)
            info = QLabel("")
            info.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 11px;")
            footer.addWidget(info, 1)
            close_btn = QPushButton("Close")
            close_btn.clicked.connect(self._cross_section_dialog.close)
            footer.addWidget(close_btn, 0)
            layout.addLayout(footer)

            self._cross_section_dialog._profile_fig = fig
            self._cross_section_dialog._profile_canvas = canvas
            self._cross_section_dialog._profile_info = info
            self._cross_section_dialog._geodk_panel = geodk_panel
            self._cross_section_dialog._tabs = tabs

            # Wire Geo.dk panel -> main window handlers (same as map widget uses).
            try:
                geodk_panel.geodkFetchRequested.connect(self.main_window._on_plot_geodk_fetch_requested)
                geodk_panel.geodkCredentialsRequested.connect(self.main_window._on_map_geodk_credentials_requested)
                geodk_panel.geodkDownloadRequested.connect(self.main_window._on_plot_geodk_download_requested)
                geodk_panel.geodkCopyReproRequested.connect(self.main_window._on_plot_geodk_copy_repro_requested)
            except Exception:
                pass

        fig = self._cross_section_dialog._profile_fig
        canvas = self._cross_section_dialog._profile_canvas
        info = self._cross_section_dialog._profile_info

        dist = np.asarray(profile.get("distance", []), dtype=float)
        head = np.asarray(profile.get("head", []), dtype=float)
        valid = np.isfinite(dist) & np.isfinite(head)

        fig.clear()
        use_geology_strip = bool(isinstance(geology, dict) and geology.get("available") and geology.get("segments"))
        if use_geology_strip:
            gs = fig.add_gridspec(2, 1, height_ratios=[4.0, 1.2], hspace=0.14)
            ax = fig.add_subplot(gs[0, 0])
            gax = fig.add_subplot(gs[1, 0], sharex=ax)
        else:
            ax = fig.add_subplot(111)
            gax = None

        if np.count_nonzero(valid) >= 2:
            ax.plot(dist[valid], head[valid], color=Colors.ACCENT_PRIMARY, linewidth=1.8)
            ax.scatter(
                [dist[valid][0], dist[valid][-1]],
                [head[valid][0], head[valid][-1]],
                c=[Colors.ACCENT_PRIMARY, Colors.ACCENT_BRIGHT],
                s=24,
                zorder=4,
            )
            ax.grid(True, linestyle=":", linewidth=0.8, alpha=0.35)
            ax.set_xlabel("Distance Along Transect [m]", color=Colors.PLOT_TEXT)
            ax.set_ylabel("Hydraulic Head", color=Colors.PLOT_TEXT)
            ax.set_title("Cross-Section Profile", color=Colors.PLOT_TEXT, fontsize=11, fontweight="600")
        else:
            ax.text(
                0.5,
                0.5,
                "Unable to generate profile for this transect",
                ha="center",
                va="center",
                transform=ax.transAxes,
                fontsize=11,
                color=Colors.PLOT_TEXT,
            )
            ax.set_axis_off()

        if gax is not None:
            segments = list(geology.get("segments", []))
            for seg in segments:
                try:
                    x0 = float(seg.start_m)
                    x1 = float(seg.end_m)
                    color = str(seg.color)
                    code = str(seg.layer_code)
                except Exception:
                    continue
                gax.axvspan(x0, x1, ymin=0.0, ymax=1.0, facecolor=color, alpha=0.88, linewidth=0.0)
                if (x1 - x0) > 0.08 * max(1e-9, float(np.nanmax(dist) - np.nanmin(dist))):
                    gax.text(
                        0.5 * (x0 + x1),
                        0.5,
                        code,
                        ha="center",
                        va="center",
                        fontsize=9,
                        color="#1a1a1f",
                        fontweight="600",
                    )
            gax.set_ylim(0.0, 1.0)
            gax.set_yticks([])
            gax.set_ylabel("Layers", color=Colors.PLOT_TEXT, fontsize=9)
            gax.grid(False)
            for sp in gax.spines.values():
                sp.set_color("#cfd3da")
                sp.set_linewidth(0.8)
            gax.set_xlabel("Distance Along Transect [m]", color=Colors.PLOT_TEXT)
            ax.tick_params(labelbottom=False)
        else:
            ax.set_xlabel("Distance Along Transect [m]", color=Colors.PLOT_TEXT)

        p0 = profile.get("p0", (np.nan, np.nan))
        p1 = profile.get("p1", (np.nan, np.nan))
        length = float(profile.get("length", float("nan")))
        status = f"Line length: {length:.2f} m | Start: ({p0[0]:.2f}, {p0[1]:.2f}) | End: ({p1[0]:.2f}, {p1[1]:.2f})"
        if isinstance(geology, dict):
            notes = [str(n) for n in geology.get("notes", []) if str(n).strip()]
            if notes:
                status = f"{status} | {notes[0]}"
        info.setText(status)
        canvas.draw_idle()

        self._cross_section_dialog.show()
        self._cross_section_dialog.raise_()
        self._cross_section_dialog.activateWindow()

    def _apply_plot_settings(self, ax, *, polar: bool = False, is_3d: bool = False):
        """Apply user-controlled settings on top of the baseline theme.

        Two-layer theming — call both at the top of every draw function:
            self.canvas._apply_axis_theme(ax, self.canvas.fig, polar=polar, is_3d=is_3d)
            self._apply_plot_settings(ax, polar=polar, is_3d=is_3d)

        Layer 1 (_apply_axis_theme): aesthetic defaults — white bg, spine shape,
            tick direction, font weight. Lives on PlotCanvas.
        Layer 2 (_apply_plot_settings): user-facing settings - chosen format
            (Default/Minimal/Scientific/Publication) and the grid on/off toggle.
            Lives on PlotWidget (has access to main_window).
        """
        from styles.plot_styles import PlotStyles
        current_style = getattr(
            self.main_window,
            'current_plot_format',
            getattr(self.main_window, 'current_plot_style', 'Default'),
        )
        show_grid = bool(getattr(self.main_window, 'show_grid', True))

        # Style: typography, spine colour, etc.  Skip for 3D (limited mpl support).
        if not is_3d:
            PlotStyles.apply_to_axes(ax, current_style)

        # Grid: honour the user toggle; strip 'axis' kwarg for polar axes.
        if show_grid and not is_3d:
            grid_props = PlotStyles.get_grid_props(current_style)
            if polar:
                grid_props = {k: v for k, v in grid_props.items() if k != 'axis'}
            ax.grid(True, **grid_props)
        else:
            ax.grid(False)

    def _draw_2d_plot(self, data, x_col, y_col, h_col, id_col):
        """Draw 2D contour and scatter plot."""
        # Ensure we have 2D axes (not 3D or polar)
        self.canvas.fig.clear()
        ax = self.canvas.fig.add_subplot(111)
        self.canvas.ax = ax
        self.canvas._apply_axis_theme(ax, self.canvas.fig)
        self._apply_plot_settings(ax)

        # Check for excluded points
        excluded_ids = getattr(self.main_window, 'excluded_ids', set())
        excluded_ids_str = {str(v) for v in excluded_ids}
        excluded_member_keys = {str(v) for v in getattr(self.main_window, 'excluded_member_keys', set())}
        show_excluded_points = bool(getattr(self.main_window, 'show_excluded_points', True))
        custom_excluded_style = bool(getattr(self.main_window, 'custom_excluded_style', False))
        excluded_marker = str(getattr(self.main_window, 'excluded_marker', 'x') or 'x')
        excluded_color = str(getattr(self.main_window, 'excluded_color', '#6a6a6a') or '#6a6a6a')
        try:
            excluded_alpha = float(getattr(self.main_window, 'excluded_opacity', 0.3))
        except Exception:
            excluded_alpha = 0.3
        excluded_alpha = float(np.clip(excluded_alpha, 0.0, 1.0))
        try:
            excluded_size_scale = float(getattr(self.main_window, 'excluded_size_scale', 0.75))
        except Exception:
            excluded_size_scale = 0.75
        if excluded_size_scale <= 0:
            excluded_size_scale = 0.75

        scatter_excluded = None
        has_any_exclusions = bool(excluded_ids_str or excluded_member_keys)
        if has_any_exclusions and id_col and id_col in data.columns:
            # Separate data into included and excluded
            id_series = data[id_col].astype(str)
            member_key_series = id_series + "::" + data.index.astype(str)
            excluded_mask = id_series.isin(excluded_ids_str)
            if excluded_member_keys:
                excluded_mask = excluded_mask | member_key_series.isin(excluded_member_keys)
            included_data = data[~excluded_mask]
            excluded_data = data[excluded_mask]

            # Plot included points normally
            show_points = bool(getattr(self.main_window, 'show_points', True))
            if not included_data.empty and show_points:
                x_inc = included_data[x_col].values
                y_inc = included_data[y_col].values
                h_inc = included_data[h_col].values

                point_size = getattr(self.main_window, 'marker_size', getattr(self.main_window, 'point_size', 80))

                # Glow layer (below main points)
                show_glow = bool(getattr(self.main_window, 'show_point_glow', True))
                if show_glow:
                    glow_multiplier = float(getattr(self.main_window, 'point_glow_size_multiplier', 2.2))
                    glow_alpha = float(getattr(self.main_window, 'point_glow_alpha', 0.12))
                    ax.scatter(
                        x_inc, y_inc,
                        c=h_inc if self.main_window.show_colorbar else 'white',
                        cmap=getattr(self.main_window, 'colormap_2d', 'viridis'),
                        s=point_size * glow_multiplier,
                        alpha=glow_alpha,
                        edgecolors='none',
                        zorder=4
                    )

                # Main scatter layer
                scatter = ax.scatter(
                    x_inc, y_inc,
                    c=h_inc if self.main_window.show_colorbar else 'white',
                    cmap=getattr(self.main_window, 'colormap_2d', 'viridis'),
                    s=point_size,
                    edgecolors='white',
                    linewidths=0.7,
                    alpha=0.98,
                    zorder=5
                )
            else:
                scatter = None

            # Plot excluded points with different style
            if not excluded_data.empty and show_excluded_points:
                x_exc = excluded_data[x_col].values
                y_exc = excluded_data[y_col].values
                if custom_excluded_style:
                    point_size = float(getattr(self.main_window, 'point_size', 80))
                    excluded_size = max(10.0, point_size * excluded_size_scale)
                    excluded_marker_used = excluded_marker
                    excluded_color_used = excluded_color
                    excluded_alpha_used = excluded_alpha
                else:
                    excluded_size = 60.0
                    excluded_marker_used = 'x'
                    excluded_color_used = '#6a6a6a'
                    excluded_alpha_used = 0.3

                scatter_excluded = ax.scatter(
                    x_exc, y_exc,
                    color=excluded_color_used,
                    marker=excluded_marker_used,
                    s=excluded_size,
                    alpha=excluded_alpha_used,
                    label='Excluded Points',
                    zorder=3
                )
        else:
            # No exclusions, plot all points normally
            included_data = data
            excluded_data = None
            x = data[x_col].values
            y = data[y_col].values
            h = data[h_col].values

            show_points = bool(getattr(self.main_window, 'show_points', True))
            if show_points:
                point_size = getattr(self.main_window, 'point_size', 80)

                # Glow layer (below main points)
                show_glow = bool(getattr(self.main_window, 'show_point_glow', True))
                if show_glow:
                    glow_multiplier = float(getattr(self.main_window, 'point_glow_size_multiplier', 2.2))
                    glow_alpha = float(getattr(self.main_window, 'point_glow_alpha', 0.12))
                    ax.scatter(
                        x, y,
                        c=h if self.main_window.show_colorbar else 'white',
                        cmap=getattr(self.main_window, 'colormap_2d', 'viridis'),
                        s=point_size * glow_multiplier,
                        alpha=glow_alpha,
                        edgecolors='none',
                        zorder=4
                    )

                # Main scatter layer
                scatter = ax.scatter(
                    x, y,
                    c=h if self.main_window.show_colorbar else 'white',
                    cmap=getattr(self.main_window, 'colormap_2d', 'viridis'),
                    s=point_size,
                    edgecolors='white',
                    linewidths=0.7,
                    alpha=0.98,
                    zorder=5
                )
            else:
                scatter = None

        # Contours / filled contours (use full data for contours, or just included data)
        contour_data = included_data if has_any_exclusions and id_col and id_col in data.columns else data
        contourf = None
        show_contours = bool(self.main_window.show_contours)
        fill_contours = bool(getattr(self.main_window, "fill_contours", False)) and show_contours
        if show_contours and len(contour_data) >= 4:
            try:
                x_contour = contour_data[x_col].values
                y_contour = contour_data[y_col].values
                h_contour = contour_data[h_col].values

                grid = compute_contour_grid(
                    x=x_contour,
                    y=y_contour,
                    h=h_contour,
                    interpolation_method=getattr(self.main_window, "interpolation_method", "cubic"),
                    contour_extent_pct=getattr(self.main_window, "contour_extent_pct", 0),
                    contour_extrapolation=getattr(self.main_window, "contour_extrapolation", "none"),
                    grid_resolution=100,
                )
                if grid is None:
                    raise RuntimeError("Contour grid generation failed")
                xi, yi, zi = grid

                num_levels = getattr(self.main_window, 'contour_levels', 10)
                colormap_contour = getattr(self.main_window, 'colormap_2d', 'viridis')

                if fill_contours:
                    contourf = ax.contourf(xi, yi, zi, levels=num_levels, cmap=colormap_contour, alpha=0.75, zorder=1)

                if show_contours:
                    cs = ax.contour(xi, yi, zi, levels=num_levels, colors='black', alpha=0.5,
                                  linewidths=getattr(self.main_window, 'contour_linewidth', 0.8), zorder=2)
                    ax.clabel(cs, inline=True,
                             fontsize=getattr(self.main_window, 'contour_label_font_size', 8),
                             colors='black')
            except Exception:
                pass

        # Colorbar
        if self.main_window.show_colorbar and scatter is not None:
            divider = make_axes_locatable(ax)
            cax = divider.append_axes("right", size="3%", pad=0.1)
            cbar_src = contourf if contourf is not None else scatter
            cbar = self.canvas.fig.colorbar(cbar_src, cax=cax)
            cbar.ax.yaxis.set_tick_params(color=Colors.PLOT_AXIS)
            cbar.outline.set_edgecolor(Colors.PLOT_GRID)
            plt.setp(plt.getp(cbar.ax.axes, 'yticklabels'), color=Colors.PLOT_TEXT)
            cbar.set_label('Hydraulic Head', color=Colors.PLOT_TEXT)

        self._render_2d_static_labels(
            ax=ax,
            data=data,
            included_data=included_data,
            excluded_data=excluded_data if show_excluded_points else None,
            x_col=x_col,
            y_col=y_col,
            h_col=h_col,
            id_col=id_col,
            excluded_ids=(set(excluded_ids_str) | set(excluded_member_keys)),
        )

        # Gradient arrow
        if self.main_window.show_arrow and hasattr(self.main_window, 'gradient_calculator'):
            self._draw_gradient_arrow(ax, data, x_col, y_col)
        else:
            self._mean_arrow_artist = None
            self._mean_arrow_info = None

        stacked_clusters = []
        if bool(getattr(self.main_window, "show_stacked_points_experimental", True)):
            stacked_clusters = self._compute_stacked_clusters(data, x_col, y_col, h_col, id_col)

        # 2D plot interactivity (hover + click selection + mean arrow tooltip + stacked-point explode)
        self._install_2d_interactivity(
            ax,
            data,
            scatter,
            scatter_excluded,
            x_col,
            y_col,
            h_col,
            id_col,
            stacked_clusters=stacked_clusters,
        )

        # Style + grid already applied by _apply_plot_settings() at the top of this function.

        has_stacked = bool(stacked_clusters)
        show_stacked_legend = bool(getattr(self.main_window, "show_stacked_points_experimental", True)) and has_stacked

        # Legend
        if self.main_window.show_legend or show_stacked_legend:
            legend_elements = []

            # Data points entry
            if getattr(self.main_window, 'show_points', True):
                legend_elements.append(plt.Line2D([0], [0], marker='o', color='w',
                                                 markerfacecolor='#818cf8', markersize=8,
                                                 label='Data Points', linestyle='None'))

            # Excluded points entry (if any)
            if has_any_exclusions and id_col and id_col in data.columns and show_excluded_points:
                legend_marker = excluded_marker if custom_excluded_style else 'x'
                legend_color = excluded_color if custom_excluded_style else '#6a6a6a'
                legend_alpha = excluded_alpha if custom_excluded_style else 0.3
                legend_size = max(6.0, float(np.sqrt(max(25.0, float(getattr(self.main_window, 'point_size', 80)) * excluded_size_scale))))
                legend_elements.append(plt.Line2D(
                    [0], [0],
                    marker=legend_marker,
                    color=legend_color,
                    markerfacecolor=legend_color,
                    markeredgecolor=legend_color,
                    markersize=legend_size,
                    alpha=legend_alpha,
                    label='Excluded Points',
                    linestyle='None'
                ))

            if show_stacked_legend:
                legend_elements.append(plt.Line2D(
                    [0], [0],
                    marker='D',
                    color='w',
                    markerfacecolor=Colors.ACCENT_PRIMARY,
                    markeredgecolor='white',
                    markeredgewidth=1.0,
                    markersize=8.5,
                    label='Stacked Point (xN)',
                    linestyle='None',
                ))

            # Keep legend away from compass when both are visible.
            legend_loc = 'lower left' if bool(getattr(self.main_window, 'show_compass', True)) else 'best'

            # Add legend with custom styling (white background for white plot)
            legend = ax.legend(handles=legend_elements, loc=legend_loc,
                             facecolor='white', edgecolor='#cccccc',
                             framealpha=0.95, fontsize=9)
            # Style legend text (dark for white background)
            for text in legend.get_texts():
                text.set_color('#333333')

        # Labels (use customization properties)
        ax.set_xlabel(
            getattr(self.main_window, 'x_axis_label', 'X Coordinate [m]'),
            fontsize=getattr(self.main_window, 'axis_label_font_size', 11),
            color=Colors.PLOT_TEXT
        )
        ax.set_ylabel(
            getattr(self.main_window, 'y_axis_label', 'Y Coordinate [m]'),
            fontsize=getattr(self.main_window, 'axis_label_font_size', 11),
            color=Colors.PLOT_TEXT
        )
        ax.tick_params(labelsize=getattr(self.main_window, 'axis_tick_font_size', 9))
        self._apply_square_geo_axes(ax)
        self._apply_synced_geo_major_ticks(ax)

    def _install_2d_interactivity(
        self,
        ax,
        data,
        scatter_included,
        scatter_excluded,
        x_col,
        y_col,
        h_col,
        id_col,
        stacked_clusters=None,
    ):
        if scatter_included is None:
            return
        if id_col is None or id_col not in data.columns:
            return

        excluded_ids = getattr(self.main_window, "excluded_ids", set())
        excluded_ids_str = {str(v) for v in excluded_ids}
        excluded_member_keys = {str(v) for v in getattr(self.main_window, "excluded_member_keys", set())}
        row_keys_all = data.index.astype(str)
        if excluded_ids or excluded_member_keys:
            id_series = data[id_col].astype(str)
            member_key_series = id_series + "::" + row_keys_all
            excluded_mask = id_series.isin(excluded_ids_str)
            if excluded_member_keys:
                excluded_mask = excluded_mask | member_key_series.isin(excluded_member_keys)
            excluded_mask = excluded_mask.to_numpy(dtype=bool)
            included_data = data[~excluded_mask]
            excluded_data = data[excluded_mask]
            included_row_keys = row_keys_all[~excluded_mask]
            excluded_row_keys = row_keys_all[excluded_mask]
        else:
            included_data = data
            excluded_data = None
            included_row_keys = row_keys_all
            excluded_row_keys = np.empty((0,), dtype=object)

        included_ids = included_data[id_col].astype(str).tolist()
        included_info = {
            "id": included_ids,
            "member_key": [f"{pid}::{str(r)}" for pid, r in zip(included_ids, included_row_keys)],
            "x": included_data[x_col].tolist(),
            "y": included_data[y_col].tolist(),
            "h": included_data[h_col].tolist(),
            "excluded": [False] * len(included_data),
        }
        excluded_info = None
        if excluded_data is not None and scatter_excluded is not None and not excluded_data.empty:
            excluded_ids_list = excluded_data[id_col].astype(str).tolist()
            excluded_info = {
                "id": excluded_ids_list,
                "member_key": [f"{pid}::{str(r)}" for pid, r in zip(excluded_ids_list, excluded_row_keys)],
                "x": excluded_data[x_col].tolist(),
                "y": excluded_data[y_col].tolist(),
                "h": excluded_data[h_col].tolist(),
                "excluded": [True] * len(excluded_data),
            }

        point_lookup = {}
        point_lookup_member = {}

        def register_lookup(info):
            if not info:
                return
            for idx, pid in enumerate(info["id"]):
                pid_str = str(pid)
                mkey = str(info["member_key"][idx]) if "member_key" in info else pid_str
                status = "EXCLUDED" if bool(info["excluded"][idx]) else "INCLUDED"
                point = {
                    "id": pid_str,
                    "member_key": mkey,
                    "x": float(info["x"][idx]),
                    "y": float(info["y"][idx]),
                    "h": float(info["h"][idx]),
                    "status": status,
                }
                point_lookup_member[mkey] = dict(point)
                point_lookup.setdefault(pid_str, dict(point))

        register_lookup(included_info)
        register_lookup(excluded_info)

        self._selection_marker = ax.scatter(
            [],
            [],
            s=200,
            facecolors="none",
            edgecolors=Colors.ACCENT_PRIMARY,
            linewidths=2.0,
            zorder=20,
        )

        self._hover_annotation = self._popup_create(ax, zorder=30)
        self._hover_key = None

        selected_points = {}
        last_primary_id = None
        last_emitted_ids = []

        box_state = {
            "active": False,
            "start_data": None,
            "start_px": None,
            "additive": False,
        }
        box_patch = Rectangle(
            (0.0, 0.0),
            0.0,
            0.0,
            fill=False,
            linewidth=1.4,
            linestyle="--",
            edgecolor=Colors.ACCENT_PRIMARY,
            alpha=0.9,
            zorder=19,
            visible=False,
        )
        ax.add_patch(box_patch)
        stack_badges = []
        stack_explode_artists = []
        stack_explode_hit_targets = []
        exploded_cluster = None
        pending_stack_choice_id = None
        active_stack_key = None

        def clear_stack_explode():
            nonlocal stack_explode_artists, stack_explode_hit_targets, exploded_cluster, active_stack_key
            for artist in stack_explode_artists:
                try:
                    artist.remove()
                except Exception:
                    pass
            stack_explode_artists = []
            stack_explode_hit_targets = []
            exploded_cluster = None
            active_stack_key = None

        def get_cluster_key(cluster):
            k = (cluster or {}).get("key")
            if isinstance(k, (tuple, list)) and len(k) == 2:
                return (int(k[0]), int(k[1]))
            return None

        def get_saved_choice_for_cluster(cluster):
            key = get_cluster_key(cluster)
            if key is None:
                return None
            choice_map = getattr(self.main_window, "stacked_intake_choice_map", {}) or {}
            val = choice_map.get(key)
            return str(val) if val is not None else None

        def make_stack_badges():
            nonlocal stack_badges
            stack_badges = []
            clusters = stacked_clusters or []
            if not clusters:
                return
            for cl in clusters:
                members = []
                for p in cl.get("members", []):
                    pid = str(p.get("id", ""))
                    member_key = str(p.get("member_key", pid))
                    if not pid:
                        continue
                    info = point_lookup_member.get(member_key, point_lookup.get(pid, {}))
                    enriched = dict(p)
                    enriched["id"] = pid
                    enriched["member_key"] = member_key
                    enriched["x"] = float(info.get("x", enriched.get("x", np.nan)))
                    enriched["y"] = float(info.get("y", enriched.get("y", np.nan)))
                    enriched["h"] = float(info.get("h", enriched.get("h", np.nan)))
                    enriched["status"] = str(info.get("status", "EXCLUDED" if pid in excluded_ids_str else "INCLUDED"))
                    if np.isfinite(enriched["x"]) and np.isfinite(enriched["y"]) and np.isfinite(enriched["h"]):
                        members.append(enriched)
                if len(members) < 2:
                    continue
                cx = float(cl.get("center_x", members[0]["x"]))
                cy = float(cl.get("center_y", members[0]["y"]))

                # Concept-style stacked marker: rotated square (diamond) with glow.
                glow = ax.scatter(
                    [cx],
                    [cy],
                    s=220,
                    marker="D",
                    c=Colors.ACCENT_PRIMARY,
                    edgecolors="none",
                    linewidths=0.0,
                    zorder=16,
                    alpha=0.12,
                )
                marker_outer = ax.scatter(
                    [cx],
                    [cy],
                    s=118,
                    marker="D",
                    c=Colors.ACCENT_PRIMARY,
                    edgecolors="white",
                    linewidths=1.2,
                    zorder=17,
                    alpha=0.98,
                )
                marker_inner = ax.scatter(
                    [cx],
                    [cy],
                    s=52,
                    marker="D",
                    c=Colors.ACCENT_DARK,
                    edgecolors="none",
                    linewidths=0.0,
                    zorder=18,
                    alpha=1.0,
                )

                # Small pill badge above the marker: xN
                try:
                    cx_px, cy_px = ax.transData.transform((cx, cy))
                    bx, by = ax.transData.inverted().transform((cx_px, cy_px - 16.0))
                except Exception:
                    bx, by = cx, cy
                txt = ax.text(
                    bx,
                    by,
                    f"x{len(members)}",
                    fontsize=7.2,
                    color="white",
                    fontweight="700",
                    ha="center",
                    va="center",
                    zorder=19,
                    bbox=dict(
                        boxstyle="round,pad=0.22,rounding_size=0.6",
                        fc="#1f2430",
                        ec=Colors.PLOT_BORDER,
                        alpha=0.96,
                    ),
                )
                stack_badges.append(
                    {
                        "badge": marker_outer,
                        "glow": glow,
                        "inner": marker_inner,
                        "text": txt,
                        "members": members,
                        "cx": cx,
                        "cy": cy,
                        "key": cl.get("key"),
                    }
                )

        def stack_badge_hit(event):
            if event.x is None or event.y is None:
                return None
            for b in stack_badges:
                try:
                    contains, _ = b["badge"].contains(event)
                    if bool(contains):
                        return b
                except Exception:
                    pass
                try:
                    x_disp, y_disp = ax.transData.transform((b["cx"], b["cy"]))
                    dx = float(event.x) - float(x_disp)
                    dy = float(event.y) - float(y_disp)
                    if (dx * dx + dy * dy) <= (16.0 * 16.0):
                        return b
                except Exception:
                    pass
            return None

        def explode_stack_cluster(cluster):
            nonlocal exploded_cluster, pending_stack_choice_id, active_stack_key
            clear_stack_explode()
            if cluster is None:
                self._request_interaction_draw(force=True)
                return
            members = list(cluster.get("members", []))
            if len(members) < 2:
                return
            active_stack_key = get_cluster_key(cluster)
            saved = get_saved_choice_for_cluster(cluster)
            ids_here = {str(m.get("member_key", m.get("id", ""))) for m in members}
            if saved in ids_here:
                pending_stack_choice_id = saved
            elif pending_stack_choice_id not in ids_here:
                pending_stack_choice_id = str(members[0].get("member_key", members[0].get("id", "")))

            cx = float(cluster["cx"])
            cy = float(cluster["cy"])
            n = len(members)
            # Fixed radius in pixels for consistent appearance at any zoom level
            radius_px = 50.0
            try:
                c_disp = ax.transData.transform((cx, cy))
                inv = ax.transData.inverted()
            except Exception:
                return

            for i, point in enumerate(members):
                # Evenly space points around the circle, starting from top (-π/2)
                ang = (2.0 * np.pi * i) / float(n) - (np.pi / 2.0)
                px = float(c_disp[0]) + radius_px * np.cos(ang)
                py = float(c_disp[1]) + radius_px * np.sin(ang)
                try:
                    dx, dy = inv.transform((px, py))
                except Exception:
                    continue

                # Tether line from center to orbit point
                line, = ax.plot(
                    [cx, float(dx)],
                    [cy, float(dy)],
                    color="#4b5563",
                    linewidth=1.0,
                    alpha=0.5,
                    zorder=18,
                    solid_capstyle="round",
                )
                stack_explode_artists.append(line)

                # Orbit point marker - clean circle matching concept
                mkey = str(point.get("member_key", point.get("id", "")))
                is_selected = (mkey == pending_stack_choice_id)
                status = str(point.get("status", "INCLUDED")).upper()

                # Fill color: dark gray base, or error color if excluded
                fill_color = "#2a2f3a" if status != "EXCLUDED" else Colors.ERROR
                # Border: accent when selected, white otherwise
                edge_col = Colors.ACCENT_PRIMARY if is_selected else "white"
                lw = 2.0 if is_selected else 1.5
                marker_size = 70

                # Selection glow (only for selected point)
                if is_selected:
                    glow = ax.scatter(
                        [float(dx)], [float(dy)],
                        s=marker_size * 2.2,
                        c=Colors.ACCENT_PRIMARY,
                        edgecolors="none",
                        alpha=0.18,
                        zorder=18,
                    )
                    stack_explode_artists.append(glow)

                m = ax.scatter(
                    [float(dx)], [float(dy)],
                    s=marker_size,
                    c=fill_color,
                    edgecolors=edge_col,
                    linewidths=lw,
                    zorder=19,
                    alpha=1.0,
                )
                stack_explode_artists.append(m)
                stack_explode_hit_targets.append({
                    "artist": m,
                    "point": dict(point),
                    "ex_x": float(dx),
                    "ex_y": float(dy),
                    "ex_px": float(px),
                    "ex_py": float(py),
                })
                # No labels - side panel provides all detail

            exploded_cluster = dict(cluster)
            self._request_interaction_draw(force=True)

        def exploded_hit_point(event):
            if event.x is None or event.y is None:
                return None
            for item in stack_explode_hit_targets:
                marker = item.get("artist")
                point = item.get("point")
                if marker is None or point is None:
                    continue
                try:
                    contains, _ = marker.contains(event)
                    if bool(contains):
                        return dict(point)
                except Exception:
                    pass
                try:
                    ex_px = item.get("ex_px")
                    ex_py = item.get("ex_py")
                    if ex_px is None or ex_py is None:
                        ex_x = item.get("ex_x")
                        ex_y = item.get("ex_y")
                        if ex_x is None or ex_y is None:
                            continue
                        x_disp, y_disp = ax.transData.transform((float(ex_x), float(ex_y)))
                    else:
                        x_disp, y_disp = float(ex_px), float(ex_py)
                    dx = float(event.x) - float(x_disp)
                    dy = float(event.y) - float(y_disp)
                    if (dx * dx + dy * dy) <= (26.0 * 26.0):
                        out = dict(point)
                        out["x"] = float(item.get("ex_x", out.get("x", np.nan)))
                        out["y"] = float(item.get("ex_y", out.get("y", np.nan)))
                        return out
                except Exception:
                    pass
            return None

        def set_pending_stack_choice(member_key, redraw=True):
            nonlocal pending_stack_choice_id
            pending_stack_choice_id = str(member_key or "").strip() or None
            if pending_stack_choice_id:
                self._set_stacked_panel_pending_visual(pending_stack_choice_id)
            if redraw and exploded_cluster is not None:
                explode_stack_cluster(exploded_cluster)

        def apply_current_stack_choice(pid):
            if exploded_cluster is None:
                return
            apply_stacked_choice(
                pid,
                list(exploded_cluster.get("members", [])),
                stack_key=get_cluster_key(exploded_cluster),
            )
            clear_stack_explode()
            self._hide_stacked_intake_panel()

        make_stack_badges()

        def event_has_modifier(event, qt_modifier, key_name: str) -> bool:
            return bool(self.canvas._event_has_modifier(event, qt_modifier, key_name))

        def get_event_data_xy(event):
            if event.xdata is not None and event.ydata is not None:
                return float(event.xdata), float(event.ydata)
            if event.x is None or event.y is None:
                return None
            try:
                x_data, y_data = ax.transData.inverted().transform((event.x, event.y))
                return float(x_data), float(y_data)
            except Exception:
                return None

        def format_point(idx, info):
            pid = str(info["id"][idx])
            mkey = str(info["member_key"][idx]) if "member_key" in info else pid
            x = float(info["x"][idx])
            y = float(info["y"][idx])
            h = float(info["h"][idx])
            status = "EXCLUDED" if bool(info["excluded"][idx]) else "INCLUDED"
            return {"id": pid, "member_key": mkey, "x": x, "y": y, "h": h, "status": status}

        def get_hit_point(event):
            contains, details = scatter_included.contains(event)
            if contains and details.get("ind") is not None and len(details["ind"]) > 0:
                idx = int(details["ind"][0])
                return format_point(idx, included_info)

            if scatter_excluded is not None and excluded_info is not None:
                contains2, details2 = scatter_excluded.contains(event)
                if contains2 and details2.get("ind") is not None and len(details2["ind"]) > 0:
                    idx = int(details2["ind"][0])
                    return format_point(idx, excluded_info)
            return None

        def emit_selection_signals(emit_signal: bool):
            nonlocal last_emitted_ids
            if not emit_signal:
                return
            ids = [str(pt.get("id", "")) for pt in selected_points.values()]
            if ids == last_emitted_ids:
                return
            last_emitted_ids = ids.copy()
            if ids:
                self.points_selected.emit(ids)
                self.point_selected.emit(ids[0])
            else:
                self.point_deselected.emit()

        def refresh_selected_artists(emit_signal: bool):
            nonlocal last_primary_id

            if self._selection_marker is not None:
                if selected_points:
                    offsets = np.array([[pt["x"], pt["y"]] for pt in selected_points.values()], dtype=float)
                else:
                    offsets = np.empty((0, 2))
                self._selection_marker.set_offsets(offsets)

            if selected_points:
                if last_primary_id not in selected_points:
                    last_primary_id = next(iter(selected_points.keys()))
                primary = selected_points[last_primary_id]
                self._selected_point = dict(primary)

                if len(selected_points) == 1:
                    text = self._popup_compose(
                        f"Point {primary['id']}",
                        lines=[
                            f"Head:  {primary['h']:.3f} m",
                            f"X:     {primary['x']:.1f}",
                            f"Y:     {primary['y']:.1f}",
                        ],
                    )
                    if self._pinned_annotation is None:
                        self._pinned_annotation = self._popup_create(ax, zorder=21)
                        self._pinned_annotation.set_text(text)
                        self._pinned_annotation.xy = (primary["x"], primary["y"])
                        self._pinned_annotation.set_visible(True)
                    else:
                        self._pinned_annotation.set_text(text)
                        self._pinned_annotation.xy = (primary["x"], primary["y"])
                        self._pinned_annotation.set_visible(True)
                elif self._pinned_annotation is not None:
                    self._pinned_annotation.set_visible(False)
            else:
                self._selected_point = None
                last_primary_id = None
                if self._pinned_annotation is not None:
                    self._pinned_annotation.set_visible(False)

            emit_selection_signals(emit_signal)
            self._request_interaction_draw(force=True)

        def set_selected(pid, x, y, h, status, emit_signal=True, member_key=None):
            nonlocal last_primary_id
            pid_str = str(pid)
            member_key_str = str(member_key or pid_str)
            point = {
                "id": pid_str,
                "member_key": member_key_str,
                "x": float(x),
                "y": float(y),
                "h": float(h),
                "status": str(status),
            }
            point_lookup_member[member_key_str] = dict(point)
            point_lookup.setdefault(pid_str, dict(point))
            selected_points.clear()
            selected_points[member_key_str] = dict(point)
            last_primary_id = member_key_str
            refresh_selected_artists(emit_signal)

        def set_selected_ids(id_values, emit_signal=True):
            nonlocal last_primary_id
            ordered = []
            seen = set()
            for raw in id_values or []:
                key = str(raw)
                if key in seen:
                    continue
                seen.add(key)
                ordered.append(key)

            selected_points.clear()
            for key in ordered:
                point = point_lookup.get(key)
                if point is None:
                    point = point_lookup_member.get(key)
                if point is not None:
                    mkey = str(point.get("member_key", point.get("id", key)))
                    selected_points[mkey] = dict(point)

            if selected_points:
                if ordered and ordered[0] in selected_points:
                    last_primary_id = ordered[0]
                elif last_primary_id not in selected_points:
                    last_primary_id = next(iter(selected_points.keys()))
            else:
                last_primary_id = None

            refresh_selected_artists(emit_signal)

        def clear_selected(emit_signal=True):
            selected_points.clear()
            refresh_selected_artists(emit_signal)

        def apply_stacked_choice(chosen_member_key, members, stack_key=None):
            chosen_member_key = str(chosen_member_key or "").strip()
            if not chosen_member_key or not members:
                return
            member_records = []
            for m in members:
                pid = str(m.get("id", "")).strip()
                mkey = str(m.get("member_key", pid)).strip()
                if pid and mkey:
                    member_records.append((mkey, pid))
            if not member_records:
                return

            if stack_key is not None:
                try:
                    choice_map = getattr(self.main_window, "stacked_intake_choice_map", None)
                    if not isinstance(choice_map, dict):
                        choice_map = {}
                        self.main_window.stacked_intake_choice_map = choice_map
                    choice_map[(int(stack_key[0]), int(stack_key[1]))] = chosen_member_key
                except Exception:
                    pass

            changed = False
            for mkey, pid in member_records:
                want_excluded = (mkey != chosen_member_key)
                try:
                    changed = bool(
                        self.main_window.apply_point_exclusion(
                            str(pid), member_key=str(mkey), exclude=bool(want_excluded)
                        )
                    ) or changed
                except Exception:
                    pass

            if changed:
                try:
                    self.main_window.refilter_and_recalculate()
                except Exception:
                    pass

        def toggle_selected(point, emit_signal=True):
            nonlocal last_primary_id
            pkey = str(point.get("member_key", point.get("id", "")))
            if pkey in selected_points:
                del selected_points[pkey]
                if last_primary_id == pkey:
                    last_primary_id = next(iter(selected_points.keys()), None)
            else:
                selected_points[pkey] = dict(point)
                last_primary_id = pkey
            refresh_selected_artists(emit_signal)

        def select_only(point, emit_signal=True):
            set_selected(
                point["id"],
                point["x"],
                point["y"],
                point["h"],
                point["status"],
                emit_signal=emit_signal,
                member_key=point.get("member_key"),
            )

        def apply_box_selection(x0, y0, x1, y1, additive: bool):
            nonlocal last_primary_id
            lo_x, hi_x = (x0, x1) if x0 <= x1 else (x1, x0)
            lo_y, hi_y = (y0, y1) if y0 <= y1 else (y1, y0)

            if not additive:
                selected_points.clear()

            for pkey, point in point_lookup_member.items():
                px = point["x"]
                py = point["y"]
                if lo_x <= px <= hi_x and lo_y <= py <= hi_y:
                    selected_points[pkey] = dict(point)

            if selected_points:
                if last_primary_id not in selected_points:
                    last_primary_id = next(iter(selected_points.keys()))
            else:
                last_primary_id = None

            refresh_selected_artists(True)

        def clear_arrow_pin():
            if self._arrow_pinned_annotation is not None:
                self._arrow_pinned_annotation.set_visible(False)
                self._request_interaction_draw(force=True)

        def format_mean_arrow_text():
            info = self._mean_arrow_info
            if not isinstance(info, dict):
                return None

            avg_gradient = info.get("avg_gradient")
            angle_unweighted = info.get("angle_unweighted")
            angle_weighted = info.get("angle_weighted")

            if avg_gradient is None:
                return None

            lines = [f"Gradient:   {float(avg_gradient):.6f} m/m"]
            if angle_unweighted is not None:
                card = self._angle_to_cardinal(float(angle_unweighted))
                lines.append(f"Direction:  {float(angle_unweighted):.1f}°  {card}")
            if angle_weighted is not None:
                card_w = self._angle_to_cardinal(float(angle_weighted))
                lines.append(f"Weighted:   {float(angle_weighted):.1f}°  {card_w}")
            return self._popup_compose("Mean Gradient", lines=lines)

        def arrow_hit_test(event, tol_px: float = 12.0) -> bool:
            info = self._mean_arrow_info
            if not isinstance(info, dict):
                return False
            if event.x is None or event.y is None:
                return False

            artist = self._mean_arrow_artist
            if artist is not None and hasattr(artist, "contains"):
                try:
                    contains, _ = artist.contains(event)
                    if bool(contains):
                        return True
                except Exception:
                    pass

                try:
                    renderer = getattr(self.canvas, "get_renderer", None)
                    renderer = renderer() if callable(renderer) else None
                    if renderer is not None and hasattr(artist, "get_window_extent"):
                        bbox = artist.get_window_extent(renderer=renderer)
                        bbox = bbox.expanded(1.15, 1.25)
                        if bbox.contains(event.x, event.y):
                            return True
                except Exception:
                    pass
            try:
                cx = float(info.get("cx"))
                cy = float(info.get("cy"))
            except Exception:
                return False

            try:
                x_disp, y_disp = ax.transData.transform((cx, cy))
            except Exception:
                return False

            dx = float(event.x) - float(x_disp)
            dy = float(event.y) - float(y_disp)
            return (dx * dx + dy * dy) <= (tol_px * tol_px)

        def toggle_arrow_pin():
            text = format_mean_arrow_text()
            info = self._mean_arrow_info
            if text is None or not isinstance(info, dict):
                return

            cx = float(info["cx"])
            cy = float(info["cy"])

            if self._arrow_pinned_annotation is None:
                self._arrow_pinned_annotation = self._popup_create(ax, zorder=25, xytext=(12, -12), va="top")
                self._arrow_pinned_annotation.set_text(text)
                self._arrow_pinned_annotation.xy = (cx, cy)
                self._arrow_pinned_annotation.set_visible(True)
                self._request_interaction_draw(force=True)
                return

            if self._arrow_pinned_annotation.get_visible():
                self._arrow_pinned_annotation.set_visible(False)
            else:
                self._arrow_pinned_annotation.xy = (cx, cy)
                self._arrow_pinned_annotation.set_text(text)
                self._arrow_pinned_annotation.set_visible(True)
            self._request_interaction_draw(force=True)

        def set_hover(pid, x, y, h, status, key):
            if self._hover_key == key and self._hover_annotation.get_visible():
                return
            self._hover_key = key
            self._hover_annotation.xy = (x, y)
            self._hover_annotation.set_text(
                self._popup_compose(
                    f"Point {pid}",
                    lines=[f"Head:  {h:.3f} m"],
                )
            )
            self._hover_annotation.set_visible(True)
            self._request_interaction_draw()

        def clear_hover():
            self._hover_key = None
            if self._hover_annotation is not None and self._hover_annotation.get_visible():
                self._hover_annotation.set_visible(False)
                self._request_interaction_draw()

        def on_press(event):
            if event.button != 1 or event.inaxes != ax:
                return
            if not event_has_modifier(event, Qt.ControlModifier, "control"):
                return

            xy = get_event_data_xy(event)
            if xy is None:
                return

            box_state["active"] = True
            box_state["start_data"] = xy
            if event.x is not None and event.y is not None:
                box_state["start_px"] = (float(event.x), float(event.y))
            else:
                box_state["start_px"] = None
            box_state["additive"] = event_has_modifier(event, Qt.ShiftModifier, "shift")

            box_patch.set_xy((xy[0], xy[1]))
            box_patch.set_width(0.0)
            box_patch.set_height(0.0)
            box_patch.set_visible(True)
            clear_hover()
            self._request_interaction_draw(force=True)

        def on_hover(event):
            if self._cross_section_mode:
                clear_hover()
                if len(self._cross_section_points) == 1 and event.inaxes == ax:
                    preview_xy = get_event_data_xy(event)
                    self._update_cross_section_artists(ax, preview_xy=preview_xy)
                elif len(self._cross_section_points) == 1:
                    self._update_cross_section_artists(ax, preview_xy=None)
                return

            if box_state["active"]:
                start = box_state["start_data"]
                current = get_event_data_xy(event)
                if start is not None and current is not None:
                    x0, y0 = start
                    x1, y1 = current
                    box_patch.set_xy((min(x0, x1), min(y0, y1)))
                    box_patch.set_width(abs(x1 - x0))
                    box_patch.set_height(abs(y1 - y0))
                    self._request_interaction_draw()
                return

            if event.inaxes != ax:
                clear_hover()
                return

            if getattr(self.canvas, "_press", None) is not None and getattr(self.canvas, "_moved", False):
                clear_hover()
                return

            if self._disable_hover_redraws:
                clear_hover()
                return

            exp_hit = exploded_hit_point(event)
            if exp_hit is not None:
                set_hover(exp_hit["id"], exp_hit["x"], exp_hit["y"], exp_hit["h"], exp_hit["status"], ("exp", exp_hit["id"]))
                return

            point = get_hit_point(event)
            if point is not None:
                set_hover(point["id"], point["x"], point["y"], point["h"], point["status"], ("pt", point["id"]))
                return

            if arrow_hit_test(event):
                text = format_mean_arrow_text()
                info = self._mean_arrow_info
                if text is not None and isinstance(info, dict):
                    cx = float(info["cx"])
                    cy = float(info["cy"])
                    self._hover_key = ("mean_arrow", 0)
                    self._hover_annotation.xy = (cx, cy)
                    self._hover_annotation.set_text(text)
                    self._hover_annotation.set_visible(True)
                    self._request_interaction_draw()
                    return

            clear_hover()

        def on_release(event):
            if event.button != 1:
                return

            if box_state["active"]:
                start = box_state["start_data"]
                start_px = box_state["start_px"]
                additive = bool(box_state["additive"])

                box_state["active"] = False
                box_state["start_data"] = None
                box_state["start_px"] = None
                box_state["additive"] = False
                box_patch.set_visible(False)

                moved = False
                if start_px is not None and event.x is not None and event.y is not None:
                    moved = max(abs(float(event.x) - start_px[0]), abs(float(event.y) - start_px[1])) >= 4.0

                end_xy = get_event_data_xy(event)
                if moved and start is not None and end_xy is not None:
                    apply_box_selection(start[0], start[1], end_xy[0], end_xy[1], additive=additive)
                else:
                    self._request_interaction_draw(force=True)
                return

            if event.inaxes != ax:
                return

            try:
                self.canvas.setFocus()
            except Exception:
                pass

            if getattr(self.canvas, "_dragged_last", False):
                return

            hit_exploded = exploded_hit_point(event)
            if hit_exploded is not None:
                chosen_id = str(hit_exploded.get("member_key", hit_exploded.get("id", ""))).strip()
                base_point = point_lookup_member.get(chosen_id)
                if base_point is None:
                    base_point = point_lookup.get(str(hit_exploded.get("id", "")).strip())
                if base_point is not None:
                    select_only(base_point, emit_signal=True)
                set_pending_stack_choice(chosen_id, redraw=True)
                return

            badge_hit = stack_badge_hit(event)
            if badge_hit is not None:
                try:
                    if exploded_cluster is not None and exploded_cluster.get("cx") == badge_hit.get("cx") and exploded_cluster.get("cy") == badge_hit.get("cy"):
                        clear_stack_explode()
                        self._hide_stacked_intake_panel()
                    else:
                        explode_stack_cluster(badge_hit)
                        saved = get_saved_choice_for_cluster(badge_hit)
                        ids_here = [str(m.get("member_key", m.get("id", ""))) for m in list(badge_hit.get("members", []))]
                        pending = saved if saved in ids_here else (ids_here[0] if ids_here else None)
                        if pending:
                            set_pending_stack_choice(str(pending), redraw=False)
                            explode_stack_cluster(badge_hit)
                        self._show_stacked_intake_panel(
                            cluster=badge_hit,
                            pending_id=pending_stack_choice_id,
                            on_select=lambda pid: set_pending_stack_choice(pid, redraw=True),
                            on_apply=lambda pid: apply_current_stack_choice(pid),
                            on_collapse=lambda: clear_stack_explode(),
                        )
                except Exception:
                    clear_stack_explode()
                    self._hide_stacked_intake_panel()
                return

            if self._cross_section_mode:
                xy = get_event_data_xy(event)
                if xy is None:
                    return
                self._cross_section_points.append((float(xy[0]), float(xy[1])))
                if len(self._cross_section_points) == 1:
                    self._update_cross_section_artists(ax)
                    return

                self._cross_section_points = self._cross_section_points[:2]
                self._cross_section_mode = False
                self._update_cross_section_artists(ax)

                profile = self._compute_cross_section_profile(
                    data=data,
                    x_col=x_col,
                    y_col=y_col,
                    h_col=h_col,
                    p0=self._cross_section_points[0],
                    p1=self._cross_section_points[1],
                )
                if profile is not None:
                    geology = self._sample_cross_section_geology(profile, data)
                    self._show_cross_section_dialog(profile, geology=geology)

                # Geo.dk fetch (plot uses the same panel+backend as map, but with this line as path).
                try:
                    path_utm = [
                        [float(self._cross_section_points[0][0]), float(self._cross_section_points[0][1])],
                        [float(self._cross_section_points[1][0]), float(self._cross_section_points[1][1])],
                    ]
                    self.geodk_transect_requested.emit(path_utm)
                except Exception:
                    pass
                return

            shift_pressed = event_has_modifier(event, Qt.ShiftModifier, "shift")
            hit = get_hit_point(event)
            if hit is not None:
                if shift_pressed:
                    toggle_selected(hit, emit_signal=True)
                else:
                    select_only(hit, emit_signal=True)
                return

            if (not shift_pressed) and arrow_hit_test(event):
                toggle_arrow_pin()
                return

            if not shift_pressed:
                clear_selected(emit_signal=True)

        def apply_exclusion(exclude: bool):
            points = list(selected_points.values())
            if not points:
                return

            changed = False
            for point in points:
                pid = str(point.get("id", "")).strip()
                mkey = str(point.get("member_key", pid)).strip()
                try:
                    changed = bool(
                        self.main_window.apply_point_exclusion(
                            str(pid), member_key=str(mkey), exclude=bool(exclude)
                        )
                    ) or changed
                except Exception:
                    pass

            if changed:
                try:
                    self.main_window.refilter_and_recalculate()
                except Exception:
                    pass

        def on_key(event):
            if event.key in ("x", "X"):
                self._cross_section_mode = not bool(self._cross_section_mode)
                self._cross_section_points = []
                self._update_cross_section_artists(ax)
                clear_hover()
                return
            if event.key in ("escape", "esc"):
                clear_stack_explode()
                self._hide_stacked_intake_panel()
                if self._cross_section_mode or self._cross_section_points:
                    self._cross_section_mode = False
                    self._cross_section_points = []
                    self._update_cross_section_artists(ax)
                clear_selected(emit_signal=True)
                clear_arrow_pin()
                return
            if event.key in ("e", "E"):
                apply_exclusion(True)
                return
            if event.key in ("i", "I"):
                apply_exclusion(False)
                return

        self._mpl_cids.append(self.canvas.mpl_connect("button_press_event", on_press))
        self._mpl_cids.append(self.canvas.mpl_connect("button_release_event", on_release))
        self._mpl_cids.append(self.canvas.mpl_connect("key_press_event", on_key))
        self._mpl_cids.append(self.canvas.mpl_connect("motion_notify_event", on_hover))

        self._2d_data_ref = {"included": included_info, "excluded": excluded_info}
        self._2d_set_selected_fn = lambda pid, x, y, h, status: set_selected(
            pid, x, y, h, status, emit_signal=False
        )
        self._2d_set_selected_ids_fn = lambda id_values: set_selected_ids(id_values, emit_signal=False)
        self._2d_clear_selected_fn = lambda: clear_selected(emit_signal=False)

    @staticmethod
    def _normalize_2d_label_mode(value) -> str:
        mode = str(value or "all").strip().lower()
        return mode if mode in {"all", "smart", "off", "pinned"} else "all"

    def _pick_smart_label_positions(self, ax, label_data, x_col, y_col):
        """Pick a spatially sparse subset of points for label rendering."""
        if label_data is None or getattr(label_data, "empty", True):
            return []

        coords = label_data[[x_col, y_col]].to_numpy(dtype=float)
        n = int(coords.shape[0])
        if n <= 1:
            return [0] if n == 1 else []

        # Keep all labels for small datasets to preserve detail.
        if n <= 35:
            return list(range(n))

        max_labels = int(getattr(self.main_window, "smart_label_max_count", 70) or 70)
        min_px = float(getattr(self.main_window, "smart_label_min_px", 22.0) or 22.0)
        min_px2 = min_px * min_px

        try:
            coords_px = ax.transData.transform(coords)
        except Exception:
            return list(range(min(n, max_labels)))

        cell = max(8.0, min_px)
        buckets = {}
        keep = []

        for idx, (px, py) in enumerate(coords_px):
            if len(keep) >= max_labels:
                break

            gx = int(px // cell)
            gy = int(py // cell)
            should_keep = True

            for nx in (gx - 1, gx, gx + 1):
                if not should_keep:
                    break
                for ny in (gy - 1, gy, gy + 1):
                    for j in buckets.get((nx, ny), []):
                        dx = px - coords_px[j, 0]
                        dy = py - coords_px[j, 1]
                        if (dx * dx + dy * dy) < min_px2:
                            should_keep = False
                            break
                    if not should_keep:
                        break

            if should_keep:
                keep.append(idx)
                buckets.setdefault((gx, gy), []).append(idx)

        if not keep:
            keep.append(0)
        return keep

    def _clear_static_labels(self):
        for artist in getattr(self, "_static_label_artists", []):
            try:
                artist.remove()
            except Exception:
                pass
        self._static_label_artists = []

    def _render_2d_static_labels(self, ax, data, included_data, excluded_data, x_col, y_col, h_col, id_col, excluded_ids):
        """Render static 2D point labels according to label mode."""
        self._clear_static_labels()

        label_mode = self._normalize_2d_label_mode(getattr(self.main_window, "label_mode_2d", "all"))
        if label_mode not in ("all", "smart"):
            return

        label_data = included_data if excluded_ids and id_col and id_col in data.columns else data
        if label_mode == "smart":
            keep_idx = self._pick_smart_label_positions(ax, label_data, x_col, y_col)
            label_data = label_data.iloc[keep_idx]

        if self.main_window.show_id_labels and id_col:
            id_offset = -getattr(self.main_window, "label_offset", 10)
            for i, row in label_data.iterrows():
                ann = ax.annotate(
                    str(row[id_col]),
                    (row[x_col], row[y_col]),
                    xytext=(0, id_offset),
                    textcoords="offset points",
                    ha="center",
                    fontsize=getattr(self.main_window, "id_font_size", 9),
                    color=getattr(self.main_window, "id_label_color", "#818cf8"),
                )
                self._static_label_artists.append(ann)

            if (
                label_mode == "all"
                and excluded_ids
                and id_col
                and id_col in data.columns
                and excluded_data is not None
                and not excluded_data.empty
            ):
                for i, row in excluded_data.iterrows():
                    ann = ax.annotate(
                        str(row[id_col]),
                        (row[x_col], row[y_col]),
                        xytext=(0, id_offset),
                        textcoords="offset points",
                        ha="center",
                        fontsize=getattr(self.main_window, "id_font_size", 9),
                        color="#6a6a6a",
                        alpha=0.5,
                    )
                    self._static_label_artists.append(ann)

        if self.main_window.show_head_labels:
            head_offset = getattr(self.main_window, "label_offset", 10)
            for i, row in label_data.iterrows():
                ann = ax.annotate(
                    f"{float(row[h_col]):.3f}",
                    (row[x_col], row[y_col]),
                    xytext=(0, head_offset),
                    textcoords="offset points",
                    ha="center",
                    fontsize=getattr(self.main_window, "head_font_size", 8),
                    color=getattr(self.main_window, "head_label_color", "#a0a0a0"),
                )
                self._static_label_artists.append(ann)

    def refresh_2d_labels_only(self) -> bool:
        """Fast path: update only static 2D labels without full redraw."""
        try:
            if getattr(self.main_window, "current_plot_type", "2D") != "2D":
                return False
            ax = getattr(self.canvas, "ax", None)
            if ax is None:
                return False

            data = getattr(self.main_window, "filtered_plot_data", None)
            if data is None:
                data = getattr(self.main_window, "filtered_data", None)
            if data is None:
                data = getattr(self.main_window, "data", None)
            if data is None or getattr(data, "empty", True):
                return False

            col_map = getattr(self.main_window, "col_mapping", {}) or {}
            x_col = col_map.get("x")
            y_col = col_map.get("y")
            h_col = col_map.get("hydraulic head")
            id_col = col_map.get("ID")
            if not all([x_col, y_col, h_col]):
                return False

            excluded_ids = getattr(self.main_window, "excluded_ids", set())
            if excluded_ids and id_col and id_col in data.columns:
                excluded_ids_str = {str(v) for v in excluded_ids}
                id_series = data[id_col].astype(str)
                included_data = data[~id_series.isin(excluded_ids_str)]
                excluded_data = data[id_series.isin(excluded_ids_str)]
            else:
                included_data = data
                excluded_data = None

            self._render_2d_static_labels(
                ax=ax,
                data=data,
                included_data=included_data,
                excluded_data=excluded_data,
                x_col=x_col,
                y_col=y_col,
                h_col=h_col,
                id_col=id_col,
                excluded_ids=excluded_ids,
            )
            self.canvas.draw_idle()
            return True
        except Exception:
            return False

    @staticmethod
    def _fill_idw(zi, xi, yi, x_pts, y_pts, v_pts, power: float = 2.0):
        """Fill NaNs in zi using inverse-distance weighting (IDW)."""
        try:
            flat = zi.reshape(-1)
            xi_flat = xi.reshape(-1)
            yi_flat = yi.reshape(-1)
            nan_idx = np.where(np.isnan(flat))[0]
            if nan_idx.size == 0:
                return zi

            x_pts = np.asarray(x_pts, dtype=float)
            y_pts = np.asarray(y_pts, dtype=float)
            v_pts = np.asarray(v_pts, dtype=float)

            for i in nan_idx:
                xg = xi_flat[i]
                yg = yi_flat[i]
                dx = x_pts - xg
                dy = y_pts - yg
                dist2 = dx * dx + dy * dy
                if dist2.size == 0:
                    continue
                if np.any(dist2 == 0):
                    flat[i] = v_pts[np.argmin(dist2)]
                    continue
                w = 1.0 / np.power(dist2, power / 2.0)
                w_sum = np.sum(w)
                if w_sum > 0:
                    flat[i] = float(np.sum(w * v_pts) / w_sum)
            return flat.reshape(zi.shape)
        except Exception:
            return zi

    def _draw_3d_plot(self, data, x_col, y_col, h_col):
        """Draw 3D surface plot."""
        # Clear and recreate as 3D axes
        self.canvas.fig.clear()
        ax = self.canvas.fig.add_subplot(111, projection='3d')
        self.canvas._apply_axis_theme(ax, self.canvas.fig, is_3d=True)
        self._apply_plot_settings(ax, is_3d=True)

        x = data[x_col].values
        y = data[y_col].values
        h = data[h_col].values

        # Get 3D plot options
        colormap_3d = getattr(self.main_window, 'colormap_3d', 'viridis')
        elevation = getattr(self.main_window, 'elevation_3d', 30)
        azimuth = getattr(self.main_window, 'azimuth_3d', 45)

        try:
            from scipy.interpolate import griddata
            xi = np.linspace(x.min(), x.max(), 50)
            yi = np.linspace(y.min(), y.max(), 50)
            xi, yi = np.meshgrid(xi, yi)
            zi = griddata((x, y), h, (xi, yi), method='cubic')

            # Get customization options
            surface_alpha = getattr(self.main_window, 'surface_alpha', 0.8)
            show_wireframe = getattr(self.main_window, 'show_wireframe', False)

            # Draw surface with customized alpha
            surf = ax.plot_surface(xi, yi, zi, cmap=colormap_3d, alpha=surface_alpha,
                                 edgecolor='none' if not show_wireframe else 'gray',
                                 linewidth=0.3 if show_wireframe else 0)
            if getattr(self.main_window, 'show_points', True):
                ax.scatter(x, y, h, c='white', s=30)

            self.canvas.fig.colorbar(surf, ax=ax, shrink=0.5, label='Hydraulic Head')
        except Exception:
            if getattr(self.main_window, 'show_points', True):
                ax.scatter(x, y, h, c=h, cmap=colormap_3d, s=50)

        # Set view angle
        ax.view_init(elev=elevation, azim=azimuth)

        ax.set_xlabel('X', color=Colors.PLOT_TEXT)
        ax.set_ylabel('Y', color=Colors.PLOT_TEXT)
        ax.set_zlabel('Head', color=Colors.PLOT_TEXT)

        # Re-store as regular axes for consistency
        self.canvas.ax = ax

    def _draw_gradient_vectors(self, data, x_col, y_col):
        """Draw gradient vector plot."""
        # Ensure we have 2D axes (not 3D)
        self.canvas.fig.clear()
        ax = self.canvas.fig.add_subplot(111)
        self.canvas.ax = ax
        self.canvas._apply_axis_theme(ax, self.canvas.fig)
        self._apply_plot_settings(ax)

        triangle_data = self.main_window.triangle_data
        if triangle_data is None or triangle_data.empty:
            ax.text(0.5, 0.5, 'No gradient data available',
                   transform=ax.transAxes, ha='center', color=Colors.PLOT_TEXT)
            return

        # Plot measurement points (if enabled)
        x = data[x_col].values
        y = data[y_col].values
        show_vector_points = getattr(self.main_window, 'show_vector_points', True)
        if show_vector_points:
            ax.scatter(x, y, c=Colors.ACCENT_PRIMARY, s=10, zorder=3, alpha=0.28, linewidths=0)

        # Get vector plot options
        vector_scale = getattr(self.main_window, 'vector_scale', 40)
        vector_alpha = getattr(self.main_window, 'vector_alpha', 0.8)
        colormap_vectors = getattr(self.main_window, 'colormap_vectors', 'viridis')
        max_vector_count = getattr(self.main_window, 'max_vector_count', 500)
        show_vector_id_labels = getattr(self.main_window, 'show_vector_id_labels', False)

        # Work on a view with stable IDs (preserve original index for selection labels).
        triangle_view = triangle_data.reset_index().rename(columns={"index": "triangle_index"})

        # Apply V1-style downsampling if needed (visualization only; does NOT mutate the dataset)
        # V1 behavior: preserve highest gradients + LTTB on remaining.
        if len(triangle_view) > max_vector_count:
            # Import via the same module layout used elsewhere in the app (MainWindow imports `core.*`)
            from core.downsampling import v1_style_vector_downsample_indices

            gradients_full = triangle_view['gradient'].apply(lambda g: g[0] if isinstance(g, (list, np.ndarray)) else g)
            sorted_tri = triangle_view.assign(_g=gradients_full).sort_values(by='_g', ascending=False)

            centroids = list(zip(sorted_tri['centroid_x'].to_numpy(), sorted_tri['centroid_y'].to_numpy()))
            keep_centroids = v1_style_vector_downsample_indices(
                centroids,
                max_count=max_vector_count,
                high_gradient_fraction=getattr(self.main_window, 'high_gradient_percentage', 0.2),
            )

            keep_df = pd.DataFrame(keep_centroids, columns=['centroid_x', 'centroid_y']).round(10)
            sorted_tri_round = sorted_tri.drop(columns=['_g']).round(10)
            triangle_view = sorted_tri_round.merge(keep_df, on=['centroid_x', 'centroid_y'], how='inner')

        # Plot gradient vectors with robust percentile normalization so long vectors
        # do not dominate the field visually.
        gradients = triangle_view['gradient'].apply(
            lambda g: g[0] if isinstance(g, (list, np.ndarray)) else g
        ).astype(float)
        angles = triangle_view['angle'].apply(
            lambda a: a[0] if isinstance(a, (list, np.ndarray)) else a
        ).astype(float)
        cx = triangle_view['centroid_x'].astype(float).to_numpy()
        cy = triangle_view['centroid_y'].astype(float).to_numpy()
        grad = gradients.to_numpy(dtype=float)
        angles_deg = angles.to_numpy(dtype=float)

        finite = np.isfinite(grad) & np.isfinite(angles_deg) & np.isfinite(cx) & np.isfinite(cy)
        if not np.any(finite):
            ax.text(0.5, 0.5, 'No finite vector values available',
                    transform=ax.transAxes, ha='center', color=Colors.PLOT_TEXT)
            return
        grad = grad[finite]
        angles_deg = angles_deg[finite]
        cx = cx[finite]
        cy = cy[finite]
        triangle_view = triangle_view.iloc[np.flatnonzero(finite)].reset_index(drop=True)

        norm = plt.Normalize(float(np.nanmin(grad)), float(np.nanmax(grad)))
        cmap = plt.get_cmap(colormap_vectors)

        span = max(float(np.nanmax(cx) - np.nanmin(cx)), float(np.nanmax(cy) - np.nanmin(cy)))
        if not np.isfinite(span) or span <= 0:
            span = 1.0
        g_ref = float(np.nanpercentile(grad, 95))
        if not np.isfinite(g_ref) or g_ref <= 0:
            g_ref = float(np.nanmax(grad)) if np.isfinite(np.nanmax(grad)) else 1.0
        g_ref = max(g_ref, 1e-12)

        # Vector length in data units, tuned to remain readable across datasets.
        base_min = 0.015 * span
        base_max = 0.060 * span
        user_scale = max(0.2, float(vector_scale) / 5.0)
        min_len = base_min * user_scale
        max_len = base_max * user_scale
        mag_t = np.clip(grad / g_ref, 0.0, 1.0)
        disp_len = min_len + (max_len - min_len) * mag_t

        angle_rad = np.deg2rad(angles_deg)
        u = np.cos(angle_rad) * disp_len
        v = np.sin(angle_rad) * disp_len

        # Draw lower gradients first and higher gradients last for prominence.
        order = np.argsort(grad, kind="mergesort")
        grad = grad[order]
        angles_deg = angles_deg[order]
        cx = cx[order]
        cy = cy[order]
        u = u[order]
        v = v[order]
        triangle_view = triangle_view.iloc[order].reset_index(drop=True)

        # ── Normalize mode: uniform arrow length to emphasise direction field ──
        normalize_vectors = getattr(self.main_window, 'normalize_vectors', False)
        if normalize_vectors:
            angle_rad_sorted = np.deg2rad(angles_deg)
            u = np.cos(angle_rad_sorted) * max_len
            v = np.sin(angle_rad_sorted) * max_len

        # ── Main colored quiver — drawn with C=grad so quiverkey works correctly ──
        quiv = ax.quiver(
            cx, cy, u, v,
            grad,
            cmap=cmap,
            norm=norm,
            alpha=max(0.65, vector_alpha),
            angles='xy',
            scale_units='xy',
            scale=1.0,
            width=0.0033,
            headwidth=4.6,
            headlength=5.6,
            headaxislength=5.0,
            minlength=0.0,
            pivot='tail',
            zorder=4,
        )

        # ── Per-arrow alpha fade applied post-draw (low-gradient = translucent) ──
        try:
            norm_g = np.clip(
                (grad - float(np.nanmin(grad))) / (float(np.nanmax(grad)) - float(np.nanmin(grad)) + 1e-12),
                0.0, 1.0,
            )
            alpha_arr = np.clip((0.30 + 0.70 * norm_g) * max(0.65, vector_alpha), 0.0, 1.0)
            fc = quiv.get_facecolors()
            if len(fc) == len(grad):
                fc = fc.copy()
                fc[:, 3] = alpha_arr
                quiv.set_facecolors(fc)
        except Exception:
            pass

        # ── Mean vector overlay ──
        # Use the same source as the 2D gradient arrow: gradient_calculator.calculate_average_gradient()
        # so direction is always consistent between plots regardless of downsampling.
        if getattr(self.main_window, 'show_mean_vector', True) and len(grad) > 0:
            mean_angle = None
            try:
                calc = getattr(self.main_window, 'gradient_calculator', None)
                if calc is not None:
                    _res = calc.calculate_average_gradient()
                    _avg_grad, _avg_angle_unweighted, _avg_angle_weighted = _res
                    if _avg_angle_unweighted is not None:
                        mean_angle = float(np.deg2rad(float(_avg_angle_unweighted)))
            except Exception:
                pass
            if mean_angle is None:
                # Fallback: weighted circular mean of displayed triangles
                angle_rad_all = np.deg2rad(angles_deg)
                mean_angle = np.arctan2(
                    float(np.sum(grad * np.sin(angle_rad_all))),
                    float(np.sum(grad * np.cos(angle_rad_all))),
                )
            mean_cx_val = float(np.mean(cx))
            mean_cy_val = float(np.mean(cy))
            arrow_dx = float(np.cos(mean_angle) * max_len)
            arrow_dy = float(np.sin(mean_angle) * max_len)
            tail_mx = mean_cx_val - arrow_dx * 0.5
            tail_my = mean_cy_val - arrow_dy * 0.5
            mean_patch = FancyArrow(
                tail_mx, tail_my, arrow_dx, arrow_dy,
                width=max_len * 0.065,
                head_width=max_len * 0.210,
                head_length=max_len * 0.280,
                length_includes_head=True,
                overhang=0.10,
                fc=Colors.ACCENT_PRIMARY,
                ec='none',
                zorder=10,
                alpha=0.92,
            )
            mean_patch.set_path_effects([pe.withStroke(linewidth=5.0, foreground='white')])
            ax.add_patch(mean_patch)
            tip_mx = mean_cx_val + arrow_dx * 0.5
            tip_my = mean_cy_val + arrow_dy * 0.5
            mean_deg = float(np.rad2deg(mean_angle)) % 360.0
            mean_dir_str = self._angle_to_cardinal(mean_deg)
            ax.annotate(
                f"Mean \u2207H  {mean_deg:.1f}\u00b0 {mean_dir_str}",
                xy=(tip_mx, tip_my),
                xytext=(12, 8),
                textcoords='offset points',
                ha='left', va='bottom',
                fontsize=8.5, fontweight='600',
                color=Colors.PLOT_TEXT,
                bbox=dict(
                    boxstyle='round,pad=0.38',
                    fc='white',
                    ec=Colors.ACCENT_PRIMARY,
                    alpha=0.92,
                ),
                annotation_clip=False,
                zorder=11,
            )

        # Optional: highlight globally-selected triangles (from histogram/rose) if enabled.
        try:
            if bool(getattr(self.main_window, "show_triangle_selection_overlay", False)):
                selected = getattr(self.main_window, "selected_triangle_indices", None)
                if selected:
                    selected_total = len(selected)
                    sel_view = triangle_view[triangle_view["triangle_index"].astype(int).isin([int(v) for v in selected])]
                    if not sel_view.empty:
                        ax.scatter(
                            sel_view["centroid_x"].astype(float).to_numpy(),
                            sel_view["centroid_y"].astype(float).to_numpy(),
                            s=220,
                            facecolors="none",
                            edgecolors=Colors.ACCENT_PRIMARY,
                            linewidths=2.2,
                            zorder=6,
                            label=f"Selected triangles shown: {len(sel_view)}/{selected_total}",
                        )
                        # Only show legend if selection exists (keeps plot clean by default).
                        ax.legend(loc="lower left", facecolor="white", edgecolor="#cccccc",
                                  fontsize=9, labelcolor="#333333", framealpha=0.95)
        except Exception:
            pass

        # Add colorbar (V1-style)
        try:
            from mpl_toolkits.axes_grid1 import make_axes_locatable

            divider = make_axes_locatable(ax)
            cax = divider.append_axes("right", size="3%", pad=0.1)
            cbar = self.canvas.fig.colorbar(quiv, cax=cax)
            cbar.set_label("Gradient Magnitude", color=Colors.PLOT_TEXT)
            cbar.ax.yaxis.set_tick_params(color=Colors.PLOT_AXIS)
            cbar.outline.set_edgecolor(Colors.PLOT_GRID)
            plt.setp(plt.getp(cbar.ax.axes, 'yticklabels'), color=Colors.PLOT_TEXT)
        except Exception:
            pass

        # Show vector triangle IDs if enabled
        if show_vector_id_labels:
            for _, row in triangle_view.iterrows():
                ax.annotate(
                    str(int(row.get('triangle_index', 0))),
                    (row['centroid_x'], row['centroid_y']),
                    xytext=(0, -8),
                    textcoords='offset points',
                    ha='center',
                    fontsize=7,
                    color=getattr(self.main_window, 'id_label_color', '#818cf8'),
                    alpha=0.8
                )

        # Interactivity: hover tooltip + click selection on vectors.
        self._install_gradient_vectors_interactivity(
            ax, data, triangle_view, cx, cy, grad, angles_deg, u, v
        )

        ax.set_xlabel(
            getattr(self.main_window, 'x_axis_label', 'X Coordinate [m]'),
            color=Colors.PLOT_TEXT,
            fontsize=getattr(self.main_window, 'axis_label_font_size', 11)
        )
        ax.set_ylabel(
            getattr(self.main_window, 'y_axis_label', 'Y Coordinate [m]'),
            color=Colors.PLOT_TEXT,
            fontsize=getattr(self.main_window, 'axis_label_font_size', 11)
        )
        ax.tick_params(labelsize=getattr(self.main_window, 'axis_tick_font_size', 9))
        self._apply_square_geo_axes(ax)
        self._apply_synced_geo_major_ticks(ax)

        # ── Scale legend: drawn after axes limits are finalised ──
        # Placed in data coordinates so the arrow is physically max_len units long.
        try:
            xlim = ax.get_xlim()
            ylim = ax.get_ylim()
            x_span = xlim[1] - xlim[0]
            y_span = ylim[1] - ylim[0]
            leg_x0 = xlim[0] + 0.04 * x_span
            leg_y  = ylim[0] + 0.045 * y_span
            g_ref_label = f'{g_ref:.5f} m/m' if g_ref < 0.1 else f'{g_ref:.4f} m/m'
            ax.annotate(
                '',
                xy=(leg_x0 + max_len, leg_y),
                xytext=(leg_x0, leg_y),
                arrowprops=dict(
                    arrowstyle='-|>',
                    color=Colors.PLOT_TEXT,
                    lw=1.4,
                    mutation_scale=10,
                ),
                zorder=20,
                annotation_clip=False,
            )
            ax.text(
                leg_x0 + max_len * 0.5, leg_y + 0.018 * y_span,
                f'\u2259 {g_ref_label}',
                ha='center', va='bottom',
                fontsize=7.5, color=Colors.PLOT_TEXT,
                bbox=dict(boxstyle='round,pad=0.25', fc='white', ec=Colors.PLOT_GRID, alpha=0.88),
                zorder=20,
            )
        except Exception:
            pass

    def _install_gradient_vectors_interactivity(self, ax, data, triangle_view, cx, cy, grad, angles_deg, u, v):
        if triangle_view is None or len(triangle_view) == 0:
            return

        id_col = self.main_window.col_mapping.get('ID') if hasattr(self.main_window, 'col_mapping') else None
        has_ids = id_col is not None and id_col in data.columns

        # Selection ring at centroid
        self._selection_marker = ax.scatter(
            [], [],
            s=220,
            facecolors="none",
            edgecolors=Colors.ACCENT_PRIMARY,
            linewidths=2.2,
            zorder=20,
        )

        # Hover annotation
        self._hover_annotation = self._popup_create(ax, zorder=30)
        self._hover_key = None

        # Highlight triangle member points (by ID) on this plot.
        highlight_pts = ax.scatter(
            [], [],
            s=140,
            facecolors="none",
            edgecolors=Colors.ERROR,
            linewidths=2.0,
            zorder=25,
        )
        self._highlight_artists.append(highlight_pts)

        def _closest_vector_index(event):
            if event.x is None or event.y is None:
                return None
            if event.inaxes != ax or event.xdata is None or event.ydata is None:
                return None
            # Compute nearest in pixel space for consistent behavior across zoom levels.
            pts_disp = ax.transData.transform(np.column_stack([cx, cy]))
            dx = pts_disp[:, 0] - float(event.x)
            dy = pts_disp[:, 1] - float(event.y)
            d2 = dx * dx + dy * dy
            i = int(np.argmin(d2))
            # 12 px threshold
            if float(d2[i]) <= 144.0:
                return i
            return None

        def _format_vector(i, verbose: bool):
            row = triangle_view.iloc[i]
            tri_id = row.get("triangle_index", None)
            tri_id_str = str(int(tri_id)) if tri_id is not None and str(tri_id).strip() != "" else "-"
            angle = float(angles_deg[i]) % 360.0
            g = float(grad[i])
            ids = row.get("point_ids", [])
            ids_str = ", ".join([str(v) for v in ids]) if isinstance(ids, (list, tuple, np.ndarray)) else str(ids)

            point_lines = []
            try:
                row_labels = row.get("point_row_labels", [])
                if isinstance(row_labels, (list, tuple, np.ndarray)) and len(row_labels) == 3:
                    x_col = self.main_window.col_mapping.get('x')
                    y_col = self.main_window.col_mapping.get('y')
                    h_col = self.main_window.col_mapping.get('hydraulic head')
                    if has_ids and x_col in data.columns and y_col in data.columns and h_col in data.columns:
                        pts = data.loc[list(row_labels), [id_col, x_col, y_col, h_col]].copy()
                        pts = pts.reset_index().rename(columns={"index": "row_label"})
                        # Preserve original ordering
                        pts["__order"] = [list(row_labels).index(v) for v in pts["row_label"].to_list()]
                        pts = pts.sort_values("__order", ascending=True)
                        for _, r in pts.iterrows():
                            point_lines.append(
                                f"{str(r[id_col])}: head={float(r[h_col]):.3f} @ ({float(r[x_col]):.3f}, {float(r[y_col]):.3f})"
                            )
                elif has_ids and isinstance(ids, (list, tuple, np.ndarray)) and len(ids) == 3:
                    # Fallback (duplicate IDs possible): list rows for each ID (bounded).
                    x_col = self.main_window.col_mapping.get('x')
                    y_col = self.main_window.col_mapping.get('y')
                    h_col = self.main_window.col_mapping.get('hydraulic head')
                    if x_col in data.columns and y_col in data.columns and h_col in data.columns:
                        for pid in [str(v) for v in ids]:
                            rows = data[data[id_col].astype(str) == pid].copy()
                            if rows.empty:
                                continue
                            rows = rows.head(3)
                            for idx2, r in rows.iterrows():
                                point_lines.append(
                                    f"{pid}[{idx2}]: head={float(r[h_col]):.3f} @ ({float(r[x_col]):.3f}, {float(r[y_col]):.3f})"
                                )
            except Exception:
                point_lines = []

            if verbose:
                lines = [
                    f"Gradient:   {g:.6f} m/m",
                    f"Direction:  {angle:.1f}°  {self._angle_to_cardinal(angle)}",
                    f"Points:     {ids_str}",
                ]
                lines.extend(point_lines)
                text = self._popup_compose(f"Triangle {tri_id_str}", lines=lines)
            else:
                text = self._popup_compose(
                    f"Triangle {tri_id_str}",
                    lines=[
                        f"Gradient:   {g:.6f} m/m",
                        f"Direction:  {angle:.1f}°  {self._angle_to_cardinal(angle)}",
                        f"Points:     {ids_str}",
                    ],
                )
            return row, text, ids

        def _set_selected(i):
            row, text, ids = _format_vector(i, verbose=True)
            self._selected_point = {"tri_idx": int(i), "ids": ids}
            self._selection_marker.set_offsets([[float(cx[i]), float(cy[i])]])

            if self._pinned_annotation is None:
                self._pinned_annotation = self._popup_create(ax, zorder=31)
                self._pinned_annotation.xy = (float(cx[i]), float(cy[i]))
                self._pinned_annotation.set_text(text)
                self._pinned_annotation.set_visible(True)
            else:
                self._pinned_annotation.xy = (float(cx[i]), float(cy[i]))
                self._pinned_annotation.set_text(text)
                self._pinned_annotation.set_visible(True)

            # Highlight member points (if we can map IDs to points in current data).
            if has_ids and isinstance(ids, (list, tuple, np.ndarray)) and len(ids) > 0:
                sel = data[data[id_col].astype(str).isin([str(v) for v in ids])]
                if not sel.empty:
                    x_col = self.main_window.col_mapping.get('x')
                    y_col = self.main_window.col_mapping.get('y')
                    if x_col in sel.columns and y_col in sel.columns:
                        highlight_pts.set_offsets(sel[[x_col, y_col]].to_numpy())
                else:
                    highlight_pts.set_offsets(np.empty((0, 2)))
            else:
                highlight_pts.set_offsets(np.empty((0, 2)))

            self._request_interaction_draw(force=True)

        def _clear_selected():
            self._selected_point = None
            if self._selection_marker is not None:
                self._selection_marker.set_offsets(np.empty((0, 2)))
            if self._pinned_annotation is not None:
                self._pinned_annotation.set_visible(False)
            highlight_pts.set_offsets(np.empty((0, 2)))
            self._request_interaction_draw(force=True)

        def _set_hover(i):
            if self._hover_key == i and self._hover_annotation.get_visible():
                return
            _, text, _ = _format_vector(i, verbose=False)
            self._hover_key = i
            self._hover_annotation.xy = (float(cx[i]), float(cy[i]))
            self._hover_annotation.set_text(text)
            self._hover_annotation.set_visible(True)
            self._request_interaction_draw()

        def _clear_hover():
            self._hover_key = None
            if self._hover_annotation is not None and self._hover_annotation.get_visible():
                self._hover_annotation.set_visible(False)
                self._request_interaction_draw()

        def on_hover(event):
            if event.inaxes != ax:
                _clear_hover()
                return
            if getattr(self.canvas, "_press", None) is not None and getattr(self.canvas, "_moved", False):
                _clear_hover()
                return
            if self._disable_hover_redraws:
                _clear_hover()
                return
            i = _closest_vector_index(event)
            if i is None:
                _clear_hover()
                return
            _set_hover(i)

        def on_click(event):
            if event.button != 1 or event.inaxes != ax:
                return
            try:
                self.canvas.setFocus()
            except Exception:
                pass
            if getattr(self.canvas, "_dragged_last", False):
                return
            i = _closest_vector_index(event)
            if i is None:
                _clear_selected()
                return
            if self._selected_point is not None and int(self._selected_point.get("tri_idx", -1)) == int(i):
                _clear_selected()
                return
            _set_selected(i)

        def on_press(event):
            if event.button != 1 or event.inaxes != ax:
                return
            if not getattr(event, "dblclick", False):
                return
            i = _closest_vector_index(event)
            if i is None:
                return
            row = triangle_view.iloc[int(i)]
            tri_id = row.get("triangle_index", None)
            if tri_id is None:
                return
            try:
                self.main_window.set_triangle_selection([int(tri_id)], meta={"source": "vector", "triangle": int(tri_id)})
                self.main_window.show_selection_inspector()
            except Exception as e:
                print(f"Selection inspector open failed: {e}")

        def apply_exclusion(exclude: bool):
            if self._selected_point is None:
                return
            ids = self._selected_point.get("ids", [])
            if not isinstance(ids, (list, tuple, np.ndarray)):
                return
            ids_str = [str(v) for v in ids]
            if exclude:
                self.main_window.excluded_ids.update(ids_str)
            else:
                for v in ids_str:
                    self.main_window.excluded_ids.discard(v)
            try:
                self.main_window.refilter_and_recalculate()
            except Exception:
                pass

        def on_key(event):
            if event.key in ("escape", "esc"):
                _clear_selected()
                return
            if event.key in ("e", "E"):
                apply_exclusion(True)
                return
            if event.key in ("i", "I"):
                apply_exclusion(False)
                return

        self._mpl_cids.append(self.canvas.mpl_connect("motion_notify_event", on_hover))
        self._mpl_cids.append(self.canvas.mpl_connect("button_press_event", on_press))
        self._mpl_cids.append(self.canvas.mpl_connect("button_release_event", on_click))
        self._mpl_cids.append(self.canvas.mpl_connect("key_press_event", on_key))

        # Store vector data for external highlight_points_by_ids
        self._vector_data_ref = {
            "triangle_view": triangle_view,
            "cx": cx, "cy": cy,
            "ax": ax,
            "highlight_pts": highlight_pts,
            "grad": grad,
            "angles_deg": angles_deg,
            "u": u,
            "v": v,
        }

    def _draw_histogram(self):
        """Draw gradient histogram."""
        # Ensure we have 2D axes
        self.canvas.fig.clear()
        ax = self.canvas.fig.add_subplot(111)
        self.canvas.ax = ax
        self.canvas._apply_axis_theme(ax, self.canvas.fig)
        self._apply_plot_settings(ax)

        triangle_data = self.main_window.triangle_data
        if triangle_data is None or triangle_data.empty:
            ax.text(0.5, 0.5, 'No gradient data available',
                   transform=ax.transAxes, ha='center', color=Colors.PLOT_TEXT)
            return

        gradients_series = triangle_data['gradient'].apply(
            lambda g: g[0] if isinstance(g, (list, np.ndarray)) else g
        )
        gradients_series = gradients_series.dropna().astype(float)
        if gradients_series.empty:
            ax.text(0.5, 0.5, 'No gradient data available',
                   transform=ax.transAxes, ha='center', color=Colors.PLOT_TEXT)
            return

        # Get histogram options
        num_bins = getattr(self.main_window, 'histogram_bins', 30)
        bar_color_name = getattr(self.main_window, 'histogram_bar_color', 'grey')
        edge_color_name = getattr(self.main_window, 'histogram_edge_color', 'black')
        show_mean = getattr(self.main_window, 'histogram_show_mean', False)
        show_median = getattr(self.main_window, 'histogram_show_median', False)
        show_ci = getattr(self.main_window, 'histogram_show_ci', False)
        show_kde = getattr(self.main_window, 'histogram_show_kde', False)
        ci_level = getattr(self.main_window, 'histogram_ci_level', 95)
        ci_resamples = getattr(self.main_window, 'histogram_ci_resamples', 200)

        # Map color names to actual colors
        color_map = {
            'grey': '#808080', 'blue': Colors.ACCENT_PRIMARY, 'green': '#4ade80',
            'red': '#ff6b6b', 'orange': '#fb923c', 'purple': '#a78bfa', 'teal': '#818cf8'
        }
        edge_map = {
            'black': '#000000', 'white': '#ffffff', 'grey': '#808080', 'none': 'none'
        }
        bar_color = color_map.get(bar_color_name, Colors.ACCENT_PRIMARY)
        edge_color = edge_map.get(edge_color_name, Colors.PLOT_BORDER)

        counts, bin_edges, patches = ax.hist(
            gradients_series.to_numpy(),
            bins=num_bins,
            color=bar_color,
            edgecolor=edge_color,
            alpha=0.8,
        )

        # Map each triangle to a histogram bin for selection.
        tri_idx = triangle_data.loc[gradients_series.index].index.to_numpy()
        vals = gradients_series.to_numpy()
        bin_index = np.digitize(vals, bin_edges, right=False) - 1
        bin_index = np.clip(bin_index, 0, len(bin_edges) - 2)
        triangles_by_bin = {i: [] for i in range(len(bin_edges) - 1)}
        for b, t in zip(bin_index.tolist(), tri_idx.tolist()):
            triangles_by_bin[int(b)].append(int(t))

        # Restore/reflect current global selection (if it came from histogram).
        selected_meta = getattr(self.main_window, "selection_meta", None)
        selected_bin = None
        if isinstance(selected_meta, dict) and selected_meta.get("source") == "histogram":
            try:
                selected_bin = int(selected_meta.get("bin"))
            except Exception:
                selected_bin = None

        if selected_bin is not None and 0 <= selected_bin < len(patches):
            try:
                patches[selected_bin].set_edgecolor(Colors.ACCENT_PRIMARY)
                patches[selected_bin].set_linewidth(2.5)
                patches[selected_bin].set_alpha(0.95)
            except Exception:
                pass

        legend_handles = []

        # Mean line (conditional)
        if show_mean:
            mean_grad = float(np.mean(vals))
            ax.axvline(mean_grad, color='#ff6b6b', linestyle='--', linewidth=2)
            legend_handles.append(
                plt.Line2D([0], [0], color='#ff6b6b', linestyle='--', linewidth=2, label=f"Mean: {mean_grad:.4f}")
            )
            if show_ci:
                ci = self._bootstrap_ci(vals, np.mean, level_pct=ci_level, resamples=ci_resamples)
                if ci is not None:
                    lo, hi = ci
                    ax.axvspan(lo, hi, color='#ff6b6b', alpha=0.12)
                    legend_handles.append(
                        plt.Line2D([0], [0], color='#ff6b6b', linestyle=':', linewidth=2,
                                   label=f"Approx {int(ci_level)}% CI (mean): {lo:.4f} - {hi:.4f}")
                    )

        # Median line (conditional) — green
        if show_median:
            median_grad = float(np.median(vals))
            ax.axvline(median_grad, color='#4ade80', linestyle='-.', linewidth=2)
            legend_handles.append(
                plt.Line2D([0], [0], color='#4ade80', linestyle='-.', linewidth=2, label=f"Median: {median_grad:.4f}")
            )
            if show_ci:
                ci = self._bootstrap_ci(vals, np.median, level_pct=ci_level, resamples=ci_resamples)
                if ci is not None:
                    lo, hi = ci
                    ax.axvspan(lo, hi, color='#4ade80', alpha=0.10)
                    legend_handles.append(
                        plt.Line2D([0], [0], color='#4ade80', linestyle=':', linewidth=2,
                                   label=f"Approx {int(ci_level)}% CI (median): {lo:.4f} - {hi:.4f}")
                    )

        # KDE curve overlay
        if show_kde and len(vals) >= 3:
            try:
                from scipy.stats import gaussian_kde as _gkde
                _kde = _gkde(vals, bw_method='scott')
                x_kde = np.linspace(float(np.min(vals)), float(np.max(vals)), 300)
                y_kde = _kde(x_kde)
                bin_width = (bin_edges[-1] - bin_edges[0]) / max(num_bins, 1)
                y_kde_scaled = y_kde * len(vals) * bin_width
                ax.plot(x_kde, y_kde_scaled, color=bar_color, linewidth=2.5,
                        linestyle='-', zorder=5, alpha=0.9)
                legend_handles.append(
                    plt.Line2D([0], [0], color=bar_color, linewidth=2.5, label='KDE')
                )
            except Exception:
                pass

        if legend_handles:
            ax.legend(handles=legend_handles, facecolor='white', edgecolor='#cccccc', labelcolor='#333333', fontsize=9)

        ax.set_xlabel('Gradient Magnitude', color=Colors.PLOT_TEXT)
        ax.set_ylabel('Frequency', color=Colors.PLOT_TEXT)
        ax.set_title('Hydraulic Gradient Distribution', color=Colors.PLOT_TEXT)

        # Interactivity: hover tooltip + click-to-select bin (sets global triangle selection).
        self._install_histogram_interactivity(ax, counts, bin_edges, patches, triangles_by_bin)

    def _install_histogram_interactivity(self, ax, counts, bin_edges, patches, triangles_by_bin):
        if patches is None or len(patches) == 0:
            return

        # Hover annotation
        self._hover_annotation = self._popup_create(ax, zorder=30)
        self._hover_key = None

        # Pinned selection annotation and drag-brush state.
        self._pinned_annotation = None
        selected_bins = set()
        brush_span = None
        drag_start_x = None
        drag_start_px = None
        drag_active = False

        def _bin_under_mouse(event):
            if event.inaxes != ax:
                return None
            for i, p in enumerate(patches):
                try:
                    hit, _ = p.contains(event)
                    if hit:
                        return int(i)
                except Exception:
                    continue
            if event.xdata is None:
                return None
            try:
                x = float(event.xdata)
            except Exception:
                return None
            i = int(np.searchsorted(bin_edges, x, side="right") - 1)
            if 0 <= i < (len(bin_edges) - 1):
                return i
            return None

        def _format_bin(i):
            lo = float(bin_edges[i])
            hi = float(bin_edges[i + 1])
            count = int(counts[i]) if i < len(counts) else 0
            total = int(np.sum(counts)) if len(counts) else 0
            pct = (100.0 * count / total) if total > 0 else 0.0
            return lo, hi, count, total, pct

        def _set_hover(i):
            if self._hover_key == i and self._hover_annotation.get_visible():
                return
            lo, hi, count, total, pct = _format_bin(i)
            self._hover_key = i
            self._hover_annotation.xy = (0.5 * (lo + hi), count)
            self._hover_annotation.set_text(
                self._popup_compose(
                    f"Bin  {lo:.5f} – {hi:.5f}",
                    lines=[f"Count:  {count} / {total}  ({pct:.1f}%)"],
                )
            )
            self._hover_annotation.set_visible(True)
            self._request_interaction_draw()

        def _clear_hover():
            self._hover_key = None
            if self._hover_annotation is not None and self._hover_annotation.get_visible():
                self._hover_annotation.set_visible(False)
                self._request_interaction_draw()

        def _apply_selected_style(i, on: bool):
            try:
                if on:
                    patches[i].set_edgecolor(Colors.ACCENT_PRIMARY)
                    patches[i].set_linewidth(2.5)
                    patches[i].set_alpha(0.95)
                else:
                    patches[i].set_edgecolor(Colors.PLOT_BORDER)
                    patches[i].set_linewidth(1.0)
                    patches[i].set_alpha(0.8)
            except Exception:
                pass

        def _clear_selection():
            nonlocal selected_bins
            for i in list(selected_bins):
                if 0 <= int(i) < len(patches):
                    _apply_selected_style(int(i), on=False)
            selected_bins = set()
            try:
                if hasattr(self.main_window, "clear_triangle_selection"):
                    self.main_window.clear_triangle_selection()
            except Exception:
                pass
            if self._pinned_annotation is not None:
                self._pinned_annotation.set_visible(False)
            self._request_interaction_draw(force=True)

        def _set_selected_bins(bin_indices, *, source: str, selected_range=None):
            nonlocal selected_bins
            valid = sorted({int(i) for i in (bin_indices or []) if 0 <= int(i) < len(patches)})
            if not valid:
                _clear_selection()
                return
            if len(valid) == 1 and selected_bins == {int(valid[0])}:
                _clear_selection()
                return

            for i in list(selected_bins):
                if 0 <= int(i) < len(patches):
                    _apply_selected_style(int(i), on=False)
            selected_bins = set(valid)
            for i in valid:
                _apply_selected_style(i, on=True)

            tri = []
            for i in valid:
                tri.extend(list(triangles_by_bin.get(int(i), []) or []))
            tri = sorted({int(v) for v in tri})

            lo = float(bin_edges[valid[0]])
            hi = float(bin_edges[valid[-1] + 1])
            if isinstance(selected_range, (tuple, list)) and len(selected_range) == 2:
                try:
                    lo = float(selected_range[0])
                    hi = float(selected_range[1])
                except Exception:
                    pass
            if lo > hi:
                lo, hi = hi, lo

            tri_count = int(len(tri))
            total_tri = int(np.sum(counts)) if len(counts) else 0
            pct = (100.0 * tri_count / total_tri) if total_tri > 0 else 0.0

            try:
                if hasattr(self.main_window, "set_triangle_selection"):
                    meta = {"source": str(source), "bins": list(valid), "range": (float(lo), float(hi)), "count": tri_count}
                    if len(valid) == 1:
                        meta["bin"] = int(valid[0])
                    self.main_window.set_triangle_selection(tri, meta=meta)
            except Exception:
                pass

            text = self._popup_compose(
                f"Bin  {lo:.5f} – {hi:.5f}",
                lines=[f"Count:  {tri_count} / {total_tri}  ({pct:.1f}%)"],
            )
            anchor_x = 0.5 * (float(lo) + float(hi))
            anchor_y = float(max([counts[i] for i in valid])) if valid else 0.0
            if self._pinned_annotation is None:
                self._pinned_annotation = self._popup_create(ax, zorder=31)
                self._pinned_annotation.xy = (anchor_x, anchor_y)
                self._pinned_annotation.set_text(text)
                self._pinned_annotation.set_visible(True)
            else:
                self._pinned_annotation.xy = (anchor_x, anchor_y)
                self._pinned_annotation.set_text(text)
                self._pinned_annotation.set_visible(True)
            self._request_interaction_draw(force=True)

        def _open_inspector_for_current_selection(preferred_bin=None):
            i = None
            if preferred_bin is not None:
                try:
                    i = int(preferred_bin)
                except Exception:
                    i = None
            if selected_bins:
                if i is None or i not in selected_bins:
                    i = int(sorted(selected_bins)[0])
            if i is not None and (i not in selected_bins):
                _set_selected_bins([int(i)], source="histogram")
            try:
                self.main_window.show_selection_inspector()
            except Exception as e:
                print(f"Selection inspector open failed: {e}")

        def on_hover(event):
            if event.inaxes != ax:
                _clear_hover()
                return
            if getattr(self.canvas, "_press", None) is not None and getattr(self.canvas, "_moved", False):
                _clear_hover()
                return
            if self._disable_hover_redraws:
                _clear_hover()
                return
            i = _bin_under_mouse(event)
            if i is None:
                _clear_hover()
                return
            _set_hover(i)

        suppress_release = False
        press_bin = None
        last_motion_xdata = None

        def on_click(event):
            nonlocal suppress_release, press_bin, drag_start_x, drag_start_px, drag_active, brush_span, last_motion_xdata
            if event.button != 1:
                return
            try:
                self.canvas.setFocus()
            except Exception:
                pass
            if suppress_release:
                suppress_release = False
                return
            if drag_start_x is not None and drag_active:
                x0 = float(drag_start_x)
                if event.inaxes == ax and event.xdata is not None:
                    x1 = float(event.xdata)
                elif last_motion_xdata is not None:
                    x1 = float(last_motion_xdata)
                else:
                    x1 = x0
                lo, hi = (x0, x1) if x0 <= x1 else (x1, x0)
                bins = []
                for bi in range(len(bin_edges) - 1):
                    blo = float(bin_edges[bi])
                    bhi = float(bin_edges[bi + 1])
                    if bhi >= lo and blo <= hi:
                        bins.append(int(bi))
                if bins:
                    _set_selected_bins(bins, source="histogram_brush", selected_range=(lo, hi))
                drag_start_x = None
                drag_start_px = None
                drag_active = False
                if brush_span is not None:
                    brush_span.set_visible(False)
                self._request_interaction_draw(force=True)
                return
            if event.inaxes != ax:
                drag_start_x = None
                drag_start_px = None
                drag_active = False
                press_bin = None
                return
            drag_start_x = None
            drag_start_px = None
            drag_active = False
            last_motion_xdata = None
            if brush_span is not None:
                brush_span.set_visible(False)
            if getattr(self.canvas, "_dragged_last", False):
                return
            i = press_bin if press_bin is not None else _bin_under_mouse(event)
            press_bin = None
            if i is None:
                return
            _set_selected_bins([int(i)], source="histogram")

        def on_press(event):
            nonlocal suppress_release, press_bin, drag_start_x, drag_start_px, drag_active, last_motion_xdata
            if event.button != 1 or event.inaxes != ax:
                return
            press_bin = _bin_under_mouse(event)
            if not getattr(event, "dblclick", False):
                drag_start_x = float(event.xdata) if event.xdata is not None else None
                drag_start_px = float(event.x) if event.x is not None else None
                drag_active = False
                last_motion_xdata = drag_start_x
                return
            i = press_bin
            if i is not None and selected_bins != {int(i)}:
                _set_selected_bins([int(i)], source="histogram")
            suppress_release = True
            _open_inspector_for_current_selection(preferred_bin=i)

        def on_motion(event):
            nonlocal drag_active, brush_span, last_motion_xdata
            if drag_start_x is None or drag_start_px is None:
                return
            if event.x is None:
                return
            if event.inaxes == ax and event.xdata is not None:
                last_motion_xdata = float(event.xdata)
            if abs(float(event.x) - float(drag_start_px)) < 8.0:
                return
            if event.inaxes != ax or event.xdata is None:
                return
            drag_active = True
            x0 = float(drag_start_x)
            x1 = float(event.xdata)
            lo, hi = (x0, x1) if x0 <= x1 else (x1, x0)
            if brush_span is not None:
                try:
                    brush_span.remove()
                except Exception:
                    pass
            brush_span = ax.axvspan(lo, hi, color=Colors.ACCENT_PRIMARY, alpha=0.10, zorder=5)
            _clear_hover()
            self._request_interaction_draw()

        def on_key(event):
            nonlocal drag_start_x, drag_start_px, drag_active, brush_span, press_bin, last_motion_xdata, suppress_release
            if event.key in ("escape", "esc"):
                drag_start_x = None
                drag_start_px = None
                drag_active = False
                press_bin = None
                last_motion_xdata = None
                suppress_release = False
                if brush_span is not None:
                    brush_span.set_visible(False)
                _clear_selection()
            elif event.key in ("enter", "return"):
                _open_inspector_for_current_selection()

        self._mpl_cids.append(self.canvas.mpl_connect("motion_notify_event", on_motion))
        self._mpl_cids.append(self.canvas.mpl_connect("motion_notify_event", on_hover))
        self._mpl_cids.append(self.canvas.mpl_connect("button_press_event", on_press))
        self._mpl_cids.append(self.canvas.mpl_connect("button_release_event", on_click))
        self._mpl_cids.append(self.canvas.mpl_connect("key_press_event", on_key))
    def _draw_rose_diagram(self):
        """Draw gradient direction rose diagram with dual mean lines."""
        # Clear and recreate as polar axes
        self.canvas.fig.clear()
        ax = self.canvas.fig.add_subplot(111, polar=True)
        self.canvas._apply_axis_theme(ax, self.canvas.fig, polar=True)
        self._apply_plot_settings(ax, polar=True)

        triangle_data = self.main_window.triangle_data
        if triangle_data is None or triangle_data.empty:
            ax.text(0, 0, 'No data', ha='center', color=Colors.PLOT_TEXT)
            self.canvas.ax = ax
            return

        # Extract angles and gradients (keep aligned indices for selection)
        angles_series = triangle_data['angle'].apply(
            lambda a: a[0] if isinstance(a, (list, np.ndarray)) else a
        )
        gradients_series = triangle_data['gradient'].apply(
            lambda g: g[0] if isinstance(g, (list, np.ndarray)) else g
        )
        tri_df = pd.DataFrame({"angle": angles_series, "gradient": gradients_series}).dropna()
        if tri_df.empty:
            ax.text(0, 0, 'No data', ha='center', color=Colors.PLOT_TEXT)
            self.canvas.ax = ax
            return

        tri_indices = tri_df.index.to_numpy()
        angles_deg = tri_df["angle"].astype(float).to_numpy() % 360.0
        gradients_array = tri_df["gradient"].astype(float).to_numpy()
        angles_rad = np.deg2rad(angles_deg)

        # Get rose diagram options
        num_bins = getattr(self.main_window, 'rose_bins', 16)
        show_mean = getattr(self.main_window, 'rose_show_mean', True)
        show_weighted_mean = getattr(self.main_window, 'rose_show_weighted_mean', True)
        show_median = getattr(self.main_window, 'rose_show_median', False)
        show_ci = getattr(self.main_window, 'rose_show_ci', False)
        ci_level = getattr(self.main_window, 'rose_ci_level', 95)
        ci_resamples = getattr(self.main_window, 'rose_ci_resamples', 200)
        rose_mode = getattr(self.main_window, 'rose_mode', 'count')  # 'count' or 'gradient_weighted'
        rose_color_name = getattr(self.main_window, 'rose_color', 'blue')

        # Map color names to actual colors
        color_map = {
            'blue': Colors.ACCENT_PRIMARY, 'red': '#ff6b6b', 'green': '#4ade80',
            'purple': '#a78bfa', 'orange': '#fb923c', 'teal': '#818cf8',
            'grey': '#808080', 'black': '#111827'
        }
        rose_color = color_map.get(rose_color_name, Colors.ACCENT_PRIMARY)

        # Histogram bins (match V1 offset behavior: shift bins by 5 degrees)
        # Important: use a 0..2π bin frame and shift the angles so we don't drop angles in (360-5, 360).
        offset_rad = float(np.deg2rad(5))
        edges = np.linspace(0.0, 2.0 * np.pi, num_bins + 1)
        widths = np.diff(edges)
        centers = (edges[:-1] + edges[1:]) / 2.0 - offset_rad

        angles_shifted = (angles_rad + offset_rad) % (2.0 * np.pi)

        if rose_mode == 'gradient_weighted':
            # Bar height = sum of gradient magnitudes in each bin
            bar_values, _ = np.histogram(angles_shifted, bins=edges, weights=gradients_array)
        else:
            # Bar height = count of triangles (V1 behavior)
            bar_values, _ = np.histogram(angles_shifted, bins=edges)

        bar_container = ax.bar(
            centers,
            bar_values,
            width=widths,
            color=rose_color,
            edgecolor='#1a1a1f',
            linewidth=0.55,
            alpha=0.85,
            zorder=2,
        )
        bars = getattr(bar_container, "patches", [])

        # Map triangles to bins for selection (use the same shifted frame as the bars).
        bin_index = np.searchsorted(edges, angles_shifted, side="right") - 1
        bin_index = np.clip(bin_index, 0, num_bins - 1)
        triangles_by_bin = {i: [] for i in range(num_bins)}
        for b, t in zip(bin_index.tolist(), tri_indices.tolist()):
            triangles_by_bin[int(b)].append(int(t))

        # Restore/reflect current global selection (if it came from rose diagram).
        selected_meta = getattr(self.main_window, "selection_meta", None)
        selected_bin = None
        if isinstance(selected_meta, dict) and selected_meta.get("source") == "rose":
            try:
                selected_bin = int(selected_meta.get("bin"))
            except Exception:
                selected_bin = None
        if selected_bin is not None and 0 <= selected_bin < len(bars):
            try:
                bars[selected_bin].set_edgecolor(Colors.ACCENT_PRIMARY)
                bars[selected_bin].set_linewidth(2.5)
                bars[selected_bin].set_alpha(0.95)
            except Exception:
                pass

        # Legend elements
        legend_handles = []

        # Mean direction lines (use the shared calculator for consistency across views)
        if hasattr(self.main_window, 'gradient_calculator'):
            result = self.main_window.gradient_calculator.calculate_average_gradient()
        else:
            result = None

        # Unweighted mean direction (red dashed)
        if show_mean and result and len(result) >= 2 and result[1] is not None:
            mean_angle_unweighted_deg = float(result[1])
            mean_angle_unweighted_rad = np.deg2rad(mean_angle_unweighted_deg)
            ax.axvline(mean_angle_unweighted_rad, color='#ff6b6b', linestyle='--', linewidth=2)

            if show_ci:
                ci = self._bootstrap_circular_ci(
                    angles_deg,
                    point_estimate_deg=mean_angle_unweighted_deg,
                    level_pct=ci_level,
                    resamples=ci_resamples,
                    weights=None,
                )
                if ci is not None:
                    lo_deg, hi_deg = ci
                    ax.axvline(np.deg2rad(lo_deg), color='#ff6b6b', linestyle=':', linewidth=1.5, alpha=0.9)
                    ax.axvline(np.deg2rad(hi_deg), color='#ff6b6b', linestyle=':', linewidth=1.5, alpha=0.9)
                    if lo_deg <= hi_deg:
                        range_str = f"{lo_deg:.1f}-{hi_deg:.1f}"
                    else:
                        range_str = f"{lo_deg:.1f}-360,0-{hi_deg:.1f}"
                    legend_handles.append(
                        plt.Line2D(
                            [0], [0],
                            color='#ff6b6b',
                            linestyle=':',
                            linewidth=2,
                            label=f"Approx {int(ci_level)}% CI (mean): {range_str} deg"
                        )
                    )
            legend_handles.append(
                plt.Line2D(
                    [0], [0],
                    color='#ff6b6b',
                    linestyle='--',
                    linewidth=2,
                    label=f'Mean Angle: {mean_angle_unweighted_deg:.1f}°'
                )
            )

        # Weighted mean direction (blue solid)
        if show_weighted_mean and result and len(result) >= 3 and result[2] is not None:
            mean_angle_weighted_deg = float(result[2])
            mean_angle_weighted_rad = np.deg2rad(mean_angle_weighted_deg)
            ax.axvline(mean_angle_weighted_rad, color='#818cf8', linestyle='-', linewidth=2.5)

            if show_ci:
                ci = self._bootstrap_circular_ci(
                    angles_deg,
                    point_estimate_deg=mean_angle_weighted_deg,
                    level_pct=ci_level,
                    resamples=ci_resamples,
                    weights=gradients_array,
                )
                if ci is not None:
                    lo_deg, hi_deg = ci
                    ax.axvline(np.deg2rad(lo_deg), color='#818cf8', linestyle=':', linewidth=1.5, alpha=0.9)
                    ax.axvline(np.deg2rad(hi_deg), color='#818cf8', linestyle=':', linewidth=1.5, alpha=0.9)
                    if lo_deg <= hi_deg:
                        range_str = f"{lo_deg:.1f}-{hi_deg:.1f}"
                    else:
                        range_str = f"{lo_deg:.1f}-360,0-{hi_deg:.1f}"
                    legend_handles.append(
                        plt.Line2D(
                            [0], [0],
                            color='#818cf8',
                            linestyle=':',
                            linewidth=2,
                            label=f"Approx {int(ci_level)}% CI (weighted): {range_str} deg"
                        )
                    )
            legend_handles.append(
                plt.Line2D(
                    [0], [0],
                    color='#818cf8',
                    linestyle='-',
                    linewidth=2.5,
                    label=f'Weighted Mean: {mean_angle_weighted_deg:.1f}°'
                )
            )

        # Circular median (L1 minimiser via dense grid search)
        if show_median and len(angles_rad) >= 2:
            try:
                _cands = np.linspace(0.0, 2.0 * np.pi, 720, endpoint=False)
                _costs = np.array([
                    np.sum(np.abs(np.angle(np.exp(1j * (angles_rad - c)))))
                    for c in _cands
                ])
                med_rad = float(_cands[np.argmin(_costs)])
                ax.axvline(med_rad, color='#4ade80', linestyle='-.', linewidth=2, zorder=6)
                legend_handles.append(
                    plt.Line2D(
                        [0], [0],
                        color='#4ade80',
                        linestyle='-.',
                        linewidth=2,
                        label=f'Median Angle: {np.rad2deg(med_rad) % 360:.1f}°'
                    )
                )
            except Exception:
                pass

        if legend_handles:
            ax.legend(handles=legend_handles, loc='upper right',
                     facecolor='white', edgecolor='#cccccc',
                     fontsize=9, labelcolor='#333333')

        # Mathematical convention orientation: 0°=East, 90°=North (counterclockwise)
        ax.set_theta_zero_location('E')  # 0° on the right
        ax.set_theta_direction(1)  # Counterclockwise (mathematical convention)

        # Set cardinal direction labels with degrees
        ax.set_thetagrids(
            [0, 45, 90, 135, 180, 225, 270, 315],
            labels=['0° E', '45°', 'N\n90°', '135°', 'W 180°', '225°', '270°\nS', '315°'],
            fontweight='bold',
            fontsize=9,
            color=Colors.PLOT_TEXT
        )

        # Mean resultant length + circular variance stats box
        if getattr(self.main_window, 'rose_show_mean_resultant', True):
            try:
                R = float(np.abs(np.mean(np.exp(1j * angles_rad))))
                circ_var = 1.0 - R
                stats_text = f"R = {R:.3f}    Circ. var. = {circ_var:.3f}"
                ax.text(
                    0.5, -0.08, stats_text,
                    transform=ax.transAxes,
                    ha='center', va='top',
                    fontsize=8.5, color=Colors.PLOT_TEXT,
                    bbox=dict(boxstyle='round,pad=0.35', fc='white', ec=Colors.PLOT_GRID, alpha=0.90),
                    zorder=20,
                )
            except Exception:
                pass

        # Add title indicating mode
        mode_label = "Gradient Sum" if rose_mode == 'gradient_weighted' else "Triangle Count"
        ax.set_title(f'Rose Diagram ({mode_label})', color=Colors.PLOT_TEXT, pad=20, fontsize=11)

        self.canvas.ax = ax

        # Interactivity: hover + click-to-select wedge (sets global triangle selection).
        self._install_rose_interactivity(ax, bars, edges, offset_rad, bar_values, triangles_by_bin, rose_mode)

    def _install_rose_interactivity(self, ax, bars, edges, offset_rad, bar_values, triangles_by_bin, rose_mode):
        if bars is None or len(bars) == 0:
            return

        self._hover_annotation = self._popup_create(ax, zorder=30)
        self._hover_key = None

        selected_bin = None

        def _bin_under_mouse(event):
            if event.inaxes != ax:
                return None
            # Prefer patch hit-testing (when possible); fallback to theta-based binning.
            for i, p in enumerate(bars):
                try:
                    hit, _ = p.contains(event)
                    if hit:
                        return int(i)
                except Exception:
                    continue

            if event.xdata is None:
                return None
            try:
                theta = float(event.xdata)
            except Exception:
                return None

            shifted = (theta + float(offset_rad)) % (2.0 * np.pi)
            i = int(np.searchsorted(edges, shifted, side="right") - 1)
            i = max(0, min(i, int(len(edges) - 2)))
            return i

        def _bin_range_deg(i):
            # Display range in the visual frame (shifted by -offset_rad).
            lo = float(np.rad2deg(float(edges[i]) - float(offset_rad)) % 360.0)
            hi = float(np.rad2deg(float(edges[i + 1]) - float(offset_rad)) % 360.0)
            return lo, hi

        def _format_bin(i):
            lo, hi = _bin_range_deg(i)
            val = float(bar_values[i]) if i < len(bar_values) else 0.0
            total = float(np.sum(bar_values)) if len(bar_values) else 0.0
            pct = (100.0 * val / total) if total > 0 else 0.0
            tri_count = len(triangles_by_bin.get(i, []))
            metric = "Gradient sum" if rose_mode == "gradient_weighted" else "Count"
            val_str = f"{val:.6f}" if rose_mode == "gradient_weighted" else f"{int(val)}"
            return lo, hi, metric, val_str, pct, tri_count

        def _set_hover(i):
            if self._hover_key == i and self._hover_annotation.get_visible():
                return
            lo, hi, metric, val_str, pct, tri_count = _format_bin(i)
            self._hover_key = i
            theta = float(0.5 * (edges[i] + edges[i + 1]) - float(offset_rad))
            r = float(bar_values[i]) if i < len(bar_values) else 0.0
            self._hover_annotation.xy = (theta, r)
            self._hover_annotation.set_text(
                self._popup_compose(
                    f"Sector  {lo:.1f}° – {hi:.1f}°",
                    lines=[
                        f"{metric}:  {val_str}  ({pct:.1f}%)",
                        f"Count:    {tri_count}",
                    ],
                )
            )
            self._hover_annotation.set_visible(True)
            self._request_interaction_draw()

        def _clear_hover():
            self._hover_key = None
            if self._hover_annotation is not None and self._hover_annotation.get_visible():
                self._hover_annotation.set_visible(False)
                self._request_interaction_draw()

        def _apply_selected_style(i, on: bool):
            try:
                if on:
                    bars[i].set_edgecolor(Colors.ACCENT_PRIMARY)
                    bars[i].set_linewidth(2.5)
                    bars[i].set_alpha(0.95)
                else:
                    bars[i].set_edgecolor('#ffffff')
                    bars[i].set_linewidth(1.0)
                    bars[i].set_alpha(0.85)
            except Exception:
                pass

        def _set_selected(i):
            nonlocal selected_bin
            if selected_bin is not None and 0 <= selected_bin < len(bars):
                _apply_selected_style(selected_bin, on=False)

            if selected_bin == i:
                selected_bin = None
                try:
                    if hasattr(self.main_window, "clear_triangle_selection"):
                        self.main_window.clear_triangle_selection()
                except Exception:
                    pass
                if self._pinned_annotation is not None:
                    self._pinned_annotation.set_visible(False)
                self._request_interaction_draw(force=True)
                return

            selected_bin = int(i)
            _apply_selected_style(selected_bin, on=True)

            tri = triangles_by_bin.get(selected_bin, [])
            lo, hi = _bin_range_deg(selected_bin)
            try:
                if hasattr(self.main_window, "set_triangle_selection"):
                    self.main_window.set_triangle_selection(
                        tri,
                        meta={"source": "rose", "bin": selected_bin, "range_deg": (lo, hi), "mode": rose_mode},
                    )
            except Exception:
                pass

            theta = float(0.5 * (edges[selected_bin] + edges[selected_bin + 1]) - float(offset_rad))
            r = float(bar_values[selected_bin]) if selected_bin < len(bar_values) else 0.0
            metric = "Gradient sum" if rose_mode == "gradient_weighted" else "Count"
            val = float(bar_values[selected_bin]) if selected_bin < len(bar_values) else 0.0
            val_str = f"{val:.6f}" if rose_mode == "gradient_weighted" else f"{int(val)}"
            text = self._popup_compose(
                f"Sector  {lo:.1f}° – {hi:.1f}°",
                lines=[
                    f"{metric}:  {val_str}",
                    f"Count:    {len(tri)}",
                ],
            )

            if self._pinned_annotation is None:
                self._pinned_annotation = self._popup_create(ax, zorder=31)
                self._pinned_annotation.xy = (theta, r)
                self._pinned_annotation.set_text(text)
                self._pinned_annotation.set_visible(True)
            else:
                self._pinned_annotation.xy = (theta, r)
                self._pinned_annotation.set_text(text)
                self._pinned_annotation.set_visible(True)
            self._request_interaction_draw(force=True)

        def _open_inspector_for_current_selection(preferred_bin=None):
            i = None
            if preferred_bin is not None:
                try:
                    i = int(preferred_bin)
                except Exception:
                    i = None
            if selected_bin is not None:
                i = int(selected_bin)
            if i is not None and selected_bin != i:
                _set_selected(i)
            try:
                self.main_window.show_selection_inspector()
            except Exception as e:
                print(f"Selection inspector open failed: {e}")

        ignore_next_release = False

        def on_hover(event):
            if event.inaxes != ax:
                _clear_hover()
                return
            if getattr(self.canvas, "_press", None) is not None and getattr(self.canvas, "_moved", False):
                _clear_hover()
                return
            if self._disable_hover_redraws:
                _clear_hover()
                return
            i = _bin_under_mouse(event)
            if i is None:
                _clear_hover()
                return
            _set_hover(i)

        def on_click(event):
            if event.button != 1 or event.inaxes != ax:
                return
            try:
                self.canvas.setFocus()
            except Exception:
                pass
            nonlocal ignore_next_release
            if ignore_next_release:
                ignore_next_release = False
                return
            if getattr(self.canvas, "_dragged_last", False):
                return
            i = _bin_under_mouse(event)
            if i is None:
                return
            _set_selected(i)

        def on_press(event):
            nonlocal ignore_next_release
            if event.button != 1 or event.inaxes != ax:
                return
            if not getattr(event, "dblclick", False):
                return
            i = _bin_under_mouse(event)
            if i is not None and selected_bin != i:
                _set_selected(i)
            ignore_next_release = True
            _open_inspector_for_current_selection(preferred_bin=i)

        def on_key(event):
            if event.key in ("escape", "esc"):
                nonlocal selected_bin
                if selected_bin is not None and 0 <= selected_bin < len(bars):
                    _apply_selected_style(selected_bin, on=False)
                    selected_bin = None
                try:
                    if hasattr(self.main_window, "clear_triangle_selection"):
                        self.main_window.clear_triangle_selection()
                except Exception:
                    pass
                if self._pinned_annotation is not None:
                    self._pinned_annotation.set_visible(False)
                self._request_interaction_draw(force=True)

        self._mpl_cids.append(self.canvas.mpl_connect("motion_notify_event", on_hover))
        self._mpl_cids.append(self.canvas.mpl_connect("button_press_event", on_press))
        self._mpl_cids.append(self.canvas.mpl_connect("button_release_event", on_click))
        self._mpl_cids.append(self.canvas.mpl_connect("key_press_event", on_key))

    @staticmethod
    def _format_compass_span(value: float) -> str:
        try:
            v = abs(float(value))
        except Exception:
            return "0"
        if v >= 1000.0:
            return f"{v:,.0f}"
        if v >= 100.0:
            return f"{v:.1f}"
        if v >= 10.0:
            return f"{v:.2f}"
        return f"{v:.3f}"

    def _on_compass_axis_changed(self, _ax):
        self._update_compass_metrics_text()

    def _update_compass_metrics_text(self):
        txt = self._compass_view_text
        ax = self._compass_parent_ax
        if txt is None or ax is None:
            return
        try:
            x0, x1 = ax.get_xlim()
            y0, y1 = ax.get_ylim()
            dx = abs(float(x1) - float(x0))
            dy = abs(float(y1) - float(y0))
            cx = 0.5 * (float(x0) + float(x1))
            cy = 0.5 * (float(y0) + float(y1))
            if bool(getattr(self, "_compass_show_center", False)):
                txt.set_text(
                    f"X {self._format_compass_span(dx)}  Y {self._format_compass_span(dy)}\n"
                    f"C {self._format_compass_span(cx)}, {self._format_compass_span(cy)}"
                )
            else:
                txt.set_text(f"X {self._format_compass_span(dx)}  Y {self._format_compass_span(dy)}")
        except Exception:
            pass

    def _clear_compass_overlay(self):
        ax = self._compass_parent_ax
        if ax is not None:
            try:
                if self._compass_xlim_cid is not None:
                    ax.callbacks.disconnect(self._compass_xlim_cid)
            except Exception:
                pass
            try:
                if self._compass_ylim_cid is not None:
                    ax.callbacks.disconnect(self._compass_ylim_cid)
            except Exception:
                pass
        self._compass_xlim_cid = None
        self._compass_ylim_cid = None
        self._compass_parent_ax = None
        self._compass_view_text = None
        self._compass_show_center = False

        if self._compass_ax is not None:
            try:
                self._compass_ax.remove()
            except Exception:
                pass
            self._compass_ax = None

    def _sync_compass_overlay(self):
        show = bool(getattr(self.main_window, "show_compass", True))
        current_type = normalize_plot_type(getattr(self.main_window, "current_plot_type", "2D"))
        spatial_types = {"2D", "Gradient Vectors", "3D"}
        if (not show) or (current_type not in spatial_types):
            self._clear_compass_overlay()
            return

        ax = getattr(self.canvas, "ax", None)
        if ax is None:
            self._clear_compass_overlay()
            return

        # Keep compass in 2D axes only; 3D projection and polar plots are intentionally excluded.
        if str(getattr(ax, "name", "")).lower() in {"3d", "polar"}:
            self._clear_compass_overlay()
            return

        self._draw_compass(ax)

    def _draw_compass(self, ax):
        """Draw an in-plot compass overlay anchored inside the current axes."""
        from matplotlib.patches import Polygon as MplPolygon

        self._clear_compass_overlay()

        min_dim_px = float(min(max(self.canvas.width(), 1), max(self.canvas.height(), 1)))
        target_px = float(np.clip(min_dim_px * 0.17, 78.0, 128.0))
        size_pct = float(np.clip((target_px / max(min_dim_px, 1.0)) * 100.0, 14.0, 28.0))
        detail_rich = size_pct >= 18.0

        try:
            compass_loc = "upper left" if bool(getattr(self.main_window, "show_legend", False)) else "upper right"
            comp_ax = inset_axes(
                ax,
                width=f"{size_pct:.1f}%",
                height=f"{size_pct:.1f}%",
                loc=compass_loc,
                borderpad=0.9,
            )
        except Exception:
            return

        self._compass_ax = comp_ax
        self._compass_parent_ax = ax

        comp_ax.set_xlim(0, 1)
        comp_ax.set_ylim(0, 1)
        comp_ax.set_aspect("equal")
        comp_ax.axis("off")

        dark = bool(getattr(self, "_dark_canvas", False))
        face = "#171b22" if dark else "#f8fafc"
        edge = "#5b6476" if dark else "#c2cad8"
        major = "#8f9bb3" if dark else "#64748b"
        minor = "#657086" if dark else "#a0aabc"
        text = "#d7dceb" if dark else "#334155"
        subtle = "#8a94a8" if dark else "#64748b"

        center_x, center_y = 0.5, 0.60
        r_outer = 0.35
        r_inner = 0.28

        bg = plt.Circle((center_x, center_y), r_outer, facecolor=face, edgecolor=edge, linewidth=1.15, alpha=0.95, zorder=1)
        ring_inner = plt.Circle((center_x, center_y), r_inner, facecolor="none", edgecolor=edge, linewidth=0.9, alpha=0.95, zorder=1)
        comp_ax.add_patch(bg)
        comp_ax.add_patch(ring_inner)

        for deg in range(0, 360, 15):
            ang = np.deg2rad(float(deg))
            is_major = (deg % 45) == 0
            r0 = (r_inner - 0.055) if is_major else (r_inner - 0.03)
            r1 = r_outer - 0.01
            x0 = center_x + r0 * np.cos(ang)
            y0 = center_y + r0 * np.sin(ang)
            x1 = center_x + r1 * np.cos(ang)
            y1 = center_y + r1 * np.sin(ang)
            comp_ax.plot(
                [x0, x1],
                [y0, y1],
                color=major if is_major else minor,
                linewidth=1.0 if is_major else 0.7,
                alpha=0.95,
                zorder=2,
            )

        cardinals = {
            "N": (0.0, +1.0, Colors.ACCENT_PRIMARY),
            "E": (+1.0, 0.0, text),
            "S": (0.0, -1.0, text),
            "W": (-1.0, 0.0, text),
        }
        for label, (dx, dy, color) in cardinals.items():
            x0 = center_x + (r_inner + 0.03) * dx
            y0 = center_y + (r_inner + 0.03) * dy
            comp_ax.text(
                x0,
                y0,
                label,
                ha="center",
                va="center",
                fontsize=8.8 if detail_rich else 7.6,
                fontweight="bold",
                color=color,
                zorder=5,
            )

        if detail_rich:
            for deg in (0, 90, 180, 270):
                ang = np.deg2rad(float(deg))
                x0 = center_x + (r_outer + 0.035) * np.cos(ang)
                y0 = center_y + (r_outer + 0.035) * np.sin(ang)
                comp_ax.text(
                    x0,
                    y0,
                    f"{deg}",
                    ha="center",
                    va="center",
                    fontsize=6.1,
                    color=subtle,
                    zorder=4,
                )

        north_tip = (center_x, center_y + r_inner - 0.015)
        north_left = (center_x - 0.035, center_y + 0.005)
        north_right = (center_x + 0.035, center_y + 0.005)
        south_tip = (center_x, center_y - r_inner + 0.015)
        south_left = (center_x - 0.032, center_y - 0.005)
        south_right = (center_x + 0.032, center_y - 0.005)
        comp_ax.add_patch(
            MplPolygon([north_tip, north_left, north_right], closed=True, facecolor=Colors.ACCENT_PRIMARY, edgecolor="none", zorder=6)
        )
        comp_ax.add_patch(
            MplPolygon([south_tip, south_left, south_right], closed=True, facecolor=subtle, edgecolor="none", zorder=6, alpha=0.9)
        )
        comp_ax.plot(
            [center_x, center_x],
            [center_y - 0.16, center_y + 0.16],
            color=major,
            linewidth=0.9,
            alpha=0.8,
            zorder=5,
        )
        comp_ax.plot([center_x], [center_y], marker="o", markersize=2.5, color=major, zorder=7)

        self._compass_show_center = bool(detail_rich and size_pct >= 22.0)
        metrics_font = 5.5 if detail_rich else 5.1
        metrics_y = 0.085 if self._compass_show_center else 0.065
        self._compass_view_text = comp_ax.text(
            0.5,
            metrics_y,
            "",
            ha="center",
            va="center",
            fontsize=metrics_font,
            color=text,
            zorder=8,
            bbox=dict(
                boxstyle="round,pad=0.16",
                fc=face,
                ec=edge,
                alpha=0.9,
                linewidth=0.8,
            ),
        )

        # Keep values in sync with current view span while zooming/panning.
        self._update_compass_metrics_text()

        try:
            self._compass_xlim_cid = ax.callbacks.connect("xlim_changed", self._on_compass_axis_changed)
            self._compass_ylim_cid = ax.callbacks.connect("ylim_changed", self._on_compass_axis_changed)
        except Exception:
            self._compass_xlim_cid = None
            self._compass_ylim_cid = None

    def _draw_gradient_arrow(self, ax, data, x_col, y_col):
        """Draw average gradient arrow as a prominent FancyArrow with optional inline label."""
        try:
            result = self.main_window.gradient_calculator.calculate_average_gradient()
            avg_gradient, avg_angle_unweighted, avg_angle_weighted = result
            avg_angle = avg_angle_unweighted  # V1 behavior: use unweighted angle

            if not (avg_gradient and avg_angle):
                return

            # Arrow center — user-specified or data median
            arrow_start_x = getattr(self.main_window, 'arrow_start_x', None)
            arrow_start_y = getattr(self.main_window, 'arrow_start_y', None)
            if arrow_start_x is not None and arrow_start_y is not None:
                cx, cy = float(arrow_start_x), float(arrow_start_y)
            else:
                cx = float(data[x_col].median())
                cy = float(data[y_col].median())

            angle_rad = np.deg2rad(float(avg_angle))
            ux = np.cos(angle_rad)   # unit vector x
            uy = np.sin(angle_rad)   # unit vector y

            # Arrow length: 22% of the larger visible axis span
            xlim = ax.get_xlim()
            ylim = ax.get_ylim()
            x_span = xlim[1] - xlim[0]
            y_span = ylim[1] - ylim[0]
            arrow_len = max(x_span, y_span) * 0.22

            dx = ux * arrow_len
            dy = uy * arrow_len
            tail_x = cx - dx * 0.5
            tail_y = cy - dy * 0.5

            arrow_color = getattr(self.main_window, 'arrow_color', Colors.ACCENT_PRIMARY)

            shaft_w   = arrow_len * 0.050
            head_w    = arrow_len * 0.170
            head_len  = arrow_len * 0.230

            patch = FancyArrow(
                tail_x, tail_y, dx, dy,
                width=shaft_w,
                head_width=head_w,
                head_length=head_len,
                length_includes_head=True,
                overhang=0.10,
                fc=arrow_color,
                ec='none',
                zorder=100,
                alpha=0.92,
            )
            # White halo separates the arrow from background and points
            patch.set_path_effects([pe.withStroke(linewidth=4.0, foreground='white')])
            ax.add_patch(patch)
            patch.set_picker(True)

            self._mean_arrow_artist = patch
            self._mean_arrow_info = {
                "avg_gradient": float(avg_gradient),
                "angle_unweighted": float(avg_angle_unweighted) if avg_angle_unweighted is not None else None,
                "angle_weighted": float(avg_angle_weighted) if avg_angle_weighted is not None else None,
                "cx": float(cx),
                "cy": float(cy),
            }

            # ── Optional label near arrowhead (horizontal, always readable) ──
            show_label = getattr(self.main_window, 'show_arrow_label', True)
            if show_label:
                cardinal = self._angle_to_cardinal(float(avg_angle))
                label_text = f"{float(avg_gradient):.5f} m/m  •  {float(avg_angle):.1f}°  {cardinal}"

                # Tip of the arrowhead in data coordinates
                tip_x = cx + dx * 0.5
                tip_y = cy + dy * 0.5

                # Offset label in screen pixels so it clears the arrowhead on all sides.
                # Push perpendicular to the arrow direction so it doesn't sit on the shaft.
                # xytext uses offset points from the tip — pick the side that keeps the
                # label from drifting outside the axes.
                off_px =  14
                off_py =  10
                ax.annotate(
                    label_text,
                    xy=(tip_x, tip_y),
                    xytext=(off_px, off_py),
                    textcoords='offset points',
                    ha='left', va='bottom',
                    fontsize=9,
                    fontweight='600',
                    color=Colors.PLOT_TEXT,
                    bbox=dict(
                        boxstyle='round,pad=0.35',
                        fc='white',
                        ec=Colors.PLOT_BORDER,
                        alpha=0.90,
                    ),
                    annotation_clip=False,
                    zorder=101,
                )
        except Exception:
            pass

    def highlight_point_by_id(self, id_value):
        """Highlight a point on the plot by its ID (called from table selection)."""
        if self._2d_data_ref is None:
            return

        id_str = str(id_value)

        # Preferred path: use shared 2D multi-select setter.
        if self._2d_set_selected_ids_fn is not None:
            self._2d_set_selected_ids_fn([id_str])
            return

        if self._2d_set_selected_fn is None:
            return

        # Search included points first
        info = self._2d_data_ref.get("included")
        if info:
            for i, pid in enumerate(info["id"]):
                if str(pid) == id_str:
                    status = "EXCLUDED" if info["excluded"][i] else "INCLUDED"
                    self._2d_set_selected_fn(pid, info["x"][i], info["y"][i], info["h"][i], status)
                    return

        # Then excluded points
        info = self._2d_data_ref.get("excluded")
        if info:
            for i, pid in enumerate(info["id"]):
                if str(pid) == id_str:
                    status = "EXCLUDED" if info["excluded"][i] else "INCLUDED"
                    self._2d_set_selected_fn(pid, info["x"][i], info["y"][i], info["h"][i], status)
                    return

    def clear_point_highlight(self):
        """Clear any highlighted point on the plot (called from table deselection)."""
        if self._2d_clear_selected_fn is not None:
            self._2d_clear_selected_fn()
        self._clear_vector_focus_selection()
        self._clear_vector_highlights()

    def highlight_points_by_ids(self, id_values):
        """Highlight multiple points on the plot by their IDs (from table multi-select).

        For 2D plots: uses the shared multi-select mechanism.
        For vector plots: highlights all arrows whose triangle contains any selected point.
        """
        if not id_values:
            self.clear_point_highlight()
            return

        # 2D highlight for all selected points
        if self._2d_set_selected_ids_fn is not None:
            self._2d_set_selected_ids_fn(id_values)
        elif self._2d_data_ref is not None and self._2d_set_selected_fn is not None:
            self.highlight_point_by_id(id_values[0])

        # Vector plot: highlight all arrows connected to ANY selected point
        if self._vector_data_ref is not None:
            self._highlight_vectors_for_points(id_values)

    def _highlight_vectors_for_points(self, id_values):
        """On gradient vector plot, highlight arrows containing any of the given point IDs."""
        if self._vector_data_ref is None:
            return
        # Table-driven highlight should reflect table state only; clear any stale
        # click-selected vector marker/annotation first.
        self._clear_vector_focus_selection()
        self._clear_vector_highlights()

        try:
            triangle_view = self._vector_data_ref["triangle_view"]
            cx = self._vector_data_ref["cx"]
            cy = self._vector_data_ref["cy"]
            ax = self._vector_data_ref["ax"]

            if triangle_view is None or len(triangle_view) == 0:
                return

            # Accept both plain IDs ("P12") and member keys ("P12::row_label").
            member_tokens = set()
            plain_tokens = set()
            for v in (id_values or []):
                tok = str(v).strip()
                if not tok:
                    continue
                if "::" in tok:
                    member_tokens.add(tok)
                else:
                    plain_tokens.add(tok)

            # Find triangles where any point_id is in our selection
            def _row_matches(row):
                ids = row.get("point_ids", [])
                if not isinstance(ids, (list, tuple, np.ndarray)):
                    return False
                ids_list = [str(v) for v in ids]

                # Exact member match when row labels are available.
                if member_tokens:
                    row_labels = row.get("point_row_labels", None)
                    if isinstance(row_labels, (list, tuple, np.ndarray)) and len(row_labels) == len(ids_list):
                        member_here = {f"{pid}::{str(r)}" for pid, r in zip(ids_list, list(row_labels))}
                        if member_here.intersection(member_tokens):
                            return True
                    else:
                        # Fallback for rows without member labels: degrade to base-ID matching.
                        member_base = {str(t).split("::", 1)[0] for t in member_tokens}
                        if any(pid in member_base for pid in ids_list):
                            return True

                if plain_tokens and any(pid in plain_tokens for pid in ids_list):
                    return True
                return False

            mask = triangle_view.apply(_row_matches, axis=1)
            matching = triangle_view[mask]

            if matching.empty:
                return

            # Highlight matching arrow centroids with accent rings
            match_cx = matching['centroid_x'].astype(float).to_numpy()
            match_cy = matching['centroid_y'].astype(float).to_numpy()

            scatter = ax.scatter(
                match_cx, match_cy,
                s=260,
                facecolors="none",
                edgecolors=Colors.ACCENT_BRIGHT,
                linewidths=2.5,
                zorder=25,
                alpha=0.8,
            )
            self._vector_highlight_artists.append(scatter)

            # Also highlight the selected measurement points themselves
            data = getattr(self.main_window, 'filtered_data', None)
            if data is None:
                data = getattr(self.main_window, 'data', None)
            if data is not None:
                id_col = self.main_window.col_mapping.get('ID')
                x_col = self.main_window.col_mapping.get('x')
                y_col = self.main_window.col_mapping.get('y')
                if id_col and x_col and y_col and id_col in data.columns:
                    sel = data.iloc[0:0]
                    try:
                        if member_tokens:
                            member_series = data[id_col].astype(str) + "::" + data.index.astype(str)
                            sel = data[member_series.isin(member_tokens)]
                    except Exception:
                        sel = data.iloc[0:0]
                    if sel.empty and plain_tokens:
                        sel = data[data[id_col].astype(str).isin(plain_tokens)]
                    if not sel.empty:
                        # Draw matched vectors again as a "ghost" highlight layer.
                        try:
                            v_u = self._vector_data_ref.get("u")
                            v_v = self._vector_data_ref.get("v")
                            if v_u is not None and v_v is not None:
                                mask_arr = mask.to_numpy(dtype=bool)
                                sel_u = v_u[mask_arr]
                                sel_v = v_v[mask_arr]
                                sel_cx = self._vector_data_ref.get("cx")[mask_arr]
                                sel_cy = self._vector_data_ref.get("cy")[mask_arr]
                                if len(sel_u) > 0:
                                    ghost = ax.quiver(
                                        sel_cx, sel_cy,
                                        sel_u, sel_v,
                                        color="#FF3333",
                                        facecolor='none',
                                        edgecolor='#FF3333',
                                        linewidth=1.5,
                                        angles='xy',
                                        scale_units='xy',
                                        scale=1.0,
                                        zorder=200,
                                        headwidth=4,
                                        headlength=5,
                                        width=0.012,
                                    )
                                    self._vector_highlight_artists.append(ghost)
                        except Exception:
                            pass

                        # Fallback/Additional: Highlight point locations
                        pt_scatter = ax.scatter(
                            sel[x_col].astype(float).to_numpy(),
                            sel[y_col].astype(float).to_numpy(),
                            s=180,
                            facecolors="none",
                            edgecolors=Colors.ACCENT_PRIMARY,
                            linewidths=2.5,
                            zorder=200,
                        )
                        self._vector_highlight_artists.append(pt_scatter)

            self.canvas.draw_idle()

        except Exception:
            pass

    def _clear_vector_highlights(self):
        """Remove any vector highlight artists."""
        for a in self._vector_highlight_artists:
            try:
                a.remove()
            except Exception:
                pass
        self._vector_highlight_artists = []

    def _clear_vector_focus_selection(self):
        """Clear focused vector selection marker/annotations (click state)."""
        try:
            self._selected_point = None
        except Exception:
            pass
        try:
            if self._selection_marker is not None:
                self._selection_marker.set_offsets(np.empty((0, 2)))
        except Exception:
            pass
        try:
            if self._pinned_annotation is not None:
                self._pinned_annotation.set_visible(False)
        except Exception:
            pass
        try:
            if self._hover_annotation is not None:
                self._hover_annotation.set_visible(False)
        except Exception:
            pass
        try:
            self._request_interaction_draw(force=True)
        except Exception:
            pass

    # --------------------------------------------------
    #  COMPASS + HINT BAR OVERLAY CONTROL
    # --------------------------------------------------

    def set_compass_visible(self, visible: bool):
        """Show or hide the in-plot compass overlay."""
        try:
            self.main_window.show_compass = bool(visible)
        except Exception:
            pass
        self._sync_compass_overlay()
        self._request_interaction_draw(force=True)

    def set_hint_plot_type(self, plot_type: str):
        """Update hint bar for a new plot type."""
        if hasattr(self, '_hint_bar'):
            self._hint_bar.set_plot_type(plot_type)

    # --------------------------------------------------
    #  TRIANGLE SELECTION OVERLAY
    # --------------------------------------------------

    def highlight_triangles(self, triangle_data: list):
        """Draw polygon overlays for selected triangles on the current axes.

        Args:
            triangle_data: list of dicts with keys:
                'point_coords': [(x1,y1), (x2,y2), (x3,y3)]
                'status': "kept" or "rejected"
                'gradient': float or None
                'angle': float or None (degrees)
                'centroid_x': float or None
                'centroid_y': float or None
        """
        from matplotlib.patches import Polygon as MplPolygon

        self.clear_triangle_overlay()

        ax = self.canvas.ax

        for tri in triangle_data:
            coords = tri.get('point_coords', [])
            status = str(tri.get('status', 'kept') or 'kept').strip().lower()

            if len(coords) != 3:
                continue

            if status == "rejected":
                fc = '#f87171'
                fc_alpha = 0.11
                ec = '#f87171'
                ls = 'dashed'
                hatch = '//'
            else:
                fc = '#22c55e'
                fc_alpha = 0.09
                ec = '#22c55e'
                ls = 'solid'
                hatch = None

            # Triangle polygon — use alpha= parameter, never CSS rgba()
            poly = MplPolygon(
                coords,
                closed=True,
                facecolor=fc,
                alpha=fc_alpha,
                edgecolor=ec,
                linewidth=1.5,
                linestyle=ls,
                hatch=hatch,
                zorder=100,
            )
            ax.add_patch(poly)
            self._triangle_overlay_artists.append(poly)

            # Edge outline (full alpha for edge)
            edge_poly = MplPolygon(
                coords,
                closed=True,
                facecolor='none',
                edgecolor=ec,
                linewidth=1.5,
                linestyle=ls,
                alpha=0.6,
                zorder=101,
            )
            ax.add_patch(edge_poly)
            self._triangle_overlay_artists.append(edge_poly)

            # Vertex markers
            xs = [c[0] for c in coords]
            ys = [c[1] for c in coords]
            scatter = ax.scatter(
                xs, ys,
                s=200,
                facecolors='none',
                edgecolors=ec,
                linewidths=1.5,
                zorder=102,
                alpha=0.7,
            )
            self._triangle_overlay_artists.append(scatter)

            # Gradient arrow overlay
            try:
                grad_val = tri.get('gradient', None)
                angle_val = tri.get('angle', None)
                cx = tri.get('centroid_x', None)
                cy = tri.get('centroid_y', None)

                if grad_val is not None and angle_val is not None and cx is not None and cy is not None:
                    grad_f = float(np.atleast_1d(grad_val).ravel()[0])
                    angle_f = float(np.atleast_1d(angle_val).ravel()[0])
                    cx_f = float(np.atleast_1d(cx).ravel()[0])
                    cy_f = float(np.atleast_1d(cy).ravel()[0])

                    if not (np.isnan(grad_f) or grad_f == 0 or np.isnan(angle_f)):
                        angle_rad = np.deg2rad(angle_f)
                        u = np.cos(angle_rad) * grad_f
                        v = np.sin(angle_rad) * grad_f
                        quiv = ax.quiver(
                            cx_f, cy_f, u, v,
                            color=ec,  # Use triangle edge color
                            alpha=1.0,  # Full opacity
                            scale_units='width',
                            scale=max(grad_f * 8, 1e-6),
                            zorder=105,  # Higher than labels
                            headwidth=4.5,
                            headlength=5.5,
                            width=0.012,
                        )
                        # Black outline for visibility
                        quiv.set_path_effects([pe.withStroke(linewidth=1.5, foreground="black")])
                        self._triangle_overlay_artists.append(quiv)
            except Exception:
                pass

        # Draw point labels for unique vertices
        seen_ids = set()
        for tri in triangle_data:
            p_ids = tri.get('point_ids', [])
            coords = tri.get('point_coords', [])
            if not p_ids or len(p_ids) != len(coords):
                continue
            
            for pid, (x, y) in zip(p_ids, coords):
                pid_str = str(pid)
                if pid_str in seen_ids:
                    continue
                seen_ids.add(pid_str)
                
                # Draw label with outline for visibility
                txt = ax.text(
                    x, y, pid_str,
                    fontsize=9,
                    color='white',
                    fontweight='bold',
                    ha='center', va='center',
                    bbox=dict(boxstyle="round,pad=0.2", fc="#333333", ec="none", alpha=0.7),
                    zorder=104
                )
                self._triangle_overlay_artists.append(txt)

        self.canvas.draw_idle()

    def clear_triangle_overlay(self):
        """Remove all triangle overlay artists from the plot."""
        for artist in self._triangle_overlay_artists:
            try:
                artist.remove()
            except Exception:
                pass
        self._triangle_overlay_artists = []
        try:
            self.canvas.draw_idle()
        except Exception:
            pass

    def export_plot(self, file_path):
        """Export the current plot to file."""
        self.canvas.fig.savefig(file_path, dpi=150, facecolor=Colors.PLOT_BG,
                                edgecolor='none', bbox_inches='tight')
