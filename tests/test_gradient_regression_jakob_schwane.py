from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from core.data_processing import DataProcessing
from core.gradient_calculation import GradientCalculation


def _load_like_app(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, delimiter=";", dtype=str, encoding="utf-8-sig")
    app = SimpleNamespace(col_mapping={"ID": "Boring", "x": "X", "y": "Y", "hydraulic head": "VS"})
    df = DataProcessing(app).convert_decimal_separator(df)
    return df.dropna(subset=["X", "Y", "VS"]).reset_index(drop=True)


def test_jakob_schwane_2022_06_27_regression_full_triangle_set():
    """
    Regression test for a known dataset with stacked points and duplicate IDs.

    This verifies that:
    - stacked-point triangles are rejected
    - duplicates in the ID column do not corrupt calculations
    - summary stats are stable
    """
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "Testing data" / "Jakob_Schwane_data" / "Pejling_BilagJ_27-06-2022.csv"
    df = _load_like_app(path)

    app = SimpleNamespace(
        col_mapping={"ID": "Boring", "x": "X", "y": "Y", "hydraulic head": "VS"},
        gradient_data=None,
        rejected_data=None,
        total_triangles=None,
        rejected_due_to_triangle_quality=None,
        rejected_due_to_uncertainty=None,
    )
    calc = GradientCalculation(app)
    tri = calc.create_gradient_dataframe(df)

    assert len(df) == 31
    assert len(tri) == 983
    assert app.rejected_data is not None
    assert len(app.rejected_data) == 3512  # 31 choose 3 = 4495 total

    avg_gradient, avg_angle_unweighted, avg_angle_weighted = calc.calculate_average_gradient()
    assert avg_gradient == pytest.approx(0.0029443470963503183, rel=0, abs=1e-12)
    assert avg_angle_unweighted == pytest.approx(128.19834229916054, rel=0, abs=1e-9)
    assert avg_angle_weighted == pytest.approx(82.1007497956823, rel=0, abs=1e-9)


def test_duplicate_id_labels_do_not_change_results():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "Testing data" / "Jakob_Schwane_data" / "Pejling_BilagJ_27-06-2022.csv"
    df = _load_like_app(path)

    app_base = SimpleNamespace(
        col_mapping={"ID": "Boring", "x": "X", "y": "Y", "hydraulic head": "VS"},
        gradient_data=None,
        rejected_data=None,
        total_triangles=None,
        rejected_due_to_triangle_quality=None,
        rejected_due_to_uncertainty=None,
    )
    calc_base = GradientCalculation(app_base)
    calc_base.create_gradient_dataframe(df)
    base = calc_base.calculate_average_gradient()

    # Rewrite IDs to be unique; results should be identical (IDs are labels only).
    df_unique = df.copy()
    df_unique["Boring"] = [f"{v}_{i}" for i, v in enumerate(df_unique["Boring"].astype(str).tolist())]

    app_unique = SimpleNamespace(
        col_mapping={"ID": "Boring", "x": "X", "y": "Y", "hydraulic head": "VS"},
        gradient_data=None,
        rejected_data=None,
        total_triangles=None,
        rejected_due_to_triangle_quality=None,
        rejected_due_to_uncertainty=None,
    )
    calc_unique = GradientCalculation(app_unique)
    calc_unique.create_gradient_dataframe(df_unique)
    unique = calc_unique.calculate_average_gradient()

    assert unique[0] == pytest.approx(base[0], rel=0, abs=1e-12)
    assert unique[1] == pytest.approx(base[1], rel=0, abs=1e-9)
    assert unique[2] == pytest.approx(base[2], rel=0, abs=1e-9)


def test_jakob_schwane_2022_10_03_regression_small_dataset():
    """
    Regression test for a small dataset (no stacked points, no duplicate IDs).
    """
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "Testing data" / "Jakob_Schwane_data" / "Pejling_BilagJ_03-10-2022.csv"
    df = _load_like_app(path)

    app = SimpleNamespace(
        col_mapping={"ID": "Boring", "x": "X", "y": "Y", "hydraulic head": "VS"},
        gradient_data=None,
        rejected_data=None,
        total_triangles=None,
        rejected_due_to_triangle_quality=None,
        rejected_due_to_uncertainty=None,
    )
    calc = GradientCalculation(app)
    tri = calc.create_gradient_dataframe(df)

    assert len(df) == 8
    assert len(tri) == 30
    assert app.rejected_data is not None
    assert len(app.rejected_data) == 26  # 8 choose 3 = 56 total

    avg_gradient, avg_angle_unweighted, avg_angle_weighted = calc.calculate_average_gradient()
    assert avg_gradient == pytest.approx(0.0008428899734871727, rel=0, abs=1e-12)
    assert avg_angle_unweighted == pytest.approx(191.06436535964036, rel=0, abs=1e-9)
    assert avg_angle_weighted == pytest.approx(188.06650687060937, rel=0, abs=1e-9)
