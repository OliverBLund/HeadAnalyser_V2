"use strict";

const state = {
  map: null,
  lineLayer: null,
  lineCoords: null, // [[x,y], [x,y], ...]
  lastPath25832: null,
  bboxLayer: null,
  tokenClaims: null,
  tokenBbox25832: null, // {xmin,ymin,xmax,ymax,epsg}
  tokenProfileLayers: null,
  tokenGeoModels: null,
  pathModels: [],
  svgFitMode: true,
  lastResponse: null,
};

const API_BASE = window.location.protocol === "file:" ? "http://127.0.0.1:8765" : "";

function byId(id) {
  return document.getElementById(id);
}

function normalizeTokenInput(rawToken) {
  const token = String(rawToken || "").trim();
  if (token.toLowerCase().startsWith("bearer ")) {
    return token.slice(7).trim();
  }
  return token;
}

function setStatus(msg, level = "info") {
  const el = byId("status");
  el.textContent = msg;
  el.className = "status";
  if (level === "error") el.classList.add("error");
  if (level === "ok") el.classList.add("ok");
}

function decodeJwtClaims(jwtToken) {
  try {
    const parts = jwtToken.split(".");
    if (parts.length < 2) return null;
    const b64 = parts[1].replace(/-/g, "+").replace(/_/g, "/");
    const padded = b64 + "=".repeat((4 - (b64.length % 4)) % 4);
    const json = atob(padded);
    return JSON.parse(json);
  } catch (err) {
    return null;
  }
}

function parseBoundingBoxClaim(raw) {
  if (!raw || typeof raw !== "string") return null;
  // Example: "443000,6277000,464800,6289900,epsg=25832"
  const parts = raw.split(",").map((p) => p.trim());
  if (parts.length < 5) return null;
  const xmin = Number(parts[0]);
  const ymin = Number(parts[1]);
  const xmax = Number(parts[2]);
  const ymax = Number(parts[3]);
  const epsgMatch = parts[4].match(/epsg\s*=\s*(\d+)/i);
  const epsg = epsgMatch ? Number(epsgMatch[1]) : null;
  if ([xmin, ymin, xmax, ymax].some((v) => Number.isNaN(v))) return null;
  return { xmin, ymin, xmax, ymax, epsg };
}

function parseCsvClaimToList(raw) {
  if (typeof raw !== "string") return null;
  return raw
    .split(",")
    .map((s) => s.trim())
    .filter((s) => s.length > 0);
}

function ensureProjDefs() {
  if (typeof proj4 === "undefined") {
    throw new Error("proj4 is not loaded");
  }
  proj4.defs("EPSG:25832", "+proj=utm +zone=32 +ellps=GRS80 +units=m +no_defs");
}

function lonLatTo25832(lon, lat) {
  ensureProjDefs();
  return proj4("EPSG:4326", "EPSG:25832", [lon, lat]);
}

function xy25832ToLonLat(x, y) {
  ensureProjDefs();
  return proj4("EPSG:25832", "EPSG:4326", [x, y]);
}

function setTokenMetadata(token) {
  state.tokenClaims = decodeJwtClaims(token);
  state.tokenBbox25832 = null;
  state.tokenProfileLayers = null;
  state.tokenGeoModels = null;

  if (!state.tokenClaims) return;

  state.tokenProfileLayers = parseCsvClaimToList(state.tokenClaims["GAL.ProfileLayers"]);
  state.tokenGeoModels = parseCsvClaimToList(state.tokenClaims["GAL.GeoModels"]);

  const bboxRaw = state.tokenClaims["GAL.BoundingBox"];
  const bbox = parseBoundingBoxClaim(bboxRaw);
  if (!bbox) return;
  state.tokenBbox25832 = bbox;
}

function drawTokenBboxOnMap() {
  if (!state.map) return;
  if (state.bboxLayer) {
    state.map.removeLayer(state.bboxLayer);
    state.bboxLayer = null;
  }
  if (!state.tokenBbox25832) return;

  const b = state.tokenBbox25832;
  const sw = xy25832ToLonLat(b.xmin, b.ymin); // [lon, lat]
  const ne = xy25832ToLonLat(b.xmax, b.ymax);

  state.bboxLayer = L.rectangle(
    [
      [sw[1], sw[0]],
      [ne[1], ne[0]],
    ],
    { color: "#ef4444", weight: 2, fill: false, dashArray: "4 4" }
  ).addTo(state.map);
}

function lineIsInsideTokenBbox25832(path25832) {
  if (!state.tokenBbox25832) return true;
  const b = state.tokenBbox25832;
  return path25832.some(([x, y]) => x >= b.xmin && x <= b.xmax && y >= b.ymin && y <= b.ymax);
}

function getCurrentPath25832() {
  if (!state.lineCoords || state.lineCoords.length < 2) return null;
  const path25832 = state.lineCoords.map(([lon, lat]) => {
    const [x, y] = lonLatTo25832(lon, lat);
    return [Number(x.toFixed(3)), Number(y.toFixed(3))];
  });
  return path25832;
}

function setModelChoiceOptions(models) {
  const select = byId("model-choice");
  select.innerHTML = "";

  const empty = document.createElement("option");
  empty.value = "";
  empty.textContent = "(none)";
  select.appendChild(empty);

  for (const model of models) {
    const id = model?.ID ?? model?.Id;
    const name = model?.Name ?? `Model ${id}`;
    if (id === undefined || id === null) continue;
    const opt = document.createElement("option");
    opt.value = String(id);
    opt.textContent = `${id} - ${name}`;
    select.appendChild(opt);
  }
}

function initMap() {
  const map = L.map("map").setView([56.65, 9.10], 8);
  state.map = map;

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: "&copy; OpenStreetMap contributors",
  }).addTo(map);

  const drawnItems = new L.FeatureGroup();
  map.addLayer(drawnItems);

  const drawControl = new L.Control.Draw({
    draw: {
      polygon: false,
      rectangle: false,
      circle: false,
      circlemarker: false,
      marker: false,
      polyline: true,
    },
    edit: {
      featureGroup: drawnItems,
      remove: true,
    },
  });
  map.addControl(drawControl);

  // CSS animations/layout shifts can cause Leaflet to mis-measure initial size.
  setTimeout(() => {
    try {
      map.invalidateSize();
    } catch (_err) {
      // ignore
    }
  }, 220);

  function updateLineFromLayer(layer) {
    const latLngs = layer.getLatLngs();
    if (!latLngs || latLngs.length < 2) {
      state.lineCoords = null;
      state.lastPath25832 = null;
      state.pathModels = [];
      setModelChoiceOptions([]);
      return;
    }
    // API expects [x, y]. For EPSG:4326 that is [lon, lat].
    state.lineCoords = latLngs.map((ll) => [Number(ll.lng.toFixed(6)), Number(ll.lat.toFixed(6))]);
    try {
      state.lastPath25832 = getCurrentPath25832();
    } catch (_err) {
      state.lastPath25832 = null;
    }
    state.pathModels = [];
    setModelChoiceOptions([]);
    setStatus(`Line updated: ${state.lineCoords.length} points`, "ok");
  }

  map.on(L.Draw.Event.CREATED, (evt) => {
    if (state.lineLayer) {
      drawnItems.removeLayer(state.lineLayer);
    }
    state.lineLayer = evt.layer;
    drawnItems.addLayer(state.lineLayer);
    updateLineFromLayer(state.lineLayer);
  });

  map.on(L.Draw.Event.EDITED, () => {
    if (state.lineLayer) {
      updateLineFromLayer(state.lineLayer);
    }
  });

  map.on(L.Draw.Event.DELETED, () => {
    state.lineLayer = null;
    state.lineCoords = null;
    state.lastPath25832 = null;
    state.pathModels = [];
    setModelChoiceOptions([]);
    setStatus("Line removed. Draw a new line.", "info");
  });
}

async function postJSON(url, payload) {
  const response = await fetch(`${API_BASE}${url}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  let data = null;
  try {
    data = await response.json();
  } catch (err) {
    data = { error: `Invalid JSON response: ${err}` };
  }

  if (!response.ok) {
    const message = data && data.error ? data.error : `HTTP ${response.status}`;
    const detail = data && data.detail ? String(data.detail).replace(/\s+/g, " ").trim() : "";
    throw new Error(detail ? `${message} | ${detail}` : message);
  }
  return data;
}

async function getModelsForPath(token, path, geoareaid, apiMajorVersion) {
  const data = await postJSON("/api/geomodels_for_path", {
    token,
    path,
    geoareaid,
    api_major_version: apiMajorVersion,
  });
  if (!data || !Array.isArray(data.models)) return [];
  return data.models;
}

function readRequestParams() {
  const widthRaw = byId("width").value.trim();
  return {
    geoareaid: Number(byId("geoareaid").value || 1),
    srid: Number(byId("srid").value || 4326),
    api_major_version: Number(byId("api-major-version").value || 3),
    api_version: byId("api-version").value.trim(),
    linepointdistance: Number(byId("linepointdistance").value || 10),
    maxdepth: Number(byId("maxdepth").value || -40),
    xresolution: Number(byId("xresolution").value || 2),
    height: Number(byId("height").value || 320),
    width: widthRaw ? Number(widthRaw) : 1000,
    geomodelid: byId("geomodelid").value.trim(),
    auto_linepointdistance: byId("auto-linepointdistance").checked,
    auto_select_model: byId("auto-select-model").checked,
  };
}

function extractModelTextFromSvg(svgText) {
  if (!svgText || typeof svgText !== "string") return "";
  const marker = "Model:";
  const idx = svgText.indexOf(marker);
  if (idx < 0) return "";
  const tail = svgText.slice(idx + marker.length);
  const end = tail.indexOf("</text>");
  return (end < 0 ? tail : tail.slice(0, end)).trim();
}

function computePathLength(path) {
  if (!Array.isArray(path) || path.length < 2) return 0;
  let sum = 0;
  for (let i = 1; i < path.length; i += 1) {
    const [x1, y1] = path[i - 1];
    const [x2, y2] = path[i];
    sum += Math.hypot(x2 - x1, y2 - y1);
  }
  return sum;
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function getSvgStats(svgText) {
  const text = typeof svgText === "string" ? svgText : "";
  return {
    polygons: (text.match(/<polygon\b/gi) || []).length,
    polylines: (text.match(/<polyline\b/gi) || []).length,
    geounitClassRefs: (text.match(/class=['"]geounit-\d+/gi) || []).length,
    geoenhedClassRefs: (text.match(/class=['"]geoenhed-\d+/gi) || []).length,
  };
}

function normalizeSvgForDisplay(svgText, layout) {
  if (!svgText || typeof svgText !== "string") return "";

  const widthFromSvg = Number((svgText.match(/<svg[^>]*\bwidth=['"]?([0-9.]+)/i) || [])[1] || 0);
  const heightFromSvg = Number((svgText.match(/<svg[^>]*\bheight=['"]?([0-9.]+)/i) || [])[1] || 0);
  const width = Number(layout?.Width || 0) || widthFromSvg || 1000;
  const height = Number(layout?.Height || 0) || heightFromSvg || 320;

  let out = svgText.replace(/-webkit-font-smoothing:\s*antialiased;?/gi, "");
  if (!/\bviewBox\s*=/.test(out)) {
    out = out.replace(
      /<svg\b/i,
      `<svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="xMinYMin meet"`
    );
  } else if (!/\bpreserveAspectRatio\s*=/.test(out)) {
    out = out.replace(/<svg\b/i, "<svg preserveAspectRatio=\"xMinYMin meet\"");
  }
  return out;
}

function applySvgDisplayMode(svgEl, data) {
  if (!svgEl) return;
  const targetHeight = Math.max(260, Number(data?.SvgLayout?.Height || 320));
  if (state.svgFitMode) {
    svgEl.style.width = "100%";
    svgEl.style.height = "auto";
    svgEl.style.maxWidth = "100%";
    svgEl.style.maxHeight = "none";
  } else {
    svgEl.style.width = "auto";
    svgEl.style.height = `${targetHeight}px`;
    svgEl.style.maxWidth = "none";
    svgEl.style.maxHeight = "none";
  }
  svgEl.style.display = "block";
}

function setSvgFitMode(fit) {
  state.svgFitMode = !!fit;
  const fitBtn = byId("svg-fit-btn");
  const actualBtn = byId("svg-actual-btn");
  if (fitBtn) fitBtn.classList.toggle("is-active", state.svgFitMode);
  if (actualBtn) actualBtn.classList.toggle("is-active", !state.svgFitMode);

  const svgEl = byId("svg-container")?.querySelector?.("svg");
  if (svgEl) applySvgDisplayMode(svgEl, state.lastResponse);
}

function extractGeoUnitColorsFromSvg(svgText) {
  const colors = new Map();
  if (!svgText || typeof svgText !== "string") return colors;

  const regexes = [
    /\.geounit-(\d+)\s*\{[^}]*fill:\s*([^;}\n]+)[^}]*\}/gi,
    /\.geoenhed-(\d+)\s*\{[^}]*fill:\s*([^;}\n]+)[^}]*\}/gi,
  ];
  for (const re of regexes) {
    let match = re.exec(svgText);
    while (match) {
      colors.set(String(match[1]), String(match[2]).trim());
      match = re.exec(svgText);
    }
  }
  return colors;
}

function buildGeoUnitLegend(model, svgText) {
  if (!model || !Array.isArray(model.GeoUnits) || model.GeoUnits.length === 0) return "";
  const colorMap = extractGeoUnitColorsFromSvg(svgText);
  const items = model.GeoUnits
    .map((unit) => {
      const id = escapeHtml(unit.Id);
      const name = escapeHtml(unit.Name || `Unit ${unit.Id}`);
      const color = colorMap.get(String(unit.Id));
      const style = color ? ` style="background:${escapeHtml(color)};border-color:${escapeHtml(color)};"` : "";
      return `<li><span class="legend-swatch"${style}></span><span>${name}</span></li>`;
    })
    .join("");
  return `<div class="legend-block"><strong>GeoUnits</strong><ul>${items}</ul></div>`;
}

function hasGeology(data) {
  const stats = getSvgStats(data?.Svg || "");
  if (stats.polygons > 0 && stats.geounitClassRefs + stats.geoenhedClassRefs > 0) return true;

  const profileLayersCount = Array.isArray(data?.ProfileLayers) ? data.ProfileLayers.length : 0;
  if (profileLayersCount > 0) return true;
  if (data?.Model && data.Model.Name) {
    const modelName = String(data.Model.Name).toLowerCase();
    if (!modelName.includes("dhm") && !modelName.includes("terr")) return true;
  }
  const modelText = extractModelTextFromSvg(data?.Svg || "");
  const mt = modelText.toLowerCase();
  if (mt && !mt.includes("dhm") && !mt.includes("terr")) return true;
  return false;
}

function renderResult(data) {
  state.lastResponse = data;
  const profileLayers = Array.isArray(data.ProfileLayers) ? data.ProfileLayers.length : 0;
  const modelName = data.Model && data.Model.Name ? data.Model.Name : "N/A";
  const normalizedSvg = normalizeSvgForDisplay(data.Svg || "", data.SvgLayout || null);
  const modelText = extractModelTextFromSvg(normalizedSvg || "");
  const effectiveGeomodelId = data.__meta && data.__meta.geomodelid ? data.__meta.geomodelid : "auto";
  const tries = data.__meta && data.__meta.tries ? data.__meta.tries : 1;
  const svgStats = getSvgStats(normalizedSvg);
  const pathLengthMeters = data?.__meta?.pathLengthMeters ?? data.PathLength;
  const linePointDistance = data?.__meta?.linepointdistance ?? "N/A";

  byId("summary").innerHTML = `
    <div class="kpis">
      <div class="kpi"><div class="k">Model</div><div class="v">${escapeHtml(modelName)}</div></div>
      <div class="kpi"><div class="k">Model Text</div><div class="v">${escapeHtml(modelText || "N/A")}</div></div>
      <div class="kpi"><div class="k">GeoModelId</div><div class="v">${escapeHtml(effectiveGeomodelId)}</div></div>

      <div class="kpi"><div class="k">Attempts</div><div class="v">${escapeHtml(tries)}</div></div>
      <div class="kpi"><div class="k">Length (m)</div><div class="v">${escapeHtml(pathLengthMeters ?? "N/A")}</div></div>
      <div class="kpi"><div class="k">LinePointDistance</div><div class="v">${escapeHtml(linePointDistance)}</div></div>

      <div class="kpi"><div class="k">Z range</div><div class="v">${escapeHtml(`${data.ZMin ?? "?"} to ${data.ZMax ?? "?"}`)}</div></div>
      <div class="kpi"><div class="k">ProfileLayers</div><div class="v">${escapeHtml(profileLayers)}</div></div>
      <div class="kpi"><div class="k">SVG polygons</div><div class="v">${escapeHtml(svgStats.polygons)}</div></div>
      <div class="kpi"><div class="k">SVG polylines</div><div class="v">${escapeHtml(svgStats.polylines)}</div></div>
    </div>
  `;
  const legendEl = byId("legend-container");
  if (legendEl) {
    legendEl.innerHTML = buildGeoUnitLegend(data.Model, normalizedSvg);
  }

  byId("svg-container").innerHTML = normalizedSvg || "<p>No SVG returned.</p>";
  const svgEl = byId("svg-container").querySelector("svg");
  if (svgEl) {
    applySvgDisplayMode(svgEl, data);
  }
  byId("raw-json").textContent = JSON.stringify(data, null, 2);

  if (!hasGeology(data)) {
    if (svgStats.polygons === 0) {
      setStatus(
        "Cross section loaded, but API SVG has no geology polygons (surface-only). Try another line/model and compare with QGIS request settings.",
        "info"
      );
    } else if (state.tokenProfileLayers && state.tokenProfileLayers.length === 0) {
      setStatus(
        "Request succeeded, but token claim GAL.ProfileLayers is empty and response is terrain-only. QGIS may still use other data paths; API crosssection here has no geology layers.",
        "info"
      );
    } else {
      setStatus(
        "Request succeeded, but response is terrain-only. Try explicit GeoModelId or compare exact QGIS crosssection request parameters.",
        "info"
      );
    }
  } else {
    setStatus("Cross section loaded.", "ok");
  }
}

async function onGetToken() {
  setStatus("Requesting token...", "info");
  const username = byId("username").value.trim();
  const password = byId("password").value;
  const role = byId("role").value.trim();
  try {
    const data = await postJSON("/api/token", { username, password, role });
    const normalizedToken = normalizeTokenInput(data.token || "");
    byId("token").value = normalizedToken;
    setTokenMetadata(normalizedToken);
    drawTokenBboxOnMap();
    if (!byId("geomodelid").value && Array.isArray(state.tokenGeoModels) && state.tokenGeoModels.length > 0) {
      byId("geomodelid").placeholder = `e.g. ${state.tokenGeoModels[0]}`;
    }
    if (state.tokenBbox25832) {
      const b = state.tokenBbox25832;
      const profileLayerInfo =
        state.tokenProfileLayers === null
          ? "ProfileLayers: n/a"
          : `ProfileLayers: ${state.tokenProfileLayers.length}`;
      const geoModelInfo =
        state.tokenGeoModels === null ? "GeoModels: n/a" : `GeoModels: ${state.tokenGeoModels.join(",")}`;
      setStatus(
        `Token received. Allowed bbox (EPSG:${b.epsg || 25832}): ${b.xmin},${b.ymin} to ${b.xmax},${b.ymax}. ${profileLayerInfo}. ${geoModelInfo}`,
        state.tokenProfileLayers && state.tokenProfileLayers.length === 0 ? "info" : "ok"
      );
    } else {
      setStatus("Token received.", "ok");
    }
  } catch (err) {
    setStatus(`Token request failed: ${err.message}`, "error");
  }
}

async function onLoadModelsForLine() {
  const token = normalizeTokenInput(byId("token").value);
  byId("token").value = token;
  if (!token) {
    setStatus("Missing token. Fetch or paste token first.", "error");
    return;
  }
  if (!state.lineCoords || state.lineCoords.length < 2) {
    setStatus("Draw a line with at least 2 points.", "error");
    return;
  }

  const params = readRequestParams();
  let path25832 = null;
  try {
    path25832 = getCurrentPath25832();
    state.lastPath25832 = path25832;
  } catch (err) {
    setStatus(`Projection failed: ${err.message}`, "error");
    return;
  }
  if (!path25832 || path25832.length < 2) {
    setStatus("Could not build a valid projected path.", "error");
    return;
  }
  if (!lineIsInsideTokenBbox25832(path25832)) {
    setStatus(
      "Line is outside your token's allowed bbox (GAL.BoundingBox). Move line inside the red rectangle.",
      "error"
    );
    return;
  }

  setStatus("Loading models for current line...", "info");
  try {
    const models = await getModelsForPath(token, path25832, params.geoareaid, params.api_major_version);
    state.pathModels = Array.isArray(models) ? models : [];
    setModelChoiceOptions(state.pathModels);

    const first = state.pathModels.find((m) => Number(m?.ID ?? m?.Id) > 0);
    if (first) {
      const firstId = String(first.ID ?? first.Id);
      byId("model-choice").value = firstId;
      if (!byId("geomodelid").value.trim()) {
        byId("geomodelid").value = firstId;
      }
    }
    setStatus(`Loaded ${state.pathModels.length} model candidates for this line.`, "ok");
  } catch (err) {
    setStatus(`Model lookup failed: ${err.message}`, "error");
  }
}

async function onRequestCrossSection() {
  const token = normalizeTokenInput(byId("token").value);
  byId("token").value = token;
  if (!token) {
    setStatus("Missing token. Fetch or paste token first.", "error");
    return;
  }
  if (!state.lineCoords || state.lineCoords.length < 2) {
    setStatus("Draw a line with at least 2 points.", "error");
    return;
  }

  const params = readRequestParams();
  // Leaflet provides lon/lat; convert to UTM32 for geo.dk crosssection.
  let path25832 = null;
  try {
    path25832 = state.lineCoords.map(([lon, lat]) => {
      const [x, y] = lonLatTo25832(lon, lat);
      return [Number(x.toFixed(3)), Number(y.toFixed(3))];
    });
  } catch (err) {
    setStatus(`Projection failed: ${err.message}`, "error");
    return;
  }

  if (!lineIsInsideTokenBbox25832(path25832)) {
    setStatus(
      "Line is outside your token's allowed bbox (GAL.BoundingBox). Move line inside the red rectangle.",
      "error"
    );
    return;
  }

  const pathLengthMeters = computePathLength(path25832);
  const widthForRequest = Number.isFinite(params.width) && params.width > 0 ? Math.round(params.width) : 1000;
  const autoLinePointDistance = Math.max(1, Math.ceil(pathLengthMeters / widthForRequest));
  const linepointdistance = params.auto_linepointdistance
    ? autoLinePointDistance
    : Math.max(1, Number(params.linepointdistance || 10));

  const userGeomodel = params.geomodelid ? String(params.geomodelid).trim() : "";
  const selectedGeomodel = byId("model-choice").value.trim();
  let initialGeomodel = userGeomodel;
  if (!initialGeomodel && selectedGeomodel) {
    initialGeomodel = selectedGeomodel;
  }
  if (!initialGeomodel && params.auto_select_model) {
    try {
      const models = await getModelsForPath(token, path25832, params.geoareaid, params.api_major_version);
      const firstFromPath = models.find((m) => Number(m?.ID) > 0);
      if (firstFromPath) {
        initialGeomodel = String(firstFromPath.ID);
      }
    } catch (_err) {
      // Fallback below if model lookup endpoint fails.
    }
  }
  if (!initialGeomodel && params.auto_select_model && Array.isArray(state.tokenGeoModels)) {
    const firstFromToken = state.tokenGeoModels
      .map((v) => Number(v))
      .find((v) => Number.isFinite(v) && v > 0);
    if (firstFromToken) initialGeomodel = String(firstFromToken);
  }

  const basePayload = {
    token,
    path: path25832,
    ...params,
    width: widthForRequest,
    linepointdistance,
    srid: 25832,
  };
  delete basePayload.auto_linepointdistance;
  delete basePayload.auto_select_model;
  if (!initialGeomodel) {
    delete basePayload.geomodelid;
  }

  setStatus("Requesting cross section...", "info");
  try {
    const tries = [];

    async function tryRequest(extra = {}) {
      const payload = { ...basePayload, ...extra };
      const data = await postJSON("/api/crosssection", payload);
      tries.push({ geomodelid: payload.geomodelid || null, data });
      return data;
    }

    let selectedData = await tryRequest(initialGeomodel ? { geomodelid: initialGeomodel } : {});
    let selectedGeomodel = initialGeomodel || null;

    const autoTryModels = byId("auto-try-models").checked;
    if (!hasGeology(selectedData) && autoTryModels && !userGeomodel && Array.isArray(state.tokenGeoModels)) {
      const candidates = state.tokenGeoModels
        .map((v) => Number(v))
        .filter((v) => Number.isFinite(v) && v > 0)
        .filter((v) => String(v) !== String(selectedGeomodel || ""));

      for (const mid of candidates) {
        try {
          const d = await tryRequest({ geomodelid: mid });
          if (hasGeology(d)) {
            selectedData = d;
            selectedGeomodel = String(mid);
            break;
          }
        } catch (_err) {
          // Keep trying next model id.
        }
      }
    }

    selectedData.__meta = {
      geomodelid: selectedGeomodel,
      tries: tries.length,
      pathLengthMeters: Number(pathLengthMeters.toFixed(2)),
      linepointdistance,
    };
    renderResult(selectedData);
  } catch (err) {
    setStatus(`Cross section request failed: ${err.message}`, "error");
  }
}

function wireUI() {
  byId("get-token-btn").addEventListener("click", onGetToken);
  byId("load-models-btn").addEventListener("click", onLoadModelsForLine);
  byId("model-choice").addEventListener("change", (evt) => {
    const value = String(evt.target.value || "").trim();
    byId("geomodelid").value = value;
  });
  byId("request-btn").addEventListener("click", onRequestCrossSection);

  const fitBtn = byId("svg-fit-btn");
  const actualBtn = byId("svg-actual-btn");
  if (fitBtn) fitBtn.addEventListener("click", () => setSvgFitMode(true));
  if (actualBtn) actualBtn.addEventListener("click", () => setSvgFitMode(false));

  const toggleJsonBtn = byId("toggle-json-btn");
  if (toggleJsonBtn) {
    toggleJsonBtn.addEventListener("click", () => {
      const details = byId("raw-json-details");
      if (!details) return;
      details.open = !details.open;
      if (details.open) {
        try {
          details.scrollIntoView({ behavior: "smooth", block: "start" });
        } catch (_err) {
          // Ignore if browser doesn't support smooth scrolling options.
        }
      }
    });
  }

  // Depth preset buttons.
  for (const btn of Array.from(document.querySelectorAll("button[data-depth]"))) {
    btn.addEventListener("click", (evt) => {
      const value = String(evt.currentTarget.getAttribute("data-depth") || "").trim();
      if (!value) return;
      byId("maxdepth").value = value;
      for (const b of Array.from(document.querySelectorAll("button[data-depth]"))) {
        b.classList.toggle("is-active", b === evt.currentTarget);
      }
    });
  }
}

window.addEventListener("DOMContentLoaded", () => {
  initMap();
  wireUI();
  if (window.location.protocol === "file:") {
    setStatus("Running from file://. Using API base http://127.0.0.1:8765", "info");
  }
});
