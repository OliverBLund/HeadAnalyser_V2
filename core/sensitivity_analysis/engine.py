from __future__ import annotations

import hashlib
import time
from dataclasses import asdict
from types import SimpleNamespace
from typing import Callable, Dict, Optional

import numpy as np
import pandas as pd

from core.gradient_calculation import GradientCalculation

from .models import RunSummary, SensitivityConfig, SensitivityResult
from .scenarios import build_run_plans
from .scope import resolve_point_scope


def _circular_mean_deg(angles_deg: np.ndarray, weights: Optional[np.ndarray] = None) -> tuple[Optional[float], Optional[float]]:
    if angles_deg.size == 0:
        return None, None
    rad = np.deg2rad(angles_deg.astype(float))
    if weights is None:
        s = float(np.mean(np.sin(rad)))
        c = float(np.mean(np.cos(rad)))
    else:
        w = weights.astype(float)
        sw = float(np.sum(w))
        if sw <= 0:
            return None, None
        s = float(np.sum(np.sin(rad) * w) / sw)
        c = float(np.sum(np.cos(rad) * w) / sw)
    angle = float(np.degrees(np.arctan2(s, c)) % 360.0)
    coherence_r = float(np.hypot(s, c))
    return angle, coherence_r


def _circular_delta_deg(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b is None:
        return None
    d = (float(a) - float(b) + 180.0) % 360.0 - 180.0
    return float(d)


class SensitivityAnalysisEngine:
    """Isolated backend engine for sensitivity analysis runs.

    No direct dependencies on Qt widgets. The engine can be used from dialogs,
    scripts, or tests.
    """

    SETTINGS_KEYS = (
        "gradient_head_uncertainty",
        "gradient_confidence_level",
        "gradient_base_height_low",
        "gradient_base_height_high",
        "gradient_max_base_or_height",
        "gradient_stacked_epsilon",
    )

    def __init__(self, calculator_cls=GradientCalculation):
        self._calculator_cls = calculator_cls

    @staticmethod
    def _dataset_hash(data: pd.DataFrame, col_mapping: Dict[str, str]) -> str:
        if data is None or getattr(data, "empty", False):
            return ""
        cols = [col_mapping["ID"], col_mapping["x"], col_mapping["y"], col_mapping["hydraulic head"]]
        subset = data[cols]
        row_hash = pd.util.hash_pandas_object(subset, index=True).values
        return hashlib.blake2b(row_hash.tobytes(), digest_size=12).hexdigest()

    def _make_context(self, col_mapping: Dict[str, str], calc_params: Dict[str, float], mode: str, run_id: str):
        ctx = SimpleNamespace(
            col_mapping=dict(col_mapping),
            gradient_data=None,
            rejected_data=None,
            total_triangles=0,
            rejected_due_to_uncertainty=0,
            rejected_due_to_triangle_quality=0,
            rejected_due_to_calculation_failed=0,
            progress_parent=None,
            dataset_name=f"sensitivity-{mode}",
            _calc_reason=f"sensitivity:{mode}:{run_id}",
        )
        for k in self.SETTINGS_KEYS:
            setattr(ctx, k, float(calc_params[k]))
        return ctx

    def _run_once(self, *, mode: str, run_id: str, label: str, data: pd.DataFrame, col_mapping: Dict[str, str], calc_params: Dict[str, float], seed: Optional[int]):
        """Run a single scenario. Returns (RunSummary, kept_keys_set, rejected_keys_set)."""
        ctx = self._make_context(col_mapping, calc_params, mode, run_id)
        calc = self._calculator_cls(ctx)
        # Sensitivity backend should never show progress dialogs.
        setattr(calc, "_disable_progress", True)
        tri_df = calc.create_gradient_dataframe(data)
        tri = tri_df if tri_df is not None else pd.DataFrame()

        total = int(getattr(ctx, "total_triangles", 0) or 0)
        kept = int(len(tri))
        rejected = max(0, total - kept)
        rejected_ratio = (float(rejected) / float(total)) if total > 0 else None

        # Rejection reason counts from ctx (populated by GradientCalculation)
        rej_uncertainty = int(getattr(ctx, "rejected_due_to_uncertainty", 0) or 0)
        rej_quality = int(getattr(ctx, "rejected_due_to_triangle_quality", 0) or 0)
        rej_calc_failed = int(getattr(ctx, "rejected_due_to_calculation_failed", 0) or 0)

        if kept > 0 and {"gradient", "angle"}.issubset(set(tri.columns)):
            gradients = tri["gradient"].astype(float).to_numpy()
            angles = tri["angle"].astype(float).to_numpy()
            avg_gradient = float(np.mean(gradients)) if gradients.size else None
            avg_angle_unweighted, _ = _circular_mean_deg(angles)
            avg_angle_weighted, coherence_r = _circular_mean_deg(angles, gradients)
        else:
            avg_gradient = None
            avg_angle_unweighted = None
            avg_angle_weighted = None
            coherence_r = None

        # Extract triangle keys (frozenset of point_ids) for flip tracking
        kept_keys = set()
        rejected_keys = set()
        if kept > 0 and "point_ids" in tri.columns:
            for ids in tri["point_ids"]:
                if ids is not None:
                    kept_keys.add(frozenset(str(v) for v in ids))
        rej_df = getattr(ctx, "rejected_data", None)
        if rej_df is not None and not rej_df.empty and "point_ids" in rej_df.columns:
            for ids in rej_df["point_ids"]:
                if ids is not None:
                    rejected_keys.add(frozenset(str(v) for v in ids))

        summary = RunSummary(
            run_id=str(run_id),
            mode=str(mode),
            scenario_label=str(label),
            num_points=int(len(data)),
            total_triangles=total,
            kept_triangles=kept,
            rejected_triangles=rejected,
            rejected_ratio=rejected_ratio,
            avg_gradient=avg_gradient,
            avg_angle_unweighted=avg_angle_unweighted,
            avg_angle_weighted=avg_angle_weighted,
            direction_coherence_r=coherence_r,
            calc_params={k: float(calc_params[k]) for k in self.SETTINGS_KEYS},
            seed=int(seed) if seed is not None else None,
            rejected_due_to_uncertainty=rej_uncertainty,
            rejected_due_to_triangle_quality=rej_quality,
            rejected_due_to_calculation_failed=rej_calc_failed,
        )
        return summary, kept_keys, rejected_keys

    def run(
        self,
        *,
        filtered_data: pd.DataFrame,
        col_mapping: Dict[str, str],
        base_settings: Dict[str, float],
        config: SensitivityConfig | Dict,
        selected_point_ids: set | None = None,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> SensitivityResult:
        t0 = time.perf_counter()
        cfg = config if isinstance(config, SensitivityConfig) else SensitivityConfig.from_dict(config)

        for key in self.SETTINGS_KEYS:
            if key not in base_settings:
                raise ValueError(f"Missing base setting: {key}")

        id_col = col_mapping["ID"]
        scoped_data, scope_meta = resolve_point_scope(
            filtered_data,
            id_col=id_col,
            point_scope=cfg.point_scope,
            selected_point_ids=selected_point_ids,
        )

        baseline_result, _, _ = self._run_once(
            mode=cfg.mode,
            run_id="BASE",
            label="baseline",
            data=scoped_data,
            col_mapping=col_mapping,
            calc_params=dict(base_settings),
            seed=cfg.seed,
        )
        baseline = baseline_result

        plans = build_run_plans(
            cfg=cfg,
            data=scoped_data,
            col_mapping=col_mapping,
            base_settings={k: float(base_settings[k]) for k in self.SETTINGS_KEYS},
        )

        runs = []
        # Triangle flip tracker: {frozenset: [kept_count, rejected_count]}
        triangle_tracker: dict = {}
        total_runs = len(plans)

        for i, plan in enumerate(plans, start=1):
            if cancel_check and bool(cancel_check()):
                break
            summary, kept_keys, rejected_keys = self._run_once(
                mode=cfg.mode,
                run_id=plan.run_id,
                label=plan.scenario_label,
                data=plan.data,
                col_mapping=col_mapping,
                calc_params=plan.calc_params,
                seed=plan.seed,
            )
            summary.delta_avg_gradient = (
                float(summary.avg_gradient - baseline.avg_gradient)
                if (summary.avg_gradient is not None and baseline.avg_gradient is not None)
                else None
            )
            summary.delta_avg_angle_weighted = _circular_delta_deg(summary.avg_angle_weighted, baseline.avg_angle_weighted)
            runs.append(summary)

            # Accumulate triangle flip tracking
            for k in kept_keys:
                entry = triangle_tracker.get(k)
                if entry is None:
                    triangle_tracker[k] = [1, 0]
                else:
                    entry[0] += 1
            for k in rejected_keys:
                entry = triangle_tracker.get(k)
                if entry is None:
                    triangle_tracker[k] = [0, 1]
                else:
                    entry[1] += 1

            if progress_callback:
                progress_callback(i, total_runs, summary.scenario_label)

        # --- Compute rejection breakdown ---
        rejection_breakdown = {
            "uncertainty": [r.rejected_due_to_uncertainty for r in runs],
            "triangle_quality": [r.rejected_due_to_triangle_quality for r in runs],
            "calculation_failed": [r.rejected_due_to_calculation_failed for r in runs],
        }

        # --- Compute fragile points ---
        # Fragile triangle = one with both kept_count > 0 AND rejected_count > 0
        fragile_triangles = {
            k: counts for k, counts in triangle_tracker.items()
            if counts[0] > 0 and counts[1] > 0
        }
        total_unique_triangles = len(triangle_tracker) if triangle_tracker else 0

        # For each point, count how many fragile triangles it participates in
        point_fragile_count: dict = {}
        point_total_count: dict = {}
        for tri_key, _ in triangle_tracker.items():
            for pt in tri_key:
                point_total_count[pt] = point_total_count.get(pt, 0) + 1
        for tri_key, _ in fragile_triangles.items():
            for pt in tri_key:
                point_fragile_count[pt] = point_fragile_count.get(pt, 0) + 1

        fragile_points = []
        for pt, fcount in point_fragile_count.items():
            tcount = point_total_count.get(pt, 1)
            score = fcount / tcount if tcount > 0 else 0.0
            fragile_points.append({
                "point_id": pt,
                "fragile_triangle_count": fcount,
                "total_triangle_count": tcount,
                "fragility_score": round(score, 4),
            })
        fragile_points.sort(key=lambda x: x["fragility_score"], reverse=True)

        if cfg.mode == "leave_out":
            influence = [
                {
                    "point_label": r.scenario_label,
                    "delta_avg_gradient": r.delta_avg_gradient,
                    "delta_avg_angle_weighted": r.delta_avg_angle_weighted,
                }
                for r in sorted(
                    runs,
                    key=lambda r: abs(r.delta_avg_angle_weighted) if r.delta_avg_angle_weighted is not None else -1.0,
                    reverse=True,
                )
            ]
        else:
            influence = []

        result = SensitivityResult(
            config=cfg,
            baseline=baseline,
            runs=runs,
            distributions={
                "avg_gradient": [float(r.avg_gradient) for r in runs if r.avg_gradient is not None],
                "avg_angle_weighted": [float(r.avg_angle_weighted) for r in runs if r.avg_angle_weighted is not None],
                "rejected_ratio": [float(r.rejected_ratio) for r in runs if r.rejected_ratio is not None],
            },
            influence=influence,
            metadata={
                "engine_version": "v2",
                "dataset_hash": self._dataset_hash(scoped_data, col_mapping),
                "elapsed_ms": float((time.perf_counter() - t0) * 1000.0),
                **scope_meta,
                "baseline": asdict(baseline),
                "run_count": int(len(runs)),
                "unique_triangles": total_unique_triangles,
                "fragile_triangles": len(fragile_triangles),
            },
            rejection_breakdown=rejection_breakdown,
            fragile_points=fragile_points,
        )
        return result
