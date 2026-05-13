"""
HeadAnalyser V2 - Plot Quick Stats (Bottom Drawer)
Compact, glanceable statistics panel intended for fast iteration during analysis.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Dict, Iterable, List, Tuple

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
)

from styles.colors import Colors


def _iter_point_ids(value: Any) -> Iterable[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return value
    return [value]


def _angle_to_compass(angle: float) -> str:
    # 0° = E, counterclockwise (matches existing app convention)
    directions = ["E", "NE", "N", "NW", "W", "SW", "S", "SE"]
    idx = round(float(angle) / 45.0) % 8
    return directions[idx]


class _MetricPill(QWidget):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(
            f"""
            QWidget {{
                background-color: {Colors.BG_SURFACE};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 8px;
            }}
            """
        )
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 6, 10, 6)
        root.setSpacing(2)

        self.title = QLabel(title)
        self.title.setStyleSheet(f"color: {Colors.TEXT_TERTIARY}; font-size: 9px; font-weight: 700;")
        root.addWidget(self.title)

        self.value = QLabel("-")
        self.value.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; font-size: 12px; font-weight: 800;")
        root.addWidget(self.value)

    def set_value(self, text: str):
        self.value.setText(text)


class PlotQuickStatsPanel(QWidget):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.setObjectName("plotQuickStats")
        self.setAttribute(Qt.WA_StyledBackground, True)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(10)

        title = QLabel("Quick Stats")
        title.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; font-size: 12px; font-weight: 700;")
        header.addWidget(title)

        self.hint = QLabel("Double-click an ID to inspect (valid triangles only).")
        self.hint.setStyleSheet(f"color: {Colors.TEXT_TERTIARY}; font-size: 10px;")
        header.addWidget(self.hint)

        header.addStretch()

        self.btn_full_stats = QPushButton("Open Full Statistics")
        self.btn_full_stats.clicked.connect(self._open_full_statistics)
        header.addWidget(self.btn_full_stats)

        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.clicked.connect(self.update_from_app)
        header.addWidget(self.btn_refresh)

        root.addLayout(header)

        # Summary row (compact, glanceable)
        summary = QHBoxLayout()
        summary.setSpacing(10)

        self.metric_mean_grad = _MetricPill("Mean gradient")
        summary.addWidget(self.metric_mean_grad)

        self.metric_mean_dir = _MetricPill("Mean direction")
        summary.addWidget(self.metric_mean_dir)

        self.metric_weighted_dir = _MetricPill("Weighted direction")
        summary.addWidget(self.metric_weighted_dir)

        summary.addStretch()
        root.addLayout(summary)

        tables = QHBoxLayout()
        tables.setSpacing(12)

        self.rejected_table = self._make_table(
            "Top rejected IDs",
            ["ID", "Rejected", "Valid", "Rej. Rate"],
        )
        self.rejected_table.itemDoubleClicked.connect(lambda item: self._inspect_row(self.rejected_table, item.row()))
        tables.addWidget(self.rejected_table, 1)

        self.gradient_table = self._make_table(
            "Top gradient IDs",
            ["ID", "Max Grad", "Mean Grad", "N Triangles"],
        )
        self.gradient_table.itemDoubleClicked.connect(lambda item: self._inspect_row(self.gradient_table, item.row()))
        tables.addWidget(self.gradient_table, 1)

        root.addLayout(tables, 1)

        self.setStyleSheet(
            f"""
            QWidget#plotQuickStats {{
                background-color: {Colors.BG_ELEVATED};
                border-top: 1px solid {Colors.BORDER_DEFAULT};
            }}
            QLabel {{
                background: transparent;
            }}
            QTableWidget {{
                background-color: {Colors.BG_SURFACE};
                border: 1px solid {Colors.BORDER_DEFAULT};
                color: {Colors.TEXT_PRIMARY};
                gridline-color: {Colors.BORDER_SUBTLE};
            }}
            QHeaderView::section {{
                background-color: {Colors.BG_ELEVATED};
                color: {Colors.TEXT_SECONDARY};
                border: none;
                border-bottom: 1px solid {Colors.BORDER_DEFAULT};
                padding: 6px 8px;
                font-size: 10px;
                font-weight: 700;
            }}
            QTableWidget::item {{
                padding: 4px 8px;
            }}
            QTableWidget::item:selected {{
                background-color: {Colors.OVERLAY_ACTIVE};
            }}
            QPushButton {{
                background-color: {Colors.BG_SURFACE};
                border: 1px solid {Colors.BORDER_STRONG};
                border-radius: 6px;
                padding: 5px 10px;
                font-size: 10px;
                font-weight: 600;
                color: {Colors.TEXT_PRIMARY};
                min-height: 26px;
            }}
            QPushButton:hover {{
                background-color: {Colors.BG_HOVER};
                border-color: {Colors.ACCENT_PRIMARY};
            }}
            """
        )

    def _make_table(self, title: str, columns: List[str]) -> QTableWidget:
        table = QTableWidget()
        table.setColumnCount(len(columns))
        table.setHorizontalHeaderLabels(columns)
        table.verticalHeader().setVisible(False)
        table.setShowGrid(False)
        table.setAlternatingRowColors(True)
        table.setSortingEnabled(False)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setSelectionMode(QTableWidget.SingleSelection)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.horizontalHeader().setHighlightSections(False)
        table.setMinimumHeight(140)
        table.setToolTip(title)
        return table

    def _open_full_statistics(self):
        try:
            self.main_window.nav_sidebar.set_active_page("stats")
            self.main_window.on_page_changed("stats")
        except Exception:
            pass

    def _inspect_row(self, table: QTableWidget, row: int):
        try:
            item = table.item(row, 0)
            if item is None:
                return
            point_id = item.text()
        except Exception:
            return

        tri_df = getattr(self.main_window, "triangle_data", None)
        if tri_df is None or getattr(tri_df, "empty", True):
            return

        tri_indices: List[int] = []
        try:
            for idx, ids in tri_df["point_ids"].items():
                if point_id in [str(v) for v in _iter_point_ids(ids)]:
                    tri_indices.append(int(idx))
        except Exception:
            tri_indices = []

        # Avoid selecting huge sets (still useful for inspection).
        tri_indices = tri_indices[:500]
        self.main_window.set_triangle_selection(tri_indices, meta={"source": "quick_stats", "point_id": point_id})
        try:
            self.main_window.show_selection_inspector()
        except Exception:
            pass

    def update_from_app(self):
        """Refresh tables from the current active dataset/app state."""
        rejected_df = getattr(self.main_window, "rejected_data", None)
        valid_df = getattr(self.main_window, "triangle_data", None)

        self._fill_summary_metrics(valid_df)
        self._fill_rejected_ids(rejected_df, valid_df)
        self._fill_gradient_ids(valid_df)

    def _fill_summary_metrics(self, valid_df):
        # Mean gradient (from current valid triangles)
        try:
            if valid_df is not None and not valid_df.empty and "gradient" in valid_df.columns:
                mean_g = float(valid_df["gradient"].astype(float).mean())
                self.metric_mean_grad.set_value(f"{mean_g:.6f} m/m")
            else:
                self.metric_mean_grad.set_value("-")
        except Exception:
            self.metric_mean_grad.set_value("-")

        # Mean direction + weighted mean direction (uses the same helper as main stats)
        try:
            calc = getattr(self.main_window, "gradient_calculator", None)
            if calc is None:
                self.metric_mean_dir.set_value("-")
                self.metric_weighted_dir.set_value("-")
                return

            result = calc.calculate_average_gradient()
            if not result or len(result) < 3:
                self.metric_mean_dir.set_value("-")
                self.metric_weighted_dir.set_value("-")
                return

            _, ang, ang_w = result
            if ang is None:
                self.metric_mean_dir.set_value("-")
            else:
                compass = _angle_to_compass(float(ang))
                self.metric_mean_dir.set_value(f"{float(ang):.1f}° {compass}")

            if ang_w is None:
                self.metric_weighted_dir.set_value("-")
            else:
                compass_w = _angle_to_compass(float(ang_w))
                self.metric_weighted_dir.set_value(f"{float(ang_w):.1f}° {compass_w}")
        except Exception:
            self.metric_mean_dir.set_value("-")
            self.metric_weighted_dir.set_value("-")

    def _fill_rejected_ids(self, rejected_df, valid_df):
        rej_freq: Counter = Counter()
        val_freq: Counter = Counter()

        try:
            if rejected_df is not None and not rejected_df.empty and "point_ids" in rejected_df.columns:
                for ids in rejected_df["point_ids"]:
                    rej_freq.update([str(v) for v in _iter_point_ids(ids)])
        except Exception:
            rej_freq = Counter()

        try:
            if valid_df is not None and not valid_df.empty and "point_ids" in valid_df.columns:
                for ids in valid_df["point_ids"]:
                    val_freq.update([str(v) for v in _iter_point_ids(ids)])
        except Exception:
            val_freq = Counter()

        all_ids = set(rej_freq.keys()) | set(val_freq.keys())
        rows: List[Tuple[str, int, int, float]] = []
        for pid in all_ids:
            r = int(rej_freq.get(pid, 0))
            v = int(val_freq.get(pid, 0))
            tot = r + v
            rate = (r / tot * 100.0) if tot > 0 else 0.0
            rows.append((pid, r, v, rate))

        rows.sort(key=lambda t: (t[1], t[3]), reverse=True)
        rows = rows[:20]

        self.rejected_table.setRowCount(len(rows))
        for i, (pid, r, v, rate) in enumerate(rows):
            self.rejected_table.setItem(i, 0, QTableWidgetItem(str(pid)))
            self.rejected_table.setItem(i, 1, QTableWidgetItem(str(r)))
            self.rejected_table.setItem(i, 2, QTableWidgetItem(str(v)))
            self.rejected_table.setItem(i, 3, QTableWidgetItem(f"{rate:.1f}%"))

        if len(rows) == 0:
            self.rejected_table.setRowCount(1)
            self.rejected_table.setItem(0, 0, QTableWidgetItem("No rejected data"))
            for c in range(1, self.rejected_table.columnCount()):
                self.rejected_table.setItem(0, c, QTableWidgetItem(""))

    def _fill_gradient_ids(self, valid_df):
        per_id: Dict[str, Dict[str, float]] = defaultdict(lambda: {"count": 0.0, "sum": 0.0, "max": 0.0})
        try:
            if valid_df is not None and not valid_df.empty and "point_ids" in valid_df.columns and "gradient" in valid_df.columns:
                for _, row in valid_df.iterrows():
                    try:
                        g = float(row["gradient"])
                    except Exception:
                        continue
                    for pid in [str(v) for v in _iter_point_ids(row["point_ids"])]:
                        rec = per_id[pid]
                        rec["count"] += 1.0
                        rec["sum"] += g
                        if g > rec["max"]:
                            rec["max"] = g
        except Exception:
            per_id = defaultdict(lambda: {"count": 0.0, "sum": 0.0, "max": 0.0})

        rows: List[Tuple[str, float, float, int]] = []
        for pid, rec in per_id.items():
            c = int(rec["count"])
            mean = (rec["sum"] / rec["count"]) if rec["count"] > 0 else 0.0
            rows.append((pid, float(rec["max"]), float(mean), c))

        rows.sort(key=lambda t: (t[1], t[2]), reverse=True)
        rows = rows[:20]

        self.gradient_table.setRowCount(len(rows))
        for i, (pid, gmax, gmean, c) in enumerate(rows):
            self.gradient_table.setItem(i, 0, QTableWidgetItem(str(pid)))
            self.gradient_table.setItem(i, 1, QTableWidgetItem(f"{gmax:.6f}"))
            self.gradient_table.setItem(i, 2, QTableWidgetItem(f"{gmean:.6f}"))
            self.gradient_table.setItem(i, 3, QTableWidgetItem(str(c)))

        if len(rows) == 0:
            self.gradient_table.setRowCount(1)
            self.gradient_table.setItem(0, 0, QTableWidgetItem("No triangle data"))
            for c in range(1, self.gradient_table.columnCount()):
                self.gradient_table.setItem(0, c, QTableWidgetItem(""))
