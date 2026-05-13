"""Experimental Geo.dk fence view dialog (isolated from core workflows)."""

from __future__ import annotations

import math
from typing import Any

from PyQt5.QtCore import QThread, Qt
from PyQt5.QtGui import QImage, QMatrix4x4, QPainter
from PyQt5.QtWidgets import (
    QCheckBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ui.workers import FunctionWorker


class GeoDKFenceDialog(QDialog):
    """Experimental multi-transect fence renderer using Geo.dk cross-sections."""

    def __init__(self, *, parent=None, main_window=None) -> None:
        super().__init__(parent)
        self.main_window = main_window
        self._dataset = None
        self._gl = None
        self._glw = None
        self._items: list[Any] = []
        self._job_refs: list[dict] = []

        self.setWindowTitle("Geo.dk Fence View (Experimental)")
        self.resize(1320, 860)
        self.setModal(False)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        splitter = QSplitter(self)
        splitter.setOrientation(Qt.Horizontal)
        root.addWidget(splitter, 1)

        left = QWidget(splitter)
        lyt = QVBoxLayout(left)
        lyt.setContentsMargins(0, 0, 0, 0)
        lyt.setSpacing(8)

        hdr = QLabel("Transects (history)")
        lyt.addWidget(hdr)
        self.listw = QListWidget(left)
        lyt.addWidget(self.listw, 1)

        row = QHBoxLayout()
        btn_all = QPushButton("All")
        btn_none = QPushButton("None")
        row.addWidget(btn_all)
        row.addWidget(btn_none)
        row.addStretch(1)
        lyt.addLayout(row)
        btn_all.clicked.connect(self._select_all)
        btn_none.clicked.connect(self._select_none)

        form = QFormLayout()
        self.geomodel_edit = QLineEdit("auto")
        self.maxdepth_spin = QSpinBox()
        self.maxdepth_spin.setRange(-500, 500)
        self.maxdepth_spin.setValue(-40)
        self.width_spin = QSpinBox()
        self.width_spin.setRange(200, 4000)
        self.width_spin.setValue(1000)
        self.height_spin = QSpinBox()
        self.height_spin.setRange(120, 2000)
        self.height_spin.setValue(320)
        self.auto_lpd = QCheckBox("Auto")
        self.auto_lpd.setChecked(True)
        self.lpd_spin = QSpinBox()
        self.lpd_spin.setRange(1, 10000)
        self.lpd_spin.setValue(2)
        self.vert_exag = QDoubleSpinBox()
        self.vert_exag.setRange(0.5, 30.0)
        self.vert_exag.setSingleStep(0.5)
        self.vert_exag.setValue(6.0)
        self.fence_spacing = QDoubleSpinBox()
        self.fence_spacing.setRange(20.0, 1200.0)
        self.fence_spacing.setSingleStep(10.0)
        self.fence_spacing.setValue(180.0)
        self.target_len = QDoubleSpinBox()
        self.target_len.setRange(200.0, 4000.0)
        self.target_len.setSingleStep(50.0)
        self.target_len.setValue(950.0)
        form.addRow("GeoModelId", self.geomodel_edit)
        form.addRow("Depth (Level)", self.maxdepth_spin)
        form.addRow("Width", self.width_spin)
        form.addRow("Height", self.height_spin)
        lpd_row = QHBoxLayout()
        lpd_row.addWidget(self.auto_lpd)
        lpd_row.addWidget(self.lpd_spin, 1)
        form.addRow("LinePointDistance", lpd_row)
        form.addRow("Vertical exag", self.vert_exag)
        form.addRow("Fence spacing", self.fence_spacing)
        form.addRow("Target length", self.target_len)
        lyt.addLayout(form)

        btm = QHBoxLayout()
        self.fetch_btn = QPushButton("Fetch + Render")
        self.fetch_btn.setDefault(True)
        self.close_btn = QPushButton("Close")
        btm.addWidget(self.fetch_btn)
        btm.addStretch(1)
        btm.addWidget(self.close_btn)
        lyt.addLayout(btm)
        self.fetch_btn.clicked.connect(self._on_fetch_clicked)
        self.close_btn.clicked.connect(self.close)

        self.status = QLabel("Select transects and click Fetch + Render.")
        lyt.addWidget(self.status)

        right = QWidget(splitter)
        rlyt = QVBoxLayout(right)
        rlyt.setContentsMargins(0, 0, 0, 0)
        rlyt.setSpacing(6)
        self.scene_status = QLabel("3D scene requires pyqtgraph + OpenGL.")
        rlyt.addWidget(self.scene_status)
        self.scene_host = QWidget(right)
        self.scene_host.setLayout(QVBoxLayout())
        self.scene_host.layout().setContentsMargins(0, 0, 0, 0)
        rlyt.addWidget(self.scene_host, 1)
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([390, 920])

        self._init_gl_view()

    def _init_gl_view(self):
        try:
            import pyqtgraph.opengl as gl  # type: ignore

            self._gl = gl
            self._glw = gl.GLViewWidget(self.scene_host)
            self._glw.setBackgroundColor((8, 18, 28))
            self.scene_host.layout().addWidget(self._glw, 1)
            self.scene_status.setText("Ready. Fetch transects to render fence view.")
        except Exception as exc:
            self._gl = None
            self._glw = None
            self.scene_status.setText(f"OpenGL unavailable: {exc}")

    def refresh_from_dataset(self, dataset) -> None:
        self._dataset = dataset
        self.listw.clear()
        hist = list(getattr(dataset, "geodk_transect_history", []) or [])
        for i, t in enumerate(hist):
            if not isinstance(t, dict):
                continue
            try:
                ln = float(t.get("length_m", 0.0) or 0.0)
            except Exception:
                ln = 0.0
            src = str(t.get("source") or "map")
            tid = str(t.get("id") or f"T{i+1}")
            txt = f"{tid} | {src} | {ln:.0f} m"
            it = QListWidgetItem(txt, self.listw)
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(2)
            it.setData(Qt.UserRole, t)
            self.listw.addItem(it)
        self.status.setText(f"Loaded {self.listw.count()} transects from dataset history.")

    def _select_all(self):
        for i in range(self.listw.count()):
            self.listw.item(i).setCheckState(2)

    def _select_none(self):
        for i in range(self.listw.count()):
            self.listw.item(i).setCheckState(0)

    def _selected_transects(self) -> list[dict]:
        out = []
        for i in range(self.listw.count()):
            it = self.listw.item(i)
            if int(it.checkState()) != 2:
                continue
            t = it.data(Qt.UserRole)
            if isinstance(t, dict):
                out.append(t)
        return out

    def _on_fetch_clicked(self):
        if self.main_window is None:
            return
        if self._gl is None or self._glw is None:
            QMessageBox.warning(self, "OpenGL Missing", "pyqtgraph.opengl is required.")
            return
        selected = self._selected_transects()
        if not selected:
            QMessageBox.information(self, "No Transects", "Select at least one transect.")
            return

        try:
            client = self.main_window._get_geodk_client()
        except Exception as exc:
            QMessageBox.warning(self, "Geo.dk", f"Geo.dk setup failed: {exc}")
            return

        cfg = {
            "geomodelid": str(self.geomodel_edit.text() or "auto").strip(),
            "maxdepth": int(self.maxdepth_spin.value()),
            "width": int(self.width_spin.value()),
            "height": int(self.height_spin.value()),
            "auto_lpd": bool(self.auto_lpd.isChecked()),
            "linepointdistance": int(self.lpd_spin.value()),
            "vertical_exag": float(self.vert_exag.value()),
            "fence_spacing": float(self.fence_spacing.value()),
            "target_length": float(self.target_len.value()),
        }
        self.fetch_btn.setEnabled(False)
        self.status.setText(f"Fetching {len(selected)} transects from Geo.dk...")

        thread = QThread(self)
        worker = FunctionWorker(self._fence_job, client, selected, cfg)
        worker.moveToThread(thread)
        worker.finished.connect(self._on_job_done)
        worker.failed.connect(self._on_job_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.started.connect(worker.run)
        self._job_refs.append({"thread": thread, "worker": worker})
        thread.finished.connect(lambda: self._cleanup_job(thread, worker))
        thread.start()

    def _cleanup_job(self, thread, worker):
        self._job_refs = [j for j in self._job_refs if j.get("thread") is not thread and j.get("worker") is not worker]

    @staticmethod
    def _fence_job(client, selected: list[dict], cfg: dict) -> dict:
        from core.geodk_api import auto_linepointdistance, normalize_svg_for_display, path_length_m
        from core.geology_layers import GeoDkSvgSurfaceGeologyProvider

        out = []
        for t in selected:
            path_utm = list(t.get("path_utm") or [])
            if len(path_utm) < 2:
                continue
            models, _cache = client.geomodels_for_path(path_utm)
            chosen = None
            if str(cfg.get("geomodelid", "auto")).lower() != "auto":
                try:
                    chosen = int(cfg.get("geomodelid"))
                except Exception:
                    chosen = None
            if chosen is None:
                for m in models:
                    if not isinstance(m, dict):
                        continue
                    mid = m.get("ID", m.get("Id", m.get("id", None)))
                    try:
                        midi = int(mid)
                    except Exception:
                        continue
                    if midi > 0:
                        chosen = midi
                        break
            if chosen is None:
                continue

            length_m = float(path_length_m(path_utm))
            if bool(cfg.get("auto_lpd", True)):
                lpd = int(auto_linepointdistance(length_m=length_m, width_px=int(cfg.get("width", 1000))))
            else:
                lpd = int(max(1, int(cfg.get("linepointdistance", 2))))
            section = client.crosssection(
                path_25832=path_utm,
                geomodelid=int(chosen),
                width=int(cfg.get("width", 1000)),
                height=int(cfg.get("height", 320)),
                maxdepth=int(cfg.get("maxdepth", -40)),
                linepointdistance=int(lpd),
            )
            svg_raw = str(section.get("Svg") or "")
            layout = section.get("SvgLayout") if isinstance(section.get("SvgLayout"), dict) else {}
            svg_w = int(layout.get("Width") or int(cfg.get("width", 1000)))
            svg_h = int(layout.get("Height") or int(cfg.get("height", 320)))
            svg = normalize_svg_for_display(svg_raw, width=svg_w, height=svg_h)

            provider = GeoDkSvgSurfaceGeologyProvider()
            provider.update_from_svg(svg_text=svg, path_length_m=length_m)
            geo = provider.sample_transect(distances_m=[0.0, length_m])
            segs = list(geo.get("segments") or [])
            if not segs:
                class _FallbackSeg:
                    start_m = 0.0
                    end_m = float(max(1.0, length_m))
                    color = "#8f99a6"

                segs = [_FallbackSeg()]
            out.append(
                {
                    "id": str(t.get("id") or ""),
                    "source": str(t.get("source") or ""),
                    "length_m": float(length_m),
                    "segments": segs,
                    "segments_count": int(len(segs)),
                    "svg": svg,
                    "svg_w": int(svg_w),
                    "svg_h": int(svg_h),
                    "model_id": int(chosen),
                    "model_name": (section.get("Model") or {}).get("Name") if isinstance(section.get("Model"), dict) else "",
                }
            )
        return {"panels": out, "cfg": dict(cfg)}

    @staticmethod
    def _hex_rgba(color: str, alpha: float = 0.90):
        c = str(color or "").strip()
        if c.startswith("#") and len(c) in {4, 7}:
            if len(c) == 4:
                c = "#" + c[1] * 2 + c[2] * 2 + c[3] * 2
            try:
                r = int(c[1:3], 16) / 255.0
                g = int(c[3:5], 16) / 255.0
                b = int(c[5:7], 16) / 255.0
                return (float(r), float(g), float(b), float(alpha))
            except Exception:
                pass
        return (0.57, 0.62, 0.67, float(alpha))

    def _clear_scene(self):
        if self._glw is None:
            return
        for it in list(self._items):
            try:
                self._glw.removeItem(it)
            except Exception:
                pass
        self._items.clear()

    @staticmethod
    def _svg_to_texture(svg_text: str, width: int, height: int):
        import numpy as np
        from PyQt5.QtCore import QByteArray
        from PyQt5.QtSvg import QSvgRenderer

        svg = str(svg_text or "").strip()
        w = int(max(64, width))
        h = int(max(64, height))
        if not svg:
            return None
        try:
            renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
            if not renderer.isValid():
                return None
            img = QImage(w, h, QImage.Format_ARGB32)
            img.fill(Qt.transparent)
            painter = QPainter(img)
            renderer.render(painter)
            painter.end()

            ptr = img.bits()
            ptr.setsize(img.byteCount())
            # ARGB32 byte layout in memory is BGRA on little-endian hosts.
            bgra = np.frombuffer(ptr, dtype=np.uint8).reshape((h, w, 4)).copy()
            rgba = bgra[:, :, [2, 1, 0, 3]]

            # Remove white background from the rendered SVG to keep a clean scene.
            near_white = (rgba[:, :, 0] > 246) & (rgba[:, :, 1] > 246) & (rgba[:, :, 2] > 246)
            rgba[near_white, 3] = 0

            # GLImageItem expects x,y indexing; transpose from row,col.
            tex = np.transpose(rgba, (1, 0, 2)).copy()
            return tex
        except Exception:
            return None

    def _on_job_done(self, payload: object):
        self.fetch_btn.setEnabled(True)
        if not isinstance(payload, dict):
            self.status.setText("Unexpected result.")
            return
        panels = list(payload.get("panels") or [])
        cfg = dict(payload.get("cfg") or {})
        if not panels:
            self.status.setText("No panels returned.")
            return
        textured, fallback = self._render_panels(panels, cfg)
        self.status.setText(
            f"Rendered {len(panels)} transects. Textured: {int(textured)}  Fallback-mesh: {int(fallback)}"
        )

    def _on_job_failed(self, msg: str, tb: str):
        self.fetch_btn.setEnabled(True)
        self.status.setText(f"Fetch failed: {msg}")
        print(f"[geodk-fence] failed: {msg}\n{tb}")

    def _render_panels(self, panels: list[dict], cfg: dict):
        if self._gl is None or self._glw is None:
            return (0, 0)
        import numpy as np
        from PyQt5.QtGui import QVector3D

        gl = self._gl
        self._clear_scene()

        max_len = max(float(p.get("length_m", 1.0) or 1.0) for p in panels)
        max_depth = max(8.0, abs(float(cfg.get("maxdepth", -40) or -40)))
        local_len = float(max(250.0, cfg.get("target_length", 950.0)))
        exag = float(max(0.5, cfg.get("vertical_exag", 6.0)))
        local_depth = float(max(30.0, max_depth * exag))
        n = len(panels)
        z_spacing = float(max(20.0, cfg.get("fence_spacing", 180.0)))
        total_z = float(max(10.0, (n - 1) * z_spacing))

        self._glw.opts["center"] = QVector3D(0.0, float(-0.45 * local_depth), 0.0)
        self._glw.setCameraPosition(distance=max(700.0, local_len * 1.4 + total_z * 0.7), elevation=18, azimuth=-34)

        # Floor grid
        grid = gl.GLGridItem()
        grid.setSize(x=max(120.0, local_len * 1.15), y=max(120.0, total_z * 1.25))
        grid.setSpacing(x=max(25.0, local_len / 16.0), y=max(25.0, total_z / max(2.0, n - 1)))
        grid.translate(0.0, float(-local_depth), 0.0)
        self._glw.addItem(grid)
        self._items.append(grid)

        textured_count = 0
        fallback_count = 0
        center_idx = 0.5 * (n - 1)
        for i, p in enumerate(panels):
            segs = list(p.get("segments") or [])
            lm = float(max(1.0, p.get("length_m", 1.0)))
            z = (float(i) - center_idx) * z_spacing
            rendered_textured = False

            if hasattr(gl, "GLImageItem"):
                tex = self._svg_to_texture(
                    str(p.get("svg") or ""),
                    int(p.get("svg_w") or int(cfg.get("width", 1000))),
                    int(p.get("svg_h") or int(cfg.get("height", 320))),
                )
                if tex is not None:
                    try:
                        tex_w = float(max(1, int(tex.shape[0])))
                        tex_h = float(max(1, int(tex.shape[1])))
                        img_item = gl.GLImageItem(tex)
                        m = QMatrix4x4()
                        m.translate(0.0, 0.0, float(z))
                        m.translate(float(-0.5 * local_len), 0.0, 0.0)
                        m.scale(float(local_len / tex_w), float(-local_depth / tex_h), 1.0)
                        img_item.setTransform(m)
                        try:
                            img_item.setGLOptions("translucent")
                        except Exception:
                            pass
                        self._glw.addItem(img_item)
                        self._items.append(img_item)
                        rendered_textured = True
                        textured_count += 1
                    except Exception:
                        rendered_textured = False

            if rendered_textured:
                top = gl.GLLinePlotItem(
                    pos=np.array([[-0.5 * local_len, 0.0, z], [0.5 * local_len, 0.0, z]], dtype=float),
                    color=(0.39, 0.80, 1.0, 0.95 if i == int(round(center_idx)) else 0.45),
                    width=2.0 if i == int(round(center_idx)) else 1.2,
                    antialias=True,
                )
                self._glw.addItem(top)
                self._items.append(top)
                continue

            sx = local_len / lm
            verts = []
            faces = []
            cols = []
            for seg in segs:
                x0m = float(getattr(seg, "start_m", 0.0))
                x1m = float(getattr(seg, "end_m", lm))
                if not math.isfinite(x0m) or not math.isfinite(x1m) or x1m <= x0m:
                    continue
                x0 = (x0m - 0.5 * lm) * sx
                x1 = (x1m - 0.5 * lm) * sx
                y0 = 0.0
                y1 = -max_depth * exag
                b = len(verts)
                verts.extend([[x0, y0, z], [x0, y1, z], [x1, y0, z], [x1, y1, z]])
                faces.append([b + 0, b + 1, b + 2])
                faces.append([b + 2, b + 1, b + 3])
                col = self._hex_rgba(getattr(seg, "color", "#8f99a6"))
                cols.append(col)
                cols.append(col)

            if verts:
                md = gl.MeshData(
                    vertexes=np.array(verts, dtype=float),
                    faces=np.array(faces, dtype=np.int32),
                    faceColors=np.array(cols, dtype=float),
                )
                mesh = gl.GLMeshItem(
                    meshdata=md,
                    smooth=False,
                    drawEdges=True,
                    edgeColor=(0.95, 0.98, 1.0, 0.22),
                    shader="shaded",
                )
                mesh.rotate(8.0, 0, 1, 0)
                self._glw.addItem(mesh)
                self._items.append(mesh)
                fallback_count += 1

            top = gl.GLLinePlotItem(
                pos=np.array([[-0.5 * local_len, 0.0, z], [0.5 * local_len, 0.0, z]], dtype=float),
                color=(0.39, 0.80, 1.0, 0.95 if i == int(round(center_idx)) else 0.45),
                width=2.0 if i == int(round(center_idx)) else 1.2,
                antialias=True,
            )
            self._glw.addItem(top)
            self._items.append(top)
        return (textured_count, fallback_count)
