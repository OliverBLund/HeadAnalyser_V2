# HeadAnalyser V2 - Master Improvement Plan (4-6 Weeks)

## 1) Purpose
This document is the implementation reference for improving existing systems in HeadAnalyser V2 with a balanced focus on:
- scientific/backend robustness,
- UX and design quality,
- cross-view integration (plots, tables, statistics, quick stats, map),
- practical delivery for commercial use.

Primary constraint:
- Build on `design_concept.html` before significant new coding work.

## Progress Update (2026-02-11)
- Implemented plot toolbar redesign, sidebar redesign, plot settings dialog overhaul, and resize robustness fixes.
- Added PDF report generator scaffolding (toolbar button, settings dialog, generator; dependencies: reportlab + PyPDF2).
- 2D + contour plot merged with fill-contour toggle and contour settings refinements.
- Design-first concept HTML updates remain pending to reconcile with implemented changes.

## How To Use This Plan
1. Use this file as the execution guide for the current 4-6 week cycle.
2. Use `todo.md` for raw capture and ideation.
3. Use `MASTER_TODO_COVERAGE.md` when you need 1:1 traceability from `todo.md`.
4. Do not start implementation-heavy work until Phase 1 design sign-off is complete.

## 2) Scope and Intent
This plan prioritizes improving and integrating existing systems. It avoids open-ended feature sprawl.

In scope:
- Plot system quality and discoverability.
- Triangle diagnostics and backend transparency.
- Statistics Dashboard and Quick Stats quality.
- Table/plot/map integration workflows.
- Practical map analysis layers (not a full GIS platform).

Out of scope (for this cycle):
- Large unrelated new modules.
- Major architecture rewrites not tied to current workflows.
- Startup/welcome screen polish unless needed for release.

## 3) Product Positioning and Audience
Development audience:
- Primary: you (maintainer/owner).
- Secondary: future collaborators touching code and UI.

Operational audience:
- End users are domain practitioners using the compiled app for groundwater gradient and flow-direction investigation.

Implication:
- The plan must be implementation-ready, but also readable as a product-level decision record.

## 4) Guiding Principles
1. Design-first execution.
- UI/interaction changes are first validated in concept HTML prototypes and only then ported to Qt.

2. One diagnostics truth model.
- Avoid separate logic paths for table/statistics/plot/map diagnostics.

3. Integration before new features.
- Improve handoff and consistency between existing views before adding depth.

4. Scientific transparency.
- Users should understand what was kept/rejected and why, with traceable settings.

5. Progressive disclosure.
- Keep default UX simple; expose advanced diagnostics via details/inspectors.

## 5) Current Baseline (Known)
- Rejection diagnostics now include `reason_flags` and quality metrics for rejected triangles.
- `Primary` vs `All causes` reason modes exist.
- Table-level details popup exists on double-click.
- Export paths exist in inspector and statistics.
- `todo.md` contains broad UI/plot/stats/performance wishlist.

Gap:
- Diagnostics parity for kept triangles is not fully standardized yet.

## 6) Success Criteria for This Cycle
By end of cycle, the app should provide:
1. Coherent interaction experience across plots, table, statistics, and map.
2. Reliable diagnostics visibility for both kept and rejected triangles.
3. Better plot usability and discoverability (subtle in-plot interaction hints).
4. Improved statistical interpretability (dispersion/robustness cues).
5. Map workflows that are genuinely useful for investigation, not just display.

## 7) Execution Roadmap (4-6 Weeks)

## Phase 0 - Alignment and Lock (2-3 days)
Goals:
- Convert ideas into a locked near-term execution set.
- Establish the implementation contract for this cycle.

Deliverables:
- Scope lock from `todo.md` into three buckets:
  - `Now (this cycle)`,
  - `Next`,
  - `Later`.
- Confirm design source-of-truth files:
  - `design_concept.html`,
  - `triangle_inspector_final.html`,
  - optional map concept file.
- Define acceptance checklist template used for every feature.

Acceptance:
- No major coding starts before Phase 1 design sign-off.

## Phase 1 - Design-First Foundation (Week 1)
Goals:
- Finalize UX/visual behavior before implementation.
- Remove ambiguity in interaction design.

Work:
- Update concept HTMLs for:
  - plot toolbar/sidebar refinement,
  - subtle in-plot interaction hints,
  - triangle details behavior,
  - breakdown mode semantics,
  - map layer legend/controls.
- Define visual tokens to reuse in Qt (spacing, elevation, border contrast, chip styles).
- Define behavior matrix:
  - click, double-click, hover, keyboard shortcuts per plot type.

Deliverables:
- Concept spec section in HTML comments or companion markdown:
  - component behavior,
  - state variants,
  - error/empty/loading states.

Acceptance:
- You sign off concept behavior first; then implementation starts.

## Phase 2 - Backend Diagnostics Unification (Week 2)
Goals:
- Build a shared diagnostics data contract powering all views.

Core decision:
- Create a unified triangle diagnostics schema for both kept and rejected rows.

Required fields (minimum):
- `status`, `point_ids`, `point_row_labels`, `centroid_x`, `centroid_y`
- `gradient`, `angle`
- `reason`, `reason_flags`, `detailed_reason`
- `quality_side_lengths`, `quality_heights`, `quality_base_height_ratio`
- `quality_area`, `quality_h_range`, `quality_thresholds`
- `settings_snapshot_id` or equivalent to tie rows to calculation settings.

Work:
- Extend diagnostics calculation to kept triangles where missing.
- Ensure all diagnostics views consume the same computed source (not recomputed ad hoc).
- Add/verify export flattening for list/dict fields.

Acceptance:
- Same row-level diagnostics visible in table popup, inspector export, and downstream stats.
- `Primary` and `All causes` diverge whenever multi-cause data exists.

## Phase 3 - Integration Spine (Week 3)
Goals:
- Make cross-view analysis feel like one system.

Work:
- Selection synchronization:
  - selecting in table highlights plot/map/stat entries where applicable.
- Filter synchronization:
  - reason/status/point filters apply consistently.
- Interaction hint note in plot area:
  - subtle, plot-specific, non-intrusive guidance.
- Common legend semantics:
  - same colors/labels for reason/status across table/plot/map.

Acceptance:
- A user can move between table -> plot -> inspector -> map without losing context.
- No contradictory counts for same selection/filter context.

## Phase 4 - Plot and Statistics Upgrade (Week 4)
Goals:
- Improve usability and interpretability in main analysis views.

Plot work:
- Toolbar/side panel visual cleanup to align with concept.
- Improve compass rendering and placement.
- Address resize robustness issues.
- Ensure interaction hints are present and context-sensitive.

Statistics work:
- Improve card sizing/layout consistency.
- Add robust metrics where feasible this cycle:
  - gradient quantiles/IQR,
  - angle dispersion indicators (e.g., resultant length / circular dispersion).
- Clarify metric labels and confidence caveats.

Quick Stats work:
- Keep lightweight but consistent with full stats semantics.
- Avoid duplicate logic; source from same diagnostics model.

Acceptance:
- Plot interactions are discoverable without extra docs.
- Stats and quick stats agree with each other and with underlying data.

## Phase 5 - Map as Analysis Surface (Week 5)
Goals:
- Make map useful for diagnosis and decision support.

Minimum useful map layers:
- points (base layer),
- rejection rate / frequency layer,
- valid-triangle support (coverage quality) layer,
- optional selected-triangle/point highlight layer.

Work:
- Add map controls mirroring inspector semantics:
  - reason/status filters,
  - selection sync,
  - consistent legend/color rules.
- Ensure coordinate transform reliability and clear fallback messaging.

Acceptance:
- Map can answer at least:
  - where support is weak,
  - where rejection is high,
  - which selected points/triangles drive patterns.

## Phase 6 - Hardening and Release Buffer (Week 6, optional)
Goals:
- Stabilize and de-risk for production use.

Work:
- Performance pass on large datasets.
- Regression QA across all synchronized views.
- Export validation (CSV and plot/report outputs).
- Small UX refinements from internal testing.

Acceptance:
- No major regressions.
- Known limitations documented.
- Release candidate checklist complete.

## 8) Cross-System Integration Contracts

Data contract:
- One triangle diagnostics schema consumed by:
  - `triangle_table`,
  - `triangle_inspector`,
  - statistics dashboard,
  - quick stats,
  - map overlays.

Selection contract:
- Single selection state per dataset context.
- Views subscribe/update without conflicting ownership.

Filter contract:
- Global dataset filters (depth/head/exclusions/settings) and local view filters are explicitly separated.
- UI must show active filter state visibly.

Reason-count contract:
- `Primary`: one categorical reason row.
- `All causes`: per-flag aggregation from `reason_flags`.
- UI note always clarifies if no multi-cause rows exist.

## 9) QA and Validation Strategy

Automated tests:
- Unit tests for diagnostics field generation.
- Unit tests for primary/all-cause aggregation behavior.
- Integration tests for selection/filter sync where practical.

Manual QA scenarios:
- Load, filter, exclude, and recalc with diagnostics verified.
- Double-click table row shows matching details.
- Exports include expected diagnostics fields.
- Stats and quick stats match table totals.
- Map layers match inspector counts for same selection/filter state.

Performance checks:
- Track compute time and UI response for representative dataset sizes.
- Ensure new diagnostics do not create unacceptable slowdown.

## 10) Risks and Mitigations
Risk:
- Scope creep from many good ideas.
Mitigation:
- Strict `Now/Next/Later` locking in Phase 0.

Risk:
- Divergent logic between views.
Mitigation:
- Shared diagnostics model and contracts.

Risk:
- UI complexity overwhelm.
Mitigation:
- Progressive disclosure and subtle hints.

Risk:
- Performance cost from richer diagnostics.
Mitigation:
- Compute once, reuse everywhere, profile and optimize hotspots.

## 11) Immediate Next Actions
1. Lock `Now (this cycle)` items from `todo.md` under this plan.
2. Update `design_concept.html` and related concept HTML with signed-off behavior.
3. Start Phase 2 only after design sign-off.

## 12) Suggested `Now` Scope (Balanced)
- Keep/rejected diagnostics parity for core geometry metrics.
- Plot interaction hints overlay.
- Plot toolbar/sidebar/compass polish and resize fixes.
- Statistics/Quick Stats consistency pass + selected robust metrics.
- Map minimum analysis layers (rejection + support + selection sync).
- Export reliability and settings traceability.

## 13) Todo Traceability
Full 1:1 mapping from 	odo.md is maintained in MASTER_TODO_COVERAGE.md.

