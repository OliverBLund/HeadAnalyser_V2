"""
Triangle summary cards row — Total / Kept / Rejected / Ratio / Avg Gradient.
All visuals use QSS + real child widgets (no custom QPainter).
"""

from __future__ import annotations

from typing import Any, Dict

from PyQt5.QtCore import Qt, QSize
from PyQt5.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from styles.colors import Colors
from ui.icons import icon, Icons


class _SummaryCard(QWidget):
    """Single metric card with colored left bar — pure QSS."""

    def __init__(self, label: str, icon_name: str = None, bar_color: str = Colors.ACCENT_PRIMARY,
                 value_color: str = Colors.TEXT_PRIMARY, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(140)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setFixedHeight(64)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            _SummaryCard {{
                background-color: {Colors.BG_SURFACE};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-left: 3px solid {bar_color};
                border-radius: 8px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 10, 8)
        layout.setSpacing(2)

        # Title row with optional icon
        title_row = QHBoxLayout()
        title_row.setSpacing(4)
        title_row.setContentsMargins(0, 0, 0, 0)

        if icon_name:
            icon_lbl = QLabel()
            icon_lbl.setPixmap(icon(icon_name, color=Colors.TEXT_TERTIARY, scale_factor=0.7).pixmap(QSize(10, 10)))
            title_row.addWidget(icon_lbl)

        title = QLabel(label)
        title.setStyleSheet(f"""
            color: {Colors.TEXT_TERTIARY};
            font-size: 9px; font-weight: 700;
            text-transform: uppercase; letter-spacing: 0.7px;
            background: transparent; border: none;
        """)
        title_row.addWidget(title)
        title_row.addStretch()

        layout.addLayout(title_row)

        self.value_label = QLabel("-")
        self.value_label.setStyleSheet(f"""
            color: {value_color};
            font-size: 17px; font-weight: 600;
            background: transparent; border: none;
            line-height: 1.1;
        """)
        layout.addWidget(self.value_label)

        self.detail_label = QLabel("")
        self.detail_label.setStyleSheet(f"""
            color: {Colors.TEXT_MUTED};
            font-size: 10px;
            background: transparent; border: none;
        """)
        self.detail_label.setVisible(False)
        layout.addWidget(self.detail_label)

    def set_value(self, value: str, detail: str = ""):
        self.value_label.setText(value)
        if detail:
            self.detail_label.setText(detail)
            self.detail_label.setVisible(True)
        else:
            self.detail_label.setVisible(False)


class _RatioBarCard(QWidget):
    """Card with a stacked kept/rejected bar — pure QSS + child widgets."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(140)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setFixedHeight(64)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            _RatioBarCard {{
                background-color: {Colors.BG_SURFACE};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 8px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(6)

        header = QHBoxLayout()
        header.setSpacing(4)

        # Icon
        icon_lbl = QLabel()
        icon_lbl.setPixmap(icon("fa6s.chart-pie", color=Colors.TEXT_TERTIARY, scale_factor=0.7).pixmap(QSize(10, 10)))
        header.addWidget(icon_lbl)

        label = QLabel("KEPT / REJECTED")
        label.setStyleSheet(f"""
            color: {Colors.TEXT_TERTIARY};
            font-size: 9px; font-weight: 700;
            text-transform: uppercase; letter-spacing: 0.7px;
            background: transparent; border: none;
        """)
        header.addWidget(label)
        header.addStretch()

        self.ratio_label = QLabel("")
        self.ratio_label.setStyleSheet(f"""
            color: {Colors.TEXT_SECONDARY};
            font-size: 10px; font-weight: 600;
            background: transparent; border: none;
        """)
        header.addWidget(self.ratio_label)
        layout.addLayout(header)

        # Bar — single widget with gradient (Qt can't clip children to border-radius)
        self._bar = QWidget()
        self._bar.setFixedHeight(8)
        self._bar.setAttribute(Qt.WA_StyledBackground, True)
        self._bar.setStyleSheet(f"background-color: {Colors.BG_HOVER}; border-radius: 4px;")
        layout.addWidget(self._bar)

        # Legend row
        legend = QHBoxLayout()
        legend.setSpacing(12)

        self.kept_label = QLabel("")
        self.kept_label.setStyleSheet(f"color: {Colors.SUCCESS}; font-size: 10px; font-weight: 600; background: transparent;")
        legend.addWidget(self.kept_label)

        self.rej_label = QLabel("")
        self.rej_label.setStyleSheet(f"color: {Colors.ERROR}; font-size: 10px; font-weight: 600; background: transparent;")
        legend.addWidget(self.rej_label)
        legend.addStretch()
        layout.addLayout(legend)

    def set_data(self, kept: int, rejected: int, kept_pct: float, rejected_pct: float):
        self.ratio_label.setText(f"{kept_pct:.1f}% / {rejected_pct:.1f}%")
        self.kept_label.setText(f"{kept_pct:.1f}% kept")
        self.rej_label.setText(f"{rejected_pct:.1f}% rej.")

        total = kept_pct + rejected_pct
        if total > 0:
            kept_stop = kept_pct / total
            k = max(0.001, min(0.999, kept_stop))
            self._bar.setStyleSheet(f"""
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {Colors.SUCCESS},
                    stop:{k:.4f} {Colors.SUCCESS},
                    stop:{k + 0.001:.4f} {Colors.ERROR},
                    stop:1 {Colors.ERROR});
                border-radius: 4px;
            """)
        else:
            self._bar.setStyleSheet(f"background-color: {Colors.BG_HOVER}; border-radius: 4px;")


class TriangleSummaryCards(QWidget):
    """Horizontal row of summary metric cards."""

    def __init__(self, compact: bool = False, parent=None):
        super().__init__(parent)
        self._compact = compact
        self.setStyleSheet("background: transparent;")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.card_total = _SummaryCard("Total", icon_name="fa6s.table-cells", bar_color=Colors.INFO)
        self.card_kept = _SummaryCard("Kept", icon_name="fa6s.circle-check", bar_color=Colors.SUCCESS, value_color=Colors.SUCCESS)
        self.card_rejected = _SummaryCard("Rejected", icon_name="fa6s.circle-xmark", bar_color=Colors.ERROR, value_color=Colors.ERROR)
        self.card_ratio = _RatioBarCard()
        self.card_gradient = _SummaryCard("Avg Gradient", icon_name="fa6s.chart-line", bar_color=Colors.ACCENT_PRIMARY, value_color=Colors.ACCENT_BRIGHT)

        layout.addWidget(self.card_total)
        layout.addWidget(self.card_kept)
        layout.addWidget(self.card_rejected)
        layout.addWidget(self.card_ratio)
        layout.addWidget(self.card_gradient)

    def update_data(self, summary: Dict[str, Any]):
        total = summary.get("total", 0)
        kept = summary.get("kept", 0)
        rejected = summary.get("rejected", 0)
        kept_pct = summary.get("kept_pct", 0)
        rejected_pct = summary.get("rejected_pct", 0)
        avg_gradient = summary.get("avg_gradient")

        self.card_total.set_value(str(total))
        self.card_kept.set_value(str(kept), f"{kept_pct:.1f}%")
        self.card_rejected.set_value(str(rejected), f"{rejected_pct:.1f}%")
        self.card_ratio.set_data(kept, rejected, kept_pct, rejected_pct)

        if avg_gradient is not None:
            self.card_gradient.set_value(f"{avg_gradient:.5f}")
        else:
            self.card_gradient.set_value("-")

    def clear(self):
        self.card_total.set_value("-")
        self.card_kept.set_value("-")
        self.card_rejected.set_value("-")
        self.card_ratio.set_data(0, 0, 0, 0)
        self.card_gradient.set_value("-")
