# HeadAnalyser V2 - TODO (Next)

## Backend Closeout Focus (active)
- Goal: finish backend wiring, stability, and test coverage for plot-related workflows before further UI work.
- Constraint: new experimental features must stay isolated and never affect the stable default workflows.

### Execution order (backend-first)
- [ ] Lock and verify plot-mode routing contracts (`2D`, `3D`, `Gradient`, `Histogram`, `Rose`) in `ui/plot_widget.py` and `ui/plot_page.py` so every mode has deterministic redraw + state sync.
- [ ] Harden selection/exclusion synchronization contract between plot and data table (`ui/plot_widget.py`, `ui/data_table.py`, `ui/main_window.py`) with regression checks for single-select, multi-select, and include/exclude recalculation.
- [ ] Add/finish tests for stacked-point member-level behavior (selection identity, include/exclude, recompute) using fixtures in `tests/data/stacked_points/`.
- [ ] Verify Geo.dk transect backend plumbing end-to-end for stable paths only (map and plot trigger contracts), while keeping fence/3D experiments opt-in and isolated.
- [ ] Add parser regression checks for Geo.dk SVG variants (attribute-order differences in polygon tags) to prevent fallback-only renders from silent parsing failures.
- [ ] Perform a backend smoke matrix across dataset/tab isolation: tab switch, filter changes, recompute, plot redraw, map redraw; confirm no cross-tab state bleed.
- [ ] Capture residual technical debt as explicit follow-up tickets (not implicit TODO text) with owner + risk + file references.

### Progress Notes (2026-02-16)
- Step 1 started: canonical plot-type normalization is now centralized in `ui/plot_types.py` and wired into `ui/plot_page.py`, `ui/plot_sidebar.py`, `ui/plot_widget.py`, and `ui/main_window.py`.
- Legacy/alias handling (`Contour & Gradient`) now routes through the same normalization path used by runtime mode changes.
- Toolbar plot-type label sync now follows canonical internal mode on dataset/tab state sync.
- Step 2 started: exclusion mutation is now centralized through `MainWindow.apply_point_exclusion(...)` with backend helper `core/exclusion_state.py`.
- Member-level exclude/include now honors `member_key` semantics (avoids accidental full-ID exclusion when member-level context exists).
- Table -> plot multi-select now uses member keys (`rows_selected_member_keys`) for deterministic duplicate-ID highlighting.

## Done (recent)
- Map refactor: extracted runtime/render + interaction concerns from `ui/map_widget.py` into `ui/map/map_runtime_renderer.py` and `ui/map/map_interaction_controller.py` (including heatmap runtime/update methods).
- Map refactor: extracted payload-construction logic from `ui/map_widget.py` into `ui/map/map_payload_builder.py` and rewired `MapWidget` to delegate heatmap/vector/coverage/triangle/contour + point-color payload helpers.
- Map refactor checkpoint: `ui/map_widget.py` reduced to orchestration-focused surface; core map logic now lives in dedicated `ui/map/*` modules.
- Dataset tab strip: compact square tabs + improved close button.
- Calculation Settings moved out of plot settings and into main header toolbar (per-dataset with apply-globally defaults).
- Plot Quick Stats drawer: collapsible bottom drawer with splitter, mode switch, and Selection Inspector integration.
- Major gradient backend performance fix: vectorized triangle processing with scalar fallback (`core/gradient_calculation.py`).
- Large triangle table usability fix: lazy/incremental loading keeps Ctrl+T responsive on large datasets.
- Dataset isolation fix: per-tab filters/options now persist correctly; tab mapping and sidebar signal handling hardened.
- Regression fix: file-load/tab-switch mapping overwrite bug fixed (`KeyError` on cross-dataset tab switch).
- Stacked points (WIP/experimental): explode/select flow fixed for duplicate stacked rows.
- Stacked points: member-level identity support (`member_key`) added so duplicate `ID+XY` can still be selected separately.
- Stacked points: depth metadata now shown in intake chooser when available; head precision increased to reduce over-rounding.
- Added synthetic stacked-point QA datasets in `tests/data/stacked_points/`.
- Map render reliability fix: switched map HTML loading to file-based `QWebEngineView.load(...)` to avoid large inline HTML load failures.
- Map debug instrumentation added for render kind, payload counts, marker counts, and webview load status.
- Map state contract repaired between `ui/map_widget.py` and `ui/map_resources.py` (single layer-state source of truth path).
- External GIS layers v1 implemented (shp-first): `.shp` loader (optional `geopandas`), Qt External Layer Manager dialog, per-layer styling/visibility/rename, legend per-layer entries with rename + drag-to-reorder, and attribute popups.

## Current Startup Checklist (2026-02-14)
- Keep non-heatmap map workflows stable while feature work continues (selection sync, triangle overlay, exclusions, vectors/contours).
- Run A/B tab isolation smoke test:
- Dataset A: contours ON, custom filters, custom labels/colors.
- Dataset B: different options.
- Switch tabs repeatedly and verify no bleed.
- Run stacked-points QA with synthetic fixtures:
- `tests/data/stacked_points/stacked_same_id_same_xy.csv`
- `tests/data/stacked_points/stacked_same_xy_diff_id.csv`
- `tests/data/stacked_points/stacked_precision_heads.csv`
- Confirm exploded-point click selects distinct members, not always the same point.
- Confirm depth values (top/bottom) appear when dataset has depth columns.
- Start next feature track:
- external layers hardening (shp-first)
- gradient-arrow styling controls (map parity with vector plot intent)
- keep transect integration deferred while side-track work continues

## Agreed Execution Direction (2026-02-14)
- Priority 1: harden existing non-heatmap workflows before new complexity.
- Priority 2: harden external GIS layers (shp-first): CRS handling UX, zoom-to-layer, packaging decision, and QA on large shapefiles.
- Priority 3: ship first gradient-arrow styling slice (presets for width/head/opacity/readability).
- Priority 4: keep `Draw Transect` scoped to side-track work for now; only preserve compatibility hooks in main map UI.
- Priority 5: build interaction backlog after core stability/features land.

## Brainstorm Backlog (map interactions/features)
- Box/lasso selection on map with full table/plot/stats sync.
- Gradient vector threshold filters (above/below/range) and direction-sector filters.
- Confidence/uncertainty overlay for vectors and contour interpretation support.
- Compare mode (two datasets or two filter states side-by-side/overlaid).
- Transect profile panel integration when side-track contract is ready.

## Map Inconsistency Audit (updated 2026-02-14)
- [x] Point click -> selection card/exclude intermittent binding.
- Evidence: marker event delegation is centralized in runtime renderer (`window.__haMarkerDelegateInit`) rather than one delayed bind attempt.
- Residual risk: event behavior still depends on marker class contract (`point-marker`, `point-idx-*`).

- [x] Exclude from selection card member safety.
- Evidence: selection-card exclude now forwards `{id, idx, member_key}` and `MainWindow._on_map_exclude_requested(...)` parses `member_key`.
- Residual risk: correctness still depends on stable `member_key` propagation in point payloads.

- [ ] Heatmap + filter behavior when rejection heatmap is active (deferred).
- Evidence: observed issue remains when filtering with heatmap enabled.
- Plan: keep deferred until heatmap feature scope is confirmed.

- [ ] Point-size slider may desync in mixed DOM/Leaflet mutation paths.
- Evidence: radius application and exclusion/filter visual updates still travel through different JS paths.
- Plan: revisit only if regression appears in non-heatmap workflows.

- [ ] Major contour interval behavior remains index-based (`level_index % n`).
- Risk: user expectation can be value-interval based.

- [ ] Map UI script surface remains split (`map_resources` static JS + runtime injected JS).
- Risk: broader global JS contract increases regression surface when adding new map features.

## Map Follow-up (next session)
- Harden external layers (shp-first): CRS handling UX, zoom-to-layer, dependency/packaging decision, and QA on large shapefiles.
- Add gradient-arrow styling controls (shaft/head scaling, width/opacity presets, color options).
- Keep transect UI hooks stable but defer integration details until side-track output is ready.

## External Layers - Remaining Work (to call it "complete")

### Scope/UX decisions
- Make `.shp` the only advertised import type in the UI (keep GeoJSON support as dev-only, or remove it entirely).
- Decide whether external layers are per-dataset or global across all dataset tabs.

### Shapefile ingestion hardening
- CRS handling: if `.shp` has missing CRS, prompt for an EPSG code (offer a reasonable default, e.g. dataset CRS); if CRS looks incompatible, warn and allow override/reproject.
- Missing sidecars: show a friendly message when `.dbf`/`.shx`/`.prj` are missing.
- Optional: support zipped shapefiles (select `.zip` and unpack to temp).
- Optional: multi-select load of multiple `.shp` files in one import.

### Map integration polish
- "Zoom to layer" action (manager dialog, and optionally legend right-click).
- Legend per-layer UX: click-to-toggle visibility from the legend list (not only via manager dialog), show hidden state clearly (eye icon or strike-through), and keep reordering obvious/stable (drag handle, no accidental text editing).

### Feature inspection UX
- Popups for point layers with attributes (current point rendering may not retain full feature properties).
- Optional: include a "Copy attributes" action in the popup.

### Performance + QA
- Large shapefile performance: loading time + map interactivity, optional geometry simplification.
- QA: load `.shp` in EPSG:4326 and non-4326 CRS and verify reprojection; load `.shp` with missing CRS and verify prompt + correct placement; verify legend rename/reorder persists after map rerender triggers (e.g. toggling contours/heatmap).

## UI polish (short-term)
- Ensure consistent 1px separators between tab strip, plot toolbar, and plot canvas.
- Reduce visual noise: remove/soften harsh splitters and keep one divider style across the app.
- Standardize spacing: align left edges of plot toolbar controls and plot/sidebar headers.
- Add a dedicated secondary button style for compact toolbar actions (Export, Plot Settings, etc.).

## Plot Quick Stats (bottom drawer)
- Core UX implemented (drawer + splitter + rejected/gradient views + ID inspect).
- Next: refine visuals/spacing and finalize dataset-context vs selected-ID behavior.
- Nice-to-have later:
- Toggle "only currently selected triangles" vs "global".
- Export quick tables to CSV.

## Statistics panel (medium-term)
- Restructure layout to place cards side-by-side (2-3 columns) to reduce scrolling.
- Add more robust stats:
- Gradient: Q1/Q3/IQR, trimmed mean, top-N% mean.
- Angles: circular variance/dispersion (R), circular std (deg).
- Add by-point panels:
- Top IDs by max gradient (and by mean gradient).
- Top IDs by rejection rate.

## Transparency / Inspector tools (later)
- Triangle Inspector (valid + rejected) with filter/sort/search + CSV export.
- Point Inspector: show stacked-location groups and per-location rows.
