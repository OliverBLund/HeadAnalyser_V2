"""Window chrome mode resolution helpers."""

from __future__ import annotations

import os
from typing import Optional


_NATIVE_VALUES = {"native", "system", "default"}
_FRAMELESS_VALUES = {"frameless", "custom", "none"}


def normalize_chrome_mode(raw_mode: str | None) -> Optional[str]:
    mode = str(raw_mode or "").strip().lower()
    if mode in _NATIVE_VALUES:
        return "native"
    if mode in _FRAMELESS_VALUES:
        return "frameless"
    return None


def resolve_window_chrome_mode(
    default_windows: str = "native",
    default_other: str = "native",
    **_ignored,
) -> str:
    """
    Resolve window chrome mode from fixed defaults.
    """
    normalized_windows = normalize_chrome_mode(default_windows) or "frameless"
    normalized_other = normalize_chrome_mode(default_other) or "native"
    return normalized_windows if os.name == "nt" else normalized_other
