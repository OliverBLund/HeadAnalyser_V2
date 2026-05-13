
"""
Resources for Map Widget styling and HTML structure (Concept).
"""

import re

from styles.colors import Colors


CONCEPT_PROPERTIES_SIDEBAR = """
<!-- Properties Sidebar (Left) -->
<aside class="properties">
  <div class="properties-header">
    <div class="properties-title">Map Properties</div>
    <div class="properties-subtitle">Selection & Settings</div>
  </div>

  <div class="properties-body">
    <!-- Selected Point / Stacked Intake Selection -->
    <div class="section-header">
      <span class="section-header-text">Selection</span>
      <div class="section-header-line"></div>
    </div>

    <!-- Active Selection Card -->
    <div class="selection-card">
      <div class="selection-card-header">
        <span class="selection-id" id="prop-id">-</span>
        <span class="selection-badge neutral" id="prop-badge">None</span>
      </div>

      <!-- Stacked Intake List (Dynamic) -->
      <div class="intake-list" id="intakeList">
          <div class="note" style="margin:0;">No point selected.</div>
      </div>

      <div class="selection-actions" style="border-top:none; padding-top:4px;">
        <button class="selection-btn" id="showInPlotBtn" onclick="showSelectedInPlot()">Show in Plot</button>
        <button class="selection-btn danger" id="excludeSelectedBtn" onclick="excludeSelectedPoint()">Exclude</button>
      </div>

      <div class="note">
        Selection determines which intake is used for gradient analysis.
      </div>
    </div>

    <!-- Layer Settings -->
    <div class="section-header">
      <span class="section-header-text">Display Settings</span>
      <div class="section-header-line"></div>
    </div>

    <div class="layer-setting" id="opacitySlider">
      <div class="layer-setting-header">
        <span class="layer-setting-label">Heatmap Opacity</span>
        <span class="layer-setting-value" id="opacityValue">50%</span>
      </div>
      <div class="slider-track">
        <div class="slider-fill" style="left: 0; width: 50%;"></div>
        <div class="slider-thumb" style="left: 50%;"></div>
        <input id="opacityRange" class="slider-native" type="range" min="0" max="100" step="1" value="50"
               oninput="__mapOnOpacityInput(this.value)" />
      </div>
    </div>
    <div class="layer-setting">
      <div class="layer-setting-header">
        <span class="layer-setting-label">Heatmap Mode</span>
      </div>
      <div class="heatmap-mode-toggle" id="heatmapModeToggle">
        <button class="mode-btn active" data-mode="smooth" onclick="setHeatmapMode('smooth', this)">Smooth</button>
        <button class="mode-btn" data-mode="hex" onclick="setHeatmapMode('hex', this)">Hex</button>
      </div>
    </div>
    <div class="layer-setting" id="pointSizeSlider">
      <div class="layer-setting-header">
        <span class="layer-setting-label">Point Size</span>
        <span class="layer-setting-value" id="pointSizeValue">8px</span>
      </div>
      <div class="slider-track">
        <div class="slider-fill" style="left: 0; width: 50%;"></div>
        <div class="slider-thumb" style="left: 50%;"></div>
        <input id="pointSizeRange" class="slider-native" type="range" min="2" max="32" step="1" value="8"
               oninput="__mapOnPointSizeInput(this.value)"
               onchange="__mapCommitPointSize(this.value)" />
      </div>
    </div>

    <div class="toggle-row">
      <span class="toggle-label">Show Point Labels</span>
      <div class="toggle-switch" id="labelsToggle" onclick="togglePointLabels(this)">
        <div class="toggle-knob"></div>
      </div>
    </div>

    <div class="toggle-row">
      <span class="toggle-label">Color Points by Head</span>
      <div class="toggle-switch" id="pointColorToggle" onclick="togglePointColorByValue(this)">
        <div class="toggle-knob"></div>
      </div>
    </div>

    <div class="toggle-row">
      <span class="toggle-label">Show Scale Bar</span>
      <div class="toggle-switch on" id="scaleBarToggle" onclick="toggleScaleBar(this)">
        <div class="toggle-knob"></div>
      </div>
    </div>

    <div class="section-header">
      <span class="section-header-text">Contours</span>
      <div class="section-header-line"></div>
    </div>

    <div class="toggle-row">
      <span class="toggle-label">Show Contour Labels</span>
      <div class="toggle-switch on" id="contourLabelsToggle" onclick="toggleContourLabels(this)">
        <div class="toggle-knob"></div>
      </div>
    </div>

    <div class="layer-setting" id="contourMajorSlider">
      <div class="layer-setting-header">
        <span class="layer-setting-label">Major Line Interval</span>
        <span class="layer-setting-value" id="contourMajorValue">2</span>
      </div>
      <div class="slider-track">
        <div class="slider-fill" style="left: 0; width: 14%;"></div>
        <div class="slider-thumb" style="left: 14%;"></div>
        <input id="contourMajorRange" class="slider-native" type="range" min="1" max="8" step="1" value="2"
               oninput="__mapOnContourMajorInput(this.value)"
               onchange="__mapCommitContourMajor(this.value)" />
      </div>
    </div>

    <div class="layer-setting">
      <div class="layer-setting-header">
        <span class="layer-setting-label">Label Precision</span>
      </div>
      <select id="contourPrecisionSelect" class="plot-select" onchange="setContourLabelPrecision(this.value)">
        <option value="0">0 decimals</option>
        <option value="1">1 decimal</option>
        <option value="2" selected>2 decimals</option>
        <option value="3">3 decimals</option>
      </select>
    </div>

    <div class="note" id="contourConfigInfo" style="margin-top:6px;">
      Method -, Levels -, Extent -, Extrapolation -
    </div>
    <div style="margin-top:8px;">
      <button class="selection-btn" onclick="if(window.pyBridge) window.pyBridge.onContourSettingsRequested()">Contour Settings...</button>
    </div>

    <div class="section-header">
      <span class="section-header-text">External Layers</span>
      <div class="section-header-line"></div>
    </div>

    <div class="external-layer-summary">
      <div class="external-layer-summary-top">
        <span class="external-layer-summary-count" id="propExternalLayerCount">0 loaded (0 visible)</span>
        <button class="layer-manage-btn" onclick="if(window.pyBridge && window.pyBridge.onOpenExternalLayerManagerRequested) window.pyBridge.onOpenExternalLayerManagerRequested()">Open Manager</button>
      </div>
      <div class="external-layer-summary-note" id="propExternalLayerNote">
        No external layers loaded.
      </div>
    </div>

    <!-- Sync -->
    <div class="section-header">
      <span class="section-header-text">Sync</span>
      <div class="section-header-line"></div>
    </div>

    <div class="toggle-row">
      <span class="toggle-label">Sync Selection with Plot</span>
      <div class="toggle-switch on" id="syncToggle" onclick="toggleSync(this)">
        <div class="toggle-knob"></div>
      </div>
    </div>

    <!-- Export -->
    <div class="section-header">
      <span class="section-header-text">Export</span>
      <div class="section-header-line"></div>
    </div>

    <div class="export-options">
      <button class="export-btn" onclick="if(window.pyBridge) window.pyBridge.onExportRequested('html')">
        <svg viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
        Export as HTML
      </button>
      <button class="export-btn" onclick="if(window.pyBridge) window.pyBridge.onExportRequested('png')">
        <svg viewBox="0 0 24 24"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
        Export as PNG
      </button>
      <button class="export-btn" onclick="if(window.pyBridge) window.pyBridge.onExportRequested('geojson')">
        <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z"/></svg>
        Export as GeoJSON
      </button>
    </div>
  </div>
</aside>
"""

_CONCEPT_CSS_TEMPLATE = """
/* ═══════════════════════════════════════════
   CSS CUSTOM PROPERTIES — WARM DARK THEME (TEAL)
   ═══════════════════════════════════════════ */
:root {
  /* Accent: Program Blue */
  --accent: #60a5fa;
  --accent-dim: #3b82f6;
  --accent-glow: rgba(96, 165, 250, 0.18);
  --accent-ghost: rgba(96, 165, 250, 0.10);
  --accent-text: #60a5fa;
  --accent-border: rgba(96, 165, 250, 0.30);

  /* Warm Backgrounds */
  --bg-deepest: #0f0f12;
  --bg-base: #141418;
  --bg-panel: #1a1a1f;
  --bg-surface: #212127;
  --bg-elevated: #28282f;
  --bg-hover: #2f2f37;
  --bg-well: rgba(255, 255, 255, 0.025);

  /* Borders */
  --border-subtle: rgba(255, 255, 255, 0.04);
  --border-default: rgba(255, 255, 255, 0.07);
  --border-medium: rgba(255, 255, 255, 0.10);
  --border-strong: rgba(255, 255, 255, 0.14);

  /* Text */
  --text-primary: #ececf0;
  --text-secondary: #a8a8b3;
  --text-tertiary: #6e6e7a;
  --text-muted: #4a4a55;

  /* Nav icon colors */
  --icon-plot: #60a5fa;
  --icon-map: #4ade80;
  --icon-stats: #fbbf24;

  /* Status */
  --success: #4ade80;
  --warning: #fbbf24;
  --error: #f87171;
  --info: #60a5fa;

  /* Map layer colors */
  --layer-points: #60a5fa;
  --layer-excluded: #6e6e7a;
  --layer-external: #22c55e;
  --layer-rejection: #f87171;
  --layer-coverage: #4ade80;
  --layer-contours: #a78bfa;
  --layer-vectors: #fbbf24;
  --layer-selection: #60a5fa;
  --layer-transect: #f472b6;

  /* Geology layer colors */
  --geo-sand: #d4b483;
  --geo-clay: #9a7b6f;
  --geo-till: #7f9aa3;
  --geo-limestone: #b7bfd1;

  /* Radius */
  --r-sm: 6px;
  --r-md: 8px;
  --r-lg: 10px;
  --r-xl: 12px;
  --r-2xl: 16px;
  --r-pill: 100px;

  /* Shadows */
  --shadow-sm: 0 1px 2px rgba(0,0,0,0.2), 0 1px 3px rgba(0,0,0,0.1);
  --shadow-md: 0 2px 8px rgba(0,0,0,0.25), 0 1px 3px rgba(0,0,0,0.15);
  --shadow-lg: 0 4px 16px rgba(0,0,0,0.3), 0 2px 6px rgba(0,0,0,0.2);

  /* Transition */
  --ease: cubic-bezier(0.4, 0, 0.2, 1);
  --duration: 150ms;
}

body {
  font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
  background: var(--bg-deepest);
  color: var(--text-primary);
  margin: 0;
  padding: 0;
  overflow: hidden;
  -webkit-font-smoothing: antialiased;
}

/* Hide default Leaflet controls if we replace them */
.leaflet-control-zoom { display: none !important; }
.leaflet-control-attribution { display: none !important; }
.leaflet-control-layers { display: none !important; }

/* PROPERTIES SIDEBAR (Left) */
.properties {
  position: absolute;
  top: 0; bottom: 0; left: 0;
  width: 280px; min-width: 280px;
  background: var(--bg-panel);
  border-right: 1px solid var(--border-default); /* Right border instead of left */
  display: flex; flex-direction: column; overflow: hidden;
  z-index: 5000;
  font-family: 'Segoe UI', sans-serif;
  pointer-events: auto;
}
.properties, .properties * { pointer-events: auto; }

.properties-header {
  padding: 16px 18px 14px; border-bottom: 1px solid var(--border-default);
  background: linear-gradient(180deg, var(--bg-elevated) 0%, var(--bg-surface) 100%);
  flex-shrink: 0;
}
.properties-title { font-size: 15px; font-weight: 700; color: var(--text-primary); margin-bottom: 2px; }
.properties-subtitle { font-size: 10px; font-weight: 500; color: var(--text-tertiary); }

.properties-body { flex: 1; overflow-y: auto; padding: 14px; }
.properties-body::-webkit-scrollbar { width: 6px; }
.properties-body::-webkit-scrollbar-track { background: transparent; }
.properties-body::-webkit-scrollbar-thumb { background: var(--border-strong); border-radius: 3px; }

/* Section headers */
.section-header { display: flex; align-items: center; gap: 10px; margin: 16px 0 10px; }
.section-header:first-child { margin-top: 0; }
.section-header-line { flex: 1; height: 1px; background: var(--border-medium); }
.section-header-text {
  font-size: 10px; font-weight: 700; color: var(--accent-text);
  text-transform: uppercase; letter-spacing: 1.2px; white-space: nowrap;
}

/* Selection card */
.selection-card {
  background: var(--bg-surface); border: 1px solid var(--border-default);
  border-radius: var(--r-lg); padding: 14px; margin-bottom: 12px;
}
.selection-card-header {
  display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px;
}
.selection-id { font-size: 14px; font-weight: 700; color: var(--accent-text); }
.selection-badge {
  font-size: 9px; font-weight: 600; padding: 3px 8px;
  border-radius: var(--r-sm); text-transform: uppercase;
}
.selection-badge.neutral { background: var(--bg-well); color: var(--text-tertiary); }
.selection-badge.included { background: var(--success-bg); color: var(--success); border: 1px solid var(--success-border); }
.selection-badge.excluded { background: var(--error-bg); color: var(--error); border: 1px solid var(--error-border); }

.selection-rows { display: flex; flex-direction: column; gap: 6px; }
.selection-row { display: flex; justify-content: space-between; align-items: center; }
.selection-label { font-size: 10px; color: var(--text-tertiary); }
.selection-value { font-family: 'Consolas', monospace; font-size: 11px; font-weight: 500; color: var(--text-primary); }

.selection-actions {
  display: flex; gap: 6px; margin-top: 12px;
  padding-top: 10px; border-top: 1px solid var(--border-subtle);
}
.selection-btn {
  flex: 1; font-family: inherit; font-size: 10px; font-weight: 600;
  padding: 7px 10px; border-radius: var(--r-sm);
  border: 1px solid var(--border-default); background: var(--bg-panel);
  color: var(--text-secondary); cursor: pointer;
  transition: all var(--duration) var(--ease);
}
.selection-btn:hover { border-color: var(--accent-border); color: var(--accent-text); }
.selection-btn.danger:hover { border-color: var(--error-border); color: var(--error); }


/* STACKED INTAKE STYLES */
.intake-list {
  display: flex; flex-direction: column; gap: 8px; margin-bottom: 8px;
}
.intake {
  background: var(--bg-elevated);
  border: 1px solid var(--border-medium);
  border-radius: 10px;
  padding: 10px 12px;
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 12px;
  cursor: pointer;
  transition: border-color 160ms ease, box-shadow 160ms ease, background 160ms ease;
}
.intake:hover { background: var(--bg-hover); }
.intake[data-selected="true"] {
  border-color: var(--accent);
  box-shadow: 0 0 0 1px var(--accent-glow);
  background: var(--accent-ghost);
}

.intake input {
  appearance: none; width: 14px; height: 14px;
  border-radius: 50%; border: 2px solid var(--text-tertiary);
  position: relative; margin: 0; outline: none;
}
.intake input:checked { border-color: var(--accent); }
.intake input:checked::after {
  content: ""; position: absolute; inset: 2px;
  border-radius: 50%; background: var(--accent);
}

.intake-title { font-size: 12px; font-weight: 700; color: var(--text-primary); }
.intake-meta { font-size: 10px; color: var(--text-muted); margin-top: 2px; font-family: 'Consolas', monospace; }

.pill {
  font-size: 9px; font-weight: 700; padding: 2px 7px;
  border-radius: 10px;
  background: var(--accent-ghost); color: var(--accent);
  border: 1px solid var(--accent-border);
}

.btn {
  font-family: inherit; font-size: 11px; font-weight: 700;
  padding: 8px 12px; border-radius: 8px; cursor: pointer;
  border: 1px solid var(--border-default); background: var(--bg-elevated);
  color: var(--text-secondary); transition: all 150ms ease;
}
.btn.primary {
  background: var(--accent); color: var(--bg-deepest);
  border-color: var(--accent);
}
.btn.primary:hover { background: var(--accent-dim); }

.note { margin-top: 10px; font-size: 10px; color: var(--text-muted); line-height: 1.4; font-style: italic; }

/* EXPLODED MARKER VISUALIZATION (Map) */
.orbit-point {
  position: absolute; width: 14px; height: 14px;
  background: var(--bg-elevated); border-radius: 50%;
  border: 2px solid var(--control-knob); box-shadow: 0 0 0 2px var(--control-border);
  transform: translate(-50%, -50%);
  transition: transform 220ms ease, opacity 220ms ease;
  z-index: 500;
}
.orbit-point[data-selected="true"] {
  border-color: var(--accent);
  box-shadow: 0 0 0 4px var(--accent-glow);
}
.tether {
  position: absolute; height: 1px;
  background: var(--line-contrast); transform-origin: left center;
  z-index: 400;
}


/* Layer settings */
.layer-setting { margin-bottom: 14px; }
.layer-setting-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.layer-setting-label { font-size: 11px; font-weight: 600; color: var(--text-secondary); }
.layer-setting-value {
  font-family: 'Consolas', monospace; font-size: 10px; font-weight: 500;
  color: var(--accent-text); background: var(--accent-ghost);
  border: 1px solid var(--accent-border); padding: 2px 8px; border-radius: var(--r-sm);
}

.slider-track {
  height: 6px; background: var(--bg-surface); border-radius: 3px;
  position: relative; margin: 6px 0; cursor: pointer;
  pointer-events: auto;
  touch-action: none;
  user-select: none;
}
.slider-fill {
  position: absolute; height: 100%;
  background: linear-gradient(90deg, var(--accent-dim), var(--accent));
  border-radius: 3px;
}
.slider-thumb {
  position: absolute; width: 16px; height: 16px;
  background: var(--text-primary); border: 2px solid var(--accent);
  border-radius: 50%; top: 50%; transform: translate(-50%, -50%);
  cursor: grab; box-shadow: 0 1px 3px rgba(0,0,0,0.3);
  z-index: 2;
  pointer-events: auto;
  touch-action: none;
  user-select: none;
}
.slider-native {
  position: absolute;
  left: 0;
  top: -6px;
  width: 100%;
  height: 18px;
  margin: 0;
  opacity: 0.01;
  cursor: pointer;
  z-index: 8;
  -webkit-appearance: none;
  appearance: none;
  background: transparent;
  pointer-events: auto;
}
.slider-native:focus { outline: none; }

.heatmap-mode-toggle {
  display: flex; gap: 6px;
}
.mode-btn {
  flex: 1; padding: 6px 8px; border-radius: 6px;
  border: 1px solid var(--border-medium);
  background: var(--bg-surface); color: var(--text-secondary);
  font-size: 10px; font-weight: 700; cursor: pointer;
}
.mode-btn.active {
  color: var(--accent-text);
  border-color: var(--accent-border);
  background: var(--accent-ghost);
}

.plot-select {
  width: 100%;
  background: var(--bg-surface);
  color: var(--text-primary);
  border: 1px solid var(--border-medium);
  border-radius: 6px;
  padding: 6px 8px;
  font-size: 11px;
}

.toggle-row { display: flex; align-items: center; justify-content: space-between; padding: 8px 0; }
.toggle-label { font-size: 11px; font-weight: 500; color: var(--text-primary); }
.toggle-switch {
  width: 40px; height: 22px; background: var(--control-bg); border-radius: 11px;
  position: relative; cursor: pointer; transition: background var(--duration) var(--ease);
  border: 1px solid var(--border-medium);
}
.toggle-switch.on { background: var(--accent-dim); border-color: var(--accent); }
.toggle-knob {
  position: absolute; width: 16px; height: 16px; background: var(--control-knob);
  border-radius: 50%; top: 2px; left: 2px;
  transition: transform var(--duration) var(--ease);
  box-shadow: var(--shadow-sm);
}
.toggle-switch.on .toggle-knob { transform: translateX(18px); }

/* Export options */
.export-options { display: flex; flex-direction: column; gap: 6px; }
.export-btn {
  display: flex; align-items: center; gap: 8px;
  font-family: inherit; font-size: 11px; font-weight: 600;
  color: var(--text-primary); background: var(--bg-surface);
  border: 1px solid var(--border-medium); border-radius: var(--r-md);
  padding: 10px 14px; cursor: pointer;
  transition: all var(--duration) var(--ease); text-align: left;
}
.export-btn:hover { border-color: var(--accent-border); color: var(--accent-text); background: var(--accent-ghost); }
.export-btn svg { width: 14px; height: 14px; stroke: currentColor; fill: none; stroke-width: 1.8; }


/* Custom Overlays Styles */

/* Leaflet-style zoom controls - Shifted right by 280px + margin */
.map-zoom-controls {
  position: absolute; left: 292px; top: 12px;
  display: flex; flex-direction: column;
  background: var(--control-bg-elevated); border: 1px solid var(--control-border);
  border-radius: var(--r-sm); box-shadow: var(--shadow-md);
  z-index: 1000;
}
.zoom-btn {
  width: 30px; height: 30px; display: flex; align-items: center; justify-content: center;
  background: var(--control-bg-elevated); border: none; cursor: pointer;
  color: var(--control-fg); font-size: 18px; font-weight: 500;
  transition: background 100ms ease;
}
.zoom-btn:hover { background: var(--control-hover); }
.zoom-btn:first-child { border-bottom: 1px solid var(--control-border); }

/* Layers Panel - Right aligned */
.map-layers-panel {
  position: absolute; right: 12px; top: 12px; width: 216px; height: 290px;
  max-height: calc(100% - 24px); min-width: 180px; min-height: 170px;
  background: var(--bg-panel); border: 1px solid var(--border-medium);
  border-radius: 12px; box-shadow: var(--shadow-lg);
  z-index: 1000; overflow: hidden;
  display: flex; flex-direction: column; /* Flex layout for body scrolling */
  font-family: 'Segoe UI', sans-serif;
}
.layers-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 10px; background: var(--bg-surface);
  border-bottom: 1px solid var(--border-default);
  flex-shrink: 0; /* Keep header fixed */
  cursor: grab; user-select: none;
}
.layers-header:active { cursor: grabbing; }
.layers-header-actions {
  display: flex; align-items: center; gap: 6px;
}
.layers-collapse-btn {
  width: 22px;
  height: 20px;
  border-radius: 6px;
  border: 1px solid var(--border-medium);
  background: var(--bg-surface);
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: transform var(--duration) var(--ease), background var(--duration) var(--ease), color var(--duration) var(--ease);
}
.layers-collapse-btn:hover {
  border-color: var(--accent-border);
  color: var(--accent-text);
  background: var(--accent-ghost);
}
.map-layers-panel.collapsed .layers-collapse-btn {
  transform: rotate(-90deg);
}
.overlay-reset-btn {
  height: 20px;
  padding: 0 8px;
  border-radius: 6px;
  border: 1px solid var(--border-medium);
  background: var(--bg-surface);
  color: var(--text-secondary);
  font-size: 10px;
  font-weight: 600;
  cursor: pointer;
}
.overlay-reset-btn:hover {
  border-color: var(--accent-border);
  color: var(--accent-text);
  background: var(--accent-ghost);
}
.layers-title {
  font-size: 10px; font-weight: 700; color: var(--text-primary);
  text-transform: uppercase; letter-spacing: 0.8px;
}
.layers-body {
  padding: 6px 0;
  overflow-y: auto;
  flex: 1; /* Take remaining height */
  min-height: 0;
}

.layer-group { margin-bottom: 6px; padding: 0 6px; }
.layer-group-title {
  font-size: 9px; font-weight: 600; color: var(--text-tertiary);
  text-transform: uppercase; letter-spacing: 0.5px;
  padding: 8px 10px 4px;
  margin-top: 2px;
}

.layer-item {
  display: flex; align-items: center; gap: 8px;
  padding: 6px 10px; border-radius: 6px;
  cursor: pointer; transition: background 150ms ease;
  margin-bottom: 1px;
}
.layer-item:hover { background: var(--bg-hover); }

/* Custom Checkbox */
.layer-check {
  width: 15px; height: 15px; border-radius: 4px;
  border: 1.5px solid var(--border-strong); background: transparent;
  display: flex; align-items: center; justify-content: center;
  transition: all 150ms ease; flex-shrink: 0;
}
.layer-item.active .layer-check {
  background: var(--accent); border-color: var(--accent);
}
.layer-item.active .layer-check svg { display: block; }
.layer-check svg { width: 9px; height: 9px; stroke: var(--control-on-text); stroke-width: 3; fill: none; display: none; }

/* Circle Icon */
.layer-icon-circle {
  width: 10px; height: 10px; border-radius: 50%;
  flex-shrink: 0;
}

/* Info Text */
.layer-info { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 1px; }
.layer-name {
  font-size: 11px; font-weight: 600; color: var(--text-primary);
}
.layer-desc {
  font-size: 9px; color: var(--text-tertiary);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}

/* Mini Slider */
.layer-mini-slider {
  width: 30px; height: 3px; background: var(--border-medium); border-radius: 2px;
  margin-left: 4px; position: relative;
}
.layer-mini-slider-fill {
  position: absolute; height: 100%; left: 0;
  background: var(--accent); border-radius: 2px;
}
.layer-manage-btn {
  border: 1px solid var(--border-medium);
  background: var(--bg-surface);
  color: var(--text-secondary);
  font-size: 9px;
  font-weight: 700;
  border-radius: var(--r-sm);
  padding: 3px 7px;
  cursor: pointer;
  transition: all var(--duration) var(--ease);
  white-space: nowrap;
}
.layer-manage-btn:hover {
  border-color: var(--accent-border);
  color: var(--accent-text);
  background: var(--accent-ghost);
}

/* Transect Lines Section (in Legend) */
.transect-lines-list { padding: 0; }
.transect-lines-empty {
  font-size: 10px;
  color: var(--text-tertiary);
  padding: 4px 0;
  font-style: italic;
}
.transect-line-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 6px;
  margin: 0 -6px;
  border-radius: 4px;
  cursor: pointer;
  transition: background var(--duration) var(--ease);
  position: relative;
}
.transect-line-item:hover { background: var(--bg-hover); }
.transect-line-item.active { background: var(--accent-ghost); }
.transect-line-item.selected {
  background: var(--accent-ghost);
  border-left: 2px solid var(--accent);
  margin-left: -8px;
  padding-left: 8px;
}
.transect-line-check {
  width: 15px; height: 15px;
  border-radius: 4px;
  border: 1.5px solid var(--border-strong);
  background: transparent;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: all var(--duration) var(--ease);
}
.transect-line-item.visible .transect-line-check {
  background: var(--accent);
  border-color: var(--accent);
}
.transect-line-check svg {
  width: 9px; height: 9px;
  stroke: var(--control-on-text);
  stroke-width: 3;
  fill: none;
  display: none;
}
.transect-line-item.visible .transect-line-check svg { display: block; }
.transect-line-color {
  width: 10px; height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}
.transect-line-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 1px;
}
.transect-line-name {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.transect-line-name input {
  background: transparent;
  border: none;
  border-bottom: 1px solid var(--accent);
  font-size: 11px;
  font-weight: 600;
  color: var(--text-primary);
  padding: 0;
  width: 100%;
  outline: none;
}
.transect-line-desc {
  font-size: 9px;
  color: var(--text-tertiary);
}
.transect-line-actions {
  display: flex;
  gap: 4px;
  opacity: 0;
  transition: opacity var(--duration) var(--ease);
}
.transect-line-item:hover .transect-line-actions { opacity: 1; }
.transect-line-btn {
  width: 18px; height: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  color: var(--text-muted);
  transition: all var(--duration) var(--ease);
  padding: 0;
}
.transect-line-btn:hover {
  background: var(--bg-surface);
  color: var(--text-primary);
}
.transect-line-btn.delete:hover {
  background: var(--error-ghost);
  color: var(--error);
}
.transect-line-btn svg {
  width: 12px; height: 12px;
  stroke: currentColor;
  stroke-width: 2;
  fill: none;
}

.external-layer-summary {
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  border-radius: var(--r-md);
  padding: 10px;
  margin-bottom: 10px;
}
.external-layer-summary-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}
.external-layer-summary-count {
  font-size: 10px;
  font-weight: 700;
  color: var(--accent-text);
}
.external-layer-summary-note {
  font-size: 10px;
  color: var(--text-tertiary);
}

/* External layer manager dialog */
.layer-manager-backdrop {
  position: fixed;
  inset: 0;
  background: var(--overlay-scrim);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 12000;
  backdrop-filter: blur(4px);
  opacity: 0;
  visibility: hidden;
  pointer-events: none;
  transition: opacity 160ms var(--ease), visibility 0s linear 160ms;
}
.layer-manager-backdrop.open {
  opacity: 1;
  visibility: visible;
  pointer-events: auto;
  transition: opacity 160ms var(--ease);
}
.layer-manager-dialog {
  width: min(860px, 94vw);
  max-height: min(720px, 90vh);
  background: var(--bg-panel);
  border: 1px solid var(--border-medium);
  border-radius: var(--r-xl);
  box-shadow: var(--shadow-lg);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transform: translateY(8px) scale(0.985);
  opacity: 0;
  transition: transform 170ms var(--ease), opacity 170ms var(--ease);
}
.layer-manager-backdrop.open .layer-manager-dialog {
  transform: translateY(0) scale(1);
  opacity: 1;
}
.layer-manager-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-bottom: 1px solid var(--border-default);
  background: var(--bg-elevated);
}
.layer-manager-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--text-primary);
}
.layer-manager-subtitle {
  font-size: 10px;
  color: var(--text-tertiary);
  margin-top: 2px;
}
.layer-manager-close {
  width: 28px;
  height: 28px;
  border: 1px solid var(--border-medium);
  border-radius: var(--r-sm);
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
}
.layer-manager-body {
  display: grid;
  grid-template-columns: 280px 1fr;
  min-height: 0;
  flex: 1;
}
.layer-manager-list {
  border-right: 1px solid var(--border-default);
  padding: 10px;
  overflow: auto;
}
.external-layer-empty {
  font-size: 10px;
  color: var(--text-tertiary);
  padding: 8px;
}
.external-layer-row {
  display: grid;
  grid-template-columns: 1fr auto;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border: 1px solid transparent;
  border-radius: var(--r-md);
  cursor: pointer;
  margin-bottom: 6px;
  background: transparent;
}
.external-layer-row:hover { background: var(--bg-surface); }
.external-layer-row.active {
  border-color: var(--accent-border);
  background: var(--accent-ghost);
}
.external-layer-row-name {
  font-size: 11px;
  font-weight: 700;
  color: var(--text-primary);
}
.external-layer-row-meta {
  font-size: 10px;
  color: var(--text-tertiary);
  margin-top: 2px;
}
.external-visibility-btn {
  border: 1px solid var(--border-medium);
  background: var(--bg-surface);
  color: var(--text-secondary);
  border-radius: var(--r-pill);
  padding: 4px 8px;
  font-size: 9px;
  font-weight: 700;
  cursor: pointer;
}
.external-visibility-btn.on {
  color: var(--accent-text);
  border-color: var(--accent-border);
  background: var(--accent-ghost);
}
.layer-manager-detail {
  padding: 12px 14px;
  overflow: auto;
}
.layer-detail-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}
.layer-detail-name {
  font-size: 13px;
  font-weight: 700;
  color: var(--text-primary);
}
.layer-geometry-badge {
  font-size: 9px;
  font-weight: 700;
  color: var(--text-secondary);
  border: 1px solid var(--border-medium);
  border-radius: var(--r-pill);
  padding: 3px 8px;
  text-transform: uppercase;
  letter-spacing: 0.6px;
}
.layer-detail-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  margin-bottom: 10px;
}
.layer-detail-card {
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  border-radius: var(--r-md);
  padding: 8px 10px;
}
.layer-detail-card-label {
  font-size: 9px;
  color: var(--text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.6px;
}
.layer-detail-card-value {
  margin-top: 4px;
  font-size: 11px;
  font-weight: 700;
  color: var(--text-primary);
}
.layer-style-block {
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  border-radius: var(--r-md);
  padding: 10px;
  margin-bottom: 8px;
}
.layer-style-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}
.layer-style-row:last-child { margin-bottom: 0; }
.layer-style-label {
  font-size: 10px;
  color: var(--text-secondary);
  font-weight: 600;
}
.layer-style-value {
  font-family: 'Consolas', 'IBM Plex Mono', monospace;
  font-size: 10px;
  color: var(--accent-text);
}
.layer-style-color {
  width: 36px;
  height: 22px;
  border: 1px solid var(--border-medium);
  border-radius: var(--r-sm);
  padding: 0;
  cursor: pointer;
  background: transparent;
}
.layer-style-range { width: 180px; }
.layer-manager-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-top: 1px solid var(--border-default);
  padding: 10px 14px;
  background: var(--bg-elevated);
}
.layer-manager-note {
  font-size: 10px;
  color: var(--text-tertiary);
}
body.external-layer-dialog-open {
  overflow: hidden;
}

/* Legend - Shifted to avoid sidebar */
.map-legend {
  position: absolute; left: 292px; top: 80px; width: 248px;
  background: var(--bg-panel); border: 1px solid var(--border-medium);
  border-radius: 12px; padding: 10px 12px;
  box-shadow: 0 4px 20px rgba(0,0,0,0.4); z-index: 1000;
  min-width: 196px; min-height: 180px;
  font-family: 'Segoe UI', sans-serif;
  overflow: auto;
}
.legend-header {
  display: flex; align-items: center; justify-content: space-between;
  margin: -10px -12px 8px;
  padding: 10px 10px;
  border-bottom: 1px solid rgba(255,255,255,0.05);
  background: #212127;
  cursor: grab; user-select: none;
}
.legend-header:active { cursor: grabbing; }
.legend-title {
  font-size: 11px; font-weight: 700; color: var(--text-secondary);
  text-transform: uppercase; letter-spacing: 0.6px;
}
.legend-section { margin-bottom: 10px; }
.legend-section:last-child { margin-bottom: 0; }
.legend-section-title {
  font-size: 10px; font-weight: 600; color: var(--text-tertiary); margin-bottom: 6px;
}
.legend-item { display: flex; align-items: center; gap: 8px; padding: 4px 0; }
.legend-symbol {
  width: 13px; height: 13px; border-radius: 50%; flex-shrink: 0;
}
.legend-symbol.square { border-radius: 2px; }
.legend-label { font-size: 11px; color: var(--text-secondary); border-radius: 4px; padding: 0 2px; }
.legend-label[contenteditable="true"] {
  background: rgba(96, 165, 250, 0.12);
  outline: 1px solid rgba(96, 165, 250, 0.35);
}
.legend-gradient { height: 9px; border-radius: 4px; margin: 6px 0; }
.legend-gradient-labels { display: flex; justify-content: space-between; }
.legend-gradient-labels span {
  font-size: 10px; color: var(--text-muted); font-family: 'Consolas', 'IBM Plex Mono', monospace;
}
.legend-external-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-top: 4px;
}
.legend-external-item {
  padding: 4px 0;
  border-radius: 8px;
}
.legend-external-item.drag-over {
  background: rgba(96, 165, 250, 0.10);
  outline: 1px dashed rgba(96, 165, 250, 0.35);
}
.legend-external-item.is-hidden {
  opacity: 0.55;
}
.legend-external-handle {
  width: 14px;
  color: var(--text-muted);
  font-weight: 800;
  cursor: grab;
  user-select: none;
  flex: 0 0 14px;
  text-align: center;
  line-height: 1;
  opacity: 0.75;
}
.legend-external-handle:active { cursor: grabbing; }
.legend-external-meta {
  margin-left: auto;
  font-size: 10px;
  color: var(--text-muted);
  font-family: 'Consolas', 'IBM Plex Mono', monospace;
}

/* Leaflet popups (used by external layer feature click) */
.leaflet-popup-content-wrapper, .leaflet-popup-tip {
  background: #1f1f25;
  color: #e5e7eb;
  border: 1px solid rgba(255,255,255,0.08);
  box-shadow: 0 10px 28px rgba(0,0,0,0.55);
}
.leaflet-popup-close-button {
  color: rgba(229, 231, 235, 0.65) !important;
}
.leaflet-popup-close-button:hover {
  color: rgba(229, 231, 235, 0.95) !important;
}
.ha-ext-popup-title {
  font-size: 12px;
  font-weight: 700;
  margin: 0 0 6px;
}
.ha-ext-popup-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 11px;
}
.ha-ext-popup-table td {
  padding: 2px 4px;
  vertical-align: top;
}
.ha-ext-popup-table td.key {
  color: rgba(229, 231, 235, 0.62);
  font-weight: 700;
  white-space: nowrap;
  padding-right: 8px;
}
.ha-ext-popup-table td.val {
  color: rgba(229, 231, 235, 0.92);
  word-break: break-word;
}

.floating-resize-handle {
  position: absolute;
  right: 4px;
  bottom: 4px;
  width: 12px;
  height: 12px;
  border-right: 2px solid rgba(255,255,255,0.28);
  border-bottom: 2px solid rgba(255,255,255,0.28);
  border-radius: 2px;
  cursor: nwse-resize;
  opacity: 0.75;
  z-index: 2;
}
.floating-resize-handle:hover { opacity: 1; }
.map-layers-panel.panel-moving, .map-legend.panel-moving {
  box-shadow: 0 8px 26px rgba(0,0,0,0.55);
}
.map-layers-panel.collapsed {
  height: auto !important;
  min-height: 0 !important;
}
.map-layers-panel.collapsed .layers-body {
  display: none;
}
.map-layers-panel.collapsed .floating-resize-handle {
  display: none;
}

/* Scale & Coords - Shifted */
.map-scale {
  position: absolute; left: 292px; bottom: 24px;
  background: var(--scale-bg); padding: 4px 8px;
  border-radius: 2px; font-size: 10px; color: var(--control-fg);
  box-shadow: var(--shadow-sm); z-index: 1000;
}
.scale-bar {
  width: 100px; height: 4px; margin-bottom: 2px;
  background: linear-gradient(90deg, var(--scale-strong) 0%, var(--scale-strong) 50%, var(--scale-soft) 50%, var(--scale-soft) 100%);
  border: 1px solid var(--scale-strong);
}

.map-coords {
  position: absolute; right: 12px; bottom: 24px;
  background: var(--bg-panel); border: 1px solid var(--border-medium);
  border-radius: var(--r-md); padding: 8px 12px;
  box-shadow: var(--shadow-md); z-index: 1000;
  font-family: 'Segoe UI', sans-serif;
}
.coords-row { display: flex; gap: 16px; }
.coord-item { display: flex; align-items: center; gap: 6px; }
.coord-label { font-size: 9px; font-weight: 600; color: var(--text-tertiary); text-transform: uppercase; }
.coord-value { font-family: 'Consolas', 'IBM Plex Mono', monospace; font-size: 10px; font-weight: 500; color: var(--text-primary); }

.map-attribution {
  position: absolute; bottom: 4px; right: 4px;
  font-size: 9px; color: #666; background: rgba(255,255,255,0.7);
  padding: 2px 6px; border-radius: 2px; z-index: 1000;
}

/* Geology Panel - Shifted to respect sidebar */
.geology-panel {
  position: absolute; left: 280px; right: 0; bottom: 0;
  height: 320px; max-height: 52vh; background: var(--bg-panel);
  border-top: 1px solid var(--border-medium);
  border-left: 1px solid var(--border-medium);
  display: flex; flex-direction: column;
  transform: translateY(100%);
  transition: transform 300ms var(--ease);
  z-index: 1100;
  font-family: 'Segoe UI', sans-serif;
}
.geology-panel.visible { transform: translateY(0); }

.geology-resize-handle {
  height: 10px;
  cursor: ns-resize;
  background:
    radial-gradient(circle at 50% 50%, rgba(255,255,255,0.18) 0 1px, transparent 2px) 0 0 / 10px 10px,
    linear-gradient(180deg, rgba(255,255,255,0.06), rgba(0,0,0,0.0));
  border-bottom: 1px solid var(--border-subtle);
}

.geology-header {
  display: flex; align-items: center; padding: 10px 16px;
  background: var(--bg-elevated); border-bottom: 1px solid var(--border-subtle);
  gap: 12px;
}
.geology-title {
  font-size: 12px; font-weight: 700; color: var(--text-primary);
  display: flex; align-items: center; gap: 8px;
}
.geology-info {
  font-size: 10px; color: var(--text-tertiary);
  font-family: 'Consolas', monospace;
}
.geology-status-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px 4px 8px;
  border-radius: 999px;
  border: 1px solid var(--border-medium);
  background: rgba(255,255,255,0.03);
  color: var(--text-secondary);
  font-size: 10px;
  font-weight: 700;
  cursor: pointer;
  transition: all var(--duration) var(--ease);
  position: relative;
}
.geology-status-pill:hover {
  background: rgba(255,255,255,0.06);
  border-color: var(--border-strong);
}
.geology-status-pill .status-icon {
  width: 14px; height: 14px;
  display: none;
}
.geology-status-pill .status-icon svg {
  width: 14px; height: 14px;
}
.geology-status-pill .status-expand {
  width: 10px; height: 10px;
  margin-left: 2px;
  opacity: 0.5;
  transition: transform var(--duration) var(--ease);
}
.geology-status-pill.expanded .status-expand {
  transform: rotate(180deg);
}

/* Status icon states */
.geology-status-pill .icon-idle { display: flex; color: var(--info); }
.geology-panel[data-state="loading"] .geology-status-pill .icon-idle { display: none; }
.geology-panel[data-state="loading"] .geology-status-pill .icon-loading { display: flex; color: var(--warning); }
.geology-panel[data-state="error"] .geology-status-pill .icon-idle { display: none; }
.geology-panel[data-state="error"] .geology-status-pill .icon-error { display: flex; color: var(--error); }
.geology-panel[data-state="ready"] .geology-status-pill .icon-idle { display: none; }
.geology-panel[data-state="ready"] .geology-status-pill .icon-success { display: flex; color: var(--success); }
.geology-panel[data-state="warning"] .geology-status-pill .icon-idle { display: none; }
.geology-panel[data-state="warning"] .geology-status-pill .icon-warning { display: flex; color: var(--warning); }

/* Spin animation for loading */
@keyframes geo-spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
.geology-status-pill .icon-loading svg {
  animation: geo-spin 1s linear infinite;
}

/* Status detail popup */
.geology-status-detail {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  min-width: 240px;
  max-width: 360px;
  padding: 10px 12px;
  background: var(--bg-elevated);
  border: 1px solid var(--border-medium);
  border-radius: var(--r-lg);
  box-shadow: var(--shadow-lg);
  font-size: 11px;
  font-weight: 500;
  color: var(--text-secondary);
  line-height: 1.5;
  z-index: 100;
  opacity: 0;
  pointer-events: none;
  transform: translateY(-4px);
  transition: all var(--duration) var(--ease);
}
.geology-status-pill.expanded .geology-status-detail {
  opacity: 1;
  pointer-events: auto;
  transform: translateY(0);
}
.geology-status-detail::before {
  content: '';
  position: absolute;
  top: -6px;
  right: 16px;
  width: 10px; height: 10px;
  background: var(--bg-elevated);
  border-left: 1px solid var(--border-medium);
  border-top: 1px solid var(--border-medium);
  transform: rotate(45deg);
}
.geology-header-spacer { flex: 1; }
.geology-header-actions {
  display: flex;
  align-items: center;
  gap: 6px;
}
.geology-action {
  height: 26px;
  border: 1px solid var(--border-medium);
  background: var(--bg-surface);
  color: var(--text-secondary);
  border-radius: 6px;
  padding: 0 12px;
  cursor: pointer;
  transition: all var(--duration) var(--ease);
  font-size: 10px;
  font-weight: 700;
}
.geology-action:hover {
  color: var(--accent-text);
  border-color: var(--accent-border);
  background: var(--accent-ghost);
}
.geology-action:active { transform: scale(0.97); }
.geology-close {
  width: 24px; height: 24px; display: flex; align-items: center; justify-content: center;
  background: transparent; border: none; border-radius: var(--r-sm);
  cursor: pointer; color: var(--text-muted);
  transition: all var(--duration) var(--ease);
}
.geology-close:hover { background: var(--bg-hover); color: var(--error); }
.geology-close svg { width: 14px; height: 14px; stroke: currentColor; stroke-width: 2; fill: none; }

.geology-content { flex: 1; display: flex; padding: 12px 16px; gap: 16px; overflow: hidden; }

/* Main area: viewer only (legend is now overlay inside viewport) */
.geology-main {
  flex: 1;
  min-width: 0;
  display: flex;
  gap: 12px;
}

/* Viewer (left column) */
.geology-view {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

/* Viewport row: cross-section + legend side by side */
.geology-viewport-row {
  flex: 1;
  display: flex;
  gap: 0;
  min-height: 160px;
  border-radius: var(--r-xl);
  border: 1px solid var(--border-medium);
  overflow: hidden;
  background:
    radial-gradient(1200px 320px at 50% 0%, rgba(45,212,191,0.07), transparent 60%),
    linear-gradient(180deg, rgba(255,255,255,0.06), rgba(0,0,0,0.0));
}

/* Inline legend - side panel next to cross-section */
.geology-inline-legend {
  width: 140px;
  min-width: 120px;
  display: flex;
  flex-direction: column;
  background: var(--bg-panel);
  border-left: 1px solid var(--border-medium);
}
.geology-inline-legend-header {
  padding: 8px 10px;
  background: var(--bg-elevated);
  border-bottom: 1px solid var(--border-subtle);
  font-size: 9px;
  font-weight: 700;
  color: var(--text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.4px;
}
.geology-inline-legend-content {
  flex: 1;
  overflow-y: auto;
  padding: 6px 8px;
}
.geology-inline-legend-content::-webkit-scrollbar { width: 4px; }
.geology-inline-legend-content::-webkit-scrollbar-thumb { background: var(--border-strong); border-radius: 2px; }
.geology-inline-legend-empty {
  color: var(--text-muted);
  font-size: 10px;
  font-style: italic;
  padding: 4px;
}
/* Legend items styling */
.geology-inline-legend .geology-legend-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 3px 2px;
}
.geology-inline-legend .geology-legend-color {
  width: 14px;
  height: 14px;
  border-radius: 2px;
  border: 1px solid rgba(0,0,0,0.15);
  flex-shrink: 0;
}
.geology-inline-legend .geology-legend-text {
  font-size: 10px;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
/* Hide unit IDs in inline legend for cleaner look */
.geology-inline-legend .geology-legend-code {
  display: none;
}
.geology-view-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: var(--r-lg);
}
.geology-view-toolbar .seg {
  display: inline-flex;
  border: 1px solid var(--border-medium);
  background: var(--bg-well);
  border-radius: 6px;
  overflow: hidden;
  padding: 2px;
  gap: 2px;
}
.geology-view-toolbar .seg button {
  border: none;
  background: transparent;
  color: var(--text-tertiary);
  padding: 5px 12px;
  font-size: 10px;
  font-weight: 700;
  cursor: pointer;
  border-radius: 4px;
  transition: all var(--duration) var(--ease);
}
.geology-view-toolbar .seg button.active {
  color: var(--accent-text);
  background: var(--accent-ghost);
  border: 1px solid var(--accent-border);
}
.geology-view-toolbar .seg button:not(.active):hover {
  color: var(--text-secondary);
  background: rgba(255,255,255,0.04);
}
.geology-view-toolbar .spacer { flex: 1; }
.geology-mini {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--text-tertiary);
  font-size: 10px;
  font-weight: 700;
}
.geology-mini input[type="range"] { width: 140px; }
.geology-mini .mono {
  font-family: 'Consolas', monospace;
  font-size: 10px;
  color: var(--text-secondary);
}
.geology-viewport {
  flex: 1;
  min-width: 0;
  position: relative;
  overflow: hidden;
}
.geology-viewport .geology-empty,
.geology-viewport .geology-loading {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 16px;
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 700;
  backdrop-filter: blur(2px);
}
.geology-viewport .geology-loading { display: none; }
.geology-panel[data-state="loading"] .geology-viewport .geology-loading { display: flex; }
.geology-panel[data-state="loading"] .geology-viewport .geology-empty { display: none; }
.geology-panel[data-state="ready"] .geology-viewport .geology-empty { display: none; }
.geology-viewport img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: contain;
  background: rgba(255,255,255,0.92);
  transform-origin: 50% 50%;
}
.geology-viewport svg.geology-overlay {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}
.geology-viewport .bh-line {
  stroke: rgba(0,0,0,0.92);
  stroke-width: 1.4;
}
.geology-viewport .bh-screen {
  stroke: rgba(0,0,0,0.92);
  stroke-width: 2.6;
}
.geology-viewport .bh-cap {
  stroke: rgba(0,0,0,0.92);
  stroke-width: 2.0;
}
.geology-viewport .bh-label {
  fill: rgba(0,0,0,0.82);
  font-family: 'Consolas', monospace;
  font-size: 10px;
  font-weight: 700;
}
.geology-metrics {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 8px;
}
.geo-metric {
  background: var(--bg-well);
  border: 1px solid var(--border-subtle);
  border-radius: var(--r-lg);
  padding: 8px 10px;
  min-width: 0;
}
.geo-metric .k {
  font-size: 9px;
  font-weight: 800;
  color: var(--text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.8px;
}
.geo-metric .v {
  margin-top: 3px;
  font-family: 'Consolas', monospace;
  font-size: 11px;
  font-weight: 700;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Geology side panel (Request + Diagnostics tabs) */
.geology-side {
  width: 280px;
  min-width: 260px;
  max-width: 300px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
/* Hide legend tab since legend is now inline */
.geo-tab[data-tab="legend"] { display: none; }
.geology-side-tabs {
  display: flex;
  gap: 2px;
  background: var(--bg-well);
  border: 1px solid var(--border-medium);
  border-radius: 8px;
  padding: 3px;
}
.geo-tab {
  flex: 1;
  border: none;
  background: transparent;
  color: var(--text-tertiary);
  font-size: 10px;
  font-weight: 700;
  padding: 8px 12px;
  border-radius: 6px;
  cursor: pointer;
  transition: all var(--duration) var(--ease);
}
.geo-tab:hover:not(.active) {
  color: var(--text-secondary);
  background: rgba(255,255,255,0.03);
}
.geo-tab.active {
  background: var(--accent-ghost);
  color: var(--accent-text);
  border: 1px solid var(--accent-border);
}
.geo-tabpanel {
  flex: 1;
  display: none;
  overflow: auto;
  padding-right: 4px;
}
.geo-tabpanel.active { display: block; }
.geo-tabpanel::-webkit-scrollbar { width: 6px; }
.geo-tabpanel::-webkit-scrollbar-thumb { background: var(--border-strong); border-radius: 3px; }

.geology-legend {
  display: flex; flex-direction: column; gap: 6px;
  overflow: auto;
}
.geology-legend-title {
  font-size: 9px; font-weight: 600; color: var(--text-tertiary);
  text-transform: uppercase; letter-spacing: 0.5px;
  margin-bottom: 4px;
}
.geology-legend-item {
  display: flex; align-items: center; gap: 8px;
}
.geology-legend-color {
  width: 16px; height: 16px; border-radius: 3px;
  border: 1px solid rgba(0,0,0,0.1);
}
.geology-legend-text {
  font-size: 10px; color: var(--text-secondary);
}
.geology-legend-code {
  font-family: 'Consolas', monospace;
  font-size: 9px; color: var(--text-muted);
  margin-left: auto;
}

/* Geo.dk request controls (request tab) */
.geodk-form {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.geodk-help {
  font-size: 10px;
  color: var(--text-tertiary);
  line-height: 1.35;
  background: var(--bg-well);
  border: 1px solid var(--border-subtle);
  border-radius: var(--r-lg);
  padding: 10px 10px;
}
.geodk-row {
  display: grid;
  grid-template-columns: 110px 1fr;
  gap: 10px;
  align-items: center;
}
.geodk-row .lbl {
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.8px;
  text-transform: uppercase;
  color: var(--text-tertiary);
}
.geodk-row .ctl { min-width: 0; }
.geodk-input,
.geodk-select {
  width: 100%;
  border: 1px solid var(--border-medium);
  background: var(--bg-surface);
  color: var(--text-primary);
  border-radius: var(--r-md);
  padding: 7px 9px;
  font-size: 11px;
  font-weight: 700;
  outline: none;
}
.geodk-input:focus,
.geodk-select:focus {
  border-color: var(--accent-border);
  box-shadow: 0 0 0 3px var(--accent-ghost);
}
.geodk-inline {
  display: flex;
  gap: 8px;
  align-items: center;
}
/* Styled range sliders for geodk */
.geodk-inline input[type="range"],
.geology-mini input[type="range"] {
  -webkit-appearance: none;
  appearance: none;
  width: 100%;
  height: 6px;
  background: var(--bg-well);
  border: 1px solid var(--border-subtle);
  border-radius: 3px;
  outline: none;
  cursor: pointer;
}
.geodk-inline input[type="range"]::-webkit-slider-thumb,
.geology-mini input[type="range"]::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 14px;
  height: 14px;
  background: var(--accent);
  border: 2px solid var(--bg-surface);
  border-radius: 50%;
  cursor: pointer;
  box-shadow: 0 1px 3px rgba(0,0,0,0.3);
  transition: transform 0.15s ease;
}
.geodk-inline input[type="range"]::-webkit-slider-thumb:hover,
.geology-mini input[type="range"]::-webkit-slider-thumb:hover {
  transform: scale(1.1);
}
.geodk-inline input[type="range"]::-moz-range-thumb,
.geology-mini input[type="range"]::-moz-range-thumb {
  width: 14px;
  height: 14px;
  background: var(--accent);
  border: 2px solid var(--bg-surface);
  border-radius: 50%;
  cursor: pointer;
}
.geodk-diag pre {
  font-family: 'Consolas', monospace;
  font-size: 10px;
  color: var(--text-secondary);
  white-space: pre-wrap;
  word-break: break-word;
  background: var(--bg-well);
  border: 1px solid var(--border-subtle);
  border-radius: var(--r-lg);
  padding: 10px 10px;
}

/* Tooltip (Custom) */
.point-tooltip {
  position: fixed; background: var(--bg-elevated); border-radius: 4px;
  padding: 10px 14px; box-shadow: var(--shadow-md);
  z-index: 2000; min-width: 180px; pointer-events: none;
  opacity: 0; transform: translateY(4px);
  transition: all var(--duration) var(--ease);
  color: var(--text-primary);
  border: 1px solid var(--tooltip-border);
}
.point-tooltip::after {
  content: ''; position: absolute; bottom: -8px; left: 50%;
  transform: translateX(-50%);
  border-left: 8px solid transparent;
  border-right: 8px solid transparent;
  border-top: 8px solid var(--bg-elevated);
}
.point-tooltip.visible { opacity: 1; transform: translateY(0); }
.tooltip-header {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 8px; padding-bottom: 6px;
  border-bottom: 1px solid var(--tooltip-border);
}
.tooltip-id { font-size: 13px; font-weight: 700; color: var(--layer-points); }
.tooltip-status {
  font-size: 9px; font-weight: 600; padding: 2px 6px;
  border-radius: var(--r-sm); text-transform: uppercase;
}
.tooltip-status.included { background: var(--success-bg); color: var(--success); }
.tooltip-status.excluded { background: var(--error-bg); color: var(--error); }
.tooltip-row { display: flex; justify-content: space-between; padding: 3px 0; }
.tooltip-label { font-size: 11px; color: var(--tooltip-muted); }
.tooltip-value { font-family: 'Consolas', monospace; font-size: 11px; font-weight: 500; color: var(--text-primary); }

/* Labels default-hidden; JS toggles visibility deterministically. */
.point-id-label { display: none; }

.overlay-contours {
  transition: stroke-width 120ms ease, opacity 120ms ease;
}
"""


def _shadow_stack(primary: str, secondary: str, *, large: bool = False) -> str:
    if large:
        return f"0 4px 16px {primary}, 0 2px 6px {secondary}"
    return f"0 1px 2px {primary}, 0 1px 3px {secondary}"


def _map_theme_root_css() -> str:
    return f"""
:root {{
  --accent: {Colors.ACCENT_PRIMARY};
  --accent-dim: {Colors.ACCENT_PRESSED};
  --accent-glow: {Colors.ACCENT_GLOW};
  --accent-ghost: {Colors.ACCENT_GHOST};
  --accent-text: {Colors.TEXT_ACCENT};
  --accent-border: {Colors.BORDER_ACCENT};

  --bg-deepest: {Colors.BG_APP};
  --bg-base: {Colors.BG_DARK};
  --bg-panel: {Colors.BG_PANEL};
  --bg-surface: {Colors.BG_SURFACE};
  --bg-elevated: {Colors.BG_ELEVATED};
  --bg-hover: {Colors.BG_HOVER};
  --bg-well: {Colors.BG_WELL};

  --border-subtle: {Colors.BORDER_SUBTLE};
  --border-default: {Colors.BORDER_DEFAULT};
  --border-medium: {Colors.BORDER_MEDIUM};
  --border-strong: {Colors.BORDER_STRONG};

  --text-primary: {Colors.TEXT_PRIMARY};
  --text-secondary: {Colors.TEXT_SECONDARY};
  --text-tertiary: {Colors.TEXT_TERTIARY};
  --text-muted: {Colors.TEXT_MUTED};

  --icon-plot: {Colors.ICON_PLOT};
  --icon-map: {Colors.ICON_MAP};
  --icon-stats: {Colors.ICON_STATS};

  --success: {Colors.SUCCESS};
  --success-bg: {Colors.SUCCESS_BG};
  --success-border: {Colors.rgba(Colors.SUCCESS, 0.25)};
  --warning: {Colors.WARNING};
  --warning-border: {Colors.rgba(Colors.WARNING, 0.30)};
  --error: {Colors.ERROR};
  --error-bg: {Colors.ERROR_BG};
  --error-border: {Colors.rgba(Colors.ERROR, 0.25)};
  --info: {Colors.INFO};
  --error-ghost: {Colors.ERROR_BG};

  --layer-points: {Colors.INFO};
  --layer-excluded: {Colors.TEXT_TERTIARY};
  --layer-external: {Colors.SUCCESS};
  --layer-rejection: {Colors.ERROR};
  --layer-coverage: {Colors.SUCCESS_LIGHT};
  --layer-contours: {Colors.REJECTION_BASE_HEIGHT};
  --layer-vectors: {Colors.WARNING};
  --layer-selection: {Colors.ACCENT_PRIMARY};
  --layer-transect: #ec4899;

  --geo-sand: #d4b483;
  --geo-clay: #9a7b6f;
  --geo-till: #7f9aa3;
  --geo-limestone: #b7bfd1;

  --r-sm: 6px;
  --r-md: 8px;
  --r-lg: 10px;
  --r-xl: 12px;
  --r-2xl: 16px;
  --r-pill: 100px;

  --shadow-sm: {_shadow_stack(Colors.SHADOW_SUBTLE, Colors.SHADOW_MEDIUM)};
  --shadow-md: 0 2px 8px {Colors.SHADOW_MEDIUM}, 0 1px 3px {Colors.SHADOW_SUBTLE};
  --shadow-lg: {_shadow_stack(Colors.SHADOW_STRONG, Colors.SHADOW_MEDIUM, large=True)};

  --overlay-scrim: {Colors.OVERLAY_SCRIM};
  --control-bg: {Colors.BG_HOVER};
  --control-bg-elevated: {Colors.BG_ELEVATED};
  --control-hover: {Colors.BG_HOVER};
  --control-fg: {Colors.TEXT_PRIMARY};
  --control-knob: {Colors.BG_ELEVATED};
  --control-on-text: {Colors.TEXT_INVERSE};
  --control-border: {Colors.BORDER_MEDIUM};
  --line-contrast: {Colors.rgba(Colors.TEXT_PRIMARY, 0.22)};
  --scale-bg: {Colors.rgba(Colors.BG_ELEVATED, 0.88)};
  --scale-strong: {Colors.TEXT_PRIMARY};
  --scale-soft: {Colors.BG_ELEVATED};
  --tooltip-border: {Colors.BORDER_DEFAULT};
  --tooltip-muted: {Colors.TEXT_SECONDARY};

  --ease: cubic-bezier(0.4, 0, 0.2, 1);
  --duration: 150ms;
}}
""".strip()


def get_concept_css() -> str:
    return re.sub(
        r":root\s*\{.*?\n\}",
        lambda _match: _map_theme_root_css(),
        _CONCEPT_CSS_TEMPLATE,
        count=1,
        flags=re.S,
    )


CONCEPT_CSS = get_concept_css()

CONCEPT_HTML_OVERLAYS = """
<!-- Zoom Controls (Custom) -->
<div class="map-zoom-controls">
    <button class="zoom-btn" onclick="map.zoomIn()">+</button>
    <button class="zoom-btn" onclick="map.zoomOut()">&#8722;</button>
</div>

<!-- Layers Panel -->
<div class="map-layers-panel">
    <div class="layers-header">
        <span class="layers-title">Layers</span>
        <div class="layers-header-actions">
            <button class="layers-collapse-btn" onclick="toggleLayersPanel()" title="Collapse/Expand Layers">&#9662;</button>
            <button class="overlay-reset-btn" onclick="resetOverlayLayout()">Reset UI</button>
        </div>
    </div>
    <div class="layers-body" id="layersBody">
        <div class="layer-group">
            <div class="layer-group-title">Data Layers</div>

            <div class="layer-item active" onclick="toggleLayer('points', this)">
                <div class="layer-check"><svg viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></svg></div>
                <div class="layer-icon-circle" style="background: var(--layer-points);"></div>
                <div class="layer-info">
                    <div class="layer-name">Data Points</div>
                    <div class="layer-desc">47 points (44 active)</div>
                </div>
            </div>

            <div class="layer-item active" onclick="toggleLayer('excluded', this)">
                <div class="layer-check"><svg viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></svg></div>
                <div class="layer-icon-circle" style="background: var(--layer-excluded);"></div>
                <div class="layer-info">
                    <div class="layer-name">Excluded Points</div>
                    <div class="layer-desc">3 excluded</div>
                </div>
            </div>

            <div class="layer-item active" id="layerToggleExternal" onclick="toggleLayer('external', this)">
                <div class="layer-check"><svg viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></svg></div>
                <div class="layer-icon-circle" style="background: var(--layer-external);"></div>
                <div class="layer-info">
                    <div class="layer-name">External GIS Layers</div>
                    <div class="layer-desc" id="externalLayerCount">0 loaded (0 visible)</div>
                </div>
                <button class="layer-manage-btn" onclick="event.stopPropagation(); if(window.pyBridge && window.pyBridge.onOpenExternalLayerManagerRequested) window.pyBridge.onOpenExternalLayerManagerRequested();">Manage</button>
            </div>
        </div>

        <div class="layer-group">
            <div class="layer-group-title">Analysis Overlays</div>

            <div class="layer-item active" onclick="toggleLayer('heatmap', this)">
                <div class="layer-check"><svg viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></svg></div>
                <div class="layer-icon-circle" style="background: var(--layer-rejection);"></div>
                <div class="layer-info">
                    <div class="layer-name">Rejection Heatmap</div>
                    <div class="layer-desc">Spatial density</div>
                </div>
                <div class="layer-mini-slider"><div class="layer-mini-slider-fill" style="width: 50%;"></div></div>
            </div>

            <div class="layer-item" onclick="toggleLayer('coverage', this)">
                <div class="layer-check"><svg viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></svg></div>
                <div class="layer-icon-circle" style="background: var(--layer-coverage);"></div>
                <div class="layer-info">
                    <div class="layer-name">Coverage Quality</div>
                    <div class="layer-desc">Triangle support</div>
                </div>
                <div class="layer-mini-slider"><div class="layer-mini-slider-fill" style="width: 50%;"></div></div>
            </div>

            <div class="layer-item active" onclick="toggleLayer('contours', this)">
                <div class="layer-check"><svg viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></svg></div>
                <div class="layer-icon-circle" style="background: var(--layer-contours);"></div>
                <div class="layer-info">
                    <div class="layer-name">Head Contours</div>
                    <div class="layer-desc">Isolines</div>
                </div>
            </div>

            <div class="layer-item" onclick="toggleLayer('vectors', this)">
                <div class="layer-check"><svg viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></svg></div>
                <div class="layer-icon-circle" style="background: var(--layer-vectors);"></div>
                <div class="layer-info">
                    <div class="layer-name">Gradient Vectors</div>
                    <div class="layer-desc">Flow direction</div>
                </div>
            </div>

            <div class="layer-item" onclick="toggleLayer('main_arrow', this)">
                <div class="layer-check"><svg viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></svg></div>
                <div class="layer-icon-circle" style="background: var(--layer-selection);"></div>
                <div class="layer-info">
                    <div class="layer-name">Main Direction Arrow</div>
                    <div class="layer-desc">Mean flow direction</div>
                </div>
            </div>
        </div>
    </div>
    <div class="floating-resize-handle" data-panel="layers"></div>
</div>

<!-- Scale Bar -->
<div class="map-scale">
    <div class="scale-bar"></div>
    <span>500 m</span>
</div>

<!-- Custom Legend -->
<div class="map-legend">
    <div class="legend-header">
        <div class="legend-title">Legend</div>
    </div>
    <div class="legend-section" id="legendSectionPoints">
        <div class="legend-section-title">Points</div>
        <div class="legend-item" id="legendItemActivePoint">
            <div class="legend-symbol" style="background: var(--layer-points); border: 2px solid var(--control-knob);"></div>
            <span class="legend-label" data-legend-key="active_point">Active Point</span>
        </div>
        <div class="legend-item" id="legendItemExcludedPoint">
            <div class="legend-symbol" style="background: var(--layer-excluded); border: 2px dashed var(--control-knob); opacity: 0.6;"></div>
            <span class="legend-label" data-legend-key="excluded_point">Excluded Point</span>
        </div>
        <div class="legend-item">
            <div class="legend-symbol" style="background: var(--layer-selection); box-shadow: 0 0 6px var(--layer-selection);"></div>
            <span class="legend-label" data-legend-key="selected_point">Selected</span>
        </div>
        <div class="legend-item" id="legendPointValueScale" style="display:none; flex-direction:column; align-items:stretch; gap:4px;">
            <span class="legend-label" data-legend-key="point_color_scale" style="opacity:0.9;">Head (Point Color)</span>
            <div class="legend-gradient" id="legendPointValueGradient"></div>
            <div class="legend-gradient-labels">
                <span id="legendPointValueMin">-</span>
                <span id="legendPointValueMax">-</span>
            </div>
        </div>
    </div>
    <div class="legend-section" id="legendSectionExternal" style="display:none;">
        <div class="legend-section-title">External Layers</div>
        <div class="legend-item">
            <div class="legend-symbol square" style="background: var(--layer-external);"></div>
            <span class="legend-label" id="legendExternalLabel">0 loaded (0 visible)</span>
        </div>
        <div class="legend-external-list" id="legendExternalList"></div>
    </div>
    <div class="legend-section" id="legendSectionHeatmap">
        <div class="legend-section-title">Rejection Rate</div>
        <div class="legend-gradient" style="background: linear-gradient(90deg, var(--success) 0%, var(--warning) 50%, var(--error) 100%);"></div>
        <div class="legend-gradient-labels">
            <span>Low</span>
            <span>High</span>
        </div>
    </div>
    <div class="legend-section" id="legendSectionContours">
        <div class="legend-section-title">Contours</div>
        <div class="legend-item">
            <div class="legend-symbol" style="width:18px;height:0;border-top:2px solid var(--layer-contours);border-radius:0;background:transparent;"></div>
            <span class="legend-label" data-legend-key="head_isoline">Head Isoline</span>
        </div>
        <div class="legend-item" id="legendContourFill" style="display:none; flex-direction:column; align-items:stretch; gap:4px;">
            <span class="legend-label" data-legend-key="filled_contours" style="opacity:0.9;">Filled Contours</span>
            <div class="legend-gradient" id="legendContourGradient"></div>
            <div class="legend-gradient-labels">
                <span id="legendContourMin">-</span>
                <span id="legendContourMax">-</span>
            </div>
        </div>
    </div>
    <div class="legend-section" id="legendSectionCoverage">
        <div class="legend-section-title">Coverage</div>
        <div class="legend-item">
            <div class="legend-symbol" style="background: var(--layer-coverage); opacity:0.7;"></div>
            <span class="legend-label" data-legend-key="triangle_support">Triangle Support</span>
        </div>
    </div>
    <div class="legend-section" id="legendSectionVectors">
        <div class="legend-section-title">Vectors</div>
        <div class="legend-item">
            <div class="legend-symbol" style="width:18px;height:0;border-top:2px solid var(--layer-vectors);border-radius:0;background:transparent;"></div>
            <span class="legend-label" data-legend-key="flow_direction">Flow Direction</span>
        </div>
        <div class="legend-item" id="legendItemMainArrow">
            <div class="legend-symbol" style="width:18px;height:0;border-top:3px solid var(--layer-selection);border-radius:0;background:transparent;"></div>
            <span class="legend-label" data-legend-key="main_direction">Main Direction Arrow</span>
        </div>
    </div>
    <div class="legend-section" id="legendSectionTransects" style="display:none;">
        <div class="legend-section-title">Transect Lines</div>
        <div class="transect-lines-list" id="transectLinesList">
            <div class="transect-lines-empty" id="transectLinesEmpty">
                No transects drawn yet.
            </div>
        </div>
    </div>
    <div class="floating-resize-handle" data-panel="legend"></div>
</div>

<!-- Coordinates -->
<div class="map-coords">
    <div class="coords-row">
        <div class="coord-item">
            <span class="coord-label">X</span>
            <span class="coord-value" id="coordsX">0</span>
        </div>
        <div class="coord-item">
            <span class="coord-label">Y</span>
            <span class="coord-value" id="coordsY">0</span>
        </div>
    </div>
</div>

<!-- Attribution -->
<div class="map-attribution">© OpenStreetMap contributors</div>

<!-- Custom Tooltip -->
<div class="point-tooltip" id="pointTooltip">
    <div class="tooltip-header">
        <span class="tooltip-id" id="tooltipId">BH-001</span>
        <span class="tooltip-status included" id="tooltipStatus">Included</span>
    </div>
    <div class="tooltip-row">
        <span class="tooltip-label">Hydraulic Head</span>
        <span class="tooltip-value" id="tooltipHead">45.23 m</span>
    </div>
    <div class="tooltip-row">
        <span class="tooltip-label">X (UTM)</span>
        <span class="tooltip-value" id="tooltipX">723,456</span>
    </div>
    <div class="tooltip-row">
        <span class="tooltip-label">Y (UTM)</span>
        <span class="tooltip-value" id="tooltipY">6,178,234</span>
    </div>
</div>

<!-- Geology Panel -->
<div class="geology-panel" id="geologyPanel" data-state="idle">
    <div class="geology-resize-handle" title="Drag to resize"></div>
    <div class="geology-header">
        <div class="geology-title">
            <svg viewBox="0 0 24 24" style="width:18px;height:18px;stroke:var(--text-primary);fill:none;stroke-width:2;"><line x1="5" y1="19" x2="19" y2="5"/><circle cx="5" cy="19" r="2"/><circle cx="19" cy="5" r="2"/></svg>
            Geology Cross-Section
        </div>
        <span class="geology-info" id="geologyInfo">Draw a transect to request a Geo.dk cross-section.</span>
        <span class="geology-status-pill" id="geoStatusPill" onclick="if(window.__haGeoDK && window.__haGeoDK.toggleStatusDetail) window.__haGeoDK.toggleStatusDetail();">
            <span class="status-icon icon-idle"><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2"><circle cx="8" cy="8" r="6"/></svg></span>
            <span class="status-icon icon-loading"><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2"><path d="M8 2v3M8 11v3M2 8h3M11 8h3"/></svg></span>
            <span class="status-icon icon-success"><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 8l4 4 6-8"/></svg></span>
            <span class="status-icon icon-warning"><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2"><path d="M8 3l6 10H2z"/><line x1="8" y1="7" x2="8" y2="9"/><circle cx="8" cy="11" r="0.5" fill="currentColor"/></svg></span>
            <span class="status-icon icon-error"><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2"><circle cx="8" cy="8" r="6"/><line x1="5" y1="5" x2="11" y2="11"/><line x1="11" y1="5" x2="5" y2="11"/></svg></span>
            <span id="geoStatusText">Idle</span>
            <svg class="status-expand" viewBox="0 0 10 10" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M2 4l3 3 3-3"/></svg>
            <div class="geology-status-detail" id="geoStatusDetail">Draw a transect to request a cross-section.</div>
        </span>
        <div class="geology-header-spacer"></div>
        <div class="geology-header-actions">
            <button class="geology-action" onclick="if(window.__haGeoDK && window.__haGeoDK.requestCredentials) window.__haGeoDK.requestCredentials();">Credentials</button>
            <button class="geology-action" onclick="if(window.__haGeoDK && window.__haGeoDK.fetchFromPanel) window.__haGeoDK.fetchFromPanel();">Fetch</button>
            <button class="geology-action" onclick="toggleGeologyPanel()">Collapse</button>
            <button class="geology-close" onclick="toggleGeologyPanel()">
                <svg viewBox="0 0 24 24"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            </button>
        </div>
    </div>
    <div class="geology-content">
        <div class="geology-main">
            <div class="geology-view">
                <div class="geology-view-toolbar">
                    <div class="seg" role="group" aria-label="Cross-section view mode">
                        <button class="active" id="geoFitBtn" onclick="if(window.__haGeoDK && window.__haGeoDK.setViewMode) window.__haGeoDK.setViewMode('fit');">Fit</button>
                        <button id="geo11Btn" onclick="if(window.__haGeoDK && window.__haGeoDK.setViewMode) window.__haGeoDK.setViewMode('11');">1:1</button>
                    </div>
                    <div class="geology-mini">
                        <span>Zoom</span>
                        <input type="range" min="60" max="180" value="100" id="geoZoomRange" oninput="if(window.__haGeoDK && window.__haGeoDK.setZoom) window.__haGeoDK.setZoom(this.value);" />
                        <span class="mono" id="geoZoomVal">100%</span>
                    </div>
                    <div class="spacer"></div>
                    <button class="geology-action" onclick="if(window.__haGeoDK && window.__haGeoDK.onDownload) window.__haGeoDK.onDownload();">Download</button>
                    <button class="geology-action" onclick="if(window.__haGeoDK && window.__haGeoDK.onCopyRepro) window.__haGeoDK.onCopyRepro();">Copy Repro</button>
                </div>

                <div class="geology-viewport-row">
                <div class="geology-viewport">
                    <!-- Real app: SVG is rendered as an <img> data URL to isolate Geo.dk CSS. -->
                    <img id="geologySvgImg" alt="Geo.dk cross section" />
                    <svg id="geologyOverlaySvg" class="geology-overlay" aria-hidden="true"></svg>
                    <div class="geology-empty" id="geoEmpty">Draw a transect to request a Geo.dk cross-section.</div>
                    <div class="geology-loading" id="geoLoading">Requesting Geo.dk cross-section...</div>
                </div>
                <div class="geology-inline-legend" id="geologyInlineLegend">
                    <div class="geology-inline-legend-header">Legend</div>
                    <div class="geology-inline-legend-content" id="geologyInlineLegendContent">
                        <div class="geology-inline-legend-empty">No legend loaded.</div>
                    </div>
                </div>
            </div>

                <div class="geology-metrics">
                    <div class="geo-metric"><div class="k">Model</div><div class="v" id="geoMetricModel">-</div></div>
                    <div class="geo-metric"><div class="k">Depth</div><div class="v" id="geoMetricDepth">-</div></div>
                    <div class="geo-metric"><div class="k">Polygons</div><div class="v" id="geoMetricPoly">-</div></div>
                    <div class="geo-metric"><div class="k">Path</div><div class="v" id="geoMetricPath">-</div></div>
                    <div class="geo-metric"><div class="k">Cache</div><div class="v" id="geoMetricCache">-</div></div>
                </div>
            </div>
        </div>

        <div class="geology-side">
            <div class="geology-side-tabs">
                <button class="geo-tab active" data-tab="request" onclick="if(window.__haGeoDK && window.__haGeoDK.setTab) window.__haGeoDK.setTab('request');">Request</button>
                <button class="geo-tab" data-tab="legend" onclick="if(window.__haGeoDK && window.__haGeoDK.setTab) window.__haGeoDK.setTab('legend');">Legend</button>
                <button class="geo-tab" data-tab="diag" onclick="if(window.__haGeoDK && window.__haGeoDK.setTab) window.__haGeoDK.setTab('diag');">Diagnostics</button>
            </div>

            <div class="geo-tabpanel active" data-tabpanel="request">
                <div class="geodk-form">
                    <div class="geodk-help">
                        Depth is “Level”: negative values go down (GeoAtlas/QGIS default is <b>-40</b>).
                        Model selection is bbox-filtered to avoid terrain-only output.
                    </div>

                    <div class="geodk-row">
                        <div class="lbl">Model</div>
                        <div class="ctl">
                            <input class="geodk-input" id="geodkModelFilter" placeholder="Filter models..." oninput="if(window.__haGeoDK && window.__haGeoDK.filterModels) window.__haGeoDK.filterModels(this.value);" />
                        </div>
                    </div>
                    <div class="geodk-row">
                        <div class="lbl">GeoModel</div>
                        <div class="ctl">
                            <select class="geodk-select" id="geodkModelSelect" onchange="if(window.__haGeoDK && window.__haGeoDK.onModelChanged) window.__haGeoDK.onModelChanged(this.value);"></select>
                        </div>
                    </div>

                    <div class="geodk-row">
                        <div class="lbl">Depth</div>
                        <div class="ctl geodk-inline">
                            <input id="geodkDepthRange" type="range" min="-200" max="200" value="-40" oninput="if(window.__haGeoDK && window.__haGeoDK.setDepth) window.__haGeoDK.setDepth(this.value);" />
                            <input class="geodk-input" style="width: 92px;" type="number" min="-200" max="200" value="-40" id="geodkDepthInput" oninput="if(window.__haGeoDK && window.__haGeoDK.setDepth) window.__haGeoDK.setDepth(this.value);" />
                        </div>
                    </div>

                    <div class="geodk-row">
                        <div class="lbl">Size</div>
                        <div class="ctl geodk-inline">
                            <input class="geodk-input" style="width: 110px;" type="number" min="200" max="4000" value="1000" id="geodkWidthInput" />
                            <span style="color: var(--text-muted); font-weight: 800;">×</span>
                            <input class="geodk-input" style="width: 110px;" type="number" min="120" max="2000" value="320" id="geodkHeightInput" />
                        </div>
                    </div>

                    <div class="geodk-row">
                        <div class="lbl">Sampling</div>
                        <div class="ctl geodk-inline">
                            <label style="display:flex;align-items:center;gap:8px;color:var(--text-secondary);font-size:10px;font-weight:800;">
                                <input id="geodkAutoLpdCheck" type="checkbox" checked />
                                Auto linepointdistance
                            </label>
                            <input class="geodk-input" style="width: 92px;" type="number" min="1" max="10000" value="2" id="geodkLpdInput" />
                        </div>
                    </div>

                    <div class="geodk-row">
                        <div class="lbl">Boreholes</div>
                        <div class="ctl geodk-inline">
                            <span style="color: var(--text-muted); font-weight: 800;">Tol (m)</span>
                            <input class="geodk-input" style="width: 92px;" type="number" min="0" max="500" value="10" id="geodkBoreTolInput" />
                        </div>
                    </div>

                    <div class="geodk-row">
                        <div class="lbl">Auto-Fetch</div>
                        <div class="ctl geodk-inline">
                            <div class="toggle-switch on" id="geodkAutoFetchToggle" onclick="if(window.__haGeoDK && window.__haGeoDK.toggleAutoFetch) window.__haGeoDK.toggleAutoFetch();">
                                <div class="toggle-knob"></div>
                            </div>
                            <span style="color: var(--text-muted); font-size: 9px;">On model/depth change</span>
                        </div>
                    </div>

                </div>
            </div>

            <div class="geo-tabpanel" data-tabpanel="legend">
                <div class="geology-legend" id="geodkLegend">
                    <div class="geology-legend-title">GeoUnits</div>
                    <div class="geology-legend-item"><span class="geology-legend-text">No legend loaded.</span></div>
                </div>
            </div>

            <div class="geo-tabpanel geodk-diag" data-tabpanel="diag">
                <div class="geodk-help">
                    The app writes a repro bundle for bug reports containing request params, selected model, depth,
                    SVG polygon count, normalized SVG, and borehole overlay mapping diagnostics (folder is rotated to keep it bounded).
                </div>
                <pre id="geodkDiagPre">{}</pre>
            </div>
        </div>
    </div>
</div>

<!-- External Layer Manager -->
<div class="layer-manager-backdrop" id="layerManagerBackdrop" onclick="onExternalLayerManagerBackdropClick(event)">
    <div class="layer-manager-dialog" role="dialog" aria-modal="true" aria-label="External Layer Manager">
        <div class="layer-manager-header">
            <div>
                <div class="layer-manager-title">External Layer Manager</div>
                <div class="layer-manager-subtitle">Browse loaded layers and apply geometry-aware styling.</div>
            </div>
            <button class="layer-manager-close" onclick="toggleExternalLayerDialog(false)" aria-label="Close">✕</button>
        </div>

        <div class="layer-manager-body">
            <div class="layer-manager-list" id="externalLayerList"></div>

            <div class="layer-manager-detail">
                <div class="layer-detail-title-row">
                    <div class="layer-detail-name" id="detailLayerName">-</div>
                    <div class="layer-geometry-badge" id="detailLayerGeometry">-</div>
                </div>

                <div class="layer-detail-grid">
                    <div class="layer-detail-card">
                        <div class="layer-detail-card-label">Source</div>
                        <div class="layer-detail-card-value" id="detailLayerSource">-</div>
                    </div>
                    <div class="layer-detail-card">
                        <div class="layer-detail-card-label">Features</div>
                        <div class="layer-detail-card-value" id="detailLayerFeatures">-</div>
                    </div>
                </div>

                <div class="layer-style-block">
                    <div class="layer-style-row">
                        <span class="layer-style-label">Color</span>
                        <input id="extStyleColor" class="layer-style-color" type="color" value="#22c55e" oninput="__onExternalStyleInput('color', this.value)" />
                    </div>

                    <div class="layer-style-row" id="extStyleLineWidthRow">
                        <span class="layer-style-label">Line Width</span>
                        <input id="extStyleLineWidth" class="layer-style-range" type="range" min="1" max="8" step="1" value="2" oninput="__onExternalStyleInput('line_width', this.value)" />
                        <span class="layer-style-value" id="extStyleLineWidthValue">2 px</span>
                    </div>

                    <div class="layer-style-row" id="extStyleLineOpacityRow">
                        <span class="layer-style-label">Line Opacity</span>
                        <input id="extStyleLineOpacity" class="layer-style-range" type="range" min="5" max="100" step="5" value="90" oninput="__onExternalStyleInput('line_opacity', this.value)" />
                        <span class="layer-style-value" id="extStyleLineOpacityValue">90%</span>
                    </div>

                    <div class="layer-style-row" id="extStyleFillOpacityRow">
                        <span class="layer-style-label">Fill Opacity</span>
                        <input id="extStyleFillOpacity" class="layer-style-range" type="range" min="0" max="100" step="5" value="12" oninput="__onExternalStyleInput('fill_opacity', this.value)" />
                        <span class="layer-style-value" id="extStyleFillOpacityValue">12%</span>
                    </div>

                    <div class="layer-style-row" id="extStylePointSizeRow">
                        <span class="layer-style-label">Point Size</span>
                        <input id="extStylePointSize" class="layer-style-range" type="range" min="2" max="24" step="1" value="8" oninput="__onExternalStyleInput('point_size', this.value)" />
                        <span class="layer-style-value" id="extStylePointSizeValue">8 px</span>
                    </div>
                </div>
            </div>
        </div>

        <div class="layer-manager-footer">
            <span class="layer-manager-note">Geometry-specific controls are shown based on the selected layer type.</span>
            <button class="layer-manage-btn" onclick="toggleExternalLayerDialog(false)">Done</button>
        </div>
    </div>
</div>
"""

CONCEPT_JS = """
<script>
    var map = null; // Will be set by finding the leaflet map object
    window.__sliderDragging = false;

    // Helper to find the map object
    function findMap() {
        if (map && typeof map.eachLayer === 'function') return map;
        // Prefer true Leaflet map instances when available.
        if (window.L && window.L.Map) {
            for (var k in window) {
                try {
                    var cand = window[k];
                    if (!cand) continue;
                    if (!(cand instanceof window.L.Map)) continue;
                    if (typeof cand.eachLayer === 'function' && typeof cand.getCenter === 'function') {
                        map = cand;
                        return map;
                    }
                } catch (err) {}
            }
        }
        // Fallback for embedded contexts where instanceof checks can fail.
        for (var i in window) {
            try {
                var obj = window[i];
                if (obj && typeof obj.eachLayer === 'function' && typeof obj.getCenter === 'function' &&
                    typeof obj.zoomIn === 'function' && typeof obj.zoomOut === 'function') {
                    map = obj;
                    return map;
                }
            } catch (err) {}
        }
        return map || null;
    }

    class Slider {
        constructor(id, min, max, initial, isInt, callback) {
            this.container = document.getElementById(id);
            if (!this.container) return;
            this.track = this.container.querySelector('.slider-track');
            this.fill = this.container.querySelector('.slider-fill');
            this.thumb = this.container.querySelector('.slider-thumb');
            this.valueDisplay = this.container.querySelector('.layer-setting-value');

            this.min = min;
            this.max = max;
            this.value = initial;
            this.isInt = isInt;
            this.callback = callback;
            this.isDragging = false;

            this.init();
        }

        init() {
            this.updateUI();
            // Pointer events are the most reliable path in QtWebEngine (mouse+touch unified)
            this.track.addEventListener('pointerdown', (e) => this.startDrag(e));
            this.thumb.addEventListener('pointerdown', (e) => this.startDrag(e));
            this.track.addEventListener('click', (e) => this.startDrag(e));
            this.thumb.addEventListener('click', (e) => this.startDrag(e));

            document.addEventListener('pointermove', (e) => this.onDrag(e), {passive:false});
            document.addEventListener('pointerup', () => this.stopDrag(), {passive:true});

            // Mouse fallback (some embedded engines still behave better on mouse events)
            this.track.addEventListener('mousedown', (e) => this.startDrag(e));
            this.thumb.addEventListener('mousedown', (e) => this.startDrag(e));
            document.addEventListener('mousemove', (e) => this.onDrag(e), {passive:false});
            document.addEventListener('mouseup', () => this.stopDrag(), {passive:true});

            // Touch fallback
            this.track.addEventListener('touchstart', (e) => this.startDrag(e), {passive:false});
            this.thumb.addEventListener('touchstart', (e) => this.startDrag(e), {passive:false});
            document.addEventListener('touchmove', (e) => this.onDrag(e), {passive:false});
            document.addEventListener('touchend', () => this.stopDrag(), {passive:true});
        }

        startDrag(e) {
            this.isDragging = true;
            window.__sliderDragging = true;
            this.updateFromEvent(e);
            e.preventDefault();
            if (e.stopPropagation) e.stopPropagation();
            if (e.stopImmediatePropagation) e.stopImmediatePropagation();
        }

        onDrag(e) {
            if (!this.isDragging) return;
            e.preventDefault();
            this.updateFromEvent(e);
        }

        stopDrag() {
            if (this.isDragging) {
                this.isDragging = false;
                window.__sliderDragging = false;
                if (this.callback) this.callback(this.value);
            }
        }

        updateFromEvent(e) {
            const rect = this.track.getBoundingClientRect();
            let clientX = e.clientX;
            if ((clientX === undefined || clientX === null) && e.touches && e.touches.length) {
                clientX = e.touches[0].clientX;
            }
            if (clientX === undefined || clientX === null) return;
            let x = clientX - rect.left;
            let pct = Math.max(0, Math.min(1, x / rect.width));

            this.value = this.min + pct * (this.max - this.min);
            if (this.isInt) this.value = Math.round(this.value);

            this.updateUI();
        }

        updateUI() {
            const pct = (this.value - this.min) / (this.max - this.min) * 100;
            this.fill.style.width = pct + '%';
            this.thumb.style.left = pct + '%';

            let text = '';
            if (!this.isInt) {
                text = Math.round(this.value * 100) + '%';
            } else {
                text = Math.round(this.value) + 'px';
            }
            if (this.valueDisplay) this.valueDisplay.innerText = text;
        }
    }

    function __clamp(v, lo, hi) {
        return Math.max(lo, Math.min(hi, v));
    }

    function __setMapDragEnabled(enabled) {
        try {
            if (!map || !map.dragging) return;
            if (enabled) map.dragging.enable();
            else map.dragging.disable();
        } catch (err) {}
    }

    function __persistPanelState(key, state) {
        try {
            localStorage.setItem(key, JSON.stringify(state));
        } catch (err) {}
    }

    function __loadPanelState(key) {
        try {
            var raw = localStorage.getItem(key);
            return raw ? JSON.parse(raw) : null;
        } catch (err) {
            return null;
        }
    }

    function __makeFloatingPanel(panelSelector, dragSelector, storageKey, minW, minH) {
        var panel = document.querySelector(panelSelector);
        if (!panel || panel.__floatingBound) return;
        panel.__floatingBound = true;
        var dragEl = panel.querySelector(dragSelector) || panel;
        var resizeEl = panel.querySelector('.floating-resize-handle');

        var rect = panel.getBoundingClientRect();
        panel.style.left = rect.left + 'px';
        panel.style.top = rect.top + 'px';
        panel.style.right = 'auto';
        panel.style.bottom = 'auto';
        panel.style.width = Math.round(rect.width) + 'px';
        panel.style.height = Math.round(rect.height) + 'px';

        var stored = __loadPanelState(storageKey);
        if (stored && typeof stored === 'object') {
            if (isFinite(stored.left)) panel.style.left = Math.round(stored.left) + 'px';
            if (isFinite(stored.top)) panel.style.top = Math.round(stored.top) + 'px';
            if (isFinite(stored.width)) panel.style.width = Math.round(Math.max(minW, stored.width)) + 'px';
            if (isFinite(stored.height)) panel.style.height = Math.round(Math.max(minH, stored.height)) + 'px';
        }

        var startX = 0, startY = 0, startL = 0, startT = 0, startW = 0, startH = 0;
        var moving = false;
        var resizing = false;

        var stopAll = function() {
            if (!moving && !resizing) return;
            var wasResizing = resizing;
            moving = false;
            resizing = false;
            panel.classList.remove('panel-moving');
            __setMapDragEnabled(true);
            if (wasResizing) {
                panel.__userResized = true;
            }
            __persistPanelState(storageKey, {
                left: panel.offsetLeft,
                top: panel.offsetTop,
                width: panel.offsetWidth,
                height: panel.offsetHeight
            });
        };

        var onMove = function(e) {
            if (!moving && !resizing) return;
            var cx = e.clientX;
            var cy = e.clientY;
            if (cx === undefined || cx === null || cy === undefined || cy === null) return;
            if (moving) {
                var l = startL + (cx - startX);
                var t = startT + (cy - startY);
                var maxL = Math.max(8, window.innerWidth - panel.offsetWidth - 8);
                var maxT = Math.max(8, window.innerHeight - panel.offsetHeight - 8);
                panel.style.left = __clamp(l, 8, maxL) + 'px';
                panel.style.top = __clamp(t, 8, maxT) + 'px';
            } else if (resizing) {
                var w = startW + (cx - startX);
                var h = startH + (cy - startY);
                panel.style.width = __clamp(w, minW, Math.max(minW, window.innerWidth - panel.offsetLeft - 8)) + 'px';
                panel.style.height = __clamp(h, minH, Math.max(minH, window.innerHeight - panel.offsetTop - 8)) + 'px';
            }
            if (e.preventDefault) e.preventDefault();
        };

        document.addEventListener('pointermove', onMove, {passive:false});
        document.addEventListener('pointerup', stopAll, {passive:true});
        document.addEventListener('mousemove', onMove, {passive:false});
        document.addEventListener('mouseup', stopAll, {passive:true});

        dragEl.addEventListener('mousedown', function(e) {
            var t = e.target;
            if (t && (t.closest('button') || t.closest('input') || t.closest('select') || t.closest('[contenteditable=\"true\"]'))) return;
            moving = true;
            resizing = false;
            startX = e.clientX; startY = e.clientY;
            startL = panel.offsetLeft; startT = panel.offsetTop;
            panel.classList.add('panel-moving');
            __setMapDragEnabled(false);
            if (e.preventDefault) e.preventDefault();
            if (e.stopPropagation) e.stopPropagation();
        });

        if (resizeEl) {
            resizeEl.addEventListener('mousedown', function(e) {
                resizing = true;
                moving = false;
                startX = e.clientX; startY = e.clientY;
                startW = panel.offsetWidth; startH = panel.offsetHeight;
                panel.classList.add('panel-moving');
                __setMapDragEnabled(false);
                if (e.preventDefault) e.preventDefault();
                if (e.stopPropagation) e.stopPropagation();
            });
        }
    }

    function __ensureLayersFitsContent(forceFit) {
        var panel = document.querySelector('.map-layers-panel');
        var header = panel ? panel.querySelector('.layers-header') : null;
        var body = panel ? panel.querySelector('.layers-body') : null;
        if (!panel || !header || !body) return;
        if (panel.classList.contains('collapsed')) return;
        var maxH = Math.max(170, window.innerHeight - 16);
        var needed = Math.ceil(header.offsetHeight + body.scrollHeight + 8);
        var target = __clamp(needed, 170, maxH);
        panel.style.minHeight = '170px';
        var shouldFit = !!forceFit || !panel.__userResized;
        if (shouldFit && panel.offsetHeight < target) {
            panel.style.height = target + 'px';
        }
        if (panel.offsetTop + panel.offsetHeight > window.innerHeight - 8) {
            panel.style.top = Math.max(8, window.innerHeight - panel.offsetHeight - 8) + 'px';
        }
    }

    function __ensureLegendFitsContent(forceFit) {
        var panel = document.querySelector('.map-legend');
        var header = panel ? panel.querySelector('.legend-header') : null;
        if (!panel || !header) return;
        var maxH = Math.max(180, window.innerHeight - 16);
        panel.style.minHeight = '180px';
        panel.style.maxHeight = maxH + 'px';

        var shouldFit = !!forceFit || !panel.__userResized;
        if (shouldFit) {
            // Natural-fit mode: panel tracks content both up and down.
            panel.style.height = 'auto';
            var needed = Math.ceil(panel.scrollHeight + 8);
            var target = __clamp(needed, 180, maxH);
            if (Math.abs(panel.offsetHeight - target) > 1) {
                panel.style.height = target + 'px';
            }
        } else if (panel.offsetHeight > maxH) {
            // Respect manual resize, but keep panel inside viewport.
            panel.style.height = maxH + 'px';
        }
        if (panel.offsetTop + panel.offsetHeight > window.innerHeight - 8) {
            panel.style.top = Math.max(8, window.innerHeight - panel.offsetHeight - 8) + 'px';
        }
    }

    function __initLegendAutoFit() {
        var panel = document.querySelector('.map-legend');
        if (!panel || panel.__legendAutoFitInit) return;
        panel.__legendAutoFitInit = true;
        var obs = new MutationObserver(function() {
            __ensureLegendFitsContent(false);
        });
        obs.observe(panel, {
            childList: true,
            subtree: true,
            characterData: true
        });
    }

    function __setLayersCollapsed(collapsed) {
        var panel = document.querySelector('.map-layers-panel');
        if (!panel) return;
        var isCollapsed = !!collapsed;
        panel.classList.toggle('collapsed', isCollapsed);
        try { localStorage.setItem('ha_map_panel_layers_collapsed', isCollapsed ? '1' : '0'); } catch (err) {}
        if (!isCollapsed) {
            __ensureLayersFitsContent(false);
        }
    }

    function __initLayersCollapsedState() {
        var raw = null;
        try { raw = localStorage.getItem('ha_map_panel_layers_collapsed'); } catch (err) { raw = null; }
        __setLayersCollapsed(raw === '1');
    }

    function __initLegendRenaming() {
        if (window.__legendRenameInit) return;
        window.__legendRenameInit = true;

        var storageKey = 'ha_map_legend_labels';
        var saved = {};
        try {
            saved = JSON.parse(localStorage.getItem(storageKey) || '{}') || {};
        } catch (err) { saved = {}; }

        document.querySelectorAll('.map-legend .legend-label[data-legend-key]').forEach(function(lbl) {
            var key = String(lbl.getAttribute('data-legend-key') || '').trim();
            if (!key) return;
            if (!lbl.getAttribute('data-default-legend')) {
                lbl.setAttribute('data-default-legend', String(lbl.textContent || '').trim());
            }
            if (saved[key]) lbl.textContent = String(saved[key]);

            var finishEdit = function(commit) {
                lbl.removeAttribute('contenteditable');
                lbl.blur();
                var next = String(lbl.textContent || '').trim();
                if (!commit || !next) {
                    lbl.textContent = saved[key] ? String(saved[key]) : next || lbl.getAttribute('data-default-text') || '';
                    return;
                }
                saved[key] = next;
                try { localStorage.setItem(storageKey, JSON.stringify(saved)); } catch (err) {}
            };

            lbl.addEventListener('dblclick', function(e) {
                lbl.setAttribute('data-default-text', String(lbl.textContent || ''));
                lbl.setAttribute('contenteditable', 'true');
                lbl.focus();
                try { document.execCommand('selectAll', false, null); } catch (err) {}
                if (e.preventDefault) e.preventDefault();
                if (e.stopPropagation) e.stopPropagation();
            });
            lbl.addEventListener('keydown', function(e) {
                if (e.key === 'Enter') {
                    finishEdit(true);
                    if (e.preventDefault) e.preventDefault();
                } else if (e.key === 'Escape') {
                    finishEdit(false);
                    if (e.preventDefault) e.preventDefault();
                }
            });
            lbl.addEventListener('blur', function() { finishEdit(true); });
        });
    }

    function resetOverlayLayout() {
        try {
            localStorage.removeItem('ha_map_panel_layers');
            localStorage.removeItem('ha_map_panel_legend');
            localStorage.removeItem('ha_map_legend_labels');
            localStorage.removeItem('ha_map_panel_layers_collapsed');
        } catch (err) {}

        var layers = document.querySelector('.map-layers-panel');
        if (layers) {
            layers.classList.remove('collapsed');
            layers.__userResized = false;
            layers.style.left = '';
            layers.style.top = '';
            layers.style.right = '12px';
            layers.style.bottom = 'auto';
            layers.style.width = '216px';
            layers.style.height = 'auto';
            layers.style.minHeight = '170px';
        }
        var legend = document.querySelector('.map-legend');
        if (legend) {
            legend.__userResized = false;
            legend.style.left = '292px';
            legend.style.top = '80px';
            legend.style.right = 'auto';
            legend.style.bottom = 'auto';
            legend.style.width = '248px';
            legend.style.height = 'auto';
            legend.style.minHeight = '180px';
        }

        document.querySelectorAll('.map-legend .legend-label[data-legend-key]').forEach(function(lbl) {
            var d = lbl.getAttribute('data-default-legend');
            if (d) lbl.textContent = d;
        });

        // Re-bind defaults in floating layout engine and enforce fit.
        try {
            if (layers) layers.__floatingBound = false;
            if (legend) legend.__floatingBound = false;
            __makeFloatingPanel('.map-layers-panel', '.layers-header', 'ha_map_panel_layers', 180, 170);
            __makeFloatingPanel('.map-legend', '.legend-header', 'ha_map_panel_legend', 196, 180);
            __initLayersCollapsedState();
            __ensureLayersFitsContent(true);
            __ensureLegendFitsContent(true);
        } catch (err) {}
    }

    function __initMapUiOnce() {
        if (window.__mapUiInited) return;
        window.__mapUiInited = true;
        setTimeout(function() {
            findMap();
            if (map) {
                // Prevent map drag from stealing slider/property interactions.
                var prop = document.querySelector('.properties');
                if (prop && map.dragging) {
                    var disableDrag = function(e){
                        try { map.dragging.disable(); } catch(err){}
                        if (e && e.stopPropagation) e.stopPropagation();
                    };
                    var enableDrag = function(){ try { map.dragging.enable(); } catch(err){} };

                    prop.addEventListener('mouseenter', disableDrag);
                    prop.addEventListener('mouseleave', enableDrag);
                    prop.addEventListener('mousedown', disableDrag);
                    prop.addEventListener('touchstart', disableDrag, {passive:false});
                    document.addEventListener('mouseup', enableDrag);
                    document.addEventListener('touchend', enableDrag, {passive:true});
                }

                // Hook up map events for coordinates
                map.on('mousemove', function(e) {
                     if (window.__sliderDragging) return;
                     var lat = e.latlng.lat.toFixed(4);
                     var lng = e.latlng.lng.toFixed(4);
                     document.getElementById('coordsX').innerText = lng;
                     document.getElementById('coordsY').innerText = lat;
                });

                map.on('click', function(e) {
                    if (window.__sliderDragging) return;
                    // When the transect tool is enabled, map clicks are owned by that tool.
                    // Avoid clearing selection/target capture while the user is picking A->B.
                    if (window.__haTransect && window.__haTransect.enabled) return;
                    try {
                        var t = e && e.originalEvent ? e.originalEvent.target : null;
                        var cls = '';
                        if (t && typeof t.className === 'string') cls = t.className;
                        else if (t && t.className && typeof t.className.baseVal === 'string') cls = t.className.baseVal;
                        else if (t && t.getAttribute) cls = t.getAttribute('class') || '';
                        if (String(cls).indexOf('point-marker') !== -1) return;
                    } catch (err) {}

                    if (window.pyBridge && e && e.latlng) {
                        try {
                            window.pyBridge.onMapClick(Number(e.latlng.lat), Number(e.latlng.lng));
                        } catch (err) {}
                    }
                });
            }

            __makeFloatingPanel('.map-layers-panel', '.layers-header', 'ha_map_panel_layers', 180, 170);
            __makeFloatingPanel('.map-legend', '.legend-header', 'ha_map_panel_legend', 196, 180);
            __initLegendRenaming();
            __initLegendAutoFit();
            __initLayersCollapsedState();
            __ensureLayersFitsContent(true);
            __ensureLegendFitsContent(true);
            window.addEventListener('resize', function() {
                __ensureLayersFitsContent(false);
                __ensureLegendFitsContent(false);
            });

            // Initialize Sliders from current map UI state (if provided by Python).
            var uiState = window.__mapUiState || {};
            var contourState = window.__mapContourState || {};
            var opacityInit = (typeof uiState.heatmap_opacity === 'number') ? uiState.heatmap_opacity : 0.5;
            var pointSizeInit = (typeof uiState.point_size === 'number') ? uiState.point_size : 8;
            var heatmapModeInit = (typeof uiState.heatmap_mode === 'string') ? uiState.heatmap_mode : 'smooth';
            var pointLabelsInit = !!uiState.point_labels;
            var contourLabelsInit = (typeof contourState.show_labels === 'boolean') ? contourState.show_labels : true;
            var contourPrecisionInit = (typeof contourState.label_precision === 'number') ? contourState.label_precision : 2;
            var contourMajorInit = (typeof contourState.major_interval === 'number') ? contourState.major_interval : 2;
            var pointColorByValueInit = !!uiState.point_color_by_value;
            var opR = document.getElementById('opacityRange');
            var psR = document.getElementById('pointSizeRange');
            var cmR = document.getElementById('contourMajorRange');
            if (opR) opR.value = String(Math.round(opacityInit * 100));
            if (psR) psR.value = String(Math.round(pointSizeInit));
            if (cmR) cmR.value = String(Math.round(contourMajorInit));
            function bindNativeSlider(opts) {
                var wrap = document.getElementById(opts.wrapId);
                var range = document.getElementById(opts.rangeId);
                if (!wrap || !range) return;
                var fill = wrap.querySelector('.slider-fill');
                var thumb = wrap.querySelector('.slider-thumb');
                var valueEl = wrap.querySelector('.layer-setting-value');
                var min = Number(range.min);
                var max = Number(range.max);
                var toPct = function(v){ return ((v - min) / (max - min)) * 100; };
                var redraw = function(v){
                    var pct = Math.max(0, Math.min(100, toPct(v)));
                    if (fill) fill.style.width = pct + '%';
                    if (thumb) thumb.style.left = pct + '%';
                    if (valueEl) valueEl.innerText = opts.format(v);
                };
                range.value = String(opts.initial);
                redraw(Number(opts.initial));
            }

            bindNativeSlider({
                wrapId: 'opacitySlider',
                rangeId: 'opacityRange',
                initial: Math.round(opacityInit * 100),
                format: function(v){ return String(v) + '%'; }
            });

            bindNativeSlider({
                wrapId: 'pointSizeSlider',
                rangeId: 'pointSizeRange',
                initial: Math.round(pointSizeInit),
                format: function(v){ return String(v) + 'px'; }
            });

            bindNativeSlider({
                wrapId: 'contourMajorSlider',
                rangeId: 'contourMajorRange',
                initial: Math.round(contourMajorInit),
                format: function(v){ return String(v); }
            });

            // Initialize heatmap mode buttons
            window.setHeatmapMode(heatmapModeInit, null, true);
            var contourToggle = document.getElementById('contourLabelsToggle');
            if (contourToggle) contourToggle.classList.toggle('on', !!contourLabelsInit);
            var pointLabelsToggle = document.getElementById('labelsToggle');
            if (pointLabelsToggle) pointLabelsToggle.classList.toggle('on', !!pointLabelsInit);
            window.__pointLabelsVisible = !!pointLabelsInit;
            if (window.__applyPointLabelVisibility) window.__applyPointLabelVisibility();
            var pointColorToggle = document.getElementById('pointColorToggle');
            if (pointColorToggle) pointColorToggle.classList.toggle('on', !!pointColorByValueInit);
            if (window.__applyPointColorMode) window.__applyPointColorMode(!!pointColorByValueInit);
            var prec = document.getElementById('contourPrecisionSelect');
            if (prec) prec.value = String(Math.max(0, Math.min(3, Math.round(contourPrecisionInit))));
            var contourInfo = document.getElementById('contourConfigInfo');
            if (contourInfo) {
                var m = String(contourState.method || '-');
                var lv = String((contourState.levels !== undefined && contourState.levels !== null) ? contourState.levels : '-');
                var ex = String((contourState.extent_pct !== undefined && contourState.extent_pct !== null) ? contourState.extent_pct : '-');
                var ep = String(contourState.extrapolation || '-');
                contourInfo.innerText = 'Method ' + m + ', Levels ' + lv + ', Extent ' + ex + '%, Extrapolation ' + ep;
            }
            if (window.__applyContourMajorInterval) window.__applyContourMajorInterval(Math.round(contourMajorInit));
            if (window.__setMapLayerState && window.__mapLayerState) {
                window.__setMapLayerState(window.__mapLayerState);
            }

        }, 200);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', __initMapUiOnce);
    } else {
        __initMapUiOnce();
    }

    function toggleGeologyPanel() {
        var panel = document.getElementById('geologyPanel');
        if (panel) panel.classList.toggle('visible');
    }

    // Geo.dk panel runtime (viewer + request controls)
    window.__haGeoDK = window.__haGeoDK || (function(){
        var st = {
            models: [],
            geomodelid: null,
            maxdepth: -40,
            width: 1000,
            height: 320,
            auto_lpd: true,
            linepointdistance: 2,
            borehole_tolerance_m: 10,
            zoom_pct: 100,
            view_mode: 'fit',
            last_repro_path: '',
            auto_fetch: true,
            _debounce_timer: null
        };

        // Debounce utility (800ms delay for auto-fetch)
        function debounce(fn, delay) {
            return function() {
                var args = arguments;
                if (st._debounce_timer) clearTimeout(st._debounce_timer);
                st._debounce_timer = setTimeout(function() {
                    st._debounce_timer = null;
                    fn.apply(null, args);
                }, delay || 800);
            };
        }

        var debouncedFetch = debounce(function() {
            if (st.auto_fetch && st.geomodelid !== null) {
                fetchFromPanel();
            }
        }, 800);

        function _el(id){ return document.getElementById(id); }
        function _setText(id, txt){ try{ var e=_el(id); if(e) e.textContent=String(txt||''); }catch(err){} }
        function _setState(state, pillText, statusBox, detailText){
            try{
                var panel=_el('geologyPanel');
                if(panel) panel.setAttribute('data-state', String(state||'idle'));
                _setText('geoStatusText', pillText || '');
                if (detailText !== undefined) _setText('geoStatusDetail', detailText || '');
                // Collapse detail popup on state change
                var pill=_el('geoStatusPill');
                if(pill) pill.classList.remove('expanded');
            }catch(err){}
        }

        function toggleStatusDetail(){
            try{
                var pill=_el('geoStatusPill');
                if(pill) pill.classList.toggle('expanded');
            }catch(err){}
        }

        function setTab(tab){
            try{
                var tabs = Array.prototype.slice.call(document.querySelectorAll('.geo-tab'));
                var panels = Array.prototype.slice.call(document.querySelectorAll('.geo-tabpanel'));
                tabs.forEach(function(t){ t.classList.toggle('active', String(t.getAttribute('data-tab')) === String(tab)); });
                panels.forEach(function(p){ p.classList.toggle('active', String(p.getAttribute('data-tabpanel')) === String(tab)); });
            }catch(err){}
        }

        function setViewMode(mode){
            st.view_mode = String(mode||'fit');
            try{
                var fitBtn=_el('geoFitBtn'); var oneBtn=_el('geo11Btn');
                if(fitBtn) fitBtn.classList.toggle('active', st.view_mode === 'fit');
                if(oneBtn) oneBtn.classList.toggle('active', st.view_mode === '11');
                var img=_el('geologySvgImg');
                if(img) img.style.objectFit = (st.view_mode === '11') ? 'none' : 'contain';
            }catch(err){}
        }

        function setZoom(v){
            try{
                var pct = Math.max(60, Math.min(180, Math.round(Number(v)||100)));
                st.zoom_pct = pct;
                _setText('geoZoomVal', String(pct) + '%');
                var img=_el('geologySvgImg');
                if(img) img.style.transform = 'scale(' + String(pct/100.0) + ')';
            }catch(err){}
        }

        function setDepth(v){
            var n = Math.max(-200, Math.min(200, Math.round(Number(v)||-40)));
            st.maxdepth = n;
            try{
                var inp=_el('geodkDepthInput'); if(inp) inp.value = String(n);
                var rng=_el('geodkDepthRange'); if(rng) rng.value = String(n);
                _setText('geoMetricDepth', String(n));
            }catch(err){}
            // Trigger auto-fetch on depth change
            debouncedFetch();
        }

        function onModelChanged(v){
            try{
                var n = Number(v);
                st.geomodelid = isFinite(n) ? Math.round(n) : null;
                // Update metric text from selected option label.
                var sel=_el('geodkModelSelect');
                if(sel && sel.selectedOptions && sel.selectedOptions.length){
                    _setText('geoMetricModel', sel.selectedOptions[0].textContent || '-');
                }
            }catch(err){}
            // Trigger auto-fetch on model change
            debouncedFetch();
        }

        function setAutoFetch(enabled){
            st.auto_fetch = !!enabled;
            try{
                var toggle=_el('geodkAutoFetchToggle');
                if(toggle) {
                    toggle.classList.toggle('on', st.auto_fetch);
                }
            }catch(err){}
        }

        function toggleAutoFetch(){
            setAutoFetch(!st.auto_fetch);
        }

        function filterModels(q){
            try{
                var needle = String(q||'').trim().toLowerCase();
                var sel=_el('geodkModelSelect'); if(!sel) return;
                Array.prototype.slice.call(sel.options).forEach(function(opt){
                    var txt = String(opt.textContent||'').toLowerCase();
                    opt.hidden = needle ? (txt.indexOf(needle) === -1) : false;
                });
            }catch(err){}
        }

        function setModels(models, opts){
            try{
                var list = Array.isArray(models) ? models : [];
                st.models = list;
                var sel=_el('geodkModelSelect');
                if(sel){
                    sel.innerHTML = '';
                    list.forEach(function(m){
                        try{
                            var id = (m && (m.ID !== undefined)) ? m.ID : (m && (m.Id !== undefined)) ? m.Id : (m && (m.id !== undefined)) ? m.id : null;
                            var name = (m && (m.Name !== undefined)) ? m.Name : (m && (m.name !== undefined)) ? m.name : '';
                            if(id === null || id === undefined) return;
                            var idStr = String(id);
                            var optEl = document.createElement('option');
                            optEl.value = idStr;
                            optEl.textContent = String(name||'Model') + ' (ID ' + idStr + ')';
                            sel.appendChild(optEl);
                        }catch(err){}
                    });
                }
                // Default selection: prefer first non -1 model if available.
                var desired = (opts && opts.geomodelid !== undefined && opts.geomodelid !== null) ? String(opts.geomodelid) : '';
                if(sel){
                    if(desired) sel.value = desired;
                    if(!sel.value && sel.options && sel.options.length){
                        var picked = null;
                        for(var i=0;i<sel.options.length;i++){
                            if(String(sel.options[i].value) !== '-1'){ picked = sel.options[i].value; break; }
                        }
                        sel.value = picked || sel.options[0].value;
                    }
                }
                onModelChanged(sel ? sel.value : null);

                // Depth/size defaults
                if(opts && opts.maxdepth !== undefined && opts.maxdepth !== null) setDepth(opts.maxdepth);
                if(opts && opts.width !== undefined && opts.width !== null){ st.width = Math.round(Number(opts.width)||1000); var w=_el('geodkWidthInput'); if(w) w.value=String(st.width); }
                if(opts && opts.height !== undefined && opts.height !== null){ st.height = Math.round(Number(opts.height)||320); var h=_el('geodkHeightInput'); if(h) h.value=String(st.height); }
                if(opts && opts.borehole_tolerance_m !== undefined && opts.borehole_tolerance_m !== null){
                    var t = Number(opts.borehole_tolerance_m);
                    if(!isFinite(t) || t < 0) t = 10;
                    st.borehole_tolerance_m = t;
                    var bt=_el('geodkBoreTolInput'); if(bt) bt.value = String(t);
                }
                if(opts && opts.path_m !== undefined && opts.path_m !== null) _setText('geoMetricPath', String(Math.round(Number(opts.path_m)||0)) + ' m');
                if(opts && opts.cache_hit !== undefined && opts.cache_hit !== null) _setText('geoMetricCache', (opts.cache_hit ? 'HIT' : 'MISS'));

                _setState('ready', 'Ready', 'Models loaded. Adjust settings and click Fetch.');
            }catch(err){}
        }

        function setLegendHtml(html){
            try{
                var content = String(html||'');
                // Update hidden tab panel (backwards compat)
                var el=_el('geodkLegend');
                if(el) el.innerHTML = content;
                // Update inline legend next to viewport
                var inline=_el('geologyInlineLegendContent');
                if(inline) {
                    if(content && content.trim()) {
                        inline.innerHTML = content;
                    } else {
                        inline.innerHTML = '<div class="geology-inline-legend-empty">No legend loaded yet.</div>';
                    }
                }
            }catch(err){}
        }

        function setDiagJson(obj){
            try{
                var pre=_el('geodkDiagPre');
                if(!pre) return;
                pre.textContent = JSON.stringify(obj || {}, null, 2);
            }catch(err){}
        }

        function setSvgDataUrl(dataUrl){
            try{
                var img=_el('geologySvgImg');
                if(img) img.src = String(dataUrl||'');
                // Clear overlay whenever a new cross-section is shown.
                var ov=_el('geologyOverlaySvg');
                if(ov) ov.innerHTML = '';
                _setState('ready', 'Ready');
            }catch(err){}
        }

        function setBoreholesOverlay(items, viewbox){
            try{
                var ov=_el('geologyOverlaySvg');
                if(!ov) return;
                var list = Array.isArray(items) ? items : [];
                var vb = (viewbox && typeof viewbox === 'object') ? viewbox : null;
                if(vb && isFinite(Number(vb.w)) && isFinite(Number(vb.h))){
                    ov.setAttribute('viewBox', '0 0 ' + String(Number(vb.w)) + ' ' + String(Number(vb.h)));
                    ov.setAttribute('preserveAspectRatio', 'xMinYMin meet');
                }
                ov.innerHTML = '';

                for(var i=0;i<list.length;i++){
                    var it=list[i]||{};
                    var x=Number(it.x), y1=Number(it.y1), y2=Number(it.y2);
                    if(!isFinite(x) || !isFinite(y1) || !isFinite(y2)) continue;
                    var label = (it.label !== undefined && it.label !== null) ? String(it.label) : '';
                    var yTop = Math.min(y1,y2), yBot = Math.max(y1,y2);

                    // Thin line (surface -> bottom)
                    var ln = document.createElementNS('http://www.w3.org/2000/svg','line');
                    ln.setAttribute('x1', String(x));
                    ln.setAttribute('x2', String(x));
                    ln.setAttribute('y1', String(yTop));
                    ln.setAttribute('y2', String(yBot));
                    ln.setAttribute('class','bh-line');
                    ov.appendChild(ln);

                    // Optional "screen" segment (top->bottom) if provided.
                    if(it.screen && isFinite(Number(it.screen.y1)) && isFinite(Number(it.screen.y2))){
                        var s1=Number(it.screen.y1), s2=Number(it.screen.y2);
                        var sn = document.createElementNS('http://www.w3.org/2000/svg','line');
                        sn.setAttribute('x1', String(x));
                        sn.setAttribute('x2', String(x));
                        sn.setAttribute('y1', String(Math.min(s1,s2)));
                        sn.setAttribute('y2', String(Math.max(s1,s2)));
                        sn.setAttribute('class','bh-screen');
                        ov.appendChild(sn);
                    }

                    // Small cap at surface.
                    var cap = document.createElementNS('http://www.w3.org/2000/svg','line');
                    cap.setAttribute('x1', String(x-3.5));
                    cap.setAttribute('x2', String(x+3.5));
                    cap.setAttribute('y1', String(yTop));
                    cap.setAttribute('y2', String(yTop));
                    cap.setAttribute('class','bh-cap');
                    ov.appendChild(cap);

                    if(label){
                        var tx = document.createElementNS('http://www.w3.org/2000/svg','text');
                        tx.setAttribute('x', String(x+5));
                        tx.setAttribute('y', String(Math.max(0, yTop-4)));
                        tx.setAttribute('class','bh-label');
                        tx.textContent = label;
                        ov.appendChild(tx);
                    }
                }
            }catch(err){}
        }

        function fetchFromPanel(){
            try{
                var sel=_el('geodkModelSelect');
                var depth=_el('geodkDepthInput');
                var w=_el('geodkWidthInput');
                var h=_el('geodkHeightInput');
                var auto=_el('geodkAutoLpdCheck');
                var lpd=_el('geodkLpdInput');
                var bt=_el('geodkBoreTolInput');
                var geomodelid = sel && sel.value ? Number(sel.value) : null;
                var maxdepth = depth ? Number(depth.value) : -40;
                var width = w ? Number(w.value) : 1000;
                var height = h ? Number(h.value) : 320;
                var auto_lpd = auto ? !!auto.checked : true;
                var linepointdistance = lpd ? Number(lpd.value) : 2;
                var borehole_tolerance_m = bt ? Number(bt.value) : 10;
                if(geomodelid === null || !isFinite(geomodelid)){
                    _setState('error', 'Error', 'Pick a model first.');
                    return;
                }
                if(!isFinite(maxdepth)) maxdepth = -40;
                if(!isFinite(width) || width<=0) width = 1000;
                if(!isFinite(height) || height<=0) height = 320;
                if(!isFinite(linepointdistance) || linepointdistance<=0) linepointdistance = 2;
                if(!isFinite(borehole_tolerance_m) || borehole_tolerance_m < 0) borehole_tolerance_m = 10;
                _setState('loading', 'Loading', 'Requesting Geo.dk cross-section...');
                if(window.pyBridge && window.pyBridge.onGeoDKFetchRequested){
                    window.pyBridge.onGeoDKFetchRequested(JSON.stringify({
                        geomodelid: Math.round(geomodelid),
                        maxdepth: Math.round(maxdepth),
                        width: Math.round(width),
                        height: Math.round(height),
                        auto_linepointdistance: !!auto_lpd,
                        linepointdistance: Math.round(linepointdistance),
                        borehole_tolerance_m: Number(borehole_tolerance_m)
                    }));
                }
            }catch(err){}
        }

        function requestCredentials(){
            try{
                if(window.pyBridge && window.pyBridge.onGeoDKCredentialsRequested){
                    window.pyBridge.onGeoDKCredentialsRequested();
                }
            }catch(err){}
        }

        function onDownload(){
            // Concept hook: Python can handle this later (open file / export repro).
            try{
                if(window.pyBridge && window.pyBridge.onGeoDKDownloadRequested){
                    window.pyBridge.onGeoDKDownloadRequested();
                }
            }catch(err){}
        }

        function onCopyRepro(){
            // Concept hook: Python can handle copying repro path to clipboard.
            try{
                if(window.pyBridge && window.pyBridge.onGeoDKCopyReproRequested){
                    window.pyBridge.onGeoDKCopyReproRequested();
                }
            }catch(err){}
        }

        // Resizable drawer init (drag handle)
        (function initResize(){
            try{
                var panel = _el('geologyPanel');
                if(!panel) return;
                var handle = panel.querySelector('.geology-resize-handle');
                if(!handle) return;
                var dragging=false, startY=0, startH=0;
                function down(e){
                    dragging=true;
                    startY = (e.touches && e.touches.length) ? e.touches[0].clientY : e.clientY;
                    startH = panel.getBoundingClientRect().height;
                    document.body.style.userSelect='none';
                }
                function move(e){
                    if(!dragging) return;
                    var y = (e.touches && e.touches.length) ? e.touches[0].clientY : e.clientY;
                    var dy = startY - y;
                    var next = Math.max(180, Math.min(window.innerHeight*0.7, startH + dy));
                    panel.style.height = String(Math.round(next)) + 'px';
                }
                function up(){
                    dragging=false;
                    document.body.style.userSelect='';
                }
                handle.addEventListener('mousedown', down);
                document.addEventListener('mousemove', move);
                document.addEventListener('mouseup', up);
                handle.addEventListener('touchstart', down, {passive:true});
                document.addEventListener('touchmove', move, {passive:true});
                document.addEventListener('touchend', up);
            }catch(err){}
        })();

        // Public API used by Python-side MapWidget methods.
        return {
            state: st,
            setTab: setTab,
            setViewMode: setViewMode,
            setZoom: setZoom,
            setDepth: setDepth,
            onModelChanged: onModelChanged,
            filterModels: filterModels,
            fetchFromPanel: fetchFromPanel,
            requestCredentials: requestCredentials,
            onDownload: onDownload,
            onCopyRepro: onCopyRepro,
            toggleStatusDetail: toggleStatusDetail,
            setAutoFetch: setAutoFetch,
            toggleAutoFetch: toggleAutoFetch,
            __setState: _setState,
            __setModels: setModels,
            __setLegendHtml: setLegendHtml,
            __setSvgDataUrl: setSvgDataUrl,
            __setDiagJson: setDiagJson,
            __setBoreholesOverlay: setBoreholesOverlay
        };
    })();

    function toggleLayersPanel() {
        var panel = document.querySelector('.map-layers-panel');
        if (!panel) return;
        __setLayersCollapsed(!panel.classList.contains('collapsed'));
    }

    function toggleLayer(layerName, element) {
        var current = !!(element && element.classList.contains('active'));
        var nextValue = !current;
        var state = window.__mapLayerState || {};
        state[layerName] = nextValue;
        if (window.__setMapLayerState) {
            window.__setMapLayerState(state);
        } else {
            if (element) element.classList.toggle('active', nextValue);
        }
        if (window.pyBridge) {
            window.pyBridge.onLayerToggled(layerName, !!nextValue);
        }
    }

    // Transect Lines management in Legend panel
    window.__updateTransectLinesPanel = function(transects, activeId) {
        var list = document.getElementById('transectLinesList');
        var empty = document.getElementById('transectLinesEmpty');
        var section = document.getElementById('legendSectionTransects');
        if (!list) return;
        var items = Array.isArray(transects) ? transects : [];
        // Show/hide the entire section based on whether we have transects
        if (section) section.style.display = items.length > 0 ? 'block' : 'none';
        // Clear existing items (keep empty placeholder)
        var existing = list.querySelectorAll('.transect-line-item');
        existing.forEach(function(el) { el.remove(); });
        if (items.length === 0) {
            if (empty) empty.style.display = 'block';
            return;
        }
        if (empty) empty.style.display = 'none';
        items.forEach(function(t) {
            var el = document.createElement('div');
            el.className = 'transect-line-item' + (t.visible !== false ? ' visible' : '') + (String(t.id) === String(activeId) ? ' selected' : '');
            el.setAttribute('data-transect-id', String(t.id || ''));
            el.innerHTML = '<div class="transect-line-check" onclick="event.stopPropagation(); window.__toggleTransectVisibility(\\''+String(t.id)+'\\');"><svg viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></svg></div>' +
                '<div class="transect-line-color" style="background:' + String(t.color || '#f472b6') + ';"></div>' +
                '<div class="transect-line-info">' +
                    '<div class="transect-line-name">' + String(t.name || 'Transect') + '</div>' +
                    '<div class="transect-line-desc">' + String(t.desc || '') + '</div>' +
                '</div>' +
                '<div class="transect-line-actions">' +
                    '<button class="transect-line-btn" title="Rename" onclick="event.stopPropagation(); window.__renameTransect(\\''+String(t.id)+'\\');"><svg viewBox="0 0 24 24"><path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/></svg></button>' +
                    '<button class="transect-line-btn delete" title="Delete" onclick="event.stopPropagation(); window.__deleteTransect(\\''+String(t.id)+'\\');"><svg viewBox="0 0 24 24"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></button>' +
                '</div>';
            el.onclick = function() { window.__selectTransect(String(t.id)); };
            list.appendChild(el);
        });
    };
    window.__toggleTransectVisibility = function(transectId) {
        if (window.pyBridge && window.pyBridge.onTransectVisibilityToggled) {
            window.pyBridge.onTransectVisibilityToggled(String(transectId));
        }
    };
    window.__selectTransect = function(transectId) {
        if (window.pyBridge && window.pyBridge.onTransectSelected) {
            window.pyBridge.onTransectSelected(String(transectId));
        }
    };
    window.__renameTransect = function(transectId) {
        var el = document.querySelector('.transect-line-item[data-transect-id="'+transectId+'"] .transect-line-name');
        if (!el) return;
        var current = el.textContent || '';
        var input = document.createElement('input');
        input.type = 'text';
        input.value = current;
        el.innerHTML = '';
        el.appendChild(input);
        input.focus();
        input.select();
        function commit() {
            var newName = (input.value || '').trim() || current;
            el.textContent = newName;
            if (window.pyBridge && window.pyBridge.onTransectRenamed) {
                window.pyBridge.onTransectRenamed(String(transectId), newName);
            }
        }
        input.onblur = commit;
        input.onkeydown = function(e) {
            if (e.key === 'Enter') { e.preventDefault(); input.blur(); }
            if (e.key === 'Escape') { el.textContent = current; }
        };
    };
    window.__deleteTransect = function(transectId) {
        if (window.pyBridge && window.pyBridge.onTransectDeleted) {
            window.pyBridge.onTransectDeleted(String(transectId));
        }
    };

    if (typeof window.toggleExternalLayerDialog !== 'function') {
        window.toggleExternalLayerDialog = function(forceOpen) {
            var backdrop = document.getElementById('layerManagerBackdrop');
            if (!backdrop) return;
            if (forceOpen === true) backdrop.classList.add('open');
            else if (forceOpen === false) backdrop.classList.remove('open');
            else backdrop.classList.toggle('open');
        };
    }
    if (typeof window.onExternalLayerManagerBackdropClick !== 'function') {
        window.onExternalLayerManagerBackdropClick = function(event) {
            var backdrop = document.getElementById('layerManagerBackdrop');
            if (!backdrop) return;
            if (event && event.target === backdrop) window.toggleExternalLayerDialog(false);
        };
    }
    if (typeof window.__onExternalStyleInput !== 'function') {
        window.__onExternalStyleInput = function() {};
    }
    window.__mapOnOpacityInput = function(v) {
        try {
            var val = Number(v);
            var el = document.getElementById('opacityValue');
            if (el) el.innerText = String(Math.round(val)) + '%';
            var wrap = document.getElementById('opacitySlider');
            if (wrap) {
                var fill = wrap.querySelector('.slider-fill');
                var thumb = wrap.querySelector('.slider-thumb');
                if (fill) fill.style.width = String(val) + '%';
                if (thumb) thumb.style.left = String(val) + '%';
            }
            if (window.pyBridge) window.pyBridge.onOpacityChanged(val / 100.0);
        } catch (err) {}
    };

    window.__applyPointRadius = function(px) {
        try {
            var val = Number(px);
            if (!isFinite(val)) return;
            val = Math.max(2, Math.min(32, val));
            if (!map) findMap();
            if (!map || !map.eachLayer) return;
            var selectedIdx = (window.__selectedPointIdx === undefined || window.__selectedPointIdx === null)
                ? null : String(window.__selectedPointIdx);

            map.eachLayer(function(layer){
                try {
                    if (!layer || typeof layer.setRadius !== 'function' || !layer.options) return;
                    var cls = '';
                    if (layer._path && layer._path.getAttribute) {
                        cls = String(layer._path.getAttribute('class') || '');
                    }
                    if (!cls) cls = String(layer.options.className || '');
                    var hasPointClass = cls.indexOf('point-marker') !== -1;
                    if (!hasPointClass && layer._path && layer._path.classList) {
                        hasPointClass = layer._path.classList.contains('point-marker');
                    }
                    if (!hasPointClass) return;

                    var isExcluded = cls.indexOf('excluded') !== -1;
                    var radius = val;
                    var idxMatch = cls.match(/point-idx-([^\\s]+)/);
                    if ((!idxMatch || !idxMatch[1]) && layer._path) {
                        var pathCls = String(layer._path.getAttribute('class') || '');
                        idxMatch = pathCls.match(/point-idx-([^\\s]+)/);
                    }
                    var idx = idxMatch ? idxMatch[1] : null;
                    if (!isExcluded && selectedIdx && idx && idx === selectedIdx) {
                        radius = val * 1.5;
                    }
                    layer.setRadius(radius);
                } catch (err) {}
            });
        } catch (err) {}
    };

    window.__mapOnPointSizeInput = function(v) {
        try {
            var val = Number(v);
            var el = document.getElementById('pointSizeValue');
            if (el) el.innerText = String(Math.round(val)) + 'px';
            var wrap = document.getElementById('pointSizeSlider');
            if (wrap) {
                var fill = wrap.querySelector('.slider-fill');
                var thumb = wrap.querySelector('.slider-thumb');
                var pct = ((val - 2) / (32 - 2)) * 100.0;
                if (fill) fill.style.width = String(pct) + '%';
                if (thumb) thumb.style.left = String(pct) + '%';
            }
            if (window.__applyPointRadius) window.__applyPointRadius(val);
        } catch (err) {}
    };

    window.__mapCommitPointSize = function(v) {
        try {
            var val = Number(v);
            if (window.__mapOnPointSizeInput) window.__mapOnPointSizeInput(val);
            if (window.pyBridge) window.pyBridge.onPointSizeChanged(Math.round(val));
        } catch (err) {}
    };

    window.__mapOnContourMajorInput = function(v) {
        try {
            var val = Number(v);
            var el = document.getElementById('contourMajorValue');
            if (el) el.innerText = String(Math.round(val));
            var wrap = document.getElementById('contourMajorSlider');
            if (wrap) {
                var fill = wrap.querySelector('.slider-fill');
                var thumb = wrap.querySelector('.slider-thumb');
                var pct = ((val - 1) / (8 - 1)) * 100.0;
                if (fill) fill.style.width = String(pct) + '%';
                if (thumb) thumb.style.left = String(pct) + '%';
            }
            if (window.__applyContourMajorInterval) window.__applyContourMajorInterval(Math.round(val));
        } catch (err) {}
    };

    window.__mapCommitContourMajor = function(v) {
        try {
            var val = Math.max(1, Math.min(8, Number(v)));
            if (window.__mapOnContourMajorInput) window.__mapOnContourMajorInput(val);
            if (window.pyBridge) window.pyBridge.onContourMajorIntervalChanged(Math.round(val));
        } catch (err) {}
    };

    window.__applyContourMajorInterval = function(everyN) {
        try {
            var n = Math.max(1, Math.min(8, Number(everyN)));
            var labelsOn = true;
            var toggle = document.getElementById('contourLabelsToggle');
            if (toggle) labelsOn = toggle.classList.contains('on');
            var contourNodes = document.querySelectorAll('.overlay-contours');
            contourNodes.forEach(function(node){
                var cls = String(node.getAttribute('class') || '');
                var m = cls.match(/contour-level-(\\d+)/);
                if (!m) return;
                var li = Number(m[1]);
                var isMajor = (li % n) === 0;
                node.style.strokeWidth = isMajor ? '2.4' : '0.9';
                node.setAttribute('stroke-width', isMajor ? '2.4' : '0.9');
                node.style.opacity = isMajor ? '0.92' : '0.30';
                node.setAttribute('opacity', isMajor ? '0.92' : '0.30');
            });

            var labelNodes = document.querySelectorAll('.contour-line-label');
            labelNodes.forEach(function(node){
                var cls = String(node.getAttribute('class') || '');
                var m = cls.match(/contour-level-label-(\\d+)/);
                if (!m) return;
                var li = Number(m[1]);
                var isMajor = (li % n) === 0;
                node.style.display = (labelsOn && isMajor) ? '' : 'none';
            });
        } catch (err) {}
    };

    window.toggleScaleBar = function(el) {
        el.classList.toggle('on');
        var isOn = el.classList.contains('on');
        if (window.pyBridge) window.pyBridge.onScaleBarToggled(isOn);
    };

    window.toggleSync = function(el) {
        el.classList.toggle('on');
        var isOn = el.classList.contains('on');
        if (window.pyBridge) window.pyBridge.onSyncSelectionToggled(isOn);
    };

    window.togglePointLabels = function(el) {
        el.classList.toggle('on');
        var isOn = el.classList.contains('on');
        window.__pointLabelsVisible = !!isOn;
        if (window.__applyPointLabelVisibility) window.__applyPointLabelVisibility();
        else {
            document.querySelectorAll('.point-id-label').forEach(function(node){
                node.style.display = isOn ? 'block' : 'none';
            });
        }
        if (window.pyBridge) window.pyBridge.onLabelsToggled(isOn);
    };

    window.togglePointColorByValue = function(el) {
        el.classList.toggle('on');
        var isOn = el.classList.contains('on');
        if (window.__applyPointColorMode) window.__applyPointColorMode(isOn);
        if (window.pyBridge) window.pyBridge.onPointColorByValueToggled(isOn);
    };

    window.toggleContourLabels = function(el) {
        el.classList.toggle('on');
        var isOn = el.classList.contains('on');
        if (window.pyBridge) window.pyBridge.onContourLabelsToggled(isOn);
    };

    window.setContourLabelPrecision = function(v) {
        try {
            var val = Math.max(0, Math.min(3, Number(v)));
            if (window.pyBridge) window.pyBridge.onContourLabelPrecisionChanged(Math.round(val));
        } catch (err) {}
    };

    window.setHeatmapMode = function(mode, btn, silent) {
        var wrap = document.getElementById('heatmapModeToggle');
        if (wrap) {
            wrap.querySelectorAll('.mode-btn').forEach(function(b){
                b.classList.toggle('active', b.getAttribute('data-mode') === mode);
            });
        }
        if (!silent && window.pyBridge) window.pyBridge.onHeatmapModeChanged(mode);
    };

    // Tooltip logic
    var tooltip = document.getElementById('pointTooltip');

    window.showTooltip = function(data) {
        if (!tooltip) return;
        document.getElementById('tooltipId').innerText = data.id;
        document.getElementById('tooltipStatus').innerText = data.status;
        document.getElementById('tooltipStatus').className = 'tooltip-status ' + data.status.toLowerCase();
        document.getElementById('tooltipHead').innerText = data.head ? data.head.toFixed(2) + ' m' : '-';
        document.getElementById('tooltipX').innerText = data.x.toFixed(1);
        document.getElementById('tooltipY').innerText = data.y.toFixed(1);

        tooltip.classList.add('visible');
    }

    window.hideTooltip = function() {
        if (tooltip) tooltip.classList.remove('visible');
    }

    window.moveTooltip = function(e) {
        if (!tooltip) return;
        var x = (e && e.clientX !== undefined) ? Number(e.clientX) : 0;
        var y = (e && e.clientY !== undefined) ? Number(e.clientY) : 0;
        var pad = 10;
        var w = tooltip.offsetWidth || 180;
        var h = tooltip.offsetHeight || 80;
        var left = x + 14;
        var top = y - h - 10;
        if (left + w + pad > window.innerWidth) left = x - w - 14;
        if (top < pad) top = y + 14;
        left = Math.max(pad, Math.min(left, window.innerWidth - w - pad));
        top = Math.max(pad, Math.min(top, window.innerHeight - h - pad));
        tooltip.style.left = left + 'px';
        tooltip.style.top = top + 'px';
    }

</script>
"""
