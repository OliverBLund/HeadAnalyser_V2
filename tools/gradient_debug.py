"""
Gradient debug utility (HeadAnalyser V2).

Prints average gradient and mean directions for a dataset using the same core
triangle algorithm as the app (V2 core).

This is intended for validating changes and comparing conventions:
- Unweighted circular mean of triangle angles (each triangle equal weight)
- Gradient-weighted circular mean of triangle angles (vector-sum style)

Optionally simulates V1's gradient vector plot downsampling approach.
"""

import argparse
import math
import pathlib
import sys
import types
from typing import Iterable

import numpy as np
import pandas as pd

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from HeadAnalyser_V2.core.gradient_calculation import GradientCalculation  # noqa: E402


def _safe_float(value):
    if isinstance(value, str):
        value = value.replace(",", ".")
    try:
        if pd.isna(value):
            return value
    except Exception:
        pass
    try:
        return float(value)
    except (ValueError, TypeError):
        return np.nan


def convert_decimal_separator(df: pd.DataFrame, id_column: str) -> pd.DataFrame:
    df = df.copy()
    for col in df.columns:
        if col == id_column:
            continue
        df[col] = df[col].apply(_safe_float)
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def circular_mean_deg(angles_deg: Iterable[float]) -> float:
    angles_rad = np.deg2rad(np.asarray(list(angles_deg), dtype=float))
    sin_mean = np.mean(np.sin(angles_rad))
    cos_mean = np.mean(np.cos(angles_rad))
    return float((np.rad2deg(np.arctan2(sin_mean, cos_mean)) + 360) % 360)


def weighted_circular_mean_deg(angles_deg: Iterable[float], weights: Iterable[float]) -> float:
    angles_rad = np.deg2rad(np.asarray(list(angles_deg), dtype=float))
    weights_arr = np.asarray(list(weights), dtype=float)
    if weights_arr.sum() > 0:
        weights_arr = weights_arr / weights_arr.sum()
    else:
        weights_arr = np.ones_like(weights_arr) / len(weights_arr)
    sin_mean = np.sum(weights_arr * np.sin(angles_rad))
    cos_mean = np.sum(weights_arr * np.cos(angles_rad))
    return float((np.rad2deg(np.arctan2(sin_mean, cos_mean)) + 360) % 360)


def largest_triangle_three_buckets(data, threshold):
    if threshold >= len(data):
        return data
    data = [(float(x), float(y)) for x, y in data if not (math.isnan(float(x)) or math.isnan(float(y)))]
    every = (len(data) - 2) / (threshold - 2)
    a = 0
    next_a = 0
    max_area_point = (0, 0)
    sampled = [data[0]]
    for i in range(0, threshold - 2):
        avg_x = 0
        avg_y = 0
        avg_range_start = int(math.floor((i + 1) * every) + 1)
        avg_range_end = int(math.floor((i + 2) * every) + 1)
        avg_rang_end = avg_range_end if avg_range_end < len(data) else len(data)
        avg_range_length = avg_rang_end - avg_range_start
        while avg_range_start < avg_rang_end:
            avg_x += data[avg_range_start][0]
            avg_y += data[avg_range_start][1]
            avg_range_start += 1
        avg_x /= avg_range_length
        avg_y /= avg_range_length
        range_offs = int(math.floor((i + 0) * every) + 1)
        range_to = int(math.floor((i + 1) * every) + 1)
        point_ax = data[a][0]
        point_ay = data[a][1]
        max_area = -1
        while range_offs < range_to:
            area = math.fabs(
                (point_ax - avg_x) * (data[range_offs][1] - point_ay)
                - (point_ax - data[range_offs][0]) * (avg_y - point_ay)
            ) * 0.5
            if area > max_area:
                max_area = area
                max_area_point = data[range_offs]
                next_a = range_offs
            range_offs += 1
        sampled.append(max_area_point)
        a = next_a
    sampled.append(data[-1])
    return sampled


def simulate_v1_vector_downsample(triangle_df: pd.DataFrame, max_arrows: int, high_gradient_percentage: float) -> pd.DataFrame:
    sorted_data = triangle_df.sort_values(by="gradient", ascending=False)
    high_count = int(max_arrows * high_gradient_percentage)
    high = sorted_data.head(high_count)
    remaining = sorted_data.iloc[high_count:]
    remaining_count = max_arrows - high_count
    pts_for_sampling = remaining[["centroid_x", "centroid_y"]].values.tolist()
    sampled_pts = largest_triangle_three_buckets(pts_for_sampling, remaining_count)
    sampled_df = pd.DataFrame(sampled_pts, columns=["centroid_x", "centroid_y"]).round(10)
    sampled_data = remaining.round(10).merge(sampled_df, on=["centroid_x", "centroid_y"], how="inner")
    return pd.concat([high, sampled_data], ignore_index=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", help="Input CSV/XLSX path")
    parser.add_argument("--sep", default=";", help="CSV separator (default: ';')")
    parser.add_argument("--encoding", default="utf-8-sig", help="CSV encoding (default: utf-8-sig)")
    parser.add_argument("--id", dest="id_col", default="Boring")
    parser.add_argument("--x", dest="x_col", default="X")
    parser.add_argument("--y", dest="y_col", default="Y")
    parser.add_argument("--h", dest="h_col", default="VS")
    parser.add_argument("--drop-top-gradients", type=int, default=0, metavar="N",
                        help="Drop N highest-gradient triangles before summary (default: 0).")
    parser.add_argument("--simulate-v1-downsample", type=int, default=0, metavar="N")
    parser.add_argument("--high-gradient-percentage", type=float, default=0.2)
    args = parser.parse_args()

    if args.path.lower().endswith(".xlsx"):
        df = pd.read_excel(args.path)
    else:
        df = pd.read_csv(args.path, sep=args.sep, encoding=args.encoding)

    df = convert_decimal_separator(df, id_column=args.id_col)
    df = df.dropna(subset=[args.x_col, args.y_col, args.h_col]).reset_index(drop=True)

    app = types.SimpleNamespace(
        col_mapping={"ID": args.id_col, "x": args.x_col, "y": args.y_col, "hydraulic head": args.h_col},
        gradient_data=None,
        rejected_data=None,
        total_triangles=None,
        rejected_due_to_triangle_quality=None,
        rejected_due_to_uncertainty=None,
    )
    calc = GradientCalculation(app)
    triangle_df = calc.create_gradient_dataframe(df)

    print(f"points: {len(df)}")
    print(f"valid_triangles: {len(triangle_df)}")
    print(f"rejected_triangles: {len(app.rejected_data) if app.rejected_data is not None else 0}")

    if triangle_df is None or triangle_df.empty:
        print("No valid triangles.")
        return 1

    tri_for_stats = triangle_df
    if args.drop_top_gradients > 0:
        tri_for_stats = tri_for_stats.sort_values(by="gradient", ascending=True).iloc[:-args.drop_top_gradients]
        tri_for_stats = tri_for_stats.reset_index(drop=True)

    avg_grad = float(tri_for_stats["gradient"].mean())
    grad_std = float(tri_for_stats["gradient"].std(ddof=1)) if len(tri_for_stats) > 1 else float("nan")

    mean_unweighted = circular_mean_deg(tri_for_stats["angle"])
    mean_weighted = weighted_circular_mean_deg(tri_for_stats["angle"], tri_for_stats["gradient"])

    # Circular spread (unweighted) via mean resultant length R.
    angles_rad = np.deg2rad(tri_for_stats["angle"].to_numpy(dtype=float))
    R = float(np.sqrt(np.mean(np.cos(angles_rad)) ** 2 + np.mean(np.sin(angles_rad)) ** 2))
    circ_std_rad = float(np.sqrt(-2.0 * np.log(R))) if R > 0 else float("inf")
    circ_std_deg = float(np.rad2deg(circ_std_rad))

    print(f"avg_gradient: {avg_grad:.10f}")
    print(f"stdev_gradient: {grad_std:.10f}")
    print(f"mean_angle_unweighted_deg: {mean_unweighted:.10f}")
    print(f"mean_angle_unweighted_rad: {math.radians(mean_unweighted):.10f}")
    print(f"mean_angle_weighted_deg: {mean_weighted:.10f}")
    print(f"mean_angle_weighted_rad: {math.radians(mean_weighted):.10f}")
    print(f"flow_dir_unweighted_deg: {(mean_unweighted + 180.0) % 360.0:.10f}")
    print(f"flow_dir_weighted_deg: {(mean_weighted + 180.0) % 360.0:.10f}")
    print(f"circ_stdev_unweighted_deg: {circ_std_deg:.10f}")
    print(f"circ_stdev_unweighted_rad: {circ_std_rad:.10f}")
    if args.drop_top_gradients > 0:
        print(f"dropped_top_gradients: {args.drop_top_gradients}")
        print(f"triangles_used_for_stats: {len(tri_for_stats)}")

    # Overall plane fit ("all wells") summary using the same V1-style formula.
    overall = calc.h_gradient(df)
    if overall is not None and not overall.empty:
        og = float(overall["gradient"].iloc[0])
        oa = float(overall["angle"].iloc[0])
        print("")
        print(f"all_wells_plane_gradient: {og:.10f}")
        print(f"all_wells_plane_angle_deg: {oa:.10f}")
        print(f"all_wells_plane_angle_rad: {math.radians(oa):.10f}")
        print(f"all_wells_plane_flow_deg: {(oa + 180.0) % 360.0:.10f}")

    if args.simulate_v1_downsample:
        ds = simulate_v1_vector_downsample(
            tri_for_stats,
            max_arrows=args.simulate_v1_downsample,
            high_gradient_percentage=args.high_gradient_percentage,
        )
        avg_grad_ds = float(ds["gradient"].mean())
        mean_unweighted_ds = circular_mean_deg(ds["angle"])
        mean_weighted_ds = weighted_circular_mean_deg(ds["angle"], ds["gradient"])
        print("")
        print(f"simulate_v1_downsample_n: {args.simulate_v1_downsample}")
        print(f"downsampled_rows: {len(ds)}")
        print(f"avg_gradient_downsampled: {avg_grad_ds:.10f}")
        print(f"mean_angle_unweighted_downsampled_deg: {mean_unweighted_ds:.10f}")
        print(f"mean_angle_weighted_downsampled_deg: {mean_weighted_ds:.10f}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
