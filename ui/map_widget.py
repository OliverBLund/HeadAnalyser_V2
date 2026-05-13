"""
HeadAnalyser V2 - Map Widget (Render Surface + JS Bridge).

This module owns map rendering and in-place JS updates. It receives a canonical
MapPayload from MainWindow and decides whether to:
- apply a fast in-place update (no full HTML rebuild), or
- do a full rerender when required by overlay state/payload changes.

Contract rule:
- Callers should refresh map state through `MainWindow._update_map_view(...)`,
  which dispatches `MapWidget.update_map(**payload)`.
"""

import numpy as np
import pyproj
import json
import os
import re
import tempfile
import base64
from pathlib import Path
from core.contour_engine import compute_contour_grid

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox,
    QLabel, QFrame, QPushButton, QSizePolicy, QShortcut,
    QFileDialog, QMessageBox
)
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineSettings, QWebEnginePage
from PyQt5.QtWebChannel import QWebChannel
from PyQt5.QtCore import Qt, pyqtSignal, QUrl, QByteArray
from PyQt5.QtGui import QKeySequence, QIcon, QPixmap
from PyQt5.QtSvg import QSvgRenderer

from styles.colors import Colors
from ui.theme_utils import reset_widget_layout
from .map import MapBridge, MAP_COLORS, MAP_TILE_PROVIDERS, initialize_map_widget_state
from .map.point_labels import (
    build_apply_points_visibility_js,
    build_point_label_contract_js,
    build_set_labels_visibility_js,
)
from .map.contours import (
    build_replace_dynamic_contours_js,
    build_set_contour_layers_visible_js,
)
from .map.heatmap import build_replace_dynamic_heatmap_js
from .map.analysis_overlays import (
    build_replace_dynamic_coverage_js,
    build_replace_dynamic_vectors_js,
)
from .map.layers_runtime import build_layers_runtime_js
from .map.legend_runtime import build_legend_runtime_js
from .map.points_runtime import build_points_runtime_js
from .map.triangle_overlay import build_replace_triangle_overlay_js
from .map.table_drawer import MapTableDrawer
from .map.map_payload_builder import MapPayloadBuilder
from .map.map_runtime_renderer import MapRuntimeRenderer
from .map.map_interaction_controller import MapInteractionController
from .map.external_layers import (
    ExternalLayerError,
    build_external_layer_style,
    load_external_layer_payload,
    normalize_external_layer_style,
)
from .dialogs.external_layer_manager import ExternalLayerManagerDialog


# ═══════════════════════════════════════════════════════════════════
#  MAP PAYLOAD CONTRACT
#  Canonical data shape passed from MainWindow → MapWidget.update_map().
#  All callers MUST assemble this dict from the active Dataset object.
#  See Dataset class (core/dataset.py) for the source fields.
# ═══════════════════════════════════════════════════════════════════
#
#   MapPayload = {
#       'data':          pd.DataFrame,       # filtered_plot_data (includes excluded rows)
#       'col_mapping':   dict,               # {'ID': str, 'x': str, 'y': str, 'hydraulic head': str}
#       'excluded_ids':  set,                # IDs currently excluded from analysis
#       'triangle_data': pd.DataFrame | None,# kept triangles (from gradient calc)
#       'gradient_data': pd.DataFrame | None,# gradient vectors for overlay
#       'rejected_data': pd.DataFrame | None,# rejected triangles (for heatmap)
#   }
#
# ═══════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════
#  TOOLBAR ICONS (inline SVG)
# ═══════════════════════════════════════════════════════════════════

TOOLBAR_ICONS = {
    "transect": """<svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
        <line x1="3" y1="14" x2="15" y2="4"/>
        <circle cx="3" cy="14" r="2" fill="currentColor" stroke="none"/>
        <circle cx="15" cy="4" r="2" fill="currentColor" stroke="none"/>
        <text x="1" y="11" font-size="4" font-weight="700" fill="currentColor" stroke="none">A</text>
        <text x="13" y="16" font-size="4" font-weight="700" fill="currentColor" stroke="none">B</text>
    </svg>""",
    "measure": """<svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
        <line x1="2" y1="16" x2="16" y2="16"/>
        <line x1="2" y1="14" x2="2" y2="16"/>
        <line x1="16" y1="14" x2="16" y2="16"/>
        <line x1="5" y1="15" x2="5" y2="16"/>
        <line x1="9" y1="14" x2="9" y2="16"/>
        <line x1="13" y1="15" x2="13" y2="16"/>
        <text x="7" y="10" font-size="6" font-weight="700" fill="currentColor" stroke="none">m</text>
    </svg>""",
    "add_point": """<svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="9" cy="9" r="6"/>
        <circle cx="9" cy="9" r="2"/>
        <line x1="9" y1="1" x2="9" y2="4"/>
        <line x1="9" y1="14" x2="9" y2="17"/>
        <line x1="1" y1="9" x2="4" y2="9"/>
        <line x1="14" y1="9" x2="17" y2="9"/>
    </svg>""",
    "layers": """<svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
        <path d="M9 2L2 6l7 4 7-4-7-4z"/>
        <path d="M2 10l7 4 7-4"/>
        <path d="M2 14l7 4 7-4"/>
    </svg>""",
    "geology": """<svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
        <path d="M2 4c2 1 4-1 6 0s4-1 6 0"/>
        <path d="M2 8c2 1.5 4-0.5 6 1s4-1.5 6 0"/>
        <path d="M2 12c2 0.5 4-1 6 0.5s4-0.5 6 0.5"/>
        <path d="M2 16h14"/>
    </svg>""",
    "export": """<svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
        <path d="M9 2v10"/>
        <path d="M5 8l4 4 4-4"/>
        <path d="M2 14v2h14v-2"/>
    </svg>""",
}


def _svg_to_icon(svg_str: str, size: int = 16, color: str = None) -> QIcon:
    """Convert an SVG string to a QIcon with optional color replacement."""
    svg = svg_str.strip()
    if color:
        svg = svg.replace('currentColor', color)
    else:
        svg = svg.replace('currentColor', Colors.TEXT_SECONDARY)

    data = QByteArray(svg.encode('utf-8'))
    renderer = QSvgRenderer(data)

    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)

    from PyQt5.QtGui import QPainter
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()

    return QIcon(pixmap)


class MapToolbar(QFrame):
    """Toolbar for map controls matching the concept design."""

    tileChanged = pyqtSignal(str)
    layerToggled = pyqtSignal(str, bool)
    fitBoundsRequested = pyqtSignal()
    exportRequested = pyqtSignal(str)
    transectModeChanged = pyqtSignal(bool)
    geologyPanelRequested = pyqtSignal()
    addPointModeChanged = pyqtSignal(bool)
    externalLayerManagerRequested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        self.setObjectName("mapToolbar")
        # Concepts style for toolbar
        self.setStyleSheet(f"""
            #mapToolbar {{
                background: {Colors.BG_PANEL};
                border-bottom: 1px solid {Colors.BORDER_DEFAULT};
                padding: 8px 14px;
            }}
            QLabel {{
                font-size: 10px; font-weight: 600; color: {Colors.TEXT_TERTIARY};
                text-transform: uppercase; letter-spacing: 0.8px;
            }}
            QComboBox {{
                font-family: 'Segoe UI', sans-serif; font-size: 11px; font-weight: 500;
                color: {Colors.TEXT_PRIMARY}; background: {Colors.BG_SURFACE};
                border: 1px solid {Colors.BORDER_MEDIUM}; border-radius: 6px;
                padding: 4px 10px; min-width: 140px;
            }}
            QComboBox:hover {{ border-color: {Colors.ACCENT_PRIMARY}; }}
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: center right;
                width: 20px;
                border: none;
                background-color: transparent;
            }}
            QComboBox::down-arrow {{
                width: 8px; height: 8px; image: none;
                border-left: 3px solid transparent;
                border-right: 3px solid transparent;
                border-top: 4px solid {Colors.TEXT_MUTED};
            }}
            QComboBox::down-arrow:hover {{
                border-top-color: {Colors.ACCENT_PRIMARY};
            }}
            
            QPushButton {{
                font-family: 'Segoe UI', sans-serif; font-size: 11px; font-weight: 600;
                color: {Colors.TEXT_SECONDARY}; background: {Colors.BG_SURFACE};
                border: 1px solid {Colors.BORDER_MEDIUM}; border-radius: 6px;
                padding: 5px 10px 5px 8px;
                icon-size: 14px;
            }}
            QPushButton:hover {{
                color: {Colors.ACCENT_PRIMARY}; border-color: {Colors.BORDER_ACCENT};
                background: {Colors.ACCENT_GHOST};
            }}
            QPushButton:checked {{
                color: {Colors.TEXT_ACCENT}; border-color: {Colors.BORDER_ACCENT};
                background: {Colors.OVERLAY_ACTIVE};
            }}
            QPushButton:checked:hover {{
                color: {Colors.ACCENT_PRIMARY}; border-color: {Colors.ACCENT_PRIMARY};
                background: {Colors.OVERLAY_FOCUS};
            }}
            QPushButton:disabled {{
                color: {Colors.TEXT_MUTED}; background: {Colors.BG_WELL};
                border-color: {Colors.BORDER_SUBTLE};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # Tile selector
        tile_label = QLabel("Tiles")
        layout.addWidget(tile_label)

        self.tile_combo = QComboBox()
        self.tile_combo.addItems([
            "OpenStreetMap",
            "CartoDB Positron",
            "CartoDB Dark Matter",
            "Esri World Imagery"
        ])
        self.tile_combo.currentTextChanged.connect(self.tileChanged.emit)
        layout.addWidget(self.tile_combo)

        # Separator
        layout.addWidget(self._create_separator())

        # Transect tool button
        self.transect_btn = QPushButton("Draw Transect")
        self.transect_btn.setIcon(_svg_to_icon(TOOLBAR_ICONS["transect"]))
        self.transect_btn.setCheckable(True)
        self.transect_btn.setToolTip("Draw a transect line for geology cross-section")
        self.transect_btn.toggled.connect(self.transectModeChanged.emit)
        layout.addWidget(self.transect_btn)

        # Measure button (Placeholder)
        self.measure_btn = QPushButton("Measure")
        self.measure_btn.setIcon(_svg_to_icon(TOOLBAR_ICONS["measure"]))
        self.measure_btn.setToolTip("Measure distance")
        layout.addWidget(self.measure_btn)

        self.add_point_btn = QPushButton("Add Point")
        self.add_point_btn.setIcon(_svg_to_icon(TOOLBAR_ICONS["add_point"]))
        self.add_point_btn.setToolTip("Toggle point creation mode")
        self.add_point_btn.setCheckable(True)
        self.add_point_btn.toggled.connect(self.addPointModeChanged.emit)
        layout.addWidget(self.add_point_btn)

        layout.addStretch()

        # Geology Panel Toggle
        self.geology_btn = QPushButton("Geology")
        self.geology_btn.setIcon(_svg_to_icon(TOOLBAR_ICONS["geology"]))
        self.geology_btn.setToolTip("Toggle Geology Cross-Section Panel")
        self.geology_btn.clicked.connect(self.geologyPanelRequested.emit)
        layout.addWidget(self.geology_btn)

        self.external_layers_btn = QPushButton("Layers")
        self.external_layers_btn.setIcon(_svg_to_icon(TOOLBAR_ICONS["layers"]))
        self.external_layers_btn.setToolTip("Manage loaded external GeoJSON / Shapefile overlays")
        self.external_layers_btn.clicked.connect(self.externalLayerManagerRequested.emit)
        layout.addWidget(self.external_layers_btn)

        # Export button
        export_btn = QPushButton("Export")
        export_btn.setIcon(_svg_to_icon(TOOLBAR_ICONS["export"]))
        export_btn.setToolTip("Export map")
        export_btn.clicked.connect(lambda: self.exportRequested.emit("html"))
        layout.addWidget(export_btn)

    def _create_separator(self):
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setStyleSheet(f"background: {Colors.BORDER_MEDIUM}; margin: 2px 4px;")
        sep.setFixedWidth(1)
        sep.setFixedHeight(24)
        return sep

    def apply_theme(self):
        current_tile = self.tile_combo.currentText() if hasattr(self, "tile_combo") else "OpenStreetMap"
        transect_checked = self.transect_btn.isChecked() if hasattr(self, "transect_btn") else False
        add_point_checked = self.add_point_btn.isChecked() if hasattr(self, "add_point_btn") else False

        reset_widget_layout(self)

        self._setup_ui()
        self.tile_combo.blockSignals(True)
        self.transect_btn.blockSignals(True)
        self.add_point_btn.blockSignals(True)
        self.tile_combo.setCurrentText(current_tile)
        self.transect_btn.setChecked(bool(transect_checked))
        self.add_point_btn.setChecked(bool(add_point_checked))
        self.tile_combo.blockSignals(False)
        self.transect_btn.blockSignals(False)
        self.add_point_btn.blockSignals(False)


class MapWebPage(QWebEnginePage):
    """Web page with JS console forwarding for runtime diagnostics."""

    def javaScriptConsoleMessage(self, level, message, line_number, source_id):
        try:
            src = str(source_id or "")
            msg = str(message or "")
            print(f"[map-js-console] level={int(level)} line={int(line_number)} src={src} msg={msg}")
        except Exception:
            pass
        super().javaScriptConsoleMessage(level, message, line_number, source_id)


class MapWidget(QWidget):
    """
    Widget for displaying interactive map with data points and analysis layers.

    Event Contract (outgoing signals):
        pointSelected(str)      - Emitted when user clicks a data point on the map.
                                  Payload: the point's ID string (from col_mapping['ID']).
        transectCreated(list)   - Emitted when user finishes drawing a transect line.
                                  Payload: list of [lat, lon] coordinate pairs.

    Internal bridge signals (MapBridge → MapWidget, not for external consumers):
        bridge.pointClicked     - JS click → _on_point_clicked() → pointSelected
        bridge.pointHovered     - JS hover → _on_point_hovered() (tooltip only)
        bridge.mapClicked       - JS map click (deselect)
        bridge.layerToggled     - JS layer panel → set_layer_visibility()
        bridge.transectDrawn    - JS transect → transectCreated

    Data contract:
        Callers update the map via update_map(**MapPayload). See MapPayload
        contract comment block at the top of this file.
    """

    # Signals
    pointSelected = pyqtSignal(str)  # Emits point ID when selected
    pointDeselected = pyqtSignal()   # Emits when selection is cleared
    transectCreated = pyqtSignal(list)  # Emits transect coordinates
    pointExcludeRequested = pyqtSignal(str)
    pointShowInPlotRequested = pyqtSignal(str)
    contourSettingsRequested = pyqtSignal()
    mapLocationClicked = pyqtSignal(float, float)  # Emits clicked map lat, lon
    addPointModeChanged = pyqtSignal(bool)
    geodkFetchRequested = pyqtSignal(str)  # JSON payload from Geo.dk panel
    geodkCredentialsRequested = pyqtSignal()
    geodkDownloadRequested = pyqtSignal()
    geodkCopyReproRequested = pyqtSignal()

    # Layer colors matching the concept
    COLORS = MAP_COLORS

    # Tile providers
    TILE_PROVIDERS = MAP_TILE_PROVIDERS

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        initialize_map_widget_state(self)
        self._payload_builder = MapPayloadBuilder(self)
        self._runtime_renderer = MapRuntimeRenderer(self)
        self._interaction_controller = MapInteractionController(self)

        self._setup_ui()
        self._setup_bridge()
        self._setup_shortcuts()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Toolbar
        self.toolbar = MapToolbar()
        self.toolbar.tileChanged.connect(self._on_tile_changed)
        self.toolbar.fitBoundsRequested.connect(self._fit_bounds)
        self.toolbar.exportRequested.connect(self._export_map)
        self.toolbar.transectModeChanged.connect(self._set_transect_mode)
        self.toolbar.geologyPanelRequested.connect(self.toggle_geology_panel)
        self.toolbar.addPointModeChanged.connect(self.addPointModeChanged.emit)
        self.toolbar.externalLayerManagerRequested.connect(self._open_external_layer_manager_dialog)
        layout.addWidget(self.toolbar)

        # Map view
        self.web_view = QWebEngineView()
        self.web_view.setPage(MapWebPage(self.web_view))
        self.web_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # Configure settings for local storage and access
        settings = self.web_view.page().settings()
        settings.setAttribute(QWebEngineSettings.LocalStorageEnabled, True)
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        
        # Enable developer extras for debugging if needed
        # settings.setAttribute(QWebEngineSettings.DeveloperExtrasEnabled, True)
        
        layout.addWidget(self.web_view)
        self.web_view.loadFinished.connect(self._on_webview_load_finished)

        # Bottom drawer table (map-context data/triangle tables).
        self._table_drawer = MapTableDrawer(self.main_window, parent=self)
        self._table_drawer.tableRowSelected.connect(self._on_table_row_selected_local)
        self._table_drawer.tableRowsSelected.connect(self._on_table_rows_selected_local)
        self._table_drawer.tableRowDeselected.connect(self.clear_selected_point)
        self._table_drawer.triangleSelectionChanged.connect(self._on_triangle_selection_changed_local)
        layout.addWidget(self._table_drawer)

        # Show empty map initially
        self._show_empty_map(reason="startup")

        # Apply dark theme to web view page background (to avoid white flash)
        self.web_view.setStyleSheet(f"background: {Colors.BG_APP};")

    def _on_webview_load_finished(self, ok):
        """Debug current client-side map/marker state after each HTML load."""
        if not ok:
            print("[map-js] loadFinished ok=False")
            return
        js = """
        (function(){
            function findLeafletMap(){
                try {
                    if (window.findMap) {
                        var mm = window.findMap();
                        if (mm) return mm;
                    }
                } catch (err) {}
                if (window.L && window.L.Map) {
                    for (var k in window) {
                        try {
                            var cand = window[k];
                            if (cand && (cand instanceof window.L.Map)) return cand;
                        } catch (err) {}
                    }
                }
                return null;
            }
            var all = Array.prototype.slice.call(document.querySelectorAll('.point-marker'));
            var visible = all.filter(function(el){
                try {
                    var st = window.getComputedStyle(el);
                    return st.display !== 'none' && st.visibility !== 'hidden' && Number(st.opacity || '1') > 0;
                } catch (err) {
                    return true;
                }
            }).length;
            var map = findLeafletMap();
            var center = null, zoom = null, bounds = null;
            try {
                if (map && map.getCenter) {
                    var c = map.getCenter();
                    center = {lat: Number(c.lat), lon: Number(c.lng)};
                }
                if (map && map.getZoom) zoom = Number(map.getZoom());
                if (map && map.getBounds) {
                    var b = map.getBounds();
                    bounds = {
                        south: Number(b.getSouth()),
                        west: Number(b.getWest()),
                        north: Number(b.getNorth()),
                        east: Number(b.getEast())
                    };
                }
            } catch (err) {}
            var first = null;
            if (all.length) {
                try {
                    var el = all[0];
                    var cls = (typeof el.className === 'string') ? el.className : (el.getAttribute ? (el.getAttribute('class') || '') : '');
                    first = {cls: String(cls), fill: String(el.style.fill || ''), stroke: String(el.style.stroke || ''), display: String(el.style.display || '')};
                } catch (err) {}
            }
            var pointLayers = 0;
            try {
                if (map && map.eachLayer) {
                    map.eachLayer(function(layer){
                        try {
                            if (layer && typeof layer.getLatLng === 'function' && typeof layer.setRadius === 'function') pointLayers += 1;
                        } catch (err) {}
                    });
                }
            } catch (err) {}
            return {
                markers_all: all.length,
                markers_visible: visible,
                point_layers: pointLayers,
                center: center,
                zoom: zoom,
                bounds: bounds,
                first_marker: first,
                has_contract: {
                    updateSelectionPanel: (typeof window.updateSelectionPanel === 'function'),
                    excludeSelectedPoint: (typeof window.excludeSelectedPoint === 'function'),
                    applyPointRadius: (typeof window.__applyPointRadius === 'function'),
                    applyPointColorMode: (typeof window.__applyPointColorMode === 'function'),
                    applyContourMajorInterval: (typeof window.__applyContourMajorInterval === 'function'),
                    markerDelegateInit: !!window.__haMarkerDelegateInit
                },
                point_payload_count: Object.keys(window.__mapPointData || {}).length
            };
        })();
        """
        self.web_view.page().runJavaScript(js, self._on_map_js_debug_result)
        self._push_external_layer_catalog()

    def _on_map_js_debug_result(self, result):
        try:
            if isinstance(result, dict):
                center = result.get("center") or {}
                zoom = result.get("zoom")
                lat = center.get("lat") if isinstance(center, dict) else None
                lon = center.get("lon") if isinstance(center, dict) else None
                try:
                    if lat is not None and lon is not None and zoom is not None:
                        lat_f = float(lat)
                        lon_f = float(lon)
                        zoom_f = float(zoom)
                        if np.isfinite(lat_f) and np.isfinite(lon_f) and np.isfinite(zoom_f):
                            self._last_view_state = {
                                "lat": lat_f,
                                "lon": lon_f,
                                "zoom": zoom_f,
                            }
                except Exception:
                    pass
            print(f"[map-js] {result}")
        except Exception:
            print("[map-js] <unserializable result>")

    def _setup_bridge(self):
        """Setup JavaScript-Python communication bridge."""
        self.bridge = MapBridge()
        self.bridge.pointClicked.connect(self._on_point_clicked)
        self.bridge.mapClicked.connect(self._on_map_clicked)
        self.bridge.transectDrawn.connect(self._on_transect_drawn)
        self.bridge.layerToggled.connect(self.set_layer_visibility)
        self.bridge.exportRequested.connect(self._export_map)
        self.bridge.opacityChanged.connect(self.set_heatmap_opacity)
        self.bridge.pointSizeChanged.connect(self.set_point_size)
        self.bridge.scaleBarToggled.connect(self.set_scale_bar_visibility)
        self.bridge.syncSelectionToggled.connect(self.set_sync_selection_enabled)
        self.bridge.labelsToggled.connect(self.set_labels_visibility)
        self.bridge.excludePointRequested.connect(self.pointExcludeRequested.emit)
        self.bridge.showPointInPlotRequested.connect(self.pointShowInPlotRequested.emit)
        self.bridge.heatmapModeChanged.connect(self.set_heatmap_mode)
        self.bridge.pointColorByValueToggled.connect(self.set_point_color_by_value)
        self.bridge.contourLabelsToggled.connect(self.set_contour_labels_visibility)
        self.bridge.contourLabelPrecisionChanged.connect(self.set_contour_label_precision)
        self.bridge.contourMajorIntervalChanged.connect(self.set_contour_major_interval)
        self.bridge.contourSettingsRequested.connect(self.contourSettingsRequested.emit)
        self.bridge.externalLayerVisibilityChanged.connect(self._on_external_layer_visibility_changed)
        self.bridge.externalLayerStyleChanged.connect(self._on_external_layer_style_changed)
        self.bridge.externalLayerRenamed.connect(self._on_external_layer_renamed)
        self.bridge.externalLayerOrderChanged.connect(self._on_external_layer_order_changed)
        self.bridge.externalLayerManagerRequested.connect(self._open_external_layer_manager_dialog)
        self.bridge.geodkFetchRequested.connect(self.geodkFetchRequested.emit)
        self.bridge.geodkCredentialsRequested.connect(self.geodkCredentialsRequested.emit)
        self.bridge.geodkDownloadRequested.connect(self.geodkDownloadRequested.emit)
        self.bridge.geodkCopyReproRequested.connect(self.geodkCopyReproRequested.emit)
        self.bridge.transectSelected.connect(self._on_transect_selected)
        self.bridge.transectDeleted.connect(self._on_transect_deleted)
        self.bridge.transectVisibilityToggled.connect(self._on_transect_visibility_toggled)
        self.bridge.transectRenamed.connect(self._on_transect_renamed)

        self.channel = QWebChannel()
        self.channel.registerObject('pyBridge', self.bridge)
        self.web_view.page().setWebChannel(self.channel)

    def _setup_shortcuts(self):
        """Setup keyboard shortcuts for map interactions."""
        self._shortcut_clear_selection = QShortcut(QKeySequence(Qt.Key_Escape), self)
        self._shortcut_clear_selection.setContext(Qt.WidgetWithChildrenShortcut)
        self._shortcut_clear_selection.activated.connect(self.clear_selected_point)

    def _prompt_external_layer_file(self):
        """Open file picker and load one external GIS layer."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Load External GIS Layer",
            "",
            "GIS Files (*.geojson *.json *.shp);;GeoJSON (*.geojson *.json);;Shapefile (*.shp);;All Files (*)",
        )
        if not file_path:
            return
        self.load_external_layer(file_path)

    def _open_external_layer_manager_dialog(self):
        dlg = getattr(self, "_external_layer_manager_dialog", None)
        if dlg is not None:
            try:
                if dlg.isVisible():
                    dlg.raise_()
                    dlg.activateWindow()
                    dlg.refresh_from_map()
                    return
            except Exception:
                pass
        dlg = ExternalLayerManagerDialog(self.main_window, self, parent=self.main_window)
        self._external_layer_manager_dialog = dlg
        dlg.finished.connect(lambda *_: setattr(self, "_external_layer_manager_dialog", None))
        dlg.show()

    def set_external_layer_visible(self, layer_id: str, visible: bool):
        self._on_external_layer_visibility_changed(str(layer_id), bool(visible))

    def set_external_layer_style(self, layer_id: str, style: dict):
        try:
            payload = json.dumps(style or {})
        except Exception:
            payload = "{}"
        self._on_external_layer_style_changed(str(layer_id), payload)

    def rename_external_layer(self, layer_id: str, name: str) -> bool:
        """Rename an external layer (display label) and push catalog updates."""
        lid = str(layer_id or "")
        next_name = str(name or "").strip()
        if not lid or not next_name:
            return False
        layer = self._find_external_layer_by_id(lid)
        if layer is None:
            return False
        if str(layer.get("name") or "").strip() == next_name:
            return False
        layer["name"] = next_name
        self._push_external_layer_catalog()
        return True

    def remove_external_layer(self, layer_id: str):
        lid = str(layer_id or "")
        before = len(self._external_layers)
        self._external_layers = [layer for layer in self._external_layers if str(layer.get("layer_id", "")) != lid]
        if len(self._external_layers) == before:
            return
        if self._current_data is not None:
            self._rerender_map()
        else:
            self._push_external_layer_catalog()

    def reorder_external_layers(self, layer_ids: list) -> bool:
        """Reorder external layers by layer_id (bottom-to-top render order)."""
        try:
            desired = [str(v) for v in (layer_ids or []) if str(v)]
        except Exception:
            desired = []
        if not desired or not self._external_layers:
            return False

        by_id = {str(layer.get("layer_id", "")): layer for layer in self._external_layers}
        used = set()
        next_layers = []
        for lid in desired:
            layer = by_id.get(lid)
            if layer is None:
                continue
            next_layers.append(layer)
            used.add(lid)
        for layer in self._external_layers:
            lid = str(layer.get("layer_id", ""))
            if lid and lid not in used:
                next_layers.append(layer)
        if [str(l.get("layer_id", "")) for l in next_layers] == [str(l.get("layer_id", "")) for l in self._external_layers]:
            return False

        self._external_layers = next_layers
        self._push_external_layer_catalog()
        return True

    def load_external_layer(self, file_path: str) -> bool:
        """Load and register one external layer payload."""
        try:
            payload = load_external_layer_payload(file_path)
        except ExternalLayerError as exc:
            QMessageBox.warning(self, "Layer Load Failed", str(exc))
            return False
        except Exception as exc:
            QMessageBox.warning(self, "Layer Load Failed", f"Unexpected error: {exc}")
            return False

        try:
            style = normalize_external_layer_style(
                build_external_layer_style(len(self._external_layers)),
                fallback_color=self.COLORS.get("external", "#22c55e"),
            )
            payload["style"] = style
            payload["layer_id"] = f"ext_{len(self._external_layers) + 1}"
            payload["visible"] = True
            self._external_layers.append(payload)
            self._show_external = True
        except Exception as exc:
            QMessageBox.warning(self, "Layer Load Failed", f"Failed to register layer: {exc}")
            return False

        if self._current_data is not None:
            self._rerender_map()
            self._push_external_layer_catalog()
        else:
            self._push_external_layer_catalog()
            QMessageBox.information(
                self,
                "Layer Loaded",
                "Layer loaded. It will appear once map data is available.",
            )
        return True

    def clear_external_layers(self):
        """Remove all loaded external layers from this map dataset."""
        if not self._external_layers:
            return
        self._external_layers = []
        if self._current_data is not None:
            self._rerender_map()
        self._push_external_layer_catalog()

    def _external_layer_signature(self):
        """Return a compact signature for external-layer render state."""
        sig = []
        for layer in self._external_layers:
            sig.append(
                (
                    str(layer.get("layer_id", "")),
                    str(layer.get("source_path", "")),
                    int(layer.get("feature_count", 0) or 0),
                    str(layer.get("geometry_kind", "")),
                )
            )
        return tuple(sig)

    @staticmethod
    def _external_layer_css_class(layer_id: str) -> str:
        raw = str(layer_id or "layer").strip().lower()
        safe = re.sub(r"[^a-z0-9_-]+", "-", raw).strip("-")
        if not safe:
            safe = "layer"
        return f"overlay-external-layer-{safe}"

    @staticmethod
    def _external_layer_geometry_label(layer: dict) -> str:
        kinds = layer.get("geometry_types") if isinstance(layer.get("geometry_types"), list) else []
        cleaned = [str(v).strip() for v in kinds if str(v).strip()]
        if len(cleaned) == 1:
            return cleaned[0]
        kind = str(layer.get("geometry_kind", "")).strip().lower()
        if kind == "point":
            return "Point"
        if kind == "line":
            return "LineString"
        if kind == "polygon":
            return "Polygon"
        if kind == "mixed":
            return "Mixed"
        return "Geometry"

    def _external_layer_catalog_payload(self):
        payload = []
        for layer in self._external_layers:
            style = normalize_external_layer_style(
                layer.get("style"),
                fallback_color=self.COLORS.get("external", "#22c55e"),
            )
            layer["style"] = style
            payload.append(
                {
                    "id": str(layer.get("layer_id", "")),
                    "name": str(layer.get("name", "External Layer")),
                    "geometry": self._external_layer_geometry_label(layer),
                    "geometry_kind": str(layer.get("geometry_kind", "other")),
                    "source": str(layer.get("source_path", "-")),
                    "feature_count": int(layer.get("feature_count", 0) or 0),
                    "visible": bool(layer.get("visible", True)),
                    "style": style,
                }
            )
        return payload

    def _push_external_layer_catalog(self):
        catalog = self._external_layer_catalog_payload()
        layer_state = self._layer_state_payload()
        js = f"""
        (function(){{
            window.__externalLayerCatalog = {json.dumps(catalog)};
            if(window.__setExternalLayerCatalog) window.__setExternalLayerCatalog(window.__externalLayerCatalog);
            if(window.__setMapLayerState){{
                if(!window.__mapLayerState) window.__mapLayerState = {json.dumps(layer_state)};
                window.__setMapLayerState(window.__mapLayerState);
            }}
        }})();
        """
        self.web_view.page().runJavaScript(js)

    def _find_external_layer_by_id(self, layer_id: str):
        lid = str(layer_id or "")
        for layer in self._external_layers:
            if str(layer.get("layer_id", "")) == lid:
                return layer
        return None

    def _on_external_layer_visibility_changed(self, layer_id: str, visible: bool):
        layer = self._find_external_layer_by_id(layer_id)
        if layer is None:
            return
        next_visible = bool(visible)
        if bool(layer.get("visible", True)) == next_visible:
            return
        layer["visible"] = next_visible
        self._push_external_layer_catalog()

    def _on_external_layer_style_changed(self, layer_id: str, style_json: str):
        layer = self._find_external_layer_by_id(layer_id)
        if layer is None:
            return
        try:
            parsed = json.loads(style_json) if style_json else {}
        except Exception:
            parsed = {}
        normalized = normalize_external_layer_style(
            parsed,
            fallback_color=self.COLORS.get("external", "#22c55e"),
        )
        previous = normalize_external_layer_style(
            layer.get("style"),
            fallback_color=self.COLORS.get("external", "#22c55e"),
        )
        if previous == normalized:
            return
        layer["style"] = normalized
        self._push_external_layer_catalog()

    def _on_external_layer_renamed(self, layer_id: str, name: str):
        try:
            self.rename_external_layer(str(layer_id), str(name))
        except Exception:
            return

    def _on_external_layer_order_changed(self, order_json: str):
        try:
            parsed = json.loads(order_json) if order_json else []
        except Exception:
            parsed = []
        if not isinstance(parsed, list):
            return
        try:
            self.reorder_external_layers(parsed)
        except Exception:
            return

    def _add_external_layers(self, feature_group):
        """Render loaded external GeoJSON layers into the provided feature group."""
        if not self._external_layers:
            return
        try:
            import folium
        except Exception:
            return

        for layer in self._external_layers:
            feature_collection = layer.get("feature_collection")
            if not isinstance(feature_collection, dict):
                continue
            style = normalize_external_layer_style(
                layer.get("style"),
                fallback_color=self.COLORS.get("external", "#22c55e"),
            )
            layer["style"] = style
            color = str(style.get("color") or self.COLORS.get("external", "#22c55e"))
            line_width = float(style.get("line_width") or 2.0)
            line_opacity = float(style.get("line_opacity") or 0.9)
            fill_opacity = float(style.get("fill_opacity") or 0.12)
            point_size = float(style.get("point_size") or 8.0)
            layer_name = str(layer.get("name") or "External Layer")
            layer_css_class = self._external_layer_css_class(str(layer.get("layer_id", "")))
            geometry_kind = str(layer.get("geometry_kind", "other")).strip().lower()

            if geometry_kind == "point":
                for lat, lon in self._iter_geojson_points(feature_collection):
                    try:
                        folium.CircleMarker(
                            location=[lat, lon],
                            radius=point_size,
                            color=color,
                            weight=max(1.0, line_width * 0.5),
                            opacity=line_opacity,
                            fill=True,
                            fill_color=color,
                            fill_opacity=line_opacity,
                            class_name=f"overlay-external {layer_css_class}",
                        ).add_to(feature_group)
                    except Exception:
                        continue
                continue

            def _style_fn(
                _feature,
                c=color,
                w=line_width,
                o=line_opacity,
                fo=fill_opacity,
                gk=geometry_kind,
                cls=layer_css_class,
            ):
                return {
                    "color": c,
                    "weight": w,
                    "opacity": o,
                    "fillColor": c,
                    "fillOpacity": 0.0 if gk == "line" else fo,
                    "className": f"overlay-external {cls}",
                }

            try:
                folium.GeoJson(
                    data=feature_collection,
                    name=layer_name,
                    style_function=_style_fn,
                ).add_to(feature_group)
            except Exception:
                continue

    @classmethod
    def _iter_geojson_points(cls, feature_collection):
        if not isinstance(feature_collection, dict):
            return
        features = feature_collection.get("features")
        if not isinstance(features, list):
            return
        for feat in features:
            if not isinstance(feat, dict):
                continue
            geom = feat.get("geometry")
            if not isinstance(geom, dict):
                continue
            yield from cls._iter_geometry_points(geom)

    @classmethod
    def _iter_geometry_points(cls, geometry):
        if not isinstance(geometry, dict):
            return
        gtype = str(geometry.get("type", "")).strip()
        coords = geometry.get("coordinates")
        if gtype == "Point":
            pair = cls._coerce_lon_lat_pair(coords)
            if pair is not None:
                lon, lat = pair
                yield lat, lon
            return
        if gtype == "MultiPoint" and isinstance(coords, list):
            for item in coords:
                pair = cls._coerce_lon_lat_pair(item)
                if pair is None:
                    continue
                lon, lat = pair
                yield lat, lon
            return
        if gtype == "GeometryCollection":
            geoms = geometry.get("geometries")
            if not isinstance(geoms, list):
                return
            for child in geoms:
                yield from cls._iter_geometry_points(child)

    @staticmethod
    def _coerce_lon_lat_pair(value):
        if not isinstance(value, (list, tuple)) or len(value) < 2:
            return None
        lon = MapWidget._coerce_float(value[0])
        lat = MapWidget._coerce_float(value[1])
        if lon is None or lat is None:
            return None
        if not (np.isfinite(lon) and np.isfinite(lat)):
            return None
        lon = float(lon)
        lat = float(lat)
        if -180.0 <= lon <= 180.0 and -90.0 <= lat <= 90.0:
            return lon, lat
        if -90.0 <= lon <= 90.0 and -180.0 <= lat <= 180.0:
            return float(lat), float(lon)
        return None

    def toggle_table_panel(self):
        self._interaction_controller.toggle_table_panel()

    def ensure_table_panel_visible(self):
        self._interaction_controller.ensure_table_panel_visible()

    def _on_triangle_selection_changed_local(self, triangle_indices: list):
        self._interaction_controller.on_triangle_selection_changed_local(triangle_indices)

    def _on_table_rows_selected_local(self, point_ids):
        self._interaction_controller.on_table_rows_selected_local(point_ids)

    def _on_table_row_selected_local(self, point_id: str):
        self._interaction_controller.on_table_row_selected_local(point_id)

    def _get_transformer(self):
        """Get or create coordinate transformer (UTM32N to WGS84)."""
        if self._transformer is None:
            self._transformer = pyproj.Transformer.from_crs(
                "epsg:25832",  # UTM32N EUREF89 for Denmark
                "epsg:4326",   # WGS84
                always_xy=True
            )
        return self._transformer

    @staticmethod
    def _read_wgs84_from_row(row):
        """Return (lon, lat) from explicit WGS84 columns when available."""
        for lon_col, lat_col in (
            ("Longitude", "Latitude"),
            ("longitude", "latitude"),
            ("lon", "lat"),
            ("Lon", "Lat"),
        ):
            if lon_col in row.index and lat_col in row.index:
                try:
                    lon = MapWidget._coerce_float(row[lon_col])
                    lat = MapWidget._coerce_float(row[lat_col])
                    if lon is None or lat is None:
                        continue
                    if np.isfinite(lon) and np.isfinite(lat) and -180.0 <= lon <= 180.0 and -90.0 <= lat <= 90.0:
                        return lon, lat
                except Exception:
                    continue
        return None

    def _project_xy_to_wgs84(self, x_value, y_value, transformer=None):
        """
        Return (lon, lat) from numeric XY.
        Heuristics:
        - If XY already looks like lon/lat or lat/lon, use it directly.
        - Otherwise assume UTM32 (EPSG:25832) and project to WGS84.
        """
        x = self._coerce_float(x_value)
        y = self._coerce_float(y_value)
        if x is None or y is None:
            return None
        if not (np.isfinite(x) and np.isfinite(y)):
            return None

        if -180.0 <= x <= 180.0 and -90.0 <= y <= 90.0:
            return x, y
        if -90.0 <= x <= 90.0 and -180.0 <= y <= 180.0:
            return y, x

        tf = transformer or self._get_transformer()
        try:
            lon, lat = tf.transform(x, y)
        except Exception:
            return None
        if not (np.isfinite(lon) and np.isfinite(lat)):
            return None
        lon = float(lon)
        lat = float(lat)
        if -180.0 <= lon <= 180.0 and -90.0 <= lat <= 90.0:
            return lon, lat

        # Keep rows renderable even when CRS assumptions are wrong.
        if -180.0 <= lat <= 180.0 and -90.0 <= lon <= 90.0:
            return float(lat), float(lon)
        if np.isfinite(lon) and np.isfinite(lat):
            wrapped_lon = ((lon + 180.0) % 360.0) - 180.0
            clamped_lat = max(-89.999999, min(89.999999, lat))
            return float(wrapped_lon), float(clamped_lat)
        return None

    def _project_xy_to_wgs84_strict(self, x_value, y_value, transformer=None):
        """
        Strict projection path for analytical overlays (contours/vectors/coverage).
        Keeps overlays aligned with point coordinates produced from UTM32->WGS84.
        """
        x = self._coerce_float(x_value)
        y = self._coerce_float(y_value)
        if x is None or y is None:
            return None
        if not (np.isfinite(x) and np.isfinite(y)):
            return None
        tf = transformer or self._get_transformer()
        try:
            lon, lat = tf.transform(x, y)
        except Exception:
            return None
        if not (np.isfinite(lon) and np.isfinite(lat)):
            return None
        return float(lon), float(lat)

    @staticmethod
    def _coerce_float(value):
        """Parse numeric values robustly from mixed locale/string inputs."""
        if value is None:
            return None
        try:
            return float(value)
        except Exception:
            pass
        try:
            txt = str(value).strip()
            if not txt:
                return None
            txt = txt.replace(" ", "")
            if "," in txt and "." in txt:
                txt = txt.replace(",", "")
            elif "," in txt:
                txt = txt.replace(",", ".")
            return float(txt)
        except Exception:
            return None

    def _layer_state_payload(self):
        """Canonical map-layer state mirrored between Python and JS."""
        return {
            "points": bool(self._show_points),
            "excluded": bool(self._show_excluded),
            "external": bool(self._show_external),
            "heatmap": bool(self._show_heatmap),
            "coverage": bool(self._show_coverage),
            "vectors": bool(self._show_vectors),
            "main_arrow": bool(self._show_main_arrow),
            "contours": bool(self._show_contours),
            "transect": bool(self._transect_mode),
        }

    def _show_empty_map(self, reason: str = "empty"):
        self._runtime_renderer.show_empty_map(reason)

    def _dump_rendered_html(self, html: str, reason: str = "map"):
        self._runtime_renderer.dump_rendered_html(html, reason=reason)

    def _set_html_content(self, html: str, reason: str = "map"):
        self._runtime_renderer.set_html_content(html, reason=reason)

    def _get_fallback_html(self):
        return self._runtime_renderer.get_fallback_html()

    def _inject_custom_css(self, m):
        self._runtime_renderer.inject_custom_css(m)

    def _inject_overlays(self, m):
        self._runtime_renderer.inject_overlays(m)

    def _inject_webchannel(self, html):
        return self._runtime_renderer.inject_webchannel(html)

    def _inject_point_data(self, html, points):
        return self._runtime_renderer.inject_point_data(html, points)

    def update_map(self, data, col_mapping, excluded_ids=None, triangle_data=None,
                   gradient_data=None, rejected_data=None, force=False):
        """
        Update map with data points and analysis layers.

        This is the single entry point for refreshing the map. All callers
        should assemble a MapPayload dict (see top of file) and unpack it here.

        Args:
            data:          pd.DataFrame  - filtered_plot_data from the active Dataset.
            col_mapping:   dict          - column name mapping {'ID', 'x', 'y', 'hydraulic head'}.
            excluded_ids:  set | None    - IDs currently excluded from analysis.
            triangle_data: pd.DataFrame | None - kept triangles for overlay.
            gradient_data: pd.DataFrame | None - gradient vectors for flow arrows.
            rejected_data: pd.DataFrame | None - rejected triangles for heatmap.
        """
        try:
            import folium
            from folium.plugins import HeatMap
        except ImportError:
            return

        # Preserve previous state for in-place fast-path checks.
        prev_data = self._current_data
        prev_col_mapping = self._current_col_mapping
        prev_triangle_data = self._current_triangle_data
        prev_gradient_data = self._current_gradient_data
        prev_rejected_data = self._current_rejected_data
        prev_excluded_ids = set(self._excluded_ids or set())

        # Store current state
        self._current_data = data
        self._current_col_mapping = col_mapping
        self._current_triangle_data = triangle_data
        self._current_gradient_data = gradient_data
        self._current_rejected_data = rejected_data
        self._excluded_ids = {str(v) for v in (excluded_ids or set())}
        try:
            self._table_drawer.set_data(data)
            self._table_drawer.refresh_triangle_data(self._current_triangle_data, self._current_rejected_data)
        except Exception:
            pass

        # Fast path: avoid full map rebuild when point payload remains compatible.
        # For exclusion changes we can still update in-place in point/contour mode even
        # when gradient payload objects were recomputed.
        if not bool(force):
            same_payload_core = (
                (data is prev_data)
                and (col_mapping is prev_col_mapping)
                and (triangle_data is prev_triangle_data)
                and (gradient_data is prev_gradient_data)
                and (rejected_data is prev_rejected_data)
            )
            overlays_stable = (
                (triangle_data is prev_triangle_data)
                and (gradient_data is prev_gradient_data)
                and (rejected_data is prev_rejected_data)
            )
            compatible_point_payload = self._is_point_payload_compatible(
                prev_data=prev_data,
                new_data=data,
                prev_col_mapping=prev_col_mapping,
                new_col_mapping=col_mapping,
            )
            exclusions_changed = (self._excluded_ids != prev_excluded_ids)
            if (same_payload_core or compatible_point_payload) and exclusions_changed:
                self._apply_exclusions_visual_only()
                if self._show_contours:
                    self._apply_dynamic_contours_visual_only()
                if self._show_heatmap:
                    self._apply_dynamic_heatmap_visual_only()
                if self._show_vectors or self._show_main_arrow:
                    self._apply_dynamic_vectors_visual_only()
                if self._show_coverage:
                    self._apply_dynamic_coverage_visual_only()
                return
            can_filter_fast = self._can_apply_filter_fast_path(
                prev_data=prev_data,
                new_data=data,
                prev_col_mapping=prev_col_mapping,
                new_col_mapping=col_mapping,
            )
            if can_filter_fast and (not exclusions_changed):
                if self._apply_filtered_points_visual_only(data, col_mapping):
                    if self._show_contours:
                        self._apply_dynamic_contours_visual_only()
                    if self._show_heatmap:
                        self._apply_dynamic_heatmap_visual_only()
                    if self._show_vectors or self._show_main_arrow:
                        self._apply_dynamic_vectors_visual_only()
                    if self._show_coverage:
                        self._apply_dynamic_coverage_visual_only()
                    return

        render_signature = (
            id(data),
            id(col_mapping),
            id(triangle_data),
            id(gradient_data),
            id(rejected_data),
            tuple(sorted(self._excluded_ids)),
            str(self._current_tile),
            bool(self._show_points),
            bool(self._show_excluded),
            bool(self._show_external),
            bool(self._color_points_by_head),
            bool(self._show_heatmap),
            bool(self._show_coverage),
            bool(self._show_contours),
            bool(self._show_vectors),
            bool(self._show_main_arrow),
            self._external_layer_signature(),
            int(self._point_size),
            float(self._heatmap_opacity),
            str(self._heatmap_mode),
            bool(getattr(self.main_window, "fill_contours", False)),
            str(getattr(self.main_window, "colormap_2d", "viridis")),
            str(getattr(self.main_window, "interpolation_method", "cubic")),
            int(getattr(self.main_window, "contour_levels", 10) or 10),
            int(getattr(self.main_window, "contour_extent_pct", 0) or 0),
            str(getattr(self.main_window, "contour_extrapolation", "none")),
            float(getattr(self.main_window, "contour_linewidth", 0.8) or 0.8),
            bool(self._show_contour_labels),
            int(self._contour_label_precision),
            int(self._contour_major_interval),
            int(self._contour_label_font_size),
            float(self._contour_fill_opacity),
        )
        if (not bool(force)) and (self._last_render_signature == render_signature):
            return
        self._last_render_signature = render_signature

        if data is None or data.empty:
            try:
                prev_len = int(len(prev_data)) if prev_data is not None else 0
            except Exception:
                prev_len = 0
            if prev_len > 0 and not bool(force):
                print(f"[map] skip empty render: keeping previous data map prev_rows={prev_len}")
                return
            self._point_legend = {"available": False, "gradient": "", "min_label": "-", "max_label": "-"}
            self._contour_legend = {"enabled": False, "gradient": "", "min_label": "-", "max_label": "-"}
            self._show_empty_map(reason="update_map_empty_payload")
            return

        x_col = col_mapping.get('x')
        y_col = col_mapping.get('y')
        id_col = col_mapping.get('ID')
        h_col = col_mapping.get('hydraulic head')

        if not all([x_col, y_col]):
            print(f"[map] skip update: missing coordinate mapping x={x_col!r} y={y_col!r}")
            return

        # Transform coordinates
        transformer = self._get_transformer()
        coords_data = []
        failed_project = 0

        for idx, row in data.iterrows():
            try:
                wgs = self._read_wgs84_from_row(row)
                if wgs is not None:
                    lon, lat = wgs
                else:
                    projected = self._project_xy_to_wgs84(row[x_col], row[y_col], transformer=transformer)
                    if projected is None:
                        failed_project += 1
                        continue
                    lon, lat = projected
                point_id = str(row[id_col]) if id_col else str(idx)
                head_val = row[h_col] if h_col else 0
                is_excluded = point_id in self._excluded_ids
                coords_data.append({
                    'idx': idx,
                    'lat': lat,
                    'lon': lon,
                    'id': point_id,
                    'member_key': row.get("member_key") if hasattr(row, "get") else None,
                    'head': head_val,
                    'x': row[x_col],
                    'y': row[y_col],
                    'excluded': is_excluded
                })
            except Exception:
                failed_project += 1
                continue

        try:
            sample = [(c.get("id"), round(float(c.get("lon")), 6), round(float(c.get("lat")), 6)) for c in coords_data[:3]]
        except Exception:
            sample = []
        print(
            f"[map] payload rows={len(data)} cols(x={x_col!r}, y={y_col!r}, id={id_col!r}, h={h_col!r}) "
            f"coords={len(coords_data)} failed={failed_project} "
            f"layers(points={self._show_points}, excluded={self._show_excluded}) sample={sample}"
        )

        if not coords_data:
            self._show_empty_map(reason="coords_data_empty")
            return

        self._apply_point_colors(coords_data)

        # Calculate center and bounds
        lats = [c['lat'] for c in coords_data]
        lons = [c['lon'] for c in coords_data]
        center_lat = sum(lats) / len(lats)
        center_lon = sum(lons) / len(lons)
        lat_span = max(lats) - min(lats) if len(lats) > 1 else 0.0
        lon_span = max(lons) - min(lons) if len(lons) > 1 else 0.0
        span_deg = max(float(lat_span), float(lon_span))
        render_point_size = int(self._point_size)
        if span_deg < 0.002:
            render_point_size = max(render_point_size, 14)
        print(f"[map] bounds span_deg={span_deg:.6f} render_point_size={render_point_size}")

        # Preserve viewport across data rerenders to avoid zoom flicker.
        preserve_view = bool(self._last_render_kind == "data" and isinstance(self._last_view_state, dict))
        if preserve_view:
            try:
                map_lat = float(self._last_view_state.get("lat", center_lat))
                map_lon = float(self._last_view_state.get("lon", center_lon))
                map_zoom = int(round(float(self._last_view_state.get("zoom", 14))))
                map_zoom = max(1, min(22, map_zoom))
            except Exception:
                map_lat, map_lon, map_zoom = center_lat, center_lon, 14
                preserve_view = False
        else:
            map_lat, map_lon, map_zoom = center_lat, center_lon, 14

        # Get tile provider
        tile_provider = self.TILE_PROVIDERS.get(self._current_tile, 'OpenStreetMap')

        # Create map with custom options
        if tile_provider.startswith('http'):
            m = folium.Map(
                location=[map_lat, map_lon],
                zoom_start=map_zoom,
                tiles=None,
                zoom_control=False
            )
            folium.TileLayer(
                tiles=tile_provider,
                attr='Esri',
                name='Esri World Imagery'
            ).add_to(m)
        else:
            m = folium.Map(
                location=[map_lat, map_lon],
                zoom_start=map_zoom,
                tiles=tile_provider,
                zoom_control=False
            )

        # Inject styles and overlays
        self._inject_custom_css(m)
        self._inject_overlays(m)

        # Create feature groups for layers (matching logical layers, not UI panels yet)
        fg_points = folium.FeatureGroup(name='Data Points', show=self._show_points)
        fg_excluded = folium.FeatureGroup(name='Excluded Points', show=self._show_excluded)
        fg_external = folium.FeatureGroup(name='External GIS Layers', show=True)
        fg_heatmap = folium.FeatureGroup(name='Rejection Heatmap', show=self._show_heatmap)
        fg_coverage = folium.FeatureGroup(name='Coverage Quality', show=self._show_coverage)
        fg_contours = folium.FeatureGroup(name='Head Contours', show=self._show_contours)
        fg_vectors = folium.FeatureGroup(name='Gradient Vectors', show=self._show_vectors)
        fg_main_arrow = folium.FeatureGroup(name='Main Direction Arrow', show=self._show_main_arrow)

        # Add data points
        added_active = 0
        added_excluded = 0
        for point in coords_data:
            # We don't use the popup anymore for the 'Concept' look, we use the tooltip.
            # But we can keep a popup as fallback or empty.
            # IMPORTANT: We add class_name so Folium emits Leaflet className for JS hooks.
            
            is_selected = point['id'] == self._selected_id
            
            # Helper to create style
            if point['excluded'] and self._show_excluded:
                 folium.CircleMarker(
                    location=[point['lat'], point['lon']],
                    radius=render_point_size,
                    color=self.COLORS['excluded'],
                    fill=True,
                    fill_color=self.COLORS['excluded'],
                    fill_opacity=0.4,
                    weight=3,
                    dash_array='4,4',
                    class_name=f'point-marker excluded point-idx-{point["idx"]}'
                ).add_to(fg_excluded)
                 added_excluded += 1
            elif not point['excluded'] and self._show_points:
                base_color = str(point.get('point_color') or self.COLORS['points'])
                normal_color = base_color if bool(self._color_points_by_head) else self.COLORS['points']
                color = self.COLORS['selected'] if is_selected else normal_color
                # Increase radius/weight for selected
                base_radius = render_point_size
                radius = (base_radius * 1.5) if is_selected else base_radius
                weight = 4 if is_selected else 3
                
                folium.CircleMarker(
                    location=[point['lat'], point['lon']],
                    radius=radius,
                    color='#111111',
                    fill=True,
                    fill_color=color,
                    fill_opacity=0.95,
                    weight=weight,
                    class_name=f'point-marker active point-idx-{point["idx"]}'
                ).add_to(fg_points)
                added_active += 1

                # Add labels only when enabled; this keeps behavior deterministic.
                if self._show_labels and point['id']:
                    folium.Marker(
                        location=[point['lat'], point['lon']],
                        icon=folium.DivIcon(
                            class_name="point-id-label",
                            html=f'''<div style="
                                font-size: 9px; font-weight: 600; color: #333;
                                background: rgba(255,255,255,0.85); padding: 1px 4px;
                                border-radius: 2px; white-space: nowrap;
                                transform: translate(-50%, -100%); margin-top: -12px;
                                box-shadow: 0 1px 2px rgba(0,0,0,0.15);
                            ">{point["id"]}</div>''',
                            icon_size=(60, 20),
                            icon_anchor=(30, 20)
                        )
                    ).add_to(fg_points)
        print(f"[map] markers added active={added_active} excluded={added_excluded}")

        # Add rejection heatmap if we have rejected data (visibility handled by JS toggles).
        if rejected_data is not None and not rejected_data.empty:
            heatmap_data = self._prepare_heatmap_data(rejected_data, col_mapping, transformer)
            if heatmap_data:
                if str(self._heatmap_mode).lower() == "hex":
                    self._add_hex_heatmap(fg_heatmap, heatmap_data)
                else:
                    HeatMap(
                        heatmap_data,
                        radius=25,
                        blur=15,
                        gradient={
                            0.4: self.COLORS['coverage'],
                            0.65: '#fbbf24',
                            1.0: self.COLORS['rejection']
                        },
                        min_opacity=self._heatmap_opacity
                    ).add_to(fg_heatmap)

        # Add gradient vectors if we have gradient data (visibility handled by JS toggles).
        if gradient_data is not None and not gradient_data.empty:
            self._add_gradient_vectors(fg_vectors, gradient_data, col_mapping, transformer)
            self._add_main_direction_arrow(fg_main_arrow, gradient_data, col_mapping, transformer)

        # Add coverage quality overlay (per-point triangle support)
        if triangle_data is not None and not triangle_data.empty:
            self._add_coverage_overlay(fg_coverage, data, col_mapping, triangle_data, transformer)

        # Add head contours from point heads
        self._add_head_contours(fg_contours, data, col_mapping, transformer)

        # Add external GIS overlays (GeoJSON / Shapefile-converted GeoJSON)
        self._add_external_layers(fg_external)

        # Add feature groups to map in strict z-order.
        # Contours must remain behind points.
        fg_heatmap.add_to(m)
        fg_coverage.add_to(m)
        fg_contours.add_to(m)
        fg_external.add_to(m)
        fg_vectors.add_to(m)
        fg_main_arrow.add_to(m)
        fg_points.add_to(m)
        fg_excluded.add_to(m)

        # Add layer control (Hidden by CSS, but functionality remains)
        folium.LayerControl(collapsed=False).add_to(m)

        # Fit bounds on the first data render; preserve viewport on subsequent rerenders.
        if (not preserve_view) and len(lats) > 1:
            bounds_sig = (
                len(lats),
                round(min(lats), 6), round(min(lons), 6),
                round(max(lats), 6), round(max(lons), 6),
            )
            m.fit_bounds([[min(lats), min(lons)], [max(lats), max(lons)]])
            self._last_bounds_signature = bounds_sig
            print(f"[map] fit_bounds={bounds_sig}")

        # Render and display
        import io
        data = io.BytesIO()
        m.save(data, close_file=False)
        html = data.getvalue().decode()
        
        self._point_data_map = {str(p.get("idx")): p for p in coords_data}
        by_id = {}
        for p in coords_data:
            pid = str(p.get("id", ""))
            by_id.setdefault(pid, []).append(p)
        self._point_data_by_id = by_id
        self._render_point_size = float(render_point_size)
        html = self._inject_webchannel(html)
        html = self._inject_point_data(html, coords_data)
        self._dump_rendered_html(html, reason="data")
        self._last_render_kind = "data"
        print(f"[map] render kind=data rows={len(coords_data)}")
        self._set_html_content(html, reason="data")

    def _create_popup_html(self, point):
        # Legacy method, no longer used
        pass

    def _prepare_heatmap_data(self, rejected_data, col_mapping, transformer):
        return self._payload_builder.prepare_heatmap_data(rejected_data, col_mapping, transformer)

    def _build_heatmap_payload(self):
        return self._payload_builder.build_heatmap_payload()

    def _apply_dynamic_heatmap_visual_only(self):
        self._runtime_renderer.apply_dynamic_heatmap_visual_only()

    def _add_hex_heatmap(self, feature_group, heatmap_data):
        self._runtime_renderer.add_hex_heatmap(feature_group, heatmap_data)

    def _add_gradient_vectors(self, feature_group, gradient_data, col_mapping, transformer):
        self._runtime_renderer.add_gradient_vectors(feature_group, gradient_data, col_mapping, transformer)

    def _add_main_direction_arrow(self, feature_group, gradient_data, col_mapping, transformer):
        self._runtime_renderer.add_main_direction_arrow(feature_group, gradient_data, col_mapping, transformer)

    def _add_coverage_overlay(self, feature_group, data, col_mapping, triangle_data, transformer):
        self._runtime_renderer.add_coverage_overlay(feature_group, data, col_mapping, triangle_data, transformer)

    def _add_head_contours(self, feature_group, data, col_mapping, transformer):
        self._runtime_renderer.add_head_contours(feature_group, data, col_mapping, transformer)

    def _build_vectors_payload(self):
        return self._payload_builder.build_vectors_payload()

    def _apply_dynamic_vectors_visual_only(self):
        self._runtime_renderer.apply_dynamic_vectors_visual_only()

    def _build_coverage_payload(self):
        return self._payload_builder.build_coverage_payload()

    def _apply_dynamic_coverage_visual_only(self):
        self._runtime_renderer.apply_dynamic_coverage_visual_only()

    def _build_triangle_overlay_payload(self, triangle_indices, combined_df=None):
        return self._payload_builder.build_triangle_overlay_payload(triangle_indices, combined_df=combined_df)

    def apply_triangle_selection_overlay(self, triangle_indices, combined_df=None):
        self._runtime_renderer.apply_triangle_selection_overlay(triangle_indices, combined_df=combined_df)

    def _build_colormap_gradient(self, cmap):
        return self._payload_builder.build_colormap_gradient(cmap)

    def _is_point_payload_compatible(self, *, prev_data, new_data, prev_col_mapping, new_col_mapping):
        """
        Return True when point payload is effectively the same for in-place exclusion updates.
        This allows no-flash updates even if DataFrame identity changes after refilter.
        """
        try:
            if prev_data is None or new_data is None:
                return False
            if prev_col_mapping is None or new_col_mapping is None:
                return False
            try:
                if int(len(prev_data)) != int(len(new_data)):
                    return False
            except Exception:
                return False

            keys = ("ID", "x", "y", "hydraulic head")
            for k in keys:
                if str(prev_col_mapping.get(k)) != str(new_col_mapping.get(k)):
                    return False

            id_col = new_col_mapping.get("ID")
            if id_col and (id_col in prev_data.columns) and (id_col in new_data.columns):
                prev_ids = prev_data[id_col].astype(str).tolist()
                new_ids = new_data[id_col].astype(str).tolist()
                if prev_ids != new_ids:
                    return False
            else:
                # No mapped ID; fallback to positional index equality.
                if list(prev_data.index) != list(new_data.index):
                    return False
            return True
        except Exception:
            return False

    def _can_apply_filter_fast_path(self, *, prev_data, new_data, prev_col_mapping, new_col_mapping):
        """
        Return True when filtered data can be applied by toggling existing markers in-place.
        Requirement: new filtered IDs must be a subset of currently rendered marker IDs.
        """
        try:
            if prev_data is None or new_data is None:
                return False
            if prev_col_mapping is None or new_col_mapping is None:
                return False
            id_prev = prev_col_mapping.get("ID")
            id_new = new_col_mapping.get("ID")
            if str(id_prev) != str(id_new):
                return False
            if not id_new or id_new not in new_data.columns:
                return False
            if not isinstance(self._point_data_map, dict) or not self._point_data_map:
                return False
            existing_ids = {
                str(v.get("id"))
                for v in self._point_data_map.values()
                if isinstance(v, dict) and v.get("id") is not None
            }
            new_ids = {str(v) for v in new_data[id_new].astype(str).tolist()}
            return new_ids.issubset(existing_ids)
        except Exception:
            return False

    def _build_contour_payload(self):
        return self._payload_builder.build_contour_payload()

    def _apply_dynamic_contours_visual_only(self):
        self._runtime_renderer.apply_dynamic_contours_visual_only()

    def toggle_geology_panel(self):
        """Toggle the visibility of the geology panel via JS."""
        self.web_view.page().runJavaScript("toggleGeologyPanel();")

    def set_geology_panel_visible(self, visible: bool):
        """Force geology panel open/closed (non-toggle)."""
        js = f"""
        (function(){{
            var panel = document.getElementById('geologyPanel');
            if (!panel) return;
            panel.classList.toggle('visible', {str(bool(visible)).lower()});
        }})();
        """
        self.web_view.page().runJavaScript(js)

    def set_geology_panel_loading(self, message: str):
        """Show a lightweight loading/error message inside the geology panel."""
        msg = str(message or "").strip() or "Loading..."
        lower = msg.lower()
        state = "loading"
        if ("failed" in lower) or ("error" in lower) or ("invalid" in lower) or ("required" in lower) or ("no " in lower and "model" in lower):
            state = "error"
        js = f"""
        (function(){{
            var panel = document.getElementById('geologyPanel');
            if (panel) panel.classList.add('visible');
            if (window.__haGeoDK && window.__haGeoDK.__setState) {{
                window.__haGeoDK.__setState({json.dumps(state)}, {json.dumps('Loading' if state=='loading' else 'Error')}, {json.dumps(msg)});
            }}
        }})();
        """
        self.web_view.page().runJavaScript(js)

    def set_geology_panel_svg(self, *, svg_html: str, info_text: str = "", legend_html: str = ""):
        """Render Geo.dk SVG + legend into the geology panel."""
        svg = str(svg_html or "")
        info = str(info_text or "")
        legend = str(legend_html or "")
        # Store data for active transect (for multi-transect support)
        if svg:
            self.store_active_transect_data(svg_data=svg, legend_html=legend)
        # Important: do NOT inline the raw <svg> into the map DOM.
        # Geo.dk SVG contains generic CSS selectors (e.g. `svg { background-color: white; }`)
        # which will affect Leaflet's own <svg> overlay and "white out" the map.
        try:
            b64 = base64.b64encode(svg.encode("utf-8")).decode("ascii")
            data_url = f"data:image/svg+xml;base64,{b64}"
            svg_payload = (
                "<img class=\"geology-svg-img\" alt=\"Geo.dk cross section\" "
                f"src=\"{data_url}\" />"
            )
        except Exception:
            svg_payload = ""
        js = f"""
        (function(){{
            var panel = document.getElementById('geologyPanel');
            if (panel) panel.classList.add('visible');
            var infoEl = document.getElementById('geologyInfo');
            if (infoEl && {str(bool(info)).lower()}) infoEl.innerText = {json.dumps(info)};
            // svg_payload is an <img ... src="data:..."> tag; inject into the dedicated viewer <img>.
            var img = document.getElementById('geologySvgImg');
            try {{
                // Extract the data URL from the <img> payload string.
                var tmp = document.createElement('div');
                tmp.innerHTML = {json.dumps(svg_payload)};
                var injected = tmp.querySelector('img');
                if (img && injected && injected.getAttribute) {{
                    img.src = injected.getAttribute('src') || '';
                }}
            }} catch(err) {{}}
            if (window.__haGeoDK && window.__haGeoDK.__setState) {{
                window.__haGeoDK.__setState('ready', 'Ready', 'Loaded. If polygons are 0, try another model or a different line.');
            }}
            if (window.__haGeoDK && window.__haGeoDK.__setLegendHtml) {{
                window.__haGeoDK.__setLegendHtml({json.dumps(legend)} || '');
            }}
        }})();
        """
        self.web_view.page().runJavaScript(js)

    def set_geology_panel_legend(self, legend_html: str):
        """Set only the legend HTML in the geology panel."""
        legend = str(legend_html or "")
        js = f"""
        (function(){{
            if (window.__haGeoDK && window.__haGeoDK.__setLegendHtml) {{
                window.__haGeoDK.__setLegendHtml({json.dumps(legend)} || '');
            }}
        }})();
        """
        self.web_view.page().runJavaScript(js)

    def set_geodk_panel_models(
        self,
        *,
        models: list,
        default_geomodelid: int | None = None,
        default_maxdepth: int = -40,
        default_width: int = 1000,
        default_height: int = 320,
        default_borehole_tolerance_m: float = 10.0,
        path_m: float | None = None,
        cache_hit: bool | None = None,
    ) -> None:
        """Populate the Geo.dk request panel (models + defaults)."""
        try:
            import json as _json

            models_json = _json.dumps(models or [])
        except Exception:
            models_json = "[]"
        opts = {
            "geomodelid": default_geomodelid,
            "maxdepth": int(default_maxdepth),
            "width": int(default_width),
            "height": int(default_height),
            "borehole_tolerance_m": float(default_borehole_tolerance_m),
            "path_m": float(path_m) if path_m is not None else None,
            "cache_hit": bool(cache_hit) if cache_hit is not None else None,
        }
        js = f"""
        (function(){{
            var panel = document.getElementById('geologyPanel');
            if (panel) panel.classList.add('visible');
            var infoEl = document.getElementById('geologyInfo');
            if (infoEl) {{
                var m = {json.dumps(float(path_m) if path_m is not None else None)};
                if (m !== null && m !== undefined && isFinite(Number(m))) {{
                    infoEl.textContent = 'Transect | ' + String(Math.round(Number(m))) + ' m';
                }}
            }}
            if (window.__haGeoDK && window.__haGeoDK.__setModels) {{
                try {{
                    var models = {models_json};
                    window.__haGeoDK.__setModels(models, {json.dumps(opts)});
                }} catch(err) {{}}
            }}
        }})();
        """
        self.web_view.page().runJavaScript(js)

    def set_geodk_panel_diag(self, diag: dict) -> None:
        """Update the Diagnostics tab JSON."""
        js = f"""
        (function(){{
            if (window.__haGeoDK && window.__haGeoDK.__setDiagJson) {{
                window.__haGeoDK.__setDiagJson({json.dumps(diag or {})});
            }}
        }})();
        """
        self.web_view.page().runJavaScript(js)

    def set_geodk_panel_metrics(
        self,
        *,
        polygons: int | None = None,
        cache_hit: bool | None = None,
    ) -> None:
        """Update key metrics row (best-effort)."""
        payload = {
            "polygons": int(polygons) if polygons is not None else None,
            "cache_hit": bool(cache_hit) if cache_hit is not None else None,
        }
        js = f"""
        (function(){{
            var p = {json.dumps(payload)};
            try {{
                if (p.polygons !== null && p.polygons !== undefined) {{
                    var el = document.getElementById('geoMetricPoly');
                    if (el) el.textContent = String(p.polygons);
                }}
                if (p.cache_hit !== null && p.cache_hit !== undefined) {{
                    var el2 = document.getElementById('geoMetricCache');
                    if (el2) el2.textContent = (p.cache_hit ? 'HIT' : 'MISS');
                }}
            }} catch(err) {{}}
        }})();
        """
        self.web_view.page().runJavaScript(js)

    def set_geodk_boreholes_overlay(self, *, items: list[dict], viewbox_w: float, viewbox_h: float) -> None:
        """Render borehole overlays (vertical black lines) on top of the SVG image."""
        payload = {
            "items": list(items or []),
            "viewbox": {"w": float(viewbox_w), "h": float(viewbox_h)},
        }
        js = f"""
        (function(){{
            try {{
                if (window.__haGeoDK && window.__haGeoDK.__setBoreholesOverlay) {{
                    window.__haGeoDK.__setBoreholesOverlay({json.dumps(payload["items"])}, {json.dumps(payload["viewbox"])});
                }}
            }} catch(err) {{}}
        }})();
        """
        self.web_view.page().runJavaScript(js)
    
    def _on_tile_changed(self, tile_name):
        """Handle tile provider change."""
        self._current_tile = tile_name
        if self._current_data is not None:
            self._rerender_map()
        else:
            self._show_empty_map()

    def _on_point_clicked(self, point_id):
        self._interaction_controller.on_point_clicked(point_id)

    def _resolve_point_payload(self, point_ref):
        return self._interaction_controller.resolve_point_payload(point_ref)

    def _on_transect_drawn(self, coords):
        self._interaction_controller.on_transect_drawn(coords)

    def _on_transect_selected(self, transect_id: str):
        """Handle transect selection from Legend panel."""
        transect_id = str(transect_id or "").strip()
        if not transect_id or transect_id == self._active_transect_id:
            return  # Already selected
        # Find the transect
        for t in self._transects:
            if t.get("id") == transect_id:
                self._active_transect_id = transect_id
                self._transect_coords = t.get("coords")
                # Restore SVG and legend if available
                svg_data = t.get("svg_data")
                legend_html = t.get("legend_html")
                if svg_data:
                    # Temporarily disable storing to avoid re-storing the same data
                    self._restoring_transect = True
                    self.set_geology_panel_svg(svg_html=svg_data, legend_html=legend_html or "")
                    self._restoring_transect = False
                elif legend_html:
                    self.set_geology_panel_legend(legend_html)
                else:
                    # No stored data - emit signal so main_window can fetch
                    if self._transect_coords:
                        self.transectCreated.emit(self._transect_coords)
                break
        self._update_transect_lines_panel()
        self._redraw_all_transect_lines()

    def _on_transect_deleted(self, transect_id: str):
        """Handle transect deletion."""
        transect_id = str(transect_id or "").strip()
        if not transect_id:
            return
        # Remove the transect from list
        self._transects = [t for t in self._transects if t.get("id") != transect_id]
        # If we deleted the active transect, switch to another or clear
        if self._active_transect_id == transect_id:
            if self._transects:
                self._active_transect_id = self._transects[-1].get("id")
                self._transect_coords = self._transects[-1].get("coords")
                # Restore last transect's SVG/legend
                svg_data = self._transects[-1].get("svg_data")
                legend_html = self._transects[-1].get("legend_html")
                if svg_data:
                    self.set_geology_panel_svg(svg_html=svg_data, legend_html=legend_html or "")
                elif legend_html:
                    self.set_geology_panel_legend(legend_html)
            else:
                self._active_transect_id = None
                self._transect_coords = None
                # Clear the geology panel
                self.set_geology_panel_svg(svg_html="", legend_html="")
        self._update_transect_lines_panel()
        self._redraw_all_transect_lines()

    def _on_transect_visibility_toggled(self, transect_id: str):
        """Handle transect visibility toggle."""
        transect_id = str(transect_id or "").strip()
        if not transect_id:
            return
        for t in self._transects:
            if t.get("id") == transect_id:
                t["visible"] = not t.get("visible", True)
                break
        self._update_transect_lines_panel()
        self._redraw_all_transect_lines()

    def _on_transect_renamed(self, transect_id: str, new_name: str):
        """Handle transect rename."""
        transect_id = str(transect_id or "").strip()
        new_name = str(new_name or "").strip()
        if not transect_id or not new_name:
            return
        for t in self._transects:
            if t.get("id") == transect_id:
                t["name"] = new_name
                break
        self._update_transect_lines_panel()

    def _update_transect_lines_panel(self):
        """Update the transect lines list in the Layers panel."""
        import json
        transects_data = [
            {
                "id": t.get("id"),
                "name": t.get("name"),
                "color": t.get("color", "#f472b6"),
                "desc": t.get("desc", ""),
                "visible": t.get("visible", True),
            }
            for t in self._transects
        ]
        active_id = self._active_transect_id or ""
        js = f"""
        (function(){{
            if(window.__updateTransectLinesPanel){{
                window.__updateTransectLinesPanel({json.dumps(transects_data)}, {json.dumps(active_id)});
            }}
        }})();
        """
        self.web_view.page().runJavaScript(js)

    def _redraw_all_transect_lines(self):
        """Redraw all visible transect lines on the map."""
        # This will be implemented to draw polylines for each visible transect
        import json
        visible_transects = [t for t in self._transects if t.get("visible", True)]
        lines_data = []
        for t in visible_transects:
            coords = t.get("coords", [])
            if coords:
                lines_data.append({
                    "id": t.get("id"),
                    "coords": coords,
                    "color": t.get("color", "#f472b6"),
                    "active": t.get("id") == self._active_transect_id,
                })
        js = f"""
        (function(){{
            if(window.__drawTransectLines){{
                window.__drawTransectLines({json.dumps(lines_data)});
            }}
        }})();
        """
        self.web_view.page().runJavaScript(js)

    def store_active_transect_data(self, svg_data: str = None, legend_html: str = None):
        """Store SVG and legend data for the active transect."""
        # Skip storing if we're currently restoring data (avoid re-storing the same data)
        if getattr(self, '_restoring_transect', False):
            return
        if not self._active_transect_id:
            return
        for t in self._transects:
            if t.get("id") == self._active_transect_id:
                if svg_data is not None:
                    t["svg_data"] = svg_data
                if legend_html is not None:
                    t["legend_html"] = legend_html
                break

    def _on_map_clicked(self, lat, lon):
        self._interaction_controller.on_map_clicked(lat, lon)

    def _fit_bounds(self):
        """Fit map to data bounds."""
        if self._current_data is None or self._current_col_mapping is None:
            return
        try:
            x_col = self._current_col_mapping.get('x')
            y_col = self._current_col_mapping.get('y')
            if not x_col or not y_col:
                return
            d = self._current_data
            if d is None or d.empty:
                return
            transformer = self._get_transformer()
            lats = []
            lons = []
            for _, row in d.iterrows():
                try:
                    wgs = self._read_wgs84_from_row(row)
                    if wgs is not None:
                        lon, lat = wgs
                    else:
                        projected = self._project_xy_to_wgs84(float(row[x_col]), float(row[y_col]), transformer=transformer)
                        if projected is None:
                            continue
                        lon, lat = projected
                    lats.append(float(lat))
                    lons.append(float(lon))
                except Exception:
                    continue
            if len(lats) < 2:
                return
            bounds = [[min(lats), min(lons)], [max(lats), max(lons)]]
            js = f"""
            (function(){{
                try {{
                    if (!map && window.findMap) window.findMap();
                    if (map && map.fitBounds) map.fitBounds({json.dumps(bounds)});
                }} catch (err) {{}}
            }})();
            """
            self.web_view.page().runJavaScript(js)
        except Exception:
            return

    def _set_transect_mode(self, enabled):
        """Enable/disable transect drawing mode."""
        self._transect_mode = bool(enabled)
        self._apply_layer_panel_state_only()
        self._apply_overlay_visibility_only()
        # JS runtime (`ui/map/transect_runtime.py`) handles the actual click-to-draw behavior.

    def _export_map(self, format_type):
        """Export the map."""
        pass

    def set_layer_visibility(self, layer_name, visible):
        """Set visibility of a layer."""
        changed = False
        requires_rerender = False

        if layer_name == 'points':
            if self._show_points != visible:
                self._show_points = visible
                self._apply_points_visibility_only()
                self._apply_layer_panel_state_only()
                changed = True
        elif layer_name == 'excluded':
            if self._show_excluded != visible:
                self._show_excluded = visible
                self._apply_points_visibility_only()
                self._apply_layer_panel_state_only()
                changed = True
        elif layer_name == 'external':
            if self._show_external != visible:
                self._show_external = visible
                changed = True
        elif layer_name == 'heatmap':
            if self._show_heatmap != visible:
                self._show_heatmap = visible
                changed = True
        elif layer_name == 'coverage':
            if self._show_coverage != visible:
                self._show_coverage = visible
                changed = True
                if self._current_data is not None:
                    self._apply_dynamic_coverage_visual_only()
        elif layer_name == 'vectors':
            if self._show_vectors != visible:
                self._show_vectors = visible
                changed = True
                if self._current_data is not None:
                    self._apply_dynamic_vectors_visual_only()
        elif layer_name == 'main_arrow':
            if self._show_main_arrow != visible:
                self._show_main_arrow = visible
                changed = True
                if self._current_data is not None:
                    self._apply_dynamic_vectors_visual_only()
        elif layer_name == 'contours':
            if self._show_contours != visible:
                self._show_contours = visible
                changed = True
                if self._current_data is not None:
                    self._apply_dynamic_contours_visual_only()
        elif layer_name == 'transect':
            next_visible = bool(visible)
            if self._transect_mode != next_visible:
                self._transect_mode = next_visible
                changed = True
            btn = getattr(self.toolbar, "transect_btn", None)
            if btn is not None and bool(btn.isChecked()) != next_visible:
                btn.blockSignals(True)
                btn.setChecked(next_visible)
                btn.blockSignals(False)

        if changed:
            if requires_rerender and self._current_data is not None:
                self._rerender_map()
                return
            self._apply_layer_panel_state_only()
            self._apply_overlay_visibility_only()

    def _apply_points_visibility_only(self):
        """Toggle point marker visibility in DOM without full map rebuild."""
        js = build_apply_points_visibility_js(
            show_points=bool(self._show_points),
            show_excluded=bool(self._show_excluded),
            labels_on=bool(self._show_labels),
        )
        self.web_view.page().runJavaScript(js)

    def _apply_layer_panel_state_only(self):
        """Keep layer checkmarks consistent with internal layer state."""
        state = self._layer_state_payload()
        js = f"""
        (function(){{
            if(window.__setMapLayerState) window.__setMapLayerState({json.dumps(state)});
            else if(window.__applyLayerPanelState) window.__applyLayerPanelState({json.dumps(state)});
        }})();
        """
        self.web_view.page().runJavaScript(js)

    def _apply_overlay_visibility_only(self):
        """Toggle analysis overlays in DOM without rebuilding the map."""
        state = self._layer_state_payload()
        js = f"""
        (function(){{
            if(window.__setMapLayerState) window.__setMapLayerState({json.dumps(state)});
            else if(window.__applyOverlayVisibility) window.__applyOverlayVisibility({json.dumps(state)});
        }})();
        """
        self.web_view.page().runJavaScript(js)

    def set_heatmap_opacity(self, value):
        """Set heatmap opacity (0.0 - 1.0)."""
        self._heatmap_opacity = max(0.0, min(1.0, value))
        # Apply immediately to current heat layer if present.
        js = f"""
        (function(){{
            var el = document.querySelector('.leaflet-heatmap-layer');
            if (el) el.style.opacity = String({self._heatmap_opacity});
        }})();
        """
        self.web_view.page().runJavaScript(js)

    def set_heatmap_mode(self, mode):
        """Set heatmap mode: smooth | hex."""
        mode = str(mode).strip().lower()
        if mode not in {"smooth", "hex"}:
            mode = "smooth"
        if self._heatmap_mode == mode:
            return
        self._heatmap_mode = mode
        if self._current_data is not None and self._show_heatmap:
            self._rerender_map()

    def set_point_size(self, size_px):
        """Set point size (px)."""
        try:
            size_px = int(size_px)
        except Exception:
            return
        size_px = max(2, min(32, size_px))
        if size_px == self._point_size:
            return
        self._point_size = size_px
        # Apply in-place visual scale to avoid full map flash/reload.
        self._apply_point_size_visual_only()

    def set_scale_bar_visibility(self, visible):
        """Set visibility of scale bar."""
        self._show_scale_bar = visible
        display = "block" if visible else "none"
        js = f"""
        (function() {{
            var el = document.querySelector('.map-scale');
            if (el) el.style.display = '{display}';
        }})();
        """
        self.web_view.page().runJavaScript(js)

    def set_sync_selection_enabled(self, enabled):
        """Enable/disable selection synchronization with plot."""
        self._sync_selection = enabled

    def set_labels_visibility(self, enabled):
        """Enable/disable point ID labels."""
        enabled = bool(enabled)
        if self._show_labels == enabled:
            return
        self._show_labels = enabled
        if enabled and self._current_data is not None:
            # Labels are created at render time; rebuild once when turning on.
            self._rerender_map()
            return
        js = build_set_labels_visibility_js(visible=bool(enabled))
        self.web_view.page().runJavaScript(js)

    def set_contour_labels_visibility(self, enabled):
        enabled = bool(enabled)
        if self._show_contour_labels == enabled:
            return
        self._show_contour_labels = enabled
        js = f"""
        (function(){{
            var visible = {str(bool(enabled)).lower()};
            document.querySelectorAll('.contour-line-label').forEach(function(el){{
                el.style.display = visible ? '' : 'none';
            }});
        }})();
        """
        self.web_view.page().runJavaScript(js)

    def set_contour_label_precision(self, digits):
        try:
            digits = int(digits)
        except Exception:
            return
        digits = max(0, min(3, digits))
        if self._contour_label_precision == digits:
            return
        self._contour_label_precision = digits
        js = f"""
        (function(){{
            var d = {int(digits)};
            document.querySelectorAll('.contour-line-label div[data-level]').forEach(function(el){{
                var raw = Number(el.getAttribute('data-level'));
                if (!isFinite(raw)) return;
                el.textContent = raw.toFixed(d);
            }});
        }})();
        """
        self.web_view.page().runJavaScript(js)

    def set_contour_major_interval(self, every_n):
        try:
            every_n = int(every_n)
        except Exception:
            return
        every_n = max(1, min(8, every_n))
        if self._contour_major_interval == every_n:
            return
        self._contour_major_interval = every_n
        js = f"""
        (function(){{
            if (window.__applyContourMajorInterval) window.__applyContourMajorInterval({int(every_n)});
        }})();
        """
        self.web_view.page().runJavaScript(js)
        if bool(self._show_contours):
            self._apply_dynamic_contours_visual_only()

    def set_contour_fill_opacity(self, opacity):
        try:
            opacity = float(opacity)
        except Exception:
            return
        opacity = max(0.0, min(1.0, opacity))
        if abs(self._contour_fill_opacity - opacity) < 1e-9:
            return
        self._contour_fill_opacity = opacity
        js = f"""
        (function(){{
            var op = {float(opacity)};
            document.querySelectorAll('.overlay-contours-fill').forEach(function(el){{
                try {{
                    el.style.fillOpacity = String(op);
                    el.setAttribute('fill-opacity', String(op));
                }} catch(err) {{}}
            }});
        }})();
        """
        self.web_view.page().runJavaScript(js)

    def set_contour_label_font_size(self, size_px):
        try:
            size_px = int(size_px)
        except Exception:
            return
        size_px = max(8, min(24, size_px))
        if self._contour_label_font_size == size_px:
            return
        self._contour_label_font_size = size_px
        js = f"""
        (function(){{
            var fs = {int(size_px)} + 'px';
            document.querySelectorAll('.contour-line-label div').forEach(function(el){{
                el.style.fontSize = fs;
            }});
        }})();
        """
        self.web_view.page().runJavaScript(js)


    def set_selected_point(self, point_id):
        self._interaction_controller.set_selected_point(point_id)

    def clear_selected_point(self):
        self._interaction_controller.clear_selected_point()

    def _apply_selection_visual_only(self, point_id):
        self._interaction_controller.apply_selection_visual_only(point_id)

    def _apply_point_size_visual_only(self):
        """Update marker radii in-place without rebuilding map."""
        if self._current_data is None:
            return
        js = f"""
        (function(){{
            if (window.__applyPointRadius) window.__applyPointRadius({int(self._point_size)});
        }})();
        """
        self.web_view.page().runJavaScript(js)

    def _apply_exclusions_visual_only(self):
        """Update marker inclusion/exclusion styling in-place without rebuilding map."""
        if self._current_data is None:
            return
        if bool(self._color_points_by_head) and self._current_col_mapping is not None:
            self._refresh_point_color_payload_for_data(self._current_data, self._current_col_mapping)
        excluded_ids_json = json.dumps(sorted(self._excluded_ids))
        js = f"""
        (function(){{
            var excludedSet = new Set({excluded_ids_json});
            var points = window.__mapPointData || {{}};
            var selectedIdx = (window.__selectedPointIdx===undefined||window.__selectedPointIdx===null)?null:String(window.__selectedPointIdx);
            var showPoints = {str(bool(self._show_points)).lower()};
            var showExcluded = {str(bool(self._show_excluded)).lower()};
            var useValueColor = {str(bool(self._color_points_by_head)).lower()};
            var defaultColor = {json.dumps(self.COLORS["points"])};
            var selectedColor = {json.dumps(self.COLORS["selected"])};
            var excludedColor = {json.dumps(self.COLORS["excluded"])};
            document.querySelectorAll('.point-marker').forEach(function(el){{
                try {{
                    var cls = '';
                    if (typeof el.className === 'string') cls = el.className;
                    else if (el.className && typeof el.className.baseVal === 'string') cls = el.className.baseVal;
                    else if (el.getAttribute) cls = el.getAttribute('class') || '';
                    var idxMatch = String(cls).match(/point-idx-([\\w-]+)/);
                    var idx = idxMatch ? String(idxMatch[1]) : null;
                    var pdata = (idx && points[idx]) ? points[idx] : null;
                    if (!pdata) return;
                    var pid = String(pdata.id || '');
                    var isExcluded = excludedSet.has(pid);
                    var isSelected = !!(selectedIdx && idx && selectedIdx === idx);

                    // Keep data payload status in sync (tooltip/selection card consumers).
                    pdata.status = isExcluded ? 'Excluded' : 'Included';
                    pdata.excluded = !!isExcluded;

                    // Keep class names aligned with layer toggles.
                    if (isExcluded) {{
                        el.classList.remove('active');
                        el.classList.add('excluded');
                        el.style.display = showExcluded ? '' : 'none';
                        el.style.fill = excludedColor;
                        el.setAttribute('fill', excludedColor);
                        el.style.stroke = '#111111';
                        el.setAttribute('stroke', '#111111');
                        el.style.strokeWidth = '3px';
                        el.style.strokeDasharray = '4,4';
                        el.style.fillOpacity = '0.4';
                        el.style.opacity = '0.9';
                    }} else {{
                        el.classList.remove('excluded');
                        el.classList.add('active');
                        el.style.display = showPoints ? '' : 'none';
                        var baseColor = (useValueColor && pdata.point_color) ? String(pdata.point_color) : defaultColor;
                        var fill = isSelected ? selectedColor : baseColor;
                        el.style.fill = fill;
                        el.setAttribute('fill', fill);
                        el.style.stroke = '#111111';
                        el.setAttribute('stroke', '#111111');
                        el.style.strokeDasharray = '';
                        el.style.strokeWidth = isSelected ? '4px' : '3px';
                        el.style.fillOpacity = '0.95';
                        el.style.opacity = isSelected ? '0.95' : '0.8';
                    }}
                }} catch(err) {{}}
            }});
            if(window.__setMapLayerState){{
                window.__setMapLayerState({{
                    points: showPoints,
                    excluded: showExcluded
                }});
            }} else if(window.__applyLegendState){{
                window.__applyLegendState({{
                    points: showPoints,
                    excluded: showExcluded,
                    external: {str(bool(self._show_external)).lower()},
                    heatmap: {str(bool(self._show_heatmap)).lower()},
                    coverage: {str(bool(self._show_coverage)).lower()},
                    vectors: {str(bool(self._show_vectors)).lower()},
                    main_arrow: {str(bool(self._show_main_arrow)).lower()},
                    contours: {str(bool(self._show_contours)).lower()},
                    transect: {str(bool(self._transect_mode)).lower()}
                }});
            }}
        }})();
        """
        self.web_view.page().runJavaScript(js)

    def _apply_filtered_points_visual_only(self, new_data, col_mapping):
        """
        Apply filter-only point visibility updates in-place.
        Returns True when update was applied, False when caller should fallback to full rerender.
        """
        if self._current_data is None or new_data is None or col_mapping is None:
            return False
        id_col = col_mapping.get("ID")
        if not id_col or id_col not in new_data.columns:
            return False
        try:
            visible_ids = {str(v) for v in new_data[id_col].astype(str).tolist()}
        except Exception:
            return False
        if not isinstance(self._point_data_map, dict) or not self._point_data_map:
            return False
        existing_ids = {str(v.get("id")) for v in self._point_data_map.values() if isinstance(v, dict) and v.get("id") is not None}
        if not visible_ids.issubset(existing_ids):
            return False

        if bool(self._color_points_by_head):
            self._refresh_point_color_payload_for_data(new_data, col_mapping)

        visible_ids_json = json.dumps(sorted(visible_ids))
        excluded_ids_json = json.dumps(sorted(self._excluded_ids))
        js = f"""
        (function(){{
            var visibleSet = new Set({visible_ids_json});
            var excludedSet = new Set({excluded_ids_json});
            var points = window.__mapPointData || {{}};
            var selectedIdx = (window.__selectedPointIdx===undefined||window.__selectedPointIdx===null)?null:String(window.__selectedPointIdx);
            var showPoints = {str(bool(self._show_points)).lower()};
            var showExcluded = {str(bool(self._show_excluded)).lower()};
            var useValueColor = {str(bool(self._color_points_by_head)).lower()};
            var defaultColor = {json.dumps(self.COLORS["points"])};
            var selectedColor = {json.dumps(self.COLORS["selected"])};
            var excludedColor = {json.dumps(self.COLORS["excluded"])};
            var selectedStillVisible = false;

            document.querySelectorAll('.point-marker').forEach(function(el){{
                try {{
                    var cls = '';
                    if (typeof el.className === 'string') cls = el.className;
                    else if (el.className && typeof el.className.baseVal === 'string') cls = el.className.baseVal;
                    else if (el.getAttribute) cls = el.getAttribute('class') || '';
                    var idxMatch = String(cls).match(/point-idx-([\\w-]+)/);
                    var idx = idxMatch ? String(idxMatch[1]) : null;
                    var pdata = (idx && points[idx]) ? points[idx] : null;
                    if (!pdata) return;
                    var pid = String(pdata.id || '');
                    var isInFilter = visibleSet.has(pid);
                    var isExcluded = excludedSet.has(pid);
                    var isSelected = !!(selectedIdx && idx && selectedIdx === idx);
                    if (isSelected && isInFilter) selectedStillVisible = true;

                    if (!isInFilter) {{
                        el.style.display = 'none';
                        return;
                    }}

                    pdata.status = isExcluded ? 'Excluded' : 'Included';
                    pdata.excluded = !!isExcluded;

                    if (isExcluded) {{
                        el.classList.remove('active');
                        el.classList.add('excluded');
                        el.style.display = showExcluded ? '' : 'none';
                        el.style.fill = excludedColor;
                        el.setAttribute('fill', excludedColor);
                        el.style.stroke = '#111111';
                        el.setAttribute('stroke', '#111111');
                        el.style.strokeWidth = '3px';
                        el.style.strokeDasharray = '4,4';
                        el.style.fillOpacity = '0.4';
                        el.style.opacity = '0.9';
                    }} else {{
                        el.classList.remove('excluded');
                        el.classList.add('active');
                        el.style.display = showPoints ? '' : 'none';
                        var baseColor = (useValueColor && pdata.point_color) ? String(pdata.point_color) : defaultColor;
                        var fill = isSelected ? selectedColor : baseColor;
                        el.style.fill = fill;
                        el.setAttribute('fill', fill);
                        el.style.stroke = '#111111';
                        el.setAttribute('stroke', '#111111');
                        el.style.strokeDasharray = '';
                        el.style.strokeWidth = isSelected ? '4px' : '3px';
                        el.style.fillOpacity = '0.95';
                        el.style.opacity = isSelected ? '0.95' : '0.8';
                    }}
                }} catch(err) {{}}
            }});

            if (!selectedStillVisible) {{
                window.__selectedPointIdx = null;
                if (window.clearSelectionPanel) window.clearSelectionPanel();
            }}

            if(window.__setMapLayerState){{
                window.__setMapLayerState({{
                    points: showPoints,
                    excluded: showExcluded
                }});
            }} else if(window.__applyLegendState){{
                window.__applyLegendState({{
                    points: showPoints,
                    excluded: showExcluded,
                    external: {str(bool(self._show_external)).lower()},
                    heatmap: {str(bool(self._show_heatmap)).lower()},
                    coverage: {str(bool(self._show_coverage)).lower()},
                    vectors: {str(bool(self._show_vectors)).lower()},
                    main_arrow: {str(bool(self._show_main_arrow)).lower()},
                    contours: {str(bool(self._show_contours)).lower()},
                    transect: {str(bool(self._transect_mode)).lower()}
                }});
            }}
        }})();
        """
        self.web_view.page().runJavaScript(js)
        if str(self._selected_id) not in visible_ids:
            self._selected_id = None
            self._selected_point_data = None
            self.pointDeselected.emit()
        return True

    def _apply_point_colors(self, coords_data):
        self._payload_builder.apply_point_colors(coords_data)

    def _refresh_point_color_payload(self):
        self._payload_builder.refresh_point_color_payload()

    def _refresh_point_color_payload_for_data(self, data, col_mapping):
        self._payload_builder.refresh_point_color_payload_for_data(data, col_mapping)

    def set_point_color_by_value(self, enabled):
        enabled = bool(enabled)
        if self._current_data is None:
            return
        if self._color_points_by_head == enabled:
            if enabled:
                self._refresh_point_color_payload()
            else:
                return
        self._color_points_by_head = enabled
        self._refresh_point_color_payload()
        js = f"""
        (function(){{
            var t=document.getElementById('pointColorToggle');
            if(t) t.classList.toggle('on', {str(bool(enabled)).lower()});
            if(window.__applyPointColorMode) window.__applyPointColorMode({str(bool(enabled)).lower()});
            if(window.__setMapLayerState){{
                window.__setMapLayerState(window.__mapLayerState || {{
                    points: {str(bool(self._show_points)).lower()},
                    excluded: {str(bool(self._show_excluded)).lower()},
                    external: {str(bool(self._show_external)).lower()},
                    heatmap: {str(bool(self._show_heatmap)).lower()},
                    coverage: {str(bool(self._show_coverage)).lower()},
                    vectors: {str(bool(self._show_vectors)).lower()},
                    main_arrow: {str(bool(self._show_main_arrow)).lower()},
                    contours: {str(bool(self._show_contours)).lower()},
                    transect: {str(bool(self._transect_mode)).lower()}
                }});
            }} else if(window.__applyLegendState){{
                window.__applyLegendState({{
                    points: {str(bool(self._show_points)).lower()},
                    excluded: {str(bool(self._show_excluded)).lower()},
                    external: {str(bool(self._show_external)).lower()},
                    heatmap: {str(bool(self._show_heatmap)).lower()},
                    coverage: {str(bool(self._show_coverage)).lower()},
                    vectors: {str(bool(self._show_vectors)).lower()},
                    main_arrow: {str(bool(self._show_main_arrow)).lower()},
                    contours: {str(bool(self._show_contours)).lower()},
                    transect: {str(bool(self._transect_mode)).lower()}
                }});
            }}
        }})();
        """
        self.web_view.page().runJavaScript(js)

    def clear_map(self):
        """Clear the map."""
        self._current_data = None
        self._current_col_mapping = None
        self._current_triangle_data = None
        self._current_gradient_data = None
        self._current_rejected_data = None
        self._excluded_ids = set()
        self._selected_id = None
        self._selected_point_data = None
        self._point_data_map = {}
        self._point_data_by_id = {}
        self._show_empty_map(reason="clear_map")

    def refresh_map(self):
        """Public helper to rebuild map with current payload."""
        self._rerender_map()

    def apply_theme(self):
        if hasattr(self, "toolbar") and self.toolbar is not None:
            self.toolbar.apply_theme()
        if hasattr(self, "web_view") and self.web_view is not None:
            self.web_view.setStyleSheet(f"background: {Colors.BG_APP};")
        if self._current_data is not None:
            self._rerender_map()
        else:
            self._show_empty_map(reason="theme")

    def apply_contour_visual_settings(self, *, show_labels, label_precision, major_interval, label_font_size, fill_opacity):
        """Apply contour display settings in one pass, then re-render once."""
        self._show_contour_labels = bool(show_labels)
        try:
            self._contour_label_precision = max(0, min(3, int(label_precision)))
        except Exception:
            self._contour_label_precision = 2
        try:
            self._contour_major_interval = max(1, min(8, int(major_interval)))
        except Exception:
            self._contour_major_interval = 2
        try:
            self._contour_label_font_size = max(8, min(24, int(label_font_size)))
        except Exception:
            self._contour_label_font_size = 12
        try:
            self._contour_fill_opacity = max(0.0, min(1.0, float(fill_opacity)))
        except Exception:
            self._contour_fill_opacity = 0.22
        if self._current_data is not None:
            self._rerender_map()

    def _rerender_map(self):
        """Re-render map using full last-known payload."""
        if self._current_data is None:
            return
        self.update_map(
            self._current_data,
            self._current_col_mapping,
            self._excluded_ids,
            triangle_data=self._current_triangle_data,
            gradient_data=self._current_gradient_data,
            rejected_data=self._current_rejected_data,
            force=True,
        )
