"""
Downsampling utilities for visualization.

These functions are intended to reduce the number of vectors drawn in plots
without affecting the underlying dataset used for statistics.

Ported from the V1.1.x visualization behavior:
- Keep a fraction of the highest-gradient vectors
- Downsample remaining vectors using Largest-Triangle-Three-Buckets (LTTB)
"""

from __future__ import annotations

import math
from typing import Iterable, List, Sequence, Tuple


Point2D = Tuple[float, float]


def largest_triangle_three_buckets(points: Sequence[Point2D], threshold: int) -> List[Point2D]:
    """
    LTTB downsampling for a list of 2D points.

    Note: LTTB assumes an ordering of points. For the HeadAnalyser gradient vectors
    the ordering is deterministic but not spatially meaningful; this is preserved
    for backwards-compatible selection behavior with V1.
    """

    if threshold >= len(points):
        return list(points)
    if threshold < 3:
        raise ValueError("threshold must be >= 3")

    # Convert data to float, filtering NaNs
    data: List[Point2D] = []
    for x, y in points:
        xf = float(x)
        yf = float(y)
        if math.isnan(xf) or math.isnan(yf):
            continue
        data.append((xf, yf))

    if threshold >= len(data):
        return data

    # Bucket size (leave room for first and last points)
    every = (len(data) - 2) / (threshold - 2)

    a = 0
    next_a = 0
    max_area_point: Point2D = (0.0, 0.0)
    sampled: List[Point2D] = [data[0]]

    for i in range(0, threshold - 2):
        avg_x = 0.0
        avg_y = 0.0
        avg_range_start = int(math.floor((i + 1) * every) + 1)
        avg_range_end = int(math.floor((i + 2) * every) + 1)
        avg_range_end = avg_range_end if avg_range_end < len(data) else len(data)

        avg_range_length = avg_range_end - avg_range_start
        while avg_range_start < avg_range_end:
            avg_x += data[avg_range_start][0]
            avg_y += data[avg_range_start][1]
            avg_range_start += 1

        if avg_range_length > 0:
            avg_x /= avg_range_length
            avg_y /= avg_range_length

        range_offs = int(math.floor((i + 0) * every) + 1)
        range_to = int(math.floor((i + 1) * every) + 1)

        point_ax = data[a][0]
        point_ay = data[a][1]

        max_area = -1.0
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


def v1_style_vector_downsample_indices(
    centroids: Sequence[Point2D],
    max_count: int,
    high_gradient_fraction: float = 0.2,
) -> List[Point2D]:
    """
    Return a list of centroid points to keep using V1.1.x behavior.
    """
    if max_count >= len(centroids):
        return list(centroids)
    high_count = int(max_count * high_gradient_fraction)
    remaining_count = max_count - high_count
    if remaining_count < 3:
        remaining_count = 3

    head = list(centroids[:high_count])
    tail = list(centroids[high_count:])
    sampled_tail = largest_triangle_three_buckets(tail, remaining_count)
    return head + sampled_tail

