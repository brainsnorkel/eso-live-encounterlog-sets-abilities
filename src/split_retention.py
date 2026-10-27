"""
Split log retention: zip split logs older than N weeks (issue #86) and
move those older than M weeks to the Recycle Bin (issue #87).

Which files. Only the splitter's own names are touched:
``YYMMDDHHMMSS-<Zone-Name>[-vet][-N].log`` and the same with ``.zip``
added. The split folder defaults to the log's folder, which also holds
Encounter.log and the archiver's ``Encounter-*.zip``, and Chris's split
folder holds ``*-report.txt`` files another tool writes; none of those
match. ``-temp.log`` (a split still waiting for its zone) never matches,
subfolders are never entered, and symbolic links are skipped. That makes a
``keep`` folder inside the split folder a place where nothing is ever
zipped; the job creates it so it is there to use.

How old. A split's age runs from the later of the session stamp in its name
and its modification time. On the 899 splits in Chris's folder
(2026-10-27), 433 had a modification time more than two days off their
stamp, because the splitter wrote some sessions out again long after they
were played (issue #85). The later of the two never makes a file look older
than it is, and a session that stays open for days, with an old stamp and a
file still growing, stays young.

The latest session. The split of the live log's newest session (its last
BEGIN_LOG) is never touched: it may be the file the splitter has open, and
it is the one session the app replays at every start, so deleting its
split would only have it written out again. The newest session in the
folder is spared too: it is almost always the same one, and Settings can
find it without reading the log, so its preview counts what a run does.

Deleting (issue #87) moves files to the Recycle Bin (recycle_bin), never
deletes outright; a file the bin cannot take is left and reported. M must
be more than N while zipping is on, so a split is zipped before it can be
deleted; settings_from_config holds to that even for a hand-edited config.
A run deletes first and zips what is left, since zipping a file about to
be deleted is wasted work. Settings asks before saving a change that
deletes: turning it on, lowering M, or pointing it at another folder; the
daily run deletes only within what was confirmed and asks nothing.

Zipped splits are still splits. ``<stem>.log.zip`` holds one member,
``<stem>.log``, so the original name stays visible and a ``*.zip`` pattern
cannot mix it up with the archives. The splitter's checks for "this session
already has a split" (LogSplitter._scan_existing_splits and
LogFileMonitor._session_split_exists) accept the zipped form, indexed by
the member's size; without that, zipping the newest split of someone who
had not played for N weeks would have it written out again at the next
start, and zipped again under a ``-1`` name.

Writing safely, as the log archiver does: the zip is written to
``.partial``, read back in full (CRC and size), given its final name, and
only then is the log removed, so an interrupted run leaves the log or a
verified zip, never neither. A ``.partial`` left by an interrupted run is
removed at the start of the next. The zip and its member keep the log's
modification time. A zip of the same name that already exists is either
the same log (the log is then removed as a copy) or a different one (the
log is left and reported).

What it saves. Deflate at level 6 brings a split to about 6% of its size
(a 95 MB Hel Ra split to 6.0 MB in 1.0 s, a 573 MB Dreadsail split to
34.8 MB in 5.7 s, both read back in under 2 s). On a folder Windows
already compresses (Chris's: 105 GB stored in 32 GB) the saving is
smaller: about 26 GB there rather than 92.

When. At startup and once a day while the app is open, on a thread of its
own (RetentionRunner), one file at a time with a check for cancel between
chunks: the first run over a large folder takes minutes, and the engine
thread that polls the live log must not wait for it.
"""

import os
import re
import threading
import time
import zipfile
import zlib
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

ZIP_SUFFIX = ".log.zip"
PARTIAL_SUFFIX = ".partial"
KEEP_FOLDER = "keep"
WEEK_SECONDS = 7 * 24 * 3600

_STAMP_FORMAT = "%y%m%d%H%M%S"
_NAME = re.compile(r"^(\d{12})-(.+)\.log(\.zip)?$")
_PARTIAL = re.compile(r"^\d{12}-.+\.log\.zip\.partial$")
_CHUNK_SIZE = 4 * 1024 * 1024
# How far back the newest BEGIN_LOG is looked for (the monitor's own cap)
_LATEST_SESSION_LOOKBACK = 2 * 1024 * 1024 * 1024


class Cancelled(Exception):
    """The run was asked to stop."""


@dataclass(frozen=True)
class SplitFile:
    """One of the splitter's files, plain or zipped."""
    path: Path
    stamp: str          # YYMMDDHHMMSS, the session's BEGIN_LOG
    zone: str           # "Dreadsail Reef"
    vet: bool
    zipped: bool
    size: int           # bytes on disk
    reference: float    # epoch seconds the age runs from

    def older_than(self, weeks: int, now: float) -> bool:
        return now - self.reference > weeks * WEEK_SECONDS


def parse_split_name(name: str):
    """(stamp, zone, vet, zipped) for a splitter file name, else None."""
    match = _NAME.match(name)
    if match is None or name.endswith("-temp.log"):
        return None
    stamp, rest, zipped = match.group(1), match.group(2), bool(match.group(3))
    try:
        datetime.strptime(stamp, _STAMP_FORMAT)
    except ValueError:
        return None
    rest = re.sub(r"-\d+$", "", rest)
    vet = rest.endswith("-vet")
    if vet:
        rest = rest[:-len("-vet")]
    return stamp, rest.replace("-", " "), vet, zipped


def scan_splits(split_dir: Path) -> list[SplitFile]:
    """The splitter's files directly in *split_dir* (never a subfolder)."""
    found = []
    try:
        with os.scandir(split_dir) as it:
            for entry in it:
                parsed = parse_split_name(entry.name)
                if parsed is None:
                    continue
                try:
                    if entry.is_symlink() or not entry.is_file():
                        continue
                    stat = entry.stat()
                except OSError:
                    continue
                stamp, zone, vet, zipped = parsed
                stamp_time = datetime.strptime(stamp, _STAMP_FORMAT).timestamp()
                found.append(SplitFile(
                    path=Path(entry.path), stamp=stamp, zone=zone, vet=vet, zipped=zipped,
                    size=stat.st_size, reference=max(stamp_time, stat.st_mtime)))
    except OSError:
        pass
    found.sort(key=lambda f: (f.stamp, f.path.name))
    return found


def select_for_zip(files: Iterable[SplitFile], weeks: int, now: float,
                   protected: set[str] = frozenset()) -> list[SplitFile]:
    """Plain splits older than *weeks*, but none of a protected session."""
    return [f for f in files
            if not f.zipped and f.stamp not in protected and f.older_than(weeks, now)]


def select_for_delete(files: Iterable[SplitFile], weeks: int, now: float,
                      protected: set[str] = frozenset()) -> list[SplitFile]:
    """Splits, plain or zipped, older than *weeks*, but none of a protected session."""
    return [f for f in files if f.stamp not in protected and f.older_than(weeks, now)]


def newest_stamp(files: Iterable[SplitFile]) -> str | None:
    return max((f.stamp for f in files), default=None)


def total_size(files: Iterable[SplitFile]) -> int:
    return sum(f.size for f in files)


@dataclass
class Plan:
    """What a run would do now: delete these, then zip those."""
    delete: list[SplitFile]
    zip: list[SplitFile]


def plan(files: list[SplitFile], zip_weeks: int | None, delete_weeks: int | None,
         now: float, protected: set[str]) -> Plan:
    """The one selection both a run and Settings' preview use."""
    protected = set(protected)
    newest = newest_stamp(files)
    if newest:
        protected.add(newest)
    delete = select_for_delete(files, delete_weeks, now, protected) if delete_weeks else []
    gone = {f.path for f in delete}
    zipping = ([f for f in select_for_zip(files, zip_weeks, now, protected) if f.path not in gone]
               if zip_weeks else [])
    return Plan(delete=delete, zip=zipping)


def _stamp_date(stamp: str) -> str:
    when = datetime.strptime(stamp, _STAMP_FORMAT)
    return f"{when.day} {when:%b %Y}"


@dataclass
class DeleteSummary:
    """The splits a change would delete, for the preview and the question."""
    count: int
    size: int
    first: str                    # "3 Jan 2026", the oldest session's date
    last: str
    groups: list[tuple[str, int, int]]   # (zone and difficulty, sessions, bytes), largest first
    names: list[str]


def summarize(files: list[SplitFile]) -> DeleteSummary:
    groups: dict[str, list] = {}
    for f in files:
        label = f"{f.zone} (vet)" if f.vet else f.zone
        entry = groups.setdefault(label, [0, 0])
        entry[0] += 1
        entry[1] += f.size
    ordered = sorted(((label, n, size) for label, (n, size) in groups.items()),
                     key=lambda g: (-g[2], g[0]))
    stamps = sorted(f.stamp for f in files)
    return DeleteSummary(count=len(files), size=total_size(files),
                         first=_stamp_date(stamps[0]) if stamps else "",
                         last=_stamp_date(stamps[-1]) if stamps else "",
                         groups=ordered, names=sorted(f.path.name for f in files))


def describe_deletion(summary: DeleteSummary, trash_name: str,
                      shown_groups: int = 12) -> tuple[str, str, str]:
    """(question, details, every file) for the confirmation."""
    noun = "log" if summary.count == 1 else "logs"
    question = (f"Move {summary.count} split {noun} ({format_bytes(summary.size)}) "
                f"to the {trash_name}?")
    lines = [f"Sessions from {summary.first} to {summary.last}:"]
    for label, sessions, size in summary.groups[:shown_groups]:
        word = "session" if sessions == 1 else "sessions"
        lines.append(f"    {label} — {sessions} {word}, {format_bytes(size)}")
    hidden = summary.groups[shown_groups:]
    if hidden:
        rest = sum(g[1] for g in hidden)
        lines.append(f"    and {len(hidden)} more zones, {rest} sessions")
    lines.append("")
    lines.append(f"To keep one, move it into the {KEEP_FOLDER} folder inside the split "
                 "folder first. The newest session's split is always kept. After this, "
                 "the same happens once a day without asking.")
    return question, "\n".join(lines), "\n".join(summary.names)


def zip_member(zip_path: Path) -> str:
    """The log a split's zip holds: its own name without ``.zip``."""
    return zip_path.name[:-len(".zip")]


def zipped_log_size(zip_path: Path) -> int | None:
    """The size of the log inside a split's zip (central directory only)."""
    try:
        with zipfile.ZipFile(zip_path) as zf:
            return zf.getinfo(zip_member(zip_path)).file_size
    except (OSError, KeyError, zipfile.BadZipFile):
        return None


def latest_session_stamp(log_path: Path | None) -> str | None:
    """The stamp the splitter gives the live log's newest session, if any."""
    if log_path is None:
        return None
    from esolog_tail import find_session_start_offset  # it imports this module
    try:
        end = Path(log_path).stat().st_size
        offset = find_session_start_offset(Path(log_path), end, _LATEST_SESSION_LOOKBACK)
        if offset is None:
            return None
        with open(log_path, "rb") as f:
            f.seek(offset)
            parts = f.readline().decode("utf-8", errors="ignore").split(",")
        if len(parts) < 3 or parts[1] != "BEGIN_LOG":
            return None
        return datetime.fromtimestamp(int(parts[2]) / 1000).strftime(_STAMP_FORMAT)
    except (OSError, ValueError):
        return None


def clean_partials(split_dir: Path) -> int:
    """Remove zips an interrupted run left half-written; returns how many."""
    removed = 0
    try:
        with os.scandir(split_dir) as it:
            for entry in it:
                if _PARTIAL.match(entry.name) and entry.is_file(follow_symlinks=False):
                    try:
                        os.remove(entry.path)
                        removed += 1
                    except OSError:
                        pass
    except OSError:
        pass
    return removed


@dataclass
class ZipResult:
    kind: str              # "zipped", "copy" (log removed, same zip there), "skipped"
    path: Path
    saved: int = 0         # bytes freed on disk
    reason: str = ""


def _same_log(zip_path: Path, log_path: Path) -> bool:
    """True when the zip already holds exactly this log (size and CRC)."""
    try:
        with zipfile.ZipFile(zip_path) as zf:
            info = zf.getinfo(zip_member(zip_path))
        if info.file_size != log_path.stat().st_size:
            return False
        crc = 0
        with open(log_path, "rb") as f:
            while chunk := f.read(_CHUNK_SIZE):
                crc = zlib.crc32(chunk, crc)
        return crc == info.CRC
    except (OSError, KeyError, zipfile.BadZipFile):
        return False


def zip_split(log_path: Path, cancel: threading.Event | None = None) -> ZipResult:
    """Zip one split beside itself and remove the log once the zip reads
    back whole. Never raises for an expected failure; Cancelled leaves the
    log in place and no zip behind."""
    log_path = Path(log_path)
    target = log_path.with_name(log_path.name + ".zip")
    try:
        stat = log_path.stat()
    except OSError as exc:
        return ZipResult("skipped", log_path, reason=str(exc))
    if target.exists():
        if _same_log(target, log_path):
            try:
                log_path.unlink()
            except OSError as exc:
                return ZipResult("skipped", log_path, reason=f"could not remove the copy: {exc}")
            return ZipResult("copy", log_path, saved=stat.st_size)
        return ZipResult("skipped", log_path,
                         reason=f"a different {target.name} is already there")

    partial = target.with_name(target.name + PARTIAL_SUFFIX)
    try:
        with zipfile.ZipFile(partial, "w", zipfile.ZIP_DEFLATED, compresslevel=6,
                             allowZip64=True) as zf:
            info = zipfile.ZipInfo(log_path.name,
                                   date_time=time.localtime(stat.st_mtime)[:6])
            info.compress_type = zipfile.ZIP_DEFLATED
            with open(log_path, "rb") as source, zf.open(info, "w", force_zip64=True) as dest:
                while chunk := source.read(_CHUNK_SIZE):
                    if cancel is not None and cancel.is_set():
                        raise Cancelled()
                    dest.write(chunk)
        if not _verify(partial, log_path.name, stat.st_size, cancel):
            partial.unlink()
            return ZipResult("skipped", log_path, reason="the zip did not read back; log kept")
        os.utime(partial, (stat.st_atime, stat.st_mtime))
        partial.replace(target)
    except Cancelled:
        _remove_quietly(partial)
        raise
    except (OSError, zipfile.BadZipFile) as exc:
        _remove_quietly(partial)
        return ZipResult("skipped", log_path, reason=str(exc))

    # The log changed while it was zipped (the splitter still writing it):
    # keep it, and drop the zip that no longer matches
    try:
        current = log_path.stat()
        if (current.st_size, current.st_mtime) != (stat.st_size, stat.st_mtime):
            raise OSError("the log changed while it was zipped")
        log_path.unlink()
    except OSError as exc:
        _remove_quietly(target)
        return ZipResult("skipped", log_path, reason=f"log kept: {exc}")
    return ZipResult("zipped", log_path, saved=stat.st_size - target.stat().st_size)


def _verify(zip_path: Path, member: str, size: int,
            cancel: threading.Event | None) -> bool:
    """Read the member back in full: its CRC is checked as the read ends."""
    try:
        with zipfile.ZipFile(zip_path) as zf:
            if zf.getinfo(member).file_size != size:
                return False
            with zf.open(member) as f:
                while f.read(_CHUNK_SIZE):
                    if cancel is not None and cancel.is_set():
                        raise Cancelled()
        return True
    except (OSError, KeyError, zipfile.BadZipFile):
        return False


def _remove_quietly(path: Path) -> None:
    try:
        path.unlink()
    except OSError:
        pass


@dataclass
class RetentionSettings:
    split_dir: Path | None
    log_path: Path | None
    zip_weeks: int | None            # None: zipping is off
    delete_weeks: int | None = None  # None: deleting is off

    @property
    def active(self) -> bool:
        return self.split_dir is not None and (self.zip_weeks is not None
                                               or self.delete_weeks is not None)


def resolve_log(log_path_value) -> Path | None:
    """The configured log, or the auto-detected one (app_startup's rule)."""
    if log_path_value:
        return Path(log_path_value)
    from esolog_tail import _find_eso_log_file  # it imports this module
    return _find_eso_log_file()


def split_folder(split_dir_value, log_path: Path | None) -> Path | None:
    """The split folder: the one set, else the log's own (the splitter's rule)."""
    if split_dir_value:
        return Path(split_dir_value)
    return Path(log_path).parent if log_path is not None else None


def format_bytes(size: int) -> str:
    if size >= 1024 ** 3:
        return f"{size / 1024 ** 3:.1f} GB"
    if size >= 1024 ** 2:
        return f"{size / 1024 ** 2:.0f} MB"
    return f"{size / 1024:.0f} KB"


def settings_from_config(config) -> RetentionSettings:
    """The folder and ages Settings chose."""
    log_path = resolve_log(config.get("log_path"))
    split_dir = split_folder(config.get("split.dir"), log_path)
    zip_weeks = (int(config.get("split.zip_after_weeks", 4) or 4)
                 if config.get("split.zip_enabled", False) else None)
    delete_weeks = (int(config.get("split.delete_after_weeks", 52) or 52)
                    if config.get("split.delete_enabled", False) else None)
    if delete_weeks is not None and zip_weeks is not None and delete_weeks <= zip_weeks:
        delete_weeks = zip_weeks + 1  # a split is zipped before it can be deleted
    return RetentionSettings(split_dir=split_dir, log_path=log_path, zip_weeks=zip_weeks,
                             delete_weeks=delete_weeks)


@dataclass
class RetentionEvent:
    """What a run is doing, for the status bar.

    kind: "started" (total files), "progress" (done of total, name, and
    action: "delete" or "zip"), "completed" (the counts), "failed" (reason).
    """
    kind: str
    done: int = 0
    total: int = 0
    name: str = ""
    action: str = ""
    zipped: int = 0
    saved: int = 0
    deleted: int = 0
    freed: int = 0
    skipped: list[str] = field(default_factory=list)
    reason: str = ""


def run_retention(settings: RetentionSettings,
                  notify: Callable[[RetentionEvent], None],
                  cancel: threading.Event | None = None,
                  now: float | None = None,
                  trash: Callable[[Path], None] | None = None) -> RetentionEvent | None:
    """One run: delete what is due, then zip what is due. Returns the
    "completed" event, or None when there was nothing to do or the run was
    cancelled. *trash* moves one file to the Recycle Bin (recycle_bin's, by
    default)."""
    if trash is None:
        from recycle_bin import move_to_trash as trash
    if not settings.active or not settings.split_dir.is_dir():
        return None
    now = time.time() if now is None else now
    clean_partials(settings.split_dir)
    try:
        (settings.split_dir / KEEP_FOLDER).mkdir(exist_ok=True)
    except OSError:
        pass
    latest = latest_session_stamp(settings.log_path)
    work = plan(scan_splits(settings.split_dir), settings.zip_weeks, settings.delete_weeks,
                now, {latest} if latest else set())
    steps = [("delete", f) for f in work.delete] + [("zip", f) for f in work.zip]
    if not steps:
        return None
    done = RetentionEvent("completed", total=len(steps))
    notify(RetentionEvent("started", total=len(steps)))
    try:
        for index, (action, split) in enumerate(steps):
            if cancel is not None and cancel.is_set():
                return None
            notify(RetentionEvent("progress", done=index, total=len(steps),
                                  name=split.path.name, action=action))
            if action == "delete":
                try:
                    trash(split.path)
                except OSError as exc:
                    done.skipped.append(f"{split.path.name}: {exc}")
                else:
                    done.deleted += 1
                    done.freed += split.size
                continue
            result = zip_split(split.path, cancel)
            if result.kind == "skipped":
                done.skipped.append(f"{split.path.name}: {result.reason}")
            else:
                done.zipped += 1
                done.saved += result.saved
    except Cancelled:
        return None
    done.done = len(steps)
    notify(done)
    return done


class RetentionRunner:
    """Runs run_retention on a thread of its own, one run at a time."""

    def __init__(self):
        self._thread: threading.Thread | None = None
        self._cancel = threading.Event()

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self, settings: RetentionSettings,
              notify: Callable[[RetentionEvent], None]) -> bool:
        """Start a run unless one is going or there is nothing to do."""
        if self.running or not settings.active:
            return False
        self._cancel = threading.Event()
        cancel = self._cancel

        def run():
            try:
                run_retention(settings, notify, cancel)
            except Exception as exc:  # a run must never take the app down
                notify(RetentionEvent("failed", reason=f"{type(exc).__name__}: {exc}"))

        self._thread = threading.Thread(target=run, name="split-retention", daemon=True)
        self._thread.start()
        return True

    def wait(self, timeout: float | None = None) -> None:
        if self._thread is not None:
            self._thread.join(timeout)

    def stop(self, timeout: float = 10.0) -> None:
        """Ask a run to stop and wait for it (it stops within one chunk)."""
        self._cancel.set()
        self.wait(timeout)
