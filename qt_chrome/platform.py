"""Platform-specific window chrome helpers."""

from __future__ import annotations

import os


def _window_hwnd(window) -> int:
    if os.name != "nt" or window is None:
        return 0
    handle = window.windowHandle()
    if handle is None:
        return 0
    try:
        return int(handle.winId())
    except Exception:
        return 0


def enable_windows_soft_corners(window) -> None:
    """Best-effort rounded window corners on Windows 11."""
    try:
        import ctypes

        hwnd = _window_hwnd(window)
        if not hwnd:
            return

        DWMWA_WINDOW_CORNER_PREFERENCE = 33
        DWMWCP_ROUND = 2
        preference = ctypes.c_int(DWMWCP_ROUND)

        dwmapi = ctypes.WinDLL("dwmapi", use_last_error=True)
        dwmapi.DwmSetWindowAttribute(
            ctypes.c_void_p(hwnd),
            ctypes.c_uint(DWMWA_WINDOW_CORNER_PREFERENCE),
            ctypes.byref(preference),
            ctypes.sizeof(preference),
        )
    except Exception:
        pass


def enable_windows_frameless_snap_styles(window) -> None:
    """Best-effort Win32 styles to restore snap behavior for frameless windows."""
    try:
        import ctypes

        hwnd = _window_hwnd(window)
        if not hwnd:
            return

        GWL_STYLE = -16
        SWP_NOMOVE = 0x0002
        SWP_NOSIZE = 0x0001
        SWP_NOZORDER = 0x0004
        SWP_NOACTIVATE = 0x0010
        SWP_FRAMECHANGED = 0x0020

        WS_THICKFRAME = 0x00040000
        WS_MAXIMIZEBOX = 0x00010000
        WS_MINIMIZEBOX = 0x00020000
        WS_SYSMENU = 0x00080000

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        get_style = user32.GetWindowLongPtrW
        set_style = user32.SetWindowLongPtrW
        set_pos = user32.SetWindowPos

        get_style.argtypes = [ctypes.c_void_p, ctypes.c_int]
        get_style.restype = ctypes.c_ssize_t
        set_style.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_ssize_t]
        set_style.restype = ctypes.c_ssize_t
        set_pos.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_uint,
        ]
        set_pos.restype = ctypes.c_bool

        style = int(get_style(ctypes.c_void_p(hwnd), GWL_STYLE))
        if not style:
            return

        target_style = style | WS_THICKFRAME | WS_MAXIMIZEBOX | WS_MINIMIZEBOX | WS_SYSMENU
        if target_style == style:
            return

        set_style(ctypes.c_void_p(hwnd), GWL_STYLE, ctypes.c_ssize_t(target_style))
        set_pos(
            ctypes.c_void_p(hwnd),
            None,
            0,
            0,
            0,
            0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED,
        )
    except Exception:
        pass

