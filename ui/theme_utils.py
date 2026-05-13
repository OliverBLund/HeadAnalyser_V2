"""Helpers for rebuilding widgets when the active theme changes."""

from PyQt5.QtWidgets import QLayout, QWidget


def clear_layout(layout: QLayout) -> None:
    """Delete all child widgets/layouts from a layout tree."""
    if layout is None:
        return
    while layout.count():
        item = layout.takeAt(0)
        child_widget = item.widget()
        child_layout = item.layout()
        if child_layout is not None:
            clear_layout(child_layout)
            child_layout.deleteLater()
        if child_widget is not None:
            child_widget.deleteLater()


def reset_widget_layout(widget: QWidget) -> None:
    """Remove the current layout from a widget so a fresh one can be installed."""
    if widget is None:
        return
    layout = widget.layout()
    if layout is None:
        return
    clear_layout(layout)
    holder = QWidget()
    holder.setLayout(layout)
    holder.deleteLater()
