"""
HeadAnalyser V2 - Column Mapping Dialog
Dialog for mapping data columns to application fields.
"""

import re

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QFormLayout, QFrame
)
from PyQt5.QtCore import Qt

from styles.colors import Colors


class ColumnMappingDialog(QDialog):
    """Dialog for mapping CSV columns to required fields."""
    
    def __init__(self, columns: list, parent=None, initial_mapping: dict = None):
        super().__init__(parent)
        self.columns = columns
        self.initial_mapping = initial_mapping if isinstance(initial_mapping, dict) else {}
        self.mapping = {}
        
        self.setWindowTitle("Column Mapping")
        self.setMinimumWidth(400)
        self.setModal(True)

        self._setup_ui()
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        
        # Header
        header = QLabel("Map your data columns to the required fields:")
        header.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; font-size: 13px;")
        layout.addWidget(header)
        
        # Form
        form_frame = QFrame()
        form_layout = QFormLayout(form_frame)
        form_layout.setSpacing(12)
        
        # Required fields
        fields = [
            ('ID', 'Unique identifier column'),
            ('x', 'X coordinate column'),
            ('y', 'Y coordinate column'),
            ('hydraulic head', 'Hydraulic head column')
        ]
        
        self.combos = {}
        
        used_columns = set()

        for field_name, description in fields:
            combo = QComboBox()
            combo.addItem("-- Select column --")
            combo.addItems(self.columns)

            selected_column = self._prefill_or_autodetect_field(field_name, used_columns)
            if selected_column in self.columns:
                combo.setCurrentIndex(self.columns.index(selected_column) + 1)
                used_columns.add(selected_column)
                    
            self.combos[field_name] = combo
            
            label = QLabel(f"{field_name}:")
            label.setStyleSheet(f"color: {Colors.ACCENT_PRIMARY}; font-weight: bold;")
            form_layout.addRow(label, combo)
            
        layout.addWidget(form_frame)
        
        # Optional fields section
        optional_label = QLabel("Optional columns:")
        optional_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 12px; margin-top: 8px;")
        layout.addWidget(optional_label)
        
        optional_frame = QFrame()
        optional_layout = QFormLayout(optional_frame)
        optional_layout.setSpacing(12)
        
        # Top depth
        self.top_combo = QComboBox()
        self.top_combo.addItem("-- None --")
        self.top_combo.addItems(self.columns)
        top_col = self._prefill_optional('top')
        if top_col in self.columns:
            self.top_combo.setCurrentIndex(self.columns.index(top_col) + 1)
        optional_layout.addRow(QLabel("Top depth:"), self.top_combo)
        
        # Bottom depth
        self.bottom_combo = QComboBox()
        self.bottom_combo.addItem("-- None --")
        self.bottom_combo.addItems(self.columns)
        bottom_col = self._prefill_optional('bottom')
        if bottom_col in self.columns:
            self.bottom_combo.setCurrentIndex(self.columns.index(bottom_col) + 1)
        optional_layout.addRow(QLabel("Bottom depth:"), self.bottom_combo)

        # Unified depth
        self.depth_combo = QComboBox()
        self.depth_combo.addItem("-- None --")
        self.depth_combo.addItems(self.columns)
        depth_col = self._prefill_optional('depth')
        if depth_col in self.columns:
            self.depth_combo.setCurrentIndex(self.columns.index(depth_col) + 1)
        optional_layout.addRow(QLabel("Depth (single):"), self.depth_combo)
        
        layout.addWidget(optional_frame)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setAutoDefault(False)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        apply_btn = QPushButton("Apply")
        apply_btn.setStyleSheet(f"background-color: {Colors.ACCENT_PRIMARY};")
        apply_btn.setDefault(True)
        apply_btn.setAutoDefault(True)
        apply_btn.clicked.connect(self._on_apply)
        self.apply_btn = apply_btn
        button_layout.addWidget(apply_btn)
        
        layout.addLayout(button_layout)
        
    def _on_apply(self):
        """Validate and apply mapping."""
        # Check required fields
        for field_name, combo in self.combos.items():
            if combo.currentIndex() == 0:
                from PyQt5.QtWidgets import QMessageBox
                QMessageBox.warning(
                    self, 
                    "Missing Field",
                    f"Please select a column for '{field_name}'"
                )
                return
                
        # Build mapping
        for field_name, combo in self.combos.items():
            self.mapping[field_name] = combo.currentText()
            
        # Optional fields
        if self.top_combo.currentIndex() > 0:
            self.mapping['top'] = self.top_combo.currentText()
        if self.bottom_combo.currentIndex() > 0:
            self.mapping['bottom'] = self.bottom_combo.currentText()
        if self.depth_combo.currentIndex() > 0:
            self.mapping['depth'] = self.depth_combo.currentText()
            
        self.accept()
        
    def get_mapping(self):
        """Return the column mapping."""
        return self.mapping

    @staticmethod
    def _normalize_column_name(column_name: str) -> str:
        value = str(column_name or "").strip().lower()
        value = value.replace("æ", "ae").replace("ø", "oe").replace("å", "aa")
        return re.sub(r"[^a-z0-9]+", "", value)

    @staticmethod
    def _column_tokens(column_name: str) -> set:
        raw = str(column_name or "").strip().lower()
        parts = re.split(r"[^a-z0-9]+", raw)
        return {p for p in parts if p}

    def _prefill_or_autodetect_field(self, field_name: str, used_columns: set) -> str:
        preferred = str(self.initial_mapping.get(field_name) or "")
        if preferred in self.columns and preferred not in used_columns:
            return preferred
        return self._detect_best_column(field_name, used_columns=used_columns)

    def _prefill_optional(self, field_name: str) -> str:
        preferred = str(self.initial_mapping.get(field_name) or "")
        if preferred in self.columns:
            return preferred
        return ""

    def _detect_best_column(self, field_name: str, used_columns: set, optional: bool = False) -> str:
        best_col = ""
        best_score = -1
        for col in self.columns:
            if col in used_columns:
                continue
            score = self._score_column_for_field(field_name, col, optional=optional)
            if score > best_score:
                best_score = score
                best_col = col
        if best_score <= 0:
            return ""
        return best_col

    def _score_column_for_field(self, field_name: str, column_name: str, optional: bool = False) -> int:
        normalized = self._normalize_column_name(column_name)
        tokens = self._column_tokens(column_name)

        if field_name == "ID":
            score = 0
            if normalized in {"id", "dgu", "dgunr", "dgunummer", "wellid", "boreholeid", "boringid", "boringnr"}:
                score += 120
            if "id" in tokens:
                score += 80
            if {"dgu", "dgunr", "dgunummer", "boringnr", "wellid"} & tokens:
                score += 70
            if "name" in tokens:
                score += 20
            return score

        if field_name == "x":
            score = 0
            if normalized in {"x", "utmx", "easting", "xcoord", "xcoordinate", "coordx"}:
                score += 120
            if "x" in tokens:
                score += 60
            if "utm" in tokens:
                score += 35
            if {"east", "easting", "xcoord"} & tokens:
                score += 60
            if "32eu" in normalized or ("32" in tokens and ("eu" in tokens or "euref" in tokens)):
                score += 60
            if "north" in tokens or "northing" in tokens:
                score -= 35
            return score

        if field_name == "y":
            score = 0
            if normalized in {"y", "utmy", "northing", "ycoord", "ycoordinate", "coordy"}:
                score += 120
            if "y" in tokens:
                score += 60
            if "utm" in tokens:
                score += 35
            if {"north", "northing", "ycoord"} & tokens:
                score += 60
            if "32nu" in normalized or ("32" in tokens and ("nu" in tokens or "north" in tokens)):
                score += 60
            if "east" in tokens or "easting" in tokens:
                score -= 35
            return score

        if field_name == "hydraulic head":
            score = 0
            if normalized in {"gvs", "head", "hydraulichead", "waterlevel", "grundvandsspejl", "h"}:
                score += 120
            if "gvs" in tokens:
                score += 120
            if {"head", "hydraulic", "waterlevel", "piezometric"} & tokens:
                score += 80
            if normalized == "h":
                score += 35
            return score

        if field_name == "top":
            if normalized in {"top", "topdepth", "fromdepth", "upperdepth"}:
                return 120
            score = 0
            if "top" in tokens or "upper" in tokens or "from" in tokens:
                score += 80
            if "depth" in tokens:
                score += 25
            return score

        if field_name == "bottom":
            if normalized in {"bottom", "bottomdepth", "todepth", "lowerdepth"}:
                return 120
            score = 0
            if "bottom" in tokens or "lower" in tokens or "to" in tokens:
                score += 80
            if "depth" in tokens:
                score += 25
            return score

        if field_name == "depth":
            score = 0
            if normalized in {"depth", "screen", "screenlength"}:
                score += 110
            if "depth" in tokens:
                score += 80
            if "top" in tokens or "bottom" in tokens:
                score -= 30
            return score

        return 0

    def keyPressEvent(self, event):
        """Ensure Enter applies mapping instead of canceling the dialog."""
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self._on_apply()
            event.accept()
            return
        super().keyPressEvent(event)
