"""
Triangle Inspector Dialog - composing all triangle analysis widgets.
Two-column layout with hover sync between table and geometry plot.

Modernized with FontAwesome icons.
"""

from __future__ import annotations

from typing import Dict, Optional, Set

import numpy as np
import pandas as pd
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QPushButton, QSizePolicy,
    QSplitter, QVBoxLayout, QWidget, QFrame, QFileDialog, QMessageBox,
)

from styles.colors import Colors
from ui.icons import icon, Icons
from ui.triangle_widgets.triangle_data_helper import TriangleDataHelper
from ui.triangle_widgets.summary_cards import TriangleSummaryCards
from ui.triangle_widgets.breakdown_bars import RejectionBreakdownBars
from ui.triangle_widgets.point_frequency import PointFrequencyBars
from ui.triangle_widgets.triangle_table import TriangleTableWidget
from ui.triangle_widgets.geometry_plot import TriangleGeometryPlot
from qt_chrome import FramelessDialogMixin


def _danger_text() -> str:
    return Colors.ERROR_LIGHT if Colors.is_dark() else Colors.ERROR_DARK


class TriangleInspectorDialog(FramelessDialogMixin, QDialog):
    """Full triangle inspector popup composing all analysis widgets."""

    def __init__(self, main_window, parent=None):
        super().__init__(parent or main_window)
        self.main_window = main_window
        self.setWindowTitle("Triangle Inspector")
        self.resize(1120, 720)
        self.setMinimumSize(800, 500)
        self.init_frameless_dialog_chrome(
            default_windows="frameless",
            default_other="native",
            resize_margin=10,
            top_resize_margin=10,
        )

        self._combined_df: Optional[pd.DataFrame] = None
        self._selected_ids: Set[str] = set()

        self._setup_ui()
        self._setup_style()
        self.bind_frameless_drag_widget(self._chrome_header)

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        header = QWidget()
        header.setObjectName("inspHeader")
        header.setFixedHeight(60)
        self._chrome_header = header
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 0, 20, 0)
        header_layout.setSpacing(14)

        # Icon box with FontAwesome
        icon_box = QWidget()
        icon_box.setFixedSize(38, 38)
        icon_box.setStyleSheet(f"""
            background-color: {Colors.ACCENT_GHOST};
            border: 1px solid {Colors.BORDER_ACCENT};
            border-radius: 10px;
        """)
        icon_lbl = QLabel()
        icon_lbl.setPixmap(icon("fa6s.draw-polygon", color=Colors.ACCENT_PRIMARY, scale_factor=1.1).pixmap(QSize(20, 20)))
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_box_layout = QVBoxLayout(icon_box)
        icon_box_layout.setContentsMargins(0, 0, 0, 0)
        icon_box_layout.addWidget(icon_lbl)
        header_layout.addWidget(icon_box)

        # Title block
        title_block = QVBoxLayout()
        title_block.setSpacing(2)
        self._title = QLabel("Triangle Inspector")
        self._title.setStyleSheet(f"""
            color: {Colors.TEXT_PRIMARY};
            font-size: 16px;
            font-weight: 700;
            letter-spacing: -0.2px;
            background: transparent;
        """)
        title_block.addWidget(self._title)
        self._subtitle = QLabel("Full dataset analysis")
        self._subtitle.setStyleSheet(f"color: {Colors.TEXT_TERTIARY}; font-size: 12px; background: transparent;")
        title_block.addWidget(self._subtitle)
        header_layout.addLayout(title_block)
        header_layout.addStretch()

        # Selection chip — compact dot + count
        self._selection_chip = QLabel("")
        self._selection_chip.setFixedHeight(22)
        self._selection_chip.setStyleSheet(f"""
            color: {Colors.TEXT_ACCENT};
            background-color: {Colors.ACCENT_GHOST};
            border: 1px solid {Colors.BORDER_ACCENT};
            border-radius: 11px;
            font-size: 11px; font-weight: 600;
            padding: 0px 10px;
        """)
        self._selection_chip.setVisible(False)
        header_layout.addWidget(self._selection_chip)

        # Close button
        close_btn = QPushButton("×")
        close_btn.setObjectName("close_btn")
        close_btn.setFixedSize(32, 32)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self.close)
        close_btn.setToolTip("Close")
        header_layout.addWidget(close_btn)
        root.addWidget(header)

        # Summary row
        self.summary_cards = TriangleSummaryCards()
        summary_wrap = QWidget()
        summary_wrap.setObjectName("inspSummaryWrap")
        sw_layout = QHBoxLayout(summary_wrap)
        sw_layout.setContentsMargins(20, 12, 20, 12)
        sw_layout.addWidget(self.summary_cards)
        root.addWidget(summary_wrap)

        # Separator
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background-color: {Colors.BORDER_SUBTLE}; border: none;")
        root.addWidget(sep)

        # Body: two-column layout
        body_splitter = QSplitter(Qt.Horizontal)
        body_splitter.setHandleWidth(1)
        body_splitter.setChildrenCollapsible(False)

        # Left column: geometry plot + frequency
        left = QWidget()
        left.setMinimumWidth(360)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(16, 12, 8, 12)
        left_layout.setSpacing(12)

        self.geometry_plot = TriangleGeometryPlot()
        left_layout.addWidget(self.geometry_plot, 3)

        self.frequency_bars = PointFrequencyBars()
        self.frequency_bars.point_clicked.connect(self._on_point_clicked)
        left_layout.addWidget(self.frequency_bars)

        body_splitter.addWidget(left)

        # Right column: triangle table
        right = QWidget()
        right.setMinimumWidth(380)
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(8, 12, 16, 12)
        right_layout.setSpacing(8)

        # Table header with icon
        table_header = QHBoxLayout()
        table_header.setSpacing(8)

        table_icon_lbl = QLabel()
        table_icon_lbl.setPixmap(icon(Icons.TABLE, color=Colors.TEXT_TERTIARY, scale_factor=0.8).pixmap(QSize(12, 12)))
        table_header.addWidget(table_icon_lbl)

        table_title = QLabel("TRIANGLE TABLE")
        table_title.setStyleSheet(f"""
            color: {Colors.TEXT_TERTIARY};
            font-size: 10px; font-weight: 700;
            text-transform: uppercase; letter-spacing: 0.7px;
            background: transparent;
        """)
        table_header.addWidget(table_title)
        table_header.addStretch()

        right_layout.addLayout(table_header)

        self.triangle_table = TriangleTableWidget()
        self.triangle_table.triangle_hovered.connect(self._on_table_hover)
        self.triangle_table.filter_changed.connect(self.geometry_plot.set_filter_mode)
        right_layout.addWidget(self.triangle_table, 1)

        self.breakdown_bars = RejectionBreakdownBars()
        right_layout.addWidget(self.breakdown_bars)

        body_splitter.addWidget(right)
        body_splitter.setSizes([420, 680])

        root.addWidget(body_splitter, 1)

        # Footer
        footer = QWidget()
        footer.setObjectName("inspFooter")
        footer.setFixedHeight(48)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(20, 0, 20, 0)
        footer_layout.setSpacing(12)

        # Hint with icon
        hint_icon = QLabel()
        hint_icon.setPixmap(icon(Icons.INFO, color=Colors.TEXT_MUTED, scale_factor=0.8).pixmap(QSize(12, 12)))
        footer_layout.addWidget(hint_icon)

        hint = QLabel("Click rows to highlight triangles on the plot")
        hint.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: 11px; background: transparent;")
        footer_layout.addWidget(hint)
        footer_layout.addStretch()

        # Export button with icon
        self._export_btn = QPushButton()
        self._export_btn.setText(" Export CSV")
        self._export_btn.setIcon(icon(Icons.EXPORT, color=Colors.TEXT_SECONDARY))
        self._export_btn.setIconSize(QSize(14, 14))
        self._export_btn.setCursor(Qt.PointingHandCursor)
        self._export_btn.setObjectName("btn_secondary")
        self._export_btn.clicked.connect(self._export_csv)
        footer_layout.addWidget(self._export_btn)

        # Close button
        close_footer_btn = QPushButton("Close")
        close_footer_btn.setCursor(Qt.PointingHandCursor)
        close_footer_btn.setObjectName("btn_secondary")
        close_footer_btn.clicked.connect(self.close)
        footer_layout.addWidget(close_footer_btn)

        root.addWidget(footer)

    def _setup_style(self):
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {Colors.BG_MODAL};
            }}
            QWidget#inspHeader {{
                background: {Colors.GRADIENT_HEADER};
                border-bottom: 1px solid {Colors.BORDER_ACCENT};
            }}
            QWidget#inspSummaryWrap {{
                background-color: {Colors.BG_MODAL};
            }}
            QWidget#inspFooter {{
                background: {Colors.BG_SURFACE};
                border-top: 1px solid {Colors.BORDER_SUBTLE};
            }}
            QSplitter::handle {{
                background-color: {Colors.BORDER_SUBTLE};
            }}

            /* Close button */
            #close_btn {{
                background: transparent;
                border: 1px solid transparent;
                border-radius: 8px;
                color: {Colors.TEXT_TERTIARY};
                font-size: 24px;
                font-weight: 400;
                padding: 0;
            }}
            #close_btn:hover {{
                background: {Colors.rgba(Colors.ERROR, 0.15)};
                border-color: {Colors.rgba(Colors.ERROR, 0.30)};
                color: {_danger_text()};
            }}
            #close_btn:pressed {{
                background: {Colors.rgba(Colors.ERROR, 0.25)};
            }}

            /* Secondary buttons */
            #btn_secondary {{
                background: {Colors.GRADIENT_BUTTON};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 8px;
                color: {Colors.TEXT_SECONDARY};
                font-size: 12px; font-weight: 600;
                padding: 7px 16px;
            }}
            #btn_secondary:hover {{
                border-color: {Colors.ACCENT_PRIMARY};
                color: {Colors.TEXT_PRIMARY};
                background: {Colors.GRADIENT_SURFACE};
            }}
        """)

    def _on_table_hover(self, row_idx: int):
        self.geometry_plot.highlight_triangle(row_idx)

    def _on_point_clicked(self, point_id: str):
        pass  # Could filter or highlight in future

    def _export_csv(self):
        if self._combined_df is None or self._combined_df.empty:
            QMessageBox.information(self, "No Data", "No triangle data available to export.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Triangle Data", "triangle_data.csv", "CSV Files (*.csv)"
        )
        if path:
            try:
                export_df = self._combined_df.copy()
                # Flatten complex columns for CSV.
                for col in export_df.columns:
                    export_df[col] = export_df[col].apply(
                        lambda v: ", ".join(str(x) for x in v)
                        if isinstance(v, (list, tuple, np.ndarray))
                        else (str(v) if isinstance(v, dict) else v)
                    )
                export_df.to_csv(path, index=False)
                QMessageBox.information(self, "Export Complete", f"Triangle data exported to:\n{path}")
            except Exception as exc:
                QMessageBox.critical(self, "Export Failed", f"Could not export triangle data.\n\n{exc}")

    def update_for_selection(
        self,
        selected_point_ids: Optional[Set[str]],
        triangle_data: Optional[pd.DataFrame],
        rejected_data: Optional[pd.DataFrame],
        gradient_data: Optional[pd.DataFrame],
        filtered_data: Optional[pd.DataFrame],
        col_mapping: Dict[str, Optional[str]],
        total_triangles: Optional[int],
    ):
        self._selected_ids = selected_point_ids or set()

        # Filter if we have a point selection
        if self._selected_ids:
            tri_data, rej_data = TriangleDataHelper.filter_by_point_ids(
                triangle_data, rejected_data, self._selected_ids
            )
            n = len(self._selected_ids)
            self._subtitle.setText(f"Triangles involving selected points")
            self._selection_chip.setText(f"\u00b7 {n} point{'s' if n != 1 else ''} selected")
            self._selection_chip.setVisible(True)
        else:
            tri_data, rej_data = triangle_data, rejected_data
            self._subtitle.setText("Full dataset analysis")
            self._selection_chip.setVisible(False)

        # Compute data
        summary = TriangleDataHelper.compute_summary(tri_data, rej_data, total_triangles)
        self.summary_cards.update_data(summary)

        breakdown = TriangleDataHelper.compute_reason_breakdown(rej_data)
        breakdown_all = TriangleDataHelper.compute_reason_breakdown(rej_data, mode="all")
        self.breakdown_bars.update_data(breakdown, breakdown_all)

        freq_df = TriangleDataHelper.compute_point_frequency(rej_data, gradient_data)
        self.frequency_bars.update_data(freq_df)

        combined_df = TriangleDataHelper.build_combined_triangle_df(tri_data, rej_data)
        self._combined_df = combined_df
        self.triangle_table.update_data(combined_df)

        heatmap_df = TriangleDataHelper.compute_heatmap_data(freq_df, filtered_data, col_mapping)
        self.geometry_plot.update_data(
            combined_df, filtered_data, col_mapping, heatmap_df,
            selected_ids=self._selected_ids or None,
        )

    def update_for_full_dataset(
        self,
        triangle_data: Optional[pd.DataFrame],
        rejected_data: Optional[pd.DataFrame],
        gradient_data: Optional[pd.DataFrame],
        filtered_data: Optional[pd.DataFrame],
        col_mapping: Dict[str, Optional[str]],
        total_triangles: Optional[int],
    ):
        self.update_for_selection(
            None, triangle_data, rejected_data, gradient_data,
            filtered_data, col_mapping, total_triangles,
        )
