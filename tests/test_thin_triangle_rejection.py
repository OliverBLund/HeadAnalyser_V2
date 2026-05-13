from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pandas as pd

from core.gradient_calculation import GradientCalculation


def _build_app(*, low: float = 0.2, high: float = 8.0, head_unc: float = 0.01):
    return SimpleNamespace(
        col_mapping={"ID": "ID", "x": "x", "y": "y", "hydraulic head": "h"},
        gradient_data=None,
        rejected_data=None,
        total_triangles=None,
        rejected_due_to_triangle_quality=None,
        rejected_due_to_uncertainty=None,
        gradient_base_height_low=low,
        gradient_base_height_high=high,
        gradient_head_uncertainty=head_unc,
        gradient_stacked_epsilon=1e-10,
        gradient_max_base_or_height=1e9,
    )


def _square_dataset() -> pd.DataFrame:
    # Four non-collinear points -> 4 triangles; heads ensure uncertainty check passes.
    return pd.DataFrame(
        [
            {"ID": "A", "x": 0.0, "y": 0.0, "h": 10.00},
            {"ID": "B", "x": 1.0, "y": 0.0, "h": 10.10},
            {"ID": "C", "x": 0.0, "y": 1.0, "h": 10.20},
            {"ID": "D", "x": 1.0, "y": 1.0, "h": 10.30},
        ]
    )


def test_default_thresholds_do_not_reject_all_as_thin_triangle():
    app = _build_app(low=0.2, high=8.0)
    calc = GradientCalculation(app)
    tri = calc.create_gradient_dataframe(_square_dataset())

    assert app.total_triangles == 4
    assert len(tri) == 4
    assert app.rejected_data is not None
    if not app.rejected_data.empty:
        assert not (app.rejected_data["reason"] == "thin_triangle").any()


def test_strict_high_threshold_rejects_all_as_thin_triangle():
    # Right triangles in _square_dataset have a base/height ratio of 2.0 on one side.
    app = _build_app(low=0.2, high=1.3)
    calc = GradientCalculation(app)
    tri = calc.create_gradient_dataframe(_square_dataset())

    assert app.total_triangles == 4
    assert len(tri) == 0
    assert app.rejected_data is not None
    assert len(app.rejected_data) == 4
    assert set(app.rejected_data["reason"].tolist()) == {"thin_triangle"}
    assert app.rejected_data["quality_is_thin_triangle"].all()
    assert not app.rejected_data["quality_is_uncertainty"].any()
    assert app.rejected_data["gradient_computed"].all()
    assert app.rejected_data["gradient"].notna().all()
    assert app.rejected_data["angle"].notna().all()


def test_misconfigured_low_greater_than_high_rejects_all_triangles():
    # When low > high the accepted interval is impossible, so all triangles fail thin-triangle check.
    app = _build_app(low=2.5, high=1.3)
    calc = GradientCalculation(app)
    tri = calc.create_gradient_dataframe(_square_dataset())

    assert app.total_triangles == 4
    assert len(tri) == 0
    assert app.rejected_data is not None
    assert len(app.rejected_data) == 4
    assert set(app.rejected_data["reason"].tolist()) == {"thin_triangle"}


def test_mixed_rejection_sets_both_quality_flags_and_still_computes_gradient():
    df = pd.DataFrame(
        [
            {"ID": "A", "x": 0.0, "y": 0.0, "h": 10.000},
            {"ID": "B", "x": 10.0, "y": 0.0, "h": 10.005},
            {"ID": "C", "x": 0.001, "y": 0.02, "h": 10.006},
        ]
    )
    app = _build_app(low=0.2, high=8.0, head_unc=0.01)
    calc = GradientCalculation(app)
    tri = calc.create_gradient_dataframe(df)

    assert len(tri) == 0
    assert app.rejected_data is not None
    assert len(app.rejected_data) == 1
    row = app.rejected_data.iloc[0]
    assert row["reason"] == "mixed"
    assert bool(row["quality_is_thin_triangle"])
    assert bool(row["quality_is_uncertainty"])
    assert bool(row["gradient_computed"])
    assert np.isfinite(float(row["gradient"]))
    assert np.isfinite(float(row["angle"]))
