from __future__ import annotations

from typing import Dict, Tuple

import pandas as pd

from .models import PointScope


def resolve_point_scope(
    data: pd.DataFrame,
    id_col: str,
    point_scope: PointScope,
    selected_point_ids: set | None = None,
) -> Tuple[pd.DataFrame, Dict[str, object]]:
    """Apply scope selection to the input DataFrame.

    The function is deliberately simple and pure so it can be reused from UI code
    and unit tests without coupling to MainWindow internals.
    """
    if data is None or getattr(data, "empty", False):
        return pd.DataFrame(), {
            "scope_type": "all_points",
            "scope_point_count": 0,
            "scope_point_ids": [],
        }

    scope = point_scope.normalize()
    work = data.copy()

    if scope.type == "selected_points":
        ids = set(scope.ids)
        if not ids:
            ids = {str(v) for v in (selected_point_ids or set()) if str(v).strip()}
        if not ids:
            return work.iloc[0:0].copy(), {
                "scope_type": "selected_points",
                "scope_point_count": 0,
                "scope_point_ids": [],
            }
        scoped = work[work[id_col].astype(str).isin(ids)].copy()
        return scoped, {
            "scope_type": "selected_points",
            "scope_point_count": int(len(scoped)),
            "scope_point_ids": sorted(ids),
        }

    all_ids = sorted(set(work[id_col].astype(str).tolist()))
    return work, {
        "scope_type": "all_points",
        "scope_point_count": int(len(work)),
        "scope_point_ids": all_ids,
    }
