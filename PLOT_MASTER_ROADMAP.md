# Plot Master Roadmap

Single source of truth for plots: current behavior, controls, interactions, planned sub-variants, and concept alignment.

**Scope**
1. Only improve existing plots and add sub-variants.
2. New plot types only if they represent a fundamentally different analysis mode.
3. Always check current options before adding new ones.

**Reference Files**
1. Concept: `concepts/plot_area_concept_v2.html`
2. Plot code: `ui/plot_widget.py`
3. Sidebar controls: `ui/plot_sidebar.py`
4. Plot settings dialog: `ui/dialogs/plot_settings.py`
5. Interactions wiring: `ui/plot_page.py`, `ui/data_table.py`, `ui/main_window.py`

**Plot Catalog (code locations)**
1. 2D scatter + contours (primary): `ui/plot_widget.py` (`_draw_2d_plot`)
2. 3D surface: `ui/plot_widget.py` (`_draw_3d_plot`)
3. Gradient vectors: `ui/plot_widget.py` (`_draw_gradient_vectors`)
4. Histogram: `ui/plot_widget.py` (`_draw_histogram`)
5. Rose diagram: `ui/plot_widget.py` (`_draw_rose_diagram`)

**Shared Visual Spec (concept alignment)**
1. Enforce canvas, grid, spine, label, tick, and title styling through rcParams.
2. Fonts: labels in Segoe UI, ticks in monospace (Consolas or IBM Plex Mono).
3. Hide top and right spines, keep left and bottom.
4. Standard colorbar width and label/tick sizing.
5. For filled contours, colorbar should represent contour levels, not point values.

**Themes (Default / Minimal / Scientific / Publication)**
1. Toolbar selects theme via `MainWindow.current_plot_style` (set in `ui/plot_page.py`).
2. Current implementation applies themes in merged 2D via `styles/plot_styles.py`.
3. Theme application is inconsistent across 3D, Vectors, Histogram, and Rose (needs unification).
4. Planned: apply theme consistently in all plot draw paths.
5. Planned: theme controls rcParams defaults (fonts, spines, grid weight, tick styling, colorbar).

**Global Interactions (current)**
1. 2D plot point selection -> data table row highlight.
2. Data table row selection -> plot point highlight.
3. Data table multi-select -> vector plot highlight of matching triangles.
4. Histogram and rose selections -> global triangle selection + selection inspector.
5. Triangle table selection in plot drawer -> plot triangle overlay.
6. Quick stats interactions -> triangle selection and triangle inspector.

**Global Tools (planned overlays)**
1. Annotation mode.
2. Measurement tool (distance + head difference).
3. Focus region (subset analysis).
4. Side-by-side compare view (linked zoom/pan).
5. Quick export (PNG/SVG/clipboard).
6. Stacked points explode/selection UI (2D only).

**Settings Surfaces**
1. Live sidebar controls: `ui/plot_sidebar.py`
2. Advanced plot settings dialog: `ui/dialogs/plot_settings.py`
3. Legacy customization dialog (not wired): `ui/dialogs/customization.py`

**Current Priority (2026-02-12)**
1. Resume roadmap feature execution after baseline timing pass.
2. Flow lines overlay explicitly deferred (not prioritized by users right now).

**Status Snapshot (2026-02-16)**
1. Stable and active:
   - Merged 2D + contours draw path with contour-fill behavior.
   - Core plot interactions (table/plot selection sync, histogram/rose inspector wiring).
   - Stacked-point member-level selection identity and related UI/selection plumbing.
2. In progress:
   - Plot-mode routing hardening (single canonical mode contract across plot page/sidebar/widget/main window).
   - Backend closeout and regression coverage for selection/exclusion + tab/dataset isolation.
3. Experimental and isolated (must not affect default workflow):
   - Geo.dk cross-section and 3D/fence prototypes.
4. Deferred:
   - Flow lines / streamlines overlays.

**Backend Closeout Acceptance Criteria (before further plot expansion)**
1. Mode routing is canonical: one normalization contract for mode names with no duplicated ad-hoc mappings.
2. Switching plot mode, tab, filters, and recalculation never leaves stale artists or stale state.
3. Selection/exclusion behavior is deterministic for single, multi, and member-level stacked points.
4. Dataset/tab isolation is stable: no cross-tab bleed of plot type or plot options.
5. Geo.dk stable paths (map/plot trigger) are verified; experimental panels remain opt-in only.

**Remaining Roadmap Items (execution order after closeout)**
1. Theme unification across all plot types (2D/3D/Gradient/Histogram/Rose).
2. 3D upgrades: z-exag, base-plane contours, lighting, wireframe-only and point-only variants.
3. Gradient upgrades: normalize mode, rejected-display mode, mean vector toggle.
4. Histogram upgrades: kept/rejected stacking, KDE, CDF, robust binning rules.
5. Rose upgrades: axial symmetry, ring grid, resultant/circular variance stats.
6. Cross-cutting exports and caching: triangulation caching, percentile clipping, contour export/map overlay.

---

**Plot: 2D Scatter + Contours (merged)**

Current Implementation
1. Single 2D draw path with optional contour lines and optional contour fill in `ui/plot_widget.py:_draw_2d_plot`.
2. Shows included/excluded points, labels, compass, gradient arrow, and triangle overlay integration.
3. Selection + hover interactions in `ui/plot_widget.py:_install_2d_interactivity`.
4. Colorbar source switches to contour fill when fill is enabled; otherwise uses scatter values.

Current Controls (Sidebar)
1. Colormap.
2. Point size.
3. Contours toggle.
4. Fill contours toggle (nested under contours).
5. Contour levels.
6. Visualization toggles: arrows, points, labels, colorbar.

Current Controls (Plot Settings)
1. Interpolation method.
2. Arrow start X and Y.
3. Contour line width and contour label size.
4. Contour extent (%) and extrapolation mode (None/Nearest/IDW).
5. Label fonts, offsets, colors, axis labels and tick sizes.
6. Excluded points controls: show or hide, custom marker, color, opacity, size scale.
7. Engineering tick consistency toggle: sync X/Y major tick step.

Current Interactions
1. Point click -> data table highlight.
2. Shift+click toggle multi-select and Ctrl+drag box multi-select.
3. Table row or multi-row selection -> plot highlight sync.
4. Exclude/include via keyboard (`E`/`I`) or data table context menu -> recompute.
5. Triangle overlay from drawer triangle table selection.

Sub-Variants Status (2026-02-12)
1. Done: Merge 2D + contour as one plot.
2. Done: Contour fill toggle.
3. Done: Contour lines-only mode (contours on + fill off).
4. Deferred: Flow lines overlay (streamlines).
5. Done: Smart labels (declutter) with fast label-only redraw path.
6. Done (WIP/experimental): Cross-section profile tool (line draw) with optional geology strip placeholder integration.
7. Done (WIP/experimental): Triangle overlay styling (kept vs rejected).
8. Done (WIP/experimental): Stacked points explode + intake chooser panel.
9. Done (2026-02-12): Stacked selection identity upgraded to member-level (`member_key`) so duplicate `ID+XY` rows can still be chosen individually by head/depth.
10. Done (2026-02-12): Stacked panel now surfaces top/bottom depth when present and head values with higher precision (reduced over-rounding).

Controls Status (2026-02-12)
1. Done: Fill contours toggle and contour levels control.
2. Deferred: Contour method switch (griddata vs triangulation) and grid resolution.
3. Done: Label mode (Off, Smart, All, Pinned) with fast label-only redraw.
4. Done: Excluded point display controls (show or hide + optional custom marker, color, opacity, size scale).
5. Deferred: Flow line density slider.
6. In progress: Stacked points mode (Collapse/Exclude/Depth band/Choose intake).
7. In progress: Stacked points explode toggle (on click) and auto-collapse behavior.
8. Done: Optional synced X/Y major tick step for engineering-style axis consistency.
9. Done: Stable square plot shape on geospatial 2D axes.
10. Done (2026-02-12): Stacked-point exclusions now support row/member-level handling in addition to legacy ID-level exclusion.

Concept Alignment Status (2026-02-12)
1. Done: Contour fill behind scatter, contour lines above fill, scatter above lines.
2. Done: Colorbar switches to contour levels when fill is on.
3. Done: Geospatial 1:1 axes with stable square plot layout for 2D.
4. Done: Stacked points marker + count badge (`xN`).
5. In progress: Stacked intake side panel visual parity ("pill" formatting and spacing) with concept.

**Stacked Points Testing Plan (Friday, 2026-02-13)**
1. Validate duplicate `ID+XY` selection path using `tests/data/stacked_points/stacked_same_id_same_xy.csv`.
2. Validate same-XY/different-ID behavior using `tests/data/stacked_points/stacked_same_xy_diff_id.csv`.
3. Validate precision display and selection confidence using `tests/data/stacked_points/stacked_precision_heads.csv`.
4. Verify include/exclude recalculation behavior for both legacy ID-level and new member-level exclusions.

---

**Legacy Contour Debt (closed 2026-02-12)**
1. Removed legacy `_draw_contour_gradient_plot` draw path.
2. Removed legacy `"Contour & Gradient"` runtime mappings from plot widget/sidebar/settings.
3. Added load-time migration so old datasets with `"Contour & Gradient"` are normalized to `"2D"`.

---

**Plot: 3D Surface**

Current Implementation
1. Surface interpolation via griddata with optional wireframe overlay.
2. Colormap and view angles.

Current Controls (Sidebar)
1. Elevation and azimuth.
2. Colormap.
3. Visualization toggles: points and colorbar.

Current Controls (Plot Settings)
1. Surface opacity.
2. Wireframe overlay toggle.

Current Interactions
1. None beyond scroll zoom and drag rotate.

Planned Sub-Variants
1. Base-plane contours.
2. Lighting (LightSource).
3. Wireframe only mode.
4. Point-only mode for sparse data.

Planned Controls
1. Z exaggeration slider.
2. Base-plane contour toggle.
3. Lighting toggle.

Concept Alignment Notes
1. Semi-transparent panes and oriented axis labels.

---

**Plot: Gradient Vectors**

Current Implementation
1. Quiver plot on triangle centroids with colorbar.
2. Downsampling for large triangle sets.
3. Hover and click selection with inspector.
4. Geospatial square axes and optional synchronized X/Y major tick step.

Current Controls (Sidebar)
1. Arrow scale.
2. Alpha.
3. Colormap.

Current Controls (Plot Settings)
1. Scale factor.
2. Opacity.
3. Marker size.
4. Sync X/Y major tick step.

Current Interactions
1. Double-click vector -> selection inspector.
2. Histogram or rose selection overlays on vectors (if enabled).
3. Multi-select points from data table highlights vectors containing those points.

Planned Sub-Variants
1. Normalize vectors (direction emphasis).
2. Background point layer.
3. Rejected vectors display mode.
4. Mean vector toggle.
5. Optional streamlines overlay.

Planned Controls
1. Max vectors slider with downsampling strategy selector.
2. Normalize toggle.
3. Show rejected toggle.
4. Background points toggle.
5. Mean vector toggle.
6. Future note: rejected-element styling parity with 2D excluded styling, using density-aware rendering for high triangle counts.

Concept Alignment Notes
1. Add vector scale legend.

---

**Plot: Histogram (Gradient)**

Current Implementation
1. Gradient histogram with mean, median, CI overlays.
2. Click and double-click selection to drive inspector.

Current Controls (Sidebar)
1. Bin count.
2. Bar and edge colors.
3. Mean, median, CI toggles and CI level.

Current Controls (Plot Settings)
1. X label and Y label.

Current Interactions
1. Click bin -> global triangle selection.
2. Double-click bin -> selection inspector.
3. Esc clears selection.

Planned Sub-Variants
1. Kept vs rejected stacked bars.
2. KDE curve overlay.
3. CDF overlay on secondary axis.
4. Threshold highlight or clip range.

Planned Controls
1. Binning rule selector (Fixed, Freedman-Diaconis, Scott).
2. Stack kept/rejected toggle.
3. KDE toggle.
4. CDF toggle.

Concept Alignment Notes
1. Statistics overlay with labels and consistent styling.

---

**Plot: Rose Diagram**

Current Implementation
1. Directional histogram with mean and weighted mean lines.
2. Selection and inspector wiring.

Current Controls (Sidebar)
1. Bar mode (count vs gradient sum).
2. Bin count.
3. Mean and weighted mean toggles.
4. CI toggle and level.
5. Color.

Current Controls (Plot Settings)
1. Title.

Current Interactions
1. Click wedge -> global triangle selection.
2. Double-click wedge -> selection inspector.
3. Esc clears selection.

Planned Sub-Variants
1. Axial symmetry (0 to 180 deg).
2. Concentric frequency rings.
3. Mean direction arrowheads at rim.
4. Mean resultant length and circular variance display.

Planned Controls
1. Symmetry toggle.
2. Ring grid toggle.
3. Mean resultant stats toggle.

Concept Alignment Notes
1. Cardinal labels and ring grid per concept spec.

---

**Cross-Cutting Backlog**
1. Triangulation-based contours with caching.
2. Percentile color clipping toggle.
3. Smart label declutter.
4. Curated colormap list with optional custom import.
5. Standard export presets.
6. Stacked points detection and handling at data load.
7. Shared popup/tooltip system with consistent styling (plot tooltips, inspectors, quick stats).
8. Contour export + map integration (export contour lines as WKT; optional overlay on map view when available). Note: exists in old version; code can be ported.

**Stacked Points (Data Load + Calculation Handling)**
1. Detect stacked points during data load by grouping identical XY (or within `stacked_epsilon`).
2. Store a per-row `stack_group_id` + `stack_count` for UI rendering.
3. Provide a default calculation policy:
   - Exclude stacked points (safe default) or
   - Collapse to representative (mean/median/shallowest/deepest) or
   - Use user-selected intake per stack (persisted).
4. Expose stacked policy in Plot Settings (or Calculation Settings) and in 2D sidebar.
5. UI behavior:
   - Default collapsed marker with `xN` badge.
   - Click to explode into displaced intake markers.
   - Selecting an intake updates the calculation policy for that stack.

**Recommended Implementation Order**
1. Merge 2D + contour as a single plot.
2. Replace contour interpolation with triangulation.
3. Add shared visual spec defaults.
4. Add vector plot normalization and rejected modes.
5. Add histogram stacking and KDE.
6. Add rose symmetry and ring grid.
