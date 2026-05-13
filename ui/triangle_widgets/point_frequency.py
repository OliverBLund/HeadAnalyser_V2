"""
Per-point rejection frequency bars with threshold filter.
All visuals use QSS + real child widgets (no custom QPainter).
"""

from __future__ import annotations

import math
from typing import Optional

import pandas as pd
from PyQt5.QtCore import Qt, pyqtSignal, QSize
from PyQt5.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QScrollArea, QSizePolicy,
    QVBoxLayout, QWidget, QFrame,
)

from styles.colors import Colors
from ui.icons import icon


class _FreqRow(QWidget):
    """Single point frequency row: ID + stacked bar + percentage — widget-based."""

    clicked = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(30)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet("background: transparent;")

        self._point_id = ""
        self._rejected_pct = 0.0
        self._valid_pct = 0.0
        self._selected = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(8)

        self.id_label = QLabel("")
        self.id_label.setFixedWidth(60)
        self.id_label.setStyleSheet(f"""
            color: {Colors.TEXT_PRIMARY};
            font-size: 11px; font-weight: 600;
            background: transparent;
        """)
        layout.addWidget(self.id_label)

        # Bar — single widget with gradient (Qt can't clip children to border-radius)
        self._bar = QWidget()
        self._bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._bar.setFixedHeight(14)
        self._bar.setAttribute(Qt.WA_StyledBackground, True)
        self._bar.setStyleSheet(f"background-color: {Colors.BG_SURFACE}; border-radius: 4px;")
        layout.addWidget(self._bar)

        self.pct_label = QLabel("")
        self.pct_label.setFixedWidth(50)
        self.pct_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.pct_label.setStyleSheet(f"""
            color: {Colors.TEXT_SECONDARY};
            font-size: 10px; font-weight: 600;
            background: transparent;
        """)
        layout.addWidget(self.pct_label)

        self.grad_label = QLabel("")
        self.grad_label.setFixedWidth(70)
        self.grad_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.grad_label.setStyleSheet(f"""
            color: {Colors.TEXT_TERTIARY};
            font-size: 9px; font-weight: 600;
            font-family: 'IBM Plex Mono', 'Consolas', monospace;
            background: transparent;
        """)
        layout.addWidget(self.grad_label)

    def set_data(self, point_id: str, rejected_count: int, valid_count: int, rate: float,
                 max_gradient: float = None, mean_gradient: float = None):
        self._point_id = point_id
        total = rejected_count + valid_count
        self._rejected_pct = (rejected_count / total * 100) if total > 0 else 0
        self._valid_pct = (valid_count / total * 100) if total > 0 else 0
        self.id_label.setText(point_id)
        self.pct_label.setText(f"{rate:.1f}%")
        if mean_gradient is not None:
            self.grad_label.setText(f"\u2300 {mean_gradient:.4f}")
            self.grad_label.setToolTip(f"Max: {max_gradient:.6f}\nMean: {mean_gradient:.6f}")
        else:
            self.grad_label.setText("")
            self.grad_label.setToolTip("")

        self._update_bar_gradient()

    def _update_bar_gradient(self):
        """Render the bar as a single-widget gradient: rejected | kept | empty."""
        rej = self._rejected_pct / 100.0
        val = self._valid_pct / 100.0
        split = rej + val  # total filled portion (usually ~1.0)

        if split <= 0:
            self._bar.setStyleSheet(f"background-color: {Colors.BG_SURFACE}; border-radius: 4px;")
            return

        # Normalise stop positions to 0..1
        rej_stop = rej / split if split > 0 else 0
        # Build gradient: rejected color → kept color → track bg
        # Use a sharp transition via two stops at the same position
        r_end = max(0.001, min(0.999, rej_stop))

        self._bar.setStyleSheet(f"""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 {Colors.rgba(Colors.ERROR, 0.55)},
                stop:{r_end:.4f} {Colors.rgba(Colors.ERROR, 0.55)},
                stop:{r_end + 0.001:.4f} {Colors.rgba(Colors.SUCCESS, 0.35)},
                stop:1 {Colors.rgba(Colors.SUCCESS, 0.35)});
            border-radius: 4px;
        """)

    def set_selected(self, selected: bool):
        """Toggle visual highlight for selection state."""
        self._selected = selected
        if selected:
            self.setStyleSheet(f"""
                background-color: {Colors.ACCENT_GHOST};
                border-radius: 4px;
                border-left: 3px solid {Colors.ACCENT_PRIMARY};
            """)
            self.id_label.setStyleSheet(f"""
                color: {Colors.ACCENT_BRIGHT};
                font-size: 11px; font-weight: 700;
                background: transparent;
            """)
            self.pct_label.setStyleSheet(f"""
                color: {Colors.ACCENT_BRIGHT};
                font-size: 10px; font-weight: 700;
                background: transparent;
            """)
        else:
            self.setStyleSheet("background: transparent;")
            self.id_label.setStyleSheet(f"""
                color: {Colors.TEXT_PRIMARY};
                font-size: 11px; font-weight: 600;
                background: transparent;
            """)
            self.pct_label.setStyleSheet(f"""
                color: {Colors.TEXT_SECONDARY};
                font-size: 10px; font-weight: 600;
                background: transparent;
            """)

    def mousePressEvent(self, event):
        if self._point_id:
            self.clicked.emit(self._point_id)
        super().mousePressEvent(event)


class PointFrequencyBars(QWidget):
    """Per-point rejection frequency with threshold filter."""

    point_clicked = pyqtSignal(str)
    selection_changed = pyqtSignal(object)  # emits set of selected point IDs

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")

        self._freq_df: Optional[pd.DataFrame] = None
        self._threshold = 0  # minimum rejection_rate %
        self._selected_ids: set = set()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Header row
        header = QHBoxLayout()
        header.setSpacing(8)

        # Icon
        icon_lbl = QLabel()
        icon_lbl.setPixmap(icon("fa6s.location-dot", color=Colors.TEXT_TERTIARY, scale_factor=0.8).pixmap(QSize(12, 12)))
        header.addWidget(icon_lbl)

        title = QLabel("Point Rejection Frequency")
        title.setStyleSheet(f"""
            color: {Colors.TEXT_TERTIARY};
            font-size: 10px; font-weight: 700;
            text-transform: uppercase; letter-spacing: 0.7px;
            background: transparent;
        """)
        header.addWidget(title)
        header.addStretch()

        # Threshold dropdown
        self.threshold_combo = QComboBox()
        self.threshold_combo.addItems(["All", ">10%", ">20%", ">30%", ">40%", ">50%"])
        self.threshold_combo.setFixedWidth(80)
        self.threshold_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {Colors.BG_SURFACE};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 6px;
                color: {Colors.TEXT_SECONDARY};
                font-size: 10px;
                padding: 3px 8px;
                padding-right: 20px;
            }}
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: center right;
                width: 20px;
                border: none;
                background-color: transparent;
            }}
            QComboBox::down-arrow {{
                width: 8px;
                height: 8px;
                image: none;
                border-left: 3px solid transparent;
                border-right: 3px solid transparent;
                border-top: 4px solid {Colors.TEXT_MUTED};
            }}
            QComboBox::down-arrow:hover {{
                border-top-color: {Colors.ACCENT_PRIMARY};
            }}
            QComboBox QAbstractItemView {{
                background-color: {Colors.BG_ELEVATED};
                border: 1px solid {Colors.BORDER_DEFAULT};
                color: {Colors.TEXT_SECONDARY};
                selection-background-color: {Colors.ACCENT_GHOST};
            }}
        """)
        self.threshold_combo.currentIndexChanged.connect(self._on_threshold_changed)
        header.addWidget(self.threshold_combo)

        self.count_chip = QLabel("0")
        self.count_chip.setStyleSheet(f"""
            color: {Colors.TEXT_ACCENT};
            background-color: {Colors.ACCENT_GHOST};
            border: 1px solid {Colors.BORDER_ACCENT};
            border-radius: 10px;
            font-size: 10px; font-weight: 600;
            padding: 2px 8px;
        """)
        header.addWidget(self.count_chip)
        layout.addLayout(header)

        # Scrollable list — show at least 6-7 rows
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setMinimumHeight(180)
        scroll.setMaximumHeight(260)
        scroll.setStyleSheet(f"""
            QScrollArea {{ background: transparent; border: none; }}
            QScrollBar:vertical {{
                background: transparent; width: 5px;
            }}
            QScrollBar::handle:vertical {{
                background: {Colors.BG_HOVER}; border-radius: 2px; min-height: 20px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)

        self._list_container = QWidget()
        self._list_container.setStyleSheet("background: transparent;")
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(1)
        self._list_layout.addStretch()

        scroll.setWidget(self._list_container)
        layout.addWidget(scroll)

        self._row_widgets: list = []

    def _on_threshold_changed(self, index: int):
        thresholds = [0, 10, 20, 30, 40, 50]
        self._threshold = thresholds[index] if index < len(thresholds) else 0
        self._apply_filter()

    def _apply_filter(self):
        visible = 0
        total = 0
        for w in self._row_widgets:
            if not isinstance(w, _FreqRow):
                continue
            total += 1
            rate = w._rejected_pct
            show = rate >= self._threshold
            w.setVisible(show)
            if show:
                visible += 1
        if self._threshold == 0:
            self.count_chip.setText(f"{total}")
        else:
            self.count_chip.setText(f"{visible} of {total}")

    def _on_row_toggle(self, point_id: str):
        """Toggle selection of a point ID and update visuals."""
        if point_id in self._selected_ids:
            self._selected_ids.discard(point_id)
        else:
            self._selected_ids.add(point_id)

        # Update visual state for all rows
        for w in self._row_widgets:
            if isinstance(w, _FreqRow):
                w.set_selected(w._point_id in self._selected_ids)

        self.point_clicked.emit(point_id)
        self.selection_changed.emit(set(self._selected_ids))

    def clear_selection(self):
        """Clear all selected points."""
        self._selected_ids.clear()
        for w in self._row_widgets:
            if isinstance(w, _FreqRow):
                w.set_selected(False)
        self.selection_changed.emit(set())

    @property
    def selected_ids(self) -> set:
        return set(self._selected_ids)

    def update_data(self, freq_df: pd.DataFrame):
        self._freq_df = freq_df
        self._selected_ids.clear()

        # Clear existing rows
        for w in self._row_widgets:
            self._list_layout.removeWidget(w)
            w.deleteLater()
        self._row_widgets.clear()

        if freq_df is None or freq_df.empty:
            empty = QLabel("No data available")
            empty.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: 11px; background: transparent;")
            self._list_layout.insertWidget(0, empty)
            self._row_widgets.append(empty)
            self.count_chip.setText("0")
            return

        for _, row_data in freq_df.iterrows():
            row = _FreqRow()
            _max_raw = row_data.get("max_gradient")
            _mean_raw = row_data.get("mean_gradient")
            max_g = float(_max_raw) if _max_raw is not None and not (isinstance(_max_raw, float) and math.isnan(_max_raw)) else None
            mean_g = float(_mean_raw) if _mean_raw is not None and not (isinstance(_mean_raw, float) and math.isnan(_mean_raw)) else None
            row.set_data(
                point_id=str(row_data["point_id"]),
                rejected_count=int(row_data["rejected_count"]),
                valid_count=int(row_data["valid_count"]),
                rate=float(row_data["rejection_rate"]),
                max_gradient=max_g,
                mean_gradient=mean_g,
            )
            row.clicked.connect(self._on_row_toggle)
            idx = max(0, self._list_layout.count() - 1)
            self._list_layout.insertWidget(idx, row)
            self._row_widgets.append(row)

        self._apply_filter()

    def clear(self):
        for w in self._row_widgets:
            self._list_layout.removeWidget(w)
            w.deleteLater()
        self._row_widgets.clear()
        self.count_chip.setText("0")
