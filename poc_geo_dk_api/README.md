# Geo.dk Draw-to-Transect PoC

This is a standalone proof-of-concept that demonstrates:

1. Draw a line on a Leaflet map.
2. Request a cross section from `data.geo.dk` (`/api/v3/crosssection`).
3. Render the returned transect SVG in the UI.

It uses a local Python proxy server to avoid browser CORS issues and to keep the token out of frontend-to-Geo.dk direct calls.
It also includes a QGIS-like model lookup (`/api/geomodel`) to auto-pick model IDs from line coordinates.

## Files

- `poc_geo_dk_api/server.py` - local HTTP server + API proxy.
- `poc_geo_dk_api/index.html` - PoC UI.
- `poc_geo_dk_api/app.js` - frontend logic.
- `poc_geo_dk_api/styles.css` - UI styles.

## Run

From project root:

```bash
python3 poc_geo_dk_api/server.py --host 127.0.0.1 --port 8765
```

Open:

`http://127.0.0.1:8765`

If your environment fails TLS validation (certificate verify failed), run:

```bash
python3 poc_geo_dk_api/server.py --host 127.0.0.1 --port 8765 --insecure-ssl
```

`--insecure-ssl` is for PoC/debug only.

## Usage

1. Draw a polyline on the map.
2. Keep defaults or set your own credentials.
3. Click `Get Token`.
4. Click `Load Models For Line` (optional but recommended).
5. Pick a model in `Model Choice` (or leave auto).
6. Click `Request Cross Section`.
5. The right panel shows:
- summary metadata,
- returned SVG transect,
- raw JSON response.

The map now draws your token's allowed bounding box (red dashed rectangle, from `GAL.BoundingBox` in JWT claims). Draw the line inside that area.

## Notes

- Leaflet line coordinates are converted automatically from `EPSG:4326` to `EPSG:25832` before API calls.
- With demo credentials, the request may return terrain-only profile (no geological layers, `Model=null`, `ProfileLayers=0`).
- With a project/user token that has broader model permissions, the same flow should return geological layer content in the response/SVG.
- `Width` defaults to `1000` and `LinePointDistance` can be auto-calculated from line length (matching the QGIS plugin approach).
- `Depth (Level)` defaults to `-40` (matching the GeoAtlas QGIS plugin default; negative values go down).
- `Load Models For Line` uses `/api/geomodel` + model bounding boxes to list model IDs valid for your current transect.
- `Auto-select first GeoModelId from token claim` + path-based model lookup attempts to choose a better starting model before requesting cross section.
- If default request is terrain-only, enable `Auto-try token GeoModelIds` to try additional `GAL.GeoModels` IDs from token claims automatically.
- You can switch between `v3` and `v2` API major versions from the UI for diagnostics.

## Backend Smoke Test (No Browser)

If you want to validate the backend pipeline headlessly:

```bash
python3 poc_geo_dk_api/smoke_test.py \
  --username "you@example.com" --password "..." --role "" \
  --geomodelid auto \
  --path '[[486406.903,6261887.022],[496204.85,6259164.59]]' \
  --insecure-ssl
```

Success signal: `SVG polygons` is > 0 for a geological model.
