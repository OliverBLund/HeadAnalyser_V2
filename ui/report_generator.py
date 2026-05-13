"""
HeadAnalyser V2 - PDF Report Generator
Builds a multi-page PDF report with plots, stats, and tables.
"""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import datetime
import tempfile
from typing import Any, Callable, Dict, List

import numpy as np

from PyQt5.QtWidgets import QApplication

from ui.triangle_widgets.triangle_data_helper import TriangleDataHelper


@dataclass
class ReportSettings:
    plots: List[str]
    include_general_stats: bool
    include_gradient_stats: bool
    include_valid: bool
    include_rejected: bool
    include_rejection_analysis: bool
    dpi: int
    plot_width: float
    plot_height: float
    row_limit: str
    use_landscape: bool
    include_map: bool
    map_style: str


class PdfReportGenerator:
    def __init__(self, main_window):
        self.main_window = main_window

    def generate(
        self,
        settings: Dict[str, Any],
        file_path: str,
        progress_callback: Callable[[float, str], None] | None = None,
    ):
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4, landscape
            from reportlab.platypus import (
                SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
                Image, PageBreak
            )
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            from PyPDF2 import PdfMerger
        except Exception as exc:
            raise RuntimeError(
                "Missing PDF dependencies. Install reportlab and PyPDF2 to use report export."
            ) from exc

        s = ReportSettings(**settings)
        dataset = self.main_window.get_active_dataset()
        if dataset is None:
            raise RuntimeError("No active dataset.")

        data = self._get_active_data()
        if data is None or data.empty:
            raise RuntimeError("No data available for report.")

        # Prepare docs
        portrait_story = []
        plot_story = []
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            "ReportTitle",
            parent=styles["Heading1"],
            fontSize=22,
            spaceAfter=20,
            alignment=1,
        )
        heading_style = ParagraphStyle(
            "Heading",
            parent=styles["Heading2"],
            fontSize=14,
            spaceBefore=16,
            spaceAfter=8,
        )

        if progress_callback:
            progress_callback(0.1, "Creating document structure...")

        with tempfile.TemporaryDirectory() as tmpdir:
            portrait_path = f"{tmpdir}/portrait_temp.pdf"
            landscape_path = f"{tmpdir}/landscape_temp.pdf"

            portrait_doc = SimpleDocTemplate(
                portrait_path,
                pagesize=A4,
                rightMargin=36, leftMargin=36,
                topMargin=36, bottomMargin=36,
            )
            landscape_doc = SimpleDocTemplate(
                landscape_path,
                pagesize=landscape(A4) if s.use_landscape else A4,
                rightMargin=36, leftMargin=36,
                topMargin=36, bottomMargin=36,
            )

            # Title page
            portrait_story.append(Paragraph("Hydraulic Gradient Analysis Report", title_style))
            portrait_story.append(Spacer(1, 24))
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            portrait_story.append(Paragraph(f"Generated: {timestamp}", styles["Normal"]))
            portrait_story.append(Paragraph("Software: HeadAnalyser v2.0", styles["Normal"]))
            portrait_story.append(Spacer(1, 16))

            # Analysis parameters
            portrait_story.append(Paragraph("Analysis Parameters", heading_style))
            head_min, head_max = self._get_head_range()
            if head_min is not None and head_max is not None:
                portrait_story.append(
                    Paragraph(f"Hydraulic Head Range: {head_min:.2f} to {head_max:.2f} m", styles["Normal"])
                )
            excluded_ids = getattr(self.main_window, "excluded_ids", set())
            if excluded_ids:
                portrait_story.append(
                    Paragraph(f"Excluded Points: {len(excluded_ids)}", styles["Normal"])
                )
            portrait_story.append(Spacer(1, 8))

            # General statistics
            if s.include_general_stats:
                portrait_story.append(Paragraph("General Statistics", heading_style))
                stats_rows = self._build_general_stats()
                if stats_rows:
                    t = Table(stats_rows, colWidths=[220, 140])
                    t.setStyle(self._basic_table_style(colors))
                    portrait_story.append(t)
                    portrait_story.append(Spacer(1, 12))

            # Gradient statistics
            if s.include_gradient_stats:
                grad_rows = self._build_gradient_stats()
                if grad_rows:
                    portrait_story.append(Paragraph("Gradient Statistics", heading_style))
                    t = Table(grad_rows, colWidths=[220, 140])
                    t.setStyle(self._basic_table_style(colors))
                    portrait_story.append(t)
                    portrait_story.append(Spacer(1, 12))

            if progress_callback:
                progress_callback(0.3, "Generating plots...")

            # Plots
            plot_types = self._resolve_plot_types(s.plots)
            total_plots = max(len(plot_types), 1)
            for i, plot_type in enumerate(plot_types):
                if progress_callback:
                    progress_callback(0.3 + (0.4 * (i / total_plots)), f"Generating {plot_type} plot...")
                buf = self._render_plot(plot_type, s.dpi)
                if buf:
                    plot_story.append(Paragraph(f"{plot_type} Analysis", heading_style))
                    img = Image(buf)
                    max_w = landscape_doc.width * 0.95
                    max_h = landscape_doc.height * (0.85 if s.use_landscape else 0.75)
                    desired_w = s.plot_width * inch
                    desired_h = s.plot_height * inch
                    scale = min(max_w / desired_w, max_h / desired_h)
                    img.drawWidth = desired_w * scale
                    img.drawHeight = desired_h * scale
                    plot_story.append(img)
                    plot_story.append(PageBreak())

            # Map
            if s.include_map:
                if progress_callback:
                    progress_callback(0.7, "Generating location map...")
                map_buf = self._render_map_image(data, s.map_style)
                if map_buf:
                    plot_story.append(Paragraph("Location Map", heading_style))
                    img = Image(map_buf)
                    desired_w = s.plot_width * inch
                    desired_h = s.plot_height * inch
                    img.drawWidth = desired_w
                    img.drawHeight = desired_h
                    plot_story.append(img)
                    plot_story.append(PageBreak())
                else:
                    plot_story.append(Paragraph("Location Map (unavailable)", styles["Italic"]))
                    plot_story.append(PageBreak())

            if progress_callback:
                progress_callback(0.8, "Adding data tables...")

            # Valid results table
            if s.include_valid:
                valid_df = getattr(self.main_window, "triangle_data", None)
                if valid_df is not None and not valid_df.empty:
                    portrait_story.append(Paragraph("Valid Results", heading_style))
                    df_display = self._limit_rows(valid_df, s.row_limit).copy()
                    df_display = df_display.round(4)
                    data_rows = [df_display.columns.tolist()] + df_display.values.tolist()
                    t = Table(data_rows, repeatRows=1)
                    t.setStyle(self._data_table_style(colors, header_color="#4A6741"))
                    portrait_story.append(t)
                    if self._row_limit_active(s.row_limit) and len(valid_df) > len(df_display):
                        portrait_story.append(Spacer(1, 8))
                        portrait_story.append(Paragraph(
                            f"(Showing first {len(df_display)} of {len(valid_df)} rows)",
                            styles["Italic"],
                        ))

            # Rejected results table
            if s.include_rejected:
                rejected_df = getattr(self.main_window, "rejected_data", None)
                if rejected_df is not None and not rejected_df.empty:
                    portrait_story.append(Paragraph("Rejected Results", heading_style))
                    df_display = self._limit_rows(rejected_df, s.row_limit).copy()
                    df_display = df_display.round(4)
                    data_rows = [df_display.columns.tolist()] + df_display.values.tolist()
                    t = Table(data_rows, repeatRows=1)
                    t.setStyle(self._data_table_style(colors, header_color="#8B0000"))
                    portrait_story.append(t)
                    if self._row_limit_active(s.row_limit) and len(rejected_df) > len(df_display):
                        portrait_story.append(Spacer(1, 8))
                        portrait_story.append(Paragraph(
                            f"(Showing first {len(df_display)} of {len(rejected_df)} rows)",
                            styles["Italic"],
                        ))

            # Rejection analysis
            if s.include_rejection_analysis:
                rejected_df = getattr(self.main_window, "rejected_data", None)
                gradient_df = getattr(self.main_window, "gradient_data", None)
                if gradient_df is None or getattr(gradient_df, "empty", True):
                    gradient_df = getattr(self.main_window, "triangle_data", None)
                if rejected_df is not None and not rejected_df.empty:
                    portrait_story.append(Paragraph("Rejected Points Analysis", heading_style))
                    freq_df = TriangleDataHelper.compute_point_frequency(rejected_df, gradient_df)
                    freq_df = freq_df.head(50)
                    data_rows = [freq_df.columns.tolist()] + freq_df.values.tolist()
                    t = Table(data_rows, repeatRows=1)
                    t.setStyle(self._data_table_style(colors, header_color="#6B7280"))
                    portrait_story.append(t)

            if progress_callback:
                progress_callback(0.9, "Assembling final document...")

            # Build PDFs
            portrait_doc.build(portrait_story)
            landscape_doc.build(plot_story)

            # Merge
            merger = PdfMerger()
            merger.append(portrait_path)
            if plot_story:
                merger.append(landscape_path)
            merger.write(file_path)
            merger.close()

        if progress_callback:
            progress_callback(1.0, "Complete!")

    def _get_active_data(self):
        return self.main_window.filtered_data if self.main_window.filtered_data is not None else self.main_window.data

    def _get_head_range(self):
        try:
            head_range = self.main_window.properties_panel.head_range.get_values()
            return head_range
        except Exception:
            return None, None

    def _build_general_stats(self):
        data = self._get_active_data()
        col_map = getattr(self.main_window, "col_mapping", {}) or {}
        id_col = col_map.get("ID")
        h_col = col_map.get("hydraulic head")
        if data is None or data.empty or h_col not in data.columns:
            return []

        unique_ids = "N/A"
        if id_col and id_col in data.columns:
            unique_ids = int(data[id_col].nunique())

        mean_head = float(data[h_col].mean())
        median_head = float(data[h_col].median())
        std_head = float(data[h_col].std())

        rows = [
            ["Unique IDs", f"{unique_ids}"],
            ["Mean Hydraulic Head", f"{mean_head:.2f} m"],
            ["Median Hydraulic Head", f"{median_head:.2f} m"],
            ["Std. Dev. of Hydraulic Head", f"{std_head:.2f} m"],
        ]

        total_triangles = getattr(self.main_window, "total_triangles", None)
        if total_triangles is not None:
            used = None
            try:
                used = int(len(getattr(self.main_window, "triangle_data", []) or []))
            except Exception:
                used = None
            rows.extend([
                ["Total Triangles", f"{total_triangles}"],
                ["Triangles Rejected (Uncertainty)", f"{getattr(self.main_window, 'rejected_due_to_uncertainty', 0)}"],
                ["Triangles Rejected (Quality)", f"{getattr(self.main_window, 'rejected_due_to_triangle_quality', 0)}"],
            ])
            if used is not None:
                rows.append(["Triangles Used", f"{used}"])
        return rows

    def _build_gradient_stats(self):
        grad_df = getattr(self.main_window, "gradient_data", None)
        if grad_df is None or grad_df.empty:
            grad_df = getattr(self.main_window, "triangle_data", None)
        if grad_df is None or grad_df.empty:
            return []

        gradients = self._flatten_series(grad_df.get("gradient"))
        angles = self._flatten_series(grad_df.get("angle"))
        if gradients.size == 0 or angles.size == 0:
            return []

        avg_angle = None
        try:
            calc = getattr(self.main_window, "gradient_calculator", None)
            if calc is not None:
                avg_angle = calc.calculate_average_angle(angles)
        except Exception:
            avg_angle = None

        rows = [
            ["Average Gradient", f"{np.mean(gradients):.5f}"],
            ["Median Gradient", f"{np.median(gradients):.5f}"],
            ["Std. Dev. of Gradient", f"{np.std(gradients):.5f}"],
            ["Min Gradient", f"{np.min(gradients):.5f}"],
            ["Max Gradient", f"{np.max(gradients):.5f}"],
        ]
        if avg_angle is not None:
            rows.append(["Average Angle", f"{avg_angle:.2f} deg"])
        rows.extend([
            ["Median Angle", f"{np.median(angles):.2f} deg"],
            ["Std. Dev. of Angle", f"{np.std(angles):.2f} deg"],
            ["Min Angle", f"{np.min(angles):.2f} deg"],
            ["Max Angle", f"{np.max(angles):.2f} deg"],
        ])
        return rows

    @staticmethod
    def _flatten_series(series):
        if series is None:
            return np.array([])
        values = []
        for v in series:
            if isinstance(v, (list, tuple, np.ndarray)):
                values.extend(list(v))
            else:
                values.append(v)
        try:
            return np.array(values, dtype=float)
        except Exception:
            return np.array([])

    @staticmethod
    def _basic_table_style(colors):
        return TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("ALIGN", (0, 0), (0, -1), "LEFT"),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F5F5F5")),
            ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, colors.HexColor("#F5F5F5")]),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ])

    @staticmethod
    def _data_table_style(colors, header_color="#4A6741"):
        return TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(header_color)),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 10),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 10),
            ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F5F5F5")),
            ("TEXTCOLOR", (0, 1), (-1, -1), colors.black),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 1), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F5F5")]),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ])

    @staticmethod
    def _row_limit_active(row_limit: str) -> bool:
        return str(row_limit).lower() != "all"

    def _limit_rows(self, df, row_limit: str):
        if not self._row_limit_active(row_limit):
            return df
        try:
            return df.head(int(row_limit))
        except Exception:
            return df

    @staticmethod
    def _resolve_plot_types(selected: List[str]) -> List[str]:
        display_to_internal = {
            "2D Hydraulic Head": "2D",
            "3D Surface": "3D",
            "Gradient Vectors": "Gradient Vectors",
            "Gradient Histogram": "Histogram",
            "Rose Diagram": "Rose Diagram",
        }
        return [display_to_internal.get(p, p) for p in selected]

    def _render_plot(self, plot_type: str, dpi: int):
        dataset = self.main_window.get_active_dataset()
        if dataset is None:
            return None
        plot_page = dataset.plot_page
        display_map = {
            "2D": "2D Hydraulic Head",
            "3D": "3D Surface",
            "Gradient Vectors": "Gradient Vectors",
            "Histogram": "Gradient Histogram",
            "Rose Diagram": "Rose Diagram",
        }

        previous_display = plot_page.plot_type_combo.currentText()
        try:
            target_display = display_map.get(plot_type, previous_display)
            plot_page.plot_type_combo.setCurrentText(target_display)
            self.main_window.update_plot()
            QApplication.processEvents()
            buf = BytesIO()
            plot_page.plot_widget.canvas.fig.savefig(
                buf,
                format="png",
                dpi=dpi,
                bbox_inches="tight",
                pad_inches=0.1,
            )
            buf.seek(0)
            return buf
        finally:
            plot_page.plot_type_combo.setCurrentText(previous_display)
            self.main_window.update_plot()
            QApplication.processEvents()

    def _render_map_image(self, data, map_style: str):
        try:
            import folium
        except Exception:
            return None

        lat_col = "Latitude"
        lon_col = "Longitude"
        if lat_col not in data.columns or lon_col not in data.columns:
            return None

        lats = data[lat_col].astype(float).tolist()
        lons = data[lon_col].astype(float).tolist()
        if not lats or not lons:
            return None

        min_lat, max_lat = min(lats), max(lats)
        min_lon, max_lon = min(lons), max(lons)
        lat_padding = (max_lat - min_lat) * 0.2 if max_lat != min_lat else 0.01
        lon_padding = (max_lon - min_lon) * 0.2 if max_lon != min_lon else 0.01

        m = folium.Map(zoom_control=False, tiles=map_style)
        m.fit_bounds([
            [min_lat - lat_padding, min_lon - lon_padding],
            [max_lat + lat_padding, max_lon + lon_padding],
        ])

        for lat, lon in zip(lats, lons):
            folium.CircleMarker(
                location=[lat, lon],
                radius=5,
                color="blue",
                fill=True,
                fillOpacity=0.7,
                weight=1,
            ).add_to(m)

        # Try folium's built-in PNG export (requires selenium)
        try:
            png_data = m._to_png(5)
            if png_data:
                return BytesIO(png_data)
        except Exception:
            return None

        return None
