"""
HeadAnalyser V2 - File Handler (Load + Filter Engine).

Responsibilities:
- Load source files and run column mapping.
- Apply depth/head filters and exclusion masks.
- Produce both:
  - `filtered_plot_data` (pre-exclusion, for visual contexts that show excluded),
  - `filtered_data` (post-exclusion, for analysis/triangles/gradients).

Coordination rule:
- This module computes filtered outputs.
- View refresh orchestration is owned by MainWindow centralizers.
"""

import os
import pandas as pd
import numpy as np
from PyQt5.QtWidgets import QMessageBox

from .data_processing import DataProcessing
from ui.dialogs.column_mapping import ColumnMappingDialog


class FileHandler:
    """Handles file operations and data filtering."""
    
    def __init__(self, app_ref):
        self.app_ref = app_ref
        self.aggregated_data = None
        
    def detect_delimiter(self, file_path: str) -> str:
        """Detect the delimiter used in a CSV file."""
        with open(file_path, 'r', encoding='utf-8') as file:
            lines = file.readlines()
            possible_delimiters = [',', ';', '\t', ' ']
            delimiter_counts = {delim: lines[0].count(delim) for delim in possible_delimiters}
            return max(delimiter_counts, key=delimiter_counts.get)
            
    def load_file(self, file_path: str, use_recent_mapping: bool = False):
        """Load a data file."""
        if not file_path or not os.path.exists(file_path):
            QMessageBox.critical(self.app_ref, "Error", "File not found.")
            return None

        # Persist active dataset state before any new-file mapping/settings mutate main-window state.
        try:
            if hasattr(self.app_ref, "get_active_dataset") and hasattr(self.app_ref, "sync_to_dataset"):
                active_ds = self.app_ref.get_active_dataset()
                if active_ds is not None:
                    self.app_ref.sync_to_dataset(active_ds)
        except Exception:
            pass
            
        _, file_extension = os.path.splitext(file_path)
        
        try:
            # Load based on file type
            if file_extension == '.csv':
                delimiter = self.detect_delimiter(file_path)
                data = pd.read_csv(file_path, delimiter=delimiter, dtype=str)
            elif file_extension == '.xlsx':
                xls = pd.ExcelFile(file_path)
                sheets = xls.sheet_names
                
                if len(sheets) > 1:
                    # Show sheet selection dialog
                    from PyQt5.QtWidgets import QInputDialog
                    sheet, ok = QInputDialog.getItem(
                        self.app_ref,
                        "Select Sheet",
                        "Choose a sheet to load:",
                        sheets,
                        0,
                        False
                    )
                    if not ok:
                        return None
                else:
                    sheet = sheets[0]
                    
                data = pd.read_excel(file_path, sheet_name=sheet, dtype=str)
            elif file_extension == '.json':
                data = pd.read_json(file_path)
            else:
                QMessageBox.critical(
                    self.app_ref, 
                    "Error", 
                    f"Unsupported file format: {file_extension}"
                )
                return None
                
        except PermissionError:
            QMessageBox.critical(
                self.app_ref,
                "Permission Error",
                "Cannot access file. It may be open in another program."
            )
            return None
        except Exception as e:
            QMessageBox.critical(
                self.app_ref,
                "Error",
                f"Failed to load file: {str(e)}"
            )
            return None
            
        # Large data warning
        if len(data) > 30:
            reply = QMessageBox.question(
                self.app_ref,
                "Large Dataset",
                f"This file contains {len(data)} rows which may take longer to process. Continue?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )
            if reply == QMessageBox.No:
                return None
                
        selected_mapping = {}
        saved_mapping = {}
        if use_recent_mapping and hasattr(self.app_ref, "get_recent_mapping_for_file"):
            try:
                saved_mapping = self.app_ref.get_recent_mapping_for_file(file_path, list(data.columns)) or {}
            except Exception:
                saved_mapping = {}

        if saved_mapping:
            selected_mapping = dict(saved_mapping)
        else:
            # Show column mapping dialog
            dialog = ColumnMappingDialog(
                list(data.columns),
                self.app_ref,
                initial_mapping=saved_mapping if isinstance(saved_mapping, dict) else None,
            )
            try:
                if dialog.exec_():
                    selected_mapping = dialog.get_mapping()
                else:
                    return None
            finally:
                dialog.deleteLater()

        self.app_ref.col_mapping = {
            'ID': selected_mapping.get('ID'),
            'x': selected_mapping.get('x'),
            'y': selected_mapping.get('y'),
            'hydraulic head': selected_mapping.get('hydraulic head')
        }
        self.app_ref.top_column = selected_mapping.get('top')
        self.app_ref.bottom_column = selected_mapping.get('bottom')
        self.app_ref.depth_column = selected_mapping.get('depth')
            
        # Convert ID column to string
        id_col = self.app_ref.col_mapping.get('ID')
        if id_col and id_col in data.columns:
            data[id_col] = data[id_col].astype(str)
            
        # Convert decimal separators and numeric columns
        data = self.app_ref.data_processor.convert_decimal_separator(data)
        
        # Validate columns
        if not self.app_ref.data_processor.validate_columns(data):
            return None
            
        # Validate data types
        if not self.app_ref.data_processor.validate_data_types(data):
            return None
            
        # Drop rows with missing required values
        required_cols = [
            self.app_ref.col_mapping['x'],
            self.app_ref.col_mapping['y'],
            self.app_ref.col_mapping['hydraulic head']
        ]
        data = data.dropna(subset=required_cols)

        # Warn about duplicate IDs (V1.1.x caches by ID tuples, which can produce wrong results)
        id_col = self.app_ref.col_mapping.get('ID')
        if id_col and id_col in data.columns:
            dup_count = int(data[id_col].duplicated().sum())
            if dup_count > 0:
                QMessageBox.warning(
                    self.app_ref,
                    "Duplicate IDs detected",
                    (
                        f"Column '{id_col}' contains {dup_count} duplicate value(s).\n\n"
                        "HeadAnalyser V2 will still compute gradients correctly, but older V1.1.x versions "
                        "may show different/incorrect averages due to ID-based caching."
                    ),
                )

        # Create new dataset tab
        dataset_name = os.path.basename(file_path).split('.')[0]
        dataset_id = self.app_ref.create_new_dataset_tab(dataset_name, file_path)

        # Get the new dataset object
        dataset = self.app_ref.datasets[dataset_id]

        # Store data in dataset and legacy attributes
        self.app_ref.data = data
        self.app_ref.filtered_data = data.copy()
        self.app_ref.filtered_plot_data = data.copy()
        dataset.data = data
        dataset.filtered_data = data.copy()
        dataset.filtered_plot_data = data.copy()
        dataset.col_mapping = self.app_ref.col_mapping.copy()
        dataset.top_column = self.app_ref.top_column
        dataset.bottom_column = self.app_ref.bottom_column
        dataset.depth_column = getattr(self.app_ref, "depth_column", None)

        # Ensure runtime state reflects this dataset after mapped columns/data are assigned.
        # Doing this earlier can overwrite mapping with dataset defaults (None values).
        if hasattr(self.app_ref, "sync_from_dataset"):
            self.app_ref.sync_from_dataset(dataset)

        self.create_aggregated_data()

        # Transform coordinates for map
        self._transform_coordinates(data)

        # Calculate gradients (threaded async is optional; default is synchronous with progress dialog)
        async_enabled = bool(getattr(self.app_ref, "_async_gradient_enabled", False))
        if async_enabled and hasattr(self.app_ref, "request_active_gradient_recompute_async"):
            self.app_ref.triangle_data = pd.DataFrame()
            self.app_ref.gradient_data = pd.DataFrame()
            self.app_ref.rejected_data = pd.DataFrame()
            self.app_ref.total_triangles = None
            self.app_ref.rejected_due_to_uncertainty = None
            self.app_ref.rejected_due_to_triangle_quality = None
            self.app_ref.rejected_due_to_calculation_failed = None
            dataset.triangle_data = self.app_ref.triangle_data
            self.app_ref.request_active_gradient_recompute_async(reason="load_file")
        else:
            self.app_ref.dataset_name = str(getattr(dataset, "name", dataset_name))
            self.app_ref._calc_reason = "load_file"
            self.app_ref.triangle_data = self.app_ref.gradient_calculator.create_gradient_dataframe(data)
            dataset.triangle_data = self.app_ref.triangle_data

        # Update UI
        self.app_ref.update_status(
            file_name=dataset_name,
            num_points=len(data),
            num_triangles=len(self.app_ref.triangle_data) if self.app_ref.triangle_data is not None else 0
        )

        # Setup filter ranges for this dataset
        self._setup_filter_ranges()

        # Sync back to dataset
        self.app_ref.sync_to_dataset(dataset)

        # Update views
        self.app_ref.update_data_views()
        self.app_ref.update_plot()

        # Refresh triangle table in drawer (if it exists)
        try:
            dataset.plot_page.refresh_triangle_data()
        except Exception:
            pass

        # Persist to recent sessions after successful end-to-end load.
        try:
            if hasattr(self.app_ref, "add_recent_session"):
                mapping_payload = {
                    "ID": self.app_ref.col_mapping.get("ID"),
                    "x": self.app_ref.col_mapping.get("x"),
                    "y": self.app_ref.col_mapping.get("y"),
                    "hydraulic head": self.app_ref.col_mapping.get("hydraulic head"),
                    "top": getattr(self.app_ref, "top_column", None),
                    "bottom": getattr(self.app_ref, "bottom_column", None),
                    "depth": getattr(self.app_ref, "depth_column", None),
                }
                self.app_ref.add_recent_session(
                    file_path,
                    dataset_name=dataset_name,
                    mapping=mapping_payload,
                )
        except Exception:
            pass

        return data
        
    def _transform_coordinates(self, data):
        """Add lat/lon columns for map display."""
        import pyproj
        
        x_col = self.app_ref.col_mapping['x']
        y_col = self.app_ref.col_mapping['y']
        
        # Validate column mapping
        if x_col is None or y_col is None:
            print(f"Coordinate transformation skipped: column mapping incomplete (x={x_col}, y={y_col})")
            return
        
        try:
            transformer = pyproj.Transformer.from_crs(
                "epsg:25832",  # UTM32N EUREF89 for Denmark
                "epsg:4326",   # WGS84
                always_xy=True
            )
            
            lon, lat = transformer.transform(
                data[x_col].values,
                data[y_col].values
            )
            
            data['Latitude'] = lat
            data['Longitude'] = lon

            # Keep all active filtered views in sync; map uses filtered_plot_data.
            for view_name in ("filtered_data", "filtered_plot_data"):
                try:
                    view_df = getattr(self.app_ref, view_name, None)
                    if isinstance(view_df, pd.DataFrame) and len(view_df) == len(data):
                        view_df['Latitude'] = lat
                        view_df['Longitude'] = lon
                except Exception:
                    pass

            try:
                dataset = self.app_ref.get_active_dataset() if hasattr(self.app_ref, "get_active_dataset") else None
                if dataset is not None:
                    if isinstance(getattr(dataset, "data", None), pd.DataFrame) and len(dataset.data) == len(data):
                        dataset.data['Latitude'] = lat
                        dataset.data['Longitude'] = lon
                    if isinstance(getattr(dataset, "filtered_data", None), pd.DataFrame) and len(dataset.filtered_data) == len(data):
                        dataset.filtered_data['Latitude'] = lat
                        dataset.filtered_data['Longitude'] = lon
                    if isinstance(getattr(dataset, "filtered_plot_data", None), pd.DataFrame) and len(dataset.filtered_plot_data) == len(data):
                        dataset.filtered_plot_data['Latitude'] = lat
                        dataset.filtered_plot_data['Longitude'] = lon
            except Exception:
                pass
        except Exception as e:
            print(f"Coordinate transformation failed: {e}")
            
    def _setup_filter_ranges(self):
        """Setup filter slider ranges based on data."""
        data = self.app_ref.data
        depth_bounds = None
        head_bounds = None

        # Depth range
        depth_mode, depth_cols = self._resolve_depth_filter_columns(data)
        if depth_mode == "top_bottom":
            top_col, bottom_col = depth_cols
            top_vals = pd.to_numeric(data[top_col], errors='coerce')
            bot_vals = pd.to_numeric(data[bottom_col], errors='coerce')
            dmin = np.nanmin([top_vals.min(), bot_vals.min()])
            dmax = np.nanmax([top_vals.max(), bot_vals.max()])
            if np.isfinite(dmin) and np.isfinite(dmax):
                depth_bounds = (float(dmin), float(dmax))
        elif depth_mode == "single":
            col = depth_cols[0]
            vals = pd.to_numeric(data[col], errors='coerce')
            dmin = vals.min()
            dmax = vals.max()
            if np.isfinite(dmin) and np.isfinite(dmax):
                depth_bounds = (float(dmin), float(dmax))

        # Hydraulic head range
        h_col = self.app_ref.col_mapping['hydraulic head']
        if h_col:
            head_min = data[h_col].min()
            head_max = data[h_col].max()
            head_bounds = (float(head_min), float(head_max))

        self.app_ref.properties_panel.update_filter_ranges(
            depth_range=depth_bounds,
            head_range=head_bounds,
            depth_values=depth_bounds,
            head_values=head_bounds,
        )

        try:
            dataset = self.app_ref.get_active_dataset() if hasattr(self.app_ref, "get_active_dataset") else None
            if dataset is not None:
                if depth_bounds is not None:
                    dataset.depth_bounds = depth_bounds
                    dataset.depth_range = depth_bounds
                if head_bounds is not None:
                    dataset.head_bounds = head_bounds
                    dataset.head_range = head_bounds
        except Exception:
            pass
        try:
            if hasattr(self.app_ref, "properties_panel"):
                self.app_ref.properties_panel.update_from_main_window()
        except Exception:
            pass

    def _resolve_depth_filter_columns(self, data):
        """Return depth filter mode and columns based on available mapping."""
        cols = set(data.columns)
        top_col = getattr(self.app_ref, "top_column", None)
        bottom_col = getattr(self.app_ref, "bottom_column", None)
        depth_col = getattr(self.app_ref, "depth_column", None)

        top_ok = bool(top_col and top_col in cols)
        bottom_ok = bool(bottom_col and bottom_col in cols)
        depth_ok = bool(depth_col and depth_col in cols)

        if top_ok and bottom_ok:
            return "top_bottom", (top_col, bottom_col)
        if top_ok:
            return "single", (top_col,)
        if bottom_ok:
            return "single", (bottom_col,)
        if depth_ok:
            return "single", (depth_col,)
        return None, tuple()
            
    def create_aggregated_data(self):
        """Create aggregated dataset for gradient calculation."""
        data_source = self.app_ref.filtered_data if self.app_ref.filtered_data is not None else self.app_ref.data
        self.aggregated_data = data_source
        
    def get_aggregated_data(self):
        """Return aggregated data."""
        return self.aggregated_data
        
    def filter_data(self, depth_min=None, depth_max=None, head_min=None, head_max=None, async_gradients: bool = False):
        """Filter data based on depth and hydraulic head ranges."""
        if self.app_ref.data is None:
            return

        # Any recompute invalidates triangle selections.
        try:
            if hasattr(self.app_ref, "clear_triangle_selection"):
                self.app_ref.clear_triangle_selection()
        except Exception:
            pass
            
        filtered = self.app_ref.data.copy()
        
        # Apply depth filters
        depth_mode, depth_cols = self._resolve_depth_filter_columns(filtered)
        if depth_mode == "top_bottom":
            top_col, bottom_col = depth_cols
            if depth_min is not None:
                top_vals = pd.to_numeric(filtered[top_col], errors='coerce')
                filtered = filtered[top_vals >= float(depth_min)]
            if depth_max is not None:
                bot_vals = pd.to_numeric(filtered[bottom_col], errors='coerce')
                filtered = filtered[bot_vals <= float(depth_max)]
        elif depth_mode == "single":
            col = depth_cols[0]
            vals = pd.to_numeric(filtered[col], errors='coerce')
            if depth_min is not None:
                filtered = filtered[vals >= float(depth_min)]
                vals = pd.to_numeric(filtered[col], errors='coerce')
            if depth_max is not None:
                filtered = filtered[vals <= float(depth_max)]
            
        # Apply hydraulic head filter
        h_col = self.app_ref.col_mapping.get('hydraulic head')
        if h_col:
            if head_min is not None:
                filtered = filtered[filtered[h_col] >= head_min]
            if head_max is not None:
                filtered = filtered[filtered[h_col] <= head_max]
                
        # Keep a plotting copy before exclusions so 2D can render excluded points.
        plot_filtered = filtered.copy()

        # Apply exclusions for calculations/derived products
        excluded_member_keys = {str(v) for v in getattr(self.app_ref, "excluded_member_keys", set())}
        if self.app_ref.excluded_ids or excluded_member_keys:
            id_col = self.app_ref.col_mapping.get('ID')
            if id_col:
                excluded_str = {str(v) for v in self.app_ref.excluded_ids}
                id_series = filtered[id_col].astype(str)
                member_keys = id_series + "::" + filtered.index.astype(str)
                exclude_mask = id_series.isin(excluded_str)
                if excluded_member_keys:
                    exclude_mask = exclude_mask | member_keys.isin(excluded_member_keys)
                filtered = filtered[~exclude_mask]
                 
        self.app_ref.filtered_plot_data = plot_filtered
        self.app_ref.filtered_data = filtered
        self.create_aggregated_data()

        async_enabled = bool(getattr(self.app_ref, "_async_gradient_enabled", False))
        if async_gradients and async_enabled and hasattr(self.app_ref, "request_active_gradient_recompute_async"):
            # Clear active gradient-dependent outputs while the background job runs.
            self.app_ref.triangle_data = pd.DataFrame()
            self.app_ref.gradient_data = pd.DataFrame()
            self.app_ref.rejected_data = pd.DataFrame()
            self.app_ref.total_triangles = None
            self.app_ref.rejected_due_to_uncertainty = None
            self.app_ref.rejected_due_to_triangle_quality = None
            self.app_ref.rejected_due_to_calculation_failed = None
            self.app_ref.request_active_gradient_recompute_async(reason="filter_data")
        else:
            # Recalculate gradients (synchronous path)
            ds_name = None
            try:
                if hasattr(self.app_ref, "get_active_dataset"):
                    ds = self.app_ref.get_active_dataset()
                    ds_name = getattr(ds, "name", None) if ds is not None else None
            except Exception:
                ds_name = None
            self.app_ref.dataset_name = str(ds_name or "active")
            self.app_ref._calc_reason = "filter_data_sync"
            self.app_ref.triangle_data = self.app_ref.gradient_calculator.create_gradient_dataframe(filtered)

        # Update status
        self.app_ref.update_status(
            num_points=len(filtered),
            num_triangles=len(self.app_ref.triangle_data) if self.app_ref.triangle_data is not None else 0
        )

        # Persist into active dataset (multi-dataset support).
        try:
            if hasattr(self.app_ref, "get_active_dataset") and hasattr(self.app_ref, "sync_to_dataset"):
                ds = self.app_ref.get_active_dataset()
                if ds is not None:
                    self.app_ref.sync_to_dataset(ds)
                    # Refresh triangle table in drawer
                    ds.plot_page.refresh_triangle_data()
        except Exception:
            pass
