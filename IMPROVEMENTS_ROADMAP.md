# HeadAnalyser V2 – Improvements Roadmap

This document captures agreed/planned improvements (UI, plotting, transparency, exports) so we can implement them one-by-one without losing scope.

Related: `HeadAnalyser_V2/INTERACTIVITY_SPEC.md` focuses specifically on plot interactivity; this file includes broader product work.

## 1) Triangle Counts Prominently (Total / Valid / Rejected)

**Goal:** Users always see “how much data” is used in computations.

**Status:** Partially complete (status bar + statistics panel done; properties panel pending)

**Implemented**
- Status bar: `Triangles: 30/100 valid (70 rejected)` (valid/total + rejected count).
- Status bar: compact chips for `Total / Valid / Rejected` with gray/green/red emphasis.
- Statistics panel: shows `Valid/Total` and `Rejected/Total`.

**Still to do**
- Properties panel (top “at a glance”): add a compact chip row.

**Acceptance**
- Counts update immediately when filters/exclusions/constraints change.
- Uses the *current* filtered dataset and current constraints.

## 2) More Statistics (Median/Std/etc.)

**Goal:** Provide robust summary stats (avoid over-relying on means).

**Status:** Partially complete (median + std for gradient magnitude added; more pending)

**Gradient magnitude**
- Mean, median, std (implemented)
- Min/max, quartiles (Q1/Q3), IQR (pending)
- Optionally: trimmed mean, top-N% mean (diagnostic).

**Angles**
- Unweighted circular mean (already).
- Weighted circular mean (already).
- Circular dispersion: resultant length `R`, circular std (deg), circular variance.
- Clarify convention in labels: “counterclockwise from x-axis”.

**Acceptance**
- All statistics are computed from the same triangle set (no hidden downsampling).

## 3) “Transparent Backend” / Inspector Tools

**Goal:** Make computations auditable and actionable.

**Triangle Inspector (new view/panel)**
- Table of all triangles (valid + rejected) with:
  - `point_ids`, `centroid_x/y`, `gradient`, `angle`, rejection reason + detailed reason.
  - Diagnostic columns: base/height ratios, head range, etc.
- Filter/sort/search (e.g., “show only thin_triangle”, “top 50 gradients”).
- Actions:
  - Select triangle → highlight in plots (points + centroid).
  - Exclude/include member points (E/I behavior) from inspector.
  - Export table to CSV.

**Point Inspector**
- Show stacked locations groups (same X/Y).
- Show all rows for a location and allow choosing an “active” row (future: optional for calculations).

**Acceptance**
- Inspector reflects exactly the data used by plots/stats.
- Exported CSV matches what’s shown (including current constraints).

## 4) Move “Advanced” Out of Plot Settings

**Goal:** Separate “plot appearance” from “calculation settings”.

**Status:** Completed (dedicated Calculation Settings dialog + header toolbar button; per-dataset overrides with optional apply-globally defaults)

**Plan**
- Keep existing “Settings” as plot customization.
- Add a dedicated toolbar button: **Calculation Settings** (or **Analysis Settings**).
  - Contains triangle constraints:
    - `± on head (L)` (measurement uncertainty)
    - base:height ratio min/max
    - stacked-point epsilon
    - max base/height (optional)
  - Changing any value triggers recompute using current filters/exclusions.

**Acceptance**
- No calculation knobs appear in the plot customization dialog.

**Implemented**
- New Calculation Settings dialog (separate from plot appearance settings).
- Button added to the main header toolbar.
- Per-dataset calculation settings with defaults + “Apply globally” option; changing settings recomputes using current filters/exclusions.

## 12) “Quick Stats” Drawer (Lite stats under plot)

**Goal:** Provide fast, glanceable diagnostics without switching to the full Statistics view.

**Status:** Implemented (functional) — visuals/UX still being iterated; OK to pause.

**Implemented**
- Collapsible bottom drawer under the plot with a resizable splitter.
- Quick tables: top rejected IDs + top high-gradient IDs.
- Selected-ID details + jump to Selection Inspector / Statistics.

## 5) Finish Plot Interactivity

**Already implemented**
- 2D: hover + click selection + pinned annotation; E/I exclusion; stable hover tooltips.
- 2D: hover/click on the **mean gradient arrow** to show summary tooltip; click pins/unpins; `Esc` clears.
- Gradient Vectors: hover + click selection; highlight triangle member points; E/I exclusion.
- Histogram: hover bins + click bin selects triangles in range (sets global triangle selection).
- Rose: hover wedges + click wedge selects triangles in sector (sets global triangle selection).
- Selection Inspector: double-click a histogram bin / rose wedge to open a table of triangles + points; supports A/B compare.

**Missing / next**
- Cross-plot linked selection model (persist selection when switching plot types).

## 6) PDF Export (Complete Report)

**Goal:** Bring back `Export Complete Report (PDF)` from V1.1.1, but based on V2 data model.

**Contents (suggested)**
- File metadata + column mapping + filter/constraint settings.
- Key stats: points/triangles valid/rejected + gradient summary.
- Figures: 2D plot, contour, gradient vectors, histogram, rose, rejection breakdown.
- Optional appendix: rejected triangle table summary.

**Implementation notes**
- Prefer `reportlab` (already used in V1); reuse styling and figure exports from V2.
- Ensure plots export at consistent DPI and use the “current view” state (toggles included).

## 7) Triangles Plot (All Triangles Visualizer)

**Goal:** Bring back an explicit “Triangles” plot, but make it useful.

**Features**
- Draw triangle edges (for valid triangles only by default; toggle to include rejected in gray).
- Hover/click triangle:
  - show `point_ids`, gradient, angle, reason if rejected.
  - highlight corresponding points in 2D and/or vectors plot.
- Controls: declutter (sample), show only top-N gradients, show only a rejection reason.

## 8) Branding / Footer in Properties Panel

**Goal:** Restore flavor text + DTU logo at bottom of Properties panel.

**Features**
- Small DTU logo (`DTU_logo.png`) with a short “based on … methodology” line.
- Clickable link (optional): open user manual / project doc.

## 9) Map View Overhaul

**Goal:** Make map view a real analysis surface, not just point display.

**Scope ideas**
- Points layer (included/excluded styling).
- Contours layer (raster or isolines) generated from the same interpolation as contour plot.
- Gradient arrows / centroid vectors overlay:
  - either aggregated mean arrow or sampled triangle vectors.
- Layer toggles + legend.
- Export map as HTML and/or screenshot/PDF.

**Implementation approach**
- If continuing with `folium`:
  - generate contour overlays as geo-referenced images and add as `ImageOverlay`.
  - add vector layers as `PolyLine`/`CircleMarker` with tooltip/popups.
- If moving to `plotly` later:
  - keep export quality requirements in mind (kaleido/static export).

## Suggested Implementation Order

1. Triangle counts prominently (low risk, high value). (partially complete)
2. More stats (add min/max, quartiles + circular dispersion). (partially complete)
3. Mean arrow tooltip in 2D (quick UX win). (done)
4. Separate Calculation Settings dialog from plot customization. (next)
5. Triangle Inspector (transparency foundation; powers later “compare mode”).
6. Histogram + Rose interactivity (selection propagation).
7. Triangles visualizer plot.
8. PDF complete report export.
9. Map overhaul (largest scope; do after data/selection model stabilizes).

## 10) Compare Mode (Future)

**Goal:** Compare a filtered view against baseline, or compare two datasets, without losing transparency.

**Compare targets**
- **Filtered vs full** (same dataset): baseline = raw dataset; overlay = current filtered/excluded state.
- **Dataset vs dataset** (two loaded datasets): overlay key summary metrics and/or plots.

**UX options**
- “Snapshot” baseline: capture current stats + plots into a stored record.
- Side-by-side plots: same plot type, two panels.
- Overlay plots: dual layers with style differences (alpha/color/linestyle).
- Difference view: show deltas in mean head, mean gradient, mean direction, rose shift, etc.

**Key dependencies**
- Central "selection + filtering state" model (so snapshots are reproducible).
- Export pipeline that can export side-by-side and overlay views to images/PDF.

## 11) Selection Inspector Statistics Comparison

**Goal:** When inspecting a histogram bin or rose wedge selection, show comparative statistics (not just raw triangle/point lists).

**Selection vs Global**
When any selection exists, show a comparison table:
| Metric | Selection | Global | Delta |
|--------|-----------|--------|-------|
| Count | 45 | 1,234 | - |
| Mean Gradient | 0.0052 | 0.0038 | +0.0014 |
| Median Gradient | 0.0048 | 0.0035 | +0.0013 |
| Std Dev | 0.0012 | 0.0025 | -0.0013 |
| Mean Angle | 125.3° | 98.2° | +27.1° |

This answers: *"Is this subset different from the overall dataset?"*

**A vs B Comparison**
When both A and B are set via "Set as A" / "Set as B" buttons:
| Metric | A | B | Delta (A-B) |
|--------|---|---|-------------|
| Count | 45 | 62 | -17 |
| Mean Gradient | 0.0052 | 0.0031 | +0.0021 |
| Mean Angle | 125.3° | 45.8° | +79.5° |

This answers: *"How do these two subsets differ?"* (e.g., compare North-facing vs South-facing triangles)

**Point Frequency Analysis**
Show which points appear most frequently in the selected triangles:
| Point ID | Count in Selection | % of Selection | Count in Global | % of Global |
|----------|-------------------|----------------|-----------------|-------------|
| P12 | 8 | 17.8% | 45 | 3.6% |
| P7 | 6 | 13.3% | 52 | 4.2% |
| P23 | 5 | 11.1% | 12 | 1.0% |

This answers: *"Which points dominate this subset?"* - useful for identifying if a selection is driven by specific well locations.

**Implementation notes**
- Reuse statistics computation logic from `statistics_panel.py`.
- Extract a utility function that computes gradient stats for any subset of triangle indices.
- Enhance the existing "Compare" tab in SelectionInspectorDialog (or add a "Statistics" tab).
- Keep it lightweight: focus on key gradient metrics, not full rejection analysis.
