"""Render/runtime helpers extracted from MapWidget."""

import json
import os
import tempfile
from pathlib import Path

import numpy as np
from PyQt5.QtCore import QUrl

from styles.colors import Colors
from ..map_resources import CONCEPT_HTML_OVERLAYS, CONCEPT_JS, CONCEPT_PROPERTIES_SIDEBAR, get_concept_css
from .analysis_overlays import (
    build_replace_dynamic_coverage_js,
    build_replace_dynamic_vectors_js,
)
from .contours import (
    build_replace_dynamic_contours_js,
    build_set_contour_layers_visible_js,
)
from .heatmap import build_replace_dynamic_heatmap_js
from .layers_runtime import build_layers_runtime_js
from .legend_runtime import build_legend_runtime_js
from .external_layers_runtime import build_external_layers_runtime_js
from .point_labels import (
    build_point_label_contract_js,
)
from .points_runtime import build_points_runtime_js
from .transect_runtime import build_transect_runtime_js, build_transect_lines_js
from .triangle_overlay import build_replace_triangle_overlay_js


class MapRuntimeRenderer:
    """Rendering runtime and JS contract helpers for MapWidget."""

    def __init__(self, widget):
        self._widget = widget

    def show_empty_map(self, reason: str = "empty"):
        """Show an empty map centered on Denmark."""
        w = self._widget
        try:
            import folium
            import io
            m = folium.Map(
                location=[55.6761, 12.5683],
                zoom_start=7,
                tiles=w._current_tile,
                zoom_control=False,
            )
            self.inject_custom_css(m)
            self.inject_overlays(m)

            data = io.BytesIO()
            m.save(data, close_file=False)
            html = data.getvalue().decode()

            html = self.inject_webchannel(html)
            self.dump_rendered_html(html, reason=f"empty_{reason}")
            w._last_render_kind = "empty"
            print(f"[map] render kind=empty reason={reason}")
            self.set_html_content(html, reason=f"empty_{reason}")
        except ImportError:
            w.web_view.setHtml(self.get_fallback_html())

    def dump_rendered_html(self, html: str, reason: str = "map"):
        """Persist the exact HTML sent to QWebEngineView for debugging."""
        if str(os.getenv("HEADANALYSER_MAP_DEBUG_HTML", "")).strip().lower() not in {"1", "true", "yes", "on"}:
            return
        try:
            root = Path(__file__).resolve().parents[1]
            out_dir = root / ".recovery"
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / f"map_last_render_{reason}.html"
            out_path.write_text(str(html), encoding="utf-8")
            print(f"[map] html_dump={out_path}")
        except Exception as exc:
            print(f"[map] html_dump_failed reason={reason} error={exc}")

    def set_html_content(self, html: str, reason: str = "map"):
        """
        Load HTML through a local file URL.
        setHtml/setContent can fail on large payloads due data-URL size limits.
        """
        w = self._widget
        try:
            out_dir = Path(tempfile.gettempdir()) / "headanalyser_runtime"
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / "map_runtime_render.html"
            out_path.write_text(str(html), encoding="utf-8")
            w.web_view.load(QUrl.fromLocalFile(str(out_path)))
            print(f"[map] load_file bytes={out_path.stat().st_size} reason={reason}")
        except Exception as exc:
            print(f"[map] load_file_failed reason={reason} error={exc}")
            w.web_view.setHtml(html)

    def get_fallback_html(self):
        """Fallback HTML when folium is not installed."""
        return f"""
            <html>
            <body style="background-color: {Colors.BG_DARK}; color: {Colors.TEXT_SECONDARY};
                         display: flex; justify-content: center; align-items: center;
                         height: 100%; margin: 0; font-family: 'Segoe UI', sans-serif;">
                <div style="text-align: center;">
                    <h3 style="color: {Colors.TEXT_PRIMARY};">Map View Unavailable</h3>
                    <p>Install folium: <code>pip install folium</code></p>
                </div>
            </body>
            </html>
        """

    def inject_custom_css(self, m):
        """Inject custom CSS into the folium map."""
        import folium
        style_element = f"<style>{get_concept_css()}</style>"
        m.get_root().html.add_child(folium.Element(style_element))

    def inject_overlays(self, m):
        """Inject HTML overlays (Legend, Panels, etc.)."""
        import folium
        m.get_root().html.add_child(folium.Element(CONCEPT_PROPERTIES_SIDEBAR))
        m.get_root().html.add_child(folium.Element(CONCEPT_HTML_OVERLAYS))
        m.get_root().html.add_child(folium.Element(CONCEPT_JS))
        m.get_root().html.add_child(folium.Element(f"<script>{build_external_layers_runtime_js()}</script>"))

        click_handler_script = """
        <script>
            (function() {
                if (window.__haMarkerDelegateInit) return;
                window.__haMarkerDelegateInit = true;

                function markerClass(el) {
                    if (!el) return '';
                    if (typeof el.className === 'string') return el.className;
                    if (el.className && typeof el.className.baseVal === 'string') return el.className.baseVal;
                    if (el.getAttribute) return el.getAttribute('class') || '';
                    return '';
                }
                function markerElementFromEventTarget(target) {
                    if (!target) return null;
                    var cur = target;
                    while (cur && cur !== document) {
                        try {
                            var cls = markerClass(cur);
                            if (String(cls).indexOf('point-marker') !== -1) return cur;
                        } catch (err) {}
                        cur = cur.parentNode;
                    }
                    return null;
                }
                function markerData(el) {
                    var cls = String(markerClass(el));
                    var m = cls.match(/(?:^|\\s)point-idx-([^\\s]+)/);
                    if (!m || !m[1]) return null;
                    var idx = String(m[1]);
                    var pointMap = window.__mapPointData || {};
                    var d = pointMap[idx];
                    if (!d) return null;
                    return { idx: idx, data: d };
                }

                document.addEventListener('click', function(e) {
                    var el = markerElementFromEventTarget(e.target);
                    if (!el) return;
                    var hit = markerData(el);
                    if (!hit) return;
                    var d = hit.data;
                    if (window.pyBridge) {
                        window.pyBridge.onPointClick(JSON.stringify({
                            id: String(d.id || ''),
                            idx: String(d.idx || hit.idx),
                            member_key: (d.member_key === undefined || d.member_key === null) ? '' : String(d.member_key)
                        }));
                    }
                    if (window.updateSelectionPanel) window.updateSelectionPanel(d);
                }, true);

                document.addEventListener('mousemove', function(e) {
                    var el = markerElementFromEventTarget(e.target);
                    if (!el) {
                        if (window.hideTooltip) window.hideTooltip();
                        return;
                    }
                    var hit = markerData(el);
                    if (!hit) return;
                    if (window.showTooltip) window.showTooltip(hit.data);
                    if (window.moveTooltip) window.moveTooltip(e);
                }, true);
            })();
        </script>
        """
        m.get_root().html.add_child(folium.Element(click_handler_script))

    def inject_webchannel(self, html):
        """Inject QWebChannel JavaScript for Python-JS communication."""
        webchannel_js = """
        <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
        <script>
            var pyBridge = null;
            new QWebChannel(qt.webChannelTransport, function(channel) {
                pyBridge = channel.objects.pyBridge;
                window.pyBridge = pyBridge; // Make globally accessible
            });
        </script>
        """
        return html.replace('</head>', webchannel_js + '</head>')

    def inject_point_data(self, html, points):
        """Inject dynamic point payload and selection panel bootstrap script."""
        w = self._widget
        point_map = {}
        for p in points:
            try:
                point_map[str(p.get('idx'))] = {
                    "idx": str(p.get("idx", "")),
                    "id": str(p.get("id", "")),
                    "member_key": str(p.get("member_key", "")) if p.get("member_key", None) is not None else "",
                    "status": "Excluded" if bool(p.get("excluded")) else "Included",
                    "head": float(p.get("head", 0.0)),
                    "x": float(p.get("x", 0.0)),
                    "y": float(p.get("y", 0.0)),
                    "lat": float(p.get("lat", 0.0)),
                    "lon": float(p.get("lon", 0.0)),
                    "point_color": str(p.get("point_color") or w.COLORS["points"]),
                }
            except Exception:
                continue

        default_data = None
        if isinstance(w._selected_point_data, dict):
            default_data = point_map.get(str(w._selected_point_data.get("idx")))
        if default_data is None and w._selected_id is not None:
            for item in point_map.values():
                if str(item.get("id")) == str(w._selected_id):
                    default_data = item
                    break

        scale_display = "block" if w._show_scale_bar else "none"
        script = (
            "<script>"
            f"window.__mapPointData = {json.dumps(point_map)};"
            "window.updateSelectionPanel = function(data){"
            "if(!data) return;"
            "window.__selectedPointData = data;"
            "window.__selectedPointIdx = (data.idx===undefined||data.idx===null)?null:String(data.idx);"
            "var idEl=document.getElementById('prop-id'); if(idEl) idEl.innerText=String(data.id||'-');"
            "var badge=document.getElementById('prop-badge');"
            "if(badge){"
            "var excluded=String(data.status||'').toLowerCase()==='excluded';"
            "badge.innerText=excluded?'Excluded':'Included';"
            "badge.className='selection-badge ' + (excluded?'excluded':'included');"
            "}"
            "var list=document.getElementById('intakeList');"
            "if(list){"
            "var head=(data.head===null||data.head===undefined||isNaN(Number(data.head)))?'-':Number(data.head).toFixed(2)+' m';"
            "var x=(data.x===null||data.x===undefined||isNaN(Number(data.x)))?'-':Number(data.x).toFixed(1);"
            "var y=(data.y===null||data.y===undefined||isNaN(Number(data.y)))?'-':Number(data.y).toFixed(1);"
            "list.innerHTML=''"
            "+ '<label class=\"intake\" data-selected=\"true\">'"
            "+ '<input type=\"radio\" name=\"intake\" checked>'"
            "+ '<div><div class=\"intake-title\">Point '+String(data.id||'-')+'</div>'"
            "+ '<div class=\"intake-meta\">Head '+head+' | X '+x+' | Y '+y+'</div></div>'"
            "+ '<div class=\"pill\">Selected</div></label>';"
            "}"
            "};"
            "window.clearSelectionPanel = function(){"
            "window.__selectedPointData = null;"
            "window.__selectedPointIdx = null;"
            "var idEl=document.getElementById('prop-id'); if(idEl) idEl.innerText='-';"
            "var badge=document.getElementById('prop-badge');"
            "if(badge){ badge.innerText='None'; badge.className='selection-badge neutral'; }"
            "var list=document.getElementById('intakeList');"
            "if(list){ list.innerHTML='<div class=\"note\" style=\"margin:0;\">No point selected.</div>'; }"
            "};"
            "window.excludeSelectedPoint = function(){"
            "var d=window.__selectedPointData||null;"
            "if(!d) return;"
            "if(window.pyBridge) window.pyBridge.onExcludePointRequested(JSON.stringify({"
            "id:String(d.id||''),"
            "idx:(d.idx===undefined||d.idx===null)?'':String(d.idx),"
            "member_key:(d.member_key===undefined||d.member_key===null)?'':String(d.member_key)"
            "}));"
            "};"
            "window.showSelectedInPlot = function(){"
            "var d=window.__selectedPointData||null;"
            "var id=d?String(d.id||''):'';"
            "if(id && window.pyBridge) window.pyBridge.onShowPointInPlotRequested(id);"
            "};"
            f"window.__mapUiState = {json.dumps({'heatmap_opacity': float(w._heatmap_opacity), 'point_size': int(w._point_size), 'heatmap_mode': str(w._heatmap_mode), 'render_point_size': float(w._render_point_size), 'point_color_by_value': bool(w._color_points_by_head), 'point_labels': bool(w._show_labels)})};"
            f"window.__mapContourState = {json.dumps({'show_labels': bool(w._show_contour_labels), 'label_precision': int(w._contour_label_precision), 'major_interval': int(w._contour_major_interval), 'label_font_size': int(w._contour_label_font_size), 'fill_opacity': float(w._contour_fill_opacity), 'method': str(getattr(w.main_window, 'interpolation_method', 'cubic')), 'levels': int(getattr(w.main_window, 'contour_levels', 10) or 10), 'extent_pct': float(getattr(w.main_window, 'contour_extent_pct', 0) or 0), 'extrapolation': str(getattr(w.main_window, 'contour_extrapolation', 'none')), 'fill_contours': bool(getattr(w.main_window, 'fill_contours', False)), 'line_width': float(getattr(w.main_window, 'contour_linewidth', 0.8))})};"
            f"{build_layers_runtime_js()}"
            f"{build_transect_runtime_js()}"
            f"{build_transect_lines_js()}"
            f"{build_external_layers_runtime_js()}"
            f"{build_set_contour_layers_visible_js()}"
            f"{build_point_label_contract_js(labels_visible=bool(w._show_labels and w._show_points))}"
            f"{build_replace_dynamic_contours_js(contour_color=str(w.COLORS['contours']).lower())}"
            f"{build_replace_dynamic_heatmap_js()}"
            f"{build_replace_dynamic_vectors_js()}"
            f"{build_replace_dynamic_coverage_js()}"
            f"{build_replace_triangle_overlay_js()}"
            "window.__applyPointColorMode = function(enabled){"
            "try{"
            "window.__pointColorByValue = !!enabled;"
            "var selectedIdx=(window.__selectedPointIdx===undefined||window.__selectedPointIdx===null)?null:String(window.__selectedPointIdx);"
            "var points=window.__mapPointData||{};"
            "var markers=document.querySelectorAll('.point-marker');"
            "markers.forEach(function(el){"
            "try{"
            "var cls='';"
            "if(typeof el.className==='string') cls=el.className;"
            "else if(el.className&&typeof el.className.baseVal==='string') cls=el.className.baseVal;"
            "else if(el.getAttribute) cls=el.getAttribute('class')||'';"
            "if(String(cls).indexOf('excluded')!==-1) return;"
            "var idxMatch=String(cls).match(/point-idx-([\\w-]+)/);"
            "var idx=idxMatch?String(idxMatch[1]):null;"
            "var data=(idx&&points[idx])?points[idx]:null;"
            "var baseColor=(enabled&&data&&data.point_color)?String(data.point_color):'#60a5fa';"
            "var isSel=(idx&&selectedIdx&&idx===selectedIdx);"
            "var fill=isSel?'#60a5fa':baseColor;"
            "el.style.fill=fill;"
            "el.setAttribute('fill', fill);"
            "el.style.stroke='white';"
            "el.setAttribute('stroke', 'white');"
            "}catch(err){}"
            "});"
            "}catch(err){}"
            "};"
            f"{build_legend_runtime_js()}"
            f"{build_points_runtime_js()}"
            f"window.__mapPointLegend = {json.dumps(w._point_legend)};"
            f"window.__mapContourLegend = {json.dumps(w._contour_legend)};"
            f"window.__externalLayerCatalog = {json.dumps(w._external_layer_catalog_payload())};"
            "if(window.__setExternalLayerCatalog) window.__setExternalLayerCatalog(window.__externalLayerCatalog);"
            f"var scaleEl=document.querySelector('.map-scale'); if(scaleEl) scaleEl.style.display='{scale_display}';"
            f"var labelsToggle=document.getElementById('labelsToggle'); if(labelsToggle) labelsToggle.classList.toggle('on', {str(bool(w._show_labels)).lower()});"
            f"var pointColorToggle=document.getElementById('pointColorToggle'); if(pointColorToggle) pointColorToggle.classList.toggle('on', {str(bool(w._color_points_by_head)).lower()});"
            f"var syncToggle=document.getElementById('syncToggle'); if(syncToggle) syncToggle.classList.toggle('on', {str(bool(w._sync_selection)).lower()});"
            f"window.__mapLayerState = {json.dumps(w._layer_state_payload())};"
            "if(window.__setMapLayerState) window.__setMapLayerState(window.__mapLayerState);"
            "if(window.__haIndexPointLayers) window.__haIndexPointLayers();"
            "if(window.__haBindPointLayerEvents) window.__haBindPointLayerEvents();"
            "setTimeout(function(){"
            "if(window.__haIndexPointLayers) window.__haIndexPointLayers();"
            "if(window.__haBindPointLayerEvents) window.__haBindPointLayerEvents();"
            "if(window.__setMapLayerState && window.__mapLayerState) window.__setMapLayerState(window.__mapLayerState);"
            "if(window.__applyPointLabelVisibility) window.__applyPointLabelVisibility();"
            "}, 120);"
            "setTimeout(function(){"
            "if(window.__applyPointLabelVisibility) window.__applyPointLabelVisibility();"
            "}, 360);"
            f"window.__applyPointColorMode({str(bool(w._color_points_by_head)).lower()});"
            "if(window.__applyPointLabelVisibility) window.__applyPointLabelVisibility();"
            f"{'window.updateSelectionPanel(' + json.dumps(default_data) + ');' if default_data is not None else 'if(window.clearSelectionPanel) window.clearSelectionPanel();'}"
            "</script>"
        )
        if "</body>" in html:
            return html.replace("</body>", script + "</body>")
        return html + script

    def apply_dynamic_heatmap_visual_only(self):
        """Replace heatmap layer in-place without full map rebuild."""
        w = self._widget
        payload = w._build_heatmap_payload()
        js = f"""
        (function(){{
            if(window.__replaceDynamicHeatmap){{
                window.__replaceDynamicHeatmap({json.dumps(payload)});
            }}
        }})();
        """
        w.web_view.page().runJavaScript(js)

    def add_hex_heatmap(self, feature_group, heatmap_data):
        """Render a lightweight hex-like heatmap variant using quantized bins."""
        w = self._widget
        import folium
        if not heatmap_data:
            return
        try:
            arr = np.array(heatmap_data, dtype=float)
            if arr.ndim != 2 or arr.shape[1] < 3:
                return
            lats = arr[:, 0]
            lons = arr[:, 1]
            weights = arr[:, 2]
            if len(lats) == 0:
                return
            lat_span = max(1e-9, float(np.max(lats) - np.min(lats)))
            lon_span = max(1e-9, float(np.max(lons) - np.min(lons)))
            cell = max(lat_span, lon_span) / 35.0
            bins = {}
            for la, lo, ww in zip(lats, lons, weights):
                key = (int(round(la / cell)), int(round(lo / cell)))
                bins[key] = float(bins.get(key, 0.0)) + float(ww)
            max_bin = max(bins.values()) if bins else 1.0
            max_bin = max(1e-9, float(max_bin))
            for (iy, ix), vv in bins.items():
                la = iy * cell
                lo = ix * cell
                t = max(0.0, min(1.0, float(vv) / max_bin))
                color = "#4ade80" if t < 0.34 else ("#fbbf24" if t < 0.67 else "#f87171")
                folium.RegularPolygonMarker(
                    location=[la, lo],
                    number_of_sides=6,
                    radius=8,
                    color=color,
                    fill=True,
                    fill_color=color,
                    fill_opacity=max(0.15, min(1.0, w._heatmap_opacity)),
                    weight=1,
                ).add_to(feature_group)
        except Exception:
            return

    def add_gradient_vectors(self, feature_group, gradient_data, col_mapping, transformer):
        """Add gradient vectors as arrows with normalized, readable lengths."""
        w = self._widget
        import folium
        if gradient_data is None or gradient_data.empty:
            return
        if not {'centroid_x', 'centroid_y', 'angle', 'gradient'}.issubset(set(gradient_data.columns)):
            return

        max_vectors = 800
        sample = gradient_data.head(max_vectors) if len(gradient_data) > max_vectors else gradient_data

        grad_vals = sample['gradient'].apply(
            lambda g: float(g[0]) if isinstance(g, (list, tuple, np.ndarray)) and len(g) else float(g)
        ).replace([np.inf, -np.inf], np.nan).to_numpy(dtype=float)
        ang_vals = sample['angle'].apply(
            lambda a: float(a[0]) if isinstance(a, (list, tuple, np.ndarray)) and len(a) else float(a)
        ).replace([np.inf, -np.inf], np.nan).to_numpy(dtype=float)
        cx_vals = sample['centroid_x'].astype(float).to_numpy()
        cy_vals = sample['centroid_y'].astype(float).to_numpy()

        finite = np.isfinite(grad_vals) & np.isfinite(ang_vals) & np.isfinite(cx_vals) & np.isfinite(cy_vals)
        if not np.any(finite):
            return
        grad_vals = grad_vals[finite]
        ang_vals = ang_vals[finite]
        cx_vals = cx_vals[finite]
        cy_vals = cy_vals[finite]

        g_ref = float(np.nanpercentile(grad_vals, 95))
        if not np.isfinite(g_ref) or g_ref <= 0:
            g_ref = float(np.nanmax(grad_vals))
        if not np.isfinite(g_ref) or g_ref <= 0:
            return

        span = max(float(np.nanmax(cx_vals) - np.nanmin(cx_vals)), float(np.nanmax(cy_vals) - np.nanmin(cy_vals)))
        if not np.isfinite(span) or span <= 0:
            span = 1000.0
        min_len = 0.018 * span
        max_len = 0.065 * span

        try:
            import matplotlib
            cmap = matplotlib.cm.get_cmap(getattr(w.main_window, "colormap_vectors", "viridis"))
            norm = matplotlib.colors.Normalize(vmin=float(np.nanmin(grad_vals)), vmax=float(np.nanmax(grad_vals)))
        except Exception:
            cmap = None
            norm = None

        order = np.argsort(grad_vals, kind="mergesort")
        cx_vals = cx_vals[order]
        cy_vals = cy_vals[order]
        ang_vals = ang_vals[order]
        grad_vals = grad_vals[order]

        for cx, cy, direction, magnitude in zip(cx_vals, cy_vals, ang_vals, grad_vals):
            try:
                t = float(np.clip(magnitude / g_ref, 0.0, 1.0))
                length_m = float(min_len + (max_len - min_len) * t)
                ang = np.radians(direction)
                dx = np.cos(ang) * length_m
                dy = np.sin(ang) * length_m

                start_projected = w._project_xy_to_wgs84_strict(cx, cy, transformer=transformer)
                end_projected = w._project_xy_to_wgs84_strict(cx + dx, cy + dy, transformer=transformer)
                if start_projected is None or end_projected is None:
                    continue
                lon, lat = start_projected
                end_lon, end_lat = end_projected
                color = w.COLORS['vectors']
                if cmap is not None and norm is not None:
                    try:
                        color = matplotlib.colors.to_hex(cmap(norm(float(magnitude))), keep_alpha=False)
                    except Exception:
                        color = w.COLORS['vectors']
                weight = 2.0 + 1.2 * t

                folium.PolyLine(
                    locations=[[lat, lon], [end_lat, end_lon]],
                    color=color,
                    weight=weight,
                    opacity=0.85,
                    class_name='overlay-vectors'
                ).add_to(feature_group)

                head_len = 0.26 * length_m
                wing_ang = np.deg2rad(26.0)
                bx1 = (cx + dx) - head_len * np.cos(ang - wing_ang)
                by1 = (cy + dy) - head_len * np.sin(ang - wing_ang)
                bx2 = (cx + dx) - head_len * np.cos(ang + wing_ang)
                by2 = (cy + dy) - head_len * np.sin(ang + wing_ang)
                b1_projected = w._project_xy_to_wgs84_strict(bx1, by1, transformer=transformer)
                b2_projected = w._project_xy_to_wgs84_strict(bx2, by2, transformer=transformer)
                if b1_projected is None or b2_projected is None:
                    continue
                b1_lon, b1_lat = b1_projected
                b2_lon, b2_lat = b2_projected

                folium.PolyLine(
                    locations=[[end_lat, end_lon], [b1_lat, b1_lon]],
                    color=color,
                    weight=weight,
                    opacity=0.85,
                    class_name='overlay-vectors'
                ).add_to(feature_group)
                folium.PolyLine(
                    locations=[[end_lat, end_lon], [b2_lat, b2_lon]],
                    color=color,
                    weight=weight,
                    opacity=0.85,
                    class_name='overlay-vectors'
                ).add_to(feature_group)
            except Exception:
                continue

    def add_main_direction_arrow(self, feature_group, gradient_data, col_mapping, transformer):
        """Render a single mean-direction arrow matching 2D plot semantics."""
        w = self._widget
        import folium
        if gradient_data is None or gradient_data.empty:
            return
        if not {'centroid_x', 'centroid_y', 'angle', 'gradient'}.issubset(set(gradient_data.columns)):
            return
        try:
            grad = gradient_data['gradient'].apply(
                lambda g: float(g[0]) if isinstance(g, (list, tuple, np.ndarray)) and len(g) else float(g)
            ).replace([np.inf, -np.inf], np.nan).to_numpy(dtype=float)
            ang_deg = gradient_data['angle'].apply(
                lambda a: float(a[0]) if isinstance(a, (list, tuple, np.ndarray)) and len(a) else float(a)
            ).replace([np.inf, -np.inf], np.nan).to_numpy(dtype=float)
            cx_vals = gradient_data['centroid_x'].astype(float).to_numpy()
            cy_vals = gradient_data['centroid_y'].astype(float).to_numpy()
            finite = np.isfinite(grad) & np.isfinite(ang_deg) & np.isfinite(cx_vals) & np.isfinite(cy_vals)
            if not np.any(finite):
                return
            grad = grad[finite]
            ang_deg = ang_deg[finite]
            cx_vals = cx_vals[finite]
            cy_vals = cy_vals[finite]

            ang = np.deg2rad(ang_deg)
            mean_ang = float(np.arctan2(np.nanmean(np.sin(ang)), np.nanmean(np.cos(ang))))
            if not np.isfinite(mean_ang):
                return

            cx = float(np.nanmedian(cx_vals))
            cy = float(np.nanmedian(cy_vals))
            span = max(float(np.nanmax(cx_vals) - np.nanmin(cx_vals)), float(np.nanmax(cy_vals) - np.nanmin(cy_vals)))
            if not np.isfinite(span) or span <= 0:
                span = 1000.0

            g_ref = float(np.nanpercentile(grad, 95))
            if not np.isfinite(g_ref) or g_ref <= 0:
                g_ref = float(np.nanmean(grad)) if np.isfinite(np.nanmean(grad)) else 1.0
            mag_t = float(np.clip(float(np.nanmean(grad)) / max(g_ref, 1e-9), 0.0, 1.0))

            length_m = float((0.07 + 0.08 * mag_t) * span)
            dx = np.cos(mean_ang) * length_m
            dy = np.sin(mean_ang) * length_m
            start_projected = w._project_xy_to_wgs84_strict(cx, cy, transformer=transformer)
            end_projected = w._project_xy_to_wgs84_strict(cx + dx, cy + dy, transformer=transformer)
            if start_projected is None or end_projected is None:
                return
            lon, lat = start_projected
            end_lon, end_lat = end_projected
            color = w.COLORS['selected']
            weight = 4.0

            folium.PolyLine(
                locations=[[lat, lon], [end_lat, end_lon]],
                color=color,
                weight=weight,
                opacity=0.95,
                class_name='overlay-main-arrow'
            ).add_to(feature_group)

            head_len = 0.30 * length_m
            wing_ang = np.deg2rad(28.0)
            bx1 = (cx + dx) - head_len * np.cos(mean_ang - wing_ang)
            by1 = (cy + dy) - head_len * np.sin(mean_ang - wing_ang)
            bx2 = (cx + dx) - head_len * np.cos(mean_ang + wing_ang)
            by2 = (cy + dy) - head_len * np.sin(mean_ang + wing_ang)
            b1_projected = w._project_xy_to_wgs84_strict(bx1, by1, transformer=transformer)
            b2_projected = w._project_xy_to_wgs84_strict(bx2, by2, transformer=transformer)
            if b1_projected is None or b2_projected is None:
                return
            b1_lon, b1_lat = b1_projected
            b2_lon, b2_lat = b2_projected
            folium.PolyLine(
                locations=[[end_lat, end_lon], [b1_lat, b1_lon]],
                color=color,
                weight=weight,
                opacity=0.95,
                class_name='overlay-main-arrow'
            ).add_to(feature_group)
            folium.PolyLine(
                locations=[[end_lat, end_lon], [b2_lat, b2_lon]],
                color=color,
                weight=weight,
                opacity=0.95,
                class_name='overlay-main-arrow'
            ).add_to(feature_group)
        except Exception:
            return

    def add_coverage_overlay(self, feature_group, data, col_mapping, triangle_data, transformer):
        """Add a simple coverage-quality layer based on triangle support per point."""
        w = self._widget
        import folium
        try:
            id_col = col_mapping.get('ID')
            x_col = col_mapping.get('x')
            y_col = col_mapping.get('y')
            if not id_col or not x_col or not y_col:
                return
            if id_col not in data.columns or x_col not in data.columns or y_col not in data.columns:
                return
            if 'point_ids' not in triangle_data.columns:
                return

            counts = {}
            for ids in triangle_data['point_ids']:
                vals = ids if isinstance(ids, (list, tuple, np.ndarray)) else [ids]
                for v in vals:
                    k = str(v)
                    counts[k] = int(counts.get(k, 0)) + 1
            if not counts:
                return

            max_count = max(counts.values()) if counts else 1
            max_count = max(1, int(max_count))
            for _, row in data.iterrows():
                pid = str(row[id_col])
                c = int(counts.get(pid, 0))
                if c <= 0:
                    continue
                projected = w._project_xy_to_wgs84_strict(float(row[x_col]), float(row[y_col]), transformer=transformer)
                if projected is None:
                    continue
                lon, lat = projected
                t = c / float(max_count)
                color = "#4ade80" if t >= 0.66 else ("#fbbf24" if t >= 0.33 else "#f87171")
                folium.CircleMarker(
                    location=[lat, lon],
                    radius=4 + int(4 * t),
                    color=color,
                    fill=True,
                    fill_color=color,
                    fill_opacity=0.35,
                    weight=1,
                    class_name='overlay-coverage',
                ).add_to(feature_group)
        except Exception:
            return

    def add_head_contours(self, feature_group, data, col_mapping, transformer):
        """Add interpolated head contours as polylines."""
        w = self._widget
        import folium  # noqa: F401
        w._contour_legend = {"enabled": False, "gradient": "", "min_label": "-", "max_label": "-"}
        if not bool(w._show_contours):
            return
        try:
            import matplotlib.pyplot as plt  # noqa: F401
        except Exception:
            return

    def apply_dynamic_vectors_visual_only(self):
        """Replace vectors/main-arrow in-place without full map rebuild."""
        w = self._widget
        payload = w._build_vectors_payload()
        js = f"""
        (function(){{
            if(window.__replaceDynamicVectors){{
                window.__replaceDynamicVectors({json.dumps(payload)});
            }}
        }})();
        """
        w.web_view.page().runJavaScript(js)

    def apply_dynamic_coverage_visual_only(self):
        """Replace coverage overlay in-place without full map rebuild."""
        w = self._widget
        payload = w._build_coverage_payload()
        js = f"""
        (function(){{
            if(window.__replaceDynamicCoverage){{
                window.__replaceDynamicCoverage({json.dumps(payload)});
            }}
        }})();
        """
        w.web_view.page().runJavaScript(js)

    def apply_dynamic_contours_visual_only(self):
        """Recompute and replace contour layers via JS without full map rebuild."""
        w = self._widget
        payload = {"fills": [], "lines": [], "labels": []}
        if bool(w._show_contours):
            built = w._build_contour_payload()
            if isinstance(built, dict):
                payload = built
        js = f"""
        (function(){{
            if(window.__replaceDynamicContours){{
                window.__replaceDynamicContours({json.dumps(payload)});
            }}
        }})();
        """
        w.web_view.page().runJavaScript(js)

    def apply_triangle_selection_overlay(self, triangle_indices, combined_df=None):
        """Render multiselect triangle overlay on map."""
        w = self._widget
        payload = w._build_triangle_overlay_payload(triangle_indices, combined_df=combined_df)
        js = f"""
        (function(){{
            if(window.__replaceTriangleSelectionOverlay){{
                window.__replaceTriangleSelectionOverlay({json.dumps(payload)});
            }}
        }})();
        """
        w.web_view.page().runJavaScript(js)
