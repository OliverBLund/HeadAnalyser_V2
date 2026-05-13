"""Point-label JS helpers for MapWidget.

This module isolates label-specific runtime snippets so label behavior can be
maintained/tested independently from other map concerns.
"""

import json


def build_point_label_contract_js(*, labels_visible: bool) -> str:
    """Return JS that defines the shared point-label visibility contract."""
    visible_js = str(bool(labels_visible)).lower()
    return (
        f"window.__pointLabelsVisible = {visible_js};"
        "window.__applyPointLabelVisibility = function(){"
        "try{"
        "var visible = !!window.__pointLabelsVisible;"
        "document.querySelectorAll('.point-id-label').forEach(function(el){"
        "el.style.display = visible ? 'block' : 'none';"
        "});"
        "}catch(err){}"
        "};"
    )


def build_apply_points_visibility_js(*, show_points: bool, show_excluded: bool, labels_on: bool) -> str:
    """Return JS for point/excluded/label DOM visibility updates."""
    show_points_js = str(bool(show_points)).lower()
    show_excluded_js = str(bool(show_excluded)).lower()
    labels_on_js = str(bool(labels_on)).lower()
    return (
        "(function(){"
        f"var showPoints = {show_points_js};"
        f"var showExcluded = {show_excluded_js};"
        f"var labelsOn = {labels_on_js};"
        "window.__pointLabelsVisible = !!(showPoints && labelsOn);"
        "var active = document.querySelectorAll('.point-marker.active');"
        "var excluded = document.querySelectorAll('.point-marker.excluded');"
        "var labels = document.querySelectorAll('.point-id-label');"
        "active.forEach(function(el){ el.style.display = showPoints ? '' : 'none'; });"
        "excluded.forEach(function(el){ el.style.display = showExcluded ? '' : 'none'; });"
        "labels.forEach(function(el){ el.style.display = (showPoints && labelsOn) ? 'block' : 'none'; });"
        "})();"
    )


def build_set_labels_visibility_js(*, visible: bool) -> str:
    """Return JS for direct label toggle updates."""
    visible_js = json.dumps(bool(visible))
    return (
        "(function(){"
        f"var visible = {visible_js};"
        "window.__pointLabelsVisible = visible;"
        "document.querySelectorAll('.point-id-label').forEach(function(el){"
        "el.style.display = visible ? 'block' : 'none';"
        "});"
        "})();"
    )

