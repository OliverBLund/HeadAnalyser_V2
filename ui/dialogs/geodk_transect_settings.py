"""Geo.dk transect (model + depth + resolution) settings dialog."""

from __future__ import annotations

import math
from dataclasses import dataclass

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from core.geodk_api import auto_linepointdistance
from styles.colors import Colors


@dataclass(frozen=True)
class GeoDKTransectSettings:
    geomodelid: int
    maxdepth: int
    width: int
    height: int
    linepointdistance: int
    auto_linepointdistance: bool
    borehole_tolerance_m: float = 10.0


class GeoDKTransectSettingsDialog(QDialog):
    def __init__(
        self,
        *,
        parent=None,
        models: list[dict],
        line_length_m: float,
        default_geomodelid: int | None = None,
        default_maxdepth: int = -40,
        default_width: int = 1000,
        default_height: int = 320,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Geo.dk Cross Section Settings")
        self.setModal(True)
        self.resize(520, 260)

        self._models = list(models or [])
        self._line_length_m = float(line_length_m or 0.0)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        title = QLabel("Select a GeoModel and request settings")
        title.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; font-size: 12px; font-weight: 600;")
        layout.addWidget(title)

        sub = QLabel(f"Line length: {self._format_m(self._line_length_m)}")
        sub.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 11px;")
        layout.addWidget(sub)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignLeft)

        self.model_combo = QComboBox()
        self._model_ids: list[int] = []
        for m in self._models:
            try:
                mid = m.get("ID") if isinstance(m, dict) else None
                if mid is None:
                    mid = m.get("Id") if isinstance(m, dict) else None
                mid_int = int(mid)
            except Exception:
                continue
            name = ""
            try:
                name = str(m.get("Name") or "").strip()
            except Exception:
                name = ""
            label = f"{name or 'Model'} (ID {mid_int})"
            self.model_combo.addItem(label)
            self._model_ids.append(mid_int)
        form.addRow("GeoModel:", self.model_combo)

        self.maxdepth_spin = QSpinBox()
        self.maxdepth_spin.setRange(-200, 200)
        self.maxdepth_spin.setValue(int(default_maxdepth))
        self.maxdepth_spin.setToolTip("Depth (Level). Negative values go down. QGIS default is -40.")
        form.addRow("Depth (Level):", self.maxdepth_spin)

        self.width_spin = QSpinBox()
        self.width_spin.setRange(200, 4000)
        self.width_spin.setValue(int(default_width))
        form.addRow("SVG Width (px):", self.width_spin)

        self.height_spin = QSpinBox()
        self.height_spin.setRange(120, 2000)
        self.height_spin.setValue(int(default_height))
        form.addRow("SVG Height (px):", self.height_spin)

        self.auto_lpd_check = QCheckBox("Auto linepointdistance (QGIS-like)")
        self.auto_lpd_check.setChecked(True)
        form.addRow("", self.auto_lpd_check)

        self.lpd_spin = QSpinBox()
        self.lpd_spin.setRange(1, 10000)
        self.lpd_spin.setValue(
            int(auto_linepointdistance(length_m=self._line_length_m, width_px=int(default_width)))
        )
        form.addRow("LinePointDistance (m):", self.lpd_spin)

        layout.addLayout(form)

        self.summary = QLabel("")
        self.summary.setStyleSheet(f"color: {Colors.TEXT_TERTIARY}; font-size: 10px;")
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        cancel_btn = QPushButton("Cancel")
        ok_btn = QPushButton("Fetch")
        ok_btn.setDefault(True)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)

        cancel_btn.clicked.connect(self.reject)
        ok_btn.clicked.connect(self.accept)

        self.auto_lpd_check.toggled.connect(self._sync_lpd_enabled)
        self.width_spin.valueChanged.connect(self._recalc_auto_lpd)
        self._sync_lpd_enabled(self.auto_lpd_check.isChecked())
        self._refresh_summary(default_geomodelid=default_geomodelid)

        if default_geomodelid is not None:
            self._select_geomodelid(int(default_geomodelid))

    @staticmethod
    def _format_m(val_m: float) -> str:
        if not math.isfinite(val_m):
            return "n/a"
        if val_m >= 1000.0:
            return f"{val_m/1000.0:.2f} km"
        return f"{val_m:.0f} m"

    def _select_geomodelid(self, geomodelid: int) -> None:
        try:
            idx = self._model_ids.index(int(geomodelid))
        except Exception:
            return
        self.model_combo.setCurrentIndex(int(idx))

    def _sync_lpd_enabled(self, auto_enabled: bool) -> None:
        auto_on = bool(auto_enabled)
        self.lpd_spin.setEnabled(not auto_on)
        self._recalc_auto_lpd()

    def _recalc_auto_lpd(self) -> None:
        if not self.auto_lpd_check.isChecked():
            return
        w = int(self.width_spin.value())
        self.lpd_spin.setValue(int(auto_linepointdistance(length_m=self._line_length_m, width_px=w)))

    def _refresh_summary(self, *, default_geomodelid: int | None = None) -> None:
        try:
            if default_geomodelid is not None:
                self.summary.setText(f"Default GeoModelId: {int(default_geomodelid)}")
                return
        except Exception:
            pass
        self.summary.setText("Tip: If SVG polygons are 0, try another model or a different line.")

    def settings(self) -> GeoDKTransectSettings:
        idx = int(self.model_combo.currentIndex())
        geomodelid = self._model_ids[idx] if 0 <= idx < len(self._model_ids) else -1
        auto_lpd = bool(self.auto_lpd_check.isChecked())
        width = int(self.width_spin.value())
        lpd = (
            int(auto_linepointdistance(length_m=self._line_length_m, width_px=width))
            if auto_lpd
            else int(self.lpd_spin.value())
        )
        return GeoDKTransectSettings(
            geomodelid=int(geomodelid),
            maxdepth=int(self.maxdepth_spin.value()),
            width=int(width),
            height=int(self.height_spin.value()),
            linepointdistance=int(max(1, lpd)),
            auto_linepointdistance=auto_lpd,
            borehole_tolerance_m=10.0,
        )
