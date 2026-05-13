"""
HeadAnalyser V2 - Navigation Sidebar
Left sidebar with distinct colored icons and left-edge active indicator.
"""

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QSpacerItem, QSizePolicy, QFrame
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPainter, QColor, QPen, QPainterPath

from styles.colors import Colors
from ui.theme_utils import reset_widget_layout

# Icon color mapping
ICON_COLORS = {
    "plot": {"active": "#60a5fa", "glow": "rgba(96, 165, 250, 0.08)"},
    "map": {"active": "#4ade80", "glow": "rgba(74, 222, 128, 0.08)"},
    "stats": {"active": "#fbbf24", "glow": "rgba(251, 191, 36, 0.08)"},
}


class NavButton(QPushButton):
    """Navigation button with distinct color and left-edge active indicator."""

    def __init__(self, icon_type: str, text: str, parent=None):
        super().__init__(parent)
        self.icon_type = icon_type
        self.setText("")
        self.setToolTip(text)
        self._active = False
        self._hovered = False
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(52, 48)
        self.setCheckable(True)
        self._icon_color = ICON_COLORS.get(icon_type, ICON_COLORS["plot"])
        self._update_style()

    def _update_style(self):
        active_color = self._icon_color["active"]
        glow_bg = self._icon_color["glow"]

        if self._active:
            self.setStyleSheet(f"""
                QPushButton {{
                    background: {glow_bg};
                    border: none;
                    border-left: 3px solid {active_color};
                    border-radius: 0px 10px 10px 0px;
                    margin: 4px 8px 4px 0px;
                    padding-left: 5px;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    border: none;
                    border-left: 3px solid transparent;
                    border-radius: 0px 10px 10px 0px;
                    margin: 4px 8px 4px 0px;
                    padding-left: 5px;
                }}
                QPushButton:hover {{
                    background-color: {Colors.BG_SURFACE};
                }}
            """)

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def set_active(self, active: bool):
        self._active = active
        self.setChecked(active)
        self._update_style()
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        # Icon color based on state
        active_color = self._icon_color["active"]
        if self._active:
            color = QColor(active_color)
        elif self._hovered:
            color = QColor(active_color)
            color.setAlpha(160)
        else:
            color = QColor(Colors.TEXT_MUTED)

        pen = QPen(color, 2.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)

        # Offset slightly right to account for left border
        ix, iy = 27, 24
        s = 10

        if self.icon_type == "plot":
            # Chart icon
            painter.drawRect(int(ix - s), int(iy - s), int(s * 2), int(s * 2))
            painter.drawLine(int(ix - s + 4), int(iy + 4), int(ix - 2), int(iy - 4))
            painter.drawLine(int(ix - 2), int(iy - 4), int(ix + 4), int(iy + 2))
            painter.drawLine(int(ix + 4), int(iy + 2), int(ix + s - 3), int(iy - s + 4))

        elif self.icon_type == "map":
            # Map pin icon
            r = 3
            painter.drawEllipse(int(ix - r), int(iy - s + 2), int(r * 2), int(r * 2))
            # Pin body
            path = QPainterPath()
            path.moveTo(ix - s * 0.5, iy - s * 0.3)
            path.quadTo(ix, iy + s * 0.8, ix + s * 0.5, iy - s * 0.3)
            painter.drawPath(path)
            # Map frame
            painter.drawRect(int(ix - s), int(iy - s + 1), int(s * 2), int(s * 2 - 2))

        elif self.icon_type == "stats":
            # Bar chart icon
            bar_w = 5
            painter.drawRect(int(ix - 8), int(iy + 1), bar_w, 9)
            painter.drawRect(int(ix - 2), int(iy - 6), bar_w, 16)
            painter.drawRect(int(ix + 4), int(iy - 2), bar_w, 12)


class NavigationSidebar(QWidget):
    """Left navigation sidebar with colored icon buttons."""

    page_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(68)
        self.setObjectName("navigationSidebar")
        self.setAttribute(Qt.WA_StyledBackground, True)

        self.buttons = {}
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 16, 0, 16)
        layout.setSpacing(4)

        pages = [
            ("plot", "Plot"),
            ("map", "Map"),
            ("stats", "Statistics"),
        ]

        for icon_type, text in pages:
            btn = NavButton(icon_type, text)
            btn.clicked.connect(lambda checked, p=icon_type: self._on_page_clicked(p))
            self.buttons[icon_type] = btn
            layout.addWidget(btn)

        layout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))

        self.set_active_page("plot")

    def _on_page_clicked(self, page: str):
        self.set_active_page(page)
        self.page_changed.emit(page)

    def set_active_page(self, page: str):
        for key, btn in self.buttons.items():
            btn.set_active(key == page)

    def apply_theme(self):
        active_page = next((key for key, btn in self.buttons.items() if btn.isChecked()), "plot")
        reset_widget_layout(self)
        self.buttons = {}
        self._setup_ui()
        self.set_active_page(active_page)
