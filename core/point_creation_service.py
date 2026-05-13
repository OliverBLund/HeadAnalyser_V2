"""Shared point-creation helpers used by plot/map workflows."""

from __future__ import annotations

import pandas as pd


def validate_target(target_xy):
    """Validate and normalize a target XY tuple in dataset CRS."""
    if target_xy is None:
        raise ValueError("Target location is not set.")
    if not isinstance(target_xy, (tuple, list)) or len(target_xy) != 2:
        raise ValueError("Target location must be a 2-value tuple/list.")
    x = float(target_xy[0])
    y = float(target_xy[1])
    return x, y


def _generate_id(existing_data: pd.DataFrame, id_col: str | None) -> str:
    if not id_col:
        return "P1"
    if existing_data is None or existing_data.empty or id_col not in existing_data.columns:
        return "P1"

    used = set(existing_data[id_col].astype(str).fillna("").tolist())
    i = 1
    while True:
        candidate = f"P{i}"
        if candidate not in used:
            return candidate
        i += 1


def suggest_point_id(existing_data: pd.DataFrame, id_col: str | None) -> str:
    """Return next available auto-generated point ID."""
    return _generate_id(existing_data, id_col)


def build_point_record(target_xy, head_value, col_mapping, existing_data, point_id=None):
    """Build a new row dict using mapped dataset columns."""
    if not isinstance(col_mapping, dict):
        raise ValueError("Column mapping is missing.")

    x_col = col_mapping.get("x")
    y_col = col_mapping.get("y")
    h_col = col_mapping.get("hydraulic head")
    id_col = col_mapping.get("ID")
    if not x_col or not y_col or not h_col:
        raise ValueError("Column mapping must include x, y, and hydraulic head.")

    x, y = validate_target(target_xy)
    head = float(head_value)

    record = {}
    if isinstance(existing_data, pd.DataFrame):
        for col in existing_data.columns:
            record[col] = pd.NA

    record[x_col] = x
    record[y_col] = y
    record[h_col] = head
    if id_col:
        resolved_id = str(point_id).strip() if point_id is not None else ""
        if not resolved_id:
            resolved_id = _generate_id(existing_data, id_col)
        elif (
            isinstance(existing_data, pd.DataFrame)
            and id_col in existing_data.columns
            and resolved_id in set(existing_data[id_col].astype(str).fillna("").tolist())
        ):
            raise ValueError(f"Point ID '{resolved_id}' already exists.")
        record[id_col] = resolved_id

    return record


def append_point(existing_data, record):
    """Append one row and return a new DataFrame."""
    if existing_data is None:
        return pd.DataFrame([record])
    return pd.concat([existing_data, pd.DataFrame([record])], ignore_index=True)
