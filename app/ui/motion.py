"""Respect the Windows accessibility preference without an additional dependency."""
import sys


def system_motion_enabled():
    if sys.platform == 'win32':
        import ctypes
        from ctypes import wintypes
        enabled = wintypes.BOOL()
        if ctypes.windll.user32.SystemParametersInfoW(0x1042, 0, ctypes.byref(enabled), 0):
            return bool(enabled.value)
    return True
