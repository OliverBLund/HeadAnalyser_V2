"""
HeadAnalyser V2 - Data Processing
Handles data validation and conversion.
Ported from original HeadAnalyser with minimal changes.
"""

import numpy as np
import pandas as pd
from PyQt5.QtWidgets import QMessageBox


class DataProcessing:
    """Handles data processing and validation."""
    
    def __init__(self, app_ref):
        self.app_ref = app_ref
        
    def convert_decimal_separator(self, data: pd.DataFrame) -> pd.DataFrame:
        """Convert comma decimal separators to dots and convert to numeric."""
        id_column = self.app_ref.col_mapping.get('ID')
        
        for col in data.columns:
            # Skip ID column
            if col == id_column:
                continue
                
            def safe_convert(x):
                try:
                    if isinstance(x, str):
                        return float(x.replace(',', '.'))
                    elif pd.isna(x):
                        return x
                    else:
                        return float(x)
                except (ValueError, TypeError):
                    return np.nan
                    
            data[col] = data[col].apply(safe_convert)
            data[col] = pd.to_numeric(data[col], errors='coerce')
            
        return data
        
    def validate_columns(self, data: pd.DataFrame) -> bool:
        """Validate that all required columns exist in the data."""
        for col_name, user_col in self.app_ref.col_mapping.items():
            if user_col and user_col not in data.columns:
                QMessageBox.critical(
                    self.app_ref,
                    "Error",
                    f"Column '{user_col}' for '{col_name}' not found in data."
                )
                return False
        return True
        
    def validate_data_types(self, data: pd.DataFrame) -> bool:
        """Validate that numeric columns contain numeric data."""
        numeric_cols = [
            self.app_ref.col_mapping.get('x'),
            self.app_ref.col_mapping.get('y'),
            self.app_ref.col_mapping.get('hydraulic head')
        ]
        
        for col in numeric_cols:
            if col and not pd.api.types.is_numeric_dtype(data[col]):
                QMessageBox.critical(
                    self.app_ref,
                    "Error",
                    f"Column '{col}' should contain numeric values."
                )
                return False
                
        return True
