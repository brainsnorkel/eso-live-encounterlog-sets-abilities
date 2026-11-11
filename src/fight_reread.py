"""
Re-reading one fight's unit states from disk (issue #214), for a view that
shows the fight paused at a moment: where everyone stood, with their health
and pools. The engine keeps no unit's place for a whole session. It keeps a
locator on each fight's entry (fight_locator), and this module reads that
fight's lines back by it. No Qt, and the engine is never imported.

What it reads. Unit states, and the maps they are drawn on. A state is the
ten fields the log writes for a unit: its id, health, magicka, stamina,
ultimate, werewolf and shield, then its place and heading. They are read
where the engine reads them: the source and target of COMBAT_EVENT,
EFFECT_CHANGED and BEGIN_CAST, and HEALTH_REGEN's unit. Three are skipped.
A target of ``*`` is the source again. Unit id 0 is no unit. The 1/1
placeholder (health 1 of 1 at place 0, 0) is what the log writes for a unit
it knows nothing about. A member far off the map, in another zone or
instance, is kept as written; on_map tells such a place. Casts are not
read. The game hands a cast's track id on to later casts, so a second count
would disagree with the engine's, and the cast rule is the casts step's.

The range. It runs from LEAD_MS before BEGIN_COMBAT to TAIL_MS after
END_COMBAT: the opener's and the waiting hits' window before the fight and
the late-death grace after it (fight_locator). The group fighting on after
END_COMBAT (#162) is not in it, as the fight's clock, deaths and recaps
are not. The locator stores no range. The reader reads back from
the BEGIN_COMBAT line to the first line whose time is start - LEAD_MS or
later. It never reads past the zone's ZONE_CHANGED line, where unit ids
start over, or the session's BEGIN_LOG, and a ZONE_CHANGED met in the
lead-in drops what was read before it. It reads on past END_COMBAT to the
first line later than end + TAIL_MS. It stops early at the next
BEGIN_COMBAT, ZONE_CHANGED, BEGIN_LOG or END_LOG: the next fight's
BEGIN_COMBAT came within the tail in 801 of the 8,932 fights of the 391
split logs. A fight the game
cut in two is read whole, its first END_COMBAT and second BEGIN_COMBAT
included. When the bytes end first, as in a live log, the read ends there
with tail_seen False, and a last line still being written is not read.

Finding and checking the bytes. The places are tried in order: the
reviewed file and the session's splits by its stamp (session_splits),
plain before zipped (a zip's member streams from its start and cannot
seek); the live log among the plain files when the line at the engine's
hint, or its first line, is the session's BEGIN_LOG, else after them all,
since it would be searched back whole; then the archives. In each the
session's BEGIN_LOG is found: at offset 0 in
a split, at the engine's hint in the live log, else by a search back from
the end for its exact token ``,BEGIN_LOG,<unix ms>,``. The offsets are then
checked before they are trusted. That line must be the session's BEGIN_LOG,
the line at the BEGIN_COMBAT offset must be exactly ``<start>,BEGIN_COMBAT``,
and the line at the zone offset a ZONE_CHANGED. A split written before
0.19.0 lacks the lines the parser rejects, a median 7.7 KB before a fight,
so offsets from the live log land late in it. When no place passes, each
place holding the session is searched by time: a bisection on line times
in a plain file (times never go back within a session), one pass over a
zip's member. A fight with no BEGIN_COMBAT line, in a session that opens
mid-fight, is always found by time. found_by says which way it went.

Who is who. Identity is the engine's, frozen in the locator's unit table;
nothing here works it out again. A unit id at a time names the table row
that lists the id and whose window, since_ms to until_ms with both ends
in, holds the time. The latest arrival wins, so an id the game handed to a
new unit names each unit in turn. All of a row's ids make one track, so a
player back on a new unit id stays one track. An id that names no row at
that time gets an unknown track of its own: anchors, hazards, objects whose
UNIT_ADDED the parser rejects.

Frames. The log's coordinates are fractions of the map last named by a
MAP_CHANGED line. Frame 0 is the map the locator names for the lead-in's
start, and each MAP_CHANGED line in the range starts the next frame, in
file order: states written after the line, even in its millisecond, are of
the new map.

What it keeps. Each track keeps one state a millisecond, the last line of
the millisecond winning (a damage line shows the health after its own
hit), and drops a state equal to the one before, keeping instead when it
was last written (seen). A unit standing still at full pools is written
again and again unchanged, so the time of its state is not when the log
last said where it was: over seven boss fights of Kyne's Aegis and
Sanity's Edge, 25 to 88% of the player-seconds whose state was over a
second old had a line for that player within the second, and every one in
Sanity's Edge's lead-ins did. So a moment's age counts from seen, and a
unit is stale only when no line has written it. The states are packed in
columns: time, place, heading, health, magicka and stamina with their
maxima, ultimate, shield, frame and seen. Each column of all tracks is one
immutable bytes object read through read-only memoryviews, so a result is
cheap to hold and safe to hand from the reading thread to the UI.

Measured on the 21-split sample (846 MB, 545 fights;
scripts/check_fight_reread.py). The offsets held in all 545 fights, and
with every offset spoiled by 13 bytes all 545 were found by time with
identical states. Of 17,167 tracks built from the engine's own fields and
identity at each line, 17,154 were byte-identical. The other 13, in 8
fights, held 49 states of companions the engine had not yet linked to their
owner, which the table already names. Of 7.71 million state occurrences
the table named the engine's unit for all but those 49, and the owner for
all but 824 (0.011%): pets after their owner field dropped to 0, which the
table keeps and the engine forgets. A state costs 48 bytes, against 441 as
tuples; a 12-player boss fight's result is a median 609 KB, 2.2 MB at most
(46,368 states). Every fight of three splits zipped as split retention
zips them read the same from the zip, by offset and by time.

Read alone from its split, a 12-player boss fight took a median 95 ms by
offset (p90 229 ms, at most 402 ms for a 316 s Lord Falgravn kill) and 145
ms by time. That kill took 396 ms from a two-session live log with the
hint, 455 ms without it, and 643 ms from its zip, whose member streams from
its start to the fight 92 MB in. Reading in 4 MB chunks needs at most 19 MB
from a plain file and 27 MB from a zip. RereadRunner reads on a thread of
its own, not the review's, whose one job can run for minutes, and a cancel
is seen between chunks.
"""

from __future__ import annotations

import contextlib
import csv
import os
import threading
import zipfile
import zlib
from array import array
from bisect import bisect_right
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import NamedTuple

import log_open
import session_splits
from fight_locator import LEAD_MS, TAIL_MS, FightLocator, FightUnit, MapFrame

# A coordinate further than this outside 0..1 is not on its map: a member
# in another zone or instance, written as far fractions of this map
FAR_LIMIT = 4.0
# Bytes read at a time forward (a cancel is seen between them), back from
# BEGIN_COMBAT for the lead-in, and when searching or skipping
CHUNK = 4 << 20
BACK_CHUNK = 256 << 10
SCAN_CHUNK = 1 << 20
# Frame 0 when the locator names no map for the lead-in's start
UNKNOWN_MAP = MapFrame("", "", "")
# Every track's columns: (name, array typecode). *seen* is the time of the
# last line that wrote the state, its own or a repeat (see the module)
STATE_COLUMNS = (("t", "i"), ("x", "f"), ("y", "f"), ("heading", "f"), ("health", "i"),
                 ("health_max", "i"), ("magicka", "i"), ("magicka_max", "i"),
                 ("stamina", "i"), ("stamina_max", "i"), ("ultimate", "h"), ("shield", "i"),
                 ("frame", "H"), ("seen", "i"))
# Why a place did not give the fight
NOT_HERE = "session not in the file"
STALE = "offsets do not hold"
NO_BEGIN = "fight has no BEGIN_COMBAT line"
NO_FIGHT = "fight not found by time in the session"
NOT_KNOWN = "session not known (no BEGIN_LOG seen)"

_FOREVER = 1 << 62
_ZERO = b"0.0000"
_LEAD, _FIGHT, _TAIL = 0, 1, 2

# One state of a track, a row of STATE_COLUMNS
State = NamedTuple("State", [(name, float if code == "f" else int)
                             for name, code in STATE_COLUMNS])


class Cancelled(Exception):
    """The read was asked to stop."""


class NotOnDisk(Exception):
    """No place gave the fight; *reasons*: (place, why) for each tried."""

    def __init__(self, reasons: Sequence[tuple]):
        self.reasons = tuple(reasons)
        super().__init__("; ".join(f"{place.kind} {place.path.name}: {why}"
                                   for place, why in self.reasons) or "no place to read")


class _Stale(Exception):
    """A zip's BEGIN_COMBAT line was not at its offset."""


class Place(NamedTuple):
    """A file that may hold the fight: *kind* 'review', 'split', 'live' or
    'archive'; *member* a zip's log (its only one when None); *hint* the
    session's BEGIN_LOG offset in it, when known."""
    path: Path
    kind: str
    member: str | None = None
    hint: int | None = None


def places_for(locator: FightLocator, *, reviewed=None, member: str | None = None,
               split_dir=None, live_log=None, archives: Sequence = ()) -> list[Place]:
    """The places to try for the fight (see the module for their order):
    the reviewed file (with its zip *member*), the session's splits in
    *split_dir* by its stamp (the whole one first), the live log and the
    archives (``Encounter-*.zip``)."""
    hint = locator.session_offset
    found = [Place(Path(reviewed), "review", member, hint)] if reviewed else []
    if split_dir is not None and locator.session_stamp:
        found += [Place(split.path, "split", None, 0) for split in
                  session_splits.splits_for([locator.session_stamp], split_dir)[0].files]
    if live_log:
        found.append(Place(Path(live_log), "live", None, hint))
    found += [Place(Path(path), "archive", None, hint) for path in archives]
    unique: dict = {}
    for place in found:
        unique.setdefault((os.path.normcase(os.path.abspath(place.path)), place.member), place)

    def rank(place: Place) -> int:
        zipped = log_open.is_zip(place.path)
        if place.kind in ("review", "split"):
            return 1 if zipped else 0
        return 0 if not zipped and _holds_at_hint(place, locator.session_epoch_ms) else 2

    return sorted(unique.values(), key=rank)


def _holds_at_hint(place: Place, epoch: int | None) -> bool:
    """Whether a plain file's line at the place's hint, or its first line,
    is the session's BEGIN_LOG: two short reads, where a miss would cost a
    search back through the whole file."""
    if epoch is None:
        return False
    try:
        with open(place.path, "rb") as f:
            return any(_is_session(_line_at(f, at), epoch)
                       for at in dict.fromkeys((place.hint, 0)) if at is not None)
    except OSError:
        return False


def on_map(x: float, y: float) -> bool:
    """Whether a place can be drawn on its frame (see FAR_LIMIT)."""
    return -FAR_LIMIT <= x <= 1 + FAR_LIMIT and -FAR_LIMIT <= y <= 1 + FAR_LIMIT


# ------------------------------------------------------------ the result --

class _Table:
    """The unit table's ids, as bytes, to their rows' (since, until, row)."""

    def __init__(self, units: Sequence[FightUnit]):
        rows: dict[bytes, list] = {}
        for index, unit in enumerate(units):
            window = (-_FOREVER if unit.since_ms is None else unit.since_ms,
                      _FOREVER if unit.until_ms is None else unit.until_ms, index)
            for unit_id in unit.ids:
                rows.setdefault(str(unit_id).encode("ascii", "replace"), []).append(window)
        # Most ids name one row: one lookup and its window
        self.single = {uid: found[0] for uid, found in rows.items() if len(found) == 1}
        self.rows = rows

    def row(self, uid: bytes, t: int) -> int | None:
        """The row *uid* names at *t*, None when none does."""
        best = None
        for since, until, index in self.rows.get(uid, ()):
            if since <= t <= until and (best is None or since >= best[0]):
                best = (since, index)
        return None if best is None else best[1]


class Track:
    """One unit's states: *unit* its FightUnit row (None for an unknown
    unit), *ids* the unit ids it holds, and a read-only memoryview for each
    of STATE_COLUMNS (track.t, track.x, ...)."""
    __slots__ = ("_columns", "_hi", "_lo", "_row", "ids", "unit")

    def __init__(self, unit, ids, row, columns, lo, hi):
        self.unit, self.ids, self._row = unit, ids, row
        self._columns, self._lo, self._hi = columns, lo, hi

    def __len__(self) -> int:
        return self._hi - self._lo

    def at(self, t_ms: int) -> int:
        """The index of the last state at or before *t_ms*, -1 if none."""
        return bisect_right(self.t, t_ms) - 1

    def row(self, index: int) -> State:
        if not 0 <= index < len(self):
            raise IndexError(index)
        return State(*(self._columns[name][self._lo + index] for name, _code in STATE_COLUMNS))


for _name, _code in STATE_COLUMNS:
    setattr(Track, _name, property(lambda self, name=_name: self._columns[name][self._lo:self._hi]))


class FightStates:
    """A fight re-read, immutable. *tracks*: one per table row that has
    states, in the table's order, then the unknown units by first sight;
    *frames*: a MapFrame per frame index; *found_by*: 'offset' or 'scan';
    *source*: the file read; *range_start_ms*: the time of the range's
    first line; *tail_seen*: whether the read ended at the tail's end
    rather than the bytes'."""

    def __init__(self, locator, table, tracks, columns, frames, **about):
        self.locator, self.start_ms, self.end_ms = locator, locator.start_ms, locator.end_ms
        self.tracks, self.frames = tuple(tracks), tuple(frames)
        self.found_by = self.source = self.range_start_ms = self.tail_seen = None
        self.lines = self.skipped = self.bytes_read = 0
        self.__dict__.update(about)
        self._table, self._columns = table, columns
        self._by_row = {track._row: track for track in self.tracks if track._row >= 0}
        self._unknown = {track.ids[0].encode("ascii", "replace"): track
                         for track in self.tracks if track._row < 0}

    @property
    def state_count(self) -> int:
        return len(self._columns["t"])

    def track_of(self, unit_id, t_ms: int | None = None) -> Track | None:
        """The track *unit_id* is part of at *t_ms* (see the module); with
        no time, that of the latest-arriving row naming it that has
        states, else its unknown track; None when it has no states."""
        uid = str(unit_id).encode("ascii", "replace")
        if t_ms is not None:
            row = self._table.row(uid, t_ms)
            return self._unknown.get(uid) if row is None else self._by_row.get(row)
        held = [(since, index) for since, _until, index in self._table.rows.get(uid, ())
                if index in self._by_row]
        return self._by_row[max(held)[1]] if held else self._unknown.get(uid)

    def moment(self, t_ms: int) -> list[tuple[Track, State, int]]:
        """(track, its last state at or before *t_ms*, the ms since a line
        last wrote that state, 0 when one wrote it at or after *t_ms*) for
        each track that has one."""
        found = []
        for track in self.tracks:
            index = track.at(t_ms)
            if index >= 0:
                state = track.row(index)
                found.append((track, state, t_ms - min(state.seen, t_ms)))
        return found

    def nbytes(self) -> int:
        """The bytes of every column."""
        return sum(view.nbytes for view in self._columns.values())


# ------------------------------------------------------------ extraction --

class _Builder:
    """A track's columns as read, and its state waiting for the rest of its
    millisecond: [t, frame, the nine raw fields after the unit id, the time
    of the last line that wrote it]."""
    __slots__ = ("columns", "last", "pending")

    def __init__(self):
        self.pending = self.last = None
        self.columns = [array(code) for _name, code in STATE_COLUMNS]


def _append(builder: _Builder, pending: list) -> bool:
    """Append *pending* unless it equals the last state, which then was
    seen as late as it was; False when its fields do not parse."""
    t, frame, raw, seen = pending
    columns = builder.columns
    if builder.last == (frame, raw):
        columns[-1][-1] = max(columns[-1][-1], seen)
        return True
    size = len(columns[0])
    try:
        hp, _, hp_max = raw[0].partition(b"/")
        mg, _, mg_max = raw[1].partition(b"/")
        st, _, st_max = raw[2].partition(b"/")
        for column, value in zip(columns, (
                t, float(raw[6]), float(raw[7]), float(raw[8]), int(hp), int(hp_max or 0),
                int(mg), int(mg_max or 0), int(st), int(st_max or 0),
                int(raw[3].partition(b"/")[0]), int(raw[5]), frame, seen)):
            column.append(value)
    except (ValueError, IndexError, OverflowError):
        for column in columns:
            del column[size:]
        return False
    builder.last = (frame, raw)
    return True


class _Extractor:
    """Reads the range from whole lines fed in file order: the lead-in up
    to the fight's BEGIN_COMBAT line (or, with none, its start time), the
    fight up to its END_COMBAT line, then the tail."""

    def __init__(self, locator: FightLocator, table: _Table):
        self.locator, self.table, self.rows = locator, table, len(locator.units)
        self.begin = None if locator.begin_offset is None else b"%d" % locator.start_ms
        self.end = b"%d" % locator.end_ms
        self.phase = _LEAD
        self.done = self.tail_seen = False
        self.lines = self.skipped = 0
        self.range_start_ms = None
        self.frames = [locator.map_at_lead or UNKNOWN_MAP]
        self.builders: dict = {}
        self.unknown: dict = {}

    def feed(self, data: bytes) -> bool:
        """The whole lines in *data*; False once the range is over."""
        if self.done:
            return False
        single, resolve, rows = self.table.single, self.table.row, self.rows
        builders, unknown, frame = self.builders, self.unknown, len(self.frames) - 1
        phase, first_ms, begin, end = self.phase, self.range_start_ms, self.begin, self.end
        start_ms, stop_after = self.locator.start_ms, self.locator.end_ms + TAIL_MS
        lines = data.splitlines()

        def state(t, parts, at):
            uid = parts[at]
            raw = parts[at + 1:at + 10]
            if uid == b"0" or (raw[0] == b"1/1" and raw[6] == _ZERO and raw[7] == _ZERO):
                return
            hit = single.get(uid)
            if hit is not None and hit[0] <= t <= hit[1]:
                index = hit[2]
            else:
                index = resolve(uid, t)
                if index is None:
                    index = unknown.get(uid)
                    if index is None:
                        index = unknown[uid] = rows + len(unknown)
            b = builders.get(index)
            if b is None:
                b = builders[index] = _Builder()
            pending = b.pending
            if pending is None:
                b.pending = [t, frame, raw, t]
            elif pending[1] != frame or raw != pending[2]:
                if pending[0] == t and pending[1] == frame:
                    pending[2], pending[3] = raw, t
                else:
                    if not _append(b, pending):
                        self.skipped += 1
                    b.pending = [t, frame, raw, t]
            else:
                pending[3] = t  # the same state written again

        for line in lines:
            parts = line.split(b",")
            head = parts[0]
            if not head.isdigit() or len(parts) < 2:
                self.skipped += bool(line)
                continue
            t = int(head)
            if t > stop_after:
                self.done = self.tail_seen = True
                break
            if first_ms is None:
                first_ms = t
            if phase == _LEAD and begin is None and t >= start_ms:
                phase = _FIGHT
            kind = parts[1]
            if kind == b"COMBAT_EVENT":
                if len(parts) >= 19:
                    state(t, parts, 9)
                if len(parts) >= 29 and parts[19] != b"*":
                    state(t, parts, 19)
            elif kind == b"EFFECT_CHANGED" or kind == b"BEGIN_CAST":
                if len(parts) >= 16:
                    state(t, parts, 6)
                if len(parts) >= 26 and parts[16] != b"*":
                    state(t, parts, 16)
            elif kind == b"HEALTH_REGEN":
                if len(parts) >= 13:
                    state(t, parts, 3)
            elif kind == b"MAP_CHANGED":
                fields = next(csv.reader([line.decode("utf-8", "replace")]))
                self.frames.append(MapFrame(*(fields[2:5] + ["", "", ""])[:3]))
                frame = len(self.frames) - 1
            elif kind == b"BEGIN_COMBAT":
                if phase == _LEAD and head == begin:
                    phase = _FIGHT
                elif phase == _TAIL:
                    self.done = self.tail_seen = True
                    break
            elif kind == b"END_COMBAT":
                if phase == _FIGHT and head == end:
                    phase = _TAIL
            elif kind == b"ZONE_CHANGED" and phase == _LEAD:
                # The lead-in crossed into this zone: what came before it
                # is the zone before's, whose unit ids start over here
                self.frames = [UNKNOWN_MAP]
                builders, unknown = self.builders, self.unknown = {}, {}
                frame, first_ms = 0, t
            elif kind in (b"ZONE_CHANGED", b"BEGIN_LOG", b"END_LOG") and not (
                    kind == b"BEGIN_LOG" and self.lines == 0 and line is lines[0]):
                # The session's own BEGIN_LOG may open the range; another
                # session or zone ends it (in the lead-in: no fight here)
                self.done = self.tail_seen = True
                break
        self.phase, self.range_start_ms = phase, first_ms
        self.lines += len(lines)
        return not self.done

    def finish(self, **about) -> FightStates:
        """The states read, frozen."""
        columns = {name: array(code) for name, code in STATE_COLUMNS}
        ids_of = {index: uid.decode("ascii", "replace") for uid, index in self.unknown.items()}
        tracks = []
        for index in sorted(self.builders):
            b = self.builders[index]
            if b.pending is not None and not _append(b, b.pending):
                self.skipped += 1
            if b.columns[0]:
                lo = len(columns["t"])
                for (name, _code), column in zip(STATE_COLUMNS, b.columns):
                    columns[name].extend(column)
                unit = self.locator.units[index] if index < self.rows else None
                tracks.append((unit, tuple(unit.ids) if unit else (ids_of[index],),
                               index if unit else -1, lo, len(columns["t"])))
        frozen = {name: memoryview(column.tobytes()).cast(column.typecode)
                  for name, column in columns.items()}
        return FightStates(self.locator, self.table,
                           [Track(*track[:3], frozen, *track[3:]) for track in tracks],
                           frozen, self.frames, range_start_ms=self.range_start_ms,
                           tail_seen=self.tail_seen, lines=self.lines, skipped=self.skipped,
                           **about)


def _pump(read, extractor: _Extractor, cancel, at: int, verify=None) -> int:
    """Feed *extractor* the whole lines *read* gives, from offset *at*,
    until the range or the bytes end (a last line without its newline is
    not read). *verify*: (offset, line), a line that must start at that
    offset, checked as the bytes pass it. The bytes read."""
    carry, total = b"", 0
    while True:
        _check(cancel)
        chunk = read(CHUNK)
        if not chunk:
            break
        total += len(chunk)
        data = carry + chunk
        cut = data.rfind(b"\n") + 1
        if verify is not None and verify[0] < at + cut:
            i, line = verify[0] - at, verify[1]
            if i < 0 or (i and data[i - 1] != 10) or not (
                    data.startswith(line + b"\r\n", i) or data.startswith(line + b"\n", i)):
                raise _Stale()
            verify = None
        carry, at = data[cut:], at + cut
        if cut and not extractor.feed(data[:cut]):
            break
    if verify is not None:
        raise _Stale()
    return total


def _check(cancel) -> None:
    if cancel is not None and cancel.is_set():
        raise Cancelled()


def _time(line: bytes) -> int | None:
    head = line[:24].split(b",", 1)[0]
    return int(head) if head.isdigit() else None


def _kind(line: bytes) -> bytes:
    parts = line.split(b",", 2)
    return parts[1].rstrip(b"\r\n") if len(parts) > 1 else b""


def _is_session(line: bytes, epoch: int) -> bool:
    parts = line.split(b",", 3)
    return (len(parts) > 3 and parts[0].isdigit() and parts[1] == b"BEGIN_LOG"
            and parts[2] == b"%d" % epoch)


# ---------------------------------------------------------- plain files --

def _line_at(f, offset: int) -> bytes:
    """The line that starts at *offset*, b'' when none does."""
    if offset < 0:
        return b""
    if offset:
        f.seek(offset - 1)
        if f.read(1) != b"\n":
            return b""
    f.seek(offset)
    return f.readline(4096)


def _find_base(f, hint: int | None, epoch: int, cancel=None) -> int | None:
    """The session's BEGIN_LOG line in a plain file: at the hint, the first
    line, or the last line holding its token, searched back from the end."""
    for guess in (hint, 0):
        if guess is not None and _is_session(_line_at(f, guess), epoch):
            return guess
    token = b",BEGIN_LOG,%d," % epoch
    end = pos = f.seek(0, 2)
    while pos > 0:
        _check(cancel)
        start = max(0, pos - SCAN_CHUNK)
        f.seek(start)
        # A token across the boundary is found, and one at pos not twice
        at = f.read(min(end, pos + len(token) - 1) - start).rfind(token)
        if at == -1:
            pos = start
            continue
        pos = start + at
        f.seek(max(0, pos - 64))
        head = f.read(pos - max(0, pos - 64))
        line = pos - len(head) + head.rfind(b"\n") + 1
        if _is_session(_line_at(f, line), epoch):
            return line
    return None


def _session_end(f, base: int, cancel=None) -> int:
    """The next BEGIN_LOG line after *base*, or the end of the file."""
    f.seek(base)
    data_at, carry = base + len(f.readline()), b""
    while chunk := f.read(SCAN_CHUNK):
        _check(cancel)
        data = carry + chunk
        at = data.find(b",BEGIN_LOG,")
        if at != -1:
            return data_at + data.rfind(b"\n", 0, at) + 1
        keep = data.rfind(b"\n") + 1
        data_at, carry = data_at + keep, data[keep:]
    return data_at + len(carry)


def _first_at(f, lo: int, hi: int, target: int) -> int:
    """The first line in [lo, hi) of time *target* or later (*hi* when
    none); *lo* is a line start and times never go back in between, so
    this bisects, then walks the last stretch."""
    while hi - lo > 65536:
        mid = (lo + hi) // 2
        f.seek(mid)
        pos = mid + len(f.readline())
        if pos >= hi:
            break
        line = f.readline()
        if (_time(line) or -1) >= target:
            hi = pos
        else:
            lo = pos + len(line)
    f.seek(lo)
    while lo < hi and (line := f.readline()):
        if (_time(line) or -1) >= target:
            return lo
        lo += len(line)
    return hi


def _find_begin(f, base: int, locator: FightLocator, cancel=None) -> int | None:
    """The fight's BEGIN_COMBAT line by time in the session at *base*, or
    with none its first line at its start."""
    end = _session_end(f, base, cancel)
    at = _first_at(f, base, end, locator.start_ms)
    if at >= end or locator.begin_offset is None:
        return None if at >= end else at
    f.seek(at)
    while at < end and _time(line := f.readline()) == locator.start_ms:
        if line.rstrip(b"\r\n") == b"%d,BEGIN_COMBAT" % locator.start_ms:
            return at
        at += len(line)
    return None


def _lead_start(f, floor: int, at: int, from_ms: int, cancel=None) -> int:
    """The first line in [floor, at] of time *from_ms* or later, read back
    from *at* in chunks; *floor* and *at* are line starts, at's own time
    late enough."""
    pos, back = at, BACK_CHUNK
    while pos > floor:
        _check(cancel)
        start = max(floor, pos - back)
        f.seek(start)
        data = f.read(pos - start)
        first = data.find(b"\n") + 1 if start > floor else 0
        if start > floor and first == len(data):
            # The chunk's only newline ends it: the line before pos is longer
            # than the chunk, so read further back
            back *= 2
            continue
        back = BACK_CHUNK
        offset = start + first
        for line in data[first:].split(b"\n")[:-1]:
            if (_time(line) or -1) >= from_ms:
                break
            offset += len(line) + 1
        if offset > start + first or start == floor:
            return offset
        pos = offset  # the chunk's first whole line is late enough: further back
    return floor


def _read_plain(place: Place, locator: FightLocator, table: _Table, cancel, scan: bool):
    with open(place.path, "rb") as f:
        base = _find_base(f, place.hint, locator.session_epoch_ms, cancel)
        if base is None:
            return None, NOT_HERE
        floor = base
        if scan:
            begin = _find_begin(f, base, locator, cancel)
            if begin is None:
                return None, NO_FIGHT
        elif locator.begin_offset is None:
            return None, NO_BEGIN
        else:
            begin = base + locator.begin_offset
            if _line_at(f, begin).rstrip(b"\r\n") != b"%d,BEGIN_COMBAT" % locator.start_ms:
                return None, STALE
            if locator.zone_offset is not None:
                floor = base + locator.zone_offset
                if floor > begin or _kind(_line_at(f, floor)) != b"ZONE_CHANGED":
                    return None, STALE
        start = _lead_start(f, floor, begin, locator.start_ms - LEAD_MS, cancel)
        f.seek(start)
        extractor = _Extractor(locator, table)
        read = _pump(f.read, extractor, cancel, start)
    if extractor.phase == _LEAD:
        return None, NO_FIGHT
    return extractor.finish(found_by="scan" if scan else "offset", source=str(place.path),
                            bytes_read=read), ""


# ------------------------------------------------------------------ zips --

class _Stream:
    """A zip's member read forward, its position counted, with bytes put
    back: a member cannot seek."""

    def __init__(self, f, cancel):
        self.f, self.cancel, self.pos, self.back = f, cancel, 0, b""

    def read(self, n: int) -> bytes:
        _check(self.cancel)
        if self.back:
            out, self.back = self.back[:n], self.back[n:]
        else:
            out = self.f.read(n)
        self.pos += len(out)
        return out

    def push(self, data: bytes) -> None:
        self.back = data + self.back
        self.pos -= len(data)

    def line(self) -> bytes:
        """The line at the position, which stays."""
        data = self.read(4096)
        self.push(data)
        return data.split(b"\n", 1)[0]

    def to_line(self, token: bytes, offset: int = 0) -> bool:
        """Stand at *offset*, or with a *token* at the first line holding
        it; False when the bytes end first."""
        carry = b""
        while not token and self.pos < offset:
            if not self.read(min(SCAN_CHUNK, offset - self.pos)):
                return False
        while token:
            chunk = self.read(SCAN_CHUNK)
            if not chunk:
                return False
            data = carry + chunk
            at = data.find(token)
            if at != -1:
                self.push(data[data.rfind(b"\n", 0, at) + 1:])
                return True
            carry = data[data.rfind(b"\n") + 1:]
        return self.pos == offset


def _skip_to_time(stream: _Stream, from_ms: int) -> bool:
    """From the session's BEGIN_LOG line, stand at the first line of time
    *from_ms* or later; False when the session or the bytes end first. A
    chunk whose last line is still too early is passed over whole: times
    never go back within a session."""
    carry, own = b"", True
    while chunk := stream.read(SCAN_CHUNK):
        data = carry + chunk
        cut = data.rfind(b"\n") + 1
        body, carry = data[:cut], data[cut:]
        later = body.find(b",BEGIN_LOG,", body.find(b"\n") + 1 if own and body else 0)
        own = own and not body
        limit = len(body) if later == -1 else body.rfind(b"\n", 0, later) + 1
        last = _time(body[body.rfind(b"\n", 0, limit - 1) + 1:limit]) if limit else None
        if later == -1 and (last is None or last < from_ms):
            continue
        at = _first_in(body, limit, from_ms)
        if at < limit:
            stream.push(body[at:] + carry)
            return True
        if later != -1:
            return False
    return False


def _first_in(data: bytes, end: int, from_ms: int) -> int:
    """The first line of *data*'s whole lines before *end* whose time is
    *from_ms* or later (*end* when none): a bisection, then a walk."""
    lo, hi = 0, end
    while hi - lo > 4096:
        at = data.find(b"\n", (lo + hi) // 2, hi) + 1
        if not at or at >= hi:
            break
        if (_time(data[at:at + 24]) or -1) >= from_ms:
            hi = at
        else:
            lo = at
    while lo < hi:
        if (_time(data[lo:lo + 24]) or -1) >= from_ms:
            return lo
        lo = data.find(b"\n", lo, hi) + 1 or hi
    return hi


def _read_zip(place: Place, locator: FightLocator, table: _Table, cancel, scan: bool):
    """The same from a zip's log member: at the hint, else searched from
    the member's start; the BEGIN_COMBAT line is checked as it passes."""
    epoch = locator.session_epoch_ms
    if not scan and locator.begin_offset is None:
        return None, NO_BEGIN
    for hint in ((place.hint, None) if place.hint else (None,)):
        with log_open.open_log_bytes(place.path, place.member) as (f, _size, label):
            stream = _Stream(f, cancel)
            if not (stream.to_line(b"" if hint else b",BEGIN_LOG,%d," % epoch, hint or 0)
                    and _is_session(stream.line(), epoch)):
                continue
            base = stream.pos
            verify = None if scan else (base + locator.begin_offset,
                                        b"%d,BEGIN_COMBAT" % locator.start_ms)
            if not _skip_to_time(stream, locator.start_ms - LEAD_MS):
                return None, NO_FIGHT if scan else STALE
            extractor = _Extractor(locator, table)
            try:
                _pump(stream.read, extractor, None, stream.pos, verify)
            except _Stale:
                return None, STALE
            if extractor.phase == _LEAD:
                return None, NO_FIGHT
            return extractor.finish(found_by="scan" if scan else "offset", source=label,
                                    bytes_read=stream.pos), ""
    return None, NOT_HERE


# --------------------------------------------------------------- reading --

def read_fight(locator: FightLocator, places: Sequence[Place],
               cancel: threading.Event | None = None) -> FightStates:
    """The fight's states from the first place whose offsets hold, else
    from the first place holding the session where it is found by time.
    Raises NotOnDisk when none gives it, Cancelled when *cancel* is set."""
    if locator.session_epoch_ms is None:
        raise NotOnDisk([(place, NOT_KNOWN) for place in places])
    table = _Table(locator.units)
    reasons: dict = {}
    held: list = []
    for scan in (False, True):
        for place in (held if scan else places):
            _check(cancel)
            try:
                reader = _read_zip if log_open.is_zip(place.path) else _read_plain
                states, why = reader(place, locator, table, cancel, scan)
            except FileNotFoundError:
                states, why = None, "no such file"
            except (OSError, zipfile.BadZipFile, log_open.NoLogInZip, EOFError,
                    zlib.error) as exc:
                states, why = None, f"unreadable ({exc})"
            if states is not None:
                return states
            reasons[place] = f"{reasons[place]}; {why}" if scan else why
            if why in (STALE, NO_BEGIN) and not scan:
                held.append(place)
    raise NotOnDisk(list(reasons.items()))


# ------------------------------------------------------------ the thread --

class RereadEvent(NamedTuple):
    """*kind*: 'loaded' (with *states*), 'missing' or 'failed' (with
    *error*), or 'cancelled'; *locator*: the request's, by which the
    receiver drops an answer it no longer wants."""
    kind: str
    locator: FightLocator
    states: FightStates | None = None
    error: str = ""


class RereadRunner:
    """Reads on one thread of its own, 'fight-reread', not the review
    runner's, which a review keeps busy for minutes. A request cancels the
    read running and replaces one waiting. The thread holds no Qt object:
    it reports through *notify*, called on it, which the window turns into
    a signal of an object on the UI thread."""

    def __init__(self):
        self._lock = threading.Condition()
        self._waiting = self._cancel = self._thread = None
        self._busy = self._closed = False

    def request(self, locator: FightLocator, places: Sequence[Place],
                notify: Callable[[RereadEvent], None]) -> None:
        with self._lock:
            if self._closed:
                raise RuntimeError("the runner is closed")
            self.cancel()
            self._waiting = (locator, tuple(places), notify)
            if self._thread is None:
                self._thread = threading.Thread(target=self._run, name="fight-reread",
                                                daemon=True)
                self._thread.start()
            self._lock.notify_all()

    def cancel(self) -> None:
        """Stop the read running, and drop one waiting."""
        with self._lock:
            self._waiting = None
            if self._cancel is not None:
                self._cancel.set()

    def wait(self, timeout: float | None = None) -> bool:
        """Until no read runs or waits; False on a timeout."""
        with self._lock:
            return self._lock.wait_for(lambda: not (self._waiting or self._busy), timeout)

    def close(self, timeout: float | None = None) -> None:
        """Cancel, and end the thread."""
        with self._lock:
            self._closed = True
            self.cancel()
            self._lock.notify_all()
        if self._thread is not None:
            self._thread.join(timeout)

    def _run(self) -> None:
        while True:
            with self._lock:
                self._lock.wait_for(lambda: self._waiting or self._closed)
                if self._closed:
                    return
                (locator, places, notify), self._waiting = self._waiting, None
                cancel = self._cancel = threading.Event()
                self._busy = True
            try:
                event = RereadEvent("loaded", locator, read_fight(locator, places, cancel))
            except Cancelled:
                event = RereadEvent("cancelled", locator)
            except NotOnDisk as exc:
                event = RereadEvent("missing", locator, error=str(exc))
            except Exception as exc:  # noqa: BLE001 - reported, never raised on the thread
                event = RereadEvent("failed", locator, error=f"{type(exc).__name__}: {exc}")
            try:
                # The thread outlives a receiver that fails (a window's
                # bridge already deleted raises RuntimeError)
                with contextlib.suppress(Exception):
                    notify(event)
            finally:
                # Nothing of the read is kept while the thread waits: the
                # loop's names would hold the last answer's states (up to
                # 2.2 MB for a boss fight) after its window dropped them
                event = locator = places = notify = cancel = None
                with self._lock:
                    self._busy = False
                    self._lock.notify_all()
