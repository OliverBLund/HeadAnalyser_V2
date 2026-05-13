"""
Triangle geometry plot — wire mesh view + heatmap toggle.
Uses matplotlib with hex colors only (critical project gotcha).

Key design decisions:
- Kept triangles: thin green wire edges (no fill) to avoid green-blob
- Rejected triangles: thicker dashed red edges, faint fill
- Point locations shown as labeled blue dots (like the HTML demo)
- Click to focus: only updates a single overlay artist, does NOT redraw
- Focus info bar: shows triangle details below the plot when clicked
- Colorbar: stored and removed before re-creating to prevent stacking
"""

from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)

from styles.colors import Colors
from ui.icons import icon

try:
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    from matplotlib.collections import PolyCollection, LineCollection
    import matplotlib.colors as mcolors
    HAS_MPL = True
except ImportError:
    HAS_MPL = False


_MAX_REJECTED_DRAW = 100


def _plot_bg() -> str:
    return Colors.PLOT_DARK_BG if Colors.is_dark() else Colors.PLOT_BG


def _plot_axes_bg() -> str:
    return Colors.PLOT_DARK_FACE if Colors.is_dark() else Colors.PLOT_FACE


def _kept_edge() -> str:
    return Colors.SUCCESS


def _rejected_edge() -> str:
    return Colors.ERROR


def _accent_color() -> str:
    return Colors.ACCENT_PRIMARY


def _accent_edge() -> str:
    return Colors.ACCENT_BRIGHT if Colors.is_dark() else Colors.ACCENT_DARK


def _text_color() -> str:
    return Colors.PLOT_DARK_TEXT if Colors.is_dark() else Colors.PLOT_TEXT


def _grid_color() -> str:
    return Colors.PLOT_DARK_GRID if Colors.is_dark() else Colors.PLOT_GRID


def _point_dot() -> str:
    return Colors.ACCENT_PRIMARY


def _point_label() -> str:
    return Colors.PLOT_DARK_TEXT if Colors.is_dark() else Colors.TEXT_SECONDARY


def _muted_point_fill() -> str:
    return Colors.BG_HOVER


def _muted_point_label() -> str:
    return Colors.TEXT_MUTED


def _mpl_rgba(color_value: str, alpha: float):
    if not HAS_MPL:
        return color_value
    red, green, blue, _ = mcolors.to_rgba(color_value)
    return (red, green, blue, alpha)


class TriangleGeometryPlot(QWidget):
    """Matplotlib canvas: triangle wire mesh or rejection heatmap view."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        self._view_mode = "triangles"
        self._filter_mode = "all"  # "all", "kept", or "rejected"

        # Stored data
        self._combined_df: Optional[pd.DataFrame] = None
        self._filtered_data: Optional[pd.DataFrame] = None
        self._col_mapping: Dict[str, Optional[str]] = {}
        self._heatmap_df: Optional[pd.DataFrame] = None
        self._selected_ids: Optional[set] = None  # highlighted point IDs

        # Highlight state
        self._highlight_idx: Optional[int] = None
        self._highlight_artist = None
        self._colorbar = None

        # Pre-computed caches
        self._vertex_cache: Dict[int, List[tuple]] = {}
        self._coord_map: Dict[str, tuple] = {}  # point_id → (x, y)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Header with toggle pills
        header = QHBoxLayout()
        header.setSpacing(6)

        # Icon
        icon_lbl = QLabel()
        icon_lbl.setPixmap(icon("fa6s.shapes", color=Colors.TEXT_TERTIARY, scale_factor=0.8).pixmap(QSize(12, 12)))
        header.addWidget(icon_lbl)

        title = QLabel("GEOMETRY")
        title.setStyleSheet(f"""
            color: {Colors.TEXT_TERTIARY};
            font-size: 10px; font-weight: 700;
            text-transform: uppercase; letter-spacing: 0.7px;
            background: transparent;
        """)
        header.addWidget(title)
        header.addStretch()

        self._pill_triangles = self._make_toggle("Triangles", checked=True)
        self._pill_heatmap = self._make_toggle("Heatmap")
        self._pill_triangles.clicked.connect(lambda: self._set_view("triangles"))
        self._pill_heatmap.clicked.connect(lambda: self._set_view("heatmap"))
        header.addWidget(self._pill_triangles)
        header.addWidget(self._pill_heatmap)

        # Legend indicators
        _legend_lbl_style = f"font-size: 9px; font-weight: 600; background: transparent;"
        _dot_style = "border-radius: 3px; border: none;"

        header.addSpacing(10)

        kept_dot = QLabel()
        kept_dot.setFixedSize(8, 8)
        kept_dot.setStyleSheet(f"background-color: {_kept_edge()}; {_dot_style}")
        header.addWidget(kept_dot)
        kept_lbl = QLabel("Kept")
        kept_lbl.setStyleSheet(f"color: {_kept_edge()}; {_legend_lbl_style}")
        header.addWidget(kept_lbl)

        header.addSpacing(4)

        rej_dot = QLabel()
        rej_dot.setFixedSize(8, 8)
        rej_dot.setStyleSheet(f"background-color: {_rejected_edge()}; {_dot_style}")
        header.addWidget(rej_dot)
        rej_lbl = QLabel("Rejected")
        rej_lbl.setStyleSheet(f"color: {_rejected_edge()}; {_legend_lbl_style}")
        header.addWidget(rej_lbl)

        header.addSpacing(4)

        hov_dot = QLabel()
        hov_dot.setFixedSize(8, 8)
        hov_dot.setStyleSheet(f"background-color: {_accent_edge()}; {_dot_style}")
        header.addWidget(hov_dot)
        hov_lbl = QLabel("Hovered")
        hov_lbl.setStyleSheet(f"color: {_accent_edge()}; {_legend_lbl_style}")
        header.addWidget(hov_lbl)

        layout.addLayout(header)

        # Canvas
        if HAS_MPL:
            self._fig = Figure(figsize=(5, 3.5), dpi=90, facecolor=_plot_bg())
            self._ax = self._fig.add_subplot(111)
            self._canvas = FigureCanvas(self._fig)
            self._canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            self._canvas.setStyleSheet(f"border: 1px solid {Colors.BORDER_DEFAULT}; border-radius: 8px;")
            layout.addWidget(self._canvas, 1)
        else:
            placeholder = QLabel("Matplotlib not available")
            placeholder.setAlignment(Qt.AlignCenter)
            placeholder.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: 12px;")
            layout.addWidget(placeholder, 1)
            self._fig = None
            self._ax = None
            self._canvas = None

        # Triangle focus info bar — compact card matching HTML concept
        self._info_bar = QWidget()
        self._info_bar.setObjectName("triInfoBar")
        self._info_bar.setFixedHeight(42)
        self._info_bar.setAttribute(Qt.WA_StyledBackground, True)
        self._info_bar.setStyleSheet(f"""
            QWidget#triInfoBar {{
                background-color: {Colors.BG_SURFACE};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 6px;
            }}
            QWidget#triInfoBar QLabel {{
                border: none;
                background: transparent;
            }}
        """)
        info_layout = QHBoxLayout(self._info_bar)
        info_layout.setContentsMargins(12, 4, 12, 4)
        info_layout.setSpacing(16)

        _lbl_ss = f"color: {Colors.TEXT_MUTED}; font-size: 8px; font-weight: 700; letter-spacing: 0.5px;"
        _val_ss = f"color: {Colors.TEXT_PRIMARY}; font-size: 11px; font-weight: 600; font-family: 'IBM Plex Mono', 'Consolas', monospace;"

        def _info_col(label_text: str):
            col = QVBoxLayout()
            col.setContentsMargins(0, 0, 0, 0)
            col.setSpacing(0)
            lbl = QLabel(label_text)
            lbl.setStyleSheet(_lbl_ss)
            col.addWidget(lbl)
            val = QLabel("\u2014")
            val.setStyleSheet(_val_ss)
            col.addWidget(val)
            return col, val

        c1, self._info_points = _info_col("TRIANGLE")
        info_layout.addLayout(c1)
        c2, self._info_gradient = _info_col("GRADIENT")
        info_layout.addLayout(c2)
        c3, self._info_angle = _info_col("ANGLE")
        info_layout.addLayout(c3)
        c4, self._info_status = _info_col("STATUS")
        info_layout.addLayout(c4)
        info_layout.addStretch()

        self._info_bar.setVisible(False)
        layout.addWidget(self._info_bar)

        # Footer note
        self._footer = QLabel("")
        self._footer.setStyleSheet(f"""
            color: {Colors.TEXT_MUTED};
            font-size: 10px; font-style: italic;
            background: transparent;
        """)
        layout.addWidget(self._footer)

    def _make_toggle(self, text: str, checked: bool = False) -> QPushButton:
        btn = QPushButton(text)
        btn.setCheckable(True)
        btn.setChecked(checked)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFixedHeight(22)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.BG_SURFACE};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 11px;
                color: {Colors.TEXT_MUTED};
                font-size: 10px; font-weight: 600;
                padding: 0 10px;
            }}
            QPushButton:hover {{ color: {Colors.TEXT_SECONDARY}; }}
            QPushButton:checked {{
                background-color: {Colors.ACCENT_GHOST};
                color: {Colors.TEXT_ACCENT};
                border-color: {Colors.BORDER_ACCENT};
            }}
        """)
        return btn

    def _set_view(self, mode: str):
        self._view_mode = mode
        self._pill_triangles.setChecked(mode == "triangles")
        self._pill_heatmap.setChecked(mode == "heatmap")
        self._highlight_idx = None
        self._highlight_artist = None
        self._info_bar.setVisible(False)
        self._full_redraw()

    # ── Public API ──────────────────────────────────────────

    def update_data(
        self,
        combined_df: pd.DataFrame,
        filtered_data: Optional[pd.DataFrame],
        col_mapping: Dict[str, Optional[str]],
        heatmap_df: Optional[pd.DataFrame] = None,
        selected_ids: Optional[set] = None,
    ):
        self._combined_df = combined_df
        self._filtered_data = filtered_data
        self._col_mapping = col_mapping
        self._heatmap_df = heatmap_df
        self._selected_ids = selected_ids
        self._filter_mode = "all"  # Reset filter on new data
        self._highlight_idx = None
        self._highlight_artist = None
        self._info_bar.setVisible(False)
        self._build_caches()
        self._full_redraw()

    def highlight_triangle(self, idx: int):
        """Update ONLY the highlight overlay — no full redraw."""
        if self._ax is None or self._combined_df is None:
            return
        if idx == self._highlight_idx:
            return

        self._highlight_idx = idx
        self._update_highlight_only()
        self._update_info_bar(idx)

    def clear_highlight(self):
        if self._highlight_artist is not None:
            try:
                self._highlight_artist.remove()
            except (ValueError, AttributeError):
                pass
            self._highlight_artist = None
        self._highlight_idx = None
        self._info_bar.setVisible(False)
        if self._canvas:
            self._canvas.draw_idle()

    def clear(self):
        self._combined_df = None
        self._filtered_data = None
        self._heatmap_df = None
        self._highlight_idx = None
        self._highlight_artist = None
        self._vertex_cache.clear()
        self._coord_map.clear()
        self._remove_colorbar()
        self._info_bar.setVisible(False)
        if self._ax:
            self._ax.clear()
            self._ax.set_facecolor(_plot_axes_bg())
            self._canvas.draw_idle()
        self._footer.setText("")

    def set_filter_mode(self, mode: str):
        """Set which triangles to draw: 'all', 'kept', or 'rejected'."""
        if mode == self._filter_mode:
            return
        self._filter_mode = mode
        self._highlight_idx = None
        self._highlight_artist = None
        self._info_bar.setVisible(False)
        self._full_redraw()

    # ── Caches ──────────────────────────────────────────────

    def _build_caches(self):
        """Pre-compute triangle vertices and point coords."""
        self._vertex_cache.clear()
        self._coord_map.clear()
        if self._combined_df is None or self._combined_df.empty or self._filtered_data is None:
            return

        x_col = self._col_mapping.get("x")
        y_col = self._col_mapping.get("y")
        id_col = self._col_mapping.get("ID")
        if not x_col or not y_col or not id_col:
            return

        # Build fast lookup: string(id) → (x, y)
        for _, row in self._filtered_data.iterrows():
            pid = str(row[id_col])
            self._coord_map[pid] = (float(row[x_col]), float(row[y_col]))

        for df_idx, row in self._combined_df.iterrows():
            ids = row.get("point_ids")
            if ids is None or not isinstance(ids, (list, tuple, np.ndarray)):
                continue
            verts = []
            for pid in ids:
                coord = self._coord_map.get(str(pid))
                if coord is None:
                    break
                verts.append(coord)
            if len(verts) == 3:
                self._vertex_cache[df_idx] = verts

    def _get_verts(self, df_idx) -> Optional[List[tuple]]:
        return self._vertex_cache.get(df_idx)

    # ── Colorbar management ─────────────────────────────────

    def _remove_colorbar(self):
        if self._colorbar is not None:
            try:
                self._colorbar.remove()
            except (ValueError, AttributeError):
                pass
            self._colorbar = None

    # ── Info bar (focus details) ────────────────────────────

    def _update_info_bar(self, idx: int):
        """Update the info bar with focused triangle details."""
        if self._combined_df is None or idx >= len(self._combined_df):
            self._info_bar.setVisible(False)
            return

        try:
            row = self._combined_df.iloc[idx]
        except (IndexError, KeyError):
            self._info_bar.setVisible(False)
            return

        # Points
        ids = row.get("point_ids", [])
        if isinstance(ids, (list, tuple, np.ndarray)):
            self._info_points.setText(" \u2013 ".join(str(v) for v in ids))
        else:
            self._info_points.setText(str(ids))

        # Gradient
        g = row.get("gradient")
        if isinstance(g, (list, np.ndarray)):
            g = g[0] if len(g) > 0 else np.nan
        try:
            gf = float(g)
            if not np.isnan(gf):
                self._info_gradient.setText(f"{gf:.5f}")
            else:
                self._info_gradient.setText("\u2014")
        except (ValueError, TypeError):
            self._info_gradient.setText("\u2014")

        # Angle
        a = row.get("angle")
        try:
            af = float(a)
            if not np.isnan(af):
                self._info_angle.setText(f"{af:.1f}\u00b0")
            else:
                self._info_angle.setText("\u2014")
        except (ValueError, TypeError):
            self._info_angle.setText("\u2014")

        # Status
        status = str(row.get("status", ""))
        if status == "kept":
            self._info_status.setText("Kept")
            self._info_status.setStyleSheet(f"color: {Colors.SUCCESS}; font-size: 11px; font-weight: 700; background: transparent;")
        elif status == "rejected":
            self._info_status.setText("Rejected")
            self._info_status.setStyleSheet(f"color: {Colors.ERROR}; font-size: 11px; font-weight: 700; background: transparent;")
        else:
            self._info_status.setText("\u2014")
            self._info_status.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; font-size: 11px; font-weight: 600; background: transparent;")

        self._info_bar.setVisible(True)

    # ── Full redraw (on data change or view toggle) ─────────

    def _full_redraw(self):
        if self._ax is None:
            return

        self._remove_colorbar()
        self._ax.clear()
        self._ax.set_facecolor(_plot_axes_bg())
        self._fig.set_facecolor(_plot_bg())

        if self._view_mode == "triangles":
            self._draw_triangles()
        else:
            self._draw_heatmap()

        self._ax.tick_params(colors=_text_color(), labelsize=8)
        for spine in self._ax.spines.values():
            spine.set_color(_grid_color())
        self._ax.set_aspect("equal", adjustable="datalim")
        self._fig.tight_layout(pad=0.5)
        self._canvas.draw_idle()

    # ── Highlight-only update (on click) ────────────────────

    def _update_highlight_only(self):
        """Remove old highlight artist, add new one — no full redraw."""
        if self._ax is None:
            return

        # Remove previous
        if self._highlight_artist is not None:
            try:
                self._highlight_artist.remove()
            except (ValueError, AttributeError):
                pass
            self._highlight_artist = None

        # Add new
        if self._highlight_idx is not None and self._combined_df is not None:
            try:
                if self._highlight_idx < len(self._combined_df):
                    df_idx = self._combined_df.index[self._highlight_idx]
                    verts = self._get_verts(df_idx)
                    if verts and len(verts) == 3:
                        poly = PolyCollection(
                            [verts],
                            facecolors=_mpl_rgba(_accent_color(), 0.22 if Colors.is_dark() else 0.14),
                            edgecolors=_accent_edge(),
                            linewidths=2.5,
                            alpha=0.95,
                            zorder=10,
                        )
                        self._ax.add_collection(poly)
                        self._highlight_artist = poly
            except (IndexError, KeyError):
                pass

        self._canvas.draw_idle()

    # ── Triangle mesh drawing ───────────────────────────────

    def _draw_triangles(self):
        if self._combined_df is None or self._combined_df.empty:
            self._footer.setText("")
            return

        all_kept = self._combined_df[self._combined_df["status"] == "kept"]
        all_rejected = self._combined_df[self._combined_df["status"] == "rejected"]

        # Apply filter mode
        if self._filter_mode == "kept":
            kept = all_kept
            rejected = all_rejected.iloc[0:0]  # empty
        elif self._filter_mode == "rejected":
            kept = all_kept.iloc[0:0]  # empty
            rejected = all_rejected
        else:
            kept = all_kept
            rejected = all_rejected

        # Draw kept triangles as wire edges (no fill)
        kept_lines = []
        for idx in kept.index:
            verts = self._get_verts(idx)
            if verts and len(verts) == 3:
                kept_lines.append([verts[0], verts[1]])
                kept_lines.append([verts[1], verts[2]])
                kept_lines.append([verts[2], verts[0]])

        if kept_lines:
            lc = LineCollection(
                kept_lines,
                colors=_kept_edge(),
                linewidths=0.4,
                alpha=0.35,
                zorder=2,
            )
            self._ax.add_collection(lc)

        # Draw rejected triangles
        # BUG FIX: don't dropna on angle (all rejected have NaN angle)
        rej_to_draw = rejected
        total_rej = len(rejected)
        if total_rej > _MAX_REJECTED_DRAW:
            rej_to_draw = rejected.head(_MAX_REJECTED_DRAW)

        rej_polys = []
        for idx in rej_to_draw.index:
            verts = self._get_verts(idx)
            if verts and len(verts) == 3:
                rej_polys.append(verts)

        if rej_polys:
            coll = PolyCollection(
                rej_polys,
                facecolors=_mpl_rgba(_rejected_edge(), 0.12 if Colors.is_dark() else 0.16),
                edgecolors=_rejected_edge(),
                linewidths=0.8,
                linestyles="dashed",
                alpha=0.5,
                zorder=3,
            )
            self._ax.add_collection(coll)

        # Draw point locations as labeled dots
        if self._coord_map:
            has_selection = self._selected_ids and len(self._selected_ids) > 0

            for pid, (px, py) in self._coord_map.items():
                is_selected = has_selection and str(pid) in self._selected_ids

                if has_selection and not is_selected:
                    # Grayed-out unselected points
                    self._ax.scatter(
                        [px], [py], s=12, c=_muted_point_fill(),
                        alpha=0.5, zorder=5, linewidths=0.5,
                        edgecolors=_mpl_rgba(Colors.TEXT_INVERSE if Colors.is_dark() else Colors.TEXT_PRIMARY, 0.08),
                    )
                    self._ax.annotate(
                        pid, (px, py),
                        textcoords="offset points", xytext=(5, 5),
                        fontsize=6, color=_muted_point_label(), alpha=0.5, zorder=7,
                    )
                else:
                    # Selected (or no selection = all highlighted)
                    dot_color = _accent_color() if is_selected else _point_dot()
                    edge_color = _accent_edge() if is_selected else _mpl_rgba(
                        Colors.TEXT_INVERSE if Colors.is_dark() else Colors.TEXT_PRIMARY,
                        0.18,
                    )
                    label_color = _accent_edge() if is_selected else _point_label()
                    dot_size = 30 if is_selected else 18
                    glow_size = 70 if is_selected else 50

                    # Outer glow
                    self._ax.scatter(
                        [px], [py], s=glow_size, c=dot_color, alpha=0.20,
                        zorder=5, linewidths=0, edgecolors="none",
                    )
                    # Inner dot
                    self._ax.scatter(
                        [px], [py], s=dot_size, c=dot_color, alpha=0.8,
                        zorder=6, linewidths=1.0 if is_selected else 0.5,
                        edgecolors=edge_color,
                    )
                    # Label
                    self._ax.annotate(
                        pid, (px, py),
                        textcoords="offset points", xytext=(5, 5),
                        fontsize=7, fontweight="bold",
                        color=label_color, alpha=0.9, zorder=7,
                    )

        # Draw highlight if present
        if self._highlight_idx is not None:
            self._update_highlight_only()

        # Auto-scale
        self._ax.autoscale_view()

        # Footer
        drawn_rej = len(rej_polys)
        if total_rej > _MAX_REJECTED_DRAW:
            self._footer.setText(
                f"{len(kept)} kept (edges), {drawn_rej} of {total_rej} rejected (dashed)"
            )
        elif total_rej > 0:
            self._footer.setText(
                f"{len(kept)} kept (edges), {drawn_rej} rejected (dashed)"
            )
        else:
            self._footer.setText(f"{len(kept)} kept triangles")

    # ── Heatmap drawing ─────────────────────────────────────

    def _draw_heatmap(self):
        if self._heatmap_df is None or self._heatmap_df.empty:
            self._footer.setText("No heatmap data")
            return

        x = self._heatmap_df["x"].values
        y = self._heatmap_df["y"].values
        rates = self._heatmap_df["rejection_rate"].values

        scatter = self._ax.scatter(
            x, y,
            c=rates,
            s=np.clip(rates * 3, 20, 200),
            cmap="YlOrRd",
            edgecolors=_text_color(),
            linewidths=0.5,
            alpha=0.85,
            vmin=0,
            vmax=max(100, rates.max()) if len(rates) > 0 else 100,
            zorder=2,
        )

        # Add point labels
        for _, row in self._heatmap_df.iterrows():
            self._ax.annotate(
                str(row["point_id"]),
                (row["x"], row["y"]),
                textcoords="offset points",
                xytext=(5, 5),
                fontsize=7,
                fontweight="bold" if row["rejection_rate"] > 30 else "normal",
                color=_point_label(),
                alpha=0.85,
            )

        self._colorbar = self._fig.colorbar(scatter, ax=self._ax, shrink=0.7, pad=0.02)
        self._colorbar.set_label("Rejection Rate %", color=_text_color(), fontsize=8)
        self._colorbar.ax.tick_params(colors=_text_color(), labelsize=7)

        self._footer.setText(f"{len(self._heatmap_df)} points with rejection data")
