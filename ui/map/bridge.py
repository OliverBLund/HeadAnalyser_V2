"""Qt WebChannel bridge for map JS <-> Python communication."""

from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot


class MapBridge(QObject):
    """Bridge for JavaScript to Python communication."""

    pointClicked = pyqtSignal(str)  # Emits point ID or JSON payload when clicked
    pointHovered = pyqtSignal(str)  # Emits point ID on hover
    transectDrawn = pyqtSignal(list)  # Emits list of [lat, lon] coordinates
    mapClicked = pyqtSignal(float, float)  # Emits lat, lon on map click
    layerToggled = pyqtSignal(str, bool)
    exportRequested = pyqtSignal(str)  # Emits format type ('html', 'png', 'geojson')
    opacityChanged = pyqtSignal(float)
    pointSizeChanged = pyqtSignal(int)
    scaleBarToggled = pyqtSignal(bool)
    syncSelectionToggled = pyqtSignal(bool)
    labelsToggled = pyqtSignal(bool)
    excludePointRequested = pyqtSignal(str)
    showPointInPlotRequested = pyqtSignal(str)
    heatmapModeChanged = pyqtSignal(str)
    pointColorByValueToggled = pyqtSignal(bool)
    contourLabelsToggled = pyqtSignal(bool)
    contourLabelPrecisionChanged = pyqtSignal(int)
    contourMajorIntervalChanged = pyqtSignal(int)
    contourSettingsRequested = pyqtSignal()
    externalLayerVisibilityChanged = pyqtSignal(str, bool)
    externalLayerStyleChanged = pyqtSignal(str, str)
    externalLayerRenamed = pyqtSignal(str, str)
    externalLayerOrderChanged = pyqtSignal(str)
    externalLayerManagerRequested = pyqtSignal()
    geodkFetchRequested = pyqtSignal(str)  # JSON payload from Geo.dk panel
    geodkCredentialsRequested = pyqtSignal()
    geodkDownloadRequested = pyqtSignal()
    geodkCopyReproRequested = pyqtSignal()
    transectSelected = pyqtSignal(str)  # Emits transect ID when selected
    transectDeleted = pyqtSignal(str)   # Emits transect ID to delete
    transectVisibilityToggled = pyqtSignal(str)  # Emits transect ID to toggle visibility
    transectRenamed = pyqtSignal(str, str)  # Emits transect ID and new name

    @pyqtSlot(str)
    def onPointClick(self, point_id):
        self.pointClicked.emit(point_id)

    @pyqtSlot(str)
    def onPointHover(self, point_id):
        self.pointHovered.emit(point_id)

    @pyqtSlot(str, bool)
    def onLayerToggled(self, layer_name, visible):
        self.layerToggled.emit(layer_name, visible)

    @pyqtSlot(str)
    def onTransectDrawn(self, coords_json):
        import json
        try:
            coords = json.loads(coords_json)
            self.transectDrawn.emit(coords)
        except Exception:
            pass

    @pyqtSlot(float, float)
    def onMapClick(self, lat, lon):
        self.mapClicked.emit(lat, lon)

    @pyqtSlot(str)
    def onExportRequested(self, format_type):
        self.exportRequested.emit(format_type)

    @pyqtSlot(float)
    def onOpacityChanged(self, value):
        self.opacityChanged.emit(value)

    @pyqtSlot(int)
    def onPointSizeChanged(self, value):
        self.pointSizeChanged.emit(value)

    @pyqtSlot(bool)
    def onScaleBarToggled(self, visible):
        self.scaleBarToggled.emit(visible)

    @pyqtSlot(bool)
    def onSyncSelectionToggled(self, enabled):
        self.syncSelectionToggled.emit(enabled)

    @pyqtSlot(bool)
    def onLabelsToggled(self, enabled):
        self.labelsToggled.emit(enabled)

    @pyqtSlot(str)
    def onExcludePointRequested(self, point_id):
        self.excludePointRequested.emit(str(point_id))

    @pyqtSlot(str)
    def onShowPointInPlotRequested(self, point_id):
        self.showPointInPlotRequested.emit(str(point_id))

    @pyqtSlot(str)
    def onHeatmapModeChanged(self, mode):
        self.heatmapModeChanged.emit(str(mode))

    @pyqtSlot(bool)
    def onPointColorByValueToggled(self, enabled):
        self.pointColorByValueToggled.emit(bool(enabled))

    @pyqtSlot(bool)
    def onContourLabelsToggled(self, enabled):
        self.contourLabelsToggled.emit(bool(enabled))

    @pyqtSlot(int)
    def onContourLabelPrecisionChanged(self, digits):
        self.contourLabelPrecisionChanged.emit(int(digits))

    @pyqtSlot(int)
    def onContourMajorIntervalChanged(self, every_n):
        self.contourMajorIntervalChanged.emit(int(every_n))

    @pyqtSlot()
    def onContourSettingsRequested(self):
        self.contourSettingsRequested.emit()

    @pyqtSlot(str, bool)
    def onExternalLayerVisibilityChanged(self, layer_id, visible):
        self.externalLayerVisibilityChanged.emit(str(layer_id), bool(visible))

    @pyqtSlot(str, str)
    def onExternalLayerStyleChanged(self, layer_id, style_json):
        self.externalLayerStyleChanged.emit(str(layer_id), str(style_json))

    @pyqtSlot(str, str)
    def onExternalLayerRenamed(self, layer_id, name):
        self.externalLayerRenamed.emit(str(layer_id), str(name))

    @pyqtSlot(str)
    def onExternalLayerOrderChanged(self, order_json):
        self.externalLayerOrderChanged.emit(str(order_json))

    @pyqtSlot()
    def onOpenExternalLayerManagerRequested(self):
        self.externalLayerManagerRequested.emit()

    @pyqtSlot(str)
    def onGeoDKFetchRequested(self, payload_json: str):
        self.geodkFetchRequested.emit(str(payload_json or ""))

    @pyqtSlot()
    def onGeoDKCredentialsRequested(self):
        self.geodkCredentialsRequested.emit()

    @pyqtSlot()
    def onGeoDKDownloadRequested(self):
        self.geodkDownloadRequested.emit()

    @pyqtSlot()
    def onGeoDKCopyReproRequested(self):
        self.geodkCopyReproRequested.emit()

    @pyqtSlot(str)
    def onTransectSelected(self, transect_id: str):
        self.transectSelected.emit(str(transect_id or ""))

    @pyqtSlot(str)
    def onTransectDeleted(self, transect_id: str):
        self.transectDeleted.emit(str(transect_id or ""))

    @pyqtSlot(str)
    def onTransectVisibilityToggled(self, transect_id: str):
        self.transectVisibilityToggled.emit(str(transect_id or ""))

    @pyqtSlot(str, str)
    def onTransectRenamed(self, transect_id: str, new_name: str):
        self.transectRenamed.emit(str(transect_id or ""), str(new_name or ""))
