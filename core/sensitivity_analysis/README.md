# Sensitivity Analysis Backend

Isolated backend module for sensitivity runs.

## Files
- `models.py`: typed config/result data containers.
- `scope.py`: applies point scope (`all_points` / `selected_points`).
- `scenarios.py`: run plan generation for sweep, leave-out, Monte Carlo.
- `engine.py`: orchestration and metric extraction.
- `exports.py`: run table and JSON export helpers.

This package is intentionally UI-agnostic for easy plug-in/plug-out.
