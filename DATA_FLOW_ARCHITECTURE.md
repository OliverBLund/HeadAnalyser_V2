# HeadAnalyser V2 Data Flow Architecture

## Goal
Keep map and plot behavior consistent while integrating concept features as a plug-and-play addition to the existing code/data pathways.

This document defines canonical data paths and centralizers so new work is added in batches without introducing parallel logic.

## Canonical State Ownership
- Dataset-level source of truth: `core/dataset.py`
- Active-tab compatibility mirror: `ui/main_window.py` via:
  - `sync_from_dataset(...)`
  - `sync_to_dataset(...)`

Rule: persistent state belongs on `Dataset`; legacy fields on `MainWindow` are active-tab mirrors.

## Canonical Pipeline (Filters and Exclusions)
1. UI action updates filter/exclusion inputs.
2. `MainWindow._run_filter_pipeline(...)` (`ui/main_window.py`) is called.
3. `FileHandler.filter_data(...)` (`core/file_handler.py`) computes:
   - `filtered_plot_data` (pre-exclusion, visual contexts),
   - `filtered_data` (post-exclusion, analysis contexts).
4. MainWindow fans out updates:
   - `update_plot()`
   - `update_data_views()`
   - `properties_panel.refresh_excluded_list()`

Rule: do not call `file_handler.filter_data(...)` directly from view widgets for normal UI flows.

## Canonical Map Refresh Path
1. `MainWindow._update_map_view(...)` builds MapPayload from active `Dataset`.
2. `MapWidget.update_map(**payload)` receives payload and applies:
   - in-place fast update when payload is compatible, or
   - full rerender when needed.

Payload entrypoint remains `MapWidget.update_map(...)`; payload construction/runtime helpers are delegated to:
- `ui/map/map_payload_builder.py`
- `ui/map/map_runtime_renderer.py`
- `ui/map/map_interaction_controller.py`

## Exclusion Semantics
- `excluded_ids`: ID-level exclusion.
- `excluded_member_keys`: row-member-level exclusion for duplicate IDs (`{id}::{row_index}`).

Rule: table/plot/map interactions should update both sets when row-level precision is needed.

## Render Policy
- Prefer in-place JS updates for map-only visual changes and compatible filter/exclusion deltas.
- Full rerender is reserved for incompatible payload changes or overlays that require rebuild.
- Preserve viewport/zoom unless the map has never been fit.

## Batch Delivery Policy
- Work in explicit batches.
- Each batch should keep UI behavior faithful to concept variant where intended.
- For concept-to-production integration:
  - preserve existing visuals and interactions that already work,
  - add missing functionality through centralizers,
  - avoid introducing parallel update pathways.

## Current Centralizers (Reference)
- Filter orchestration: `ui/main_window.py` `_run_filter_pipeline(...)`
- Map payload dispatch: `ui/main_window.py` `_update_map_view(...)`
- Map render entrypoint: `ui/map_widget.py` `update_map(...)`
- Map payload helpers: `ui/map/map_payload_builder.py`
- Map runtime/render helpers: `ui/map/map_runtime_renderer.py`
- Map interaction helpers: `ui/map/map_interaction_controller.py`
- Filter computation: `core/file_handler.py` `filter_data(...)`
- Dataset sync boundary: `ui/main_window.py` `sync_from_dataset(...)` / `sync_to_dataset(...)`

## Guardrails For Future Changes
- New feature toggles should write state on `Dataset`, then trigger MainWindow centralizers.
- Avoid adding direct `update_map(...)` or `filter_data(...)` calls from leaf widgets.
- If a second path is temporarily necessary, mark it clearly and schedule consolidation in the next batch.

## Developer Flow Map
Use these as default implementation routes for new features.

- New data filter control:
  - Add UI in `ui/properties_panel.py`.
  - Emit through existing filter signal.
  - Handle in `MainWindow._run_filter_pipeline(...)`.
  - Apply filtering logic in `core/file_handler.py:filter_data(...)`.
  - Let MainWindow fan out to plot/table/map.

- New map overlay toggle or setting:
  - Persist state on `Dataset` (and synced MainWindow mirror if needed).
  - Trigger `MainWindow._update_map_view(...)` (or map visual-only helper when compatible).
  - Render through `ui/map_widget.py:update_map(...)` and delegated helpers in `ui/map/map_runtime_renderer.py` / `ui/map/map_payload_builder.py`.
  - Do not call `setHtml(...)` directly from other modules.

- New exclusion action (table/plot/map):
  - Update both exclusion sets when row precision matters:
    - `excluded_ids`
    - `excluded_member_keys` (`{id}::{row_index}` format)
  - Trigger `MainWindow.refilter_and_recalculate()`.
  - Rely on canonical filter pipeline for downstream recompute and refresh.

- New dataset-level option:
  - Add field in `core/dataset.py`.
  - Include in MainWindow sync boundary (`sync_from_dataset` / `sync_to_dataset`).
  - Apply where rendered (plot/map) via existing central update entrypoints.

- New view-side refresh trigger:
  - Prefer calling MainWindow centralizers over direct low-level updates:
    - filtering: `refilter_and_recalculate()` / `_run_filter_pipeline(...)`
    - map: `_update_map_view(...)`
    - full redraws only when fast-path compatibility is not possible
