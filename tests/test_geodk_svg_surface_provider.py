def test_geodk_svg_surface_provider_extracts_segments():
    from core.geology_layers import GeoDkSvgSurfaceGeologyProvider

    svg = (
        '<svg viewBox="0 0 1000 320" xmlns="http://www.w3.org/2000/svg">'
        "<style>.geounit-1{fill:#111111}.geounit-2{fill:#222222}</style>"
        # unit 1 is shallow (miny=10), unit 2 deeper (miny=60)
        '<polygon class="geounit-1" points="0,10 500,10 500,50 0,50" />'
        '<polygon class="geounit-2" points="500,60 1000,60 1000,120 500,120" />'
        "</svg>"
    )

    p = GeoDkSvgSurfaceGeologyProvider()
    p.update_from_svg(svg_text=svg, path_length_m=100.0)
    out = p.sample_transect(distances_m=[0.0, 50.0, 100.0])
    assert out["available"] is True
    segs = out["segments"]
    assert len(segs) >= 1
    assert segs[0].layer_code in {"1", "2"}
