"""
Recent activity: the newest archives of Encounter.log and the newest split
logs, for the window to show while the fight list is empty (issue #191).

Why. At a quiet start the fight list is empty, the pane said only
"Monitoring for encounters…" or "Waiting for Encounter.log…", and the status
bar "No log file" in red; meanwhile the app had just archived the log, and
with *Delete Encounter.log after a verified archive* on, removed it. A
reader could not tell "the app did its job and is waiting" from "something
went wrong and my logs are gone". So the pane names the newest archive and
when it was made, and offers the recent archives and splits, each of which
opens for review.

Which files. The archiver's own, ``Encounter-YYMMDDHHMMSS[-N].zip``
(log_archiver.LogArchiver._archive_target), in the archive folder: the one
set in Settings, else the log's folder, the archiver's rule. The splitter's
own, plain or zipped (split_retention.scan_splits: never a ``-temp.log``
still waiting for its zone, never another tool's files), in the split
folder, the one set in Settings, else the log's folder. Nothing is opened:
a scan is a directory listing, so it can run on the UI thread at every
redraw of the pane.

Which time. An archive shows when it was made, the file's own time, since
"archived at" is what the reader wants to know; the stamp in its name is
the log's newest entry (the archiver names it so), shown beside it as "its
last entry". Archives are ordered by the time they were made. A split shows
its session's start, the stamp in its name, and the splits are ordered by
that stamp, not by file time: the splitter writes some old sessions out
again long after they were played (issue #85; 433 of 899 files in the
maintainer's folder were more than two days off), and by file time an old
evening would head the list.
"""

import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from split_retention import SplitFile, scan_splits

# How many of each the pane lists
RECENT_COUNT = 5

_STAMP_FORMAT = "%y%m%d%H%M%S"
_ARCHIVE_NAME = re.compile(r"^Encounter-(\d{12})(?:-\d+)?\.zip$")


@dataclass(frozen=True)
class ArchiveFile:
    """One archive the log archiver wrote."""
    path: Path
    made: datetime          # when the archive was written (the file's time)
    last_entry: datetime | None  # the log's newest entry, from the name's stamp
    size: int               # bytes on disk


@dataclass
class RecentActivity:
    """The newest archives and splits, newest first, RECENT_COUNT of each
    at most; how many there are in all and their bytes on disk, which the
    page shows in place of the folders (a worried reader wants "how much",
    and the full path is on each file's hover); the folders they were
    looked for in (None: unknown)."""
    archives: list[ArchiveFile] = field(default_factory=list)
    splits: list[SplitFile] = field(default_factory=list)
    archive_count: int = 0
    archive_bytes: int = 0
    split_count: int = 0
    split_bytes: int = 0
    archive_dir: Path | None = None
    split_dir: Path | None = None

    @property
    def newest_archive(self) -> ArchiveFile | None:
        return self.archives[0] if self.archives else None

    def __bool__(self) -> bool:
        return bool(self.archives or self.splits)


def parse_archive_stamp(name: str) -> str | None:
    """The YYMMDDHHMMSS stamp of an archiver's file name, else None."""
    match = _ARCHIVE_NAME.match(name)
    if match is None:
        return None
    stamp = match.group(1)
    try:
        datetime.strptime(stamp, _STAMP_FORMAT)
    except ValueError:
        return None
    return stamp


def archive_folder(archive_dir_value, log_path: Path | None) -> Path | None:
    """The archive folder: the one set, else the log's own (the archiver's rule)."""
    if archive_dir_value:
        return Path(archive_dir_value)
    return Path(log_path).parent if log_path is not None else None


def scan_archives(folder: Path | None) -> list[ArchiveFile]:
    """The archiver's files directly in *folder*, newest made first."""
    found = []
    if folder is None:
        return found
    try:
        with os.scandir(folder) as it:
            for entry in it:
                stamp = parse_archive_stamp(entry.name)
                if stamp is None:
                    continue
                try:
                    if entry.is_symlink() or not entry.is_file():
                        continue
                    stat = entry.stat()
                except OSError:
                    continue
                found.append(ArchiveFile(
                    path=Path(entry.path), made=datetime.fromtimestamp(stat.st_mtime),
                    last_entry=datetime.strptime(stamp, _STAMP_FORMAT), size=stat.st_size))
    except OSError:
        pass
    found.sort(key=lambda a: (a.made, a.path.name), reverse=True)
    return found


def recent_splits(folder: Path | None) -> list[SplitFile]:
    """The splitter's files in *folder*, newest session first."""
    if folder is None:
        return []
    files = scan_splits(folder)  # sorted by stamp, oldest first
    files.reverse()
    return files


def split_time(split: SplitFile) -> datetime:
    """The session's start, from the split's name."""
    return datetime.strptime(split.stamp, _STAMP_FORMAT)


def scan(archive_dir: Path | None, split_dir: Path | None,
         count: int = RECENT_COUNT) -> RecentActivity:
    """The *count* newest archives and splits in the two folders, which may
    be the same folder (then each file is listed once, under its own kind),
    with the count and size of all of them."""
    archives = scan_archives(archive_dir)
    splits = recent_splits(split_dir)
    return RecentActivity(archives=archives[:count], splits=splits[:count],
                          archive_count=len(archives),
                          archive_bytes=sum(a.size for a in archives),
                          split_count=len(splits), split_bytes=sum(s.size for s in splits),
                          archive_dir=archive_dir, split_dir=split_dir)


def format_when(when: datetime) -> str:
    """'2 Nov 2026, 21:14': the day first, as Settings' retention question
    writes dates, with the time of day."""
    return f"{when.day} {when:%b %Y}, {when:%H:%M}"
