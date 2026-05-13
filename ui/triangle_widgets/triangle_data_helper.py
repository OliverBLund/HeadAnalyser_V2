"""
Pure-data transformations for triangle analysis widgets.
No Qt dependency — testable without QApplication.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np
import pandas as pd


def _iter_point_ids(value: Any):
    if value is None:
        return []
    if isinstance(value, (list, tuple, np.ndarray)):
        return value
    return [value]


# Canonical reason → display label mapping
_REASON_LABELS = {
    "thin_triangle": "Thin Triangle",
    "stacked_points": "Stacked Points",
    "uncertainty": "Uncertainty",
    "max_base_or_height": "Base/Height",
    "mixed": "Mixed",
    "calculation_failed": "Calc Failed",
}

# Canonical reason → Colors attribute name
_REASON_COLOR_KEYS = {
    "thin_triangle": "REJECTION_THIN",
    "stacked_points": "REJECTION_STACKED",
    "uncertainty": "REJECTION_UNCERTAINTY",
    "max_base_or_height": "REJECTION_BASE_HEIGHT",
    "mixed": "REJECTION_THIN",
    "calculation_failed": "REJECTION_CALC_FAILED",
}


class TriangleDataHelper:
    """Static helper methods for computing triangle analysis data."""

    @staticmethod
    def compute_summary(
        triangle_data: Optional[pd.DataFrame],
        rejected_data: Optional[pd.DataFrame],
        total_triangles: Optional[int],
    ) -> Dict[str, Any]:
        kept = int(len(triangle_data)) if triangle_data is not None and not triangle_data.empty else 0
        rejected = int(len(rejected_data)) if rejected_data is not None and not rejected_data.empty else 0
        total = int(total_triangles) if isinstance(total_triangles, (int, np.integer)) and int(total_triangles) > 0 else (kept + rejected)

        kept_pct = (kept / total * 100) if total > 0 else 0
        rejected_pct = (rejected / total * 100) if total > 0 else 0

        avg_gradient = None
        if triangle_data is not None and not triangle_data.empty and "gradient" in triangle_data.columns:
            grads = triangle_data["gradient"].apply(
                lambda g: g[0] if isinstance(g, (list, np.ndarray)) else g
            ).dropna()
            if len(grads) > 0:
                avg_gradient = float(grads.mean())

        return {
            "total": total,
            "kept": kept,
            "rejected": rejected,
            "kept_pct": kept_pct,
            "rejected_pct": rejected_pct,
            "avg_gradient": avg_gradient,
        }

    @staticmethod
    def compute_reason_breakdown(
        rejected_data: Optional[pd.DataFrame],
        mode: str = "primary",
    ) -> List[Dict[str, Any]]:
        if rejected_data is None or rejected_data.empty:
            return []

        if mode == "all":
            if "reason_flags" in rejected_data.columns:
                counts = Counter()
                for flags in rejected_data["reason_flags"]:
                    for reason in _iter_point_ids(flags):
                        if reason:
                            counts[str(reason)] += 1
            elif "reason" in rejected_data.columns:
                counts = rejected_data["reason"].value_counts()
            else:
                return []
        elif "reason" in rejected_data.columns:
            counts = rejected_data["reason"].value_counts()
        else:
            return []
        total = int(len(rejected_data))
        result = []
        for reason, count in counts.items():
            result.append({
                "reason": reason,
                "label": _REASON_LABELS.get(reason, str(reason)),
                "count": int(count),
                "total": total,
                "pct": (int(count) / total * 100) if total > 0 else 0,
                "color_key": _REASON_COLOR_KEYS.get(reason, "REJECTION_CALC_FAILED"),
            })
        return result

    @staticmethod
    def compute_point_frequency(
        rejected_data: Optional[pd.DataFrame],
        gradient_data: Optional[pd.DataFrame],
    ) -> pd.DataFrame:
        rej_freq: Counter = Counter()
        val_freq: Counter = Counter()
        grad_per_point: Dict[str, List[float]] = {}

        if rejected_data is not None and not rejected_data.empty and "point_ids" in rejected_data.columns:
            for ids in rejected_data["point_ids"]:
                rej_freq.update([str(v) for v in _iter_point_ids(ids)])

        has_gradient = (
            gradient_data is not None
            and not gradient_data.empty
            and "point_ids" in gradient_data.columns
        )
        if has_gradient:
            has_grad_col = "gradient" in gradient_data.columns
            for _, row in gradient_data.iterrows():
                pids = [str(v) for v in _iter_point_ids(row["point_ids"])]
                val_freq.update(pids)
                if has_grad_col:
                    try:
                        g = row["gradient"]
                        g = float(g[0] if isinstance(g, (list, np.ndarray)) else g)
                        for pid in pids:
                            grad_per_point.setdefault(pid, []).append(g)
                    except (TypeError, ValueError, IndexError):
                        pass

        all_ids = set(rej_freq.keys()) | set(val_freq.keys())
        if not all_ids:
            return pd.DataFrame(columns=[
                "point_id", "rejected_count", "valid_count", "rejection_rate",
                "max_gradient", "mean_gradient",
            ])

        rows = []
        for pid in all_ids:
            r = int(rej_freq.get(pid, 0))
            v = int(val_freq.get(pid, 0))
            tot = r + v
            rate = (r / tot * 100) if tot > 0 else 0
            grads = grad_per_point.get(pid, [])
            max_g = float(max(grads)) if grads else None
            mean_g = float(np.mean(grads)) if grads else None
            rows.append({
                "point_id": pid, "rejected_count": r, "valid_count": v,
                "rejection_rate": rate, "max_gradient": max_g, "mean_gradient": mean_g,
            })

        df = pd.DataFrame(rows)
        df = df.sort_values("rejected_count", ascending=False).reset_index(drop=True)
        return df

    @staticmethod
    def build_combined_triangle_df(
        triangle_data: Optional[pd.DataFrame],
        rejected_data: Optional[pd.DataFrame],
    ) -> pd.DataFrame:
        parts = []

        if triangle_data is not None and not triangle_data.empty:
            # Shallow copy is enough: we only add new metadata columns for table view.
            kept = triangle_data.reset_index().rename(columns={"index": "triangle_index"}).copy(deep=False)
            kept["triangle_source"] = "kept"
            kept["status"] = "kept"
            kept["reason"] = ""
            parts.append(kept)

        if rejected_data is not None and not rejected_data.empty:
            # Shallow copy keeps this fast on very large rejected sets.
            rej = rejected_data.reset_index().rename(columns={"index": "rejected_index"}).copy(deep=False)
            rej["triangle_source"] = "rejected"
            if "triangle_index" not in rej.columns:
                rej["triangle_index"] = np.nan
            rej["status"] = "rejected"
            if "gradient" not in rej.columns:
                rej["gradient"] = np.nan
            if "angle" not in rej.columns:
                rej["angle"] = np.nan
            parts.append(rej)

        if not parts:
            return pd.DataFrame()

        combined = pd.concat(parts, ignore_index=True, sort=False)
        return combined

    @staticmethod
    def filter_by_point_ids(
        triangle_data: Optional[pd.DataFrame],
        rejected_data: Optional[pd.DataFrame],
        selected_ids: Set[str],
    ) -> Tuple[Optional[pd.DataFrame], Optional[pd.DataFrame]]:
        if not selected_ids:
            return triangle_data, rejected_data

        def _filter(df):
            if df is None or df.empty or "point_ids" not in df.columns:
                return df
            mask = df["point_ids"].apply(
                lambda ids: bool(set(str(v) for v in _iter_point_ids(ids)) & selected_ids)
            )
            return df[mask].copy()

        return _filter(triangle_data), _filter(rejected_data)

    @staticmethod
    def compute_heatmap_data(
        freq_df: pd.DataFrame,
        filtered_data: Optional[pd.DataFrame],
        col_mapping: Dict[str, Optional[str]],
    ) -> pd.DataFrame:
        if freq_df.empty or filtered_data is None or filtered_data.empty:
            return pd.DataFrame(columns=["point_id", "x", "y", "rejection_rate"])

        x_col = col_mapping.get("x")
        y_col = col_mapping.get("y")
        id_col = col_mapping.get("ID")

        if not x_col or not y_col or not id_col:
            return pd.DataFrame(columns=["point_id", "x", "y", "rejection_rate"])

        if x_col not in filtered_data.columns or y_col not in filtered_data.columns:
            return pd.DataFrame(columns=["point_id", "x", "y", "rejection_rate"])

        rows = []
        for _, row in freq_df.iterrows():
            pid = str(row["point_id"])
            rate = float(row["rejection_rate"])
            match = filtered_data[filtered_data[id_col].astype(str) == pid]
            if not match.empty:
                rows.append({
                    "point_id": pid,
                    "x": float(match.iloc[0][x_col]),
                    "y": float(match.iloc[0][y_col]),
                    "rejection_rate": rate,
                })
        return pd.DataFrame(rows)
