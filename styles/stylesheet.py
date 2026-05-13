"""
HeadAnalyser V2 - Centralized Stylesheet System
Warm & Approachable dark theme with warm indigo accent.
"""

from .colors import Colors


class StyleSheet:
    """Centralized stylesheet generator for consistent theming."""

    @staticmethod
    def get_main_stylesheet():
        """
        Main application stylesheet - warm, approachable, generous radius.
        """
        return f"""
            /* ========== GLOBAL DEFAULTS ========== */
            * {{
                font-family: 'Segoe UI', 'Plus Jakarta Sans', Arial, sans-serif;
                outline: none;
            }}

            QMainWindow {{
                background-color: {Colors.BG_APP};
            }}

            QWidget {{
                background-color: transparent;
                color: {Colors.TEXT_PRIMARY};
            }}

            /* ========== PANELS & CONTAINERS ========== */
            QWidget#propertiesPanel {{
                background-color: {Colors.BG_PANEL};
                border-left: 1px solid {Colors.BORDER_DEFAULT};
            }}

            QWidget#navigationSidebar {{
                background-color: {Colors.BG_PANEL};
                border-right: 1px solid {Colors.BORDER_DEFAULT};
            }}

            QWidget#headerBar {{
                background-color: {Colors.BG_PANEL};
            }}

            /* ========== SCROLL AREAS ========== */
            QScrollArea {{
                background-color: transparent;
                border: none;
            }}

            QScrollBar:vertical {{
                background-color: transparent;
                width: 8px;
                border: none;
                margin: 0;
            }}

            QScrollBar::handle:vertical {{
                background-color: {Colors.BORDER_STRONG};
                border-radius: 4px;
                min-height: 30px;
                margin: 2px;
            }}

            QScrollBar::handle:vertical:hover {{
                background-color: {Colors.TEXT_MUTED};
            }}

            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}

            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: none;
            }}

            QScrollBar:horizontal {{
                background-color: transparent;
                height: 8px;
                border: none;
                margin: 0;
            }}

            QScrollBar::handle:horizontal {{
                background-color: {Colors.BORDER_STRONG};
                border-radius: 4px;
                min-width: 30px;
                margin: 2px;
            }}

            QScrollBar::handle:horizontal:hover {{
                background-color: {Colors.TEXT_MUTED};
            }}

            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                width: 0px;
            }}

            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
                background: none;
            }}

            /* ========== SPLITTER ========== */
            QSplitter::handle {{
                background-color: {Colors.BORDER_DEFAULT};
                width: 2px;
                height: 2px;
            }}

            QSplitter::handle:hover {{
                background-color: {Colors.ACCENT_PRIMARY};
            }}

            QSplitter::handle:pressed {{
                background-color: {Colors.ACCENT_BRIGHT};
            }}

            /* ========== TABS - Warm with accent bottom bar ========== */
            QTabWidget::pane {{
                background-color: transparent;
                border: none;
            }}

            QTabBar {{
                background-color: {Colors.BG_DARK};
                border: none;
                padding-left: 8px;
            }}

            QTabBar::tab {{
                background-color: transparent;
                color: {Colors.TEXT_TERTIARY};
                padding: 6px 22px 6px 14px;
                margin: 0px 2px 0px 0px;
                border: none;
                border-bottom: 2px solid transparent;
                border-radius: {Colors.RADIUS_MD} {Colors.RADIUS_MD} 0px 0px;
                font-size: 11px;
                font-weight: 600;
                min-height: 28px;
                min-width: 90px;
            }}

            QTabBar::tab:selected {{
                background-color: {Colors.BG_PANEL};
                color: {Colors.TEXT_PRIMARY};
                font-weight: 700;
                border-bottom: 2px solid {Colors.ACCENT_PRIMARY};
            }}

            QTabBar::tab:hover:!selected {{
                background-color: {Colors.BG_SURFACE};
                color: {Colors.TEXT_SECONDARY};
            }}

            QToolButton#datasetTabCloseButton {{
                background-color: transparent;
                border: 1px solid transparent;
                border-radius: 4px;
                color: {Colors.TEXT_MUTED};
                font-size: 12px;
                font-weight: 900;
                padding: 0px;
            }}

            QToolButton#datasetTabCloseButton:hover {{
                background-color: {Colors.ERROR_BG};
                border-color: transparent;
                color: {Colors.ERROR};
            }}

            QToolButton#datasetTabCloseButton:pressed {{
                background-color: {Colors.ERROR};
                color: {Colors.TEXT_PRIMARY};
            }}

            /* ========== BUTTONS - Warm with generous radius ========== */
            QPushButton {{
                background-color: {Colors.BG_SURFACE};
                color: {Colors.TEXT_PRIMARY};
                border: 1px solid {Colors.BORDER_MEDIUM};
                border-radius: {Colors.RADIUS_MD};
                padding: 8px 16px;
                font-size: 12px;
                font-weight: 600;
            }}

            QPushButton:hover {{
                background-color: {Colors.BG_HOVER};
                border-color: {Colors.BORDER_ACCENT};
                color: {Colors.TEXT_ACCENT};
            }}

            QPushButton:pressed {{
                background-color: {Colors.ACCENT_PRESSED};
                border-color: {Colors.ACCENT_PRESSED};
                color: {Colors.TEXT_PRIMARY};
            }}

            QPushButton:disabled {{
                background-color: {Colors.STATE_DISABLED_BG};
                color: {Colors.STATE_DISABLED_TEXT};
                border-color: {Colors.BORDER_SUBTLE};
            }}

            QPushButton[primary="true"] {{
                background-color: {Colors.ACCENT_PRIMARY};
                color: {Colors.TEXT_INVERSE};
                border: 1px solid {Colors.ACCENT_PRIMARY};
                font-weight: 700;
            }}

            QPushButton[primary="true"]:hover {{
                background-color: {Colors.ACCENT_HOVER};
                border-color: {Colors.ACCENT_HOVER};
            }}

            QPushButton[primary="true"]:pressed {{
                background-color: {Colors.ACCENT_PRESSED};
                border-color: {Colors.ACCENT_PRESSED};
            }}

            /* ========== COMBO BOX ========== */
            QComboBox {{
                background-color: {Colors.BG_SURFACE};
                color: {Colors.TEXT_PRIMARY};
                border: 1px solid {Colors.BORDER_MEDIUM};
                border-radius: 6px;
                padding: 6px 12px;
                padding-right: 30px;
                min-height: 28px;
                font-size: 12px;
            }}

            QComboBox:hover {{
                border-color: {Colors.ACCENT_PRIMARY};
            }}

            QComboBox:focus {{
                border-color: {Colors.ACCENT_PRIMARY};
            }}

            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: center right;
                width: 30px;
                border: none;
                border-left: none;
                background-color: transparent;
            }}

            QComboBox::down-arrow {{
                width: 8px;
                height: 8px;
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid {Colors.TEXT_MUTED};
            }}

            QComboBox::down-arrow:hover {{
                border-top-color: {Colors.ACCENT_PRIMARY};
            }}

            QComboBox QAbstractItemView {{
                background-color: {Colors.BG_ELEVATED};
                color: {Colors.TEXT_PRIMARY};
                border: 1px solid {Colors.BORDER_MEDIUM};
                border-radius: 6px;
                padding: 4px;
                selection-background-color: {Colors.ACCENT_PRIMARY};
                selection-color: white;
                outline: none;
            }}

            QComboBox QAbstractItemView::item {{
                padding: 8px 12px;
                min-height: 24px;
                background-color: {Colors.BG_ELEVATED};
                color: {Colors.TEXT_PRIMARY};
            }}

            QComboBox QAbstractItemView::item:hover {{
                background-color: {Colors.BG_HOVER};
            }}

            QComboBox QAbstractItemView::item:selected {{
                background-color: {Colors.ACCENT_PRIMARY};
                color: white;
            }}

            /* Fix for Windows - ensure popup inherits theme */
            QComboBox QListView {{
                background-color: {Colors.BG_ELEVATED};
                color: {Colors.TEXT_PRIMARY};
                border: 1px solid {Colors.BORDER_MEDIUM};
                outline: none;
            }}

            /* ========== CHECKBOXES ========== */
            QCheckBox {{
                color: {Colors.TEXT_SECONDARY};
                spacing: 10px;
                font-size: 12px;
            }}

            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border: 1.5px solid {Colors.BORDER_STRONG};
                border-radius: {Colors.RADIUS_XS};
                background-color: {Colors.BG_SURFACE};
            }}

            QCheckBox::indicator:hover {{
                border-color: {Colors.ACCENT_PRIMARY};
                background-color: {Colors.BG_HOVER};
            }}

            QCheckBox::indicator:checked {{
                background-color: {Colors.ACCENT_PRIMARY};
                border: 1.5px solid {Colors.ACCENT_PRIMARY};
                image: none;
            }}

            QCheckBox::indicator:checked:hover {{
                background-color: {Colors.ACCENT_HOVER};
                border-color: {Colors.ACCENT_HOVER};
            }}

            /* ========== SPIN BOXES ========== */
            QSpinBox, QDoubleSpinBox {{
                background-color: {Colors.BG_SURFACE};
                color: {Colors.TEXT_PRIMARY};
                border: 1px solid {Colors.BORDER_MEDIUM};
                border-radius: 6px;
                padding: 6px 8px;
                padding-right: 24px;
                font-size: 12px;
            }}

            QSpinBox:hover, QDoubleSpinBox:hover {{
                border-color: {Colors.ACCENT_PRIMARY};
            }}

            QSpinBox:focus, QDoubleSpinBox:focus {{
                border-color: {Colors.ACCENT_PRIMARY};
            }}

            QSpinBox::up-button, QDoubleSpinBox::up-button {{
                subcontrol-origin: border;
                subcontrol-position: top right;
                background-color: transparent;
                border: none;
                border-left: none;
                width: 20px;
            }}

            QSpinBox::down-button, QDoubleSpinBox::down-button {{
                subcontrol-origin: border;
                subcontrol-position: bottom right;
                background-color: transparent;
                border: none;
                border-left: none;
                width: 20px;
            }}

            QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
                image: none;
                width: 8px;
                height: 8px;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-bottom: 4px solid {Colors.TEXT_MUTED};
            }}

            QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
                image: none;
                width: 8px;
                height: 8px;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 4px solid {Colors.TEXT_MUTED};
            }}

            QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover {{
                background-color: transparent;
            }}

            QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
                background-color: transparent;
            }}

            QSpinBox::up-arrow:hover, QDoubleSpinBox::up-arrow:hover {{
                border-bottom-color: {Colors.ACCENT_PRIMARY};
            }}

            QSpinBox::down-arrow:hover, QDoubleSpinBox::down-arrow:hover {{
                border-top-color: {Colors.ACCENT_PRIMARY};
            }}

            /* ========== LINE EDIT ========== */
            QLineEdit {{
                background-color: {Colors.BG_SURFACE};
                color: {Colors.TEXT_PRIMARY};
                border: 1px solid {Colors.BORDER_MEDIUM};
                border-radius: {Colors.RADIUS_SM};
                padding: 6px 12px;
                font-size: 12px;
            }}

            QLineEdit:hover {{
                border-color: {Colors.BORDER_ACCENT};
            }}

            QLineEdit:focus {{
                border: 2px solid {Colors.ACCENT_PRIMARY};
                padding: 5px 11px;
            }}

            /* ========== LABELS ========== */
            QLabel {{
                color: {Colors.TEXT_SECONDARY};
                background-color: transparent;
            }}

            /* ========== STATUS BAR ========== */
            QStatusBar {{
                background-color: {Colors.BG_PANEL};
                color: {Colors.TEXT_TERTIARY};
                border-top: 1px solid {Colors.BORDER_DEFAULT};
                padding: 6px 12px;
                font-size: 10px;
            }}

            QStatusBar QLabel {{
                color: {Colors.TEXT_TERTIARY};
                padding: 0px 8px;
                font-size: 10px;
            }}

            QStatusBar::item {{
                border: none;
            }}

            /* ========== TOOLTIPS ========== */
            QToolTip {{
                background-color: {Colors.ELEVATION_4};
                color: {Colors.TEXT_PRIMARY};
                border: 1px solid {Colors.BORDER_MEDIUM};
                border-radius: {Colors.RADIUS_SM};
                padding: 6px 10px;
                font-size: 11px;
            }}

            /* ========== MENUS ========== */
            QMenu {{
                background-color: {Colors.ELEVATION_4};
                color: {Colors.TEXT_PRIMARY};
                border: 1px solid {Colors.BORDER_MEDIUM};
                border-radius: {Colors.RADIUS_MD};
                padding: 4px;
            }}

            QMenu::item {{
                padding: 6px 20px 6px 12px;
                border-radius: {Colors.RADIUS_XS};
            }}

            QMenu::item:selected {{
                background-color: {Colors.ACCENT_PRIMARY};
                color: {Colors.TEXT_INVERSE};
            }}

            QMenu::separator {{
                height: 1px;
                background-color: {Colors.BORDER_DEFAULT};
                margin: 4px 8px;
            }}

            /* ========== DIALOGS ========== */
            QDialog {{
                background-color: {Colors.BG_MODAL};
                color: {Colors.TEXT_PRIMARY};
            }}

            /* ========== TABLE VIEWS ========== */
            QTableView {{
                background-color: {Colors.BG_SURFACE};
                alternate-background-color: {Colors.BG_DARK};
                gridline-color: {Colors.BORDER_SUBTLE};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: {Colors.RADIUS_MD};
                selection-background-color: {Colors.STATE_SELECTED_BG};
                selection-color: {Colors.TEXT_PRIMARY};
            }}

            QTableView::item {{
                padding: 6px;
                border: none;
            }}

            QTableView::item:hover {{
                background-color: {Colors.BG_HOVER};
            }}

            QTableView::item:selected {{
                background-color: {Colors.STATE_SELECTED_BG};
            }}

            QHeaderView::section {{
                background-color: {Colors.BG_ELEVATED};
                color: {Colors.TEXT_TERTIARY};
                padding: 8px 16px;
                border: none;
                border-bottom: 1px solid {Colors.BORDER_MEDIUM};
                border-right: 1px solid {Colors.BORDER_SUBTLE};
                font-weight: 700;
                font-size: 10px;
                text-transform: uppercase;
                letter-spacing: 0.8px;
            }}

            QHeaderView::section:hover {{
                background-color: {Colors.BG_HOVER};
                color: {Colors.TEXT_SECONDARY};
            }}

            QHeaderView::section:checked {{
                color: {Colors.ACCENT_BRIGHT};
            }}
        """

    @staticmethod
    def get_section_widget_style():
        """Style for section widgets."""
        return f"""
            QFrame {{
                background-color: {Colors.BG_ELEVATED};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: {Colors.RADIUS_XL};
                margin: 10px 12px;
                padding: 0px;
            }}
        """

    @staticmethod
    def get_panel_header_style():
        """Style for panel section headers."""
        return f"""
            background-color: {Colors.BG_SURFACE};
            border: none;
            border-bottom: 1px solid {Colors.BORDER_DEFAULT};
            border-radius: {Colors.RADIUS_XL} {Colors.RADIUS_XL} 0px 0px;
        """

    @staticmethod
    def get_panel_title_style():
        """Style for panel title text."""
        return f"""
            background-color: transparent;
            color: {Colors.ACCENT_PRIMARY};
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 1.2px;
        """

    @staticmethod
    def get_range_slider_style():
        """Enhanced style for range sliders."""
        return f"""
            QSlider::groove:horizontal {{
                height: 6px;
                background-color: {Colors.BG_SURFACE};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 3px;
            }}

            QSlider::handle:horizontal {{
                width: 16px;
                height: 16px;
                margin: -6px 0;
                background-color: {Colors.TEXT_PRIMARY};
                border: 2px solid {Colors.ACCENT_PRIMARY};
                border-radius: 9px;
            }}

            QSlider::handle:horizontal:hover {{
                background-color: {Colors.TEXT_PRIMARY};
                width: 18px;
                height: 18px;
                margin: -7px 0;
                border: 2px solid {Colors.ACCENT_BRIGHT};
                border-radius: 10px;
            }}

            QSlider::handle:horizontal:pressed {{
                background-color: {Colors.ACCENT_PRIMARY};
                border-color: {Colors.ACCENT_PRIMARY};
            }}

            QSlider::sub-page:horizontal {{
                background: {Colors.GRADIENT_ACCENT};
                border-radius: 3px;
            }}
        """

    @staticmethod
    def get_toolbar_style():
        """Style for horizontal toolbars."""
        return f"""
            QWidget#plotToolbar {{
                background-color: {Colors.BG_PANEL};
                border-bottom: 1px solid {Colors.BORDER_SUBTLE};
                padding: 6px 12px;
            }}

            QLabel {{
                color: {Colors.TEXT_TERTIARY};
                font-size: 10px;
                font-weight: 600;
                letter-spacing: 0.8px;
                padding: 0px 8px 0px 4px;
                background-color: transparent;
                border: none;
            }}

            QComboBox {{
                background-color: {Colors.BG_SURFACE};
                border: 1px solid {Colors.BORDER_MEDIUM};
                border-radius: {Colors.RADIUS_SM};
                padding: 4px 10px;
                font-size: 11px;
                min-width: 120px;
                min-height: 26px;
                color: {Colors.TEXT_PRIMARY};
                font-weight: 500;
            }}

            QComboBox:hover {{
                border-color: {Colors.BORDER_ACCENT};
                background-color: {Colors.BG_HOVER};
            }}

            QComboBox:focus {{
                border: 2px solid {Colors.ACCENT_PRIMARY};
                padding: 3px 9px;
            }}

            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: center right;
                border: none;
                background: transparent;
                width: 22px;
            }}

            QComboBox::down-arrow {{
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid {Colors.TEXT_TERTIARY};
                width: 0px;
                height: 0px;
            }}

            QComboBox::down-arrow:hover {{
                border-top-color: {Colors.ACCENT_PRIMARY};
            }}

            QComboBox QAbstractItemView {{
                background-color: {Colors.BG_ELEVATED};
                color: {Colors.TEXT_PRIMARY};
                selection-background-color: {Colors.ACCENT_PRIMARY};
                selection-color: {Colors.TEXT_INVERSE};
                border: 1px solid {Colors.BORDER_MEDIUM};
                border-radius: {Colors.RADIUS_SM};
                outline: none;
                padding: 6px;
            }}

            QComboBox QAbstractItemView::item {{
                padding: 8px 12px;
                border-radius: {Colors.RADIUS_XS};
                min-height: 28px;
            }}

            QComboBox QAbstractItemView::item:hover {{
                background-color: {Colors.BG_HOVER};
            }}

            /* Checkboxes */
            QCheckBox {{
                color: {Colors.TEXT_SECONDARY};
                font-size: 10px;
                font-weight: 500;
                spacing: 8px;
                background-color: transparent;
                padding: 4px 8px;
            }}

            QCheckBox:hover {{
                color: {Colors.TEXT_PRIMARY};
            }}

            QCheckBox::indicator {{
                width: 14px;
                height: 14px;
                background-color: {Colors.BG_SURFACE};
                border: 1.5px solid {Colors.BORDER_STRONG};
                border-radius: 4px;
            }}

            QCheckBox::indicator:hover {{
                border-color: {Colors.ACCENT_PRIMARY};
                background-color: {Colors.BG_HOVER};
            }}

            QCheckBox::indicator:checked {{
                background-color: {Colors.ACCENT_PRIMARY};
                border: 1.5px solid {Colors.ACCENT_PRIMARY};
                image: none;
            }}

            QCheckBox::indicator:checked:hover {{
                background-color: {Colors.ACCENT_HOVER};
                border-color: {Colors.ACCENT_HOVER};
            }}

            /* Buttons - compact toolbar style */
            QPushButton {{
                background-color: {Colors.BG_SURFACE};
                border: 1px solid {Colors.BORDER_MEDIUM};
                border-radius: {Colors.RADIUS_MD};
                padding: 5px 12px;
                font-size: 10px;
                font-weight: 600;
                color: {Colors.TEXT_SECONDARY};
                min-height: 26px;
            }}

            QPushButton:hover {{
                background-color: {Colors.ACCENT_GHOST};
                border-color: {Colors.BORDER_ACCENT};
                color: {Colors.TEXT_ACCENT};
            }}

            QPushButton:pressed {{
                background-color: {Colors.ACCENT_PRESSED};
                border-color: {Colors.ACCENT_PRESSED};
                color: {Colors.TEXT_PRIMARY};
            }}

            /* ToolButton */
            QToolButton {{
                background-color: {Colors.BG_SURFACE};
                border: 1px solid {Colors.BORDER_MEDIUM};
                border-radius: {Colors.RADIUS_MD};
                padding: 4px 10px;
                font-size: 10px;
                font-weight: 600;
                color: {Colors.TEXT_SECONDARY};
                min-width: 28px;
                min-height: 26px;
            }}

            QToolButton:hover {{
                background-color: {Colors.ACCENT_GHOST};
                border-color: {Colors.BORDER_ACCENT};
                color: {Colors.TEXT_ACCENT};
            }}

            QToolButton:pressed {{
                background-color: {Colors.ACCENT_PRESSED};
                border-color: {Colors.ACCENT_PRESSED};
                color: {Colors.TEXT_PRIMARY};
            }}

            QWidget {{
                background-color: transparent;
            }}
        """

    @staticmethod
    def get_sidebar_style():
        """Style for plot sidebar."""
        return f"""
            QWidget {{
                background-color: {Colors.BG_ELEVATED};
                border-right: 1px solid {Colors.BORDER_DEFAULT};
                border-left: 1px solid {Colors.BORDER_DEFAULT};
            }}
        """

    @staticmethod
    def get_header_bar_style():
        """Style for header bar."""
        return f"""
            QWidget#headerBar {{
                background: {Colors.GRADIENT_HEADER};
            }}
        """

    # ──────────────────────────────────────────────────
    #  NEW STYLES — Plot Area Concept Port
    # ──────────────────────────────────────────────────

    @staticmethod
    def get_table_base_style():
        """Shared QSS for BaseStyledTable (used by both data table and triangle table).
        Extracted from triangle_table.py inline QSS."""
        return f"""
            QTableView {{
                background-color: {Colors.BG_SURFACE};
                alternate-background-color: {Colors.BG_PANEL};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 8px;
                color: {Colors.TEXT_PRIMARY};
                font-size: 12px;
                gridline-color: transparent;
                outline: 0;
            }}
            QTableView::item {{
                padding: 4px 8px;
                border-bottom: 1px solid rgba(255, 255, 255, 0.03);
            }}
            QTableView::item:selected {{
                background-color: {Colors.OVERLAY_ACTIVE};
            }}
            QTableView::item:hover {{
                background-color: {Colors.BG_HOVER};
            }}
            QHeaderView::section {{
                background-color: {Colors.BG_ELEVATED};
                color: {Colors.TEXT_TERTIARY};
                border: none;
                border-bottom: 1px solid {Colors.BORDER_DEFAULT};
                padding: 8px 8px;
                font-size: 10px;
                font-weight: 700;
                text-transform: uppercase;
            }}
            QHeaderView::section:first {{
                border-top-left-radius: 8px;
            }}
            QHeaderView::section:last {{
                border-top-right-radius: 8px;
            }}
            QHeaderView::down-arrow {{
                image: none;
                width: 0;
            }}
            QHeaderView::up-arrow {{
                image: none;
                width: 0;
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 6px;
                margin: 0;
            }}
            QScrollBar::handle:vertical {{
                background: {Colors.BG_HOVER};
                border-radius: 3px;
                min-height: 20px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
            QScrollBar:horizontal {{
                height: 0;
            }}
        """

    @staticmethod
    def get_toolbar_compact_style():
        """Style for the redesigned 40px compact plot toolbar."""
        return f"""
            QWidget#plotToolbar {{
                background-color: {Colors.BG_PANEL};
                border-bottom: 1px solid {Colors.BORDER_DEFAULT};
                min-height: 46px;
                max-height: 46px;
            }}

            QComboBox {{
                background-color: {Colors.BG_SURFACE};
                border: 1px solid {Colors.BORDER_MEDIUM};
                border-radius: 6px;
                padding: 4px 10px;
                padding-right: 28px;
                font-size: 11px;
                color: {Colors.TEXT_PRIMARY};
                font-weight: 500;
            }}
            QComboBox:hover {{
                border-color: {Colors.ACCENT_PRIMARY};
            }}
            QComboBox:focus {{
                border-color: {Colors.ACCENT_PRIMARY};
            }}
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: center right;
                border: none;
                background: transparent;
                width: 24px;
            }}
            QComboBox::down-arrow {{
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid {Colors.TEXT_MUTED};
                width: 0; height: 0;
            }}
            QComboBox QAbstractItemView {{
                background-color: {Colors.BG_ELEVATED};
                color: {Colors.TEXT_PRIMARY};
                selection-background-color: {Colors.ACCENT_PRIMARY};
                selection-color: white;
                border: 1px solid {Colors.BORDER_MEDIUM};
                border-radius: 6px;
                padding: 4px;
                outline: none;
            }}
            QComboBox QAbstractItemView::item {{
                padding: 6px 10px;
                border-radius: 4px;
                min-height: 24px;
                background-color: {Colors.BG_ELEVATED};
            }}
            QComboBox QAbstractItemView::item:hover {{
                background-color: {Colors.BG_HOVER};
            }}

            QLabel {{
                color: {Colors.TEXT_TERTIARY};
                font-size: 10px;
                font-weight: 600;
                letter-spacing: 0.5px;
                background: transparent;
                border: none;
                padding: 0 4px;
            }}

            QToolButton {{
                background-color: transparent;
                border: 1px solid transparent;
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 10px;
                font-weight: 600;
                color: {Colors.TEXT_MUTED};
                min-width: 24px;
            }}
            QToolButton:hover {{
                background-color: {Colors.BG_HOVER};
                color: {Colors.TEXT_SECONDARY};
            }}
            QToolButton:checked {{
                background-color: {Colors.ACCENT_GHOST};
                color: {Colors.ACCENT_BRIGHT};
            }}

            QWidget#tbActionGroup {{
                background-color: {Colors.BG_WELL};
                border: 1px solid {Colors.BORDER_SUBTLE};
                border-radius: 8px;
            }}
            QWidget#tbActionGroup QToolButton {{
                min-width: 28px;
                max-width: 28px;
                min-height: 28px;
                max-height: 28px;
                padding: 0px;
                font-size: 13px;
                border-radius: 6px;
            }}
        """

    @staticmethod
    def get_drawer_header_style():
        """Style for drawer header bar (32px, with drag pill and mode toggle)."""
        return f"""
            QWidget#drawerHeader {{
                background-color: {Colors.BG_PANEL};
                border-top: 1px solid {Colors.BORDER_MEDIUM};
                min-height: 32px;
                max-height: 32px;
            }}
        """

    @staticmethod
    def get_settings_dialog_style():
        """Style for the PlotSettingsDialog."""
        return f"""
            QDialog {{
                background-color: {Colors.BG_MODAL};
            }}

            QLabel {{
                background: transparent;
                color: {Colors.TEXT_SECONDARY};
            }}

            QLabel#settingsTitle {{
                color: {Colors.TEXT_PRIMARY};
                font-size: 15px;
                font-weight: 700;
            }}
            QLabel#settingsSubtitle {{
                color: {Colors.TEXT_TERTIARY};
                font-size: 10px;
                font-weight: 500;
            }}

            QLineEdit {{
                background-color: {Colors.BG_SURFACE};
                color: {Colors.TEXT_PRIMARY};
                border: 1px solid {Colors.BORDER_MEDIUM};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 11px;
            }}
            QLineEdit:focus {{
                border-color: {Colors.ACCENT_PRIMARY};
            }}

            QSpinBox, QDoubleSpinBox {{
                background-color: {Colors.BG_SURFACE};
                color: {Colors.TEXT_PRIMARY};
                border: 1px solid {Colors.BORDER_MEDIUM};
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 11px;
            }}
            QSpinBox:focus, QDoubleSpinBox:focus {{
                border-color: {Colors.ACCENT_PRIMARY};
            }}

            QPushButton#settingsApply {{
                background-color: {Colors.ACCENT_PRIMARY};
                color: {Colors.TEXT_INVERSE};
                border: 1px solid {Colors.ACCENT_PRIMARY};
                border-radius: 6px;
                font-weight: 700;
                font-size: 11px;
                padding: 8px 20px;
            }}
            QPushButton#settingsApply:hover {{
                background-color: {Colors.ACCENT_HOVER};
            }}

            QPushButton#settingsCancel {{
                background-color: transparent;
                color: {Colors.TEXT_SECONDARY};
                border: 1px solid {Colors.BORDER_MEDIUM};
                border-radius: 6px;
                font-size: 11px;
                padding: 8px 16px;
            }}
            QPushButton#settingsCancel:hover {{
                border-color: {Colors.BORDER_STRONG};
                color: {Colors.TEXT_PRIMARY};
            }}

            QPushButton#settingsReset {{
                background-color: transparent;
                color: {Colors.ERROR};
                border: 1px solid {Colors.ERROR_BG};
                border-radius: 6px;
                font-size: 10px;
                padding: 6px 12px;
            }}
            QPushButton#settingsReset:hover {{
                background-color: {Colors.ERROR_BG};
            }}
        """

    @staticmethod
    def get_compass_style():
        """Style for the compass overlay widget (52px circle)."""
        return f"""
            QWidget#compassOverlay {{
                background: transparent;
            }}
        """

    @staticmethod
    def get_hint_bar_style():
        """Style for the floating hint bar pill at bottom of plot."""
        hint_bg = Colors.rgba(Colors.BG_DARK if Colors.is_dark() else Colors.BG_ELEVATED, 0.88 if Colors.is_dark() else 0.92)
        return f"""
            QWidget#hintBar {{
                background-color: {hint_bg};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 14px;
                min-height: 28px;
                max-height: 28px;
            }}
            QLabel {{
                color: {Colors.TEXT_TERTIARY};
                font-size: 10px;
                font-weight: 500;
                background: transparent;
                border: none;
            }}
            QToolButton#hintClose {{
                background: transparent;
                border: none;
                color: {Colors.TEXT_MUTED};
                font-size: 11px;
                padding: 2px;
                border-radius: 10px;
                min-width: 20px;
                max-width: 20px;
                min-height: 20px;
                max-height: 20px;
            }}
            QToolButton#hintClose:hover {{
                background-color: {Colors.BG_HOVER};
                color: {Colors.TEXT_PRIMARY};
            }}
        """

    @staticmethod
    def get_toggle_pill_group_style():
        """Style for the toggle pill group (Grid/Legend/Compass) in toolbar."""
        return f"""
            QWidget#togglePillGroup {{
                background-color: {Colors.BG_WELL};
                border: 1px solid {Colors.BORDER_SUBTLE};
                border-radius: 6px;
            }}
            QWidget#togglePillGroup QToolButton {{
                background-color: transparent;
                border: 1px solid transparent;
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 10px;
                font-weight: 600;
                color: {Colors.TEXT_MUTED};
            }}
            QWidget#togglePillGroup QToolButton:hover {{
                color: {Colors.TEXT_SECONDARY};
                background-color: {Colors.BG_HOVER};
            }}
            QWidget#togglePillGroup QToolButton:checked {{
                background-color: {Colors.ACCENT_GHOST};
                color: {Colors.ACCENT_BRIGHT};
                border-color: {Colors.BORDER_ACCENT};
            }}
        """
