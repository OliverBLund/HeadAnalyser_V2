"""
HeadAnalyser V2 - Shared UI Widgets
SectionHeader, ToggleSwitch, _TogglePill, CollapsibleSection,
CardSection, ToggleRow, CompactTogglePill.
Extracted from properties_panel.py and plot_sidebar.py so every panel
can import the same building blocks.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QSizePolicy, QPushButton, QToolButton, QGraphicsDropShadowEffect,
)
from PyQt5.QtCore import Qt, pyqtSignal, QSize, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QPainter, QPen

from styles.colors import Colors
from ui.icons import icon, Icons
from ui.scaling import build_screen_metrics


# ────────────────────────────────────────────────────────
# SectionHeader  (line + label pattern)
# ────────────────────────────────────────────────────────

class SectionHeader(QWidget):
    """Section header using the 'line + label' pattern.

    A left-aligned label in accent color with uppercase lettering
    and a horizontal line extending to the right. Optionally includes
    a Font Awesome icon before the label.
    """

    def __init__(self, title: str, icon_name: str = None, parent=None):
        super().__init__(parent)
        metrics = build_screen_metrics(self)
        icon_size = 10 if metrics.compact else 12

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 10 if metrics.compact else 12, 0, 4)
        header_layout.setSpacing(5 if metrics.compact else 6)

        # Optional icon
        if icon_name:
            icon_label = QLabel()
            icon_label.setPixmap(icon(icon_name, color=Colors.ACCENT_PRIMARY).pixmap(QSize(icon_size, icon_size)))
            icon_label.setFixedSize(icon_size, icon_size)
            icon_label.setStyleSheet("background-color: transparent;")
            header_layout.addWidget(icon_label)

        label = QLabel(title.upper())
        label.setStyleSheet(f"""
            color: {Colors.ACCENT_PRIMARY};
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 1.5px;
            background-color: transparent;
            padding: 0px;
        """)
        header_layout.addWidget(label)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFixedHeight(1)
        line.setStyleSheet(f"background-color: {Colors.BORDER_MEDIUM}; border: none; max-height: 1px;")
        line.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        header_layout.addWidget(line)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(4 if metrics.compact else 5)
        outer.addLayout(header_layout)

        self._content_layout = QVBoxLayout()
        self._content_layout.setContentsMargins(0, 4, 0, 8)
        self._content_layout.setSpacing(8 if metrics.compact else 10)
        outer.addLayout(self._content_layout)

    def contentLayout(self):
        """Return the layout where child widgets should be added."""
        return self._content_layout


# ────────────────────────────────────────────────────────
# ToggleSwitch + _TogglePill
# ────────────────────────────────────────────────────────

class _TogglePill(QPushButton):
    """A compact on/off pill button with a drawn knob."""

    def __init__(self, parent=None):
        super().__init__(parent)
        metrics = build_screen_metrics(self)
        self.setCheckable(True)
        self.setFixedSize(40 if metrics.compact else 44, 22 if metrics.compact else 24)
        self.setCursor(Qt.PointingHandCursor)
        self._hovered = False
        self.setText("")
        self.setFocusPolicy(Qt.NoFocus)

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        return super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.update()
        return super().leaveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.rect().adjusted(1, 1, -1, -1)
        radius = rect.height() / 2.0

        on = self.isChecked()
        if on:
            bg = Colors.qcolor(Colors.ACCENT_PRESSED)
            border_color = Colors.qcolor(Colors.ACCENT_PRIMARY)
        else:
            bg = Colors.qcolor(Colors.BG_HOVER)
            border_color = Colors.qcolor(Colors.BORDER_MEDIUM)

        if self.isDown():
            bg = bg.darker(115)
        elif self._hovered:
            bg = bg.lighter(110)

        painter.setBrush(bg)
        painter.setPen(QPen(border_color, 1))
        painter.drawRoundedRect(rect, radius, radius)

        # Knob
        knob_d = rect.height() - 6
        y = rect.y() + (rect.height() - knob_d) / 2.0
        x = rect.x() + 3 if not on else rect.right() - 3 - knob_d
        painter.setBrush(Colors.qcolor(Colors.BG_ELEVATED))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(int(x), int(y), int(knob_d), int(knob_d))


class ToggleSwitch(QWidget):
    """Custom toggle switch widget with label."""

    toggled = pyqtSignal(bool)

    def __init__(self, label_text: str, parent=None):
        super().__init__(parent)
        metrics = build_screen_metrics(self)
        self._checked = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 6 if metrics.compact else 8, 0, 6 if metrics.compact else 8)
        layout.setSpacing(10 if metrics.compact else 12)

        self.label = QLabel(label_text)
        self.label.setStyleSheet(f"""
            color: {Colors.TEXT_PRIMARY};
            font-size: 11px;
            font-weight: 500;
        """)
        layout.addWidget(self.label)
        layout.addStretch()

        self.toggle_btn = _TogglePill(self)
        self.toggle_btn.setChecked(False)
        self.toggle_btn.toggled.connect(self._on_toggled)
        layout.addWidget(self.toggle_btn)

    def _on_toggled(self, checked: bool):
        self._checked = bool(checked)
        self.toggled.emit(self._checked)

    def setChecked(self, checked: bool):
        self._checked = checked
        self.toggle_btn.setChecked(bool(checked))

    def isChecked(self) -> bool:
        return self._checked


# ────────────────────────────────────────────────────────
# CollapsibleSection
# ────────────────────────────────────────────────────────

class CollapsibleSection(QWidget):
    """Collapsible section with header and content area."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.is_expanded = True
        self._title = title

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Header button
        self.toggle_button = QToolButton()
        self._update_header_text()
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(True)
        self.toggle_button.setStyleSheet(f"""
            QToolButton {{
                background-color: {Colors.BG_SURFACE};
                color: {Colors.TEXT_PRIMARY};
                border: none;
                border-bottom: 1px solid {Colors.BORDER_SUBTLE};
                padding: 8px 12px;
                text-align: left;
                font-size: 10px;
                font-weight: 600;
                letter-spacing: 0.3px;
            }}
            QToolButton:hover {{
                background-color: {Colors.BG_HOVER};
            }}
        """)
        self.toggle_button.clicked.connect(self.toggle_section)
        main_layout.addWidget(self.toggle_button)

        # Content area
        self.content_area = QWidget()
        self.content_layout = QVBoxLayout(self.content_area)
        self.content_layout.setContentsMargins(12, 8, 12, 8)
        self.content_layout.setSpacing(6)
        main_layout.addWidget(self.content_area)

    def toggle_section(self):
        self.is_expanded = self.toggle_button.isChecked()
        self.content_area.setVisible(self.is_expanded)
        self._update_header_text()

    def _update_header_text(self):
        arrow = "\u25BC" if self.is_expanded else "\u25B6"
        self.toggle_button.setText(f"{arrow}  {self._title}")

    def add_widget(self, widget):
        self.content_layout.addWidget(widget)

    def add_layout(self, layout):
        self.content_layout.addLayout(layout)


# ────────────────────────────────────────────────────────
# CompactTogglePill (smaller version for card sections)
# ────────────────────────────────────────────────────────

class CompactTogglePill(QPushButton):
    """A compact on/off pill button - smaller than _TogglePill."""

    def __init__(self, parent=None):
        super().__init__(parent)
        metrics = build_screen_metrics(self)
        self.setCheckable(True)
        self.setFixedSize(30 if metrics.compact else 32, 16 if metrics.compact else 18)
        self.setCursor(Qt.PointingHandCursor)
        self._hovered = False
        self.setText("")
        self.setFocusPolicy(Qt.NoFocus)

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        return super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.update()
        return super().leaveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.rect().adjusted(1, 1, -1, -1)
        radius = rect.height() / 2.0

        on = self.isChecked()
        if on:
            bg = Colors.qcolor(Colors.ACCENT_GHOST)
            border_color = Colors.qcolor(Colors.ACCENT_PRESSED)
        else:
            bg = Colors.qcolor(Colors.BG_WELL)
            border_color = Colors.qcolor(Colors.BORDER_MEDIUM)

        if self.isDown():
            bg = bg.darker(115)
        elif self._hovered:
            bg = bg.lighter(110)

        painter.setBrush(bg)
        painter.setPen(QPen(border_color, 1))
        painter.drawRoundedRect(rect, radius, radius)

        # Knob
        knob_d = rect.height() - 4
        y = rect.y() + (rect.height() - knob_d) / 2.0
        if on:
            x = rect.right() - 2 - knob_d
            knob_color = Colors.qcolor(Colors.ACCENT_PRIMARY)
        else:
            x = rect.x() + 2
            knob_color = Colors.qcolor(Colors.TEXT_MUTED)

        painter.setBrush(knob_color)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(int(x), int(y), int(knob_d), int(knob_d))


# ────────────────────────────────────────────────────────
# ToggleRow (compact row for card sections)
# ────────────────────────────────────────────────────────

class ToggleRow(QWidget):
    """Compact toggle row with optional icon and sub-option support."""

    toggled = pyqtSignal(bool)

    def __init__(self, label_text: str, icon_name: str = None, is_sub: bool = False, parent=None):
        super().__init__(parent)
        metrics = build_screen_metrics(self)
        self._checked = False
        self._is_sub = is_sub
        self._sub_options_widget = None

        layout = QHBoxLayout(self)
        base_margin = 5 if metrics.compact else 6
        sub_margin = 3 if metrics.compact else 4
        layout.setContentsMargins(0, sub_margin if is_sub else base_margin, 0, sub_margin if is_sub else base_margin)
        layout.setSpacing(5 if metrics.compact else 6)

        # Icon (optional)
        if icon_name:
            icon_label = QLabel()
            icon_edge = 10 if (is_sub or metrics.compact) else 12
            icon_box = 12 if metrics.compact else 14
            icon_label.setPixmap(icon(icon_name, color=Colors.TEXT_MUTED).pixmap(QSize(icon_edge, icon_edge)))
            icon_label.setFixedSize(icon_box, icon_box)
            icon_label.setAlignment(Qt.AlignCenter)
            icon_label.setStyleSheet("background-color: transparent;")
            layout.addWidget(icon_label)

        # Label
        self.label = QLabel(label_text)
        font_size = "10px" if is_sub else "11px"
        color = Colors.TEXT_MUTED if is_sub else Colors.TEXT_SECONDARY
        self.label.setStyleSheet(f"""
            color: {color};
            font-size: {font_size};
            font-weight: 500;
            background-color: transparent;
        """)
        layout.addWidget(self.label)
        layout.addStretch()

        # Toggle
        self.toggle_btn = CompactTogglePill(self)
        self.toggle_btn.setChecked(False)
        self.toggle_btn.toggled.connect(self._on_toggled)
        layout.addWidget(self.toggle_btn)

    def _on_toggled(self, checked: bool):
        self._checked = bool(checked)
        self.toggled.emit(self._checked)
        # Show/hide sub-options
        if self._sub_options_widget:
            self._sub_options_widget.setVisible(self._checked)

    def setChecked(self, checked: bool):
        self._checked = checked
        self.toggle_btn.setChecked(bool(checked))
        if self._sub_options_widget:
            self._sub_options_widget.setVisible(self._checked)

    def isChecked(self) -> bool:
        return self._checked

    def setSubOptionsWidget(self, widget):
        """Set a widget to show/hide based on toggle state."""
        self._sub_options_widget = widget
        widget.setVisible(self._checked)


class SubOptionsContainer(QWidget):
    """Container for sub-options with left border indent."""

    def __init__(self, parent=None):
        super().__init__(parent)
        metrics = build_screen_metrics(self)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(16 if metrics.compact else 20, 0, 0, 4)
        self._layout.setSpacing(0)

        # Visual left border
        self.setStyleSheet(f"""
            SubOptionsContainer {{
                border-left: 2px solid {Colors.BORDER_MEDIUM};
                margin-left: {16 if metrics.compact else 20}px;
                padding-left: {8 if metrics.compact else 10}px;
            }}
        """)

    def addWidget(self, widget):
        self._layout.addWidget(widget)

    def layout(self):
        return self._layout


# ────────────────────────────────────────────────────────
# CardSection (modern collapsible card)
# ────────────────────────────────────────────────────────

class CardSection(QWidget):
    """Modern card-style collapsible section with colored icon box."""

    def __init__(self, title: str, icon_name: str = None, icon_color: str = None, parent=None):
        super().__init__(parent)
        metrics = build_screen_metrics(self)
        self.is_expanded = True
        self._title = title
        self._icon_name = icon_name
        self._icon_color = icon_color or Colors.ACCENT_PRIMARY

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Card container
        self._card = QFrame()
        self._card.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.BG_SURFACE};
                border: 1px solid {Colors.BORDER_SUBTLE};
                border-radius: 8px;
            }}
        """)
        card_layout = QVBoxLayout(self._card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        # Header (clickable)
        self._header = QWidget()
        self._header.setCursor(Qt.PointingHandCursor)
        self._header.mousePressEvent = lambda e: self.toggle_section()
        header_layout = QHBoxLayout(self._header)
        header_layout.setContentsMargins(10 if metrics.compact else 12, 8 if metrics.compact else 10, 10 if metrics.compact else 12, 8 if metrics.compact else 10)
        header_layout.setSpacing(6 if metrics.compact else 8)

        # Icon box
        if icon_name:
            icon_box = QFrame()
            icon_box_size = 18 if metrics.compact else 20
            icon_box.setFixedSize(icon_box_size, icon_box_size)
            # Determine background color based on icon_color
            bg_color = self._get_icon_bg_color()
            icon_box.setStyleSheet(f"""
                QFrame {{
                    background-color: {bg_color};
                    border-radius: 5px;
                    border: none;
                }}
            """)
            icon_box_layout = QHBoxLayout(icon_box)
            icon_box_layout.setContentsMargins(0, 0, 0, 0)
            icon_lbl = QLabel()
            icon_edge = 9 if metrics.compact else 10
            icon_lbl.setPixmap(icon(icon_name, color=self._icon_color).pixmap(QSize(icon_edge, icon_edge)))
            icon_lbl.setAlignment(Qt.AlignCenter)
            icon_lbl.setStyleSheet("background-color: transparent;")
            icon_box_layout.addWidget(icon_lbl)
            header_layout.addWidget(icon_box)

        # Title
        title_label = QLabel(title.upper())
        title_label.setStyleSheet(f"""
            color: {Colors.TEXT_SECONDARY};
            font-size: 11px;
            font-weight: 600;
            letter-spacing: 0.5px;
            background-color: transparent;
        """)
        header_layout.addWidget(title_label)
        header_layout.addStretch()

        # Chevron
        self._chevron = QLabel()
        self._update_chevron()
        self._chevron.setStyleSheet(f"color: {Colors.TEXT_MUTED}; background-color: transparent;")
        header_layout.addWidget(self._chevron)

        # Hover effect for header
        self._header.setStyleSheet(f"""
            QWidget {{
                background-color: transparent;
                border: none;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
            }}
            QWidget:hover {{
                background-color: {Colors.BG_HOVER};
            }}
        """)

        card_layout.addWidget(self._header)

        # Content body
        self._body = QWidget()
        self._body.setObjectName("cardBody")
        self._body_layout = QVBoxLayout(self._body)
        self._body_layout.setContentsMargins(10 if metrics.compact else 12, 8 if metrics.compact else 8, 10 if metrics.compact else 12, 10 if metrics.compact else 12)
        self._body_layout.setSpacing(0)
        self._body.setStyleSheet(f"""
            QWidget#cardBody {{
                background-color: transparent;
                border-top: 1px solid {Colors.BORDER_SUBTLE};
            }}
            QWidget#cardBody QLabel {{
                background-color: transparent;
                border: none;
            }}
            QWidget#cardBody QWidget {{
                background-color: transparent;
                border: none;
            }}
        """)
        card_layout.addWidget(self._body)

        main_layout.addWidget(self._card)

    def _get_icon_bg_color(self):
        """Get a semi-transparent background color based on icon color."""
        return Colors.tint_surface(self._icon_color or Colors.ACCENT_PRIMARY)

    def _update_chevron(self):
        chevron_icon = Icons.CHEVRON_DOWN if self.is_expanded else Icons.CHEVRON_RIGHT
        self._chevron.setPixmap(icon(chevron_icon, color=Colors.TEXT_MUTED).pixmap(QSize(10, 10)))

    def toggle_section(self):
        self.is_expanded = not self.is_expanded
        self._body.setVisible(self.is_expanded)
        self._update_chevron()

    def addWidget(self, widget):
        """Add a widget to the section body."""
        self._body_layout.addWidget(widget)

    def addLayout(self, layout):
        """Add a layout to the section body."""
        self._body_layout.addLayout(layout)

    def addToggleRow(self, label: str, icon_name: str = None, checked: bool = False) -> ToggleRow:
        """Add a toggle row and return it for signal connection."""
        row = ToggleRow(label, icon_name=icon_name, parent=self)
        row.setChecked(checked)
        self._body_layout.addWidget(row)
        return row

    def addSeparator(self):
        """Add a subtle separator line."""
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background-color: {Colors.BORDER_SUBTLE}; border: none;")
        self._body_layout.addWidget(sep)
