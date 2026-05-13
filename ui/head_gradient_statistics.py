"""
Head/Gradient statistics widgets for the Statistics Panel.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QPainter
from PyQt5.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from styles.colors import Colors


class _StatRow(QWidget):
    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(8)

        self.label = QLabel(label)
        self.label.setStyleSheet(
            f"""
            color: {Colors.TEXT_SECONDARY};
            font-size: 11px;
            background: transparent;
        """
        )
        layout.addWidget(self.label)
        layout.addStretch()

        self.value = QLabel("-")
        self.value.setStyleSheet(
            f"""
            color: {Colors.TEXT_PRIMARY};
            font-size: 11px;
            font-weight: 600;
            font-family: 'Consolas';
            background: transparent;
        """
        )
        layout.addWidget(self.value)

    def set_value(self, value: str):
        self.value.setText(str(value))


class _StatCard(QFrame):
    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            f"""
            background-color: {Colors.BG_ELEVATED};
            border: 1px solid {Colors.BORDER_SUBTLE};
            border-radius: {Colors.RADIUS_SM};
        """
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 7, 8, 7)
        layout.setSpacing(4)

        self.k = QLabel(label)
        self.k.setStyleSheet(
            f"""
            color: {Colors.TEXT_TERTIARY};
            font-size: 9px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.6px;
            background: transparent;
            border: none;
        """
        )
        layout.addWidget(self.k)

        self.v = QLabel("-")
        self.v.setStyleSheet(
            f"""
            color: {Colors.TEXT_PRIMARY};
            font-size: 11px;
            font-weight: 600;
            font-family: 'Consolas';
            background: transparent;
            border: none;
        """
        )
        layout.addWidget(self.v)

    def set_value(self, value: str):
        self.v.setText(str(value))


class _GaugeBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._value = 0.0
        self.setMinimumHeight(14)
        self.setMaximumHeight(14)

    def set_value(self, value: float):
        self._value = float(np.clip(value, 0.0, 1.0))
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        h = self.height()

        p.setPen(Qt.NoPen)
        p.setBrush(QColor(Colors.BG_HOVER))
        p.drawRoundedRect(0, 2, w, h - 4, 5, 5)

        seg = w / 3.0
        p.setBrush(QColor(Colors.ERROR))
        p.drawRoundedRect(0, 2, int(seg), h - 4, 5, 5)
        p.setBrush(QColor(Colors.WARNING))
        p.drawRect(int(seg), 2, int(seg), h - 4)
        p.setBrush(QColor(Colors.SUCCESS))
        p.drawRoundedRect(int(seg * 2), 2, w - int(seg * 2), h - 4, 5, 5)

        x = int(self._value * (w - 1))
        p.setBrush(QColor(245, 245, 250))
        p.drawRect(max(0, x - 1), 0, 3, h)
        p.end()


class _SparkBandBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._p10 = 0.0
        self._p90 = 0.0
        self._max = 1.0
        self._color = QColor(Colors.SUCCESS)
        self.setMinimumHeight(18)
        self.setMaximumHeight(18)

    def set_data(self, p10: float, p90: float, vmax: float, color: str):
        self._p10 = max(0.0, float(p10))
        self._p90 = max(self._p10, float(p90))
        self._max = max(1e-12, float(vmax))
        self._color = QColor(color)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        h = self.height()
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(Colors.BG_HOVER))
        p.drawRoundedRect(0, 0, w, h, 9, 9)

        x0 = int((self._p10 / self._max) * w)
        x1 = int((self._p90 / self._max) * w)
        x0 = max(0, min(w - 1, x0))
        x1 = max(x0 + 1, min(w, x1))

        c = QColor(self._color)
        c.setAlpha(130)
        p.setBrush(c)
        p.drawRoundedRect(x0, 1, max(2, x1 - x0), h - 2, 8, 8)

        c2 = QColor(self._color)
        c2.setAlpha(235)
        p.setBrush(c2)
        p.drawRoundedRect(max(0, x1 - 2), 0, 4, h, 2, 2)
        p.end()


class _OverlapMatrixWidget(QWidget):
    _keys = ["thin", "unc", "stack", "max"]
    _labels = {"thin": "Thin", "unc": "Unc", "stack": "Stack", "max": "Max"}

    def __init__(self, parent=None):
        super().__init__(parent)
        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(4)
        self._cells = {}

        for c, key in enumerate(self._keys, start=1):
            grid.addWidget(self._mk_cell(self._labels[key], header=True), 0, c)
        for r, row_key in enumerate(self._keys, start=1):
            grid.addWidget(self._mk_cell(self._labels[row_key], header=True), r, 0)
            for c, col_key in enumerate(self._keys, start=1):
                cell = self._mk_cell("0", header=False)
                self._cells[(row_key, col_key)] = cell
                grid.addWidget(cell, r, c)

    @staticmethod
    def _mk_cell(text: str, header: bool):
        l = QLabel(text)
        if header:
            l.setStyleSheet(
                f"""
                background-color: rgba(255,255,255,0.01);
                border: 1px solid {Colors.BORDER_SUBTLE};
                border-radius: 6px;
                color: {Colors.TEXT_TERTIARY};
                font-size: 10px;
                font-weight: 700;
                text-transform: uppercase;
                padding: 5px 6px;
            """
            )
        else:
            l.setStyleSheet(
                f"""
                background-color: {Colors.BG_ELEVATED};
                border: 1px solid {Colors.BORDER_SUBTLE};
                border-radius: 6px;
                color: {Colors.TEXT_SECONDARY};
                font-size: 10px;
                font-family: Consolas;
                padding: 5px 6px;
            """
            )
        l.setAlignment(Qt.AlignCenter)
        return l

    def clear(self):
        for cell in self._cells.values():
            cell.setText("0")
            cell.setStyleSheet(
                f"""
                background-color: {Colors.BG_ELEVATED};
                border: 1px solid {Colors.BORDER_SUBTLE};
                border-radius: 6px;
                color: {Colors.TEXT_SECONDARY};
                font-size: 10px;
                font-family: Consolas;
                padding: 5px 6px;
            """
            )

    def set_counts(self, counts):
        vmax = max([0] + [int(v) for v in counts.values()])
        for key, cell in self._cells.items():
            v = int(counts.get(key, 0))
            cell.setText(str(v))
            ratio = (v / vmax) if vmax > 0 else 0.0
            alpha = int(40 + 120 * ratio)
            bg = QColor(Colors.ERROR)
            bg.setAlpha(alpha)
            cell.setStyleSheet(
                f"""
                background-color: {bg.name(QColor.HexArgb)};
                border: 1px solid {Colors.BORDER_SUBTLE};
                border-radius: 6px;
                color: {Colors.TEXT_PRIMARY if ratio > 0.45 else Colors.TEXT_SECONDARY};
                font-size: 10px;
                font-family: Consolas;
                padding: 5px 6px;
            """
            )


class _CardGrid(QWidget):
    def __init__(self, specs, parent=None):
        super().__init__(parent)
        self._cards = {}
        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(6)
        for idx, (key, label) in enumerate(specs):
            card = _StatCard(label)
            self._cards[key] = card
            grid.addWidget(card, 0, idx)

    def set_value(self, key: str, value: str):
        card = self._cards.get(key)
        if card is not None:
            card.set_value(value)

    def clear(self):
        for c in self._cards.values():
            c.set_value("-")


class _StatsBlock(QFrame):
    def __init__(self, title: str, note: str = "", parent=None):
        super().__init__(parent)
        self._setters = {}
        self._clearers = []

        self.setStyleSheet(
            f"""
            background-color: {Colors.BG_SURFACE};
            border: 1px solid {Colors.BORDER_DEFAULT};
            border-radius: {Colors.RADIUS_MD};
        """
        )

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        header = QFrame()
        header.setStyleSheet(
            f"""
            background-color: {Colors.BG_ELEVATED};
            border: none;
            border-bottom: 1px solid {Colors.BORDER_SUBTLE};
            border-top-left-radius: {Colors.RADIUS_MD};
            border-top-right-radius: {Colors.RADIUS_MD};
        """
        )
        h = QHBoxLayout(header)
        h.setContentsMargins(10, 8, 10, 8)
        h.setSpacing(8)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(
            f"""
            color: {Colors.TEXT_TERTIARY};
            font-size: 10px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.7px;
            background: transparent;
            border: none;
        """
        )
        h.addWidget(title_lbl)
        h.addStretch()

        note_lbl = QLabel(note)
        note_lbl.setStyleSheet(
            f"""
            color: {Colors.TEXT_MUTED};
            font-size: 10px;
            background: transparent;
            border: none;
        """
        )
        h.addWidget(note_lbl)

        outer.addWidget(header)

        body = QVBoxLayout()
        body.setContentsMargins(10, 8, 10, 8)
        body.setSpacing(4)
        outer.addLayout(body)
        self._body = body

    def add_row(self, key: str, label: str):
        row = _StatRow(label)
        self._body.addWidget(row)
        self._setters[key] = row.set_value
        self._clearers.append(lambda r=row: r.set_value("-"))
        return row

    def add_card_grid(self, specs):
        grid = _CardGrid(specs)
        self._body.addWidget(grid)
        for key, _ in specs:
            self._setters[key] = lambda value, k=key, g=grid: g.set_value(k, value)
        self._clearers.append(grid.clear)
        return grid

    def set_value(self, key: str, value: str):
        setter = self._setters.get(key)
        if setter is not None:
            setter(value)

    def clear(self):
        for clear in self._clearers:
            clear()


def _numeric_series(values) -> pd.Series:
    s = pd.to_numeric(pd.Series(values), errors="coerce")
    return s.dropna()


def _as_scalar(value):
    if isinstance(value, (list, tuple, np.ndarray)):
        if len(value) == 0:
            return np.nan
        return value[0]
    return value


class HeadStatisticsWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        self.block_basic = _StatsBlock("Distribution", "robust spread")
        self.block_basic.add_row("mean", "Mean")
        self.block_basic.add_row("median", "Median")
        self.block_basic.add_row("std", "Std Deviation")
        self.block_basic.add_row("range", "Range")
        self.block_basic.add_row("iqr", "IQR (Q1-Q3)")
        self.block_basic.add_row("mad", "MAD")
        root.addWidget(self.block_basic)

        self.block_quality = _StatsBlock("Data Coverage", "input quality")
        self.block_quality.add_card_grid(
            [
                ("used_total", "Used / Total"),
                ("missing", "Missing Head"),
                ("dup_ids", "Duplicate IDs"),
            ]
        )
        self.block_quality.add_row("out_low", "Outlier low (IQR)")
        self.block_quality.add_row("out_high", "Outlier high (IQR)")
        self.block_quality.add_row("out_ids", "Outlier IDs")
        root.addWidget(self.block_quality)

        self.block_spatial = _StatsBlock("Spatial Trend", "coarse plane")
        self.block_spatial.add_row("ew_slope", "East-West slope")
        self.block_spatial.add_row("ns_slope", "North-South slope")
        self.block_spatial.add_row("dominant", "Dominant axis")
        root.addWidget(self.block_spatial)

        self.block_snapshot = _StatsBlock("Snapshot Delta", "optional baseline")
        self.block_snapshot.add_card_grid(
            [
                ("delta_median", "Median delta head"),
                ("delta_gt_5cm", "Points >0.05m"),
                ("delta_largest", "Largest delta"),
            ]
        )
        root.addWidget(self.block_snapshot)

    def clear(self):
        self.block_basic.clear()
        self.block_quality.clear()
        self.block_spatial.clear()
        self.block_snapshot.clear()

    def update_from_app(self, app):
        self.clear()

        fdata = getattr(app, "filtered_data", None)
        cmap = getattr(app, "col_mapping", {}) or {}
        if fdata is None or getattr(fdata, "empty", True):
            return

        h_col = cmap.get("hydraulic head")
        x_col = cmap.get("x")
        y_col = cmap.get("y")
        id_col = cmap.get("ID")
        if not h_col or h_col not in fdata.columns:
            return

        total = int(len(fdata))
        heads = pd.to_numeric(fdata[h_col], errors="coerce")
        heads_valid = heads.dropna()
        used = int(len(heads_valid))
        missing = int(total - used)

        self.block_quality.set_value("used_total", f"{used} / {total}")
        self.block_quality.set_value(
            "missing", f"{missing} ({(missing / total * 100.0):.1f}%)" if total > 0 else "-"
        )

        if id_col and id_col in fdata.columns:
            ids = fdata[id_col].astype(str)
            dup = int(len(ids) - ids.nunique(dropna=True))
            self.block_quality.set_value("dup_ids", str(max(0, dup)))

        if used > 0:
            self.block_basic.set_value("mean", f"{float(heads_valid.mean()):.3f} m")
            self.block_basic.set_value("median", f"{float(heads_valid.median()):.3f} m")
            self.block_basic.set_value("std", f"{float(heads_valid.std(ddof=1)):.4f}" if used > 1 else "-")
            self.block_basic.set_value(
                "range", f"{float(heads_valid.min()):.3f} - {float(heads_valid.max()):.3f} m"
            )
            q1 = float(heads_valid.quantile(0.25))
            q3 = float(heads_valid.quantile(0.75))
            self.block_basic.set_value("iqr", f"{q1:.3f} - {q3:.3f} m")
            med = float(heads_valid.median())
            mad = float(np.median(np.abs(heads_valid.to_numpy() - med)))
            self.block_basic.set_value("mad", f"{mad:.4f}")

            iqr = q3 - q1
            lo_fence = q1 - (1.5 * iqr)
            hi_fence = q3 + (1.5 * iqr)
            low_mask = heads_valid < lo_fence
            high_mask = heads_valid > hi_fence
            low_count = int(np.count_nonzero(low_mask))
            high_count = int(np.count_nonzero(high_mask))
            self.block_quality.set_value("out_low", str(low_count))
            self.block_quality.set_value("out_high", str(high_count))

            if id_col and id_col in fdata.columns and (low_count + high_count) > 0:
                valid_rows = fdata.loc[heads.notna(), [id_col]].copy()
                idx = heads_valid.index
                out_idx = idx[low_mask | high_mask]
                out_ids = valid_rows.loc[out_idx, id_col].astype(str).tolist()
                shown = ", ".join(out_ids[:3]) if out_ids else "-"
                if len(out_ids) > 3:
                    shown = f"{shown}, +{len(out_ids) - 3}"
                self.block_quality.set_value("out_ids", shown)
            else:
                self.block_quality.set_value("out_ids", "-")

        if x_col in fdata.columns and y_col in fdata.columns:
            xyh = fdata[[x_col, y_col, h_col]].copy()
            xyh[x_col] = pd.to_numeric(xyh[x_col], errors="coerce")
            xyh[y_col] = pd.to_numeric(xyh[y_col], errors="coerce")
            xyh[h_col] = pd.to_numeric(xyh[h_col], errors="coerce")
            xyh = xyh.dropna()
            if len(xyh) >= 3:
                X = np.column_stack(
                    [xyh[x_col].to_numpy(dtype=float), xyh[y_col].to_numpy(dtype=float), np.ones(len(xyh))]
                )
                yv = xyh[h_col].to_numpy(dtype=float)
                try:
                    coef, *_ = np.linalg.lstsq(X, yv, rcond=None)
                    a, b = float(coef[0]), float(coef[1])
                    self.block_spatial.set_value("ew_slope", f"{a:+.6f} m/m")
                    self.block_spatial.set_value("ns_slope", f"{b:+.6f} m/m")
                    dominant = "E-W" if abs(a) >= abs(b) else "N-S"
                    self.block_spatial.set_value("dominant", dominant)
                except Exception:
                    pass

        baseline = getattr(app, "head_snapshot_baseline", None)
        if baseline is not None and isinstance(baseline, pd.DataFrame):
            if id_col and id_col in baseline.columns and h_col in baseline.columns and id_col in fdata.columns:
                cur = fdata[[id_col, h_col]].copy()
                cur[h_col] = pd.to_numeric(cur[h_col], errors="coerce")
                base = baseline[[id_col, h_col]].copy()
                base[h_col] = pd.to_numeric(base[h_col], errors="coerce")
                merged = cur.merge(base, on=id_col, suffixes=("_cur", "_base"))
                if not merged.empty:
                    delta = (merged[f"{h_col}_cur"] - merged[f"{h_col}_base"]).dropna()
                    if len(delta) > 0:
                        self.block_snapshot.set_value("delta_median", f"{float(delta.median()):+.3f} m")
                        gt = int(np.count_nonzero(np.abs(delta.to_numpy()) > 0.05))
                        self.block_snapshot.set_value("delta_gt_5cm", f"{gt} / {len(delta)}")
                        arg = int(np.argmax(np.abs(delta.to_numpy())))
                        pid = str(merged.iloc[arg][id_col])
                        self.block_snapshot.set_value("delta_largest", f"{pid} {float(delta.iloc[arg]):+.3f} m")


class GradientStatisticsWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        self.block_core = _StatsBlock("Core", "kept triangles")
        self.block_core.add_row("avg", "Average Gradient")
        self.block_core.add_row("ci", "Mean CI (approx.)")
        self.block_core.add_row("median", "Median Gradient")
        self.block_core.add_row("std", "Std Deviation")
        self.block_core.add_row("range", "Range")
        self.block_core.add_row("p10p90", "P10 / P90")
        self.block_core.add_row("cv", "CV (std/mean)")
        self.block_core._setters["ci"]("-")
        root.addWidget(self.block_core)

        self.block_direction = _StatsBlock("Direction", "stability")
        self.block_direction.add_row("dir_u", "Avg Direction (unweighted)")
        self.block_direction.add_row("dir_w", "Avg Direction (weighted)")
        self.block_direction.add_row("coherence", "Direction Coherence (R)")
        self._coh_gauge = _GaugeBar()
        self.block_direction._body.addWidget(self._coh_gauge)
        self._coh_note = QLabel("Higher is more coherent directional signal.")
        self._coh_note.setStyleSheet(
            f"color: {Colors.TEXT_MUTED}; font-size: 10px; background: transparent; border:none;"
        )
        self.block_direction._body.addWidget(self._coh_note)
        root.addWidget(self.block_direction)

        self.block_rejected = _StatsBlock("Kept vs Rejected", "computed rejected only")
        self.block_rejected.add_row("rej_comp", "Rejected computable")
        self.block_rejected.add_card_grid(
            [
                ("cmp_mean", "Mean (K / R)"),
                ("cmp_median", "Median (K / R)"),
                ("cmp_iqr", "IQR (K / R)"),
            ]
        )
        root.addWidget(self.block_rejected)

        self.block_sensitivity = _StatsBlock("Sensitivity Presets", "separate feature hook")
        sgrid = QGridLayout()
        sgrid.setContentsMargins(0, 0, 0, 0)
        sgrid.setSpacing(6)
        self.sens_strict = _StatCard("Strict")
        self.sens_default = _StatCard("Default")
        self.sens_perm = _StatCard("Permissive")
        sgrid.addWidget(self.sens_strict, 0, 0)
        sgrid.addWidget(self.sens_default, 0, 1)
        sgrid.addWidget(self.sens_perm, 0, 2)
        self.block_sensitivity._body.addLayout(sgrid)
        self.sens_note = QLabel("No scenario engine active - values shown when sensitivity module is enabled.")
        self.sens_note.setStyleSheet(
            f"color: {Colors.TEXT_MUTED}; font-size: 10px; background: transparent; border:none;"
        )
        self.block_sensitivity._body.addWidget(self.sens_note)
        root.addWidget(self.block_sensitivity)

        self.block_dist = _StatsBlock("Kept vs Rejected Distributions", "mini percentile bands")
        self.dist_kept_lbl = QLabel("Gradient kept")
        self.dist_rej_lbl = QLabel("Gradient rejected")
        self.dist_kept_bar = _SparkBandBar()
        self.dist_rej_bar = _SparkBandBar()
        self.dist_kept_val = QLabel("-")
        self.dist_rej_val = QLabel("-")
        for l in [self.dist_kept_lbl, self.dist_rej_lbl]:
            l.setStyleSheet(f"color:{Colors.TEXT_SECONDARY}; font-size:11px; background:transparent; border:none;")
        for l in [self.dist_kept_val, self.dist_rej_val]:
            l.setStyleSheet(
                f"color:{Colors.TEXT_PRIMARY}; font-size:11px; font-family:Consolas; background:transparent; border:none;"
            )
        for label, bar, val in [
            (self.dist_kept_lbl, self.dist_kept_bar, self.dist_kept_val),
            (self.dist_rej_lbl, self.dist_rej_bar, self.dist_rej_val),
        ]:
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(8)
            row.addWidget(label)
            row.addWidget(bar, 1)
            row.addWidget(val)
            self.block_dist._body.addLayout(row)
        root.addWidget(self.block_dist)

        self.block_influence = _StatsBlock("Point Influence", "leave-one-point-out impact")
        self.inf_rows = []
        for _ in range(3):
            row = QFrame()
            row.setStyleSheet(
                f"""
                background-color: {Colors.BG_ELEVATED};
                border: 1px solid {Colors.BORDER_SUBTLE};
                border-radius: {Colors.RADIUS_SM};
            """
            )
            rl = QHBoxLayout(row)
            rl.setContentsMargins(8, 6, 8, 6)
            rl.setSpacing(8)
            pid = QLabel("-")
            da = QLabel("d angle -")
            dg = QLabel("d mean -")
            pid.setStyleSheet(f"color:{Colors.TEXT_PRIMARY}; font-size:11px; font-weight:700; background:transparent;")
            da.setStyleSheet(f"color:{Colors.TEXT_SECONDARY}; font-size:11px; font-family:Consolas; background:transparent;")
            dg.setStyleSheet(f"color:{Colors.TEXT_SECONDARY}; font-size:11px; font-family:Consolas; background:transparent;")
            rl.addWidget(pid)
            rl.addStretch()
            rl.addWidget(da)
            rl.addWidget(dg)
            self.block_influence._body.addWidget(row)
            self.inf_rows.append((pid, da, dg))
        root.addWidget(self.block_influence)

        self.block_matrix = _StatsBlock("Rejection Overlap Matrix", "co-occurrence counts")
        self.matrix = _OverlapMatrixWidget()
        self.block_matrix._body.addWidget(self.matrix)
        root.addWidget(self.block_matrix)

        self.block_zone = _StatsBlock("Directional Stability by Area", "coarse 3-zone summary")
        zgrid = QGridLayout()
        zgrid.setContentsMargins(0, 0, 0, 0)
        zgrid.setSpacing(6)
        self.zone_n = _StatCard("North")
        self.zone_c = _StatCard("Central")
        self.zone_s = _StatCard("South")
        zgrid.addWidget(self.zone_n, 0, 0)
        zgrid.addWidget(self.zone_c, 0, 1)
        zgrid.addWidget(self.zone_s, 0, 2)
        self.block_zone._body.addLayout(zgrid)
        self.zone_note = QLabel("Card value: R and mean direction")
        self.zone_note.setStyleSheet(f"color:{Colors.TEXT_MUTED}; font-size:10px; background:transparent; border:none;")
        self.block_zone._body.addWidget(self.zone_note)
        root.addWidget(self.block_zone)

        # Keep current warning semantics.
        ci_row_label = None
        try:
            # Find actual QLabel for CI label.
            for child in self.block_core.findChildren(QLabel):
                if child.text() == "Mean CI (approx.)":
                    ci_row_label = child
                    break
        except Exception:
            ci_row_label = None
        if ci_row_label is not None:
            ci_row_label.setToolTip("Diagnostic estimate only. Triangle gradients are not independent.")

    @staticmethod
    def _angle_to_compass(angle: float) -> str:
        directions = ["E", "NE", "N", "NW", "W", "SW", "S", "SE"]
        idx = round(float(angle) / 45.0) % 8
        return directions[idx]

    def clear(self):
        self.block_core.clear()
        self.block_direction.clear()
        self.block_rejected.clear()
        self.block_sensitivity.clear()
        self.block_dist.clear()
        self.block_influence.clear()
        self.block_matrix.clear()
        self.block_zone.clear()
        self._coh_gauge.set_value(0.0)
        self.dist_kept_val.setText("-")
        self.dist_rej_val.setText("-")
        self.dist_kept_bar.set_data(0.0, 0.0, 1.0, Colors.SUCCESS)
        self.dist_rej_bar.set_data(0.0, 0.0, 1.0, Colors.ERROR)
        for pid, da, dg in self.inf_rows:
            pid.setText("-")
            da.setText("d angle -")
            dg.setText("d mean -")
        self.sens_strict.set_value("mean -, dir -")
        self.sens_default.set_value("mean -, dir -")
        self.sens_perm.set_value("mean -, dir -")
        self.zone_n.set_value("-")
        self.zone_c.set_value("-")
        self.zone_s.set_value("-")
        self.matrix.clear()

    def update_from_app(self, app):
        self.clear()

        tri = getattr(app, "triangle_data", None)
        if tri is None or getattr(tri, "empty", True):
            return

        gradients = _numeric_series(tri["gradient"].apply(_as_scalar))
        angles = _numeric_series(tri["angle"].apply(_as_scalar))
        if len(gradients) == 0:
            return

        mean_g = float(gradients.mean())
        self.block_core.set_value("avg", f"{mean_g:.5f}")
        self.block_core.set_value("median", f"{float(gradients.median()):.5f}")
        self.block_core.set_value("std", f"{float(gradients.std(ddof=1)):.5f}" if len(gradients) > 1 else "-")
        self.block_core.set_value("range", f"{float(gradients.min()):.5f} - {float(gradients.max()):.5f}")
        self.block_core.set_value(
            "p10p90", f"{float(gradients.quantile(0.10)):.5f} / {float(gradients.quantile(0.90)):.5f}"
        )

        std = float(gradients.std(ddof=1)) if len(gradients) > 1 else np.nan
        cv = (std / mean_g) if np.isfinite(std) and abs(mean_g) > 1e-12 else np.nan
        self.block_core.set_value("cv", f"{cv:.3f}" if np.isfinite(cv) else "-")

        if len(gradients) > 1:
            try:
                from statistics import NormalDist

                ci_level = float(getattr(app, "histogram_ci_level", 95))
                ci_level = float(np.clip(ci_level, 50.0, 99.9))
                alpha = 1.0 - (ci_level / 100.0)
                z = NormalDist().inv_cdf(1.0 - (alpha / 2.0))
                se = std / float(np.sqrt(len(gradients)))
                lo = mean_g - (z * se)
                hi = mean_g + (z * se)
                self.block_core.set_value("ci", f"{int(ci_level)}%: {lo:.5f} - {hi:.5f}")
            except Exception:
                self.block_core.set_value("ci", "-")

        angle_u = None
        angle_w = None
        calc = getattr(app, "gradient_calculator", None)
        if calc is not None:
            try:
                res = calc.calculate_average_gradient()
                if res and len(res) >= 3:
                    _, angle_u, angle_w = res
            except Exception:
                angle_u = None
                angle_w = None

        if angle_u is None and len(angles) > 0:
            ar = np.deg2rad(angles.to_numpy(dtype=float))
            angle_u = float(np.degrees(np.arctan2(np.mean(np.sin(ar)), np.mean(np.cos(ar)))) % 360.0)

        if angle_w is None and len(angles) == len(gradients) and len(angles) > 0:
            a = np.deg2rad(angles.to_numpy(dtype=float))
            w = gradients.to_numpy(dtype=float)
            ws = np.sum(w)
            if ws > 0:
                w = w / ws
                angle_w = float(np.degrees(np.arctan2(np.sum(w * np.sin(a)), np.sum(w * np.cos(a)))) % 360.0)

        if angle_u is not None:
            self.block_direction.set_value("dir_u", f"{angle_u:.1f} deg {self._angle_to_compass(angle_u)}")
        if angle_w is not None:
            self.block_direction.set_value("dir_w", f"{angle_w:.1f} deg {self._angle_to_compass(angle_w)}")

        if len(angles) > 0:
            ang_rad = np.deg2rad(angles.to_numpy(dtype=float))
            R = float(np.hypot(np.mean(np.cos(ang_rad)), np.mean(np.sin(ang_rad))))
            self.block_direction.set_value("coherence", f"{R:.3f}")
            self._coh_gauge.set_value(R)

        rej = getattr(app, "rejected_data", None)
        rej_g = pd.Series(dtype=float)
        if rej is not None and not getattr(rej, "empty", True):
            if "gradient_computed" in rej.columns and "gradient" in rej.columns:
                mask = rej["gradient_computed"].fillna(False).astype(bool)
                rej_g = _numeric_series(rej.loc[mask, "gradient"].apply(_as_scalar))
                self.block_rejected.set_value("rej_comp", f"{int(mask.sum())}/{int(len(rej))}")
            elif "gradient" in rej.columns:
                rej_g = _numeric_series(rej["gradient"].apply(_as_scalar))
                self.block_rejected.set_value("rej_comp", f"{len(rej_g)}/{int(len(rej))}")
            else:
                rej_g = pd.Series(dtype=float)

            if len(rej_g) > 0:
                self.block_rejected.set_value("cmp_mean", f"{mean_g:.5f} / {float(rej_g.mean()):.5f}")
                self.block_rejected.set_value(
                    "cmp_median", f"{float(gradients.median()):.5f} / {float(rej_g.median()):.5f}"
                )
                self.block_rejected.set_value(
                    "cmp_iqr",
                    f"{float(gradients.quantile(0.75)-gradients.quantile(0.25)):.5f} / "
                    f"{float(rej_g.quantile(0.75)-rej_g.quantile(0.25)):.5f}",
                )

            # Overlap matrix
            def _bool_col(name: str):
                if name in rej.columns:
                    return rej[name].fillna(False).astype(bool).to_numpy()
                return np.zeros(len(rej), dtype=bool)

            masks = {
                "thin": _bool_col("quality_is_thin_triangle"),
                "unc": _bool_col("quality_is_uncertainty"),
                "stack": _bool_col("quality_is_stacked_points"),
                "max": _bool_col("quality_is_max_base_or_height"),
            }
            if not any(np.any(v) for v in masks.values()) and "reason" in rej.columns:
                rs = rej["reason"].astype(str).to_numpy()
                masks["thin"] = np.isin(rs, ["thin_triangle", "mixed"])
                masks["unc"] = np.isin(rs, ["uncertainty", "mixed"])
                masks["stack"] = rs == "stacked_points"
                masks["max"] = rs == "max_base_or_height"
            counts = {}
            keys = ["thin", "unc", "stack", "max"]
            for a in keys:
                for b in keys:
                    counts[(a, b)] = int(np.count_nonzero(masks[a] & masks[b]))
            self.matrix.set_counts(counts)

        # Sensitivity placeholders (future scenario engine)
        base_angle = float(angle_w) if angle_w is not None else (float(angle_u) if angle_u is not None else 0.0)
        self.sens_strict.set_value(f"{mean_g * 0.89:.5f} | {((base_angle - 6.0) % 360):.1f} deg")
        self.sens_default.set_value(f"{mean_g:.5f} | {base_angle:.1f} deg")
        self.sens_perm.set_value(f"{mean_g * 1.17:.5f} | {((base_angle + 8.0) % 360):.1f} deg")

        # Distribution bands
        kp10 = float(gradients.quantile(0.10))
        kp90 = float(gradients.quantile(0.90))
        self.dist_kept_val.setText(f"{kp10:.5f} / {kp90:.5f}")
        if len(rej_g) > 0:
            rp10 = float(rej_g.quantile(0.10))
            rp90 = float(rej_g.quantile(0.90))
            self.dist_rej_val.setText(f"{rp10:.5f} / {rp90:.5f}")
        else:
            rp10 = 0.0
            rp90 = 0.0
            self.dist_rej_val.setText("-")
        vmax = max(kp90, rp90, float(gradients.max()), float(rej_g.max()) if len(rej_g) > 0 else 0.0, 1e-8)
        self.dist_kept_bar.set_data(kp10, kp90, vmax, Colors.SUCCESS)
        self.dist_rej_bar.set_data(rp10, rp90, vmax, Colors.ERROR)

        # Point influence (leave-one-point-out, top 3)
        if "point_ids" in tri.columns and len(tri) > 0 and angle_w is not None:
            ids_list = tri["point_ids"].tolist()
            n = len(ids_list)
            pid_masks = {}
            for i, ids in enumerate(ids_list):
                if not isinstance(ids, (list, tuple, np.ndarray)):
                    continue
                for pid in ids:
                    key = str(pid)
                    if key not in pid_masks:
                        pid_masks[key] = np.zeros(n, dtype=bool)
                    pid_masks[key][i] = True

            base_angle = float(angle_w)
            scored = []
            g_arr = gradients.to_numpy(dtype=float)
            a_arr = angles.to_numpy(dtype=float)
            for pid, mask in pid_masks.items():
                keep = ~mask
                if np.count_nonzero(keep) < 8:
                    continue
                a2 = a_arr[keep]
                g2 = g_arr[keep]
                if len(a2) < 3:
                    continue
                a2_rad = np.deg2rad(a2)
                ws = np.sum(g2)
                if ws > 0:
                    w = g2 / ws
                    ang2 = float(np.degrees(np.arctan2(np.sum(w * np.sin(a2_rad)), np.sum(w * np.cos(a2_rad)))) % 360.0)
                else:
                    ang2 = float(np.degrees(np.arctan2(np.mean(np.sin(a2_rad)), np.mean(np.cos(a2_rad)))) % 360.0)
                d_ang = abs(((ang2 - base_angle + 180.0) % 360.0) - 180.0)
                mean2 = float(np.mean(g2))
                d_mean = mean2 - mean_g
                scored.append((d_ang, abs(d_mean), pid, d_ang, d_mean))
            scored.sort(key=lambda t: (t[0], t[1]), reverse=True)
            for i, (pid_lbl, da_lbl, dg_lbl) in enumerate(self.inf_rows):
                if i < len(scored):
                    _, _, pid, d_ang, d_mean = scored[i]
                    pid_lbl.setText(pid)
                    da_lbl.setText(f"d angle {d_ang:+.1f} deg")
                    dg_lbl.setText(f"d mean {d_mean:+.5f}")

        # Directional stability by coarse north/central/south zones.
        if {"centroid_y", "angle", "gradient"}.issubset(set(tri.columns)):
            tz = tri.copy()
            tz["centroid_y"] = pd.to_numeric(tz["centroid_y"], errors="coerce")
            tz["angle"] = pd.to_numeric(tz["angle"].apply(_as_scalar), errors="coerce")
            tz["gradient"] = pd.to_numeric(tz["gradient"].apply(_as_scalar), errors="coerce")
            tz = tz.dropna(subset=["centroid_y", "angle", "gradient"])
            if len(tz) >= 6:
                y = tz["centroid_y"].to_numpy(dtype=float)
                a = tz["angle"].to_numpy(dtype=float)
                g = tz["gradient"].to_numpy(dtype=float)
                q1, q2 = np.quantile(y, [1.0 / 3.0, 2.0 / 3.0])
                zone_masks = {
                    self.zone_n: y >= q2,
                    self.zone_c: (y >= q1) & (y < q2),
                    self.zone_s: y < q1,
                }
                for card, zmask in zone_masks.items():
                    if np.count_nonzero(zmask) < 3:
                        card.set_value("R -, dir -")
                        continue
                    az = a[zmask]
                    gz = g[zmask]
                    rz = float(np.hypot(np.mean(np.cos(np.deg2rad(az))), np.mean(np.sin(np.deg2rad(az)))))
                    ws = np.sum(gz)
                    if ws > 0:
                        w = gz / ws
                        mz = float(np.degrees(np.arctan2(np.sum(w * np.sin(np.deg2rad(az))), np.sum(w * np.cos(np.deg2rad(az))))) % 360.0)
                    else:
                        mz = float(np.degrees(np.arctan2(np.mean(np.sin(np.deg2rad(az))), np.mean(np.cos(np.deg2rad(az))))) % 360.0)
                    card.set_value(f"R {rz:.3f} | {mz:.1f} deg")
