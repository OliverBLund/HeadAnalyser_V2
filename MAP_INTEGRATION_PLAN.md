# Map Integration Plan (Phased Batches, Concept-Faithful)

## Objective
Integrate the map concept into the existing HeadAnalyser V2 pipeline in controlled batches, with explicit quality gates, while preserving a 1:1 faithful reconstruction of the concept UI.

## Implementation Status (2026-02-14)
### Completed Batches/Items
1. Phase 1 UI reconstruction is effectively complete for active map controls:
- Display settings include `Heatmap Opacity`, `Point Size`, `Show Point Labels`, `Show Scale Bar`.
- `Sync Selection with Plot` section/toggle is present.
- `Export` section/buttons are present in the UI (backend wiring intentionally deferred).
2. Rendering and interaction stability upgrades are in place:
- Layer/contour toggles now use in-place DOM updates where possible.
- Render-policy guard reduces unnecessary full HTML map rebuilds.
- Most map flash/reset regressions were removed.
3. Contour integration has moved beyond baseline parity:
- Shared contour-engine pathway with plot.
- Map contour settings dialog added and connected.
- Major-line contour labels with plot-like behavior.
4. Legend behavior improved:
- Modular legend sections follow live layer visibility.
5. Depth filter behavior improved:
- Supports both top+bottom and single-depth-source modes.
- Shows depth-source hinting and disabled state when depth data is unavailable.
6. Runtime map-load reliability hardening:
- Root-cause found for "data exists but map stays empty": large rendered HTML could fail WebEngine load (`loadFinished ok=False`).
- Mitigation applied: load rendered map from local runtime HTML file (file URL) instead of inline HTML payload.
- Added temporary diagnostics (`[map]`, `[map-js]`) to trace render-kind transitions and webview load outcomes.
7. Map architecture split completed:
- Payload construction extracted to `ui/map/map_payload_builder.py`.
- Runtime/render + JS contract extracted to `ui/map/map_runtime_renderer.py`.
- Interaction/selection routing extracted to `ui/map/map_interaction_controller.py`.
- `ui/map_widget.py` now acts primarily as orchestration and entrypoint.
8. External GIS overlay v1 implemented (shp-first):
- Load external GIS overlays from `.shp` (optional `geopandas` dependency).
- Qt External Layer Manager dialog: load/remove/clear, per-layer visibility, styling, rename.
- Legend shows per-layer entries (with style swatch), supports rename and drag-to-reorder.
- Click external features to open an attribute popup (polygons/lines; points may be limited depending on source properties).

### Current In-Progress Focus
1. External GIS overlay hardening (shp-first):
- CRS handling UX (missing/incorrect CRS), zoom-to-layer, and dependency/packaging decisions.
2. Gradient-vector styling feature track:
- better arrow readability controls and parity with vector plot intent.
3. Interaction backlog shaping track:
- shortlist high-value interactions for hydraulic-gradient decision support (lasso/box sync, vector filters, uncertainty overlays, compare mode).
4. Transect integration remains deferred for now:
- side-track development continues separately; main branch keeps only stable hooks/placeholders.
5. Heatmap behavior is currently de-prioritized:
- known filter+heatmap edge behavior intentionally deferred until feature scope is confirmed.

### Immediate Next Session Plan (2026-02-14)
1. Harden external layers (shp-first):
- decide/implement CRS handling when `.shp` has missing CRS (prompt + default)
- add "Zoom to layer" (manager + legend affordance)
- decide packaging for `.shp` loader (ship `geopandas` vs keep optional + document)
2. Implement first arrow-style slice:
- expose 2-3 runtime style presets (line width/head size/opacity)
- verify in-place updates remain stable
3. Record prioritized interaction backlog in roadmap:
- define acceptance goals for first non-transect interaction candidate
- keep contracts compatible with later transect integration

### Backlog Ideas (Map Arrows)
1. Add gradient threshold filter for vectors:
- Show only arrows above threshold.
- Show only arrows below threshold.
- Optional range mode (min-max window).
2. Keep threshold controls aligned between map layer controls and Gradient Vectors plot options.

### Explicitly Deferred
1. Transect/backend contract.
2. Export backend wiring and final export QA.

## Non-Negotiable Constraints
1. No coding outside the active batch.
2. Each batch must pass its exit criteria before the next batch starts.
3. UI reconstruction must be 1:1 faithful to concept visuals and layout.
4. Reuse existing state and data pathways before introducing new pathways.
5. Transect/backend contract remains deferred.
6. New map update calls guarded behind `if hasattr(self, 'map_widget')` to prevent regressions during development.

## 1:1 UI Fidelity Policy
1. Primary reference:
- `map_view_concept.html`
2. Integrated implementation target:
- `ui/map_resources.py` + `ui/map_widget.py` + delegated map modules under `ui/map/`
3. Fidelity rule:
- Match structure, section order, control presence, labels, and visual behavior of concept.
- Functional hooks may be added, but no visual redesign.
4. Allowed differences:
- Deferred transect functionality.
- Data-driven text replacing hardcoded concept placeholders.
5. Batch-level fidelity check:
- Compare rendered integrated map UI against concept before closing batch.

## Scope
### In Scope
1. Cross-view sync: map, plot, stats, data table, triangle table.
2. Data table row selection highlights map points.
3. Triangle table row selection highlights map triangles.
4. Filtering/exclusion/recompute updates map immediately.
5. Display settings from concept:
- Heatmap Opacity
- Point Size
- Show Point Labels
- Show Scale Bar
- Sync Selection with Plot
6. Export options from concept:
- HTML
- PNG
- GeoJSON (points first)

### Deferred
1. Transect drawing contract.
2. Geology/transect backend or online DB contract.

## Reuse Anchors (Do Not Duplicate Logic)

> **Note**: Anchors reference function/method names, not line numbers. These are stable across edits.

### Map layer and bridge (`ui/map_widget.py` + `ui/map/*`)
- `MapWidget` class — map entrypoint/orchestrator
- `MapWidget.update_map()` — core map render entrypoint (accepts data, col_mapping, excluded_ids, triangle_data, gradient_data, rejected_data)
- `MapPayloadBuilder` (`ui/map/map_payload_builder.py`) — payload construction and point-color payload refresh helpers
- `MapRuntimeRenderer` (`ui/map/map_runtime_renderer.py`) — HTML/JS contract injection + runtime overlay replacement
- `MapInteractionController` (`ui/map/map_interaction_controller.py`) — map/table selection routing and selection visuals
- `MapWidget.set_layer_visibility()` — layer toggle handler
- `MapWidget._export_map()` — export stub (currently `pass`)

### Main controller and shared state (`ui/main_window.py`)
- `MainWindow.on_page_changed()` — navigation page switch handler
- `MainWindow.update_data_views()` — refreshes all data-bound views
- `MainWindow.refilter_and_recalculate()` — central filter/exclusion + recompute path
- `MainWindow.set_triangle_selection()` — global triangle selection state
- `MainWindow.clear_triangle_selection()` — clears global triangle selection
- `MainWindow.create_new_dataset_tab()` — dataset creation with signal wiring

### Table selection pipelines (`ui/plot_page.py`)
- `PlotPage._connect_selection_sync()` — bidirectional plot↔table selection wiring
- `PlotPage._on_triangle_selection_changed()` — debounced triangle selection handler
- `PlotPage._flush_triangle_selection_overlay()` — overlay rendering logic

### Triangle data shaping (`ui/triangle_widgets/triangle_data_helper.py`)
- `TriangleDataHelper.build_combined_triangle_df()` — combines kept + rejected DataFrames
- ⚠️ Uses `pd.concat([kept, rej], ignore_index=True)` — fragile index coupling (Phase 4 fix)

### Filter/recompute pathway (`core/file_handler.py`)
- `FileHandler.filter_data()` — filters data based on depth/head ranges, triggers recompute

### Export/report reuse
- `PdfReportGenerator._render_map_image()` (`ui/report_generator.py`)
- `ReportSettingsDialog._setup_ui()` — map section (`ui/dialogs/report_generator.py`)

## Current UI Parity Gaps

### Properties Sidebar (`CONCEPT_PROPERTIES_SIDEBAR` in `map_resources.py`)

| Section | Control | Status |
|---|---|---|
| Selection | Selected Point card + stacked intake variant | ✅ Present |
| Display Settings | Heatmap Opacity slider | ✅ Present |
| Display Settings | Point Size slider | ✅ Present |
| Display Settings | Show Point Labels toggle | ✅ Present |
| Display Settings | Show Scale Bar toggle | ✅ Present |
| Sync | Sync Selection with Plot toggle | ✅ Present |
| Export | HTML / PNG / GeoJSON buttons | ✅ Present (UI), ⏳ Deferred (backend wiring) |

### Map Canvas Overlays (`CONCEPT_HTML_OVERLAYS`)
All overlays are at full concept parity: Zoom Controls, Layers Panel, Scale Bar, Legend, Coordinates, Attribution, Tooltip, Geology Panel. ✅

## Empty-State Behavior
- **No data loaded**: `_show_empty_map()` — centered on Denmark (55.68°N, 12.57°E), zoom 7.
- **All points filtered out**: Same as above.
- **No triangle/gradient data**: Map renders points only, heatmap/vectors feature groups remain empty.

## Phased Batch Plan

## Phase 0: Contract + Baseline Audit (Batch 0)
### Goal
Freeze data contracts and baseline behavior before edits.

### Tasks
1. Define one canonical map payload contract as a typed dict/dataclass in `MainWindow`:
   ```python
   MapPayload = TypedDict('MapPayload', {
       'data': pd.DataFrame,
       'col_mapping': dict,
       'excluded_ids': set,
       'triangle_data': Optional[pd.DataFrame],
       'gradient_data': Optional[pd.DataFrame],
       'rejected_data': Optional[pd.DataFrame],
   })
   ```
2. Define one canonical map event contract from `MapWidget` (signals: `pointSelected`, `transectCreated`).
3. Document current concept parity gaps (see table above — frozen).

### Exit Criteria
1. Payload contract documented in code comments or typed class.
2. Parity gap list agreed and frozen.
3. No functional edits shipped yet.

## Phase 1: 1:1 UI Reconstruction (Batch 1)
### Goal
Reconstruct concept UI sections and controls faithfully before advanced behavior.

### Tasks
1. Add to `CONCEPT_PROPERTIES_SIDEBAR` in `ui/map_resources.py`:
   - **Point Size** slider (Display Settings section)
   - **Show Scale Bar** toggle (Display Settings section)
   - **Sync** section with "Sync Selection with Plot" toggle (defaults ON)
   - **Export** section with HTML / PNG / GeoJSON buttons
2. Keep concept styling/layout intact (no redesign).
3. Keep deferred controls visibly present if needed (transect allowed as placeholder).

### Exit Criteria
1. Visual structure matches concept 1:1 (section order, labels, controls).
2. No regressions in existing map render.
3. User fidelity check signed off.

## Phase 2: Core Data Flow Wiring (Batch 2)
### Goal
Make map fully data-driven from existing state pipelines.

### Tasks
1. Replace minimal map update calls in:
   - `MainWindow.on_page_changed()` (only refresh map when navigating to map page)
   - `MainWindow.update_data_views()` (include map in standard refresh)
   with full payload-driven calls using the Phase 0 contract.
2. Route all map refreshes through centralized filter/exclusion path (`MainWindow.refilter_and_recalculate()` → `FileHandler.filter_data()`).
3. Ensure points use `filtered_plot_data`; derived layers use `filtered_data` + triangle/gradient/rejected frames.
4. Guard all new calls: `if hasattr(self, 'map_widget'):`.

### Exit Criteria
1. Filtering/exclusion instantly updates map.
2. No duplicate map-specific shadow state.
3. Dataset tab switch restores map data correctly.

## Phase 3: Interaction Sync (Batch 3)
### Goal
Integrate map interactions with existing selection/exclusion system.

### Tasks
1. Connect map signals in dataset creation flow (`MainWindow.create_new_dataset_tab()`).
2. Map point selection syncs with plot/table selection paths.
3. Honor `Sync Selection with Plot` control behavior.
4. Keep transect interaction deferred/no-op without breaking UI.

### Exit Criteria
1. Point selection is bidirectional map ↔ plot/table.
2. Sync toggle behavior is deterministic and documented.
3. No broken selection paths (even though table→map highlighting is Phase 4).

## Phase 4: Table-Driven Map Highlighting (Batch 4)
### Goal
Use existing table selection flows to render map highlights.

### Tasks
1. Data table selection → map point highlight (reuse `PlotPage._connect_selection_sync()` flow).
2. Triangle table selection → map triangle overlay (reuse/extend `PlotPage._flush_triangle_selection_overlay()` prep logic).
3. Stabilize triangle identity:
   - Replace fragile index coupling caused by `ignore_index=True` in `TriangleDataHelper.build_combined_triangle_df()`.
   - Introduce stable triangle key in combined triangle dataframe.

### Exit Criteria
1. Data row selections map-highlight correct points.
2. Triangle row selections map-highlight correct polygons.
3. Sort/filter in triangle table does not break mapping.

## Phase 5: Display Settings Behavior (Batch 5)
### Goal
Make concept display controls operational.

### Tasks
1. Wire controls:
   - Heatmap Opacity
   - Point Size
   - Show Point Labels
   - Show Scale Bar
2. Persist these settings per dataset via `_DATASET_EXTRA_OPTION_ATTRS` in `MainWindow` (in-memory, on `Dataset` object).

### Exit Criteria
1. Each control visibly affects map render.
2. Settings persist across tab switch.

## Phase 6: Export Integration (Batch 6)
### Goal
Enable concept export actions from map UI.

### Tasks
1. Implement `MapWidget._export_map()`:
   - HTML export
   - PNG export
   - GeoJSON export (points first)
2. Reuse/extend report pathway conventions from `PdfReportGenerator._render_map_image()`.

### Exit Criteria
1. All three export actions produce files.
2. Export reflects current map state (within format limits).

## Phase 7: Hardening + Performance + QA (Batch 7)
### Goal
Stabilize behavior and protect responsiveness.

### Tasks
1. Add cap/guardrails for large triangle overlay selections.
2. Ensure stale overlays clear on recompute/filter/exclusion changes.
3. Expand in-place update coverage and keep full rerender limited to structural/incompatible payload changes.
4. Run end-to-end scenario checks:
   - filter → recompute → map update
   - exclude/restore → map + table + plot sync
   - data/triangle selections → map highlights
   - export flows

### Exit Criteria
1. No stale selection overlays.
2. Acceptable responsiveness on large datasets.
3. All acceptance criteria passed.

## Batch Delivery Rules
1. Each batch ships with:
   - changed files list
   - brief behavior delta
   - explicit pass/fail against batch exit criteria
2. If a batch fails fidelity or integration criteria, fix within same batch before moving on.
3. No cross-batch scope creep.

## Verification
- **Visual fidelity**: User compares `map_view_concept.html` side-by-side with running app after each batch.
- **Functional smoke test**: Load CSV → Map view → points render → toggle layers → click point → sidebar updates.
- No automated test harness required; user performs manual verification.

## Final Acceptance Criteria
1. 1:1 concept-faithful UI reconstruction is complete.
2. Map is fully integrated into existing data and selection pathways.
3. Data and triangle tables drive map highlights reliably.
4. Filtering/exclusion/recompute always refresh map correctly.
5. Display settings and export options from concept are functional.
6. Transect remains explicit placeholder without blocking release.

## Default Behavior
1. `Sync Selection with Plot` defaults to ON.

## Immediate Next Batch Gate (Stop-and-Test)
1. Implement contour-fill colorbar integration in the map legend (map-only, no 2D regression).
2. Verify legend visibility logic for:
- Data Points ON + Excluded OFF.
- Data Points OFF + Excluded ON.
- Heatmap OFF + Contours OFF.
3. Require manual test pass before starting point value-driven styling.
