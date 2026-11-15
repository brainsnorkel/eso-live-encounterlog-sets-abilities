"""
Startup log archiver: zip an oversized Encounter.log into a dated archive.

Safety model (log-archiving spec):
- ESO holds Encounter.log open for the whole game session, so archiving is
  attempted only at app startup (or via the manual "Archive now" action).
- The archiver opens the log with deny-all sharing (CreateFileW, dwShareMode=0)
  and holds that exclusive handle for the entire zip, so no process can write
  to (or even open) the log mid-archive. If exclusive access can't be acquired
  (ESO running), the archive is skipped with a notification.
- The zip is verified (testzip + exact size match) before success is reported.
- The original is kept unless delete_original is opted in; deletion happens
  through the still-held exclusive handle (delete-on-close), so there is no
  window for another process to write between verification and deletion.
- Linux has no deny-all sharing. There the archive is skipped when another
  process has the log open (a /proc scan at the start), and a log that grows
  during the zip fails the size verification, so the original is kept.
- macOS has neither deny-all sharing nor /proc. There lsof is asked who has
  the log open (holder_check): at the start, where a holder skips the
  archive, and again at the moment of an opted-in delete, which happens only
  on the answer "free" and straight after it. A game that has the log open and writes nothing
  while it is zipped passes the size verification, and deleting the log
  under it would lose the rest of the session: the delete succeeds and the
  game keeps writing to a file with no name.

Trigger model:
- Size-based: archive when the log has grown more than size_threshold_mb
  since the size recorded at the last archive (marker persisted in AppConfig).
  Default 1024 MB ~= five veteran trials (measured 100-300 MB per vet trial).
"""

import os
import subprocess
import sys
import time
import zipfile
from pathlib import Path
from typing import Optional

from app_config import AppConfig
from engine_events import ArchiveEvent, ListenerMixin
from log_freshness import derive_log_freshness

_CHUNK_SIZE = 4 * 1024 * 1024


class LogInUseError(Exception):
    """The log file is open in another process (ESO is running)."""


# holder_check's three answers
HELD = "held"
FREE = "free"
UNKNOWN = "unknown"

# Why an opted-in delete left the original (ArchiveEvent.kept_reason), as the
# status bar writes it after "original kept: "
KEPT_IN_USE = "the log is in use"
KEPT_UNKNOWN = "could not check whether the log is in use"
KEPT_NOT_DELETED = "the log could not be deleted"

_LSOF = "/usr/sbin/lsof"
_LSOF_TIMEOUT_S = 5


def holder_check(path: Path) -> str:
    """HELD, FREE or UNKNOWN: whether another process has *path* open, as
    `lsof -t +w -- path` tells it. macOS uses it; it is defined on every
    platform so that every platform's tests can run it.

    HELD: lsof names a process other than this one. FREE: lsof found none
    and said nothing else (exit 1 with both streams empty, measured on
    macOS 27 for a file nobody has open), or named this process only (exit 0;
    the app's own tail and the archive's own read handle do not count).
    UNKNOWN: anything else, including a missing lsof, a timeout and any
    message on stderr (a file it could not stat is one). Only FREE allows a
    delete, so an answer that cannot be read keeps the original.

    +w, because -t alone turns lsof's warnings off (its man page: "-t
    selects the -w option"): something lsof could not look into would then
    read as nobody having the log open. With +w it says so on stderr, and
    the answer is UNKNOWN.

    lsof sees the processes of the user who runs it, which is where the game
    is.
    """
    try:
        result = subprocess.run(
            [_LSOF, "-t", "+w", "--", str(path)], stdin=subprocess.DEVNULL,
            capture_output=True, text=True, errors="replace",
            timeout=_LSOF_TIMEOUT_S)
    except (OSError, subprocess.SubprocessError):
        return UNKNOWN
    lines = result.stdout.split()
    if not all(line.isdigit() for line in lines):
        return UNKNOWN
    own_pid = str(os.getpid())
    if any(pid != own_pid for pid in lines):
        return HELD
    if result.stderr.strip():
        return UNKNOWN
    if result.returncode == (0 if lines else 1):
        return FREE
    return UNKNOWN


if sys.platform == "win32":
    import ctypes
    import msvcrt
    from ctypes import wintypes

    _GENERIC_READ = 0x80000000
    _DELETE = 0x00010000
    _OPEN_EXISTING = 3
    _FILE_ATTRIBUTE_NORMAL = 0x80
    _INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value
    _ERROR_SHARING_VIOLATION = 32
    _FILE_DISPOSITION_INFO = 4

    class _FileDispositionInfo(ctypes.Structure):
        _fields_ = [("DeleteFile", wintypes.BOOLEAN)]

    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _kernel32.CreateFileW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
        wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    _kernel32.CreateFileW.restype = wintypes.HANDLE
    _kernel32.SetFileInformationByHandle.argtypes = [
        wintypes.HANDLE, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD]
    _kernel32.SetFileInformationByHandle.restype = wintypes.BOOL

    class _ExclusiveFile:
        """Read handle with deny-all sharing; can delete-on-close."""

        def __init__(self, path: Path):
            self._kernel32 = _kernel32
            handle = self._kernel32.CreateFileW(
                str(path), _GENERIC_READ | _DELETE,
                0,  # dwShareMode=0: deny all sharing
                None, _OPEN_EXISTING, _FILE_ATTRIBUTE_NORMAL, None)
            if handle is None or handle == _INVALID_HANDLE_VALUE:
                err = ctypes.get_last_error()
                if err == _ERROR_SHARING_VIOLATION:
                    raise LogInUseError(str(path))
                raise OSError(f"CreateFileW failed with error {err} for {path}")
            self._handle = handle
            # fdopen takes ownership: closing the file closes the handle.
            fd = msvcrt.open_osfhandle(handle, os.O_RDONLY)
            self.file = os.fdopen(fd, "rb")

        def mark_delete_on_close(self) -> bool:
            info = _FileDispositionInfo(True)
            ok = self._kernel32.SetFileInformationByHandle(
                wintypes.HANDLE(self._handle), _FILE_DISPOSITION_INFO,
                ctypes.byref(info), ctypes.sizeof(info))
            return bool(ok)

        def close(self) -> None:
            try:
                self.file.close()
            except OSError:
                pass

else:  # POSIX: no deny-all sharing; look for other holders, then size-verify
    def _held_by_another_process(path: Path) -> bool:
        """True when another process has *path* open (Linux /proc scan).

        ESO under Wine/Proton keeps the log open like it does on Windows.
        Matching is by device and inode, so it holds across mount namespaces
        (Flatpak). Processes we may not inspect are skipped; without /proc
        this is always False, which is why macOS asks holder_check instead.
        """
        try:
            target = os.stat(path)
        except OSError:
            return False
        try:
            pids = [name for name in os.listdir("/proc") if name.isdigit()]
        except OSError:
            return False
        own_pid = str(os.getpid())
        for pid in pids:
            if pid == own_pid:
                continue
            fd_dir = f"/proc/{pid}/fd"
            try:
                fds = os.listdir(fd_dir)
            except OSError:
                continue  # another user's process, or it just exited
            for fd in fds:
                try:
                    held = os.stat(f"{fd_dir}/{fd}")
                except OSError:
                    continue
                if (held.st_dev, held.st_ino) == (target.st_dev, target.st_ino):
                    return True
        return False

    class _ExclusiveFile:
        def __init__(self, path: Path):
            self._path = Path(path)
            # macOS: only a known holder skips the archive. An answer that
            # cannot be read lets the zip be made; the delete is where it
            # counts, and that asks again.
            if sys.platform == "darwin":
                held = holder_check(self._path) == HELD
            else:
                held = _held_by_another_process(self._path)
            if held:
                raise LogInUseError(str(path))
            self.file = open(path, "rb")
            self._delete = False
            self.kept_reason = ""  # why mark_delete_on_close said no

        def mark_delete_on_close(self) -> bool:
            """Delete the log when it is closed. On macOS, only when lsof
            says now that nobody else has it open: the check at the start is
            seconds or minutes old, and a game that opened the log since and
            has written nothing yet passes the size verification. There the
            log is removed here, straight after the answer, not at close():
            the config's save and the listeners run in between, and each
            moment is one in which the game could open the log."""
            if sys.platform == "darwin":
                answer = holder_check(self._path)
                if answer != FREE:
                    self.kept_reason = KEPT_IN_USE if answer == HELD else KEPT_UNKNOWN
                    return False
                try:
                    self._path.unlink()  # our own read handle stays good
                except OSError:
                    self.kept_reason = KEPT_NOT_DELETED
                    return False
                return True
            self._delete = True
            return True

        def close(self) -> None:
            try:
                self.file.close()
            finally:
                if self._delete:
                    try:
                        self._path.unlink()
                    except OSError:
                        pass


class LogArchiver(ListenerMixin):
    """Creates dated zip archives of the active encounter log."""

    def __init__(self, config: AppConfig):
        ListenerMixin.__init__(self)
        self.config = config

    # ---- trigger logic ----

    def growth_since_last_archive(self, log_path: Path) -> int:
        try:
            size = Path(log_path).stat().st_size
        except OSError:
            return 0
        marker = int(self.config.get("archive.size_at_last_archive", 0) or 0)
        if size < marker:
            # Log shrank or was replaced: reset the marker
            self.config.set("archive.size_at_last_archive", 0)
            self.config.save()
            marker = 0
        return size - marker

    def should_auto_archive(self, log_path: Path) -> bool:
        raw = self.config.get("archive.size_threshold_mb", 1024)
        threshold_mb = 1024 if raw is None else int(raw)
        return self.growth_since_last_archive(log_path) > threshold_mb * 1024 * 1024

    def auto_archive_if_needed(self, log_path: Path) -> Optional[Path]:
        """Startup entry point: archive when growth exceeds the threshold."""
        log_path = Path(log_path)
        if not log_path.exists() or not self.should_auto_archive(log_path):
            return None
        return self.archive(log_path)

    # ---- archive operation ----

    def _archive_target(self, log_path: Path) -> Path:
        status = derive_log_freshness(log_path)
        stamp_time = status.latest_entry_time or time.localtime()
        if hasattr(stamp_time, "strftime"):
            stamp = stamp_time.strftime("%y%m%d%H%M%S")
        else:
            stamp = time.strftime("%y%m%d%H%M%S", stamp_time)
        archive_dir = self.config.get("archive.dir") or log_path.parent
        archive_dir = Path(archive_dir)
        archive_dir.mkdir(parents=True, exist_ok=True)
        target = archive_dir / f"Encounter-{stamp}.zip"
        suffix = 1
        while target.exists():
            target = archive_dir / f"Encounter-{stamp}-{suffix}.zip"
            suffix += 1
        return target

    def archive(self, log_path: Path) -> Optional[Path]:
        """Zip the log into a dated archive. Returns the archive path or None.

        Emits ArchiveEvents throughout. Never raises for expected conditions
        (file in use, verification failure); those surface as events.
        """
        log_path = Path(log_path)
        if not log_path.exists():
            self._notify('on_archive_event', ArchiveEvent(
                kind="skipped", log_path=log_path, reason="log file not found"))
            return None

        # Derive the dated name before taking exclusive access (the freshness
        # scan opens the file itself and would hit our own deny-all sharing).
        try:
            planned_target = self._archive_target(log_path)
        except OSError as exc:
            self._notify('on_archive_event', ArchiveEvent(
                kind="skipped", log_path=log_path, reason=str(exc)))
            return None

        # In-use guard: exclusive access held for the whole operation
        try:
            source = _ExclusiveFile(log_path)
        except LogInUseError:
            self._notify('on_archive_event', ArchiveEvent(
                kind="skipped", log_path=log_path,
                reason="Encounter.log is in use (is ESO running?); "
                       "close ESO and use Archive now, or restart this app"))
            return None
        except OSError as exc:
            self._notify('on_archive_event', ArchiveEvent(
                kind="skipped", log_path=log_path, reason=str(exc)))
            return None

        archive_path = None
        partial_path = None
        try:
            total = log_path.stat().st_size
            archive_path = planned_target
            # Write to a .partial name and rename only after verification:
            # an interrupted run (app killed mid-zip) must never leave a
            # plausible-looking .zip behind.
            partial_path = archive_path.with_name(archive_path.name + ".partial")
            self._notify('on_archive_event', ArchiveEvent(
                kind="started", log_path=log_path, archive_path=archive_path,
                total_bytes=total))

            done = 0
            with zipfile.ZipFile(partial_path, "w", zipfile.ZIP_DEFLATED,
                                 allowZip64=True) as zf:
                info = zipfile.ZipInfo(log_path.name,
                                       date_time=time.localtime()[:6])
                info.compress_type = zipfile.ZIP_DEFLATED
                with zf.open(info, "w", force_zip64=True) as dest:
                    while True:
                        chunk = source.file.read(_CHUNK_SIZE)
                        if not chunk:
                            break
                        dest.write(chunk)
                        done += len(chunk)
                        self._notify('on_archive_event', ArchiveEvent(
                            kind="progress", log_path=log_path,
                            archive_path=archive_path,
                            done_bytes=done, total_bytes=total))

            # Verify: zip integrity plus exact size match against the source
            if not self._verify(partial_path, log_path.name, total):
                try:
                    partial_path.unlink()
                except OSError:
                    pass
                self._notify('on_archive_event', ArchiveEvent(
                    kind="failed", log_path=log_path, archive_path=archive_path,
                    reason="archive verification failed; original kept"))
                return None

            # Verified: give the archive its final name
            partial_path.replace(archive_path)
            partial_path = None

            # Original file: kept unless deletion was opted in. Deletion goes
            # through the exclusive handle (delete-on-close): no other process
            # can touch the file between verification and deletion.
            deleted = False
            kept_reason = ""
            if bool(self.config.get("archive.delete_original", False)):
                deleted = source.mark_delete_on_close()
                if not deleted:
                    # Only the POSIX handle gives a reason (the macOS check)
                    kept_reason = getattr(source, "kept_reason", "")

            self.config.set("archive.size_at_last_archive",
                            0 if deleted else total)
            self.config.save()

            self._notify('on_archive_event', ArchiveEvent(
                kind="completed", log_path=log_path, archive_path=archive_path,
                done_bytes=total, total_bytes=total, original_deleted=deleted,
                kept_reason=kept_reason))
            return archive_path

        except Exception as exc:
            if partial_path is not None:
                try:
                    partial_path.unlink()
                except OSError:
                    pass
            self._notify('on_archive_event', ArchiveEvent(
                kind="failed", log_path=log_path, archive_path=archive_path,
                reason=f"{type(exc).__name__}: {exc}"))
            return None
        finally:
            source.close()

    @staticmethod
    def _verify(archive_path: Path, member_name: str, expected_size: int) -> bool:
        try:
            with zipfile.ZipFile(archive_path) as zf:
                if zf.testzip() is not None:
                    return False
                return zf.getinfo(member_name).file_size == expected_size
        except (OSError, KeyError, zipfile.BadZipFile):
            return False
