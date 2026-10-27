"""
Moving a file to the Recycle Bin (the trash on Linux and macOS), never
deleting it outright (issue #87).

Why not send2trash on Windows. Both its Windows backends ask the shell to
delete with "allow undo" and "no confirmation". When the Recycle Bin cannot
take a file (a network or removable drive, the bin turned off for the
drive, a file larger than the bin's limit), Windows then deletes it
outright without a word; its pywin32 backend's progress sink returns
E_FAIL in that case, but its own comment says the delete goes ahead. So on
Windows this module:

1. Checks the bin can take the file: a fixed local drive, no
   NoRecycleFiles policy, the drive's bin not set to delete at once
   (NukeOnDelete), and the file no larger than the drive's bin limit
   (MaxCapacity in MB, under HKCU\\...\\Explorer\\BitBucket\\Volume\\{guid};
   a RecycleBinSize policy, a percentage of the drive, wins; a drive with
   neither gets Windows' default of 5%). A file that fails the check is
   left where it is and reported.
2. Asks the shell (SHFileOperationW) with FOF_WANTNUKEWARNING as well, so
   should the check ever be wrong, Windows asks before deleting outright
   rather than doing it.

Elsewhere send2trash moves the file to the freedesktop trash (Linux) or the
Finder's (macOS); both fail rather than delete outright when there is no
trash for the file.
"""

import sys
from pathlib import Path

TRASH_NAME = "Recycle Bin" if sys.platform == "win32" else "trash"


class TrashUnavailable(OSError):
    """The file could not go to the Recycle Bin; it is still where it was."""


if sys.platform == "win32":
    import ctypes
    import winreg
    from ctypes import wintypes

    _DRIVE_FIXED = 3
    _FO_DELETE = 3
    _FOF_SILENT = 0x0004
    _FOF_NOCONFIRMATION = 0x0010
    _FOF_ALLOWUNDO = 0x0040
    _FOF_NOERRORUI = 0x0400
    _FOF_WANTNUKEWARNING = 0x4000
    _DEFAULT_PERCENT = 5
    _BITBUCKET = r"Software\Microsoft\Windows\CurrentVersion\Explorer\BitBucket\Volume"
    _POLICIES = r"Software\Microsoft\Windows\CurrentVersion\Policies\Explorer"

    class _SHFileOpStruct(ctypes.Structure):
        _fields_ = [
            ("hwnd", wintypes.HWND),
            ("wFunc", wintypes.UINT),
            ("pFrom", wintypes.LPCWSTR),
            ("pTo", wintypes.LPCWSTR),
            ("fFlags", ctypes.c_ushort),
            ("fAnyOperationsAborted", wintypes.BOOL),
            ("hNameMappings", ctypes.c_void_p),
            ("lpszProgressTitle", wintypes.LPCWSTR),
        ]

    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _shell32 = ctypes.WinDLL("shell32")
    _kernel32.GetVolumePathNameW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
    _kernel32.GetVolumePathNameW.restype = wintypes.BOOL
    _kernel32.GetVolumeNameForVolumeMountPointW.argtypes = [
        wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
    _kernel32.GetVolumeNameForVolumeMountPointW.restype = wintypes.BOOL
    _kernel32.GetDriveTypeW.argtypes = [wintypes.LPCWSTR]
    _kernel32.GetDriveTypeW.restype = wintypes.UINT
    _kernel32.GetDiskFreeSpaceExW.argtypes = [
        wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_ulonglong),
        ctypes.POINTER(ctypes.c_ulonglong), ctypes.POINTER(ctypes.c_ulonglong)]
    _kernel32.GetDiskFreeSpaceExW.restype = wintypes.BOOL
    _shell32.SHFileOperationW.argtypes = [ctypes.POINTER(_SHFileOpStruct)]
    _shell32.SHFileOperationW.restype = ctypes.c_int

    def _registry_value(root, key: str, name: str):
        try:
            with winreg.OpenKey(root, key) as handle:
                return winreg.QueryValueEx(handle, name)[0]
        except OSError:
            return None

    def _policy(name: str):
        for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            value = _registry_value(root, _POLICIES, name)
            if value is not None:
                return value
        return None

    def _volume_root(path: Path) -> str:
        buffer = ctypes.create_unicode_buffer(1024)
        if not _kernel32.GetVolumePathNameW(str(path), buffer, len(buffer)):
            raise TrashUnavailable(f"no drive for {path}")
        return buffer.value

    def _volume_guid(root: str):
        buffer = ctypes.create_unicode_buffer(1024)
        if not _kernel32.GetVolumeNameForVolumeMountPointW(root, buffer, len(buffer)):
            return None
        name = buffer.value  # \\?\Volume{guid}\
        start, end = name.find("{"), name.find("}")
        return name[start:end + 1] if start != -1 and end > start else None

    def _drive_size(root: str) -> int:
        total = ctypes.c_ulonglong(0)
        if not _kernel32.GetDiskFreeSpaceExW(root, None, ctypes.byref(total), None):
            return 0
        return total.value

    def refusal(path: Path, size: int):
        """Why the Recycle Bin would not take *path* (*size* bytes), or None."""
        root = _volume_root(path)
        if _kernel32.GetDriveTypeW(root) != _DRIVE_FIXED:
            return "not on a fixed local drive, which has no Recycle Bin"
        if _policy("NoRecycleFiles") == 1:
            return "the Recycle Bin is turned off by policy"
        guid = _volume_guid(root)
        key = f"{_BITBUCKET}\\{guid}" if guid else None
        if key and _registry_value(winreg.HKEY_CURRENT_USER, key, "NukeOnDelete") == 1:
            return f"the Recycle Bin is set to delete at once on {root}"
        percent = _policy("RecycleBinSize")
        capacity_mb = None if percent is not None or not key else _registry_value(
            winreg.HKEY_CURRENT_USER, key, "MaxCapacity")
        if capacity_mb is not None:
            limit = int(capacity_mb) * 1024 * 1024
        else:
            share = _DEFAULT_PERCENT if percent is None else int(percent)
            limit = _drive_size(root) * share // 100
        if limit and size > limit:
            return f"larger than the Recycle Bin's limit on {root}"
        return None

    def move_to_trash(path: Path) -> None:
        path = Path(path).resolve()
        try:
            size = path.stat().st_size
        except OSError as exc:
            raise TrashUnavailable(str(exc)) from exc
        reason = refusal(path, size)
        if reason:
            raise TrashUnavailable(reason)
        op = _SHFileOpStruct()
        op.wFunc = _FO_DELETE
        op.pFrom = str(path) + "\0"  # the field is a list ending in an empty string
        op.fFlags = (_FOF_ALLOWUNDO | _FOF_NOCONFIRMATION | _FOF_WANTNUKEWARNING
                     | _FOF_SILENT | _FOF_NOERRORUI)
        result = _shell32.SHFileOperationW(ctypes.byref(op))
        if result or op.fAnyOperationsAborted:
            raise TrashUnavailable(f"the shell refused (code {result:#x})")
        if path.exists():
            raise TrashUnavailable("the file is still there")

else:
    def refusal(path: Path, size: int):
        return None

    def move_to_trash(path: Path) -> None:
        try:
            from send2trash import send2trash
        except ImportError as exc:
            raise TrashUnavailable("send2trash is not installed") from exc
        try:
            send2trash(str(path))
        except OSError as exc:
            raise TrashUnavailable(str(exc)) from exc
