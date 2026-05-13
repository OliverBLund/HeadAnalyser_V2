# Plot Interactivity & Actions (V2 Status Spec)

Last updated: February 17, 2026

This document reflects current code behavior and planned gaps for plot interactivity in HeadAnalyser V2.

## Status Legend

- `Implemented`: behavior exists and is wired in current UI flow.
- `Partial`: behavior exists but with scope limits, edge cases, or missing cross-view sync.
- `Planned`: desired behavior not implemented yet.

## Guiding Principles

- Backend truth first: interactivity must not change computation unless explicitly applied (for example `Exclude selected points`).
- No hidden analysis downsampling: any rendering downsampling must remain visualization-only.
- Family-based consistency: interaction should be consistent within plot families, not forced identical across all plot types.
- Export fidelity: exports should match current visual state.
- Keyboard + mouse parity where practical.

## Interaction Families

### Spatial Family (`2D`, `Gradient Vectors`, `3D`)

Primary entities: points and triangles in XY space.

Current intent:
- Data table selection should directly highlight spatial entities.
- Point/triangle focus should be immediate and visual.
- `Esc` should clear spatial selection state.

### Distribution Family (`Histogram`, `Rose`)

Primary entities: triangle subsets from bins/sectors.

Current intent:
- Bin/sector interaction selects triangle subsets globally.
- Distribution views are subset selectors, not direct point-picking surfaces.
- `Esc` should clear distribution subset selection.

## Global Cross-Plot Interactions

### Linked Selection

- Triangle subset selection from Histogram/Rose to Gradient Vectors: `Implemented`.
- Triangle subset selection to Selection Inspector: `Implemented`.
- Point selection persistence across all plot switches: `Partial`.
- Triangle selection persistence within dataset: `Implemented`.

### Selection UI

- Quick Stats drawer under plot: `Implemented` (interim panel).
- Full persistent selection panel (counts + actions + exports): `Partial`.

### Keyboard Shortcuts

- `Esc`: clear selection in key contexts: `Implemented` (including Data/Triangles table deselect).
- `E` / `I`: include/exclude in interactive spatial contexts: `Implemented`.
- `C`: copy selection stats: `Planned`.
- `R`: reset current plot view: `Partial` (context-dependent).

### Context Menu on Plot Area

- Right-click plot context menu with overlays/export/reset: `Planned`.

### Export Options

- Export current view: `Implemented` (existing export flow).
- Export selected-only view/data from plot UI: `Partial`.
- Format matrix `PNG/SVG/PDF` with consistent options: `Partial`.

## Plot-Specific Status

## Plot: 2D (Scatter + Optional Contours + Mean Arrow)

Status: `Implemented` (core) / `Partial` (advanced selection tools)

Implemented:
- Point hover tooltip.
- Click selection + pinned annotation behavior.
- `Esc` clear and `E`/`I` actions.
- Mean arrow hover/click summary interactions.
- Data table to plot point highlight sync.

Partial / Planned:
- Box/lasso selection UX refinement.
- Selection-summary panel actions for large multi-select workflows.

## Plot: Contour & Gradient

Status: `Partial`

Implemented:
- Contour rendering/toggles exist in current plotting pipeline.

Planned:
- Cursor probe with interpolated head + nearest point.
- Persistent probe list.
- Interactive cross-section probe line from contour view.

## Plot: 3D

Status: `Partial`

Implemented:
- 3D plotting and navigation controls exist.

Partial / Planned:
- Rich hover/click point labeling parity with 2D.
- Preset camera views (`Publication` / `Analysis`).

## Plot: Gradient Vectors (Triangle Vectors)

Status: `Implemented` (core) / `Partial` (advanced controls)

Implemented:
- Vector hover (magnitude, angle, centroid, member IDs).
- Vector click selection and inspector handoff.
- Table-driven point/member selection highlighting in vectors.
- `Esc` deselection and `E`/`I` include/exclude flow.

Partial / Planned:
- Dedicated min/max gradient sliders on-plot.
- Top-N and declutter controls in final UX form.
- Additional colormap/colorbar controls surfaced in unified way.

## Plot: Histogram (Gradient Magnitude)

Status: `Implemented` (core + brush) / `Partial` (UX polish)

Implemented:
- Hover bin range/count/percent.
- Click bin selects triangle subset globally.
- Double-click opens Selection Inspector.

Partial / Planned:
- Full normalization/log-scale UX polishing.

## Plot: Rose Diagram (Direction)

Status: `Implemented` (core) / `Partial` (mode extensions)

Implemented:
- Hover wedge details.
- Click wedge selects triangle subset globally.
- Double-click opens Selection Inspector.

Partial / Planned:
- Mean-line direct interaction polish.
- Additional mode controls and 180-degree mirror behavior.

## Compare Mode (Future)

Status: `Planned`

Deferred targets:
- Filtered vs full (same dataset) comparison.
- Dataset vs dataset comparison.
- Overlay/difference export workflows.

## Immediate Next Spec Tasks

1. Lock exact behavior matrix for `Esc`, click, and deselect by plot family.
2. Define source-of-truth mapping rules for `point IDs` vs `member keys` in all selection paths.
3. Add acceptance checks for table <-> plot synchronization regressions.

## Behavior Matrix (Acceptance Baseline)

This matrix is the current acceptance baseline for interactivity work.
Any new change should preserve this behavior unless the spec is explicitly updated.

### Spatial Family (`2D`, `Gradient Vectors`, `3D`)

#### `2D`

- Point click on plot: select point, show visual focus, emit point selection.
- Empty click on plot: clear point focus (and pinned annotation if present).
- `Esc` in plot: clear point selection/focus.
- Data table single row select: highlight corresponding point in plot.
- Data table multi-select: highlight all selected points.
- Data table `Esc`: clear table selection and clear plot point highlights.

#### `Gradient Vectors`

- Vector hover: show vector metadata tooltip.
- Vector click: focus selected vector and show vector annotation.
- `Esc` in plot: clear focused vector state.
- Data table single row select: highlight vectors containing that selected member/ID.
- Data table multi-select: highlight union of vectors containing selected members/IDs.
- Data table `Esc`: clear vector highlights and focused vector state.
- Matching precedence for table-driven vector highlight:
  1. member-key exact match (`ID::row`) when `point_row_labels` are available
  2. plain ID match fallback when member labels are unavailable

#### `3D`

- Current baseline: preserve camera/navigation behavior and avoid breaking table-driven point targeting.
- Planned enhancement: explicit hover/click selection parity with `2D`.

### Distribution Family (`Histogram`, `Rose`)

#### `Histogram`

- Bin hover: show range/count/percent.
- Bin click: set global triangle subset selection (source=`histogram`).
- Bin double-click: open Selection Inspector.
- `Esc` in plot: clear selected bin and clear global triangle subset selection.

#### `Rose`

- Wedge hover: show sector details.
- Wedge click: set global triangle subset selection (source=`rose`).
- Wedge double-click: open Selection Inspector.
- `Esc` in plot: clear selected wedge and clear global triangle subset selection.

### Table Behavior

#### Data Table

- Row selection emits:
  - first selected `ID` (backward compatibility)
  - full selected IDs list
  - selected member keys list (`ID::row`)
- `Esc` must emit explicit deselection signals even for programmatic clear paths.

#### Triangles Table

- Row selection emits selected triangle table rows for overlay rendering.
- Global triangle selection should map only to canonical kept-triangle IDs.
- `Esc` clears table selection and emits deselection (`triangle_selected([])`).

### Cross-View Mapping Rules

- Point entity identity:
  - Canonical for row-precise operations: `member_key = ID::row_index`
  - Canonical for aggregate/legacy operations: plain `ID`
- Triangle identity:
  - Canonical for global triangle subset selection: `triangle_index` (kept triangles)
  - Table source row index may be used only as local UI selection index in combined tables.

### Regression Checklist (Minimum Manual Pass)

Run after each interactivity change:

1. `2D`: Data table single select highlights one point.
2. `2D`: Data table multi-select highlights multiple points.
3. `2D`: Data table `Esc` clears plot highlights.
4. `Gradient Vectors`: Data table single select highlights matching vectors only.
5. `Gradient Vectors`: Data table multi-select highlights union of matching vectors.
6. `Gradient Vectors`: Data table `Esc` clears vector highlights/focus.
7. `Histogram`: click bin highlights subset in vectors; `Esc` clears subset.
8. `Rose`: click wedge highlights subset in vectors; `Esc` clears subset.
9. Triangles table `Esc`: clears triangle overlay immediately.
10. Resize with open sidebar + open drawer: no overlap/clipping.

## Session Progress (February 17, 2026)

### Implemented Today

- Histogram interactivity hardened:
  - click bin selection
  - drag-brush multi-bin range selection
  - `Esc` clear behavior
  - deterministic press/release handling to reduce wonky toggles
- Histogram inspector flow improved:
  - double-click opens inspector for current active selection
  - `Enter`/`Return` opens inspector for current active selection
- Popup system upgraded with shared formatting/style helpers and applied to:
  - `2D`
  - `Gradient Vectors`
  - `Histogram`
  - `Rose`

### Known Gaps / Verify Tomorrow

- Run manual UX verification for histogram click/drag/double-click/Enter behavior in live UI.
- Confirm popup readability/placement near plot edges and under zoom/pan.
- Confirm no regressions in table-driven sync (`Data`/`Triangles` to plots).

### Suggested Next Step

- If histogram interaction still feels ambiguous, add an explicit `Inspect Selection` control in the histogram UI for zero-ambiguity access to inspector.
