"""
Opening a log for review: a plain log, a split the retention job zipped
(``<stem>.log.zip``, issue #86) or an archive the log archiver wrote
(``Encounter-*.zip``).

A zip is read as a stream through its member, never extracted to disk or
read whole into memory: an archive can hold a log of more than a gigabyte.
The size reported for progress is the member's own, since the zip's is
about a sixteenth of it. A zip is recognised by its content, not its name.
"""

import io
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO, TextIO

# A zip member is read through a buffer this size: iterating the member's
# own stream line by line is about 70% slower than reading it as text
MEMBER_BUFFER = 1 << 20


class NoLogInZip(ValueError):
    """The zip holds no log, or several and none was chosen."""


def is_zip(path: Path) -> bool:
    try:
        return zipfile.is_zipfile(path)
    except OSError:
        return False


def log_members(path: Path) -> list[str]:
    """The ``.log`` files in a zip, in archive order."""
    with zipfile.ZipFile(path) as zf:
        return [info.filename for info in zf.infolist()
                if not info.is_dir() and info.filename.lower().endswith(".log")]


def log_size(path: Path, member: str | None = None) -> int:
    """The log's own size in bytes: the file's, or in a zip its member's
    (its only log when *member* is None; NoLogInZip when that is unclear)."""
    path = Path(path)
    if not is_zip(path):
        return path.stat().st_size
    with zipfile.ZipFile(path) as zf:
        if member is None:
            members = log_members(path)
            if len(members) != 1:
                raise NoLogInZip(f"{path.name} holds no encounter log" if not members
                                 else f"{path.name} holds {len(members)} logs; choose one")
            member = members[0]
        return zf.getinfo(member).file_size


def _member(zf: zipfile.ZipFile, path: Path, member: str | None) -> tuple[zipfile.ZipInfo, str]:
    """The zip's log *member* (its only one when None) and the name to
    show for it."""
    members = log_members(path)
    if member is None:
        if len(members) != 1:
            raise NoLogInZip(f"{path.name} holds no encounter log" if not members
                             else f"{path.name} holds {len(members)} logs; choose one")
        member = members[0]
    label = str(path) if len(members) == 1 else f"{path} › {member}"
    return zf.getinfo(member), label


@contextmanager
def open_log_text(path: Path, member: str | None = None
                  ) -> Iterator[tuple[TextIO, int, str]]:
    """(text stream, size in bytes, name to show) for a log or a zipped one.

    In a zip, *member* picks the log; without it the zip must hold exactly
    one, or NoLogInZip is raised.
    """
    path = Path(path)
    if not is_zip(path):
        with open(path, encoding="utf-8", errors="ignore") as f:
            yield f, path.stat().st_size, str(path)
        return
    with zipfile.ZipFile(path) as zf:
        info, label = _member(zf, path, member)
        with zf.open(info) as raw, io.TextIOWrapper(raw, encoding="utf-8", errors="ignore") as f:
            yield f, info.file_size, label


@contextmanager
def open_log_bytes(path: Path, member: str | None = None
                   ) -> Iterator[tuple[BinaryIO, int, str]]:
    """(byte stream, size in bytes, name to show) for a log or a zipped one,
    as open_log_text, for a reader that counts each line's bytes: a zip's
    member is a byte copy of its log, so its offsets are the log's own
    (fight_locator)."""
    path = Path(path)
    if not is_zip(path):
        with open(path, "rb") as f:
            yield f, path.stat().st_size, str(path)
        return
    with zipfile.ZipFile(path) as zf:
        info, label = _member(zf, path, member)
        with zf.open(info) as raw, io.BufferedReader(raw, MEMBER_BUFFER) as f:
            yield f, info.file_size, label
