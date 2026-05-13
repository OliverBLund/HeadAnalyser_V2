def test_compute_borehole_overlay_basic_mapping():
    from core.geodk_overlay import compute_borehole_overlay

    # Minimal SVG with viewBox and surface polyline.
    svg = (
        '<svg viewBox="0 0 1000 320" xmlns="http://www.w3.org/2000/svg">'
        '<polyline id="surface-1" points="0,20 1000,20" />'
        "</svg>"
    )

    path_utm = [[0.0, 0.0], [100.0, 0.0]]  # length 100m
    boreholes = [{"id": "BH1", "x": 10.0, "y": 0.0, "depth_m": 5.0}]
    res = compute_borehole_overlay(
        svg_text=svg,
        svg_w=1000,
        svg_h=320,
        path_utm=path_utm,
        boreholes=boreholes,
        length_m=100.0,
        response_summary={"ZMin": 0, "ZMax": -40, "PathLength": 100.0},
        tolerance_m=10.0,
    )

    assert res.viewbox_w == 1000.0
    assert res.viewbox_h == 320.0
    assert res.diag["count"] == 1
    item = res.items[0]
    assert item["label"] == "BH1"
    # surface is at y=20; depth_m 5 => y2 should be > y1
    assert item["y1"] == 20.0
    assert item["y2"] > item["y1"]


def test_compute_borehole_overlay_respects_tolerance():
    from core.geodk_overlay import compute_borehole_overlay

    svg = (
        '<svg viewBox="0 0 1000 320" xmlns="http://www.w3.org/2000/svg">'
        '<polyline id="surface-1" points="0,20 1000,20" />'
        "</svg>"
    )
    path_utm = [[0.0, 0.0], [100.0, 0.0]]
    # 20m off the line.
    boreholes = [{"id": "BHfar", "x": 10.0, "y": 20.0, "depth_m": 5.0}]
    res0 = compute_borehole_overlay(
        svg_text=svg,
        svg_w=1000,
        svg_h=320,
        path_utm=path_utm,
        boreholes=boreholes,
        length_m=100.0,
        response_summary={"ZMin": 0, "ZMax": -40, "PathLength": 100.0},
        tolerance_m=10.0,
    )
    assert res0.items == []

    res1 = compute_borehole_overlay(
        svg_text=svg,
        svg_w=1000,
        svg_h=320,
        path_utm=path_utm,
        boreholes=boreholes,
        length_m=100.0,
        response_summary={"ZMin": 0, "ZMax": -40, "PathLength": 100.0},
        tolerance_m=25.0,
    )
    assert len(res1.items) == 1


def test_compute_borehole_overlay_short_transect_axis_labels_map_x():
    from core.geodk_overlay import compute_borehole_overlay

    # X-axis labels are short distances (<200), so legacy value-size heuristics
    # would fail. Row-based axis detection should still recover x mapping.
    svg = (
        '<svg viewBox="0 0 1000 320" xmlns="http://www.w3.org/2000/svg">'
        '<text x="0" y="300">0</text>'
        '<text x="500" y="300">50</text>'
        '<text x="1000" y="300">100</text>'
        '<text x="20" y="40">0</text>'
        '<text x="20" y="120">-10</text>'
        '<text x="20" y="200">-20</text>'
        "</svg>"
    )
    path_utm = [[0.0, 0.0], [100.0, 0.0]]
    boreholes = [{"id": "BH1", "x": 20.0, "y": 0.0, "depth_m": 5.0}]
    res = compute_borehole_overlay(
        svg_text=svg,
        svg_w=1000,
        svg_h=320,
        path_utm=path_utm,
        boreholes=boreholes,
        length_m=100.0,
        response_summary={"ZMin": 0, "ZMax": -20, "PathLength": 100.0},
        tolerance_m=10.0,
    )

    assert len(res.items) == 1
    assert res.diag["x_mapping"] == "axis_text"
    assert res.diag["surface"] == "synthetic_from_yfit"


def test_compute_borehole_overlay_falls_back_without_surface_polyline():
    from core.geodk_overlay import compute_borehole_overlay

    svg = '<svg viewBox="0 0 1000 320" xmlns="http://www.w3.org/2000/svg"></svg>'
    path_utm = [[0.0, 0.0], [100.0, 0.0]]
    boreholes = [{"id": "BH1", "x": 10.0, "y": 0.0, "depth_m": 5.0}]
    res = compute_borehole_overlay(
        svg_text=svg,
        svg_w=1000,
        svg_h=320,
        path_utm=path_utm,
        boreholes=boreholes,
        length_m=100.0,
        response_summary={"ZMin": 0, "ZMax": -40, "PathLength": 100.0},
        tolerance_m=10.0,
    )

    assert len(res.items) == 1
    assert res.diag["x_mapping"] in {"surface_span", "viewbox_span"}
    assert res.diag["y_mapping"] == "zmin_zmax"
    assert res.diag["surface"] in {"synthetic_from_yfit", "surface_polyline"}


def test_compute_borehole_overlay_reports_drop_reasons():
    from core.geodk_overlay import compute_borehole_overlay

    svg = (
        '<svg viewBox="0 0 1000 320" xmlns="http://www.w3.org/2000/svg">'
        '<polyline id="surface-1" points="0,20 1000,20" />'
        "</svg>"
    )
    path_utm = [[0.0, 0.0], [100.0, 0.0]]
    boreholes = [
        {"id": "OK", "x": 10.0, "y": 0.0, "depth_m": 5.0},
        {"id": "NoDepth", "x": 15.0, "y": 0.0},
        {"id": "Far", "x": 20.0, "y": 50.0, "depth_m": 5.0},
        {"id": "BadXY", "x": "bad", "y": 0.0, "depth_m": 5.0},
    ]
    res = compute_borehole_overlay(
        svg_text=svg,
        svg_w=1000,
        svg_h=320,
        path_utm=path_utm,
        boreholes=boreholes,
        length_m=100.0,
        response_summary={"ZMin": 0, "ZMax": -40, "PathLength": 100.0},
        tolerance_m=10.0,
    )

    assert res.diag["boreholes_input"] == 4
    assert res.diag["boreholes_rendered"] == 1
    assert res.diag["drop_reasons"].get("missing_depth", 0) >= 1
    assert res.diag["drop_reasons"].get("out_of_tolerance", 0) >= 1
    assert res.diag["drop_reasons"].get("invalid_xy", 0) >= 1
