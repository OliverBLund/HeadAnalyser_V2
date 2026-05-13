from __future__ import annotations

import base64
import json

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWebChannel import QWebChannel
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtWidgets import QWidget, QVBoxLayout

from ui.map.bridge import MapBridge


_GEODK_PANEL_HTML = r"""<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
    :root{
      --bg:#0f1116; --panel:#171a22; --panel2:#1d2130;
      --text:#e7e9ee; --muted:#aab0bf; --border:#2a2f41;
      --accent:#60a5fa; --err:#fb7185; --ok:#34d399;
      --mono: ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace;
    }
    body{margin:0;background:var(--bg);color:var(--text);font:12px/1.4 system-ui,-apple-system,Segoe UI,Roboto,Ubuntu,"Helvetica Neue",Arial;}
    .geology-panel{height:100vh;display:flex;flex-direction:column;background:var(--panel);border:1px solid var(--border);}
    .geology-header{display:flex;gap:10px;align-items:center;padding:10px 12px;border-bottom:1px solid var(--border);background:var(--panel2);}
    .geology-title{font-weight:700;letter-spacing:.02em;}
    .geology-info{color:var(--muted);flex:1;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
    .geology-status-pill{display:inline-flex;align-items:center;gap:8px;border:1px solid var(--border);padding:4px 8px;border-radius:999px;color:var(--muted);}
    .geology-status-pill .dot{width:7px;height:7px;border-radius:50%;background:var(--muted);}
    .geology-content{flex:1;display:grid;grid-template-columns: 1fr 360px;min-height:0;}
    .geology-view{display:flex;flex-direction:column;min-width:0;border-right:1px solid var(--border);}
    .geology-view-toolbar{display:flex;align-items:center;gap:10px;padding:8px 10px;border-bottom:1px solid var(--border);}
    .seg{display:inline-flex;border:1px solid var(--border);border-radius:10px;overflow:hidden;}
    .seg button{border:0;background:transparent;color:var(--muted);padding:6px 10px;font-weight:700;cursor:pointer;}
    .seg button.active{background:rgba(96,165,250,.18);color:var(--text);}
    .geology-mini{display:flex;align-items:center;gap:8px;color:var(--muted);font-weight:700;}
    .geology-mini input{width:160px;}
    .mono{font-family:var(--mono);}
    .spacer{flex:1;}
    .geology-action{border:1px solid var(--border);background:transparent;color:var(--text);padding:6px 10px;border-radius:10px;font-weight:700;cursor:pointer;}
    .geology-action:disabled{opacity:.5;cursor:default;}
    .geology-viewport{position:relative;flex:1;min-height:0;background:#0b0d12;}
    #geologySvgImg{position:absolute;inset:0;margin:auto;max-width:100%;max-height:100%;transform-origin:center center;object-fit:contain;}
    #geologyOverlaySvg{position:absolute;inset:0;pointer-events:none;}
    .geology-empty,.geology-loading{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;color:var(--muted);padding:12px;text-align:center;}
    .geology-loading{display:none;}
    .geology-metrics{display:grid;grid-template-columns: repeat(5, 1fr);gap:8px;padding:8px 10px;border-top:1px solid var(--border);}
    .geo-metric{border:1px solid var(--border);border-radius:10px;padding:6px 8px;background:rgba(255,255,255,.02);}
    .geo-metric .k{color:var(--muted);font-weight:800;font-size:10px;}
    .geo-metric .v{font-weight:800;}
    .geology-side{display:flex;flex-direction:column;min-width:0;min-height:0;}
    .geology-side-tabs{display:flex;border-bottom:1px solid var(--border);}
    .geo-tab{flex:1;border:0;background:transparent;color:var(--muted);padding:10px 8px;font-weight:900;cursor:pointer;}
    .geo-tab.active{color:var(--text);background:rgba(255,255,255,.03);}
    .geo-tabpanel{display:none;flex:1;min-height:0;overflow:auto;padding:10px;}
    .geo-tabpanel.active{display:block;}
    .geodk-help{color:var(--muted);font-size:11px;margin-bottom:10px;}
    .geodk-row{display:flex;gap:10px;align-items:center;margin:8px 0;}
    .geodk-row .lbl{width:76px;color:var(--muted);font-weight:900;font-size:10px;text-transform:uppercase;letter-spacing:.06em;}
    .geodk-row .ctl{flex:1;min-width:0;}
    .geodk-inline{display:flex;align-items:center;gap:10px;}
    .geodk-input,.geodk-select{width:100%;box-sizing:border-box;border:1px solid var(--border);background:#0b0d12;color:var(--text);padding:8px 10px;border-radius:10px;font-weight:800;}
    .geodk-actions{display:flex;gap:10px;margin-top:10px;}
    .geodk-btn{border:1px solid var(--border);background:transparent;color:var(--text);padding:8px 10px;border-radius:10px;font-weight:900;cursor:pointer;}
    .geodk-btn.primary{background:rgba(96,165,250,.18);border-color:rgba(96,165,250,.35);}
    .geodk-status{border:1px dashed var(--border);border-radius:10px;padding:10px;color:var(--muted);margin-top:10px;}
    .geology-legend-title{color:var(--muted);font-weight:900;margin-bottom:8px;}
    .geology-legend-item{display:flex;align-items:center;gap:10px;padding:6px 0;border-bottom:1px solid rgba(255,255,255,.04);}
    .geology-legend-color{width:14px;height:14px;border-radius:4px;border:1px solid var(--border);background:#666;}
    .geology-legend-text{flex:1;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
    .geology-legend-code{font-family:var(--mono);color:var(--muted);font-weight:900;}
    .geodk-diag pre, #geodkDiagPre{white-space:pre-wrap;word-break:break-word;font-family:var(--mono);font-size:10px;color:#d7dbe6;}

    /* Borehole overlay classes (match map panel runtime expectations) */
    .bh-line{stroke:#000;stroke-width:1.1;opacity:.85}
    .bh-screen{stroke:#000;stroke-width:2.8;opacity:.92}
    .bh-cap{stroke:#000;stroke-width:2.2;opacity:.9}
    .bh-label{fill:#000;font-size:10px;font-family:var(--mono);font-weight:900;paint-order:stroke;stroke:#fff;stroke-width:2px;stroke-linejoin:round;opacity:.92}
  </style>
  <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
</head>
<body>
  <div class="geology-panel" id="geologyPanel" data-state="idle">
    <div class="geology-header">
      <div class="geology-title">Geology Cross-Section (Geo.dk)</div>
      <span class="geology-info" id="geologyInfo">Draw a line to request a Geo.dk cross-section.</span>
      <span class="geology-status-pill" id="geoStatusPill"><span class="dot"></span><span id="geoStatusText">Idle</span></span>
      <button class="geology-action" onclick="if(window.__haGeoDK && window.__haGeoDK.fetchFromPanel) window.__haGeoDK.fetchFromPanel();">Fetch</button>
      <button class="geology-action" onclick="if(window.__haGeoDK && window.__haGeoDK.onDownload) window.__haGeoDK.onDownload();">Download</button>
      <button class="geology-action" onclick="if(window.__haGeoDK && window.__haGeoDK.onCopyRepro) window.__haGeoDK.onCopyRepro();">Copy Repro</button>
    </div>
    <div class="geology-content">
      <div class="geology-view">
        <div class="geology-view-toolbar">
          <div class="seg" role="group" aria-label="Cross-section view mode">
            <button class="active" id="geoFitBtn" onclick="if(window.__haGeoDK && window.__haGeoDK.setViewMode) window.__haGeoDK.setViewMode('fit');">Fit</button>
            <button id="geo11Btn" onclick="if(window.__haGeoDK && window.__haGeoDK.setViewMode) window.__haGeoDK.setViewMode('11');">1:1</button>
          </div>
          <div class="geology-mini">
            <span>Zoom</span>
            <input type="range" min="60" max="180" value="100" id="geoZoomRange" oninput="if(window.__haGeoDK && window.__haGeoDK.setZoom) window.__haGeoDK.setZoom(this.value);" />
            <span class="mono" id="geoZoomVal">100%</span>
          </div>
          <div class="spacer"></div>
        </div>
        <div class="geology-viewport">
          <img id="geologySvgImg" alt="Geo.dk cross section" />
          <svg id="geologyOverlaySvg" class="geology-overlay" aria-hidden="true"></svg>
          <div class="geology-empty" id="geoEmpty">Draw a line to request a Geo.dk cross-section.</div>
          <div class="geology-loading" id="geoLoading">Requesting Geo.dk cross-section...</div>
        </div>
        <div class="geology-metrics">
          <div class="geo-metric"><div class="k">Model</div><div class="v" id="geoMetricModel">-</div></div>
          <div class="geo-metric"><div class="k">Depth</div><div class="v" id="geoMetricDepth">-</div></div>
          <div class="geo-metric"><div class="k">Polygons</div><div class="v" id="geoMetricPoly">-</div></div>
          <div class="geo-metric"><div class="k">Path</div><div class="v" id="geoMetricPath">-</div></div>
          <div class="geo-metric"><div class="k">Cache</div><div class="v" id="geoMetricCache">-</div></div>
        </div>
      </div>
      <div class="geology-side">
        <div class="geology-side-tabs">
          <button class="geo-tab active" data-tab="request" onclick="if(window.__haGeoDK && window.__haGeoDK.setTab) window.__haGeoDK.setTab('request');">Request</button>
          <button class="geo-tab" data-tab="legend" onclick="if(window.__haGeoDK && window.__haGeoDK.setTab) window.__haGeoDK.setTab('legend');">Legend</button>
          <button class="geo-tab" data-tab="diag" onclick="if(window.__haGeoDK && window.__haGeoDK.setTab) window.__haGeoDK.setTab('diag');">Diagnostics</button>
        </div>
        <div class="geo-tabpanel active" data-tabpanel="request">
          <div class="geodk-form">
            <div class="geodk-help">
              Same request controls as the map Geo.dk panel. Draw/adjust the line to update the path, then Fetch.
            </div>
            <div class="geodk-row">
              <div class="lbl">Model</div>
              <div class="ctl">
                <input class="geodk-input" id="geodkModelFilter" placeholder="Filter models..." oninput="if(window.__haGeoDK && window.__haGeoDK.filterModels) window.__haGeoDK.filterModels(this.value);" />
              </div>
            </div>
            <div class="geodk-row">
              <div class="lbl">GeoModel</div>
              <div class="ctl">
                <select class="geodk-select" id="geodkModelSelect" onchange="if(window.__haGeoDK && window.__haGeoDK.onModelChanged) window.__haGeoDK.onModelChanged(this.value);"></select>
              </div>
            </div>
            <div class="geodk-row">
              <div class="lbl">Depth</div>
              <div class="ctl geodk-inline">
                <input id="geodkDepthRange" type="range" min="-200" max="200" value="-40" oninput="if(window.__haGeoDK && window.__haGeoDK.setDepth) window.__haGeoDK.setDepth(this.value);" />
                <input class="geodk-input" style="width: 92px;" type="number" min="-200" max="200" value="-40" id="geodkDepthInput" oninput="if(window.__haGeoDK && window.__haGeoDK.setDepth) window.__haGeoDK.setDepth(this.value);" />
              </div>
            </div>
            <div class="geodk-row">
              <div class="lbl">Size</div>
              <div class="ctl geodk-inline">
                <input class="geodk-input" style="width: 110px;" type="number" min="200" max="4000" value="1000" id="geodkWidthInput" />
                <span style="color: var(--muted); font-weight: 900;">×</span>
                <input class="geodk-input" style="width: 110px;" type="number" min="120" max="2000" value="320" id="geodkHeightInput" />
              </div>
            </div>
            <div class="geodk-row">
              <div class="lbl">Sampling</div>
              <div class="ctl geodk-inline">
                <label style="display:flex;align-items:center;gap:8px;color:var(--muted);font-size:10px;font-weight:900;">
                  <input id="geodkAutoLpdCheck" type="checkbox" checked />
                  Auto LPD
                </label>
                <input class="geodk-input" style="width: 92px;" type="number" min="1" max="10000" value="2" id="geodkLpdInput" />
              </div>
            </div>
            <div class="geodk-row">
              <div class="lbl">Boreholes</div>
              <div class="ctl geodk-inline">
                <span style="color: var(--muted); font-weight: 900;">Tol (m)</span>
                <input class="geodk-input" style="width: 92px;" type="number" min="0" max="500" value="10" id="geodkBoreTolInput" />
              </div>
            </div>
            <div class="geodk-actions">
              <button class="geodk-btn primary" id="geodkFetchBtn" onclick="if(window.__haGeoDK && window.__haGeoDK.fetchFromPanel) window.__haGeoDK.fetchFromPanel();">Fetch Cross-Section</button>
              <button class="geodk-btn" onclick="if(window.__haGeoDK && window.__haGeoDK.requestCredentials) window.__haGeoDK.requestCredentials();">Credentials</button>
            </div>
            <div class="geodk-status" id="geodkStatus">Draw a line, pick a model, adjust depth, then Fetch.</div>
          </div>
        </div>
        <div class="geo-tabpanel" data-tabpanel="legend">
          <div class="geology-legend" id="geodkLegend">
            <div class="geology-legend-title">GeoUnits</div>
            <div class="geology-legend-item"><span class="geology-legend-text">No legend loaded.</span></div>
          </div>
        </div>
        <div class="geo-tabpanel geodk-diag" data-tabpanel="diag">
          <div class="geodk-help">Diagnostics JSON (repro bundle is rotated).</div>
          <pre id="geodkDiagPre">{}</pre>
        </div>
      </div>
    </div>
  </div>

  <script>
    // QWebChannel hookup
    new QWebChannel(qt.webChannelTransport, function(channel){
      window.pyBridge = channel.objects.pyBridge;
    });

    window.__haGeoDK = window.__haGeoDK || (function(){
      var st = {
        models: [],
        geomodelid: null,
        maxdepth: -40,
        width: 1000,
        height: 320,
        auto_lpd: true,
        linepointdistance: 2,
        borehole_tolerance_m: 10,
        zoom_pct: 100,
        view_mode: 'fit',
        last_repro_path: ''
      };
      function _el(id){ return document.getElementById(id); }
      function _setText(id, txt){ try{ var e=_el(id); if(e) e.textContent=String(txt||''); }catch(err){} }
      function _setState(state, pillText, statusBox){
        try{
          var panel=_el('geologyPanel');
          if(panel) panel.setAttribute('data-state', String(state||'idle'));
          _setText('geoStatusText', pillText || '');
          if (statusBox !== undefined) _setText('geodkStatus', statusBox || '');
          var btn=_el('geodkFetchBtn');
          if(btn) btn.disabled = (String(state||'') === 'loading');
          var empty=_el('geoEmpty'); var load=_el('geoLoading');
          if(empty) empty.style.display = (String(state||'')==='idle' || String(state||'')==='error') ? 'flex' : 'none';
          if(load) load.style.display = (String(state||'')==='loading') ? 'flex' : 'none';
        }catch(err){}
      }
      function setTab(tab){
        try{
          var tabs = Array.prototype.slice.call(document.querySelectorAll('.geo-tab'));
          var panels = Array.prototype.slice.call(document.querySelectorAll('.geo-tabpanel'));
          tabs.forEach(function(t){ t.classList.toggle('active', String(t.getAttribute('data-tab')) === String(tab)); });
          panels.forEach(function(p){ p.classList.toggle('active', String(p.getAttribute('data-tabpanel')) === String(tab)); });
        }catch(err){}
      }
      function setViewMode(mode){
        st.view_mode = String(mode||'fit');
        try{
          var fitBtn=_el('geoFitBtn'); var oneBtn=_el('geo11Btn');
          if(fitBtn) fitBtn.classList.toggle('active', st.view_mode === 'fit');
          if(oneBtn) oneBtn.classList.toggle('active', st.view_mode === '11');
          var img=_el('geologySvgImg');
          if(img) img.style.objectFit = (st.view_mode === '11') ? 'none' : 'contain';
        }catch(err){}
      }
      function setZoom(v){
        try{
          var pct = Math.max(60, Math.min(180, Math.round(Number(v)||100)));
          st.zoom_pct = pct;
          _setText('geoZoomVal', String(pct) + '%');
          var img=_el('geologySvgImg');
          if(img) img.style.transform = 'scale(' + String(pct/100.0) + ')';
        }catch(err){}
      }
      function setDepth(v){
        var n = Math.max(-200, Math.min(200, Math.round(Number(v)||-40)));
        st.maxdepth = n;
        try{
          var inp=_el('geodkDepthInput'); if(inp) inp.value = String(n);
          var rng=_el('geodkDepthRange'); if(rng) rng.value = String(n);
          _setText('geoMetricDepth', String(n));
        }catch(err){}
      }
      function onModelChanged(v){
        try{
          var n = Number(v);
          st.geomodelid = isFinite(n) ? Math.round(n) : null;
          var sel=_el('geodkModelSelect');
          if(sel && sel.selectedOptions && sel.selectedOptions.length){
            _setText('geoMetricModel', sel.selectedOptions[0].textContent || '-');
          }
        }catch(err){}
      }
      function filterModels(q){
        try{
          var needle = String(q||'').trim().toLowerCase();
          var sel=_el('geodkModelSelect'); if(!sel) return;
          Array.prototype.slice.call(sel.options).forEach(function(opt){
            var txt = String(opt.textContent||'').toLowerCase();
            opt.hidden = needle ? (txt.indexOf(needle) === -1) : false;
          });
        }catch(err){}
      }
      function setModels(models, opts){
        try{
          var list = Array.isArray(models) ? models : [];
          st.models = list;
          var sel=_el('geodkModelSelect');
          if(sel){
            sel.innerHTML = '';
            list.forEach(function(m){
              try{
                var id = (m && (m.ID !== undefined)) ? m.ID : (m && (m.Id !== undefined)) ? m.Id : (m && (m.id !== undefined)) ? m.id : null;
                var name = (m && (m.Name !== undefined)) ? m.Name : (m && (m.name !== undefined)) ? m.name : '';
                if(id === null || id === undefined) return;
                var idStr = String(id);
                var optEl = document.createElement('option');
                optEl.value = idStr;
                optEl.textContent = String(name||'Model') + ' (ID ' + idStr + ')';
                sel.appendChild(optEl);
              }catch(err){}
            });
          }
          var desired = (opts && opts.geomodelid !== undefined && opts.geomodelid !== null) ? String(opts.geomodelid) : '';
          if(sel){
            if(desired) sel.value = desired;
            if(!sel.value && sel.options && sel.options.length){
              var picked = null;
              for(var i=0;i<sel.options.length;i++){
                if(String(sel.options[i].value) !== '-1'){ picked = sel.options[i].value; break; }
              }
              sel.value = picked || sel.options[0].value;
            }
          }
          onModelChanged(sel ? sel.value : null);
          if(opts && opts.maxdepth !== undefined && opts.maxdepth !== null) setDepth(opts.maxdepth);
          if(opts && opts.width !== undefined && opts.width !== null){ st.width = Math.round(Number(opts.width)||1000); var w=_el('geodkWidthInput'); if(w) w.value=String(st.width); }
          if(opts && opts.height !== undefined && opts.height !== null){ st.height = Math.round(Number(opts.height)||320); var h=_el('geodkHeightInput'); if(h) h.value=String(st.height); }
          if(opts && opts.borehole_tolerance_m !== undefined && opts.borehole_tolerance_m !== null){
            var t = Number(opts.borehole_tolerance_m);
            if(!isFinite(t) || t < 0) t = 10;
            st.borehole_tolerance_m = t;
            var bt=_el('geodkBoreTolInput'); if(bt) bt.value = String(t);
          }
          if(opts && opts.path_m !== undefined && opts.path_m !== null) _setText('geoMetricPath', String(Math.round(Number(opts.path_m)||0)) + ' m');
          if(opts && opts.cache_hit !== undefined && opts.cache_hit !== null) _setText('geoMetricCache', (opts.cache_hit ? 'HIT' : 'MISS'));
          _setState('ready', 'Ready', 'Models loaded. Adjust settings and click Fetch.');
        }catch(err){}
      }
      function setLegendHtml(html){
        try{ var el=_el('geodkLegend'); if(el) el.innerHTML = String(html||''); }catch(err){}
      }
      function setDiagJson(obj){
        try{ var pre=_el('geodkDiagPre'); if(pre) pre.textContent = JSON.stringify(obj || {}, null, 2); }catch(err){}
      }
      function setSvgDataUrl(dataUrl){
        try{
          var img=_el('geologySvgImg');
          if(img) img.src = String(dataUrl||'');
          var ov=_el('geologyOverlaySvg');
          if(ov) ov.innerHTML = '';
          _setState('ready', 'Ready');
        }catch(err){}
      }
      function setBoreholesOverlay(items, viewbox){
        try{
          var ov=_el('geologyOverlaySvg');
          if(!ov) return;
          var list = Array.isArray(items) ? items : [];
          var vb = (viewbox && typeof viewbox === 'object') ? viewbox : null;
          if(vb && isFinite(Number(vb.w)) && isFinite(Number(vb.h))){
            ov.setAttribute('viewBox', '0 0 ' + String(Number(vb.w)) + ' ' + String(Number(vb.h)));
            ov.setAttribute('preserveAspectRatio', 'xMinYMin meet');
          }
          ov.innerHTML = '';
          for(var i=0;i<list.length;i++){
            var it=list[i]||{};
            var x=Number(it.x), y1=Number(it.y1), y2=Number(it.y2);
            if(!isFinite(x) || !isFinite(y1) || !isFinite(y2)) continue;
            var label = (it.label !== undefined && it.label !== null) ? String(it.label) : '';
            var yTop = Math.min(y1,y2), yBot = Math.max(y1,y2);
            var ln = document.createElementNS('http://www.w3.org/2000/svg','line');
            ln.setAttribute('x1', String(x)); ln.setAttribute('x2', String(x));
            ln.setAttribute('y1', String(yTop)); ln.setAttribute('y2', String(yBot));
            ln.setAttribute('class','bh-line'); ov.appendChild(ln);
            if(it.screen && isFinite(Number(it.screen.y1)) && isFinite(Number(it.screen.y2))){
              var s1=Number(it.screen.y1), s2=Number(it.screen.y2);
              var sn = document.createElementNS('http://www.w3.org/2000/svg','line');
              sn.setAttribute('x1', String(x)); sn.setAttribute('x2', String(x));
              sn.setAttribute('y1', String(Math.min(s1,s2))); sn.setAttribute('y2', String(Math.max(s1,s2)));
              sn.setAttribute('class','bh-screen'); ov.appendChild(sn);
            }
            var cap = document.createElementNS('http://www.w3.org/2000/svg','line');
            cap.setAttribute('x1', String(x-3.5)); cap.setAttribute('x2', String(x+3.5));
            cap.setAttribute('y1', String(yTop)); cap.setAttribute('y2', String(yTop));
            cap.setAttribute('class','bh-cap'); ov.appendChild(cap);
            if(label){
              var tx = document.createElementNS('http://www.w3.org/2000/svg','text');
              tx.setAttribute('x', String(x+5));
              tx.setAttribute('y', String(Math.max(0, yTop-4)));
              tx.setAttribute('class','bh-label');
              tx.textContent = label;
              ov.appendChild(tx);
            }
          }
        }catch(err){}
      }
      function fetchFromPanel(){
        try{
          var sel=_el('geodkModelSelect');
          var depth=_el('geodkDepthInput');
          var w=_el('geodkWidthInput');
          var h=_el('geodkHeightInput');
          var auto=_el('geodkAutoLpdCheck');
          var lpd=_el('geodkLpdInput');
          var bt=_el('geodkBoreTolInput');
          var geomodelid = sel && sel.value ? Number(sel.value) : null;
          var maxdepth = depth ? Number(depth.value) : -40;
          var width = w ? Number(w.value) : 1000;
          var height = h ? Number(h.value) : 320;
          var auto_lpd = auto ? !!auto.checked : true;
          var linepointdistance = lpd ? Number(lpd.value) : 2;
          var borehole_tolerance_m = bt ? Number(bt.value) : 10;
          if(geomodelid === null || !isFinite(geomodelid)){
            _setState('error', 'Error', 'Pick a model first.');
            return;
          }
          if(!isFinite(maxdepth)) maxdepth = -40;
          if(!isFinite(width) || width<=0) width = 1000;
          if(!isFinite(height) || height<=0) height = 320;
          if(!isFinite(linepointdistance) || linepointdistance<=0) linepointdistance = 2;
          if(!isFinite(borehole_tolerance_m) || borehole_tolerance_m < 0) borehole_tolerance_m = 10;
          _setState('loading', 'Loading', 'Requesting Geo.dk cross-section...');
          if(window.pyBridge && window.pyBridge.onGeoDKFetchRequested){
            window.pyBridge.onGeoDKFetchRequested(JSON.stringify({
              geomodelid: Math.round(geomodelid),
              maxdepth: Math.round(maxdepth),
              width: Math.round(width),
              height: Math.round(height),
              auto_linepointdistance: !!auto_lpd,
              linepointdistance: Math.round(linepointdistance),
              borehole_tolerance_m: Number(borehole_tolerance_m)
            }));
          }
        }catch(err){}
      }
      function requestCredentials(){
        try{ if(window.pyBridge && window.pyBridge.onGeoDKCredentialsRequested) window.pyBridge.onGeoDKCredentialsRequested(); }catch(err){}
      }
      function onDownload(){
        try{
          if(window.pyBridge && window.pyBridge.onGeoDKDownloadRequested) window.pyBridge.onGeoDKDownloadRequested();
          else _setText('geodkStatus', 'Download is not wired yet.');
        }catch(err){}
      }
      function onCopyRepro(){
        try{
          if(window.pyBridge && window.pyBridge.onGeoDKCopyReproRequested) window.pyBridge.onGeoDKCopyReproRequested();
          else _setText('geodkStatus', 'Copy repro is not wired yet.');
        }catch(err){}
      }
      // Public API used by Python-side widget methods.
      return {
        state: st,
        setTab: setTab,
        setViewMode: setViewMode,
        setZoom: setZoom,
        setDepth: setDepth,
        onModelChanged: onModelChanged,
        filterModels: filterModels,
        fetchFromPanel: fetchFromPanel,
        requestCredentials: requestCredentials,
        onDownload: onDownload,
        onCopyRepro: onCopyRepro,
        __setState: _setState,
        __setModels: setModels,
        __setLegendHtml: setLegendHtml,
        __setSvgDataUrl: setSvgDataUrl,
        __setDiagJson: setDiagJson,
        __setBoreholesOverlay: setBoreholesOverlay
      };
    })();
    window.__haGeoDK.__setState('idle','Idle','Draw a line, pick a model, then Fetch.');
  </script>
</body>
</html>
"""


class GeoDKPanelWidget(QWidget):
    """
    Standalone Geo.dk panel widget: same request controls + SVG viewer contract
    as the map geology panel, but without the rest of the map HTML.
    """

    geodkFetchRequested = pyqtSignal(str)
    geodkCredentialsRequested = pyqtSignal()
    geodkDownloadRequested = pyqtSignal()
    geodkCopyReproRequested = pyqtSignal()

    def __init__(self, *, parent=None, dataset_id: str = "") -> None:
        super().__init__(parent)
        self._ha_dataset_id = str(dataset_id or "")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.web_view = QWebEngineView(self)
        layout.addWidget(self.web_view, 1)

        self.bridge = MapBridge()
        self.bridge.geodkFetchRequested.connect(self.geodkFetchRequested.emit)
        self.bridge.geodkCredentialsRequested.connect(self.geodkCredentialsRequested.emit)
        self.bridge.geodkDownloadRequested.connect(self.geodkDownloadRequested.emit)
        self.bridge.geodkCopyReproRequested.connect(self.geodkCopyReproRequested.emit)

        self.channel = QWebChannel(self.web_view.page())
        self.channel.registerObject("pyBridge", self.bridge)
        self.web_view.page().setWebChannel(self.channel)

        self.web_view.setHtml(_GEODK_PANEL_HTML)

    def set_geology_panel_loading(self, message: str):
        msg = str(message or "").strip() or "Loading..."
        lower = msg.lower()
        state = "loading"
        if ("failed" in lower) or ("error" in lower) or ("invalid" in lower) or ("required" in lower) or ("no " in lower and "model" in lower):
            state = "error"
        js = f"""
        (function(){{
            if (window.__haGeoDK && window.__haGeoDK.__setState) {{
                window.__haGeoDK.__setState({json.dumps(state)}, {json.dumps('Loading' if state=='loading' else 'Error')}, {json.dumps(msg)});
            }}
        }})();
        """
        self.web_view.page().runJavaScript(js)

    def set_geology_panel_svg(self, *, svg_html: str, info_text: str = "", legend_html: str = ""):
        svg = str(svg_html or "")
        info = str(info_text or "")
        legend = str(legend_html or "")
        try:
            b64 = base64.b64encode(svg.encode("utf-8")).decode("ascii")
            data_url = f"data:image/svg+xml;base64,{b64}"
        except Exception:
            data_url = ""
        js = f"""
        (function(){{
            var infoEl = document.getElementById('geologyInfo');
            if (infoEl && {str(bool(info)).lower()}) infoEl.innerText = {json.dumps(info)};
            if (window.__haGeoDK && window.__haGeoDK.__setSvgDataUrl) {{
                window.__haGeoDK.__setSvgDataUrl({json.dumps(data_url)});
            }}
            if (window.__haGeoDK && window.__haGeoDK.__setLegendHtml) {{
                window.__haGeoDK.__setLegendHtml({json.dumps(legend)} || '');
            }}
            if (window.__haGeoDK && window.__haGeoDK.__setState) {{
                window.__haGeoDK.__setState('ready', 'Ready', 'Loaded.');
            }}
        }})();
        """
        self.web_view.page().runJavaScript(js)

    def set_geodk_panel_models(
        self,
        *,
        models: list,
        default_geomodelid: int | None = None,
        default_maxdepth: int = -40,
        default_width: int = 1000,
        default_height: int = 320,
        default_borehole_tolerance_m: float = 10.0,
        path_m: float | None = None,
        cache_hit: bool | None = None,
    ) -> None:
        try:
            models_json = json.dumps(models or [])
        except Exception:
            models_json = "[]"
        opts = {
            "geomodelid": default_geomodelid,
            "maxdepth": int(default_maxdepth),
            "width": int(default_width),
            "height": int(default_height),
            "borehole_tolerance_m": float(default_borehole_tolerance_m),
            "path_m": float(path_m) if path_m is not None else None,
            "cache_hit": bool(cache_hit) if cache_hit is not None else None,
        }
        js = f"""
        (function(){{
            if (window.__haGeoDK && window.__haGeoDK.__setModels) {{
                try {{
                    var models = {models_json};
                    window.__haGeoDK.__setModels(models, {json.dumps(opts)});
                }} catch(err) {{}}
            }}
        }})();
        """
        self.web_view.page().runJavaScript(js)

    def set_geodk_panel_diag(self, diag: dict) -> None:
        js = f"""
        (function(){{
            if (window.__haGeoDK && window.__haGeoDK.__setDiagJson) {{
                window.__haGeoDK.__setDiagJson({json.dumps(diag or {})});
            }}
        }})();
        """
        self.web_view.page().runJavaScript(js)

    def set_geodk_panel_metrics(self, *, polygons: int | None = None, cache_hit: bool | None = None) -> None:
        payload = {
            "polygons": int(polygons) if polygons is not None else None,
            "cache_hit": bool(cache_hit) if cache_hit is not None else None,
        }
        js = f"""
        (function(){{
            var p = {json.dumps(payload)};
            try {{
                if (p.polygons !== null && p.polygons !== undefined) {{
                    var el = document.getElementById('geoMetricPoly');
                    if (el) el.textContent = String(p.polygons);
                }}
                if (p.cache_hit !== null && p.cache_hit !== undefined) {{
                    var el2 = document.getElementById('geoMetricCache');
                    if (el2) el2.textContent = (p.cache_hit ? 'HIT' : 'MISS');
                }}
            }} catch(err) {{}}
        }})();
        """
        self.web_view.page().runJavaScript(js)

    def set_geodk_boreholes_overlay(self, *, items: list[dict], viewbox_w: float, viewbox_h: float) -> None:
        payload = {
            "items": list(items or []),
            "viewbox": {"w": float(viewbox_w), "h": float(viewbox_h)},
        }
        js = f"""
        (function(){{
            try {{
                if (window.__haGeoDK && window.__haGeoDK.__setBoreholesOverlay) {{
                    window.__haGeoDK.__setBoreholesOverlay({json.dumps(payload["items"])}, {json.dumps(payload["viewbox"])});
                }}
            }} catch(err) {{}}
        }})();
        """
        self.web_view.page().runJavaScript(js)

