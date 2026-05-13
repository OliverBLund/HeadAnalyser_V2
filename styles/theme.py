"""Qt palette helpers for the active application theme."""

from PyQt5.QtGui import QColor, QPalette

from .colors import Colors


def build_qpalette() -> QPalette:
    """Build a QPalette that roughly matches the active stylesheet theme."""
    palette = QPalette()

    window = QColor(Colors.BG_PANEL)
    base = QColor(Colors.BG_SURFACE)
    alt_base = QColor(Colors.BG_DARK)
    text = QColor(Colors.TEXT_PRIMARY)
    button = QColor(Colors.BG_SURFACE)
    button_text = QColor(Colors.TEXT_PRIMARY)
    tooltip_base = QColor(Colors.BG_ELEVATED)
    tooltip_text = QColor(Colors.TEXT_PRIMARY)
    highlight = QColor(Colors.ACCENT_PRIMARY)
    highlighted_text = QColor(Colors.TEXT_INVERSE)
    placeholder = QColor(Colors.TEXT_MUTED)
    disabled_text = QColor(Colors.STATE_DISABLED_TEXT)
    disabled_bg = QColor(Colors.STATE_DISABLED_BG)

    palette.setColor(QPalette.Window, window)
    palette.setColor(QPalette.WindowText, text)
    palette.setColor(QPalette.Base, base)
    palette.setColor(QPalette.AlternateBase, alt_base)
    palette.setColor(QPalette.Text, text)
    palette.setColor(QPalette.Button, button)
    palette.setColor(QPalette.ButtonText, button_text)
    palette.setColor(QPalette.ToolTipBase, tooltip_base)
    palette.setColor(QPalette.ToolTipText, tooltip_text)
    palette.setColor(QPalette.Highlight, highlight)
    palette.setColor(QPalette.HighlightedText, highlighted_text)
    palette.setColor(QPalette.PlaceholderText, placeholder)
    palette.setColor(QPalette.Link, highlight)
    palette.setColor(QPalette.LinkVisited, QColor(Colors.ACCENT_PRESSED))

    palette.setColor(QPalette.Disabled, QPalette.Text, disabled_text)
    palette.setColor(QPalette.Disabled, QPalette.WindowText, disabled_text)
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, disabled_text)
    palette.setColor(QPalette.Disabled, QPalette.Base, disabled_bg)
    palette.setColor(QPalette.Disabled, QPalette.Button, disabled_bg)

    return palette

