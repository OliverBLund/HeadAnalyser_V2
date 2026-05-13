from __future__ import annotations

import pandas as pd

from core.sensitivity_analysis import SensitivityAnalysisEngine


def _col_mapping():
    return {"ID": "ID", "x": "x", "y": "y", "hydraulic head": "h"}


def _base_settings():
    return {
        "gradient_head_uncertainty": 0.01,
        "gradient_confidence_level": 0.66,
        "gradient_base_height_low": 0.2,
        "gradient_base_height_high": 8.0,
        "gradient_max_base_or_height": 1e9,
        "gradient_stacked_epsilon": 1e-10,
    }


def _dataset() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"ID": "A", "x": 0.0, "y": 0.0, "h": 10.00},
            {"ID": "B", "x": 1.0, "y": 0.0, "h": 10.10},
            {"ID": "C", "x": 0.0, "y": 1.0, "h": 10.20},
            {"ID": "D", "x": 1.0, "y": 1.0, "h": 10.35},
            {"ID": "E", "x": 2.0, "y": 0.5, "h": 10.45},
        ]
    )


def test_parameter_sweep_backend_isolated_and_returns_runs():
    engine = SensitivityAnalysisEngine()
    data = _dataset()
    base = _base_settings()
    base_before = dict(base)

    result = engine.run(
        filtered_data=data,
        col_mapping=_col_mapping(),
        base_settings=base,
        config={"mode": "parameter_sweep", "seed": 1001},
    )

    assert result.baseline.run_id == "BASE"
    assert len(result.runs) == 3
    assert result.metadata["scope_type"] == "all_points"
    assert result.metadata["scope_point_count"] == len(data)
    assert base == base_before  # verify no mutation of caller-owned settings


def test_leave_out_respects_selected_point_scope():
    engine = SensitivityAnalysisEngine()
    data = _dataset()

    result = engine.run(
        filtered_data=data,
        col_mapping=_col_mapping(),
        base_settings=_base_settings(),
        config={
            "mode": "leave_out",
            "point_scope": {"type": "selected_points", "ids": ["A", "B", "C", "D"]},
            "leave_out": {"strategy": "one"},
        },
    )

    assert result.metadata["scope_type"] == "selected_points"
    assert result.metadata["scope_point_count"] == 4
    assert len(result.runs) == 4
    assert all(r.num_points == 3 for r in result.runs)


def test_monte_carlo_is_reproducible_for_same_seed():
    engine = SensitivityAnalysisEngine()
    data = _dataset()
    cfg = {
        "mode": "monte_carlo",
        "seed": 4242,
        "iterations": 12,
        "monte_carlo": {
            "perturb_h_sigma": 0.02,
            "perturb_xy_sigma": 0.0,
            "apply_xy": False,
        },
    }

    r1 = engine.run(
        filtered_data=data,
        col_mapping=_col_mapping(),
        base_settings=_base_settings(),
        config=cfg,
    )
    r2 = engine.run(
        filtered_data=data,
        col_mapping=_col_mapping(),
        base_settings=_base_settings(),
        config=cfg,
    )

    assert r1.distributions["avg_gradient"] == r2.distributions["avg_gradient"]
    assert r1.distributions["avg_angle_weighted"] == r2.distributions["avg_angle_weighted"]
    assert r1.distributions["rejected_ratio"] == r2.distributions["rejected_ratio"]
