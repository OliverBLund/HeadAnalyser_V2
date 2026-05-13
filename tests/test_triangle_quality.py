from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pandas as pd

from core.gradient_calculation import GradientCalculation


def test_stacked_points_are_rejected_and_not_in_valid_triangles():
    # Two points share X/Y but have different heads (stacked points / multi-intake at same coords).
    df = pd.DataFrame(
        [
            {"ID": "A", "x": 0.0, "y": 0.0, "h": 10.0},
            {"ID": "B", "x": 0.0, "y": 0.0, "h": 11.0},
            {"ID": "C", "x": 1.0, "y": 0.0, "h": 10.2},
            {"ID": "D", "x": 0.0, "y": 1.0, "h": 10.3},
        ]
    )
    app = SimpleNamespace(
        col_mapping={"ID": "ID", "x": "x", "y": "y", "hydraulic head": "h"},
        gradient_data=None,
        rejected_data=None,
        total_triangles=None,
        rejected_due_to_triangle_quality=None,
        rejected_due_to_uncertainty=None,
    )
    calc = GradientCalculation(app)
    tri = calc.create_gradient_dataframe(df)

    # 4 choose 3 = 4 triangles. The triangle containing both A and B must be rejected.
    assert app.rejected_data is not None
    rejected = app.rejected_data
    assert (rejected["reason"] == "stacked_points").any()

    # No valid triangle contains both stacked points.
    valid_sets = [set(ids) for ids in tri["point_ids"].tolist()]
    assert not any({"A", "B"}.issubset(s) for s in valid_sets)


def test_average_angle_wraps_correctly_near_zero():
    app = SimpleNamespace(
        col_mapping={"ID": "ID", "x": "x", "y": "y", "hydraulic head": "h"},
        gradient_data=None,
    )
    calc = GradientCalculation(app)
    # Angles near 0/360 should average to ~0, not 180.
    angles = np.array([350.0, 10.0])
    avg = calc.calculate_average_angle(angles)
    assert avg < 1.0 or avg > 359.0

