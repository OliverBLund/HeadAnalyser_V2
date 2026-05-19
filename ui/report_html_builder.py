"""
HeadAnalyser V2 - HTML report builder.

Builds the preview/export document used by the report sidebar. The generated
HTML is intentionally self-contained so QWebEngine can preview it and print the
same rendered document to PDF.
"""

from __future__ import annotations

import base64
import datetime
import math
from html import escape
from io import BytesIO
from typing import Any, Callable, Iterable, List

from ui.report_generator import PdfReportGenerator, ReportSettings
from ui.triangle_widgets.triangle_data_helper import TriangleDataHelper


ProgressCallback = Callable[[float, str], None]


class HeadReportHtmlBuilder:
    """Create self-contained report HTML from the active HeadAnalyser dataset."""

    def __init__(self, main_window):
        self.main_window = main_window
        self._legacy = PdfReportGenerator(main_window)

    def build(
        self,
        settings: dict[str, Any],
        progress_callback: ProgressCallback | None = None,
    ) -> str:
        s = ReportSettings(**settings)
        dataset = self.main_window.get_active_dataset()
        if dataset is None:
            raise RuntimeError("No active dataset.")

        data = self._legacy._get_active_data()
        if data is None or getattr(data, "empty", True):
            raise RuntimeError("No data available for report.")

        self._progress(progress_callback, 0.05, "Collecting report data...")
        title = (s.project_title or "").strip() or "Hydraulic Gradient Analysis Report"
        sections: list[str] = [
            self._cover_html(s, dataset, data, title),
            self._summary_html(dataset, data),
            self._analysis_parameters_html(),
        ]

        if s.include_general_stats:
            rows = self._legacy._build_general_stats()
            if rows:
                sections.append(self._section("General Statistics", self._key_value_table(rows)))

        if s.include_gradient_stats:
            rows = self._legacy._build_gradient_stats()
            if rows:
                sections.append(self._section("Gradient Statistics", self._key_value_table(rows)))

        self._progress(progress_callback, 0.25, "Rendering plots...")
        plot_sections = self._plot_sections(s, progress_callback)
        if plot_sections:
            sections.append(self._section("Plots", "".join(plot_sections), class_name="plot-section"))

        if s.include_map:
            self._progress(progress_callback, 0.65, "Rendering location map...")
            map_html = self._map_html(data, s.map_style)
            sections.append(self._section("Location Map", map_html))

        self._progress(progress_callback, 0.75, "Building result tables...")
        table_sections = self._result_table_sections(s)
        sections.extend(table_sections)

        self._progress(progress_callback, 0.95, "Finalizing preview...")
        body = "\n".join(sections)
        self._progress(progress_callback, 1.0, "Preview ready.")
        return self._document_html(title, body)

    def _progress(self, callback: ProgressCallback | None, fraction: float, message: str):
        if callback is not None:
            callback(fraction, message)

    def _document_html(self, title: str, body: str) -> str:
        return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>{escape(title)}</title>
{self._style()}
</head>
<body>
<main class="report-shell">
{body}
</main>
</body>
</html>"""

    def _style(self) -> str:
        return """
<style>
:root {
  --brand: #2563eb;
  --brand-dark: #1d4ed8;
  --brand-soft: #eaf1ff;
  --ink: #15171c;
  --muted: #5f6673;
  --faint: #8d95a3;
  --line: #d9dde5;
  --line-strong: #c7ceda;
  --paper: #ffffff;
  --wash: #f6f8fb;
  --success: #15803d;
  --danger: #b91c1c;
}
* { box-sizing: border-box; }
@page {
  size: A4;
  margin: 16mm 15mm 18mm 15mm;
}
@media print {
  body { background: white; padding: 0; }
  .report-shell { width: auto; margin: 0; box-shadow: none; }
  .report-section, .metric-grid, figure, table { break-inside: avoid; page-break-inside: avoid; }
  .page-break { break-before: page; page-break-before: always; }
}
body {
  margin: 0;
  padding: 32px;
  color: var(--ink);
  background: #e8edf5;
  font-family: "Calibri", "Segoe UI", Arial, sans-serif;
  font-size: 10.5pt;
  line-height: 1.5;
}
.report-shell {
  max-width: 880px;
  margin: 0 auto;
  padding: 0 42px 48px;
  background: var(--paper);
  box-shadow: 0 18px 50px rgba(20, 31, 50, 0.18);
  border-top: 8px solid var(--brand);
}
.cover {
  min-height: 520px;
  padding: 58px 0 42px;
  border-bottom: 1px solid var(--line);
}
.kicker {
  color: var(--brand);
  font-weight: 800;
  font-size: 9pt;
  letter-spacing: 1.4px;
  text-transform: uppercase;
  margin-bottom: 20px;
}
h1 {
  color: var(--ink);
  font-size: 31pt;
  letter-spacing: -0.8px;
  line-height: 1.05;
  margin: 0 0 12px;
}
.subtitle {
  color: var(--muted);
  font-size: 13pt;
  margin-bottom: 36px;
}
.metadata-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px 24px;
  margin: 28px 0;
}
.metadata-item {
  border-top: 1px solid var(--line);
  padding-top: 8px;
}
.metadata-key {
  color: var(--faint);
  font-size: 8pt;
  font-weight: 800;
  letter-spacing: 0.9px;
  text-transform: uppercase;
}
.metadata-value {
  color: var(--ink);
  font-weight: 700;
  margin-top: 2px;
  word-break: break-word;
}
.notes {
  margin-top: 24px;
  padding: 14px 16px;
  background: var(--wash);
  border-left: 4px solid var(--brand);
  color: var(--muted);
}
.report-section {
  padding: 28px 0 8px;
}
.report-section + .report-section {
  border-top: 1px solid var(--line);
}
h2 {
  color: var(--ink);
  font-size: 17pt;
  letter-spacing: -0.25px;
  margin: 0 0 14px;
}
h3 {
  color: var(--ink);
  font-size: 12.5pt;
  margin: 0 0 9px;
}
.section-lede {
  color: var(--muted);
  margin: -5px 0 16px;
}
.metric-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}
.metric {
  padding: 14px;
  background: var(--wash);
  border: 1px solid var(--line);
}
.metric-value {
  font-size: 18pt;
  font-weight: 800;
  color: var(--ink);
}
.metric-label {
  color: var(--faint);
  font-size: 8pt;
  font-weight: 800;
  letter-spacing: 0.7px;
  text-transform: uppercase;
}
table {
  width: 100%;
  border-collapse: collapse;
  margin: 10px 0 16px;
  font-size: 9pt;
}
th {
  background: #172033;
  color: white;
  text-align: left;
  font-weight: 800;
  padding: 7px 8px;
  border: 1px solid #172033;
}
td {
  padding: 6px 8px;
  border: 1px solid var(--line);
  vertical-align: top;
}
tbody tr:nth-child(even) td { background: #fafbfe; }
.key-table td:first-child {
  color: var(--muted);
  font-weight: 700;
  width: 46%;
}
.plot-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 18px;
}
figure {
  margin: 0 0 18px;
  padding: 12px;
  border: 1px solid var(--line);
  background: #fbfcff;
}
figure img {
  display: block;
  max-width: 100%;
  margin: 0 auto;
}
figcaption {
  margin-top: 8px;
  color: var(--muted);
  font-size: 9pt;
  font-weight: 700;
}
.warning {
  padding: 12px 14px;
  background: #fff7ed;
  border-left: 4px solid #ea580c;
  color: #9a3412;
}
.small-note {
  color: var(--faint);
  font-size: 8.5pt;
  margin-top: -6px;
}
</style>"""

    def _cover_html(self, s: ReportSettings, dataset, data, title: str) -> str:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        metadata = [
            ("Generated", timestamp),
            ("Software", "HeadAnalyser v2.0"),
            ("Dataset", getattr(dataset, "name", "Untitled")),
            ("Rows", len(data)),
        ]
        optional = [
            ("Project", s.project_number),
            ("Analyst", s.analyst),
            ("Client", s.client),
        ]
        metadata.extend((key, value) for key, value in optional if str(value or "").strip())
        metadata_html = "\n".join(
            f"""<div class="metadata-item">
  <div class="metadata-key">{escape(str(key))}</div>
  <div class="metadata-value">{escape(str(value))}</div>
</div>"""
            for key, value in metadata
        )
        notes = (s.notes or "").strip()
        notes_html = f'<div class="notes">{self._paragraph_text(notes)}</div>' if notes else ""
        return f"""<section class="cover">
  <div class="kicker">Hydraulic Head Analysis</div>
  <h1>{escape(title)}</h1>
  <div class="subtitle">Report generated from the active HeadAnalyser dataset.</div>
  <div class="metadata-grid">{metadata_html}</div>
  {notes_html}
</section>"""

    def _summary_html(self, dataset, data) -> str:
        triangle_data = getattr(self.main_window, "triangle_data", None)
        rejected_data = getattr(self.main_window, "rejected_data", None)
        valid_count = len(triangle_data) if triangle_data is not None and not getattr(triangle_data, "empty", True) else 0
        rejected_count = len(rejected_data) if rejected_data is not None and not getattr(rejected_data, "empty", True) else 0
        excluded_count = len(getattr(self.main_window, "excluded_ids", set()) or set())
        total_triangles = getattr(self.main_window, "total_triangles", None)
        total_triangles = total_triangles if total_triangles is not None else valid_count + rejected_count
        metrics = [
            ("Points", len(data)),
            ("Total Triangles", total_triangles),
            ("Valid Triangles", valid_count),
            ("Rejected", rejected_count),
            ("Excluded Points", excluded_count),
        ]
        metric_html = "\n".join(
            f"""<div class="metric">
  <div class="metric-value">{escape(str(value))}</div>
  <div class="metric-label">{escape(label)}</div>
</div>"""
            for label, value in metrics
        )
        return self._section(
            "Dataset Summary",
            f'<p class="section-lede">Current state of the active dataset after filtering and exclusion rules.</p><div class="metric-grid">{metric_html}</div>',
        )

    def _analysis_parameters_html(self) -> str:
        rows: list[list[str]] = []
        head_min, head_max = self._legacy._get_head_range()
        if head_min is not None and head_max is not None:
            rows.append(["Hydraulic Head Range", f"{head_min:.2f} to {head_max:.2f} m"])
        excluded_ids = getattr(self.main_window, "excluded_ids", set()) or set()
        rows.append(["Excluded Points", str(len(excluded_ids))])
        constraints = [
            ("Head Uncertainty", "gradient_head_uncertainty"),
            ("Base/Height Low", "gradient_base_height_low"),
            ("Base/Height High", "gradient_base_height_high"),
            ("Stacked Epsilon", "gradient_stacked_epsilon"),
        ]
        for label, attr in constraints:
            value = getattr(self.main_window, attr, None)
            if value is not None:
                rows.append([label, self._format_value(value)])
        if not rows:
            rows.append(["Parameters", "No active calculation parameters were available."])
        return self._section("Analysis Parameters", self._key_value_table(rows))

    def _plot_sections(self, s: ReportSettings, progress_callback: ProgressCallback | None) -> list[str]:
        plot_types = self._legacy._resolve_plot_types(s.plots)
        if not plot_types:
            return ['<div class="warning">No plots selected.</div>']

        parts: list[str] = ['<div class="plot-grid">']
        total = max(len(plot_types), 1)
        for index, plot_type in enumerate(plot_types):
            self._progress(
                progress_callback,
                0.25 + (0.35 * (index / total)),
                f"Rendering {plot_type} plot...",
            )
            try:
                buf = self._legacy._render_plot(plot_type, s.dpi)
            except Exception as exc:
                parts.append(
                    f'<div class="warning">Could not render {escape(plot_type)}: {escape(str(exc))}</div>'
                )
                continue
            if buf is None:
                parts.append(f'<div class="warning">{escape(plot_type)} plot unavailable.</div>')
                continue
            image_uri = self._image_data_uri(buf)
            parts.append(
                f"""<figure>
  <img src="{image_uri}" alt="{escape(plot_type)} plot">
  <figcaption>{escape(plot_type)} analysis</figcaption>
</figure>"""
            )
        parts.append("</div>")
        return parts

    def _map_html(self, data, map_style: str) -> str:
        try:
            buf = self._legacy._render_map_image(data, map_style)
        except Exception as exc:
            return f'<div class="warning">Location map could not be rendered: {escape(str(exc))}</div>'
        if buf is None:
            return '<div class="warning">Location map unavailable. Check coordinate columns and optional map rendering dependencies.</div>'
        return f"""<figure>
  <img src="{self._image_data_uri(buf)}" alt="Location map">
  <figcaption>Location map ({escape(map_style)})</figcaption>
</figure>"""

    def _result_table_sections(self, s: ReportSettings) -> list[str]:
        sections: list[str] = []
        if s.include_valid:
            valid_df = getattr(self.main_window, "triangle_data", None)
            if valid_df is not None and not getattr(valid_df, "empty", True):
                sections.append(self._dataframe_section("Valid Results", valid_df, s.row_limit))
        if s.include_rejected:
            rejected_df = getattr(self.main_window, "rejected_data", None)
            if rejected_df is not None and not getattr(rejected_df, "empty", True):
                sections.append(self._dataframe_section("Rejected Results", rejected_df, s.row_limit))
        if s.include_rejection_analysis:
            rejected_df = getattr(self.main_window, "rejected_data", None)
            gradient_df = getattr(self.main_window, "gradient_data", None)
            if gradient_df is None or getattr(gradient_df, "empty", True):
                gradient_df = getattr(self.main_window, "triangle_data", None)
            if rejected_df is not None and not getattr(rejected_df, "empty", True):
                freq_df = TriangleDataHelper.compute_point_frequency(rejected_df, gradient_df).head(50)
                sections.append(self._dataframe_section("Rejected Points Analysis", freq_df, "All"))
        return sections

    def _dataframe_section(self, title: str, df, row_limit: str) -> str:
        display_df = self._legacy._limit_rows(df, row_limit).copy()
        try:
            display_df = display_df.round(4)
        except Exception:
            pass
        note = ""
        if self._legacy._row_limit_active(row_limit) and len(df) > len(display_df):
            note = f'<p class="small-note">Showing first {len(display_df)} of {len(df)} rows.</p>'
        return self._section(title, self._dataframe_table(display_df) + note)

    def _dataframe_table(self, df) -> str:
        headers = "".join(f"<th>{escape(str(col))}</th>" for col in list(df.columns))
        body_rows = []
        for _, row in df.iterrows():
            cells = "".join(f"<td>{escape(self._format_value(value))}</td>" for value in row.tolist())
            body_rows.append(f"<tr>{cells}</tr>")
        body = "\n".join(body_rows) if body_rows else '<tr><td colspan="99">No rows.</td></tr>'
        return f"<table><thead><tr>{headers}</tr></thead><tbody>{body}</tbody></table>"

    def _key_value_table(self, rows: Iterable[Iterable[Any]]) -> str:
        body = "\n".join(
            f"<tr><td>{escape(str(key))}</td><td>{escape(self._format_value(value))}</td></tr>"
            for key, value in rows
        )
        return f'<table class="key-table"><tbody>{body}</tbody></table>'

    def _section(self, title: str, inner_html: str, class_name: str = "") -> str:
        cls = f"report-section {class_name}".strip()
        return f"""<section class="{cls}">
  <h2>{escape(title)}</h2>
  {inner_html}
</section>"""

    def _paragraph_text(self, text: str) -> str:
        return "<br>".join(escape(line) for line in str(text).splitlines())

    def _image_data_uri(self, buf: BytesIO) -> str:
        buf.seek(0)
        encoded = base64.b64encode(buf.read()).decode("ascii")
        return f"data:image/png;base64,{encoded}"

    def _format_value(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, float):
            if math.isnan(value) or math.isinf(value):
                return ""
            return f"{value:.6g}"
        if hasattr(value, "item"):
            try:
                return self._format_value(value.item())
            except Exception:
                pass
        if isinstance(value, (list, tuple)):
            return ", ".join(self._format_value(item) for item in value)
        return str(value)
