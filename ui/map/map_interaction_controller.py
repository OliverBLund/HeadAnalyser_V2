"""Interaction/selection helpers extracted from MapWidget."""

import json


class MapInteractionController:
    """Handle map interaction flows while reading/writing MapWidget state."""

    def __init__(self, widget):
        self._widget = widget

    def toggle_table_panel(self):
        """Public table toggle used by Ctrl+T from map page."""
        w = self._widget
        w._table_drawer.toggle_panel()

    def ensure_table_panel_visible(self):
        """Ensure map-side table drawer is open."""
        w = self._widget
        w._table_drawer.ensure_visible()

    def on_triangle_selection_changed_local(self, triangle_indices: list):
        """Route map-side triangle table selection through existing global pathway."""
        w = self._widget
        combined = w._table_drawer.current_triangle_combined_df()
        w.apply_triangle_selection_overlay(list(triangle_indices or []), combined_df=combined)
        if not bool(w._sync_selection):
            return
        try:
            w.main_window.set_triangle_selection(list(triangle_indices or []), meta={"source": "map_triangle_table"})
        except Exception:
            pass

    def on_table_rows_selected_local(self, point_ids):
        """Multi-row table selection: pick first for map selected-point panel."""
        w = self._widget
        if not bool(w._sync_selection):
            return
        try:
            ids = [str(v).strip() for v in (point_ids or []) if str(v).strip()]
        except Exception:
            ids = []
        if ids:
            self.on_table_row_selected_local(ids[0])

    def on_table_row_selected_local(self, point_id: str):
        """Single-row table selection -> map selection + shared target update."""
        w = self._widget
        if not bool(w._sync_selection):
            return
        pid = str(point_id).strip()
        if not pid:
            return
        self.set_selected_point(pid)
        try:
            w.main_window._on_plot_point_selected(pid)
        except Exception:
            pass

    def on_point_clicked(self, point_id):
        """Handle point click from map."""
        w = self._widget
        point_ref = str(point_id)
        point_id_for_emit = str(point_id)
        parsed_payload = None
        try:
            raw = str(point_id).strip()
            if raw.startswith("{"):
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    parsed_payload = parsed
                    parsed_idx = str(parsed.get("idx", "")).strip()
                    parsed_id = str(parsed.get("id", "")).strip()
                    if parsed_idx:
                        point_ref = parsed_idx
                    elif parsed_id:
                        point_ref = parsed_id
                    if parsed_id:
                        point_id_for_emit = parsed_id
        except Exception:
            pass

        w._selected_point_data = self.resolve_point_payload(point_ref)
        if isinstance(w._selected_point_data, dict) and isinstance(parsed_payload, dict):
            mk = str(parsed_payload.get("member_key", "")).strip()
            if mk:
                w._selected_point_data["member_key"] = mk
        if isinstance(w._selected_point_data, dict):
            w._selected_id = str(w._selected_point_data.get("id", point_id_for_emit))
            point_ref = str(w._selected_point_data.get("idx", point_ref))
            point_id_for_emit = w._selected_id
        if not w._sync_selection:
            self.apply_selection_visual_only(point_ref)
            try:
                w._table_drawer.switch_to_data_mode_if_open()
                w._table_drawer.highlight_rows_by_ids([str(point_id_for_emit)])
            except Exception:
                pass
            return

        w.pointSelected.emit(point_id_for_emit)
        self.apply_selection_visual_only(point_ref)
        try:
            w._table_drawer.switch_to_data_mode_if_open()
            w._table_drawer.highlight_rows_by_ids([str(point_id_for_emit)])
        except Exception:
            pass

    def resolve_point_payload(self, point_ref):
        """Resolve point payload by idx first, then by ID fallback."""
        w = self._widget
        key = str(point_ref).strip()
        if not key:
            return None
        by_idx = w._point_data_map.get(key)
        if isinstance(by_idx, dict):
            return by_idx
        by_id = w._point_data_by_id.get(key)
        if isinstance(by_id, list) and by_id:
            for item in by_id:
                if not bool(item.get("excluded")):
                    return item
            return by_id[0]
        return None

    def on_transect_drawn(self, coords):
        """Handle transect line drawn on map - creates new transect entry."""
        from ui.map.state import TRANSECT_NAMES, TRANSECT_COLORS
        import math

        w = self._widget
        # Backwards compat: keep _transect_coords for existing consumers
        w._transect_coords = coords

        # Calculate transect distance in km
        def calc_distance(coords_list):
            """Calculate total distance of a polyline in km (haversine)."""
            total = 0.0
            for i in range(len(coords_list) - 1):
                lat1, lon1 = coords_list[i]
                lat2, lon2 = coords_list[i + 1]
                # Haversine formula
                R = 6371  # Earth radius in km
                dlat = math.radians(lat2 - lat1)
                dlon = math.radians(lon2 - lon1)
                a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
                c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
                total += R * c
            return total

        distance_km = calc_distance(coords) if coords else 0
        desc = f"{distance_km:.1f} km" if distance_km >= 1 else f"{distance_km*1000:.0f} m"

        # Check if at max (10 transects)
        if len(w._transects) >= 10:
            # Replace the active transect instead of creating new
            if w._active_transect_id:
                for t in w._transects:
                    if t.get("id") == w._active_transect_id:
                        t["coords"] = coords
                        t["desc"] = desc
                        t["svg_data"] = None
                        t["legend_html"] = None
                        break
            w.transectCreated.emit(coords)
            w._update_transect_lines_panel()
            w._redraw_all_transect_lines()
            return

        # Create new transect entry with A-A', B-B' naming
        idx = len(w._transects)
        transect_id = f"T{w._next_transect_num}"
        transect_name = TRANSECT_NAMES[idx] if idx < len(TRANSECT_NAMES) else f"Line {idx+1}"
        transect_color = TRANSECT_COLORS[idx % len(TRANSECT_COLORS)]
        w._next_transect_num += 1

        new_transect = {
            "id": transect_id,
            "name": transect_name,
            "coords": coords,
            "color": transect_color,
            "desc": desc,
            "visible": True,
            "svg_data": None,
            "legend_html": None,
        }
        w._transects.append(new_transect)
        w._active_transect_id = transect_id

        w.transectCreated.emit(coords)
        w._update_transect_lines_panel()
        w._redraw_all_transect_lines()

    def on_map_clicked(self, lat, lon):
        """Handle background map click (target capture in WGS84 lat/lon)."""
        w = self._widget
        try:
            w.mapLocationClicked.emit(float(lat), float(lon))
        except Exception:
            return

    def set_selected_point(self, point_id):
        """Set the selected point."""
        w = self._widget
        selected = self.resolve_point_payload(point_id)
        if selected is None:
            w._selected_id = point_id
            w._selected_point_data = None
            self.apply_selection_visual_only(point_id)
            return
        w._selected_id = str(selected.get("id", point_id))
        w._selected_point_data = selected
        self.apply_selection_visual_only(str(selected.get("idx", point_id)))

    def clear_selected_point(self):
        """Clear selected map point without rebuilding the map."""
        w = self._widget
        if w._selected_id is None and w._selected_point_data is None:
            return
        w._selected_id = None
        w._selected_point_data = None

        default_color = w.COLORS["points"]
        js = f"""
        (function(){{
            window.__selectedPointIdx = null;
            var markers = document.querySelectorAll('.point-marker');
            markers.forEach(function(el){{
                try {{
                    var cls = '';
                    if (typeof el.className === 'string') cls = el.className;
                    else if (el.className && typeof el.className.baseVal === 'string') cls = el.className.baseVal;
                    else if (el.getAttribute) cls = el.getAttribute('class') || '';
                    var isExcluded = String(cls).indexOf('excluded') !== -1;
                    if (isExcluded) return;
                    var idxMatch = String(cls).match(/point-idx-([\\w-]+)/);
                    var idx = idxMatch ? idxMatch[1] : null;
                    var pdata = (window.__mapPointData && idx && window.__mapPointData[idx]) ? window.__mapPointData[idx] : null;
                    var baseColor = ({str(bool(w._color_points_by_head)).lower()} && pdata && pdata.point_color)
                        ? String(pdata.point_color)
                        : {json.dumps(default_color)};
                    el.style.fill = baseColor;
                    el.setAttribute('fill', baseColor);
                    el.style.stroke = 'white';
                    el.setAttribute('stroke', 'white');
                    el.style.strokeWidth = '2px';
                    el.style.opacity = '0.8';
                }} catch(err) {{}}
            }});
            if (window.__applyPointRadius) window.__applyPointRadius({int(w._point_size)});
            if (window.clearSelectionPanel) window.clearSelectionPanel();
        }})();
        """
        w.web_view.page().runJavaScript(js)
        try:
            w._table_drawer.clear_highlight()
        except Exception:
            pass
        w.pointDeselected.emit()

    def apply_selection_visual_only(self, point_id):
        """Update selected marker + selection card through JS without full map reload."""
        w = self._widget
        if w._current_data is None:
            return
        selected = self.resolve_point_payload(point_id)
        if not selected:
            w._rerender_map()
            return

        selected_idx = str(selected.get("idx", ""))
        selected_json = json.dumps({
            "idx": str(selected.get("idx", "")),
            "id": str(selected.get("id", "")),
            "status": "Excluded" if bool(selected.get("excluded")) else "Included",
            "head": float(selected.get("head", 0.0)),
            "x": float(selected.get("x", 0.0)),
            "y": float(selected.get("y", 0.0)),
            "member_key": str(selected.get("member_key", "")) if selected.get("member_key", None) is not None else "",
        })
        selected_color = w.COLORS["selected"]
        default_color = w.COLORS["points"]

        js = f"""
        (function() {{
            window.__selectedPointIdx = {json.dumps(selected_idx)};
            var markers = document.querySelectorAll('.point-marker');
            markers.forEach(function(el) {{
                try {{
                    var cls = '';
                    if (typeof el.className === 'string') cls = el.className;
                    else if (el.className && typeof el.className.baseVal === 'string') cls = el.className.baseVal;
                    else if (el.getAttribute) cls = el.getAttribute('class') || '';

                    var isExcluded = String(cls).indexOf('excluded') !== -1;
                    if (isExcluded) return;

                    var idxMatch = String(cls).match(/point-idx-([\\w-]+)/);
                    var idx = idxMatch ? idxMatch[1] : null;
                    var isSel = idx && idx === {json.dumps(selected_idx)};

                    var pdata = (window.__mapPointData && idx && window.__mapPointData[idx]) ? window.__mapPointData[idx] : null;
                    var baseColor = ({str(bool(w._color_points_by_head)).lower()} && pdata && pdata.point_color)
                        ? String(pdata.point_color)
                        : {json.dumps(default_color)};
                    var fill = isSel ? {json.dumps(selected_color)} : baseColor;
                    el.style.fill = fill;
                    el.setAttribute('fill', fill);
                    el.style.stroke = 'white';
                    el.setAttribute('stroke', 'white');
                    el.style.strokeWidth = isSel ? '3px' : '2px';
                    el.style.opacity = isSel ? '0.95' : '0.8';
                }} catch (err) {{}}
            }});
            if (window.__applyPointRadius) window.__applyPointRadius({int(w._point_size)});
            if (window.updateSelectionPanel) window.updateSelectionPanel({selected_json});
        }})();
        """
        w.web_view.page().runJavaScript(js)
