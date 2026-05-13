"""Payload builders extracted from MapWidget."""

import json

import numpy as np

from core.contour_engine import compute_contour_grid


class MapPayloadBuilder:
    """Build dynamic map payloads while reading state from a MapWidget instance."""

    def __init__(self, widget):
        self._widget = widget

    def prepare_heatmap_data(self, rejected_data, col_mapping, transformer):
        """Prepare heatmap data from rejected triangles."""
        w = self._widget
        heatmap_points = []
        if 'centroid_x' in rejected_data.columns and 'centroid_y' in rejected_data.columns:
            for _, row in rejected_data.iterrows():
                try:
                    projected = w._project_xy_to_wgs84_strict(row['centroid_x'], row['centroid_y'], transformer=transformer)
                    if projected is None:
                        continue
                    lon, lat = projected
                    heatmap_points.append([lat, lon, 1.0])
                except Exception:
                    continue
        elif 'point_ids' in rejected_data.columns and w._current_data is not None:
            try:
                data = w._current_data
                id_col = col_mapping.get('ID')
                x_col = col_mapping.get('x')
                y_col = col_mapping.get('y')
                if id_col and x_col and y_col and all(c in data.columns for c in (id_col, x_col, y_col)):
                    rej_counts = {}
                    for ids in rejected_data['point_ids']:
                        vals = ids if isinstance(ids, (list, tuple, np.ndarray)) else [ids]
                        for v in vals:
                            k = str(v)
                            rej_counts[k] = int(rej_counts.get(k, 0)) + 1
                    if rej_counts:
                        max_count = max(rej_counts.values())
                        max_count = max(1, int(max_count))
                        for _, row in data.iterrows():
                            pid = str(row[id_col])
                            c = int(rej_counts.get(pid, 0))
                            if c <= 0:
                                continue
                            projected = w._project_xy_to_wgs84_strict(float(row[x_col]), float(row[y_col]), transformer=transformer)
                            if projected is None:
                                continue
                            lon, lat = projected
                            weight = float(c) / float(max_count)
                            heatmap_points.append([lat, lon, weight])
            except Exception:
                pass
        return heatmap_points

    def build_heatmap_payload(self):
        """Build lightweight dynamic heatmap payload for in-place updates."""
        w = self._widget
        try:
            if w._current_rejected_data is None or getattr(w._current_rejected_data, "empty", True):
                return {"points": []}
            if w._current_col_mapping is None:
                return {"points": []}
            transformer = w._get_transformer()
            pts = self.prepare_heatmap_data(w._current_rejected_data, w._current_col_mapping, transformer)
            payload = {"points": []}
            for item in pts or []:
                try:
                    if len(item) < 3:
                        continue
                    payload["points"].append({
                        "lat": float(item[0]),
                        "lon": float(item[1]),
                        "w": float(item[2]),
                        "opacity": float(w._heatmap_opacity),
                    })
                except Exception:
                    continue
            return payload
        except Exception:
            return {"points": []}

    def build_vectors_payload(self):
        """Build vector + main-arrow payload for in-place JS replacement."""
        w = self._widget
        payload = {"vectors": [], "main_arrow": []}
        gradient_data = w._current_gradient_data
        if gradient_data is None or getattr(gradient_data, "empty", True):
            return payload
        if not {'centroid_x', 'centroid_y', 'angle', 'gradient'}.issubset(set(gradient_data.columns)):
            return payload
        transformer = w._get_transformer()
        try:
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
                return payload
            grad_vals = grad_vals[finite]
            ang_vals = ang_vals[finite]
            cx_vals = cx_vals[finite]
            cy_vals = cy_vals[finite]
            g_ref = float(np.nanpercentile(grad_vals, 95))
            if not np.isfinite(g_ref) or g_ref <= 0:
                g_ref = float(np.nanmax(grad_vals))
            if not np.isfinite(g_ref) or g_ref <= 0:
                return payload
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
                        import matplotlib
                        color = matplotlib.colors.to_hex(cmap(norm(float(magnitude))), keep_alpha=False)
                    except Exception:
                        color = w.COLORS['vectors']
                weight = 2.0 + 1.2 * t
                payload["vectors"].append({
                    "latlngs": [[float(lat), float(lon)], [float(end_lat), float(end_lon)]],
                    "color": color,
                    "weight": float(weight),
                    "opacity": 0.85,
                })
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
                payload["vectors"].append({
                    "latlngs": [[float(end_lat), float(end_lon)], [float(b1_lat), float(b1_lon)]],
                    "color": color,
                    "weight": float(weight),
                    "opacity": 0.85,
                })
                payload["vectors"].append({
                    "latlngs": [[float(end_lat), float(end_lon)], [float(b2_lat), float(b2_lon)]],
                    "color": color,
                    "weight": float(weight),
                    "opacity": 0.85,
                })

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
                return payload
            grad = grad[finite]
            ang_deg = ang_deg[finite]
            cx_vals = cx_vals[finite]
            cy_vals = cy_vals[finite]
            ang = np.deg2rad(ang_deg)
            mean_ang = float(np.arctan2(np.nanmean(np.sin(ang)), np.nanmean(np.cos(ang))))
            if not np.isfinite(mean_ang):
                return payload
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
                return payload
            lon, lat = start_projected
            end_lon, end_lat = end_projected
            color = w.COLORS['selected']
            weight = 4.0
            payload["main_arrow"].append({
                "latlngs": [[float(lat), float(lon)], [float(end_lat), float(end_lon)]],
                "color": color,
                "weight": float(weight),
                "opacity": 0.95,
            })
            head_len = 0.30 * length_m
            wing_ang = np.deg2rad(28.0)
            bx1 = (cx + dx) - head_len * np.cos(mean_ang - wing_ang)
            by1 = (cy + dy) - head_len * np.sin(mean_ang - wing_ang)
            bx2 = (cx + dx) - head_len * np.cos(mean_ang + wing_ang)
            by2 = (cy + dy) - head_len * np.sin(mean_ang + wing_ang)
            b1_projected = w._project_xy_to_wgs84_strict(bx1, by1, transformer=transformer)
            b2_projected = w._project_xy_to_wgs84_strict(bx2, by2, transformer=transformer)
            if b1_projected is None or b2_projected is None:
                return payload
            b1_lon, b1_lat = b1_projected
            b2_lon, b2_lat = b2_projected
            payload["main_arrow"].append({
                "latlngs": [[float(end_lat), float(end_lon)], [float(b1_lat), float(b1_lon)]],
                "color": color,
                "weight": float(weight),
                "opacity": 0.95,
            })
            payload["main_arrow"].append({
                "latlngs": [[float(end_lat), float(end_lon)], [float(b2_lat), float(b2_lon)]],
                "color": color,
                "weight": float(weight),
                "opacity": 0.95,
            })
        except Exception:
            return {"vectors": [], "main_arrow": []}
        return payload

    def build_coverage_payload(self):
        """Build coverage payload for in-place JS replacement."""
        w = self._widget
        payload = {"points": []}
        try:
            data = w._current_data
            col_mapping = w._current_col_mapping
            triangle_data = w._current_triangle_data
            if data is None or col_mapping is None or triangle_data is None or getattr(triangle_data, "empty", True):
                return payload
            id_col = col_mapping.get('ID')
            x_col = col_mapping.get('x')
            y_col = col_mapping.get('y')
            if not id_col or not x_col or not y_col:
                return payload
            if id_col not in data.columns or x_col not in data.columns or y_col not in data.columns:
                return payload
            if 'point_ids' not in triangle_data.columns:
                return payload
            counts = {}
            for ids in triangle_data['point_ids']:
                vals = ids if isinstance(ids, (list, tuple, np.ndarray)) else [ids]
                for v in vals:
                    k = str(v)
                    counts[k] = int(counts.get(k, 0)) + 1
            if not counts:
                return payload
            max_count = max(1, int(max(counts.values())))
            transformer = w._get_transformer()
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
                payload["points"].append({
                    "lat": float(lat),
                    "lon": float(lon),
                    "radius": float(4 + int(4 * t)),
                    "color": color,
                    "fill_opacity": 0.35,
                    "weight": 1.0,
                })
        except Exception:
            return {"points": []}
        return payload

    def build_triangle_overlay_payload(self, triangle_indices, combined_df=None):
        """Build selected-triangle overlay payload for map rendering."""
        w = self._widget
        payload = {"triangles": []}
        if w._current_data is None or w._current_col_mapping is None:
            return payload
        try:
            ids = [int(v) for v in (triangle_indices or [])]
        except Exception:
            ids = []
        if not ids:
            return payload

        if combined_df is None:
            try:
                from ..triangle_widgets.triangle_data_helper import TriangleDataHelper
                combined_df = TriangleDataHelper.build_combined_triangle_df(w._current_triangle_data, w._current_rejected_data)
            except Exception:
                combined_df = None
        if combined_df is None or getattr(combined_df, "empty", True):
            return payload

        col_mapping = w._current_col_mapping
        id_col = col_mapping.get("ID")
        x_col = col_mapping.get("x")
        y_col = col_mapping.get("y")
        data = w._current_data
        if not id_col or not x_col or not y_col:
            return payload
        if id_col not in data.columns or x_col not in data.columns or y_col not in data.columns:
            return payload

        transformer = w._get_transformer()
        coord_map = {}
        try:
            for _, row in data.iterrows():
                pid = str(row[id_col])
                if pid in coord_map:
                    continue
                wgs = w._read_wgs84_from_row(row)
                if wgs is not None:
                    lon, lat = wgs
                else:
                    projected = w._project_xy_to_wgs84_strict(float(row[x_col]), float(row[y_col]), transformer=transformer)
                    if projected is None:
                        continue
                    lon, lat = projected
                coord_map[pid] = [float(lat), float(lon)]
        except Exception:
            return payload

        for idx in ids:
            try:
                if idx < 0 or idx >= len(combined_df):
                    continue
                tri = combined_df.iloc[idx]
                point_ids = tri.get("point_ids", None)
                if point_ids is None:
                    continue
                if isinstance(point_ids, np.ndarray):
                    point_ids = point_ids.tolist()
                if not isinstance(point_ids, (list, tuple)):
                    continue
                latlngs = []
                for pid in point_ids:
                    ll = coord_map.get(str(pid))
                    if ll is not None:
                        latlngs.append(ll)
                if len(latlngs) != 3:
                    continue
                payload["triangles"].append({
                    "latlngs": latlngs,
                    "status": str(tri.get("status", "kept")).lower(),
                })
            except Exception:
                continue
        return payload

    def build_colormap_gradient(self, cmap):
        """Create CSS gradient string from a Matplotlib colormap."""
        try:
            import matplotlib
            stops = []
            for t in (0.0, 0.25, 0.5, 0.75, 1.0):
                color_hex = matplotlib.colors.to_hex(cmap(float(t)), keep_alpha=False)
                stops.append(f"{color_hex} {int(t * 100)}%")
            return f"linear-gradient(90deg, {', '.join(stops)})"
        except Exception:
            return "linear-gradient(90deg, #3b82f6 0%, #10b981 100%)"

    def build_contour_payload(self):
        """Build contour overlay payload for in-place JS replacement."""
        w = self._widget
        data = w._current_data
        col_mapping = w._current_col_mapping or {}
        if data is None or data.empty:
            return None
        try:
            x_col = col_mapping.get('x')
            y_col = col_mapping.get('y')
            h_col = col_mapping.get('hydraulic head')
            if not x_col or not y_col or not h_col:
                return None
            if x_col not in data.columns or y_col not in data.columns or h_col not in data.columns:
                return None

            contour_data = data
            id_col = col_mapping.get('ID')
            if id_col and id_col in data.columns and w._excluded_ids:
                try:
                    id_vals = data[id_col].astype(str)
                    contour_data = data[~id_vals.isin(set(w._excluded_ids))]
                except Exception:
                    contour_data = data
            if contour_data is None or contour_data.empty or len(contour_data) < 4:
                return {"fills": [], "lines": [], "labels": []}

            x = contour_data[x_col].astype(float).to_numpy()
            y = contour_data[y_col].astype(float).to_numpy()
            h = contour_data[h_col].astype(float).to_numpy()
            if not np.isfinite(x).all() or not np.isfinite(y).all() or not np.isfinite(h).all():
                mask = np.isfinite(x) & np.isfinite(y) & np.isfinite(h)
                x, y, h = x[mask], y[mask], h[mask]
            if len(x) < 4:
                return {"fills": [], "lines": [], "labels": []}

            grid = compute_contour_grid(
                x=x,
                y=y,
                h=h,
                interpolation_method=getattr(w.main_window, "interpolation_method", "cubic"),
                contour_extent_pct=getattr(w.main_window, "contour_extent_pct", 0),
                contour_extrapolation=getattr(w.main_window, "contour_extrapolation", "none"),
                grid_resolution=100,
            )
            if grid is None:
                return {"fills": [], "lines": [], "labels": []}
            xi2, yi2, zi = grid

            num_levels = int(getattr(w.main_window, "contour_levels", 10) or 10)
            num_levels = max(2, min(num_levels, 50))
            levels = np.linspace(float(np.nanmin(h)), float(np.nanmax(h)), num_levels)
            levels = np.unique(levels.astype(float))
            if len(levels) < 2:
                return {"fills": [], "lines": [], "labels": []}

            transformer = w._get_transformer()
            payload = {"fills": [], "lines": [], "labels": []}

            import matplotlib
            import matplotlib.pyplot as plt
            fig = plt.figure(figsize=(1, 1))
            ax = fig.add_subplot(111)
            try:
                if bool(getattr(w.main_window, "fill_contours", False)):
                    cmap = matplotlib.cm.get_cmap(getattr(w.main_window, "colormap_2d", "viridis"))
                    norm = matplotlib.colors.Normalize(vmin=float(levels[0]), vmax=float(levels[-1]))
                    cf = ax.contourf(xi2, yi2, zi, levels=levels, cmap=cmap)
                    for li, seg_group in enumerate(cf.allsegs):
                        if li >= len(levels) - 1:
                            continue
                        lv0 = float(levels[li])
                        lv1 = float(levels[min(li + 1, len(levels) - 1)])
                        mid_val = 0.5 * (lv0 + lv1)
                        rgba = cmap(norm(mid_val))
                        color_hex = matplotlib.colors.to_hex(rgba, keep_alpha=False)
                        for seg in seg_group:
                            v = np.asarray(seg, dtype=float)
                            if v is None or len(v) < 3:
                                continue
                            latlngs = []
                            for vx, vy in v:
                                projected = w._project_xy_to_wgs84_strict(float(vx), float(vy), transformer=transformer)
                                if projected is None:
                                    continue
                                lon, lat = projected
                                latlngs.append([float(lat), float(lon)])
                            if len(latlngs) >= 3:
                                payload["fills"].append({
                                    "latlngs": latlngs,
                                    "color": color_hex,
                                    "opacity": float(w._contour_fill_opacity),
                                })

                cs = ax.contour(xi2, yi2, zi, levels=levels)
                try:
                    base_lw = float(getattr(w.main_window, "contour_linewidth", 0.8))
                except Exception:
                    base_lw = 0.8
                base_lw = max(0.2, min(5.0, base_lw))
                major_every = max(1, int(w._contour_major_interval))
                for li, seg_group in enumerate(cs.allsegs):
                    level_value = float(cs.levels[li]) if li < len(cs.levels) else None
                    is_major = (li % major_every) == 0
                    line_weight = (base_lw * 1.8) if is_major else max(0.4, base_lw * 0.75)
                    line_opacity = 0.8 if is_major else 0.6
                    for seg in seg_group:
                        v = np.asarray(seg, dtype=float)
                        if v is None or len(v) < 2:
                            continue
                        latlngs = []
                        for vx, vy in v:
                            projected = w._project_xy_to_wgs84_strict(float(vx), float(vy), transformer=transformer)
                            if projected is None:
                                continue
                            lon, lat = projected
                            latlngs.append([float(lat), float(lon)])
                        if len(latlngs) >= 2:
                            payload["lines"].append({
                                "latlngs": latlngs,
                                "level_index": int(li),
                                "color": w.COLORS["contours"],
                                "weight": float(line_weight),
                                "opacity": float(line_opacity),
                            })
                            if is_major and level_value is not None and len(latlngs) >= 8:
                                mid = len(latlngs) // 2
                                a = max(1, mid - 1)
                                b = min(len(latlngs) - 1, mid + 1)
                                lat1, lon1 = latlngs[a][0], latlngs[a][1]
                                lat2, lon2 = latlngs[b][0], latlngs[b][1]
                                angle_deg = float(np.degrees(np.arctan2((lat2 - lat1), (lon2 - lon1))))
                                txt = f"{level_value:.{max(0, min(3, int(w._contour_label_precision)))}f}"
                                payload["labels"].append({
                                    "lat": float(latlngs[mid][0]),
                                    "lon": float(latlngs[mid][1]),
                                    "text": txt,
                                    "angle": float(angle_deg),
                                    "level_index": int(li),
                                    "level_value": f"{level_value:.12g}",
                                    "font_size": int(w._contour_label_font_size),
                                    "hidden": not bool(w._show_contour_labels),
                                })
            finally:
                plt.close(fig)
            return payload
        except Exception:
            return None

    def apply_point_colors(self, coords_data):
        """Assign display color for included points from the active 2D colormap."""
        w = self._widget
        default_color = w.COLORS["points"]
        w._point_legend = {"available": False, "gradient": "", "min_label": "-", "max_label": "-"}
        for p in coords_data:
            p["point_color"] = default_color
        included = [p for p in coords_data if not bool(p.get("excluded"))]
        if not included:
            return
        try:
            import matplotlib
            cmap = matplotlib.cm.get_cmap(getattr(w.main_window, "colormap_2d", "viridis"))
            heads = np.asarray([float(p.get("head", np.nan)) for p in included], dtype=float)
            finite = np.isfinite(heads)
            if not finite.any():
                return
            vmin = float(np.nanmin(heads[finite]))
            vmax = float(np.nanmax(heads[finite]))
            if not np.isfinite(vmin) or not np.isfinite(vmax):
                return
            w._point_legend = {
                "available": True,
                "gradient": self.build_colormap_gradient(cmap),
                "min_label": f"{vmin:.2f}",
                "max_label": f"{vmax:.2f}",
            }
            if abs(vmax - vmin) < 1e-12:
                flat_color = matplotlib.colors.to_hex(cmap(0.5), keep_alpha=False)
                for p in included:
                    p["point_color"] = flat_color
                return
            norm = matplotlib.colors.Normalize(vmin=vmin, vmax=vmax)
            for p in included:
                hv = float(p.get("head", np.nan))
                if not np.isfinite(hv):
                    p["point_color"] = default_color
                    continue
                p["point_color"] = matplotlib.colors.to_hex(cmap(norm(hv)), keep_alpha=False)
        except Exception:
            return

    def refresh_point_color_payload(self):
        """Recompute per-point colors from current payload and sync JS cache."""
        w = self._widget
        if not isinstance(w._point_data_map, dict) or not w._point_data_map:
            return
        points = [p for p in w._point_data_map.values() if isinstance(p, dict)]
        if not points:
            return
        self.apply_point_colors(points)
        w._point_data_map = {str(p.get("idx")): p for p in points}
        by_id = {}
        point_map = {}
        for p in points:
            try:
                pid = str(p.get("id", ""))
                by_id.setdefault(pid, []).append(p)
                point_map[str(p.get("idx"))] = {
                    "idx": str(p.get("idx", "")),
                    "id": pid,
                    "member_key": str(p.get("member_key", "")) if p.get("member_key", None) is not None else "",
                    "status": "Excluded" if bool(p.get("excluded")) else "Included",
                    "head": float(p.get("head", 0.0)),
                    "x": float(p.get("x", 0.0)),
                    "y": float(p.get("y", 0.0)),
                    "point_color": str(p.get("point_color") or w.COLORS["points"]),
                }
            except Exception:
                continue
        w._point_data_by_id = by_id
        js = f"""
        (function(){{
            window.__mapPointData = {json.dumps(point_map)};
            window.__mapPointLegend = {json.dumps(w._point_legend)};
        }})();
        """
        w.web_view.page().runJavaScript(js)

    def refresh_point_color_payload_for_data(self, data, col_mapping):
        """Recompute point colors for a specific filtered data snapshot."""
        w = self._widget
        if data is None or col_mapping is None:
            return
        if not isinstance(w._point_data_map, dict) or not w._point_data_map:
            return
        id_col = col_mapping.get("ID")
        h_col = col_mapping.get("hydraulic head")
        if not id_col or not h_col or id_col not in data.columns or h_col not in data.columns:
            return
        points = []
        for idx, row in data.iterrows():
            key = str(idx)
            base = w._point_data_map.get(key)
            if not isinstance(base, dict):
                continue
            p = dict(base)
            try:
                p["id"] = str(row[id_col])
            except Exception:
                p["id"] = str(base.get("id", ""))
            p["excluded"] = str(p.get("id", "")) in w._excluded_ids
            try:
                p["head"] = float(row[h_col])
            except Exception:
                p["head"] = float(base.get("head", 0.0))
            points.append(p)
        if not points:
            return
        self.apply_point_colors(points)
        for p in points:
            w._point_data_map[str(p.get("idx"))] = p

        point_map = {}
        by_id = {}
        for p in w._point_data_map.values():
            if not isinstance(p, dict):
                continue
            try:
                pid = str(p.get("id", ""))
                by_id.setdefault(pid, []).append(p)
                point_map[str(p.get("idx"))] = {
                    "idx": str(p.get("idx", "")),
                    "id": pid,
                    "member_key": str(p.get("member_key", "")) if p.get("member_key", None) is not None else "",
                    "status": "Excluded" if bool(p.get("excluded")) else "Included",
                    "head": float(p.get("head", 0.0)),
                    "x": float(p.get("x", 0.0)),
                    "y": float(p.get("y", 0.0)),
                    "point_color": str(p.get("point_color") or w.COLORS["points"]),
                }
            except Exception:
                continue
        w._point_data_by_id = by_id
        js = f"""
        (function(){{
            window.__mapPointData = {json.dumps(point_map)};
            window.__mapPointLegend = {json.dumps(w._point_legend)};
            if (window.__applyPointColorMode) window.__applyPointColorMode({str(bool(w._color_points_by_head)).lower()});
            if (window.__setMapLayerState) window.__setMapLayerState(window.__mapLayerState || {{}});
        }})();
        """
        w.web_view.page().runJavaScript(js)
