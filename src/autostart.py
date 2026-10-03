"""
Start-at-login toggle (Windows).

Uses the per-user Run registry key (HKCU\\Software\\Microsoft\\Windows\\
CurrentVersion\\Run) - no administrator rights, and the value survives
in-place upgrades because the installed exe path is stable. The registry is
the single source of truth; nothing is mirrored into the app config.

On non-Windows platforms every call is a harmless no-op.
"""

import os
import sys
from pathlib import Path
from typing import Optional

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "ESO Log Tail"

_INSTALLED_EXE = (Path(os.environ.get("LOCALAPPDATA", ""))
                  / "Programs" / "ESO Log Tail" / "esolog-gui.exe")


def autostart_command() -> Optional[str]:
    """Command to launch at login, or None when unavailable.

    Frozen (installed/portable) builds use their own executable; a dev
    checkout points at the installed copy when one exists, since a
    python-script invocation is not a sensible login command.
    """
    if sys.platform != "win32":
        return None
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    if _INSTALLED_EXE.exists():
        return f'"{_INSTALLED_EXE}"'
    return None


def is_enabled(value_name: str = VALUE_NAME) -> bool:
    if sys.platform != "win32":
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, value_name)
        return True
    except OSError:
        return False


def set_enabled(enabled: bool, value_name: str = VALUE_NAME,
                command: Optional[str] = None) -> bool:
    """Add or remove the login-start entry. Returns True on success."""
    if sys.platform != "win32":
        return False
    import winreg
    try:
        if enabled:
            command = command or autostart_command()
            if not command:
                return False
            # CreateKeyEx: fresh profiles may not have the Run key yet
            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0,
                                    winreg.KEY_SET_VALUE) as key:
                winreg.SetValueEx(key, value_name, 0, winreg.REG_SZ, command)
        else:
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0,
                                    winreg.KEY_SET_VALUE) as key:
                    winreg.DeleteValue(key, value_name)
            except FileNotFoundError:
                pass  # key or value absent: already disabled
        return True
    except OSError:
        return False
