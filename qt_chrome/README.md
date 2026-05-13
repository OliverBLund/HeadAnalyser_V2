# qt_chrome (QGIS/PyQt5)

Reusable frameless window helpers for the QGIS desktop app.

## Included
- `mode.py`:
  - `resolve_window_chrome_mode(...)`
- `window_helper.py`:
  - `FramelessWindowChromeHelper`
- `frameless_main_window_mixin.py`:
  - `FramelessMainWindowMixin` (single-file drop-in for QMainWindow apps)
- `frameless_dialog_mixin.py`:
  - `FramelessDialogMixin` (single-file drop-in for QDialog apps)
- `mask.py`:
  - `apply_frameless_round_mask(...)`
- `platform.py`:
  - `enable_windows_soft_corners(...)`

Default is `frameless` on Windows and `native` elsewhere.

## Performance Note (Important)

Frameless dialogs can cause significant UI lag in large/interactive apps if used incorrectly.

In HeadAnalyser, the lag was reproducible when opening certain frameless dialogs, while
header-based frameless dialogs remained smooth. Keep these rules:

1. Prefer native `QDialog` for heavy forms (`column_mapping`, `calculation_settings`, etc.).
2. If using frameless dialogs, bind drag on a dedicated header only:
   - Good: `bind_frameless_drag_widget(self._chrome_header)`
   - Avoid: `bind_frameless_drag_widget(self)` on full dialog roots.
3. Keep edge-resize helpers disabled for dialogs unless strictly needed.
4. After modal `exec_()`, explicitly cleanup dialog instances (e.g., `deleteLater()`).

If lag appears after opening a dialog, first switch that dialog to native chrome and retest.
