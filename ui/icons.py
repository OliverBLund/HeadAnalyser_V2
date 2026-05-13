"""
HeadAnalyser V2 - Icon System

Centralized icon management using QtAwesome (Font Awesome 6).
Provides consistent, high-quality icons throughout the application.

Usage:
    from ui.icons import icon, Icons

    # Get an icon with default styling
    button.setIcon(icon(Icons.SAVE))

    # Get an icon with custom color
    button.setIcon(icon(Icons.EXPORT, color='#ff0000'))

    # Get an icon with multiple state colors
    button.setIcon(icon(Icons.CALC, color='#818cf8', color_active='#ffffff'))
"""

import qtawesome as qta
from PyQt5.QtGui import QIcon
from styles.colors import Colors


class Icons:
    """
    Icon name constants using Font Awesome 6.

    Naming: fa6s = solid, fa6 = regular, fa6b = brands
    Browse available icons: run `qta-browser` in terminal
    """

    # File operations
    OPEN = "fa6s.folder-open"
    SAVE = "fa6s.floppy-disk"
    EXPORT = "fa6s.file-export"
    REPORT = "fa6s.file-lines"

    # Analysis / Tools
    CALC = "fa6s.sliders"
    TABLE = "fa6s.table"
    SENSITIVITY = "fa6s.flask"
    RESET = "fa6s.arrow-rotate-left"
    HELP = "fa6s.circle-question"

    # Window controls
    WIN_MINIMIZE = "fa6s.minus"
    WIN_MAXIMIZE = "fa6s.square"
    WIN_RESTORE = "fa6s.window-restore"
    WIN_CLOSE = "fa6s.xmark"

    # Map / Navigation
    TRANSECT = "fa6s.route"
    MEASURE = "fa6s.ruler"
    ADD_POINT = "fa6s.location-crosshairs"
    LAYERS = "fa6s.layer-group"
    GEOLOGY = "fa6s.mountain"

    # General UI
    SETTINGS = "fa6s.gear"
    FILTER = "fa6s.filter"
    SEARCH = "fa6s.magnifying-glass"
    PLUS = "fa6s.plus"
    MINUS = "fa6s.minus"
    CHECK = "fa6s.check"
    TIMES = "fa6s.xmark"
    CHEVRON_DOWN = "fa6s.chevron-down"
    CHEVRON_RIGHT = "fa6s.chevron-right"
    CHEVRON_LEFT = "fa6s.chevron-left"
    CHEVRON_UP = "fa6s.chevron-up"
    BARS = "fa6s.bars"
    GRID = "fa6s.table-cells"
    LIST = "fa6s.list"
    MOON = "fa6s.moon"
    SUN = "fa6s.sun"
    CHART_LINE = "fa6s.chart-line"
    SLIDERS = "fa6s.sliders"
    EYE = "fa6s.eye"

    # Plot types
    PLOT_2D = "fa6s.chart-scatter"  # Note: may need "fa6s.circle" as fallback
    PLOT_3D = "fa6s.cube"
    PLOT_VECTORS = "fa6s.arrow-trend-up"
    PLOT_HISTOGRAM = "fa6s.chart-column"
    PLOT_ROSE = "fa6s.compass"
    PLOT_CROSSSECTION = "fa6s.chart-area"

    # Data / Status
    WARNING = "fa6s.triangle-exclamation"
    ERROR = "fa6s.circle-exclamation"
    INFO = "fa6s.circle-info"
    SUCCESS = "fa6s.circle-check"

    # Misc
    DOWNLOAD = "fa6s.download"
    UPLOAD = "fa6s.upload"
    COPY = "fa6s.copy"
    TRASH = "fa6s.trash"
    EDIT = "fa6s.pen"
    EYE_SLASH = "fa6s.eye-slash"
    LOCK = "fa6s.lock"
    UNLOCK = "fa6s.lock-open"
    CLOSE = "fa6s.xmark"

    # Settings dialog specific
    HEADING = "fa6s.heading"
    TEXT_HEIGHT = "fa6s.text-height"
    BORDER_ALL = "fa6s.border-all"
    PALETTE = "fa6s.palette"


def icon(
    name: str,
    color: str = None,
    color_hover: str = None,
    color_active: str = None,
    color_disabled: str = None,
    scale_factor: float = 1.0,
) -> QIcon:
    """
    Get a QIcon from Font Awesome with app theming.

    Args:
        name: Icon name (use Icons.* constants or FA6 names like 'fa6s.star')
        color: Normal state color (default: Colors.TEXT_SECONDARY)
        color_hover: Hover state color (optional, for QToolButton)
        color_active: Active/pressed state color (optional)
        color_disabled: Disabled state color (default: Colors.TEXT_MUTED)
        scale_factor: Scale the icon (default 1.0)

    Returns:
        QIcon ready for use with setIcon()
    """
    options = {
        "color": color or Colors.TEXT_SECONDARY,
        "scale_factor": scale_factor,
    }

    if color_active:
        options["color_active"] = color_active
    if color_disabled:
        options["color_disabled"] = color_disabled or Colors.TEXT_MUTED

    return qta.icon(name, **options)


def toolbar_icon(name: str, destructive: bool = False) -> QIcon:
    """
    Get a toolbar-styled icon with appropriate coloring.

    Args:
        name: Icon name from Icons class
        destructive: If True, uses error/red coloring (for reset, delete, close)

    Returns:
        QIcon with toolbar styling
    """
    if destructive:
        return icon(
            name,
            color=Colors.ERROR,
            color_active="#ffffff",
        )
    else:
        return icon(
            name,
            color=Colors.ACCENT_PRIMARY,
            color_active="#0f0f12",
        )


def nav_icon(name: str, active: bool = False) -> QIcon:
    """
    Get a navigation sidebar icon.

    Args:
        name: Icon name from Icons class
        active: Whether this nav item is currently active

    Returns:
        QIcon with navigation styling
    """
    if active:
        return icon(name, color=Colors.ACCENT_PRIMARY)
    else:
        return icon(name, color=Colors.TEXT_MUTED)
