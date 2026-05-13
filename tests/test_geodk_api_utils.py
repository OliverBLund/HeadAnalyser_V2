import pytest


def test_normalize_token_strips_quotes_and_bearer():
    from core.geodk_api import normalize_token

    assert normalize_token('"abc"') == "abc"
    assert normalize_token("Bearer abc") == "abc"
    assert normalize_token(" bearer   abc  ") == "abc"
    assert normalize_token("") == ""


def test_svg_stats_counts_polygons_and_polylines():
    from core.geodk_api import svg_stats

    svg = "<svg><polygon /><polyline /><polygon></polygon></svg>"
    st = svg_stats(svg)
    assert st["polygons"] == 2
    assert st["polylines"] == 1


def test_normalize_svg_for_display_adds_viewbox_and_preserve():
    from core.geodk_api import normalize_svg_for_display

    raw = '<svg width="1000" height="320"><g></g></svg>'
    out = normalize_svg_for_display(raw)
    assert "viewBox=" in out
    assert "preserveAspectRatio=" in out


def test_normalize_svg_for_display_adds_preserve_when_viewbox_present():
    from core.geodk_api import normalize_svg_for_display

    raw = '<svg viewBox="0 0 10 10"><g></g></svg>'
    out = normalize_svg_for_display(raw)
    assert "viewBox=" in out
    assert "preserveAspectRatio=" in out


def test_normalize_svg_for_display_removes_webkit_font_smoothing():
    from core.geodk_api import normalize_svg_for_display

    raw = '<svg><style>.x{ -webkit-font-smoothing: antialiased; }</style></svg>'
    out = normalize_svg_for_display(raw, width=10, height=10)
    assert "-webkit-font-smoothing" not in out


def test_bbox_path_bbox_and_intersects():
    from core.geodk_api import BBox, path_bbox

    pb = path_bbox([[0, 0], [10, 10]])
    assert pb is not None
    assert pb.minx == 0
    assert pb.miny == 0
    assert pb.maxx == 10
    assert pb.maxy == 10

    assert pb.intersects(BBox(-1, -1, 0, 0))
    assert pb.intersects(BBox(10, 10, 11, 11))
    assert not pb.intersects(BBox(11, 0, 12, 1))


def test_write_repro_bundle_rotation_keeps_last_n(tmp_path):
    from core.geodk_api import write_repro_bundle

    stamps = [
        "20240101_000000_000",
        "20240101_000000_001",
        "20240101_000000_002",
    ]
    for s in stamps:
        write_repro_bundle(
            {"stamp": s},
            svg_text=f"<svg>{s}</svg>",
            root_dir=tmp_path,
            keep_last_n=2,
            stamp=s,
        )

    out_dir = tmp_path / ".recovery" / "geo_dk"
    jsons = sorted([p.name for p in out_dir.glob("geo_dk_repro_*.json")])
    svgs = sorted([p.name for p in out_dir.glob("geo_dk_crosssection_*.svg")])

    assert jsons == [
        "geo_dk_repro_20240101_000000_001.json",
        "geo_dk_repro_20240101_000000_002.json",
    ]
    assert svgs == [
        "geo_dk_crosssection_20240101_000000_001.svg",
        "geo_dk_crosssection_20240101_000000_002.svg",
    ]
