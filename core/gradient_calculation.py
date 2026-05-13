"""
HeadAnalyser V2 - Gradient Calculation
Core gradient calculation logic - preserved from original.
"""

import numpy as np
import pandas as pd
import os
import time
import hashlib
from collections import OrderedDict
from itertools import combinations, islice


class GradientCalculation:
    """
    Gradient calculation engine.
    This class contains the core mathematical logic and is largely unchanged from the original.
    """
    
    def __init__(self, app_ref):
        self.app_ref = app_ref
        self.triangle_gradients = []
        self.triangle_angles = []
        self.cache = OrderedDict()
        self._cache = self.cache  # Backward-compatible alias.
        self._cache_enabled = not self._env_flag("HEADANALYSER_DISABLE_GRADIENT_CACHE")
        try:
            self._cache_max_entries = max(0, int(os.getenv("HEADANALYSER_GRADIENT_CACHE_SIZE", "3")))
        except Exception:
            self._cache_max_entries = 3
        self._disable_progress = self._env_flag("HEADANALYSER_DISABLE_GRADIENT_PROGRESS")
        try:
            self._progress_update_min_interval_s = max(
                0.02, float(os.getenv("HEADANALYSER_GRADIENT_PROGRESS_MIN_INTERVAL_S", "0.08"))
            )
        except Exception:
            self._progress_update_min_interval_s = 0.08
        self.triu_indices = np.triu_indices(3, k=1)
        self.progress_window = None
        self.start_time = 0.0
        self._progress_max_value = 0
        self._progress_last_ui_t = 0.0
        self._perf_enabled = not self._env_flag("HEADANALYSER_DISABLE_PERF_LOGS")
        self._last_cache_hit = False
        self._last_elapsed_ms = 0.0
        self._last_cache_key = None

    @staticmethod
    def _env_flag(name: str) -> bool:
        return str(os.getenv(name, "")).strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def _coerce_float(value, fallback: float) -> float:
        try:
            return float(value)
        except Exception:
            return float(fallback)

    def _perf_log(self, message: str):
        if self._perf_enabled:
            print(message)

    def _constraints_signature(self):
        return (
            round(self._coerce_float(getattr(self.app_ref, "gradient_head_uncertainty", 0.01), 0.01), 12),
            round(self._coerce_float(getattr(self.app_ref, "gradient_confidence_level", 0.66), 0.66), 12),
            round(self._coerce_float(getattr(self.app_ref, "gradient_base_height_low", 0.2), 0.2), 12),
            round(self._coerce_float(getattr(self.app_ref, "gradient_base_height_high", 8.0), 8.0), 12),
            round(self._coerce_float(getattr(self.app_ref, "gradient_max_base_or_height", 1e9), 1e9), 12),
            round(self._coerce_float(getattr(self.app_ref, "gradient_stacked_epsilon", 1e-10), 1e-10), 15),
        )

    def _cache_get(self, key):
        if not self._cache_enabled or self._cache_max_entries <= 0:
            return None
        payload = self._cache.get(key)
        if payload is None:
            return None
        self._cache.move_to_end(key)
        return payload

    def _cache_put(self, key, payload):
        if not self._cache_enabled or self._cache_max_entries <= 0:
            return
        self._cache[key] = payload
        self._cache.move_to_end(key)
        while len(self._cache) > self._cache_max_entries:
            self._cache.popitem(last=False)

    def clear_cache(self):
        self._cache.clear()

    def initialize_progress_bar(self, max_value: int):
        self.close_progress_bar()
        if self._disable_progress:
            return
        if int(max_value) <= 0:
            return

        try:
            from PyQt5.QtCore import Qt
            from PyQt5.QtWidgets import QApplication, QProgressDialog, QWidget
        except Exception:
            return

        app = QApplication.instance()
        if app is None:
            return

        parent = getattr(self.app_ref, "progress_parent", None)
        if parent is None:
            parent = self.app_ref if isinstance(self.app_ref, QWidget) else None

        try:
            dlg = QProgressDialog("0% Complete\nTime remaining: calculating...", "", 0, 100, parent)
            dlg.setWindowTitle("Processing...")
            dlg.setWindowModality(Qt.WindowModal if parent is not None else Qt.NonModal)
            dlg.setMinimumDuration(250)
            dlg.setAutoClose(False)
            dlg.setAutoReset(False)
            dlg.setCancelButton(None)
            dlg.setValue(0)
            self.progress_window = dlg
            self.start_time = time.monotonic()
            self._progress_max_value = int(max_value)
            self._progress_last_ui_t = self.start_time
            app.processEvents()
        except Exception:
            self.progress_window = None

    def update_progress_bar(self, value: int, max_value: int = None):
        dlg = self.progress_window
        if dlg is None:
            return

        try:
            from PyQt5.QtWidgets import QApplication
        except Exception:
            return

        if max_value is None:
            max_value = self._progress_max_value

        try:
            max_value = max(1, int(max_value))
            value = max(0, min(int(value), max_value))
        except Exception:
            return

        now = time.monotonic()
        if value < max_value and (now - self._progress_last_ui_t) < self._progress_update_min_interval_s:
            return
        self._progress_last_ui_t = now

        pct = (float(value) / float(max_value)) * 100.0
        elapsed = max(0.0, now - self.start_time)
        est_total = (elapsed / float(value) * float(max_value)) if value > 0 else 0.0
        remaining = max(0.0, est_total - elapsed)
        rem_m = int(remaining // 60)
        rem_s = int(remaining % 60)

        try:
            dlg.setLabelText(f"{pct:.0f}% Complete\nTime remaining: {rem_m}m {rem_s}s")
            dlg.setValue(int(min(100, max(0, round(pct)))))
            app = QApplication.instance()
            if app is not None:
                app.processEvents()
        except Exception:
            pass

    def close_progress_bar(self):
        dlg = getattr(self, "progress_window", None)
        self.progress_window = None
        if dlg is None:
            return
        try:
            dlg.close()
            dlg.deleteLater()
        except Exception:
            pass
        finally:
            self._progress_max_value = 0
            self._progress_last_ui_t = 0.0

    def _build_cache_key(self, filtered_data, x_col, y_col, h_col, id_col):
        if not self._cache_enabled or self._cache_max_entries <= 0:
            return None
        try:
            subset = filtered_data[[x_col, y_col, h_col, id_col]]
            row_hash = pd.util.hash_pandas_object(subset, index=True).values
            digest = hashlib.blake2b(row_hash.tobytes(), digest_size=16).hexdigest()
            return (
                "gradient-v2",
                digest,
                int(len(filtered_data)),
                tuple(self._constraints_signature()),
            )
        except Exception:
            return None

    def _apply_result_to_app(
        self,
        triangle_df,
        rejected_df,
        total_triangles: int,
        rejected_due_to_uncertainty: int,
        rejected_due_to_triangle_quality: int,
        rejected_due_to_calculation_failed: int,
    ):
        self.app_ref.rejected_data = rejected_df
        self.app_ref.total_triangles = int(total_triangles)
        self.app_ref.rejected_due_to_uncertainty = int(rejected_due_to_uncertainty)
        self.app_ref.rejected_due_to_triangle_quality = int(rejected_due_to_triangle_quality)
        self.app_ref.rejected_due_to_calculation_failed = int(rejected_due_to_calculation_failed)
        self.app_ref.gradient_data = triangle_df

    @staticmethod
    def _triangle_index_chunks(n: int, chunk_size: int):
        idx_iter = combinations(range(int(n)), 3)
        size = max(1, int(chunk_size))
        while True:
            batch = list(islice(idx_iter, size))
            if not batch:
                break
            yield np.asarray(batch, dtype=np.int32)

    def _create_gradient_dataframe_scalar(self, data_array, id_array, row_label_array, total_triangles):
        n = int(data_array.shape[0])
        results = []
        rejected = []
        rejected_due_to_uncertainty = 0
        rejected_due_to_triangle_quality = 0
        rejected_due_to_calculation_failed = 0

        self.initialize_progress_bar(total_triangles)
        try:
            processed = 0
            step = max(1, total_triangles // 200)  # target ~200 UI updates max
            next_update = step

            for i0, i1, i2 in combinations(range(n), 3):
                pts = data_array[[i0, i1, i2]]
                ids = [id_array[i0], id_array[i1], id_array[i2]]
                row_labels = [row_label_array[i0], row_label_array[i1], row_label_array[i2]]

                # Check triangle quality
                is_valid, quality_reason, detailed_reason, reason_flags, quality_debug = self._check_triangle_quality(pts)

                if not is_valid:
                    gradient, angle = self._calculate_triangle_gradient(pts)
                    gradient_ok = bool(np.isfinite(gradient) and np.isfinite(angle))
                    checks = quality_debug.get("checks", {}) if quality_debug else {}
                    rejected.append({
                        'point_ids': ids,
                        'reason': quality_reason,
                        'detailed_reason': detailed_reason,
                        'reason_flags': reason_flags,
                        'quality_is_stacked_points': bool(checks.get("stacked_points", quality_reason == "stacked_points")),
                        'quality_is_thin_triangle': bool(checks.get("thin_triangle", quality_reason in ("thin_triangle", "mixed"))),
                        'quality_is_uncertainty': bool(checks.get("uncertainty", quality_reason in ("uncertainty", "mixed"))),
                        'quality_is_max_base_or_height': bool(checks.get("max_base_or_height", quality_reason == "max_base_or_height")),
                        'quality_is_calculation_failed': False,
                        'gradient_computed': gradient_ok,
                        'gradient': float(gradient) if gradient_ok else np.nan,
                        'angle': float(angle % 360.0) if gradient_ok else np.nan,
                        'quality_side_lengths': quality_debug.get("side_lengths") if quality_debug else None,
                        'quality_heights': quality_debug.get("heights") if quality_debug else None,
                        'quality_base_height_ratio': quality_debug.get("base_height_ratio") if quality_debug else None,
                        'quality_area': quality_debug.get("area") if quality_debug else None,
                        'quality_h_range': quality_debug.get("h_range") if quality_debug else None,
                        'quality_thresholds': quality_debug.get("thresholds") if quality_debug else None,
                    })
                    if quality_reason in ('uncertainty', 'mixed'):
                        rejected_due_to_uncertainty += 1
                    if quality_reason in ('stacked_points', 'thin_triangle', 'mixed'):
                        rejected_due_to_triangle_quality += 1
                else:
                    # Calculate gradient
                    gradient, angle = self._calculate_triangle_gradient(pts)

                    if np.isnan(gradient) or np.isnan(angle):
                        rejected.append({
                            'point_ids': ids,
                            'reason': 'calculation_failed',
                            'detailed_reason': 'Gradient calculation returned NaN (singular matrix or division by zero)',
                            'reason_flags': ['calculation_failed'],
                            'quality_is_stacked_points': False,
                            'quality_is_thin_triangle': False,
                            'quality_is_uncertainty': False,
                            'quality_is_max_base_or_height': False,
                            'quality_is_calculation_failed': True,
                            'gradient_computed': False,
                            'gradient': np.nan,
                            'angle': np.nan,
                            'quality_side_lengths': None,
                            'quality_heights': None,
                            'quality_base_height_ratio': None,
                            'quality_area': None,
                            'quality_h_range': None,
                            'quality_thresholds': None,
                        })
                        rejected_due_to_calculation_failed += 1
                    else:
                        # Calculate centroid
                        cx = np.mean(pts[:, 0])
                        cy = np.mean(pts[:, 1])

                        results.append({
                            'point_ids': ids,
                            'point_row_labels': row_labels,
                            'gradient': gradient,
                            'angle': angle,
                            'centroid_x': cx,
                            'centroid_y': cy
                        })

                processed += 1
                if processed >= next_update:
                    self.update_progress_bar(processed, total_triangles)
                    next_update += step

            self.update_progress_bar(total_triangles, total_triangles)
        finally:
            self.close_progress_bar()

        rejected_df = pd.DataFrame(rejected)
        df = pd.DataFrame(results) if results else pd.DataFrame()
        return (
            df,
            rejected_df,
            rejected_due_to_uncertainty,
            rejected_due_to_triangle_quality,
            rejected_due_to_calculation_failed,
        )

    def _create_gradient_dataframe_vectorized(self, data_array, id_array, row_label_array, total_triangles):
        n = int(data_array.shape[0])
        try:
            chunk_size = max(5000, int(os.getenv("HEADANALYSER_GRADIENT_CHUNK_SIZE", "25000")))
        except Exception:
            chunk_size = 25000
        try:
            debug_limit = max(0, int(os.getenv("HEADANALYSER_REJECTION_DEBUG_MAX_TRIANGLES", "50000")))
        except Exception:
            debug_limit = 50000
        include_debug = bool(total_triangles <= debug_limit)

        # Resolve constraints from app settings (Excel defaults).
        eps = float(getattr(self.app_ref, "gradient_stacked_epsilon", 1e-10))
        base_height_low = float(getattr(self.app_ref, "gradient_base_height_low", 0.2))
        base_height_high = float(getattr(self.app_ref, "gradient_base_height_high", 8.0))
        head_unc = float(getattr(self.app_ref, "gradient_head_uncertainty", 0.01))
        max_base_or_height = float(getattr(self.app_ref, "gradient_max_base_or_height", 1e9))
        uncertainty_threshold = float(np.sqrt(2 * head_unc**2))

        detail_map = {
            "stacked_points": "Triangles with stacked points were found.",
            "max_base_or_height": "Triangle base/height exceeded the configured maximum.",
            "uncertainty": "Uncertainty in hydraulic head measurements is too low.",
            "thin_triangle": "Base-to-height ratio outside configured thresholds.",
            "mixed": "Uncertainty too low and base-to-height ratio outside configured thresholds.",
            "calculation_failed": "Gradient calculation returned NaN (singular matrix or division by zero).",
        }
        flags_map = {
            "stacked_points": ["stacked_points"],
            "max_base_or_height": ["max_base_or_height"],
            "uncertainty": ["uncertainty"],
            "thin_triangle": ["thin_triangle"],
            "mixed": ["uncertainty", "thin_triangle"],
            "calculation_failed": ["calculation_failed"],
        }
        thresholds_payload = {
            "stacked_epsilon": eps,
            "base_height_low": base_height_low,
            "base_height_high": base_height_high,
            "head_uncertainty": head_unc,
            "max_base_or_height": max_base_or_height,
        }

        x = data_array[:, 0].astype(float, copy=False)
        y = data_array[:, 1].astype(float, copy=False)
        h = data_array[:, 2].astype(float, copy=False)
        id_values = id_array.tolist()
        row_values = row_label_array.tolist()

        result_point_ids = []
        result_row_labels = []
        result_gradient = []
        result_angle = []
        result_cx = []
        result_cy = []

        rejected_point_ids = []
        rejected_reason = []
        rejected_detailed = []
        rejected_flags = []
        rejected_quality_is_stacked_points = []
        rejected_quality_is_thin_triangle = []
        rejected_quality_is_uncertainty = []
        rejected_quality_is_max_base_or_height = []
        rejected_quality_is_calculation_failed = []
        rejected_gradient_computed = []
        rejected_gradient = []
        rejected_angle = []
        rejected_side_lengths = []
        rejected_heights = []
        rejected_ratios = []
        rejected_area = []
        rejected_h_range = []
        rejected_thresholds = []

        rejected_due_to_uncertainty = 0
        rejected_due_to_triangle_quality = 0
        rejected_due_to_calculation_failed = 0
        processed = 0

        self.initialize_progress_bar(total_triangles)
        try:
            for idx_chunk in self._triangle_index_chunks(n, chunk_size):
                i0 = idx_chunk[:, 0]
                i1 = idx_chunk[:, 1]
                i2 = idx_chunk[:, 2]

                x0 = x[i0]
                x1 = x[i1]
                x2 = x[i2]
                y0 = y[i0]
                y1 = y[i1]
                y2 = y[i2]
                h0 = h[i0]
                h1 = h[i1]
                h2 = h[i2]

                d01 = np.hypot(x1 - x0, y1 - y0)
                d02 = np.hypot(x2 - x0, y2 - y0)
                d12 = np.hypot(x2 - x1, y2 - y1)
                stacked = (d01 < eps) | (d02 < eps) | (d12 < eps)

                p = 0.5 * (d01 + d02 + d12)
                area_sq = np.maximum(p * (p - d01) * (p - d02) * (p - d12), 0.0)
                area = np.sqrt(area_sq)

                with np.errstate(divide='ignore', invalid='ignore'):
                    height0 = np.divide(2.0 * area, d01, out=np.full_like(area, np.inf), where=d01 != 0)
                    height1 = np.divide(2.0 * area, d02, out=np.full_like(area, np.inf), where=d02 != 0)
                    height2 = np.divide(2.0 * area, d12, out=np.full_like(area, np.inf), where=d12 != 0)

                if max_base_or_height > 0 and np.isfinite(max_base_or_height):
                    max_d = np.maximum(np.maximum(d01, d02), d12)
                    max_h = np.maximum(np.maximum(height0, height1), height2)
                    reject_max = (max_d > max_base_or_height) | (max_h > max_base_or_height)
                else:
                    reject_max = np.zeros_like(stacked)

                with np.errstate(divide='ignore', invalid='ignore'):
                    ratio0 = np.divide(d01, height0, out=np.zeros_like(d01), where=height0 != 0)
                    ratio1 = np.divide(d02, height1, out=np.zeros_like(d02), where=height1 != 0)
                    ratio2 = np.divide(d12, height2, out=np.zeros_like(d12), where=height2 != 0)

                reject_triangle = (
                    (ratio0 > base_height_high) | (ratio1 > base_height_high) | (ratio2 > base_height_high) |
                    (ratio0 < base_height_low) | (ratio1 < base_height_low) | (ratio2 < base_height_low)
                )
                h_range = np.maximum(np.maximum(h0, h1), h2) - np.minimum(np.minimum(h0, h1), h2)
                reject_uncertainty = h_range < uncertainty_threshold

                reason_codes = np.full(idx_chunk.shape[0], "", dtype=object)
                reason_codes[reject_uncertainty] = "uncertainty"
                reason_codes[reject_triangle] = "thin_triangle"
                reason_codes[reject_triangle & reject_uncertainty] = "mixed"
                reason_codes[reject_max] = "max_base_or_height"
                reason_codes[stacked] = "stacked_points"

                v1x = x1 - x0
                v1y = y1 - y0
                v1h = h1 - h0
                v2x = x2 - x0
                v2y = y2 - y0
                v2h = h2 - h0

                A0_all = v1y * v2h - v1h * v2y
                A1_all = v1h * v2x - v1x * v2h
                A2_all = v1x * v2y - v1y * v2x
                safe_all = np.isfinite(A2_all) & (np.abs(A2_all) >= 1e-30)
                with np.errstate(divide='ignore', invalid='ignore'):
                    gradient_all = np.sqrt((A0_all * A0_all + A1_all * A1_all) / (A2_all * A2_all))
                    angle_all = np.degrees(np.arctan(A1_all / A0_all))
                    angle_all = np.where(
                        (1 - 1e9 * A0_all / A2_all) > (1 + 1e9 * A0_all / A2_all),
                        angle_all + 180.0,
                        angle_all,
                    )
                angle_all = np.mod(angle_all, 360.0)
                calc_ok_all = safe_all & np.isfinite(gradient_all) & np.isfinite(angle_all)

                candidate_mask = reason_codes == ""
                calc_fail_idx = np.flatnonzero(candidate_mask & (~calc_ok_all))
                if calc_fail_idx.size > 0:
                    reason_codes[calc_fail_idx] = "calculation_failed"
                valid_idx = np.flatnonzero(candidate_mask & calc_ok_all)

                if valid_idx.size > 0:
                    valid_triples = idx_chunk[valid_idx]
                    result_point_ids.extend(
                        [[id_values[a], id_values[b], id_values[c]] for a, b, c in valid_triples]
                    )
                    result_row_labels.extend(
                        [[row_values[a], row_values[b], row_values[c]] for a, b, c in valid_triples]
                    )
                    result_gradient.extend(gradient_all[valid_idx].astype(float).tolist())
                    result_angle.extend(angle_all[valid_idx].astype(float).tolist())
                    result_cx.extend(((x0 + x1 + x2) / 3.0)[valid_idx].astype(float).tolist())
                    result_cy.extend(((y0 + y1 + y2) / 3.0)[valid_idx].astype(float).tolist())

                rejected_mask = reason_codes != ""
                rej_idx = np.flatnonzero(rejected_mask)
                if rej_idx.size > 0:
                    rej_triples = idx_chunk[rej_idx]
                    codes = reason_codes[rej_idx].tolist()
                    rejected_point_ids.extend(
                        [[id_values[a], id_values[b], id_values[c]] for a, b, c in rej_triples]
                    )
                    rejected_reason.extend(codes)
                    rejected_detailed.extend([detail_map.get(code, "") for code in codes])
                    rejected_flags.extend([list(flags_map.get(code, ())) for code in codes])
                    rejected_quality_is_stacked_points.extend(stacked[rej_idx].astype(bool).tolist())
                    rejected_quality_is_thin_triangle.extend(reject_triangle[rej_idx].astype(bool).tolist())
                    rejected_quality_is_uncertainty.extend(reject_uncertainty[rej_idx].astype(bool).tolist())
                    rejected_quality_is_max_base_or_height.extend(reject_max[rej_idx].astype(bool).tolist())
                    rejected_quality_is_calculation_failed.extend((reason_codes[rej_idx] == "calculation_failed").tolist())
                    rejected_gradient_computed.extend(calc_ok_all[rej_idx].astype(bool).tolist())
                    grad_vals = gradient_all[rej_idx]
                    ang_vals = angle_all[rej_idx]
                    grad_ok = calc_ok_all[rej_idx]
                    rejected_gradient.extend(np.where(grad_ok, grad_vals, np.nan).astype(float).tolist())
                    rejected_angle.extend(np.where(grad_ok, ang_vals, np.nan).astype(float).tolist())

                    if include_debug:
                        side_matrix = np.stack((d01, d02, d12), axis=1)
                        height_matrix = np.stack((height0, height1, height2), axis=1)
                        ratio_matrix = np.stack((ratio0, ratio1, ratio2), axis=1)
                        for idx_pos, code in zip(rej_idx, codes):
                            if code == "calculation_failed":
                                rejected_side_lengths.append(None)
                                rejected_heights.append(None)
                                rejected_ratios.append(None)
                                rejected_area.append(None)
                                rejected_h_range.append(None)
                                rejected_thresholds.append(None)
                            else:
                                rejected_side_lengths.append(np.round(side_matrix[idx_pos], 6).tolist())
                                rejected_heights.append(np.round(height_matrix[idx_pos], 6).tolist())
                                rejected_ratios.append(np.round(ratio_matrix[idx_pos], 6).tolist())
                                rejected_area.append(float(np.round(area[idx_pos], 6)))
                                rejected_h_range.append(float(h_range[idx_pos]))
                                rejected_thresholds.append(thresholds_payload)
                    else:
                        pad = rej_idx.size
                        rejected_side_lengths.extend([None] * pad)
                        rejected_heights.extend([None] * pad)
                        rejected_ratios.extend([None] * pad)
                        rejected_area.extend([None] * pad)
                        rejected_h_range.extend([None] * pad)
                        rejected_thresholds.extend([None] * pad)

                    code_arr = np.asarray(codes, dtype=object)
                    rejected_due_to_uncertainty += int(
                        np.count_nonzero((code_arr == "uncertainty") | (code_arr == "mixed"))
                    )
                    rejected_due_to_triangle_quality += int(
                        np.count_nonzero(
                            (code_arr == "stacked_points") | (code_arr == "thin_triangle") | (code_arr == "mixed")
                        )
                    )
                    rejected_due_to_calculation_failed += int(np.count_nonzero(code_arr == "calculation_failed"))

                processed += int(idx_chunk.shape[0])
                self.update_progress_bar(processed, total_triangles)

            self.update_progress_bar(total_triangles, total_triangles)
        finally:
            self.close_progress_bar()

        rejected_df = pd.DataFrame({
            "point_ids": rejected_point_ids,
            "reason": rejected_reason,
            "detailed_reason": rejected_detailed,
            "reason_flags": rejected_flags,
            "quality_is_stacked_points": rejected_quality_is_stacked_points,
            "quality_is_thin_triangle": rejected_quality_is_thin_triangle,
            "quality_is_uncertainty": rejected_quality_is_uncertainty,
            "quality_is_max_base_or_height": rejected_quality_is_max_base_or_height,
            "quality_is_calculation_failed": rejected_quality_is_calculation_failed,
            "gradient_computed": rejected_gradient_computed,
            "gradient": rejected_gradient,
            "angle": rejected_angle,
            "quality_side_lengths": rejected_side_lengths,
            "quality_heights": rejected_heights,
            "quality_base_height_ratio": rejected_ratios,
            "quality_area": rejected_area,
            "quality_h_range": rejected_h_range,
            "quality_thresholds": rejected_thresholds,
        })

        df = pd.DataFrame({
            "point_ids": result_point_ids,
            "point_row_labels": result_row_labels,
            "gradient": result_gradient,
            "angle": result_angle,
            "centroid_x": result_cx,
            "centroid_y": result_cy,
        })
        return (
            df,
            rejected_df,
            rejected_due_to_uncertainty,
            rejected_due_to_triangle_quality,
            rejected_due_to_calculation_failed,
        )

    def h_gradient(self, aggregated_data):
        """Calculate overall gradient from aggregated data."""
        x_col = self.app_ref.col_mapping['x']
        y_col = self.app_ref.col_mapping['y']
        h_col = self.app_ref.col_mapping['hydraulic head']
        
        data_np = aggregated_data[[x_col, y_col, h_col]].to_numpy()
        
        if data_np.shape[0] >= 3:
            D = np.ones((data_np.shape[0], 1))
            try:
                A = np.linalg.lstsq(data_np, D, rcond=None)[0].reshape(-1)
            except np.linalg.LinAlgError:
                return pd.DataFrame({
                    'gradient': [np.nan],
                    'angle': [np.nan],
                    'n_point': [len(aggregated_data)]
                })
                
            A0, A1, A2 = A[0], A[1], A[2]
            gradient = np.sqrt((A0**2 + A1**2) / A2**2)
            angle = np.arctan(A1 / A0) * 180 / np.pi
            if (1 - 1e9 * A0 / A2) > (1 + 1e9 * A0 / A2):
                angle += 180
            angle = float(angle % 360)
            gradient = float(gradient)
                
            return pd.DataFrame({
                'gradient': [gradient],
                'angle': [angle],
                'n_point': [data_np.shape[0]]
            })
        else:
            return pd.DataFrame({
                'gradient': [np.nan],
                'angle': [np.nan],
                'n_point': [len(aggregated_data)]
            })
            
    def create_gradient_dataframe(self, filtered_data):
        """Create dataframe with gradient data for all valid triangles."""
        t0_total = time.perf_counter()
        dataset_name = str(getattr(self.app_ref, "dataset_name", getattr(self.app_ref, "name", "active")))
        reason = str(getattr(self.app_ref, "_calc_reason", "") or "")

        if filtered_data is None or len(filtered_data) < 3:
            empty = pd.DataFrame()
            self._apply_result_to_app(
                triangle_df=empty,
                rejected_df=empty,
                total_triangles=0,
                rejected_due_to_uncertainty=0,
                rejected_due_to_triangle_quality=0,
                rejected_due_to_calculation_failed=0,
            )
            self._last_cache_hit = False
            self._last_cache_key = None
            self._last_elapsed_ms = (time.perf_counter() - t0_total) * 1000.0
            self._perf_log(
                f"[perf][gradient] dataset={dataset_name} reason={reason or 'n/a'} points=0 "
                f"cache=miss elapsed={self._last_elapsed_ms:.1f}ms valid=0 total=0"
            )
            return pd.DataFrame()

        x_col = self.app_ref.col_mapping['x']
        y_col = self.app_ref.col_mapping['y']
        h_col = self.app_ref.col_mapping['hydraulic head']
        id_col = self.app_ref.col_mapping['ID']
        
        # Validate that column mapping is complete
        if None in (x_col, y_col, h_col, id_col):
            print(f"Error: Column mapping is incomplete - x={x_col}, y={y_col}, h={h_col}, ID={id_col}")
            empty = pd.DataFrame()
            self._apply_result_to_app(
                triangle_df=empty,
                rejected_df=empty,
                total_triangles=0,
                rejected_due_to_uncertainty=0,
                rejected_due_to_triangle_quality=0,
                rejected_due_to_calculation_failed=0,
            )
            self._last_cache_hit = False
            self._last_cache_key = None
            self._last_elapsed_ms = (time.perf_counter() - t0_total) * 1000.0
            return pd.DataFrame()

        cache_key = self._build_cache_key(filtered_data, x_col, y_col, h_col, id_col)
        cached = self._cache_get(cache_key) if cache_key is not None else None
        if cached is not None:
            self._apply_result_to_app(
                triangle_df=cached["triangle_df"],
                rejected_df=cached["rejected_df"],
                total_triangles=cached["total_triangles"],
                rejected_due_to_uncertainty=cached["rejected_due_to_uncertainty"],
                rejected_due_to_triangle_quality=cached["rejected_due_to_triangle_quality"],
                rejected_due_to_calculation_failed=cached["rejected_due_to_calculation_failed"],
            )
            self._last_cache_hit = True
            self._last_cache_key = cache_key
            self._last_elapsed_ms = (time.perf_counter() - t0_total) * 1000.0
            self._perf_log(
                f"[perf][gradient] dataset={dataset_name} reason={reason or 'n/a'} points={len(filtered_data)} "
                f"cache=hit elapsed={self._last_elapsed_ms:.1f}ms "
                f"valid={len(cached['triangle_df']) if cached['triangle_df'] is not None else 0} "
                f"total={cached.get('total_triangles', 0)}"
            )
            return cached["triangle_df"]

        data_array = filtered_data[[x_col, y_col, h_col]].to_numpy()
        id_array = filtered_data[id_col].to_numpy()
        row_label_array = filtered_data.index.to_numpy()

        n = len(filtered_data)
        total_triangles = (n * (n - 1) * (n - 2)) // 6

        use_vectorized = not self._env_flag("HEADANALYSER_DISABLE_GRADIENT_VECTORIZE")
        if use_vectorized:
            try:
                (
                    df,
                    rejected_df,
                    rejected_due_to_uncertainty,
                    rejected_due_to_triangle_quality,
                    rejected_due_to_calculation_failed,
                ) = self._create_gradient_dataframe_vectorized(
                    data_array, id_array, row_label_array, total_triangles
                )
            except Exception as exc:
                self._perf_log(f"[perf][gradient] vectorized_failed={type(exc).__name__} fallback=scalar")
                (
                    df,
                    rejected_df,
                    rejected_due_to_uncertainty,
                    rejected_due_to_triangle_quality,
                    rejected_due_to_calculation_failed,
                ) = self._create_gradient_dataframe_scalar(
                    data_array, id_array, row_label_array, total_triangles
                )
        else:
            (
                df,
                rejected_df,
                rejected_due_to_uncertainty,
                rejected_due_to_triangle_quality,
                rejected_due_to_calculation_failed,
            ) = self._create_gradient_dataframe_scalar(
                data_array, id_array, row_label_array, total_triangles
            )

        self._apply_result_to_app(
            triangle_df=df,
            rejected_df=rejected_df,
            total_triangles=total_triangles,
            rejected_due_to_uncertainty=rejected_due_to_uncertainty,
            rejected_due_to_triangle_quality=rejected_due_to_triangle_quality,
            rejected_due_to_calculation_failed=rejected_due_to_calculation_failed,
        )

        if cache_key is not None:
            self._cache_put(
                cache_key,
                {
                    "triangle_df": df,
                    "rejected_df": rejected_df,
                    "total_triangles": total_triangles,
                    "rejected_due_to_uncertainty": rejected_due_to_uncertainty,
                    "rejected_due_to_triangle_quality": rejected_due_to_triangle_quality,
                    "rejected_due_to_calculation_failed": rejected_due_to_calculation_failed,
                },
            )

        self._last_cache_hit = False
        self._last_cache_key = cache_key
        self._last_elapsed_ms = (time.perf_counter() - t0_total) * 1000.0
        self._perf_log(
            f"[perf][gradient] dataset={dataset_name} reason={reason or 'n/a'} points={n} "
            f"cache=miss elapsed={self._last_elapsed_ms:.1f}ms valid={len(df)} total={total_triangles}"
        )

        return df
        
    def _check_triangle_quality(self, pts, epsilon=None):
        """
        Check if triangle meets quality criteria.
        Uses V1's original algorithm (gradient_estimator_numpy).
        
        Args:
            pts: Array of 3 points with x, y, h coordinates
            epsilon: Minimum distance threshold for stacked points
            
        Returns:
            (is_valid, reason, detailed_reason, reason_flags, debug_info) tuple
        """
        # Resolve constraints from app settings (Excel defaults).
        eps = float(getattr(self.app_ref, "gradient_stacked_epsilon", 1e-10)) if epsilon is None else float(epsilon)
        base_height_low = float(getattr(self.app_ref, "gradient_base_height_low", 0.2))
        base_height_high = float(getattr(self.app_ref, "gradient_base_height_high", 8.0))
        head_unc = float(getattr(self.app_ref, "gradient_head_uncertainty", 0.01))
        max_base_or_height = float(getattr(self.app_ref, "gradient_max_base_or_height", 1e9))

        # Distances for pairs (0,1), (0,2), (1,2) without scipy overhead.
        p0 = pts[0]
        p1 = pts[1]
        p2 = pts[2]
        d01 = float(np.hypot(float(p1[0] - p0[0]), float(p1[1] - p0[1])))
        d02 = float(np.hypot(float(p2[0] - p0[0]), float(p2[1] - p0[1])))
        d12 = float(np.hypot(float(p2[0] - p1[0]), float(p2[1] - p1[1])))
        d = np.array([d01, d02, d12], dtype=float)
        h0 = float(p0[2])
        h1 = float(p1[2])
        h2 = float(p2[2])
        h_range = float(max(h0, h1, h2) - min(h0, h1, h2))

        def _debug_base():
            return {
                "side_lengths": [float(v) for v in np.round(d, 6).tolist()],
                "h_range": h_range,
                "thresholds": {
                    "stacked_epsilon": eps,
                    "base_height_low": base_height_low,
                    "base_height_high": base_height_high,
                    "head_uncertainty": head_unc,
                    "max_base_or_height": max_base_or_height,
                },
            }

        # Check for stacked points
        if np.any(d < eps):
            dbg = _debug_base()
            dbg["checks"] = {
                "stacked_points": True,
                "thin_triangle": False,
                "uncertainty": False,
                "max_base_or_height": False,
            }
            return (
                False,
                'stacked_points',
                "Triangles with stacked points were found.",
                ["stacked_points"],
                dbg,
            )
        
        # Calculate triangle area using Heron's formula
        p = np.sum(d) / 2  # Semi-perimeter
        area_sq = np.maximum(p * (p - d[0]) * (p - d[1]) * (p - d[2]), 0)
        area = np.sqrt(area_sq)
        
        # Calculate heights for each side
        with np.errstate(divide='ignore', invalid='ignore'):
            height = np.divide(2 * area, d, out=np.full_like(d, np.inf), where=d != 0)
        debug_info = None
        d_h_ratio = np.divide(d, height, out=np.zeros_like(d), where=height != 0)
        reject_triangle = np.any((d_h_ratio > base_height_high) | (d_h_ratio < base_height_low))
        reject_uncertainty = h_range < np.sqrt(2 * head_unc**2)  # ~0.0141 for 0.01
        reject_max = False
        if max_base_or_height > 0 and np.isfinite(max_base_or_height):
            reject_max = bool(float(np.max(d)) > max_base_or_height or float(np.max(height)) > max_base_or_height)

        # Optional absolute constraint: reject if any base length or height exceeds a limit.
        if reject_max:
            debug_info = _debug_base()
            debug_info["area"] = float(np.round(area, 6))
            debug_info["heights"] = [float(v) for v in np.round(height, 6).tolist()]
            debug_info["base_height_ratio"] = [float(v) for v in np.round(d_h_ratio, 6).tolist()]
            debug_info["checks"] = {
                "stacked_points": False,
                "thin_triangle": bool(reject_triangle),
                "uncertainty": bool(reject_uncertainty),
                "max_base_or_height": True,
            }
            return (
                False,
                'max_base_or_height',
                "Triangle base/height exceeded the configured maximum.",
                ["max_base_or_height"],
                debug_info,
            )

        if reject_triangle or reject_uncertainty:
            reasons = []
            reason_code = 'mixed'
            reason_flags = []

            if reject_uncertainty:
                reasons.append("Uncertainty in hydraulic head measurements is too low.")
                reason_code = 'uncertainty'
                reason_flags.append("uncertainty")

            if reject_triangle:
                exceeding_ratios = d_h_ratio[d_h_ratio > base_height_high]
                below_ratios = d_h_ratio[d_h_ratio < base_height_low]
                if len(exceeding_ratios) > 0:
                    reasons.append(
                        f"Base-to-height ratios >{base_height_high:g}: {exceeding_ratios.round(2).tolist()}."
                    )
                if len(below_ratios) > 0:
                    reasons.append(
                        f"Base-to-height ratios <{base_height_low:g}: {below_ratios.round(2).tolist()}."
                    )
                if reason_code == 'mixed':
                    reason_code = 'thin_triangle'
                elif reason_code == 'uncertainty':
                    reason_code = 'mixed' # Both issues
                reason_flags.append("thin_triangle")

            debug_info = _debug_base()
            debug_info["area"] = float(np.round(area, 6))
            debug_info["heights"] = [float(v) for v in np.round(height, 6).tolist()]
            debug_info["base_height_ratio"] = [float(v) for v in np.round(d_h_ratio, 6).tolist()]
            debug_info["checks"] = {
                "stacked_points": False,
                "thin_triangle": bool(reject_triangle),
                "uncertainty": bool(reject_uncertainty),
                "max_base_or_height": False,
            }
            return False, reason_code, "; ".join(reasons), reason_flags, debug_info
            
        return True, None, None, [], None
        
    def _calculate_triangle_gradient(self, pts):
        """
        Calculate gradient magnitude and direction for a triangle.
        Uses the original V1 algorithm (h_gradient_numpy).
        
        Args:
            pts: Array of 3 points with x, y, h coordinates
            
        Returns:
            (gradient, angle_degrees) tuple
        """
        # Closed-form plane normal avoids per-triangle lstsq overhead.
        if pts.shape[0] < 3:
            return np.nan, np.nan
        try:
            p0 = pts[0]
            p1 = pts[1]
            p2 = pts[2]
            v1 = p1 - p0
            v2 = p2 - p0

            # Normal vector components for plane in (x, y, h)-space
            A0 = float(v1[1] * v2[2] - v1[2] * v2[1])
            A1 = float(v1[2] * v2[0] - v1[0] * v2[2])
            A2 = float(v1[0] * v2[1] - v1[1] * v2[0])

            if (not np.isfinite(A2)) or abs(A2) < 1e-30:
                return np.nan, np.nan

            with np.errstate(divide='ignore', invalid='ignore'):
                gradient = np.sqrt((A0**2 + A1**2) / A2**2)
                angle = np.arctan(A1 / A0) * 180 / np.pi
                if (1 - 1e9 * A0 / A2) > (1 + 1e9 * A0 / A2):
                    angle += 180

            if (not np.isfinite(gradient)) or (not np.isfinite(angle)):
                return np.nan, np.nan

            return float(gradient), float(angle % 360)
        except Exception:
            return np.nan, np.nan
        
    def calculate_average_gradient(self):
        """Calculate average gradient magnitude and direction (both weighted and unweighted).
        
        Returns:
            Tuple of (avg_gradient, avg_angle_unweighted, avg_angle_weighted)
        """
        if self.app_ref.gradient_data is None or self.app_ref.gradient_data.empty:
            return None, None, None
            
        gradients = self.app_ref.gradient_data['gradient']
        angles = self.app_ref.gradient_data['angle']
        
        # Average gradient magnitude
        avg_gradient = gradients.mean()
        
        # Unweighted circular mean for angles
        avg_angle_unweighted = self.calculate_average_angle(angles)
        
        # Weighted circular mean (weighted by gradient magnitude)
        avg_angle_weighted = self.calculate_weighted_average_angle(angles, gradients)
        
        return avg_gradient, avg_angle_unweighted, avg_angle_weighted
        
    def calculate_average_angle(self, angles):
        """
        Calculate circular mean of angles (unweighted).
        
        Args:
            angles: Series or array of angles in degrees
            
        Returns:
            Average angle in degrees
        """
        if isinstance(angles, pd.Series):
            angles = angles.values
            
        # Handle nested arrays
        flat_angles = []
        for a in angles:
            if isinstance(a, (list, np.ndarray)):
                flat_angles.extend(a)
            else:
                flat_angles.append(a)
                
        angles_rad = np.deg2rad(flat_angles)
        
        # Circular mean
        sin_mean = np.mean(np.sin(angles_rad))
        cos_mean = np.mean(np.cos(angles_rad))
        
        avg_angle = np.degrees(np.arctan2(sin_mean, cos_mean))
        
        # Normalize to 0-360
        if avg_angle < 0:
            avg_angle += 360
            
        return avg_angle
    
    def calculate_weighted_average_angle(self, angles, weights):
        """
        Calculate weighted circular mean of angles.
        
        Args:
            angles: Series or array of angles in degrees
            weights: Series or array of weights (e.g., gradient magnitudes)
            
        Returns:
            Weighted average angle in degrees
        """
        if isinstance(angles, pd.Series):
            angles = angles.values
        if isinstance(weights, pd.Series):
            weights = weights.values
            
        # Handle nested arrays
        flat_angles = []
        flat_weights = []
        for a, w in zip(angles, weights):
            if isinstance(a, (list, np.ndarray)):
                flat_angles.extend(a)
                # Repeat weight for each angle if needed
                flat_weights.extend([w] * len(a) if not isinstance(w, (list, np.ndarray)) else w)
            else:
                flat_angles.append(a)
                flat_weights.append(w if not isinstance(w, (list, np.ndarray)) else w[0])
        
        angles_rad = np.deg2rad(flat_angles)
        weights = np.array(flat_weights)
        
        # Normalize weights to avoid numerical issues
        if weights.sum() > 0:
            weights = weights / weights.sum()
        else:
            weights = np.ones_like(weights) / len(weights)
        
        # Weighted circular mean
        sin_mean = np.sum(weights * np.sin(angles_rad))
        cos_mean = np.sum(weights * np.cos(angles_rad))
        
        avg_angle = np.degrees(np.arctan2(sin_mean, cos_mean))
        
        # Normalize to 0-360
        if avg_angle < 0:
            avg_angle += 360
            
        return avg_angle

