# HeadAnalyser V2 - Execution Roadmap (Scope-Locked)

> Phase 0 scope lock completed 2026-02-11.
> No implementation coding starts before W1 design sign-off.
> Every change must trace to one item here AND one item in MASTER_TODO_COVERAGE.md.

## Progress Update (2026-02-14)
- NOW-14: Plot toolbar redesign implemented (`ui/plot_page.py`).
- NOW-15: Plot sidebar + plot-specific options redesign implemented (`ui/plot_sidebar.py`).
- NOW-18: Plot resizing robustness fix implemented (`ui/plot_widget.py`).
- NOW-19: Plot settings dialog overhaul implemented (`ui/dialogs/plot_settings.py`).
- 2D + contour plot merged with fill-contour toggle and contour settings refinements.
- Added PDF report generator scaffolding (toolbar button + dialog + generator). Not yet reflected in scope tables.
- 2026-02-12 blocker resolved: severe app lag traced to specific frameless modal dialog patterns (not plot stack).
- Mitigation applied: keep heavy forms native (`column_mapping`, `calculation_settings`), harden dialog lifecycle cleanup, and document frameless performance caveats in `qt_chrome/README.md`.
- 2026-02-12 major backend speedup: triangle gradient calculation path vectorized in `core/gradient_calculation.py` with scalar fallback and perf toggles.
- 2026-02-12 table responsiveness improvements: large-triangle table incremental loading restored smooth interaction on 200k+ rows.
- 2026-02-12 dataset isolation hardening: fixed cross-tab state leakage for filters and plot options (including contours) via per-dataset state sync, deterministic tab mapping, and sidebar signal-blocking during programmatic updates.
- 2026-02-12 regression fixes completed: repaired column-mapping overwrite and tab-switch `KeyError` caused by dataset sync ordering during file loads.
- 2026-02-12 stacked-points reliability fixes: member-level stacked identity (`member_key`) implemented to support duplicate `ID+XY` rows with different head/depth values.
- 2026-02-12 stacked-points UX/data fixes: depth metadata now shown when available, exploded-point hit testing hardened, and head display precision increased to reduce over-rounding confusion.
- 2026-02-12 test assets added: synthetic stacked-point fixtures under `tests/data/stacked_points/` for repeatable QA.
- 2026-02-13 map recovery milestone: resolved "data payload exists but map stays empty" by changing map webview loading to runtime file URL (avoids large inline HTML load failures in Qt WebEngine).
- 2026-02-13 map state-contract hardening: layer/legend/overlay sync moved toward a shared state path with additional runtime diagnostics.
- 2026-02-14 map architecture split completed: payload/runtime/interaction concerns moved from `ui/map_widget.py` into `ui/map/map_payload_builder.py`, `ui/map/map_runtime_renderer.py`, and `ui/map/map_interaction_controller.py`.
- 2026-02-14 heatmap decision: heatmap behavior remains available but is currently de-prioritized due known filter+heatmap edge behavior.
- 2026-02-14 external GIS layers v1 implemented (shp-first): `.shp` loader (optional `geopandas`), Qt manager dialog, per-layer legend entries with rename + reorder, and attribute popups.

## Next Session Focus (starting 2026-02-14)
1. Harden external GIS layers (shp-first): CRS handling UX + zoom-to-layer + packaging decision for `.shp` loader.
2. Improve gradient-arrow styling controls (readability presets + parity intent with vector plot).
3. Keep `Draw Transect` integration deferred while side-track implementation evolves separately.
4. Keep non-heatmap map workflows stable while feature additions land (selection sync, triangle overlay, exclusions, contours/vectors).
5. Keep heatmap work deferred until product decision confirms it should stay in active scope.
6. Capture and prioritize interaction backlog for hydraulic-gradient workflows:
   - map lasso/box sync,
   - vector threshold/direction filters,
   - uncertainty overlays,
   - compare mode.

## Performance Optimization Roadmap (2026-02-12)
1. Dataset switch latency: implemented table rebind skip when DataFrame object is unchanged.
2. Attribute table contract (`raw` vs `filtered`): still pending final UX decision.
3. Large triangle table mode: implemented lazy/incremental row loading and large-mode safeguards.
4. Gradient recalculation reuse: implemented strong speedup in backend triangle processing (vectorized path + fallback).
5. End-to-end instrumentation: active and useful (`[perf]` logging for load/filter/refresh/gradient paths).
6. Next bottleneck target: plot redraw/tick/label work in Matplotlib canvas interaction paths.
7. Future architecture: centralize per-dataset derived analysis cache (Ctrl+T triangles, Statistics, Inspector, exports) with strict version/invalidation keys.

---

## Now (This Cycle, W1-W6)

### W1 - Design-First Gate (design + bug fixes only)

| # | Item | Owner | Acceptance Criterion | COVERAGE ref |
|---|------|-------|---------------------|--------------|
| 1a | Update concept HTML: plot area, toolbar, sidebar, interaction hints | claude | Concept HTML shows finalized plot toolbar layout, sidebar options, and interaction hints with behavior documented in HTML comments | Plots #1 |
| 1b | Conceptualize plots: publication-quality visuals per plot type, merge 2D+contour, brainstorm new features/interactivity | claude | Concept HTML with finalized per-type plot designs (2D, Contour, 3D, Vectors, Histogram, Rose), merged 2D/contour option, and feature/interactivity brainstorm documented | Plots #1 |
| 2 | Define behavior matrix (click/dblclick/hover/keyboard per plot type) | claude | Markdown or HTML comment table specifying every interaction per plot type exists in concept file | (Phase 1 deliverable) |
| 3 | Define visual tokens for Qt (spacing, elevation, border, chip styles) | claude | Token list with exact pixel/color values documented for Qt port | (Phase 1 deliverable) |
| 4 | Fix status bar white vertical line (bug fix) | claude | No white vertical line artifact visible in status bar on Windows | Visual polish #6 |
| 5 | Fix table `#` column width on large datasets (bug fix) | claude | Row numbers are fully visible (not truncated to "1...") with 1000+ rows | Stats panel #5 |

### W2 - Backend Diagnostics Unification

| # | Item | Owner | Acceptance Criterion | COVERAGE ref |
|---|------|-------|---------------------|--------------|
| 6 | Kept-triangle geometry diagnostics parity | claude | Kept triangles expose side_lengths, heights, area, base_height_ratio, head_range in same schema as rejected | Integration #1 |
| 7 | Shared diagnostics model across all views | claude | Table, inspector, stats, quick stats, and map consume the same computed diagnostics source (no ad-hoc recomputation) | Integration #2 |
| 8 | Calculation audit trail (settings snapshots) | claude | Every diagnostics row carries a settings_snapshot_id; exports include the settings used | Gradient analysis #7 |
| 9 | Directional uncertainty/dispersion metric | claude | Angular spread metric (e.g. resultant length or circular std dev) is computed and available to stats views | Gradient analysis #4 |
| 10 | Attribute table sync after filtering | claude | Applying data filters updates the attribute table correctly without stale rows | Stats panel #6 |

### W3 - Integration Spine

| # | Item | Owner | Acceptance Criterion | COVERAGE ref |
|---|------|-------|---------------------|--------------|
| 11 | Synchronized cross-view selection | claude | Selecting a triangle/point in the table highlights it in plot, map, and stats; and vice versa | Integration #3 |
| 12 | Linked filters across views | claude | Reason/status/point filters set in one view apply consistently to all other views | Integration #4 |
| 13 | Map/inspector legend and semantic parity | claude | Map layers and inspector use identical color coding and legend labels for reasons/status | Integration #8 |

### W4 - Plot + Stats Upgrades

| # | Item | Owner | Acceptance Criterion | COVERAGE ref |
|---|------|-------|---------------------|--------------|
| 14 | Plot toolbar redesign (compact, high-quality controls) | claude | Toolbar matches concept HTML style; buttons are compact, icons are clean | Plots #2 |
| 15 | Plot sidebar + plot-specific options redesign | claude | Sidebar shows plot-specific options matching properties panel design quality | Plots #3 |
| 16 | Improve overall plot design quality | claude | Plots have consistent styling, proper spacing, clean axes/labels matching concept | Plots #4 |
| 17 | Compass redesign/fix | claude | Compass renders correctly at all window sizes with clean visual design | Plots #5 |
| 18 | Plot resizing robustness | claude | Resizing the window does not break plot layout, cut off labels, or cause rendering artifacts | Plots #6 |
| 19 | Plot settings dialog design/UX overhaul | claude | Settings dialog matches overall app design quality; controls are logically grouped | Plots #7 |
| 20 | In-plot interaction hints | claude | Each plot type shows a subtle, non-intrusive hint about available interactions (hover/click/etc.) | Plots #8 |
| 21 | KPI pills consistent size | claude | Total/kept/rejected metric cards are all identical width regardless of content | Stats panel #1 |
| 22 | Kept/rejected bar quality | claude | Kept/rejected proportional bar renders as a proper filled bar, not just colored text | Stats panel #2 |
| 23 | Point rejection frequency + breakdown bar quality | claude | Frequency and breakdown bars have clean fill, labels, and proportional rendering | Stats panel #3 |
| 24 | Triangle geometry plot improvement | claude | Geometry plot is legible, zoomable, and provides useful visual information about mesh structure | Stats panel #4 |
| 25 | Header color improvements | claude | Header button groups have distinct, harmonious colors matching the warm-indigo theme | Visual polish #2 |
| 26 | Header button-group background proportion | claude | Button group backgrounds are proportioned to show main background between groups | Visual polish #3 |
| 27 | Header button hover effects | claude | Buttons show smooth, visible hover state transitions | Visual polish #4 |
| 28 | Stacked points diagnostics visibility | claude | Stacked/duplicate points are flagged visibly in diagnostics and relevant stats views | Other #3 (Now portion) |

### W5 - Map Analysis Layers

| # | Item | Owner | Acceptance Criterion | COVERAGE ref |
|---|------|-------|---------------------|--------------|
| 29 | Spatial coverage/quality overlay (map layer) | claude | Map shows a layer indicating where gradient support from valid triangles is weak | Gradient analysis #1 |
| 30 | Reproducible exports with state/settings | claude | CSV and figure exports include active filter state and calculation settings snapshot | Integration #9 |
| 31 | Performance profiling + obvious fixes | claude | Profiling run on representative large dataset completed; any >2x hotspots fixed | Other #2 (Now portion) |

### W6 - Hardening Buffer

| # | Item | Owner | Acceptance Criterion | COVERAGE ref |
|---|------|-------|---------------------|--------------|
| 32 | Regression QA across synchronized views | claude | All manual QA scenarios from MASTER_IMPROVEMENT_PLAN.md section 9 pass | (Phase 6) |
| 33 | Export validation (CSV + plot outputs) | claude | Exports produce valid CSV with all diagnostics fields; plot exports render correctly | (Phase 6) |
| 34 | Small UX refinements from testing | claude | Any UX issues found during W1-W5 testing are resolved or documented as known limitations | (Phase 6) |

---

## Next (After This Cycle)

| # | Item | COVERAGE ref |
|---|------|--------------|
| N1 | Light mode + header toggle | Visual polish #2 |
| N2 | Add DTU logo/text from V1 in properties panel | Visual polish #5 |
| N3 | Reusable loading/progress dialog | Other #1 |
| N4 | Performance deep work (beyond obvious fixes) | Other #2 (Next portion) |
| N5 | Stacked points workflow improvements | Other #3 (Next portion) |
| N6 | Sensitivity/robustness (leave-one-out/jackknife) | Gradient analysis #2 |
| N7 | Outlier diagnostics | Gradient analysis #3 |
| N8 | Triangle size awareness (area/edge bins/filters) | Gradient analysis #5 |
| N9 | Confidence overlay | Gradient analysis #6 |
| N10 | Focus mode (point/region local analysis) | Integration #5 |
| N11 | Kept vs rejected comparison distributions | Integration #6 |
| N12 | Uncertainty/context badges on key outputs | Integration #7 |
| N13 | Minimal "why changed" state-transition log | Integration #10 |
| N14 | Map view layer controls and legend concept HTML | Integration #8 |

---

## Later (Not Scheduled)

| # | Item | COVERAGE ref |
|---|------|--------------|
| L1 | Better .svg icons (copyright sourcing needed) | Visual polish #1 |
| L2 | Welcome/startup screen (Kornsize-inspired) | Startup #1 |
| L3 | Splash screen with DTU logo + creator name | Startup #2 |

---

## Design Source-of-Truth Files
- `design_concept.html` - Main app layout and component design (approved, root)
- `concepts/triangle_inspector_final.html` - Triangle inspector dialog behavior
- `concepts/triangle_dashboard_concept.html` - Dashboard/statistics panel concept
- `concepts/` folder - All concept files consolidated here

## Scope Freeze Rules
1. No new items enter "Now" without removing an equal-effort item.
2. "Next" items can be promoted only at weekly review.
3. Bug fixes discovered during implementation are allowed without scope change.
4. Every PR/commit message must reference the item number from this roadmap (e.g. "NOW-14: Plot toolbar redesign").
