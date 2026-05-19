"""
HeadAnalyser V2 - Header Bar with Toolbar
Top header with title and grouped toolbar icons.
"""

import os

from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QToolButton, QSpacerItem,
    QAbstractButton, QActionGroup, QMenu,
    QSizePolicy, QFrame
)
from PyQt5.QtCore import Qt, pyqtSignal, QSize
from PyQt5.QtGui import QPainter, QColor, QPainterPath, QLinearGradient, QPixmap

from styles.colors import Colors
from ui.icons import Icons, icon
from ui.scaling import build_screen_metrics
from ui.theme_utils import reset_widget_layout


# Map icon_type strings to Font Awesome icon names
TOOLBAR_ICON_MAP = {
    "open": Icons.OPEN,
    "save": Icons.SAVE,
    "export": Icons.EXPORT,
    "report": Icons.REPORT,
    "calc": Icons.CALC,
    "table": Icons.TABLE,
    "sensitivity": Icons.SENSITIVITY,
    "reset": Icons.RESET,
    "help": Icons.HELP,
    "theme": Icons.PALETTE,
    "win_min": Icons.WIN_MINIMIZE,
    "win_max": Icons.WIN_MAXIMIZE,
    "win_restore": Icons.WIN_RESTORE,
    "win_close": Icons.WIN_CLOSE,
}


class ToolbarButton(QToolButton):
    """Toolbar button with Font Awesome icons and semantic coloring."""

    def __init__(self, icon_type: str, tooltip: str, parent=None, metrics=None):
        super().__init__(parent)
        metrics = metrics or build_screen_metrics(parent)
        self.icon_type = icon_type
        self.setToolTip(tooltip)
        self.setFixedSize(metrics.header_button_width, metrics.header_button_height)
        self.setIconSize(QSize(metrics.header_icon_size, metrics.header_icon_size))
        self.setCursor(Qt.PointingHandCursor)
        self._hovered = False

        # Define colors based on purpose
        if icon_type in ("reset", "win_close"):
            # Destructive/Red theme
            self.col_idle = Colors.ERROR
            self.col_hover = Colors.ERROR_LIGHT if Colors.is_dark() else Colors.ERROR_DARK
            self.bg_hover = Colors.qcolor(Colors.ERROR_BG)
            self.col_pressed = Colors.TEXT_INVERSE
            self.grad_start = Colors.qcolor(Colors.ERROR_DARK)
            self.grad_end = Colors.qcolor(Colors.ERROR)
        else:
            # Standard/theme-aware accent colors
            self.col_idle = Colors.ACCENT_PRIMARY
            self.col_hover = Colors.ACCENT_BRIGHT if Colors.is_dark() else Colors.ACCENT_DARK
            self.bg_hover = Colors.qcolor(Colors.ACCENT_GHOST)
            self.col_pressed = Colors.TEXT_INVERSE
            self.grad_start = Colors.qcolor(Colors.ACCENT_PRESSED)
            self.grad_end = Colors.qcolor(Colors.ACCENT_PRIMARY)

        # Set the initial icon
        self._update_icon()

    def _update_icon(self):
        """Update the icon based on current state."""
        fa_icon = self._resolve_icon_name()
        if fa_icon:
            if self.isDown():
                color = self.col_pressed
            elif self._hovered:
                color = self.col_hover
            else:
                color = self.col_idle
            self.setIcon(icon(fa_icon, color=color))

    def _resolve_icon_name(self):
        return TOOLBAR_ICON_MAP.get(self.icon_type)

    def enterEvent(self, event):
        self._hovered = True
        self._update_icon()
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self._update_icon()
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self._update_icon()
        self.update()

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        self._update_icon()
        self.update()

    def paintEvent(self, event):
        # Draw background for hover/pressed states
        if self._hovered or self.isDown():
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            rect = self.rect()

            path = QPainterPath()
            path.addRoundedRect(rect.x(), rect.y(), rect.width(), rect.height(), 6, 6)

            if self.isDown():
                gradient = QLinearGradient(0, 0, rect.width(), 0)
                gradient.setColorAt(0, self.grad_start)
                gradient.setColorAt(1, self.grad_end)
                painter.fillPath(path, gradient)
            else:
                painter.fillPath(path, self.bg_hover)

            painter.end()

        # Let QToolButton draw the icon
        super().paintEvent(event)


class ButtonGroup(QWidget):
    """A subtle well/container that groups toolbar buttons."""

    def __init__(self, parent=None, metrics=None):
        super().__init__(parent)
        metrics = metrics or build_screen_metrics(parent)
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {Colors.BG_WELL};
                border: 1px solid {Colors.BORDER_SUBTLE};
                border-radius: 5px;
            }}
        """)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedHeight(metrics.header_group_height)

        self._layout = QHBoxLayout(self)
        # Zero vertical margins for compact look
        self._layout.setContentsMargins(1, 0, 1, 0)
        self._layout.setSpacing(1)

    def add_button(self, button):
        self._layout.addWidget(button)


class HeaderBar(QWidget):
    """Top header bar with title and grouped toolbar."""

    open_clicked = pyqtSignal()
    save_clicked = pyqtSignal()
    export_clicked = pyqtSignal()
    report_clicked = pyqtSignal()
    calc_clicked = pyqtSignal()
    table_clicked = pyqtSignal()
    sensitivity_clicked = pyqtSignal()
    reset_clicked = pyqtSignal()
    help_clicked = pyqtSignal()
    theme_selected = pyqtSignal(str)
    window_minimize_clicked = pyqtSignal()
    window_maximize_clicked = pyqtSignal()
    window_close_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._metrics = build_screen_metrics(parent)
        # Keep header near original height.
        self.setFixedHeight(self._metrics.header_height)
        self.setObjectName("headerBar")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._window_is_maximized = False
        self._manual_drag_active = False
        self._manual_drag_offset = None
        self._theme_menu = None
        self._theme_action_group = None

        self._setup_ui()

    def _setup_ui(self):
        metrics = self._metrics
        layout = QHBoxLayout(self)
        # Keep spacing tight so logo does not push toolbar groups.
        layout.setContentsMargins(12 if metrics.compact else 16, 0, 10 if metrics.compact else 12, 0)
        layout.setSpacing(5 if metrics.compact else 6)

        # Prominent app logo badge next to title.
        assets_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
        logo_candidates = [
            os.path.join(assets_dir, "logo_newest.png"),
            os.path.join(assets_dir, "headanalyser_logo.svg"),
            os.path.join(assets_dir, "logo_newest_clean.svg"),
            os.path.join(assets_dir, "logo_newest.svg"),
        ]
        logo_frame = QFrame()
        logo_frame.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        logo_frame.setStyleSheet(f"""
            background-color: {Colors.BG_WELL};
            border: 1px solid {Colors.BORDER_SUBTLE};
            border-radius: 7px;
        """)
        logo_frame.setFixedSize(metrics.header_logo_box_size, metrics.header_logo_box_size)
        logo_frame_layout = QHBoxLayout(logo_frame)
        logo_frame_layout.setContentsMargins(2, 2, 2, 2)
        logo_frame_layout.setSpacing(0)

        logo_label = QLabel()
        logo_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        logo_label.setStyleSheet("background: transparent; border: none;")
        for logo_path in logo_candidates:
            if not os.path.exists(logo_path):
                continue
            logo_pixmap = QPixmap(logo_path)
            if logo_pixmap.isNull():
                continue
            # Prevent very wide logos from stretching header width.
            if logo_pixmap.width() > int(logo_pixmap.height() * 1.2):
                side = min(logo_pixmap.width(), logo_pixmap.height())
                x = max(0, (logo_pixmap.width() - side) // 2)
                y = max(0, (logo_pixmap.height() - side) // 2)
                logo_pixmap = logo_pixmap.copy(x, y, side, side)
            logo_pixmap = logo_pixmap.scaled(
                metrics.header_logo_pixmap_size,
                metrics.header_logo_pixmap_size,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            logo_label.setPixmap(logo_pixmap)
            logo_label.setFixedSize(logo_pixmap.size())
            logo_frame_layout.addWidget(logo_label, 0, Qt.AlignCenter)
            layout.addWidget(logo_frame, 0, Qt.AlignVCenter)
            break

        # App title
        title = QLabel("HeadAnalyser")
        title.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        title.setStyleSheet(f"""
            background-color: transparent;
            color: {Colors.ACCENT_PRIMARY};
            font-size: {metrics.font_display}px;
            font-weight: 800;
            letter-spacing: -0.3px;
        """)
        layout.addWidget(title)

        # Spacer
        layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        # Separator (Scaled down height)
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setFrameShadow(QFrame.Plain)
        sep.setFixedWidth(1)
        sep.setFixedHeight(metrics.header_separator_height)
        sep.setStyleSheet(f"""
            background-color: {Colors.BORDER_MEDIUM};
            border-radius: 1px;
        """)
        layout.addWidget(sep)

        layout.addSpacing(6 if metrics.compact else 8)

        # File operations group
        file_group = ButtonGroup(metrics=self._metrics)
        self.btn_open = ToolbarButton("open", "Open File  (Ctrl+O)", metrics=self._metrics)
        self.btn_open.clicked.connect(self.open_clicked.emit)
        file_group.add_button(self.btn_open)

        self.btn_save = ToolbarButton("save", "Save  (Ctrl+S)", metrics=self._metrics)
        self.btn_save.clicked.connect(self.save_clicked.emit)
        file_group.add_button(self.btn_save)

        self.btn_export = ToolbarButton("export", "Export Plot  (Ctrl+E)", metrics=self._metrics)
        self.btn_export.clicked.connect(self.export_clicked.emit)
        file_group.add_button(self.btn_export)

        self.btn_report = ToolbarButton("report", "Generate PDF Report", metrics=self._metrics)
        self.btn_report.clicked.connect(self.report_clicked.emit)
        file_group.add_button(self.btn_report)

        layout.addWidget(file_group)

        layout.addSpacing(4 if metrics.compact else 6)

        # Analysis operations group
        analysis_group = ButtonGroup(metrics=self._metrics)
        self.btn_calc = ToolbarButton("calc", "Calculation Settings", metrics=self._metrics)
        self.btn_calc.clicked.connect(self.calc_clicked.emit)
        analysis_group.add_button(self.btn_calc)

        self.btn_table = ToolbarButton("table", "Open Attribute Table  (Ctrl+T)", metrics=self._metrics)
        self.btn_table.clicked.connect(self.table_clicked.emit)
        analysis_group.add_button(self.btn_table)

        self.btn_sensitivity = ToolbarButton("sensitivity", "Sensitivity Analysis", metrics=self._metrics)
        self.btn_sensitivity.clicked.connect(self.sensitivity_clicked.emit)
        analysis_group.add_button(self.btn_sensitivity)

        layout.addWidget(analysis_group)

        layout.addSpacing(4 if metrics.compact else 6)

        # Help group
        help_group = ButtonGroup(metrics=self._metrics)
        self.btn_help = ToolbarButton("help", "Help & Documentation", metrics=self._metrics)
        self.btn_help.clicked.connect(self.help_clicked.emit)
        help_group.add_button(self.btn_help)

        layout.addWidget(help_group)

        layout.addSpacing(4 if metrics.compact else 6)

        theme_group = ButtonGroup(metrics=self._metrics)
        self.btn_theme = ToolbarButton("theme", self._theme_tooltip(), metrics=self._metrics)
        self._build_theme_menu()
        self.btn_theme.clicked.connect(self._show_theme_menu)
        theme_group.add_button(self.btn_theme)
        layout.addWidget(theme_group)

        layout.addSpacing(4 if metrics.compact else 6)

        # Reset group
        reset_group = ButtonGroup(metrics=self._metrics)
        self.btn_reset = ToolbarButton("reset", "Reset Application", metrics=self._metrics)
        self.btn_reset.clicked.connect(self.reset_clicked.emit)
        reset_group.add_button(self.btn_reset)

        layout.addWidget(reset_group)
        layout.addSpacing(8 if metrics.compact else 10)

        self.window_button_group = ButtonGroup(metrics=self._metrics)
        self.btn_window_minimize = ToolbarButton("win_min", "Minimize", metrics=self._metrics)
        self.btn_window_minimize.clicked.connect(self.window_minimize_clicked.emit)
        self.window_button_group.add_button(self.btn_window_minimize)

        self.btn_window_maximize = ToolbarButton("win_max", "Maximize", metrics=self._metrics)
        self.btn_window_maximize.clicked.connect(self.window_maximize_clicked.emit)
        self.window_button_group.add_button(self.btn_window_maximize)

        self.btn_window_close = ToolbarButton("win_close", "Close", metrics=self._metrics)
        self.btn_window_close.clicked.connect(self.window_close_clicked.emit)
        self.window_button_group.add_button(self.btn_window_close)

        layout.addWidget(self.window_button_group)

    def _build_theme_menu(self):
        self._theme_menu = QMenu(self)
        self._theme_action_group = QActionGroup(self._theme_menu)
        self._theme_action_group.setExclusive(True)

        current_theme = Colors.current_theme()
        last_scheme = None
        for spec in Colors.theme_specs():
            scheme = str(spec.get("scheme") or "dark")
            if last_scheme is not None and scheme != last_scheme:
                self._theme_menu.addSeparator()
            label = str(spec.get("label") or spec.get("name") or "Theme")
            theme_name = str(spec.get("name") or "")
            action = self._theme_menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(theme_name == current_theme)
            action.triggered.connect(lambda checked=False, name=theme_name: self.theme_selected.emit(name))
            self._theme_action_group.addAction(action)
            last_scheme = scheme

    def _show_theme_menu(self):
        if self._theme_menu is None or not hasattr(self, "btn_theme"):
            return
        origin = self.btn_theme.mapToGlobal(self.btn_theme.rect().bottomLeft())
        self._theme_menu.exec_(origin)

    @staticmethod
    def _theme_tooltip() -> str:
        return f"Choose UI Theme (Current: {Colors.theme_label()})"

    def set_frameless_mode(self, enabled: bool):
        if hasattr(self, "window_button_group"):
            self.window_button_group.setVisible(bool(enabled))

    def set_maximized_state(self, is_maximized: bool):
        self._window_is_maximized = bool(is_maximized)
        if hasattr(self, "btn_window_maximize"):
            self.btn_window_maximize.icon_type = "win_restore" if is_maximized else "win_max"
            self.btn_window_maximize.setToolTip("Restore Down" if is_maximized else "Maximize")
            self.btn_window_maximize._update_icon()
            self.btn_window_maximize.update()

    def apply_theme(self):
        self._metrics = build_screen_metrics(self)
        self.setFixedHeight(self._metrics.header_height)
        reset_widget_layout(self)
        self._setup_ui()
        window = self.window()
        is_frameless = True
        if window is not None and hasattr(window, "_is_frameless_mode"):
            try:
                is_frameless = bool(window._is_frameless_mode())
            except Exception:
                is_frameless = True
        self.set_frameless_mode(is_frameless)
        self.set_maximized_state(self._window_is_maximized)

    def _is_drag_region(self, pos) -> bool:
        child = self.childAt(pos)
        while child is not None and child is not self:
            if isinstance(child, QAbstractButton):
                return False
            child = child.parentWidget()
        return True

    def _is_in_resize_margin(self, pos) -> bool:
        window = self.window()
        if window is None or not hasattr(window, "_is_frameless_mode"):
            return False
        try:
            if not window._is_frameless_mode():
                return False
        except Exception:
            return False

        global_pos = self.mapToGlobal(pos)
        win_pos = window.mapFromGlobal(global_pos)
        rect = window.rect()
        margin = max(2, int(getattr(window, "_chrome_resize_margin", 8)))
        top_margin = max(2, int(getattr(window, "_chrome_top_resize_margin", margin)))

        return (
            win_pos.x() <= margin
            or win_pos.x() >= rect.width() - margin
            or win_pos.y() <= top_margin
            or win_pos.y() >= rect.height() - margin
        )

    def _try_start_system_move(self) -> bool:
        window = self.window()
        if window is None or not hasattr(window, "_is_frameless_mode"):
            return False
        try:
            if not window._is_frameless_mode():
                return False
        except Exception:
            return False
        handle = window.windowHandle()
        if handle is None:
            return False
        try:
            return bool(handle.startSystemMove())
        except Exception:
            return False

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self._is_in_resize_margin(event.pos()):
            super().mousePressEvent(event)
            return
        if event.button() == Qt.LeftButton and self._is_drag_region(event.pos()):
            if self._try_start_system_move():
                event.accept()
                return
            window = self.window()
            if window is not None and hasattr(window, "_is_frameless_mode"):
                try:
                    is_frameless = bool(window._is_frameless_mode())
                    is_effectively_maximized = bool(
                        window.is_window_effectively_maximized()
                        if hasattr(window, "is_window_effectively_maximized")
                        else window.isMaximized()
                    )
                except Exception:
                    is_frameless = False
                    is_effectively_maximized = False
                if is_frameless and not is_effectively_maximized:
                    self._manual_drag_active = True
                    self._manual_drag_offset = event.globalPos() - window.pos()
                    event.accept()
                    return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton and self._is_in_resize_margin(event.pos()):
            super().mouseDoubleClickEvent(event)
            return
        if event.button() == Qt.LeftButton and self._is_drag_region(event.pos()):
            window = self.window()
            if window is not None and hasattr(window, "toggle_window_maximize"):
                window.toggle_window_maximize()
                event.accept()
                return
        super().mouseDoubleClickEvent(event)

    def mouseMoveEvent(self, event):
        if self._manual_drag_active and (event.buttons() & Qt.LeftButton):
            window = self.window()
            if window is not None and self._manual_drag_offset is not None:
                window.move(event.globalPos() - self._manual_drag_offset)
                event.accept()
                return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._manual_drag_active:
            self._manual_drag_active = False
            self._manual_drag_offset = None
            event.accept()
            return
        super().mouseReleaseEvent(event)
