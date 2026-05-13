"""
Rejection reason breakdown bars widget.
All visuals use QSS + real child widgets (no custom QPainter).
"""

from __future__ import annotations

from typing import Any, Dict, List

from PyQt5.QtCore import Qt, QSize
from PyQt5.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from styles.colors import Colors
from ui.icons import icon


class _BreakdownRow(QWidget):
    """Single breakdown row: label + bar + count — pure widget-based."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(32)
        self.setStyleSheet("background: transparent;")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(10)

        self.label = QLabel("")
        self.label.setFixedWidth(110)
        self.label.setStyleSheet(f"""
            color: {Colors.TEXT_SECONDARY};
            font-size: 11px; font-weight: 500;
            background: transparent;
        """)
        layout.addWidget(self.label)

        # Bar — single widget with gradient (Qt can't clip children to border-radius)
        self._bar = QWidget()
        self._bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._bar.setFixedHeight(6)
        self._bar.setAttribute(Qt.WA_StyledBackground, True)
        self._bar.setStyleSheet(f"background-color: {Colors.BG_SURFACE}; border-radius: 3px;")
        layout.addWidget(self._bar)

        self.count_label = QLabel("0")
        self.count_label.setFixedWidth(90)
        self.count_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.count_label.setStyleSheet(f"""
            color: {Colors.TEXT_PRIMARY};
            font-size: 11px; font-weight: 600;
            background: transparent;
        """)
        layout.addWidget(self.count_label)

    def set_data(self, label: str, count: int, total: int, pct: float, color: str):
        self.label.setText(label)
        self.count_label.setText(f"{count}  ({pct:.1f}%)")

        if pct > 0:
            p = max(0.01, min(0.99, pct / 100.0))
            self._bar.setStyleSheet(f"""
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {color},
                    stop:{p:.4f} {color},
                    stop:{p + 0.001:.4f} {Colors.BG_SURFACE},
                    stop:1 {Colors.BG_SURFACE});
                border-radius: 3px;
            """)
        else:
            self._bar.setStyleSheet(f"background-color: {Colors.BG_SURFACE}; border-radius: 3px;")


class RejectionBreakdownBars(QWidget):
    """Vertical stack of rejection reason breakdown bars."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        self._mode = "primary"
        self._primary_data: List[Dict[str, Any]] = []
        self._all_data: List[Dict[str, Any]] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)

        # Icon
        icon_lbl = QLabel()
        icon_lbl.setPixmap(icon("fa6s.chart-column", color=Colors.TEXT_TERTIARY, scale_factor=0.8).pixmap(QSize(12, 12)))
        header.addWidget(icon_lbl)

        self.title_label = QLabel("Breakdown by Reason")
        self.title_label.setStyleSheet(f"""
            color: {Colors.TEXT_TERTIARY};
            font-size: 10px; font-weight: 700;
            text-transform: uppercase; letter-spacing: 0.7px;
            background: transparent;
        """)
        header.addWidget(self.title_label)
        header.addStretch()

        self._btn_primary = QLabel("Primary")
        self._btn_primary.setObjectName("breakdownPrimary")
        self._btn_primary.setAlignment(Qt.AlignCenter)
        self._btn_primary.setFixedHeight(20)
        self._btn_primary.setMinimumWidth(56)
        self._btn_primary.setStyleSheet(self._pill_style(active=True))
        self._btn_primary.setCursor(Qt.PointingHandCursor)

        self._btn_all = QLabel("All causes")
        self._btn_all.setObjectName("breakdownAll")
        self._btn_all.setAlignment(Qt.AlignCenter)
        self._btn_all.setFixedHeight(20)
        self._btn_all.setMinimumWidth(64)
        self._btn_all.setStyleSheet(self._pill_style(active=False))
        self._btn_all.setCursor(Qt.PointingHandCursor)

        header.addWidget(self._btn_primary)
        header.addWidget(self._btn_all)

        layout.addLayout(header)

        self._rows_layout = QVBoxLayout()
        self._rows_layout.setContentsMargins(0, 4, 0, 0)
        self._rows_layout.setSpacing(2)
        layout.addLayout(self._rows_layout)

        self._row_widgets: list = []
        self._note = QLabel("")
        self._note.setWordWrap(True)
        self._note.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: 10px; background: transparent;")
        layout.addWidget(self._note)
        self._btn_primary.mousePressEvent = lambda e: self._set_mode("primary")
        self._btn_all.mousePressEvent = lambda e: self._set_mode("all")

    def _pill_style(self, active: bool) -> str:
        if active:
            return f"""
                QLabel {{
                    background-color: {Colors.ACCENT_GHOST};
                    color: {Colors.TEXT_ACCENT};
                    border: 1px solid {Colors.BORDER_ACCENT};
                    border-radius: 10px;
                    font-size: 10px; font-weight: 600;
                    padding: 0 8px;
                }}
            """
        return f"""
            QLabel {{
                background-color: {Colors.BG_SURFACE};
                color: {Colors.TEXT_MUTED};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 10px;
                font-size: 10px; font-weight: 600;
                padding: 0 8px;
            }}
        """

    def _set_mode(self, mode: str):
        if mode not in ("primary", "all"):
            return
        if self._mode == mode:
            return
        self._mode = mode
        self._btn_primary.setStyleSheet(self._pill_style(active=self._mode == "primary"))
        self._btn_all.setStyleSheet(self._pill_style(active=self._mode == "all"))
        self._render_rows()

    def update_data(self, breakdown_primary: List[Dict[str, Any]], breakdown_all: List[Dict[str, Any]]):
        self._primary_data = breakdown_primary or []
        self._all_data = breakdown_all or []
        self._render_rows()

    def _render_rows(self):
        breakdown_list = self._primary_data if self._mode == "primary" else self._all_data
        self._update_note()
        # Clear existing rows
        for w in self._row_widgets:
            self._rows_layout.removeWidget(w)
            w.deleteLater()
        self._row_widgets.clear()

        if not breakdown_list:
            empty = QLabel("No rejected triangles")
            empty.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: 11px; background: transparent;")
            self._rows_layout.addWidget(empty)
            self._row_widgets.append(empty)
            return

        for item in breakdown_list:
            row = _BreakdownRow()
            color = getattr(Colors, item.get("color_key", "REJECTION_CALC_FAILED"), Colors.REJECTION_CALC_FAILED)
            row.set_data(
                label=item.get("label", "Unknown"),
                count=item.get("count", 0),
                total=item.get("total", 0),
                pct=item.get("pct", 0),
                color=color,
            )
            self._rows_layout.addWidget(row)
            self._row_widgets.append(row)

    def _update_note(self):
        if not self._primary_data and not self._all_data:
            self._note.setText("")
            return

        primary_total = int(sum(int(v.get("count", 0)) for v in (self._primary_data or [])))
        all_total = int(sum(int(v.get("count", 0)) for v in (self._all_data or [])))
        if all_total <= primary_total:
            self._note.setText("No multi-cause rejections detected in current data.")
        else:
            extra = all_total - primary_total
            self._note.setText(f"All causes includes {extra} additional cause hits vs primary-only.")

    def clear(self):
        for w in self._row_widgets:
            self._rows_layout.removeWidget(w)
            w.deleteLater()
        self._row_widgets.clear()
        self._primary_data = []
        self._all_data = []
        self._note.setText("")
