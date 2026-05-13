## Visual polish:
Generally better .svgs for icons?
- Handle later. Copyright etc is important to consider for commercial software like this.
Lightmode and add button for toggling in header_bar.py

Header_bar.py:
- header_bar: better colors for different buttons to give a more colorful look
- gray background each groups of buttons needs to be slightly less vertical to allow for the main background to show.
- buttons: add a hover effect to make them more interactive

Properties_panel.py:
- Add the DTU logo and the text from the V1 version

Status bar along the bottom:
- fix the "white vertical line" issue

## Plots
PERHAPS UPDATE THE CONCEPT HTML WITH UPDATED PLOT AREA DESIGN WITH PLOT TOOLBAR SIDEBAR AND PLOTS ETC?
plot_page.py
- Improve the toolbar to better match the style of the design_concept.html. It needs to have more sleek and comapct buttons, b etter icons etc to match the design style and overall quality of the concept html.
- Massive improvements must also be made to the sidebar and the plot settings to better handle plot-specific options which should show up in the sidebar and also fix the terrible UI/UX of the plot settings dialog.
- In the plot_sidebar.py we have "Visualization" area and "Plot specifici options" which dont match the better design of the properties panel

Plot area itself and plots:
- Ask about how we can potentially improve the overall quality and design of the plots.
- Compass still sucks and looks terrible and formats badly.
- Plot resizing sometimes a problem.
- Improve the layout and design of the plot settings dialog to better match the overall design style and quality of the concept HTML.
- Add subtle in-plot "interaction hints" note/panel (plot-specific) so users can discover controls/interactions without clutter.

## Statistics_panel -> triangle analysis
- The KPI / pills with total, kept, rejected etc are not all the same size.
- The kept/rejected needs to look like a proper "bar". Currently it does not. Image required to explain
  - Same issue with the point rejection frequency and breakdown by reason.
- The triangles plot needs to be improved and look better. Not sure how, but difficult to really use it.
The # column needs more room when there is lots of data as it just says "1..." for most rows in the triangle table.
Attribute table:
- Does not seem to update correctly when data filters are applied?

## Startup and welcome screen (WAIT WITH THIS)
- Take inspiration from the kornsize program where we have a welcome screen, background and a startup screen.
 - startup screen / splash screen should show DTU logo and name of the program creator (ME!)

## Other things
- Loading dialog like the old variant to show progress of loading data and calculations and filtering etc. Must be resuable across different parts of the program.
- Performance considerations regarding loading large datasets and statistics dashboard for large datasets.
- MORE FOCUS ON STACKED POINTS?!

## Gradient analysis features (new ideas)
- Spatial coverage/quality overlay: show where gradients are under-supported by valid triangles.
- Sensitivity/robustness (leave-one-out/jackknife): show influence of each point on mean gradient/direction.
- Outlier diagnostics: flag triangles with extreme gradients or local-direction conflicts.
- Directional uncertainty/dispersion: report angular spread alongside mean direction.
- Triangle size awareness: filter or bin by triangle size (area/edge length) to separate local vs regional gradients.
- Confidence overlay: map rejection rate/uncertainty over the field area.
- Calculation audit trail: save/export settings used for each dataset snapshot for reproducibility.

## Integration-first brainstorm (kept + rejected)
- Expose triangle geometry metrics for kept triangles too (side lengths, heights, area, base/height ratios, head range) in the same schema as rejected triangles.
- Keep one shared "triangle diagnostics" model used by table, inspector, statistics, plot overlays, and map layers (avoid duplicate logic per view).
- Add synchronized selection across views: selecting triangles/points in one place highlights the same entities in table, plot, stats bars, and map.
- Add linked filters: reason, size bin, gradient range, direction sector, point ID; filters apply consistently across all views.
- Add "focus mode" workflow: pick a point or polygon region and see only local triangles + local summary metrics in all panels.
- Add quick comparison mode for kept vs rejected distributions (area, ratio, gradient, direction) to explain rejection behavior.
- Add uncertainty/context badges on key outputs (mean direction, mean gradient, support count) so interpretation quality is always visible.
- Add map-layer parity with inspector: reasons, coverage/support, and frequency layers share same color semantics and legends.
- Add reproducible exports: every CSV/figure export includes filter state + calculation settings snapshot.
- Add minimal "why this changed" log when filters/settings update so users can trace state transitions during investigation.
